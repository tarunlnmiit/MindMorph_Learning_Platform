# Visual Generator (Content DAG §6.3 tail): produces one Mermaid concept diagram for a lesson.

import logging
import os
import re
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
from prompts.visual_generator_prompt import (
    VISUAL_GENERATOR_HUMAN_TEMPLATE,
    VISUAL_GENERATOR_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

# Accept the output only as a fenced ```mermaid block opening with a real diagram header. Both guards
# matter: the fence is what the frontend routes to the diagram renderer (unfenced text would render as
# prose), and the header guards against the LLM emitting prose inside the fence.
_MERMAID_FENCE = re.compile(r"```mermaid\s")
_MERMAID_HEADER = re.compile(r"\b(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram)\b")


def _escape_braces(text: str) -> str:
    """Escape literal braces so lesson code in the prompt isn't read as a template variable (KeyError)."""
    return text.replace("{", "{{").replace("}", "}}")


class VisualGeneratorAgent:
    """Generates a single Mermaid concept diagram for the lesson. Best-effort: returns None on empty
    input, failure, or output that isn't a recognizable Mermaid diagram (so the lesson degrades to
    text-only rather than rendering a broken block)."""

    def __init__(self, push_to_langsmith: bool = False):
        self.llm = llm
        self.chat_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(VISUAL_GENERATOR_SYSTEM_PROMPT),
            HumanMessagePromptTemplate.from_template(VISUAL_GENERATOR_HUMAN_TEMPLATE),
        ])
        self.push_to_langsmith = push_to_langsmith

    def generate_diagram(self, lesson: str, user_query: str) -> Optional[str]:
        """Return a ```mermaid fenced diagram (Markdown), or None on empty input / failure / non-diagram."""
        if not lesson:
            return None
        logger.info("VisualGenerator: composing diagram for %r", user_query)
        try:
            messages = self.chat_prompt.format_messages(
                lesson=_escape_braces(lesson), user_query=_escape_braces(user_query)
            )
            text = (self.llm.invoke(messages).content or "").strip()
        except Exception:
            logger.exception("VisualGenerator: failed; lesson assembles without a diagram")
            return None
        return text if (text and _MERMAID_FENCE.search(text) and _MERMAID_HEADER.search(text)) else None
