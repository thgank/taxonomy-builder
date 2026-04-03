from types import ModuleType, SimpleNamespace
import sys

from app import health, main


def test_health_endpoint_returns_expected_payload():
    assert health.health() == {"status": "UP", "service": "taxonomy-worker"}


def test_main_starts_health_thread_and_consumer(monkeypatch):
    calls = []

    class FakeThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            calls.append(("thread_started", self.daemon))
            self.target()

    monkeypatch.setattr(main, "config", SimpleNamespace(
        health_port=8099,
        queue_import="import",
        queue_nlp="nlp",
        queue_terms="terms",
        queue_build="build",
        queue_evaluate="evaluate",
    ))
    monkeypatch.setattr(main.threading, "Thread", FakeThread)
    monkeypatch.setattr(main.uvicorn, "run", lambda app, host, port, log_level: calls.append(("uvicorn", host, port, log_level, app.title)))
    monkeypatch.setattr(main, "start_consumer", lambda handlers: calls.append(("consumer", sorted(handlers.keys()))))

    main.main()

    assert ("thread_started", True) in calls
    assert ("uvicorn", "0.0.0.0", 8099, "warning", "Taxonomy Worker Health") in calls
    assert ("consumer", ["build", "evaluate", "import", "nlp", "terms"]) in calls

