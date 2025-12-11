from agents.agent_metadata import AgentMetadata
from prompts.orchestrator_prompts import ORCHESTRATOR_SYSTEM_PROMPT
from prompts.agent_prompts import SCOUT_PROMPT, CONTENT_PROMPT, EXERCISE_PROMPT, GENERAL_PROMPT
from langchain_core.messages import SystemMessage, HumanMessage
from config import llm
import json


class OrchestratorAgent:

    """Orchestrator agent that routes queries to appropriate sub-agents and generates responses."""
    
    def __init__(self):
        self.llm = llm
        self.agent_metadata = AgentMetadata()
        self.agent_prompts = {
            "SCOUT": SCOUT_PROMPT,
            "CONTENT": CONTENT_PROMPT,
            "EXERCISE": EXERCISE_PROMPT,
            "GENERAL": GENERAL_PROMPT
        }

    def _extract_json(self, text:str) -> dict:
        """Extract JSON object from text response"""
        import re
        try:
            # Match strict JSON object
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                json_str = match.group(0)
                return json.loads(json_str)
            else:
                raise ValueError("No JSON object found in response.")
        except Exception as e:
            # Fallback for simple general queries if JSON fails
            # Log the failure for debugging
            print(f"DEBUG: JSON Parsing Failed for: '{text}'. Error: {e}")
            return {"Assigned_Agent": "GENERAL", "Reasoning": "Fallback due to JSON error.", "User_Query": text}

    def _generate_agent_response(self, agent_name: str, user_query: str) -> str:
        """Generate a response using the specific agent's persona."""
        system_prompt = self.agent_prompts.get(agent_name, GENERAL_PROMPT)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_query)
        ]
        
        response = self.llm.invoke(messages)
        return response.content

    def process_query(self, user_query:str) -> dict:
        """Route user query to appropriate agent and get the response."""

        try:
            # 1. Orchestration Step (Intent Analysis)
            agents_descriptions = self.agent_metadata.get_agent_descriptions()
            # Note: prompts.orchestrator_prompts already has the full prompt, so description injection might be redundant 
            # if the prompt text is hardcoded. Checking the prompt file...
            # The prompt file currently has hardcoded descriptions. 
            # Let's just use the prompt as is.
            
            orchestrator_messages = [
                SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT),
                HumanMessage(content=f"User Query: {user_query}")
            ]

            decision_response = self.llm.invoke(orchestrator_messages)
            decision = self._extract_json(decision_response.content)

            assigned_agent = decision.get("Assigned_Agent", "GENERAL").upper()
            reasoning = decision.get("Reasoning", "No reasoning provided.")

            # 2. Generation Step (Get the actual answer)
            agent_response = self._generate_agent_response(assigned_agent, user_query)

            return {
                "agent": assigned_agent,
                "reasoning": reasoning,
                "response": agent_response
            }

        except Exception as e:
            return {
                "agent": "ERROR",
                "reasoning": f"An error occurred: {str(e)}",
                "response": "I apologize, but I encountered an error while processing your request."
            }
