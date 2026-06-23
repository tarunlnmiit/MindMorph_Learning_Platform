"""Funnel instrumentation (services/events.py): timeline recording + read-side aggregation. No LLM."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from services.events import STAGES, funnel_summary, has_event, record_event


def test_record_event_appends_ts_stage_and_fields():
    ls = {}
    record_event(ls, STAGES.LESSON_OPENED, node_id="a", cache_hit=False)
    assert len(ls["events"]) == 1
    e = ls["events"][0]
    assert e["stage"] == STAGES.LESSON_OPENED
    assert e["node_id"] == "a" and e["cache_hit"] is False
    assert "ts" in e  # ISO timestamp stamped


def test_has_event():
    ls = {}
    assert not has_event(ls, STAGES.PATH_COMPLETED)
    record_event(ls, STAGES.PATH_COMPLETED)
    assert has_event(ls, STAGES.PATH_COMPLETED)


def test_funnel_summary_over_hand_built_timeline():
    ls = {
        "events": [
            {"ts": "t0", "stage": STAGES.SESSION_CREATED, "node_count": 2},
            {"ts": "t1", "stage": STAGES.LESSON_OPENED, "node_id": "a", "cache_hit": False},
            {"ts": "t2", "stage": STAGES.EXERCISE_GRADED, "node_id": "a", "score": 20.0},
            {"ts": "t3", "stage": STAGES.LESSON_REGENERATED, "node_id": "a"},
            {"ts": "t4", "stage": STAGES.CONTENT_FLAGGED, "node_id": "a"},
        ]
    }
    s = funnel_summary(ls)
    assert s["distinct_nodes_opened"] == 1
    assert s["low_score_count"] == 1  # 20 < REVIEW_THRESHOLD (40)
    assert s["regenerations"] == 1
    assert s["content_flags"] == 1 and s["flagged_nodes"] == ["a"]
    assert s["reached_grade"] is True
    assert s["completed"] is False
    assert s["last_stage"] == STAGES.CONTENT_FLAGGED  # the drop point


def test_funnel_summary_over_real_record_event_output():
    """Guards writer/reader key drift (the cost review's `cost` vs `est_cost_usd` bug class): the
    summary must read fields that `record_event` actually writes, not a hand-built shape."""
    ls = {}
    record_event(ls, STAGES.SESSION_CREATED, node_count=1)
    record_event(ls, STAGES.LESSON_OPENED, node_id="a", cache_hit=False)
    record_event(ls, STAGES.EXERCISE_GRADED, node_id="a", score=90.0, passed=True)
    record_event(ls, STAGES.NODE_MASTERED, node_id="a")
    record_event(ls, STAGES.PATH_COMPLETED)
    s = funnel_summary(ls)
    assert s["distinct_nodes_opened"] == 1
    assert s["scores"] == [90.0]
    assert s["low_score_count"] == 0
    assert s["reached_grade"] is True
    assert s["completed"] is True
    assert s["last_stage"] == STAGES.PATH_COMPLETED


def test_funnel_summary_empty():
    s = funnel_summary({})
    assert s["event_count"] == 0
    assert s["last_stage"] is None
    assert s["completed"] is False
