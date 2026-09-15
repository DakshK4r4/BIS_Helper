from database import get_db


def search_relevant_standards(query):

    conn = get_db()

    words = [
        word.lower()
        for word in query.replace(",", " ").split()
        if len(word) > 2
    ]

    results = []

    rows = conn.execute("""
        SELECT *
        FROM standards
    """).fetchall()

    for row in rows:

        searchable = " ".join([
            row["is_number"] or "",
            row["title"] or "",
            row["description"] or "",
            row["category"] or "",
            row["industry"] or "",
            row["keywords"] or ""
        ]).lower()

        score = 0

        for word in words:
            if word in searchable:
                score += 1

        if score > 0:
            results.append({
                "score": score,
                "data": dict(row)
            })

    conn.close()

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results


def process_ai_query(query):

    results = search_relevant_standards(query)

    if results:

        best = results[0]["data"]

        confidence = min(
            95,
            60 + results[0]["score"] * 8
        )

        answer = (
            f"Based on the product/query description, "
            f"{best['is_number']} appears to be the most relevant "
            f"Indian Standard. {best['description']}"
        )

        return {
            "query": query,
            "answer": answer,
            "recommended_standard": {
                "is_number": best["is_number"],
                "title": best["title"],
                "description": best["description"],
                "category": best["category"],
                "industry": best["industry"],
                "year": best["year"],
                "status": best["status"],
                "certification": best["certification"]
            },
            "confidence_score": f"{confidence}%",
            "related_standards": [
                item["data"]["is_number"]
                for item in results[1:4]
            ],
            "source": "BIS Knowledge Base"
        }

    return {
        "query": query,
        "answer": (
            "I could not find a sufficiently relevant standard "
            "in the current BIS knowledge base. Try providing "
            "the product name, application, or technical category."
        ),
        "recommended_standard": None,
        "confidence_score": "0%",
        "related_standards": [],
        "source": "BIS Knowledge Base"
    }