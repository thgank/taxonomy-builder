"""
Unit tests for ingestion — chunking logic.
"""
from app.pipeline.ingestion import split_into_chunks


class TestSplitIntoChunks:
    def test_simple_paragraphs(self):
        text = "First paragraph here.\n\nSecond paragraph here."
        chunks = split_into_chunks(text, max_size=500)
        assert len(chunks) == 2
        assert chunks[0]["text"] == "First paragraph here."
        assert chunks[1]["text"] == "Second paragraph here."

    def test_long_paragraph_splits(self):
        # Create a paragraph longer than max_size
        long_text = "Word " * 300  # ~1500 chars
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
