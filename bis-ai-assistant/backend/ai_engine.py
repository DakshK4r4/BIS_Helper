import os
import re
import requests
import json
from dotenv import load_dotenv
from database import get_db

load_dotenv()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def search_relevant_standards(query):
    """
    Search official BIS standards in the SQLite database matching the user's query.
    Calculates a deterministic relevance score based on matches in is_number, keywords,
    title, category, industry, and description.
    Returns sorted list of top matching standard records.
    """
    if not query or not query.strip():
        return []

    conn = get_db()
    stop_words = {
        "which", "what", "where", "when", "who", "whom", "how", "standard", "standards",
        "indian", "applies", "apply", "product", "products", "under", "about", "with",
        "this", "that", "from", "have", "does", "explain", "tell", "show", "find", "give",
        "near", "required", "requirements", "please", "help", "the", "for", "and", "are", "can",
        "on", "in", "to", "by", "at", "an", "be", "as", "or", "of", "it", "is", "up", "if", "my",
        "me", "we", "he", "do", "go", "so", "no", "a"
    }

    # Normalize and tokenize query
    cleaned = (
        query.replace(",", " ")
        .replace(":", " ")
        .replace("-", " ")
        .replace("?", " ")
        .replace("/", " ")
        .replace("(", " ")
        .replace(")", " ")
        .lower()
    )
    raw_words = [w.strip() for w in cleaned.split() if len(w.strip()) > 1]
    meaningful_words = [w for w in raw_words if w not in stop_words]
    words = meaningful_words if meaningful_words else raw_words

    if not words:
        conn.close()
        return []

    results = []
    rows = conn.execute("SELECT * FROM standards").fetchall()

    for row in rows:
        is_num = (row["is_number"] or "").lower()
        title = (row["title"] or "").lower()
        keywords = (row["keywords"] or "").lower()
        desc = (row["description"] or "").lower()
        cat = (row["category"] or "").lower()
        ind = (row["industry"] or "").lower()

        score = 0
        for word in words:
            word_pat = r"\b" + re.escape(word) + r"\b"
            stem_pat = r"\b" + re.escape(word[:5]) if len(word) >= 6 else word_pat

            # High priority for exact standard number or code match
            if word in is_num or re.search(word_pat, is_num):
                score += 15
            elif re.search(word_pat, keywords):
                score += 8
            elif re.search(word_pat, title) or re.search(stem_pat, title):
                score += 6
            elif re.search(word_pat, cat) or re.search(word_pat, ind):
                score += 4
            elif re.search(word_pat, desc):
                score += 2

        if score > 0:
            results.append({
                "score": score,
                "data": dict(row)
            })

    conn.close()
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:5]


def build_context(results, document_context=None, document_filename=None):
    """
    Constructs a grounded context string from retrieved BIS standards
    and optional uploaded document content.
    """
    context_parts = []

    if results:
        context_parts.append("OFFICIAL INDIAN STANDARDS RETRIEVED FROM BIS REGISTRY:")
        for idx, item in enumerate(results[:4], 1):
            std = item["data"]
            context_parts.append(
                f"{idx}. IS Number: {std.get('is_number')}\n"
                f"   Title: {std.get('title')}\n"
                f"   Category: {std.get('category')} | Industry: {std.get('industry')}\n"
                f"   Year: {std.get('year')} | Status: {std.get('status')} | Certification Scheme: {std.get('certification')}\n"
                f"   Description & Scope: {std.get('description')}\n"
            )
    else:
        context_parts.append(
            "OFFICIAL INDIAN STANDARDS RETRIEVED FROM BIS REGISTRY:\n"
            "No matching Indian Standard was found in the local BIS registry for this specific query."
        )

    if document_context:
        filename = document_filename or "Attached Document"
        preview = str(document_context)[:2500].strip()
        context_parts.append(f"\nATTACHED DOCUMENT CONTENT ({filename}):\n{preview}")

    return "\n\n".join(context_parts)


def call_openrouter(query, context, model=None):
    """
    Calls OpenRouter Chat Completions API with the grounded prompt.
    Uses OPENROUTER_API_KEY from environment. Falls back across configured models.
    Returns: (answer_content, model_name) on success, or (None, error_code) on failure.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("[AI Engine] OPENROUTER_API_KEY is not set in environment. Falling back to database guidance.")
        return None, "API_KEY_MISSING"

    primary_model = model or os.getenv("OPENROUTER_MODEL", "nex-agi/nex-n2.5-mini:free").strip()
    fallback_models = ["nex-agi/nex-n2.5-pro:free", "liquid/lfm-2.5-2.6b:free", "google/gemma-2-9b-it:free"]
    models_to_try = [primary_model] + [m for m in fallback_models if m != primary_model]

    system_prompt = (
        "You are BIS Sahayak, the official AI compliance and standards assistant for the Bureau of Indian Standards (BIS), "
        "Ministry of Consumer Affairs, Food & Public Distribution, Government of India.\n"
        "Your role is to assist citizens, manufacturers, exporters, and testing laboratories with Indian Standards (IS), "
        "BIS certification schemes (ISI Mark Scheme I, Compulsory Registration Scheme CRS, Hallmarking Scheme, Management Systems), "
        "and conformity assessment.\n\n"
        "STRICT GROUNDING RULES:\n"
        "1. Base your answer strictly on the provided BIS Standards Registry and Document Context below.\n"
        "2. When an applicable Indian Standard exists in context, quote the exact IS number (e.g., IS 10322 : 2012, IS 302 (Part 1) : 2024) "
        "and explain its scope, mandatory testing parameters, and certification requirements.\n"
        "3. NEVER fabricate, hallucinate, or assume non-existent IS numbers or certification mandates.\n"
        "4. If NO matching standard was found in the provided BIS registry context, state clearly and transparently: "
        "'Verified BIS knowledge is not available in the current knowledge base for this query. "
        "Please consult the official BIS portal (bis.gov.in) or search the Standards Explorer with specific product keywords.' "
        "Do NOT invent an IS number.\n"
        "5. If an attached document is provided, evaluate the document's content and findings against the relevant BIS standard clauses.\n"
        "6. Provide a well-structured, authoritative, professional response with markdown formatting, bullet points, and actionable next steps."
    )

    user_prompt = f"User Query: {query}\n\nContext:\n{context}\n\nPlease provide a clear, accurate, and structured answer based on the BIS context provided above."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "BIS Sahayak AI Assistant"
    }

    for target_model in models_to_try:
        payload = {
            "model": target_model,
            "messages": messages,
            "max_tokens": 750,
            "temperature": 0.2
        }

        try:
            response = requests.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload,
                timeout=15
            )

            if response.status_code == 200:
                resp_json = response.json()
                choices = resp_json.get("choices", [])
                if choices:
                    message_obj = choices[0].get("message", {})
                    content = message_obj.get("content", "").strip()
                    if content and not content.startswith("<|tool_call"):
                        return content, target_model
                print(f"[AI Engine] Model {target_model} returned empty content. Trying fallback.")
                continue

            elif response.status_code in (401, 403):
                # Authentication error - do not log the secret key
                print(f"[AI Engine] OpenRouter authentication failed with HTTP {response.status_code}.")
                return None, f"HTTP_{response.status_code}"

            elif response.status_code == 429:
                print(f"[AI Engine] Model {target_model} rate limited (HTTP 429). Trying next fallback model.")
                continue

            elif response.status_code in (500, 502, 503, 504):
                print(f"[AI Engine] Model {target_model} upstream error (HTTP {response.status_code}). Trying next fallback model.")
                continue

            else:
                print(f"[AI Engine] OpenRouter returned status {response.status_code} for model {target_model}.")
                continue

        except requests.exceptions.Timeout:
            print(f"[AI Engine] Request timed out contacting OpenRouter on model {target_model}.")
            continue
        except requests.exceptions.RequestException as req_err:
            print(f"[AI Engine] Network request failed for model {target_model}: {req_err}")
            continue
        except Exception as err:
            print(f"[AI Engine] Unexpected error on model {target_model}: {err}")
            continue

    return None, "ALL_MODELS_UNAVAILABLE"


# Backward compatibility alias
call_openrouter_llm = call_openrouter


def process_ai_query(query, document_context=None, document_filename=None):
    """
    End-to-end grounded RAG pipeline:
    1. search_relevant_standards(query)
    2. Deterministic confidence calculation based on SQLite retrieval
    3. build_context(results, document_context, document_filename)
    4. call_openrouter(query, context)
    5. Graceful deterministic fallback if OpenRouter is unreachable or API key missing
    6. Structured dictionary with query, answer, recommended_standard, confidence_score,
       related_standards, source, ai_model, and ai_status.
    """
    results = search_relevant_standards(query)
    best = results[0]["data"] if results else None

    # Deterministic retrieval confidence
    if results:
        top_score = results[0]["score"]
        confidence = min(98, max(65, 55 + (top_score * 6)))
    else:
        confidence = 0

    context = build_context(results, document_context, document_filename)
    llm_answer, model_used = call_openrouter(query, context)

    if llm_answer:
        ai_status = "success"
        source = "BIS Knowledge Base + OpenRouter"
        final_answer = llm_answer
    else:
        ai_status = "fallback"
        source = "BIS Knowledge Base"
        model_used = "Deterministic Fallback"

        if best:
            final_answer = (
                f"Based on the official BIS Standards Registry, **{best['is_number']}** ({best['title']}) "
                f"is the applicable Indian Standard for your query.\n\n"
                f"### Standard Overview\n"
                f"- **IS Number:** {best['is_number']}\n"
                f"- **Category:** {best['category']} ({best['industry']})\n"
                f"- **Current Status:** {best['status']}\n"
                f"- **Certification Scheme:** {best['certification']}\n"
                f"- **Year of Publication:** {best['year']}\n\n"
                f"### Scope & Key Requirements\n"
                f"{best['description']}\n\n"
                f"### Mandatory Compliance Steps\n"
                f"1. Obtain the official specification document for {best['is_number']} from the BIS standards portal.\n"
                f"2. Conduct product type testing at a BIS-recognized laboratory to verify safety, performance, and construction requirements.\n"
                f"3. Submit your application for {best['certification']} through the Manakonline portal with required factory test records."
            )
        else:
            final_answer = (
                "Verified BIS knowledge is not available in the current knowledge base for this query. "
                "Please consult the official BIS portal (bis.gov.in) or search the Standards Explorer with specific product keywords "
                "(e.g., LED Luminaires, Packaged Drinking Water, Cement, Batteries, Household Electrical Appliances)."
            )

    rec_std = {
        "id": best.get("id"),
        "is_number": best.get("is_number"),
        "title": best.get("title"),
        "description": best.get("description"),
        "category": best.get("category"),
        "industry": best.get("industry"),
        "year": best.get("year"),
        "status": best.get("status"),
        "certification": best.get("certification"),
        "pdf_url": best.get("pdf_url")
    } if best else None

    related = [
        item["data"]["is_number"]
        for item in results[1:5]
        if "is_number" in item["data"]
    ]

    return {
        "query": query,
        "answer": final_answer,
        "recommended_standard": rec_std,
        "confidence_score": f"{confidence}%",
        "retrieval_confidence": confidence,
        "related_standards": related,
        "source": source,
        "ai_model": model_used,
        "model": model_used,
        "model_used": model_used,
        "ai_status": ai_status
    }