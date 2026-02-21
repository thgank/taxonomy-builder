from __future__ import annotations

import re
from typing import Any
from difflib import SequenceMatcher

from app.config import config
from app.db import DocumentChunk

GENERIC_TERMS = {
    "such", "type", "kind", "form", "sort", "other", "common", "include",
    "includes", "used", "provide", "provides", "process", "term", "service",
    "services", "product", "products", "такой", "такие", "тип", "вид", "форма",
    "түр", "нысан", "санат", "жалпы", "негізгі", "қызмет", "процесс",
}
GENERIC_PARENT_TERMS = {
    "thing", "entity", "object", "item", "category", "class", "group",
    "set", "kind", "type",
    "түр", "санат", "топ",
}
BAD_PARENT_SINGLE_TOKENS = {
    "also", "which", "usually", "many", "significant", "typically", "over",
    "major", "mostly", "often", "much", "several", "various",
    "около", "примерно", "также", "том", "числе",
    "кез", "кезінде", "үшін", "арқылы", "және", "мен",
}
BAD_GENERIC_SINGLE_TOKENS = BAD_PARENT_SINGLE_TOKENS | {
    "high", "low", "new", "old", "good", "bad", "large", "small", "different",
    "same", "general", "specific", "important", "common", "main", "basic",
    "certain", "other", "another", "more", "less", "most", "least", "than",
    "түр", "санат", "негізгі", "жалпы", "қызмет", "мысал",
}
BAD_GENERIC_PHRASES = {
    "том числе",
    "в том числе",
    "составляет около",
    "около",
    "кез келген",
    "соның ішінде",
    "атап айтқанда",
}
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
TECH_NOISE_TOKENS = {
    "kw", "mw", "gw", "kwh", "mwh", "gwh", "twh",
    "ah", "mah", "cm", "cm2", "cm3", "mm", "kv", "hz",
    "mg", "kg", "doi", "isbn", "issn", "pmid",
    "bmatrix", "latex", "fig", "table",
}
NOISE_LABEL_PATTERNS = [
    re.compile(r"^(?:doi|isbn|issn|pmid)\b", re.IGNORECASE),
    re.compile(r"^[a-z]{1,2}\d+[a-z0-9]*$", re.IGNORECASE),
    re.compile(r"^\d+[a-z]{1,3}$", re.IGNORECASE),
    re.compile(r".*\b(?:bmatrix|latex|arxiv)\b.*", re.IGNORECASE),
]
_NLP_MODELS: dict[str, Any] = {}

HEARST_PATTERNS_EN = [
    (r"([\w\s]+?)\s+such\s+as\s+([\w\s,]+?)(?:\.|,\s*and\s|\s+and\s)", "hypernym", "hyponyms"),
    (r"([\w\s,]+?)\s+and\s+other\s+([\w\s]+?)(?:\.|,|;)", "hyponyms", "hypernym"),
    (r"([\w\s]+?)\s*,?\s*including\s+([\w\s,]+?)(?:\.|,\s*and\s|\s+and\s)", "hypernym", "hyponyms"),
    (r"([\w\s]+?)\s*,?\s*especially\s+([\w\s,]+?)(?:\.|,)", "hypernym", "hyponyms"),
    (r"([\w\s]+?)\s+is\s+a\s+(?:kind|type|form|sort)\s+of\s+([\w\s]+?)(?:\.|,)", "hyponym", "hypernym"),
]

HEARST_PATTERNS_RU = [
    (r"([\w\s]+?)\s*,?\s*такие?\s+как\s+([\w\s,]+?)(?:\.|,)", "hypernym", "hyponyms"),
    (r"([\w\s,]+?)\s+и\s+други[еих]\s+([\w\s]+?)(?:\.|,)", "hyponyms", "hypernym"),
    (r"([\w\s]+?)\s*,?\s*в\s+частности\s+([\w\s,]+?)(?:\.|,)", "hypernym", "hyponyms"),
    (r"([\w\s]+?)\s*,?\s*например\s+([\w\s,]+?)(?:\.|,)", "hypernym", "hyponyms"),
    (r"([\w\s]+?)\s+является\s+(?:видом|разновидностью|типом)\s+([\w\s]+?)(?:\.|,)", "hyponym", "hypernym"),
]

HEARST_PATTERNS_KK = [
    (r"([\w\s]+?)\s*,?\s*мысалы\s+([\w\s,]+?)(?:\.|,)", "hypernym", "hyponyms"),
    (r"([\w\s]+?)\s*,?\s*атап\s+айтқанда\s+([\w\s,]+?)(?:\.|,)", "hypernym", "hyponyms"),
    (r"([\w\s]+?)\s+сияқты\s+([\w\s,]+?)(?:\.|,)", "hypernym", "hyponyms"),
    (r"([\w\s]+?)\s+және\s+басқа\s+([\w\s]+?)(?:\.|,)", "hyponyms", "hypernym"),
    (r"([\w\s]+?)\s+([\w\s]+?)\s+түрі\s+болып\s+табылады(?:\.|,)", "hyponym", "hypernym"),
]


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def _load_spacy(lang: str) -> Any:
    if lang not in _NLP_MODELS:
        import spacy
        if lang.startswith("en"):
            model_name = config.spacy_model_en
        elif lang.startswith("ru"):
            model_name = config.spacy_model_ru
        else:
            model_name = config.spacy_model_kk or config.spacy_model_ru
        try:
            _NLP_MODELS[lang] = spacy.load(model_name)
        except Exception:
            _NLP_MODELS[lang] = None
    return _NLP_MODELS.get(lang)


def _token_overlap_ratio(a: str, b: str) -> float:
    at = set(tokenize(a))
    bt = set(tokenize(b))
    if not at or not bt:
        return 0.0
    return len(at & bt) / len(at | bt)


def _is_noun_phrase_candidate(
    text: str,
    nlp_model: Any,
    allow_single: bool = False,
) -> bool:
    toks = tokenize(text)
    if not toks:
        return False
    if len(toks) == 1:
        if not allow_single:
            return False
        if toks[0] in BAD_PARENT_SINGLE_TOKENS:
            return False
    if nlp_model is None:
        # Heuristic fallback when spaCy is unavailable.
        if len(toks) == 1:
            return len(toks[0]) >= 4 and toks[0] not in GENERIC_TERMS and toks[0] not in BAD_PARENT_SINGLE_TOKENS
        return True
    try:
        doc = nlp_model(text)
    except Exception:
        return True
    useful = [t for t in doc if not t.is_punct and not t.is_space]
    if not useful:
        return False
    if len(useful) == 1:
        if not allow_single:
            return False
        return useful[0].pos_ in {"NOUN", "PROPN"} and useful[0].lemma_.lower() not in BAD_PARENT_SINGLE_TOKENS
    if useful[-1].pos_ not in {"NOUN", "PROPN"}:
        return False
    return any(t.pos_ in {"NOUN", "PROPN"} for t in useful)


def normalize_candidate(text: str) -> str | None:
    text = re.sub(r"\s+", " ", text.strip().lower())
    text = re.sub(r"^[^\w]+|[^\w]+$", "", text, flags=re.UNICODE)
    if len(text) < 2:
        return None
    if text in BAD_GENERIC_PHRASES:
        return None
    tokens = tokenize(text)
    if not tokens:
        return None
    if len(tokens) == 1 and tokens[0] in GENERIC_TERMS:
        return None
    if len(tokens) > 1:
        tokens = [t for t in tokens if t not in GENERIC_TERMS]
    if not tokens:
        return None
    if len(tokens) == 1 and tokens[0] in GENERIC_TERMS:
        return None
    normalized = " ".join(tokens).strip()
    return normalized if len(normalized) >= 2 else None


def is_low_quality_label(label: str) -> bool:
    norm = normalize_candidate(label)
    if not norm:
        return True
    if norm in BAD_GENERIC_PHRASES:
        return True
    if any(phrase in norm for phrase in BAD_GENERIC_PHRASES if " " in phrase):
        return True
    if any(pat.match(norm) for pat in NOISE_LABEL_PATTERNS):
        return True
    toks = tokenize(norm)
    if not toks:
        return True
    if len(toks) > 4:
        return True
    if len(toks) >= 3 and len(set(toks)) < len(toks):
        return True
    if len(toks) == 1 and toks[0] in GENERIC_TERMS:
        return True
    if len(toks) == 1 and toks[0] in BAD_GENERIC_SINGLE_TOKENS:
        return True
    tech_count = sum(1 for t in toks if t in TECH_NOISE_TOKENS)
    if len(toks) == 1 and tech_count == 1:
        return True
    if tech_count == len(toks):
        return True
    if any(ch.isdigit() for ch in "".join(toks)):
        alpha_lens = [len("".join(ch for ch in t if ch.isalpha())) for t in toks]
        if len(toks) == 1 and alpha_lens[0] < 3:
            return True
    if len(toks) == 1 and len(toks[0]) <= 2:
        return True
    return False


def split_enumeration(text: str) -> list[str]:
    parts = re.split(r"\s*,\s*|\s+(?:and|or|и|или|және|немесе)\s+", text)
    cleaned = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        c = normalize_candidate(p)
        if c:
            cleaned.append(c)
    return cleaned


def find_closest_concept(text: str, concept_set: set[str]) -> str | None:
    text = normalize_candidate(text or "")
    if not text:
        return None
    text_tokens = set(tokenize(text))
    if not text_tokens:
        return None

    best_concept = None
    best_score = 0.0
    for concept in concept_set:
        c_norm = normalize_candidate(concept)
        if not c_norm:
            continue
        c_tokens = set(tokenize(c_norm))
        if not c_tokens:
            continue
        inter = len(text_tokens & c_tokens)
        union = len(text_tokens | c_tokens)
        score = inter / union if union else 0.0
        if score > best_score:
            best_score = score
            best_concept = concept

    if best_score >= 0.62:
        return best_concept

    if len(text) >= 5:
        text_tokens_len = max(1, len(text_tokens))
        candidates = []
        for c in concept_set:
            if len(c) < 5 or not (text in c or c in text):
                continue
            c_norm = normalize_candidate(c)
            if not c_norm:
                continue
            c_tokens = set(tokenize(c_norm))
            overlap = len(text_tokens & c_tokens) / text_tokens_len
            if overlap < 0.6:
                continue
            seq = SequenceMatcher(None, text, c_norm).ratio()
            if seq < 0.72:
                continue
            candidates.append((overlap + (0.35 * seq), c))
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
    return None


def extract_hearst_pairs(
    chunks: list[DocumentChunk],
    concept_set: set[str],
    lang: str = "en",
) -> list[dict[str, Any]]:
    if lang.startswith("en"):
        patterns = HEARST_PATTERNS_EN
    elif lang.startswith("ru"):
        patterns = HEARST_PATTERNS_RU
    else:
        patterns = HEARST_PATTERNS_KK
    nlp_model = _load_spacy(lang)
    pairs: list[dict[str, Any]] = []

    for chunk in chunks:
        text = chunk.text
        for pattern_str, group1_role, group2_role in patterns:
            for match in re.finditer(pattern_str, text, re.IGNORECASE):
                g1 = normalize_candidate(match.group(1))
                g2 = normalize_candidate(match.group(2))
                if not g1 or not g2:
                    continue

                if group1_role == "hypernym":
                    hypernym_raw = g1
                    hyponym_raws = split_enumeration(g2) if "hyponyms" in group2_role else [g2]
                elif group1_role == "hyponym":
                    hypernym_raw = g2
                    hyponym_raws = [g1]
                else:
                    hypernym_raw = g2
                    hyponym_raws = split_enumeration(g1)

                if not _is_noun_phrase_candidate(hypernym_raw, nlp_model, allow_single=False):
                    continue

                hypernym_clean = hypernym_raw
                hypernym_exact = hypernym_clean in concept_set
                if not hypernym_exact:
                    hypernym_match = find_closest_concept(hypernym_clean, concept_set)
                    if hypernym_match:
                        hypernym_clean = hypernym_match
                    else:
                        continue

                for hypo_raw in hyponym_raws:
                    hypo_clean = normalize_candidate(hypo_raw)
                    if not hypo_clean:
                        continue
                    if not _is_noun_phrase_candidate(hypo_clean, nlp_model, allow_single=True):
                        continue
                    hypo_exact = hypo_clean in concept_set
                    if not hypo_exact:
                        hypo_match = find_closest_concept(hypo_clean, concept_set)
                        if hypo_match:
                            hypo_clean = hypo_match
                        else:
                            continue

                    if hypernym_clean == hypo_clean:
                        continue
                    overlap = _token_overlap_ratio(hypernym_clean, hypo_clean)
                    if overlap < 0.2:
                        continue
                    if len(tokenize(hypernym_clean)) == 1 and len(tokenize(hypo_clean)) == 1:
                        continue

                    snippet_start = max(0, match.start() - 30)
                    snippet_end = min(len(text), match.end() + 30)
                    score = 0.6
                    score += 0.1 if hypernym_exact else 0.03
                    score += 0.1 if hypo_exact else 0.03
                    if len(hypo_clean.split()) >= 2:
                        score += 0.05
                    if not hypernym_exact or not hypo_exact:
                        score -= 0.06
                    score = min(score, 0.9)

                    pairs.append({
                        "hypernym": hypernym_clean,
                        "hyponym": hypo_clean,
                        "score": round(score, 4),
                        "evidence": {
                            "chunk_id": str(chunk.id),
                            "snippet": text[snippet_start:snippet_end],
                            "pattern": pattern_str[:50],
                            "method": "hearst",
                        },
                    })
    return pairs
