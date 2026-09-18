import os
import requests
import json
from dotenv import load_dotenv
from database import get_db

load_dotenv()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def search_relevant_standards(query):
    conn = get_db()
    stop_words = {
        "which", "what", "where", "when", "who", "whom", "how", "standard", "standards",
        "indian", "applies", "apply", "product", "products", "under", "about", "with",
        "this", "that", "from", "have", "does", "explain", "tell", "show", "find", "give",
        "near", "required", "requirements", "please", "help"
    }

    raw_words = [
        word.lower()
        for word in query.replace(",", " ").replace(":", " ").replace("-", " ").replace("?", " ").split()
        if len(word) > 1
    ]
    meaningful_words = [w for w in raw_words if w not in stop_words]
    words = meaningful_words if meaningful_words else raw_words

    results = []
    rows = conn.execute("""
        SELECT *
        FROM standards
    """).fetchall()

    for row in rows:
        is_num = (row["is_number"] or "").lower()
        title = (row["title"] or "").lower()
        keywords = (row["keywords"] or "").lower()
        desc = (row["description"] or "").lower()
        cat = (row["category"] or "").lower()
        ind = (row["industry"] or "").lower()

        score = 0
        for word in words:
            if word in is_num:
                score += 10
            if word in keywords:
                score += 6
            if word in title:
                score += 4
            if word in cat or word in ind:
                score += 3
            if word in desc:
                score += 1

        if score > 0:
            results.append({
                "score": score,
                "data": dict(row)
            })

    conn.close()
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def call_openrouter_llm(messages, max_tokens=600):
    """
    Call OpenRouter API using the secure key from .env.
    Uses nex-agi/nex-n2.5-mini:free or models configured via OPENROUTER_MODEL.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return None, "API_KEY_MISSING"

    model = os.getenv("OPENROUTER_MODEL", "nex-agi/nex-n2.5-mini:free").strip()
    models_to_try = [model, "nex-agi/nex-n2.5-pro:free", "google/gemma-4-26b-a4b-it:free", "liquid/lfm-2.5-2.6b:free"]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "BIS Sahayak AI Assistant"
    }

    for m in models_to_try:
        data = {
            "model": m,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3
        }

        try:
            response = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=12)
            if response.status_code == 200:
                resp_json = response.json()
                choices = resp_json.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "").strip()
                    # If content is a tool call artifact or blank, try next
                    if content and not content.startswith("<|tool_call"):
                        return content, m
            elif response.status_code == 429:
                continue
        except Exception as err:
            print(f"OpenRouter attempt failed on {m}: {err}")
            continue

    return None, "ALL_MODELS_UNAVAILABLE"


def process_ai_query(query, document_context=None, document_filename=None):
    """
    Grounded RAG pipeline:
    1. Search official BIS standards matching the user's query.
    2. Ground the prompt with verified standards and optional attached document text.
    3. Query OpenRouter LLM for an authoritative, clear response.
    4. Fall back cleanly if OpenRouter is unreachable.
    """
    results = search_relevant_standards(query)
    best = results[0]["data"] if results else None
    confidence = min(98, 60 + (results[0]["score"] * 8)) if results else 0

    # Build grounded system & user prompt
    context_standards = ""
    if results:
        context_standards = "OFFICIAL BIS STANDARDS RETRIEVED FROM REGISTRY:\n"
        for idx, r in enumerate(results[:3]):
            s = r["data"]
            context_standards += f"{idx+1}. IS Number: {s['is_number']}\n   Title: {s['title']}\n   Category: {s['category']} | Industry: {s['industry']} | Status: {s['status']} | Certification: {s['certification']}\n   Description: {s['description']}\n\n"
    else:
        context_standards = "OFFICIAL BIS STANDARDS RETRIEVED: No matching standard found in BIS database for this query.\n"

    doc_section = ""
    if document_context:
        fname = document_filename or "Attached Document"
        preview = document_context[:1500]
        doc_section = f"\nATTACHED DOCUMENT CONTENT ({fname}):\n{preview}\n"

    system_prompt = (
        "You are BIS Sahayak, the official AI compliance and standards assistant for the Bureau of Indian Standards (BIS), Ministry of Consumer Affairs, Government of India.\n"
        "Your role is to help citizens, manufacturers, and testing laboratories understand Indian Standards and compliance procedures.\n"
        "RULES:\n"
        "1. Base your answer strictly on official Indian Standards (IS). Cite standard numbers (e.g. IS 10322 : 2012, IS 302 (Part 1) : 2024).\n"
        "2. If an Indian Standard was found in the provided BIS registry context, recommend it and explain its requirements clearly.\n"
        "3. If NO matching standard exists in the provided context, state clearly that no matching standard was found in the current BIS knowledge base rather than making up numbers.\n"
        "4. If a document is attached, analyze the document content in the context of BIS standards.\n"
        "5. Keep the answer structured, professional, concise, and easy to understand."
    )

    user_prompt = f"User Question: {query}\n\n{context_standards}{doc_section}\nPlease provide a clear, helpful answer based on BIS guidelines."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    llm_answer, model_used = call_openrouter_llm(messages)

    if not llm_answer:
        # Graceful grounded fallback
        if best:
            llm_answer = (
                f"Based on the official BIS Standards Registry, **{best['is_number']}** ({best['title']}) "
                f"is the applicable standard for your query.\n\n"
                f"**Key Details:**\n"
                f"- **Category:** {best['category']} ({best['industry']})\n"
                f"- **Status:** {best['status']}\n"
                f"- **Certification Type:** {best['certification']}\n"
                f"- **Overview:** {best['description']}\n\n"
                f"To obtain certification or verify conformity, ensure that product testing reports from a BIS-recognized "
                f"laboratory satisfy the mandatory safety and performance clauses of {best['is_number']}."
            )
        else:
            llm_answer = (
                "No matching Indian Standard was found in the current BIS knowledge base for your query. "
                "Please try searching by specific product name (e.g., LED Luminaires, Packaged Drinking Water, Cement, Batteries) "
                "or exploring the Standards Explorer."
            )

    return {
        "query": query,
        "answer": llm_answer,
        "recommended_standard": {
            "is_number": best["is_number"],
            "title": best["title"],
            "description": best["description"],
            "category": best["category"],
            "industry": best["industry"],
            "year": best["year"],
            "status": best["status"],
            "certification": best["certification"]
        } if best else None,
        "confidence_score": f"{confidence}%",
        "related_standards": [
            item["data"]["is_number"]
            for item in results[1:4]
        ],
        "source": "BIS Standards Registry + OpenRouter AI" if model_used != "ALL_MODELS_UNAVAILABLE" else "BIS Knowledge Base",
        "model": model_used
    }