import os
import time
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from collections import defaultdict, deque

app = FastAPI(title="TokenShield Gateway")

# Retrieve API keys from environment variables for security
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- RECONFIGURED CIRCUIT BREAKER ENGINE ---
# Real-world agents loop incredibly fast. Humans don't.
# If a single session makes more than 4 requests in 10 seconds, it's a runaway loop.
MAX_REQUESTS_IN_WINDOW = 4
TIME_WINDOW_SECONDS = 10.0

# Memory state: stores timestamps of recent requests per session
# Structure: { session_id: deque([timestamp1, timestamp2, ...]) }
session_timestamps = defaultdict(lambda: deque(maxlen=MAX_REQUESTS_IN_WINDOW))

def get_session_id(request: Request) -> str:
    """Extracts a reliable, isolated identifier for the calling client session."""
    # Prioritize custom app identifier header, then host IP
    x_session = request.headers.get("X-Session-ID", "")
    if x_session:
        return x_session
    return request.client.host if request.client else "global"

@app.post("/v1/chat/completions")
async def token_shield_proxy(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload received.")

    # Validate presence of messages
    if not body.get("messages"):
        raise HTTPException(status_code=400, detail="Missing 'messages' array in payload.")
    
    # 1. TIME-VELOCITY LOOP CASCADE DETECTION
    session_id = get_session_id(request)
    current_time = time.time()
    timestamps = session_timestamps[session_id]

    # Clean out older timestamps outside our evaluation window
    while timestamps and (current_time - timestamps[0] > TIME_WINDOW_SECONDS):
        timestamps.popleft()

    # Check if this rapid iteration trips our velocity threshold
    if len(timestamps) >= MAX_REQUESTS_IN_WINDOW - 1:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "message": "TokenShield: High-frequency agent loop cascade detected at the network layer. Request blocked.",
                    "type": "loop_cascade_exception",
                    "code": 429
                }
            }
        )
    
    # Track the current request execution timestamp
    timestamps.append(current_time)

    # 2. PROVIDER DETECTION & DYNAMIC DOWNSTREAM ROUTING
    target_model = body.get("model", "").lower()
    
    if "gemini" in target_model:
        if not GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="Gemini API Key missing on server environment.")
        target_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        headers = {"Authorization": f"Bearer {GEMINI_API_KEY}", "Content-Type": "application/json"}
    elif "gpt" in target_model or "openai" in target_model:
        if not OPENAI_API_KEY:
            raise HTTPException(status_code=500, detail="OpenAI API Key missing on server environment.")
        target_url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported model target '{body.get('model')}'. TokenShield manages Gemini and OpenAI routing flags."
        )

    # 3. CLEAN NETWORK DISPATCH W/ FIXED LIFECYCLES
    is_streaming = body.get("stream", False)

    if is_streaming:
        # Client lifecycle is bound inside the stream generator block safely
        async def stream_generator():
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", target_url, json=body, headers=headers) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    
    else:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(target_url, json=body, headers=headers)
            return JSONResponse(status_code=response.status_code, content=response.json())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)