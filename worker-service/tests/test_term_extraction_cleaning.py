from types import SimpleNamespace

from app.pipeline.term_extraction_cleaning import (
    compile_term_pattern,
    functional_terms_for_lang,
    is_functional_phrase,
    is_noise_term,
    is_noise_token,
    normalize_term,
)


class _FakeToken:
    def __init__(self, text: str, lemma: str | None = None, pos: str = "NOUN"):
        self.text = text
        self.lemma_ = lemma or text.lower()
        self.pos_ = pos
        self.is_punct = False
        self.is_space = False


class _FakeNlp:
    def __init__(self, token_map: dict[str, list[_FakeToken]]):
        self.token_map = token_map

    def __call__(self, text: str):
        return self.token_map.get(
            text,
            [_FakeToken(part) for part in text.split()],
        )


def test_compile_term_pattern_matches_whole_terms_case_insensitively():
    pattern = compile_term_pattern("bank")

    assert pattern.search("Commercial Bank services") is not None
    assert pattern.search("banking sector") is None


def test_is_noise_token_flags_stopwords_and_short_numeric_tokens():
    assert is_noise_token("and") is True
    assert is_noise_token("12") is True
    assert is_noise_token("a1") is True
    assert is_noise_token("battery") is False


def test_is_noise_term_uses_pos_signal_for_single_verbs():
    fake_nlp = _FakeNlp({"optimize": [_FakeToken("optimize", pos="VERB")]})

    assert is_noise_term("optimize", fake_nlp) is True
    assert is_noise_term("battery storage", fake_nlp) is False


def test_is_functional_phrase_detects_function_heavy_phrases_and_kazakh_tails():
    fake_nlp = _FakeNlp(
        {
            "for and": [
                _FakeToken("for", pos="ADP"),
                _FakeToken("and", pos="CCONJ"),
            ]
        }
    )

    assert functional_terms_for_lang("ru")
    assert is_functional_phrase("for and", "en", fake_nlp) is True
    assert is_functional_phrase("энергия сақтау болу", "kk") is True
    assert is_functional_phrase("battery storage", "en", fake_nlp) is False


def test_normalize_term_lemmatizes_and_removes_generic_connectors():
    fake_nlp = _FakeNlp(
        {
            "commercial banks": [
                _FakeToken("Commercial", lemma="commercial"),
                _FakeToken("Banks", lemma="bank"),
            ]
        }
    )

    assert normalize_term("Commercial Banks", fake_nlp) == "commercial bank"
    assert normalize_term("service and bank") == "bank"
    assert normalize_term("12345") is None
