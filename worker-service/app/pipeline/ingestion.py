"""
Ingestion / Parsing worker
──────────────────────────
Extracts text from PDF / DOCX / HTML / TXT documents,
splits into chunks, and stores in DB.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import config
from app.db import Document, DocumentChunk
from app.job_helper import (
    update_job_status, add_job_event, is_job_cancelled,
)
from app.logger import get_logger

log = get_logger(__name__)
HEADER_PREFIXES = (
    "source:",
    "language:",
    "title:",
    "url:",
    "retrieved:",
    "author:",
    "authors:",
    "категория:",
    "источник:",
    "тілі:",
    "дереккөз:",
)
WIKI_BANNER_PATTERNS = (
    re.compile(r"^from wikipedia\b", re.IGNORECASE),
    re.compile(r"^материал из википедии\b", re.IGNORECASE),
)

# ── Text extractors ──────────────────────────────────────

def extract_text_pdf(filepath: str) -> str:
    from pdfminer.high_level import extract_text
    return extract_text(filepath) or ""


def extract_text_docx(filepath: str) -> str:
    from docx import Document as DocxDocument
    doc = DocxDocument(filepath)
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text_html(filepath: str) -> str:
    from bs4 import BeautifulSoup
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n\n", strip=True)


def extract_text_plain(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


EXTRACTORS: dict[str, Any] = {
    "application/pdf": extract_text_pdf,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": extract_text_docx,
    "text/html": extract_text_html,
    "text/plain": extract_text_plain,
}


def _clean_extracted_text(text: str) -> str:
    if "\x00" in text:
        text = text.replace("\x00", " ")
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            cleaned_lines.append("")
            continue
        low = line.lower()
        if config.strip_document_headers and low.startswith(HEADER_PREFIXES):
            continue
        if any(pat.match(line) for pat in WIKI_BANNER_PATTERNS):
            continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


# ── Chunking ─────────────────────────────────────────────

def split_into_chunks(text: str, max_size: int | None = None) -> list[dict]:
    """
    Split text into chunks:
      1. Try paragraph boundaries first
      2. If a paragraph exceeds max_size, split by sentence / fixed size
    """
    if max_size is None:
        max_size = config.chunk_size

    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[dict] = []
    offset = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            offset += 2
            continue

        if len(para) <= max_size:
            chunks.append({
                "text": para,
                "char_start": offset,
                "char_end": offset + len(para),
            })
        else:
            # split long paragraphs by sentences or fixed windows
            sentences = re.split(r"(?<=[.!?])\s+", para)
            buffer = ""
            buf_start = offset
            for sent in sentences:
                if len(buffer) + len(sent) + 1 > max_size and buffer:
                    chunks.append({
                        "text": buffer.strip(),
                        "char_start": buf_start,
                        "char_end": buf_start + len(buffer.strip()),
                    })
                    buf_start += len(buffer)
                    buffer = ""
                buffer += sent + " "
            if buffer.strip():
                chunks.append({
                    "text": buffer.strip(),
                    "char_start": buf_start,
                    "char_end": buf_start + len(buffer.strip()),
                })

        offset += len(para) + 2  # approximate newlines

    return chunks


def _merge_short_chunks(
    chunks: list[dict],
    max_size: int,
    min_chars: int,
) -> list[dict]:
    if not chunks:
        return []
    min_chars = max(1, int(min_chars))
    merged: list[dict] = []
    buf: dict | None = None

    for chunk in chunks:
        text = str(chunk.get("text", "")).strip()
        if not text:
            continue
        current = {
            "text": text,
            "char_start": int(chunk.get("char_start", 0) or 0),
            "char_end": int(chunk.get("char_end", 0) or 0),
        }
        if buf is None:
            buf = current
            continue

        should_merge = len(buf["text"]) < min_chars or len(current["text"]) < min_chars
        if should_merge:
            candidate = f"{buf['text']} {current['text']}".strip()
            if len(candidate) <= max_size:
                buf["text"] = candidate
                buf["char_end"] = current["char_end"]
                continue

        merged.append(buf)
        buf = current

    if buf is not None:
        merged.append(buf)
    return merged


# ── Handler ──────────────────────────────────────────────

def handle_import(session: Session, msg: dict) -> None:
    """Process import message: parse documents → chunks → DB."""
    job_id = str(msg.get("jobId") or msg.get("job_id"))
    collection_id = str(msg.get("collectionId") or msg.get("collection_id"))
    params = msg.get("params", {})

    update_job_status(session, job_id, "RUNNING", progress=0)
    add_job_event(session, job_id, "INFO", "Import started")

    # Fetch all NEW documents in the collection
    docs = (
        session.query(Document)
        .filter(
            Document.collection_id == collection_id,
            Document.status == "NEW",
        )
        .all()
    )

    if not docs:
        add_job_event(session, job_id, "WARN", "No NEW documents to process")
        update_job_status(session, job_id, "RUNNING", progress=100)
        return

    total = len(docs)
    chunk_size_param = params.get("chunk_size", config.chunk_size)

    for idx, doc in enumerate(docs):
        if is_job_cancelled(session, job_id):
            add_job_event(session, job_id, "WARN", "Job cancelled during import")
            return

        try:
            filepath = os.path.join(config.storage_path, doc.storage_path)
            extractor = EXTRACTORS.get(doc.mime_type)
            if extractor is None:
                if config.allow_plaintext_fallback:
                    extractor = extract_text_plain
                else:
                    doc.status = "FAILED"
                    add_job_event(
                        session,
                        job_id,
                        "WARN",
                        f"Unsupported MIME type for {doc.filename}: {doc.mime_type}",
                    )
                    session.commit()
                    continue
            text = extractor(filepath)
            text = _clean_extracted_text(text)

            if not text.strip():
                doc.status = "FAILED"
                add_job_event(
                    session, job_id, "WARN",
                    f"Empty text extracted from {doc.filename}",
                )
                session.commit()
                continue

            # Delete any existing chunks for idempotency
            session.query(DocumentChunk).filter(
                DocumentChunk.document_id == doc.id
            ).delete()

            raw_chunks = split_into_chunks(text, max_size=int(chunk_size_param))
            raw_chunks = _merge_short_chunks(
                raw_chunks,
                max_size=int(chunk_size_param),
                min_chars=config.chunk_min_chars,
            )

            for ci, chunk_data in enumerate(raw_chunks):
                chunk = DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=doc.id,
                    chunk_index=ci,
                    text=chunk_data["text"],
                    char_start=chunk_data["char_start"],
                    char_end=chunk_data["char_end"],
                )
                session.add(chunk)

            from datetime import datetime, timezone
            doc.status = "PARSED"
            doc.parsed_at = datetime.now(timezone.utc)
            session.commit()

            add_job_event(
                session, job_id, "INFO",
                f"Parsed {doc.filename}: {len(raw_chunks)} chunks",
            )
        except Exception as exc:
            session.rollback()
            doc.status = "FAILED"
            session.commit()
            add_job_event(
                session, job_id, "ERROR",
                f"Failed to parse {doc.filename}: {exc}",
            )
            log.error("Import error for %s: %s", doc.filename, exc)

        progress = int(((idx + 1) / total) * 100)
        update_job_status(session, job_id, "RUNNING", progress=progress)

    add_job_event(session, job_id, "INFO", "Import finished")
    log.info("Import complete for collection %s", collection_id)
