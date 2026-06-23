"""Test-wide setup. Force the pure-Groq LLM path so the suite never wraps models in the Claude-CLI
fallback (which could spawn the real CLI). Set before any test imports `config`."""
import os

os.environ.setdefault("MINDMORPH_LLM_FALLBACK", "none")
# Default the §6.3 content tail OFF for the suite so building a content graph never fires the real
# example/visual LLM agents. test_content_tail.py opts back in (monkeypatch) to exercise the tail.
os.environ.setdefault("MINDMORPH_RICH_CONTENT", "0")
