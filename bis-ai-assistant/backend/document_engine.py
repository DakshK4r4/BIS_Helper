import os
import re
from database import get_db
from document_processor import process_document
from compliance_engine import evaluate_requirement_deterministic, generate_compliance_explanation


def extract_document(path):
    """
    Extract readable text using unified document processor (PDF, DOCX, PNG, JPG, JPEG, OCR).
    """
    res = process_document(path)
    return res.get("text", "").strip()


def extract_metadata_from_text(text):
    """
    Extract common product and standard metadata from document text.
    """
    meta = {}
    if not text:
        return meta

    # Product extraction
    prod_match = re.search(r"(?:Product|Product Name|Equipment|Article|Subject)\s*[:\n\r]+\s*([^\n\r\|]+)", text, re.IGNORECASE)
    if prod_match:
        meta["product"] = prod_match.group(1).strip()

    # Standard extraction
    std_match = re.search(r"(?:Reference Standard|Standard|Applicable Standard|Indian Standard)\s*[:\n\r]+\s*([^\n\r\|]+)", text, re.IGNORECASE)
    if not std_match:
        std_match = re.search(r"\b(IS\s*\d+(?:\s*(?:Part\s*\d+|:\s*\d{4}))*)", text, re.IGNORECASE)
    if std_match:
        meta["standard"] = std_match.group(1).strip()

    # Manufacturer extraction
    mfg_match = re.search(r"(?:Manufacturer|Supplier|Applicant|Company|Producer)\s*[:\n\r]+\s*([^\n\r\|]+)", text, re.IGNORECASE)
    if mfg_match:
        meta["manufacturer"] = mfg_match.group(1).strip()

    # Model extraction
    model_match = re.search(r"(?:Model|Model No|Model Number|Type Designation)\s*[:\n\r]+\s*([^\n\r\|]+)", text, re.IGNORECASE)
    if model_match:
        meta["model"] = model_match.group(1).strip()

    # Document type extraction
    type_match = re.search(r"(?:Document Type|Doc Type|Test Report|Report No)\s*[:\n\r]+\s*([^\n\r\|]+)", text, re.IGNORECASE)
    if type_match:
        meta["doc_type"] = type_match.group(1).strip()

    return meta


def generate_summary(text):
    """
    Generate structured summary of the document.
    """
    if not text or not text.strip():
        return "No text could be extracted from this document."

    metadata = extract_metadata_from_text(text)
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
    snippet = " ".join(content_words[:100])
    if len(content_words) > 100:
        snippet += "..."

    if summary_lines:
        return " | ".join(summary_lines) + "\n\nOverview:\n" + snippet
    return snippet


def get_bis_standard_rules(standard_str):
    """
    Query shared BIS Knowledge Base for clause requirements matching standard.
    """
    if not standard_str:
        return []

    is_num_match = re.search(r"\b\d{3,5}\b", standard_str)
    if not is_num_match:
        return []
    is_num_core = is_num_match.group()

    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM bis_knowledge
        WHERE is_number LIKE ?
        ORDER BY clause ASC
    """, (f"%{is_num_core}%",)).fetchall()
    conn.close()

    return [dict(r) for r in rows]


def analyze_document_content(text, filename=""):
    """
    Document analysis pipeline using shared BIS Knowledge Base:
    1. Extract metadata (product, standard, manufacturer).
    2. Extract requirement clauses, observed evidence, and measured values.
    3. Match against shared BIS knowledge base.
    4. Deterministic evaluation (PASS, FAIL, PARTIAL, UNKNOWN, NOT_FOUND).
    5. Unified backend/frontend contract.
    """
    if not text or not text.strip():
        return {
            "document": filename,
            "product": "Unknown",
            "identified_standard": "Not Identified",
            "overall_status": "NOT_FOUND",
            "compliance_score": 0,
            "summary": "Document contains no readable text. It may be an image or scanned document requiring OCR.",
            "requirements": [],
            "violations": [{
                "id": "ERR-01",
                "title": "Unreadable Document Content",
                "description": "The uploaded file could not be parsed for text.",
                "severity": "HIGH"
            }],
            "recommendations": ["Upload a text-based PDF, DOCX file, or enable OCR processing."],
            "sources": [],
            "status_counts": {"pass": 0, "fail": 0, "partial": 0, "unknown": 0, "not_found": 0},
            "compliance": {
                "score": 0,
                "risk": "HIGH",
                "result": "Unreadable Document",
                "passed": 0,
                "failed": 0,
                "total": 0
            }
        }

    metadata = extract_metadata_from_text(text)
    product_name = metadata.get("product") or filename.rsplit(".", 1)[0].replace("_", " ").title()
    standard_name = metadata.get("standard") or "General BIS Specification"

    # Query shared BIS Knowledge Base for applicable standard rules
    bis_rules = get_bis_standard_rules(standard_name)
    rule_map_by_clause = {r["clause"].strip().lower(): r for r in bis_rules}

    # 1. Structure and Clause Extraction (Two-pass parser)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    req_definitions = {} # req_id -> requirement text
    req_evidence = {}    # req_id -> { evidence, status, observed_value }
    req_order = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for REQ-xx pattern
        req_match = re.match(r"^(REQ-\d+)$", line, re.IGNORECASE)
        if req_match:
            req_id = req_match.group(1).upper()
            if req_id not in req_order:
                req_order.append(req_id)

            # Check if this occurrence is part of an Evidence/Status table:
            # e.g.:
            # REQ-01
            # Product datasheet states outdoor...
            # PASS
            if i + 2 < len(lines) and lines[i + 2].upper() in ["PASS", "FAIL", "PARTIAL", "UNKNOWN", "NOT_FOUND"]:
                ev_text = lines[i + 1]
                stat = lines[i + 2].upper()
                obs_val = ""
                obs_match = re.search(r"(?:measured|observed|finding|tested|value|result)\s*[:\n\r-]+\s*([^\n\r]+)", ev_text, re.IGNORECASE)
                if obs_match:
                    obs_val = obs_match.group(1).strip()
                else:
                    # Check for numeric measurements in evidence text
                    num_match = re.search(r"(\d*\.?\d+\s*(?:mm|m|v|a|ma|k|mpa|bar|mg/l|%|mohm|c|kg))", ev_text, re.IGNORECASE)
                    obs_val = num_match.group(1).strip() if num_match else ev_text

                req_evidence[req_id] = {
                    "evidence": ev_text,
                    "status": stat,
                    "observed_value": obs_val
                }
                i += 3
                continue

            # Check if status immediately follows:
            # REQ-01
            # PASS
            # Evidence text...
            elif i + 1 < len(lines) and lines[i + 1].upper() in ["PASS", "FAIL", "PARTIAL", "UNKNOWN", "NOT_FOUND"]:
                stat = lines[i + 1].upper()
                ev_text = lines[i + 2] if i + 2 < len(lines) and not re.match(r"^REQ-\d+$", lines[i + 2], re.IGNORECASE) else ""
                req_evidence[req_id] = {
                    "evidence": ev_text or f"Checklist evaluation: {stat}",
                    "status": stat,
                    "observed_value": ev_text or stat
                }
                i += 2 if not ev_text else 3
                continue

            # Otherwise, this is a requirement definition
            else:
                desc = lines[i + 1] if i + 1 < len(lines) and not re.match(r"^REQ-\d+$", lines[i + 1], re.IGNORECASE) else ""
                if desc and req_id not in req_definitions:
                    req_definitions[req_id] = desc
                i += 2 if desc else 1
                continue

        i += 1

    raw_reqs = []
    # Build unified requirement list from discovered REQ-xx
    if req_order:
        for r_id in req_order:
            desc = req_definitions.get(r_id) or f"Compliance requirement {r_id}"
            ev_data = req_evidence.get(r_id, {})
            status_hint = ev_data.get("status")
            evidence_val = ev_data.get("evidence", "")
            observed_val = ev_data.get("observed_value", "")

            if not evidence_val:
                evidence_val = "No test evidence provided in submitted document."
                observed_val = "Missing from report"
                status_hint = "NOT_FOUND"

            raw_reqs.append({
                "id": r_id,
                "requirement": desc,
                "evidence": evidence_val,
                "observed_value": observed_val,
                "status_hint": status_hint
            })


    # If document had no structured REQ markers, use shared BIS Knowledge Base requirements!
    if len(raw_reqs) == 0 and bis_rules:
        for idx, rule in enumerate(bis_rules, 1):
            raw_reqs.append({
                "id": f"REQ-{idx:02d}",
                "requirement": f"Clause {rule['clause']}: {rule['requirement_text']}",
                "evidence": f"Standard benchmark check for {rule['parameter'] or 'specification'}",
                "observed_value": "Not provided in uploaded document",
                "clause": rule["clause"],
                "bis_rule": rule
            })

    # Fallback if still empty: extract sentences containing 'shall'
    if len(raw_reqs) == 0:
        shall_matches = re.findall(r"([^.\n]*\bshall\b[^.\n]*\.)", text, re.IGNORECASE)
        for idx, stmt in enumerate(shall_matches[:6], 1):
            raw_reqs.append({
                "id": f"REQ-{idx:02d}",
                "requirement": stmt.strip(),
                "evidence": stmt.strip(),
                "observed_value": "Statement in documentation",
                "clause": f"{idx}.0"
            })

    # 2. Evaluate requirements with deterministic rules
    normalized_requirements = []
    status_counts = {"pass": 0, "fail": 0, "partial": 0, "unknown": 0, "not_found": 0}
    violations = []
    sources = []

    for idx, raw in enumerate(raw_reqs, 1):
        req_id = raw.get("id") or f"REQ-{idx:02d}"
        req_text = raw.get("requirement", "")
        ev_text = raw.get("evidence", "")
        obs_val = raw.get("observed_value", "")
        clause_str = raw.get("clause") or ""

        # Match corresponding BIS rule from shared knowledge base
        matched_rule = raw.get("bis_rule")
        if not matched_rule and clause_str:
            matched_rule = rule_map_by_clause.get(clause_str.lower())
        if not matched_rule:
            # Search by keyword in requirement text
            for rule in bis_rules:
                if (rule.get("parameter") and rule["parameter"].lower() in req_text.lower()) or \
                   (rule.get("clause") and rule["clause"] in req_text):
                    matched_rule = rule
                    clause_str = rule["clause"]
                    break

        if not clause_str and matched_rule:
            clause_str = matched_rule.get("clause", "")
        if not clause_str:
            clause_str = f"{idx}.1"

        # Deterministic status evaluation
        if raw.get("status_hint") in ["PASS", "FAIL", "PARTIAL", "UNKNOWN", "NOT_FOUND"]:
            status = raw["status_hint"]
            eval_reason = f"Explicit test verification: {status}"
        else:
            status, eval_reason = evaluate_requirement_deterministic(req_text, obs_val or ev_text, matched_rule)

        # Missing evidence is NOT PASS
        if not obs_val or "not provided" in obs_val.lower():
            if status == "PASS":
                status = "UNKNOWN"

        status_key = status.lower()
        if status_key in status_counts:
            status_counts[status_key] += 1
        else:
            status_counts["unknown"] += 1

        req_obj = {
            "id": req_id,
            "requirement": req_text,
            "evidence": ev_text,
            "observed_value": obs_val or ev_text,
            "status": status,
            "source_clause": clause_str,
            "source": "BIS",
            "evaluation_reason": eval_reason
        }
        normalized_requirements.append(req_obj)

        if status == "FAIL":
            violations.append({
                "id": req_id,
                "title": f"Non-Compliance at Clause {clause_str}",
                "description": f"{req_text} — Observed: {obs_val or ev_text}. Issue: {eval_reason}",
                "severity": "HIGH",
                "clause": clause_str
            })

    # Deduplicate sources
    source_set = set()
    for rule in bis_rules:
        src_label = f"{rule['is_number']} (Clause {rule['clause']})"
        if src_label not in source_set:
            source_set.add(src_label)
            sources.append({
                "standard": rule["is_number"],
                "clause": rule["clause"],
                "source": "BIS Official Knowledge Base",
                "url": rule.get("source_url") or "https://www.services.bis.gov.in/"
            })

    if not sources:
        sources.append({
            "standard": standard_name,
            "clause": "General Specification",
            "source": "BIS Official Registry",
            "url": "https://www.standardsbis.in/"
        })

    # 3. Calculate Overall Compliance Score
    total_reqs = len(normalized_requirements)
    pass_cnt = status_counts["pass"]
    fail_cnt = status_counts["fail"]
    partial_cnt = status_counts["partial"]

    if total_reqs > 0:
        score = int(round(((pass_cnt + (0.5 * partial_cnt)) / total_reqs) * 100))
    else:
        score = 0

    if fail_cnt == 0 and score >= 85:
        overall_status = "PASS"
        risk = "LOW"
        result_str = "Compliant with Indian Standard"
    elif score >= 60 and fail_cnt <= 2:
        overall_status = "PARTIAL"
        risk = "MEDIUM"
        result_str = "Partially Compliant – Technical Review Required"
    elif fail_cnt > 0 or score < 60:
        overall_status = "FAIL"
        risk = "HIGH"
        result_str = "Non-Compliances Detected"
    else:
        overall_status = "UNKNOWN"
        risk = "MEDIUM"
        result_str = "Evidence Incomplete"

    # 4. Generate Recommendations
    recommendations = []
    for v in violations:
        clause = v.get("clause", "")
        desc = v.get("description", "")
        recommendations.append({
            "priority": "HIGH",
            "action": f"Remediate non-compliance under Clause {clause}: {desc}",
            "type": "CRITICAL"
        })

    if status_counts["not_found"] > 0 or status_counts["unknown"] > 0:
        recommendations.append({
            "priority": "MEDIUM",
            "action": f"Furnish accredited test laboratory certificates for {status_counts['not_found'] + status_counts['unknown']} unverified requirement(s).",
            "type": "WARNING"
        })

    recommendations.append({
        "priority": "MEDIUM",
        "action": f"Verify batch conformance with {standard_name} and ensure factory Quality Assurance Plan (QAP) is updated.",
        "type": "INFO"
    })

    summary = generate_summary(text)

    return {
        "document": filename,
        "product": product_name,
        "identified_standard": standard_name,
        "overall_status": overall_status,
        "compliance_score": score,
        "summary": summary,
        "requirements": normalized_requirements,
        "violations": violations,
        "recommendations": recommendations[:6],
        "sources": sources,
        "status_counts": status_counts,
        "metadata": metadata,
        "compliance": {
            "score": score,
            "risk": risk,
            "result": result_str,
            "passed": pass_cnt,
            "failed": fail_cnt,
            "partial": partial_cnt,
            "unknown": status_counts["unknown"],
            "not_found": status_counts["not_found"],
            "total": total_reqs
        }
    }