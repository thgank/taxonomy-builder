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
    max_terms: int = int(os.getenv("MAX_TERMS", "500"))
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
