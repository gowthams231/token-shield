import os
import json
import urllib.request
from fastapi import FastAPI, HTTPException, Request
import uvicorn

app = FastAPI(title="BraveUp Live Toll Booth Proxy")

# Safety Configuration Constants
MAX_ALLOWED_CHARACTERS = 1000  

@app.get("/")
def read_root():
    return {"status": "active", "gateway": "BraveUp Live Proxy Core Engine"}

@app.post("/v1/chat/completions")
async def process_ai_traffic(request: Request):
    # Ensure the API key is active in the environment
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(status_code=500, detail="Proxy Configuration Error: GEMINI_API_KEY missing.")

    # 1. Intercept the network traffic payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload sent to proxy.")
    
    messages = payload.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="No messages payload detected.")
    
    latest_user_message = messages[-1].get("content", "")
    character_count = len(latest_user_message)
    
    print(f"\n🚗 [Toll Booth Entry] Inspecting vehicle message...")
    print(f"   Payload Character Count: {character_count}")
    
    # 2. THE CIRCUIT BREAKER LOGIC
    if character_count > MAX_ALLOWED_CHARACTERS:
        print(f"🛑 [CIRCUIT BREAKER TRIGGERED] Request blocked! Potential token bleed detected.")
        raise HTTPException(
            status_code=429, 
            detail="BraveUp Proxy Safety Block: Request exceeded maximum safe token/character volume."
        )
    
    # 3. Safe Passage - Forwarding to Real Gemini API (OpenAI Compatibility Endpoint)
    print(f"✅ [Toll Booth Exit] Payload verified as safe. Forwarding to Live Gemini Servers...")
    
    # Target Google's OpenAI-compatible network bridge URL
    url = f"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {gemini_key}"
    }
    
    # Re-package the payload to tell Gemini which model to use
    forward_payload = {
        "model": "gemini-3.5-flash",
        "messages": messages
    }
    
    req = urllib.request.Request(
        url, 
        data=json.dumps(forward_payload).encode("utf-8"), 
        headers=headers, 
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = response.read().decode("utf-8")
            live_response = json.loads(res_data)
            print("⚡ [Live Response Received] Successfully routed response back to user application.")
            return live_response
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8")
        print(f"❌ Downstream AI Error: {error_msg}")
        raise HTTPException(status_code=e.code, detail=f"Downstream AI Error: {error_msg}")
    except Exception as e:
        print(f"❌ Network Transport Error: {e}")
        raise HTTPException(status_code=500, detail=f"Proxy Network Error: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)