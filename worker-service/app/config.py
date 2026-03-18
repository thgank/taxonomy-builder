"""
Central configuration — loaded from environment variables.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://taxonomy:taxonomy_secret@localhost:5432/taxonomy",
    )

    # RabbitMQ
    rabbitmq_url: str = os.getenv(
        "RABBITMQ_URL",
        "amqp://taxonomy:rabbit_secret@localhost:5672/",
    )

    # Storage
    storage_path: str = os.getenv("STORAGE_PATH", "./data/uploads")
    allow_plaintext_fallback: bool = (
        os.getenv("ALLOW_PLAINTEXT_FALLBACK", "false").lower() == "true"
    )
    strip_document_headers: bool = (
        os.getenv("STRIP_DOCUMENT_HEADERS", "true").lower() == "true"
    )

    # spaCy models
    spacy_model_en: str = os.getenv("SPACY_MODEL_EN", "en_core_web_sm")
    spacy_model_ru: str = os.getenv("SPACY_MODEL_RU", "ru_core_news_sm")
    # Optional: Kazakh model may be unavailable in local env; fallback heuristics will be used.
    spacy_model_kk: str = os.getenv("SPACY_MODEL_KK", "")
    supported_languages: tuple[str, ...] = tuple(
        x.strip() for x in os.getenv("SUPPORTED_LANGUAGES", "en,ru,kk").split(",") if x.strip()
    )
    default_language: str = os.getenv("DEFAULT_LANGUAGE", "en")

    # Pipeline defaults
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1000"))
    chunk_min_chars: int = int(os.getenv("CHUNK_MIN_CHARS", "80"))
    max_terms: int = int(os.getenv("MAX_TERMS", "500"))
    max_occurrences_per_term: int = int(os.getenv("MAX_OCCURRENCES_PER_TERM", "80"))
    min_term_freq: int = int(os.getenv("MIN_TERM_FREQ", "2"))
    min_doc_freq: int = int(os.getenv("MIN_DOC_FREQ", "2"))
    min_term_quality_score: float = float(os.getenv("MIN_TERM_QUALITY_SCORE", "0.40"))
    similarity_threshold: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.58"))
    fuzz_threshold: int = int(os.getenv("FUZZ_THRESHOLD", "85"))
    max_depth: int = int(os.getenv("MAX_DEPTH", "6"))
    parent_pool_size: int = int(os.getenv("PARENT_POOL_SIZE", "5"))
    max_children_per_parent: int = int(os.getenv("MAX_CHILDREN_PER_PARENT", "6"))
    adaptive_percentile: int = int(os.getenv("ADAPTIVE_PERCENTILE", "45"))
    quality_min_edge_density: float = float(os.getenv("QUALITY_MIN_EDGE_DENSITY", "0.20"))
    quality_min_largest_component_ratio: float = float(
        os.getenv("QUALITY_MIN_LARGEST_COMPONENT_RATIO", "0.40")
    )
    quality_max_hubness: float = float(os.getenv("QUALITY_MAX_HUBNESS", "6.0"))
    quality_max_lexical_noise_rate: float = float(os.getenv("QUALITY_MAX_LEXICAL_NOISE_RATE", "0.05"))
    orphan_linking_enabled: bool = os.getenv("ORPHAN_LINKING_ENABLED", "true").lower() == "true"
    orphan_link_threshold: float = float(os.getenv("ORPHAN_LINK_THRESHOLD", "0.57"))
    orphan_link_max_links: int = int(os.getenv("ORPHAN_LINK_MAX_LINKS", "30"))
    component_bridging_enabled: bool = os.getenv("COMPONENT_BRIDGING_ENABLED", "true").lower() == "true"
    component_bridge_threshold: float = float(os.getenv("COMPONENT_BRIDGE_THRESHOLD", "0.54"))
    component_bridge_max_links: int = int(os.getenv("COMPONENT_BRIDGE_MAX_LINKS", "20"))
    min_parent_doc_freq: int = int(os.getenv("MIN_PARENT_DOC_FREQ", "3"))
    min_edge_accept_score: float = float(os.getenv("MIN_EDGE_ACCEPT_SCORE", "0.64"))
    min_bridge_semantic_similarity: float = float(
        os.getenv("MIN_BRIDGE_SEMANTIC_SIMILARITY", "0.82")
    )
    min_bridge_lexical_similarity: float = float(
        os.getenv("MIN_BRIDGE_LEXICAL_SIMILARITY", "0.28")
    )
    bridge_parent_load_penalty_alpha: float = float(
        os.getenv("BRIDGE_PARENT_LOAD_PENALTY_ALPHA", "0.06")
    )
    bridge_max_new_children_per_parent: int = int(
        os.getenv("BRIDGE_MAX_NEW_CHILDREN_PER_PARENT", "2")
    )
    hubness_protected_max_per_parent: int = int(
        os.getenv("HUBNESS_PROTECTED_MAX_PER_PARENT", "2")
    )
    recovery_lexical_override_similarity: float = float(
        os.getenv("RECOVERY_LEXICAL_OVERRIDE_SIMILARITY", "0.60")
    )
    recovery_lexical_override_lexical: float = float(
        os.getenv("RECOVERY_LEXICAL_OVERRIDE_LEXICAL", "0.22")
    )
    recovery_lexical_override_min_score: float = float(
        os.getenv("RECOVERY_LEXICAL_OVERRIDE_MIN_SCORE", "0.58")
    )
    adaptive_target_lcr_enabled: bool = (
        os.getenv("ADAPTIVE_TARGET_LCR_ENABLED", "true").lower() == "true"
    )
    adaptive_target_lcr_value: float = float(
        os.getenv("ADAPTIVE_TARGET_LCR_VALUE", "0.50")
    )
    adaptive_target_lcr_min_coverage: float = float(
        os.getenv("ADAPTIVE_TARGET_LCR_MIN_COVERAGE", "0.60")
    )
    adaptive_target_lcr_min_components: int = int(
        os.getenv("ADAPTIVE_TARGET_LCR_MIN_COMPONENTS", "6")
    )
    adaptive_target_lcr_gap_trigger: float = float(
        os.getenv("ADAPTIVE_TARGET_LCR_GAP_TRIGGER", "0.02")
    )
    adaptive_target_component_ratio: float = float(
        os.getenv("ADAPTIVE_TARGET_COMPONENT_RATIO", "0.30")
    )
    adaptive_target_component_min_count: int = int(
        os.getenv("ADAPTIVE_TARGET_COMPONENT_MIN_COUNT", "6")
    )
    orientation_sanity_enabled: bool = (
        os.getenv("ORIENTATION_SANITY_ENABLED", "true").lower() == "true"
    )
    orientation_sanity_low_score_threshold: float = float(
        os.getenv("ORIENTATION_SANITY_LOW_SCORE_THRESHOLD", "0.62")
    )
    orientation_sanity_max_rewrites: int = int(
        os.getenv("ORIENTATION_SANITY_MAX_REWRITES", "8")
    )
    root_consolidation_enabled: bool = (
        os.getenv("ROOT_CONSOLIDATION_ENABLED", "true").lower() == "true"
    )
    root_consolidation_min_similarity: float = float(
        os.getenv("ROOT_CONSOLIDATION_MIN_SIMILARITY", "0.18")
    )
    root_consolidation_max_root_outdegree: int = int(
        os.getenv("ROOT_CONSOLIDATION_MAX_ROOT_OUTDEGREE", "2")
    )
    hearst_trigger_fallback_enabled: bool = (
        os.getenv("HEARST_TRIGGER_FALLBACK_ENABLED", "true").lower() == "true"
    )
    adaptive_thresholds_enabled: bool = (
        os.getenv("ADAPTIVE_THRESHOLDS_ENABLED", "true").lower() == "true"
    )
    threshold_profile_name: str = os.getenv("THRESHOLD_PROFILE_NAME", "default")
    threshold_profile_global_fallback: bool = (
        os.getenv("THRESHOLD_PROFILE_GLOBAL_FALLBACK", "true").lower() == "true"
    )

    # Edge ranker
    edge_ranker_enabled: bool = os.getenv("EDGE_RANKER_ENABLED", "false").lower() == "true"
    edge_ranker_model_path: str = os.getenv("EDGE_RANKER_MODEL_PATH", "./data/models/edge_ranker.joblib")
    edge_ranker_blend_alpha: float = float(os.getenv("EDGE_RANKER_BLEND_ALPHA", "0.45"))
    edge_ranker_min_confidence: float = float(os.getenv("EDGE_RANKER_MIN_CONFIDENCE", "0.40"))

    # Retrieval-augmented evidence for linking
    evidence_linking_enabled: bool = (
        os.getenv("EVIDENCE_LINKING_ENABLED", "false").lower() == "true"
    )
    evidence_top_k: int = int(os.getenv("EVIDENCE_TOP_K", "5"))
    evidence_window_chars: int = int(os.getenv("EVIDENCE_WINDOW_CHARS", "220"))
    evidence_max_pairs_per_job: int = int(os.getenv("EVIDENCE_MAX_PAIRS_PER_JOB", "200"))

    # Active-learning loop
    active_learning_enabled: bool = (
        os.getenv("ACTIVE_LEARNING_ENABLED", "true").lower() == "true"
    )
    active_learning_batch_size: int = int(os.getenv("ACTIVE_LEARNING_BATCH_SIZE", "200"))
    active_learning_min_risk_score: float = float(
        os.getenv("ACTIVE_LEARNING_MIN_RISK_SCORE", "0.35")
    )
    threshold_max_update_step: float = float(os.getenv("THRESHOLD_MAX_UPDATE_STEP", "0.03"))
    threshold_min_label_samples: int = int(os.getenv("THRESHOLD_MIN_LABEL_SAMPLES", "50"))

    # Multilingual quality gates
    cross_lang_consistency_min: float = float(os.getenv("CROSS_LANG_CONSISTENCY_MIN", "0.80"))
    per_lang_min_coverage: float = float(os.getenv("PER_LANG_MIN_COVERAGE", "0.45"))

    # Global edge selector (Phase 2 architecture)
    global_selector_enabled: bool = (
        os.getenv("GLOBAL_SELECTOR_ENABLED", "true").lower() == "true"
    )
    selector_include_rejected_candidates: bool = (
        os.getenv("SELECTOR_INCLUDE_REJECTED_CANDIDATES", "true").lower() == "true"
    )
    selector_score_floor: float = float(os.getenv("SELECTOR_SCORE_FLOOR", "0.58"))
    selector_min_bridge_score: float = float(os.getenv("SELECTOR_MIN_BRIDGE_SCORE", "0.54"))
    selector_parent_cap: int = int(os.getenv("SELECTOR_PARENT_CAP", "6"))
    selector_connectivity_bonus: float = float(os.getenv("SELECTOR_CONNECTIVITY_BONUS", "0.16"))
    selector_orphan_bonus: float = float(os.getenv("SELECTOR_ORPHAN_BONUS", "0.08"))
    selector_max_edges_factor: float = float(os.getenv("SELECTOR_MAX_EDGES_FACTOR", "0.90"))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Health server
    health_port: int = int(os.getenv("HEALTH_PORT", "8081"))

    # Exchange / queue names
    exchange: str = "taxonomy"
    queue_import: str = "taxonomy.import"
    queue_nlp: str = "taxonomy.nlp"
    queue_terms: str = "taxonomy.terms"
    queue_build: str = "taxonomy.build"
    queue_evaluate: str = "taxonomy.evaluate"


config = Config()
