# 🛡️ TokenShield Enterprise Gateway

TokenShield is an intelligent local network proxy and circuit breaker designed to protect developers and teams from runaway AI agent loops that burn through API budgets.

## 📊 The Problem

Autonomous multi-agent architectures and recursive data pipelines are inherently prone to infinite loops. Standard turn caps or token limits only count total volume. When an agent hits a subtle tool failure, it often mutates its parameters slightly, such as tweaking search keywords on every turn, bypassing strict payload hashes while burning hundreds of dollars before engineers notice.

## ✨ The Solution

TokenShield acts as an unbypassable security sentinel sitting between your application code and upstream AI providers like OpenAI, Anthropic, and Google Gemini. It inspects execution state and tool response outputs at the network layer, preventing runaway loops even when LLMs introduce dynamic parameter variations.

## ⚡ Key Features

- **🧠 Hybrid Detection Engine:** Combines strict argument matching with tool stagnation tracking.
- **🟡 Tier 1 Soft Steering:** Detects near-identical tool calls and injects system re-planning instructions to redirect the agent before killing the task.
- **🔴 Tier 2 Hard Stop:** Intercepts dynamic search and keyword loops where the model keeps guessing new arguments that all fail, cutting the network connection to protect your budget.
- **🏷️ Classified Error Taxonomy:** Automatically categorizes tool failures, including `EMPTY_RESULT`, `AUTH_OR_PERMISSION_DENIED`, `INVALID_SCHEMA_OR_SYNTAX`, and `TRANSIENT_NETWORK_FAILURE`, so developers get actionable diagnostic logs instead of opaque token caps.
- **🧬 Normalized State Extraction:** Strips timestamps, UUIDs, and formatting noise so near-identical commands resolve to a consistent signature.
- **🏢 Multi-Tenant Session Isolation:** Tracks sliding-window connection counters per unique API key or session context.
- **💹 Dynamic Market Pricing Caching:** Automatically fetches live token pricing metrics to calculate financial blast radius in real time.
- **💰 Financial Threat Intercept Ledger:** Displays projected hourly savings directly in your console when a loop is intercepted.

## 📂 Project Structure

```plaintext
ai-proxy/
├── proxy.py               # Core FastAPI gateway engine
├── README.md              # Documentation
├── requirements.txt       # Project dependencies
│
├── examples/              # Interactive user applications
│   └── app.py             # Multi-agent workspace demo (Writer + Editor)
│
└── tests/                 # Automated testing suite
    └── failing_agent.py   # Integration test for dynamic loop interception
```

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.9+
- pip

### 2. Installation

Clone the repository and install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Configuration

Copy `.env.example` or create a `.env` file to configure your provider keys and threshold limits:

```bash
# Upstream AI Provider API Keys
GEMINI_API_KEY="your_gemini_api_key_here"
OPENAI_API_KEY="your_openai_api_key_here"
ANTHROPIC_API_KEY="your_anthropic_api_key_here"

# TokenShield Circuit Breaker Controls
WINDOW_SIZE_SECONDS=60
STRICT_DUPLICATE_LIMIT=2        # Tier 1: Soft steer threshold on exact/near duplicate calls
CONSECUTIVE_STAGNANT_LIMIT=5    # Tier 2: Hard stop threshold on dynamic parameter mutation loops
MAX_TOTAL_REQUESTS=15           # Absolute window speed limit
```

If you already have API keys set up as global operating system environment variables, TokenShield automatically detects and prioritizes them.

### 4. Running the Gateway

Launch the proxy server in Terminal 1:

```bash
python proxy.py
```

## 🛠️ Connecting to Your IDE or Application

Route your LLM requests through TokenShield from Cursor, Cline, LangChain, or any OpenAI-compatible client:

- **Provider:** Choose `OpenAI Compatible`
- **Base URL:** Set to `http://127.0.0.1:8000/v1`
- **API Key:** Enter a placeholder if using local environment keys, or pass a direct key
- **Model ID:** Specify your target model, such as `gpt-4o`, `claude-3-5-sonnet`, or `gemini-1.5-pro`

## 🧪 Demos and Testing

### 1. Interactive Multi-Agent Workspace

Run the interactive workspace in Terminal 2:

```bash
python examples/app.py
```

Normal run: Type `Quantum Computing` to observe a healthy multi-agent drafting workflow.

Circuit breaker test: Type `loop` to trigger TokenShield. You will see Tier 1 Soft Steering execute on turn 2 and a Tier 2 Hard Stop terminate the script on turn 5.

### 2. Automated Loop Interception Test

Run the headless integration test to verify tool-call loop catching:

```bash
python tests/failing_agent.py
```

You can also execute the test suite with:

```bash
pytest tests/
```

## 📦 File Overview

- `proxy.py`: Core FastAPI gateway engine. Implements async connection pooling, normalizers, hybrid signature matching, and dynamic routing.
- `examples/app.py`: Interactive CLI demonstrating Writer and Editor agents under proxy protection.
- `tests/failing_agent.py`: Automated test script simulating dynamic parameter mutation search loops.
- `.env`: Central configuration file for API credentials and circuit breaker limits.

## 🛡️ License

MIT
