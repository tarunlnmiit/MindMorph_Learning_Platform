"""Phase 3 — Adaptation output schema.

The Adaptation agent reads a graded skill node + its score + failure feedback and proposes a
*structural* change to the skill graph: remedial prerequisite nodes when the learner struggled,
or unlock edges to downstream skills when they mastered it. Reuses the consensus SkillNode /
SkillEdge so the adapted graph stays type-compatible with the renderer and lesson loop.

Hard invariant (enforced in the prompt AND the deterministic merge): adaptation may only ADD
new nodes/edges — never rename or delete an existing node id. Mastery state and cached lessons
key off node_id.
"""
from typing import List

from pydantic import BaseModel, Field

from agents.consensus.skill_graph_schema import SkillNode, SkillEdge


class GraphAdaptation(BaseModel):
    """A proposed additive change to the skill graph after a node is graded."""

    new_nodes: List[SkillNode] = Field(
        default_factory=list,
        description="New skill nodes to ADD (remedial prerequisites on a low score, or none). "
        "Node ids must be new and not collide with any existing id.",
    )
    new_edges: List[SkillEdge] = Field(
        default_factory=list,
        description="New directed edges to ADD. Remedial nodes point INTO the graded node "
        "(they are new prerequisites); unlock edges point from the graded node to downstream skills.",
    )
    remediation_focus: List[str] = Field(
        default_factory=list,
        description="The specific gaps the learner missed (empty on a high score). These steer "
        "score-aware regeneration of the graded node's lesson.",
    )
    rationale: str = Field(
        default="",
        description="One or two sentences explaining the adaptation decision.",
    )
