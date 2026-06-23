# Example Generator (Content DAG §6.3 tail): produces one grounded worked code example for a lesson.

import logging
import os
import sys
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)

from config import llm
from prompts.example_generator_prompt import (
    EXAMPLE_GENERATOR_HUMAN_TEMPLATE,
    EXAMPLE_GENERATOR_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


def _escape_braces(text: str) -> str:
    """Escape literal braces so ChatPromptTemplate.format_messages doesn't treat lesson code (JSX
    ``{count}``, JS/dict literals) as template variables and raise KeyError (mirrors ContentAgent)."""
    return text.replace("{", "{{").replace("}", "}}")


class ExampleGeneratorAgent:
    """Generates a single worked code example grounded in the synthesized lesson, in the path's
    language. Best-effort: any failure returns None so the lesson still assembles without it."""

    def __init__(self, push_to_langsmith: bool = False):
        self.llm = llm  # default tier — a short, focused snippet, not a large merge
        self.chat_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(EXAMPLE_GENERATOR_SYSTEM_PROMPT),
            HumanMessagePromptTemplate.from_template(EXAMPLE_GENERATOR_HUMAN_TEMPLATE),
        ])
        self.push_to_langsmith = push_to_langsmith

    def generate_example(
        self, lesson: str, user_query: str, path_context: Optional[str] = None
    ) -> Optional[str]:
        """Return a fenced worked example (Markdown), or None on empty input / failure."""
        if not lesson:
            return None
        logger.info("ExampleGenerator: composing worked example for %r", user_query)
        try:
            messages = self.chat_prompt.format_messages(
                lesson=_escape_braces(lesson),
                user_query=_escape_braces(user_query),
                path_context=_escape_braces(path_context or "(none — infer the language from the topic)"),
            )
            text = (self.llm.invoke(messages).content or "").strip()
            return text or None
        except Exception:
            logger.exception("ExampleGenerator: failed; lesson assembles without an example")
            return None
