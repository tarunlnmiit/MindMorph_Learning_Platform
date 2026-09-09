"use client";

import {
  Background,
  Controls,
  type Edge,
  Handle,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
  type ReactFlowInstance,
} from "@xyflow/react";
import { useEffect, useMemo, useRef } from "react";
import { layoutSkillGraph } from "@/lib/graphLayout";
import { STATUS_STYLE, displayStatus, lockedNodeIds } from "@/lib/status";
import type { LearningSession, NodeStatus } from "@/lib/types";

// Stagger window between two newly-inserted nodes' entrances, and the hand-off point from the
// entrance animation to the pulse-glow ring that follows it (must match `skill-node-enter`'s
// duration in globals.css).
const ENTER_STAGGER_MS = 140;
const ENTER_DURATION_MS = 580;

type SkillNodeData = {
  label: string;
  status: NodeStatus;
  locked: boolean;
  selected: boolean;
  isNew: boolean;
  enterDelayMs: number;
};

// A custom node: surface card with a status dot + glow. Locked nodes are dimmed and non-interactive.
// `isNew` gets a one-shot entrance + pulse-glow animation on THIS inner card — never on the
// `.react-flow__node` wrapper xyflow renders around it, which already carries its own position
// transition (globals.css). `enterDelayMs` staggers multiple same-render insertions so they don't all
// pop in on the same frame; the glow is chained to start right as the entrance settles.
function SkillFlowNode({ data }: NodeProps<Node<SkillNodeData>>) {
  const style = STATUS_STYLE[data.status];
  return (
    <div
      className={`surface relative w-64 px-4 py-3 ${data.isNew ? "skill-node-enter" : ""}`}
      style={{
        opacity: data.locked ? 0.45 : 1,
        borderColor: data.selected ? "var(--color-gold)" : undefined,
        boxShadow: data.selected
          ? "0 0 0 1px var(--color-gold), 0 0 28px -6px var(--color-gold)"
          : data.status === "mastered"
            ? `0 0 24px -8px ${style.color}`
            : undefined,
        cursor: data.locked ? "not-allowed" : "pointer",
        ...(data.isNew
          ? { animationDelay: `${data.enterDelayMs}ms, ${data.enterDelayMs + ENTER_DURATION_MS}ms` }
          : null),
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <div className="flex items-center gap-2">
        <span
          aria-hidden
          className="grid h-5 w-5 shrink-0 place-items-center rounded-full text-[11px]"
          style={{ background: `${style.color}22`, color: style.color }}
        >
          {style.glyph}
        </span>
        {/* No `truncate`: overflow is measured in pre-transform CSS pixels, so an ellipsis added at
            zoom 1 stays ellipsised however far the camera zooms in. Real skill names ("Advanced List
            Comprehensions") need two lines at this width; clamp at two so the card height stays the
            fixed box graphLayout reserves in dagre. */}
        <span className="line-clamp-2 text-sm font-medium leading-snug text-text-strong">
          {data.label}
        </span>
      </div>
      <p className="mt-1 text-[11px]" style={{ color: style.color }}>
        {style.label}
      </p>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = { skill: SkillFlowNode };

export function SkillGraph({
  session,
  onOpen,
  focusNodeIds,
}: {
  session: LearningSession;
  onOpen: (nodeId: string, locked: boolean) => void;
  // Ids the caller wants the camera drawn to right now (the authoritative signal is the grade
  // response's `new_node_ids` — a rewire that happened off-screen otherwise goes unnoticed since the
  // graph sits above the lesson panel the learner is scrolled down to).
  focusNodeIds?: string[];
}) {
  // Ids/edge-keys seen on a prior render, so a mid-session remedial node or edge (added by an LLM
  // adaptation after a sub-40 grade) gets its entrance animation exactly once instead of on every
  // recompute.
  const seenNodeIds = useRef<Set<string>>(new Set());
  const seenEdgeKeys = useRef<Set<string>>(new Set());
  const containerRef = useRef<HTMLDivElement>(null);
  const rfInstanceRef = useRef<ReactFlowInstance<Node<SkillNodeData>, Edge> | null>(null);

  const { nodes, edges } = useMemo(() => {
    const graph = session.skill_graph;
    const status = displayStatus(graph, session.node_state);
    const locked = lockedNodeIds(graph, session.node_state);

    // Read-only diff against the refs — StrictMode may invoke this factory twice per commit, and a
    // useMemo factory must stay pure, so the refs are updated in the effect below instead of here.
    const seenNodes = seenNodeIds.current;
    const seenEdges = seenEdgeKeys.current;
    // Preserve graph order so multiple insertions in one adaptation stagger in a stable sequence.
    const newIdOrder = graph.nodes.filter((n) => !seenNodes.has(n.id)).map((n) => n.id);
    const enterDelayByNode = new Map(newIdOrder.map((id, i) => [id, i * ENTER_STAGGER_MS]));

    // Edge-aware layered layout (dagre): position by the prereq DAG, so remedial prerequisite nodes
    // added mid-session render left of the node they unlock and the graph reflows automatically.
    const { positions } = layoutSkillGraph(graph.nodes, graph.edges ?? []);
    const rfNodes: Node<SkillNodeData>[] = graph.nodes.map((n) => {
      return {
        id: n.id,
        type: "skill",
        position: positions[n.id] ?? { x: 0, y: 0 },
        data: {
          label: n.label,
          status: status[n.id] ?? "available",
          locked: locked.has(n.id),
          selected: session.selected_node === n.id,
          isNew: enterDelayByNode.has(n.id),
          enterDelayMs: enterDelayByNode.get(n.id) ?? 0,
        },
      };
    });

    const rfEdges: Edge[] = (graph.edges ?? []).map((e, i) => {
      const key = `${e.source}->${e.target}`;
      return {
        id: `e${i}`,
        source: e.source,
        target: e.target,
        animated: false,
        className: seenEdges.has(key) ? undefined : "skill-edge-enter",
        style: { stroke: "oklch(60% 0.02 270 / 0.5)" },
      };
    });

    return { nodes: rfNodes, edges: rfEdges };
  }, [session]);

  // Mark this render's ids/edge-keys as seen AFTER commit, so the next diff excludes them. Runs
  // post-commit (not during render), so StrictMode's dev double-invoke is harmless — Set.add is
  // idempotent.
  useEffect(() => {
    const seenNodes = seenNodeIds.current;
    for (const n of nodes) seenNodes.add(n.id);
    const seenEdges = seenEdgeKeys.current;
    for (const e of edges) seenEdges.add(`${e.source}->${e.target}`);
  }, [nodes, edges]);

  // Camera cue: a grade that grew the graph shouldn't rewire off-screen while the learner is still
  // scrolled down at the editor. Scroll the graph into view, then frame the new node(s) plus whatever
  // they attach to, so the rewire reads as a connected change rather than an isolated pop-in.
  useEffect(() => {
    if (!focusNodeIds || focusNodeIds.length === 0) return;
    const container = containerRef.current;
    if (!container) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // Reduced-motion users still land on the right scroll position — just without the smooth glide.
    container.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });

    const instance = rfInstanceRef.current;
    if (!instance) return;
    // Two hops of neighbours, not one: one hop framed as few as three cards, which the maxZoom cap
    // then centred in empty canvas — the rewire read as "three cards" rather than "the map changed".
    // Each round works off a snapshot so a node added this round doesn't expand again within it.
    const edges = session.skill_graph.edges ?? [];
    const focusIds = new Set(focusNodeIds);
    for (let hop = 0; hop < 2; hop++) {
      const frontier = new Set(focusIds);
      for (const e of edges) {
        if (frontier.has(e.source)) focusIds.add(e.target);
        if (frontier.has(e.target)) focusIds.add(e.source);
      }
    }
    const run = () =>
      instance.fitView({
        nodes: [...focusIds].map((id) => ({ id })),
        // maxZoom matters as much as padding: without it a two-or-three-node focus set zooms past 1.8
        // and clips the very node the new ones attach to, so the rewire reads as an unrelated card
        // instead of a change to the map. Cap it near the mount-time framing and keep enough padding
        // that the surrounding graph stays visible for context.
        padding: 0.45,
        maxZoom: 1.1,
        duration: reduceMotion ? 0 : 900,
      });

    if (reduceMotion) {
      run();
      return;
    }
    // The same commit that triggers this cue unmounts the lesson panel and its Monaco editor. Starting
    // the camera tween inside that blocked frame eats most of its duration and lands as a snap, so let
    // the re-render settle first.
    const timer = window.setTimeout(run, 150);
    return () => window.clearTimeout(timer);
  }, [focusNodeIds, session.skill_graph.edges]);

  return (
    <div ref={containerRef} className="surface h-[420px] overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1.5 }}
        onInit={(instance) => {
          rfInstanceRef.current = instance;
        }}
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, node) => onOpen(node.id, (node.data as SkillNodeData).locked)}
        nodesDraggable={false}
        nodesConnectable={false}
        edgesFocusable={false}
      >
        <Background color="oklch(40% 0.02 270 / 0.4)" gap={22} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
