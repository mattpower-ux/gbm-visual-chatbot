"""Signed anonymous sessions and server-side abuse limits, shared across workers."""
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import threading
import time

from fastapi import HTTPException, Request
from app.config import get_settings
from app.reader_data import database

_slots = threading.BoundedSemaphore(int(os.getenv("CHAT_MAX_CONCURRENT", "4")))
PUBLIC_WORK_PATHS = {"/chat", "/api/related-cards"}


def secret():
    configured = os.getenv("CHAT_SESSION_SECRET", "")
    if configured:
        return configured.encode()
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT OR IGNORE INTO metadata VALUES ('session_secret', ?)", (secrets.token_hex(32),))
        return bytes.fromhex(db.execute("SELECT value FROM metadata WHERE key='session_secret'").fetchone()[0])


def fingerprint(request):
    if os.getenv("RENDER") == "true":
        # Render's public ingress is Cloudflare-only. XFF (and Uvicorn's
        # derived client) can contain caller input; use the edge-replaced IP.
        # Never enable this trust model on a directly accessible origin.
        try:
            address = str(ipaddress.ip_address(request.headers.get("cf-connecting-ip", "")))
        except ValueError:
            raise HTTPException(503, "Unable to verify the connection. Please try again shortly.") from None
    else:
        address = request.client.host if request.client else "unknown"
    return hmac.new(secret(), address.encode(), hashlib.sha256).hexdigest()


def rate_limit(key, maximum, period):
    now = int(time.time())
    bucket = now // period
    with database() as db:
        db.execute("CREATE TABLE IF NOT EXISTS rate_limits (key TEXT, bucket INTEGER, expires INTEGER, count INTEGER, PRIMARY KEY(key,bucket))")
        db.execute("DELETE FROM rate_limits WHERE expires < ?", (now,))
        db.execute("INSERT INTO rate_limits VALUES (?,?,?,1) ON CONFLICT(key,bucket) DO UPDATE SET count=count+1", (key, bucket, (bucket + 1) * period))
        count = db.execute("SELECT count FROM rate_limits WHERE key=? AND bucket=?", (key, bucket)).fetchone()[0]
    if count > maximum:
        raise HTTPException(429, "Too many requests. Please wait and try again.", headers={"Retry-After": str((bucket + 1) * period - now)})


def check_origin(request):
    origin = request.headers.get("origin", "")
    allowed = set(get_settings().allowed_origins)
    # Same-origin admin previews and the standalone widget remain usable.
    same_origin = str(request.base_url).rstrip("/")
    if origin and origin not in allowed and origin != same_origin:
        raise HTTPException(403, "This origin is not allowed.")
    if request.headers.get("sec-fetch-site") == "cross-site" and not origin:
        raise HTTPException(403, "Origin required.")


def issue_session(request):
    check_origin(request)
    key = fingerprint(request)
    rate_limit("session:global", 300, 60)
    rate_limit("session:" + key, 30, 3600)
    sid = "web-" + secrets.token_urlsafe(24)
    expires = int(time.time()) + 12 * 3600
    raw = base64.urlsafe_b64encode(json.dumps({"sid": sid, "exp": expires}).encode()).decode().rstrip("=")
    sig = hmac.new(secret(), raw.encode(), hashlib.sha256).hexdigest()
    return {"session_id": sid, "token": raw + "." + sig, "expires_at": expires}


def verify_token(token):
    try:
        if len(token) > 600:
            raise ValueError()
        raw, signature = token.split(".")
        expected = hmac.new(secret(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        if payload["exp"] < time.time() or not re.fullmatch(r"web-[A-Za-z0-9_-]{32}", payload["sid"]):
            raise ValueError()
        return payload["sid"]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(401, "Your chat session expired. Please try again.") from None


def admit_request(request: Request):
    check_origin(request)
    ua = request.headers.get("user-agent", "").lower()
    if re.search(r"bot\b|crawler|spider|scrapy|headlesschrome", ua):
        raise HTTPException(403, "Automated querying is not supported.")
    key = fingerprint(request)
    rate_limit("chat:global", int(os.getenv("CHAT_GLOBAL_PER_MINUTE", "120")), 60)
    rate_limit("requests:" + key, int(os.getenv("CHAT_REQUESTS_PER_MINUTE", "20")), 60)
    rate_limit("hour:" + key, int(os.getenv("CHAT_REQUESTS_PER_HOUR", "120")), 3600)
    sid = verify_token(request.headers.get("x-chat-token", ""))
    rate_limit("sid:" + sid, 20, 60)
    if not _slots.acquire(blocking=False):
        raise HTTPException(503, "The chatbot is busy. Please try again shortly.", headers={"Retry-After": "5"})
    request.state.chat_session_id = sid


def release_request():
    _slots.release()
