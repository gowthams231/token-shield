import os
import json
from fastapi import FastAPI, HTTPException, Request
import uvicorn

app = FastAPI(title="BraveUp Prompt Intelligence Sandbox Proxy")

# In-memory tracking state to analyze prompt behavior
LAST_PROMPT_SEEN = ""
PROMPT_REPEAT_COUNT = 0
TOTAL_TOKENS_CONSUMED = 0

# Guardrails Configuration
MAX_BUDGET_TOKENS = 5000
LOOP_DETECTION_THRESHOLD = 3

@app.get("/")
def read_root():
    return {"status": "active", "gateway": "BraveUp Offline Sandbox Core"}

@app.post("/v1/chat/completions")
async def process_ai_traffic(request: Request):
    global LAST_PROMPT_SEEN, PROMPT_REPEAT_COUNT, TOTAL_TOKENS_CONSUMED
    
    # 1. Intercept the network traffic payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")
    
    messages = payload.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="No messages payload detected.")
    
    latest_user_message = messages[-1].get("content", "").strip()
    
    # ----------------------------------------------------------------
    # 🧠 PROMPT INTELLIGENCE ENGINE
    # ----------------------------------------------------------------
    
    # Track Framework Prompt Loop Cascades
    if latest_user_message == LAST_PROMPT_SEEN and len(latest_user_message) > 0:
        PROMPT_REPEAT_COUNT += 1
        print(f"⚠️ [WARNING] Duplicate prompt detected! Repeat count: {PROMPT_REPEAT_COUNT}")
    else:
        PROMPT_REPEAT_COUNT = 1 # Set to 1 for the first time we see this prompt
        print(f"🚗 [Toll Booth Entry] New prompt signature intercepted: '{latest_user_message}'")
        
    LAST_PROMPT_SEEN = latest_user_message
    
    # Trigger Circuit Breaker if threshold is breached
    if PROMPT_REPEAT_COUNT >= LOOP_DETECTION_THRESHOLD:
        print(f"🛑 [CIRCUIT BREAKER TRIGGERED] Terminating request! AI agent is stuck in an infinite prompt loop.")
        raise HTTPException(
            status_code=429,
            detail="BraveUp Safety Block: Infinite loop anomaly caught at proxy level."
        )

    # Track Cumulative Budget Spent
    estimated_tokens = int(len(latest_user_message) / 4) + 15
    if TOTAL_TOKENS_CONSUMED + estimated_tokens > MAX_BUDGET_TOKENS:
        print(f"🛑 [BUDGET EXHAUSTED] Safe token consumption ceiling breached.")
        raise HTTPException(
            status_code=402,
            detail="BraveUp Safety Block: Daily token burn budget exceeded."
        )

    # 2. Safe Passage - Send immediate mock response back to user application
    print(f"✅ [Toll Booth Pass] Prompt behavior analyzed as stable. Returning safe mock payload.")
    
    TOTAL_TOKENS_CONSUMED += estimated_tokens
    print(f"📊 [Session Analytics] Current Local Token Accumulation: {TOTAL_TOKENS_CONSUMED}")
    
    return {
        "id": "prox-sandbox-mock",
        "object": "chat.completion",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Mock Response: Your prompt passed the safety gate successfully!"
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": int(len(latest_user_message) / 4),
            "completion_tokens": 15,
            "total_tokens": estimated_tokens
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)