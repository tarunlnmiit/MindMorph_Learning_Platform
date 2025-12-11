from agent_metadata import  AgentMetadata
from prompts import ORCHESTRATOR_SYSTEM_PROMPT
from langchain_core.messages import SystemMessage, HumanMessage
from orchestrator_agent.config import llm
import json


class OrchestratorAgent:

    """Orchestrator agent that routes queries to appropriate sub-agents"""
    
    def __init__(self):
        self.llm = llm
        self.agent_metadata = AgentMetadata()

    def _extract_json(self, text:str) -> dict:
        """Extract JSON object from text response"""
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            json_str = text[start:end]
            return json.loads(json_str)
        except (ValueError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to extract JSON: {str(e)}")

    

    def  route_query(self, user_query:str) -> str:
        """Route user query to appropriate agent"""

        try:

            agents_descriptions = self.agent_metadata.get_agent_descriptions()
            system_msg = ORCHESTRATOR_SYSTEM_PROMPT.format(agent_descriptions = agents_descriptions).strip()
        

            response = self.llm.invoke([
                SystemMessage(content=system_msg),
                HumanMessage(content= f"User Query: {user_query}")
                ])


            decesion = self._extract_json(response.content)

            if "Assigned_Agent" not in decesion or "Reasoning" not in decesion or "User_Query" not in decesion:
                raise ValueError("Invalid response structure from orchestrator LLM.")
            
            user_query = decesion["User_Query"]
            assigned_agent = decesion["Assigned_Agent"]
            reasoning = decesion["Reasoning"]
            final_response = f"\n -> User Query: {user_query}\n -> Routed to {assigned_agent} agent.\n -> Reasoning: {reasoning}\n"
            

            return final_response

        except Exception as e:
            return f"Error routing query: {str(e)}"


        
agent = OrchestratorAgent()

'''
response = agent.route_query("I want to learn programing and  I am good in maths")
print(response)


response = agent.route_query("Linked list in python")
print(response)

response = agent.route_query("Teach me pointers concept in c language using exercises")
print(response)

response = agent.route_query("Give me coding problems on recursion")
print(response)


response = agent.route_query("generate challenges for learning React")
print(response)


response = agent.route_query("I want to leanrn data science from scratch")
print(response)

response = agent.route_query("I am good computer basics, but want to become a web developer")
print(response)

'''

response = agent.route_query("Explain the concept of polymorphism in OOP")
print(response)
