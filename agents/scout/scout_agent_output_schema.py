from pydantic import BaseModel, Field
from typing import Dict

class SubAgentQueries(BaseModel):
    ACADEMIC: str = Field(description="Specialized query for the academic agent")
    MARKET: str = Field(description="Specialized query for the market agent")
    PRACTICAL: str = Field(description="Specialized query for the practical agent")

class ScoutOutputSchema(BaseModel):
    original_query: str = Field(description="The user's original query")
    user_context: str = Field(description="Extracted context about the user's background/goals")
    sub_agent_queries: SubAgentQueries
    reasoning: str = Field(description="Reasoning behind these specialized queries")
