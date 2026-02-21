"""
Structured JSON logger with correlation / trace id support.
"""
import logging
import json
import sys
from datetime import datetime, timezone

from app.config import config


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Attach correlation / trace ids if present
        for attr in ("correlation_id", "trace_id", "job_id"):
            val = getattr(record, attr, None)
            if val:
                log_obj[attr] = val
        if record.exc_info and record.exc_info[1]:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(config.log_level)
    return logger
