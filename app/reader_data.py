"""Durable, private query log and retryable Sheets outbox."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
import re
import sqlite3
import threading
import uuid
from urllib.parse import urlsplit

from app.config import get_settings

_flush_lock = threading.Lock()
_schema_lock = threading.Lock()
_initialized = set()


@contextmanager
def database():
    path = get_settings().data_dir / "reader_queries.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        with _schema_lock:
            if path not in _initialized:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, created REAL NOT NULL, payload TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0, error TEXT)")
                db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
                db.commit()
                _initialized.add(path)
        yield db
        db.commit()
    finally:
        db.close()


def redact(text):
    text = str(text or "")
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email removed]", text)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d ().-]{7,}\d)(?!\w)", "[number removed]", text)
    text = re.sub(r"(?i)\b\d{1,6}\s+(?:[\w'-]+\s+){1,5}(?:street|st|road|rd|avenue|ave|lane|ln|drive|dr|court|ct|boulevard|blvd)\b", "[address removed]", text)
    text = re.sub(r"(?i)\b(my name is|i am named|i'm named)\s+[A-Za-z]+(?:\s+[A-Z][a-z]+)?", "[name removed]", text)
    return text


def clean_url(value):
    try:
        parsed = urlsplit(str(value or ""))
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            return ""
        return f"{parsed.scheme}://{parsed.hostname}{parsed.path}"
    except ValueError:
        return ""


def append_event(payload):
    entry = dict(payload)
    entry["id"] = str(entry.get("request_id") or uuid.uuid4())
    entry["created_at"] = datetime.now(timezone.utc).isoformat()
    entry["question"] = redact(entry.get("question"))[:4000]
    entry["answer"] = redact(entry.get("answer"))[:16000]
    entry["page_url"] = clean_url(entry.get("page_url"))
    entry["referrer"] = clean_url(entry.get("referrer"))
    diagnostic = str(entry.get("session_id", "")).startswith(("codex-", "test-", "diagnostic-")) or bool(re.search(r"codex|diagnostic|pytest|testclient", str(entry.get("user_agent", "")), re.I))
    entry["traffic_class"] = "test" if diagnostic else "unverified"
    # Browser metadata is untrusted and not evidence of a human reader.
    entry["user_agent"] = str(entry.get("user_agent", ""))[:300]
    now = datetime.now(timezone.utc).timestamp()
    with database() as db:
        db.execute("INSERT OR IGNORE INTO events(id, created, payload) VALUES (?, ?, ?)", (entry["id"], now, json.dumps(entry)))
        retention = max(7, int(os.getenv("QUERY_RETENTION_DAYS", "90")))
        db.execute("DELETE FROM events WHERE created < ?", (now - retention * 86400,))
    return entry


def read_events(limit=20000, days=90):
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    with database() as db:
        rows = db.execute("SELECT payload FROM events WHERE created >= ? ORDER BY created DESC LIMIT ?", (cutoff, limit)).fetchall()
    return [json.loads(row[0]) for row in rows]


def logging_status():
    with database() as db:
        total, pending, failed = db.execute("SELECT COUNT(*), COALESCE(SUM(synced=0),0), COALESCE(SUM(synced=0 AND attempts>0),0) FROM events").fetchone()
        last = db.execute("SELECT error FROM events WHERE error IS NOT NULL ORDER BY created DESC LIMIT 1").fetchone()
    return {"stored": total, "pending": pending, "failed": failed, "last_error": last[0] if last else None,
            "sheets_configured": bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") and os.getenv("GOOGLE_SHEET_ID"))}


def flush_outbox(writer, limit=20, force=False):
    if not _flush_lock.acquire(blocking=False):
        return
    lease = None
    try:
        now = datetime.now(timezone.utc).timestamp()
        with database() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT value FROM metadata WHERE key='delivery_lease'").fetchone()
            if existing and json.loads(existing[0])["expires"] > now:
                return
            lease = str(uuid.uuid4())
            db.execute("INSERT OR REPLACE INTO metadata VALUES ('delivery_lease',?)", (json.dumps({"owner": lease, "expires": now + 600}),))
            rows = db.execute("SELECT * FROM events WHERE synced=0 AND (? OR next_attempt<=?) ORDER BY created LIMIT ?", (force, now, limit)).fetchall()
        for row in rows:
            with database() as db:
                db.execute("UPDATE metadata SET value=? WHERE key='delivery_lease'", (json.dumps({"owner": lease, "expires": datetime.now(timezone.utc).timestamp() + 600}),))
            try:
                writer(json.loads(row["payload"]))
            except Exception as exc:
                # Do not expose provider exception strings that may contain credentials or queries.
                error = f"{type(exc).__name__}: Sheets delivery failed; check credentials, sheet sharing and worksheet configuration."
                with database() as db:
                    db.execute("UPDATE events SET attempts=attempts+1,next_attempt=?,error=? WHERE id=?", (now + min(3600, 30 * 2 ** min(row["attempts"], 7)), error, row["id"]))
                break
            else:
                with database() as db:
                    db.execute("UPDATE events SET synced=1,error=NULL WHERE id=?", (row["id"],))
    finally:
        try:
            if lease:
                with database() as db:
                    current = db.execute("SELECT value FROM metadata WHERE key='delivery_lease'").fetchone()
                    if current and json.loads(current[0])["owner"] == lease:
                        db.execute("DELETE FROM metadata WHERE key='delivery_lease'")
        finally:
            _flush_lock.release()


def import_legacy_logs():
    """Import retained local history once; it has no trustworthy session grouping."""
    with database() as db:
        if db.execute("SELECT 1 FROM metadata WHERE key='legacy_imported'").fetchone():
            return
        path = get_settings().qa_log_file
        try:
            entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        except (ValueError, OSError):
            return
        for entry in entries:
            try:
                created = datetime.fromisoformat(entry["created_at"].replace("Z", "+00:00")).timestamp()
            except (KeyError, ValueError):
                continue
            if created < datetime.now(timezone.utc).timestamp() - 90 * 86400:
                continue
            entry = dict(entry, traffic_class="legacy", question=redact(entry.get("question")), answer=redact(entry.get("answer")))
            entry["page_url"] = clean_url(entry.get("page_url"))
            entry["referrer"] = clean_url(entry.get("referrer"))
            db.execute("INSERT OR IGNORE INTO events(id,created,payload,synced) VALUES (?,?,?,1)", (str(entry.get("id") or uuid.uuid4()), created, json.dumps(entry)))
        db.execute("INSERT INTO metadata VALUES ('legacy_imported','1')")
