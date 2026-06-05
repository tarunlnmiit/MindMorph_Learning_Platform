# Format Selector (architecture §6.4): decides whether a learning goal is best practised as a
# hands-on coding challenge or an analytical case study.

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
from agents.exercise.exercise_schema import ExerciseFormat

_SYSTEM_PROMPT = """You are the Format Selector for the MindMorph learning platform.

Given a learner's request, choose the single best exercise format:
- 'coding_challenge' when the goal is a programming/implementation skill the learner should practise by
  writing code (functions, algorithms, data structures, scripts).
- 'case_study' when the goal is conceptual, analytical, or design-oriented and best practised by
  reasoning about a realistic scenario rather than writing runnable code.

Return the format and one sentence of reasoning."""

_HUMAN_TEMPLATE = "Learner request: {user_query}\n\nChoose the exercise format."


class FormatSelectorAgent:
    """Picks the exercise format for a learning goal (structured output)."""

    def __init__(self, push_to_langsmith: bool = False):
        self.llm = llm
        self.structured_llm = self.llm.with_structured_output(ExerciseFormat)
        system_template = SystemMessagePromptTemplate.from_template(_SYSTEM_PROMPT)
        human_template = HumanMessagePromptTemplate.from_template(_HUMAN_TEMPLATE)
        self.chat_prompt = ChatPromptTemplate.from_messages([system_template, human_template])

    def select_format(self, user_query: str) -> Optional[ExerciseFormat]:
        """Returns an ExerciseFormat, or None on failure."""
        if not user_query or not isinstance(user_query, str):
            raise ValueError("User query must be a non-empty string")

        logger.info("FormatSelector: choosing exercise format for %r", user_query)
        try:
            result = self.structured_llm.invoke(self.chat_prompt.format_messages(user_query=user_query))
            if result is not None:
                logger.info("FormatSelector: chose %s", getattr(result, "format", None))
            return result
        except Exception:
            logger.exception("FormatSelector: error selecting exercise format")
            return None


if __name__ == "__main__":
    agent = FormatSelectorAgent()
    print(agent.select_format("Teach me recursion in Python with practice"))
