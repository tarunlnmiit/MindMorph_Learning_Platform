# finds github public projects based on assigned task from scout agent 

import sys
import os 
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)


from config import llm
from prompts.practical_prompt import PRACTICAL_SYSTEM_PROMPT
from prompts.prompt_registry_wrapper_method import setup_agent_prompt



class PracticalAgent:
    '''Practical agent that provides hands-on exercises and practical applications to help users solidify their understanding of concepts.'''
    
    def __init__(self, push_to_langsmith: bool = False):
        self.llm = llm
        self.chat_prompt = setup_agent_prompt(
            system_prompt= PRACTICAL_SYSTEM_PROMPT,
            agent_descriptions="Practical Agent: Provides hands-on exercises and practical applications to help users solidify their understanding of concepts.",
            human_template="User Query: {user_query}",
            push_to_langsmith=push_to_langsmith,
            prompt_identifier="practical_agent_system_prompt",
            description="Prompt used by the Practical Agent to provide hands-on exercises and practical applications.",
            tags=["practical", "hands-on", "agent"]
        )


    def provide_practical_advice(self, user_query:str, github_repos=None):
        '''Provides practical advice based on the user query.

        Args:
            user_query: The practical-learning query.
            github_repos: Optional real GitHub repository search results to ground
                the advice in concrete open-source projects. When provided, they are
                appended to the query so the LLM can reference real projects.
        '''

        # Input validation
        if not user_query or not isinstance(user_query, str):
                raise ValueError("User query must be a non-empty string")

        user_query = user_query.strip()
        if len(user_query) == 0:
                raise ValueError("User query cannot be empty after stripping whitespace")

        if github_repos:
            user_query = (
                f"{user_query}\n\n"
                f"Ground your practical advice in these real GitHub projects where relevant:\n"
                f"{github_repos}"
            )

        print("Providing practical advice...")

        try:
             chat_prompt = self.chat_prompt.format_messages(user_query=user_query)
             response = self.llm.invoke(chat_prompt)
             return response
        except Exception as e:
                print(f"Error providing practical advice: {str(e)}")
                return None



