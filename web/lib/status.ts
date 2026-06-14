// Client-side port of services/completion.py. The persisted node_state carries the RAW per-node
// status; "complete" (and therefore the 🔒 locked / ✅ complete display) is derived from the whole
// prerequisite chain. The server is the source of truth for the lock gate (open_lesson → 409); this
// mirror exists so the graph can color + disable nodes without a round-trip per render.

import type { NodeStatus, SkillGraph } from "./types";

type StateMap = Record<string, { status: NodeStatus }>;

export function prereqsByNode(graph: SkillGraph): Record<string, Set<string>> {
  const prereqs: Record<string, Set<string>> = {};
  for (const n of graph.nodes) prereqs[n.id] = new Set();
  for (const e of graph.edges ?? []) {
    if (e.target in prereqs && e.source != null) prereqs[e.target].add(e.source);
  }
  return prereqs;
}

export function completeNodeIds(graph: SkillGraph, state: StateMap): Set<string> {
  const prereqs = prereqsByNode(graph);
  const isMastered = (id: string) => state[id]?.status === "mastered";
  const memo: Record<string, boolean> = {};
  const visiting = new Set<string>();

  const complete = (id: string): boolean => {
    if (id in memo) return memo[id];
    if (visiting.has(id)) return false; // cycle guard
    if (!isMastered(id)) return (memo[id] = false);
    visiting.add(id);
    const result = [...(prereqs[id] ?? [])].every(complete);
    visiting.delete(id);
    return (memo[id] = result);
  };

  return new Set(Object.keys(prereqs).filter(complete));
}

export function lockedNodeIds(graph: SkillGraph, state: StateMap): Set<string> {
  const complete = completeNodeIds(graph, state);
  const prereqs = prereqsByNode(graph);
  const locked = new Set<string>();
  for (const [id, ps] of Object.entries(prereqs)) {
    if ([...ps].some((p) => !complete.has(p))) locked.add(id);
  }
  return locked;
}

export function incompletePrereqLabels(
  graph: SkillGraph,
  state: StateMap,
  nodeId: string,
): string[] {
  const complete = completeNodeIds(graph, state);
  const labelById = Object.fromEntries(graph.nodes.map((n) => [n.id, n.label]));
  return [...(prereqsByNode(graph)[nodeId] ?? [])]
    .filter((p) => !complete.has(p))
    .map((p) => labelById[p] ?? p);
}

// node_id -> display status: complete -> 'mastered'; locked -> 'blocked'; else raw status.
export function displayStatus(graph: SkillGraph, state: StateMap): Record<string, NodeStatus> {
  const complete = completeNodeIds(graph, state);
  const locked = lockedNodeIds(graph, state);
  const out: Record<string, NodeStatus> = {};
  for (const [id, s] of Object.entries(state)) {
    if (complete.has(id)) out[id] = "mastered";
    else if (locked.has(id)) out[id] = "blocked";
    else out[id] = s.status;
  }
  return out;
}

export interface StatusStyle {
  label: string;
  glyph: string;
  color: string; // CSS var token
}

export const STATUS_STYLE: Record<NodeStatus, StatusStyle> = {
  mastered: { label: "Complete", glyph: "✓", color: "var(--color-mastered)" },
  in_progress: { label: "In progress", glyph: "◐", color: "var(--color-progress)" },
  needs_review: { label: "Needs review", glyph: "↻", color: "var(--color-review)" },
  blocked: { label: "Locked", glyph: "🔒", color: "var(--color-blocked)" },
  available: { label: "Available", glyph: "○", color: "var(--color-available)" },
};
