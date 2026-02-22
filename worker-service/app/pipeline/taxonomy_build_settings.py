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
    min_parent_doc_freq: int
    adaptive_edge_accept_percentile: float
    target_largest_component_ratio: float
    anchor_bridging_enabled: bool
    connectivity_repair_enabled: bool
    lcr_recovery_mode_enabled: bool
    lcr_recovery_margin: float
    coverage_recovery_enabled: bool
    coverage_recovery_target: float
    anchor_bridge_max_links: int
    connectivity_repair_max_links: int
    coverage_recovery_max_links: int
    hearst_soft_mode: bool


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
        coverage_recovery_enabled=bool(params.get("coverage_recovery_enabled", True)),
        coverage_recovery_target=float(params.get("coverage_recovery_target", 0.64)),
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
    )

