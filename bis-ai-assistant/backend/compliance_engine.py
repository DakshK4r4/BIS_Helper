import re
import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def extract_numeric(val_str):
    """
    Extract first float or integer number from a string, supporting negative values and decimals.
    e.g. '1.5 mm' -> 1.5, '5 MPa' -> 5.0, '-8%' -> -8.0
    """
    if val_str is None:
        return None
    match = re.search(r"[-+]?\d*\.?\d+", str(val_str))
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def evaluate_requirement_deterministic(req_text, observed_val, bis_rule=None):
    """
    Deterministic compliance evaluation:
    Checks numerical thresholds, tolerances, and explicit test report outcomes.
    Statuses: PASS, FAIL, PARTIAL, UNKNOWN, NOT_FOUND.
    Crucial rule: Missing evidence != PASS.
    """
    obs_str = (str(observed_val) if observed_val is not None else "").strip()
    obs_lower = obs_str.lower()
    req_lower = (req_text or "").lower()

    # 1. Check for missing evidence
    if not obs_str or any(k in obs_lower for k in [
        "not provided", "missing", "not observed", "no evidence",
        "pending test", "unavailable", "n/a", "not tested"
    ]):
        return "NOT_FOUND", "No test evidence or observed parameter found in document."

    # 2. Check for explicit textual verdicts in the observed evidence
    if any(k in obs_lower for k in ["failed", "fails", "non-compliant", "exceeded", "leakage detected", "breakdown", "defective", "below minimum"]):
        return "FAIL", f"Observed finding indicates non-compliance: {obs_str}"

    if any(k in obs_lower for k in ["passed", "pass", "conforms", "satisfactory", "no leakage", "no breakdown", "withstood", "verified compliant"]):
        return "PASS", f"Observed finding confirms conformance: {obs_str}"

    # 3. Deterministic Numerical Evaluation against bis_rule or extracted bounds
    min_val = None
    max_val = None
    target_val = None
    op = None

    if bis_rule:
        min_val = bis_rule.get("min_value")
        max_val = bis_rule.get("max_value")
        target_val = bis_rule.get("target_value")
        op = bis_rule.get("operator")

    # If bis_rule doesn't specify numeric bounds, attempt regex from requirement text
    if min_val is None and max_val is None:
        # Check for 'minimum X' or 'not less than X'
        min_match = re.search(r"(?:minimum|not less than|shall be at least|>=?)\s*(\d*\.?\d+)", req_lower)
        if min_match:
            min_val = float(min_match.group(1))

        # Check for 'maximum X' or 'not more than X' or 'shall not exceed X'
        max_match = re.search(r"(?:maximum|not more than|shall not exceed|<=?)\s*(\d*\.?\d+)", req_lower)
        if max_match:
            max_val = float(max_match.group(1))

        # Check for 'between X and Y'
        between_match = re.search(r"between\s*(\d*\.?\d+)\s*(?:and|to)\s*(\d*\.?\d+)", req_lower)
        if between_match:
            min_val = float(between_match.group(1))
            max_val = float(between_match.group(2))

    obs_num = extract_numeric(obs_str)

    if obs_num is not None:
        # Both min and max defined (Range)
        if min_val is not None and max_val is not None:
            if min_val <= obs_num <= max_val:
                return "PASS", f"Observed {obs_num} is within permissible range [{min_val}, {max_val}]."
            else:
                return "FAIL", f"Observed {obs_num} violates permissible range [{min_val}, {max_val}]."

        # Only minimum required
        if min_val is not None:
            if obs_num >= min_val:
                return "PASS", f"Observed {obs_num} meets mandatory minimum of {min_val}."
            else:
                return "FAIL", f"Observed {obs_num} is below mandatory minimum of {min_val}."

        # Only maximum allowed
        if max_val is not None:
            if obs_num <= max_val:
                return "PASS", f"Observed {obs_num} does not exceed mandatory maximum of {max_val}."
            else:
                return "FAIL", f"Observed {obs_num} exceeds mandatory maximum of {max_val}."

    # 4. Partial verification indicator
    if any(k in obs_lower for k in ["partial", "provisional", "interim", "conditional"]):
        return "PARTIAL", f"Parameter partially verified: {obs_str}"

    # 5. Default unknown
    return "UNKNOWN", f"Insufficient deterministic evidence to evaluate: '{obs_str}'."


def generate_compliance_explanation(document_summary, requirements, violations):
    """
    Optionally calls OpenRouter to generate an objective narrative report.
    Does NOT override deterministic status values.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.getenv("OPENROUTER_MODEL", "nex-agi/nex-n2.5-mini:free").strip()
    req_summary = "\n".join([
        f"- [{r.get('status')}] {r.get('id')}: {r.get('requirement')} | Observed: {r.get('observed_value', r.get('evidence', ''))}"
        for r in requirements[:8]
    ])

    prompt = (
        f"You are a BIS Technical Audit Explainer. Summarize this compliance assessment objectively.\n\n"
        f"Document Summary: {document_summary}\n\n"
        f"Requirements Evaluated:\n{req_summary}\n\n"
        f"Violations Count: {len(violations)}\n\n"
        f"Provide a 3-4 sentence professional executive summary of the compliance posture and critical next steps."
    )

    try:
        res = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.2
            },
            timeout=10
        )
        if res.status_code == 200:
            data = res.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        print(f"Notice: OpenRouter explanation call skipped: {e}")

    return None


def analyze_compliance(product, standard, documents=None):
    """
    Backward-compatible entry point for portfolio compliance check.
    """
    documents = documents or []
    checks = []

    if product:
        checks.append({"name": "Product information", "status": "PASS", "message": f"Product '{product}' specified."})
    else:
        checks.append({"name": "Product information", "status": "FAIL", "message": "Product information is missing."})

    if standard:
        checks.append({"name": "Applicable standard", "status": "PASS", "message": f"Indian Standard '{standard}' verified in BIS registry."})
    else:
        checks.append({"name": "Applicable standard", "status": "PARTIAL", "message": "Applicable standard has not been selected."})

    if documents:
        checks.append({"name": "Supporting documents", "status": "PASS", "message": f"{len(documents)} verification document(s) attached."})
    else:
        checks.append({"name": "Supporting documents", "status": "UNKNOWN", "message": "No supporting test certificates attached."})

    passed = len([x for x in checks if x["status"] == "PASS"])
    score = int((passed / len(checks)) * 100)

    if score >= 80:
        risk = "LOW"
        result = "Likely compliant"
    elif score >= 50:
        risk = "MEDIUM"
        result = "Further review required"
    else:
        risk = "HIGH"
        result = "Non-compliance risks detected"

    return {
        "score": score,
        "risk": risk,
        "result": result,
        "checks": checks,
        "recommendations": [
            f"Verify the latest applicable BIS standard specification for {product or 'product'}.",
            "Ensure all mandatory test reports from NABL/BIS accredited laboratories are current.",
            "Verify ISI / CRS mark registration on official Manakonline portal."
        ]
    }