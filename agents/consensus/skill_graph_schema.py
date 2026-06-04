from typing import List, Optional
from pydantic import BaseModel, Field


class SkillNode(BaseModel):
    id: str = Field(description="Stable short identifier for the skill, e.g. 'python_basics'")
    label: str = Field(description="Human-readable skill name, e.g. 'Python Basics'")
    description: str = Field(description="One-sentence description of what this skill covers")
    level: Optional[str] = Field(
        default=None,
        description="Difficulty tier: one of 'foundational', 'intermediate', 'advanced'",
    )


class SkillEdge(BaseModel):
    source: str = Field(description="id of the prerequisite skill")
    target: str = Field(description="id of the skill that depends on the source")
    relation: Optional[str] = Field(
        default="prerequisite",
        description="Relationship type, typically 'prerequisite'",
    )


class SkillGraph(BaseModel):
    """A skill dependency graph: the most efficient ordered path to the goal."""
    summary: str = Field(description="Short overview of the roadmap this graph encodes")
    nodes: List[SkillNode] = Field(description="The skills, ordered foundational -> advanced")
    edges: List[SkillEdge] = Field(description="Directed prerequisite dependencies between skills")
