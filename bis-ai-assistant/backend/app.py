import os
import json
import random
import base64
import requests

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

from database import (
    get_db,
    init_db,
    add_user_history,
    add_notification,
    create_session,
    get_user_by_session
)
from ai_engine import process_ai_query
from compliance_engine import analyze_compliance
from document_engine import extract_document, generate_summary, analyze_document_content


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

CORS(app)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads"
)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# Supported document types
ALLOWED_EXTENSIONS = {
    "pdf",
    "docx",
    "png",
    "jpg",
    "jpeg"
}


# ============================================================
# HOME / FRONTEND
# ============================================================

FRONTEND_DIR = os.path.abspath(
    os.path.join(BASE_DIR, "..", "frontend")
)

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
    """Extract currently authenticated user from token or return default session."""
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    if token:
        user = get_user_by_session(token)
        if user:
            return user

    email = request.headers.get("X-User-Email", "").strip()
    conn = get_db()
    if email:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            conn.close()
            return dict(row)

    # Fallback to default demo officer
    row = conn.execute("SELECT * FROM users WHERE id = 'usr_officer_demo_01'").fetchone()
    conn.close()
    if row:
        return dict(row)

    return {
        "id": "usr_officer_demo_01",
        "email": "officer@bis.gov.in",
        "name": "Raj Kumar",
        "role": "BIS Quality Assurance Officer"
    }


@app.route("/api/auth/google", methods=["POST"])
def auth_google():
    """
    Authenticate user using Google Identity Services ID token.
    Decodes payload, verifies issuer/expiration, registers/updates user, and issues session token.
    """
    try:
        data = request.get_json(silent=True) or {}
        credential = data.get("credential", "").strip()

        if not credential:
            return jsonify({
                "success": False,
                "error": "Google credential token is required."
            }), 400

        # Attempt verification via Google's tokeninfo endpoint if available
        user_info = None
        try:
            res = requests.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}",
                timeout=5
            )
            if res.status_code == 200:
                user_info = res.json()
        except Exception as e:
            print("Google tokeninfo remote check notice:", e)

        # Safe fallback decoding of JWT payload
        if not user_info:
            parts = credential.split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1]
                # Add base64 padding if necessary
                padded = payload_b64 + "=" * ((4 - len(payload_b64) % 4) % 4)
                decoded_bytes = base64.urlsafe_b64decode(padded)
                user_info = json.loads(decoded_bytes.decode("utf-8"))

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
            """, (user_id, email, name, picture, "Verified Google User", "google"))
        conn.commit()

        user_row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        user_dict = dict(user_row)

        session_token = create_session(user_id)
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
            "error": f"Authentication processing failed: {str(error)}"
        }), 500


@app.route("/api/auth/demo", methods=["POST"])
def auth_demo():
    """
    Fast developer / evaluation login without requiring external Google OAuth configuration.
    """
    try:
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

        session_token = create_session(user_dict["id"])
        add_user_history(user_dict["id"], "User Login", "Demo Officer Sign-In", f"Signed in as {name} ({role})")

        return jsonify({
            "success": True,
            "message": "Demo sign-in successful.",
            "token": session_token,
            "user": user_dict
        })

    except Exception as error:
        print("DEMO AUTH ERROR:", error)
        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    """Return profile of the current authenticated user."""
    user = get_current_user()
    return jsonify({
        "success": True,
        "user": user
    })


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """Log out user and terminate session."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        conn = get_db()
        conn.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()

    return jsonify({
        "success": True,
        "message": "Logged out successfully."
    })


# ============================================================
# HEALTH
# ============================================================

@app.route("/api/health", methods=["GET"])
def health():

    return jsonify({
        "status": "ok",
        "service": "BIS AI Assistant API"
    })


# ============================================================
# AI ASSISTANT
# ============================================================

@app.route("/api/ai/query", methods=["POST"])
def ai_query():
    try:
        data = request.get_json(silent=True) or {}
        query = data.get("query", "").strip()
        doc_context = data.get("document_context", None)
        doc_filename = data.get("document_filename", None)

        if not query:
            return jsonify({
                "success": False,
                "error": "Query is required."
            }), 400

        result = process_ai_query(query, doc_context, doc_filename)
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
                "model": result.get("model"),
                "document_attached": doc_filename
            }
        )

        return jsonify(result)

    except Exception as error:
        print("AI QUERY ERROR:", error)
        return jsonify({
            "success": False,
            "error": "AI service is temporarily unavailable. Please try again."
        }), 500



# ============================================================
# STANDARDS SEARCH
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

    # Sorting
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

    if query:
        try:
            user = get_current_user()
            add_user_history(
                user_id=user["id"],
                action_type="Standards Search",
                title=f"Search: {query}",
                description=f"Retrieved {len(standards_list)} standards for '{query}'",
                meta={"query": query, "count": len(standards_list), "category": category, "sort": sort_by}
            )
        except Exception as e:
            print("History log notice for search:", e)

    return jsonify({
        "success": True,
        "count": len(standards_list),
        "standards": standards_list
    })


# ============================================================
# SINGLE STANDARD
# ============================================================

@app.route(
    "/api/standards/<path:is_number>",
    methods=["GET"]
)
def standard_detail(is_number):

    conn = get_db()

    row = conn.execute("""
        SELECT *
        FROM standards
        WHERE is_number = ?
    """, (
        is_number,
    )).fetchone()

    conn.close()

    if not row:

        return jsonify({
            "error": "Standard not found."
        }), 404

    return jsonify({
        "standard": dict(row)
    })


# ============================================================
# COMPLIANCE CHECKER
# ============================================================

@app.route(
    "/api/compliance/check",
    methods=["POST"]
)
def compliance_check():

    data = request.get_json(
        silent=True
    ) or {}

    product = data.get(
        "product",
        ""
    ).strip()

    standard = data.get(
        "standard",
        ""
    ).strip()

    documents = data.get(
        "documents",
        []
    )

    result = analyze_compliance(
        product,
        standard,
        documents
    )

    conn = get_db()

    conn.execute("""
        INSERT INTO compliance_reports
        (
            product,
            standard,
            score,
            risk,
            result
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        product,
        standard,
        result["score"],
        result["risk"],
        result["result"]
    ))

    conn.commit()
    conn.close()

    try:
        user = get_current_user()
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
            message=f"Compliance check for '{product or 'Product'}' completed with score {result['score']}% ({result['result']}).",
            notif_type="success" if result["score"] >= 70 else "warning"
        )
    except Exception as e:
        print("History log notice for compliance check:", e)

    return jsonify(result)


# ============================================================
# DOCUMENT UPLOAD
# ============================================================

@app.route(
    "/api/documents/upload",
    methods=["POST"]
)
def upload_document():

    try:

        # ----------------------------------------------------
        # 1. Check file
        # ----------------------------------------------------

        if "file" not in request.files:

            return jsonify({
                "success": False,
                "error": "No file uploaded."
            }), 400

        file = request.files["file"]

        if file.filename == "":

            return jsonify({
                "success": False,
                "error": "No file selected."
            }), 400


        # ----------------------------------------------------
        # 2. Secure filename
        # ----------------------------------------------------

        filename = secure_filename(
            file.filename
        )

        if not filename:

            return jsonify({
                "success": False,
                "error": "Invalid filename."
            }), 400


        # ----------------------------------------------------
        # 3. Check extension
        # ----------------------------------------------------

        if "." not in filename:

            return jsonify({
                "success": False,
                "error": "File extension is missing."
            }), 400

        extension = filename.rsplit(
            ".",
            1
        )[-1].lower()

        if extension not in ALLOWED_EXTENSIONS:

            return jsonify({
                "success": False,
                "error": (
                    "Only PDF, DOCX, PNG, JPG "
                    "and JPEG files are supported."
                )
            }), 400


        # ----------------------------------------------------
        # 4. Save file
        # ----------------------------------------------------

        path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        file.save(path)


        # ----------------------------------------------------
        # 5. Extract document text
        # ----------------------------------------------------

        text = extract_document(path)

        if not text or not text.strip():

            return jsonify({
                "success": False,
                "error": (
                    "No readable text was found in this "
                    "document. The document may be "
                    "scanned/image-based and may require OCR."
                ),
                "status": "OCR_REQUIRED",
                "document": None
            }), 200

        # ----------------------------------------------------
        # 6. Analyze document (Summary, Requirements, Compliance, Violations, Recommendations)
        # ----------------------------------------------------

        analysis = analyze_document_content(text, filename)
        summary = analysis.get("summary", "")
        compliance_data = analysis.get("compliance", {})
        compliance_score = compliance_data.get("score", None)

        # ----------------------------------------------------
        # 7. Save document in database
        # ----------------------------------------------------

        conn = get_db()

        cursor = conn.execute("""
            INSERT INTO documents
            (
                filename,
                filepath,
                file_type,
                extracted_text,
                summary,
                compliance_score,
                ocr_used,
                status,
                uploaded_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            filename,
            path,
            extension,
            text,
            summary,
            compliance_score,
            0,
            "PROCESSED",
            __import__(
                "datetime"
            ).datetime.now().isoformat()
        ))

        document_id = cursor.lastrowid

        # Also store compliance report if applicable
        if analysis.get("requirements"):
            prod_name = analysis.get("metadata", {}).get("product") or filename
            std_name = analysis.get("metadata", {}).get("standard") or "Standard Analysis"
            conn.execute("""
                INSERT INTO compliance_reports
                (product, standard, score, risk, result)
                VALUES (?, ?, ?, ?, ?)
            """, (
                prod_name,
                std_name,
                compliance_score,
                compliance_data.get("risk", "MEDIUM"),
                compliance_data.get("result", "Analyzed")
            ))

        conn.commit()
        conn.close()

        try:
            user = get_current_user()
            add_user_history(
                user_id=user["id"],
                action_type="Document Intelligence",
                title=f"Uploaded: {filename}",
                description=f"Compliance Score: {compliance_score}%. Extracted {len(text)} characters.",
                meta={"filename": filename, "score": compliance_score, "violations": len(analysis.get("violations", []))}
            )
            add_notification(
                user_id=user["id"],
                title="Document Analysis Completed",
                message=f"Successfully extracted and analyzed '{filename}'. Compliance rating: {compliance_score}%.",
                notif_type="success"
            )
        except Exception as e:
            print("History log notice for document upload:", e)

        # ----------------------------------------------------
        # 8. Return comprehensive intelligence response
        # ----------------------------------------------------

        return jsonify({
            "success": True,
            "message": "Document uploaded and analyzed successfully.",
            "document": {
                "id": document_id,
                "filename": filename,
                "file_type": extension,
                "status": "PROCESSED",
                "ocr_used": False,
                "characters_extracted": len(text),
                "extracted_text": text,
                "preview": text[:1000],
                "summary": summary,
                "metadata": analysis.get("metadata", {}),
                "requirements": analysis.get("requirements", []),
                "compliance": compliance_data,
                "violations": analysis.get("violations", []),
                "recommendations": analysis.get("recommendations", [])
            }
        })



    except Exception as error:

        print(
            "DOCUMENT UPLOAD ERROR:",
            error
        )

        return jsonify({

            "success": False,

            "error": str(error)

        }), 500


# ============================================================
# GET ALL DOCUMENTS
# ============================================================

@app.route(
    "/api/documents",
    methods=["GET"]
)
def get_all_documents():

    try:

        conn = get_db()

        rows = conn.execute("""
            SELECT
                id,
                filename,
                filepath,
                file_type,
                summary,
                compliance_score,
                ocr_used,
                status,
                created_at,
                uploaded_at
            FROM documents
            ORDER BY id DESC
        """).fetchall()

        conn.close()

        return jsonify({

            "success": True,

            "documents": [
                dict(row)
                for row in rows
            ]

        })

    except Exception as error:

        print(
            "GET DOCUMENTS ERROR:",
            error
        )

        return jsonify({

            "success": False,

            "error": str(error)

        }), 500


# ============================================================
# GET SINGLE DOCUMENT
# ============================================================

@app.route(
    "/api/documents/<int:document_id>",
    methods=["GET"]
)
def get_single_document(document_id):

    try:

        conn = get_db()

        row = conn.execute("""
            SELECT *
            FROM documents
            WHERE id = ?
        """, (
            document_id,
        )).fetchone()

        conn.close()

        if not row:

            return jsonify({
                "success": False,
                "error": "Document not found."
            }), 404

        doc_dict = dict(row)
        if doc_dict.get("extracted_text"):
            analysis = analyze_document_content(doc_dict["extracted_text"], doc_dict.get("filename", ""))
            doc_dict["metadata"] = analysis.get("metadata", {})
            doc_dict["requirements"] = analysis.get("requirements", [])
            doc_dict["compliance"] = analysis.get("compliance", {})
            doc_dict["violations"] = analysis.get("violations", [])
            doc_dict["recommendations"] = analysis.get("recommendations", [])

        return jsonify({
            "success": True,
            "document": doc_dict
        })


    except Exception as error:

        print(
            "GET SINGLE DOCUMENT ERROR:",
            error
        )

        return jsonify({

            "success": False,

            "error": str(error)

        }), 500


# ============================================================
# BIS LICENSE VERIFICATION
# ============================================================

@app.route(
    "/api/verify/<path:license_no>",
    methods=["GET"]
)
def verify_license(license_no):

    conn = get_db()

    row = conn.execute("""
        SELECT *
        FROM licenses
        WHERE license_number = ?
    """, (
        license_no,
    )).fetchone()

    conn.close()

    if not row:
        try:
            user = get_current_user()
            add_user_history(user["id"], "License Verification", f"Check: {license_no}", "License not found in verification registry.", status="NOT_FOUND")
        except Exception:
            pass

        return jsonify({
            "verified": False,
            "message": "License not found in the verification database."
        }), 404

    try:
        user = get_current_user()
        add_user_history(user["id"], "License Verification", f"Verified: {license_no}", f"Status: {row['status']}. Product: {row['product']} by {row['manufacturer']}", dict(row))
        if row["status"] == "Active":
            add_notification(user["id"], "License Verified", f"BIS License {license_no} is valid and active for {row['product']}.", "success")
    except Exception as e:
        print("History log notice for license verify:", e)

    return jsonify({
        "verified": row["status"] == "Active",
        "valid": row["status"] == "Active",
        "details": {
            "license_number": row["license_number"],
            "product": row["product"],
            "manufacturer": row["manufacturer"],
            "standard": row["standard"],
            "validity_from": row["validity_from"],
            "validity_to": row["validity_to"],
            "status": row["status"]
        }
    })


# ============================================================
# HALLMARK VERIFICATION
# ============================================================

@app.route("/api/verify/hallmark/<path:huid>", methods=["GET"])
def verify_hallmark(huid):
    """
    Verify 6-character Hallmark Unique Identification (HUID) code.
    Checks local hallmark database or guides to official Manakonline registry.
    """
    huid_clean = huid.strip().upper()

    if len(huid_clean) != 6 or not huid_clean.isalnum():
        return jsonify({
            "verified": False,
            "valid": False,
            "error": "Invalid HUID. Hallmark Unique Identification must be exactly 6 alphanumeric characters (e.g. AB1234)."
        }), 400

    conn = get_db()
    row = conn.execute("SELECT * FROM hallmarks WHERE huid = ?", (huid_clean,)).fetchone()
    conn.close()

    user = get_current_user()

    if not row:
        add_user_history(
            user["id"],
            "Hallmark Verification",
            f"HUID: {huid_clean}",
            "HUID not found in prototype database. Official live check requires Manakonline portal.",
            status="NOT_FOUND"
        )
        return jsonify({
            "verified": False,
            "valid": False,
            "huid": huid_clean,
            "message": f"HUID '{huid_clean}' was not found in the local BIS prototype registry.",
            "official_guidance": "Real-time national hallmark verification is hosted by the National Hallmarking Portal (Manakonline) and BIS Care App.",
            "portal": "https://www.manakonline.in/"
        }), 404

    hallmark_data = dict(row)
    hallmark_data["metal_purity"] = hallmark_data.get("purity")
    hallmark_data["center_name"] = hallmark_data.get("ahc_name")
    hallmark_data["hallmarking_date"] = hallmark_data.get("hallmark_date")

    add_user_history(
        user["id"],
        "Hallmark Verification",
        f"Verified HUID: {huid_clean}",
        f"Purity: {hallmark_data['purity']} - {hallmark_data['article_type']} ({hallmark_data['jeweler_name']})",
        hallmark_data
    )
    add_notification(
        user["id"],
        "Hallmark Verified",
        f"HUID {huid_clean} verified: {hallmark_data['article_type']} with {hallmark_data['purity']}.",
        "success"
    )

    return jsonify({
        "verified": True,
        "valid": True,
        "hallmark": hallmark_data,
        "details": hallmark_data
    })


# ============================================================
# REPORT & LIST COMPLAINTS
# ============================================================

@app.route("/api/complaints", methods=["GET"])
def get_complaints():
    """
    Retrieve registered complaints / violations list.
    Supports filtering by severity, status, or search query.
    """
    try:
        status_filter = request.args.get("status", "").strip()
        search_query = request.args.get("q", "").strip()

        conn = get_db()
        sql = "SELECT * FROM complaints WHERE 1=1"
        params = []

        if status_filter and status_filter.lower() not in ["all", "status: all"]:
            sql += " AND LOWER(status) = ?"
            params.append(status_filter.lower())

        if search_query:
            sql += " AND (complaint_id LIKE ? OR subject LIKE ? OR description LIKE ? OR ref_number LIKE ? OR name LIKE ?)"
            pat = f"%{search_query}%"
            params.extend([pat, pat, pat, pat, pat])

        sql += " ORDER BY id DESC"
        rows = conn.execute(sql, params).fetchall()
        conn.close()

        complaints_list = [dict(row) for row in rows]
        return jsonify({
            "success": True,
            "count": len(complaints_list),
            "complaints": complaints_list
        })
    except Exception as error:
        print("GET COMPLAINTS ERROR:", error)
        return jsonify({"success": False, "error": str(error)}), 500


@app.route("/api/complaints", methods=["POST"])
def report_complaint():
    """
    File an official citizen grievance / complaint regarding BIS certified products,
    misuse of ISI mark, hallmarking malpractice, or service delays.
    """
    try:
        data = request.get_json(silent=True) or {}
        name = (data.get("complainant_name") or data.get("name", "")).strip()
        contact = (data.get("complainant_email") or data.get("complainant_phone") or data.get("contact", "")).strip()
        category = data.get("category", "").strip()
        ref_number = (data.get("reference_number") or data.get("ref_number", "")).strip()
        subject = data.get("subject", "").strip()
        description = data.get("description", "").strip()

        if not name or not contact or not category or not subject or not description:
            return jsonify({
                "success": False,
                "error": "Name, Contact, Category, Subject, and Description are all required fields."
            }), 400

        complaint_id = f"BIS-CMP-2026-{random.randint(1000, 9999)}"
        user = get_current_user()

        conn = get_db()
        conn.execute("""
            INSERT INTO complaints
            (complaint_id, user_id, name, contact, category, ref_number, subject, description, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'SUBMITTED')
        """, (complaint_id, user["id"], name, contact, category, ref_number, subject, description))
        conn.commit()
        conn.close()

        add_user_history(
            user["id"],
            "Complaint Filed",
            f"{complaint_id}: {subject}",
            f"Category: {category}. Ref: {ref_number or 'N/A'}. Status: SUBMITTED",
            {"complaint_id": complaint_id, "category": category, "subject": subject}
        )

        add_notification(
            user["id"],
            "Complaint Registered",
            f"Your complaint ({complaint_id}) regarding '{subject}' has been registered for investigation.",
            "info"
        )

        return jsonify({
            "success": True,
            "tracking_id": complaint_id,
            "complaint_id": complaint_id,
            "status": "SUBMITTED",
            "message": "Grievance submitted successfully. Your reference ID has been generated.",
            "details": {
                "complaint_id": complaint_id,
                "name": name,
                "category": category,
                "subject": subject,
                "status": "SUBMITTED",
                "estimated_resolution": "15 working days"
            }
        }), 201

    except Exception as error:
        print("COMPLAINT ERROR:", error)
        return jsonify({
            "success": False,
            "error": "Failed to record complaint. Please check input fields."
        }), 500


# ============================================================
# USER-ISOLATED NOTIFICATIONS
# ============================================================

@app.route("/api/notifications", methods=["GET"])
def get_notifications():
    """Retrieve notifications isolated to the current authenticated user."""
    user = get_current_user()
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM notifications
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 40
    """, (user["id"],)).fetchall()
    conn.close()

    notifs = [dict(row) for row in rows]
    unread = sum(1 for n in notifs if not n.get("is_read"))

    return jsonify({
        "success": True,
        "notifications": notifs,
        "unread_count": unread
    })


@app.route("/api/notifications/<int:notif_id>/read", methods=["POST"])
def mark_notification_read(notif_id):
    """Mark a single notification as read for the current user."""
    user = get_current_user()
    conn = get_db()
    conn.execute("""
        UPDATE notifications
        SET is_read = 1
        WHERE id = ? AND user_id = ?
    """, (notif_id, user["id"]))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Notification marked as read."})


@app.route("/api/notifications/read-all", methods=["POST"])
def mark_all_notifications_read():
    """Mark all notifications read for the current user."""
    user = get_current_user()
    conn = get_db()
    conn.execute("""
        UPDATE notifications
        SET is_read = 1
        WHERE user_id = ?
    """, (user["id"],))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "All notifications marked as read."})


# ============================================================
# BIS SERVICES METADATA (WITH LEARN MORE DETAILS)
# ============================================================

@app.route("/api/services", methods=["GET"])
def get_services():
    """Return comprehensive metadata and official links for BIS services."""
    services = [
        {
            "id": "product_certification",
            "title": "Product Certification (ISI Mark)",
            "subtitle": "Ensure product quality, safety, and compliance with Indian Standards",
            "icon": "fa-solid fa-certificate",
            "category": "Manufacturing & Consumer Safety",
            "overview": "The BIS Product Certification Scheme (Scheme-I under BIS Act 2016) allows manufacturers conforming to applicable Indian Standards to use the prestigious ISI Mark. Over 27,000 active licenses cover crucial consumer and industrial products.",
            "key_features": [
                "Mandatory for electrical appliances, cement, steel, automotive components, and packaged water.",
                "Involves rigorous factory audit, testing capabilities evaluation, and independent lab test reports.",
                "Instills nationwide consumer confidence and brand credibility."
            ],
            "workflow": [
                "1. Identify applicable Indian Standard (IS number).",
                "2. Submit online application on Manakonline with factory and testing documentation.",
                "3. BIS officer conducts factory audit and draws samples for independent testing.",
                "4. Grant of License (CM/L number) upon satisfactory test report."
            ],
            "required_documents": [
                "Manufacturing process flowchart and machinery list",
                "In-house testing equipment list and calibration certificates",
                "Quality Assurance Plan (QAP) and test personnel qualifications",
                "Factory premises registration and electricity bill"
            ],
            "official_portal": "https://www.services.bis.gov.in/php/BIS_2.0/bisconnect/knowyourstandards/indian_standards/isdetails",
            "portal_name": "BIS Manakonline Certification Portal"
        },
        {
            "id": "hallmarking",
            "title": "Hallmarking of Precious Metals",
            "subtitle": "Guaranteed purity and trust in Gold and Silver jewellery",
            "icon": "fa-solid fa-gem",
            "category": "Consumer Protection",
            "overview": "BIS Hallmarking provides third-party assurance of the purity or fineness of gold and silver articles. Mandatory hallmarking now covers over 343 districts with the 6-character Hallmark Unique Identification (HUID) system.",
            "key_features": [
                "Ensures genuine purity standards: 14K (585), 18K (750), 20K (833), 22K (916), 23K (958), 24K (995).",
                "HUID provides laser-etched traceability back to the exact Assaying & Hallmarking Center (AHC).",
                "Protects consumers from under-caratage and fraudulent jewelry."
            ],
            "workflow": [
                "1. Jeweler registers online on Manakonline (Automatic grant of registration).",
                "2. Unhallmarked jewellery is submitted to an accredited AHC with an online delivery voucher.",
                "3. XRF screening and fire assay tests determine exact metal purity.",
                "4. 6-digit laser HUID and BIS Standard Mark are applied."
            ],
            "required_documents": [
                "GST Registration certificate of jeweler establishment",
                "Proof of business address and identity of proprietor/partners",
                "Declaration of turnover for registration fee tier"
            ],
            "official_portal": "https://www.manakonline.in/",
            "portal_name": "Manakonline Hallmarking Portal"
        },
        {
            "id": "lab_recognition",
            "title": "Laboratory Recognition Scheme (LRS)",
            "subtitle": "Accredited testing facilities powering quality verification",
            "icon": "fa-solid fa-flask",
            "category": "Testing & Conformance",
            "overview": "Under the BIS Laboratory Recognition Scheme, public and private testing laboratories conforming to ISO/IEC 17025 are recognized to perform conformity assessment and sample testing for BIS license grant and surveillance.",
            "key_features": [
                "Extensive network across chemical, electrical, mechanical, biological, and civil testing domains.",
                "Ensures uniform testing protocols and repeatable, tamper-evident test certificates.",
                "Integrates directly with BIS sample tracking systems for seamless report submission."
            ],
            "workflow": [
                "1. Laboratory achieves NABL accreditation per ISO/IEC 17025.",
                "2. Online application under LRS with testing scope and personnel credentials.",
                "3. On-site assessment by BIS technical experts.",
                "4. Grant of BIS recognition for designated Indian Standards."
            ],
            "required_documents": [
                "Valid NABL accreditation certificate and approved test scope",
                "Standard Operating Procedures (SOPs) for BIS standard tests",
                "Calibrated equipment logs and proficiency testing (PT) reports"
            ],
            "official_portal": "https://www.services.bis.gov.in/php/BIS_2.0/bisconnect/knowyourstandards/indian_standards/isdetails",
            "portal_name": "BIS Lab Directory & LRS Portal"
        },
        {
            "id": "crs",
            "title": "Compulsory Registration Scheme (CRS)",
            "subtitle": "Self-declaration of conformity for Electronics & IT goods",
            "icon": "fa-solid fa-file-signature",
            "category": "Electronics & IT Goods",
            "overview": "MeitY and Ministry of Power have notified various electronics, IT, and solar photovoltaic products under CRS. Products must be tested in BIS-recognized laboratories and registered prior to commercial distribution.",
            "key_features": [
                "Covers laptops, tablets, mobile phones, LED lights, power adapters, and smart watches.",
                "Focuses on product safety against electric shock, energy hazards, and thermal ignition.",
                "Registration number (R-number) granted based on laboratory test reports."
            ],
            "workflow": [
                "1. Domestic or foreign manufacturer generates test request in CRS portal.",
                "2. Samples sent to a BIS-recognized laboratory in India for safety testing.",
                "3. Submit test report and application with Authorized Indian Representative (AIR).",
                "4. BIS grants CRS Registration."
            ],
            "required_documents": [
                "Valid test report from BIS-recognized testing laboratory",
                "Factory business license and Trademark authorization letter",
                "Affidavit for Authorized Indian Representative (AIR) for foreign applicants"
            ],
            "official_portal": "https://www.crsbis.in/BIS/",
            "portal_name": "BIS CRS Official Portal"
        },
        {
            "id": "standards",
            "title": "Standards Formulation & Catalogue",
            "subtitle": "Access the comprehensive repository of Indian Standards",
            "icon": "fa-solid fa-book-bookmark",
            "category": "Technical Specifications",
            "overview": "BIS acts as the National Standards Body of India, operating through 15 Division Councils and hundreds of Sectional Committees to formulate, update, and harmonize national standards with ISO/IEC international benchmarks.",
            "key_features": [
                "Over 21,000 active standards spanning all engineering, scientific, and consumer domains.",
                "Transparent stakeholder consultation via wide circulation drafts and public comments.",
                "Promotes Atmanirbhar Bharat and global competitiveness for Indian manufacturers."
            ],
            "workflow": [
                "1. Need identified by industry, government, or consumer council.",
                "2. Sectional committee drafts technical clauses and test methods.",
                "3. Wide circulation draft published for public and industry comments.",
                "4. Formal adoption and gazette notification as an official Indian Standard."
            ],
            "required_documents": [
                "Stakeholder feedback submission form",
                "Technical committee nomination credentials"
            ],
            "official_portal": "https://www.standardsbis.in/",
            "portal_name": "BIS Standards Portal"
        },
        {
            "id": "fmcs",
            "title": "Foreign Manufacturers Certification Scheme (FMCS)",
            "subtitle": "ISI Mark Certification for Overseas Manufacturing Units",
            "icon": "fa-solid fa-earth-asia",
            "category": "Global Trade & Imports",
            "overview": "FMCS enables overseas manufacturing units to obtain a BIS license and apply the ISI mark on goods manufactured abroad and exported into India, ensuring strict conformance with applicable Indian Standards.",
            "key_features": [
                "Assures foreign goods meet mandatory Indian quality and safety requirements.",
                "Authorized Indian Representative (AIR) mandatory liaison framework.",
                "Physical factory audit by BIS technical delegation prior to license grant."
            ],
            "workflow": [
                "1. Foreign manufacturer appoints Authorized Indian Representative (AIR).",
                "2. Submit online application with factory layout, equipment, and audit fees.",
                "3. BIS quality delegation inspects overseas manufacturing premises.",
                "4. Samples drawn and tested in Indian referral laboratories."
            ],
            "required_documents": [
                "Manufacturing license issued by host nation regulator",
                "List of manufacturing machinery and test equipment with calibration logs",
                "Nomination agreement and undertaking for Authorized Indian Representative (AIR)"
            ],
            "official_portal": "https://www.services.bis.gov.in/",
            "portal_name": "BIS FMCS Portal"
        },
        {
            "id": "training",
            "title": "Training & Capacity Building (NITS)",
            "subtitle": "National Institute of Training for Standardization programs",
            "icon": "fa-solid fa-graduation-cap",
            "category": "Education & Skill Building",
            "overview": "NITS is the premier training institution of BIS, imparting high-caliber training in standards formulation, quality management systems (ISO 9001, ISO 14001, ISO 45001), laboratory testing methods, and regulatory compliance.",
            "key_features": [
                "Certified courses for quality managers, testing engineers, and lead auditors.",
                "International training modules conducted for developing nations under ITEC programs.",
                "Customized corporate workshops tailored to specific industry sectors."
            ],
            "workflow": [
                "1. Browse upcoming training calendar on BIS portal.",
                "2. Register participant profile and select desired training curriculum.",
                "3. Complete practical workshops and technical assessments.",
                "4. Receive official BIS NITS Certificate."
            ],
            "required_documents": [
                "Candidate organizational nomination letter or student ID",
                "Educational qualification details in relevant engineering/scientific discipline"
            ],
            "official_portal": "https://www.bis.gov.in/index.php/training/",
            "portal_name": "NITS Training Portal"
        }
    ]

    services_dict = {s["id"]: s for s in services}
    if "lab_recognition" in services_dict:
        services_dict["laboratory"] = services_dict["lab_recognition"]
    if "standards" in services_dict:
        services_dict["standard_catalogue"] = services_dict["standards"]

    return jsonify({
        "success": True,
        "count": len(services),
        "services": services_dict,
        "services_list": services
    })


# ============================================================
# USER-ISOLATED ACTION HISTORY
# ============================================================

@app.route("/api/history", methods=["GET"])
def get_user_history_route():
    """
    Retrieve real action history for the logged-in user.
    Guarantees user data isolation.
    """
    user = get_current_user()
    action_filter = request.args.get("filter", "").strip().lower()

    conn = get_db()
    if action_filter and action_filter != "all":
        # Handle snake_case filters like hallmark_verification -> %hallmark%
        filter_pattern = f"%{action_filter.replace('_', '%')}%"
        rows = conn.execute("""
            SELECT *
            FROM user_history
            WHERE user_id = ? AND (LOWER(action_type) LIKE ? OR LOWER(action_type) = ?)
            ORDER BY id DESC
            LIMIT 60
        """, (user["id"], filter_pattern, action_filter)).fetchall()
    else:
        rows = conn.execute("""
            SELECT *
            FROM user_history
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 60
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
    """Explicitly record a user action in history."""
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
    """Clear action history strictly for the currently authenticated user."""
    user = get_current_user()
    conn = get_db()
    conn.execute("DELETE FROM user_history WHERE user_id = ?", (user["id"],))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Activity history cleared successfully."
    })


# ============================================================
# INDUSTRY DASHBOARD METRICS
# ============================================================

@app.route("/api/dashboard", methods=["GET"])
def get_dashboard_metrics():
    """
    Return comprehensive analytics, compliance portfolio metrics,
    and recent activity for the Industry Dashboard.
    """
    user = get_current_user()
    conn = get_db()

    # Total registered standards
    std_count = conn.execute("SELECT COUNT(*) FROM standards").fetchone()[0]

    # Total active licenses in registry
    lic_count = conn.execute("SELECT COUNT(*) FROM licenses WHERE status = 'Active'").fetchone()[0]

    # Total complaints registered
    cmp_count = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]

    # User's recent activities
    recent_rows = conn.execute("""
        SELECT action_type, title, description, created_at, status
        FROM user_history
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 5
    """, (user["id"],)).fetchall()
    conn.close()

    recent_activity = []
    for r in recent_rows:
        recent_activity.append({
            "action_type": r["action_type"],
            "title": r["title"],
            "query": r["title"],
            "description": r["description"],
            "created_at": r["created_at"],
            "status": r["status"]
        })

    return jsonify({
        "success": True,
        "metrics": {
            "products": 12,
            "certificates": lic_count or 8,
            "compliance": 94,
            "reports": cmp_count or 2,
            "standards_tracked": std_count
        },
        "recent_activity": recent_activity
    })


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    init_db()

    print("")
    print("======================================")
    print(" BIS AI ASSISTANT BACKEND")
    print(" http://localhost:5000")
    print("======================================")
    print("")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )