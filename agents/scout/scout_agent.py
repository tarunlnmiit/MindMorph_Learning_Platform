import sys
import os
from typing import Optional


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from langsmith import Client
from config import llm
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate
)

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage  
from prompts.scout_prompt import SCOUT_SYSTEM_PROMPT
from scout_agents_personalities import scout_agent_personalities


class ScoutAgent:
    '''Scout agent that gathers preliminary information from orchestrator agent output. And routes the query to the evry sub-agent that it has. Before that it generates specialized queries for every sub-agent.'''
    
    def __init__(self, push_to_langsmith: bool = False):
        self.llm = llm
        self.agent_personality = scout_agent_personalities()
        self.langsmith_client = Client()  # Initialize LangSmith client
        self._setup_prompt(push_to_langsmith) # Setup prompt once during initialization



    def _setup_prompt(self, push_to_langsmith: bool = False):
        '''Setup the prompt templates for the scout agent and push to LangSmith if required.'''
        sub_agent_descriptions = self.agent_personality.get_scout_agent_description()

        formatted_system_prompt = SCOUT_SYSTEM_PROMPT.format(
            sub_agent_descriptions = sub_agent_descriptions
        )
        system_template = SystemMessagePromptTemplate.from_template(formatted_system_prompt)
        human_template = HumanMessagePromptTemplate.from_template("User Query: {user_query}")
        self.chat_prompt = ChatPromptTemplate.from_messages([system_template, human_template])

        if push_to_langsmith:
            try:
                self.langsmith_client.push_prompt(
                        object= self.chat_prompt,
                        description="Prompt used by the Scout Agent to generate specialized queries for sub-agents.",
                        tags=["scout", "query generation", "agent"],
                        prompt_identifier="scout_agent_system_prompt" 
                    )
                print("Scout Agent prompt pushed to LangSmith successfully.")
            except Exception as e:
                print(f"Warning: Failed to push scout agent's system prompt to langsmith. Error: {str(e)}")


    def generate_specialized_queries(self, user_query:str):
        '''Generates specialized queries for each sub-agent based on the user query.'''

        # Input validation
        if not user_query or not isinstance(user_query, str):
                raise ValueError("User query must be a non-empty string")
            
        user_query = user_query.strip()
        if len(user_query) == 0:
                raise ValueError("User query cannot be empty after stripping whitespace")
        
        print("Generating specialized queries for sub-agents...")
        
        try:
             chat_prompt = self.chat_prompt.format_messages(user_query=user_query)
             response = self.llm.invoke(chat_prompt) 
             return response
        except Exception as e:
                print(f"Error generating specialized queries: {str(e)}")
                return None
            
            


        
# Example usage
scout_agent = ScoutAgent(push_to_langsmith = False)
response = scout_agent.generate_specialized_queries("I want to learn web development")
print(response.content)
