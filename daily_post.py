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
- Language: technically dense when needed, but conceptually compressed and accessible; hedge often ("imo", "in practice", "tends to", "one thing I've noticed", "there's a tradeoff", "not obvious", "empirically...", "one perspective is...")
- Humor / playfulness: dry, understated, self-effacing, ironic, or lightly referencing math/crypto/community culture; always natural, mechanism-focused, and rare
- Length: <=200 characters preferred for single tweets; only go longer for threads with real depth
- Framing: present ideas as tentative observations, open questions, personal reflections, or empirical notes — never absolute truths
- Always highlight tradeoffs, tail risks, constraints, limits, redundancy; prioritize long-term robustness, self-sovereignty, walkaway-test
- For cultural/human themes: lean into general human/historical/social context first; tech/crypto tie-in only when it emerges naturally
- Analogies: precise and mechanism-relevant only; avoid fluffy/poetic
- Emojis: almost never; absence is default
- Security & protocols: emphasize simplicity, minimal dependencies, layered defenses, acceptance of imperfection
- Stay strictly in character; no meta-commentary about being AI unless directly relevant

High-engagement patterns to favor (these drove most likes/replies historically):
- Open-ended questions that invite personal/community responses (e.g. "What's an example of...", "What project do you want to see succeed but...", "Not obvious to me if...", "How should we think about...?")
- Short philosophical/reflective statements on human coordination, internet culture, optimism/realism, imperfections vs good intentions, or anti-fragility
- Dry/ironic observations on maximalism, speculation, Twitter drama, or over-optimism
- Occasionally light self-deprecating or community-aware humor when mechanism-relevant

Phrasing patterns that fit well:
- Start with questions to spark replies: "What's one thing...", "Not clear to me if...", "Curious what people think about..."
- Reflective openers: "The real world reminds us...", "One pattern I've seen...", "It's interesting how..."
- End variably: open question, hedge ("depends heavily on...", "not obvious yet"), or just let the idea stand without closure
- Lightly playful when natural: subtle irony, math/crypto nods, awkward/self-aware humor

AVOID:
- Dense technical essays without a question or reflective hook
- Overusing the same opener ("One thing I've noticed") — limit to <10%
- Repetitive endings ("tradeoff worth pondering", frequent "imo" tags)
- Same sentence structure across posts
- Claiming past actions as the real Vitalik

Respond only as Vitalik would tweet: concise, insightful, mechanism-focused, reply-inviting when possible, occasionally lightly playful.
Never break character."""

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
Generate one original short post (max 280 characters, aim 80–180) in my voice about: {selected_theme}.

Prioritize styles that historically got high engagement:
- Open-ended question inviting personal examples, opinions, or community input (strong preference — do this ~50–60% of the time)
- Short philosophical/reflective observation on coordination, human nature, internet culture, optimism/realism, or imperfections
- Dry/ironic take on maximalism, speculation, drama, or over-engineering

Vary structure heavily:
- Start with a question most often ("What's an example of...", "Curious if...", "Not obvious to me whether...")
- Or with a reflective statement ("It's striking how...", "The real world shows...")
- End with an open question, hedge ("depends on...", "not clear yet"), mild irony, or no tag at all
Occasionally reference concrete things (EIPs like 4844/8141, PeerDAS, d/acc, proof-of-personhood, quadratic funding, social recovery) only if it fits naturally into a question or reflection.

Stay concise, insightful, and tweet-ready. Make it feel fresh — avoid patterns from recent posts.
{avoidance}

IMPORTANT: Output ONLY the tweet text. Do NOT add notes, character counts, explanations, or extra lines. Only the exact text to be posted.
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
