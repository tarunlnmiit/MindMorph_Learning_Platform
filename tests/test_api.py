"""FastAPI integration — full loop over HTTP against the in-memory store, with the LLM/graph calls
monkeypatched. Proves: create persists a session, get/list read it back, lesson + grade mutate and
persist, the lock gate returns 409, and unknown ids return 404."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

os.environ["MINDMORPH_STORE"] = "memory"  # zero-infra store for the test (set before app import)

import pytest
from fastapi.testclient import TestClient

import api.routes as routes
from api.main import app
from persistence.repository import _memory_singleton
from services.learning_service import LockedNodeError


def _scout_ls():
    return {
        "skill_graph": {
            "summary": "Path",
            "nodes": [
                {"id": "a", "label": "A", "description": "first", "level": "foundational"},
                {"id": "b", "label": "B", "description": "second", "level": "intermediate"},
            ],
            "edges": [{"source": "a", "target": "b", "relation": "prerequisite"}],
        },
        "node_state": {
            "a": {"status": "available", "best_score": 0, "attempts": 0, "weaknesses": [], "last_feedback": None},
            "b": {"status": "available", "best_score": 0, "attempts": 0, "weaknesses": [], "last_feedback": None},
        },
        "lessons": {},
        "selected_node": None,
        "format_type": "B",
    }


@pytest.fixture(autouse=True)
def _clean_store():
    _memory_singleton._store.clear()
    yield
    _memory_singleton._store.clear()


@pytest.fixture
def client(monkeypatch):
    # start_session returns a SCOUT result with a fresh learning_session (no orchestration graph).
    monkeypatch.setattr(
        routes, "start_session",
        lambda query, fmt: {"route": "SCOUT", "learning_session": _scout_ls(),
                            "final_content": None, "exercise": None},
    )

    def fake_open(ls, node_id, user_id=None):
        from services.completion import locked_node_ids
        if node_id in locked_node_ids(ls["skill_graph"], ls["node_state"]):
            raise LockedNodeError(node_id, ["A"])
        ls["selected_node"] = node_id
        ls["lessons"][node_id] = {"content": "lesson", "exercise": {"format": "coding_challenge",
                                  "statement": "s", "grading_artifact": {}}}
        return ls

    def fake_grade(ls, node_id, solution):
        ls["node_state"][node_id]["status"] = "mastered"
        ls["node_state"][node_id]["best_score"] = 100
        return ls

    monkeypatch.setattr(routes, "open_lesson", fake_open)
    monkeypatch.setattr(routes, "grade", fake_grade)
    return TestClient(app)


def test_health_reports_memory_store(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["store"] == "memory"


def test_create_session_persists_and_returns_graph(client):
    r = client.post("/sessions", json={"user_id": "u1", "query": "learn python"})
    assert r.status_code == 200
    body = r.json()
    assert body["route"] == "SCOUT"
    sid = body["session_id"]
    assert sid and len(body["learning_session"]["node_state"]) == 2
    # Persisted: a fresh GET returns the same session.
    assert client.get(f"/sessions/u1/{sid}").json()["learning_session"]["node_state"]["a"]["status"] == "available"


def test_list_sessions_shows_created(client):
    client.post("/sessions", json={"user_id": "u1", "query": "first path"})
    metas = client.get("/sessions/u1").json()
    assert len(metas) == 1 and metas[0]["title"] == "first path"


def test_get_missing_session_404(client):
    assert client.get("/sessions/u1/nope").status_code == 404


def test_open_lesson_then_grade_persists_mastery(client):
    sid = client.post("/sessions", json={"user_id": "u1", "query": "p"}).json()["session_id"]
    # 'a' is the unlocked root.
    r = client.post(f"/sessions/u1/{sid}/lessons/a")
    assert r.status_code == 200 and r.json()["learning_session"]["selected_node"] == "a"
    g = client.post(f"/sessions/u1/{sid}/grade", params={"node_id": "a"}, json={"solution": "code"})
    assert g.status_code == 200
    # Re-fetch: mastery durably persisted.
    after = client.get(f"/sessions/u1/{sid}").json()["learning_session"]
    assert after["node_state"]["a"]["status"] == "mastered"


def test_locked_lesson_returns_409(client):
    sid = client.post("/sessions", json={"user_id": "u1", "query": "p"}).json()["session_id"]
    r = client.post(f"/sessions/u1/{sid}/lessons/b")  # 'b' locked behind 'a'
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "locked"


def test_lesson_generation_failure_returns_503_not_500(client, monkeypatch):
    # An LLM/generation failure (e.g. Groq TPM rate limit) must surface as a graceful 503 with a safe
    # message, never a raw 500 that leaks internals.
    sid = client.post("/sessions", json={"user_id": "u1", "query": "p"}).json()["session_id"]

    def boom(ls, node_id):
        raise RuntimeError("groq 413 rate_limit_exceeded: super secret internals")

    monkeypatch.setattr(routes, "open_lesson", boom)
    r = client.post(f"/sessions/u1/{sid}/lessons/a")
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert isinstance(detail, str) and "try again" in detail.lower()
    assert "secret" not in detail  # internal error text not leaked


def test_compose_failure_records_event_before_503(client, monkeypatch):
    sid = client.post("/sessions", json={"user_id": "u1", "query": "p"}).json()["session_id"]
    monkeypatch.setattr(routes, "open_lesson", lambda ls, node_id, user_id=None: (_ for _ in ()).throw(RuntimeError("boom")))
    assert client.post(f"/sessions/u1/{sid}/lessons/a").status_code == 503
    # The failed attempt was persisted as a funnel signal.
    after = client.get(f"/sessions/u1/{sid}").json()["learning_session"]
    assert any(e["stage"] == "compose_failure" for e in after.get("events", []))


def test_flag_endpoint_records_content_flagged(client):
    sid = client.post("/sessions", json={"user_id": "u1", "query": "p"}).json()["session_id"]
    r = client.post(f"/sessions/u1/{sid}/lessons/a/flag", json={"reason": "wrong language"})
    assert r.status_code == 200
    flagged = [e for e in r.json()["learning_session"]["events"] if e["stage"] == "content_flagged"]
    assert len(flagged) == 1 and flagged[0]["node_id"] == "a" and flagged[0]["reason"] == "wrong language"


def _seed(user_id, session_id, events):
    _memory_singleton.save(user_id, session_id, {"events": events})


def test_admin_funnel_requires_token(client, monkeypatch):
    monkeypatch.setenv("MINDMORPH_ADMIN_TOKEN", "s3cret")
    assert client.get("/admin/funnel").status_code == 403  # no header
    assert client.get("/admin/funnel", headers={"x-admin-token": "wrong"}).status_code == 403


def test_admin_funnel_disabled_without_env(client, monkeypatch):
    monkeypatch.delenv("MINDMORPH_ADMIN_TOKEN", raising=False)
    assert client.get("/admin/funnel", headers={"x-admin-token": "x"}).status_code == 503


def test_admin_funnel_aggregates(client, monkeypatch):
    monkeypatch.setenv("MINDMORPH_ADMIN_TOKEN", "s3cret")
    _seed("u1", "s1", [
        {"ts": "t", "stage": "session_created"},
        {"ts": "t", "stage": "lesson_opened", "node_id": "a", "cache_hit": False},
        {"ts": "t", "stage": "exercise_graded", "node_id": "a", "score": 90.0},
        {"ts": "t", "stage": "path_completed"},
    ])
    _seed("u2", "s2", [
        {"ts": "t", "stage": "session_created"},
        {"ts": "t", "stage": "content_flagged", "node_id": "a"},
    ])
    out = client.get("/admin/funnel", headers={"x-admin-token": "s3cret"}).json()
    assert out["total_sessions"] == 2
    assert out["reached_grade"] == 1
    assert out["completed"] == 1
    assert out["content_flags_total"] == 1
    assert out["sessions_reaching_stage"]["session_created"] == 2
