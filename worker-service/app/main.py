"""
Main entry point — starts health server + RabbitMQ consumer.
"""
from __future__ import annotations

import threading

import uvicorn

from app.config import config
from app.consumer import start_consumer
from app.health import health_app
from app.logger import get_logger
from app.pipeline.ingestion import handle_import
from app.pipeline.nlp import handle_nlp
from app.pipeline.term_extraction import handle_terms
from app.pipeline.taxonomy_builder import handle_build
from app.pipeline.evaluation import handle_evaluate

log = get_logger(__name__)


def main() -> None:
    log.info("Starting Taxonomy Worker Service")

    # Start health endpoint in background thread
    health_thread = threading.Thread(
        target=lambda: uvicorn.run(
            health_app,
            host="0.0.0.0",
            port=config.health_port,
            log_level="warning",
        ),
        daemon=True,
    )
    health_thread.start()
    log.info("Health endpoint started on port %d", config.health_port)

    # Define pipeline handlers:
    # queue_name → handler_function
    # Routing to next stage is handled by consumer.py based on jobType
    handlers = {
        config.queue_import:   handle_import,
        config.queue_nlp:      handle_nlp,
        config.queue_terms:    handle_terms,
        config.queue_build:    handle_build,
        config.queue_evaluate: handle_evaluate,
    }

    # This blocks forever
    start_consumer(handlers)


if __name__ == "__main__":
    main()
