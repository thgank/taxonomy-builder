from __future__ import annotations

import math
from collections import Counter, defaultdict

from app.config import config
from app.db import DocumentChunk
from app.pipeline.term_extraction_cleaning import compile_term_pattern
from app.pipeline.term_extraction_constants import BAD_SINGLE_TOKENS, GENERIC_TERMS, STOPWORDS, TOKEN_RE


def normalize_score_map(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    vals = list(scores.values())
    lo, hi = min(vals), max(vals)
    if hi <= lo:
        return {k: 1.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


def compute_token_freq(chunks: list[DocumentChunk]) -> Counter:
    cnt = Counter()
    for chunk in chunks:
        toks = [t.lower() for t in TOKEN_RE.findall(chunk.text)]
        toks = [t for t in toks if t not in STOPWORDS and len(t) > 1]
        cnt.update(toks)
    return cnt


def compute_term_freq(terms: list[str], chunks: list[DocumentChunk]) -> Counter:
    freq = Counter()
    patterns = {t: compile_term_pattern(t) for t in terms}
    for chunk in chunks:
        text = chunk.text
        for t, pat in patterns.items():
            hits = len(pat.findall(text))
            if hits > 0:
                freq[t] += hits
    return freq


def compute_term_doc_freq(terms: list[str], chunks: list[DocumentChunk]) -> dict[str, int]:
    doc_sets: dict[str, set[str]] = {t: set() for t in terms}
    patterns = {t: compile_term_pattern(t) for t in terms}
    for chunk in chunks:
        text = chunk.text
        doc_id = str(chunk.document_id)
        for t, pat in patterns.items():
            if pat.search(text):
                doc_sets[t].add(doc_id)
    return {t: len(ids) for t, ids in doc_sets.items()}


def suppress_subsumed_single_tokens(
    scores: dict[str, float],
    term_doc_freq: dict[str, int],
) -> dict[str, float]:
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


def candidate_quality_score(
    term: str,
    base_norm_score: float,
    doc_freq: int,
    total_docs: int,
) -> float:
    tokens = [t.lower() for t in TOKEN_RE.findall(term)]
    if not tokens:
        return 0.0
    df_ratio = doc_freq / max(1, total_docs)
    df_component = min(1.0, df_ratio / 0.6)
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


def compute_cvalue_scores(terms: list[str], term_freq: Counter) -> dict[str, float]:
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


def compute_pmi_scores(terms: list[str], token_freq: Counter) -> dict[str, float]:
    total = float(sum(token_freq.values()) or 1.0)
    pmis: dict[str, float] = {}
    for t in terms:
        toks = t.split()
        if len(toks) < 2:
            pmis[t] = 0.0
            continue
        p_term = min((token_freq.get(tok, 0) / total) for tok in toks)
        p_prod = 1.0
        for tok in toks:
            p_prod *= max(token_freq.get(tok, 0) / total, 1e-12)
        pmi = math.log((p_term + 1e-12) / (p_prod + 1e-12))
        pmis[t] = round(max(0.0, pmi), 6)
    return pmis


def refine_term_scores(base_scores: dict[str, float], chunks: list[DocumentChunk]) -> dict[str, float]:
    if not base_scores:
        return {}
    terms = list(base_scores.keys())
    term_freq = compute_term_freq(terms, chunks)
    token_freq = compute_token_freq(chunks)
    cvals = compute_cvalue_scores(terms, term_freq)
    pmis = compute_pmi_scores(terms, token_freq)
    n_base = normalize_score_map(base_scores)
    n_cval = normalize_score_map(cvals)
    n_pmi = normalize_score_map(pmis)
    refined: dict[str, float] = {}
    for t in terms:
        words = t.split()
        if len(words) >= 2:
            score = (0.55 * n_base.get(t, 0.0)) + (0.30 * n_cval.get(t, 0.0)) + (0.15 * n_pmi.get(t, 0.0))
        else:
            score = (0.80 * n_base.get(t, 0.0)) + (0.20 * n_cval.get(t, 0.0))
        refined[t] = round(score, 6)
    return dict(sorted(refined.items(), key=lambda x: x[1], reverse=True))


def deduplicate_terms(
    terms: dict[str, float],
    threshold: int | None = None,
) -> tuple[dict[str, float], dict[str, list[str]]]:
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
                surface_lists[canon].append(term)
                if score > canonical_scores[canon]:
                    canonical_scores[canon] = score
                matched = True
                break
        if not matched:
            canonical_scores[term] = score
            surface_lists[term] = [term]
    return canonical_scores, surface_lists

