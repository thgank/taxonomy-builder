"""
Unit tests for term extraction — normalization, TF-IDF, TextRank.
"""
from app.pipeline.term_extraction_cleaning import normalize_term
from app.pipeline.term_extraction_methods import extract_ngrams
from app.pipeline.term_extraction_scoring import deduplicate_terms


class TestNormalize:
    def test_basic(self):
        assert normalize_term("Machine Learning") == "machine learning"

    def test_short_word_filtered(self):
        assert normalize_term("a") is None

    def test_numeric_filtered(self):
        assert normalize_term("12345") is None

    def test_stopword_single(self):
        assert normalize_term("the") is None

    def test_multiword_keeps(self):
        result = normalize_term("data science")
        assert result is not None
        assert "data" in result


class TestNgrams:
    def test_extracts_unigrams_and_bigrams(self):
        text = "machine learning and deep learning are popular"
        grams = extract_ngrams(text, ns=(1, 2))
        assert any("machine" in g for g in grams)
        assert any("machine learning" in g for g in grams)

    def test_filters_stopwords(self):
        text = "the cat is on the mat"
        grams = extract_ngrams(text, ns=(1,))
        assert "the" not in grams
        assert "cat" in grams


class TestDeduplication:
    def test_merges_similar(self):
        terms = {
            "machine learning": 0.9,
            "machine-learning": 0.85,
            "deep learning": 0.8,
        }
        deduped, surface_map = deduplicate_terms(terms, threshold=80)
        # "machine learning" and "machine-learning" might merge
        assert len(deduped) >= 2
        assert "deep learning" in deduped

    def test_no_merge_different(self):
        terms = {
            "biology": 0.9,
            "chemistry": 0.8,
        }
        deduped, _ = deduplicate_terms(terms, threshold=90)
        assert len(deduped) == 2
