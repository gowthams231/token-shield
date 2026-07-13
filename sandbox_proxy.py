from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from collections import defaultdict, deque

app = FastAPI(title="TokenShield - Zero-Cost Sandbox Proxy")

LOOP_THRESHOLD = 3
WINDOW_SIZE = 5
session_history = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))

@app.post("/v1/chat/completions")
async def sandbox_proxy(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    messages = body.get("messages", [])
    latest_msg = messages[-1].get("content", "") if messages else ""
    target_model = body.get("model", "not-specified")
    
    # Track the sequence of identical messages
    history = session_history["sandbox_client"]
    if history and history[-1] == latest_msg:
        consecutive_repeats = 1
        for msg in reversed(list(history)[:-1]):
            if msg == latest_msg:
                consecutive_repeats += 1
            else:
                break
        
        # Trip the circuit breaker on loop threshold breach
        if consecutive_repeats + 1 >= LOOP_THRESHOLD:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": "TokenShield: [SANDBOX] Infinite agent loop cascade intercepted. Connection severed.",
                        "type": "loop_cascade_exception",
                        "code": 429
                    }
                }
            )
            
    history.append(latest_msg)

    # Return a mocked OpenAI/Gemini compatible response without making a real API call
    return JSONResponse(
        status_code=200,
        content={
            "id": "chatcmpl-sandbox123",
            "object": "chat.completion",
            "model": target_model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"[Sandbox Mode] Received prompt: '{latest_msg}'. TokenShield loop detector evaluated this request successfully."
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 15,
                "total_tokens": 25
            }
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)