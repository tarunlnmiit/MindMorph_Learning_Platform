# Provides an academically-grounded curriculum/roadmap for a learning topic.
# Replaces the former inline `llm.invoke("You are an Academic Agent...")` call in app.py.

import logging
import sys
import os
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

logger = logging.getLogger(__name__)


from config import llm
from prompts.academic_prompt import ACADEMIC_SYSTEM_PROMPT
from prompts.prompt_registry_wrapper_method import setup_agent_prompt


class AcademicAgent:
    '''Academic agent that grounds a topic in university-style curricula and canonical references.'''

    def __init__(self, push_to_langsmith: bool = False):
        self.llm = llm
        self.chat_prompt = setup_agent_prompt(
            system_prompt=ACADEMIC_SYSTEM_PROMPT,
            agent_descriptions="Academic Agent: Grounds a learning topic in established university curricula and canonical references.",
            human_template="User Query: {user_query}",
            push_to_langsmith=push_to_langsmith,
            prompt_identifier="academic_agent_system_prompt",
            description="Prompt used by the Academic Agent to produce a curriculum/learning roadmap.",
            tags=["academic", "curriculum", "agent"],
        )

    def provide_academic_roadmap(self, user_query: str):
        '''Generates a structured academic roadmap based on the user query.'''

        # Input validation
        if not user_query or not isinstance(user_query, str):
            raise ValueError("User query must be a non-empty string")

        user_query = user_query.strip()
        if len(user_query) == 0:
            raise ValueError("User query cannot be empty after stripping whitespace")

        logger.info("Academic: generating roadmap for %r", user_query)

        try:
            chat_prompt = self.chat_prompt.format_messages(user_query=user_query)
            response = self.llm.invoke(chat_prompt)
            return response
        except Exception:
            logger.exception("Academic: error generating roadmap")
            return None


if __name__ == "__main__":
    agent = AcademicAgent(push_to_langsmith=False)
    result = agent.provide_academic_roadmap("I want to learn Python for data science")
    print(result.content if result else "No result")
