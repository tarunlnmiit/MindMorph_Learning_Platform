from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langsmith import Client
from typing import Optional, List
import requests
from langsmith.utils import LangSmithConflictError


def setup_agent_prompt(
    system_prompt: str,
    agent_descriptions: str,
    human_template: str = "User Query: {user_query}",
    push_to_langsmith: bool = False,
    prompt_identifier: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> ChatPromptTemplate:
    """
    Generic prompt setup utility for any agent.
    
    Args:
        system_prompt: The system prompt template with placeholders
        agent_descriptions: Agent metadata descriptions to inject into system prompt
        human_template: Template for human message (default: "User Query: {user_query}")
        push_to_langsmith: Whether to push the prompt to LangSmith
        prompt_identifier: Unique identifier for the prompt in LangSmith
        description: Description of the prompt for LangSmith
        tags: Tags to associate with the prompt in LangSmith
        
    Returns:
        ChatPromptTemplate configured for the agent
        
    Raises:
        ValueError: If required parameters are missing when pushing to LangSmith
    """
    
    # Format system prompt with agent descriptions
    formatted_system_prompt = system_prompt.format(
        agent_descriptions=agent_descriptions
    )

    # Create message templates
    system_template = SystemMessagePromptTemplate.from_template(formatted_system_prompt)
    human_message_template = HumanMessagePromptTemplate.from_template(human_template)

    # Create chat prompt
    chat_prompt = ChatPromptTemplate.from_messages([system_template, human_message_template])

    # Push to LangSmith if requested
    if push_to_langsmith:
        if not prompt_identifier:
            raise ValueError("prompt_identifier is required when push_to_langsmith is True")
        
        try:
            langsmith_client = Client()
            url = langsmith_client.push_prompt(
                object=chat_prompt,
                description=description or f"Prompt for {prompt_identifier}",
                tags=tags or ["agent", "routing"],
                prompt_identifier=prompt_identifier
            )
            print(f"Prompt '{prompt_identifier}' pushed to LangSmith successfully.")

        except LangSmithConflictError as e:
            # check if the error is specifically about no changes in existing prompt
            if "Nothing to commit" in str(e):
                print(f"No changes detected for prompt '{prompt_identifier}'. Prompt is already at latest version. Skipping push.")
            else:
                print(f"Warning: Conflict error while pushing prompt '{prompt_identifier}' to LangSmith. Error: {str(e)}")

  
        except Exception as e:
           print(f"Warning: Failed to push prompt '{prompt_identifier}' to LangSmith. Error: {str(e)}")
           raise e
    
    return chat_prompt