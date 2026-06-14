import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

model_name = "llama-3.3-70b-versatile" 
temperature_setting = 0.1

if not os.getenv("GROQ_API_KEY"):
    raise ValueError("GROQ_API_KEY not found. Please check your .env file.")


def get_chat_model(tier: str = "default"):
    """Return the chat model for a complexity tier.

    Groq is always primary. When ``MINDMORPH_LLM_FALLBACK`` is ``claude_cli`` (the default), a primary
    failure (e.g. a Groq TPM rate-limit 413) transparently falls back to the local Claude Code CLI —
    Haiku for the ``default`` tier, Sonnet for ``complex``. Set ``MINDMORPH_LLM_FALLBACK=none`` for a
    pure-Groq model (used by the test suite so behavior is unchanged there).

    ``tier`` only affects the fallback model today (the primary Groq model is single-tier); it lets
    reasoning-heavy agents opt into Sonnet-on-fallback.
    """
    primary = ChatGroq(model=model_name, temperature=temperature_setting)
    if os.getenv("MINDMORPH_LLM_FALLBACK", "claude_cli").lower() == "none":
        return primary
    # Import here so the test suite / pure-Groq path never imports the CLI provider.
    from llm_providers import TIER_MODEL, ClaudeCLIChatModel, FallbackChatModel

    fallback = ClaudeCLIChatModel(model=TIER_MODEL.get(tier, "haiku"))
    return FallbackChatModel(primary=primary, fallback=fallback)


# Default-tier model reused across agents via `from config import llm`.
llm = get_chat_model("default")

# Persistence (P1 #6). Default targets the local docker-compose Postgres (see docker-compose.yml);
# override via DATABASE_URL in .env for any other deployment. Kept as a default (not a hard raise) so
# the agent/test paths that never touch the DB still import config cleanly.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://mindmorph:mindmorph@localhost:5432/mindmorph",
)
