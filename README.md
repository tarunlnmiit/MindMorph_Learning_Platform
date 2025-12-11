# MindMorph Learning Platform

MindMorph is an intelligent learning platform that uses AI agents to personalize your learning journey.

## Features

- **Personalized Learning Paths**: The Scout Agent analyzes your goals and creates a tailored plan.
- **Interactive Exercises**: The Exercise Agent provides hands-on coding challenges.
- **Knowledge Base**: The Content Agent explains complex concepts simply.
- **Smart Routing**: An Orchestrator Agent automatically directs your queries to the right specialist.

## Setup

1.  **Clone the repository**.
2.  **Create a virtual environment**:
    ```bash
    python -m venv .venv
    .\.venv\Scripts\activate
    ```
3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure Environment**:
    - Rename/Copy `.env.example` to `.env` (if applicable) or create `.env`.
    - Add your Groq API Key: `GROQ_API_KEY=gsk_...`

## Usage

Run the application:

```bash
python app.py
```

Type your learning goal or question, and the specific agent will assist you.
