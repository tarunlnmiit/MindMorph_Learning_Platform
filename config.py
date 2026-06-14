import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

model_name = "llama-3.3-70b-versatile" 
temperature_setting = 0.1

if not os.getenv("GROQ_API_KEY"):
    raise ValueError("GROQ_API_KEY not found. Please check your .env file.")

llm = ChatGroq(
    model=model_name,
    temperature=temperature_setting
)

# Persistence (P1 #6). Default targets the local docker-compose Postgres (see docker-compose.yml);
# override via DATABASE_URL in .env for any other deployment. Kept as a default (not a hard raise) so
# the agent/test paths that never touch the DB still import config cleanly.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://mindmorph:mindmorph@localhost:5432/mindmorph",
)
