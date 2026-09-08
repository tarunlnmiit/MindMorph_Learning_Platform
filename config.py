import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()

# Local-only LLM: Ollama running qwen2.5:14b by default. No hosted vendor, no API key, no cross-vendor
# fallback — Groq (deprecated its Llama models out from under this project) and the Claude-CLI fallback
# were both ripped out. Constructing ChatOllama here doesn't touch the network (it connects lazily on
# first `.invoke()`), so importing this module stays offline/hermetic even with no daemon running.
OLLAMA_MODEL = os.getenv("MINDMORPH_OLLAMA_MODEL", "qwen2.5:14b")
OLLAMA_HOST = os.getenv("MINDMORPH_OLLAMA_HOST", os.getenv("OLLAMA_HOST", "http://localhost:11434"))
temperature_setting = 0.1

# Exactly one provider now. Kept as a tuple (not a bare string) so the unknown-provider error message
# in _build_model reads the same as before.
VALID_PROVIDERS = ("ollama",)


def _build_model(name: str, tier: str) -> ChatOllama:
    """Construct the chat model for a complexity tier. ``tier`` is accepted but unused: with a single
    local model there's nothing to route between (see get_chat_model's docstring)."""
    name = name.lower()
    if name != "ollama":
        raise ValueError(f"Unknown LLM provider {name!r}; valid: {', '.join(VALID_PROVIDERS)}")
    return ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_HOST, temperature=temperature_setting)


def get_chat_model(tier: str = "default", provider: str | None = None, fallback: str | None = None):
    """Return the chat model for a complexity tier.

    Signature kept stable — every agent module calls this — even though there is now exactly one
    provider (local Ollama) and no cross-vendor fallback:

    - ``tier`` used to pick Haiku vs Sonnet on the (now-deleted) Claude-CLI fallback side. It's a
      no-op today: "default" and "complex" both resolve to ``OLLAMA_MODEL``. Left in the signature so
      a future tier can map to a different local model (e.g. a bigger one for "complex") without
      touching every call site.
    - ``provider`` must be ``"ollama"`` (or unset) — anything else raises, same as before.
    - ``fallback`` is accepted for call-site compatibility but ignored: there is no second vendor to
      fall back to. Passing a value is not an error; it just has no effect.
    """
    primary_name = (provider or os.getenv("MINDMORPH_LLM_PROVIDER", "ollama")).lower()
    return _build_model(primary_name, tier)


# Default-tier model reused across agents via `from config import llm`.
llm = get_chat_model("default")

# RAG grounding (P1 #7). Opt-in: enabling it builds a local FastEmbed-backed vector store from
# KNOWLEDGE_DIR on first content-graph build (downloads the embedding model once). Off by default so
# dev/tests never trigger a model download; retrieval augments web search, never replaces it.
RAG_ENABLED = os.getenv("MINDMORPH_RAG", "0").lower() in ("1", "true", "yes")
KNOWLEDGE_DIR = os.getenv("MINDMORPH_KNOWLEDGE_DIR", "knowledge_base")

# Persistence (P1 #6). Default targets the local docker-compose Postgres (see docker-compose.yml);
# override via DATABASE_URL in .env for any other deployment. Kept as a default (not a hard raise) so
# the agent/test paths that never touch the DB still import config cleanly.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://mindmorph:mindmorph@localhost:5432/mindmorph",
)
