"""
Term Extraction worker
──────────────────────
Two methods:
  1. TF-IDF on noun phrases / n-grams
  2. TextRank (graph-based keyword extraction)

Results: concepts + concept_occurrences stored in DB.
"""
from __future__ import annotations

import re
import uuid
import math
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.config import config
from app.db import Document, DocumentChunk, Concept, ConceptOccurrence
from app.job_helper import (
    update_job_status, add_job_event, is_job_cancelled,
)
from app.logger import get_logger

log = get_logger(__name__)

# ── spaCy lazy load ──────────────────────────────────────

_nlp_models: dict[str, Any] = {}


def _load_spacy(lang: str) -> Any:
    if lang not in _nlp_models:
        import spacy
        name = {
            "en": config.spacy_model_en,
            "ru": config.spacy_model_ru,
            "kk": config.spacy_model_kk,
        }.get(lang)
        if name:
            try:
                _nlp_models[lang] = spacy.load(name)
            except OSError:
                _nlp_models[lang] = None
        else:
            _nlp_models[lang] = None
    return _nlp_models.get(lang)


# ── Stopwords (minimal) ─────────────────────────────────

STOP_EN = set("the a an is are was were be been being have has had do does did will would shall "
              "should may might can could of in to for on with at by from as into about between "
              "through during before after above below and or but not no nor so if then that this "
              "these those it its he she they we you i my your his her our their me him us them".split())

STOP_RU = set("и в не на с что как по это он она они мы вы я а но за то все его её их этот эта "
              "эти из к у так уже от при бы до который когда только или тоже ещё более".split())
STOP_KK = set(
    "және мен бұл сол үшін бойынша сияқты өте бар жоқ емес болып туралы қажет негізгі "
    "арқылы бірге дейін кейін немесе әрі тағы бірақ да де дерек мәлімет жүйе деңгей"
    .split()
)

STOPWORDS = STOP_EN | STOP_RU | STOP_KK
GENERIC_TERMS = {
    "such", "type", "kind", "form", "sort", "other", "common", "include",
    "includes", "used", "provide", "provides", "process", "term", "service",
    "services", "product", "products",
    "түр", "нысан", "санат", "жалпы", "негізгі", "мысал", "қызмет",
    "услуга", "пример", "форма", "категория", "процесс",
}
SPLIT_CONNECTORS = {"and", "or", "и", "или", "және", "немесе"}
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
UNIT_OR_TECH_TOKENS = {
    "kw", "mw", "gw", "kwh", "mwh", "gwh", "twh",
    "wh", "ah", "mah", "cm", "cm2", "cm3", "mm", "kv", "hz",
    "kg", "mg", "lb", "doi", "isbn", "issn", "pmid",
    "bmatrix", "latex", "fig", "table", "et", "al",
}
BAD_SINGLE_TOKENS = {
    "use", "used", "using", "include", "includes", "including", "provide",
    "provides", "allow", "allows", "make", "makes", "show", "shows",
    "occur", "occurs", "work", "works", "begin", "end",
    "also", "which", "usually", "many", "significant", "typically", "over",
    "major", "mostly", "often", "much", "several", "various",
    "high", "low", "new", "old", "good", "bad", "large", "small", "different",
    "same", "general", "specific", "important", "common", "main", "basic",
    "certain", "other", "another", "more", "less", "most", "least", "than",
    "түр", "нысан", "санат", "жалпы", "негізгі", "мысал", "қызмет",
    "бұл", "сол", "яғни", "демек", "также", "пример", "процесс", "категория",
}
BAD_TERM_PHRASES = {
    "том числе",
    "в том числе",
    "составляет около",
    "около",
    "включая",
    "соның ішінде",
    "кез келген",
    "атап айтқанда",
    "үшін",
    "арқылы",
}
NOISE_TERM_PATTERNS = [
    re.compile(r"^(?:doi|isbn|issn|pmid)\b", re.IGNORECASE),
    re.compile(r"^[a-z]{1,2}\d+[a-z0-9]*$", re.IGNORECASE),
    re.compile(r"^\d+[a-z]{1,3}$", re.IGNORECASE),
    re.compile(r".*\b(?:bmatrix|latex|arxiv)\b.*", re.IGNORECASE),
]


def _compile_term_pattern(term: str) -> re.Pattern:
    # Token boundary guard to avoid partial substring hits.
    return re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE | re.UNICODE)


def _is_noise_token(token: str) -> bool:
    t = token.lower().strip()
    if not t:
        return True
    if len(t) <= 1:
        return True
    if t in STOPWORDS or t in GENERIC_TERMS:
        return True
    if t in UNIT_OR_TECH_TOKENS:
        return True
    if any(ch.isdigit() for ch in t):
        # keep only if token has meaningful alpha payload (e.g. 3phase -> reject)
        alpha = "".join(ch for ch in t if ch.isalpha())
        if len(alpha) < 3:
            return True
    if re.match(r"^\d+$", t):
        return True
    return False


def _is_noise_term(term: str, nlp_model: Any = None) -> bool:
    t = term.lower().strip()
    if not t or len(t) < 2:
        return True
    if t in BAD_TERM_PHRASES:
        return True
    if any(phrase in t for phrase in BAD_TERM_PHRASES if " " in phrase):
        return True
    for pat in NOISE_TERM_PATTERNS:
        if pat.match(t):
            return True
    tokens = [x.lower() for x in TOKEN_RE.findall(t)]
    if not tokens:
        return True
    if len(tokens) > 6:
        return True
    noise_count = sum(1 for tok in tokens if _is_noise_token(tok))
    if len(tokens) == 1 and noise_count == 1:
        return True
    if noise_count == len(tokens):
        return True
    if len(tokens) <= 2 and noise_count >= len(tokens):
        return True
    meaningful_count = len(tokens) - noise_count
    if len(tokens) >= 2 and meaningful_count < 2:
        return True
    if len(tokens) == 1 and tokens[0] in BAD_SINGLE_TOKENS:
        return True
    if len(tokens) >= 2 and tokens[0] == tokens[-1]:
        return True
    if nlp_model and len(tokens) == 1:
        try:
            doc = nlp_model(tokens[0])
            if doc and doc[0].pos_ in {"VERB", "AUX", "ADV", "ADP", "PRON", "DET"}:
                return True
        except Exception:
            pass
    return False


# ── Normalization ────────────────────────────────────────

def normalize_term(term: str, nlp_model: Any = None) -> str | None:
    """Normalize: lowercase → lemmatize → filter junk."""
    term = term.strip().lower()
    # remove tokens < 2 chars total
    if len(term) < 2:
        return None
    # remove purely numeric
    if re.match(r"^\d+$", term):
        return None
    # stopword single-token filter
    tokens = [t.lower() for t in TOKEN_RE.findall(term)]
    if not tokens:
        return None
    if len(tokens) == 1 and tokens[0] in STOPWORDS:
        return None
    # lemmatize with spaCy if available
    if nlp_model:
        doc = nlp_model(term)
        lemmas = [t.lemma_ for t in doc if not t.is_punct and not t.is_space]
        if lemmas:
            term = " ".join(lemmas).strip().lower()
    term = re.sub(r"\s+", " ", term).strip()
    if not term or len(term) < 2:
        return None
    if term in BAD_TERM_PHRASES:
        return None
    tokens = [t.lower() for t in TOKEN_RE.findall(term)]
    if len(tokens) == 1 and tokens[0] in GENERIC_TERMS:
        return None
    if len(tokens) > 1:
        tokens = [t for t in tokens if t not in GENERIC_TERMS and t not in SPLIT_CONNECTORS]
        if not tokens:
            return None
        term = " ".join(tokens).strip()
    if len(tokens) > 4:
        return None
    if len(tokens) == 1 and tokens[0] in STOPWORDS:
        return None
    if not term or len(term) < 2:
        return None
    if _is_noise_term(term, nlp_model):
        return None
    return term


# ── Method 1: TF-IDF on n-grams ─────────────────────────

def _split_phrase(phrase: str) -> list[str]:
    parts = re.split(
        r"\s*(?:,|;|/|\band\b|\bor\b|\bи\b|\bили\b|\bжәне\b|\bнемесе\b)\s*",
        phrase.strip(),
        flags=re.IGNORECASE,
    )
    return [p.strip() for p in parts if len(p.strip()) >= 2]


def _is_allowed_np(span: Any) -> bool:
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
    """Extract noun phrases using spaCy."""
    doc = nlp_model(text[:100_000])  # limit to avoid OOM
    phrases = []
    for np in doc.noun_chunks:
        if not _is_allowed_np(np):
            continue
        clean = np.text.strip()
        for part in _split_phrase(clean):
            phrases.append(part)
    # also single nouns
    for token in doc:
        if token.pos_ in ("NOUN", "PROPN") and len(token.text) > 2:
            phrases.append(token.text)
    return phrases


def extract_ngrams(text: str, ns: tuple[int, ...] = (1, 2)) -> list[str]:
    """Fallback: extract n-grams from tokens."""
    tokens = [t.lower() for t in TOKEN_RE.findall(text) if len(t) >= 2]
    tokens = [t for t in tokens if not _is_noise_token(t)]
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
    """
    TF-IDF scoring of candidate terms across chunks.
    Returns {normalized_term: score}.
    """
    # term → doc_ids (for IDF)
    term_doc_map: dict[str, set] = defaultdict(set)
    # term → total count (for TF)
    term_count: Counter = Counter()

    for chunk in chunks:
        if nlp_model:
            candidates = extract_noun_phrases_spacy(chunk.text, nlp_model)
        else:
            candidates = extract_ngrams(chunk.text)

        seen_in_chunk: set[str] = set()
        for raw in candidates:
            norm = normalize_term(raw, nlp_model)
            if not norm:
                continue
            term_count[norm] += 1
            if norm not in seen_in_chunk:
                term_doc_map[norm].add(str(chunk.document_id))
                seen_in_chunk.add(norm)

    # Filter by min frequency
    num_docs = len(set(str(c.document_id) for c in chunks))
    if num_docs == 0:
        num_docs = 1

    scores: dict[str, float] = {}
    for term, count in term_count.items():
        if count < min_freq:
            continue
        if len(term_doc_map[term]) < min_doc_freq:
            continue
        tf = math.log1p(count)
        idf = math.log1p(num_docs / len(term_doc_map[term]))
        scores[term] = round(tf * idf, 4)

    # Sort and limit
    sorted_terms = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_terms[:max_terms])


# ── Method 2: TextRank ───────────────────────────────────

def textrank_extract(
    chunks: list[DocumentChunk],
    nlp_model: Any,
    max_terms: int,
    window: int = 4,
    iterations: int = 30,
    damping: float = 0.85,
) -> dict[str, float]:
    """
    Simple TextRank for keyword extraction.
    Builds co-occurrence graph over candidate tokens, runs PageRank.
    """
    import numpy as np

    # Collect all candidate tokens
    all_tokens: list[list[str]] = []
    for chunk in chunks:
        text = chunk.text.lower()
        tokens = [t for t in TOKEN_RE.findall(text) if len(t) >= 2]
        tokens = [t for t in tokens if not _is_noise_token(t)]
        if nlp_model:
            doc = nlp_model(chunk.text[:50_000])
            tokens = [
                t.lemma_.lower()
                for t in doc
                if t.pos_ in ("NOUN", "PROPN", "ADJ") and len(t.text) > 2
            ]
            tokens = [t for t in tokens if not _is_noise_token(t)]
        all_tokens.append(tokens)

    # Build vocabulary
    vocab: dict[str, int] = {}
    for tokens in all_tokens:
        for t in tokens:
            if t not in vocab:
                vocab[t] = len(vocab)

    n = len(vocab)
    if n == 0:
        return {}

    # Build co-occurrence matrix
    cooccur = np.zeros((n, n), dtype=np.float32)
    for tokens in all_tokens:
        for i, t1 in enumerate(tokens):
            for j in range(i + 1, min(i + window + 1, len(tokens))):
                t2 = tokens[j]
                if t1 in vocab and t2 in vocab:
                    idx1, idx2 = vocab[t1], vocab[t2]
                    cooccur[idx1][idx2] += 1
                    cooccur[idx2][idx1] += 1

    # Normalize columns
    col_sums = cooccur.sum(axis=0)
    col_sums[col_sums == 0] = 1
    matrix = cooccur / col_sums

    # PageRank iteration
    scores = np.ones(n) / n
    for _ in range(iterations):
        scores = (1 - damping) / n + damping * matrix @ scores

    # Map back
    inv_vocab = {v: k for k, v in vocab.items()}
    result: dict[str, float] = {}
    for idx in range(n):
        term = inv_vocab[idx]
        result[term] = round(float(scores[idx]), 6)

    sorted_terms = sorted(result.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_terms[:max_terms])


# ── Merge results from both methods ──────────────────────

def merge_scores(
    tfidf_scores: dict[str, float],
    textrank_scores: dict[str, float],
    alpha: float = 0.6,  # weight for TF-IDF
) -> dict[str, float]:
    """Combine TF-IDF and TextRank scores with normalization."""
    all_terms = set(tfidf_scores) | set(textrank_scores)
    if not all_terms:
        return {}

    # Normalize to [0, 1]
    def norm(d: dict[str, float]) -> dict[str, float]:
        if not d:
            return {}
        mx = max(d.values()) or 1.0
        return {k: v / mx for k, v in d.items()}

    n_tfidf = norm(tfidf_scores)
    n_tr = norm(textrank_scores)

    merged: dict[str, float] = {}
    for term in all_terms:
        s = alpha * n_tfidf.get(term, 0) + (1 - alpha) * n_tr.get(term, 0)
        merged[term] = round(s, 4)

    return dict(sorted(merged.items(), key=lambda x: x[1], reverse=True))


def _normalize_score_map(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    vals = list(scores.values())
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return {k: 1.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


def _compute_token_freq(chunks: list[DocumentChunk]) -> Counter:
    cnt = Counter()
    for chunk in chunks:
        toks = [t.lower() for t in TOKEN_RE.findall(chunk.text)]
        toks = [t for t in toks if t not in STOPWORDS and len(t) > 1]
        cnt.update(toks)
    return cnt


def _compute_term_freq(terms: list[str], chunks: list[DocumentChunk]) -> Counter:
    freq = Counter()
    patterns = {t: _compile_term_pattern(t) for t in terms}
    for chunk in chunks:
        text = chunk.text
        for t, pat in patterns.items():
            hits = len(pat.findall(text))
            if hits > 0:
                freq[t] += hits
    return freq


def _compute_term_doc_freq(terms: list[str], chunks: list[DocumentChunk]) -> dict[str, int]:
    doc_sets: dict[str, set[str]] = {t: set() for t in terms}
    patterns = {t: _compile_term_pattern(t) for t in terms}
    for chunk in chunks:
        text = chunk.text
        doc_id = str(chunk.document_id)
        for t, pat in patterns.items():
            if pat.search(text):
                doc_sets[t].add(doc_id)
    return {t: len(ids) for t, ids in doc_sets.items()}


def _suppress_subsumed_single_tokens(
    scores: dict[str, float],
    term_doc_freq: dict[str, int],
) -> dict[str, float]:
    """Drop generic single-token terms if a stronger multi-token parent phrase exists."""
    if not scores:
        return {}
    multi_terms = [t for t in scores.keys() if len(t.split()) >= 2]
    if not multi_terms:
        return scores
    out = dict(scores)
    for term in list(out.keys()):
        toks = [t.lower() for t in TOKEN_RE.findall(term)]
        if len(toks) != 1:
            continue
        tok = toks[0]
        df = int(term_doc_freq.get(term, 0))
        if len(tok) < 4 or tok in GENERIC_TERMS or tok in BAD_SINGLE_TOKENS:
            out.pop(term, None)
            continue
        # Keep strongly-supported single terms, suppress weak ones.
        if df >= 4:
            continue
        for mt in multi_terms:
            mt_toks = [t.lower() for t in TOKEN_RE.findall(mt)]
            if tok not in mt_toks:
                continue
            if int(term_doc_freq.get(mt, 0)) >= max(2, df):
                out.pop(term, None)
                break
    return out


def _candidate_quality_score(
    term: str,
    base_norm_score: float,
    doc_freq: int,
    total_docs: int,
) -> float:
    tokens = [t.lower() for t in TOKEN_RE.findall(term)]
    if not tokens:
        return 0.0
    df_ratio = doc_freq / max(1, total_docs)
    df_component = min(1.0, df_ratio / 0.6)  # reward terms seen in >=60% docs
    phrase_bonus = 1.0 if len(tokens) >= 2 else 0.35
    shape_penalty = 1.0
    if any(ch.isdigit() for ch in term):
        shape_penalty -= 0.25
    if len(tokens) == 1 and len(tokens[0]) <= 3:
        shape_penalty -= 0.25
    if len(tokens) > 4:
        shape_penalty -= 0.30
    score = (0.55 * base_norm_score) + (0.30 * df_component) + (0.15 * phrase_bonus)
    return max(0.0, min(1.0, score * shape_penalty))


def _compute_cvalue_scores(terms: list[str], term_freq: Counter) -> dict[str, float]:
    containing_map: dict[str, list[str]] = defaultdict(list)
    for t in terms:
        t_space = f" {t} "
        for longer in terms:
            if longer == t or len(longer) <= len(t):
                continue
            if t_space in f" {longer} ":
                containing_map[t].append(longer)

    cvals: dict[str, float] = {}
    for t in terms:
        words = t.split()
        length_weight = math.log2(1 + len(words))
        ft = float(term_freq.get(t, 0))
        containing = containing_map.get(t, [])
        if containing:
            avg_longer = sum(term_freq.get(x, 0) for x in containing) / max(1, len(containing))
            base = max(0.0, ft - avg_longer)
        else:
            base = ft
        cvals[t] = round(length_weight * base, 6)
    return cvals


def _compute_pmi_scores(terms: list[str], token_freq: Counter) -> dict[str, float]:
    total = float(sum(token_freq.values()) or 1.0)
    pmis: dict[str, float] = {}
    for t in terms:
        toks = t.split()
        if len(toks) < 2:
            pmis[t] = 0.0
            continue
        # proxy term probability: min token probability
        p_term = min((token_freq.get(tok, 0) / total) for tok in toks)
        p_prod = 1.0
        for tok in toks:
            p_prod *= max(token_freq.get(tok, 0) / total, 1e-12)
        pmi = math.log((p_term + 1e-12) / (p_prod + 1e-12))
        pmis[t] = round(max(0.0, pmi), 6)
    return pmis


def refine_term_scores(base_scores: dict[str, float], chunks: list[DocumentChunk]) -> dict[str, float]:
    """Re-rank terms using C-value/PMI to improve concept quality."""
    if not base_scores:
        return {}
    terms = list(base_scores.keys())
    term_freq = _compute_term_freq(terms, chunks)
    token_freq = _compute_token_freq(chunks)
    cvals = _compute_cvalue_scores(terms, term_freq)
    pmis = _compute_pmi_scores(terms, token_freq)

    n_base = _normalize_score_map(base_scores)
    n_cval = _normalize_score_map(cvals)
    n_pmi = _normalize_score_map(pmis)

    refined: dict[str, float] = {}
    for t in terms:
        words = t.split()
        if len(words) >= 2:
            score = (0.55 * n_base.get(t, 0.0)) + (0.30 * n_cval.get(t, 0.0)) + (0.15 * n_pmi.get(t, 0.0))
        else:
            score = (0.80 * n_base.get(t, 0.0)) + (0.20 * n_cval.get(t, 0.0))
        refined[t] = round(score, 6)
    return dict(sorted(refined.items(), key=lambda x: x[1], reverse=True))


# ── Deduplication with fuzzy matching ────────────────────

def deduplicate_terms(
    terms: dict[str, float],
    threshold: int | None = None,
) -> dict[str, float]:
    """Merge near-duplicate terms using rapidfuzz."""
    if threshold is None:
        threshold = config.fuzz_threshold

    from rapidfuzz import fuzz

    canonical_scores: dict[str, float] = {}
    surface_lists: dict[str, list[str]] = {}

    sorted_terms = sorted(terms.items(), key=lambda x: x[1], reverse=True)

    for term, score in sorted_terms:
        matched = False
        for canon in list(canonical_scores.keys()):
            if fuzz.ratio(term, canon) >= threshold:
                # Merge into existing canonical (keep higher-scored one)
                surface_lists[canon].append(term)
                if score > canonical_scores[canon]:
                    canonical_scores[canon] = score
                matched = True
                break
        if not matched:
            canonical_scores[term] = score
            surface_lists[term] = [term]

    return canonical_scores, surface_lists


# ── Occurrence extraction ────────────────────────────────

def find_occurrences(
    term: str,
    chunks: list[DocumentChunk],
    max_per_term: int = 20,
) -> list[dict]:
    """Find sentence-bounded snippets where term appears in chunks."""
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

    occurrences = []
    pattern = _compile_term_pattern(term)

    for chunk in chunks:
        for match in pattern.finditer(chunk.text):
            s_start, s_end = sentence_bounds(chunk.text, match.start())
            start = max(0, min(match.start(), s_start))
            end = min(len(chunk.text), max(match.end(), s_end))
            snippet = re.sub(r"\s+", " ", chunk.text[start:end]).strip()
            if not snippet:
                continue
            occurrences.append({
                "chunk_id": str(chunk.id),
                "snippet": snippet,
                "start_offset": match.start(),
                "end_offset": match.end(),
                "confidence": occurrence_confidence(term, snippet),
            })
            if len(occurrences) >= max_per_term:
                return occurrences
    return occurrences


# ── Handler ──────────────────────────────────────────────

def handle_terms(session: Session, msg: dict) -> None:
    """Term extraction handler."""
    job_id = str(msg.get("jobId") or msg.get("job_id"))
    collection_id = str(msg.get("collectionId") or msg.get("collection_id"))
    params = msg.get("params", {})

    update_job_status(session, job_id, "RUNNING", progress=0)
    add_job_event(session, job_id, "INFO", "Term extraction started")

    max_terms = int(params.get("max_terms", config.max_terms))
    min_freq = int(params.get("min_freq", config.min_term_freq))
    min_doc_freq = int(params.get("min_doc_freq", config.min_doc_freq))
    min_quality_score = float(
        params.get("min_term_quality_score", config.min_term_quality_score)
    )
    method = params.get("method_term_extraction", "both")

    # Get all chunks for collection
    docs = (
        session.query(Document)
        .filter(Document.collection_id == collection_id, Document.status == "PARSED")
        .all()
    )
    doc_ids = [str(d.id) for d in docs]
    chunks = (
        session.query(DocumentChunk)
        .filter(DocumentChunk.document_id.in_(doc_ids))
        .order_by(DocumentChunk.chunk_index)
        .all()
    )

    if not chunks:
        add_job_event(session, job_id, "WARN", "No chunks found for term extraction")
        update_job_status(session, job_id, "RUNNING", progress=100)
        return

    # Extract per language to avoid collapsing mixed collections into one language.
    chunks_by_lang: dict[str, list[DocumentChunk]] = defaultdict(list)
    for c in chunks:
        lang = (c.lang or config.default_language or "en").lower()[:2]
        chunks_by_lang[lang].append(c)
    dominant_lang = Counter({k: len(v) for k, v in chunks_by_lang.items()}).most_common(1)[0][0]
    add_job_event(
        session,
        job_id,
        "INFO",
        f"Chunk language split: { {k: len(v) for k, v in chunks_by_lang.items()} }",
    )
    update_job_status(session, job_id, "RUNNING", progress=10)

    # Extract terms per language bucket, then merge.
    tfidf_scores: dict[str, float] = {}
    textrank_scores: dict[str, float] = {}
    term_lang_scores: dict[str, tuple[str, float]] = {}

    for lang, lang_chunks in chunks_by_lang.items():
        nlp_model = _load_spacy(lang)
        if method in ("tfidf", "both"):
            lang_scores = tfidf_extract(
                lang_chunks, nlp_model, max_terms * 2, min_freq, min_doc_freq
            )
            for term, score in lang_scores.items():
                if score > tfidf_scores.get(term, 0.0):
                    tfidf_scores[term] = score
                prev = term_lang_scores.get(term)
                if prev is None or score > prev[1]:
                    term_lang_scores[term] = (lang, float(score))
        if method in ("textrank", "both"):
            lang_scores = textrank_extract(lang_chunks, nlp_model, max_terms * 2)
            for term, score in lang_scores.items():
                if score > textrank_scores.get(term, 0.0):
                    textrank_scores[term] = score
                prev = term_lang_scores.get(term)
                if prev is None or score > prev[1]:
                    term_lang_scores[term] = (lang, float(score))

    if method in ("tfidf", "both"):
        add_job_event(session, job_id, "INFO",
                      f"TF-IDF extracted {len(tfidf_scores)} candidates")
    update_job_status(session, job_id, "RUNNING", progress=30)

    if method in ("textrank", "both"):
        add_job_event(session, job_id, "INFO",
                      f"TextRank extracted {len(textrank_scores)} candidates")

    update_job_status(session, job_id, "RUNNING", progress=50)

    # Merge
    if method == "both":
        final_scores = merge_scores(tfidf_scores, textrank_scores)
    elif method == "tfidf":
        final_scores = tfidf_scores
    else:
        final_scores = textrank_scores

    # Deduplicate
    deduped_scores, surface_map = deduplicate_terms(final_scores)
    deduped_scores = refine_term_scores(deduped_scores, chunks)
    deduped_scores = {
        term: score
        for term, score in deduped_scores.items()
        if not _is_noise_term(
            term,
            _load_spacy(term_lang_scores.get(term, (dominant_lang, 0.0))[0]),
        )
    }
    total_docs = max(1, len({str(c.document_id) for c in chunks}))
    term_doc_freq = _compute_term_doc_freq(list(deduped_scores.keys()), chunks)
    norm_refined = _normalize_score_map(deduped_scores)
    quality_filtered: dict[str, float] = {}
    deduped_scores = _suppress_subsumed_single_tokens(deduped_scores, term_doc_freq)
    single_token_extra = 0.17
    for term, score in deduped_scores.items():
        df = int(term_doc_freq.get(term, 0))
        if df < min_doc_freq:
            continue
        toks = [t.lower() for t in TOKEN_RE.findall(term)]
        if not toks:
            continue
        if len(toks) == 1:
            if len(toks[0]) < 4:
                continue
            if toks[0] in BAD_SINGLE_TOKENS or _is_noise_token(toks[0]):
                continue
        q_score = _candidate_quality_score(
            term,
            base_norm_score=float(norm_refined.get(term, 0.0)),
            doc_freq=df,
            total_docs=total_docs,
        )
        dynamic_threshold = min_quality_score + (single_token_extra if len(toks) == 1 else 0.0)
        if q_score < dynamic_threshold:
            continue
        quality_filtered[term] = score
    deduped_scores = quality_filtered
    surface_map = {
        term: forms
        for term, forms in surface_map.items()
        if term in deduped_scores
    }
    term_lang_map = {
        term: term_lang_scores.get(term, (dominant_lang, 0.0))[0]
        for term in deduped_scores
    }

    # Limit
    top_terms = dict(list(deduped_scores.items())[:max_terms])

    add_job_event(session, job_id, "INFO",
                  f"After dedup: {len(top_terms)} terms "
                  f"(min_doc_freq={min_doc_freq}, min_quality_score={min_quality_score:.2f})")
    update_job_status(session, job_id, "RUNNING", progress=60)

    # Delete existing concepts for idempotency
    existing = session.query(Concept).filter(
        Concept.collection_id == collection_id
    ).all()
    for c in existing:
        session.query(ConceptOccurrence).filter(
            ConceptOccurrence.concept_id == c.id
        ).delete()
    session.query(Concept).filter(
        Concept.collection_id == collection_id
    ).delete()
    session.commit()

    # Store concepts + occurrences
    stored = 0
    for term, score in top_terms.items():
        if is_job_cancelled(session, job_id):
            return

        concept = Concept(
            id=uuid.uuid4(),
            collection_id=collection_id,
            canonical=term,
            surface_forms=surface_map.get(term, [term]),
            lang=term_lang_map.get(term, dominant_lang),
            score=score,
        )
        session.add(concept)
        session.flush()

        # Find occurrences
        term_lang = concept.lang or dominant_lang
        lang_chunks = chunks_by_lang.get(term_lang[:2], chunks)
        occs = find_occurrences(term, lang_chunks)
        if not occs:
            occs = find_occurrences(term, chunks)
        for occ in occs:
            occurrence = ConceptOccurrence(
                id=uuid.uuid4(),
                concept_id=concept.id,
                chunk_id=occ["chunk_id"],
                snippet=occ["snippet"],
                start_offset=occ["start_offset"],
                end_offset=occ["end_offset"],
                confidence=occ["confidence"],
            )
            session.add(occurrence)

        stored += 1
        if stored % 50 == 0:
            session.commit()
            progress = 60 + int((stored / len(top_terms)) * 35)
            update_job_status(session, job_id, "RUNNING", progress=progress)

    session.commit()

    add_job_event(session, job_id, "INFO",
                  f"Term extraction complete: {stored} concepts stored")
    update_job_status(session, job_id, "RUNNING", progress=100)
    log.info("Term extraction complete for collection %s: %d concepts", collection_id, stored)
