"""Schemas for the dynamic skill assessment (P2 #8).

A short MCQ quiz generated from the skill graph; correct answers pre-seed which nodes the learner
already knows. ``node_id`` ties each question back to a real ``SkillNode.id``.
"""
from typing import List

from pydantic import BaseModel, Field


class MCQQuestion(BaseModel):
    node_id: str = Field(
        description="The skill node id this question assesses. MUST exactly match an id from the graph."
    )
    question: str = Field(description="A single multiple-choice question gauging that skill.")
    options: List[str] = Field(description="Exactly 4 distinct answer options.")
    correct_index: int = Field(description="0-based index into options of the single correct answer.")
    explanation: str = Field(default="", description="One sentence on why the answer is correct.")


class AssessmentQuiz(BaseModel):
    questions: List[MCQQuestion] = Field(description="One question per assessed skill node.")
