import os
import sys
import time
import uuid
from openai import OpenAI

# Generate a unique session key to isolate sliding windows across different runs
unique_session_key = f"session_{uuid.uuid4().hex}"

# 1. Route the application through the local TokenShield Proxy Gateway
client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key=unique_session_key
)

def run_research_pipeline(user_prompt):
    print(f"\n⚡ Starting Research Pipeline for topic: '{user_prompt}'")
    
    # Store the conversation state between the two agents
    current_draft = "Initial structural layout pending."
    editor_feedback = "No feedback generated yet."
    
    # The application allows up to 10 iterations for deep refining refinement
    for revision_turn in range(1, 11):
        print(f"🔄 Revision Round {revision_turn} initializing...")
        
        try:
            # --- AGENT 1: THE WRITER ---
            writer_response = client.chat.completions.create(
                model="gemini-3.1-flash-lite",
                messages=[
                    {"role": "system", "content": "You are a professional academic writer. Draft an essay layout. You must strictly incorporate the editor's feedback inside your new draft iteration."},
                    {"role": "user", "content": f"Topic: {user_prompt}. Previous Draft: {current_draft}. Editor Notes: {editor_feedback}"}
                ]
            )
            current_draft = writer_response.choices[0].message.content
            
            # --- AGENT 2: THE EDITOR ---
            editor_response = client.chat.completions.create(
                model="gemini-3.1-flash-lite",
                messages=[
                    {"role": "system", "content": "You are a ruthless factual editor. Review the provided text layout. If the core argument is fundamentally illogical, contradictory, or impossible, reply with 'REJECTED:' followed by why it fails. Do not accept bad logic."},
                    {"role": "user", "content": f"Review this draft text: {current_draft}"}
                ]
            )
            editor_feedback = editor_response.choices[0].message.content
            
            print(f"   • Writer completed draft update.")
            print(f"   • Editor response status: {editor_feedback[:50]}...")
            
            # If the editor is satisfied and doesn't reject it, the loop completes successfully!
            if "REJECTED" not in editor_feedback:
                print("\n✅ Final Report Approved Successfully!")
                print(current_draft[:200])
                return
                
            time.sleep(0.5) # Slight pacing break
            
        except Exception as e:
            print("\n🛡️ [APPLICATION GUARDRAIL ACTIVATED]")
            print(f"The proxy server forcibly cut the agent communication line to prevent a cost runway explosion.")
            print(f"Error captured: {str(e)}")
            sys.exit(0)

if __name__ == "__main__":
    # Simulate a real user interacting with your script interface
    print("--- Welcome to the AI Research Workspace ---")
    topic = input("Enter research topic: ")
    run_research_pipeline(topic)