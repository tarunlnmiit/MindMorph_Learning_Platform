# Grading Setup (architecture §6.4): builds the auto-grading harness for an exercise — pytest-style
# unit tests for a coding_challenge, or a weighted rubric for a case_study.
#
# Phase B adds `grade_submission` (run the tests / score against the rubric) below.

import sys
import os
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

from config import llm
from prompts.grader_prompt import GRADER_SYSTEM_PROMPT, GRADER_RUBRIC_SCORING_SYSTEM_PROMPT
from agents.exercise.grading_schema import GradingArtifact, RubricScore

_HUMAN_TEMPLATE = """Learner goal: {user_query}
Exercise format: {exercise_format}

EXERCISE:
{exercise_statement}

Build the grading harness for this exercise."""


class GraderAgent:
    """Generates the grading harness (unit tests or rubric) for a synthesized exercise."""

    def __init__(self, push_to_langsmith: bool = False):
        self.llm = llm
        self.structured_llm = self.llm.with_structured_output(GradingArtifact)
        system_template = SystemMessagePromptTemplate.from_template(GRADER_SYSTEM_PROMPT)
        human_template = HumanMessagePromptTemplate.from_template(_HUMAN_TEMPLATE)
        self.chat_prompt = ChatPromptTemplate.from_messages([system_template, human_template])

    def build_grading_artifact(
        self,
        user_query: str,
        exercise_format: str,
        exercise_statement: str,
    ) -> Optional[GradingArtifact]:
        """Returns a GradingArtifact, or None on failure."""
        if not exercise_statement or not isinstance(exercise_statement, str):
            raise ValueError("exercise_statement must be a non-empty string")

        print("Grader: building grading harness...")
        try:
            messages = self.chat_prompt.format_messages(
                user_query=user_query,
                exercise_format=exercise_format,
                exercise_statement=exercise_statement,
            )
            return self.structured_llm.invoke(messages)
        except Exception as e:
            print(f"Error building grading artifact: {str(e)}")
            return None


# --- Phase B: live grading of a submitted solution ---------------------------------------------
#
# Grading is intentionally NOT a graph node — it fires from the UI after the learner submits.
# coding_challenge -> run the generated unit tests in a sandboxed subprocess (tools.code_executor).
# case_study       -> LLM scores the submission against the rubric (no code execution).

_RUBRIC_HUMAN_TEMPLATE = """RUBRIC (criterion — weight):
{rubric}

LEARNER SUBMISSION:
{submission}

Score the submission against the rubric."""


def grade_submission(exercise_format: str, solution_text: str, grading_artifact: Optional[dict]):
    """Grade a learner's submission. Returns a result dict, or None on failure / empty input.

    coding_challenge -> {passed, total, failures, score, stdout, timed_out} (from code_executor).
    case_study       -> {score, per_criterion, feedback} (from the LLM rubric scorer).
    """
    if not solution_text or not solution_text.strip():
        return None

    artifact = grading_artifact or {}
    if exercise_format == "coding_challenge":
        # Lazy import keeps the code-execution surface out of the module-import path.
        from tools.code_executor import execute_tests

        # Join with "\n" (not "\n\n"): the grader sometimes returns the test module split into
        # per-line fragments; a single newline reconstructs it faithfully (indentation preserved).
        tests = artifact.get("unit_tests") or []
        return execute_tests(solution_text, "\n".join(tests))

    return _grade_case_study(solution_text, artifact)


def _grade_case_study(solution_text: str, artifact: dict) -> Optional[dict]:
    rubric = artifact.get("rubric") or []
    rubric_text = "\n".join(
        f"- {c.get('criterion')} (weight {c.get('weight')})" for c in rubric
    ) or "- Overall quality (weight 100)"

    system_template = SystemMessagePromptTemplate.from_template(GRADER_RUBRIC_SCORING_SYSTEM_PROMPT)
    human_template = HumanMessagePromptTemplate.from_template(_RUBRIC_HUMAN_TEMPLATE)
    chat_prompt = ChatPromptTemplate.from_messages([system_template, human_template])
    structured_llm = llm.with_structured_output(RubricScore)

    print("Grader: scoring case-study submission against rubric...")
    try:
        messages = chat_prompt.format_messages(rubric=rubric_text, submission=solution_text)
        result = structured_llm.invoke(messages)
        return result.model_dump()
    except Exception as e:
        print(f"Error scoring case study: {str(e)}")
        return None


if __name__ == "__main__":
    agent = GraderAgent()
    print(
        agent.build_grading_artifact(
            "recursion in Python",
            "coding_challenge",
            "Implement `factorial(n)` returning n!. factorial(0)==1, factorial(5)==120.",
        )
    )
