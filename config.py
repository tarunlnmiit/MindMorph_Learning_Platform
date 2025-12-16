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