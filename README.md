# MindMorph Learning Platform

**Online courses give everyone the same path. MindMorph builds a different one per learner, and won't let you move on until you've proven you understand.**

A multi-agent learning platform built on LangGraph: 14 specialised agents compose into 6 graph workflows that research a topic, draft a personalised plan, teach it, set exercises, grade your code in the browser, and re-plan when you struggle.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![LangGraph](https://img.shields.io/badge/built%20with-LangGraph-1a1530)](https://langchain-ai.github.io/langgraph/)

---

## How it works

```mermaid
flowchart LR
    A["Learner goal"] --> B["Orchestrator"]
    B --> C["Scout · Market · Academic<br/>research the topic"]
    C --> D["learning_plan_graph<br/>drafts a personalised plan"]
    D --> E["lesson_graph<br/>Tutor teaches a unit"]
    E --> F["exercise_graph<br/>Exercise + Reviewer"]
    F --> G{"Mastery<br/>threshold met?"}
    G -->|no| H["skill_graph_adapt<br/>re-plans the weak skill"]
    H --> E
    G -->|yes| I["Next unit unlocked"]
```

**Progression is gated on demonstrated mastery, not on clicking Next.** `services/mastery.py` scores each attempt; the adaptation graph rewrites the plan around whatever you actually got wrong rather than repeating the same lesson.

**Code is graded live, in the browser.** `streamlit-ace` gives an editor, `tools/code_executor.py` runs the submission in a sandbox, and the Reviewer agent critiques the result — no copy-pasting into a separate terminal.

## Architecture notes

- **14 agents, one composition layer.** Agents in `agents/` are single-responsibility and know nothing about each other; `graph/` wires them into workflows. Adding a teaching strategy means adding a graph, not editing an agent.
- **The vector store is deliberately swappable.** Default is `InMemoryVectorStore` with local `fastembed` embeddings, so the platform runs with no vector-DB account and no embedding API cost. Set `MINDMORPH_STORE=postgres` and the same interface persists to pgvector. `rag/store.py` and `rag/pg_store.py` share one contract — callers never change.
- **Provider-agnostic LLM layer.** `llm_providers.py` resolves the model from `MINDMORPH_LLM_PROVIDER` with `MINDMORPH_LLM_FALLBACK` behind it, so a provider outage degrades instead of failing.
- **MCP as a tool transport.** `tools/github_mcp_client.py` talks to MCP servers via `langchain-mcp-adapters`, with an explicit timeout wrapper in `tools/mcp_timeout.py` — a hung tool call can't stall a graph.
- **Postgres is the system of record.** SQLAlchemy 2 models under `persistence/`, migrations via Alembic, FastAPI routes in `api/` for programmatic access alongside the Streamlit UI.

## Quickstart

```bash
git clone https://github.com/tarunlnmiit/MindMorph_Learning_Platform.git
cd MindMorph_Learning_Platform

python -m venv .venv && source .venv/bin/activate   # or: conda create -n mindmorph python=3.11 -y
pip install -r requirements.txt

docker compose up -d db          # Postgres 16 + pgvector, matches the default DATABASE_URL
echo "GROQ_API_KEY=your_key_here" > .env
alembic upgrade head

streamlit run app.py
```

Opens at `http://localhost:8501`. A Groq API key is the only credential required — embeddings run locally via `fastembed`, so there is no second key and no vector-database signup.

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | — | Required. LLM access |
| `DATABASE_URL` | `postgresql+psycopg://mindmorph:mindmorph@localhost:5432/mindmorph` | Matches `docker-compose.yml` |
| `MINDMORPH_LLM_PROVIDER` | Groq | Primary provider |
| `MINDMORPH_LLM_FALLBACK` | — | Provider used if the primary fails |
| `MINDMORPH_RAG` | on | Toggles retrieval grounding |
| `MINDMORPH_KNOWLEDGE_DIR` | `knowledge_base/` | Corpus loaded into the vector store at startup |

### Programmatic access

```bash
uvicorn api.main:app --reload      # FastAPI routes in api/routes.py
```

## Tests

```bash
pytest -q
```

## Project layout

| Path | What lives there |
|---|---|
| `agents/` | 14 single-responsibility agents — orchestrator, tutor, assessment, exercise, reviewer, consensus, synthesizer, scout, adaptation, factual, academic, practical, market, content_generator |
| `graph/` | 6 LangGraph workflows composing those agents |
| `rag/` | Embeddings, chunking, in-memory and pgvector stores |
| `services/` | Mastery scoring, completion, learning-service orchestration |
| `tools/` | Sandboxed code executor, MCP client, scrapers |
| `api/` | FastAPI layer |
| `persistence/` | SQLAlchemy models |
| `web/`, `app.py` | Streamlit UI |

## Status

Actively developed. `docs/ARCHITECTURE.md` describes a larger target architecture than what currently ships — treat that document as the roadmap and this README as what runs today.

## License

MIT — see [LICENSE](LICENSE).

---

*I turn scattered AI capabilities into tools people can actually run. · Available for AI contract work → [github.com/tarunlnmiit](https://github.com/tarunlnmiit)*
