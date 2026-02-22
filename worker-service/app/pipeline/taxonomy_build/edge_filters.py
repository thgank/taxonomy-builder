from __future__ import annotations

import re
from collections import Counter

from app.config import config
from app.pipeline.taxonomy_build.edge_scoring import edge_method
from app.pipeline.taxonomy_text import is_low_quality_label

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
BAD_PARENT_SINGLE_TOKENS = {
    "also",
    "which",
    "usually",
    "many",
    "significant",
    "typically",
    "over",
    "major",
    "mostly",
    "often",
    "much",
    "several",
    "various",
    "about",
    "around",
    "including",
    "include",
    "among",
    "during",
    "том",
    "числе",
    "около",
    "примерно",
    "также",
    "кез",
    "кезінде",
    "үшін",
    "арқылы",
    "мен",
    "және",
    "немесе",
}
BAD_PARENT_PHRASES = {
    "том числе",
    "в том числе",
    "составляет около",
    "около",
    "кез келген",
    "соның ішінде",
}
VERBISH_SUFFIXES = (
    "ing",
    "ed",
    "ize",
    "ise",
    "ать",
    "ять",
    "ить",
    "еть",
    "ться",
    "ған",
    "ген",
    "атын",
    "етін",
    "ып",
    "іп",
)
FUNCTIONAL_PARENT_TOKENS = {
    "for",
    "to",
    "from",
    "between",
    "after",
    "before",
    "during",
    "which",
    "when",
    "while",
    "для",
    "между",
    "после",
    "до",
    "кроме",
    "того",
    "даже",
    "одна",
    "через",
    "үшін",
    "арқылы",
    "ретінде",
    "болып",
    "кезінде",
    "сияқты",
    "және",
    "мен",
}


def parent_validity_score(label: str, concept_doc_freq: dict[str, int]) -> float:
    norm = " ".join(TOKEN_RE.findall((label or "").lower())).strip()
    if not norm:
        return 0.0
    toks = norm.split()
    score = 1.0
    if norm in BAD_PARENT_PHRASES:
        return 0.0
    if any(phrase in norm for phrase in BAD_PARENT_PHRASES if " " in phrase):
        score -= 0.50
    functional_hits = sum(1 for t in toks if t in FUNCTIONAL_PARENT_TOKENS)
    if toks:
        score -= 0.45 * (functional_hits / len(toks))
    if len(toks) == 1:
        tok = toks[0]
        if tok in BAD_PARENT_SINGLE_TOKENS:
            score -= 0.70
        if len(tok) < 4:
            score -= 0.30
        if concept_doc_freq.get(label, 0) < config.min_parent_doc_freq:
            score -= 0.25
    if len(toks) <= 2 and all(any(tok.endswith(s) for s in VERBISH_SUFFIXES) for tok in toks):
        score -= 0.45
    if len(toks) > 5:
        score -= 0.25
    return max(0.0, min(1.0, score))


def is_valid_parent_label(label: str, concept_doc_freq: dict[str, int]) -> bool:
    norm = " ".join(TOKEN_RE.findall((label or "").lower())).strip()
    toks = norm.split()
    if not toks:
        return False
    if norm in BAD_PARENT_PHRASES:
        return False
    if any(phrase in norm for phrase in BAD_PARENT_PHRASES if " " in phrase):
        return False
    if len(toks) == 1:
        tok = toks[0]
        if tok in BAD_PARENT_SINGLE_TOKENS:
            return False
        if len(tok) < 4:
            return False
        if concept_doc_freq.get(label, 0) < config.min_parent_doc_freq:
            return False
    if len(toks) == 2 and any(t in BAD_PARENT_SINGLE_TOKENS for t in toks):
        return False
    if len(toks) <= 2 and all(any(tok.endswith(s) for s in VERBISH_SUFFIXES) for tok in toks):
        return False
    return True


def semantic_from_evidence(edge: dict) -> float:
    ev = edge.get("evidence", [])
    if isinstance(ev, dict):
        ev = [ev]
    best = 0.0
    for item in ev:
        if not isinstance(item, dict):
            continue
        sem = float(item.get("semantic_similarity", 0.0) or 0.0)
        lex = float(item.get("lexical_similarity", 0.0) or 0.0)
        sim = float(item.get("similarity", sem) or 0.0)
        cooc = float(item.get("cooccurrence_support", 0.0) or 0.0)
        best = max(best, (0.65 * sem) + (0.25 * lex) + (0.10 * cooc), (0.75 * sim) + (0.15 * lex) + (0.10 * cooc))
    return best


def evidence_max_value(edge: dict, key: str) -> float:
    ev = edge.get("evidence", [])
    if isinstance(ev, dict):
        ev = [ev]
    best = 0.0
    for item in ev:
        if not isinstance(item, dict):
            continue
        best = max(best, float(item.get(key, 0.0) or 0.0))
    return best


def edge_rejection_reason(
    edge: dict,
    concept_doc_freq: dict[str, int],
    min_score: float,
    recovery_mode: bool = False,
) -> str | None:
    parent = edge["hypernym"]
    child = edge["hyponym"]
    if not is_valid_parent_label(parent, concept_doc_freq):
        return "invalid_parent_label"
    if parent_validity_score(parent, concept_doc_freq) < 0.42:
        return "low_parent_validity"
    if is_low_quality_label(parent) or is_low_quality_label(child):
        return "low_quality_label"
    pt = TOKEN_RE.findall(parent.lower())
    ct = TOKEN_RE.findall(child.lower())
    recovery_sim_floor = float(config.recovery_lexical_override_similarity)
    recovery_lex_floor = float(config.recovery_lexical_override_lexical)
    recovery_score_floor = float(config.recovery_lexical_override_min_score)
    if len(pt) == 1 and len(ct) == 1:
        method = edge_method(edge)
        semantic = semantic_from_evidence(edge)
        score = float(edge.get("score", 0.0))
        sim = evidence_max_value(edge, "similarity")
        lex = evidence_max_value(edge, "lexical_similarity")
        recovery_single_ok = (
            recovery_mode
            and method in {
                "component_bridge",
                "component_anchor_bridge",
                "connectivity_repair_fallback",
                "orphan_safe_link",
            }
            and sim >= recovery_sim_floor
            and lex >= recovery_lex_floor
            and score >= recovery_score_floor
        )
        if not (
            (method in {"component_bridge", "component_anchor_bridge"} and score >= 0.72 and semantic >= 0.60)
            or (method == "component_anchor_bridge" and sim >= 0.62 and lex >= 0.28 and score >= 0.60)
            or recovery_single_ok
        ):
            return "single_to_single"
    if len(pt) > len(ct) + 1:
        return "parent_too_long"
    if float(edge.get("score", 0.0)) < min_score:
        return "score_below_threshold"
    semantic = semantic_from_evidence(edge)
    if semantic > 0:
        method = edge_method(edge)
        sim = evidence_max_value(edge, "similarity")
        lex = evidence_max_value(edge, "lexical_similarity")
        token_lex = 0.0
        if pt and ct:
            token_lex = len(set(pt) & set(ct)) / max(1, len(set(pt) | set(ct)))
        effective_lex = max(lex, token_lex)
        parent_validity = parent_validity_score(parent, concept_doc_freq)
        semantic_floor = 0.55
        if recovery_mode and method in {
            "component_bridge",
            "component_anchor_bridge",
            "connectivity_repair_fallback",
            "orphan_safe_link",
        }:
            semantic_floor -= 0.08 * max(0.0, parent_validity - 0.5)
            semantic_floor -= 0.10 * max(0.0, sim - 0.5)
            semantic_floor -= 0.06 * max(0.0, effective_lex - 0.2)
            semantic_floor = max(0.42, semantic_floor)
    else:
        semantic_floor = 0.0
        method = edge_method(edge)
        sim = evidence_max_value(edge, "similarity")
        token_lex = 0.0
        if pt and ct:
            token_lex = len(set(pt) & set(ct)) / max(1, len(set(pt) | set(ct)))
        effective_lex = max(evidence_max_value(edge, "lexical_similarity"), token_lex)

    if semantic > 0 and semantic < semantic_floor:
        if method in {"component_bridge", "component_anchor_bridge"} and float(edge.get("score", 0.0)) >= 0.68:
            return None
        if method == "component_anchor_bridge" and sim >= 0.58 and lex >= 0.18:
            return None
        if method in {"hearst", "hearst_trigger_fallback"} and sim >= 0.16 and float(edge.get("score", 0.0)) >= 0.56:
            return None
        if (
            recovery_mode
            and method == "component_anchor_bridge"
            and parent_validity >= 0.55
            and sim >= 0.50
            and effective_lex >= 0.12
            and float(edge.get("score", 0.0)) >= max(0.54, recovery_score_floor - 0.04)
        ):
            return None
        if (
            recovery_mode
            and method in {
                "component_bridge",
                "component_anchor_bridge",
                "connectivity_repair_fallback",
                "orphan_safe_link",
            }
            and sim >= recovery_sim_floor
            and effective_lex >= recovery_lex_floor
            and float(edge.get("score", 0.0)) >= recovery_score_floor
        ):
            return None
        return "low_semantic_evidence"
    return None


def is_edge_plausible(edge: dict, concept_doc_freq: dict[str, int], min_score: float) -> bool:
    return edge_rejection_reason(edge, concept_doc_freq, min_score) is None


def connectivity_min_score(edge: dict, base_min_score: float, recovery_mode: bool) -> float:
    if not recovery_mode:
        return base_min_score
    method = edge_method(edge)
    if method not in {"component_bridge", "component_anchor_bridge", "connectivity_repair_fallback", "orphan_safe_link"}:
        return base_min_score
    return max(0.48, base_min_score - 0.05)


def format_reason_counts(counts: Counter[str], max_items: int = 5) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{k}={v}" for k, v in counts.most_common(max_items))
