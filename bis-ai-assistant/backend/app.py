import os
import json

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

from database import get_db, init_db
from ai_engine import process_ai_query
from compliance_engine import analyze_compliance
from document_engine import extract_document, generate_summary, analyze_document_content
from flask import send_from_directory


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

    data = request.get_json(
        silent=True
    ) or {}

    query = data.get(
        "query",
        ""
    ).strip()

    if not query:

        return jsonify({
            "error": "Query is required."
        }), 400

    result = process_ai_query(query)

    conn = get_db()

    conn.execute("""
        INSERT INTO history
        (query, response)
        VALUES (?, ?)
    """, (
        query,
        json.dumps(result)
    ))

    conn.commit()
    conn.close()

    return jsonify(result)


# ============================================================
# STANDARDS SEARCH
# ============================================================

@app.route("/api/standards", methods=["GET"])
def standards():

    query = request.args.get(
        "q",
        ""
    ).strip()

    category = request.args.get(
        "category",
        ""
    ).strip()

    industry = request.args.get(
        "industry",
        ""
    ).strip()

    year = request.args.get(
        "year",
        ""
    ).strip()

    status = request.args.get(
        "status",
        ""
    ).strip()

    conn = get_db()

    sql = """
        SELECT *
        FROM standards
        WHERE 1=1
    """

    params = []

    if query:

        sql += """
            AND (
                is_number LIKE ?
                OR title LIKE ?
                OR description LIKE ?
                OR keywords LIKE ?
            )
        """

        keyword = f"%{query}%"

        params.extend([
            keyword,
            keyword,
            keyword,
            keyword
        ])

    if category:

        sql += """
            AND category = ?
        """

        params.append(category)

    if industry:

        sql += """
            AND industry = ?
        """

        params.append(industry)

    if year:

        sql += """
            AND year = ?
        """

        params.append(year)

    if status:

        sql += """
            AND status = ?
        """

        params.append(status)

    sql += """
        ORDER BY year DESC
    """

    rows = conn.execute(
        sql,
        params
    ).fetchall()

    conn.close()

    return jsonify({

        "count": len(rows),

        "standards": [
            dict(row)
            for row in rows
        ]

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

        return jsonify({

            "verified": False,

            "message": (
                "License not found in the "
                "verification database."
            )

        }), 404

    return jsonify({

        "verified": row["status"] == "Active",

        "details": {

            "license_number":
                row["license_number"],

            "product":
                row["product"],

            "manufacturer":
                row["manufacturer"],

            "standard":
                row["standard"],

            "validity_from":
                row["validity_from"],

            "validity_to":
                row["validity_to"],

            "status":
                row["status"]

        }

    })


# ============================================================
# DASHBOARD
# ============================================================

@app.route(
    "/api/dashboard",
    methods=["GET"]
)
def dashboard():

    conn = get_db()

    products = conn.execute("""
        SELECT COUNT(*) AS count
        FROM documents
    """).fetchone()["count"]

    certificates = conn.execute("""
        SELECT COUNT(*) AS count
        FROM licenses
        WHERE status = 'Active'
    """).fetchone()["count"]

    compliance = conn.execute("""
        SELECT AVG(score) AS average
        FROM compliance_reports
    """).fetchone()["average"]

    reports = conn.execute("""
        SELECT COUNT(*) AS count
        FROM compliance_reports
    """).fetchone()["count"]

    recent_history = conn.execute("""
        SELECT query, created_at
        FROM history
        ORDER BY id DESC
        LIMIT 5
    """).fetchall()

    conn.close()

    compliance_score = (
        round(compliance)
        if compliance is not None
        else 0
    )

    return jsonify({

        "metrics": {

            "products":
                products,

            "certificates":
                certificates,

            "compliance":
                compliance_score,

            "reports":
                reports

        },

        "recent_activity": [

            dict(row)

            for row in recent_history

        ]

    })


# ============================================================
# HISTORY
# ============================================================

@app.route(
    "/api/history",
    methods=["GET"]
)
def history():

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM history
        ORDER BY id DESC
        LIMIT 50
    """).fetchall()

    conn.close()

    return jsonify({

        "history": [

            dict(row)

            for row in rows

        ]

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