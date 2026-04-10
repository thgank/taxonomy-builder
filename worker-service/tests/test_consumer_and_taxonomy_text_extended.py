import json
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

from app import consumer
from app.pipeline import taxonomy_text


class _Token:
    def __init__(self, text, pos="NOUN", lemma=None, is_punct=False, is_space=False):
        self.text = text
        self.pos_ = pos
        self.lemma_ = lemma or text.lower()
        self.is_punct = is_punct
        self.is_space = is_space


def test_consumer_helpers_cover_fallback_logging_lock_release_and_start(monkeypatch):
    assert consumer._resolve_job_type(MagicMock(), {}, None) is None

    query = MagicMock()
    query.filter.return_value = query
    query.first.return_value = None
    session = MagicMock()
    session.query.return_value = query
    assert consumer._resolve_job_type(session, {}, "job-1") is None

    good_session = MagicMock()
    consumer._log_to_dlq(good_session, "job-1", "queue", "routing", {"x": 1}, "boom", 2)
    good_session.add.assert_called_once()
    good_session.commit.assert_called_once()

    bad_session = MagicMock()
    bad_session.add.side_effect = RuntimeError("db down")
    consumer._log_to_dlq(bad_session, "job-1", "queue", "routing", {"x": 1}, "boom", 2)

    collection = SimpleNamespace(active_job_id="job-1")
    job = SimpleNamespace(collection_id="col-1")
    job_query = MagicMock()
    job_query.filter.return_value = job_query
    job_query.first.return_value = job
    collection_query = MagicMock()
    collection_query.filter.return_value = collection_query
    collection_query.first.return_value = collection
    release_session = MagicMock()
    release_session.query.side_effect = [job_query, collection_query]
    consumer._release_collection_lock(release_session, "job-1")
    assert collection.active_job_id is None
    release_session.commit.assert_called_once()

    release_session_fail = MagicMock()
    release_session_fail.query.side_effect = RuntimeError("query failed")
    consumer._release_collection_lock(release_session_fail, "job-2")

    params_seen = {}
    callbacks = []

    class FakeParams:
        def __init__(self, url):
            self.url = url
            self.heartbeat = None
            self.blocked_connection_timeout = None

    monkeypatch.setattr(consumer.pika, "URLParameters", FakeParams)

    def _consume(queue, on_message_callback):
        callbacks.append((queue, on_message_callback))

    fake_channel = MagicMock()
    fake_channel.basic_consume.side_effect = _consume
    fake_channel.start_consuming.side_effect = KeyboardInterrupt()

    def _blocking_connection(params):
        params_seen["params"] = params
        return SimpleNamespace(
            channel=lambda: fake_channel,
            close=lambda: params_seen.setdefault("closed", True),
        )

    monkeypatch.setattr(
        consumer.pika,
        "BlockingConnection",
        _blocking_connection,
    )

    consumer.start_consumer({"taxonomy.import": lambda session, msg: None})

    assert params_seen["params"].heartbeat == 600
    assert params_seen["params"].blocked_connection_timeout == 300
    fake_channel.basic_qos.assert_called_once_with(prefetch_count=1)
    assert callbacks
    fake_channel.stop_consuming.assert_called_once()


def test_consumer_on_message_handles_parse_fail_and_finalize_failures(monkeypatch):
    channel = MagicMock()
    method = SimpleNamespace(delivery_tag=7, routing_key="evaluate", exchange="taxonomy")
    properties = SimpleNamespace(headers={})

    consumer._on_message(lambda session, msg: None, channel, method, properties, b"not-json")
    channel.basic_nack.assert_called_once_with(delivery_tag=7, requeue=False)

    session = MagicMock()
    monkeypatch.setattr(consumer, "get_session", lambda: session)
    monkeypatch.setattr(consumer, "is_job_cancelled", lambda *_args: False)
    monkeypatch.setattr(consumer, "_release_collection_lock", lambda *_args: (_ for _ in ()).throw(RuntimeError("release failed")))
    monkeypatch.setattr(consumer, "update_job_status", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(consumer, "add_job_event", lambda *_args, **_kwargs: None)

    channel.reset_mock()
    consumer._on_message(
        lambda session, msg: None,
        channel,
        method,
        properties,
        json.dumps({"jobId": "job-8", "jobType": "FULL_PIPELINE"}).encode(),
    )
    channel.basic_ack.assert_called_once_with(delivery_tag=7)

    retry_session = MagicMock()
    monkeypatch.setattr(consumer, "get_session", lambda: retry_session)
    monkeypatch.setattr(consumer, "add_job_event", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("event failed")))
    monkeypatch.setattr(consumer, "update_job_status", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("status failed")))
    channel.reset_mock()
    consumer._on_message(
        lambda session, msg: (_ for _ in ()).throw(RuntimeError("fatal")),
        channel,
        SimpleNamespace(delivery_tag=8, routing_key="terms", exchange="taxonomy"),
        SimpleNamespace(headers={}),
        json.dumps({"jobId": "job-9", "jobType": "FULL_PIPELINE"}).encode(),
    )
    channel.basic_publish.assert_called_once()
    channel.basic_ack.assert_called_once_with(delivery_tag=8)

    failing_session = MagicMock()
    monkeypatch.setattr(consumer, "get_session", lambda: failing_session)
    monkeypatch.setattr(consumer, "_log_to_dlq", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(consumer, "update_job_status", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("status fail")))
    monkeypatch.setattr(consumer, "_release_collection_lock", lambda *_args, **_kwargs: None)
    channel.reset_mock()
    consumer._on_message(
        lambda session, msg: (_ for _ in ()).throw(RuntimeError("fatal")),
        channel,
        SimpleNamespace(delivery_tag=9, routing_key="terms", exchange="taxonomy"),
        SimpleNamespace(headers={"x-retry-count": consumer.MAX_RETRIES}),
        json.dumps({"jobId": "job-10", "jobType": "FULL_PIPELINE"}).encode(),
    )
    channel.basic_nack.assert_called_once_with(delivery_tag=9, requeue=False)


def test_taxonomy_text_helpers_cover_spacy_candidates_and_quality_paths(monkeypatch):
    spacy = ModuleType("spacy")
    calls = []

    def load_model(name):
        calls.append(name)
        if name == "ru_core_news_sm":
            raise RuntimeError("missing model")
        return lambda text: [_Token("energy", "NOUN"), _Token("system", "NOUN")]

    spacy.load = load_model
    monkeypatch.setitem(sys.modules, "spacy", spacy)
    monkeypatch.setattr(taxonomy_text, "_NLP_MODELS", {})
    object.__setattr__(taxonomy_text.config, "spacy_model_kk", "kk_model")

    assert taxonomy_text._load_spacy("en") is not None
    assert taxonomy_text._load_spacy("ru") is None
    assert taxonomy_text._load_spacy("kk") is not None
    assert calls
    assert taxonomy_text._token_overlap_ratio("", "bank") == 0.0
    assert taxonomy_text._token_overlap_ratio("energy systems", "energy market") > 0
    assert taxonomy_text._is_noun_phrase_candidate("", None) is False
    assert taxonomy_text._is_noun_phrase_candidate("energy", None) is False
    assert taxonomy_text._is_noun_phrase_candidate("for", None, allow_single=True) is False
    assert taxonomy_text._is_noun_phrase_candidate("also", None, allow_single=True) is False
    assert taxonomy_text._is_noun_phrase_candidate("energy", None, allow_single=True) is True
    assert taxonomy_text._is_noun_phrase_candidate("energy system", None) is True
    assert taxonomy_text._is_noun_phrase_candidate("energy system", lambda _text: [_Token(",", is_punct=True)]) is False
    assert taxonomy_text._is_noun_phrase_candidate("energy", lambda _text: [_Token("energy", "NOUN")], allow_single=True) is True
    assert taxonomy_text._is_noun_phrase_candidate("energy", lambda _text: [_Token("energy", "VERB")], allow_single=True) is False
    assert taxonomy_text._is_noun_phrase_candidate("energy system", lambda _text: [_Token("energy", "ADJ"), _Token("system", "VERB")]) is False
    assert taxonomy_text._is_noun_phrase_candidate("energy system", lambda _text: (_ for _ in ()).throw(RuntimeError("nlp broke"))) is True

    assert taxonomy_text.normalize_candidate("!!") is None
    assert taxonomy_text.normalize_candidate("около") is None
    assert taxonomy_text.normalize_candidate("other service") is None
    assert taxonomy_text.normalize_candidate("other other") is None
    assert taxonomy_text.normalize_candidate("type") is None
    assert taxonomy_text.normalize_candidate("energy type system") == "energy system"
    assert taxonomy_text.is_low_quality_label("около") is True
    assert taxonomy_text.is_low_quality_label("a1") is True
    assert taxonomy_text.is_low_quality_label("type") is True
    assert taxonomy_text.is_low_quality_label("also") is True
    assert taxonomy_text.is_low_quality_label("kw mw") is True
    assert taxonomy_text.is_low_quality_label("ab12") is True
    assert taxonomy_text.is_low_quality_label("doi 10") is True
    assert taxonomy_text.is_low_quality_label("energy energy energy") is True
    assert taxonomy_text.is_low_quality_label("kw") is True
    assert taxonomy_text.is_low_quality_label("ab") is True
    assert taxonomy_text.is_low_quality_label("battery storage") is False

    assert taxonomy_text.find_closest_concept("", {"battery storage"}) is None
    assert taxonomy_text.find_closest_concept("bad !!!", {"battery storage"}) is None
    assert taxonomy_text.find_closest_concept("other", {"!!!"}) is None
    monkeypatch.setattr(taxonomy_text, "SequenceMatcher", lambda *args, **kwargs: SimpleNamespace(ratio=lambda: 0.8))
    assert taxonomy_text.find_closest_concept("battery", {"battery storage", "market finance"}) == "battery storage"
    assert taxonomy_text.find_closest_concept("battery energy systems", {"battery energy system", "finance platform"}) == "battery energy system"


def test_taxonomy_text_extractors_cover_hard_soft_and_trigger_branches(monkeypatch):
    chunks = [
        SimpleNamespace(id="c1", text="Energy system such as battery energy system and solar energy system."),
        SimpleNamespace(id="c2", text="Battery energy system and other energy system improve resilience."),
        SimpleNamespace(id="c3", text="Grid energy system belongs to the energy system."),
    ]
    concept_set = {"energy system", "battery energy system", "solar energy system", "grid energy system"}
    monkeypatch.setattr(taxonomy_text, "_load_spacy", lambda _lang: None)

    hard_pairs = taxonomy_text.extract_hearst_pairs(chunks, concept_set, lang="en", soft_mode=False)
    soft_pairs = taxonomy_text.extract_hearst_pairs(chunks, concept_set, lang="en", soft_mode=True)
    assert hard_pairs
    assert len(soft_pairs) >= len(hard_pairs)
    assert taxonomy_text.extract_hearst_pairs(
        [SimpleNamespace(id="cru", text="Энергия жүйесі сияқты батарея энергия жүйесі, күн энергия жүйесі.")],
        {"энергия жүйесі", "батарея энергия жүйесі", "күн энергия жүйесі"},
        lang="kk",
        soft_mode=True,
    )
    assert taxonomy_text.extract_hearst_pairs(
        [SimpleNamespace(id="cru2", text="Энергетическая система, например аккумуляторная энергетическая система.")],
        {"энергетическая система", "аккумуляторная энергетическая система"},
        lang="ru",
        soft_mode=True,
    )
    assert taxonomy_text.extract_hearst_pairs(
        [SimpleNamespace(id="c0", text="Node is a type of graph.")],
        {"node", "graph"},
        lang="en",
        soft_mode=False,
    ) == []
    assert taxonomy_text.extract_hearst_pairs(
        [SimpleNamespace(id="c0b", text="Type such as battery energy system and solar energy system.")],
        {"battery energy system", "solar energy system"},
        lang="en",
        soft_mode=False,
    ) == []

    soft_only_chunks = [SimpleNamespace(id="c4", text="Financial resilience such as liquidity buffer and capital reserve.")]
    monkeypatch.setattr(taxonomy_text, "_is_noun_phrase_candidate", lambda text, _nlp, allow_single=False: text != "financial resilience")
    monkeypatch.setattr(
        taxonomy_text,
        "find_closest_concept",
        lambda text, concept_set: {"financial resilience": "financial resilience", "liquidity buffer": "liquidity buffer", "capital reserve": "capital reserve"}.get(text),
    )
    monkeypatch.setattr(taxonomy_text, "_token_overlap_ratio", lambda _a, _b: 0.3)
    soft_only = taxonomy_text.extract_hearst_pairs(
        soft_only_chunks,
        {"financial resilience", "liquidity buffer", "capital reserve"},
        lang="en",
        soft_mode=True,
    )
    assert soft_only
    monkeypatch.setattr(taxonomy_text, "_is_noun_phrase_candidate", lambda text, _nlp, allow_single=False: False if text == "node" else True)
    assert taxonomy_text.extract_hearst_pairs(
        [SimpleNamespace(id="csoft", text="Node such as battery energy system and solar energy system.")],
        {"node", "battery energy system", "solar energy system"},
        lang="en",
        soft_mode=True,
    ) == []
    monkeypatch.setattr(taxonomy_text, "_is_noun_phrase_candidate", lambda text, _nlp, allow_single=False: False if text == "buffer" else True)
    assert taxonomy_text.extract_hearst_pairs(
        [SimpleNamespace(id="chard", text="Energy system such as buffer and solar energy system.")],
        {"energy system", "buffer", "solar energy system"},
        lang="en",
        soft_mode=False,
    ) == []
    monkeypatch.setattr(taxonomy_text, "_is_noun_phrase_candidate", lambda text, _nlp, allow_single=False: True)
    monkeypatch.setattr(taxonomy_text, "find_closest_concept", lambda text, concept_set: None)
    assert taxonomy_text.extract_hearst_pairs(
        [SimpleNamespace(id="c5", text="Energy platform such as unknown buffer and mystery reserve.")],
        {"energy platform"},
        lang="en",
        soft_mode=True,
    ) == []
    monkeypatch.setattr(
        taxonomy_text,
        "find_closest_concept",
        lambda text, concept_set: {"energy systems": "energy system", "battery energy systems": "battery energy system"}.get(text),
    )
    fuzzy_pairs = taxonomy_text.extract_hearst_pairs(
        [SimpleNamespace(id="cfuzzy", text="Energy systems such as battery energy systems and solar energy system.")],
        {"energy system", "battery energy system", "solar energy system"},
        lang="en",
        soft_mode=True,
    )
    assert fuzzy_pairs
    monkeypatch.setattr(taxonomy_text, "_token_overlap_ratio", lambda _a, _b: 0.0)
    assert taxonomy_text.extract_hearst_pairs(
        [SimpleNamespace(id="coverlap", text="Energy system such as battery energy system and solar energy system.")],
        {"energy system", "battery energy system", "solar energy system"},
        lang="en",
        soft_mode=False,
    ) == []
    monkeypatch.setattr(taxonomy_text, "_token_overlap_ratio", lambda _a, _b: 1.0)
    assert taxonomy_text.extract_hearst_pairs(
        [SimpleNamespace(id="csame", text="Energy system such as energy system and node.")],
        {"energy system", "node"},
        lang="en",
        soft_mode=True,
    ) == []

    assert taxonomy_text.extract_hearst_trigger_pairs([], set(), max_pairs=0) == []
    assert taxonomy_text.extract_hearst_trigger_pairs(
        [SimpleNamespace(id="c6", text="No trigger here")],
        {"energy systems", "battery storage"},
        lang="en",
    ) == []

    trigger_pairs = taxonomy_text.extract_hearst_trigger_pairs(
        [SimpleNamespace(id="c7", text="Energy system including battery energy system and solar energy system improves resilience.")],
        {"energy system", "battery energy system", "solar energy system"},
        lang="en",
        concept_doc_freq={"energy system": 8, "battery energy system": 3, "solar energy system": 2},
        max_pairs=2,
    )
    assert trigger_pairs
    assert all(pair["evidence"]["method"] == "hearst_trigger_fallback" for pair in trigger_pairs)

    ru_pairs = taxonomy_text.extract_hearst_trigger_pairs(
        [SimpleNamespace(id="c8", text="Энергетические системы, например аккумуляторные системы и солнечные системы.")],
        {"энергетические системы", "аккумуляторные системы", "солнечные системы"},
        lang="ru",
        concept_doc_freq={"энергетические системы": 8, "аккумуляторные системы": 3, "солнечные системы": 2},
        max_pairs=1,
    )
    assert ru_pairs
    kk_pairs = taxonomy_text.extract_hearst_trigger_pairs(
        [SimpleNamespace(id="c9", text="Энергия жүйесі сияқты батарея энергия жүйесі мен күн энергия жүйесі.")],
        {"энергия жүйесі", "батарея энергия жүйесі", "күн энергия жүйесі"},
        lang="kk",
        concept_doc_freq={"энергия жүйесі": 8, "батарея энергия жүйесі": 3, "күн энергия жүйесі": 2},
        max_pairs=1,
    )
    assert kk_pairs
    assert taxonomy_text.extract_hearst_trigger_pairs(
        [SimpleNamespace(id="c10", text="Energy system including battery energy system.")],
        {"energy system"},
        lang="en",
    ) == []
    assert taxonomy_text.extract_hearst_trigger_pairs(
        [SimpleNamespace(id="c11", text="Energy system including finance platform and credit market.")],
        {"energy system", "finance platform", "credit market"},
        lang="en",
        concept_doc_freq={"energy system": 8, "finance platform": 3, "credit market": 10},
        max_pairs=2,
    )
    assert taxonomy_text.extract_hearst_trigger_pairs(
        [SimpleNamespace(id="c12", text="Node including graph and edge.")],
        {"node", "graph", "edge"},
        lang="en",
        concept_doc_freq={"node": 5, "graph": 3, "edge": 2},
        max_pairs=2,
    ) == []
