import sys
import time
from openai import OpenAI

# 1. INITIALIZE CLIENT ROUTED THROUGH THE TOKENSHIELD PROXY
# The base_url redirects standard SDK traffic directly into your local proxy gateway
client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="placeholder-value-since-proxy-injects-real-key"
)

# 2. DEFINE SYSTEM SIMULATION CONTEXT
conversation_history = [
    {
        "role": "system", 
        "content": (
            "You are an autonomous background data migration worker. "
            "You are currently stuck in an unhandled exception state loop trying to migrate database chunks. "
            "Keep outputting sequential logs analyzing the migration failure, incrementing the status code "
            "each turn to attempt a dynamic protocol override."
        )
    },
    {
        "role": "user", 
        "content": "Execute background data migration pipeline task sequence immediately."
    }
]

MAX_TEST_ITERATIONS = 20

print("🚀 Starting continuous background agent worker simulation...")
print("------------------------------------------------------------")

# 3. HIGH-VELOCITY AGENT EXECUTION LOOP
for iteration in range(1, MAX_TEST_ITERATIONS + 1):
    print(f"\n[Iteration {iteration}] Agent executing tool action and parsing context...")
    
    start_time = time.time()
    
    try:
        # High-frequency call hitting the proxy layer with direct custom request routing headers
        raw_response = client.chat.completions.with_raw_response.create(
            # model="gpt-4o-mini",
            # model="gemini-3.5-flash",
            model="gemini-3.1-flash-lite",
            messages=conversation_history,
            stream=False,
            extra_headers={"X-Simulation-Mode": "true"}  # Inline header injection
        )
        
        # --- THE ULTIMATE PROXY GUARD CHECK ---
        # Get the underlying HTTP status code from the raw response object envelope
        http_status = raw_response.http_response.status_code
        
        if http_status == 429:
            raise RuntimeError("TokenShield Intercept: 429 Connection Severed by Proxy Gateway.")
        elif http_status != 200:
            raise RuntimeError(f"Gateway Error: Downstream returned status code {http_status}")

        # If it's a clean 200, extract the parsed data out safely
        parsed_response = raw_response.parse()

        latency = (time.time() - start_time) * 1000
        model_reply = parsed_response.choices[0].message.content
        snippet = model_reply[:90].replace('\n', ' ')
        
        print(f"✓ Success (Latency: {latency:.1f}ms) | Model response snippet: {snippet}...")
        
        # Feed the model's reply straight back into history to simulate the continuous loop state
        conversation_history.append({"role": "assistant", "content": model_reply})
        conversation_history.append({"role": "user", "content": "Error sustained. Retry variation protocol."})
        
        # Small delay to simulate immediate automated agent loop transitions
        time.sleep(0.5)
        
    except Exception as e:
        print("\n🚨 CIRCUIT BREAKER TRIGGERED NATIVE EXCEPTION!")
        print(f"Status Code / Details: {str(e)}")
        print("\n🏁 Simulation completed. TokenShield successfully protected the API runway.")
        sys.exit(0)

print("\n⚠️ Simulation ended naturally without triggering the gateway sentinel.")