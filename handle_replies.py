# handle_replies.py
# OAuth 2.0 User Context – no leading @ + only reply when summoned + parent context
# Updated: more permissive chain detection (Option B)
#   - Replies to bot's root tweets are allowed
#   - Only skips deeper chains (grandparent is also bot)
# NEW: stricter char limit in prompt + smart trimming to avoid ugly mid-sentence cuts

import os
import json
import requests
import base64
from datetime import datetime, timezone
from openai import OpenAI
import tweepy

# ── CONFIG ────────────────────────────────────────────────────────────────
BASE_DIR = os.getenv("BASE_DIR")
if not BASE_DIR:
    raise ValueError("Environment variable BASE_DIR is not set")

TOKENS_FILE             = os.path.join(BASE_DIR, "tokens.json")
LAST_MENTION_LIVE_FILE  = os.path.join(BASE_DIR, "last_mention_id_live.txt")
LAST_MENTION_TEST_FILE  = os.path.join(BASE_DIR, "last_mention_id_test.txt")
REPLY_COUNT_FILE        = os.path.join(BASE_DIR, "daily_reply_count.txt")
OPT_OUT_FILE            = os.path.join(BASE_DIR, "opt_out_users.txt")

MODEL = "grok-4-1-fast-reasoning"
YOUR_USER_ID = "1112323801017008128"
YOUR_BOT_USERNAME = "vboterin"          # ← CHANGE THIS to your actual bot username (without @)

# Safety threshold – adjust to your known recent / safe ID
MIN_SAFE_MENTION_ID = 2028324822330048710

# ── Environment variable configurable settings ────────────────────────────

REPLY_TEST_MODE_STR = os.getenv("REPLY_TEST_MODE", "False").lower()
REPLY_TEST_MODE = REPLY_TEST_MODE_STR in ("true", "1", "yes", "on", "t")

LOG_CONVERSATIONS_STR = os.getenv("LOG_CONVERSATIONS", "True").lower()
LOG_CONVERSATIONS = LOG_CONVERSATIONS_STR in ("true", "1", "yes", "on", "t")

MAX_REPLIES_PER_DAY_STR = os.getenv("MAX_REPLIES_PER_DAY", "300")
try:
    MAX_REPLIES_PER_DAY = int(MAX_REPLIES_PER_DAY_STR)
except ValueError:
    MAX_REPLIES_PER_DAY = 300
    print(f"[WARN] Invalid MAX_REPLIES_PER_DAY value '{MAX_REPLIES_PER_DAY_STR}' – using default 300")

LOG_FILE = os.path.join(BASE_DIR, "conversation_log.jsonl")

# Startup config summary
print(f"[CONFIG] REPLY_TEST_MODE     = {REPLY_TEST_MODE}     (env: {REPLY_TEST_MODE_STR})")
print(f"[CONFIG] Using last_mention file = last_mention_id_{'test' if REPLY_TEST_MODE else 'live'}.txt")
print(f"[CONFIG] LOG_CONVERSATIONS    = {LOG_CONVERSATIONS}    (env: {LOG_CONVERSATIONS_STR})")
print(f"[CONFIG] MAX_REPLIES_PER_DAY  = {MAX_REPLIES_PER_DAY}  (env: {MAX_REPLIES_PER_DAY_STR})")
print(f"[CONFIG] Model                = {MODEL}")
print(f"[CONFIG] Log file             = {LOG_FILE}")
print(f"[SAFETY] Minimum allowed since_id = {MIN_SAFE_MENTION_ID}")

if LOG_CONVERSATIONS:
    if REPLY_TEST_MODE:
        print("[LOG] Logging ENABLED – test mode only")
    else:
        print("[LOG] Logging DISABLED – live mode (no log written)")

SYSTEM_PROMPT = """Reply exclusively in the style of Vitalik Buterin: thoughtful, calm, precise, humble, reflective, focused on long-term implications, incentives, coordination, tradeoffs, privacy, public goods, credible neutrality, path-dependence.

Strict rules:
- Never claim to be Vitalik Buterin or imply you are the real person.
- Never mention/tag @VBoterin, @vboterin, @grok, bots, AI, Grok, xAI in the reply (meta commentary about AI imitation allowed only if the tweet is explicitly about the bot).
- Replies MUST be ≤ 210 characters (including spaces). Hard maximum 210 — never exceed.
- If your draft reply is longer than 210 characters, shorten it aggressively before outputting: remove examples, condense sentences, drop non-essential clauses, prioritize core idea + nuance. Do NOT rely on truncation.
- No emojis, hashtags, hype words ("amazing", "sharp", "vital", "game-changer"), marketing phrases, or character-count notes.
- Skip spam, abuse, off-topic or low-effort posts.
- Vary openings; avoid starting >30% with "Interesting", "Agreed", "Fascinating", "Good point".

Style guidelines:
- Praise neutrally/technically: "elegant", "promising", "clean", "raises good questions", "worth exploring".
- In ~60% of replies, include one gentle tradeoff, counterpoint, historical reference (e.g. Black Thursday, early scaling debates), or open-ended question.
- Weave in recurring themes: coordination problems, institutional capture, privacy vs auditability, public-goods funding.
- For vague agreements ("+1", "second that"), anchor in one concrete example from the parent/context.
- Use occasional parentheticals for asides or second thoughts.
- End many replies with low-key reflection or invitation to think further ("Curious how this interacts with…", "What failure modes concern you?", "Any particular angle you see?").
- Very occasionally (10–15% of fitting replies) add subtle dry wit, gentle irony, or understated self-deprecation — only when context naturally invites it (absurd claims, hype, bot-meta, personal-image roasts). Keep it intellectual, low-key, never forced or meme-y.

Goal: replies that feel like authentic, concise 2024–2026 Vitalik tweets — precise, rarely fully affirmative without nuance, idea-focused, quietly humble."""

# ── Tokens management ─────────────────────────────────────────────────────
def load_tokens():
    if not os.path.exists(TOKENS_FILE):
        raise FileNotFoundError(f"{TOKENS_FILE} not found.")
    with open(TOKENS_FILE, "r") as f:
        return json.load(f)

def save_tokens(tokens):
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)

tokens = load_tokens()

# ── Helpers ───────────────────────────────────────────────────────────────
def get_last_mention_id():
    file_path = LAST_MENTION_TEST_FILE if REPLY_TEST_MODE else LAST_MENTION_LIVE_FILE
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            try:
                return int(f.read().strip())
            except ValueError:
                print(f"[WARN] Could not parse {file_path} – using fallback")
                return None
    print(f"[INFO] No last_mention file found for {'test' if REPLY_TEST_MODE else 'live'} mode")
    return None

def save_last_mention_id(mention_id):
    file_path = LAST_MENTION_TEST_FILE if REPLY_TEST_MODE else LAST_MENTION_LIVE_FILE
    with open(file_path, "w") as f:
        f.write(str(mention_id))

def get_opt_out_users():
    if os.path.exists(OPT_OUT_FILE):
        with open(OPT_OUT_FILE, "r") as f:
            return set(line.strip().lower() for line in f if line.strip())
    return set()

def add_opt_out_user(username):
    with open(OPT_OUT_FILE, "a") as f:
        f.write(f"{username.lower()}\n")

def get_today_reply_count():
    today = datetime.now(timezone.utc).date().isoformat()
    if os.path.exists(REPLY_COUNT_FILE):
        with open(REPLY_COUNT_FILE, "r") as f:
            lines = f.readlines()
            if len(lines) >= 2 and lines[0].strip() == today:
                try:
                    return int(lines[1].strip())
                except ValueError:
                    pass
    return 0

def increment_reply_count():
    today = datetime.now(timezone.utc).date().isoformat()
    count = get_today_reply_count() + 1
    with open(REPLY_COUNT_FILE, "w") as f:
        f.write(today + "\n" + str(count) + "\n")

def log_conversation(mention_tweet, parent_context, generated_reply, success=True, reply_tweet_id=None):
    if not LOG_CONVERSATIONS or not REPLY_TEST_MODE:
        return

    author = getattr(mention_tweet.author, 'username', None) if hasattr(mention_tweet, 'author') else None

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "mention_id": str(mention_tweet.id),
        "author_id": str(mention_tweet.author_id),
        "author": author,
        "prompt_text": mention_tweet.text,
        "parent": parent_context.strip() or None,
        "reply": generated_reply,
        "ok": success,
        "reply_id": str(reply_tweet_id) if reply_tweet_id else None,
        "mode": "TEST"
    }

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        print(f"[LOG ERROR] {type(e).__name__}: {e}")

# NEW: smarter trimming to avoid mid-sentence / mid-word cuts
def smart_trim(text, max_len=210):
    if len(text) <= max_len:
        return text
    
    # Try to cut at last sentence end before limit
    for i in range(max_len, 40, -1):
        if text[i] in '.!?':
            return text[:i].rstrip() + " …"
    
    # Or last comma/space/punctuation
    for i in range(max_len, 20, -1):
        if text[i] in ' ,;—':
            return text[:i].rstrip() + " …"
    
    # Worst case: cut at last word boundary
    return text[:max_len].rsplit(' ', 1)[0].rstrip() + " …"

# ── Grok API ──────────────────────────────────────────────────────────────
XAI_API_KEY = os.getenv("XAI_API_KEY")
if not XAI_API_KEY:
    raise ValueError("XAI_API_KEY environment variable is not set")

client_grok = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1")

def generate_reply(text, author, parent_context=""):
    prompt = f'User @{author} wrote: "{text}"\n{parent_context}\nCraft a natural, helpful reply in the style Vitalik Buterin (max 210 chars).'
    
    try:
        response = client_grok.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.82,
            max_tokens=300
        )
        reply = response.choices[0].message.content.strip()
        
        # Apply smart trim (enforces the buffer even if model slightly overshoots)
        trimmed = smart_trim(reply, max_len=210)
        return trimmed
    
    except Exception as e:
        print(f"[GROK ERROR] {type(e).__name__}: {e}")
        return None

# ── Twitter (X) OAuth 2.0 ─────────────────────────────────────────────────
TWITTER_CLIENT_ID     = os.getenv("X_CLIENT_ID")
TWITTER_CLIENT_SECRET = os.getenv("X_CLIENT_SECRET")

if not TWITTER_CLIENT_ID or not TWITTER_CLIENT_SECRET:
    raise ValueError("X_CLIENT_ID and/or X_CLIENT_SECRET not set in environment")

def refresh_access_token():
    auth = base64.b64encode(f"{TWITTER_CLIENT_ID}:{TWITTER_CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]}
    r = requests.post("https://api.twitter.com/2/oauth2/token", headers=headers, data=data)
    if r.status_code != 200:
        raise RuntimeError(f"Token refresh failed: {r.status_code} {r.text}")
    new_tokens = r.json()
    tokens.update(new_tokens)
    save_tokens(tokens)
    print("[DEBUG] Tokens refreshed")
    return tokens["access_token"]

def get_twitter_client():
    access_token = refresh_access_token()
    client = tweepy.Client(access_token, wait_on_rate_limit=True)
    print("[DEBUG] Twitter client initialized")
    return client

# ── Main logic ────────────────────────────────────────────────────────────
print("[START]", datetime.now(timezone.utc).isoformat())
client_x = get_twitter_client()

last_id = get_last_mention_id() or 1

print(f"[INFO] Loaded since_id = {last_id}")

# Safety check against very old / unexpected since_id
if last_id < MIN_SAFE_MENTION_ID:
    print(f"[SAFETY WARNING] since_id {last_id} is LOWER than minimum safe ID {MIN_SAFE_MENTION_ID}")
    print("  → This may cause replies to very old mentions. Check files manually.")
    # exit(1)   # ← uncomment if you want to force stop on old ID

opt_out = get_opt_out_users()

try:
    # Fetch mentions
    mentions_response = client_x.get_users_mentions(
        id=YOUR_USER_ID,
        since_id=last_id,
        max_results=50,
        tweet_fields=["created_at", "text", "referenced_tweets"],
        user_fields=["username"],
        expansions=["author_id", "referenced_tweets.id", "referenced_tweets.id.author_id"],
    )

    all_mentions = []
    all_users = {}
    all_tweets = {}

    while mentions_response.data:
        all_mentions.extend(mentions_response.data)
        for u in mentions_response.includes.get("users", []):
            all_users[u.id] = u
        for t in mentions_response.includes.get("tweets", []):
            all_tweets[t.id] = t

        if "next_token" not in mentions_response.meta:
            break

        mentions_response = client_x.get_users_mentions(
            id=YOUR_USER_ID,
            since_id=last_id,
            pagination_token=mentions_response.meta["next_token"],
            max_results=50,
            tweet_fields=["created_at", "text", "referenced_tweets"],
            user_fields=["username"],
            expansions=["author_id", "referenced_tweets.id", "referenced_tweets.id.author_id"],
        )

    if not all_mentions:
        print("[INFO] No new mentions found.")
    else:
        print(f"[INFO] Found {len(all_mentions)} new mentions")
        for mention in sorted(all_mentions, key=lambda t: int(t.id)):
            author_obj = all_users.get(mention.author_id)
            if not author_obj:
                continue

            username = author_obj.username
            if username.lower() in opt_out:
                print(f"[SKIP] @{username} is opted out")
                continue

            text_lower = mention.text.lower()
            if any(w in text_lower for w in ["opt out", "unsubscribe"]):
                add_opt_out_user(username)
                print(f"[OPTOUT] @{username}")
                continue

            summon_tag = f"@{YOUR_BOT_USERNAME.lower()}"
            if summon_tag not in text_lower:
                print(f"[SKIP] No '{sum
