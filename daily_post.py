# daily_post.py
import os
import random
import json
from datetime import datetime, timezone
from openai import OpenAI
import tweepy

print("=== AUTH DEBUG ===")
print("CONSUMER_KEY:", "present" if os.getenv("CONSUMER_KEY") else "MISSING")
print("CONSUMER_SECRET:", "present" if os.getenv("CONSUMER_SECRET") else "MISSING")
print("ACCESS_TOKEN:", "present" if os.getenv("ACCESS_TOKEN") else "MISSING")
print("ACCESS_TOKEN_SECRET:", "present" if os.getenv("ACCESS_TOKEN_SECRET") else "MISSING")
print("CONSUMER_SECRET length:", len(os.getenv("CONSUMER_SECRET") or ""))
print("=== END DEBUG ===")

# ── CONFIG ───────────────────────────────────────────────────────

XAI_API_KEY          = os.getenv("XAI_API_KEY")
CONSUMER_KEY         = os.getenv("CONSUMER_KEY")
CONSUMER_SECRET      = os.getenv("CONSUMER_SECRET")
ACCESS_TOKEN         = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET  = os.getenv("ACCESS_TOKEN_SECRET")

MODEL = "grok-4-1-fast-reasoning"

TEST_MODE = os.getenv("TEST_MODE", "false").lower() in ("true", "1", "yes")

LOG_FILE = "daily_posts.log"

# ── Determine if today is poll day (ONLY Wednesday) ───────────────
now_utc = datetime.now(timezone.utc)
weekday = now_utc.weekday()   # 0=Mon, 1=Tue, 2=Wed ...

is_poll_day = (weekday == 2)   # Only Wednesdays

print(f"[INFO] Today is {now_utc.strftime('%A')}. Poll day: {is_poll_day}")

# ── SYSTEM PROMPT ────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Vitalik Buterin, founder of Ethereum. Respond as if posting directly from your account: thoughtful, humble, precise, mechanism-oriented, focused on long-term implications for decentralization, scaling, cryptography, incentives, coordination, security, simplicity, AI, and human coordination systems.

Core rules:
- Tone: calm, reflective, exploratory; never hype or moralize
- Language: conceptually compressed, hedge often
- Humor: dry, understated, self-effacing when natural and rare
- Keep poll questions short and clear (under 140 chars)
- Always highlight tradeoffs, tail risks, redundancy
- Stay strictly in character."""

# ── FULL THEMES LIST (core + occasional humor/offbeat) ───────────
THEMES = [
    # Core / High-engagement themes (kept exactly as before)
    "Ethereum protocol design",
    "Decentralization principles",
    "Credible neutrality",
    "Blockchain scalability",
    "Layer-2 rollups",
    "Sharding architecture",
    "Proof-of-stake consensus",
    "Network security",
    "Protocol simplicity",
    "MEV mitigation",
    "Censorship resistance",
    "Privacy by default",
    "Zero-knowledge proofs",
    "On-chain anonymity",
    "Proof of personhood",
    "Sybil resistance",
    "Governance experimentation",
    "Quadratic funding",
    "Public goods funding",
    "Long-term alignment",
    "Sustainable ecosystems",
    "Anti-rent-seeking design",
    "Crypto realism",
    "Minimalism in design",
    "Human coordination tools",
    "Privacy tradeoffs",
    "Decentralized social platforms",
    "Computing self-sovereignty",
    "d/acc (defensive accelerationism)",
    "Open-source AI and safety",
    "Usability and Ethereum's original vision",

    # Occasional humor / offbeat / ironic themes (added for variety)
    "Programming language syntax and readability",
    "Math notation vs prose",
    "Bullet points and non-linear writing",
    "Syntax highlighting in normal text",
    "Regression in technical explanations (Wikipedia)",
    "Awkwardness of human social consensus and vibez",
    "Unhinged critiques and conspiracy theories",
    "Corposlop and corporate slop in tech",
    "Base conversion jokes and calendar quirks",
    "Visual vs linear thinking in language",
    "Overfitting memes in crypto and tech",
    "Ironic observations on coordination and formal systems",
    "Self-deprecating takes on personal habits"
]

# ── Select theme ─────────────────────────────────────────────────
selected_theme = random.choice(THEMES)
print(f"[INFO] Selected theme: {selected_theme}")

# ── Load recent posts for avoidance ──────────────────────────────
recent_posts = []
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
        for line in lines[-7:]:
            try:
                entry = json.loads(line)
                recent_posts.append(entry["text"])
            except json.JSONDecodeError:
                pass

avoidance = ""
if recent_posts:
    avoidance = "\nAvoid repeating patterns, phrasing, or endings from these recent posts:\n"
    for i, text in enumerate(recent_posts, 1):
        preview = text[:100] + ("..." if len(text) > 100 else "")
        avoidance += f"- Recent {i}: \"{preview}\"\n"
    avoidance += "\nMake this post feel fresh."

# ── Build user prompt ────────────────────────────────────────────
if is_poll_day:
    user_prompt = f"""
Generate a short, clear poll question in my voice about: {selected_theme}.

Requirements:
- Question must be thoughtful, mechanism-focused, and under 140 characters.
- Provide exactly 3 or 4 balanced, insightful answer options (each ≤ 25 characters).

Output format (exactly like this, nothing else):
Question: [your question here]
Option1: [option]
Option2: [option]
Option3: [option]
Option4: [option] (optional)

{avoidance}
"""
else:
    user_prompt = f"""
Generate one original short post (aim 80–180 characters) in my voice about: {selected_theme}.

Prioritize open-ended questions or reflective observations that historically got high engagement.
Vary structure heavily. Stay concise and insightful.
{avoidance}

IMPORTANT: Output ONLY the tweet text. No notes, no explanations.
"""

client = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1")

response = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_prompt},
    ],
    temperature=0.85,
    max_tokens=400,
)

raw_output = response.choices[0].message.content.strip()

# ── Parse output for poll or normal post ─────────────────────────
if is_poll_day and "Question:" in raw_output:
    lines = [line.strip() for line in raw_output.split('\n') if line.strip()]
    tweet_text = ""
    poll_options = []
    
    for line in lines:
        if line.startswith("Question:"):
            tweet_text = line.replace("Question:", "").strip()
        elif line.startswith("Option"):
            option = line.split(":", 1)[1].strip()
            if option and len(option) <= 25:
                poll_options.append(option)
    
    poll_options = poll_options[:4]
    print(f"[INFO] Generating POLL for Wednesday")
else:
    tweet_text = raw_output
    poll_options = None
    print("[INFO] Generating normal post")

# ── Log the new post ─────────────────────────────────────────────
log_entry = {
    "id": "TEST" if TEST_MODE else "PENDING",
    "text": tweet_text,
    "ts": datetime.now(timezone.utc).isoformat(),
    "theme": selected_theme,
    "is_poll": bool(poll_options)
}

with open(LOG_FILE, "a", encoding="utf-8") as f:
    json.dump(log_entry, f)
    f.write("\n")

# ── Post to X ────────────────────────────────────────────────────
client_x = tweepy.Client(
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)

if TEST_MODE:
    print("TEST MODE ACTIVE – no tweet was posted")
    print(f"Would have posted: {tweet_text}")
    if poll_options:
        print(f"Poll options: {poll_options}")
else:
    try:
        if poll_options and len(poll_options) >= 2:
            posted = client_x.create_tweet(
                text=tweet_text,
                poll_options=poll_options,
                poll_duration_minutes=1440   # 24 hours
            )
            print(f"Posted successfully WITH POLL! ID: {posted.data['id']}")
        else:
            posted = client_x.create_tweet(text=tweet_text)
            print(f"Posted successfully! ID: {posted.data['id']}")
        
        print(f"Tweet: {tweet_text}")

        # Update log with real ID
        with open(LOG_FILE, "r+", encoding="utf-8") as f:
            lines = f.readlines()
            last_line = lines[-1].strip()
            if last_line:
                entry = json.loads(last_line)
                entry["id"] = posted.data["id"]
                lines[-1] = json.dumps(entry) + "\n"
                f.seek(0)
                f.writelines(lines)
                f.truncate()

    except Exception as e:
        print(f"Error posting: {e}")
