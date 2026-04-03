from types import SimpleNamespace
import uuid

from app.pipeline.taxonomy_build import build_persistence


class _FakeQuery:
    def __init__(self):
        self.filtered = False
        self.deleted = False

    def filter(self, *_args, **_kwargs):
        self.filtered = True
        return self

    def delete(self):
        self.deleted = True
        return 1


class _FakeSession:
    def __init__(self):
        self.query_obj = _FakeQuery()
        self.added = []
        self.commits = 0

    def query(self, _model):
        return self.query_obj

    def commit(self):
        self.commits += 1

    def add(self, row):
        self.added.append(row)


def _ctx(**settings_overrides):
    settings = SimpleNamespace(
        active_learning_enabled=True,
        active_learning_batch_size=2,
    )
    for key, value in settings_overrides.items():
        setattr(settings, key, value)
    parent = SimpleNamespace(id=uuid.uuid4())
    child = SimpleNamespace(id=uuid.uuid4())
    return SimpleNamespace(
        session=_FakeSession(),
        taxonomy_version_id=uuid.uuid4(),
        collection_id=uuid.uuid4(),
        job_id="job-1",
        method="hybrid",
        settings=settings,
        concept_map={"energy": parent, "battery storage": child},
    )


def test_persist_taxonomy_edges_replaces_old_edges_and_skips_unknown_concepts():
    ctx = _ctx()
    count = build_persistence.persist_taxonomy_edges(
        ctx,
        [
            {"hypernym": "energy", "hyponym": "battery storage", "score": 0.9, "evidence": {"method": "hearst"}},
            {"hypernym": "missing", "hyponym": "battery storage", "score": 0.6, "evidence": []},
        ],
    )

    assert count == 1
    assert ctx.session.query_obj.filtered is True
    assert ctx.session.query_obj.deleted is True
    assert len(ctx.session.added) == 1
    assert ctx.session.added[0].evidence == [{"method": "hearst"}]
    assert ctx.session.commits >= 2


def test_persist_edge_candidates_limits_batch_and_converts_uuid_strings():
    ctx = _ctx()
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()
    count = build_persistence.persist_edge_candidates(
        ctx,
        [
            {"parent_label": "energy", "child_label": "battery storage", "risk_score": 0.2},
            {
                "parent_concept_id": str(parent_id),
                "child_concept_id": str(child_id),
                "parent_label": "energy",
                "child_label": "battery storage",
                "risk_score": 0.9,
                "feature_vector": {"semantic_similarity": 0.8},
                "min_score": 0.55,
            },
            {"parent_concept_id": "bad-uuid", "child_label": "voltage", "risk_score": 0.4},
        ],
    )

    assert count == 2
    assert len(ctx.session.added) == 2
    top = ctx.session.added[0]
    assert top.parent_concept_id == parent_id
    assert top.child_concept_id == child_id
    assert top.feature_vector["min_score"] == 0.55


def test_finalize_helpers_emit_status_updates(monkeypatch):
    ctx = _ctx()
    events = []
    statuses = []

    monkeypatch.setattr(build_persistence, "add_job_event", lambda _session, _job_id, level, message: events.append((level, message)))
    monkeypatch.setattr(build_persistence, "update_job_status", lambda _session, _job_id, status, progress=0: statuses.append((status, progress)))
    monkeypatch.setattr(build_persistence, "update_taxonomy_status", lambda _session, tax_id, status: statuses.append((str(tax_id), status)))

    build_persistence.finalize_success(ctx, 3)
    build_persistence.finalize_empty(ctx, "nothing to build")

    assert any("Taxonomy build complete: 3 edges" in message for _level, message in events)
    assert any(message == "nothing to build" for _level, message in events)
    assert ("RUNNING", 100) in statuses

