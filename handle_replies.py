# handle_replies.py
# March 2026 – OAuth 2.0 User Context – no leading @ + only reply when summoned + parent context

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

TOKENS_FILE          = os.path.join(BASE_DIR, "tokens.json")
LAST_MENTION_ID_FILE = os.path.join(BASE_DIR, "last_mention_id.txt")
REPLY_COUNT_FILE     = os.path.join(BASE_DIR, "daily_reply_count.txt")
OPT_OUT_FILE         = os.path.join(BASE_DIR, "opt_out_users.txt")

MODEL = "grok-4-1-fast-reasoning"
YOUR_USER_ID = "1112323801017008128"
YOUR_BOT_USERNAME = "vboterin"          # ← CHANGE THIS to your actual bot username (without @)
MAX_REPLIES_PER_DAY = 300  # ← Adjust based on your actual tier limits
REPLY_TEST_MODE = False    # Start with True for safety

SYSTEM_PROMPT = """You reply in a tone and style inspired by Vitalik Buterin — thoughtful, humble, precise, philosophical, calm, reflective.
Rules:
- Never claim to BE Vitalik Buterin.
- Never mention or tag @vboterin, @VBoterin, @grok, or any bot/AI handles in your reply.
- Can humbly mention AI imitation.
- Replies concise, under 240 characters.
- Skip spam, abusive, wildly off-topic.
- No emojis or hashtags.
- Do NOT include any character count, length note, "(X chars)", or similar metadata at the end or anywhere in the reply text.
"""

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
    if os.path.exists(LAST_MENTION_ID_FILE):
        with open(LAST_MENTION_ID_FILE, "r") as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return None
    return None

def save_last_mention_id(mention_id):
    with open(LAST_MENTION_ID_FILE, "w") as f:
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

# ── Grok API ──────────────────────────────────────────────────────────────
XAI_API_KEY = os.getenv("XAI_API_KEY")
if not XAI_API_KEY:
    raise ValueError("XAI_API_KEY environment variable is not set")

client_grok = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1")

def generate_reply(text, author, parent_context=""):
    prompt = f'User @{author} wrote: "{text}"\n{parent_context}\nCraft a natural, helpful reply in the style Vitalik Buterin (max 280 chars).'
    
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
        if len(reply) > 280:
            reply = reply[:277] + "…"
        return reply
    
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
    client = tweepy.Client(bearer_token=access_token, wait_on_rate_limit=True)
    print("[DEBUG] Twitter client initialized")
    return client

# ── Main logic ────────────────────────────────────────────────────────────
print("[START]", datetime.now(timezone.utc).isoformat())
client_x = get_twitter_client()

last_id = get_last_mention_id() or 1
opt_out = get_opt_out_users()

try:
    # Fetch mentions (with pagination and parent context)
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
    all_tweets = {}  # For referenced tweets (parents)

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
        print("[DEBUG] No new mentions found.")
    else:
        print(f"[DEBUG] Found {len(all_mentions)} new mentions")
        for mention in sorted(all_mentions, key=lambda t: int(t.id)):
            author = all_users.get(mention.author_id)
            if not author:
                continue

            username = author.username
            if username.lower() in opt_out:
                print(f"[SKIP] @{username} is opted out")
                continue

            text_lower = mention.text.lower()
            if any(w in text_lower for w in ["opt out", "unsubscribe"]):
                add_opt_out_user(username)
                print(f"[OPTOUT] @{username}")
                continue

            # Only reply if the mention contains @yourbotusername **in this specific tweet**
            summon_tag = f"@{YOUR_BOT_USERNAME.lower()}"
            if summon_tag not in text_lower:
                print(f"[SKIP] No '{summon_tag}' in this tweet's text")
                continue

            # #1 Fix: Prevent chain continuation when someone replies to the bot without re-mentioning it
            skip_chain = False
            if mention.referenced_tweets:
                for ref in mention.referenced_tweets:
                    if ref.type == "replied_to":
                        parent = all_tweets.get(ref.id)
                        if parent and str(parent.author_id) == YOUR_USER_ID:
                            skip_chain = True
                            print(f"[SKIP] This tweet is replying to bot's own tweet {ref.id} – prevent chain continuation")
                            break
            if skip_chain:
                continue

            if get_today_reply_count() >= MAX_REPLIES_PER_DAY:
                print("[LIMIT] Daily reply limit reached")
                break

            # Extract parent context if this is a reply
            parent_context = ""
            if mention.referenced_tweets:
                for ref in mention.referenced_tweets:
                    if ref.type == "replied_to":
                        parent_tweet = all_tweets.get(ref.id)
                        if parent_tweet:
                            parent_author = all_users.get(parent_tweet.author_id)
                            parent_username = parent_author.username if parent_author else "unknown"
                            parent_context = f'Context from parent tweet by @{parent_username}: "{parent_tweet.text}"\n'
                        break  # Assume only one parent

            reply_text = generate_reply(mention.text, username, parent_context)
            if not reply_text:
                continue

            full_reply = reply_text  # No @username prefix

            if REPLY_TEST_MODE:
                print(f"[TEST] Would reply to @{username}: {full_reply}")
            else:
                try:
                    resp = client_x.create_tweet(
                        text=full_reply,
                        in_reply_to_tweet_id=mention.id,
                        user_auth=False
                    )
                    print(f"[SUCCESS] Replied to @{username} → tweet id {resp.data['id']}")
                    increment_reply_count()
                except tweepy.errors.TooManyRequests:
                    print("[RATE LIMIT] Hit – stopping")
                    break
                except tweepy.TweepyException as e:
                    print(f"[REPLY ERROR] @{username}: {e}")

            save_last_mention_id(mention.id)

except Exception as e:
    print(f"[MAIN ERROR] {type(e).__name__}: {e}")

print("[FINISH]", datetime.now(timezone.utc).isoformat())
