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
| **Agent orchestration** | Plain `langchain` agents called sequentially from a Streamlit script | **LangGraph + CrewAI** — LangGraph state-graph/DAG control + CrewAI role-based specialist crews |
| **LLM** | Single vendor: Groq `llama-3.3-70b-versatile` (`config.py`) | Multi-vendor **Model Router** (GPT, Claude, Gemini, Bedrock) |
| **Frontend** | Streamlit (`app.py`) | Next.js 14 / React 18 + JupyterLite |
| **Backend** | None (logic runs in Streamlit process) | FastAPI microservices + Celery/Redis workers |
| **Memory / data** | None (stateless per run) | Pinecone (long-term) + Redis (short-term) + PostgreSQL + S3 |
| **Grounding / RAG** | None | RAG pipelines + agentic web search (Playwright/Firecrawl) |
| **Observability** | LangSmith hooks (optional) | Prometheus/Grafana/OpenTelemetry + Prompt Registry feedback loop |

The repo is a **working multi-agent prototype** of the orchestration + intelligence concept — it
proves the routing/decomposition flow end-to-end on one path, but does not yet implement the
LangGraph+CrewAI orchestration, persistence, RAG, grading, or the full DAGs.

---

## 2. Status by Agent (Learning-Plan DAG)

| Agent / Step (target) | Status | Code path | Notes |
|---|---|---|---|
| Orchestrator Agent (route SCOUT/CONTENT/EXERCISE) | ✅ | `agents/orchertrator/orchestrator_agent.py` | Structured output (`Orchestrator_Output_Schema`); only the **SCOUT** route is wired in the app — CONTENT/EXERCISE show "Under development" (`app.py:189`). |
| Scout Agent (decompose → Academic/Market/Practical queries) | ✅ | `agents/scout/scout_agent.py` | Returns `ScoutOutputSchema`; "Query" and "Prompt" variants. |
| Academic Agent (check university curricula) | 🟡 | inline in `app.py:165` | Not a real agent — a single `llm.invoke("You are an Academic Agent...")` call. No curriculum source, no own module. |
| Market Agent (scan job postings) | ✅ | `agents/market/market_agent.py` + `tools/job_scrapper_tool.py` | Apify LinkedIn MCP scrape + LLM summarize. App only summarizes the **first** job (`app.py:83`). |
| Practical Agent (find GitHub projects) | 🟡 | `agents/practical/practical_agent.py` | Works as an LLM advice agent, but does **not** find GitHub projects — the GitHub tool is not wired in. |
| Consensus Agent (combine findings → skill graph) | ⛔ | — | No skill-graph synthesis; app shows three separate tabs instead. |
| Reviewer Agent (quality/coherence) | ⛔ | — | Not implemented. |
| Final Learning Plan (skill dependency graph) | ⛔ | — | No graph artifact; output is three text panels. |

## 3. Status by Agent (Content-Generation DAG)

| Step (target) | Status | Code path | Notes |
|---|---|---|---|
| Content generator (Boost/Builder/Sprint formats) | 🟡 | `agents/content_generator/content_agent.py` | Generates all 3 formats (A/B/C), but **not wired into the orchestrator/app** — run standalone only. Single-path (creative only). |
| Creative LLM (engaging draft) | 🟡 | `content_agent.py` | This is the existing single-path generation. |
| Factual Agents (live web search) | ⛔ | — | No web search / grounding. |
| Synthesizer (merge creative + factual) | ⛔ | — | No "Master LLM" synth step. |
| Visual Generator (diagrams) | ⛔ | — | Not implemented. |
| Example Generator (code examples) | ⛔ | — | Not implemented. |
| Assembler | ⛔ | — | Not implemented. |

## 4. Status by Agent (Exercise-Generation DAG)

| Step (target) | Status | Code path | Notes |
|---|---|---|---|
| Format Selector / GitHub / Blog / Dataset agents | ⛔ | — | Entire exercise pipeline unimplemented. EXERCISE route = "Under development" (`app.py:189`). |
| Synthesizer / Grading Setup (unit tests + rubric) | ⛔ | — | No automated grading. |

## 5. Status by Architecture Layer

| Layer | Status | Notes |
|---|---|---|
| Frontend | 🟡 | Streamlit prototype (`app.py`) — not the target Next.js/JupyterLite stack. |
| Application Service | 🟡 | Agents + LangSmith prompt registry exist; **no** FastAPI, Celery, gateway, rate limiting. |
| AI / LLM | 🟡 | Single Groq model + plain langchain. **No** LangGraph/CrewAI, Model Router, RAG, or eval pipelines. **Prompt Registry**: ✅ via `prompts/prompt_registry_wrapper_method.py` (LangSmith). |
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
| GitHub MCP client | 🟡 | `tools/github_mcp_client.py` | Standalone stub (`MCPClientInitialization`) — connects + lists tools + `search_github_repositories`, but **not wired into any agent**. |
| LLM config | ✅ | `config.py` | Groq `llama-3.3-70b-versatile`, temp 0.1; validates `GROQ_API_KEY`. |
| Streamlit UI | ✅ | `app.py` | Full Orchestration (SCOUT path) + Individual Agent Test modes. |
| Tests | ⛔ | — | No test suite. Example calls live at the bottom of agent files. |

---

## 7. Prioritized Roadmap

Each item notes the **architecture section** it satisfies and the **code gap** it closes.

### P0 — Orchestration foundation (everything else depends on this)
1. **Migrate to LangGraph + CrewAI.** Replace the sequential Streamlit-driven calls with a LangGraph
   state graph encoding the DAGs (§6), using CrewAI role-based crews for the parallel specialists
   (Academic/Market/Practical, Creative/Factual). *Satisfies:* §5.3 AI/LLM Layer. *Closes:* "plain
   langchain, no orchestration framework."
2. **Promote Academic & Practical into real agents** (own modules) and **wire the GitHub MCP client**
   into the Practical agent. *Closes:* `app.py:165` inline academic call; `tools/github_mcp_client.py`
   stub.
3. **Add Consensus + Reviewer agents** to complete the Learning-Plan DAG and emit a real
   **Skill Dependency Graph** artifact. *Satisfies:* §3.1, §6.2. *Closes:* missing consensus/reviewer/graph.
4. **Wire the Content generator into the orchestrator** and implement **dual-path content** (Creative
   LLM + Factual web-search agents + Master synthesizer). *Satisfies:* §3.2, §6.3.

### P1 — Close the core learning loop
5. **Exercise pipeline** — Format Selector + GitHub/Blog/Dataset agents + Synthesizer +
   **Grading Setup** (unit tests for code, LLM rubric for analysis). *Satisfies:* §3.3, §6.4.
   *Closes:* EXERCISE "Under development".
6. **Persistence + backend** — FastAPI service layer; Pinecone (long-term) + Redis (short-term)
   memory; PostgreSQL for user/progress. *Satisfies:* §5.2, §5.4. *Closes:* stateless prototype.
7. **RAG + Model Router** — grounding pipelines and multi-vendor routing. *Satisfies:* §5.3, §5.7.

### P2 — Personalization & ingestion
8. **Onboarding + Dynamic Skill Assessment** (social sign-in, MCQ assessment). *Satisfies:* §2.
9. **User material ingestion** — PyMuPDF extract + vectorize uploads. *Satisfies:* §2, §5.4.

### P3 — Full product surface
10. **AI Teaching Assistant** (chat + voice: Whisper STT, ElevenLabs TTS). *Satisfies:* §2.
11. **Screen Vision + Browser Automation agents.** *Satisfies:* §2.
12. **Next.js 14 / React 18 frontend** replacing Streamlit; JupyterLite sandboxes. *Satisfies:* §5.1.
13. **Infra, analytics, security layers** — K8s/Terraform, Kafka/Airflow/BigQuery, Auth0/RBAC/encryption.
    *Satisfies:* §5.5, §5.6, §5.8.

### Cross-cutting
- **Add a test suite** (pytest) — currently zero coverage; agents have only inline example calls.
- Fix the package-name typo `agents/orchertrator/` → `agents/orchestrator/` during the P0 refactor.
