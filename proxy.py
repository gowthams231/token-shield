import os
import time
import httpx
import asyncio
import hashlib
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from collections import defaultdict
from dotenv import load_dotenv

# Load all configurations from the local .env file
load_dotenv()

# --- ⚙️ DYNAMIC CONFIGURATION LOADER ---
HOST_GEMINI_KEY = os.getenv("GEMINI_API_KEY")
HOST_OPENAI_KEY = os.getenv("OPENAI_API_KEY")
HOST_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")

try:
    WINDOW_SIZE_SECONDS = int(os.getenv("WINDOW_SIZE_SECONDS", 60))
    MAX_DUPLICATE_REPEATS = int(os.getenv("MAX_DUPLICATE_REPEATS", 3))
    MAX_TOTAL_REQUESTS = int(os.getenv("MAX_TOTAL_REQUESTS", 15))
except ValueError:
    print("⚠️ Invalid integer found in .env settings. Falling back to baseline defaults.")
    WINDOW_SIZE_SECONDS = 60
    MAX_DUPLICATE_REPEATS = 3
    MAX_TOTAL_REQUESTS = 15

# Global pricing tracker
LIVE_MODEL_PRICING = {}
total_dollars_saved = 0.0
http_client: httpx.AsyncClient = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, LIVE_MODEL_PRICING
    
    print("🚀 Initializing TokenShield Gateway Settings...")
    print(f"    • Sliding Window Size: {WINDOW_SIZE_SECONDS} seconds")
    print(f"    • Max Duplicate Repeats allowed: {MAX_DUPLICATE_REPEATS}")
    print(f"    • Absolute Speed Limit: {MAX_TOTAL_REQUESTS} requests per window")
    
    if not any([HOST_GEMINI_KEY, HOST_OPENAI_KEY, HOST_ANTHROPIC_KEY]):
        print("⚠️ Warning: No local API keys found in your .env file! Ensure clients pass their own.")

    http_client = httpx.AsyncClient(
        timeout=60.0,
        limits=httpx.Limits(max_connections=200, max_keepalive_connections=50)
    )
    
    try:
        print("🔄 Fetching live global AI market pricing metrics...")
        response = await http_client.get("https://openrouter.ai/api/v1/models")
        if response.status_code == 200:
            data = response.json().get("data", [])
            for model in data:
                model_id = model.get("id", "").split("/")[-1].lower()
                prompt_cost = float(model.get("pricing", {}).get("prompt", 0.0))
                if model_id:
                    LIVE_MODEL_PRICING[model_id] = prompt_cost
            print(f"✅ Cached {len(LIVE_MODEL_PRICING)} live model prices dynamically.")
        else:
            print("⚠️ Live pricing fetch failed. Using fallback estimation curves.")
    except Exception as e:
        print(f"🚨 Network error fetching live pricing: {e}. Using baseline profiles.")

    yield
    await http_client.aclose()

app = FastAPI(title="TokenShield Enterprise Gateway", lifespan=lifespan)

# Stores history as lists of tuples: (timestamp, current_action_hash, last_assistant_response_hash)
session_history = defaultdict(list)
state_lock = asyncio.Lock()

def get_session_id(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        return auth_header
    return request.client.host if request.client else "global-fallback"

def normalize_and_hash(text: str) -> str:
    """Helper to strip out dynamic noise like timestamps/IDs for structural consistency"""
    import re
    text = re.sub(r'\d{2}:\d{2}:\d{2}', '', text)
    text = re.sub(r'\d{4}-\d{2}-\d{2}', '', text)
    text = re.sub(r'\b[0-9a-fA-F]{8,}\b', '', text)
    clean_text = " ".join(text.split()).lower()
    return hashlib.md5(clean_text.encode("utf-8")).hexdigest()

@app.post("/v1/chat/completions")
async def token_shield_proxy(request: Request):
    global total_dollars_saved, session_history
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload received.")

    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="Missing 'messages' array in payload.")
    
    session_id = get_session_id(request)
    current_time = time.time()
    
    # Isolate current active context fields
    last_user_content = ""
    last_assistant_content = ""
    
    for msg in reversed(messages):
        role = msg.get("role", "")
        content = msg.get("content", "")
        content_str = content if isinstance(content, str) else str(content)
        
        if role in ["user", "tool", "system"] and not last_user_content:
            last_user_content = content_str
        elif role == "assistant" and not last_assistant_content:
            last_assistant_content = content_str
            
        if last_user_content and last_assistant_content:
            break

    current_action_hash = normalize_and_hash(last_user_content)
    last_response_hash = normalize_and_hash(last_assistant_content)
    
    extracted_parts = [msg.get("content", "") for msg in messages if isinstance(msg.get("content"), str)]
    raw_text = " ".join(extracted_parts)
    estimated_tokens = len(raw_text) / 4
    
    async with state_lock:
        session_history[session_id] = [
            item for item in session_history[session_id] 
            if current_time - item[0] < WINDOW_SIZE_SECONDS
        ]
        
        duplicate_count = 0
        for item in session_history[session_id]:
            past_action = item[1]
            past_response = item[2]
            if past_action == current_action_hash and past_response == last_response_hash:
                duplicate_count += 1
                
        total_requests = len(session_history[session_id])
        
        is_loop = (duplicate_count + 1) >= MAX_DUPLICATE_REPEATS
        is_flood = total_requests > MAX_TOTAL_REQUESTS
        
        if is_loop or is_flood:
            status_reason = "LOOPING BEHAVIOR (ZERO MUTATION DIFF)" if is_loop else "CONTEXT FLOODING"
            model_name = body.get("model", "gpt-4o-mini").lower()
            
            cost_per_token = LIVE_MODEL_PRICING.get(model_name, 0.25 / 1000000)
            single_request_cost = estimated_tokens * cost_per_token
            
            burn_rate_per_minute = single_request_cost * 300
            projected_10_min_loss = burn_rate_per_minute * 10
            projected_1_hour_loss = burn_rate_per_minute * 60
            
            total_dollars_saved += single_request_cost
            
            print(f"\n🛡️ [TokenShield Threat Intercept Report]")
            print(f"   Status: VELOCITY ANOMALY DETECTED ({status_reason})")
            print(f"   Model Target: {model_name}")
            print(f"   Requests in Sliding Window: {total_requests} / {MAX_TOTAL_REQUESTS}")
            print(f"   Zero-Diff Repetitions Caught: {duplicate_count + 1} / {MAX_DUPLICATE_REPEATS}")
            print(f"   ------------------------------------------------")
            print(f"   Immediate Waste Stopped:  ${single_request_cost:.6f}")
            print(f"   🚨 RUNAWAY BURN RATE PROJECTION IF LEFT UNCHECKED:")
            print(f"      • Burn Rate / Min:     ${burn_rate_per_minute:.4f}")
            print(f"      • Lost in 10 Minutes:  ${projected_10_min_loss:.2f}")
            print(f"      • Lost in 1 Hour:      ${projected_1_hour_loss:.2f}")
            print(f"   ------------------------------------------------")
            print(f"   📊 TOTAL REPO CAPITAL PROTECTED TO DATE: ${total_dollars_saved:.6f}\n")

            warning_message = (
                f"⚠️ [TokenShield Intercept] Zero-Mutation loop pattern caught!\n"
                f"Runaway cascading loop stopped locally. "
                f"Projected 1 hour savings: ${projected_1_hour_loss:.2f}.\n\n"
                f"Your agent is sending identical commands without any operational state changes. "
                f"Please verify local system tool file permissions before resuming."
            )

            if body.get("stream", False):
                async def generate_mock_stream():
                    import json
                    chunk_id = f"chatcmpl-shield-{int(time.time())}"
                    
                    role_payload = {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model_name,
                        "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(role_payload)}\n\n".encode("utf-8")
                    await asyncio.sleep(0.01)

                    for word in warning_message.split(" "):
                        word_payload = {
                            "id": chunk_id,
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model_name,
                            "choices": [{"index": 0, "delta": {"content": word + " "}, "finish_reason": None}]
                        }
                        yield f"data: {json.dumps(word_payload)}\n\n".encode("utf-8")
                        await asyncio.sleep(0.01)

                    stop_payload = {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model_name,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                    }
                    yield f"data: {json.dumps(stop_payload)}\n\n".encode("utf-8")
                    yield b"data: [DONE]\n\n"

                return StreamingResponse(generate_mock_stream(), media_type="text/event-stream")

            else:
                return JSONResponse(
                    status_code=200,
                    content={
                        "id": f"chatcmpl-shield-{int(time.time())}",
                        "object": "chat.completion",
                        "created": int(time.time()),
                        "model": model_name,
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": warning_message
                                },
                                "finish_reason": "stop"
                              }
                        ],
                        "usage": {
                            "prompt_tokens": int(estimated_tokens),
                            "completion_tokens": 0,
                            "total_tokens": int(estimated_tokens)
                        }
                    }
                )

        session_history[session_id].append((current_time, current_action_hash, last_response_hash))

    # --- 🔀 DYNAMIC PROVIDER ROUTING ---
    target_model = body.get("model", "").lower()
    client_auth = request.headers.get("Authorization")
    client_key = client_auth.replace("Bearer ", "").strip() if client_auth else ""
    
    is_test_session_key = (
        not client_key 
        or "placeholder" in client_key 
        or client_key.startswith("session_")
    )

    if "gemini" in target_model:
        api_key = HOST_GEMINI_KEY if is_test_session_key else client_key
        if not api_key:
            raise HTTPException(status_code=500, detail="Gemini API credentials not found in environment.")
        target_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
    elif "claude" in target_model:
        api_key = HOST_ANTHROPIC_KEY if is_test_session_key else client_key
        if not api_key:
            raise HTTPException(status_code=500, detail="Anthropic API credentials not found in environment.")
        target_url = "https://api.anthropic.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
    elif "gpt" in target_model or "openai" in target_model:
        api_key = f"Bearer {HOST_OPENAI_KEY}" if is_test_session_key else f"Bearer {client_key}"
        if "Bearer None" in api_key or not HOST_OPENAI_KEY:
            if is_test_session_key:
                raise HTTPException(status_code=500, detail="OpenAI API credentials not found in environment.")
        target_url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": api_key, "Content-Type": "application/json"}
        
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported model target request: '{body.get('model')}'")

    # --- 🛰️ UPSTREAM DISPATCH TRANSMISSION ---
    is_streaming = body.get("stream", False)

    if is_streaming:
        async def stream_generator():
            try:
                async with http_client.stream("POST", target_url, json=body, headers=headers) as response:
                    if response.status_code != 200:
                        err_body = await response.aread()
                        print(f"🚨 Upstream error code {response.status_code}")
                        return

                    async for chunk in response.aiter_bytes():
                        yield chunk
            except Exception as e:
                print(f"🚨 Stream crashed: {e}")
                
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    
    else:
        try:
            response = await http_client.post(target_url, json=body, headers=headers)
            try:
                response_data = response.json()
            except Exception:
                response_data = {"error": "Failed to parse response payload.", "raw_body": response.text}
                    
            return JSONResponse(status_code=response.status_code, content=response_data)
        except Exception as e:
            print(f"🚨 Unexpected exception: {e}")
            return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)