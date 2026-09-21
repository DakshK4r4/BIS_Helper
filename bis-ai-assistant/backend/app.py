import os
import json
import random
import uuid
import requests
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename

from database import (
    get_db,
    init_db,
    add_user_history,
    add_notification,
    create_session,
    get_user_by_session,
    get_user_watchlist,
    toggle_user_watchlist,
    get_complaints as db_get_complaints,
    investigate_complaint as db_investigate_complaint,
    get_real_dashboard_metrics
)
from ai_engine import process_ai_query
from compliance_engine import analyze_compliance
from document_engine import generate_summary, analyze_document_content
from document_processor import process_document


# ============================================================
# FLASK APP & SECURITY CONFIGURATION
# ============================================================

app = Flask(__name__)

# Restrict CORS to authorized origins
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "http://localhost:5000",
            "http://localhost:5001",
            "http://localhost:5501",
            "http://127.0.0.1:5000",
            "http://127.0.0.1:5001",
            "http://127.0.0.1:5501"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-User-Email"]
    }
})

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15 MB max file upload

ALLOWED_EXTENSIONS = {"pdf", "docx", "png", "jpg", "jpeg"}
ENV = os.getenv("FLASK_ENV", "development").lower()


# ============================================================
# HOME / FRONTEND STATIC PROXY
# ============================================================

FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))

@app.route("/")
def home():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return send_from_directory(FRONTEND_DIR, "index.html")
    return jsonify({
        "status": "success",
        "message": "BIS AI Assistant Backend is running",
        "server": "Flask"
    })

@app.route("/<path:filename>")
def static_proxy(filename):
    if filename.startswith("api/"):
        return jsonify({"error": "Endpoint not found"}), 404

    target_file = os.path.join(FRONTEND_DIR, filename)
    if os.path.exists(target_file):
        return send_from_directory(FRONTEND_DIR, filename)

    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return send_from_directory(FRONTEND_DIR, "index.html")

    return jsonify({"error": "File not found"}), 404


# ============================================================
# AUTHENTICATION & USER HELPERS
# ============================================================

def get_current_user():
    """
    Extract currently authenticated user from Bearer token (with session expiry validation).
    Accepts only a server-side session in production.  Header and demo
    identities are deliberately limited to local development/evaluation.
    """
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    if token:
        user = get_user_by_session(token)
        if user:
            return user

    email = request.headers.get("X-User-Email", "").strip() if ENV != "production" else ""
    conn = get_db()
    if email:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            conn.close()
            return dict(row)

    # In development/demo mode, provide the default evaluation demo officer
    if ENV != "production":
        row = conn.execute("SELECT * FROM users WHERE id = 'usr_officer_demo_01'").fetchone()
        conn.close()
        if row:
            return dict(row)

    conn.close()
    abort(401, description="Authentication is required.")


def is_officer_user(user):
    """Check if user has officer/auditor privileges."""
    role = (user.get("role") or "").lower()
    return any(k in role for k in ["officer", "admin", "auditor", "inspector"])


@app.route("/api/auth/google", methods=["POST"])
def auth_google():
    """
    Authenticate user using Google Identity Services ID token.
    Enforces signature verification via Google tokeninfo endpoint.
    """
    try:
        data = request.get_json(silent=True) or {}
        credential = data.get("credential", "").strip()

        if not credential:
            return jsonify({
                "success": False,
                "error": "Google credential token is required."
            }), 400

        user_info = None
        # Verify token remotely with Google OAuth endpoint
        try:
            res = requests.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}",
                timeout=5
            )
            if res.status_code == 200:
                user_info = res.json()
        except Exception as e:
            print("Google tokeninfo remote check notice:", e)

        if not user_info or "email" not in user_info:
            return jsonify({
                "success": False,
                "error": "Failed to verify Google authentication token."
            }), 401

        email = user_info.get("email", "").lower().strip()
        name = user_info.get("name", email.split("@")[0].capitalize())
        picture = user_info.get("picture", "")
        google_id = user_info.get("sub", "")
        user_id = f"usr_g_{google_id[-12:]}" if google_id else f"usr_{random.randint(100000, 999999)}"

        conn = get_db()
        existing = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            user_id = existing["id"]
            conn.execute("""
                UPDATE users
                SET name = ?, picture = ?
                WHERE id = ?
            """, (name, picture or existing["picture"], user_id))
        else:
            conn.execute("""
                INSERT INTO users (id, email, name, picture, role, auth_provider)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, email, name, picture, "Citizen / Industry User", "google"))
        conn.commit()

        user_row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        user_dict = dict(user_row)

        session_token = create_session(user_id, duration_hours=48)
        add_notification(user_id, "Welcome to BIS Sahayak", f"Signed in as {name} ({email}).", "info")
        add_user_history(user_id, "User Login", "Google Sign-In", f"Authenticated successfully as {email}")

        return jsonify({
            "success": True,
            "message": "Authentication successful.",
            "token": session_token,
            "user": user_dict
        })

    except Exception as error:
        print("GOOGLE AUTH ERROR:", error)
        return jsonify({
            "success": False,
            "error": "Authentication processing failed. Please try again."
        }), 500


@app.route("/api/auth/demo", methods=["POST"])
def auth_demo():
    """
    Developer / evaluation sign-in explicitly flagged for non-production environments.
    """
    try:
        if ENV == "production":
            return jsonify({"success": False, "error": "Demo authentication is disabled in production."}), 404
        data = request.get_json(silent=True) or {}
        email = data.get("email", "officer@bis.gov.in").lower().strip()
        name = data.get("name", "Raj Kumar").strip()
        role = data.get("role", "BIS Quality Assurance Officer").strip()

        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row:
            user_id = f"usr_demo_{random.randint(1000, 9999)}"
            conn.execute("""
                INSERT INTO users (id, email, name, picture, role, auth_provider)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, email, name, "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150", role, "demo"))
            conn.commit()
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

        user_dict = dict(row)
        conn.close()

        session_token = create_session(user_dict["id"], duration_hours=24)
        add_user_history(user_dict["id"], "User Login", "Demo Sign-In", f"Signed in as {name} ({role})")

        return jsonify({
            "success": True,
            "message": "Demo evaluation sign-in successful.",
            "token": session_token,
            "user": user_dict,
            "is_demo": True,
            "environment": "development"
        })

    except Exception as error:
        print("DEMO AUTH ERROR:", error)
        return jsonify({"success": False, "error": "Demo sign-in failed."}), 500


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    user = get_current_user()
    return jsonify({"success": True, "user": user})


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        conn = get_db()
        conn.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()

    return jsonify({"success": True, "message": "Logged out successfully."})


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "BIS AI Assistant API", "version": "2.0"})


# ============================================================
# AI ASSISTANT (HYBRID RETRIEVAL + GROUNDED RAG)
# ============================================================

@app.route("/api/ai/query", methods=["POST"])
def ai_query():
    try:
        data = request.get_json(silent=True) or {}
        query = data.get("query", "").strip()
        doc_context = data.get("document_context", None)
        doc_filename = data.get("document_filename", None)
        history = data.get("history") or data.get("conversation_history") or []

        if not query:
            return jsonify({"success": False, "error": "Query is required."}), 400

        result = process_ai_query(query, doc_context, doc_filename, conversation_history=history)
        result["success"] = True

        user = get_current_user()
        rec_std = result.get("recommended_standard")
        std_str = rec_std["is_number"] if rec_std else "General Guidance"
        ans_preview = result.get("answer", "")[:120] + "..." if len(result.get("answer", "")) > 120 else result.get("answer", "")

        add_user_history(
            user_id=user["id"],
            action_type="AI Query",
            title=query,
            description=f"{std_str}: {ans_preview}",
            meta={
                "standard": std_str,
                "confidence": result.get("confidence_score"),
                "confidence_numeric": result.get("confidence_numeric"),
                "model": result.get("model"),
                "document_attached": doc_filename
            }
        )

        return jsonify(result)

    except Exception as error:
        print("AI QUERY ERROR:", error)
        return jsonify({
            "success": False,
            "error": "AI service encountered an unexpected error. Please rephrase your query."
        }), 500


# ============================================================
# STANDARDS SEARCH & CATALOG
# ============================================================

@app.route("/api/standards", methods=["GET"])
def standards():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    industry = request.args.get("industry", "").strip()
    year = request.args.get("year", "").strip()
    status = request.args.get("status", "").strip()
    type_filter = request.args.get("type", "").strip() or request.args.get("certification", "").strip()
    sort_by = request.args.get("sort", "relevance").strip().lower()

    conn = get_db()
    sql = "SELECT * FROM standards WHERE 1=1"
    params = []

    if query:
        sql += """
            AND (
                is_number LIKE ?
                OR title LIKE ?
                OR description LIKE ?
                OR keywords LIKE ?
                OR category LIKE ?
                OR industry LIKE ?
            )
        """
        keyword = f"%{query}%"
        params.extend([keyword, keyword, keyword, keyword, keyword, keyword])

    if category and category not in ["Product Category", "All Categories"]:
        sql += " AND category = ?"
        params.append(category)

    if industry and industry not in ["Industry", "All Industries"]:
        sql += " AND industry = ?"
        params.append(industry)

    if year and year not in ["Year", "All Years"]:
        try:
            params.append(int(year))
            sql += " AND year = ?"
        except ValueError:
            pass

    if status and status not in ["Status", "All Statuses"]:
        sql += " AND status = ?"
        params.append(status)

    if type_filter and type_filter not in ["Type", "All Types"]:
        sql += " AND (certification = ? OR certification LIKE ?)"
        params.extend([type_filter, f"%{type_filter}%"])

    if sort_by == "newest":
        sql += " ORDER BY year DESC, id DESC"
    elif sort_by == "oldest":
        sql += " ORDER BY year ASC, id ASC"
    elif sort_by in ["title_asc", "a-z"]:
        sql += " ORDER BY title ASC"
    elif sort_by in ["title_desc", "z-a"]:
        sql += " ORDER BY title DESC"
    elif sort_by == "is_number":
        sql += " ORDER BY is_number ASC"
    else:
        sql += " ORDER BY year DESC, id DESC"

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    standards_list = [dict(row) for row in rows]
    return jsonify({
        "success": True,
        "count": len(standards_list),
        "standards": standards_list
    })


@app.route("/api/standards/<path:is_number>", methods=["GET"])
def standard_detail(is_number):
    conn = get_db()
    row = conn.execute("SELECT * FROM standards WHERE is_number = ?", (is_number,)).fetchone()
    if not row:
        clean_num = is_number.replace(" ", "")
        row = conn.execute("SELECT * FROM standards WHERE REPLACE(is_number, ' ', '') = ?", (clean_num,)).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Standard not found."}), 404

    return jsonify({"standard": dict(row)})


# ============================================================
# STANDARDS WATCHLIST (PERSISTENT BOOKMARKS PER USER)
# ============================================================

@app.route("/api/watchlist", methods=["GET"])
def get_watchlist_route():
    user = get_current_user()
    bookmarks = get_user_watchlist(user["id"])
    return jsonify({
        "success": True,
        "user_id": user["id"],
        "watchlist": bookmarks,
        "count": len(bookmarks)
    })


@app.route("/api/watchlist", methods=["POST"])
def toggle_watchlist_route():
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    is_number = data.get("is_number", "").strip()

    if not is_number:
        return jsonify({"success": False, "error": "is_number is required"}), 400

    is_bookmarked = toggle_user_watchlist(user["id"], is_number)
    return jsonify({
        "success": True,
        "is_number": is_number,
        "bookmarked": is_bookmarked,
        "message": f"{'Added to' if is_bookmarked else 'Removed from'} watchlist."
    })


@app.route("/api/watchlist/<path:is_number>", methods=["DELETE"])
def delete_watchlist_route(is_number):
    user = get_current_user()
    conn = get_db()
    conn.execute("DELETE FROM user_watchlist WHERE user_id = ? AND is_number = ?", (user["id"], is_number))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Removed from watchlist."})


# ============================================================
# COMPLIANCE CHECKER (PORTFOLIO CHECK)
# ============================================================

@app.route("/api/compliance/check", methods=["POST"])
def compliance_check():
    data = request.get_json(silent=True) or {}
    product = data.get("product", "").strip()
    standard = data.get("standard", "").strip()
    documents = data.get("documents", [])

    result = analyze_compliance(product, standard, documents)
    user = get_current_user()

    conn = get_db()
    conn.execute("""
        INSERT INTO compliance_reports (user_id, product, standard, score, risk, result)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user["id"], product, standard, result["score"], result["risk"], result["result"]))
    conn.commit()
    conn.close()

    try:
        add_user_history(
            user_id=user["id"],
            action_type="Compliance Check",
            title=f"Check: {product or 'Product'} vs {standard or 'Standard'}",
            description=f"Score: {result['score']}% - {result['result']} (Risk: {result['risk']})",
            meta={"product": product, "standard": standard, "score": result["score"], "risk": result["risk"]}
        )
        add_notification(
            user_id=user["id"],
            title="Compliance Assessment Completed",
            message=f"Compliance check for '{product or 'Product'}' completed with score {result['score']}%.",
            notif_type="audit"
        )
    except Exception as e:
        print("Notice:", e)

    return jsonify(result)


# ============================================================
# DOCUMENT INTELLIGENCE & UPLOAD (SECURE RUNTIME PIPELINE)
# ============================================================

def validate_file_content(file_stream, ext):
    """
    Validate magic bytes to ensure file contents match declared extension.
    """
    pos = file_stream.tell()
    header = file_stream.read(16)
    file_stream.seek(pos)

    if ext == "pdf":
        return header.startswith(b"%PDF-")
    elif ext == "docx":
        return header.startswith(b"PK\x03\x04")
    elif ext == "png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    elif ext in ["jpg", "jpeg"]:
        return header.startswith(b"\xff\xd8\xff")
    return True


@app.route("/api/documents/upload", methods=["POST"])
@app.route("/api/document/analyze", methods=["POST"])
def upload_document():
    """
    Secure Document Upload & Compliance Analysis Pipeline.
    Supports: PDF, DOCX, PNG, JPG, JPEG with OCR.
    """
    save_path = None
    try:
        user = get_current_user()

        if "file" not in request.files:
            return jsonify({"success": False, "error": "No file uploaded."}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"success": False, "error": "No file selected."}), 400

        original_filename = secure_filename(file.filename)
        if not original_filename or "." not in original_filename:
            return jsonify({"success": False, "error": "Invalid file name or extension."}), 400

        ext = original_filename.rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify({
                "success": False,
                "error": "Only PDF, DOCX, PNG, JPG and JPEG files are supported."
            }), 400

        # Validate magic byte content
        if not validate_file_content(file.stream, ext):
            return jsonify({
                "success": False,
                "error": f"File content does not match the declared {ext.upper()} format."
            }), 400

        # Unique safe filename
        safe_filename = f"{uuid.uuid4().hex[:8]}_{original_filename}"
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_filename)
        file.save(save_path)

        # Extract text via unified document processor
        extraction = process_document(save_path)
        extracted_text = extraction.get("text", "")

        # Analyze extracted content against shared BIS Knowledge Base
        analysis = analyze_document_content(extracted_text, original_filename)
        summary = analysis.get("summary", "")
        compliance_score = analysis.get("compliance_score", 0)

        # Save record in database with user ownership
        conn = get_db()
        cursor = conn.execute("""
            INSERT INTO documents
            (user_id, filename, filepath, file_type, extracted_text, summary, compliance_score, ocr_used, status, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user["id"],
            original_filename,
            None,
            ext,
            extracted_text,
            summary,
            compliance_score,
            1 if extraction.get("ocr_used") else 0,
            extraction.get("status", "PROCESSED"),
            datetime.now().isoformat()
        ))
        doc_id = cursor.lastrowid

        # Insert compliance report
        conn.execute("""
            INSERT INTO compliance_reports (user_id, product, standard, score, risk, result)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user["id"],
            analysis.get("product", original_filename),
            analysis.get("identified_standard", "Standard Specification"),
            compliance_score,
            analysis.get("compliance", {}).get("risk", "MEDIUM"),
            analysis.get("overall_status", "PARTIAL")
        ))
        conn.commit()
        conn.close()
        # Uploads are processed in a private transient directory.  Only the
        # extracted, user-owned analysis is persisted; no server file path is
        # retained or returned through the API.
        try:
            os.remove(save_path)
        except OSError:
            app.logger.warning("Could not remove transient upload")

        # Log history & notification
        add_user_history(
            user["id"],
            "Document Intelligence",
            f"Uploaded: {original_filename}",
            f"Compliance Score: {compliance_score}%. Overall Status: {analysis.get('overall_status')}",
            meta={"filename": original_filename, "score": compliance_score, "standard": analysis.get("identified_standard")}
        )
        add_notification(
            user["id"],
            "Document Analysis Completed",
            f"Successfully analyzed '{original_filename}'. Compliance rating: {compliance_score}%.",
            notif_type="audit"
        )

        analysis["id"] = doc_id
        analysis["characters_extracted"] = len(extracted_text)
        analysis["extracted_text"] = extracted_text
        analysis["preview"] = extracted_text[:800]

        return jsonify({
            "success": True,
            "message": "Document uploaded and analyzed successfully.",
            "document": analysis
        })

    except Exception as error:
        if save_path and os.path.exists(save_path):
            try:
                os.remove(save_path)
            except OSError:
                app.logger.warning("Could not remove failed transient upload")
        print("DOCUMENT UPLOAD ERROR:", error)
        return jsonify({
            "success": False,
            "error": "Document processing failed. Please verify the document format."
        }), 500


@app.route("/api/documents", methods=["GET"])
def get_all_documents():
    """Retrieve documents with user isolation (officers view all; citizens view their own)."""
    try:
        user = get_current_user()
        is_officer = is_officer_user(user)

        conn = get_db()
        if is_officer:
            rows = conn.execute("""
                SELECT id, user_id, filename, file_type, summary, compliance_score, ocr_used, status, created_at, uploaded_at
                FROM documents
                ORDER BY id DESC
            """).fetchall()
        else:
            rows = conn.execute("""
                SELECT id, user_id, filename, file_type, summary, compliance_score, ocr_used, status, created_at, uploaded_at
                FROM documents
                WHERE user_id = ?
                ORDER BY id DESC
            """, (user["id"],)).fetchall()
        conn.close()

        return jsonify({
            "success": True,
            "documents": [dict(r) for r in rows]
        })
    except Exception as error:
        print("GET DOCUMENTS ERROR:", error)
        return jsonify({"success": False, "error": "Failed to retrieve documents."}), 500


@app.route("/api/documents/<int:document_id>", methods=["GET"])
def get_single_document(document_id):
    try:
        user = get_current_user()
        is_officer = is_officer_user(user)

        conn = get_db()
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        conn.close()

        if not row:
            return jsonify({"success": False, "error": "Document not found."}), 404

        doc_dict = dict(row)
        # Check ownership unless officer
        if not is_officer and doc_dict.get("user_id") != user["id"]:
            return jsonify({"success": False, "error": "Access denied to requested document."}), 403

        doc_dict.pop("filepath", None)

        if doc_dict.get("extracted_text"):
            analysis = analyze_document_content(doc_dict["extracted_text"], doc_dict.get("filename", ""))
            doc_dict["metadata"] = analysis.get("metadata", {})
            doc_dict["requirements"] = analysis.get("requirements", [])
            doc_dict["compliance"] = analysis.get("compliance", {})
            doc_dict["violations"] = analysis.get("violations", [])
            doc_dict["recommendations"] = analysis.get("recommendations", [])
            doc_dict["sources"] = analysis.get("sources", [])
            doc_dict["status_counts"] = analysis.get("status_counts", {})
            doc_dict["overall_status"] = analysis.get("overall_status", "PARTIAL")

        return jsonify({"success": True, "document": doc_dict})

    except Exception as error:
        print("GET SINGLE DOCUMENT ERROR:", error)
        return jsonify({"success": False, "error": "Failed to retrieve document details."}), 500


# ============================================================
# BIS LICENSE & HALLMARK VERIFICATION (PROTOTYPE DATABASE)
# ============================================================

@app.route("/api/verify/<path:license_no>", methods=["GET"])
def verify_license(license_no):
    """
    Verify BIS license number against the local prototype verification database.
    """
    conn = get_db()
    row = conn.execute("SELECT * FROM licenses WHERE license_number = ?", (license_no,)).fetchone()
    conn.close()

    user = get_current_user()

    if not row:
        add_user_history(user["id"], "License Verification", f"Check: {license_no}", "License not found in prototype database.", status="NOT_FOUND")
        return jsonify({
            "verified": False,
            "valid": False,
            "source": "Prototype / Demo Verification Database",
            "message": "License not found in the prototype verification database.",
            "official_portal": "https://www.services.bis.gov.in/"
        }), 404

    lic_data = dict(row)
    add_user_history(user["id"], "License Verification", f"Verified: {license_no}", f"Active license for {lic_data['product']} ({lic_data['manufacturer']})", lic_data)

    return jsonify({
        "verified": lic_data["status"] == "Active",
        "valid": lic_data["status"] == "Active",
        "source": "Prototype / Demo Verification Database",
        "notice": "Demonstration data for prototype verification.",
        "details": lic_data
    })


@app.route("/api/verify/hallmark/<path:huid>", methods=["GET"])
def verify_hallmark(huid):
    """
    Verify 6-character Hallmark Unique Identification (HUID) code against local prototype database.
    """
    huid_clean = huid.strip().upper()
    if len(huid_clean) != 6 or not huid_clean.isalnum():
        return jsonify({
            "verified": False,
            "valid": False,
            "error": "Invalid HUID. Must be exactly 6 alphanumeric characters (e.g. AB1234)."
        }), 400

    conn = get_db()
    row = conn.execute("SELECT * FROM hallmarks WHERE huid = ?", (huid_clean,)).fetchone()
    conn.close()

    user = get_current_user()

    if not row:
        add_user_history(user["id"], "Hallmark Verification", f"HUID: {huid_clean}", "HUID not found in prototype registry.", status="NOT_FOUND")
        return jsonify({
            "verified": False,
            "valid": False,
            "huid": huid_clean,
            "source": "Prototype / Demo Verification Database",
            "message": f"HUID '{huid_clean}' was not found in the local BIS prototype registry.",
            "official_guidance": "Real-time national hallmark verification is hosted by the National Hallmarking Portal (Manakonline) and BIS Care App.",
            "portal": "https://www.manakonline.in/"
        }), 404

    hallmark_data = dict(row)
    hallmark_data["metal_purity"] = hallmark_data.get("purity")
    hallmark_data["center_name"] = hallmark_data.get("ahc_name")
    hallmark_data["hallmarking_date"] = hallmark_data.get("hallmark_date")

    add_user_history(user["id"], "Hallmark Verification", f"Verified HUID: {huid_clean}", f"{hallmark_data['article_type']} ({hallmark_data['purity']})", hallmark_data)

    return jsonify({
        "verified": True,
        "valid": True,
        "source": "Prototype / Demo Verification Database",
        "notice": "Demonstration data for prototype verification.",
        "hallmark": hallmark_data,
        "details": hallmark_data
    })


# ============================================================
# COMPLAINTS & INVESTIGATION WORKFLOW
# ============================================================

@app.route("/api/complaints", methods=["GET"])
def get_complaints_route():
    """
    Retrieve registered complaints with user data isolation.
    """
    try:
        user = get_current_user()
        is_officer = is_officer_user(user)
        status_filter = request.args.get("status", "").strip()
        search_query = request.args.get("q", "").strip()

        complaints_list = db_get_complaints(
            user_id=user["id"],
            is_officer=is_officer,
            status=status_filter,
            search=search_query
        )

        return jsonify({
            "success": True,
            "count": len(complaints_list),
            "complaints": complaints_list
        })
    except Exception as error:
        print("GET COMPLAINTS ERROR:", error)
        return jsonify({"success": False, "error": "Failed to retrieve complaints."}), 500


@app.route("/api/complaints", methods=["POST"])
def report_complaint():
    """
    File an official citizen grievance / complaint with collision-resistant ID and severity tracking.
    """
    try:
        data = request.get_json(silent=True) or {}
        name = (data.get("complainant_name") or data.get("name", "")).strip()
        contact = (data.get("complainant_email") or data.get("complainant_phone") or data.get("contact", "")).strip()
        category = data.get("category", "").strip()
        ref_number = (data.get("reference_number") or data.get("ref_number", "")).strip()
        subject = data.get("subject", "").strip()
        description = data.get("description", "").strip()
        severity = data.get("severity", "MEDIUM").strip().upper()
        if severity not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            severity = "HIGH" if "misuse" in category.lower() or "counterfeit" in category.lower() else "MEDIUM"

        if not name or not contact or not category or not subject or not description:
            return jsonify({
                "success": False,
                "error": "Name, Contact, Category, Subject, and Description are all required fields."
            }), 400

        # Collision-resistant complaint ID
        unique_token = uuid.uuid4().hex[:8].upper()
        complaint_id = f"BIS-CMP-2026-{unique_token}"
        user = get_current_user()

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        conn.execute("""
            INSERT INTO complaints
            (complaint_id, user_id, name, contact, category, ref_number, subject, description, severity, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'SUBMITTED', ?)
        """, (complaint_id, user["id"], name, contact, category, ref_number, subject, description, severity, now_str))
        conn.commit()
        conn.close()

        add_user_history(
            user["id"],
            "Complaint Filed",
            f"{complaint_id}: {subject}",
            f"Category: {category}. Severity: {severity}. Status: SUBMITTED",
            {"complaint_id": complaint_id, "category": category, "severity": severity}
        )
        add_notification(
            user["id"],
            "Complaint Registered",
            f"Your complaint ({complaint_id}) regarding '{subject}' has been registered for investigation.",
            notif_type="audit"
        )

        return jsonify({
            "success": True,
            "tracking_id": complaint_id,
            "complaint_id": complaint_id,
            "status": "SUBMITTED",
            "severity": severity,
            "message": "Grievance submitted successfully. Your collision-resistant reference ID has been generated."
        }), 201

    except Exception as error:
        print("COMPLAINT SUBMIT ERROR:", error)
        return jsonify({"success": False, "error": "Failed to record complaint."}), 500


@app.route("/api/complaints/<path:complaint_id>/investigate", methods=["POST"])
def investigate_complaint_route(complaint_id):
    """
    Perform real complaint investigation workflow.
    Transitions status to INVESTIGATION, assigns officer, and records audit actions.
    """
    try:
        user = get_current_user()
        if not is_officer_user(user):
            return jsonify({"success": False, "error": "Only BIS officers may start an investigation."}), 403
        updated = db_investigate_complaint(complaint_id, user["id"], user.get("name"))
        if not updated:
            return jsonify({"success": False, "error": "Complaint not found."}), 404

        add_user_history(
            user["id"],
            "Complaint Investigation",
            f"Investigating {complaint_id}",
            f"Assigned to {user.get('name')}. Status updated to INVESTIGATION.",
            {"complaint_id": complaint_id, "status": "INVESTIGATION"}
        )
        add_notification(
            user["id"],
            "Investigation Opened",
            f"Investigation opened for complaint {complaint_id} ({updated.get('subject')}).",
            notif_type="audit"
        )

        return jsonify({
            "success": True,
            "message": f"Complaint {complaint_id} status updated to INVESTIGATION.",
            "complaint": updated
        })
    except Exception as error:
        print("INVESTIGATE COMPLAINT ERROR:", error)
        return jsonify({"success": False, "error": "Investigation workflow failed."}), 500


# ============================================================
# NOTIFICATIONS (FUNCTIONAL CATEGORY FILTERING)
# ============================================================

@app.route("/api/notifications", methods=["GET"])
def get_notifications():
    """
    Retrieve user-isolated notifications with optional category filtering (all, audit, system, standard).
    """
    user = get_current_user()
    category = request.args.get("category", "").strip().lower()

    conn = get_db()
    sql = "SELECT * FROM notifications WHERE user_id = ?"
    params = [user["id"]]

    if category and category not in ["all", "all alerts"]:
        sql += " AND (type = ? OR type LIKE ?)"
        params.extend([category, f"%{category}%"])

    sql += " ORDER BY id DESC LIMIT 50"
    rows = conn.execute(sql, params).fetchall()

    unread = conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (user["id"],)).fetchone()[0]
    conn.close()

    notifs = [dict(row) for row in rows]
    return jsonify({
        "success": True,
        "notifications": notifs,
        "unread_count": unread,
        "category": category or "all"
    })


@app.route("/api/notifications/<int:notif_id>/read", methods=["POST"])
def mark_notification_read(notif_id):
    user = get_current_user()
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notif_id, user["id"]))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Notification marked as read."})


@app.route("/api/notifications/read-all", methods=["POST"])
def mark_all_notifications_read():
    user = get_current_user()
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user["id"],))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "All notifications marked as read."})


# ============================================================
# BIS SERVICES METADATA
# ============================================================

@app.route("/api/services", methods=["GET"])
def get_services():
    services = [
        {
            "id": "product_certification",
            "title": "Product Certification (ISI Mark)",
            "subtitle": "Ensure product quality, safety, and compliance with Indian Standards",
            "icon": "fa-solid fa-certificate",
            "category": "Manufacturing & Consumer Safety",
            "overview": "The BIS Product Certification Scheme (Scheme-I under BIS Act 2016) allows manufacturers conforming to applicable Indian Standards to use the prestigious ISI Mark.",
            "official_portal": "https://www.services.bis.gov.in/",
            "portal_name": "BIS Manakonline Certification Portal"
        },
        {
            "id": "hallmarking",
            "title": "Hallmarking of Precious Metals",
            "subtitle": "Guaranteed purity and trust in Gold and Silver jewellery",
            "icon": "fa-solid fa-gem",
            "category": "Consumer Protection",
            "overview": "BIS Hallmarking provides third-party assurance of the purity or fineness of gold and silver articles with 6-character HUID laser identification.",
            "official_portal": "https://www.manakonline.in/",
            "portal_name": "Manakonline Hallmarking Portal"
        },
        {
            "id": "lab_recognition",
            "title": "Laboratory Recognition Scheme (LRS)",
            "subtitle": "Accredited testing facilities powering quality verification",
            "icon": "fa-solid fa-flask",
            "category": "Testing & Conformance",
            "overview": "Testing laboratories conforming to ISO/IEC 17025 are recognized to perform conformity assessment and sample testing.",
            "official_portal": "https://www.services.bis.gov.in/",
            "portal_name": "BIS Lab Directory & LRS Portal"
        },
        {
            "id": "crs",
            "title": "Compulsory Registration Scheme (CRS)",
            "subtitle": "Self-declaration of conformity for Electronics & IT goods",
            "icon": "fa-solid fa-file-signature",
            "category": "Electronics & IT Goods",
            "overview": "Covers laptops, tablets, mobile phones, LED lights, power adapters, and smart watches under safety standards.",
            "official_portal": "https://www.crsbis.in/BIS/",
            "portal_name": "BIS CRS Official Portal"
        },
        {
            "id": "standards",
            "title": "Standards Formulation & Catalogue",
            "subtitle": "Access the comprehensive repository of Indian Standards",
            "icon": "fa-solid fa-book-bookmark",
            "category": "Technical Specifications",
            "overview": "BIS acts as the National Standards Body of India, formulating Indian Standards harmonized with ISO/IEC international benchmarks.",
            "official_portal": "https://www.standardsbis.in/",
            "portal_name": "BIS Standards Portal"
        },
        {
            "id": "fmcs",
            "title": "Foreign Manufacturers Certification Scheme (FMCS)",
            "subtitle": "ISI Mark Certification for Overseas Manufacturing Units",
            "icon": "fa-solid fa-earth-asia",
            "category": "Global Trade & Imports",
            "overview": "FMCS enables overseas manufacturing units to obtain a BIS license and apply the ISI mark on goods exported into India.",
            "official_portal": "https://www.services.bis.gov.in/",
            "portal_name": "BIS FMCS Portal"
        }
    ]

    services_dict = {s["id"]: s for s in services}
    return jsonify({
        "success": True,
        "count": len(services),
        "services": services_dict,
        "services_list": services
    })


# ============================================================
# USER ACTION HISTORY
# ============================================================

@app.route("/api/history", methods=["GET"])
def get_user_history_route():
    user = get_current_user()
    action_filter = request.args.get("filter", "").strip().lower()

    conn = get_db()
    if action_filter and action_filter != "all":
        filter_pattern = f"%{action_filter.replace('_', '%')}%"
        rows = conn.execute("""
            SELECT * FROM user_history
            WHERE user_id = ? AND (LOWER(action_type) LIKE ? OR LOWER(action_type) = ?)
            ORDER BY id DESC LIMIT 60
        """, (user["id"], filter_pattern, action_filter)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM user_history
            WHERE user_id = ?
            ORDER BY id DESC LIMIT 60
        """, (user["id"],)).fetchall()
    conn.close()

    history_items = []
    for row in rows:
        item = dict(row)
        item["action_key"] = (item.get("action_type") or "").lower().replace(" ", "_")
        if item.get("meta_json"):
            try:
                item["meta"] = json.loads(item["meta_json"])
            except Exception:
                item["meta"] = {}
        else:
            item["meta"] = {}
        history_items.append(item)

    return jsonify({
        "success": True,
        "user_id": user["id"],
        "count": len(history_items),
        "history": history_items
    })


@app.route("/api/history", methods=["POST"])
def record_user_history_route():
    try:
        data = request.get_json(silent=True) or {}
        action_type = data.get("action_type", "User Action").strip()
        title = data.get("title", "").strip()
        description = data.get("description", "").strip()
        meta = data.get("meta", {})
        status = data.get("status", "SUCCESS")

        if not title:
            return jsonify({"success": False, "error": "Action title is required."}), 400

        user = get_current_user()
        add_user_history(user["id"], action_type, title, description, meta, status)
        return jsonify({"success": True, "message": "Action recorded."})
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


@app.route("/api/history", methods=["DELETE"])
def clear_user_history_route():
    user = get_current_user()
    conn = get_db()
    conn.execute("DELETE FROM user_history WHERE user_id = ?", (user["id"],))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Activity history cleared successfully."})


# ============================================================
# DASHBOARD METRICS (REAL DATABASE VALUES)
# ============================================================

@app.route("/api/dashboard", methods=["GET"])
def get_dashboard_metrics():
    """
    Return dynamic database metrics replacing all hardcoded values.
    """
    user = get_current_user()
    is_officer = is_officer_user(user)

    metrics = get_real_dashboard_metrics(user["id"], is_officer)

    conn = get_db()
    recent_rows = conn.execute("""
        SELECT action_type, title, description, created_at, status
        FROM user_history
        WHERE user_id = ?
        ORDER BY id DESC LIMIT 5
    """, (user["id"],)).fetchall()
    conn.close()

    recent_activity = [dict(r) for r in recent_rows]

    return jsonify({
        "success": True,
        "metrics": metrics,
        "recent_activity": recent_activity
    })


# ============================================================
# GLOBAL ERROR HANDLERS (NO STACK TRACE EXPOSURE)
# ============================================================

@app.errorhandler(404)
def handle_404(e):
    return jsonify({"success": False, "error": "Endpoint not found."}), 404

@app.errorhandler(401)
def handle_401(e):
    return jsonify({"success": False, "error": "Authentication is required or the session has expired."}), 401

@app.errorhandler(413)
def handle_413(e):
    return jsonify({"success": False, "error": "Uploaded file is too large. Maximum size is 15 MB."}), 413

@app.errorhandler(500)
def handle_500(e):
    return jsonify({"success": False, "error": "An internal server error occurred. Please try again later."}), 500


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":
    init_db()
    print("BIS AI ASSISTANT BACKEND starting on http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=True)
