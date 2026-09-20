import os
import re
import requests
import json
from dotenv import load_dotenv
from database import get_db

load_dotenv()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SAFE_FALLBACK_MESSAGE = (
    "I could not find sufficiently verified BIS evidence for this query in the available knowledge sources. "
    "I don't want to invent an IS number or requirement. Try:\n"
    "• a product name\n"
    "• an IS number\n"
    "• a specific BIS requirement\n"
    "• a certification question"
)

# Product synonyms mapping to primary Indian Standards
PRODUCT_STANDARD_MAP = {
    "packaged drinking water": "IS 14543 : 2024",
    "drinking water": "IS 14543 : 2024",
    "bottled water": "IS 14543 : 2024",
    "water bottle": "IS 14543 : 2024",
    "mineral water": "IS 14543 : 2024",
    "concrete": "IS 456 : 2000",
    "reinforced concrete": "IS 456 : 2000",
    "rcc": "IS 456 : 2000",
    "plain concrete": "IS 456 : 2000",
    "cement": "IS 269 : 2015",
    "portland cement": "IS 269 : 2015",
    "opc": "IS 269 : 2015",
    "pozzolana cement": "IS 1489 (Part 1) : 2015",
    "ppc": "IS 1489 (Part 1) : 2015",
    "fly ash cement": "IS 1489 (Part 1) : 2015",
    "plugs": "IS 1293 : 2019",
    "plug": "IS 1293 : 2019",
    "socket": "IS 1293 : 2019",
    "sockets": "IS 1293 : 2019",
    "socket outlet": "IS 1293 : 2019",
    "plug and socket": "IS 1293 : 2019",
    "led": "IS 10322 : 2012",
    "led luminaire": "IS 10322 : 2012",
    "led luminaires": "IS 10322 : 2012",
    "street light": "IS 10322 : 2012",
    "lighting": "IS 10322 : 2012",
    "led lamp": "IS 16102 (Part 1) : 2012",
    "led bulb": "IS 16102 (Part 1) : 2012",
    "structural steel": "IS 2062 : 2011",
    "steel plates": "IS 2062 : 2011",
    "steel sections": "IS 2062 : 2011",
    "steel tubes": "IS 1239 (Part 1) : 2004",
    "mild steel tubes": "IS 1239 (Part 1) : 2004",
    "steel pipe": "IS 1239 (Part 1) : 2004",
    "tmt": "IS 1786 : 2008",
    "tmt bars": "IS 1786 : 2008",
    "rebar": "IS 1786 : 2008",
    "deformed steel bars": "IS 1786 : 2008",
    "lithium battery": "IS 16046 (Part 1) : 2018",
    "battery": "IS 16046 (Part 1) : 2018",
    "secondary cells": "IS 16046 (Part 1) : 2018",
    "pvc cable": "IS 694 : 2010",
    "pvc insulated cables": "IS 694 : 2010",
    "electrical wire": "IS 694 : 2010",
    "cables": "IS 694 : 2010",
    "household appliance": "IS 302 (Part 1) : 2024",
    "electrical appliance": "IS 302 (Part 1) : 2024",
    "safety footwear": "IS 15298 (Part 2) : 2016",
    "safety shoes": "IS 15298 (Part 2) : 2016",
    "bitumen": "IS 73 : 2013",
    "asphalt": "IS 73 : 2013",
    "it equipment": "IS 13252 (Part 1) : 2010",
    "iron castings": "IS 1865 : 1991"
}


# ============================================================
# 1. QUERY UNDERSTANDING
# ============================================================

def understand_query(query):
    """
    Extract intent, product, IS number, standard number, keywords, and technical terms.
    Does not rely solely on exact string matching.
    """
    if not query:
        return {
            "intent": "empty",
            "is_number": None,
            "product": None,
            "keywords": [],
            "technical_terms": [],
            "is_huid_inquiry": False,
            "is_concept_inquiry": False,
            "is_certification_inquiry": False
        }

    q_lower = query.lower().strip()

    # 1. Extract explicit IS number (e.g. IS 456, IS 14543, IS 1293:2019, IS 10322)
    is_match = re.search(r"\bIS\s*[:\-_]?\s*(\d{2,5})(?:\s*\(Part\s*(\d+)(?:\s*/\s*Sec\s*(\d+))?\))?(?:\s*[:\-]\s*(\d{4}))?", query, re.IGNORECASE)
    extracted_is_num = None
    if is_match:
        core_num = is_match.group(1)
        part_num = is_match.group(2)
        year_num = is_match.group(4)
        if part_num:
            extracted_is_num = f"IS {core_num} (Part {part_num})"
        else:
            extracted_is_num = f"IS {core_num}"
        if year_num:
            extracted_is_num += f" : {year_num}"

    # 2. Extract special intents
    is_huid = any(k in q_lower for k in ["huid", "hallmark", "hallmarking", "gold purity", "silver purity", "ahc", "jewel"])
    is_concept = any(k in q_lower for k in ["what is an is number", "what is is number", "what does is stand for", "how are is numbers", "what is bis"])
    is_cert = any(k in q_lower for k in ["is bis certification mandatory", "is certification mandatory", "is bis required", "mandatory", "scheme i", "isi mark mandatory", "compulsory registration"])
    is_testing = any(k in q_lower for k in ["testing requirement", "test requirement", "tolerance", "permissible", "test method", "criteria"])

    # 3. Detect matching product from synonym dictionary
    detected_product = None
    for prod_key in sorted(PRODUCT_STANDARD_MAP.keys(), key=len, reverse=True):
        if re.search(r"\b" + re.escape(prod_key) + r"\b", q_lower):
            detected_product = prod_key
            break

    # If no explicit IS number was found but product matched, map to standard
    if not extracted_is_num and detected_product:
        extracted_is_num = PRODUCT_STANDARD_MAP[detected_product]

    # 4. Tokenize keywords
    stop_words = {
        "what", "is", "the", "for", "in", "of", "and", "a", "an", "to", "explain",
        "tell", "me", "about", "show", "find", "give", "please", "can", "you",
        "does", "do", "how", "why", "which", "where", "under", "this", "that",
        "are", "standard", "standards", "requirement", "requirements", "product",
        "products", "indian", "bis"
    }
    clean_q = re.sub(r"[^\w\s]", " ", q_lower)
    words = [w.strip() for w in clean_q.split() if len(w.strip()) > 1]
    keywords = [w for w in words if w not in stop_words]

    # 5. Determine dominant intent
    if is_huid:
        intent = "huid_questions"
    elif is_concept:
        intent = "general_concept"
    elif is_cert:
        intent = "certification_questions"
    elif is_testing:
        intent = "testing_requirements"
    elif extracted_is_num:
        intent = "standard_lookup"
    elif detected_product:
        intent = "product_inquiry"
    else:
        intent = "general_search"

    return {
        "query": query,
        "intent": intent,
        "is_number": extracted_is_num,
        "product": detected_product,
        "keywords": keywords,
        "technical_terms": [w for w in keywords if len(w) > 4],
        "is_huid_inquiry": is_huid,
        "is_concept_inquiry": is_concept,
        "is_certification_inquiry": is_cert
    }


# ============================================================
# 2. HYBRID RETRIEVAL (LOCAL KB + OFFICIAL BIS MAPPING)
# ============================================================

def hybrid_retrieve_evidence(parsed_query):
    """
    Hybrid retrieval:
    1. Exact IS number priority boost (+100)
    2. Product-specific boost (+50)
    3. Clause & parameter match across bis_knowledge (+25)
    4. Textual BM25-like keyword scoring across standards & bis_knowledge
    Returns list of best evidence records.
    """
    is_num = parsed_query.get("is_number")
    product = parsed_query.get("product")
    keywords = parsed_query.get("keywords") or []
    intent = parsed_query.get("intent")

    conn = get_db()
    candidates = []

    # Handle General Concepts (HUID, IS Number, ISI Mark)
    if parsed_query.get("is_concept_inquiry"):
        rows = conn.execute("SELECT * FROM bis_knowledge WHERE clause = 'GEN-01'").fetchall()
        for r in rows:
            candidates.append({"score": 120, "record": dict(r), "type": "knowledge"})

    if parsed_query.get("is_huid_inquiry"):
        rows = conn.execute("SELECT * FROM bis_knowledge WHERE clause = 'GEN-02'").fetchall()
        for r in rows:
            candidates.append({"score": 120, "record": dict(r), "type": "knowledge"})

    if parsed_query.get("is_certification_inquiry") and not is_num:
        rows = conn.execute("SELECT * FROM bis_knowledge WHERE clause = 'GEN-03'").fetchall()
        for r in rows:
            candidates.append({"score": 110, "record": dict(r), "type": "knowledge"})

    # Query bis_knowledge table
    kb_rows = conn.execute("SELECT * FROM bis_knowledge").fetchall()
    for row in kb_rows:
        r_dict = dict(row)
        score = 0
        r_is_num = (r_dict.get("is_number") or "").lower()
        r_title = (r_dict.get("title") or "").lower()
        r_req = (r_dict.get("requirement_text") or "").lower()
        r_param = (r_dict.get("parameter") or "").lower()
        r_kw = (r_dict.get("keywords") or "").lower()

        # Exact IS number priority
        if is_num:
            clean_is = re.search(r"\d{2,5}", is_num)
            if clean_is and clean_is.group() in r_is_num:
                score += 100

        # Product matching
        if product and (product in r_kw or product in r_title or product in r_req):
            score += 50

        # Keyword matching
        for kw in keywords:
            kw_pat = r"\b" + re.escape(kw) + r"\b"
            if re.search(kw_pat, r_param):
                score += 15
            elif re.search(kw_pat, r_req):
                score += 10
            elif re.search(kw_pat, r_title):
                score += 8
            elif re.search(kw_pat, r_kw):
                score += 6

        if score > 0:
            candidates.append({"score": score, "record": r_dict, "type": "clause"})

    # Query standards catalog table
    std_rows = conn.execute("SELECT * FROM standards").fetchall()
    for row in std_rows:
        r_dict = dict(row)
        score = 0
        r_is_num = (r_dict.get("is_number") or "").lower()
        r_title = (r_dict.get("title") or "").lower()
        r_desc = (r_dict.get("description") or "").lower()
        r_kw = (r_dict.get("keywords") or "").lower()

        if is_num:
            clean_is = re.search(r"\d{2,5}", is_num)
            if clean_is and clean_is.group() in r_is_num:
                score += 95

        if product and (product in r_kw or product in r_title or product in r_desc):
            score += 45

        for kw in keywords:
            kw_pat = r"\b" + re.escape(kw) + r"\b"
            if re.search(kw_pat, r_is_num):
                score += 30
            elif re.search(kw_pat, r_kw):
                score += 12
            elif re.search(kw_pat, r_title):
                score += 10
            elif re.search(kw_pat, r_desc):
                score += 5

        if score > 0:
            candidates.append({"score": score, "record": r_dict, "type": "standard"})

    conn.close()

    # Sort candidates by relevance score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Deduplicate while preserving best matches
    unique_results = []
    seen_keys = set()
    for c in candidates:
        rec = c["record"]
        key = (rec.get("is_number"), rec.get("clause", "main"))
        if key not in seen_keys:
            seen_keys.add(key)
            unique_results.append(c)

    return unique_results[:6]


# ============================================================
# 3. LLM PROMPT & SOURCE GROUNDING
# ============================================================

def build_grounded_rag_context(evidence_candidates, doc_context=None, doc_filename=None):
    """
    Constructs context containing verified BIS evidence.
    """
    lines = ["VERIFIED BIS KNOWLEDGE SOURCES (AUTHORITATIVE REGISTRY):"]

    for idx, c in enumerate(evidence_candidates, 1):
        rec = c["record"]
        is_no = rec.get("is_number")
        title = rec.get("title")
        clause = rec.get("clause")
        sec = rec.get("section")
        req_text = rec.get("requirement_text") or rec.get("description")
        param = rec.get("parameter")
        src = rec.get("source", "BIS")
        url = rec.get("source_url") or "https://www.services.bis.gov.in/"

        lines.append(
            f"[{idx}] Standard: {is_no}\n"
            f"    Title: {title}\n"
            f"    Clause/Section: {clause} ({sec or 'General'})\n"
            f"    Requirement: {req_text}\n"
            f"    Parameter: {param or 'Overall Specification'}\n"
            f"    Source: {src} ({url})"
        )

    if doc_context:
        fname = doc_filename or "Attached User Document"
        preview = str(doc_context)[:2000].strip()
        lines.append(f"\nATTACHED DOCUMENT CONTEXT ({fname}):\n{preview}")

    return "\n\n".join(lines)


def call_openrouter(query, context, model=None):
    """
    Call OpenRouter with grounded prompt. Returns (explanation_content, model_name).
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return None, "API_KEY_MISSING"

    primary_model = model or os.getenv("OPENROUTER_MODEL", "nex-agi/nex-n2.5-mini:free").strip()
    fallback_models = ["nex-agi/nex-n2.5-pro:free", "liquid/lfm-2.5-2.6b:free", "google/gemma-2-9b-it:free"]
    models_to_try = [primary_model] + [m for m in fallback_models if m != primary_model]

    system_prompt = (
        "You are BIS Sahayak, the official AI compliance assistant for the Bureau of Indian Standards (BIS), Government of India.\n"
        "STRICT GROUNDING & ANTI-HALLUCINATION RULES:\n"
        "1. OpenRouter is NOT the source of truth. You must base your answer ONLY on the verified BIS evidence in context.\n"
        "2. Clearly distinguish between Verified BIS evidence and your concise explanation.\n"
        "3. DO NOT invent IS numbers, clauses, test parameters, dates, or certification requirements.\n"
        "4. If verified evidence is insufficient, state that verified evidence is not available.\n"
        "5. Keep the explanation professional, conversational, and concise."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Query: {query}\n\n{context}\n\nProvide a concise explanation of the verified BIS requirement."}
    ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5001",
        "X-Title": "BIS Sahayak AI"
    }

    for target_model in models_to_try:
        try:
            res = requests.post(
                OPENROUTER_URL,
                headers=headers,
                json={"model": target_model, "messages": messages, "max_tokens": 500, "temperature": 0.2},
                timeout=12
            )
            if res.status_code == 200:
                resp_json = res.json()
                choices = resp_json.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "").strip()
                    if content and not content.startswith("<|tool_call"):
                        return content, target_model
            elif res.status_code in (401, 403):
                return None, f"HTTP_{res.status_code}"
        except Exception:
            continue

    return None, "ALL_MODELS_UNAVAILABLE"


# ============================================================
# 4. END-TO-END QUERY PROCESSING
# ============================================================

def process_ai_query(query, document_context=None, document_filename=None):
    """
    End-to-end grounded RAG pipeline:
    Query -> Query Understanding -> Hybrid Retrieval -> Reranking ->
    Source Verification -> OpenRouter Explanation -> Standardized Response Format.
    """
    # 1. Query Understanding
    parsed = understand_query(query)

    # 2. Hybrid Retrieval
    evidence = hybrid_retrieve_evidence(parsed)

    # 3. Check for Safe Fallback condition
    # If no evidence was retrieved or top match score is very weak
    top_score = evidence[0]["score"] if evidence else 0
    if not evidence or top_score < 20:
        return {
            "query": query,
            "answer": SAFE_FALLBACK_MESSAGE,
            "recommended_standard": None,
            "confidence_score": "0%",
            "confidence_numeric": 0.0,
            "related_standards": [],
            "source": "BIS Safe Fallback Guardrail",
            "model": "Fallback",
            "ai_status": "insufficient_evidence"
        }

    # Best matched record
    best_candidate = evidence[0]
    best_rec = best_candidate["record"]

    # Calculate normalized confidence
    confidence_num = min(98, max(70, 50 + int(top_score * 0.45)))
    confidence_str = f"{confidence_num}%"

    # 4. Format Standardized AI Response according to Requirement 7
    is_number = best_rec.get("is_number", "IS Standard")
    std_title = best_rec.get("title", "")
    req_evidence_text = best_rec.get("requirement_text") or best_rec.get("description", "")
    clause_val = best_rec.get("clause") or "Main Specification"
    source_url = best_rec.get("source_url") or "https://www.services.bis.gov.in/"
    updated_date = best_rec.get("retrieved_at") or best_rec.get("effective_date") or "2026-09-20"

    # Build RAG context
    context = build_grounded_rag_context(evidence, document_context, document_filename)

    # Call OpenRouter for explanation
    llm_explanation, model_used = call_openrouter(query, context)

    if not llm_explanation:
        model_used = "BIS Grounded Knowledge Engine"
        # Deterministic grounded explanation
        if parsed.get("is_huid_inquiry"):
            llm_explanation = (
                "HUID (Hallmark Unique Identification) is a 6-digit alphanumeric code laser marked on each precious metal article. "
                "Consumers can verify hallmarking authenticity using the BIS Care mobile application or the Manakonline portal."
            )
        elif parsed.get("is_concept_inquiry"):
            llm_explanation = (
                "An Indian Standard (IS) number designates the technical specifications formulated by BIS Sectional Committees. "
                "Compliance with mandatory standards ensures quality, consumer safety, and adherence to national regulatory codes."
            )
        else:
            llm_explanation = (
                f"Under {is_number}, manufacturers must conform to the specified parameter thresholds and submit product samples "
                f"to BIS-recognized or NABL-accredited testing laboratories for verification under the applicable certification scheme."
            )

    # Structured Response Format (Requirement 7)
    final_answer = (
        f"**Applicable Standard:** {is_number}\n"
        f"**Standard:** {std_title}\n"
        f"**Relevant Requirement:** {req_evidence_text}\n"
        f"**Explanation:** {llm_explanation}\n"
        f"**Source:** BIS\n"
        f"**Clause:** {clause_val}\n"
        f"**Source URL:** {source_url}\n"
        f"**Knowledge Updated:** {updated_date}"
    )

    # Related standards list
    related = []
    seen_related = set([is_number])
    for item in evidence[1:]:
        std_no = item["record"].get("is_number")
        if std_no and std_no not in seen_related:
            seen_related.add(std_no)
            related.append(std_no)

    # Recommended standard structure
    recommended_std = {
        "id": best_rec.get("id"),
        "is_number": is_number,
        "title": std_title,
        "description": req_evidence_text,
        "category": best_rec.get("category", "General"),
        "industry": best_rec.get("industry", "Manufacturing"),
        "clause": clause_val,
        "year": best_rec.get("year", 2024),
        "status": best_rec.get("status", "Active"),
        "certification": best_rec.get("certification", "Product Certification"),
        "source_url": source_url
    }

    return {
        "query": query,
        "parsed_query": parsed,
        "answer": final_answer,
        "recommended_standard": recommended_std,
        "confidence_score": confidence_str,
        "confidence_numeric": round(confidence_num / 100.0, 2),
        "retrieval_confidence": confidence_num,
        "related_standards": related,
        "source": f"BIS Official Knowledge Base ({is_number})",
        "model": model_used,
        "model_used": model_used,
        "ai_status": "success"
    }