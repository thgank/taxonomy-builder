"""
Central configuration — loaded from environment variables.
"""
import os
from dataclasses import dataclass, field


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

    # spaCy models
    spacy_model_en: str = os.getenv("SPACY_MODEL_EN", "en_core_web_sm")
    spacy_model_ru: str = os.getenv("SPACY_MODEL_RU", "ru_core_news_sm")

    # Pipeline defaults
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1000"))
    max_terms: int = int(os.getenv("MAX_TERMS", "500"))
    min_term_freq: int = int(os.getenv("MIN_TERM_FREQ", "2"))
    similarity_threshold: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.55"))
    fuzz_threshold: int = int(os.getenv("FUZZ_THRESHOLD", "85"))
    max_depth: int = int(os.getenv("MAX_DEPTH", "6"))

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
