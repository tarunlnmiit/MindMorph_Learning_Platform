"""DB-gated integration test for the REAL PostgresLearningSessionRepository.

Skipped automatically when Postgres at config.DATABASE_URL is unreachable (CI without a DB, or a dev
machine with no `docker compose up -d db`), so the default suite stays infra-free. When a DB is up it
exercises the actual JSONB upsert path the in-memory store only mirrors — the one seam that otherwise
returns to zero automated coverage after the manual durability proof.

Run it explicitly after `docker compose up -d db && alembic upgrade head`:
    conda run -n mindmorph python -m pytest tests/test_repository_postgres.py -q
"""
import os
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

import pytest


def _postgres_reachable() -> bool:
    try:
        from sqlalchemy import text
        from persistence.db import get_engine

        with get_engine().connect() as c:
            c.execute(text("select 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_reachable(),
    reason="Postgres not reachable at DATABASE_URL (run `docker compose up -d db && alembic upgrade head`)",
)


def _ls(summary="v1"):
    return {
        "skill_graph": {"summary": summary, "nodes": [{"id": "a", "label": "A"}], "edges": []},
        "node_state": {"a": {"status": "available", "best_score": 0, "attempts": 0,
                             "weaknesses": [], "last_feedback": None}},
        "lessons": {},
        "selected_node": None,
    }


@pytest.fixture
def repo():
    from persistence.repository import PostgresLearningSessionRepository

    return PostgresLearningSessionRepository()


@pytest.fixture
def user_id():
    # Unique per run so parallel/repeat runs never collide on the shared DB; cleaned up after.
    return f"pytest-{uuid.uuid4().hex[:8]}"


def test_postgres_roundtrip_upsert_list_delete(repo, user_id):
    sid = "s1"
    try:
        # insert
        repo.save(user_id, sid, _ls("v1"), title="Learn X")
        assert repo.get(user_id, sid) == _ls("v1")

        # upsert overwrites data; title preserved when omitted
        repo.save(user_id, sid, _ls("v2"))
        got = repo.get(user_id, sid)
        assert got["skill_graph"]["summary"] == "v2"
        metas = repo.list_sessions(user_id)
        assert len(metas) == 1 and metas[0]["title"] == "Learn X"

        # graded state (the JSONB-serializability concern) round-trips
        graded = _ls("v2")
        graded["node_state"]["a"].update(status="mastered", best_score=100,
                                         last_feedback={"score": 100, "passed": 1, "total": 1})
        repo.save(user_id, sid, graded)
        assert repo.get(user_id, sid)["node_state"]["a"]["status"] == "mastered"
    finally:
        repo.delete(user_id, sid)
        assert repo.get(user_id, sid) is None
