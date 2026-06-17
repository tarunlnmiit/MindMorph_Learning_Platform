"""ClaudeCLIChatModel — driven entirely against a MOCKED subprocess so the suite never spawns the real
CLI (slow / non-deterministic / costs subscription usage). Proves command assembly, completion parsing,
and the JSON-in-prompt structured-output path (extract + validate + retry + raise)."""
import os
import subprocess
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from llm_providers import ClaudeCLIChatModel, _extract_json


class _Schema(BaseModel):
    name: str
    score: int


def _fake_run(stdout: str, returncode: int = 0, stderr: str = ""):
    captured = {}

    def run(cmd, input=None, capture_output=None, text=None, timeout=None):
        captured["cmd"] = cmd
        captured["input"] = input
        return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    run.captured = captured
    return run


def test_generate_returns_completion(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run("hello world"))
    out = ClaudeCLIChatModel(model="haiku").invoke([HumanMessage(content="hi")])
    assert out.content == "hello world"


def test_command_assembly_passes_system_and_stdin(monkeypatch):
    fake = _fake_run("ok")
    monkeypatch.setattr(subprocess, "run", fake)
    ClaudeCLIChatModel(model="sonnet").invoke(
        [SystemMessage(content="be terse"), HumanMessage(content="the question")]
    )
    cmd = fake.captured["cmd"]
    assert "--model" in cmd and cmd[cmd.index("--model") + 1] == "sonnet"
    assert "--strict-mcp-config" in cmd
    assert cmd[cmd.index("--system-prompt") + 1] == "be terse"
    assert fake.captured["input"] == "the question"  # human turn goes on stdin, not the system flag


def test_nonzero_exit_raises(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run("", returncode=1, stderr="boom"))
    with pytest.raises(RuntimeError):
        ClaudeCLIChatModel().invoke([HumanMessage(content="hi")])


def test_structured_output_parses_clean_json(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run('{"name": "x", "score": 9}'))
    runnable = ClaudeCLIChatModel().with_structured_output(_Schema)
    result = runnable.invoke([HumanMessage(content="give me one")])
    assert isinstance(result, _Schema) and result.name == "x" and result.score == 9


def test_structured_output_tolerates_prose_and_fences(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run",
        _fake_run('Sure!\n```json\n{"name": "y", "score": 3}\n```\nHope that helps.'),
    )
    result = ClaudeCLIChatModel().with_structured_output(_Schema).invoke([HumanMessage(content="q")])
    assert result.name == "y" and result.score == 3


def test_structured_output_retries_then_raises(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run("not json at all"))
    with pytest.raises(ValueError):
        ClaudeCLIChatModel().with_structured_output(_Schema).invoke([HumanMessage(content="q")])


def test_extract_json_balanced_span():
    assert _extract_json('prefix {"a": {"b": 1}} suffix') == {"a": {"b": 1}}


# --- Fallback model + factory -------------------------------------------------------------------

from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from llm_providers import FallbackChatModel


class _Boom(BaseChatModel):
    """A primary that always fails — both plain and structured calls raise."""
    @property
    def _llm_type(self):
        return "boom"

    def _generate(self, messages, stop=None, run_manager=None, **kw):
        raise RuntimeError("primary down")

    def with_structured_output(self, schema, **kw):
        def _raise(_):
            raise RuntimeError("primary down")
        return RunnableLambda(_raise)


class _Echo(BaseChatModel):
    """A fallback that succeeds; structured calls return a fixed schema instance."""
    @property
    def _llm_type(self):
        return "echo"

    def _generate(self, messages, stop=None, run_manager=None, **kw):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="from-fallback"))])

    def with_structured_output(self, schema, **kw):
        return RunnableLambda(lambda _: schema(name="fb", score=1))


def test_fallback_used_when_primary_generate_fails():
    fm = FallbackChatModel(primary=_Boom(), fallback=_Echo())
    assert fm.invoke([HumanMessage(content="x")]).content == "from-fallback"


def test_fallback_used_for_structured_output():
    fm = FallbackChatModel(primary=_Boom(), fallback=_Echo())
    result = fm.with_structured_output(_Schema).invoke([HumanMessage(content="x")])
    assert isinstance(result, _Schema) and result.name == "fb"


def test_primary_used_when_it_succeeds():
    fm = FallbackChatModel(primary=_Echo(), fallback=_Boom())
    assert fm.invoke([HumanMessage(content="x")]).content == "from-fallback"  # _Echo is primary here


def test_factory_none_returns_plain_groq(monkeypatch):
    # get_chat_model reads the env at call time, so no module reload is needed (and none leaks).
    monkeypatch.setenv("MINDMORPH_LLM_FALLBACK", "none")
    import config
    from langchain_groq import ChatGroq
    assert isinstance(config.get_chat_model("default"), ChatGroq)


def test_factory_claude_cli_wraps_in_fallback(monkeypatch):
    monkeypatch.setenv("MINDMORPH_LLM_FALLBACK", "claude_cli")
    import config
    m = config.get_chat_model("complex")
    assert isinstance(m, FallbackChatModel)
    assert m.fallback.model == "sonnet"  # complex tier → Sonnet on fallback
