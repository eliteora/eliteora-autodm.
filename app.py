"""
Auto DM Pro  -  Instagram + Facebook (Meta platforms)

Features
  * Comment keyword  ->  private DM (Instagram + Facebook Page)
  * Optional public comment reply ("Sent to your DM!")
  * Auto-reply to incoming DMs (keyword match + welcome message)
  * Multiple products, each with its own keywords and message
  * Limit an automation to specific posts/reels
  * No duplicate DMs, leads saved in a database, CSV export
  * Meta signature check for security

Run locally:   python app.py
Run on server: gunicorn app:app
"""

import csv
import hashlib
import hmac
import io
import logging
import os
import random
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, Response, request

import config

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("autodm")

# ---------- Secrets come from environment variables (never type them here) ----------
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "")
APP_SECRET = os.environ.get("APP_SECRET", "")
IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
IG_USER_ID = os.environ.get("IG_USER_ID", "")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
# Check Meta's docs for the newest API version and update if needed
API_VERSION = os.environ.get("API_VERSION", "v23.0")
DB_PATH = os.environ.get("DB_PATH", "leads.db")


# =============================== DATABASE ===============================
def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                platform TEXT,
                event_id TEXT UNIQUE,
                user_id TEXT,
                username TEXT,
                text TEXT,
                product TEXT,
                dm_status TEXT
            )"""
        )


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def claim_event(platform, event_id, user_id, username, text, product):
    """Returns True only the first time we see this event (prevents duplicates)."""
    with sqlite3.connect(DB_PATH) as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO leads "
            "(ts, platform, event_id, user_id, username, text, product, dm_status) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (now_iso(), platform, event_id, user_id, username, text, product, "pending"),
        )
        return cur.rowcount == 1


def set_status(event_id, status):
    with sqlite3.connect(DB_PATH) as c:
        c.execute("UPDATE leads SET dm_status=? WHERE event_id=?", (status, event_id))


def fallback_sent_recently(platform, user_id, hours=24):
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute(
            "SELECT 1 FROM leads WHERE platform=? AND user_id=? "
            "AND product='_fallback' AND ts>? LIMIT 1",
            (platform, user_id, since),
        ).fetchone()
    return row is not None


# =============================== HELPERS ===============================
def first_name(name):
    """priya_sharma99 -> Priya | Rahul Verma -> Rahul | unclear -> there"""
    parts = re.findall(r"[A-Za-z\u00C0-\u024F\u0900-\u097F]+", name or "")
    if not parts or len(parts[0]) < 3:
        return "there"
    return parts[0].capitalize()


def fill(text, name, link=""):
    return text.replace("{name}", first_name(name)).replace("{link}", link)


def build_messages(product, name):
    """Returns (card_message_or_None, text_message) for a product."""
    link = (product.get("link") or "").strip()
    text_msg = {"text": fill(product["dm"], name, link)}

    image = (product.get("image_url") or "").strip()
    usable = (
        getattr(config, "SEND_PRODUCT_CARD", False)
        and image.startswith("http") and link.startswith("http")
        and "PASTE" not in image and "PASTE" not in link
    )
    if not usable:
        return None, text_msg

    subtitle = f"{product.get('card_subtitle', '')}\n{config.CARD_DISCLOSURE}".strip()
    card = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "generic",
                "elements": [{
                    "title": fill(product.get("card_title") or product["name"], name)[:80],
                    "subtitle": subtitle[:80],
                    "image_url": image,
                    "default_action": {"type": "web_url", "url": link},
                    "buttons": [{
                        "type": "web_url",
                        "url": link,
                        "title": (product.get("button_text") or "Shop Now")[:20],
                    }],
                }],
            },
        }
    }
    return card, text_msg


def send_with_fallback(send_fn, target, card, text_msg):
    """Try the premium card first; if Instagram/Facebook rejects it, send text."""
    if card and send_fn(target, card):
        return True
    if card:
        log.warning("Card was rejected, sending the text message instead")
    return send_fn(target, text_msg)


def match_product(text, media_id=None):
    """Find the first product whose keyword appears in the text."""
    t = (text or "").lower()
    for p in config.PRODUCTS:
        ids = p.get("media_ids") or []
        if media_id is not None and ids and str(media_id) not in [str(i) for i in ids]:
            continue
        if any(k.lower() in t for k in p["keywords"]):
            return p
    return None


def signature_is_valid(raw_body, header):
    if not APP_SECRET or not header:
        return False
    expected = "sha256=" + hmac.new(APP_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


def api_post(url, json=None, params=None, bearer=None):
    headers = {"Authorization": f"Bearer {bearer}"} if bearer else {}
    try:
        r = requests.post(url, json=json, params=params, headers=headers, timeout=15)
        ok = r.status_code == 200
        if not ok:
            log.error("API error %s: %s", r.status_code, r.text[:300])
        return ok
    except requests.RequestException as e:
        log.error("Network error: %s", e)
        return False


# =============================== SENDERS ===============================
GRAPH_IG = f"https://graph.instagram.com/{API_VERSION}"
GRAPH_FB = f"https://graph.facebook.com/{API_VERSION}"


def ig_private_reply(comment_id, message):
    return api_post(
        f"{GRAPH_IG}/{IG_USER_ID}/messages",
        json={"recipient": {"comment_id": comment_id}, "message": message},
        bearer=IG_ACCESS_TOKEN,
    )


def ig_public_reply(comment_id, text):
    return api_post(
        f"{GRAPH_IG}/{comment_id}/replies",
        params={"message": text},
        bearer=IG_ACCESS_TOKEN,
    )


def ig_send_dm(user_id, message):
    return api_post(
        f"{GRAPH_IG}/{IG_USER_ID}/messages",
        json={"recipient": {"id": user_id}, "message": message},
        bearer=IG_ACCESS_TOKEN,
    )


def fb_private_reply(comment_id, message):
    return api_post(
        f"{GRAPH_FB}/{FB_PAGE_ID}/messages",
        json={"recipient": {"comment_id": comment_id}, "message": message},
        params={"access_token": FB_PAGE_TOKEN},
    )


def fb_public_reply(comment_id, text):
    return api_post(
        f"{GRAPH_FB}/{comment_id}/comments",
        params={"message": text, "access_token": FB_PAGE_TOKEN},
    )


def fb_send_dm(user_id, message):
    return api_post(
        f"{GRAPH_FB}/{FB_PAGE_ID}/messages",
        json={
            "recipient": {"id": user_id},
            "messaging_type": "RESPONSE",
            "message": message,
        },
        params={"access_token": FB_PAGE_TOKEN},
    )


SENDERS = {
    "instagram": {"private": ig_private_reply, "public": ig_public_reply, "dm": ig_send_dm},
    "facebook": {"private": fb_private_reply, "public": fb_public_reply, "dm": fb_send_dm},
}


# =============================== LOGIC ===============================
def handle_comment(platform, comment_id, user_id, username, text, media_id):
    log.info("[%s] comment from %s on MEDIA ID: %s", platform, username or user_id, media_id)
    product = match_product(text, media_id)
    if not product:
        return
    if not claim_event(platform, comment_id, user_id, username, text, product["name"]):
        return  # already handled

    send = SENDERS[platform]
    card, text_msg = build_messages(product, username)
    ok = send_with_fallback(send["private"], comment_id, card, text_msg)
    set_status(comment_id, "sent" if ok else "failed")

    replies = product.get("public_replies") or []
    if ok and replies:
        send["public"](comment_id, fill(random.choice(replies), username))


def handle_dm(platform, message_id, sender_id, text):
    product = match_product(text)  # media_id=None means "no post filter"
    send = SENDERS[platform]["dm"]

    if product:
        if claim_event(platform, message_id, sender_id, "", text, product["name"]):
            card, text_msg = build_messages(product, "")
            ok = send_with_fallback(send, sender_id, card, text_msg)
            set_status(message_id, "sent" if ok else "failed")
        return

    if config.SEND_FALLBACK and not fallback_sent_recently(platform, sender_id):
        if claim_event(platform, message_id, sender_id, "", text, "_fallback"):
            ok = send(sender_id, {"text": fill(config.FALLBACK_DM, "")})
            set_status(message_id, "sent" if ok else "failed")


def run_in_background(fn, *args):
    threading.Thread(target=fn, args=args, daemon=True).start()


def process_payload(data):
    obj = data.get("object")

    for entry in data.get("entry", []):
        # ---------------- INSTAGRAM ----------------
        if obj == "instagram" and config.ENABLE_INSTAGRAM:
            for ch in entry.get("changes", []):
                if ch.get("field") != "comments":
                    continue
                v = ch.get("value", {})
                sender = v.get("from", {})
                if sender.get("id") == IG_USER_ID:
                    continue  # ignore our own comments
                run_in_background(
                    handle_comment, "instagram", v.get("id"), sender.get("id"),
                    sender.get("username", ""), v.get("text", ""),
                    str(v.get("media", {}).get("id", "")),
                )
            for m in entry.get("messaging", []):
                msg = m.get("message", {})
                sender_id = m.get("sender", {}).get("id")
                if msg.get("is_echo") or not msg.get("text") or sender_id == IG_USER_ID:
                    continue
                run_in_background(handle_dm, "instagram", msg.get("mid"), sender_id, msg["text"])

        # ---------------- FACEBOOK PAGE ----------------
        elif obj == "page" and config.ENABLE_FACEBOOK:
            for ch in entry.get("changes", []):
                v = ch.get("value", {})
                if ch.get("field") != "feed" or v.get("item") != "comment" or v.get("verb") != "add":
                    continue
                sender = v.get("from", {})
                if sender.get("id") == FB_PAGE_ID:
                    continue  # ignore our own comments
                run_in_background(
                    handle_comment, "facebook", v.get("comment_id"), sender.get("id"),
                    sender.get("name", ""), v.get("message", ""), str(v.get("post_id", "")),
                )
            for m in entry.get("messaging", []):
                msg = m.get("message", {})
                sender_id = m.get("sender", {}).get("id")
                if msg.get("is_echo") or not msg.get("text") or sender_id == FB_PAGE_ID:
                    continue
                run_in_background(handle_dm, "facebook", msg.get("mid"), sender_id, msg["text"])


# =============================== ROUTES ===============================
@app.route("/")
def home():
    return f"{config.BRAND_NAME} Auto DM is running ✅"


@app.route("/webhook", methods=["GET"])
def verify():
    if (
        request.args.get("hub.mode") == "subscribe"
        and VERIFY_TOKEN
        and request.args.get("hub.verify_token") == VERIFY_TOKEN
    ):
        return request.args.get("hub.challenge", ""), 200
    return "Verification failed", 403


@app.route("/webhook", methods=["POST"])
def receive():
    raw = request.get_data()
    if not signature_is_valid(raw, request.headers.get("X-Hub-Signature-256", "")):
        return "Invalid signature", 403
    process_payload(request.get_json(silent=True) or {})
    return "OK", 200  # answer fast; work continues in background


@app.route("/leads.csv")
def leads_csv():
    """Download your leads:  https://your-site/leads.csv?key=YOUR_ADMIN_KEY"""
    if not ADMIN_KEY or request.args.get("key") != ADMIN_KEY:
        return "Not allowed", 403
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute(
            "SELECT ts, platform, user_id, username, text, product, dm_status "
            "FROM leads ORDER BY id DESC"
        ).fetchall()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["time", "platform", "user_id", "username", "message", "product", "dm_status"])
    w.writerows(rows)
    return Response(out.getvalue(), mimetype="text/csv")


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
