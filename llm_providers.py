"""Provider chain: a pool of Groq API keys tried in order, with local Ollama as the last resort.

Groq's free tier meters per key (30 req/min, 1K req/day, 8K tok/min, 200K tok/day for
``openai/gpt-oss-120b``), so N keys multiply the effective quota ~Nx. This module owns the rotation
policy; ``config.get_chat_model`` owns which members go into the chain.

Two failure classes, deliberately treated differently:

- **Transient / per-key** — rate limit (429), token-per-minute cap (Groq returns 413 on some paths),
  auth rejection (401/403), or a server blip. The *next key* may well succeed, so advance and retry.
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

logger = logging.getLogger(__name__)

# HTTP statuses where a *different key* is worth trying. Everything else is treated as permanent.
ROTATE_STATUSES = frozenset({401, 403, 408, 413, 429, 500, 502, 503, 529})


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

    def _fallback_or_raise(self, exc: Optional[Exception]):
        if self.fallback is None:
            raise exc if exc is not None else RuntimeError("llm: no provider available")
        return self.fallback

    # -- delegated surface ----------------------------------------------------------------------

    def invoke(self, *args, **kwargs):
        last: Optional[Exception] = None
        for index, member in enumerate(self.primary):
            try:
                return member.invoke(*args, **kwargs)
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
        for index, member in enumerate(self.primary):
            try:
                return await member.ainvoke(*args, **kwargs)
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
