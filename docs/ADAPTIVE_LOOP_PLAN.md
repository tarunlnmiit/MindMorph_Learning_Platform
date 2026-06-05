# Plan — Interactive Adaptive Learning Loop (clickable graph → lesson → score → adapt)

## Context

Today MindMorph runs **one of three mutually-exclusive routes** per query (SCOUT / CONTENT /
EXERCISE) and renders a **static** Mermaid skill graph. There is no way to drill into a skill, no
lesson-with-embedded-exercise, no score capture, and no feedback loop. The user wants the product's
core experience:

1. Query → intent classification (**already done** — orchestrator routes SCOUT = learning).
2. Learning query → skill graph generated; user **picks any node**.
3. That node generates a **lesson** = content **with an exercise at the end**.
4. User **performs** the exercise (live grading already works).
5. The exercise **score feeds back** into the system.
6. Score **adjusts the graph** (structural remedial nodes + mastery) **and the content**
   (next regeneration targets the learner's gaps).

This plan covers the **full 6-step vision**, structured so **Phase 1 is independently shippable**.

---

## Implementation status (as of 2026-06-05)

- ✅ **Phase 1 — IMPLEMENTED** (steps 1–4 of the vision: query → graph → pick node → composed lesson with embedded exercise + live grading). Unit-tested (`mindmorph` conda env).
- ✅ **Phase 2 — IMPLEMENTED** (step 5: mastery capture + graph re-style). Grade → `_apply_score` writes
  `node_state[node_id]` (`best_score=max`, `attempts+=1`, **sticky** status: `best_score≥80 → mastered`
  (a worse retry never revokes it), else latest score `≥50 → in_progress / <50 → needs_review`,
  `last_feedback`); the result persists across the post-grade `st.rerun()`. `skill_graph_to_mermaid(graph, node_status)`
  overlays glyphs (✅/🔁/▶) + status colors; `render_learning_session` recomputes the Mermaid live and shows a
  `🎯 N/M skills mastered` counter. Standalone EXERCISE route unchanged. Unit-tested (`test_mastery_capture.py`,
  `test_skill_graph_render.py` status cases). **53 tests green.**
- ⏳ **Phase 3 — NOT STARTED** (adaptation: remedial nodes + score-aware regeneration). The Phase-1 hooks for it are already in place (see notes below).

**Deviations / additions beyond the original blueprint:**
- **Code editor:** the exercise solution input for `coding_challenge` uses the **`streamlit-ace`** editor (syntax highlight, line numbers, monokai), not a plain `st.text_area`. Server-side hardened-sandbox grading is unchanged. `case_study` still uses a text_area (prose). New dep: `streamlit-ace` in `requirements.txt`.
- **Logging:** all runtime `print()` across agents/graphs/tools replaced with the `logging` library. Central `logging_config.py` → `setup_logging()` (console + rotating file `logs/mindmorph.log`, level via `MINDMORPH_LOG_LEVEL`). app.py configures it at startup. Carve-outs (left as `print`): `tools/code_executor.py` `MINDMORPH_SUMMARY`/`MINDMORPH_FAILURE` (subprocess→parent grading IPC), `__main__` demo blocks, and `market_agent.run_analysis` (standalone CLI-demo method, unused by the app).
- **Mermaid render:** `render_mermaid` migrated from the deprecated `st.components.v1.html` to **`st.iframe`** (raw-HTML string; runs mermaid.js).
- **Environment:** project runs in the **`mindmorph` conda env** (see CLAUDE.md). Use `conda run -n mindmorph <cmd>`.

**Still NOT verified:** the interactive UI flow end-to-end (graph → selectbox → Open lesson → grade across Streamlit reruns) has not been browser smoke-tested. One `conda run -n mindmorph streamlit run app.py` click-through with `GROQ_API_KEY` set retires it.

---

**What already exists and is reused (do NOT rebuild):**
- Intent routing → `agents/orchestrator/orchestrator_agent.py` (SCOUT branch = the learning entry).
- Skill graph + Mermaid → `agents/consensus/skill_graph_schema.py` (`SkillGraph{summary, nodes[id,label,description,level], edges}`), `graph/skill_graph_render.py`.
- Content generation (dual-path) → `graph/content_graph.py`, `agents/content_generator/content_agent.py` (`generate_content(user_query, format_type)`).
- Exercise generation + live grading → `graph/exercise_graph.py`, `agents/exercise/grader_agent.py` (`grade_submission`), `tools/code_executor.py`, and `render_exercise()` in `app.py`.
- Structured-output agent pattern → `agents/reviewer/reviewer_agent.py` (`with_structured_output`).

**Decisions locked (user):** node picker = **selectbox alongside the existing Mermaid** (no new dep,
Streamlit iframe can't report Mermaid clicks); adaptation = **structural remedial nodes + score-aware
content**. Standalone CONTENT/EXERCISE routes are **kept** (least destructive; they still serve "quick
lesson"/"give me an exercise" queries). All state lives in `st.session_state` for the MVP — Postgres
(progress) + Redis (session) is the later swap (roadmap P1 #6), **not a prerequisite** for this loop.

---

## Session state model (single source of truth — maps cleanly to P1 #6 tables later)

`st.session_state.learning_session` (set after a SCOUT run):
- `skill_graph`: dict — the **adaptive** SkillGraph (nodes/edges). Starts = consensus output; Phase 3 mutates it.
- `node_state`: dict[`node_id` → `{status, best_score, attempts, weaknesses: list[str], last_feedback}`].
  `status` ∈ `available | in_progress | mastered | needs_review`.
- `lessons`: dict[`node_id` → `{content, exercise: {format, statement, grading_artifact}}`] — **cached** composed lesson (cost guard; re-clicking never rebuilds).
- `selected_node`: currently-open node_id.

**ID stability is a hard invariant** (mastery/lessons key off `node_id`): Phase 3 adaptation may only
**add** or **annotate** nodes — never rename or delete existing ids.

---

## Phase 1 — Click a node → composed lesson (content + embedded exercise)  ✅ DONE

*(Implemented. Sub-items below describe what shipped; file/function names are final.)*

**1A. `graph/lesson_graph.py`** ✅ — `build_lesson_graph(content_graph=None, exercise_graph=None)`.
A thin parent graph composing the two existing compiled subgraphs **sequentially** (content → exercise;
the exercise belongs at the end of the lesson):
- `LessonState(TypedDict, total=False)`: `skill_query, skill_label, skill_description, format_type,
  prior_score, prior_weaknesses, content, exercise_format, exercise_statement, grading_artifact`.
- `content_node`: `await content_graph.ainvoke({user_query: skill_query, format_type, prior_feedback})` → `content`.
- `exercise_node`: `await exercise_graph.ainvoke({user_query: skill_query})` → exercise fields.
- Shape: `START → content → exercise → END`.
- **Critical:** `skill_query = f"{skill_label}: {skill_description}"` — the lesson/exercise are about the
  **clicked skill node**, NOT the original top-level query. (Easiest thing to get wrong.)

**1B. Make content generation score-aware (no-op until Phase 3).** ✅ Add an optional `prior_feedback`
key to `ContentState` in `graph/content_graph.py`; `creative_node` passes it through to
`content_agent.generate_content(...)`. Extend `generate_content(user_query, format_type, remediation: str | None = None)`
in `agents/content_generator/content_agent.py` — when `remediation` is set, prepend a "focus on these
gaps" instruction to the prompt. Phase 1 always passes `None` ⇒ identical behavior to today.

**1C. `app.py` — SCOUT branch becomes interactive (replaces the read-only graph dump):** ✅
- After SCOUT, consensus output is stored in `st.session_state.learning_session` (skill_graph,
  `node_state` init `status="available"` per node, empty `lessons`, `selected_node`).
- New `render_learning_session()` (called **outside** the generate-button block so picker/lesson
  survive Streamlit reruns) renders the Mermaid **plus** `st.selectbox("Pick a skill to study", …)`
  + "📖 Open lesson" button. Specialist tabs moved into a collapsed "Roadmap details" expander.
- On open: if `lessons[node_id]` cached → reuse; else `run_lesson(...)` invokes `lesson_graph` with the
  node's label/description (+ `prior_weaknesses` from `node_state`), cached. **No `st.rerun()`** — the
  button press already re-runs the script; success falls through to the render block, failure keeps the
  error visible.
- Lesson render: `st.markdown(content)` then `render_exercise({...})` **inline at the end** (reuses the
  existing grade panel). The coding-challenge input is the **`st_ace`** editor (see status notes).

**1D. Phase-1 tests:** ✅ `tests/test_lesson_graph.py` (4 tests: content→exercise populate; `skill_query`
carries node label+description not the top query; `prior_weaknesses` → `prior_feedback`). `tests/test_imports.py`
extended with `graph.lesson_graph`. Plus `tests/test_logging_config.py` (logging setup) and a
`prior_feedback` thread test in `tests/test_content_graph.py`.

---

## Phase 2 — Mastery capture + graph re-style  ✅ DONE

**2A. Score → node_state.** When the Grade button returns a result, write into `node_state[node_id]`:
`best_score = max(old, new)`, `attempts += 1`, derive `status` (`≥80 → mastered`, `50–79 → in_progress`,
`<50 & attempted → needs_review`). Coding score = `result.score`; case_study score = rubric `score`.

**2B. Status overlay in the renderer.** Extend `skill_graph_to_mermaid(graph, node_status=None)` in
`graph/skill_graph_render.py`: when `node_status` is given, append a status glyph to the label
(`✅ mastered`, `🔁 needs review`, `▶ in progress`) and add a status `classDef` (green / red-outline /
amber) that overrides the level color. Pure-deterministic, no LLM — keeps the existing guarantee that
the visual always matches the JSON.

**2C. Progress summary** in `app.py`: "🎯 N / M skills mastered" above the graph; re-render the styled
Mermaid after each grade (`st.rerun()`).

**2D. Phase-2 tests:** extend `tests/test_skill_graph_render.py` — `node_status` produces the status
classes/glyphs; absent ⇒ output unchanged (back-compat).

---

## Phase 3 — Adaptation: structural remedial nodes + score-aware content (closes the loop)

**3A. `agents/adaptation/` (new package, mirrors the reviewer agent):**
- `adaptation_schema.py`: `GraphAdaptation{ new_nodes: list[SkillNode], new_edges: list[SkillEdge],
  remediation_focus: list[str], rationale: str }` (reuse `SkillNode`/`SkillEdge` from the consensus schema).
- `prompts/adaptation_prompt.py`: given the current SkillGraph JSON + the graded node + score +
  failure feedback, decide the adjustment. **Hard rules in the prompt:** (a) NEVER rename or remove an
  existing node id; (b) low score → add 1–2 **remedial sub-skill** nodes whose edges point **into** the
  failed node (new prerequisites) and set `remediation_focus` = the specific gaps; (c) high score → add
  unlock edges to downstream nodes; (d) new node ids must be new and stable.
- `adaptation_agent.py`: `AdaptationAgent.adapt(skill_graph_json, node_id, score, feedback) -> Optional[GraphAdaptation]`
  via `with_structured_output(GraphAdaptation)` (graceful `None` on failure).

**3B. `graph/skill_graph_adapt.py` (new, deterministic — no LLM):** `apply_adaptation(skill_graph, adaptation) -> new_graph`.
**Immutable merge** (build a new dict, never mutate): append new nodes/edges, drop duplicates by id,
**preserve every existing id**. Returns the new graph + the set of new node ids so the caller can seed
their `node_state` (`status="available"`).

**3C. Wire the loop in `app.py`** (after grading, when `status` lands `needs_review` or `mastered`):
- Call `AdaptationAgent.adapt(...)` → `apply_adaptation(...)` → replace `learning_session.skill_graph`,
  add `node_state` for new nodes, and write `remediation_focus` into `node_state[node_id].weaknesses`.
- **Invalidate** `lessons[node_id]` (and any node whose weaknesses changed) so the next open regenerates
  with gap-targeting content (`prior_weaknesses` → `content_graph.prior_feedback` → `generate_content(remediation=...)`).
- `st.rerun()` → graph re-renders with the remedial node + mastery colors; opening the remedial node now
  yields content aimed at the learner's specific gap. **Loop closed.**

**3D. Phase-3 tests:** `tests/test_adaptation_agent.py` (mocked: low score → remedial node added;
high score → unlock edge); `tests/test_skill_graph_adapt.py` (deterministic merge preserves existing
ids, appends new, dedups). Extend `tests/test_imports.py` with the adaptation modules.

---

## Reuse map (don't rebuild)
- Sequential/parallel graph composition + injectable builders → `graph/content_graph.py`, `graph/exercise_graph.py`.
- Structured LLM output (`with_structured_output`, graceful None) → `agents/reviewer/reviewer_agent.py`.
- Deterministic graph→Mermaid (extend, don't replace) → `graph/skill_graph_render.py`.
- Live grading + grade panel (already wired) → `agents/exercise/grader_agent.grade_submission`, `render_exercise()` in `app.py`.

## Critical files
- **New:** `graph/lesson_graph.py`, `graph/skill_graph_adapt.py`,
  `agents/adaptation/{__init__,adaptation_agent,adaptation_schema}.py`, `prompts/adaptation_prompt.py`,
  `tests/{test_lesson_graph,test_adaptation_agent,test_skill_graph_adapt}.py`.
- **Modify:** `app.py` (selectbox node picker + lesson view + score capture + adaptation+rerun + progress);
  `graph/content_graph.py` (+`prior_feedback`); `agents/content_generator/content_agent.py`
  (+`remediation` arg); `graph/skill_graph_render.py` (+`node_status` overlay);
  `tests/{test_imports,test_skill_graph_render}.py`; `docs/IMPLEMENTATION_STATUS.md` (new P1 item:
  "Adaptive learning loop").

## Cost / caching (must-do, not optional)
Each node open = content_graph (LLM + web) + exercise_graph (LLM + web). **Cache the composed lesson per
node_id** in `session_state.lessons`; only invalidate when Phase 3 changes that node's weaknesses.
Grading reuses the cached `grading_artifact` (no LLM). Without this, an 8–10 node graph is brutal.

## Verification (end-to-end)
> All commands run in the **`mindmorph` conda env** (`conda run -n mindmorph …`).
1. `conda run -n mindmorph python -m pytest -q` — all suites green (**43 passing** as of Phase 1).
2. `conda run -n mindmorph python -c "import app, graph.lesson_graph"` — imports clean, no LLM fires.
   (Phase 3 adds: `graph.skill_graph_adapt, agents.adaptation.adaptation_agent`.)
3. `conda run -n mindmorph streamlit run app.py` → Full Orchestration → learning query (e.g. *"I want to
   learn Python for data science"*) → skill graph (via `st.iframe`) + selectbox render. **[browser smoke
   test still pending]**
4. Pick a node → **Open lesson** → content renders with an exercise at the end.
5. Submit a **correct** solution → node turns ✅ mastered; progress count increments.
6. Submit a **wrong** solution → node turns 🔁 needs review → a **remedial node appears** in the graph.
7. Open the remedial node → its content is **targeted at the failed gap** (score-aware regeneration).
8. After code changes: `graphify update .` (AST-only; keeps the knowledge graph current per CLAUDE.md).

## Out of scope (later)
- Persistence: Postgres (user/progress/node_state) + Redis (session) — roadmap P1 #6. The `node_state` /
  `lessons` dicts map 1:1 to tables; swap the store, keep the logic.
- True on-node click (streamlit-agraph / Next.js graph canvas) — Streamlit selectbox is the MVP picker.
- CrewAI crews, RAG, Model Router (P1 #6/#7). Real dataset ingestion (exercise sources still return links).
