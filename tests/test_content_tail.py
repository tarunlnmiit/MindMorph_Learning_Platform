"""Content-DAG §6.3 tail: example + visual generators → deterministic assembler. LLM-free (injected
fakes). Covers section assembly + order, graceful None degradation, the flag gate, and per-agent None."""
import os
import sys
from unittest.mock import MagicMock

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from graph.content_graph import build_content_graph


def _base_agents():
    content = MagicMock()
    content.generate_content.return_value = "DRAFT"
    factual = MagicMock()
    factual.gather_facts.return_value = "FACTS"
    synthesizer = MagicMock()
    synthesizer.synthesize.return_value = "LESSON BODY"
    return content, factual, synthesizer


@pytest.fixture(autouse=True)
def _tail_on(monkeypatch):
    monkeypatch.setenv("MINDMORPH_RICH_CONTENT", "1")


async def test_tail_assembles_body_example_and_visual_in_order(monkeypatch):
    content, factual, synthesizer = _base_agents()
    example = MagicMock()
    example.generate_example.return_value = "```js\nconst x = 1;\n```"
    visual = MagicMock()
    visual.generate_diagram.return_value = "```mermaid\nflowchart TD\nA-->B\n```"

    graph = build_content_graph(
        content=content, factual=factual, synthesizer=synthesizer, example=example, visual=visual
    )
    state = await graph.ainvoke({"user_query": "MERN routing", "format_type": "B",
                                 "path_context": "Learn the MERN stack"})

    final = state["final_content"]
    assert final.startswith("LESSON BODY")
    assert "## Worked example" in final and "const x = 1;" in final
    assert "## Visual overview" in final and "flowchart TD" in final
    # body before example before visual
    assert final.index("LESSON BODY") < final.index("## Worked example") < final.index("## Visual overview")
    # the example agent gets the synthesized body + path_context (language signal)
    example.generate_example.assert_called_once_with("LESSON BODY", "MERN routing", "Learn the MERN stack")


async def test_tail_degrades_when_an_agent_returns_none(monkeypatch):
    content, factual, synthesizer = _base_agents()
    example = MagicMock()
    example.generate_example.return_value = None  # example failed
    visual = MagicMock()
    visual.generate_diagram.return_value = "```mermaid\ngraph LR\nA-->B\n```"

    graph = build_content_graph(
        content=content, factual=factual, synthesizer=synthesizer, example=example, visual=visual
    )
    state = await graph.ainvoke({"user_query": "topic"})

    final = state["final_content"]
    assert final.startswith("LESSON BODY")
    assert "## Worked example" not in final          # omitted — None section skipped
    assert "## Visual overview" in final             # still assembled


async def test_flag_off_skips_tail(monkeypatch):
    monkeypatch.setenv("MINDMORPH_RICH_CONTENT", "0")
    content, factual, synthesizer = _base_agents()
    example = MagicMock()
    visual = MagicMock()

    graph = build_content_graph(
        content=content, factual=factual, synthesizer=synthesizer, example=example, visual=visual
    )
    state = await graph.ainvoke({"user_query": "topic"})

    assert state["final_content"] == "LESSON BODY"   # synthesizer output verbatim
    example.generate_example.assert_not_called()
    visual.generate_diagram.assert_not_called()


# --- agent unit behavior (no network) ----------------------------------------------------------

def test_example_agent_passes_path_context_to_prompt():
    from agents.example_generator.example_generator_agent import ExampleGeneratorAgent

    agent = ExampleGeneratorAgent(push_to_langsmith=False)
    agent.llm = MagicMock()
    agent.llm.invoke.return_value = MagicMock(content="```js\nx\n```")
    out = agent.generate_example("lesson text", "React hooks", path_context="Learn the MERN stack")
    assert out == "```js\nx\n```"
    sent = agent.llm.invoke.call_args[0][0]  # the formatted messages
    assert any("Learn the MERN stack" in str(getattr(m, "content", "")) for m in sent)


def test_example_agent_survives_braces_in_lesson():
    """Regression: a lesson with literal braces (JSX {count}, JS/dict literals) must not break
    format_messages — they're escaped, not treated as template vars (mirrors ContentAgent)."""
    from agents.example_generator.example_generator_agent import ExampleGeneratorAgent

    agent = ExampleGeneratorAgent(push_to_langsmith=False)
    agent.llm = MagicMock()
    agent.llm.invoke.return_value = MagicMock(content="```js\nx\n```")
    out = agent.generate_example(
        "useState returns [value, setter]; render {count} in JSX with {curly} braces",
        "React {hooks}", path_context="MERN {stack}",
    )
    assert out == "```js\nx\n```"  # did not raise KeyError on the braces


def test_visual_agent_rejects_unfenced_diagram():
    """A bare (unfenced) diagram is rejected — the frontend only renders fenced ```mermaid blocks."""
    from agents.visual_generator.visual_generator_agent import VisualGeneratorAgent

    agent = VisualGeneratorAgent(push_to_langsmith=False)
    agent.llm = MagicMock()
    agent.llm.invoke.return_value = MagicMock(content="flowchart TD\nA-->B")  # no ```mermaid fence
    assert agent.generate_diagram("lesson", "topic") is None


def test_example_agent_returns_none_on_error():
    from agents.example_generator.example_generator_agent import ExampleGeneratorAgent

    agent = ExampleGeneratorAgent(push_to_langsmith=False)
    agent.llm = MagicMock()
    agent.llm.invoke.side_effect = RuntimeError("boom")
    assert agent.generate_example("lesson", "topic") is None


def test_visual_agent_rejects_non_mermaid_output():
    from agents.visual_generator.visual_generator_agent import VisualGeneratorAgent

    agent = VisualGeneratorAgent(push_to_langsmith=False)
    agent.llm = MagicMock()
    # Looks like prose, not a diagram → discarded so the frontend never renders a broken block.
    agent.llm.invoke.return_value = MagicMock(content="Here is a description of the concept.")
    assert agent.generate_diagram("lesson", "topic") is None


def test_visual_agent_accepts_valid_mermaid():
    from agents.visual_generator.visual_generator_agent import VisualGeneratorAgent

    agent = VisualGeneratorAgent(push_to_langsmith=False)
    agent.llm = MagicMock()
    agent.llm.invoke.return_value = MagicMock(content="```mermaid\nflowchart TD\nA-->B\n```")
    out = agent.generate_diagram("lesson", "topic")
    assert out is not None and "flowchart TD" in out
