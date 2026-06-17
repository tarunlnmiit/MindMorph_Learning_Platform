import { expect, test } from "@playwright/test";
import { layoutSkillGraph } from "../lib/graphLayout";
import type { SkillEdge, SkillNode } from "../lib/types";

// Pure layout unit tests — no page navigation. SkillEdge convention: source = prerequisite,
// target = the dependent skill (services/completion.py:30-31).
const node = (id: string): SkillNode => ({ id, label: id, description: "" });

test.describe("layoutSkillGraph", () => {
  test("places prerequisites left of dependents in a chain A->B->C", () => {
    const nodes: SkillNode[] = [node("A"), node("B"), node("C")];
    const edges: SkillEdge[] = [
      { source: "A", target: "B" },
      { source: "B", target: "C" },
    ];

    const { positions } = layoutSkillGraph(nodes, edges);

    expect(positions.A.x).toBeLessThan(positions.B.x);
    expect(positions.B.x).toBeLessThan(positions.C.x);
  });

  test("no two nodes share an identical position", () => {
    const nodes: SkillNode[] = [node("A"), node("B"), node("C"), node("D")];
    const edges: SkillEdge[] = [
      { source: "A", target: "C" },
      { source: "B", target: "C" },
      { source: "C", target: "D" },
    ];

    const { positions } = layoutSkillGraph(nodes, edges);
    const seen = new Set(Object.values(positions).map((p) => `${p.x},${p.y}`));

    expect(seen.size).toBe(nodes.length);
  });

  test("ignores edges with dangling endpoints without crashing", () => {
    const nodes: SkillNode[] = [node("A"), node("B")];
    const edges: SkillEdge[] = [
      { source: "A", target: "B" },
      { source: "A", target: "ghost" },
    ];

    const { positions } = layoutSkillGraph(nodes, edges);

    expect(Object.keys(positions).sort()).toEqual(["A", "B"]);
    expect(positions.A.x).toBeLessThan(positions.B.x);
  });
});
