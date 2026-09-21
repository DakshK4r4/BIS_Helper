"""Document-level ingestion and indexing script for BIS Sahayak.

Ingests standards and test specifications into `bis_documents` and `bis_chunks`
tables in SQLite, extracts text and clauses, and triggers RAG index synchronization.
"""

import os
import sys
import re
import json
import uuid
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from database import (
    get_db,
    save_bis_document,
    save_bis_chunks,
    get_bis_documents,
    get_bis_chunks,
)
from document_processor import process_document


def chunk_text_by_clauses_or_paragraphs(text, max_chunk_words=300, overlap=50):
    """
    Split text into semantically cohesive chunks.
    Attempts to break on Clause / Section headers or REQ patterns;
    falls back to sliding window over paragraphs.
    """
    if not text or not text.strip():
        return []

    lines = text.split("\n")
    chunks = []
    current_clause = None
    current_section = None
    current_lines = []
    current_word_count = 0

    clause_regex = re.compile(r"^(?:Clause|Section|CL|REQ)[\s\.:-]*([0-9A-Za-z\.\-_]+)\s*[:\-]?(.*)$", re.IGNORECASE)
    is_regex = re.compile(r"\bIS\s*[:\-_]?\s*(\d{2,5})(?:\s*\(\s*Part\s*(\d+)\s*\))?", re.IGNORECASE)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        match = clause_regex.match(stripped)
        if match and current_lines:
            # New clause detected
            chunk_body = "\n".join(current_lines).strip()
            if chunk_body:
                chunks.append({
                    "clause": current_clause,
                    "section": current_section,
                    "text": chunk_body
                })
            current_clause = match.group(1).strip()
            current_section = match.group(2).strip() or None
            current_lines = [stripped]
            current_word_count = len(stripped.split())
            continue

        words = len(stripped.split())
        if current_word_count + words > max_chunk_words and current_lines:
            chunk_body = "\n".join(current_lines).strip()
            chunks.append({
                "clause": current_clause,
                "section": current_section,
                "text": chunk_body
            })
            # Overlap: keep last few lines if any
            overlap_lines = current_lines[-2:] if len(current_lines) >= 2 else []
            current_lines = overlap_lines + [stripped]
            current_word_count = sum(len(l.split()) for l in current_lines)
        else:
            current_lines.append(stripped)
            current_word_count += words

    if current_lines:
        chunk_body = "\n".join(current_lines).strip()
        if chunk_body:
            chunks.append({
                "clause": current_clause,
                "section": current_section,
                "text": chunk_body
            })

    return chunks


def index_knowledge_base_standards():
    """
    Ingest clauses from `bis_knowledge` and `standards` tables into
    `bis_documents` and `bis_chunks`.
    """
    conn = get_db()
    try:
        # Group bis_knowledge by is_number
        rows = conn.execute("SELECT * FROM bis_knowledge").fetchall()
        by_std = {}
        for r in rows:
            rec = dict(r)
            is_num = rec.get("is_number")
            if is_num not in by_std:
                by_std[is_num] = []
            by_std[is_num].append(rec)

        print(f"Indexing {len(by_std)} standards from bis_knowledge...")
        for is_num, clauses in by_std.items():
            first = clauses[0]
            doc_id = f"doc_{re.sub(r'[^A-Za-z0-9]', '_', is_num)}"
            save_bis_document({
                "document_id": doc_id,
                "title": first.get("title", is_num),
                "is_number": is_num,
                "document_type": first.get("document_type", "Standard Specification"),
                "publication_year": int(first.get("edition")) if first.get("edition") and first.get("edition").isdigit() else 2024,
                "category": first.get("section") or "Standard Specification",
                "total_pages": 1,
                "total_chunks": len(clauses),
                "source_path": first.get("source_url") or "BIS Knowledge Base"
            })

            chunks_to_save = []
            for cl in clauses:
                chunk_id = f"chunk_{cl['id']}_{uuid.uuid4().hex[:6]}"
                text = f"{cl.get('title')}\nClause {cl.get('clause')}: {cl.get('section') or ''}\n{cl.get('requirement_text')}"
                if cl.get("parameter"):
                    text += f"\nParameter: {cl.get('parameter')} (Acceptance: {cl.get('operator')} {cl.get('target_value') or cl.get('min_value')} {cl.get('unit') or ''})"

                chunks_to_save.append({
                    "document_id": doc_id,
                    "chunk_id": chunk_id,
                    "is_number": is_num,
                    "clause": cl.get("clause"),
                    "section": cl.get("section"),
                    "title": cl.get("title"),
                    "chunk_text": text,
                    "chunk_tokens": len(text.split()),
                    "metadata_json": {
                        "is_number": is_num,
                        "clause": cl.get("clause"),
                        "section": cl.get("section"),
                        "parameter": cl.get("parameter"),
                        "unit": cl.get("unit"),
                        "mandatory": cl.get("mandatory"),
                        "source": cl.get("source") or "BIS",
                        "source_url": cl.get("source_url")
                    }
                })
            save_bis_chunks(chunks_to_save)
    finally:
        conn.close()


def index_upload_documents(upload_dir=None):
    """
    Scan upload folder and index files into bis_documents and bis_chunks.
    """
    if upload_dir is None:
        upload_dir = os.path.join(BASE_DIR, "uploads")

    if not os.path.exists(upload_dir):
        print(f"No upload directory found at {upload_dir}")
        return

    # Files to index (skip non-relevant large slide decks/generic textbooks)
    supported_exts = {".pdf", ".docx"}
    files = [f for f in os.listdir(upload_dir) if os.path.splitext(f)[1].lower() in supported_exts]

    print(f"Found {len(files)} documents in {upload_dir}")
    for fname in files:
        # Avoid indexing massive unrelated files > 20MB
        fpath = os.path.join(upload_dir, fname)
        if os.path.getsize(fpath) > 20 * 1024 * 1024:
            print(f"Skipping oversized document ({os.path.getsize(fpath)//(1024*1024)}MB): {fname}")
            continue

        print(f"Processing document: {fname}...")
        try:
            doc_result = process_document(fpath)
            raw_text = doc_result.get("text", "")
            if len(raw_text.strip()) < 50:
                print(f"  Warning: Text too short in {fname}, skipping.")
                continue

            # Detect IS numbers in document
            is_match = re.search(r"\bIS\s*[:\-_]?\s*(\d{2,5})(?:\s*\(\s*Part\s*(\d+)\s*\))?", raw_text, re.IGNORECASE)
            detected_is = None
            if is_match:
                detected_is = f"IS {is_match.group(1)}" + (f" (Part {is_match.group(2)})" if is_match.group(2) else "")

            doc_id = f"doc_{uuid.uuid4().hex[:8]}"
            title = Path(fname).stem.replace("_", " ")

            raw_chunks = chunk_text_by_clauses_or_paragraphs(raw_text)
            print(f"  Extracted {len(raw_chunks)} chunks for {fname} (IS: {detected_is or 'General'})")

            save_bis_document({
                "document_id": doc_id,
                "title": title,
                "is_number": detected_is,
                "document_type": "Official Upload / Test Document",
                "publication_year": 2024,
                "category": "Test Report / Specification",
                "total_pages": 1,
                "total_chunks": len(raw_chunks),
                "source_path": fpath
            })

            chunks_to_save = []
            for idx, ch in enumerate(raw_chunks):
                ch_id = f"{doc_id}_c{idx+1}"
                chunks_to_save.append({
                    "document_id": doc_id,
                    "chunk_id": ch_id,
                    "is_number": detected_is,
                    "clause": ch.get("clause"),
                    "section": ch.get("section"),
                    "title": title,
                    "chunk_text": ch.get("text"),
                    "chunk_tokens": len(ch.get("text", "").split()),
                    "metadata_json": {
                        "filename": fname,
                        "is_number": detected_is,
                        "clause": ch.get("clause"),
                        "section": ch.get("section"),
                        "source": f"Uploaded: {fname}"
                    }
                })

            save_bis_chunks(chunks_to_save)
            print(f"  Successfully indexed {len(chunks_to_save)} chunks from {fname}.")

        except Exception as e:
            print(f"  Error processing {fname}: {e}")


def main():
    print("=== BIS Sahayak Document Indexing ===")
    index_knowledge_base_standards()
    index_upload_documents()

    # Trigger RAG index refresh
    try:
        from ai_engine import ensure_rag_index
        print("Refreshing AI Engine RAG index...")
        ensure_rag_index(force=True)
        print("RAG index successfully refreshed.")
    except Exception as e:
        print(f"Notice: RAG index refresh: {e}")

    docs = get_bis_documents()
    chunks = get_bis_chunks(limit=1000)
    print(f"\nIndexing Complete: {len(docs)} documents and {len(chunks)} total chunks in database.")


if __name__ == "__main__":
    main()
