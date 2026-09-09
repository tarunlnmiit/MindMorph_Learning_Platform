"""Provider chain: a pool of Groq API keys tried in order, with local Ollama as the last resort.

Groq's free tier meters per key (30 req/min, 1K req/day, 8K tok/min, 200K tok/day for
``openai/gpt-oss-120b``), so N keys multiply the effective quota ~Nx. This module owns the rotation
policy; ``config.get_chat_model`` owns which members go into the chain.

Three failure classes, deliberately treated differently:

- **Transient / per-key** — rate limit (429), token-per-minute cap (Groq returns 413 on some paths),
  auth rejection (401/403), or a server blip. The *next key* may well succeed, so advance and retry.
- **Transient / per-sample** — a structured-output parse failure (``OutputParserException``, which is
  what ``with_structured_output(..., method="json_schema")`` raises when the model's JSON doesn't
  validate). The completion arrived fine; only this *sample* was malformed. A different key runs the
  same model, so rotating is pointless — instead re-sample on the *same* member a bounded number of
  times. Before this existed, one bad Scout sample was misread as permanent and cost ~60s by
  abandoning the whole Groq pool for local Ollama.
- **Permanent / config** — above all 404 model-not-found. Every key will fail identically, so retrying
  across the pool just burns latency and hides the bug. This is the exact failure that silently
  degraded this project when Groq deprecated its Llama models, so it logs at ERROR and goes straight
  to the fallback.

Deliberately NOT a ``BaseChatModel`` subclass: the members already emit LangChain callbacks, so
wrapping them in a chat model would fire ``on_llm_end`` twice and double-count in ``services.cost``.
It is a thin facade over the surface the app actually uses — ``invoke`` / ``ainvoke`` /
``with_structured_output``.
"""
import logging
from typing import Any, Optional

import pydantic
from langchain_core.exceptions import OutputParserException

logger = logging.getLogger(__name__)

# HTTP statuses where a *different key* is worth trying. Everything else is treated as permanent.
ROTATE_STATUSES = frozenset({401, 403, 408, 413, 429, 500, 502, 503, 529})

# Parse/validation failures — retried on the SAME member, never used to widen the retryable set.
# LangChain's PydanticOutputParser already wraps pydantic's ValidationError into an
# OutputParserException, so the second entry is belt-and-braces for any caller that parses itself.
PARSE_EXCEPTIONS = (OutputParserException, pydantic.ValidationError)

# Extra attempts on the same member after a parse failure. One is enough: at temperature 0.1 a
# re-sample is genuinely different, and the fallback provider is still there if it isn't.
PARSE_RETRIES = 1


def _is_parse_failure(exc: Exception) -> bool:
    return isinstance(exc, PARSE_EXCEPTIONS)


def _status_code(exc: Exception) -> Optional[int]:
    """Best-effort HTTP status from a Groq/openai-shaped SDK exception.

    Only 429/401/404 get named exception classes; TPM-limit 413s arrive as a generic
    ``APIStatusError``, so key off the status code, not the type.
    """
    code = getattr(exc, "status_code", None)
    if code is None:
        code = getattr(getattr(exc, "response", None), "status_code", None)
    try:
        return int(code) if code is not None else None
    except (TypeError, ValueError):
        return None


class ProviderChain:
    """Calls ``primary`` members in order, advancing on transient errors; then ``fallback``.

    ``primary`` is one member per API key (same vendor, same model). ``fallback`` is the zero-key
    local model, or ``None`` to re-raise instead.
    """

    def __init__(self, primary: list[Any], fallback: Any = None) -> None:
        self.primary = list(primary)
        self.fallback = fallback

    # -- rotation policy ------------------------------------------------------------------------

    def _handle(self, index: int, exc: Exception) -> bool:
        """Log the failure and report whether to try the next key."""
        code = _status_code(exc)
        position = f"key {index + 1}/{len(self.primary)}"
        if _is_parse_failure(exc):
            # Re-sampling already failed (see _invoke_member). Another key runs the same model, so
            # rotating would just repeat it — go to the fallback. Not a config error: WARNING, not
            # ERROR, so this stays visibly distinct from the 404 case below.
            logger.warning(
                "llm: %s returned unparseable structured output %d times (%s) — falling back",
                position, PARSE_RETRIES + 1, type(exc).__name__,
            )
            return False
        if code in ROTATE_STATUSES:
            logger.warning("llm: %s failed with HTTP %s (%s) — rotating to next key", position, code, type(exc).__name__)
            return True
        logger.error(
            "llm: %s failed permanently with HTTP %s — NOT rotating, falling back. "
            "A 404 here means the model id is wrong or deprecated; fix the config, "
            "the other keys will fail identically. (%s: %s)",
            position, code, type(exc).__name__, exc,
        )
        return False

    def _log_resample(self, index: int, exc: Exception) -> None:
        logger.warning(
            "llm: key %d/%d returned unparseable structured output (%s) — re-sampling the same key",
            index + 1, len(self.primary), type(exc).__name__,
        )

    def _invoke_member(self, index: int, args, kwargs):
        """One member, with bounded same-member retries on a parse failure.

        No backoff between attempts: a parse failure carries no server-side rate state to wait out,
        and a sleep would add latency to exactly the path this retry exists to keep fast.
        """
        for attempt in range(PARSE_RETRIES + 1):
            try:
                return self.primary[index].invoke(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - re-raised unless it is a retryable parse failure
                if attempt < PARSE_RETRIES and _is_parse_failure(exc):
                    self._log_resample(index, exc)
                    continue
                raise

    async def _ainvoke_member(self, index: int, args, kwargs):
        """Async twin of ``_invoke_member``."""
        for attempt in range(PARSE_RETRIES + 1):
            try:
                return await self.primary[index].ainvoke(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - re-raised unless it is a retryable parse failure
                if attempt < PARSE_RETRIES and _is_parse_failure(exc):
                    self._log_resample(index, exc)
                    continue
                raise

    def _fallback_or_raise(self, exc: Optional[Exception]):
        if self.fallback is None:
            raise exc if exc is not None else RuntimeError("llm: no provider available")
        return self.fallback

    # -- delegated surface ----------------------------------------------------------------------

    def invoke(self, *args, **kwargs):
        last: Optional[Exception] = None
        for index in range(len(self.primary)):
            try:
                return self._invoke_member(index, args, kwargs)
            except Exception as exc:  # noqa: BLE001 - classified by status code below
                last = exc
                if not self._handle(index, exc):
                    break
        else:
            if self.primary:
                logger.warning("llm: all %d keys exhausted — falling back", len(self.primary))
        return self._fallback_or_raise(last).invoke(*args, **kwargs)

    async def ainvoke(self, *args, **kwargs):
        last: Optional[Exception] = None
        for index in range(len(self.primary)):
            try:
                return await self._ainvoke_member(index, args, kwargs)
            except Exception as exc:  # noqa: BLE001 - classified by status code below
                last = exc
                if not self._handle(index, exc):
                    break
        else:
            if self.primary:
                logger.warning("llm: all %d keys exhausted — falling back", len(self.primary))
        return await self._fallback_or_raise(last).ainvoke(*args, **kwargs)

    async def astream(self, *args, **kwargs):
        """Stream tokens, rotating only on a failure that happens *before* the first token.

        Once tokens have reached the caller the reply is half-delivered; restarting on another key
        would duplicate text, so a mid-stream error propagates.

        No parse-retry here: only the tutor streams, and it streams plain text — nothing streamed is
        a structured-output model, so there is no parse failure to re-sample.
        """
        last: Optional[Exception] = None
        for index, member in enumerate(self.primary):
            started = False
            try:
                async for chunk in member.astream(*args, **kwargs):
                    started = True
                    yield chunk
                return
            except Exception as exc:  # noqa: BLE001 - classified by status code below
                if started:
                    raise
                last = exc
                if not self._handle(index, exc):
                    break
        else:
            if self.primary:
                logger.warning("llm: all %d keys exhausted — falling back", len(self.primary))
        async for chunk in self._fallback_or_raise(last).astream(*args, **kwargs):
            yield chunk

    def with_structured_output(self, *args, **kwargs) -> "ProviderChain":
        """Map structured output over every member so the fallback keeps the schema too."""
        return ProviderChain(
            [m.with_structured_output(*args, **kwargs) for m in self.primary],
            self.fallback.with_structured_output(*args, **kwargs) if self.fallback is not None else None,
        )
