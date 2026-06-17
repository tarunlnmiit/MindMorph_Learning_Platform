"""Placeholder LLM backend: the locally-installed Claude Code CLI driven headless as a chat model.

Used as a **fallback** when the primary (Groq) call fails — e.g. a free-tier TPM rate limit (413).
There is no Anthropic API key here; the CLI runs against the user's local Claude Code OAuth session, so
this is a **local-development placeholder only** (not deployable). When a real key is available, swap
this for ``langchain-anthropic``'s ``ChatAnthropic`` and delete this module — the agents are unchanged.

The CLI has no LangChain tool-calling path, so ``with_structured_output`` is implemented by injecting the
target JSON schema into the prompt and parsing the model's JSON reply (with one retry).
"""
import json
import logging
import re
import subprocess
from typing import Any, Optional, Type

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Map our tier names to the CLI's short model aliases (it resolves them to the concrete dated ids).
TIER_MODEL = {"default": "haiku", "complex": "sonnet"}


class ClaudeCLIChatModel(BaseChatModel):
    """A chat model that shells out to ``claude -p`` for each completion.

    Isolated + fast: ``--strict-mcp-config`` with an empty server set means the user's MCP servers are
    not loaded. System messages go via ``--system-prompt``; the remaining turns are sent on stdin.
    """

    model: str = "haiku"
    timeout_s: int = 180

    @property
    def _llm_type(self) -> str:
        return "claude-cli"

    # --- core completion -----------------------------------------------------------------------
    def _run_cli(self, system: str, prompt: str) -> str:
        cmd = [
            "claude", "-p",
            "--model", self.model,
            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--output-format", "text",
        ]
        if system:
            cmd += ["--system-prompt", system]
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True, timeout=self.timeout_s
        )
        if proc.returncode != 0:
            raise RuntimeError(f"claude CLI exited {proc.returncode}: {proc.stderr.strip()[:500]}")
        return proc.stdout.strip()

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        system = "\n\n".join(m.content for m in messages if isinstance(m, SystemMessage))
        prompt = "\n\n".join(
            str(m.content) for m in messages if not isinstance(m, SystemMessage)
        )
        text = self._run_cli(system, prompt)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    # --- structured output (no tool-calling on the CLI ⇒ JSON-in-prompt + parse) ---------------
    def with_structured_output(
        self, schema: Type[BaseModel], **kwargs: Any
    ) -> Runnable:
        """Return a runnable that yields a validated ``schema`` instance.

        Appends the JSON schema + a "JSON only" instruction to the prompt, parses the reply, and
        validates it. One retry on parse/validate failure; if it still fails, raises — so that under
        ``with_fallbacks`` the failure surfaces and callers' existing ``try/except → None`` applies.
        """
        json_schema = schema.model_json_schema()
        instruction = (
            "Respond with ONLY a single JSON object that conforms to this JSON Schema. "
            "No prose, no explanation, no markdown code fences.\n\nJSON Schema:\n"
            + json.dumps(json_schema)
        )

        def _invoke(messages: Any) -> BaseModel:
            msgs = _as_messages(messages)
            msgs = msgs + [SystemMessage(content=instruction)]
            last_err: Optional[Exception] = None
            for attempt in range(2):
                text = self.invoke(msgs).content
                try:
                    return schema.model_validate(_extract_json(text))
                except Exception as e:  # parse or validation failure
                    last_err = e
                    logger.warning("claude-cli structured output parse failed (attempt %d): %s", attempt + 1, e)
            raise ValueError(f"claude-cli structured output did not match {schema.__name__}: {last_err}")

        return RunnableLambda(_invoke)


class FallbackChatModel(BaseChatModel):
    """Primary chat model with a secondary used ONLY when the primary call fails.

    Wraps the primary (Groq) and a fallback (Claude CLI): a primary failure — rate limit (413),
    timeout, any exception — transparently retries on the fallback. ``with_structured_output`` composes
    via LangChain's ``Runnable.with_fallbacks`` so the same primary→fallback behavior applies to the
    structured-output path the agents rely on.
    """

    primary: BaseChatModel
    fallback: BaseChatModel

    @property
    def _llm_type(self) -> str:
        return "fallback"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        try:
            return self.primary._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        except Exception as e:
            logger.warning("primary LLM failed (%s) — falling back to %s", e, self.fallback._llm_type)
            return self.fallback._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Runnable:
        return self.primary.with_structured_output(schema, **kwargs).with_fallbacks(
            [self.fallback.with_structured_output(schema, **kwargs)]
        )


def _as_messages(value: Any) -> list[BaseMessage]:
    """Normalize with_structured_output input (PromptValue | list[BaseMessage] | str) to messages."""
    if hasattr(value, "to_messages"):
        return list(value.to_messages())
    if isinstance(value, list):
        return list(value)
    from langchain_core.messages import HumanMessage

    return [HumanMessage(content=str(value))]


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a CLI reply (tolerates stray prose / ``` fences)."""
    s = text.strip()
    # Strip a leading/trailing markdown code fence if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.DOTALL)
    if fence:
        s = fence.group(1).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Fall back to the first balanced {...} span.
    start = s.find("{")
    if start == -1:
        raise ValueError("no JSON object in CLI reply")
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(s[start : i + 1])
    raise ValueError("unbalanced JSON object in CLI reply")
