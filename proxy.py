import os
import time
import httpx
import asyncio
import hashlib
import json
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

# --- ⚙️ CONFIGURATION LOADER ---
HOST_GEMINI_KEY = os.getenv("GEMINI_API_KEY")
HOST_OPENAI_KEY = os.getenv("OPENAI_API_KEY")
HOST_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")

try:
    WINDOW_SIZE_SECONDS = int(os.getenv("WINDOW_SIZE_SECONDS", 60))
    STRICT_DUPLICATE_LIMIT = int(os.getenv("STRICT_DUPLICATE_LIMIT", 2))        # Soft steer threshold
    CONSECUTIVE_STAGNANT_LIMIT = int(os.getenv("CONSECUTIVE_STAGNANT_LIMIT", 5)) # Hard stop threshold
    MAX_TOTAL_REQUESTS = int(os.getenv("MAX_TOTAL_REQUESTS", 15))
except ValueError:
    print("⚠️ Invalid integer found in .env settings. Falling back to baseline defaults.")
    WINDOW_SIZE_SECONDS = 60
    STRICT_DUPLICATE_LIMIT = 2
    CONSECUTIVE_STAGNANT_LIMIT = 5
    MAX_TOTAL_REQUESTS = 15

LIVE_MODEL_PRICING = {}
total_dollars_saved = 0.0
http_client: httpx.AsyncClient = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, LIVE_MODEL_PRICING
    
    print("🚀 Initializing TokenShield Enterprise Gateway (Hybrid Engine)...")
    print(f"    • Sliding Window Size: {WINDOW_SIZE_SECONDS}s")
    print(f"    • Tier 1 Soft Steer Limit: {STRICT_DUPLICATE_LIMIT} repeats")
    print(f"    • Tier 2 Hard Stop Limit: {CONSECUTIVE_STAGNANT_LIMIT} consecutive attempts")
    print(f"    • Absolute Speed Limit: {MAX_TOTAL_REQUESTS} requests/window")
    
    http_client = httpx.AsyncClient(
        timeout=60.0,
        limits=httpx.Limits(max_connections=200, max_keepalive_connections=50)
    )
    
    try:
        response = await http_client.get("https://openrouter.ai/api/v1/models")
        if response.status_code == 200:
            data = response.json().get("data", [])
            for model in data:
                model_id = model.get("id", "").split("/")[-1].lower()
                prompt_cost = float(model.get("pricing", {}).get("prompt", 0.0))
                if model_id:
                    LIVE_MODEL_PRICING[model_id] = prompt_cost
            print(f"✅ Cached {len(LIVE_MODEL_PRICING)} live model prices.")
    except Exception as e:
        print(f"🚨 Pricing fetch failed ({e}). Using baseline estimates.")

    yield
    await http_client.aclose()

app = FastAPI(title="TokenShield Enterprise Gateway", lifespan=lifespan)

# Session history format: tuple -> (timestamp, strict_arg_hash, tool_stagnant_hash, error_family, tool_name)
session_history = defaultdict(list)
state_lock = asyncio.Lock()

def get_session_id(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        return auth_header
    return request.client.host if request.client else "global_fallback"

def normalize_text(text: str) -> str:
    """Strips timestamps, IDs, UUIDs, extra spaces, and normalizes casing"""
    text = re.sub(r'\d{2}:\d{2}:\d{2}', '', text)
    text = re.sub(r'\d{4}-\d{2}-\d{2}', '', text)
    text = re.sub(r'\b[0-9a-fA-F]{8,}\b', '', text)
    text = re.sub(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b', '', text)
    return " ".join(text.split()).lower()

def classify_error_family(content_str: str) -> str:
    """Classifies tool or plain content responses into human-scannable categories"""
    c = content_str.lower()
    if any(k in c for k in ["0 results", "partial match", "not found", "empty", "no match"]):
        return "EMPTY_RESULT"
    if any(k in c for k in ["401", "403", "unauthorized", "forbidden", "permission"]):
        return "AUTH_OR_PERMISSION_DENIED"
    if any(k in c for k in ["invalid", "schema", "validation", "bad request", "syntaxerror"]):
        return "INVALID_SCHEMA_OR_SYNTAX"
    if any(k in c for k in ["timeout", "500", "502", "503", "504"]):
        return "TRANSIENT_NETWORK_FAILURE"
    return "GENERIC_STAGNATION"

def extract_hybrid_signatures(messages: list):
    """
    Extracts TWO distinct signature hashes:
    1. strict_arg_hash: tool_name + normalized_args + error_family (for duplicate payloads)
    2. tool_stagnant_hash: tool_name + error_family (ignores args, catches dynamic keyword mutations)
    """
    last_tool_output = ""
    last_tool_name = ""
    last_tool_args = ""

    for msg in reversed(messages):
        role = msg.get("role", "")
        
        if role in ["tool", "function"] and not last_tool_output:
            content = msg.get("content", "")
            last_tool_output = content if isinstance(content, str) else str(content)

        if role == "assistant" and not last_tool_name:
            tool_calls = msg.get("tool_calls", [])
            if tool_calls and isinstance(tool_calls, list):
                first_call = tool_calls[0]
                if isinstance(first_call, dict):
                    func_info = first_call.get("function", {})
                    last_tool_name = func_info.get("name", "")
                    last_tool_args = func_info.get("arguments", "")

        if last_tool_output and last_tool_name:
            break

    if not last_tool_output:
        for msg in reversed(messages):
            if msg.get("role") in ["user", "system"]:
                content = msg.get("content", "")
                last_tool_output = content if isinstance(content, str) else str(content)
                break

    error_family = classify_error_family(last_tool_output)
    
    # Signature 1: Strict payload match
    strict_sig = f"{last_tool_name}:{normalize_text(str(last_tool_args))}:{error_family}"
    strict_arg_hash = hashlib.md5(strict_sig.encode("utf-8")).hexdigest()

    # Signature 2: Tool level stagnation match (ignores query variations)
    stagnant_sig = f"{last_tool_name}:{error_family}"
    tool_stagnant_hash = hashlib.md5(stagnant_sig.encode("utf-8")).hexdigest()
    
    return strict_arg_hash, tool_stagnant_hash, error_family, last_tool_name

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
    
    strict_arg_hash, tool_stagnant_hash, error_family, tool_name = extract_hybrid_signatures(messages)
    
    extracted_parts = [msg.get("content", "") for msg in messages if isinstance(msg.get("content"), str)]
    raw_text = " ".join(extracted_parts)
    estimated_tokens = len(raw_text) / 4
    
    async with state_lock:
        # Clean sliding window
        session_history[session_id] = [
            item for item in session_history[session_id] 
            if current_time - item[0] < WINDOW_SIZE_SECONDS
        ]
        
        # 1. ALWAYS RECORD THE INCOMING FRAME FIRST
        session_history[session_id].append((current_time, strict_arg_hash, tool_stagnant_hash, error_family, tool_name))
        
        # 2. CALCULATE REPEAT COUNTS FROM THE SLIDING WINDOW
        strict_duplicate_count = 0
        consecutive_stagnant_count = 0
        
        for item in session_history[session_id]:
            past_strict_hash = item[1]
            past_stagnant_hash = item[2]
            
            if past_strict_hash == strict_arg_hash:
                strict_duplicate_count += 1
                
            if past_stagnant_hash == tool_stagnant_hash:
                consecutive_stagnant_count += 1
                
        total_requests = len(session_history[session_id])
        
        # 3. INTERVENTION THRESHOLDS
        is_hard_stop = (consecutive_stagnant_count >= CONSECUTIVE_STAGNANT_LIMIT) or (strict_duplicate_count >= CONSECUTIVE_STAGNANT_LIMIT)
        is_soft_steer = (strict_duplicate_count >= STRICT_DUPLICATE_LIMIT)
        is_flood = (total_requests > MAX_TOTAL_REQUESTS)
        
        # 4. TIER 2 HARD STOP (Evaluated First)
        if is_hard_stop or is_flood:
            model_name = body.get("model", "gpt-4o-mini").lower()
            cost_per_token = LIVE_MODEL_PRICING.get(model_name, 0.25 / 1000000)
            single_request_cost = estimated_tokens * cost_per_token
            
            burn_rate_per_minute = single_request_cost * 300
            projected_10_min_loss = burn_rate_per_minute * 10
            projected_1_hour_loss = burn_rate_per_minute * 60
            
            total_dollars_saved += single_request_cost

            status_reason = f"HARD STOP ({error_family})" if is_hard_stop else "CONTEXT FLOODING"
            
            print(f"\n🛡️ [TokenShield Threat Intercept Report]")
            print(f"   Status: VELOCITY ANOMALY DETECTED ({status_reason})")
            print(f"   Target Tool: {tool_name or 'N/A'} | Error Family: {error_family}")
            print(f"   Model Target: {model_name}")
            print(f"   Requests in Sliding Window: {total_requests} / {MAX_TOTAL_REQUESTS}")
            print(f"   Consecutive Stagnant Repeats: {consecutive_stagnant_count} / {CONSECUTIVE_STAGNANT_LIMIT}")
            print(f"   ------------------------------------------------")
            print(f"   Immediate Waste Stopped:  ${single_request_cost:.6f}")
            print(f"   🚨 RUNAWAY BURN RATE PROJECTION IF LEFT UNCHECKED:")
            print(f"      • Burn Rate / Min:     ${burn_rate_per_minute:.4f}")
            print(f"      • Lost in 10 Minutes:  ${projected_10_min_loss:.2f}")
            print(f"      • Lost in 1 Hour:      ${projected_1_hour_loss:.2f}")
            print(f"   ------------------------------------------------")
            print(f"   📊 TOTAL REPO CAPITAL PROTECTED TO DATE: ${total_dollars_saved:.6f}\n")

            warning_message = (
                f"⚠️ [TokenShield Hard Intercept] Execution Halted!\n"
                f"Categorized Stop Reason: {error_family}.\n"
                f"Runaway cascading loop stopped locally. Projected 1 hour savings: ${projected_1_hour_loss:.2f}.\n\n"
                f"Your agent reached {consecutive_stagnant_count} consecutive stagnant attempts. "
                f"Connection terminated to protect API budget."
            )

            if body.get("stream", False):
                async def generate_mock_stream():
                    chunk_id = f"chatcmpl_shield_{int(time.time())}"
                    role_payload = {
                        "id": chunk_id, "object": "chat.completion.chunk", "created": int(time.time()),
                        "model": model_name, "choices": [{"index": 0, "delta": {"role": "assistant", "content": warning_message}, "finish_reason": "stop"}]
                    }
                    yield f"data: {json.dumps(role_payload)}\n\n".encode("utf-8")
                    yield b"data: [DONE]\n\n"

                return StreamingResponse(generate_mock_stream(), media_type="text/event-stream")
            else:
                return JSONResponse(status_code=200, content={
                    "id": f"chatcmpl_shield_{int(time.time())}",
                    "object": "chat.completion", "created": int(time.time()), "model": model_name,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": warning_message}, "finish_reason": "stop"}]
                })

        # 5. TIER 1 SOFT STEER (Evaluated Second)
        elif is_soft_steer:
            model_name = body.get("model", "gpt-4o-mini").lower()
            tool_label = f"tool '{tool_name}'" if tool_name else "this action"
            
            print(f"\n⚠️ [TokenShield Tier 1 Intercept] SOFT STEERING INJECTED")
            print(f"   Target Tool: {tool_name or 'N/A'} | Error Family: {error_family}")
            print(f"   Strict Argument Repeats: {strict_duplicate_count} / {STRICT_DUPLICATE_LIMIT}")
            print(f"   ------------------------------------------------")
            
            steering_message = (
                f"SYSTEM STEERING INTERCEPT: You have invoked {tool_label} with similar parameters "
                f"resulting in the error '{error_family}'. STOP making identical calls. "
                f"Re-evaluate your parameters and write out a new plan before executing."
            )

            if body.get("stream", False):
                async def stream_soft_steer():
                    chunk_id = f"chatcmpl_shield_steer_{int(time.time())}"
                    role_payload = {
                        "id": chunk_id, "object": "chat.completion.chunk", "created": int(time.time()),
                        "model": model_name, "choices": [{"index": 0, "delta": {"role": "assistant", "content": steering_message}, "finish_reason": "stop"}]
                    }
                    yield f"data: {json.dumps(role_payload)}\n\n".encode("utf-8")
                    yield b"data: [DONE]\n\n"
                return StreamingResponse(stream_soft_steer(), media_type="text/event-stream")
            else:
                return JSONResponse(status_code=200, content={
                    "id": f"chatcmpl_shield_steer_{int(time.time())}",
                    "object": "chat.completion", "created": int(time.time()), "model": model_name,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": steering_message}, "finish_reason": "stop"}]
                })

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

    # --- 🛰️ UPSTREAM TRANSMISSION ---
    is_streaming = body.get("stream", False)

    if is_streaming:
        async def stream_generator():
            try:
                async with http_client.stream("POST", target_url, json=body, headers=headers) as response:
                    if response.status_code != 200:
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