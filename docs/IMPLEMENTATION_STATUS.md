# MindMorph — Implementation Status & Roadmap

> Companion to [`ARCHITECTURE.md`](./ARCHITECTURE.md) (the target design).
> This document maps the **target architecture** to **what the code actually does today**,
> then lays out a prioritized roadmap.
> **Naming:** product = **MindMorph** (the source PDFs called it "SmartLearn" — older name; no live
> discrepancy).

**Status legend:** ✅ Done · 🟡 Partial / stub · ⛔ Planned (not in code)

---

## 1. Current Architecture vs Target

| | Today (as built) | Target (per architecture docs) |
|---|---|---|
| **Agent orchestration** | **LangGraph** state graph (`graph/learning_plan_graph.py`, `graph/content_graph.py`) — Learning-Plan + Content DAGs. CrewAI deferred (parallel LangGraph nodes used instead) | **LangGraph + CrewAI** — LangGraph state-graph/DAG control + CrewAI role-based specialist crews |
| **Grounding / web search** | Live DuckDuckGo (`ddgs`) in the Content dual-path Factual agent | RAG pipelines + agentic web search (Playwright/Firecrawl) |
| **LLM** | Single vendor: Groq `llama-3.3-70b-versatile` (`config.py`) | Multi-vendor **Model Router** (GPT, Claude, Gemini, Bedrock) |
| **Frontend** | Streamlit (`app.py`) | Next.js 14 / React 18 + JupyterLite |
| **Backend** | None (logic runs in Streamlit process) | FastAPI microservices + Celery/Redis workers |
| **Memory / data** | None (stateless per run) | Pinecone (long-term) + Redis (short-term) + PostgreSQL + S3 |
| **Grounding / RAG** | None | RAG pipelines + agentic web search (Playwright/Firecrawl) |
| **Observability** | LangSmith hooks (optional) | Prometheus/Grafana/OpenTelemetry + Prompt Registry feedback loop |

The repo is a **working multi-agent prototype** with **P0 complete**: the Learning-Plan DAG
(orchestrate → scout → academic/market/practical → consensus → reviewer → Skill Dependency Graph)
and the dual-path Content DAG (creative + live web grounding → synthesizer) both run end-to-end on
LangGraph. Still open: CrewAI (deferred), Exercise DAG + grading, persistence, RAG/Model Router,
backend, and infra (see roadmap below).

---

## 2. Status by Agent (Learning-Plan DAG)

| Agent / Step (target) | Status | Code path | Notes |
|---|---|---|---|
| Orchestrator Agent (route SCOUT/CONTENT/EXERCISE) | ✅ | `agents/orchestrator/orchestrator_agent.py` | Structured output; routes inside the LangGraph graph (`graph/learning_plan_graph.py`). SCOUT + CONTENT wired; EXERCISE → placeholder node. |
| Scout Agent (decompose → Academic/Market/Practical queries) | ✅ | `agents/scout/scout_agent.py` | Returns `ScoutOutputSchema`; "Query" and "Prompt" variants. |
| Academic Agent (check university curricula) | ✅ | `agents/academic/academic_agent.py` | Real agent + `prompts/academic_prompt.py` (university-curriculum framing). Replaced the old inline `llm.invoke`. |
| Market Agent (scan job postings) | ✅ | `agents/market/market_agent.py` + `tools/job_scrapper_tool.py` | Apify LinkedIn MCP scrape + LLM summarize; runs as a graph node (degrades to None on empty scrape). |
| Practical Agent (find GitHub projects) | ✅ | `agents/practical/practical_agent.py` | GitHub MCP wired in (`tools/github_mcp_client.py` `search_github_repositories` now returns results); folded into the practical prompt. |
| Consensus Agent (combine findings → skill graph) | ✅ | `agents/consensus/consensus_agent.py` | Structured `SkillGraph` (nodes/edges); fan-in node after the three specialists. |
| Reviewer Agent (quality/coherence) | ✅ | `agents/reviewer/reviewer_agent.py` | Structured `ReviewResult` (passed + notes). No retry loop yet (P0 stopping point). |
| Final Learning Plan (skill dependency graph) | ✅ | `graph/skill_graph_render.py` | Skill Dependency Graph artifact: JSON + deterministic Mermaid; rendered in the app. |

## 3. Status by Agent (Content-Generation DAG)

| Step (target) | Status | Code path | Notes |
|---|---|---|---|
| Content generator (Boost/Builder/Sprint formats) | ✅ | `agents/content_generator/content_agent.py` | All 3 formats (A/B/C); now wired via the CONTENT route into `graph/content_graph.py`. |
| Creative LLM (engaging draft) | ✅ | `content_agent.py` | Path A of the dual-path content graph. |
| Factual Agents (live web search) | ✅ | `agents/factual/factual_agent.py` | Path B — live DuckDuckGo search (`ddgs`), degrades to None on failure. |
| Synthesizer (merge creative + factual) | ✅ | `agents/synthesizer/synthesizer_agent.py` | "Master LLM" merges Path A + B; cites source URLs. Falls back to creative draft if no findings. |
| Visual Generator (diagrams) | ⛔ | — | Not implemented (later — Content DAG §6.3 tail). |
| Example Generator (code examples) | ⛔ | — | Not implemented. |
| Assembler | ⛔ | — | Not implemented. |

## 4. Status by Agent (Exercise-Generation DAG)

| Step (target) | Status | Code path | Notes |
|---|---|---|---|
| Format Selector / GitHub / Blog / Dataset agents | ✅ | `agents/exercise/format_selector_agent.py`, `graph/exercise_graph.py` | LangGraph Exercise DAG: format selector → [GitHub MCP \| Blog (ddgs) \| Dataset (ddgs links)] fan-in. EXERCISE route now live (no more placeholder). |
| Synthesizer / Grading Setup (unit tests + rubric) | ✅ | `agents/exercise/exercise_synthesizer_agent.py`, `agents/exercise/grader_agent.py` | Synthesizer personalizes; Grader emits unit tests (coding) or rubric (case study). |
| **Live auto-grading** | ✅ | `tools/code_executor.py`, `grader_agent.grade_submission` | Coding → runs submission against tests in an isolated subprocess (self-contained runner, no pytest dep; hang-guard, not a sandbox). Case study → LLM rubric scoring. Wired into `app.py` Grade button. |

## 5. Status by Architecture Layer

| Layer | Status | Notes |
|---|---|---|
| Frontend | 🟡 | Streamlit prototype (`app.py`) — not the target Next.js/JupyterLite stack. |
| Application Service | 🟡 | Agents + LangSmith prompt registry exist; **no** FastAPI, Celery, gateway, rate limiting. |
| AI / LLM | 🟡 | Single Groq model. **LangGraph** orchestration ✅ (CrewAI deferred). Live web grounding (DuckDuckGo) in Content dual-path. Still **no** Model Router, RAG/vector store, or eval pipelines. **Prompt Registry**: ✅ via `prompts/prompt_registry_wrapper_method.py` (LangSmith). |
| Data | ⛔ | No PostgreSQL/Redis/S3/Pinecone/Kafka — fully stateless. |
| Infrastructure | ⛔ | No K8s/Terraform/Prometheus/CI-CD. |
| Analytics & Continuous Improvement | ⛔ | No telemetry pipeline, warehouse, or human-review loop. |
| LLM Ops & Production | ⛔ | No model router, cost/latency observability, deployment pipeline. |
| Security & Governance | ⛔ | No auth/RBAC/encryption/PII scrubbing. Only `.env` secrets + `.gitignore`. |

## 6. Supporting components

| Component | Status | Code path | Notes |
|---|---|---|---|
| Prompt Registry wrapper (LangSmith) | ✅ | `prompts/prompt_registry_wrapper_method.py` | `setup_agent_prompt()` reused by all agents; optional LangSmith push. |
| Job scraper tool (Apify MCP) | ✅ | `tools/job_scrapper_tool.py` | `JobScraperService` — LinkedIn search + parse. |
| GitHub MCP client | ✅ | `tools/github_mcp_client.py` | `search_github_repositories` returns results; wired into the Practical node (degrades to None without a token). |
| Web search (DuckDuckGo) | ✅ | `agents/factual/factual_agent.py` | `ddgs` live search for the Content Factual path. |
| Skill graph renderer | ✅ | `graph/skill_graph_render.py` | Deterministic SkillGraph JSON → Mermaid. |
| LLM config | ✅ | `config.py` | Groq `llama-3.3-70b-versatile`, temp 0.1; validates `GROQ_API_KEY`. |
| Streamlit UI | ✅ | `app.py` | Full Orchestration (SCOUT skill-graph + CONTENT dual-path, Mermaid render) + Individual Agent Test. |
| Tests | 🟡 | `tests/` | 17 pytest tests (graph routing/fan-in, content dual-path, skill-graph render, import guards). Below 80% target. |

---

## 7. Prioritized Roadmap

Each item notes the **architecture section** it satisfies and the **code gap** it closes.

### P0 — Orchestration foundation ✅ COMPLETE
1. ✅ **Migrated to LangGraph** (CrewAI deferred — parallel LangGraph nodes give the same concurrency
   for now). State graphs encode the Learning-Plan + Content DAGs (§6): `graph/learning_plan_graph.py`,
   `graph/content_graph.py`. *Satisfies:* §5.3 AI/LLM Layer.
2. ✅ **Academic & Practical are real agents**; GitHub MCP client wired into Practical
   (`agents/academic/`, `tools/github_mcp_client.py` now returns results).
3. ✅ **Consensus + Reviewer agents** complete the Learning-Plan DAG and emit a real **Skill
   Dependency Graph** (JSON + Mermaid). *Satisfies:* §3.1, §6.2. Reviewer has no retry loop yet.
4. ✅ **Content generator wired** via the CONTENT route; **dual-path content** built (Creative LLM +
   Factual DuckDuckGo agent + Master synthesizer). *Satisfies:* §3.2, §6.3.

> **Deferred from P0:** CrewAI crews (architecture calls for LangGraph **+** CrewAI; revisit when
> role-based crews add value over plain parallel nodes). Visual/Example/Assembler tail of the
> Content DAG (§6.3) also still open.

### P1 — Close the core learning loop
5. ✅ **Exercise pipeline** — Format Selector + GitHub/Blog/Dataset agents + Synthesizer +
   **Grading Setup** (unit tests for code, LLM rubric for analysis) + **live auto-grading**
   (`tools/code_executor.py`). *Satisfies:* §3.3, §6.4. *Closed:* EXERCISE "Under development".
   The learn → plan → content → **practice + grade** loop now runs end-to-end on LangGraph.
   Deferred: containerized grading sandbox (Evaluation Service), real dataset ingestion.
5b. ✅ **Adaptive learning loop** — clickable skill graph → composed lesson (content + embedded
    exercise) → live grade → **mastery capture** (sticky per-node status overlay) → **adaptation**:
    a graded score mutates the graph (remedial prerequisite nodes on a low score / unlock edges on
    mastery) and triggers **score-aware regeneration** of the failed node's lesson against the gaps.
    `graph/lesson_graph.py`, `agents/adaptation/`, `graph/skill_graph_adapt.py` (deterministic,
    id-stable merge). State lives in `st.session_state.learning_session` (maps 1:1 to P1 #6 tables).
    Deferred to #6: Postgres/Redis persistence of `node_state`/`lessons`.
6. ✅ **Persistence + backend** — **FastAPI** service (`api/`) exposes the loop over HTTP (create session /
   list / get / open lesson / grade), each endpoint load→service→save. Loop logic extracted Streamlit-free
   into `services/` (mastery, completion, orchestration). **Postgres** persistence via the Repository pattern
   (`persistence/`): a `learning_session` stored as one JSONB row keyed by `(user_id, session_id)` —
   Alembic migration + `docker-compose.yml`. An in-memory repo (`MINDMORPH_STORE=memory`) backs zero-infra
   tests/dev. MVP user id = caller-supplied (no auth yet). **Verified on real Postgres:** create → open
   lesson → grade (→ adaptation, 6→8 nodes) → **killed + rebooted the process → GET returned the graded
   state intact** (cross-process durability proof); DB-gated integration test guards the JSONB path. 108
   tests green. *Deferred:* Redis (JSONB suffices at prototype scale); re-pointing Streamlit at the API
   (#12 retires it); Pinecone. *Satisfies:* §5.2, §5.4. *Closes:* the stateless prototype.
7. 🟡 **Model Router** (RAG still ⛔) — `llm_providers.py` + `config.get_chat_model(tier)`: Groq stays
   primary; on a primary failure (e.g. Groq free-tier **TPM 413**) it falls back to the **local Claude
   Code CLI** driven headless (`claude -p`, Haiku for default agents / Sonnet for complex). Composes
   through `with_structured_output` via LangChain `with_fallbacks`. Toggle `MINDMORPH_LLM_FALLBACK`
   (`claude_cli` default | `none`). **Placeholder** — the CLI uses the local Claude Code OAuth session
   (local-dev only, not deployable); swap in `langchain-anthropic` once an API key exists, agents
   unchanged. Structured-output-over-CLI verified live (real Haiku → parseable JSON). RAG/grounding +
   multi-vendor HTTP routing still open. *Satisfies (partial):* §5.3, §5.7.

### P2 — Personalization & ingestion
8. **Onboarding + Dynamic Skill Assessment** (social sign-in, MCQ assessment). *Satisfies:* §2.
9. **User material ingestion** — PyMuPDF extract + vectorize uploads. *Satisfies:* §2, §5.4.

### P3 — Full product surface
10. **AI Teaching Assistant** (chat + voice: Whisper STT, ElevenLabs TTS). *Satisfies:* §2.
11. **Screen Vision + Browser Automation agents.** *Satisfies:* §2.
12. 🟡 **Next.js 15 / React 19 frontend** (`web/`) — brought forward alongside #6 (it's what justifies
    the HTTP backend). Dark-luxury UI consuming the FastAPI API via TanStack Query: localStorage login,
    session list/resume, **react-flow skill graph with real clickable nodes** (the upgrade the Streamlit
    iframe couldn't do), status-colored + prereq-locked nodes, lesson view (react-markdown), **Monaco**
    code editor, live grade → mastery re-color + adaptation. Build + typecheck green; Playwright E2E
    (mocked API) covers the full loop + lock gate. **Verified live against the real FastAPI + Postgres:**
    login → the persisted adapted session loads through all layers and the 8-node graph renders (CORS
    preflight + read path proven; browser-driven grade is the one chain not re-run, its parts covered by
    curl write + mocked-client E2E). *Deferred:* JupyterLite sandboxes; retiring Streamlit (kept until
    full parity). *Satisfies:* §5.1.
13. **Infra, analytics, security layers** — K8s/Terraform, Kafka/Airflow/BigQuery, Auth0/RBAC/encryption.
    *Satisfies:* §5.5, §5.6, §5.8.

### Cross-cutting
- 🟡 **Test suite** — pytest started (`tests/`, 17 tests: graph routing/fan-in, content dual-path,
  skill-graph render, import side-effect guards). Still well below the 80% target.
- ✅ Fixed the package-name typo `agents/orchertrator/` → `agents/orchestrator/`.
