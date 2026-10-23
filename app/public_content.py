"""Fail-closed boundary shared by public retrieval, generation and cards."""
from urllib.parse import urlsplit, unquote


def is_public_content(item: dict) -> bool:
    if str(item.get("visibility", "")).strip().lower() != "public":
        return False
    if str(item.get("surface_policy", "")).strip().lower() not in {"public", "show_source"}:
        return False
    if str(item.get("source_type", "")).lower() in {"private", "draft", "draft_html", "preview", "internal"}:
        return False
    url = str(item.get("url", "") or "").strip()
    decoded = unquote(url).lower()
    if any(x in decoded for x in ("preview", "hs_preview", "app.hubspot.com", "\\", "..")):
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    if parsed.username or parsed.password:
        return False
    if url.startswith("/magazines/") and not parsed.netloc:
        return True
    return parsed.scheme == "https" and parsed.hostname in {
        "www.greenbuildermedia.com", "greenbuildermedia.com", "www.youtube.com", "youtube.com", "youtu.be"
    }
