import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.orchestrator import OrchestratorAgent

def main():
    print("Welcome to MindMorph Learning Platform!")
    print("Initialize Orchestrator Agent...")
    try:
        agent = OrchestratorAgent()
    except Exception as e:
        print(f"Error initializing agent: {e}")
        # Debugging hint
        if "GROQ_API_KEY" in str(e):
             print("Please ensure your .env file contains the GROQ_API_KEY.")
        return

    print("Agent ready. Type 'exit' or 'quit' to stop.")
    
    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() in ['exit', 'quit']:
                print("Goodbye!")
                break
            
            if not user_input.strip():
                continue
                
            print("MindMorph is thinking...")
            response_data = agent.process_query(user_input)
            
            agent_name = response_data.get('agent', 'UNKNOWN')
            reasoning = response_data.get('reasoning', '')
            content = response_data.get('response', '')

            print(f"\n[Routed to: {agent_name}]")
            print("-" * 50)
            print(content)
            print("-" * 50)
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
