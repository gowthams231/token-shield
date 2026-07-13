# TokenShield (Alpha Sandbox)

A lightweight FastAPI middleware gateway proxy acting as an infrastructure cost shield between autonomous AI framework architectures (like LangGraph, CrewAI, or AutoGen) and downstream Large Language Models. 

TokenShield operates entirely at the networking layer using an OpenAI-compatible inbound gate, intercepting multi-agent logic loops, duplicate prompt cascades, and token bleed anomalies before they impact your live API budget.

## Core Capabilities

- **Inbound Model Agnostic Gateway:** Listens on standard `/v1/chat/completions` endpoints, allowing seamless integration with any development framework without changing structural code schemas.
- **Dynamic Downstream Routing:** Automatically detects target payload strings to instantly map, header-sign, and route traffic to the **Google Gemini API** (via OpenAI-compatible endpoint configurations) or native **OpenAI** servers based on request demands.
- **Loop Cascade Interception:** Monitors rolling payload signatures per session/IP, automatically tripping a network-level circuit breaker (returning a `429` error) if an autonomous framework agent gets trapped in an infinite loop cycle.
- **Zero-Cost Offline Sandbox:** Bundles an entirely localized mock validation engine (`sandbox_proxy.py`) to simulate framework execution states, payload handling, and loop-breaker behavior without utilizing real API credits or requiring active internet access.

## Architecture Visualized

```text
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