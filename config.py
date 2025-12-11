from langchain_ollama import ChatOllama

# 1. Ollama LLM configuration

server_url = "http://127.0.0.1:11434"
model_name = "llama3.2:1b"
temperature_setting = 0.1

llm = ChatOllama(base_url=server_url,
              model=model_name,
                temperature=temperature_setting)


