import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

model_name = "llama-3.3-70b-versatile" 
temperature_setting = 0.1

if not os.getenv("GROQ_API_KEY"):
    raise ValueError("GROQ_API_KEY not found. Please check your .env file.")


# Selectable LLM vendors. Each builds a base chat model for a complexity tier.
VALID_PROVIDERS = ("groq", "claude_cli")


def _build_model(name: str, tier: str):
    """Construct a single-vendor chat model. ``tier`` selects the Claude model (Haiku/Sonnet);
    Groq is single-tier today."""
    name = name.lower()
    if name == "groq":
        return ChatGroq(model=model_name, temperature=temperature_setting)
    if name == "claude_cli":
        # Import here so the pure-Groq path (and the test suite) never imports the CLI provider.
        from llm_providers import TIER_MODEL, ClaudeCLIChatModel

        return ClaudeCLIChatModel(model=TIER_MODEL.get(tier, "haiku"))
    raise ValueError(f"Unknown LLM provider {name!r}; valid: {', '.join(VALID_PROVIDERS)}")


def get_chat_model(tier: str = "default", provider: str | None = None, fallback: str | None = None):
    """Return the chat model for a complexity tier — vendor-selectable, with a cross-vendor fallback.

    Two independent vendor choices (args override env, env overrides defaults):

    - **primary** — ``provider`` arg or ``MINDMORPH_LLM_PROVIDER`` env (default ``groq``).
    - **fallback** — ``fallback`` arg or ``MINDMORPH_LLM_FALLBACK`` env (default ``claude_cli``). Used
      ONLY when the primary call fails (e.g. a Groq TPM 413). ``none`` disables it; a fallback equal to
      the primary is skipped (no same-vendor fallback).

    Examples: default → Groq primary, Claude-CLI fallback. ``MINDMORPH_LLM_PROVIDER=claude_cli`` +
    ``MINDMORPH_LLM_FALLBACK=groq`` → Claude primary, Groq fallback. ``provider="claude_cli",
    fallback="none"`` → Claude only. ``MINDMORPH_LLM_FALLBACK=none`` → pure primary (the test suite uses
    this so behavior stays deterministic).

    ``tier`` selects the Claude model (Haiku for ``default``, Sonnet for ``complex``) on whichever side
    is Claude, letting reasoning-heavy agents opt into Sonnet.
    """
    primary_name = (provider or os.getenv("MINDMORPH_LLM_PROVIDER", "groq")).lower()
    fb_name = (fallback or os.getenv("MINDMORPH_LLM_FALLBACK", "claude_cli")).lower()

    primary = _build_model(primary_name, tier)
    if fb_name in ("none", primary_name):
        return primary

    from llm_providers import FallbackChatModel

    return FallbackChatModel(primary=primary, fallback=_build_model(fb_name, tier))


# Default-tier model reused across agents via `from config import llm`.
llm = get_chat_model("default")

# Persistence (P1 #6). Default targets the local docker-compose Postgres (see docker-compose.yml);
# override via DATABASE_URL in .env for any other deployment. Kept as a default (not a hard raise) so
# the agent/test paths that never touch the DB still import config cleanly.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://mindmorph:mindmorph@localhost:5432/mindmorph",
)
