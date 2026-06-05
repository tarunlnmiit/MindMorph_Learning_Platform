"""Lesson graph: composes content -> exercise sequentially for a single clicked skill node.

Both sub-graphs are mocked. The two invariants under test:
  1. content then exercise populate the lesson state.
  2. the query handed to BOTH sub-graphs is the clicked node's `label: description`,
     NOT the learner's original top-level query (the easiest thing to get wrong).
"""
import os
import sys
from unittest.mock import AsyncMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from graph.lesson_graph import build_lesson_graph


def _mock_subgraphs():
    content_graph = AsyncMock()
    content_graph.ainvoke.return_value = {"final_content": "LESSON BODY"}
    exercise_graph = AsyncMock()
    exercise_graph.ainvoke.return_value = {
        "exercise_format": "coding_challenge",
        "exercise_statement": "Implement factorial.",
        "grading_artifact": {"unit_tests": ["assert factorial(3) == 6"]},
    }
    return content_graph, exercise_graph


async def test_lesson_graph_populates_content_then_exercise():
    content_graph, exercise_graph = _mock_subgraphs()
    graph = build_lesson_graph(content_graph=content_graph, exercise_graph=exercise_graph)

    state = await graph.ainvoke(
        {
            "skill_label": "Recursion",
            "skill_description": "Functions that call themselves",
            "format_type": "A",
        }
    )

    assert state["content"] == "LESSON BODY"
    assert state["exercise_format"] == "coding_challenge"
    assert state["exercise_statement"] == "Implement factorial."
    assert state["grading_artifact"] == {"unit_tests": ["assert factorial(3) == 6"]}


async def test_lesson_query_is_clicked_node_not_top_query():
    content_graph, exercise_graph = _mock_subgraphs()
    graph = build_lesson_graph(content_graph=content_graph, exercise_graph=exercise_graph)

    await graph.ainvoke(
        {
            "skill_label": "Recursion",
            "skill_description": "Functions that call themselves",
            "format_type": "B",
            # A top-level query a naive impl might leak in — it must NOT be used.
            "skill_query": None,
        }
    )

    expected_query = "Recursion: Functions that call themselves"
    content_payload = content_graph.ainvoke.call_args.args[0]
    exercise_payload = exercise_graph.ainvoke.call_args.args[0]
    assert content_payload["user_query"] == expected_query
    assert content_payload["format_type"] == "B"
    assert exercise_payload["user_query"] == expected_query


async def test_lesson_threads_prior_weaknesses_into_content_feedback():
    content_graph, exercise_graph = _mock_subgraphs()
    graph = build_lesson_graph(content_graph=content_graph, exercise_graph=exercise_graph)

    await graph.ainvoke(
        {
            "skill_label": "Recursion",
            "skill_description": "Functions that call themselves",
            "prior_weaknesses": ["base case", "stack depth"],
        }
    )

    content_payload = content_graph.ainvoke.call_args.args[0]
    assert content_payload["prior_feedback"] == "base case, stack depth"


async def test_lesson_prior_feedback_none_when_no_weaknesses():
    content_graph, exercise_graph = _mock_subgraphs()
    graph = build_lesson_graph(content_graph=content_graph, exercise_graph=exercise_graph)

    await graph.ainvoke(
        {"skill_label": "Recursion", "skill_description": "Functions that call themselves"}
    )

    content_payload = content_graph.ainvoke.call_args.args[0]
    assert content_payload["prior_feedback"] is None
