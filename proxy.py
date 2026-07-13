import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from collections import defaultdict, deque

app = FastAPI(title="TokenShield Gateway")

# Retrieve API keys from environment variables for security
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configuration for the circuit breaker
LOOP_THRESHOLD = 3  # Triggers breaker on the 3rd consecutive duplicate prompt
WINDOW_SIZE = 5     # Tracks the last 5 request payloads per session

# Memory state: In-memory store tracking message history per user session/IP
# Structure: { session_id: deque([str, str, ...], maxlen=WINDOW_SIZE) }
session_history = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))

def get_session_id(request: Request) -> str:
    """Extracts a unique identifier for the calling client."""
    # Fallback to authorization header or client IP to distinguish users
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        return auth_header
    return request.client.host if request.client else "global"

@app.post("/v1/chat/completions")
async def token_shield_proxy(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload received.")

    # 1. UNIVERSAL LOOP DETECTION LOGIC (Generic Inbound Gate)
    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="Missing 'messages' array in payload.")
    
    # Extract the string content of the latest user prompt
    latest_msg = messages[-1].get("content", "") if messages else ""
    session_id = get_session_id(request)
    
    # Fetch previous history and analyze for loop patterns
    history = session_history[session_id]
    if history and history[-1] == latest_msg:
        # Check consecutive identical entries
        consecutive_repeats = 1
        for msg in reversed(list(history)[:-1]):
            if msg == latest_msg:
                consecutive_repeats += 1
            else:
                break
        
        # If consecutive duplicate prompts hit the threshold, trip the circuit breaker
        if consecutive_repeats + 1 >= LOOP_THRESHOLD:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": "TokenShield: Infinite agent loop cascade detected at the network layer. Connection severed.",
                        "type": "loop_cascade_exception",
                        "code": 429
                    }
                }
            )
            
    # Append the current verified prompt to the sliding session window
    history.append(latest_msg)

    # 2. PROVIDER DETECTION & DYNAMIC DOWNSTREAM ROUTING (Custom Output Gate)
    target_model = body.get("model", "").lower()
    
    if "gemini" in target_model:
        if not GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="Gemini API Key missing on server environment.")
        # Target Google's native OpenAI-compatible URL structure
        target_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        headers = {
            "Authorization": f"Bearer {GEMINI_API_KEY}",
            "Content-Type": "application/json"
        }
    elif "gpt" in target_model or "openai" in target_model:
        if not OPENAI_API_KEY:
            raise HTTPException(status_code=500, detail="OpenAI API Key missing on server environment.")
        target_url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
    else:
        # Fallback default if provider isn't explicit
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported model target '{body.get('model')}'. TokenShield currently manages Gemini and OpenAI routing flags."
        )

    # 3. NETWORK PAYLOAD DISPATCH
    is_streaming = body.get("stream", False)
    client = httpx.AsyncClient(timeout=60.0)

    if is_streaming:
        # Handle server-sent event (SSE) token chunks seamlessly
        async def stream_generator():
            async with client.stream("POST", target_url, json=body, headers=headers) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    else:
        # Handle standard unified block responses
        async with client as c:
            response = await c.post(target_url, json=body, headers=headers)
            return JSONResponse(status_code=response.status_code, content=response.json())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)