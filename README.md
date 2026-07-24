# 🛡️ TokenShield

**The Zero-Dependency Circuit Breaker for Autonomous AI Agents**

Intercept runaway tool retry loops, dynamic parameter mutation cascades, and API budget drain out-of-band at the proxy layer.

## 🚨 The Problem: The "Stuck Agent" Money Trap

When autonomous AI agents hit minor tool errors, such as a bad payload, missing parameter, empty search result, or command failure, they often ignore the output and immediately retry the tool call with near-identical parameters.

Because standard step caps or turn limits only count total request volume, an agent can easily burn 30+ turns in 2 minutes repeating a broken step before dying. Worse, parameter-shifting loops, like mutating wildcard queries across empty directories, bypass simple input-hashing rules entirely.

```plaintext
❌ WITHOUT TOKENSHIELD:
Agent Hit Error ──► Retries Same or Mutated Args ──► Retries Again ──► Burns 30 Turns ──► Runaway Token & Budget Burn 💸

✅ WITH TOKENSHIELD:
Agent Hit Error ──► Duplicate Result State ──► Tier 1: Forces Reflection Step ──► Agent Re-routes / Tier 2 Hard Stop 🛡️
```

## ✨ Key Features

- **🔌 Zero-SDK Footprint:** Operates out-of-band as an OpenAI-compatible FastAPI gateway proxy. Just point your client's `base_url` to TokenShield. Works universally across Goose, Claude Code, LangChain, AutoGen, CrewAI, LlamaIndex, or raw HTTP clients.
- **⚙️ 100% Declarative Policy Engine (YAML):** All operational thresholds, dynamic error classification rules, and steering prompts are configured in `tokenshield.yaml` without touching Python code.
- **🧬 Output-State Stagnation Hashing:** Tracks tool execution output states, such as `EMPTY_RESULT`, rather than brittle input arguments, catching parameter-shifting search loops effortlessly.
- **⏱️ True Backward Consecutive Streak Counting:** Scans recent execution history backward from the newest turn, ensuring counters immediately reset to `0` as soon as the agent makes forward progress.
- **🛡️ Non-Tool Conversational Guard:** Bypasses non-tool conversational chat turns cleanly without polluting session history or triggering false positive loop counts.
- **🟡 Tier 1: Soft Steering (Forced Reflection Step):** Before severing a run, TokenShield injects a strict system prompt requiring the agent to output a failure analysis and revised strategy before invoking any new tool.
- **🔴 Tier 2: Hard Stop (Circuit Breaker):** If state stagnation continues across consecutive turns despite Tier 1 intervention, TokenShield returns an HTTP `429` Hard Stop and cuts execution.
- **💻 Local & On-Prem Ready:** Fully compatible with local LLM runners like vLLM, Ollama, and LocalAI. Protects local CPU/GPU clusters from memory monopolization and thermal throttling.

## 🚀 Quick Start (60 Seconds)

### Installation

```bash
git clone https://github.com/gowthams231/token-shield.git
cd token-shield
pip install -r requirements.txt
```

### Configure `tokenshield.yaml`

Ensure `tokenshield.yaml` exists in your project root:

```yaml
version: "1.0"

gateway:
  host: "127.0.0.1"
  port: 8000
  upstream_base_url: "${UPSTREAM_BASE_URL:https://api.openai.com/v1}"

circuit_breaker:
  window_size_seconds: 60
  strict_duplicate_limit: 2        # Tier 1 Soft Steering threshold
  consecutive_stagnant_limit: 5    # Tier 2 Hard Stop (429) threshold
```

### Start the Proxy

```bash
python proxy.py
```

The gateway will spin up at:

```plaintext
http://127.0.0.1:8000/v1
```

### Point Your Agent to TokenShield

Simply update the `base_url` parameter in your existing AI agent code or environment setup.

**Python SDK:**

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

**CLI / Terminal Agents (Goose, Claude CLI):**

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8000/v1"
```

## ⚙️ How It Works: The 2-Tier Defense System

TokenShield evaluates true consecutive state progress across tool calls.

```plaintext
[ Incoming Agent Request ]
           │
           ▼
[ Is Active Tool Call Present? ] ──► NO ──► Pass Through (Conversational Chat)
           │
          YES
           │
           ▼
[ Dynamic Output State Classification ] (Driven by tokenshield.yaml)
           │
           ▼
[ Evaluate Backward Consecutive Failure Streak ]
           │
           ├── Streak < Tier 1 Limit  ──► Forward to Upstream LLM
           │
           ├── Streak >= Tier 1 Limit ──► 🟡 Tier 1: Inject System Reflection Prompt
           │
           └── Streak >= Tier 2 Limit ──► 🔴 Tier 2: Hard Stop (429 Circuit Broken)
```

### Tier 1: Forced Reflection Prompt Injection

Instead of abruptly crashing the task on the first failure, TokenShield injects this system instruction:

```plaintext
🚨 CRITICAL CIRCUIT BREAKER NOTICE:
You have invoked tool 'developer__shell' repeatedly resulting in the state 'EMPTY_RESULT'.
Do NOT repeat near-identical tool calls.

Before executing any tool, you MUST output a text response answering these two questions:

FAILURE ANALYSIS:
Why did your previous tool call fail or stagnate?

REVISED STRATEGY:
What specific parameter modifications or alternative tools will you use instead?

If your next step repeats the same stagnant tool pattern, your connection will be hard-terminated.
```

### Tier 2: Hard Stop Payload Response

If the agent fails to re-route, TokenShield halts budget burn and returns an HTTP `429` payload:

```json
{
  "error": {
    "message": "TokenShield Circuit Breaker: Reached 5 consecutive stagnant attempts on developer__shell.",
    "type": "tokenshield_stagnation_limit_exceeded",
    "code": "HARD_STOP_CIRCUIT_BROKEN",
    "stop_reason": "EMPTY_RESULT",
    "suggestion": "Review workflow logs. The agent failed to re-plan after soft steering."
  }
}
```

## 📊 Feature Matrix

| Feature | Raw Turn Caps / Basic SDKs | TokenShield Proxy Gateway |
| --- | --- | --- |
| Parameter-Shifting Loops | ❌ Misses mutated args | ✅ Output-State Hashing tracks result stagnation |
| Policy Management | ❌ Hardcoded in app code | ✅ 100% Declarative YAML Policy File |
| Mitigation Strategy | ❌ Abrupt crash / lost state | ✅ Tier 1 Soft Steering forces reflection first |
| Non-Tool Guard | ❌ Counts regular chat as turns | ✅ Bypasses non-tool chat automatically |
| Framework Support | ❌ Tied to specific Python wrappers | ✅ Universal HTTP Proxy (Goose, Claude, LangChain, Raw cURL) |
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
