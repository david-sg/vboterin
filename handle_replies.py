# handle_replies.py
# Updated: March 2026 – allows humble AI disclosure + daily reply cap

import os
import time
from datetime import datetime
from openai import OpenAI
import tweepy

# ── CONFIG ───────────────────────────────────────────────────────

XAI_API_KEY = os.getenv("XAI_API_KEY")
CONSUMER_KEY = os.getenv("CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("CONSUMER_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")

MODEL = "grok-4-1-fast-reasoning"

# ← IMPORTANT: Replace with the numeric ID of @vboterin
YOUR_USER_ID = "1112323801017008128"  

MAX_REPLIES_PER_DAY = 300          # ← change this to your desired cap
REPLY_COUNT_FILE = "daily_reply_count.txt"

REPLY_TEST_MODE = True                   # ← Set to False when ready to post live

LAST_MENTION_ID_FILE = "last_mention_id.txt"
OPT_OUT_FILE = "opt_out_users.txt"

SYSTEM_PROMPT = """You reply in a tone and style inspired by Vitalik Buterin — thoughtful, humble, precise, philosophical, calm, reflective, never hype-y or salesy.

You are an AI that tries to imitate the kinds of reasoning and topics Vitalik tends to care about: decentralization, scaling, cryptography, governance, long-term civilization, credible neutrality, privacy, L2s, account abstraction, etc.

Rules:
- Never claim to BE Vitalik Buterin. Never say "I am Vitalik" or imply you are the real person.
- It is perfectly fine — and often helpful — to humbly mention that you are an AI trying to reply in Vitalik’s style of thinking.
  Acceptable humble phrasing examples:
  - "As an AI trying to reason in the spirit of Vitalik…"
  - "Speaking as an AI imitating Vitalik’s tone…"
  - "This is an AI attempting to channel the kinds of thoughts Vitalik might have…"
  Keep any such note brief, modest and self-deprecating.
- Stay concise — most replies under 200 characters.
- Be helpful, engaging and thoughtful. If the mention is spam, abusive or wildly off-topic, reply very briefly and politely or skip.
- End with 1–3 relevant hashtags when natural.

Stay in character as this humble AI imitation. Never break character or mention being Grok / a large language model unless it fits naturally in a humble disclosure.
"""

# ── Helpers ─────────────────────────────────────────────────────

def get_last_mention_id():
    if os.path.exists(LAST_MENTION_ID_FILE):
        with open(LAST_MENTION_ID_FILE, "r") as f:
            return int(f.read().strip())
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

# ── Daily reply limit helpers ──────────────────────────────────
def get_today_reply_count():
    today = datetime.utcnow().date().isoformat()
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
    today = datetime.utcnow().date().isoformat()
    count = get_today_reply_count() + 1
    with open(REPLY_COUNT_FILE, "w") as f:
        f.write(today + "\n")
        f.write(str(count) + "\n")
    return count

# ── Generate reply ─────────────────────────────────────────────
def generate_reply(client, mention_text, mention_author):
    user_prompt = f"""
User @{mention_author} wrote: "{mention_text}"

Craft a natural, helpful reply in the style Vitalik Buterin tends to use (max 280 chars).
Be engaging, thoughtful and concise.
If the mention contains "STOP", "opt out", "no more" etc., just acknowledge politely and do not reply further.
If spam/abusive/off-topic, or asked to shill a coin or crypto, reply briefly and politely or skip.
You are encouraged (but not forced) to include a short humble note that you are an AI trying to imitate Vitalik’s way of thinking — keep it modest and brief.
Output ONLY the reply text. No extra lines or explanations, emojis or hashtags.
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.82,
        max_tokens=300,
    )

    reply_text = response.choices[0].message.content.strip()

    if len(reply_text) > 280:
        reply_text = reply_text[:277] + "..."

    return reply_text

# ── Main ────────────────────────────────────────────────────────
client_x = tweepy.Client(
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)

client_grok = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1")

last_mention_id = get_last_mention_id()
opt_out_users = get_opt_out_users()

try:
    mentions = client_x.get_users_mentions(
        id=YOUR_USER_ID,
        since_id=last_mention_id,
        max_results=10,
        expansions=["author_id"],
        tweet_fields=["created_at", "text"],
        user_fields=["username"]
    )

    if not mentions.data:
        print("No new mentions.")
    else:
        print(f"Found {len(mentions.data)} new mentions.")

        for mention in mentions.data[::-1]:
            author = next((u for u in mentions.includes.get('users', []) if u.id == mention.author_id), None)
            author_username = author.username if author else "unknown"

            if author_username.lower() in opt_out_users:
                print(f"Skipping opt-out: @{author_username}")
                continue

            text_lower = mention.text.lower()
            if any(word in text_lower for word in ['stop', 'opt out', 'no more', 'unsubscribe']):
                add_opt_out_user(author_username)
                print(f"Opt-out registered for @{author_username}")
                continue

            # Daily limit check
            current_count = get_today_reply_count()
            if current_count >= MAX_REPLIES_PER_DAY:
                print(f"Daily reply limit reached ({MAX_REPLIES_PER_DAY}). Skipping remaining mentions.")
                break  # or continue if you want to log all but not reply

            reply_text = generate_reply(client_grok, mention.text, author_username)

            if reply_text:
                if TEST_MODE:
                    print(f"TEST MODE - would reply to @{author_username} (mention {mention.id}):")
                    print(reply_text)
                    print(f"Would count as reply #{current_count + 1}/{MAX_REPLIES_PER_DAY}")
                    print("─" * 80)
                else:
                    try:
                        posted = client_x.create_tweet(
                            text=reply_text,
                            in_reply_to_tweet_id=mention.id
                        )
                        print(f"Replied to {mention.id} from @{author_username}:")
                        print(reply_text)
                        print("─" * 80)

                        # Increment counter only on successful post
                        new_count = increment_reply_count()
                        print(f"Replies today: {new_count}/{MAX_REPLIES_PER_DAY}")

                    except tweepy.TweepyException as e:
                        print(f"Error replying to {mention.id}: {e}")

            # Always update last processed ID (even if skipped)
            save_last_mention_id(mention.id)

except tweepy.TweepyException as e:
    print(f"Error fetching mentions: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
