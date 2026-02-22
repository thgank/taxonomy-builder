from __future__ import annotations

from dataclasses import dataclass

from app.config import config


@dataclass(frozen=True)
class BuildSettings:
    method: str
    max_depth: int
    sim_threshold: float
    parent_pool_size: int
    max_children_per_parent: int
    adaptive_percentile: int
    quality_thresholds: dict[str, float]
    enforce_quality_gate: bool
    orphan_linking_enabled: bool
    orphan_link_threshold: float
    orphan_link_max_links: int
    component_bridging_enabled: bool
    component_bridge_threshold: float
    component_bridge_max_links: int
    bridge_max_new_children_per_parent: int
    bridge_parent_load_penalty_alpha: float
    min_parent_doc_freq: int
    adaptive_edge_accept_percentile: float
    target_largest_component_ratio: float
    anchor_bridging_enabled: bool
    connectivity_repair_enabled: bool
    lcr_recovery_mode_enabled: bool
    lcr_recovery_margin: float
    adaptive_target_lcr_enabled: bool
    adaptive_target_lcr_value: float
    adaptive_target_lcr_min_coverage: float
    adaptive_target_lcr_min_components: int
    adaptive_target_lcr_gap_trigger: float
    adaptive_target_component_ratio: float
    adaptive_target_component_min_count: int
    coverage_recovery_enabled: bool
    coverage_recovery_target: float
    hubness_protected_max_per_parent: int
    orientation_sanity_enabled: bool
    orientation_sanity_low_score_threshold: float
    orientation_sanity_max_rewrites: int
    root_consolidation_enabled: bool
    root_consolidation_min_similarity: float
    root_consolidation_max_root_outdegree: int
    root_consolidation_max_links: int
    hearst_trigger_fallback_enabled: bool
    hearst_trigger_fallback_max_pairs: int
    anchor_bridge_max_links: int
    connectivity_repair_max_links: int
    coverage_recovery_max_links: int
    hearst_soft_mode: bool
    adaptive_thresholds_enabled: bool
    threshold_profile_name: str
    edge_ranker_enabled: bool
    edge_ranker_model_path: str
    edge_ranker_blend_alpha: float
    edge_ranker_min_confidence: float
    evidence_linking_enabled: bool
    evidence_top_k: int
    evidence_max_pairs_per_job: int
    active_learning_enabled: bool
    active_learning_batch_size: int
    active_learning_min_risk_score: float
    per_lang_min_coverage: float
    cross_lang_consistency_min: float


def load_build_settings(params: dict, concept_count: int) -> BuildSettings:
    quality_thresholds = {
        "min_edge_density": float(
            params.get("quality_min_edge_density", config.quality_min_edge_density)
        ),
        "min_largest_component_ratio": float(
            params.get(
                "quality_min_largest_component_ratio",
                config.quality_min_largest_component_ratio,
            )
        ),
        "max_hubness": float(params.get("quality_max_hubness", config.quality_max_hubness)),
        "max_lexical_noise_rate": float(
            params.get("quality_max_lexical_noise_rate", config.quality_max_lexical_noise_rate)
        ),
    }
    return BuildSettings(
        method=params.get("method_taxonomy", "hybrid"),
        max_depth=int(params.get("max_depth", config.max_depth)),
        sim_threshold=float(params.get("similarity_threshold", config.similarity_threshold)),
        parent_pool_size=int(params.get("parent_pool_size", config.parent_pool_size)),
        max_children_per_parent=int(
            params.get("max_children_per_parent", config.max_children_per_parent)
        ),
        adaptive_percentile=int(params.get("adaptive_percentile", config.adaptive_percentile)),
        quality_thresholds=quality_thresholds,
        enforce_quality_gate=bool(params.get("enforce_quality_gate", False)),
        orphan_linking_enabled=bool(
            params.get("orphan_linking_enabled", config.orphan_linking_enabled)
        ),
        orphan_link_threshold=float(
            params.get("orphan_link_threshold", config.orphan_link_threshold)
        ),
        orphan_link_max_links=int(
            params.get("orphan_link_max_links", config.orphan_link_max_links)
        ),
        component_bridging_enabled=bool(
            params.get("component_bridging_enabled", config.component_bridging_enabled)
        ),
        component_bridge_threshold=float(
            params.get("component_bridge_threshold", config.component_bridge_threshold)
        ),
        component_bridge_max_links=int(
            params.get("component_bridge_max_links", config.component_bridge_max_links)
        ),
        bridge_max_new_children_per_parent=int(
            params.get(
                "bridge_max_new_children_per_parent",
                config.bridge_max_new_children_per_parent,
            )
        ),
        bridge_parent_load_penalty_alpha=float(
            params.get(
                "bridge_parent_load_penalty_alpha",
                config.bridge_parent_load_penalty_alpha,
            )
        ),
        min_parent_doc_freq=int(params.get("min_parent_doc_freq", config.min_parent_doc_freq)),
        adaptive_edge_accept_percentile=float(params.get("adaptive_edge_accept_percentile", 25)),
        target_largest_component_ratio=float(
            params.get(
                "target_largest_component_ratio",
                quality_thresholds["min_largest_component_ratio"],
            )
        ),
        anchor_bridging_enabled=bool(params.get("anchor_bridging_enabled", True)),
        connectivity_repair_enabled=bool(params.get("connectivity_repair_enabled", True)),
        lcr_recovery_mode_enabled=bool(params.get("lcr_recovery_mode_enabled", True)),
        lcr_recovery_margin=float(params.get("lcr_recovery_margin", 0.02)),
        adaptive_target_lcr_enabled=bool(
            params.get("adaptive_target_lcr_enabled", config.adaptive_target_lcr_enabled)
        ),
        adaptive_target_lcr_value=float(
            params.get("adaptive_target_lcr_value", config.adaptive_target_lcr_value)
        ),
        adaptive_target_lcr_min_coverage=float(
            params.get(
                "adaptive_target_lcr_min_coverage",
                config.adaptive_target_lcr_min_coverage,
            )
        ),
        adaptive_target_lcr_min_components=int(
            params.get(
                "adaptive_target_lcr_min_components",
                config.adaptive_target_lcr_min_components,
            )
        ),
        adaptive_target_lcr_gap_trigger=float(
            params.get(
                "adaptive_target_lcr_gap_trigger",
                config.adaptive_target_lcr_gap_trigger,
            )
        ),
        adaptive_target_component_ratio=float(
            params.get(
                "adaptive_target_component_ratio",
                config.adaptive_target_component_ratio,
            )
        ),
        adaptive_target_component_min_count=int(
            params.get(
                "adaptive_target_component_min_count",
                config.adaptive_target_component_min_count,
            )
        ),
        coverage_recovery_enabled=bool(params.get("coverage_recovery_enabled", True)),
        coverage_recovery_target=float(params.get("coverage_recovery_target", 0.64)),
        hubness_protected_max_per_parent=int(
            params.get(
                "hubness_protected_max_per_parent",
                config.hubness_protected_max_per_parent,
            )
        ),
        orientation_sanity_enabled=bool(
            params.get("orientation_sanity_enabled", config.orientation_sanity_enabled)
        ),
        orientation_sanity_low_score_threshold=float(
            params.get(
                "orientation_sanity_low_score_threshold",
                config.orientation_sanity_low_score_threshold,
            )
        ),
        orientation_sanity_max_rewrites=int(
            params.get(
                "orientation_sanity_max_rewrites",
                config.orientation_sanity_max_rewrites,
            )
        ),
        root_consolidation_enabled=bool(
            params.get("root_consolidation_enabled", config.root_consolidation_enabled)
        ),
        root_consolidation_min_similarity=float(
            params.get(
                "root_consolidation_min_similarity",
                config.root_consolidation_min_similarity,
            )
        ),
        root_consolidation_max_root_outdegree=int(
            params.get(
                "root_consolidation_max_root_outdegree",
                config.root_consolidation_max_root_outdegree,
            )
        ),
        root_consolidation_max_links=int(
            params.get("root_consolidation_max_links", max(6, concept_count // 8))
        ),
        hearst_trigger_fallback_enabled=bool(
            params.get("hearst_trigger_fallback_enabled", config.hearst_trigger_fallback_enabled)
        ),
        hearst_trigger_fallback_max_pairs=int(
            params.get("hearst_trigger_fallback_max_pairs", max(5, concept_count // 8))
        ),
        anchor_bridge_max_links=int(
            params.get("anchor_bridge_max_links", max(12, concept_count // 3))
        ),
        connectivity_repair_max_links=int(
            params.get("connectivity_repair_max_links", max(10, concept_count // 4))
        ),
        coverage_recovery_max_links=int(
            params.get("coverage_recovery_max_links", max(8, concept_count // 5))
        ),
        hearst_soft_mode=bool(params.get("hearst_soft_mode", True)),
        adaptive_thresholds_enabled=bool(
            params.get("adaptive_thresholds_enabled", config.adaptive_thresholds_enabled)
        ),
        threshold_profile_name=str(
            params.get("threshold_profile_name", config.threshold_profile_name)
        ),
        edge_ranker_enabled=bool(
            params.get("edge_ranker_enabled", config.edge_ranker_enabled)
        ),
        edge_ranker_model_path=str(
            params.get("edge_ranker_model_path", config.edge_ranker_model_path)
        ),
        edge_ranker_blend_alpha=float(
            params.get("edge_ranker_blend_alpha", config.edge_ranker_blend_alpha)
        ),
        edge_ranker_min_confidence=float(
            params.get("edge_ranker_min_confidence", config.edge_ranker_min_confidence)
        ),
        evidence_linking_enabled=bool(
            params.get("evidence_linking_enabled", config.evidence_linking_enabled)
        ),
        evidence_top_k=int(
            params.get("evidence_top_k", config.evidence_top_k)
        ),
        evidence_max_pairs_per_job=int(
            params.get("evidence_max_pairs_per_job", config.evidence_max_pairs_per_job)
        ),
        active_learning_enabled=bool(
            params.get("active_learning_enabled", config.active_learning_enabled)
        ),
        active_learning_batch_size=int(
            params.get("active_learning_batch_size", config.active_learning_batch_size)
        ),
        active_learning_min_risk_score=float(
            params.get("active_learning_min_risk_score", config.active_learning_min_risk_score)
        ),
        per_lang_min_coverage=float(
            params.get("per_lang_min_coverage", config.per_lang_min_coverage)
        ),
        cross_lang_consistency_min=float(
            params.get("cross_lang_consistency_min", config.cross_lang_consistency_min)
        ),
    )
