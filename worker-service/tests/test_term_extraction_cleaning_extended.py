from app.pipeline.term_extraction_cleaning import (
    functional_terms_for_lang,
    is_functional_phrase,
    is_noise_term,
    is_noise_token,
    normalize_term,
)


class _Token:
    def __init__(self, text, lemma=None, pos="NOUN", is_punct=False, is_space=False):
        self.text = text
        self.lemma_ = lemma or text.lower()
        self.pos_ = pos
        self.is_punct = is_punct
        self.is_space = is_space


class _Nlp:
    def __init__(self, mapping=None, explode=False):
        self.mapping = mapping or {}
        self.explode = explode

    def __call__(self, text):
        if self.explode:
            raise RuntimeError("nlp failed")
        return self.mapping.get(text, [_Token(part) for part in text.split()])


def test_is_noise_token_and_noise_term_cover_edge_cases():
    assert is_noise_token("") is True
    assert is_noise_token("kwh") is True
    assert is_noise_token("12") is True
    assert is_noise_token("a1") is True
    assert is_noise_token("battery") is False

    assert is_noise_term("") is True
    assert is_noise_term("в том числе") is True
    assert is_noise_term("doi 10") is True
    assert is_noise_term("one two three four five six seven") is True
    assert is_noise_term("and") is True
    assert is_noise_term("the and") is True
    assert is_noise_term("battery battery") is True
    assert is_noise_term("optimize", _Nlp({"optimize": [_Token("optimize", pos="VERB")]})) is True
    assert is_noise_term("battery storage", _Nlp(explode=True)) is False


def test_functional_phrase_rules_cover_language_and_pos_paths():
    assert functional_terms_for_lang("kk")
    assert functional_terms_for_lang("en")

    nlp = _Nlp(
        {
            "for and": [_Token("for", pos="ADP"), _Token("and", pos="CCONJ")],
            "flow quickly": [_Token("flow", pos="VERB"), _Token("quickly", pos="ADV")],
            "battery storage": [_Token("battery", pos="NOUN"), _Token("storage", pos="NOUN")],
        }
    )

    assert is_functional_phrase("", "en") is True
    assert is_functional_phrase("for", "en") is True
    assert is_functional_phrase("for and", "en", nlp) is True
    assert is_functional_phrase("storage for", "en") is True
    assert is_functional_phrase("flow quickly", "en", nlp) is True
    assert is_functional_phrase("болып", "kk") is True
    assert is_functional_phrase("жасайтын жүйе", "kk") is True
    assert is_functional_phrase("battery storage", "en", nlp) is False


def test_normalize_term_covers_noise_and_cleanup_paths():
    nlp = _Nlp(
        {
            "commercial banks": [_Token("Commercial", lemma="commercial"), _Token("Banks", lemma="bank")],
            "energy and service": [_Token("energy"), _Token("and"), _Token("service")],
        }
    )

    assert normalize_term("!") is None
    assert normalize_term("the") is None
    assert normalize_term("Commercial Banks", nlp) == "commercial bank"
    assert normalize_term("and service") is None
    assert normalize_term("service and bank") == "bank"
    assert normalize_term("one two three four five") is None
    assert normalize_term("battery battery") is None
    assert normalize_term("data science") == "data science"


def test_cleaning_helpers_cover_remaining_rejection_branches():
    assert is_noise_term("battery and") is True
    assert is_noise_term("also") is True
    assert is_noise_term("optimize", _Nlp(explode=True)) is False

    assert is_functional_phrase("energy flow", "en", _Nlp(explode=True)) is False

    assert normalize_term("!!!") is None
    assert normalize_term("Commercial", _Nlp({"commercial": [_Token("X", lemma="x")]})) is None
    assert normalize_term("Service", _Nlp({"service": [_Token("service", lemma="service")]})) is None
    assert normalize_term("and service") is None
    assert normalize_term("bank and the") is None
