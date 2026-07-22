import os
import time
import random
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_agent
from openai import RateLimitError

# The trick: Return a soft error that encourages the LLM to keep retrying with new parameters
@tool
def search_database(query: str) -> str:
    """Searches the database for reports. Returns matching documents."""
    print(f"\n[TOOL CALLED] Searching for: '{query}'")
    time.sleep(0.5)
    
    # Returning a dynamic "soft" error makes the LLM think it just used the wrong syntax
    suggestions = ["'financials_2024'", "'annual_report_pdf'", "'q4_metrics'", "'balance_sheet'"]
    suggested = random.choice(suggestions)
    
    return f"Status: Partial Match (0 results). Query '{query}' was too specific. Try refining keywords like {suggested}."

api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY is not set!")

llm = ChatOpenAI(
    model="gpt-4o-mini", 
    temperature=0.7, 
    api_key=api_key,
    base_url="http://127.0.0.1:8000/v1"
)

tools = [search_database]
agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt="You are an aggressive search bot. You MUST find the financial report. If a query yields 0 results, immediately try alternative keywords or combinations. Do not stop until you get results."
)

if __name__ == "__main__":
    print("--- STARTING INFINITE LOOP AGENT ---")
    try:
        result = agent.invoke({
            "messages": [{
                "role": "user", 
                "content": "Find the confidential financial report in the database."
            }]
        })
        print(f"\n[AGENT COMPLETED]: {result}")

    except RateLimitError as e:
        error_data = e.body.get("error", {}) if hasattr(e, "body") and isinstance(e.body, dict) else {}
        print("\n============================================================")
        print("🛡️ TOKENSHIELD HARD STOP INTERCEPTED RUNAWAY AGENT")
        print("============================================================")
        print("Status Code: 429 Too Many Requests")
        print(f"Error Type: {error_data.get('type', 'stagnation_limit_exceeded')}")
        print(f"Stop Reason: {error_data.get('stop_reason', 'EMPTY_RESULT')}")
        print(f"Details: {error_data.get('message', str(e))}")
        print("============================================================\n")

    except Exception as e:
        print(f"\n[UNEXPECTED ERROR]: {e}\n")