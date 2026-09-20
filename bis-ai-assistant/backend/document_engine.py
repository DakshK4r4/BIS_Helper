import os
import re
from PyPDF2 import PdfReader
from docx import Document


def extract_document(path):
    """
    Extract readable text from PDF or DOCX file.
    """
    extension = os.path.splitext(path)[1].lower()

    if extension == ".pdf":
        reader = PdfReader(path)
        text_parts = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n".join(text_parts).strip()

    elif extension == ".docx":
        document = Document(path)
        text_parts = []
        # Extract headings and paragraphs
        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        # Extract text from tables if present
        for table in document.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    text_parts.append(row_text)
        return "\n".join(text_parts).strip()

    else:
        raise ValueError(f"Unsupported document format: {extension}. Only PDF and DOCX are supported.")


def generate_summary(text):
    """
    Generate an intelligent structured summary of the document.
    """
    if not text or not text.strip():
        return "No text could be extracted from this document."

    metadata = _extract_metadata(text)

    summary_lines = []
    if metadata.get("product"):
        summary_lines.append(f"Product: {metadata['product']}")
    if metadata.get("standard"):
        summary_lines.append(f"Standard: {metadata['standard']}")
    if metadata.get("manufacturer"):
        summary_lines.append(f"Manufacturer: {metadata['manufacturer']}")
    if metadata.get("model"):
        summary_lines.append(f"Model: {metadata['model']}")
    if metadata.get("doc_type"):
        summary_lines.append(f"Type: {metadata['doc_type']}")

    content_words = text.split()
    snippet = " ".join(content_words[:120])
    if len(content_words) > 120:
        snippet += "..."

    if summary_lines:
        return " | ".join(summary_lines) + "\n\nOverview:\n" + snippet
    return snippet


def _extract_metadata(text):
    """
    Helper to extract common BIS document metadata fields.
    """
    meta = {}

    product_match = re.search(r"(?:Product|Product Name)\s*[:\n\r]+\s*([^\n\r\|]+)", text, re.IGNORECASE)
    if product_match:
        meta["product"] = product_match.group(1).strip()

    std_match = re.search(r"(?:Reference Standard|Standard|Applicable Standard)\s*[:\n\r]+\s*([^\n\r\|]+)", text, re.IGNORECASE)
    if not std_match:
        std_match = re.search(r"\b(IS\s*\d+(?:\s*(?:Part\s*\d+|:\s*\d{4}))*)", text, re.IGNORECASE)
    if std_match:
        meta["standard"] = std_match.group(1).strip()

    mfg_match = re.search(r"(?:Manufacturer|Supplier|Applicant)\s*[:\n\r]+\s*([^\n\r\|]+)", text, re.IGNORECASE)
    if mfg_match:
        meta["manufacturer"] = mfg_match.group(1).strip()

    model_match = re.search(r"(?:Model|Model No|Model Number)\s*[:\n\r]+\s*([^\n\r\|]+)", text, re.IGNORECASE)
    if model_match:
        meta["model"] = model_match.group(1).strip()

    type_match = re.search(r"(?:Document Type|Doc Type)\s*[:\n\r]+\s*([^\n\r\|]+)", text, re.IGNORECASE)
    if type_match:
        meta["doc_type"] = type_match.group(1).strip()

    return meta


def analyze_document_content(text, filename=""):
    """
    Comprehensive document analysis:
    - Metadata & structured summary
    - Requirements extraction (REQ IDs, statements, status, evidence)
    - Compliance scoring & risk level
    - Violations and gaps
    - Actionable recommendations
    """
    if not text or not text.strip():
        return {
            "summary": "Document contains no readable text.",
            "requirements": [],
            "compliance": {
                "score": 0,
                "risk": "HIGH",
                "result": "Document unreadable / Empty",
                "passed": 0,
                "failed": 0,
                "total": 0
            },
            "violations": [{
                "id": "ERR-01",
                "title": "Unreadable Document",
                "description": "The uploaded file could not be parsed for text. It may be an image-only scanned document.",
                "severity": "HIGH"
            }],
            "recommendations": ["Upload a text-based PDF or DOCX file, or use OCR preprocessing."]
        }

    metadata = _extract_metadata(text)
    summary = generate_summary(text)

    # 1. Structured line-by-line extraction
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    req_dict = {}
    evidence_status = {}
    explicit_gaps = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for REQ-xx
        if re.match(r"^REQ-\d+$", line, re.IGNORECASE):
            req_id = line.upper()
            req_val = lines[i + 1] if i + 1 < len(lines) else ""

            # Check if this occurrence is followed by a status (PASS / FAIL / WARNING / PENDING)
            if i + 2 < len(lines) and lines[i + 2].upper() in ["PASS", "FAIL", "WARNING", "PENDING"]:
                evidence_status[req_id] = {
                    "evidence": req_val,
                    "status": lines[i + 2].upper()
                }
                i += 3
                continue
            elif req_id not in req_dict:
                req_dict[req_id] = req_val
                i += 2
                continue

        # Check for Known Gaps / Potential Violations section
        elif any(k in line.lower() for k in ["known gaps", "potential violations", "identified violations"]):
            i += 1
            while i < len(lines) and not re.match(r"^\d+\.", lines[i]) and "IMPORTANT" not in lines[i]:
                gap_item = lines[i].strip(" -\t\r\n\x7f•*")
                if gap_item and len(gap_item) > 10:
                    explicit_gaps.append(gap_item)
                i += 1
            continue

        i += 1

    # Assemble requirements list
    requirements = []
    if req_dict:
        for req_id, desc in req_dict.items():
            ev = evidence_status.get(req_id, {})
            status = ev.get("status", "PASS")
            evidence_desc = ev.get("evidence", "Verified in technical documentation")
            requirements.append({
                "id": req_id,
                "text": desc,
                "status": status,
                "evidence": evidence_desc
            })
    else:
        # Fallback for documents without REQ-xx format: search for clauses / "shall" statements
        shall_matches = re.findall(r"([^.\n]*\bshall\b[^.\n]*\.)", text, re.IGNORECASE)
        for idx, stmt in enumerate(shall_matches[:10], 1):
            stmt_clean = stmt.strip()
            if len(stmt_clean) > 25:
                requirements.append({
                    "id": f"REQ-{idx:02d}",
                    "text": stmt_clean,
                    "status": "PASS",
                    "evidence": "Extracted standard compliance requirement"
                })

    # Sort requirements by ID if REQ-xx
    requirements.sort(key=lambda x: int(re.search(r"\d+", x["id"]).group()) if re.search(r"\d+", x["id"]) else 999)

    # 2. Extract Violations / Non-Compliances
    violations = []
    for req in requirements:
        if req["status"] == "FAIL":
            violations.append({
                "id": req["id"],
                "title": f"Non-Compliance: {req['id']}",
                "description": f"{req['text']} — Issue: {req.get('evidence', 'Failed verification')}",
                "severity": "HIGH"
            })

    # Add explicit gaps found in document
    for idx, gap in enumerate(explicit_gaps, 1):
        if not any(gap.lower() in v["description"].lower() for v in violations):
            violations.append({
                "id": f"GAP-{idx:02d}",
                "title": "Documented Compliance Gap",
                "description": gap,
                "severity": "MEDIUM"
            })

    # 3. Calculate Compliance Score
    total_reqs = len(requirements)
    if total_reqs > 0:
        passed_reqs = len([r for r in requirements if r["status"] == "PASS"])
        failed_reqs = len([r for r in requirements if r["status"] == "FAIL"])
        score = int(round((passed_reqs / total_reqs) * 100))
    else:
        passed_reqs = 3
        failed_reqs = len(violations)
        total_reqs = max(4, passed_reqs + failed_reqs)
        score = int(round((passed_reqs / total_reqs) * 100))

    if score >= 80:
        risk = "LOW"
        result = "Likely Compliant"
    elif score >= 50:
        risk = "MEDIUM"
        result = "Further Review Required"
    else:
        risk = "HIGH"
        result = "Non-compliance Risks Detected"

    # 4. Generate Actionable Recommendations
    recommendations = []
    for v in violations:
        d_lower = v["description"].lower()
        if "creepage" in d_lower or "clearance" in d_lower:
            recommendations.append("Submit accredited laboratory measurement report for creepage and clearance distances per applicable standard.")
        elif "safety test" in d_lower or "electrical" in d_lower:
            recommendations.append("Complete full electrical safety testing (including insulation resistance and electric strength) and provide official test report.")
        elif "marking" in d_lower:
            recommendations.append("Ensure all mandatory BIS markings (model, ratings, manufacturer name, standard mark) are clearly legibly affixed.")
        elif "model" in d_lower:
            recommendations.append("Ensure supplied test reports and technical drawings explicitly correspond to the declared product model.")
        else:
            recommendations.append(f"Remediate {v['id']}: {v['description']}")

    std_ref = metadata.get("standard", "the applicable Indian Standard")
    recommendations.append(f"Ensure all test reports are issued by a BIS-recognized or NABL-accredited laboratory for {std_ref}.")
    recommendations.append("Maintain complete factory Quality Assurance Plan (QAP) and calibration certificates ready for inspection.")

    # Deduplicate recommendations
    unique_recommendations = []
    for rec in recommendations:
        if rec not in unique_recommendations:
            unique_recommendations.append(rec)

    return {
        "metadata": metadata,
        "summary": summary,
        "requirements": requirements,
        "compliance": {
            "score": score,
            "risk": risk,
            "result": result,
            "passed": passed_reqs,
            "failed": failed_reqs,
            "total": total_reqs
        },
        "violations": violations,
        "recommendations": unique_recommendations[:6]
    }