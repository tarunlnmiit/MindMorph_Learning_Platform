# MindMorph_Learning_Platform
## Running the Orchestrator and Scout agents

### Before you run
- Install Python 3.8+ and Git.
- From repo root:
    - Create and activate a virtual env:
        - Unix/macOS: `python -m venv .venv && source .venv/bin/activate`
        - Windows: `python -m venv .venv && .venv\Scripts\activate`
    - Install dependencies: `pip install -r requirements.txt`
- Configure environment and services:
    - Populate environment variables or `.env` (Setup Groq and LangSmith API keys).
    
### Running the agents
- Run orchestrator (recommended first):
    - `python orchestrator_agent.py`
   
- Run scout:
    - `python scout_agent.py`
    

