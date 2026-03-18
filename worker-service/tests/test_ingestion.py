"""
Unit tests for ingestion — chunking logic.
"""
from app.pipeline.ingestion import (
    _clean_extracted_text,
    _merge_short_chunks,
    split_into_chunks,
)


class TestSplitIntoChunks:
    def test_simple_paragraphs(self):
        text = "First paragraph here.\n\nSecond paragraph here."
        chunks = split_into_chunks(text, max_size=500)
        assert len(chunks) == 2
        assert chunks[0]["text"] == "First paragraph here."
        assert chunks[1]["text"] == "Second paragraph here."

    def test_long_paragraph_splits(self):
        # Use sentence boundaries so the splitter can break the paragraph.
        long_text = " ".join(["Word sentence." for _ in range(80)])
        chunks = split_into_chunks(long_text, max_size=200)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk["text"]) <= 200 + 50  # allow some overshoot

    def test_empty_text(self):
        chunks = split_into_chunks("", max_size=500)
        assert chunks == []

    def test_offsets_present(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        chunks = split_into_chunks(text, max_size=500)
        for chunk in chunks:
            assert "char_start" in chunk
            assert "char_end" in chunk
            assert chunk["char_end"] >= chunk["char_start"]


class TestCleanExtractedText:
    def test_removes_known_headers_and_wiki_banner(self):
        text = (
            "Source: example\n"
            "Title: Sample title\n"
            "From Wikipedia\n"
            "Actual content line.\n"
        )

        cleaned = _clean_extracted_text(text)

        assert "Source:" not in cleaned
        assert "Title:" not in cleaned
        assert "Wikipedia" not in cleaned
        assert "Actual content line." in cleaned

    def test_replaces_null_bytes_and_trims_spacing(self):
        text = "Alpha\x00Beta\n\n\nGamma"

        cleaned = _clean_extracted_text(text)

        assert "\x00" not in cleaned
        assert "Alpha Beta" in cleaned
        assert "\n\n\n" not in cleaned


class TestMergeShortChunks:
    def test_merges_adjacent_short_chunks_when_under_limit(self):
        chunks = [
            {"text": "short", "char_start": 0, "char_end": 5},
            {"text": "tiny", "char_start": 6, "char_end": 10},
            {"text": "this chunk is long enough", "char_start": 11, "char_end": 35},
        ]

        merged = _merge_short_chunks(chunks, max_size=40, min_chars=8)

        assert len(merged) == 2
        assert merged[0]["text"] == "short tiny"
        assert merged[0]["char_start"] == 0
        assert merged[0]["char_end"] == 10
