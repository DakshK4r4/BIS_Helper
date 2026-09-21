"""Grounded hybrid RAG retrieval for the BIS Sahayak AI Assistant.

Only existing SQLite catalogue and clause data are indexed.  The sparse vector
index is persisted in SQLite and is updated only when its source text changes.
"""
import hashlib
import json
import math
import os
import re

import requests
from dotenv import load_dotenv

from database import DB_PATH, get_db

load_dotenv()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
TOKEN_RE = re.compile(r"[a-z0-9]+")
EMBEDDING_MODEL_NAME = os.getenv("BIS_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
SAFE_FALLBACK_MESSAGE = (
    "I could not find a verified BIS standard or clause matching your request. "
    "Please specify an Indian Standard number (e.g., IS 456, IS 14543) or check the official BIS portal (bis.gov.in) for the latest published standards."
)

# Query-normalisation aliases only. They introduce no standards, clauses, or
# requirements; they allow semantically related wording to share vector terms.
CONCEPT_ALIASES = {
    "water": {"water", "bottled", "bottle", "beverage", "drinking", "mineral", "packaged"},
    "concrete": {"concrete", "rcc", "reinforced", "cementitious", "slab", "beam", "column"},
    "cement": {"cement", "opc", "ppc", "portland", "pozzolana", "fineness", "setting"},
    "socket": {"plug", "plugs", "socket", "sockets", "outlet", "outlets", "shutter", "pin"},
    "lighting": {"led", "luminaire", "luminaires", "lamp", "lamps", "lighting", "light", "bulb"},
    "cable": {"cable", "cables", "wire", "wires", "pvc", "conductor", "insulation"},
    "steel": {"steel", "tmt", "rebar", "tube", "tubes", "pipe", "pipes", "structural"},
    "appliance": {"appliance", "appliances", "household", "electrical", "equipment"},
    "battery": {"battery", "batteries", "cell", "cells", "lithium", "charger"},
    "certification": {"certification", "certified", "mandatory", "compulsory", "license", "licensing", "isi", "mark"},
    "hallmark": {"huid", "hallmark", "hallmarking", "jewellery", "jewelry", "gold", "silver"},
}
STOP_WORDS = {
    "a", "an", "and", "are", "about", "be", "bis", "can", "do", "does", "explain", "find", "for",
    "give", "how", "i", "in", "indian", "is", "it", "me", "of", "on", "please", "product",
    "requirements", "requirement", "standard", "standards", "tell", "that", "the", "this", "to", "what",
    "which", "with", "you",
}
RAG_SCHEMA = """
CREATE TABLE IF NOT EXISTS rag_chunks (
    chunk_key TEXT PRIMARY KEY, content_hash TEXT NOT NULL, source_table TEXT NOT NULL,
    source_id INTEGER NOT NULL, content TEXT NOT NULL, metadata_json TEXT NOT NULL,
    vector_json TEXT NOT NULL, indexed_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""
_INDEX_DB_PATH = None
_EMBEDDING_MODEL = None
_EMBEDDING_UNAVAILABLE = False


def _tokens(text):
    return [token for token in TOKEN_RE.findall((text or "").lower()) if token not in STOP_WORDS]


def _vectorise(text):
    """Create a normalised sparse semantic vector suitable for cosine search."""
    values = {}
    for token in _tokens(text):
        values[token] = values.get(token, 0.0) + 1.0
        for concept, aliases in CONCEPT_ALIASES.items():
            if token in aliases:
                key = f"concept:{concept}"
                values[key] = values.get(key, 0.0) + 1.0
    magnitude = math.sqrt(sum(value * value for value in values.values()))
    return {} if not magnitude else {key: round(value / magnitude, 8) for key, value in values.items()}


def _cosine(left, right):
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(key, 0.0) for key, value in left.items())


def _embedding_model():
    """Load the local, cached SentenceTransformers model once per process."""
    global _EMBEDDING_MODEL, _EMBEDDING_UNAVAILABLE
    if _EMBEDDING_MODEL is not None:
        return _EMBEDDING_MODEL
    if _EMBEDDING_UNAVAILABLE:
        return None
    try:
        # Import lazily: Flask can still return a safe, grounded fallback when
        # a deployment has not installed the optional model runtime yet.
        model_cache = os.path.join(os.path.dirname(DB_PATH), "embedding-models")
        os.makedirs(model_cache, exist_ok=True)
        # Keep all Hugging Face/Xet artifacts under application data rather
        # than a developer home directory or an external service.
        os.environ.setdefault("HF_HOME", model_cache)
        os.environ.setdefault("HF_HUB_CACHE", model_cache)
        os.environ.setdefault("HF_XET_CACHE", model_cache)
        from sentence_transformers import SentenceTransformer
        _EMBEDDING_MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME, cache_folder=model_cache)
        return _EMBEDDING_MODEL
    except Exception as error:
        _EMBEDDING_UNAVAILABLE = True
        print(f"RAG embedding model unavailable: {type(error).__name__}")
        return None


def _encode(texts):
    """Return normalised, genuine model embeddings or None when unavailable."""
    model = _embedding_model()
    if not model:
        return None
    try:
        return model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()
    except Exception as error:
        print(f"RAG embedding encode failed: {type(error).__name__}")
        return None


def _dense_cosine(left, right):
    if not left or not right or len(left) != len(right):
        return 0.0
    # SentenceTransformers embeddings are L2-normalised above.
    return sum(a * b for a, b in zip(left, right))


def _standard_number(value):
    match = re.search(r"\bIS\s*[:\-_]?\s*(\d{2,6})(?:\s*\(\s*Part\s*(\d+)\s*\))?", value or "", re.I)
    if not match:
        return None
    return f"IS {match.group(1)}" + (f" (Part {match.group(2)})" if match.group(2) else "")


def _source_rows(conn):
    """Convert existing records into chunks, retaining only existing metadata."""
    chunks = []
    for row in conn.execute("SELECT * FROM bis_knowledge").fetchall():
        record = dict(row)
        content = "\n".join(filter(None, [record.get("is_number"), record.get("title"), record.get("section"), record.get("parameter"), record.get("keywords"), record.get("requirement_text")]))
        metadata = {
            "is_number": record.get("is_number"), "title": record.get("title"), "edition": record.get("edition"),
            "clause": record.get("clause"), "section": record.get("section"), "source": record.get("source"),
            "source_url": record.get("source_url"), "document_type": record.get("document_type"),
            "effective_date": record.get("effective_date"), "retrieved_at": record.get("retrieved_at"),
            "requirement_text": record.get("requirement_text"), "parameter": record.get("parameter"),
        }
        chunks.append((f"knowledge:{record['id']}", "bis_knowledge", record["id"], content, metadata))
    for row in conn.execute("SELECT * FROM standards").fetchall():
        record = dict(row)
        content = "\n".join(filter(None, [record.get("is_number"), record.get("title"), record.get("description"), record.get("category"), record.get("industry"), record.get("keywords")]))
        metadata = {
            "is_number": record.get("is_number"), "title": record.get("title"), "edition": str(record.get("year")) if record.get("year") else None,
            "clause": None, "section": None, "source": None, "source_url": None,
            "document_type": "Project standards catalogue", "effective_date": None, "retrieved_at": None,
            "requirement_text": record.get("description"), "parameter": None,
        }
        chunks.append((f"standard:{record['id']}", "standards", record["id"], content, metadata))

    # 3. Chunks from indexed BIS documents
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bis_chunks'")
        if cursor.fetchone():
            for row in conn.execute("SELECT * FROM bis_chunks").fetchall():
                record = dict(row)
                content = "\n".join(filter(None, [
                    record.get("is_number"), record.get("title"), record.get("clause"),
                    record.get("section"), record.get("chunk_text")
                ]))
                metadata = {
                    "is_number": record.get("is_number"), "title": record.get("title"), "edition": None,
                    "clause": record.get("clause") or "Section", "section": record.get("section"),
                    "source": "BIS Official Documents", "source_url": "https://www.services.bis.gov.in/",
                    "document_type": "Official BIS Document Chunk", "effective_date": None, "retrieved_at": None,
                    "requirement_text": record.get("chunk_text"), "parameter": None,
                    "chunk_id": record.get("chunk_id")
                }
                chunks.append((f"chunk:{record['chunk_id']}", "bis_chunks", record["id"], content, metadata))
    except Exception as e:
        print(f"Notice: loading bis_chunks into RAG: {e}")

    return chunks


def ensure_rag_index(force=False):
    """Persist new/changed vectors once; a user query never rebuilds the index."""
    global _INDEX_DB_PATH
    if _INDEX_DB_PATH == DB_PATH and not force:
        return
    conn = get_db()
    try:
        conn.execute(RAG_SCHEMA)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(rag_chunks)").fetchall()}
        if "embedding_json" not in columns:
            conn.execute("ALTER TABLE rag_chunks ADD COLUMN embedding_json TEXT")
        if "embedding_model" not in columns:
            conn.execute("ALTER TABLE rag_chunks ADD COLUMN embedding_model TEXT")
        expected = set()
        pending = []
        model = _embedding_model()
        source_rows = _source_rows(conn)
        for key, table, source_id, content, metadata in source_rows:
            expected.add(key)
            content_hash = hashlib.sha256((content + json.dumps(metadata, sort_keys=True)).encode("utf-8")).hexdigest()
            row = conn.execute("SELECT content_hash, embedding_json, embedding_model FROM rag_chunks WHERE chunk_key = ?", (key,)).fetchone()
            embedding_needs_refresh = bool(model and (not row or not row["embedding_json"] or row["embedding_model"] != EMBEDDING_MODEL_NAME))
            if not row or row["content_hash"] != content_hash or embedding_needs_refresh:
                pending.append((key, table, source_id, content, metadata, content_hash))

        embeddings = _encode([item[3] for item in pending]) if pending and model else None
        for index, (key, table, source_id, content, metadata, content_hash) in enumerate(pending):
            embedding = embeddings[index] if embeddings else None
            conn.execute("""
                INSERT INTO rag_chunks (chunk_key, content_hash, source_table, source_id, content, metadata_json, vector_json, embedding_json, embedding_model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_key) DO UPDATE SET content_hash=excluded.content_hash,
                source_table=excluded.source_table, source_id=excluded.source_id, content=excluded.content,
                metadata_json=excluded.metadata_json, vector_json=excluded.vector_json,
                embedding_json=COALESCE(excluded.embedding_json, rag_chunks.embedding_json),
                embedding_model=COALESCE(excluded.embedding_model, rag_chunks.embedding_model), indexed_at=CURRENT_TIMESTAMP
            """, (key, content_hash, table, source_id, content, json.dumps(metadata), json.dumps(_vectorise(content)),
                  json.dumps(embedding) if embedding else None, EMBEDDING_MODEL_NAME if embedding else None))
        for row in conn.execute("SELECT chunk_key FROM rag_chunks").fetchall():
            if row["chunk_key"] not in expected:
                conn.execute("DELETE FROM rag_chunks WHERE chunk_key = ?", (row["chunk_key"],))
        conn.commit()
        _INDEX_DB_PATH = DB_PATH
    finally:
        conn.close()


def resolve_coreference(query, conversation_history=None):
    """
    If the current query contains pronouns or lacks a standard identifier,
    extract context from recent conversation turns.
    """
    if not conversation_history:
        return query, None

    clean_query = (query or "").strip()
    explicit_is = _standard_number(clean_query)
    if explicit_is:
        return clean_query, explicit_is

    ref_patterns = [
        r"\b(it|its|this|that|these|the standard|the code|the specification|the clauses?|the requirement|the test)\b",
        r"^(what\s+about|and\s+what\s+about|and|explain\s+scope|what\s+is\s+the\s+scope|scope\??|testing\??|acceptance\??)\b"
    ]
    has_ref = any(re.search(pat, clean_query, re.IGNORECASE) for pat in ref_patterns)
    is_short_followup = len(clean_query.split()) <= 6 and any(k in clean_query.lower() for k in ["scope", "clause", "requirement", "test", "tolerance", "cover", "criteria"])

    if not has_ref and not is_short_followup:
        return query, None

    context_is = None
    for turn in reversed(conversation_history):
        text = ""
        if isinstance(turn, dict):
            text = (
                turn.get("content") or
                turn.get("query") or
                turn.get("answer") or
                turn.get("message") or
                ""
            )
            rec = turn.get("recommended_standard") or turn.get("standard")
            if isinstance(rec, dict) and rec.get("is_number"):
                context_is = _standard_number(rec["is_number"])
                if context_is:
                    break
            elif isinstance(rec, str):
                context_is = _standard_number(rec)
                if context_is:
                    break
        elif isinstance(turn, str):
            text = turn

        found_is = _standard_number(text)
        if found_is:
            context_is = found_is
            break

    if context_is:
        resolved_query = f"{clean_query} for {context_is}"
        return resolved_query, context_is

    return query, None


def understand_query(query, conversation_history=None):
    """Normalise intent, product concepts, IS number, keywords, and technical terms."""
    clean_query = (query or "").strip()
    if not clean_query:
        return {
            "query": "",
            "intent": "empty_query",
            "is_number": None,
            "product": None,
            "keywords": [],
            "technical_terms": [],
            "semantic_concepts": [],
            "coreference_resolved": False
        }

    lower = clean_query.lower()

    # 1. Fast-path intent: General conversation / greeting / capabilities
    greeting_patterns = [
        r"^(hi|hello|hey|namaste|greetings|good\s+(morning|afternoon|evening))\b",
        r"^(who\s+are\s+you|what\s+is\s+bis\s+sahayak|what\s+can\s+you\s+do|how\s+does\s+this\s+work|help\s*me|help)\b",
        r"^howdy\b"
    ]
    if any(re.search(pat, lower.strip()) for pat in greeting_patterns):
        return {
            "query": clean_query,
            "intent": "general_conversation",
            "is_number": None,
            "product": None,
            "keywords": _tokens(clean_query),
            "technical_terms": [],
            "semantic_concepts": [],
            "coreference_resolved": False
        }

    # 2. Out of scope queries (sports, weather, recipes, poems)
    out_of_scope_patterns = [
        r"\b(world cup|cricket score|football match|recipe for|bake a cake|weather today|write a poem|write a song|tell me a joke)\b"
    ]
    if any(re.search(pat, lower) for pat in out_of_scope_patterns):
        return {
            "query": clean_query,
            "intent": "out_of_scope",
            "is_number": None,
            "product": None,
            "keywords": _tokens(clean_query),
            "technical_terms": [],
            "semantic_concepts": [],
            "coreference_resolved": False
        }

    # 3. Coreference resolution with conversation history
    resolved_query, resolved_is = resolve_coreference(clean_query, conversation_history)
    active_query = resolved_query if resolved_query else clean_query

    explicit_is = resolved_is or _standard_number(active_query)
    query_tokens = _tokens(active_query)
    concepts = [concept for concept, aliases in CONCEPT_ALIASES.items() if any(token in aliases for token in query_tokens)]

    if explicit_is:
        intent = "standard_lookup"
    elif "certification" in concepts:
        intent = "certification_questions"
    elif "hallmark" in concepts:
        intent = "huid_questions"
    elif any(phrase in lower for phrase in ("what is an is number", "what is is number", "what does is stand", "is numbering")):
        intent = "general_concept"
    elif concepts:
        intent = "product_inquiry"
    else:
        intent = "general_search"

    return {
        "query": active_query,
        "original_query": clean_query,
        "intent": intent,
        "is_number": explicit_is,
        "product": concepts[0] if concepts else None,
        "keywords": query_tokens,
        "technical_terms": [token for token in query_tokens if len(token) > 4],
        "semantic_concepts": concepts,
        "coreference_resolved": bool(resolved_is and resolved_is != _standard_number(clean_query))
    }


def _keyword_similarity(query_tokens, content):
    query_set, content_set = set(query_tokens), set(_tokens(content))
    return len(query_set & content_set) / len(query_set) if query_set and content_set else 0.0


def hybrid_retrieve_evidence(parsed_query, limit=5):
    """Rerank combined semantic-vector, keyword, and exact-IS candidates."""
    ensure_rag_index()
    query_vector = _vectorise(parsed_query.get("query", ""))
    query_embedding_batch = _encode([parsed_query.get("query", "")])
    query_embedding = query_embedding_batch[0] if query_embedding_batch else None
    requested = re.search(r"\d{2,5}", parsed_query.get("is_number") or "")
    requested_number = requested.group() if requested else None
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM rag_chunks").fetchall()
    finally:
        conn.close()
    candidates = []
    for row in rows:
        metadata, vector = json.loads(row["metadata_json"]), json.loads(row["vector_json"])
        stored_embedding = json.loads(row["embedding_json"]) if row["embedding_json"] else None
        semantic_score = _dense_cosine(query_embedding, stored_embedding) if query_embedding and stored_embedding else _cosine(query_vector, vector)
        keyword_score = _keyword_similarity(parsed_query["keywords"], row["content"])
        exact = bool(requested_number and re.search(rf"\b{re.escape(requested_number)}\b", metadata.get("is_number") or ""))
        # Exact known identifiers always outrank similarity; other scores are a
        # meaningful weighted combination of independently measured similarity.
        score = 0.96 + 0.04 * max(semantic_score, keyword_score) if exact else 0.65 * semantic_score + 0.35 * keyword_score
        if score:
            candidates.append({"score": min(score, 1.0), "semantic_score": semantic_score,
                               "keyword_score": keyword_score, "exact_is_match": exact,
                               "semantic_backend": "sentence-transformers" if query_embedding and stored_embedding else "sparse-fallback",
                               "record": metadata, "type": row["source_table"]})
    candidates.sort(key=lambda item: (item["exact_is_match"], item["score"], item["semantic_score"]), reverse=True)
    selected, seen = [], set()
    for candidate in candidates:
        record = candidate["record"]
        key = (record.get("is_number"), record.get("clause"), record.get("requirement_text"))
        if key not in seen:
            seen.add(key)
            selected.append(candidate)
    return selected[:limit]


def build_grounded_rag_context(evidence_candidates, doc_context=None, doc_filename=None):
    """Build compact LLM context from selected evidence only."""
    sections = ["RETRIEVED BIS KNOWLEDGE CONTEXT:"]
    for index, candidate in enumerate(evidence_candidates, 1):
        record = candidate["record"]
        sections.append("\n".join([
            f"BIS SOURCE {index}", f"IS Number: {record.get('is_number') or 'Not specified'}",
            f"Title: {record.get('title') or 'Not specified'}", f"Clause: {record.get('clause') or 'Not specified'}",
            f"Section: {record.get('section') or 'Not specified'}", f"Content: {record.get('requirement_text') or 'Not specified'}",
            f"Source: {record.get('source') or 'Project-local BIS knowledge'}", f"Source URL: {record.get('source_url') or 'Not available'}",
        ]))
    if doc_context:
        sections.append(f"ATTACHED USER DOCUMENT ({doc_filename or 'document'}):\n{str(doc_context)[:2000].strip()}")
    return "\n\n".join(sections)


def call_openrouter(query, context, model=None):
    """Use OpenRouter solely as the grounded explanation layer."""
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return None, "API_KEY_MISSING"
    system_prompt = (
        "You are BIS Sahayak. OpenRouter is an explanation layer, not the source of truth. "
        "Use ONLY supplied BIS context for standards, clauses, requirements, certification, testing, limits, dates, and regulations. "
        "Do not invent IS numbers, clauses, requirements, test values, certification rules, dates, or BIS regulations. "
        "If context is insufficient, say so plainly. Be concise and conversational."
    )
    try:
        response = requests.post(OPENROUTER_URL, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model or os.getenv("OPENROUTER_MODEL", "nex-agi/nex-n2.5-mini:free"), "messages": [
                {"role": "system", "content": system_prompt}, {"role": "user", "content": f"Question: {query}\n\n{context}"}],
                "max_tokens": 500, "temperature": 0.1}, timeout=12)
        if response.status_code == 200:
            content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if content and not content.startswith("<|tool_call"):
                return content, model or os.getenv("OPENROUTER_MODEL", "nex-agi/nex-n2.5-mini:free")
        return None, f"HTTP_{response.status_code}"
    except requests.RequestException:
        return None, "OPENROUTER_UNAVAILABLE"
    except (KeyError, TypeError, ValueError):
        return None, "OPENROUTER_INVALID_RESPONSE"


def _sources(evidence):
    sources, seen = [], set()
    for candidate in evidence:
        record = candidate["record"]
        key = (record.get("is_number"), record.get("clause"), record.get("requirement_text"))
        if key not in seen:
            seen.add(key)
            sources.append({"is_number": record.get("is_number"), "title": record.get("title"), "clause": record.get("clause"),
                            "source": record.get("source") or "Project-local BIS knowledge", "source_url": record.get("source_url"),
                            "document_type": record.get("document_type")})
    return sources


def process_ai_query(query, document_context=None, document_filename=None, conversation_history=None):
    """Query understanding → intent routing → hybrid RAG → grounded explanation."""
    if not query or not str(query).strip():
        raise ValueError("A query is required.")

    parsed = understand_query(query, conversation_history=conversation_history)

    # 1. Fast path: General conversation / greetings
    if parsed.get("intent") == "general_conversation":
        return {
            "query": query,
            "parsed_query": parsed,
            "answer": (
                "Hello! I am BIS Sahayak, your official AI assistant for Indian Standards (Bureau of Indian Standards).\n\n"
                "I can help you:\n"
                "• Look up specific Indian Standards (e.g., IS 456 for concrete, IS 14543 for packaged water, IS 10322 for LED luminaires, IS 1293 for plugs/sockets)\n"
                "• Check clause requirements and technical acceptance criteria\n"
                "• Verify ISI certification and Hallmarking (HUID) regulations\n"
                "• Audit lab test reports and quality documents for compliance\n\n"
                "How can I assist you today?"
            ),
            "recommended_standard": None,
            "sources": [],
            "confidence": 1.0,
            "confidence_score": "100%",
            "confidence_numeric": 1.0,
            "retrieval_confidence": 1.0,
            "related_standards": ["IS 456", "IS 14543", "IS 10322", "IS 1293"],
            "source": "BIS Sahayak Core Assistant",
            "model": "Assistant Intent Router",
            "model_used": "Assistant Intent Router",
            "ai_status": "success",
            "intent": "general_conversation"
        }

    # 2. Scope guardrail: Out of scope
    if parsed.get("intent") == "out_of_scope":
        return {
            "query": query,
            "parsed_query": parsed,
            "answer": (
                "I specialize strictly in Bureau of Indian Standards (BIS) specifications, Indian Standards (IS codes), "
                "product compliance, testing criteria, and certification schemes. Your query appears to be outside this scope.\n\n"
                "Please ask a question related to Indian Standards (e.g., IS 456 concrete, IS 14543 packaged water, IS 10322 LED lighting, or ISI marking)."
            ),
            "recommended_standard": None,
            "sources": [],
            "confidence": 0.0,
            "confidence_score": "0%",
            "confidence_numeric": 0.0,
            "retrieval_confidence": 0.0,
            "related_standards": [],
            "source": "BIS Scope Guardrail",
            "model": "Scope Guardrail",
            "model_used": "Scope Guardrail",
            "ai_status": "out_of_scope",
            "intent": "out_of_scope"
        }

    evidence = hybrid_retrieve_evidence(parsed)
    top_score = evidence[0]["score"] if evidence else 0.0

    # If query explicitly asked for an IS number, ensure an exact match exists in verified records
    if parsed.get("is_number"):
        has_exact = any(candidate.get("exact_is_match") for candidate in evidence)
        if not has_exact:
            return {
                "query": query,
                "parsed_query": parsed,
                "answer": SAFE_FALLBACK_MESSAGE,
                "recommended_standard": None,
                "sources": [],
                "confidence": 0.0,
                "confidence_score": "0%",
                "confidence_numeric": 0.0,
                "retrieval_confidence": 0.0,
                "related_standards": [],
                "source": "BIS Safe Fallback Guardrail",
                "model": "Fallback",
                "model_used": "Fallback",
                "ai_status": "insufficient_evidence",
                "intent": parsed.get("intent")
            }

    if not evidence or top_score < 0.25:
        return {
            "query": query,
            "parsed_query": parsed,
            "answer": SAFE_FALLBACK_MESSAGE,
            "recommended_standard": None,
            "sources": [],
            "confidence": 0.0,
            "confidence_score": "0%",
            "confidence_numeric": 0.0,
            "retrieval_confidence": 0.0,
            "related_standards": [],
            "source": "BIS Safe Fallback Guardrail",
            "model": "Fallback",
            "model_used": "Fallback",
            "ai_status": "insufficient_evidence",
            "intent": parsed.get("intent")
        }

    best = evidence[0]["record"]
    explanation, model_used = call_openrouter(query, build_grounded_rag_context(evidence, document_context, document_filename))
    requirement = best.get("requirement_text") or "The retrieved catalogue entry does not include a clause-level requirement."
    if not explanation:
        model_used = "Retrieved BIS Knowledge (LLM unavailable)"
        explanation = f"Based on verified BIS specifications: {requirement}"

    is_number = best.get("is_number") or "Not specified"
    title = best.get("title") or "Not specified"
    clause = best.get("clause") or "General Specification"
    source = best.get("source") or "Bureau of Indian Standards"
    source_url = best.get("source_url")

    answer = (
        f"**Answer:** {explanation}\n\n"
        f"**Relevant BIS Standard:** {is_number} – {title}\n"
        f"**Relevant Clause:** Clause {clause}\n"
        f"**Evidence:** {requirement}\n"
        f"**Source:** {source}" + (f" ({source_url})" if source_url else "") + "\n"
        f"**Confidence:** {round(top_score * 100)}%"
    )

    related = list(dict.fromkeys(
        item["record"].get("is_number") for item in evidence[1:]
        if item["record"].get("is_number") and item["record"].get("is_number") != is_number
    ))
    confidence = round(top_score, 2)

    return {
        "query": query,
        "parsed_query": parsed,
        "answer": answer,
        "recommended_standard": {
            "is_number": is_number,
            "title": title,
            "description": requirement,
            "clause": clause,
            "source_url": source_url
        },
        "sources": _sources(evidence),
        "confidence": confidence,
        "confidence_score": f"{round(confidence * 100)}%",
        "confidence_numeric": confidence,
        "retrieval_confidence": confidence,
        "related_standards": related,
        "source": source,
        "model": model_used,
        "model_used": model_used,
        "semantic_backend": evidence[0].get("semantic_backend"),
        "ai_status": "success",
        "intent": parsed.get("intent")
    }
