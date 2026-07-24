import os
import json
import re
import hashlib
import time
import yaml
from typing import Dict, Any, List, Tuple, Optional
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import JSONResponse
import httpx

app = FastAPI(title="TokenShield Gateway Proxy", version="0.3.1")

# ------------------------------------------------------------------------------
# CONFIGURATION & YAML POLICY LOADING
# ------------------------------------------------------------------------------
CONFIG_FILE = os.getenv("TOKENSHIELD_CONFIG", "tokenshield.yaml")

def load_config(filepath: str) -> Dict[str, Any]:
    """Loads configuration file and resolves ${ENV_VAR:default} environment patterns."""
    if not os.path.exists(filepath):
        print(f"⚠️ Warning: Config file '{filepath}' not found. Falling back to default settings.")
        return {}

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    def replace_env(match):
        var_name = match.group(1)
        default_val = match.group(3) if match.group(3) is not None else ""
        return os.getenv(var_name, default_val)

    content = re.sub(r'\$\{([A-Za-z0-9_]+)(:([^}]+))?\}', replace_env, content)
    return yaml.safe_load(content)

CONFIG = load_config(CONFIG_FILE)

# Extract Gateway Settings
gw_config = CONFIG.get("gateway", {})
UPSTREAM_BASE_URL = os.getenv("UPSTREAM_BASE_URL", gw_config.get("upstream_base_url", "https://api.openai.com/v1")).rstrip('/')
TIMEOUT_SECONDS = float(gw_config.get("timeout_seconds", 60.0))

# Extract Circuit Breaker Rules
cb_config = CONFIG.get("circuit_breaker", {})
WINDOW_SIZE_SECONDS = int(os.getenv("WINDOW_SIZE_SECONDS", cb_config.get("window_size_seconds", 60)))
STRICT_DUPLICATE_LIMIT = int(os.getenv("STRICT_DUPLICATE_LIMIT", cb_config.get("strict_duplicate_limit", 2)))
CONSECUTIVE_STAGNANT_LIMIT = int(os.getenv("CONSECUTIVE_STAGNANT_LIMIT", cb_config.get("consecutive_stagnant_limit", 5)))

# Extract Classification Mapping dynamically from YAML (Zero hardcoded keywords in Python)
class_config = CONFIG.get("classification", {})
CATEGORIES_MAP: Dict[str, List[str]] = class_config.get("categories", {})
DEFAULT_CATEGORY: str = class_config.get("default_category", "GENERIC_STAGNATION")

# Extract Steering Prompt Template
steering_config = CONFIG.get("steering", {})
STEERING_PROMPT_TEMPLATE: str = steering_config.get(
    "prompt_template", 
    "🚨 STAGNATION DETECTED on {tool_label}: State '{error_family}'. Revise strategy."
)

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
    """
    Completely generic error classification.
    Iterates dynamically through whatever categories and keywords are defined in tokenshield.yaml.
    """
    c = content_str.lower()
    
    for category_name, keywords in CATEGORIES_MAP.items():
        if any(keyword.lower() in c for keyword in keywords):
            return category_name
            
    return DEFAULT_CATEGORY


def extract_hybrid_signatures(messages: list) -> Tuple[Optional[str], Optional[str], str, str]:
    """
    EXTRACTS DUAL SIGNATURE HASHES FOR ACTIVE TOOL CALLS:
    1. strict_arg_hash: tool_name + normalized_args + error_family (catches exact payload retries)
    2. tool_stagnant_hash: tool_name + error_family (ignores query tweaks, catches parameter-shifting loops)

    Returns (None, None, "NONE", "") if no tool execution context exists in this turn.
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

    # If no tool execution took place in this request, skip stagnation tracking cleanly
    if not last_tool_name:
        return None, None, "NONE", ""

    error_family = classify_error_family(last_tool_output)
    
    # Signature 1: Strict payload match
    strict_sig = f"{last_tool_name}:{normalize_text(str(last_tool_args))}:{error_family}"
    strict_arg_hash = hashlib.md5(strict_sig.encode("utf-8")).hexdigest()

    # Signature 2: Tool-level stagnation match (Catches parameter-shifting loops)
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
    """Injects Tier 1 reflection prompt directly into system messages using YAML template."""
    tool_label = f"tool '{tool_name}'" if tool_name else "this action"
    prompt_text = STEERING_PROMPT_TEMPLATE.format(tool_label=tool_label, error_family=error_family)
    
    reflection_notice = {
        "role": "system",
        "content": prompt_text
    }
    return messages + [reflection_notice]


def clean_headers_for_forwarding(headers_dict: Dict[str, str]) -> Dict[str, str]:
    """Removes hop-by-hop and transport headers safely regardless of casing."""
    banned_headers = {"host", "content-length", "accept-encoding", "transfer-encoding", "connection"}
    cleaned = {}
    for k, v in headers_dict.items():
        if k.lower() not in banned_headers:
            cleaned[k] = v
    return cleaned


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

    # Only record history if an actual tool call occurred
    if tool_stagnant_hash and strict_arg_hash:
        history.append((now, strict_arg_hash, tool_stagnant_hash, error_family, tool_name))
        SESSION_HISTORY[session_id] = history

    # Calculate TRUE consecutive backward stagnation streaks
    consecutive_stagnant_count = 0
    strict_duplicate_count = 0

    if tool_stagnant_hash:
        for item in reversed(history):
            if item[2] == tool_stagnant_hash:
                consecutive_stagnant_count += 1
            else:
                break

    if strict_arg_hash:
        for item in reversed(history):
            if item[1] == strict_arg_hash:
                strict_duplicate_count += 1
            else:
                break

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
    if (strict_duplicate_count >= STRICT_DUPLICATE_LIMIT or consecutive_stagnant_count >= STRICT_DUPLICATE_LIMIT) and tool_stagnant_hash:
        print(f"🟡 [TokenShield] TIER 1 SOFT STEERING | Session: {session_id} | Tool: {tool_name}")
        body["messages"] = inject_reflection_prompt(messages, tool_name, error_family)
        tier1_active = True

    # --------------------------------------------------------------------------
    # UPSTREAM FORWARDING & HEADER CLEANUP
    # --------------------------------------------------------------------------
    forward_headers = clean_headers_for_forwarding(dict(request.headers))

    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        try:
            upstream_response = await client.post(
                f"{UPSTREAM_BASE_URL}/chat/completions",
                json=body,
                headers=forward_headers
            )
            
            # Print the model's text reflection response directly in terminal when Tier 1 fires
            if tier1_active and upstream_response.status_code == 200:
                try:
                    res_json = upstream_response.json()
                    model_output = res_json["choices"][0]["message"].get("content", "")
                    if model_output:
                        print(f"\n🧠 [MODEL REFLECTION RESPONSE]:\n{model_output.strip()}\n")
                except Exception:
                    pass

            response_headers = clean_headers_for_forwarding(dict(upstream_response.headers))

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
    return {"status": "healthy", "service": "TokenShield Gateway Proxy", "version": "0.3.1"}


if __name__ == "__main__":
    import uvicorn
    host = gw_config.get("host", "127.0.0.1")
    port = int(gw_config.get("port", 8000))
    uvicorn.run(app, host=host, port=port)