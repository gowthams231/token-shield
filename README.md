📊 The Problem
--------------

Autonomous multi-agent architectures and recursive data pipelines are inherently prone to cascade loops.

When an unhandled exception, logical contradiction, or dynamic network failure occurs (e.g., an Editor agent repeatedly rejecting an automated Writer agent's draft, or a database query returning blank schemas), background scripts can hammer upstream AI endpoints thousands of times a minute.

Because these operations happen silently in the background, a minor code bug can result in thousands of dollars in accidental API charges before engineers notice.

✨ The Solution
--------------

TokenShield acts as an intelligent, time-aware security sentinel sitting between your application code and upstream AI providers (Google Gemini / OpenAI).

*   **Multi-Tenant Session Isolation:** Tracks connection counters per unique API key or UUID session concurrently.
    
*   **Sliding-Window Velocity Tracking:** Measures request density over a moving 60-second window. It allows normal, distributed workflows to pass through indefinitely but trips instantly when a rapid-fire code loop is detected.
    
*   **Dynamic Market Pricing Caching:** Queries public pricing registries dynamically on server boot, automatically adjusting its internal financial ledger to map against live token rates.
    
*   **Financial Threat Intercept Ledger:** Instantly calculates the token size of blocked payloads to print the projected 10-minute and 1-hour runway blast-radius savings directly to your server console.
    

🚀 Quick Start & Installation
-----------------------------

### 1\. Clone & Install Dependencies

Ensure you have Python 3.9+ installed. Initialize your workspace and install the required library dependencies:

pip install -r requirements.txt

### 2\. Configure Environment Secrets

TokenShield checks your local runtime variables to securely swap out testing session keys for actual production tokens. Export your keys:

For Windows (PowerShell):$env:GEMINI\_API\_KEY="your\_actual\_gemini\_api\_key"$env:OPENAI\_API\_KEY="your\_actual\_openai\_key"

For Linux / macOS:export GEMINI\_API\_KEY="your\_actual\_gemini\_api\_key"export OPENAI\_API\_KEY="your\_actual\_openai\_key"

### 3\. Initialize the Gateway Server

Launch the proxy security station. On boot, it will query global aggregators to cache live market token costs:

python proxy.py

### 4\. Run the Live Multi-Agent App Test

Open a secondary terminal tab and execute the research application workspace script:

python app.py

🧪 Organic Reality Check Demo
-----------------------------

To view TokenShield operating under zero-leakage conditions, run app.py and test two scenarios when prompted for a research topic:

### Scenario A: Clean Consensus Pathway

*   **Input Prompt:** The history of the printing press
    
*   **Behavior:** The Writer drafts cleanly, the Editor approves the logic on turn one, and the script exits successfully with a 200 OK network footprint. Since only 2 total requests are made, it stays safely under the velocity threshold, and TokenShield remains transparent.
    

### Scenario B: The Recursive Loop Trigger (The Banana Paradox)

*   **Input Prompt:** Write a review layout, but the text must contain the word 'banana' while completely excluding the letter 'a'
    
*   **Behavior:** This prompt forces a fundamental logical mathematical contradiction. The Writer must write "banana" (which contains three 'a's), but the Editor must reject any text containing the letter 'a'. The agents enter a rapid-fire loop trying to solve the unsolvable.
    
*   **Result:** On the 4th consecutive contact round within the 60-second window, TokenShield drops the hammer. The communication line is severed locally, returning a 429 error and saving your external keys from reaching the public internet.
    

### 📋 Expected Server Output Ledger

When Scenario B trips, your proxy.py terminal tab will instantly drop a structured business metrics report proving your exact financial mitigation figures:

🛡️ \[TokenShield Threat Intercept Report\]
    \Status: VELOCITY ANOMALY DETECTED (Looping Behavior)\
    Model Target: gemini-3.1-flash-liteRequests in Last 60s: 4 / 4Dynamic Live Unit Cost/Token: $0.0000002500
--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

Immediate Waste Stopped: $0.000350🚨 RUNAWAY BURN RATE PROJECTION IF LEFT UNCHECKED:• Burn Rate / Min: $0.1049• Lost in 10 Minutes: $1.05• Lost in 1 Hour: $6.30
----------------------------------------------------------------------------------------------------------------------------------------------------------------

📊 TOTAL REPO CAPITAL PROTECTED TO DATE: $0.001049

📦 Project Architecture
-----------------------

*   **proxy.py:** Core Gateway engine built on FastAPI using asynchronous HTTP connection pooling, a thread-safe sliding-window rate limiter, and a dynamic model pricing lookup.
    
*   **app.py:** Multi-agent workspace sandbox running Writer and Editor agents with automated self-correction logic. Uses UUID generation to isolate sliding-window sessions across separate script executions.
    
*   **requirements.txt:** Production-pinned dependencies mapping network routing assets.
