import os
import httpx
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from collections import defaultdict

# 1. LIVE MARKET PRICE CACHE STORAGE
# Dictionary structures to track model pricing and aggregate savings metrics
LIVE_MODEL_PRICING = {}
total_dollars_saved = 0.0

http_client: httpx.AsyncClient = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, LIVE_MODEL_PRICING
    # Initialize connection pooling for processing high-velocity traffic safely
    http_client = httpx.AsyncClient(
        timeout=60.0,
        limits=httpx.Limits(max_connections=200, max_keepalive_connections=50)
    )
    
    # DYNAMIC API FETCH: Pull live global AI token costs right at boot up
    try:
        print("🔄 Fetching live global AI market pricing metrics...")
        response = await http_client.get("https://openrouter.ai/api/v1/models")
        if response.status_code == 200:
            data = response.json().get("data", [])
            for model in data:
                # OpenRouter returns pricing in total dollars per raw token (e.g. 0.00000025)
                # We strip the vendor prefix (e.g., 'google/gemini-3.5-flash' -> 'gemini-3.5-flash')
                model_id = model.get("id", "").split("/")[-1].lower()
                prompt_cost = float(model.get("pricing", {}).get("prompt", 0.0))
                
                if model_id:
                    LIVE_MODEL_PRICING[model_id] = prompt_cost
            print(f"✅ Successfully cached {len(LIVE_MODEL_PRICING)} live model prices dynamically.")
        else:
            print("⚠️ Live pricing fetch failed. Falling back to default estimation curves.")
    except Exception as e:
        print(f"🚨 Network error fetching live pricing: {e}. Using baseline profiles.")

    yield
    await http_client.aclose()

app = FastAPI(title="TokenShield Enterprise Gateway", lifespan=lifespan)

# Fallback internal host keys pulled safely from environment context variables
HOST_GEMINI_KEY = os.getenv("GEMINI_API_KEY")
HOST_OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# --- CONCURRENCY SAFE COUNTER ENGINE ---
MAX_CONSECUTIVE_REQUESTS = 4
session_counters = defaultdict(int)
state_lock = asyncio.Lock()

def get_session_id(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        return auth_header
    return request.client.host if request.client else "global-fallback"

@app.post("/v1/chat/completions")
async def token_shield_proxy(request: Request):
    global total_dollars_saved, session_counters
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload received.")

    if not body.get("messages"):
        raise HTTPException(status_code=400, detail="Missing 'messages' array in payload.")
    
    session_id = get_session_id(request)
    
    # 2. ATOMIC GATEWAY CIRCUIT BREAKER & DYNAMIC SAVINGS PROJECTION
    async with state_lock:
        session_counters[session_id] += 1
        current_count = session_counters[session_id]

        if current_count >= MAX_CONSECUTIVE_REQUESTS:
            model_name = body.get("model", "gemini-3.1-flash-lite").lower()
            
            # Count the characters to calculate estimated token metrics (1 token ≈ 4 characters)
            messages = body.get("messages", [])
            raw_text = "".join([msg.get("content", "") for msg in messages])
            estimated_tokens = len(raw_text) / 4
            
            # DYNAMIC LOOKUP: Fetch live tracked token cost from our cached system state memory
            # Baseline absolute safety fallback if model isn't indexed ($0.25 per 1M tokens)
            cost_per_token = LIVE_MODEL_PRICING.get(model_name, 0.25 / 1_000_000)
            
            single_request_cost = estimated_tokens * cost_per_token
            
            # Calculate the Runaway Burn Rate Projections (assumes ~300 loop requests per minute)
            burn_rate_per_minute = single_request_cost * 300
            projected_10_min_loss = burn_rate_per_minute * 10
            projected_1_hour_loss = burn_rate_per_minute * 60
            
            total_dollars_saved += single_request_cost
            
            # Output the dynamic, data-driven balance sheet ledger right to the console
            print(f"\n🛡️ [TokenShield Threat Intercept Report]")
            print(f"   Status: ACTIVE LOOP INTERCEPTED")
            print(f"   Model Target: {model_name}")
            print(f"   Dynamic Live Unit Cost/Token: ${cost_per_token:.10f}")
            print(f"   ------------------------------------------------")
            print(f"   Immediate Waste Stopped:  ${single_request_cost:.6f}")
            print(f"   🚨 RUNAWAY BURN RATE PROJECTION IF LEFT UNCHECKED:")
            print(f"      • Burn Rate / Min:     ${burn_rate_per_minute:.4f}")
            print(f"      • Lost in 10 Minutes:  ${projected_10_min_loss:.2f}")
            print(f"      • Lost in 1 Hour:      ${projected_1_hour_loss:.2f}")
            print(f"   ------------------------------------------------")
            print(f"   📊 TOTAL REPO CAPITAL PROTECTED TO DATE: ${total_dollars_saved:.6f}\n")

            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": f"TokenShield Intercept. Projected 1-hour runway savings: ${projected_1_hour_loss:.2f}",
                        "type": "loop_cascade_exception",
                        "code": 429
                    }
                }
            )

    # 3. DYNAMIC UPSTREAM ROUTING & TOKEN FORWARDING
    target_model = body.get("model", "").lower()
    client_auth = request.headers.get("Authorization")
    
    if "gemini" in target_model:
        api_key = client_auth.replace("Bearer ", "") if (client_auth and "placeholder" not in client_auth) else HOST_GEMINI_KEY
        if not api_key:
            raise HTTPException(status_code=500, detail="Gemini API authentication missing.")
        
        target_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
    elif "gpt" in target_model or "openai" in target_model:
        api_key = client_auth if (client_auth and "placeholder" not in client_auth) else f"Bearer {HOST_OPENAI_KEY}"
        if "Bearer None" in api_key or not HOST_OPENAI_KEY:
            if not client_auth:
                raise HTTPException(status_code=500, detail="OpenAI API authentication missing.")
        
        target_url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": api_key, "Content-Type": "application/json"}
        
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported model target '{body.get('model')}'")

    # 4. NETWORK PAYLOAD DISPATCH PIPELINE
    is_streaming = body.get("stream", False)

    if is_streaming:
        async def stream_generator():
            async with http_client.stream("POST", target_url, json=body, headers=headers) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    
    else:
        response = await http_client.post(target_url, json=body, headers=headers)
        try:
            response_data = response.json()
        except Exception:
            response_data = {"error": "Failed to decode upstream JSON response.", "raw_body": response.text}
                
        return JSONResponse(status_code=response.status_code, content=response_data)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)