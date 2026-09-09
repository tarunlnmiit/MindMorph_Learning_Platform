# MindMorph Learning Platform

**Online courses give everyone the same path. MindMorph builds a different one per learner, and won't let you move on until you've proven you understand.**

A multi-agent learning platform built on LangGraph: 16 specialised agents compose into 6 graph workflows that research a topic, draft a personalised skill graph, teach each unit on demand, set exercises, grade your work, and grow the graph around whatever you actually got wrong.

<!-- DEMO_GIF_PLACEHOLDER: drop a demo GIF/screen recording here -->

Captured footage of the adaptive rewire in action: `docs/media/rewire_demo.mp4` (before/after stills:
`rewire_before.png`, `rewire_after.png`).

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![LangGraph](https://img.shields.io/badge/built%20with-LangGraph-1a1530)](https://langchain-ai.github.io/langgraph/)

---

## How it works

```mermaid
flowchart LR
    A["Learner goal"] --> B["Orchestrator"]
    B --> C["Scout · Academic · Market · Practical<br/>research the topic"]
    C --> D["Consensus · Reviewer<br/>drafts the skill graph"]
    D --> E["lesson_graph<br/>Tutor teaches a unit"]
    E --> F["exercise_graph<br/>Exercise + grading"]
    F --> G{"Mastery<br/>threshold met?"}
    G -->|"score < 40"| H["skill_graph_adapt<br/>inserts remedial nodes"]
    H --> E
    G -->|"score 40-79"| E
    G -->|"score >= 80"| I["Next unit unlocked"]
```

**Progression is gated on demonstrated mastery, not on clicking Next.** `services/mastery.py` scores
each attempt, and the outcome is decided in Python, not the LLM:

- **Score ≥ 80** — mastered. Downstream nodes that depended on it unlock.
- **Score 40–79** — a deliberate no-op. You just retry the node.
- **Score < 40** — the node is locked and the graph grows: an LLM proposes remedial sub-skill nodes,
  inserted as new prerequisites beneath the failed node. Clearing them unlocks it again.

The LLM only ever proposes *what* to add. Adaptation is additive-only — it never renames, reorders, or
deletes an existing node, so a struggling learner never loses progress already made. That invariant is
enforced twice: as a prompt instruction, and mechanically in `apply_adaptation`
(`graph/skill_graph_adapt.py`), which drops edges pointing at unknown ids and refuses to overwrite an
existing node id. If the remediation LLM call fails outright, a `remediation_pending` flag still keeps
the failed node locked — it's never silently left open. Lock state itself isn't stored anywhere; it's
recomputed on every read from the graph plus mastery state (`services/completion.py`), so it can't drift
out of sync.

**Code is graded live, in the browser.** A Monaco editor (`web/components/CodeEditor.tsx`) collects the
submission, `tools/code_executor.py` runs its unit tests in a sandboxed subprocess, and the Reviewer
agent critiques the result — no copy-pasting into a separate terminal. Non-Python exercises and case
studies fall back to LLM rubric grading. A separate, optional in-browser JupyterLite scratchpad
(`web/components/Sandbox.tsx`) is for free experimentation only — the graded submission always goes
through the editor above.

## Architecture notes

- **16 agents, one composition layer.** Agents in `agents/` are single-responsibility and know nothing
  about each other; `graph/` wires them into 6 workflows. Adding a teaching strategy means adding a
  graph, not editing an agent.
- **The vector store is deliberately swappable.** Default is `InMemoryVectorStore` with local `fastembed`
  embeddings, so the platform runs with no vector-DB account and no embedding API cost. Set
  `MINDMORPH_STORE=postgres` and the same interface persists to pgvector. `rag/store.py` and
  `rag/pg_store.py` share one contract — callers never change.
- **Local by default, no API key.** `llm_providers.py` resolves the model from `MINDMORPH_LLM_PROVIDER`,
  which defaults to a local [Ollama](https://ollama.com) install — `qwen2.5:7b` for interactive beats
  (lesson generation, grading, tutor chat, orchestrator routing) and `qwen2.5:14b` for reasoning-heavy,
  once-per-session work (skill-graph consensus, review, scout planning). Hosted providers are supported
  as an opt-in fallback, not a requirement.
- **MCP as a tool transport.** `tools/github_mcp_client.py` talks to MCP servers via
  `langchain-mcp-adapters`, with an explicit timeout wrapper in `tools/mcp_timeout.py` — a hung tool call
  can't stall a graph.
- **Postgres is the system of record when durability is on.** SQLAlchemy 2 models under `persistence/`,
  migrations via Alembic, FastAPI routes in `api/`. For local dev, `MINDMORPH_STORE=memory` skips all of
  that and keeps sessions in memory for the process lifetime.

## Run it in two minutes

**No API key required.** The LLM is a local Ollama model — no vendor account, no key, no infra beyond
Ollama itself, no Docker, no Postgres, no Alembic, no build step to start.

```bash
git clone https://github.com/tarunlnmiit/MindMorph_Learning_Platform.git
cd MindMorph_Learning_Platform

conda create -n mindmorph python=3.11 -y && conda activate mindmorph   # or: python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Install Ollama (https://ollama.com/download), then pull both tier models
ollama pull qwen2.5:7b
ollama pull qwen2.5:14b

# Backend — zero-infra in-memory store
MINDMORPH_STORE=memory conda run -n mindmorph uvicorn api.main:app --port 8000

# Frontend, in another terminal
cd web && npm install && npm run dev
```

Opens at `http://localhost:3000`. Sessions live in memory for the process lifetime; see below for the
durable Postgres/RAG setup.

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `MINDMORPH_OLLAMA_MODEL` | `qwen2.5:7b` | Fast tier — interactive beats |
| `MINDMORPH_OLLAMA_MODEL_COMPLEX` | `qwen2.5:14b` | Quality tier — reasoning-heavy, once-per-session work |
| `MINDMORPH_OLLAMA_HOST` | `http://localhost:11434` | Ollama endpoint |
| `MINDMORPH_STORE` | `memory` | `memory` for zero-infra dev, `postgres` for the durable store |
| `DATABASE_URL` | `postgresql+psycopg://mindmorph:mindmorph@localhost:5432/mindmorph` | Matches `docker-compose.yml`, used when `MINDMORPH_STORE=postgres` |
| `MINDMORPH_RAG` | off | Toggles knowledge-base retrieval grounding |
| `MINDMORPH_KNOWLEDGE_DIR` | `knowledge_base/` | Corpus loaded into the vector store at startup |
| `NEXT_PUBLIC_JUPYTERLITE_URL` | hosted JupyterLite demo | Overrides the in-lesson scratchpad REPL |

For the durable path: `docker compose up -d db && conda run -n mindmorph alembic upgrade head`, then
start the backend without `MINDMORPH_STORE=memory`.

### Programmatic access

```bash
uvicorn api.main:app --reload      # FastAPI routes in api/routes.py
```

## Tests

```bash
MINDMORPH_STORE=memory conda run -n mindmorph python -m pytest tests/ -q
```

## Project layout

| Path | What lives there |
|---|---|
| `agents/` | 16 single-responsibility agents — orchestrator, scout, academic, market, practical, consensus, reviewer, tutor, assessment, exercise, adaptation, content_generator, example_generator, visual_generator, synthesizer, factual |
| `graph/` | 6 LangGraph workflows composing those agents |
| `rag/` | Embeddings, chunking, in-memory and pgvector stores |
| `services/` | Mastery scoring, completion, learning-service orchestration |
| `tools/` | Sandboxed code executor, MCP client, scrapers |
| `api/` | FastAPI layer |
| `persistence/` | SQLAlchemy models |
| `web/` | Next.js frontend — Monaco editor, JupyterLite scratchpad |

## Status

Actively developed, single-user, no auth, no deployment story yet. `docs/ARCHITECTURE.md` describes a
larger target architecture (Kafka, Kubernetes, Pinecone, multi-tenant) than what currently ships — treat
that document as the roadmap, `docs/IMPLEMENTATION_STATUS.md` as what's actually built, and this README
as what runs today.

## License

MIT — see [LICENSE](LICENSE).

---

*I turn scattered AI capabilities into tools people can actually run. · Available for AI contract work → [github.com/tarunlnmiit](https://github.com/tarunlnmiit)*
