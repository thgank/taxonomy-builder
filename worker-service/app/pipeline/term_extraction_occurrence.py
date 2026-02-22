from __future__ import annotations

import re
from app.db import DocumentChunk
from app.pipeline.term_extraction_cleaning import compile_term_pattern
from app.pipeline.term_extraction_constants import TOKEN_RE


def find_occurrences(
    term: str,
    chunks: list[DocumentChunk],
    max_per_term: int = 20,
) -> list[dict]:
    def sentence_bounds(text: str, pos: int) -> tuple[int, int]:
        left = text.rfind(".", 0, pos)
        q_left = text.rfind("?", 0, pos)
        e_left = text.rfind("!", 0, pos)
        start = max(left, q_left, e_left)
        start = 0 if start < 0 else start + 1
        right_candidates = [x for x in (text.find(".", pos), text.find("?", pos), text.find("!", pos)) if x != -1]
        end = min(right_candidates) + 1 if right_candidates else len(text)
        return start, end

    def occurrence_confidence(term_text: str, snippet: str) -> float:
        toks = [t.lower() for t in TOKEN_RE.findall(term_text)]
        tok_count = max(1, len(toks))
        df = len(set(toks))
        alpha_ratio = sum(1 for ch in term_text if ch.isalpha()) / max(1, len(term_text))
        base = 0.55 + min(0.18, 0.06 * tok_count) + min(0.08, 0.03 * df)
        if len(snippet) < 25:
            base -= 0.07
        if alpha_ratio < 0.65:
            base -= 0.08
        return round(max(0.35, min(0.96, base)), 3)

    by_doc: dict[str, dict] = {}
    overflow: list[dict] = []
    pattern = compile_term_pattern(term)
    for chunk in chunks:
        doc_id = str(chunk.document_id)
        for match in pattern.finditer(chunk.text):
            s_start, s_end = sentence_bounds(chunk.text, match.start())
            start = max(0, min(match.start(), s_start))
            end = min(len(chunk.text), max(match.end(), s_end))
            snippet = re.sub(r"\s+", " ", chunk.text[start:end]).strip()
            if not snippet:
                continue
            item = {
                "chunk_id": str(chunk.id),
                "snippet": snippet,
                "start_offset": match.start(),
                "end_offset": match.end(),
                "confidence": occurrence_confidence(term, snippet),
            }
            # Keep first hit per document first, then fill remaining budget with extras.
            if doc_id not in by_doc:
                by_doc[doc_id] = item
                if len(by_doc) >= max_per_term:
                    return list(by_doc.values())[:max_per_term]
            elif len(overflow) < max_per_term:
                overflow.append(item)
    out = list(by_doc.values())
    if len(out) < max_per_term and overflow:
        out.extend(overflow[: max_per_term - len(out)])
    return out[:max_per_term]
