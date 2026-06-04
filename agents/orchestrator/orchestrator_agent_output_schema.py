from pydantic import BaseModel, Field
from typing import  Annotated

class Orchestrator_Output_Schema(BaseModel):
    Assigned_Agent: Annotated[str, Field(description="The agent assigned to handle the user query. Must be one of: SCOUT, CONTENT, EXERCISE.")]
    Reasoning: Annotated[str, Field(description="The reasoning behind the agent assignment.")]