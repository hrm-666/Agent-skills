import logging
from core.agent import Agent

def run_cli(agent: Agent, initial_query: str = None, interactive: bool = False):
    """CLI 交互界面"""
    if initial_query:
        print(f"\nUser: {initial_query}")
        result = agent.run(initial_query)
        print(f"Agent: {result}")
        return

    print("--- Mini Agent CLI (输入 'exit' 或 'quit' 退出) ---")
    while True:
        try:
            query = input("\nUser> ")
            if query.lower() in ['exit', 'quit']:
                break
            
            if not query.strip():
                continue
                
            print("Thinking...")
            result = agent.run(query)
            print(f"Agent: {result}")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
