import sqlite3
import os
import json
import uuid
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
# DYNAMIC SCHEMA MIGRATION HELPER
# ============================================================

def ensure_columns(cursor, table_name, column_defs):
    """
    Ensure required columns exist in SQLite table without breaking existing data.
    """
    try:
        cursor.execute(f"PRAGMA table_info({table_name});")
        existing_cols = {row[1].lower() for row in cursor.fetchall()}
        for col_name, col_def in column_defs.items():
            if col_name.lower() not in existing_cols:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def};")
    except Exception as e:
        print(f"Migration check notice for {table_name}: {e}")



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
    # USERS TABLE
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            picture TEXT,
            role TEXT DEFAULT 'Citizen / Industry User',
            auth_provider TEXT DEFAULT 'google',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ========================================================
    # USER SESSIONS TABLE
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    """)

    # ========================================================
    # USER ACTION HISTORY TABLE
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            meta_json TEXT,
            status TEXT DEFAULT 'SUCCESS',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ========================================================
    # NOTIFICATIONS TABLE
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ========================================================
    # COMPLAINTS TABLE
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT UNIQUE NOT NULL,
            user_id TEXT,
            name TEXT NOT NULL,
            contact TEXT NOT NULL,
            category TEXT NOT NULL,
            ref_number TEXT,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'SUBMITTED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ========================================================
    # HALLMARK VERIFICATION REGISTRY TABLE
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hallmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            huid TEXT UNIQUE NOT NULL,
            article_type TEXT NOT NULL,
            purity TEXT NOT NULL,
            jeweler_name TEXT NOT NULL,
            ahc_name TEXT NOT NULL,
            hallmark_date TEXT NOT NULL,
            status TEXT DEFAULT 'VERIFIED'
        )
    """)

    # Dynamic migrations to ensure backward compatibility
    ensure_columns(cursor, 'documents', {
        'file_type': 'TEXT',
        'extracted_text': 'TEXT',
        'summary': 'TEXT',
        'compliance_score': 'INTEGER',
        'ocr_used': 'INTEGER DEFAULT 0',
        'status': "TEXT DEFAULT 'PROCESSED'",
        'uploaded_at': 'TEXT'
    })

    ensure_columns(cursor, 'user_history', {
        'user_id': 'TEXT',
        'action_type': 'TEXT',
        'title': 'TEXT',
        'description': 'TEXT',
        'meta_json': 'TEXT',
        'status': "TEXT DEFAULT 'SUCCESS'"
    })

    conn.commit()

    # ========================================================
    # SEED DEMO USER (FOR EVALUATION / DEV)
    # ========================================================

    cursor.execute("""
        INSERT OR IGNORE INTO users (id, email, name, picture, role, auth_provider)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        'usr_officer_demo_01',
        'officer@bis.gov.in',
        'Raj Kumar',
        'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150',
        'BIS Quality Assurance Officer',
        'demo'
    ))

    # ========================================================
    # RICH BIS STANDARDS SEED DATA
    # ========================================================

    standards = [
        ("IS 10322 : 2012", "LED Luminaires for General Lighting Purposes – Safety Requirements", "Safety requirements for LED luminaires used in general lighting applications.", "Electrical", "Lighting", 2012, "Active", "Product Certification", "LED,luminaire,street light,lighting"),
        ("IS 302 (Part 1) : 2024", "Safety of Household Electrical Appliances", "General safety requirements for household and similar electrical appliances.", "Electrical Appliances", "Consumer Electronics", 2024, "Active", "Product Certification", "electrical,appliance,household,safety"),
        ("IS 456 : 2000", "Plain and Reinforced Concrete – Code of Practice", "Code of practice for plain and reinforced concrete structures.", "Civil", "Construction", 2000, "Active", "Voluntary", "concrete,civil,construction,cement"),
        ("IS 1293 : 2019", "Plugs and Socket-Outlets for Domestic and Similar Purposes", "Requirements for plugs and socket-outlets rated up to 250V and 16A.", "Electrical", "Consumer Goods", 2019, "Active", "Product Certification", "plug,socket,electrical,outlet,switch"),
        ("IS 16046 (Part 1) : 2018", "Secondary Cells and Batteries Containing Alkaline / Non-Acid Electrolytes", "Safety requirements for secondary lithium cells and batteries in portable applications.", "Electronics", "Consumer Electronics", 2018, "Active", "Compulsory Registration", "battery,lithium,cell,electronics,mobile,safety"),
        ("IS 15885 (Part 2/Sec 13) : 2012", "Lamp Controlgear for LED Modules – Particular Requirements", "Safety and performance requirements for AC/DC electronic controlgear for LED modules.", "Electrical", "Lighting", 2012, "Active", "Product Certification", "led,driver,controlgear,ballast,power supply"),
        ("IS 14543 : 2024", "Packaged Drinking Water (Other than Natural Mineral Water)", "Specification for packaged drinking water including microbiological and chemical limits.", "Food & Agriculture", "Food & Beverages", 2024, "Active", "Product Certification", "water,drinking water,packaged water,bottle,beverage"),
        ("IS 694 : 2010", "Polyvinyl Chloride (PVC) Insulated Cables for Working Voltages up to 1100V", "Requirements for single core and multicore PVC insulated electrical cables.", "Electrical", "Power & Transmission", 2010, "Active", "Product Certification", "wire,cable,pvc,copper,transmission,electrical"),
        ("IS 2062 : 2011", "Hot Rolled Medium and High Tensile Structural Steel", "Standard for structural quality hot rolled steel plates, sections, and flats.", "Mechanical", "Manufacturing", 2011, "Active", "Product Certification", "steel,structural,hot rolled,plates,manufacturing"),
        ("IS 15298 (Part 2) : 2016", "Personal Protective Equipment – Safety Footwear", "Safety requirements and test methods for occupational safety footwear.", "Textiles", "Manufacturing & Safety", 2016, "Active", "Product Certification", "footwear,safety shoes,ppe,protective,boots"),
        ("IS 1786 : 2008", "High Strength Deformed Steel Bars for Concrete Reinforcement", "Technical requirements for thermo-mechanically treated (TMT) steel reinforcement bars.", "Civil", "Construction", 2008, "Active", "Product Certification", "tmt,rebar,steel,bars,concrete,construction"),
        ("IS 73 : 2013", "Paving Bitumen – Specification", "Grades and specifications for paving grade bitumen used in road and highway construction.", "Chemical", "Infrastructure & Roads", 2013, "Active", "Voluntary", "bitumen,asphalt,roads,highway,chemical,paving"),
        ("IS 16102 (Part 1) : 2012", "Self-Ballasted LED Lamps for General Lighting Services – Safety", "Safety requirements for self-ballasted LED lamps for domestic and commercial lighting.", "Electrical", "Lighting", 2012, "Active", "Compulsory Registration", "led bulb,lamp,self ballasted,lighting,energy"),
        ("IS 13252 (Part 1) : 2010", "Information Technology Equipment – Safety – General Requirements", "Essential safety requirements for IT equipment, computers, chargers and power supplies.", "Electronics", "Information Technology", 2010, "Active", "Compulsory Registration", "it equipment,computer,laptop,charger,safety,adapter"),
        ("IS 269 : 2015", "Ordinary Portland Cement – Specification", "Physical and chemical requirements for 33, 43, and 53 grade Ordinary Portland Cement.", "Civil", "Construction", 2015, "Active", "Product Certification", "cement,portland cement,opc,concrete,civil"),
        ("IS 1239 (Part 1) : 2004", "Mild Steel Tubes, Tubulars and Other Wrought Steel Fittings - Part 1: Steel Tubes", "Requirements for welded and seamless, screwed and socketed, and plain end mild steel tubes for water, gas, air, and steam. Specifies OD limit tolerances of +10% to -10%.", "Metallurgy & Steel", "Manufacturing", 2004, "Active", "Product Certification", "mild steel tubes,tubulars,steel pipe,outer diameter,hydraulic,hydrostatic,tolerance,pipe"),
        ("IS 1489 (Part 1) : 2015", "Portland Pozzolana Cement Specification (Part 1: Fly Ash Based)", "Specification for fly ash based Portland Pozzolana Cement for civil engineering and general building construction.", "Civil Engineering", "Construction", 2015, "Active", "Product Certification", "cement,pozzolana,fly ash,portland,concrete"),
        ("IS 1865 : 1991", "Spheroidal Graphite Iron Castings Specification", "Requirements for spheroidal graphite or nodular iron castings used for automotive and engineering parts.", "Metallurgy & Steel", "Automotive & Engineering", 1991, "Active", "Voluntary", "iron castings,graphite,nodular iron,castings,metallurgy")
    ]

    for std in standards:
        cursor.execute("""
            INSERT OR REPLACE INTO standards
            (is_number, title, description, category, industry, year, status, certification, keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, std)

    # ========================================================
    # SEED LICENSES
    # ========================================================

    cursor.execute("""
        INSERT OR IGNORE INTO licenses
        (license_number, product, manufacturer, standard, validity_from, validity_to, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        'CM/L-1234567',
        'LED Street Light',
        'ABC Electronics Pvt. Ltd.',
        'IS 10322 : 2012',
        '12 Jan 2024',
        '11 Jan 2027',
        'Active'
    ))

    cursor.execute("""
        INSERT OR IGNORE INTO licenses
        (license_number, product, manufacturer, standard, validity_from, validity_to, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        'CM/L-7654321',
        'Household Electric Iron',
        'HomeCare Appliances Ltd.',
        'IS 302 (Part 1) : 2024',
        '01 Mar 2023',
        '28 Feb 2026',
        'Active'
    ))

    cursor.execute("""
        INSERT OR IGNORE INTO licenses
        (license_number, product, manufacturer, standard, validity_from, validity_to, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        'CM/L-9812234',
        'Steel Pipes & Tubular Fittings',
        'Tata Quality Castings',
        'IS 1239 (Part 1) : 2004',
        '15 Oct 2023',
        '14 Oct 2026',
        'Active'
    ))

    # ========================================================
    # SEED HALLMARK REGISTRY RECORDS
    # ========================================================

    hallmarks = [
        ('AB1234', 'Gold Ring 22K (916)', '22K (916 Purity)', 'Tanishq Jewellers, New Delhi', 'Shree Ganesh Assaying & Hallmarking Center (AHC-0104)', '14 Aug 2024'),
        ('MN5678', 'Gold Bangle 18K (750)', '18K (750 Purity)', 'Kalyan Jewellers, Mumbai', 'National Bullion Assaying Center (AHC-0211)', '02 Sep 2024'),
        ('KL9012', 'Silver Coin 999 Fine', '99.9% Fine Silver', 'MMTC-PAMP India Pvt. Ltd.', 'MMTC Assaying Center, Gurugram (AHC-0005)', '19 Jan 2025'),
        ('HG3421', 'Gold Necklace 22K (916)', '22K (916 Purity)', 'Malabar Gold & Diamonds, Bengaluru', 'Southern Hallmark Assayers (AHC-0322)', '10 Nov 2024')
    ]

    for h in hallmarks:
        cursor.execute("""
            INSERT OR REPLACE INTO hallmarks
            (huid, article_type, purity, jeweler_name, ahc_name, hallmark_date, status)
            VALUES (?, ?, ?, ?, ?, ?, 'VERIFIED')
        """, h)

    # ========================================================
    # SEED COMPLAINTS (FIGMA DESIGN LOG RECORDS)
    # ========================================================

    complaints_seed = [
        ('CMP-2026-042', 'usr_officer_demo_01', 'Inspector G. S. Bhatti', 'g.bhatti@bis.gov.in', 'ISI Mark Misuse', 'IS 1239 : Part 1', 'Substandard MS Pipes Batch C', 'Substandard wall thickness detected in commercial batch shipments. OD limit exceeded.', 'IN_PROGRESS'),
        ('CMP-2026-039', 'usr_officer_demo_01', 'Dr. R. K. Prasad', 'rkprasad@nic.in', 'Counterfeit Goods', 'IS 2062 : 2011', 'Counterfeit Structural Steel Beams', 'Counterfeit ISI mark labeling and substandard tensile strength on structural steel angles.', 'UNDER_REVIEW'),
        ('CMP-2026-035', 'usr_officer_demo_01', 'Officer A. K. Sen', 'ak.sen@bis.gov.in', 'Product Quality', 'IS 1489 : Part 1', 'Adulterated Portland Pozzolana Cement', 'Fly-ash ratio variance observed exceeding mandatory 35% ceiling.', 'RESOLVED'),
        ('CMP-2026-031', 'usr_officer_demo_01', 'Citizen Complainant', 'citizen@consumer.org', 'Uncertified Product', 'IS 302 : Part 1', 'Non-certified Domestic Switches', 'Domestic toggle switches sold without mandatory ISI certification marking.', 'PENDING')
    ]

    for c in complaints_seed:
        cursor.execute("""
            INSERT OR IGNORE INTO complaints
            (complaint_id, user_id, name, contact, category, ref_number, subject, description, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, c)

    # ========================================================
    # SEED INITIAL NOTIFICATIONS
    # ========================================================

    notif_count = cursor.execute("SELECT COUNT(*) FROM notifications WHERE user_id = 'usr_officer_demo_01'").fetchone()[0]
    if notif_count == 0:
        notifications_seed = [
            ('usr_officer_demo_01', 'BIS Live Server Database Synchronization Completed', 'All 24,000+ active IS standard documents synchronized successfully with centralized gazette register.', 'system', 0),
            ('usr_officer_demo_01', 'Critical Gaps Found in Precast Concrete Solid Billet Audit', 'Audit report AUD-233B flagged for junction thickness drops. Requires immediate administrative calibration notification.', 'warning', 0),
            ('usr_officer_demo_01', 'New Amendment Published for Portland Cement (IS 1489)', 'BIS metallurgical division issued Gazetted revision details on fly-ash ratios. Check standard compliance checker update requirements.', 'info', 0),
            ('usr_officer_demo_01', 'New Consumable Substandard Product Complaint Filed', 'Substandard Steel Pipe Batch C violation complaint registered under CMP-2026-042. Assigned automatically to G. S. Bhatti.', 'info', 1)
        ]
        for n in notifications_seed:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type, is_read)
                VALUES (?, ?, ?, ?, ?)
            """, n)

    conn.commit()
    conn.close()


# ============================================================
# HELPER FUNCTIONS FOR USER ISOLATION, HISTORY & NOTIFICATIONS
# ============================================================

def add_user_history(user_id, action_type, title, description, meta=None, status='SUCCESS'):
    """Record an action specifically for the authenticated user."""
    conn = get_db()
    meta_json = json.dumps(meta) if meta else None
    conn.execute("""
        INSERT INTO user_history (user_id, action_type, title, description, meta_json, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, action_type, title, description, meta_json, status))
    # Also record into global history for dashboard activity
    conn.execute("""
        INSERT INTO history (query, response)
        VALUES (?, ?)
    """, (f"{title}: {description}", meta_json or ""))
    conn.commit()
    conn.close()

def add_notification(user_id, title, message, notif_type='info'):
    """Create a user-isolated notification."""
    conn = get_db()
    conn.execute("""
        INSERT INTO notifications (user_id, title, message, type)
        VALUES (?, ?, ?, ?)
    """, (user_id, title, message, notif_type))
    conn.commit()
    conn.close()

def create_session(user_id):
    """Generate a cryptographically secure session token."""
    token = 'bis_sess_' + str(uuid.uuid4()).replace('-', '')
    conn = get_db()
    conn.execute("""
        INSERT INTO user_sessions (token, user_id)
        VALUES (?, ?)
    """, (token, user_id))
    conn.commit()
    conn.close()
    return token

def get_user_by_session(token):
    """Retrieve user dictionary using session token."""
    if not token:
        return None
    conn = get_db()
    row = conn.execute("""
        SELECT u.* FROM users u
        JOIN user_sessions s ON u.id = s.user_id
        WHERE s.token = ?
    """, (token,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ============================================================
# DOCUMENT HELPERS
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


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully with complete tables, schema migrations, and rich BIS standards.")
    print("Database location:", DB_PATH)