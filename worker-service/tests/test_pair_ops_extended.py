from types import SimpleNamespace
from unittest.mock import MagicMock
import uuid

from app.pipeline.taxonomy_build import pair_ops


def _query_all(result):
    query = MagicMock()
    query.join.return_value = query
    query.filter.return_value = query
    query.all.return_value = result
    return query


def _yield_query(rows):
    query = MagicMock()
    query.filter.return_value = query
    query.yield_per.return_value = rows
    return query


def test_edge_rank_method_weight_and_collapse_bidirectional_pairs():
    concept_doc_freq = {"energy": 6, "battery storage": 4, "storage": 2}
    forward = {"hypernym": "energy", "hyponym": "battery storage", "score": 0.62}
    backward = {"hypernym": "battery storage", "hyponym": "energy", "score": 0.71}

    collapsed = pair_ops.collapse_bidirectional_pairs([forward, backward], concept_doc_freq)

    assert pair_ops.method_weight("hearst") == 0.72
    assert pair_ops.method_weight("component_bridge") == 0.58
    assert len(collapsed) == 1
    assert collapsed[0]["hypernym"] == "energy"


def test_compute_pair_cooccurrence_builds_discounted_support_scores():
    chunks = [
        SimpleNamespace(text="Energy and battery storage improve resilience", document_id="doc-1"),
        SimpleNamespace(text="Energy and battery storage stabilize the grid", document_id="doc-2"),
    ]

    support = pair_ops.compute_pair_cooccurrence(chunks, ["energy", "battery storage", "grid"])

    assert support[("energy", "battery storage")] > 0.0
    assert support[("battery storage", "energy")] == support[("energy", "battery storage")]


def test_compute_concept_doc_freq_refines_low_frequency_terms(monkeypatch):
    collection_id = uuid.uuid4()
    concept_energy = SimpleNamespace(id=uuid.uuid4(), canonical="energy", collection_id=collection_id)
    concept_storage = SimpleNamespace(id=uuid.uuid4(), canonical="battery storage", collection_id=collection_id)
    session = MagicMock()
    session.query.side_effect = [
        _query_all([(concept_energy.id, uuid.uuid4())]),
        _query_all([(uuid.uuid4(),), (uuid.uuid4(),)]),
        _yield_query([
            (uuid.uuid4(), "battery storage improves resilience"),
            (uuid.uuid4(), "battery storage balances load"),
        ]),
    ]
    monkeypatch.setattr(pair_ops, "config", SimpleNamespace(min_parent_doc_freq=2))

    result = pair_ops.compute_concept_doc_freq(session, [concept_energy, concept_storage])

    assert result["energy"] == 1
    assert result["battery storage"] == 2


def test_connectivity_and_hubness_helpers_preserve_critical_edges():
    concept_doc_freq = {
        "energy": 8,
        "battery storage": 5,
        "microgrid": 4,
        "solar storage": 3,
        "wind storage": 3,
    }
    pairs = [
        {"hypernym": "energy", "hyponym": "battery storage", "score": 0.8},
        {"hypernym": "energy", "hyponym": "microgrid", "score": 0.75},
        {"hypernym": "energy", "hyponym": "solar storage", "score": 0.7},
        {"hypernym": "energy", "hyponym": "wind storage", "score": 0.68},
    ]

    critical = pair_ops.connectivity_critical_edge_keys(pairs, list(concept_doc_freq.keys()), concept_doc_freq)
    capped = pair_ops.cap_protected_edge_keys_by_parent(pairs, critical, concept_doc_freq, max_per_parent=2)
    limited = pair_ops.limit_parent_hubness(pairs, concept_doc_freq, max_children_per_parent=2, protected_edge_keys=capped)

    assert ("energy", "battery storage") in critical
    assert len(capped) <= 2
    assert len(limited) <= 3
