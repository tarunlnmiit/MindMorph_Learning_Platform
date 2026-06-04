import sys
import os
from typing import Optional

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from config import llm
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate
)
from prompts.content_generator_prompt import CONTENT_PROMPTS
from agents.content_generator.content_agent_personality import ContentAgentPersonality

class ContentAgent:
    """
    Content Generator Agent that uses the LLM to generate lessons
    in various formats (Boost, Builder, Sprint).
    """

    def __init__(self, push_to_langsmith: bool = False):
        self.llm = llm
        self.personality = ContentAgentPersonality()
        # Prompt is dynamic based on format. LangSmith client is created lazily
        # only if/when a push is requested (avoids a network client at import time).
        self.push_to_langsmith = push_to_langsmith

    def generate_content(self, user_query: str, format_type: str = "C") -> str:
        """
        Generates content based on the selected format.
        format_type: 'A' (Boost), 'B' (Builder), 'C' (Sprint)
        """
        if not user_query or not isinstance(user_query, str):
            raise ValueError("User query must be a non-empty string")
            
        print(f"ContentAgent: Generating ({format_type}) lesson for '{user_query}'...")
        
        # Select prompt
        system_prompt = CONTENT_PROMPTS.get(format_type.upper(), CONTENT_PROMPTS["C"])
        
        try:
            # Create fresh prompt template for this request
            system_template = SystemMessagePromptTemplate.from_template(system_prompt)
            human_template = HumanMessagePromptTemplate.from_template("Topic: {user_query}")
            chat_prompt = ChatPromptTemplate.from_messages([system_template, human_template])
            
            # TODO: Push to LangSmith if needed (optional logic here)
            
            formatted_prompt = chat_prompt.format_messages(user_query=user_query)
            response = self.llm.invoke(formatted_prompt)
            return response.content
            
        except Exception as e:
            error_msg = f"Error generating content: {str(e)}"
            print(error_msg)
            return error_msg

# Example usage for interactive testing
if __name__ == "__main__":
    agent = ContentAgent(push_to_langsmith=False)
    # Formats: A = 5-min Boost, B = 20-min Builder, C = 2-hour Sprint
    lesson = agent.generate_content("want to learn github", "B")
    print("\n" + "="*50 + "\n")
    print(lesson)
    print("\n" + "="*50 + "\n")
