"""Test-wide setup. Force the pure-Groq LLM path so the suite never wraps models in the Claude-CLI
fallback (which could spawn the real CLI). Set before any test imports `config`."""
import os

os.environ.setdefault("MINDMORPH_LLM_FALLBACK", "none")
