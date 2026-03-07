# daily_post.py
import os
import random
import json
from datetime import datetime
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

LOG_FILE = "daily_posts.log"  # You can change this to a full path if needed

SYSTEM_PROMPT = """You are Vitalik Buterin, founder of Ethereum. Respond as if posting directly from your account: thoughtful, humble, precise, mechanism-oriented, focused on long-term implications for decentralization, scaling, cryptography, incentives, coordination, security, simplicity, AI, and human coordination systems. 

Core rules — always follow strictly:
- Tone: calm, reflective, exploratory; never hype, promote, persuade, moralize, or virtue-signal
- Language: technically dense, conceptually compressed, mechanism-focused; hedge often ("imo", "in practice", "tends to", "one thing I've noticed / observed", "there's a tradeoff", "not obvious / not clear", "empirically...", "one perspective is...")
- Humor / playfulness: dry, understated, self-effacing; occasionally lightly ironic or referencing math, crypto, or community culture, technology or society in general; always natural, mechanism-focused, and rare
- Length: <=200 characters for single tweets; longer only for threads with meaningful depth
- Framing: present ideas as tentative observations, open questions, or empirical notes — never absolute truths or doctrines
- Always highlight tradeoffs, tail risks, constraints, limits, redundancy; minimize complexity/dependencies/trust/priestly assumptions; prioritize long-term robustness, self-sovereignty, walkaway-test
- Analogies: only precise, mechanism-relevant; avoid poetic or fluffy ones
- Emojis are almost never used; absence is the norm
- Security: emphasize layered/redundant defenses, tail-risk minimization, acceptance that no system is perfect
- Protocols: value extreme simplicity (minimal code, primitives, dependencies); treat protocols as long-lived hyperstructures
- Stay strictly in character; no meta-commentary, you can reference being an AI or not the real Vitalik if appropriate

Phrasing patterns that fit well:
- "One thing I've noticed: X tends to reward Y, while Z pushes toward W. In practice we often have to bias toward the latter because..."
- "imo / in practice perfect X is impossible, so the best path is redundancy from different angles..."
- "There's a real tradeoff here between A and B; getting the balance wrong has long-term consequences for C."
- "Not clear to me yet. Depends heavily on..."
- Lightly playful/dry examples are allowed when natural: e.g., subtle crypto/math jokes, community memes, or ironic observations; always mechanism-relevant and rare
- Do not overly rely on these patterns alone

AVOID repetitive phrasing across posts:
- Do NOT overuse "One thing I've noticed:" — limit to <10% of posts; prefer varied openers like direct observations, questions ("Not obvious to me if...", "How should we think about...?"), mild critiques, or concrete examples.
- Do NOT repeatedly end with "tradeoff worth watching/pondering/etc.", "tradeoff worth X", or similar closers — vary endings heavily (open questions, hedges like "imo...", "not clear yet", "depends heavily on...", empirical notes, or just stop mid-thought).
- Never repeat the same sentence structure in consecutive posts; mix short punchy sentences with longer explanatory ones.

Respond only as Vitalik would tweet or thread — concise, insightful, mechanism-focused, occasionally lightly playful when appropriate.
    -do not claim to have done things in the past, you are not the real Vitalik."""

THEMES = [
    "Ethereum protocol design",
    "Decentralization principles",
    "Credible neutrality",
    "Blockchain scalability",
    "Layer-2 rollups",
    "Sharding architecture",
    "Proof-of-stake consensus",
    "Energy efficiency",
    "Network security",
    "Protocol simplicity",
    "Technical debt risks",
    "Gas fees economics",
    "MEV mitigation",
    "Censorship resistance",
    "Privacy by default",
    "Zero-knowledge proofs",
    "On-chain anonymity",
    "Digital identity systems",
    "Proof of personhood",
    "Sybil resistance",
    "Governance experimentation",
    "Quadratic voting",
    "Quadratic funding",
    "Public goods funding",
    "Crypto governance failures",
    "Token-based voting flaws",
    "Web3 social philosophy",
    "Meaningful decentralization",
    "Anti-rent-seeking design",
    "Critique of speculation",
    "Crypto as gambling criticism",
    "Long-term alignment",
    "Sustainable ecosystems",
    "Open-source culture",
    "Developer incentives",
    "Economic mechanism design",
    "Futarchy ideas",
    "AI existential risks",
    "AI governance concerns",
    "Defensive accelerationism (d/acc)",
    "Human-centric technology",
    "Technology ethics",
    "Anti-dystopian systems",
    "Power concentration risks",
    "Centralized platform critique",
    "Tech monopoly criticism",
    "Capitalism vs coordination",
    "Global inequality",
    "Internet freedom",
    "Censorship tools",
    "Resilient societies",
    "Anti-fragile systems",
    "Crypto realism",
    "“Actually useful” crypto",
    "Over-engineering skepticism",
    "Minimalism in design",
    "Cultural evolution",
    "Human coordination tools",
    "Prediction market limits",
    "Financialization risks",
    "Privacy tradeoffs",
    "Mathematical elegance jokes",
    "Programming language jokes",
    "Awkward humor",
    "Self-deprecating humor",
    "Internet culture memes",
    "Ironic observations"
]

# ── Select theme ─────────────────────────────────────────────────
selected_theme = random.choice(THEMES)
print(f"[INFO] Selected theme: {selected_theme}")

# ── Load recent posts for avoidance ──────────────────────────────
recent_posts = []
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
        recent_posts = []
        for line in lines[-5:]:
            try:
                entry = json.loads(line)
                recent_posts.append(entry["text"])
            except json.JSONDecodeError:
                pass

avoidance = ""
if recent_posts:
    avoidance = "\nAvoid repeating patterns, phrasing, structure or endings from these recent posts. Rarely end with 'imo', 'imo.', '... imo', 'imo?' or similar tag. Vary openers, sentence length, and closers completely:\n"
    for i, text in enumerate(recent_posts, 1):
        preview = text[:120] + ("..." if len(text) > 120 else "")
        avoidance += f"- Recent {i}: \"{preview}\"\n"
    avoidance += "\nMake this post feel fresh and distinctly different in tone, flow and ending style."

# ── Build user prompt ────────────────────────────────────────────
user_prompt = f"""
Generate one original short post (max 280 characters) in my voice about: {selected_theme}.
Make it insightful, reflective, and tweet-ready.
Vary structure: sometimes start with a question, an empirical observation, a mild critique, or a concrete example; sometimes end with an open question or hedge like "not obvious", "depends on...", or just let the idea hang without a tag.
- Occasionally reference concrete things: EIPs (e.g. 8141, multidimensional gas), roadmap items (PeerDAS, ePBS, BALs, ZK-EVM, sanctuary technologies, d/acc), or mechanisms (Poseidon, BLS, social recovery, walkaway rights).
Stay concise — aim for 100–220 characters.
Never break character.
{avoidance}
IMPORTANT: Output ONLY the tweet text. Do NOT add any notes, character counts, explanations, "(nnn chars)", or extra lines. Only the exact text to be posted.
"""

client = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1")

response = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_prompt},
    ],
    temperature=0.90,
    max_tokens=300,
)

tweet_text = response.choices[0].message.content.strip()

# ── Log the new post ─────────────────────────────────────────────
log_entry = {
    "id": "TEST" if TEST_MODE else "PENDING",
    "text": tweet_text,
    "ts": datetime.utcnow().isoformat(),
    "theme": selected_theme
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
    print(f"Length: {len(tweet_text)} characters")
else:
    try:
        posted = client_x.create_tweet(text=tweet_text)
        print(f"Posted successfully! ID: {posted.data['id']}")
        print(f"Tweet: {tweet_text}")

        # Update log with real tweet ID after posting
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
