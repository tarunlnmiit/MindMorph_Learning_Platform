import dagre from "@dagrejs/dagre";
import type { SkillEdge, SkillNode } from "./types";

// The rendered skill card (SkillFlowNode): Tailwind w-48 = 192px; height is roughly two text rows
// plus padding. Dagre needs the node box to reserve space and avoid overlap.
const NODE_WIDTH = 192;
const NODE_HEIGHT = 72;

// Spacing tuned to the prior 280px column / 120px row feel of the hand-rolled layout.
const RANK_SEP = 110; // gap between prereq depth layers (horizontal, LR)
const NODE_SEP = 48; // gap between sibling nodes within a layer

export type Position = { x: number; y: number };

/**
 * Edge-aware layered layout for the prerequisite DAG.
 *
 * SkillEdge convention (services/completion.py:30-31): source = prerequisite, target = the skill
 * that depends on it. With `rankdir: "LR"` dagre places sources left of targets, so prerequisites —
 * including remedial nodes added mid-session — render to the LEFT of the node they unlock, and the
 * whole graph reflows automatically when nodes are appended. Returns ReactFlow top-left positions
 * (dagre reports node centers, so we offset by half the node box).
 */
export function layoutSkillGraph(
  nodes: SkillNode[],
  edges: SkillEdge[],
): { positions: Record<string, Position> } {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", ranksep: RANK_SEP, nodesep: NODE_SEP });
  g.setDefaultEdgeLabel(() => ({}));

  for (const n of nodes) {
    g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  // Only wire edges whose endpoints exist, so a malformed/dangling edge can't crash layout.
  const ids = new Set(nodes.map((n) => n.id));
  for (const e of edges) {
    if (ids.has(e.source) && ids.has(e.target)) {
      g.setEdge(e.source, e.target);
    }
  }

  dagre.layout(g);

  const positions: Record<string, Position> = {};
  for (const n of nodes) {
    const node = g.node(n.id);
    positions[n.id] = node
      ? { x: node.x - NODE_WIDTH / 2, y: node.y - NODE_HEIGHT / 2 }
      : { x: 0, y: 0 };
  }
  return { positions };
}
