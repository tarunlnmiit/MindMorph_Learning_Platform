# MindMorph Learning Platform

<!-- DEMO_GIF_PLACEHOLDER: drop a demo GIF/screen recording here -->

MindMorph turns a topic into a prerequisite-linked skill graph, generates each lesson on demand from
a creative LLM and a web-grounded factual agent running in parallel, and grades your work — code by
running its unit tests, case studies by an LLM rubric.

## How the skill graph builds and adapts

A LangGraph pipeline (Orchestrator → Scout → Academic/Market/Practical specialists → Consensus →
Reviewer) turns a topic into the initial skill graph. Each node's lesson is generated the first time
you open it, via a second DAG: a creative-writing agent and a web-grounded factual agent run in
parallel, a synthesizer merges their output, then example and visual generators fill it out.

Grading drives three deterministic outcomes, decided in Python, not the LLM:

- **Score ≥ 80** — mastered. Downstream nodes that depended on it unlock.
- **Score 40–79** — no graph change. You just retry the node.
- **Score < 40** — the node is locked and the graph grows: an LLM proposes remedial sub-skill nodes,
  which are inserted as new prerequisites beneath the failed node. Clearing them unlocks it again.

The LLM only ever proposes *what* to add. The thresholds and the lock itself are plain Python
(`services/mastery.py`). Adaptation is additive-only — it never renames, reorders, or deletes an
existing node, so a struggling learner never loses progress already made. That invariant is enforced
twice: as a prompt instruction, and mechanically in `apply_adaptation`
(`graph/skill_graph_adapt.py`), which drops edges pointing at unknown ids and refuses to overwrite an
existing node id. If the remediation LLM call fails outright, a `remediation_pending` flag still keeps
the failed node locked — it's never silently left open. Lock state itself isn't stored anywhere; it's
recomputed on every read from the graph plus mastery state (`services/completion.py`), so it can't
drift out of sync.

Code exercises are graded by running the submitted code's unit tests in a subprocess; non-Python
exercises and case studies fall back to LLM rubric grading.

See `docs/ARCHITECTURE.md` for the target design and `docs/IMPLEMENTATION_STATUS.md` for what's
actually built today — they diverge in places (e.g. Kafka/Kubernetes/Pinecone in the target design
aren't part of the running system). Tests: 203 passed, 3 skipped.

## Run it in two minutes

**No API key required.** The LLM is a local [Ollama](https://ollama.com) model — no vendor account,
no key, no infra beyond Ollama itself — no Docker, no Postgres, no Alembic, no build step. (Steps 1-4
below set up the environment; skip ahead if you already have one.)

1. `conda create -n mindmorph python=3.11 -y && conda activate mindmorph` (or a `venv` — see
   [Environment Setup](#environment-setup)).
2. [Install Ollama](https://ollama.com/download), then pull both tier models — a fast model for
   interactive beats (lesson generation, grading, tutor chat, routing) and a larger model for
   reasoning-heavy, once-per-session work (skill-graph consensus, review, scout planning):

    ```bash
    ollama pull qwen2.5:7b
    ollama pull qwen2.5:14b
    ```

3. `pip install -r requirements.txt`.
4. Run the backend against the in-memory store, then the frontend in another terminal:

    ```bash
    # Backend
    MINDMORPH_STORE=memory conda run -n mindmorph uvicorn api.main:app --port 8000

    # Frontend, in another terminal
    cd web && npm install && npm run dev   # http://localhost:3000
    ```

That's it — sessions live in memory for the process lifetime. See below for the durable
Postgres/RAG setup.

## Environment Setup

### 1. Prerequisites

Ensure you have [Conda](https://docs.conda.io/en/latest/) installed (Anaconda or Miniconda), or use a standard Python 3.11+ virtual environment. Also install [Ollama](https://ollama.com/download) and pull both tier models: `ollama pull qwen2.5:7b` (default/fast tier) and `ollama pull qwen2.5:14b` (complex/quality tier).

### 2. Create and Activate Virtual Environment

Using Conda:

```bash
# Create a new conda environment named 'mindmorph' with Python 3.11
conda create -n mindmorph python=3.11 -y

# Activate the environment
conda activate mindmorph
```

Or using venv:

```bash
# Unix/macOS
python -m venv .venv && source .venv/bin/activate
# Windows
python -m venv .venv && .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

No API key is required — the LLM runs locally via Ollama (`http://localhost:11434` by default), tiered
across two models: `qwen2.5:7b` for the default/fast tier (interactive beats — lesson generation,
grading, tutor chat, orchestrator routing) and `qwen2.5:14b` for the complex/quality tier
(reasoning-heavy, once-per-session work — skill-graph consensus, review, scout planning). Optionally
create a `.env` file to override either model, the host, or to add a LangSmith key for tracing:

```env
MINDMORPH_OLLAMA_MODEL=qwen2.5:7b
MINDMORPH_OLLAMA_MODEL_COMPLEX=qwen2.5:14b
MINDMORPH_OLLAMA_HOST=http://localhost:11434
```

## Running the App

MindMorph is a **Next.js** frontend (`web/`) over a **FastAPI** backend (`api/`). The legacy Streamlit
prototype was retired in P3 #12.

```bash
# 1. Backend (FastAPI) — zero-infra in-memory store for local dev
MINDMORPH_STORE=memory conda run -n mindmorph uvicorn api.main:app --port 8000
# (for durable Postgres + pgvector: docker compose up -d db && conda run -n mindmorph alembic upgrade head)

# 2. Frontend (Next.js), in another terminal
cd web && npm install && npm run dev   # http://localhost:3000
```

Optional: `MINDMORPH_RAG=1` enables knowledge-base grounding; `NEXT_PUBLIC_JUPYTERLITE_URL` overrides the
in-lesson scratchpad REPL.

## Running the Agents

- Run orchestrator (recommended first):
    - `python agents/orchestrator/orchestrator_agent.py`
- Run scout:
    - `python agents/scout/scout_agent.py`
- Run market:
    - `python agents/market/market_agent.py`
- Run github MCP client:
    - `python tools/github_mcp_client.py`

## Running the Content Generator

The Content Generator Agent allows you to generate educational content in different formats (Boost, Builder, Sprint).

To run the interactive agent:

```bash
python agents/content_generator/content_agent.py
```

### Usage

1.  Open `agents/content_generator/content_agent.py` in your editor.
2.  Scroll to the bottom of the file to the `__main__` block.
3.  Manually modify the `generate_content` call with your **Topic** and **Format** ("A", "B", or "C"):

    ```python
    # Format Options:
    # "A": 5-min Boost (Quick summary)
    # "B": 20-min Builder (Standard lesson)
    # "C": 2-hour Sprint (Deep dive)

    lesson = agent.generate_content("Your Topic Here", "A")
    ```

4.  Run the script:

    ```bash
    python agents/content_generator/content_agent.py
    ```
