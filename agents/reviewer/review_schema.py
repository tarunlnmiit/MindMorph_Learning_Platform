from pydantic import BaseModel, Field


class ReviewResult(BaseModel):
    """Reviewer Agent verdict on a generated Skill Dependency Graph."""
    passed: bool = Field(description="True if the roadmap is coherent and fit for the learner's goal")
    notes: str = Field(
        description="Concise review: strengths, gaps, ordering problems, or missing prerequisites"
    )
