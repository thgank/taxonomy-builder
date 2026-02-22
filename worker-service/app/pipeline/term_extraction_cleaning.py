from __future__ import annotations

import re
from typing import Any

from app.pipeline.term_extraction_constants import (
    BAD_SINGLE_TOKENS,
    BAD_TERM_PHRASES,
    FUNCTIONAL_TERMS_EN,
    FUNCTIONAL_TERMS_KK,
    FUNCTIONAL_TERMS_RU,
    GENERIC_TERMS,
    KK_PARTICIPLE_SUFFIXES,
    KK_VERBAL_TAILS,
    NOISE_TERM_PATTERNS,
    SPLIT_CONNECTORS,
    STOPWORDS,
    TOKEN_RE,
    UNIT_OR_TECH_TOKENS,
)


def compile_term_pattern(term: str) -> re.Pattern:
    return re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE | re.UNICODE)


def is_noise_token(token: str) -> bool:
    t = token.lower().strip()
    if not t or len(t) <= 1:
        return True
    if t in STOPWORDS or t in GENERIC_TERMS or t in UNIT_OR_TECH_TOKENS:
        return True
    if any(ch.isdigit() for ch in t):
        alpha = "".join(ch for ch in t if ch.isalpha())
        if len(alpha) < 3:
            return True
    if re.match(r"^\d+$", t):
        return True
    return False


def is_noise_term(term: str, nlp_model: Any = None) -> bool:
    t = term.lower().strip()
    if not t or len(t) < 2:
        return True
    if t in BAD_TERM_PHRASES or any(phrase in t for phrase in BAD_TERM_PHRASES if " " in phrase):
        return True
    for pat in NOISE_TERM_PATTERNS:
        if pat.match(t):
            return True
    tokens = [x.lower() for x in TOKEN_RE.findall(t)]
    if not tokens or len(tokens) > 6:
        return True
    noise_count = sum(1 for tok in tokens if is_noise_token(tok))
    if len(tokens) == 1 and noise_count == 1:
        return True
    if noise_count == len(tokens) or (len(tokens) <= 2 and noise_count >= len(tokens)):
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


def functional_terms_for_lang(lang: str) -> set[str]:
    l = (lang or "").lower()[:2]
    if l == "ru":
        return FUNCTIONAL_TERMS_RU
    if l == "kk":
        return FUNCTIONAL_TERMS_KK
    return FUNCTIONAL_TERMS_EN


def is_functional_phrase(term: str, lang: str, nlp_model: Any = None) -> bool:
    tokens = [t.lower() for t in TOKEN_RE.findall(term)]
    if not tokens:
        return True
    functional_terms = functional_terms_for_lang(lang)
    if len(tokens) == 1 and tokens[0] in functional_terms:
        return True
    func_hits = sum(1 for t in tokens if t in functional_terms or t in STOPWORDS)
    if len(tokens) >= 2 and (func_hits / len(tokens)) >= 0.6:
        return True
    if len(tokens) >= 2 and (tokens[0] in functional_terms or tokens[-1] in functional_terms):
        return True
    if nlp_model:
        try:
            doc = nlp_model(term)
            useful = [t for t in doc if not t.is_punct and not t.is_space]
            if useful:
                noun_like = sum(1 for t in useful if t.pos_ in {"NOUN", "PROPN", "ADJ"})
                func_like = sum(1 for t in useful if t.pos_ in {"VERB", "AUX", "ADP", "SCONJ", "CCONJ", "ADV"})
                if len(useful) >= 2 and (noun_like == 0 or func_like > noun_like):
                    return True
        except Exception:
            pass
    if (lang or "").lower()[:2] == "kk":
        if len(tokens) <= 3 and tokens[-1] in KK_VERBAL_TAILS:
            return True
        if any(tok.endswith(KK_PARTICIPLE_SUFFIXES) for tok in tokens) and len(tokens) <= 3:
            return True
    return False


def normalize_term(term: str, nlp_model: Any = None) -> str | None:
    term = term.strip().lower()
    if len(term) < 2 or re.match(r"^\d+$", term):
        return None
    tokens = [t.lower() for t in TOKEN_RE.findall(term)]
    if not tokens:
        return None
    if len(tokens) == 1 and tokens[0] in STOPWORDS:
        return None
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
    if is_noise_term(term, nlp_model):
        return None
    return term

