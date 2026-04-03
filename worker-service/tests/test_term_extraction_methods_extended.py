from types import SimpleNamespace

from app.pipeline import term_extraction_methods


def _token(text, pos, lemma=None, is_space=False, is_punct=False):
    return SimpleNamespace(
        text=text,
        pos_=pos,
        lemma_=(lemma or text.lower()),
        is_space=is_space,
        is_punct=is_punct,
    )


def test_split_phrase_and_allowed_np_filters_tokens():
    phrase = "bank, insurance and lending"
    span = [_token("commercial", "ADJ"), _token("bank", "NOUN")]

    assert term_extraction_methods.split_phrase(phrase) == ["bank", "insurance", "lending"]
    assert term_extraction_methods.is_allowed_np(span) is True
    assert term_extraction_methods.is_allowed_np([_token("run", "VERB")]) is False


def test_extract_noun_phrases_spacy_collects_chunks_and_nouns():
    class FakeSpan(list):
        @property
        def text(self):
            return " ".join(token.text for token in self)

    class FakeDoc(list):
        noun_chunks = [FakeSpan([_token("commercial", "ADJ"), _token("bank", "NOUN")])]

    fake_doc = FakeDoc([_token("bank", "NOUN"), _token("credit", "NOUN")])
    model = lambda _text: fake_doc

    phrases = term_extraction_methods.extract_noun_phrases_spacy("Commercial bank credit", model)

    assert "commercial bank" in [phrase.lower() for phrase in phrases]
    assert "bank" in phrases
    assert "credit" in phrases


def test_extract_ngrams_tfidf_textrank_and_merge_scores():
    chunks = [
        SimpleNamespace(text="Battery storage improves grid resilience", document_id="doc-1"),
        SimpleNamespace(text="Battery storage supports grid balancing", document_id="doc-2"),
    ]

    grams = term_extraction_methods.extract_ngrams("Battery storage improves grid resilience", ns=(1, 2))
    tfidf = term_extraction_methods.tfidf_extract(chunks, None, max_terms=5, min_freq=1, min_doc_freq=1)
    textrank = term_extraction_methods.textrank_extract(chunks, None, max_terms=5, window=2, iterations=5)
    merged = term_extraction_methods.merge_scores(tfidf, textrank, alpha=0.5)

    assert "battery" in grams
    assert "battery storage" in grams
    assert any("battery" in term for term in tfidf)
    assert textrank
    assert merged
    assert max(merged.values()) <= 1.0
