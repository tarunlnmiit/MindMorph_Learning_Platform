from typing import Literal

from pydantic import BaseModel, Field

# The two exercise shapes MindMorph supports (architecture §6.4 Format Selector).
ExerciseFormatType = Literal["coding_challenge", "case_study"]


class ExerciseFormat(BaseModel):
    """Format Selector verdict: which kind of exercise best fits the learning goal."""

    format: ExerciseFormatType = Field(
        description=(
            "'coding_challenge' for hands-on programming the user solves with code; "
            "'case_study' for analytical/design tasks judged against a rubric."
        )
    )
    reasoning: str = Field(description="One sentence on why this format suits the request")
