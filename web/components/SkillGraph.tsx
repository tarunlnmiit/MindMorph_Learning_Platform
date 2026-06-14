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
} from "@xyflow/react";
import { useMemo } from "react";
import { STATUS_STYLE, displayStatus, lockedNodeIds } from "@/lib/status";
import type { LearningSession, NodeStatus } from "@/lib/types";

const LEVEL_RANK: Record<string, number> = { foundational: 0, intermediate: 1, advanced: 2 };

type SkillNodeData = {
  label: string;
  status: NodeStatus;
  locked: boolean;
  selected: boolean;
};

// A custom node: surface card with a status dot + glow. Locked nodes are dimmed and non-interactive.
function SkillFlowNode({ data }: NodeProps<Node<SkillNodeData>>) {
  const style = STATUS_STYLE[data.status];
  return (
    <div
      className="surface relative w-48 px-4 py-3"
      style={{
        opacity: data.locked ? 0.45 : 1,
        borderColor: data.selected ? "var(--color-gold)" : undefined,
        boxShadow: data.selected
          ? "0 0 0 1px var(--color-gold), 0 0 28px -6px var(--color-gold)"
          : data.status === "mastered"
            ? `0 0 24px -8px ${style.color}`
            : undefined,
        cursor: data.locked ? "not-allowed" : "pointer",
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <div className="flex items-center gap-2">
        <span
          aria-hidden
          className="grid h-5 w-5 place-items-center rounded-full text-[11px]"
          style={{ background: `${style.color}22`, color: style.color }}
        >
          {style.glyph}
        </span>
        <span className="truncate text-sm font-medium text-text-strong">{data.label}</span>
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
}: {
  session: LearningSession;
  onOpen: (nodeId: string, locked: boolean) => void;
}) {
  const { nodes, edges } = useMemo(() => {
    const graph = session.skill_graph;
    const status = displayStatus(graph, session.node_state);
    const locked = lockedNodeIds(graph, session.node_state);

    // Deterministic layered layout: column by level, row by order within the level.
    const perLevel: Record<number, number> = {};
    const rfNodes: Node<SkillNodeData>[] = graph.nodes.map((n) => {
      const col = LEVEL_RANK[(n.level ?? "").toLowerCase()] ?? 1;
      const row = (perLevel[col] = (perLevel[col] ?? 0) + 1) - 1;
      return {
        id: n.id,
        type: "skill",
        position: { x: col * 280, y: row * 120 },
        data: {
          label: n.label,
          status: status[n.id] ?? "available",
          locked: locked.has(n.id),
          selected: session.selected_node === n.id,
        },
      };
    });

    const rfEdges: Edge[] = (graph.edges ?? []).map((e, i) => ({
      id: `e${i}`,
      source: e.source,
      target: e.target,
      animated: false,
      style: { stroke: "oklch(60% 0.02 270 / 0.5)" },
    }));

    return { nodes: rfNodes, edges: rfEdges };
  }, [session]);

  return (
    <div className="surface h-[560px] overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
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
