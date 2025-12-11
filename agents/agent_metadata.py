from enum import Enum
from typing import Dict, Any



class AgentMetadata:
    @classmethod
    def get_agent_descriptions(cls):
        return """
AGENTS AND THEIR GOALS:

1. SCOUT AGENT (The Strategist)
   - Function: Bridging the gap between "Current State" and "Desired Goal".
   - Assign when: The user states a GOAL ("I want to be X") or provides CONTEXT ("I know Y") but lacks a structured path.
   - Core Concept: Navigation, Planning, Sequence.
   - NOT for: Explaining specific concepts or writing code.

2. CONTENT AGENT (The Encyclopedia)
   - Function: Transferring information to the user.
   - Assign when: The user seeks DEFINITIONS, EXPLANATIONS, or THEORETICAL understanding of a specific entity.
   - Core Concept: Knowledge, Theory, Concepts.
   - NOT for: Just listing topics or asking for homework.

3. EXERCISE AGENT (The Trainer)
    - Function: Providing PRACTICAL CODING TASKS for hands-on learning.
    - Assign when: The user wants to apply knowledge, write code, practise exercise, solve a problem, or "try it out".
    - Core Concept: Practice, Application, Hands-on, Implementation.
   - NOT for: Passive reading or high-level planning.

"""
 

    