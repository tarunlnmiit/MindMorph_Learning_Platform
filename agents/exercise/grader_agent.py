# Grading Setup (architecture §6.4): builds the auto-grading harness for an exercise — pytest-style
# unit tests for a coding_challenge, or a weighted rubric for a case_study.
#
# Phase B adds `grade_submission` (run the tests / score against the rubric) below.

import logging
import sys
import os
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

logger = logging.getLogger(__name__)

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
        self.structured_llm = self.llm.with_structured_output(GradingArtifact, method="json_schema")
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

        logger.info("Grader: building grading harness (%s)", exercise_format)
        messages = self.chat_prompt.format_messages(
            user_query=user_query,
            exercise_format=exercise_format,
            exercise_statement=exercise_statement,
        )
        # One retry: a test module that cannot run is worse than no tests at all, because grading it
        # produces a confident wrong score. Validate before handing it to the learner.
        for attempt in (1, 2):
            try:
                artifact = self.structured_llm.invoke(messages)
            except Exception:
                logger.exception("Grader: error building grading artifact")
                return None
            if artifact is None or artifact.format != "coding_challenge":
                return artifact  # case_study has no tests to validate
            reason = self._validate_unit_tests(artifact.unit_tests)
            if reason is None:
                return artifact
            logger.error("Grader: generated tests are unrunnable (attempt %d/2): %s", attempt, reason)
        return None

    @staticmethod
    def _validate_unit_tests(unit_tests) -> Optional[str]:
        """Reason the generated tests can never run, or None. Lazy import: see grade_submission."""
        from tools.code_executor import check_test_artifact

        return check_test_artifact(unit_tests)


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
    logger.info("Grader: grading %s submission (%d chars)", exercise_format, len(solution_text))
    if exercise_format == "coding_challenge":
        # Lazy import keeps the code-execution surface out of the module-import path.
        from tools.code_executor import execute_tests

        # Join with "\n" (not "\n\n"): the grader sometimes returns the test module split into
        # per-line fragments; a single newline reconstructs it faithfully (indentation preserved).
        tests = artifact.get("unit_tests") or []
        result = execute_tests(solution_text, "\n".join(tests))
        logger.info(
            "Grader: coding result %s/%s passed (score=%s)",
            (result or {}).get("passed"), (result or {}).get("total"), (result or {}).get("score"),
        )
        return result

    return _grade_case_study(solution_text, artifact)


def _grade_case_study(solution_text: str, artifact: dict) -> Optional[dict]:
    rubric = artifact.get("rubric") or []
    rubric_text = "\n".join(
        f"- {c.get('criterion')} (weight {c.get('weight')})" for c in rubric
    ) or "- Overall quality (weight 100)"

    system_template = SystemMessagePromptTemplate.from_template(GRADER_RUBRIC_SCORING_SYSTEM_PROMPT)
    human_template = HumanMessagePromptTemplate.from_template(_RUBRIC_HUMAN_TEMPLATE)
    chat_prompt = ChatPromptTemplate.from_messages([system_template, human_template])
    structured_llm = llm.with_structured_output(RubricScore, method="json_schema")

    logger.info("Grader: scoring case-study submission against rubric")
    try:
        messages = chat_prompt.format_messages(rubric=rubric_text, submission=solution_text)
        result = structured_llm.invoke(messages)
        return result.model_dump()
    except Exception:
        logger.exception("Grader: error scoring case study")
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
