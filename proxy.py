import json
import re
import hashlib
import time
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import StreamingResponse, JSONResponse
import httpx

app = FastAPI(title="TokenShield Gateway Proxy", version="0.2.0")

# UPSTREAM ENDPOINT CONFIGURATION (OpenAI, Ollama, vLLM, Anthropic, etc.)
UPSTREAM_BASE_URL = "https://api.openai.com/v1"

# SLIDING WINDOW MEMORY & STATE TRACKING
# Structure: { session_id: [ { "signature": str, "timestamp": float, "tier1_triggered": bool } ] }
SESSION_HISTORY: Dict[str, List[Dict[str, Any]]] = {}

WINDOW_SIZE = 3  # Track last N turns
STAGNATION_THRESHOLD = 2  # Matches within window required to trigger Tier 1


def canonicalize_payload(payload: Dict[str, Any]) -> str:
    """
    NORMALIZED STATE EXTRACTION (Canonicalization):
    Strips dynamic variable noise (UUIDs, ISO timestamps, whitespace differences)
    to generate a consistent signature for near-identical tool calls.
    """
    payload_str = json.dumps(payload, sort_keys=True)
    
    # Strip UUIDs (v4)
    payload_str = re.sub(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', '<UUID>', payload_str)
    
    # Strip ISO Timestamps
    payload_str = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?', '<TIMESTAMP>', payload_str)
    
    # Normalize Extra Whitespace
    payload_str = re.sub(r'\s+', ' ', payload_str).strip()
    
    # Hash the canonicalized representation
    return hashlib.sha256(payload_str.encode('utf-8')).hexdigest()


def extract_session_id(request: Request, body: Dict[str, Any]) -> str:
    """Extracts session identifier from headers or message payload."""
    return (
        request.headers.get("x-session-id") 
        or request.headers.get("x-user-id") 
        or body.get("user") 
        or "default_session"
    )


def inject_reflection_prompt(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    TIER 1 SOFT STEERING (FORCED REFLECTION STEP):
    Injects a strict system notice requiring the model to output a failure analysis
    and revised strategy before executing any further tool calls.
    """
    reflection_notice = {
        "role": "system",
        "content": (
            "🚨 CRITICAL CIRCUIT BREAKER NOTICE: You are stuck in a tool execution loop repeating "
            "near-identical arguments without progress. Do NOT repeat your previous tool call.\n\n"
            "Before executing any tool, you MUST output a text response answering these two questions:\n"
            "1. FAILURE ANALYSIS: Why did your previous tool call fail or stagnate?\n"
            "2. REVISED STRATEGY: What specific parameter modifications or alternative tools will you use instead?\n\n"
            "If your next step repeats the same failed arguments, your connection will be hard-terminated."
        )
    }
    return messages + [reflection_notice]


@app.post("/v1/chat/completions")
async def chat_completions_proxy(request: Request):
    """Intercepts, normalizes, inspects, and proxies chat completion requests."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    session_id = extract_session_id(request, body)
    messages = body.get("messages", [])

    # Extract the latest request state signature
    signature = canonicalize_payload(body)
    now = time.time()

    # Retrieve or initialize session history
    history = SESSION_HISTORY.get(session_id, [])
    
    # Clean up old window history (keep last WINDOW_SIZE calls)
    history = history[-WINDOW_SIZE:]

    # Count matching canonical signatures in the current sliding window
    matching_count = sum(1 for item in history if item["signature"] == signature)
    previous_tier1_fired = any(item.get("tier1_triggered", False) for item in history)

    # --------------------------------------------------------------------------
    # TIER 2: HARD STOP (Circuit Breaker)
    # --------------------------------------------------------------------------
    # Triggers if Tier 1 was already attempted AND state remains stagnant.
    if matching_count >= STAGNATION_THRESHOLD and previous_tier1_fired:
        print(f"🔴 [TokenShield] TIER 2 HARD STOP TRIGGERED | Session: {session_id}")
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "message": "TokenShield Circuit Breaker: Stagnant retry loop detected across sliding window.",
                    "type": "tokenshield_stagnation_limit_exceeded",
                    "code": "HARD_STOP_CIRCUIT_BROKEN",
                    "stop_reason": "SAME_ARGS_NO_NEW_STATE",
                    "suggestion": "Review workflow logs. The agent failed to re-plan after soft steering."
                }
            }
        )

    # --------------------------------------------------------------------------
    # TIER 1: SOFT STEERING (Forced Reflection Prompt Injection)
    # --------------------------------------------------------------------------
    tier1_triggered = False
    if matching_count >= STAGNATION_THRESHOLD and not previous_tier1_fired:
        print(f"🟡 [TokenShield] TIER 1 SOFT STEERING (FORCED REFLECTION) | Session: {session_id}")
        body["messages"] = inject_reflection_prompt(messages)
        tier1_triggered = True

    # Record current execution state in history
    history.append({
        "signature": signature,
        "timestamp": now,
        "tier1_triggered": tier1_triggered
    })
    SESSION_HISTORY[session_id] = history

    # --------------------------------------------------------------------------
    # UPSTREAM FORWARDING
    # --------------------------------------------------------------------------
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            upstream_response = await client.post(
                f"{UPSTREAM_BASE_URL}/chat/completions",
                json=body,
                headers=headers
            )
            
            return Response(
                content=upstream_response.content,
                status_code=upstream_response.status_code,
                headers=dict(upstream_response.headers)
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502, 
                detail=f"Upstream provider connection error: {str(exc)}"
            )


@app.get("/health")
def health_check():
    """Health check endpoint for Kubernetes / Load Balancer probes."""
    return {"status": "healthy", "service": "TokenShield Gateway Proxy", "version": "0.2.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)