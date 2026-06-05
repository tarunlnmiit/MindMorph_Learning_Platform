## Environment

ALWAYS use the `mindmorph` conda environment for every command in this project — running
Python, pip installs, pytest, streamlit, anything. Never use base.
- Run one-off commands with `conda run -n mindmorph <cmd>` (e.g. `conda run -n mindmorph python -m pytest -q`).
- Install deps into it: `conda run -n mindmorph pip install <pkg>` (then add to `requirements.txt`).

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- ALWAYS read graphify-out/GRAPH_REPORT.md before reading any source files, running grep/glob searches, or answering codebase questions. The graph is your primary map of the codebase.
- IF graphify-out/wiki/index.md EXISTS, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
