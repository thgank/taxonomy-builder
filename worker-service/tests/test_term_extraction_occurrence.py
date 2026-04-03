from types import SimpleNamespace
import uuid

from app.pipeline.term_extraction_occurrence import find_occurrences


def _chunk(text: str, document_id: uuid.UUID | None = None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        document_id=document_id or uuid.uuid4(),
        text=text,
    )


def test_find_occurrences_keeps_first_hit_per_document_before_overflow():
    doc1 = uuid.uuid4()
    doc2 = uuid.uuid4()
    chunks = [
        _chunk("Battery storage improves grid resilience. Battery storage also supports renewables.", doc1),
        _chunk("Battery storage reduces balancing costs.", doc2),
    ]

    result = find_occurrences("battery storage", chunks, max_per_term=3)

    assert len(result) == 3
    assert result[0]["chunk_id"] == str(chunks[0].id)
    assert result[1]["chunk_id"] == str(chunks[1].id)
    assert all(0.35 <= row["confidence"] <= 0.96 for row in result)


def test_find_occurrences_expands_to_sentence_boundaries_and_respects_limit():
    doc_id = uuid.uuid4()
    chunks = [
        _chunk(
            "Energy systems are evolving. Battery storage is essential for modern grids! "
            "Battery storage improves flexibility.",
            doc_id,
        )
    ]

    result = find_occurrences("battery storage", chunks, max_per_term=1)

    assert len(result) == 1
    assert result[0]["snippet"] == "Battery storage is essential for modern grids!"
    assert result[0]["start_offset"] < result[0]["end_offset"]
