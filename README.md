# 🛡️ TokenShield

**The Zero-Dependency Circuit Breaker for Autonomous AI Agents**

Intercept runaway tool retry loops, dynamic parameter mutation cascades, and API budget drain out-of-band at the proxy layer.

## 🚨 The Problem: The "Stuck Agent" Money Trap

When autonomous AI agents hit minor tool errors, such as a bad payload, missing parameter, or empty database result, they often ignore the failure message and immediately retry the tool call with near-identical parameters.

Because standard step caps or turn limits only count total request volume, an agent can easily burn 30+ turns in 2 minutes repeating a broken step before dying.

```plaintext
❌ WITHOUT TOKENSHIELD:
Agent Hit Error ──► Retries Same Args ──► Retries Again ──► Burns 30 Turns ──► $50 API Bill 💸

✅ WITH TOKENSHIELD:
Agent Hit Error ──► Duplicate State ──► Tier 1: Forces Reflection Step ──► Agent Re-routes / Tier 2 Hard Stop 🛡️
```

## ✨ Key Features

- **🔌 Zero-SDK Footprint:** Operates out-of-band as an OpenAI-compatible FastAPI gateway proxy. Just point your client's `base_url` to TokenShield. Works universally across LangChain, AutoGen, CrewAI, LlamaIndex, or raw HTTP clients.
- **🧬 Normalized State Extraction (Canonicalization):** Strips dynamic noise, including ISO timestamps, UUIDs, and extra whitespace, to catch parameter mutation loops that standard exact-string hashing misses.
- **🟡 Tier 1: Soft Steering (Forced Reflection Step):** Before severing a run, TokenShield injects a strict system prompt requiring the agent to output a failure analysis and revised strategy before invoking any new tool.
- **🔴 Tier 2: Hard Stop (Circuit Breaker):** If the state remains stagnant across the sliding window despite Tier 1 intervention, TokenShield immediately trips the circuit breaker and cuts the connection.
- **💻 Local & On-Prem Ready:** Fully compatible with local LLM runners like vLLM, Ollama, and LocalAI. Protects local CPU/GPU clusters from memory monopolization and thermal throttling.

## 🚀 Quick Start (60 Seconds)

### 1. Installation

```bash
git clone https://github.com/gowthams231/token-shield.git
cd token-shield
pip install -r requirements.txt
```

### 2. Start the Proxy

```bash
python proxy.py
```

The gateway will spin up at:

```plaintext
http://127.0.0.1:8000/v1
```

### 3. Point Your Agent to TokenShield

Simply update the `base_url` parameter in your existing AI agent code:

```python
from openai import OpenAI

# Direct your application traffic through TokenShield
client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="your-openai-api-key"
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Run my autonomous task"}]
)
```

## ⚙️ How It Works: The 2-Tier Defense System

TokenShield evaluates state progress using sliding window hashing across `N` execution turns.

```plaintext
[ Incoming Agent Request ]
           │
           ▼
[ Canonicalization & Normalization ] (Strips UUIDs, ISO Timestamps, Formatting)
           │
           ▼
 [ Is State Stagnant in Window? ] ──► NO  ──► Forward to Upstream LLM
           │
          YES
           │
           ▼
 [ Tier 1 Attempted? ] ──► NO  ──► 🟡 Tier 1: Inject System Reflection Prompt
           │
          YES
           │
           ▼
 🔴 Tier 2: Hard Stop (Trip Circuit Breaker & Block Network Request)
```

### Tier 1: Forced Reflection Prompt Injection

Instead of abruptly crashing the task, TokenShield injects this system instruction:

```plaintext
🚨 CRITICAL CIRCUIT BREAKER NOTICE:
You are stuck in a tool execution loop repeating near-identical arguments without progress.

Before executing any tool, you MUST output a text response answering these two questions:

FAILURE ANALYSIS:
Why did your previous tool call fail or stagnate?

REVISED STRATEGY:
What specific parameter modifications or alternative tools will you use instead?
```

### Tier 2: Hard Stop Payload Response

If the agent fails to re-route, TokenShield halts budget burn and returns a clean, structured JSON payload:

```json
{
  "error": {
    "message": "TokenShield Circuit Breaker: Stagnant retry loop detected across sliding window.",
    "type": "tokenshield_stagnation_limit_exceeded",
    "code": "HARD_STOP_CIRCUIT_BROKEN",
    "stop_reason": "SAME_ARGS_NO_NEW_STATE",
    "suggestion": "Review workflow logs. The agent failed to re-plan after soft steering."
  }
}
```

## 📊 Feature Matrix

| Feature | Raw Turn Caps / Basic SDKs | TokenShield Proxy Gateway |
| --- | --- | --- |
| Mutation Loop Handling | ❌ Misses parameter nudges | ✅ Canonicalization strips timestamps/UUIDs |
| Mitigation Strategy | ❌ Abrupt crash / lost state | ✅ Tier 1 Soft Steering forces reflection first |
| Framework Support | ❌ Tied to specific Python wrappers | ✅ Universal HTTP Proxy (LangChain, AutoGen, Raw cURL) |
| Local LLM Protection | ❌ Unprotected local GPU memory | ✅ Prevents local CPU/GPU resource starvation |

## 🧪 Testing TokenShield Locally

Run the included failing agent test script to see TokenShield intercept a runaway loop in real time:

```bash
# In Terminal 1: Start TokenShield
python proxy.py

# In Terminal 2: Run the failing agent simulation
python tests/failing_agent.py
```

Observe the terminal logs as Tier 1 injects the reflection prompt, followed by Tier 2 tripping the circuit breaker when state remains stagnant.

## 🤝 Contributing & Community

Contributions, issues, and feature requests are welcome. Feel free to check the issues page.

If TokenShield saved your API budget or protected your local GPU cluster, give us a ⭐ on GitHub.

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
