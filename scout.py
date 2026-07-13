import os
import json
import urllib.request
import xml.etree.ElementTree as ET
import gzip
import re
import time
from datetime import datetime, timedelta, UTC

# Secure import framework for the Google SDK
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

def clean_rss_html(raw_html):
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    return ' '.join(re.sub(cleanr, ' ', raw_html).replace('', '').split())

# ==========================================
# 1. DATA INGESTION NODES
# ==========================================
def fetch_github_data(repo="langchain-ai/langgraph"):
    since_date = (datetime.now(UTC) - timedelta(days=14)).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f"https://api.github.com/repos/{repo}/issues?since={since_date}&state=open&per_page=30"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/vnd.github+json'
    }
    
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers['Authorization'] = f'Bearer {github_token}'
        
    req = urllib.request.Request(url, headers=headers)
    records = []
    try:
        print(f"Connecting to public GitHub issues for {repo}...")
        with urllib.request.urlopen(req) as res:
            if res.status == 200:
                for issue in json.loads(res.read().decode()):
                    if "pull_request" in issue: continue
                    records.append({
                        "source": "GitHub", "id": str(issue.get("number")),
                        "title": issue.get("title", ""), "user": issue.get("user", {}).get("login"),
                        "url": issue.get("html_url"), "content": issue.get("body", "") or ""
                    })
    except Exception as e:
        print(f"⚠️ GitHub Ingestion Bypassed: {e}")
    return records

def fetch_reddit_data(subreddit="LangChain"):
    url = f"https://www.reddit.com/r/{subreddit}/new.rss"
    opener = urllib.request.build_opener()
    opener.addheaders = [
        ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
        ('Accept', 'application/xml,text/xml,*/*')
    ]
    records = []
    try:
        print(f"Connecting to public Reddit RSS feed for r/{subreddit}...")
        with opener.open(url, timeout=10) as res:
            if res.status == 200:
                root = ET.fromstring(res.read())
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                for entry in root.findall('atom:entry', ns):
                    title_node = entry.find('atom:title', ns)
                    content_node = entry.find('atom:content', ns)
                    link_node = entry.find('atom:link', ns)
                    author_node = entry.find('atom:author/atom:name', ns)
                    
                    records.append({
                        "source": "Reddit", 
                        "id": entry.find('atom:id', ns).text.split('_')[-1] if entry.find('atom:id', ns) is not None else "unknown",
                        "title": title_node.text if title_node is not None else "", 
                        "user": author_node.text.replace("/u/", "") if author_node is not None else "Anonymous",
                        "url": link_node.attrib.get('href') if link_node is not None else "", 
                        "content": clean_rss_html(content_node.text) if content_node is not None else ""
                    })
    except Exception as e:
        print(f"❌ Reddit RSS Error: {e}")
    return records

def fetch_stackoverflow_data(tag="langchain"):
    url = f"https://api.stackexchange.com/2.3/questions?pagesize=20&order=desc&sort=creation&tagged={tag}&site=stackoverflow"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    records = []
    try:
        print(f"Connecting to public StackOverflow tag data for '{tag}'...")
        with urllib.request.urlopen(req) as res:
            if res.status == 200:
                raw_bytes = res.read()
                try: decompressed = gzip.decompress(raw_bytes).decode('utf-8')
                except: decompressed = raw_bytes.decode('utf-8')
                for item in json.loads(decompressed).get("items", []):
                    records.append({
                        "source": "StackOverflow", "id": str(item.get("question_id")),
                        "title": item.get("title", ""), "user": item.get("owner", {}).get("display_name"),
                        "url": f"https://stackoverflow.com/q/{item.get('question_id')}", "content": item.get("title", "")
                    })
    except Exception as e:
        print(f"❌ StackOverflow Error: {e}")
    return records

# ==========================================
# 2. KEYWORD FILTERING LOGIC
# ==========================================
def run_keyword_filtering(raw_data):
    target_keywords = ["loop", "retry", "max_tokens", "truncat", "exception", "validation", "abort", "bleed", "cost", "bill", "stuck", "error", "spent", "rogue"]
    matches = []
    for r in raw_data:
        title_lower = r["title"].lower()
        content_lower = r["content"].lower()
        if any(kw in title_lower or kw in content_lower for kw in target_keywords):
            matches.append(r)
    return matches

# ==========================================
# 3. DUPLICATE CHECKING FRAMEWORK
# ==========================================
def load_existing_urls(filepath="leads.md"):
    if not os.path.exists(filepath):
        return set()
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    urls = re.findall(r'(https?://[^\s\)]+)', content)
    return set(urls)

# ==========================================
# 4. GEMINI INTELLIGENCE & EXPORT ENGINE
# ==========================================
def qualify_and_export_leads(leads, export_path="leads.md"):
    gemini_key = os.environ.get("GEMINI_API_KEY")
    
    if not GEMINI_AVAILABLE:
        print("\n⚠️ google-genai package missing. Run: pip install google-genai")
        return
    if not gemini_key:
        print("\n⚠️ GEMINI_API_KEY environment variable not detected. Outputting raw leads.")
        return
        
    client = genai.Client(api_key=gemini_key)
    print(f"\n🧠 GEMINI PRODUCTION ANALYSIS ACTIVE: Evaluating Systems Issues...")
    print("=" * 80)
    
    existing_urls = load_existing_urls(export_path)
    new_leads = [l for l in leads if l['url'] not in existing_urls]
    skipped_count = len(leads) - len(new_leads)
    
    if skipped_count > 0:
        print(f"ℹ️ Filtered out {skipped_count} duplicate posts already recorded in {export_path}")
        
    if not new_leads:
        print("✅ No new unique leads to evaluate in this batch.")
        return

    # Process up to 12 items to optimize free tier limits
    target_leads = new_leads[:12]
    
    for idx, lead in enumerate(target_leads):
        prompt = f"""
        Analyze this developer post to determine if they are facing high-value architectural pipeline issues 
        with AI agents (such as loop cascades, token bleed, high billing/costs, unhandled state exceptions, or crash loops).
        
        Platform: {lead['source']}
        Title: {lead['title']}
        Content Snippet: {lead['content'][:300]}
        
        If the issue is low-value (like a documentation grammar error or basic environment installation bug), reply with "SKIP: Low architectural intent".
        
        If it is high-value, output your analysis in this exact layout:
        [QUALIFIED]
        PAIN SCORE: [1-5]
        TECHNICAL ANALYSIS: (1 sentence explaining the systemic failure)
        PEER OUTREACH: (Write a 2-sentence non-sales, ultra-technical message from one developer to another. Suggest handling the failure at an external network proxy/gateway level before the framework loops blindly. Do not sound like a marketing pitch).
        """
        
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.1)
            )
            analysis_text = response.text.strip()
            
            if "SKIP" in analysis_text:
                continue
                
            print(f"\n[{lead['source']}] | User: {lead['user']} | Link: {lead['url']}")
            print(analysis_text)
            print("=" * 80)
            
            # Write immediate updates straight to the file system
            file_exists = os.path.exists(export_path)
            with open(export_path, "a", encoding="utf-8") as f:
                if not file_exists:
                    f.write("# 🎯 Qualified Proxy Architecture Leads\n")
                    f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d')}\n\n")
                
                f.write(f"## [{lead['source']}] Post by {lead['user']}\n")
                f.write(f"* **Link:** {lead['url']}\n")
                f.write(f"* **Title:** {lead['title']}\n\n")
                f.write(f"```text\n{analysis_text}\n```\n")
                f.write("\n---\n\n")
            
            # Pacing delay to remain within structural free constraints
            if idx < len(target_leads) - 1:
                print("⏳ Pacing connection to respect free-tier API limits (12s)...")
                time.sleep(12)
                
        except Exception as e:
            # Gracefully intercept quota ceilings and break execution loops safely
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print(f"\n🛑 API Quota Exceeded for the day: {e}")
                print("Saving current progress and shutting down pipeline until counter resets.")
                break
            else:
                print(f"❌ Gemini Processing Error on Lead {lead['id']}: {e}")

if __name__ == "__main__":
    combined_data = []
    combined_data.extend(fetch_github_data("langchain-ai/langgraph"))
    combined_data.extend(fetch_reddit_data("LangChain"))
    combined_data.extend(fetch_stackoverflow_data("langchain"))
    
    filtered_leads = run_keyword_filtering(combined_data)
    print(f"\n⚡ INGESTION COMPLETE: Found {len(filtered_leads)} Qualified Signals.")
    
    qualify_and_export_leads(filtered_leads, "leads.md")