# BraveUp Proxy Gateway (Alpha Sandbox)

A lightweight FastAPI middleware proxy designed to sit between autonomous AI frameworks (like LangGraph, CrewAI, or Autogen) and downstream LLMs. It acts as an infrastructure cost shield, trapping agent logic loops and token bleed anomalies at the network layer before they drain your API budget.

## Features
- **Loop Cascade Interception:** Automatically tracks consecutive duplicate prompt payloads and kills the connection with a `429` error if an agent gets stuck.
- **Token Budget Caps:** Keeps a local, running tally of token burn to prevent unexpected budget runaways.
- **Offline Testing Sandbox:** Includes a completely localized execution file to test logic behavior without spending live credits.

## Quick Start

1. Install dependencies:
   ```bash
   pip install fastapi uvicorn