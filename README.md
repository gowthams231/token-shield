# TokenShield (Alpha Sandbox)

A lightweight FastAPI middleware gateway proxy acting as an infrastructure cost shield between autonomous AI framework architectures (like LangGraph, CrewAI, or AutoGen) and downstream Large Language Models. 

TokenShield operates entirely at the networking layer using an OpenAI-compatible inbound gate, intercepting multi-agent logic loops, duplicate prompt cascades, and token bleed anomalies before they impact your live API budget.

## Core Capabilities

- **Inbound Model Agnostic Gateway:** Listens on standard `/v1/chat/completions` endpoints, allowing seamless integration with any development framework without changing structural code schemas.
- **Dynamic Downstream Routing:** Automatically detects target payload strings to instantly map, header-sign, and route traffic to the **Google Gemini API** (via OpenAI-compatible endpoint configurations) or native **OpenAI** servers based on request demands.
- **Loop Cascade Interception:** Monitors rolling payload signatures per session/IP, automatically tripping a network-level circuit breaker (returning a `429` error) if an autonomous framework agent gets trapped in an infinite loop cycle.
- **Zero-Cost Offline Sandbox:** Bundles an entirely localized mock validation engine (`sandbox_proxy.py`) to simulate framework execution states, payload handling, and loop-breaker behavior without utilizing real API credits or requiring active internet access.

## Architecture Visualized

<<<<<<< HEAD
[START CODE]text
=======
>>>>>>> 9d377156ed699804daea6a04604fd48cdd7c4685
[ Application Layer ] (LangGraph, CrewAI, AutoGen, Custom App)
         │
         ▼  (Generic OpenAI JSON Format)
┌────────────────────────────────────────────────────────┐
│               🚧 TokenShield Gateway                   │
├────────────────────────────────────────────────────────┤
│  🕵️  Universal Loop Cascade Detector                   │
│  🔄  Dynamic Provider Model Parser                     │
└───────────────────┬────────────────┬───────────────────┘
                    │                │
     (If model="gemini-*")        (If model="gpt-*")
                    │                │
                    ▼                ▼
         [ Google Gemini API ]    [ OpenAI API ]
<<<<<<< HEAD
[END CODE]
=======
>>>>>>> 9d377156ed699804daea6a04604fd48cdd7c4685

## Quick Start

### 1. Installation
Install the required network gateway and server hosting dependencies:

<<<<<<< HEAD
[START CODE]bash
pip install fastapi uvicorn httpx
[END CODE]
=======
pip install fastapi uvicorn httpx
>>>>>>> 9d377156ed699804daea6a04604fd48cdd7c4685

### 2. Run the Zero-Cost Offline Sandbox
To validate payload structures and test the circuit-breaking engine locally without providing any API credentials or using internet access:

<<<<<<< HEAD
[START CODE]bash
python sandbox_proxy.py
[END CODE]
=======
python sandbox_proxy.py
>>>>>>> 9d377156ed699804daea6a04604fd48cdd7c4685

### 3. Test the Circuit Breaker via PowerShell
With the sandbox running, open a new terminal window and execute this command 3 times back-to-back to simulate a looping framework agent:

<<<<<<< HEAD
[START CODE]powershell
Invoke-RestMethod -Uri "[http://127.0.0.1:8000/v1/chat/completions](http://127.0.0.1:8000/v1/chat/completions)" -Method Post -ContentType "application/json" -Body '{"model": "gemini-2.5-flash", "messages": [{"role": "user", "content": "Execute agent step 4."}]}'
[END CODE]

*Note: The third execution will trigger the TokenShield local tracking logic, trip the circuit breaker, and return a clean `429` error payload.*
=======
Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/chat/completions" -Method Post -ContentType "application/json" -Body '{"model": "gemini-2.5-flash", "messages": [{"role": "user", "content": "Execute agent step 4."}]}'

Note: The third execution will trigger the TokenShield local tracking logic, trip the circuit breaker, and return a clean 429 error payload.
>>>>>>> 9d377156ed699804daea6a04604fd48cdd7c4685

### 4. Running Production Mode
To deploy the live gateway proxy, configure your environment variables with your active keys:

<<<<<<< HEAD
[START CODE]powershell
$env:GEMINI_API_KEY="your_gemini_key_here"
$env:OPENAI_API_KEY="your_openai_key_here"
[END CODE]

Then execute the core engine:

[START CODE]bash
python proxy.py
[END CODE]

Point your framework applications directly to `[http://127.0.0.1:8000](http://127.0.0.1:8000)` to secure your live infrastructure pipelines.
=======
$env:GEMINI_API_KEY="your_gemini_key_here"
$env:OPENAI_API_KEY="your_openai_key_here"

Then execute the core engine:

python proxy.py

Point your framework applications directly to http://127.0.0.1:8000 to secure your live infrastructure pipelines.
>>>>>>> 9d377156ed699804daea6a04604fd48cdd7c4685
