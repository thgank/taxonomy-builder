from __future__ import annotations

from typing import Any

from app.config import config

_nlp_models: dict[str, Any] = {}


def load_spacy(lang: str) -> Any:
    if lang not in _nlp_models:
        import spacy

        name = {
            "en": config.spacy_model_en,
            "ru": config.spacy_model_ru,
            "kk": config.spacy_model_kk,
        }.get(lang)
        if name:
            try:
                _nlp_models[lang] = spacy.load(name)
            except OSError:
                _nlp_models[lang] = None
        else:
            _nlp_models[lang] = None
    return _nlp_models.get(lang)

