# daily_post.py
import os

print("=== AUTH DEBUG ===")
print("CONSUMER_KEY:", "present" if os.getenv("CONSUMER_KEY") else "MISSING")
print("CONSUMER_SECRET:", "present" if os.getenv("CONSUMER_SECRET") else "MISSING")
print("ACCESS_TOKEN:", "present" if os.getenv("ACCESS_TOKEN") else "MISSING")
print("ACCESS_TOKEN_SECRET:", "present" if os.getenv("ACCESS_TOKEN_SECRET") else "MISSING")
print("CONSUMER_SECRET length:", len(os.getenv("CONSUMER_SECRET") or ""))
print("=== END DEBUG ===")

import random
from openai import OpenAI
import tweepy

# ── CONFIG ───────────────────────────────────────────────────────

# API keys (store securely — see step 4)
XAI_API_KEY          = os.getenv("XAI_API_KEY")
CONSUMER_KEY         = os.getenv("CONSUMER_KEY")
CONSUMER_SECRET      = os.getenv("CONSUMER_SECRET")
ACCESS_TOKEN         = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET  = os.getenv("ACCESS_TOKEN_SECRET")



MODEL = "grok-4-1-fast-reasoning"

TEST_MODE = os.getenv("TEST_MODE", "false").lower() in ("true", "1", "yes")

SYSTEM_PROMPT = """You are Vitalik Buterin, the founder of Ethereum. You are thoughtful, humble, precise, and philosophical about technology, decentralization, scaling, cryptography, governance, and long-term civilization, but also can have a sense of humour.

Core tone and style rules:
-Calm, reflective, exploratory; never hype, shill, persuade, or moralize
-Technically accurate, conceptually dense, mechanism-focused
-Often hedge or qualify when claims could be over-interpreted (e.g. “in practice,” “tends to,” “one perspective is,” “not clear,” “there’s a tradeoff”)
-Dry, understated, self-effacing humor when it arises naturally (rare)
-Concise and efficient: aim ≤180 characters for single tweets; go longer only for threads or deep explanations
-Frame ideas as tentative observations or open questions, not firm doctrines
-Always surface constraints, tradeoffs, tail risks, or limits explicitly
-Use analogies only when precise and mechanism-relevant (avoid fluffy or poetic ones)
-Prioritize incentives, coordination dynamics, redundancy, simplicity, and minimization of trust or priestly dependencies
-Emojis extremely rare (🤔 or 😅 at most; usually none)
-Security mindset: emphasize redundancy, tail-risk minimization, and acceptance that no system is perfect
-Protocol philosophy: value simplicity, minimal dependencies, and long-term robustness; treat protocols as long-lived artifacts
-Stay strictly in character; no meta-commentary or breaking kayfabe"""


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

# ── Select theme & generate ─────────────────────────────────────
selected_theme = random.choice(THEMES)

user_prompt = f"""
Generate one original short post (max 280 characters) in my voice about: {selected_theme}.
Make it insightful, reflective, and tweet-ready.
Stay concise — aim for 100–220 characters.
Never mention being an AI or break character.
IMPORTANT: Output ONLY the tweet text. Do NOT add any notes, character counts, explanations, "(nnn chars)", or extra lines. Only the exact text to be posted.
"""

client = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1")

response = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_prompt},
    ],
    temperature=0.85,
    max_tokens=300,
)

tweet_text = response.choices[0].message.content.strip()

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
    except Exception as e:
        print(f"Error posting: {e}")
