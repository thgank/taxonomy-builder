from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any

from app.db import DocumentChunk
from app.pipeline.term_extraction_cleaning import is_noise_token, normalize_term
from app.pipeline.term_extraction_constants import TOKEN_RE


def split_phrase(phrase: str) -> list[str]:
    parts = re.split(
        r"\s*(?:,|;|/|\band\b|\bor\b|\bи\b|\bили\b|\bжәне\b|\bнемесе\b)\s*",
        phrase.strip(),
        flags=re.IGNORECASE,
    )
    return [p.strip() for p in parts if len(p.strip()) >= 2]


def is_allowed_np(span: Any) -> bool:
    tokens = [t for t in span if not t.is_space and not t.is_punct]
    if not tokens or len(tokens) > 4:
        return False
    allowed = {"ADJ", "NOUN", "PROPN", "NUM"}
    if any(t.pos_ not in allowed for t in tokens):
        return False
    if tokens[-1].pos_ not in {"NOUN", "PROPN"}:
        return False
    return any(t.pos_ in {"NOUN", "PROPN"} for t in tokens)


def extract_noun_phrases_spacy(text: str, nlp_model: Any) -> list[str]:
    doc = nlp_model(text[:100_000])
    phrases = []
    for np in doc.noun_chunks:
        if not is_allowed_np(np):
            continue
        clean = np.text.strip()
        for part in split_phrase(clean):
            phrases.append(part)
    for token in doc:
        if token.pos_ in ("NOUN", "PROPN") and len(token.text) > 2:
            phrases.append(token.text)
    return phrases


def extract_ngrams(text: str, ns: tuple[int, ...] = (1, 2)) -> list[str]:
    tokens = [t.lower() for t in TOKEN_RE.findall(text) if len(t) >= 2]
    tokens = [t for t in tokens if not is_noise_token(t)]
    grams = []
    for n in ns:
        for i in range(len(tokens) - n + 1):
            grams.append(" ".join(tokens[i : i + n]))
    return grams


def tfidf_extract(
    chunks: list[DocumentChunk],
    nlp_model: Any,
    max_terms: int,
    min_freq: int,
    min_doc_freq: int,
) -> dict[str, float]:
    term_doc_map: dict[str, set] = defaultdict(set)
    term_count: Counter = Counter()
    for chunk in chunks:
        candidates = extract_noun_phrases_spacy(chunk.text, nlp_model) if nlp_model else extract_ngrams(chunk.text)
        seen_in_chunk: set[str] = set()
        for raw in candidates:
            norm = normalize_term(raw, nlp_model)
            if not norm:
                continue
            term_count[norm] += 1
            if norm not in seen_in_chunk:
                term_doc_map[norm].add(str(chunk.document_id))
                seen_in_chunk.add(norm)

    num_docs = len(set(str(c.document_id) for c in chunks)) or 1
    scores: dict[str, float] = {}
    for term, count in term_count.items():
        if count < min_freq or len(term_doc_map[term]) < min_doc_freq:
            continue
        tf = math.log1p(count)
        idf = math.log1p(num_docs / len(term_doc_map[term]))
        scores[term] = round(tf * idf, 4)
    sorted_terms = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_terms[:max_terms])


def textrank_extract(
    chunks: list[DocumentChunk],
    nlp_model: Any,
    max_terms: int,
    window: int = 4,
    iterations: int = 30,
    damping: float = 0.85,
) -> dict[str, float]:
    import numpy as np

    all_tokens: list[list[str]] = []
    for chunk in chunks:
        text = chunk.text.lower()
        tokens = [t for t in TOKEN_RE.findall(text) if len(t) >= 2]
        tokens = [t for t in tokens if not is_noise_token(t)]
        if nlp_model:
            doc = nlp_model(chunk.text[:50_000])
            tokens = [t.lemma_.lower() for t in doc if t.pos_ in ("NOUN", "PROPN", "ADJ") and len(t.text) > 2]
            tokens = [t for t in tokens if not is_noise_token(t)]
        all_tokens.append(tokens)

    vocab: dict[str, int] = {}
    for tokens in all_tokens:
        for t in tokens:
            if t not in vocab:
                vocab[t] = len(vocab)
    n = len(vocab)
    if n == 0:
        return {}

    cooccur = np.zeros((n, n), dtype=np.float32)
    for tokens in all_tokens:
        for i, t1 in enumerate(tokens):
            for j in range(i + 1, min(i + window + 1, len(tokens))):
                t2 = tokens[j]
                if t1 in vocab and t2 in vocab:
                    idx1, idx2 = vocab[t1], vocab[t2]
                    cooccur[idx1][idx2] += 1
                    cooccur[idx2][idx1] += 1
    col_sums = cooccur.sum(axis=0)
    col_sums[col_sums == 0] = 1
    matrix = cooccur / col_sums
    scores = np.ones(n) / n
    for _ in range(iterations):
        scores = (1 - damping) / n + damping * matrix @ scores
    inv_vocab = {v: k for k, v in vocab.items()}
    result: dict[str, float] = {inv_vocab[idx]: round(float(scores[idx]), 6) for idx in range(n)}
    sorted_terms = sorted(result.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_terms[:max_terms])


def merge_scores(
    tfidf_scores: dict[str, float],
    textrank_scores: dict[str, float],
    alpha: float = 0.6,
) -> dict[str, float]:
    all_terms = set(tfidf_scores) | set(textrank_scores)
    if not all_terms:
        return {}

    def norm(d: dict[str, float]) -> dict[str, float]:
        if not d:
            return {}
        mx = max(d.values()) or 1.0
        return {k: v / mx for k, v in d.items()}

    n_tfidf = norm(tfidf_scores)
    n_tr = norm(textrank_scores)
    merged: dict[str, float] = {}
    for term in all_terms:
        merged[term] = round(alpha * n_tfidf.get(term, 0) + (1 - alpha) * n_tr.get(term, 0), 4)
    return dict(sorted(merged.items(), key=lambda x: x[1], reverse=True))

