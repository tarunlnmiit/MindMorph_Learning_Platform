"""Prerequisite-gated completion: a node is complete only when it AND its prerequisites (transitively)
are mastered. Pure helpers in app.py — no Streamlit run."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from app import (
    _prereqs_by_node,
    _complete_node_ids,
    _display_status,
    _locked_node_ids,
    _incomplete_prereq_labels,
)


def _graph(edges):
    return {
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "edges": edges,
    }


def _state(**statuses):
    # default every node to 'available' unless overridden
    base = {nid: {"status": "available"} for nid in ("a", "b", "c")}
    for nid, st in statuses.items():
        base[nid] = {"status": st}
    return base


# edge: source = prerequisite, target = dependent. a --> b means a is a prerequisite of b.
def test_prereqs_inverted_from_edges():
    prereqs = _prereqs_by_node(_graph([{"source": "a", "target": "b"}]))
    assert prereqs["b"] == {"a"}
    assert prereqs["a"] == set()


def test_mastered_with_unmastered_prereq_is_not_complete():
    g = _graph([{"source": "a", "target": "b"}])      # a is prereq of b
    state = _state(a="available", b="mastered")        # b passed, a not
    complete = _complete_node_ids(g, state)
    assert "b" not in complete                          # gated by incomplete prereq a
    assert "a" not in complete


def test_chain_completes_when_all_mastered():
    g = _graph([{"source": "a", "target": "b"}, {"source": "b", "target": "c"}])  # a->b->c
    state = _state(a="mastered", b="mastered", c="mastered")
    complete = _complete_node_ids(g, state)
    assert complete == {"a", "b", "c"}


def test_partial_chain_gates_downstream():
    g = _graph([{"source": "a", "target": "b"}, {"source": "b", "target": "c"}])
    state = _state(a="mastered", b="available", c="mastered")  # b missing in the middle
    complete = _complete_node_ids(g, state)
    assert complete == {"a"}            # a complete; b not mastered; c gated by b


def test_node_without_prereqs_completes_on_own_mastery():
    g = _graph([])
    state = _state(a="mastered")
    assert "a" in _complete_node_ids(g, state)


def test_cycle_guard_does_not_hang():
    g = _graph([{"source": "a", "target": "b"}, {"source": "b", "target": "a"}])  # a<->b cycle
    state = _state(a="mastered", b="mastered")
    complete = _complete_node_ids(g, state)              # must return, not recurse forever
    assert complete == set()                             # cyclic prereqs never resolve to complete


def test_display_status_blocks_mastered_with_pending_prereq():
    g = _graph([{"source": "a", "target": "b"}])
    state = _state(a="needs_review", b="mastered")
    ds = _display_status(g, state)
    assert ds["b"] == "blocked"          # passed its own exercise, but prereq a pending -> 🔒
    assert ds["a"] == "needs_review"     # underlying status untouched


def test_display_status_keeps_mastered_when_complete():
    g = _graph([{"source": "a", "target": "b"}])
    state = _state(a="mastered", b="mastered")
    ds = _display_status(g, state)
    assert ds["a"] == "mastered"
    assert ds["b"] == "mastered"


# --- access locking ---------------------------------------------------------------------------

def test_node_with_incomplete_prereq_is_locked():
    g = _graph([{"source": "a", "target": "b"}])      # a is prereq of b
    state = _state(a="available", b="available")
    locked = _locked_node_ids(g, state)
    assert "b" in locked                               # a not complete -> b locked
    assert "a" not in locked                           # root, no prereqs -> open


def test_root_and_completed_nodes_are_not_locked():
    g = _graph([{"source": "a", "target": "b"}])
    state = _state(a="mastered", b="available")        # a complete
    assert _locked_node_ids(g, state) == set()         # b's only prereq complete -> open


def test_downstream_of_unmastered_node_is_locked_transitively():
    g = _graph([{"source": "a", "target": "b"}, {"source": "b", "target": "c"}])  # a->b->c
    state = _state(a="mastered", b="available", c="available")
    locked = _locked_node_ids(g, state)
    assert "b" not in locked   # a complete -> b open
    assert "c" in locked       # b not complete -> c locked (transitive)


def test_locked_clears_once_chain_complete():
    g = _graph([{"source": "a", "target": "b"}, {"source": "b", "target": "c"}])
    state = _state(a="mastered", b="mastered", c="mastered")
    assert _locked_node_ids(g, state) == set()


def test_never_attempted_node_with_pending_prereq_displays_blocked():
    g = _graph([{"source": "a", "target": "b"}])
    state = _state(a="available", b="available")
    ds = _display_status(g, state)
    assert ds["b"] == "blocked"   # locked -> 🔒 even though never attempted
    assert ds["a"] == "available"  # root, openable


def test_incomplete_prereq_labels_lists_pending_prereqs():
    g = {
        "nodes": [{"id": "a", "label": "Alpha"}, {"id": "b", "label": "Beta"}],
        "edges": [{"source": "a", "target": "b"}],
    }
    state = {"a": {"status": "needs_review"}, "b": {"status": "available"}}
    assert _incomplete_prereq_labels(g, state, "b") == ["Alpha"]
