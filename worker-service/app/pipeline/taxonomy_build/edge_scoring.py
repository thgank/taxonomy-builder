from __future__ import annotations

from collections import defaultdict


CONNECTIVITY_METHOD_MIN_SCORES = {
    "component_bridge": 0.56,
    "component_anchor_bridge": 0.62,
    "orphan_safe_link": 0.58,
    "connectivity_repair_fallback": 0.56,
    "hearst_trigger_fallback": 0.62,
}


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if p <= 0:
        return float(min(values))
    if p >= 100:
        return float(max(values))
    xs = sorted(float(v) for v in values)
    pos = (len(xs) - 1) * (p / 100.0)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return float(xs[lo] * (1.0 - frac) + xs[hi] * frac)


def edge_method(edge: dict) -> str:
    ev = edge.get("evidence", {})
    if isinstance(ev, dict):
        return str(ev.get("method", "unknown"))
    if isinstance(ev, list):
        for item in ev:
            if isinstance(item, dict) and item.get("method"):
                return str(item["method"])
    return "unknown"


def adaptive_method_thresholds(
    pairs: list[dict],
    base_min_score: float,
    percentile_value: float,
) -> dict[str, float]:
    by_method: dict[str, list[float]] = defaultdict(list)
    for e in pairs:
        by_method[edge_method(e)].append(float(e.get("score", 0.0)))
    out: dict[str, float] = {}
    for method, scores in by_method.items():
        if len(scores) < 4:
            out[method] = base_min_score
            continue
        pscore = percentile(scores, percentile_value)
        out[method] = max(0.45, min(base_min_score, round(pscore, 4)))
    return out


def edge_min_score(edge: dict, default_score: float, method_thresholds: dict[str, float]) -> float:
    method = edge_method(edge)
    if method in method_thresholds:
        return float(method_thresholds[method])
    if method in CONNECTIVITY_METHOD_MIN_SCORES:
        return float(min(default_score, CONNECTIVITY_METHOD_MIN_SCORES[method]))
    return float(default_score)


def threshold_from_profile(
    profile: dict,
    method: str,
    lang: str | None,
    fallback: float,
) -> float:
    if not profile:
        return float(fallback)
    lang_key = (lang or "").lower()[:2]
    lang_profiles = profile.get("lang_method_thresholds", {})
    if isinstance(lang_profiles, dict):
        lang_row = lang_profiles.get(lang_key, {})
        if isinstance(lang_row, dict) and method in lang_row:
            return float(lang_row[method])
    method_profiles = profile.get("method_thresholds", {})
    if isinstance(method_profiles, dict) and method in method_profiles:
        return float(method_profiles[method])
    if "min_edge_accept_score" in profile:
        return float(profile["min_edge_accept_score"])
    return float(fallback)


def blend_scores(
    base_score: float,
    ranker_score: float | None = None,
    evidence_score: float | None = None,
    ranker_alpha: float = 0.45,
    evidence_alpha: float = 0.15,
) -> float:
    score = float(base_score)
    if ranker_score is not None:
        a = max(0.0, min(1.0, float(ranker_alpha)))
        score = ((1.0 - a) * score) + (a * float(ranker_score))
    if evidence_score is not None:
        b = max(0.0, min(0.4, float(evidence_alpha)))
        score = ((1.0 - b) * score) + (b * float(evidence_score))
    return max(0.0, min(1.0, float(score)))


def adaptive_bridge_budget(
    base_budget: int,
    concept_count: int,
    current_lcr: float,
    target_lcr: float,
) -> int:
    gap = max(0.0, target_lcr - current_lcr)
    adaptive = int(concept_count * (0.8 + (1.8 * gap)))
    return max(base_budget, min(max(8, concept_count), adaptive))
