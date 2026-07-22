import os
import json
import re
import hashlib
import time
from typing import Dict, Any, List, Tuple
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import JSONResponse
import httpx

app = FastAPI(title="TokenShield Gateway Proxy", version="0.2.2")

UPSTREAM_BASE_URL = os.getenv("UPSTREAM_BASE_URL", "https://api.openai.com/v1")

# SLIDING WINDOW CONFIGURATION
WINDOW_SIZE_SECONDS = int(os.getenv("WINDOW_SIZE_SECONDS", 60))
STRICT_DUPLICATE_LIMIT = int(os.getenv("STRICT_DUPLICATE_LIMIT", 2))      # Tier 1 Soft Steer
CONSECUTIVE_STAGNANT_LIMIT = int(os.getenv("CONSECUTIVE_STAGNANT_LIMIT", 5)) # Tier 2 Hard Stop

# SESSION HISTORY TRACKING
# Format: { session_id: [ (timestamp, strict_arg_hash, tool_stagnant_hash, error_family, tool_name) ] }
SESSION_HISTORY: Dict[str, List[Tuple[float, str, str, str, str]]] = {}


def normalize_text(text: str) -> str:
    """Strips timestamps, IDs, UUIDs, extra spaces, and normalizes casing."""
    text = re.sub(r'\d{2}:\d{2}:\d{2}', '', text)
    text = re.sub(r'\d{4}-\d{2}-\d{2}', '', text)
    text = re.sub(r'\b[0-9a-fA-F]{8,}\b', '', text)
    text = re.sub(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b', '', text)
    return " ".join(text.split()).lower()


def classify_error_family(content_str: str) -> str:
    """Classifies tool outputs or message contents into scannable categories."""
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


def extract_hybrid_signatures(messages: list) -> Tuple[str, str, str, str]:
    """
    EXTRACTS DUAL SIGNATURE HASHES:
    1. strict_arg_hash: tool_name + normalized_args + error_family (catches exact payload retries)
    2. tool_stagnant_hash: tool_name + error_family (ignores query tweaks, catches parameter-shifting loops)
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

    # Signature 2: Tool-level stagnation match (Catches keyword mutations)
    stagnant_sig = f"{last_tool_name}:{error_family}"
    tool_stagnant_hash = hashlib.md5(stagnant_sig.encode("utf-8")).hexdigest()
    
    return strict_arg_hash, tool_stagnant_hash, error_family, last_tool_name


def extract_session_id(request: Request, body: Dict[str, Any]) -> str:
    """Extracts session identifier and redacts raw API keys from terminal logs."""
    raw_session = (
        request.headers.get("x-session-id") 
        or request.headers.get("x-user-id") 
        or body.get("user") 
    )
    if raw_session:
        return raw_session
        
    auth_header = request.headers.get("authorization", "")
    if auth_header:
        key_hash = hashlib.md5(auth_header.encode()).hexdigest()[:8]
        return f"key_{key_hash}"
        
    return "default_session"


def inject_reflection_prompt(messages: List[Dict[str, Any]], tool_name: str, error_family: str) -> List[Dict[str, Any]]:
    """Injects Tier 1 reflection prompt directly into system messages."""
    tool_label = f"tool '{tool_name}'" if tool_name else "this action"
    reflection_notice = {
        "role": "system",
        "content": (
            f"🚨 CRITICAL CIRCUIT BREAKER NOTICE: You have invoked {tool_label} repeatedly "
            f"resulting in the state '{error_family}'. Do NOT repeat near-identical tool calls.\n\n"
            "Before executing any tool, you MUST output a text response answering these two questions:\n"
            "1. FAILURE ANALYSIS: Why did your previous tool call fail or stagnate?\n"
            "2. REVISED STRATEGY: What specific parameter modifications or alternative tools will you use instead?\n\n"
            "If your next step repeats the same stagnant tool pattern, your connection will be hard-terminated."
        )
    }
    return messages + [reflection_notice]


@app.post("/v1/chat/completions")
async def chat_completions_proxy(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="Missing 'messages' array in payload")

    session_id = extract_session_id(request, body)
    now = time.time()

    # Extract hybrid signatures
    strict_arg_hash, tool_stagnant_hash, error_family, tool_name = extract_hybrid_signatures(messages)

    # Clean sliding window
    history = SESSION_HISTORY.get(session_id, [])
    history = [item for item in history if now - item[0] < WINDOW_SIZE_SECONDS]

    # Record current frame
    history.append((now, strict_arg_hash, tool_stagnant_hash, error_family, tool_name))
    SESSION_HISTORY[session_id] = history

    # Calculate stagnation metrics across window
    strict_duplicate_count = sum(1 for item in history if item[1] == strict_arg_hash)
    consecutive_stagnant_count = sum(1 for item in history if item[2] == tool_stagnant_hash)

    # --------------------------------------------------------------------------
    # TIER 2: HARD STOP (Circuit Breaker)
    # --------------------------------------------------------------------------
    if consecutive_stagnant_count >= CONSECUTIVE_STAGNANT_LIMIT or strict_duplicate_count >= CONSECUTIVE_STAGNANT_LIMIT:
        print(f"🔴 [TokenShield] TIER 2 HARD STOP | Session: {session_id} | Tool: {tool_name} | Error: {error_family}")
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "message": f"TokenShield Circuit Breaker: Reached {consecutive_stagnant_count} consecutive stagnant attempts on {tool_name or 'action'}.",
                    "type": "tokenshield_stagnation_limit_exceeded",
                    "code": "HARD_STOP_CIRCUIT_BROKEN",
                    "stop_reason": error_family,
                    "suggestion": "Review workflow logs. The agent failed to re-plan after soft steering."
                }
            }
        )

    # --------------------------------------------------------------------------
    # TIER 1: SOFT STEERING (Inject Reflection Step)
    # --------------------------------------------------------------------------
    tier1_active = False
    if strict_duplicate_count >= STRICT_DUPLICATE_LIMIT or consecutive_stagnant_count >= STRICT_DUPLICATE_LIMIT:
        print(f"🟡 [TokenShield] TIER 1 SOFT STEERING | Session: {session_id} | Tool: {tool_name}")
        body["messages"] = inject_reflection_prompt(messages, tool_name, error_family)
        tier1_active = True

    # --------------------------------------------------------------------------
    # UPSTREAM FORWARDING & HEADER CLEANUP
    # --------------------------------------------------------------------------
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)
    headers.pop("accept-encoding", None)

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            upstream_response = await client.post(
                f"{UPSTREAM_BASE_URL}/chat/completions",
                json=body,
                headers=headers
            )
            
            # Print the model's text reflection response directly in the proxy terminal when Tier 1 fires
            if tier1_active:
                try:
                    res_json = upstream_response.json()
                    model_output = res_json["choices"][0]["message"].get("content", "")
                    if model_output:
                        print(f"\n🧠 [MODEL REFLECTION RESPONSE]:\n{model_output.strip()}\n")
                except Exception:
                    pass

            response_headers = dict(upstream_response.headers)
            response_headers.pop("content-encoding", None)
            response_headers.pop("content-length", None)
            response_headers.pop("transfer-encoding", None)

            return Response(
                content=upstream_response.content,
                status_code=upstream_response.status_code,
                headers=response_headers,
                media_type="application/json"
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502, 
                detail=f"Upstream provider connection error: {str(exc)}"
            )


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "TokenShield Gateway Proxy", "version": "0.2.2"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)