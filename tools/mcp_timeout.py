"""Bounded-await helper for MCP network calls.

MCP transports (streamable-http / SSE) can flap or go half-open and leave an
`await` blocked indefinitely. A surrounding ``try/except`` degrades on *errors*
but cannot catch a *hang*, so a single stalled connection wedges the whole
LangGraph fan-out (the fan-in node never fires). Wrapping every MCP network
await with :func:`with_mcp_timeout` bounds the blast radius: on timeout the
caller degrades to its normal "no data" value instead of blocking forever.
"""

import asyncio
import logging
import os
from typing import Awaitable, TypeVar

logger = logging.getLogger(__name__)

# Default bound (seconds) for any single MCP network round-trip.
DEFAULT_MCP_TIMEOUT_SECONDS: float = 20.0

T = TypeVar("T")


def mcp_timeout_seconds() -> float:
    """Resolve the MCP timeout at call time so MINDMORPH_MCP_TIMEOUT is honored
    even when set after import (e.g. in tests)."""
    return float(os.getenv("MINDMORPH_MCP_TIMEOUT", str(DEFAULT_MCP_TIMEOUT_SECONDS)))


async def with_mcp_timeout(coro: Awaitable[T], *, what: str) -> T:
    """Await ``coro`` with the configured MCP timeout.

    Re-raises :class:`asyncio.TimeoutError` so each caller can map it to its own
    degrade value (``None`` / ``[]``) and reset any reused client state.
    """
    timeout = mcp_timeout_seconds()
    try:
        return await asyncio.wait_for(coro, timeout)
    except asyncio.TimeoutError:
        logger.warning("MCP timeout after %ss: %s", timeout, what)
        raise
