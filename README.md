# 🛡️ TokenShield Enterprise Gateway

TokenShield is an intelligent, local-network circuit breaker designed to protect AI developers and startups from catastrophic, runaway background agent loops that rapidly burn through API credits.

## 📊 The Problem
Autonomous multi-agent architectures and recursive data pipelines are inherently prone to cascade loops. A minor code bug can result in thousands of dollars in accidental API charges before engineers notice.

## ✨ The Solution
TokenShield acts as a security sentinel sitting between your application code and upstream AI providers (Google Gemini, OpenAI, Anthropic).

### Key Features
- **Multi-Tenant Session Isolation**: Tracks connection counters per unique API key or UUID session.
- **Cryptographic Content Hash Detection**: The proxy hashes incoming prompt payloads to distinguish between aggressive, legitimate file reading and true, identical loop states, ensuring only actual runaway loops are blocked.
- **Dynamic Market Pricing Caching**: Automatically fetches live token costs to calculate your "financial blast radius."
- **Financial Threat Intercept Ledger**: Prints projected savings directly to your console when a loop is blocked.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.9+
- `pip`

### 2. Installation
Clone the repository and install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Configuration
Copy the `.env.example` (or create a new `.env` file) and populate your API keys:

```bash
# 🔑 Upstream AI Provider API Keys
GEMINI_API_KEY="your_gemini_api_key_here"
OPENAI_API_KEY="your_openai_api_key_here"
ANTHROPIC_API_KEY="your_anthropic_api_key_here"

# 🛡️ TokenShield Circuit Breaker Controls
WINDOW_SIZE_SECONDS=60
MAX_DUPLICATE_REPEATS=3
MAX_TOTAL_REQUESTS=15
```

*Note: If you already have API keys set up as global environment variables on your operating system, you do not need to paste them into the `.env` file. The proxy will automatically detect and prioritize your existing system keys, allowing you to keep the `.env` file strictly for circuit breaker threshold configuration.*

### 4. Running the Gateway
Launch the proxy server:
```bash
python proxy.py
```

### 🛠️ Connecting to your IDE (Cline / Cursor / etc.)
You can route your IDE's AI requests through TokenShield to protect your API credits:
1. **Provider**: Choose "OpenAI Compatible".
2. **Base URL**: Enter `http://127.0.0.1:8000/v1`.
3. **API Key**: Enter any placeholder (e.g., `placeholder`) if using keys from your system environment, or pass a direct key.
4. **Model ID**: Choose your target model (e.g., `gemini-3.1-flash-lite`, `claude-3-5-sonnet`, or `gpt-4o`).

### 5. Running the Demo
In a separate terminal, run the multi-agent sandbox:
```bash
python app.py
```

---

## 🧪 Testing the Circuit Breaker
Run `app.py` and try the **Banana Paradox** scenario:
*Input Prompt:* "Write a review layout, but the text must contain the word 'banana' while completely excluding the letter 'a'."

This forces a logical contradiction, triggering a rapid-fire loop. TokenShield will detect the velocity anomaly, sever the connection, and report your financial savings.

---

## 📦 Project Architecture
- **`proxy.py`**: Core FastAPI gateway engine. Handles asynchronous HTTP connection pooling, thread-safe rate limiting, and dynamic pricing lookups.
- **`app.py`**: Multi-agent workspace sandbox. Demonstrates Writer/Editor agent interaction with automated self-correction.
- **`.env`**: Centralized configuration for API keys and security thresholds.

---

## 🛡️ License
MIT
