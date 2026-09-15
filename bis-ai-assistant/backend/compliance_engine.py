def analyze_compliance(product, standard, documents=None):

    documents = documents or []

    checks = []

    # Product check
    if product:
        checks.append({
            "name": "Product information",
            "status": "PASS",
            "message": "Product information provided."
        })
    else:
        checks.append({
            "name": "Product information",
            "status": "FAIL",
            "message": "Product information is missing."
        })

    # Standard check
    if standard:
        checks.append({
            "name": "Applicable standard",
            "status": "PASS",
            "message": f"Standard {standard} selected."
        })
    else:
        checks.append({
            "name": "Applicable standard",
            "status": "WARNING",
            "message": "Applicable standard has not been selected."
        })

    # Documents
    if documents:

        checks.append({
            "name": "Supporting documents",
            "status": "PASS",
            "message": f"{len(documents)} document(s) submitted."
        })

    else:

        checks.append({
            "name": "Supporting documents",
            "status": "WARNING",
            "message": "No supporting documents submitted."
        })

    passed = len([
        x for x in checks
        if x["status"] == "PASS"
    ])

    score = int(
        (passed / len(checks)) * 100
    )

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
            "Verify the latest applicable BIS standard.",
            "Ensure all required test reports are available.",
            "Check certification requirements before commercial deployment."
        ]
    }