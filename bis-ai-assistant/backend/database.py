import sqlite3
import os
from datetime import datetime


# ============================================================
# DATABASE PATH
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "bis.db")


# ============================================================
# GET DATABASE CONNECTION
# ============================================================

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_db():

    conn = get_db()
    cursor = conn.cursor()

    # ========================================================
    # STANDARDS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS standards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            is_number TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT,
            industry TEXT,
            year INTEGER,
            status TEXT DEFAULT 'Active',
            certification TEXT,
            keywords TEXT
        )
    """)

    # ========================================================
    # BIS LICENSES
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_number TEXT UNIQUE NOT NULL,
            product TEXT,
            manufacturer TEXT,
            standard TEXT,
            validity_from TEXT,
            validity_to TEXT,
            status TEXT DEFAULT 'Active'
        )
    """)

    # ========================================================
    # DOCUMENTS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            filename TEXT NOT NULL,

            filepath TEXT,

            file_type TEXT,

            extracted_text TEXT,

            summary TEXT,

            compliance_score INTEGER,

            ocr_used INTEGER DEFAULT 0,

            status TEXT DEFAULT 'PROCESSED',

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            uploaded_at TEXT
        )
    """)

    # ========================================================
    # HISTORY
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            query TEXT,

            response TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ========================================================
    # COMPLIANCE REPORTS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compliance_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            product TEXT,

            standard TEXT,

            score INTEGER,

            risk TEXT,

            result TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ========================================================
    # DEMO STANDARDS
    # ========================================================

    standards = [

        (
            "IS 10322 : 2012",
            "LED Luminaires for General Lighting Purposes – Safety Requirements",
            "Safety requirements for LED luminaires used in general lighting applications.",
            "Electrical",
            "Lighting",
            2012,
            "Active",
            "Product Certification",
            "LED,luminaire,street light,lighting"
        ),

        (
            "IS 302 (Part 1) : 2024",
            "Safety of Household Electrical Appliances",
            "General safety requirements for household electrical appliances.",
            "Electrical Appliances",
            "Consumer Electronics",
            2024,
            "Active",
            "Product Certification",
            "electrical,appliance,household"
        ),

        (
            "IS 456 : 2000",
            "Plain and Reinforced Concrete – Code of Practice",
            "Code of practice for plain and reinforced concrete.",
            "Civil",
            "Construction",
            2000,
            "Active",
            "Voluntary",
            "concrete,civil,construction"
        )
    ]

    for standard in standards:

        cursor.execute("""
            INSERT OR IGNORE INTO standards
            (
                is_number,
                title,
                description,
                category,
                industry,
                year,
                status,
                certification,
                keywords
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, standard)

    # ========================================================
    # DEMO LICENSE
    # ========================================================

    cursor.execute("""
        INSERT OR IGNORE INTO licenses
        (
            license_number,
            product,
            manufacturer,
            standard,
            validity_from,
            validity_to,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (

        "CM/L-1234567",

        "LED Street Light",

        "ABC Electronics Pvt. Ltd.",

        "IS 10322 : 2012",

        "12 Jan 2024",

        "11 Jan 2027",

        "Active"
    ))

    conn.commit()
    conn.close()


# ============================================================
# SAVE DOCUMENT
# ============================================================

def save_document(
    filename,
    file_type,
    extracted_text,
    ocr_used=False,
    filepath=None,
    summary=None,
    compliance_score=None
):

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

        filepath,

        file_type,

        extracted_text,

        summary,

        compliance_score,

        1 if ocr_used else 0,

        "PROCESSED",

        datetime.now().isoformat()
    ))

    document_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return document_id


# ============================================================
# GET ALL DOCUMENTS
# ============================================================

def get_documents():

    conn = get_db()

    documents = conn.execute("""
        SELECT
            id,
            filename,
            filepath,
            file_type,
            ocr_used,
            status,
            compliance_score,
            created_at,
            uploaded_at
        FROM documents
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return [dict(document) for document in documents]


# ============================================================
# GET ONE DOCUMENT
# ============================================================

def get_document(document_id):

    conn = get_db()

    document = conn.execute("""
        SELECT *
        FROM documents
        WHERE id = ?
    """, (document_id,)).fetchone()

    conn.close()

    if document:
        return dict(document)

    return None


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    init_db()

    print("Database initialized successfully.")

    print("Database location:")
    print(DB_PATH)


# import sqlite3
# import os

# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# DB_PATH = os.path.join(BASE_DIR, "data", "bis.db")


# def get_db():
#     os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     return conn


# def init_db():

#     conn = get_db()
#     cursor = conn.cursor()

#     # Standards
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS standards (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             is_number TEXT UNIQUE NOT NULL,
#             title TEXT NOT NULL,
#             description TEXT,
#             category TEXT,
#             industry TEXT,
#             year INTEGER,
#             status TEXT DEFAULT 'Active',
#             certification TEXT,
#             keywords TEXT
#         )
#     """)

#     # BIS licenses
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS licenses (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             license_number TEXT UNIQUE NOT NULL,
#             product TEXT,
#             manufacturer TEXT,
#             standard TEXT,
#             validity_from TEXT,
#             validity_to TEXT,
#             status TEXT DEFAULT 'Active'
#         )
#     """)

#     # Uploaded documents
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS documents (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             filename TEXT,
#             filepath TEXT,
#             extracted_text TEXT,
#             summary TEXT,
#             compliance_score INTEGER,
#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#         )
#     """)

#     # Queries/history
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS history (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             query TEXT,
#             response TEXT,
#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#         )
#     """)

#     # Compliance reports
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS compliance_reports (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             product TEXT,
#             standard TEXT,
#             score INTEGER,
#             risk TEXT,
#             result TEXT,
#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#         )
#     """)

#     conn.commit()

#     # Demo standards
#     standards = [
#         (
#             "IS 10322 : 2012",
#             "LED Luminaires for General Lighting Purposes – Safety Requirements",
#             "Safety requirements for LED luminaires used in general lighting applications.",
#             "Electrical",
#             "Lighting",
#             2012,
#             "Active",
#             "Product Certification",
#             "LED,luminaire,street light,lighting"
#         ),
#         (
#             "IS 302 (Part 1) : 2024",
#             "Safety of Household Electrical Appliances",
#             "General safety requirements for household electrical appliances.",
#             "Electrical Appliances",
#             "Consumer Electronics",
#             2024,
#             "Active",
#             "Product Certification",
#             "electrical,appliance,household"
#         ),
#         (
#             "IS 456 : 2000",
#             "Plain and Reinforced Concrete – Code of Practice",
#             "Code of practice for plain and reinforced concrete.",
#             "Civil",
#             "Construction",
#             2000,
#             "Active",
#             "Voluntary",
#             "concrete,civil,construction"
#         )
#     ]

#     for standard in standards:
#         cursor.execute("""
#             INSERT OR IGNORE INTO standards
#             (
#                 is_number,
#                 title,
#                 description,
#                 category,
#                 industry,
#                 year,
#                 status,
#                 certification,
#                 keywords
#             )
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
#         """, standard)

#     # Demo verification record
#     cursor.execute("""
#         INSERT OR IGNORE INTO licenses
#         (
#             license_number,
#             product,
#             manufacturer,
#             standard,
#             validity_from,
#             validity_to,
#             status
#         )
#         VALUES (?, ?, ?, ?, ?, ?, ?)
#     """, (
#         "CM/L-1234567",
#         "LED Street Light",
#         "ABC Electronics Pvt. Ltd.",
#         "IS 10322 : 2012",
#         "12 Jan 2024",
#         "11 Jan 2027",
#         "Active"
#     ))

#     conn.commit()
#     conn.close()


# if __name__ == "__main__":
#     init_db()
#     print("Database initialized.")