import sys
import time
import uuid
from openai import OpenAI

# Unique session isolation per run
unique_session_key = f"session_{uuid.uuid4().hex}"

# Connect through TokenShield local gateway
client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key=unique_session_key
)

def run_research_pipeline(user_prompt: str):
    print(f"\n⚡ Starting Agent Research Pipeline for: '{user_prompt}'")
    
    current_draft = "Initial layout."
    editor_feedback = "Pending initial review."
    
    for revision_turn in range(1, 10):
        print(f"\n🔄 [Turn {revision_turn}] Processing agent interaction...")
        
        try:
            if user_prompt.lower() == "loop":
                current_draft = "Static loop payload: Water is dry and fire is freezing."
                editor_feedback = "REJECTED: Physics violation."
            
            # 1. WRITER AGENT
            writer_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an academic writer. Draft an essay layout."},
                    {"role": "user", "content": f"Topic: {user_prompt}. Draft: {current_draft}. Feedback: {editor_feedback}"}
                ]
            )
            writer_content = writer_response.choices[0].message.content
            print(f"   • Writer completed turn.")

            # Check if TokenShield proxy returned an intercept message
            if "SYSTEM STEERING INTERCEPT" in writer_content:
                print("\n⚠️ [APPLICATION DETECTED TIER 1 SOFT STEER]")
                print("TokenShield instructed the agent to stop repeating and re-plan.")
                print(f"Steering Payload:\n{writer_content}\n")
                
            elif "TokenShield Hard Intercept" in writer_content:
                print("\n🛡️ [APPLICATION DETECTED TIER 2 HARD STOP]")
                print("TokenShield circuit breaker pulled the plug on a runaway loop!")
                print(f"Intercept Report:\n{writer_content}\n")
                sys.exit(0)

            time.sleep(0.5)

        except Exception as e:
            print(f"\n🛡️ Connection terminated by TokenShield Proxy: {e}")
            sys.exit(0)

if __name__ == "__main__":
    print("==================================================")
    print("🛡️ TokenShield Multi-Agent Workspace Demo")
    print("==================================================")
    print("💡 Options:")
    print("   • Type 'Quantum Computing' for normal workflow")
    print("   • Type 'loop' to simulate an agent loop")
    print("==================================================")
    
    topic = input("Enter prompt: ")
    run_research_pipeline(topic)