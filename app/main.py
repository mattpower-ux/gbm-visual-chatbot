from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import subprocess
import time
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, List

import gspread
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from google.oauth2.service_account import Credentials

from app.admin_ui import HTML as ADMIN_HTML
from app.config import get_settings
from app.corrections import (
    append_log,
    find_correction,
    load_corrections,
    load_logs,
    save_correction,
)
from app.generation import answer_question, summarize_private_usage
from app.models import (
    ChatRequest,
    ChatResponse,
    CorrectionCreate,
    CorrectionListResponse,
    LogListResponse,
    SourceItem,
)
from app.retrieval import search

settings = get_settings()

app = FastAPI(title="Green Builder Media Retrieval Bot", version="0.3.0")
security = HTTPBasic()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

TODAY = date.today()
DAILY_CRAWL_INTERVAL_SECONDS = 60 * 60 * 24
STARTUP_CRAWL_DELAY_SECONDS = 30
ENABLE_BACKGROUND_CRAWL = os.getenv("ENABLE_BACKGROUND_CRAWL", "false").strip().lower() in {
    "1", "true", "yes", "on",
}

crawl_lock = asyncio.Lock()
rebuild_task: asyncio.Task | None = None

FUTURE_EVENT_TERMS = [
    "coming up", "upcoming", "future conference", "future conferences",
    "future event", "future events", "next conference", "next conferences",
    "next event", "next events", "conference schedule", "event schedule",
    "calendar", "webinar", "webinars", "summit", "summits", "symposium",
    "symposiums", "conference", "conferences",
]

MONTH_PATTERN = (
    "January|February|March|April|May|June|July|August|September|October|November|December|"
    "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)

DATE_PATTERNS = [
    rf"\b({MONTH_PATTERN})\s+\d{{1,2}},\s+\d{{4}}\b",
    rf"\b({MONTH_PATTERN})\s+\d{{1,2}}\s*[-â€“â€”]\s*\d{{1,2}},\s+\d{{4}}\b",
    rf"\b({MONTH_PATTERN})\s+\d{{1,2}}\b",
    rf"\b({MONTH_PATTERN})\s+\d{{1,2}}\s*[-â€“â€”]\s*\d{{1,2}}\b",
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{1,2}/\d{1,2}/\d{4}\b",
]


def admin_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    expected_username = settings.admin_username.encode("utf-8")
    expected_password = settings.admin_password.encode("utf-8")
    given_username = credentials.username.encode("utf-8")
    given_password = credentials.password.encode("utf-8")
    if not (
        secrets.compare_digest(given_username, expected_username)
        and secrets.compare_digest(given_password, expected_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def get_google_sheet():
    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    if not raw_json:
        raise RuntimeError("Missing GOOGLE_SERVICE_ACCOUNT_JSON environment variable.")
    if not sheet_id:
        raise RuntimeError("Missing GOOGLE_SHEET_ID environment variable.")

    service_account_info = json.loads(raw_json)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=scopes,
    )
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(sheet_id)
    return spreadsheet.sheet1


def ensure_sheet_header(worksheet) -> None:
    expected_header = [
        "timestamp_utc", "session_id", "page_url", "referrer", "user_agent",
        "event_query", "question", "answer", "sources_json",
        "private_archive_used", "attribution_note", "correction_applied",
        "correction_id",
    ]
    existing_header = worksheet.row_values(1)
    if existing_header != expected_header:
        worksheet.update("A1:M1", [expected_header])


def log_to_google_sheet(payload: dict) -> None:
    worksheet = get_google_sheet()
    ensure_sheet_header(worksheet)
    row = [
        datetime.utcnow().isoformat(),
        payload.get("session_id", "") or "",
        payload.get("page_url", "") or "",
        payload.get("referrer", "") or "",
        payload.get("user_agent", "") or "",
        str(payload.get("event_query", False)),
        payload.get("question", "") or "",
        payload.get("answer", "") or "",
        json.dumps(payload.get("public_sources", []), ensure_ascii=False),
        str(payload.get("private_archive_used", False)),
        payload.get("attribution_note", "") or "",
        str(payload.get("correction_applied", False)),
        payload.get("correction_id", "") or "",
    ]
    worksheet.append_row(row, value_input_option="RAW")


def append_log_everywhere(payload: dict) -> None:
    append_log(payload)
    try:
        log_to_google_sheet(payload)
    except Exception as exc:
        print(f"Google Sheets logging failed: {exc}")


async def run_crawl_and_reindex_once() -> None:
    if crawl_lock.locked():
        print("Scheduled crawl skipped because another crawl is already running.")
        return

    async with crawl_lock:
        print("Starting scheduled crawl + index rebuild...")
        from app.crawl_greenbuilder import main as crawl_main
        from app.build_index import main as build_main
        await crawl_main()
        build_main()
        print("Scheduled crawl + index rebuild completed.")


async def run_daily_crawl_loop() -> None:
    await asyncio.sleep(STARTUP_CRAWL_DELAY_SECONDS)
    while True:
        try:
            await run_crawl_and_reindex_once()
        except Exception as exc:
            print(f"Scheduled crawl + index rebuild failed: {exc}")
        await asyncio.sleep(DAILY_CRAWL_INTERVAL_SECONDS)


async def run_rebuild_once() -> None:
    from app.build_index import main as build_main
    await asyncio.to_thread(build_main)


@app.on_event("startup")
async def startup_event() -> None:
    if ENABLE_BACKGROUND_CRAWL:
        asyncio.create_task(run_daily_crawl_loop())
    else:
        print("Background crawl loop disabled by ENABLE_BACKGROUND_CRAWL.")


def is_future_event_query(question: str) -> bool:
    q = (question or "").lower()
    return any(term in q for term in FUTURE_EVENT_TERMS)


def parse_published_year(published_at: str | None) -> int | None:
    if not published_at:
        return None
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        return dt.year
    except Exception:
        pass
    match = re.search(r"\b(20\d{2}|19\d{2})\b", published_at)
    if match:
        return int(match.group(1))
    return None


def parse_single_event_date(raw: str, default_year: int | None = None) -> date | None:
    if not raw:
        return None
    raw = raw.strip()
    raw = re.sub(
        r"(\b[A-Za-z]+)\s+(\d{1,2})\s*[-â€“â€”]\s*\d{1,2},\s+(\d{4})",
        r"\1 \2, \3",
        raw,
    )
    raw = re.sub(
        r"(\b[A-Za-z]+)\s+(\d{1,2})\s*[-â€“â€”]\s*\d{1,2}",
        r"\1 \2",
        raw,
    )
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    if default_year is not None:
        for fmt in ("%B %d", "%b %d"):
            try:
                partial = datetime.strptime(raw, fmt)
                return date(default_year, partial.month, partial.day)
            except ValueError:
                pass
    return None


def extract_all_event_dates_from_text(text: str, default_year: int | None = None) -> list[date]:
    if not text:
        return []
    found_dates: list[date] = []
    for pattern in DATE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            parsed = parse_single_event_date(match.group(0), default_year=default_year)
            if parsed:
                found_dates.append(parsed)
    unique_dates: list[date] = []
    seen = set()
    for d in found_dates:
        if d not in seen:
            unique_dates.append(d)
            seen.add(d)
    return unique_dates


def extract_future_event_dates(chunk: dict[str, Any]) -> list[date]:
    future_dates: list[date] = []
    published_year = parse_published_year(chunk.get("published_at")) or TODAY.year
    for field in ("event_date", "event_start_date"):
        value = chunk.get(field)
        if isinstance(value, str):
            parsed = parse_single_event_date(value, default_year=published_year)
            if parsed and parsed >= TODAY:
                future_dates.append(parsed)
    for field in ("title", "text"):
        value = chunk.get(field)
        if isinstance(value, str):
            for parsed in extract_all_event_dates_from_text(value, default_year=published_year):
                if parsed >= TODAY:
                    future_dates.append(parsed)
    unique_dates: list[date] = []
    seen = set()
    for d in future_dates:
        if d not in seen:
            unique_dates.append(d)
            seen.add(d)
    return sorted(unique_dates)


def extract_best_event_date(chunk: dict[str, Any]) -> date | None:
    future_dates = extract_future_event_dates(chunk)
    if future_dates:
        return future_dates[0]
    published_at = chunk.get("published_at")
    if isinstance(published_at, str):
        return parse_single_event_date(published_at)
    return None


def filter_to_future_event_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    future_chunks: list[dict[str, Any]] = []
    for chunk in chunks:
        future_dates = extract_future_event_dates(chunk)
        if future_dates:
            enriched = dict(chunk)
            enriched["_next_future_event_date"] = future_dates[0].isoformat()
            future_chunks.append(enriched)
    return sorted(
        future_chunks,
        key=lambda c: c.get("_next_future_event_date", "9999-12-31"),
    )


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/widget.js")
def widget() -> FileResponse:
    root = Path(__file__).resolve().parents[1]
    widget_path = root / "widget" / "embed.js"
    return FileResponse(widget_path, media_type="application/javascript")



def _first_paragraph(text: str) -> str:
    """Return a compact first paragraph for visual mode."""
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if not parts:
        return text.strip()
    first = parts[0]
    # Keep the visual opener short enough for card-style UI.
    if len(first) > 650:
        sentence_match = re.match(r"^(.{200,650}?[.!?])\s", first + " ")
        if sentence_match:
            return sentence_match.group(1).strip()
        return first[:650].rsplit(" ", 1)[0].strip() + "..."
    return first


def _source_to_dict(source: Any) -> dict[str, Any]:
    """Convert a SourceItem or dict to a plain JSON-safe dict."""
    if hasattr(source, "model_dump"):
        return source.model_dump()
    if isinstance(source, dict):
        return dict(source)
    return {}


def _asset_safe_name(value: str) -> str:
    """Create a predictable filename stem for generated thumbnails/covers."""
    value = Path(value or "source").name
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return value or "source"


def _thumb_for_url(url: str) -> str:
    """Return the local generated thumbnail path for a public blog/article URL."""
    from urllib.parse import urlparse

    path = urlparse(str(url or "")).path.strip("/")
    slug = Path(path).name or "article"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", slug).strip("-") or "article"
    return f"/assets/thumbs/{slug}.jpg"




def _query_years(text: str) -> set[str]:
    """Return years explicitly mentioned in the user's question."""
    return set(re.findall(r"\b(20\d{2}|19\d{2})\b", text or ""))


def _chunk_years(chunk: dict[str, Any]) -> set[str]:
    """Return issue/content years known for a chunk."""
    years: set[str] = set()
    for key in ("pdf_year", "published_at", "pdf_filename", "source_name", "title", "url"):
        value = chunk.get(key)
        if value is not None:
            years.update(re.findall(r"\b(20\d{2}|19\d{2})\b", str(value)))
    return years


def _magazine_cover_for_url(url: str, chunk: dict[str, Any] | None = None) -> str:
    """Return the generated magazine cover path for a PDF URL/chunk."""
    from urllib.parse import unquote

    chunk = chunk or {}
    explicit = chunk.get("cover_url") or chunk.get("thumbnail_url") or chunk.get("image") or chunk.get("thumbnail")
    if explicit:
        return str(explicit)

    filename = str(chunk.get("pdf_filename") or "").strip()
    if not filename and url:
        filename = Path(unquote(str(url).split("/magazines/", 1)[-1])).name
    if not filename:
        return "/assets/covers/fallback-magazine.jpg"

    encoded_name = filename.replace(" ", "%20")
    stem = Path(encoded_name).stem
    return f"/assets/covers/{stem}.jpg"

def _find_chunk_for_source(source: dict[str, Any], chunks: list[dict[str, Any]]) -> dict[str, Any]:
    url = str(source.get("url", ""))
    title = str(source.get("title", ""))
    pdf_filename = str(source.get("pdf_filename", ""))

    for chunk in chunks:
        chunk_url = str(chunk.get("url", ""))
        chunk_pdf = str(chunk.get("pdf_filename", ""))
        if url and chunk_url == url:
            return chunk
        if pdf_filename and chunk_pdf == pdf_filename:
            return chunk

    for chunk in chunks:
        if title and title in str(chunk.get("title", "")):
            return chunk
    return {}


def _is_magazine_chunk(chunk: dict[str, Any]) -> bool:
    url = str(chunk.get("url", ""))
    source_type = str(chunk.get("source_type", ""))
    pdf_filename = str(chunk.get("pdf_filename", ""))
    return (
        url.startswith("/magazines/")
        or "/magazines/" in url
        or source_type in {"pdf", "magazine"}
        or pdf_filename.lower().endswith(".pdf")
    )


def _is_public_chunk(chunk: dict[str, Any]) -> bool:
    """Surface public GBM URLs and magazine PDFs; keep true private drafts hidden."""
    url = str(chunk.get("url", "") or "").strip()

    if (
        url.startswith("https://www.greenbuildermedia.com/")
        or url.startswith("https://greenbuildermedia.com/")
        or url.startswith("/magazines/")
        or "/magazines/" in url
    ):
        return True

    visibility = str(chunk.get("visibility", "public") or "public").strip().lower()
    return visibility not in {"private", "internal", "draft", "hidden", "false", "0"}




def _detect_source_type_from_url(url: str) -> str:
    """Classify public content for source caps and card labeling."""
    u = str(url or "").strip().lower()

    if not u:
        return "webpage"

    if "/magazines/" in u or u.endswith(".pdf") or ".pdf" in u:
        return "magazine"

    if "/blog/" in u:
        return "blog"

    if any(pattern in u for pattern in [
        "/lp/",
        "/landing-pages/",
        "/landing-page/",
        "/resources/",
        "/resource/",
        "/ebooks/",
        "/ebook/",
        "/webinars/",
        "/webinar/",
        "/offers/",
        "/offer/",
        "/events/",
        "/event/",
    ]):
        return "webpage"

    return "webpage"


def _detect_source_type(chunk: dict[str, Any]) -> str:
    """Prefer stored source_type, but safely infer it when older chunks lack metadata."""
    explicit = str(chunk.get("source_type", "") or "").strip().lower()
    if explicit in {"blog", "webpage", "landing_page", "landing-page", "magazine", "pdf"}:
        if explicit in {"landing_page", "landing-page"}:
            return "webpage"
        if explicit == "pdf":
            return "magazine"
        return explicit

    return _detect_source_type_from_url(str(chunk.get("url", "") or ""))


def _result_rank_score(chunk: dict[str, Any]) -> float:
    """Normalize likely score fields so lower-distance and higher-score results sort sensibly."""
    for key in ("score", "similarity", "relevance"):
        value = chunk.get(key)
        if isinstance(value, (int, float)):
            # Higher is better for these conventional score fields, so invert for ascending sort.
            return -float(value)

    for key in ("_distance", "distance"):
        value = chunk.get(key)
        if isinstance(value, (int, float)):
            # Lower is better for vector distances.
            return float(value)

    return 0.0


def _parse_datetime_for_ranking(value: Any) -> datetime | None:
    """Parse common date strings for freshness ranking without failing chat."""
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        # Make aware datetimes naive UTC-ish for safe subtraction from datetime.utcnow().
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        pass
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d")
    except Exception:
        return None


def _apply_smart_ranking(chunks: list[dict[str, Any]], question: str = "") -> list[dict[str, Any]]:
    """Promote strategic, fresh, visual content before source caps are applied.

    This keeps the vector search as the starting point, then gently boosts:
    - HubSpot / landing / resource / webinar / offer pages
    - recent content
    - pages that have real crawler images
    """
    ranked_chunks: list[dict[str, Any]] = []
    requested_years = _query_years(question)

    for index, chunk in enumerate(chunks or []):
        ranked = dict(chunk)
        source_type = _detect_source_type(ranked)
        url = str(ranked.get("url", "") or "").lower()
        chunk_years = _chunk_years(ranked)

        # Base score: lower is better because _result_rank_score normalizes
        # high-similarity scores into negative values and vector distances into positive values.
        rank_score = _result_rank_score(ranked)

        # Multipliers below reduce rank_score for boosted items, moving them upward in ascending sort.
        multiplier = 1.0

        # Strategic source boosts: let landing/resource/webinar/offer pages compete with blogs.
        if any(pattern in url for pattern in [
            "/lp/", "/landing", "/resources/", "/resource/", "/ebooks/", "/ebook/",
            "/webinars/", "/webinar/", "/offers/", "/offer/", "/events/", "/event/",
            "/guides/", "/reports/",
        ]):
            multiplier *= 0.82
        elif source_type == "blog":
            multiplier *= 0.95

        # Year-aware ranking for magazine questions such as "2020 coverage".
        # This fixes the problem where one older PDF issue can dominate answers
        # even when the user explicitly asks for another year.
        if requested_years:
            if chunk_years & requested_years:
                multiplier *= 0.45
            elif source_type == "magazine":
                multiplier *= 2.8

        # Freshness boost.
        published = _parse_datetime_for_ranking(ranked.get("published_at"))
        if published:
            age_days = max((datetime.utcnow() - published).days, 0)
            if age_days <= 30:
                multiplier *= 0.84
            elif age_days <= 90:
                multiplier *= 0.92
            elif age_days <= 365:
                multiplier *= 0.97

        # Visual-content boost for better card results.
        if (
            ranked.get("image")
            or ranked.get("og_image")
            or ranked.get("featured_image")
            or ranked.get("thumbnail")
            or ranked.get("thumbnail_url")
        ):
            multiplier *= 0.92

        ranked["_smart_rank"] = rank_score * multiplier
        ranked["_smart_rank_original"] = index
        ranked_chunks.append(ranked)

    return sorted(
        ranked_chunks,
        key=lambda c: (c.get("_smart_rank", 0.0), c.get("_smart_rank_original", 0)),
    )


def _apply_source_weights_and_limits(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Weight and cap retrieval results before answer generation and source display.

    Caps:
    - max 3 blog URLs
    - max 3 webpage / landing-page URLs
    - max 3 magazine/PDF URLs retained for answer context

    This function deduplicates by URL, preserves public/private safety checks elsewhere,
    and does not require rebuilding old chunks because source_type can be inferred from URL.
    """
    source_weights = {
        "blog": 1.00,
        "webpage": 1.10,
        "magazine": 0.95,
    }
    source_caps = {
        "blog": 3,
        "webpage": 3,
        "magazine": 3,
    }

    enriched: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks or []):
        source_type = _detect_source_type(chunk)
        weight = source_weights.get(source_type, 1.0)
        ranked = dict(chunk)
        ranked["_detected_source_type"] = source_type
        base_rank = float(chunk.get("_smart_rank", _result_rank_score(chunk)))
        ranked["_weighted_rank"] = base_rank / weight
        ranked["_original_rank"] = index
        enriched.append(ranked)

    enriched.sort(key=lambda c: (c.get("_weighted_rank", 0.0), c.get("_original_rank", 0)))

    limited: list[dict[str, Any]] = []
    counts = {"blog": 0, "webpage": 0, "magazine": 0}
    seen_urls: set[str] = set()

    for chunk in enriched:
        url = str(chunk.get("url", "") or "").strip()
        source_type = str(chunk.get("_detected_source_type") or _detect_source_type(chunk))
        dedupe_key = url or f"chunk-{chunk.get('_original_rank', len(limited))}"

        if dedupe_key in seen_urls:
            continue

        cap = source_caps.get(source_type, 3)
        if counts.get(source_type, 0) >= cap:
            continue

        limited.append(chunk)
        seen_urls.add(dedupe_key)
        counts[source_type] = counts.get(source_type, 0) + 1

    return limited


def _thumbnail_from_chunk_or_source(chunk: dict[str, Any], source: dict[str, Any], url: str) -> str:
    """Pick the best real thumbnail for visual cards.

    Priority is intentionally crawler-first: use the real image fields saved by
    crawl_greenbuilder.py before falling back to generated local thumb paths.
    """
    if _is_magazine_chunk(chunk) or _detect_source_type_from_url(url) == "magazine":
        return _magazine_cover_for_url(url, chunk)

    image = (
        chunk.get("image")
        or chunk.get("og_image")
        or chunk.get("featured_image")
        or chunk.get("thumbnail")
        or chunk.get("thumbnail_url")
        or source.get("image")
        or source.get("og_image")
        or source.get("featured_image")
        or source.get("thumbnail")
        or source.get("thumbnail_url")
        or ""
    )
    if image:
        return str(image)

    return _thumb_for_url(url) if url else "/assets/thumbs/fallback-article.jpg"


def _source_public_payload(source: Any, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Return source metadata for logs/admin UI without changing the SourceItem model.

    The admin console reads `public_sources` from logs. SourceItem intentionally
    remains conservative, so this function enriches the serialized source with
    crawler image fields and normalized source_type for display only.
    """
    source_dict = _source_to_dict(source)
    chunk = _find_chunk_for_source(source_dict, chunks)
    url = str(source_dict.get("url", "") or chunk.get("url", ""))
    source_type = _detect_source_type(chunk) if chunk else _detect_source_type_from_url(url)
    image = _thumbnail_from_chunk_or_source(chunk, source_dict, url)

    source_dict["source_type"] = source_type
    source_dict["type"] = source_type
    source_dict["image"] = image
    source_dict["thumbnail"] = image
    source_dict["thumbnail_url"] = image

    for key in ("og_image", "featured_image", "category", "page", "pdf_filename", "source_name", "pdf_year", "pdf_issue", "cover_url"):
        if key not in source_dict and chunk.get(key) is not None:
            source_dict[key] = chunk.get(key)

    return source_dict


def _public_sources_payload(sources: list[Any], chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_source_public_payload(source, chunks) for source in sources]


def _magazine_source_from_chunk(chunk: dict[str, Any]) -> SourceItem | None:
    """Build a public SourceItem from a retrieved PDF chunk.

    This is a fallback safety net: even if a PDF chunk was missed by the normal
    source-building pass, magazine/PDF chunks should still be allowed to surface
    because they are public archive material, not private draft material.
    """
    if not _is_magazine_chunk(chunk):
        return None

    visibility = chunk.get("visibility", "public")
    if visibility != "public":
        return None

    filename = str(chunk.get("pdf_filename", "")).strip()
    url = str(chunk.get("url", "")).strip()

    if not url and filename:
        url = f"/magazines/{filename}"
    if not url:
        return None

    clean_title = (
        chunk.get("source_name")
        or chunk.get("title")
        or chunk.get("pdf_filename")
        or "Green Builder Magazine Archive"
    )

    page = chunk.get("page")
    if page is not None:
        try:
            clean_title = f"{clean_title} (PDF, p. {int(page)})"
        except Exception:
            clean_title = f"{clean_title} (PDF)"
    elif not str(clean_title).lower().endswith("(pdf)"):
        clean_title = f"{clean_title} (PDF)"

    return SourceItem(
        title=str(clean_title),
        url=url,
        published_at=chunk.get("published_at"),
        excerpt=str(chunk.get("text", ""))[:240].strip(),
        score=float(chunk.get("score", 0.0)),
        visibility="public",
        attribution_label="Magazine archive",
        surface_policy="show_source",
    )


def _build_visual_cards(sources: list[Any], chunks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build visual article cards and magazine cards from public sources."""
    cards: list[dict[str, Any]] = []
    magazines: list[dict[str, Any]] = []

    for raw_source in sources:
        source = _source_to_dict(raw_source)
        url = str(source.get("url", ""))
        title = source.get("title") or "Green Builder Media source"
        excerpt = source.get("excerpt") or ""
        chunk = _find_chunk_for_source(source, chunks)
        image = _thumbnail_from_chunk_or_source(chunk, source, url)

        if url.startswith("/magazines/") or "/magazines/" in url or str(source.get("source_type", "")) in {"pdf", "magazine"}:
            cover = _magazine_cover_for_url(url, chunk)
            magazines.append(
                {
                    "title": title,
                    "url": url,
                    "cover": cover,
                    "image": cover,
                    "thumbnail_url": cover,
                    "issue": chunk.get("source_name") or source.get("attribution_label") or "Magazine archive",
                    "page": chunk.get("page"),
                    "type": "pdf",
                    "source": "Green Builder Magazine",
                    "excerpt": excerpt,
                }
            )
        else:
            source_type = _detect_source_type(chunk) if chunk else _detect_source_type_from_url(url)
            cards.append(
                {
                    "title": title,
                    "url": url,
                    "source": source.get("attribution_label") or "Green Builder",
                    "category": chunk.get("category") or source.get("attribution_label") or "Article",
                    # Frontend uses `image`; `thumbnail_url` is included for compatibility
                    # with any newer card renderer that reads thumbnail-specific fields.
                    "image": image,
                    "thumbnail_url": image,
                    "type": source_type,
                    "excerpt": excerpt,
                }
            )

    return cards[:6], magazines[:3]


def _build_key_insights(answer: str) -> list[dict[str, str]]:
    """Create lightweight insight cards from the generated answer."""
    text = answer or ""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    insights: list[dict[str, str]] = []

    titles = ["Key Insights", "Practical implication", "Related Facts"]
    icons = ["lightbulb", "check-circle", "info"]

    for idx, paragraph in enumerate(paragraphs[:3]):
        short = paragraph
        if len(short) > 260:
            match = re.match(r"^(.{120,260}?[.!?])\s", short + " ")
            short = match.group(1).strip() if match else short[:260].rsplit(" ", 1)[0].strip() + "..."
        insights.append({"title": titles[idx], "text": short, "icon": icons[idx]})

    if not insights and text:
        insights.append({"title": "Key Insights", "text": _first_paragraph(text), "icon": "lightbulb"})

    return insights


def _chat_payload(response: ChatResponse, chunks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return the backward-compatible answer plus visual-mode fields."""
    chunks = chunks or []
    base = response.model_dump()
    answer = base.get("answer", "") or ""
    sources = base.get("sources", []) or []
    cards, magazines = _build_visual_cards(sources, chunks)

    base.update(
        {
            "visual_summary": _first_paragraph(answer),
            "key_insights": _build_key_insights(answer),
            "cards": cards,
            "magazines": magazines,
            "text_only_answer": answer,
            "ui_mode_default": "visual",
        }
    )
    return base


@app.post("/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    correction = find_correction(req.question)
    if correction:
        response = ChatResponse(
            answer=correction["answer_override"],
            sources=[],
            corrected_by_editor=True,
            correction_note=correction.get("editor_note")
            or f"Editor override by {correction.get('editor_name') or 'editor'}",
        )
        append_log_everywhere(
            {
                "question": req.question,
                "session_id": req.session_id,
                "page_url": req.page_url,
                "referrer": req.referrer,
                "user_agent": req.user_agent,
                "event_query": is_future_event_query(req.question),
                "answer": response.answer,
                "public_sources": [],
                "private_archive_used": False,
                "correction_applied": True,
                "correction_id": correction.get("id"),
            }
        )
        return _chat_payload(response)

    try:
        chunks = search(req.question)
        chunks = _apply_smart_ranking(chunks, req.question)
        chunks = _apply_source_weights_and_limits(chunks)
    except Exception as exc:
        error_text = str(exc)
        if "LanceDB table 'greenbuilder_chunks' not found" in error_text:
            response = ChatResponse(
                answer=(
                    "The chatbot index is still being prepared right now. "
                    "Please try again in a few minutes."
                ),
                sources=[],
            )
            append_log_everywhere(
                {
                    "question": req.question,
                    "session_id": req.session_id,
                    "page_url": req.page_url,
                    "referrer": req.referrer,
                    "user_agent": req.user_agent,
                    "event_query": is_future_event_query(req.question),
                    "answer": response.answer,
                    "public_sources": [],
                    "private_archive_used": False,
                }
            )
            return _chat_payload(response)
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc

    future_query = is_future_event_query(req.question)
    if future_query:
        chunks = filter_to_future_event_chunks(chunks)
        if not chunks:
            response = ChatResponse(
                answer=(
                    "Iâ€™m not seeing any confirmed future conferences in the current Green Builder Media excerpts. "
                    "The available event-related content appears to be past or undated, so I canâ€™t verify an upcoming conference from the retrieved material."
                ),
                sources=[],
            )
            append_log_everywhere(
                {
                    "question": req.question,
                    "session_id": req.session_id,
                    "page_url": req.page_url,
                    "referrer": req.referrer,
                    "user_agent": req.user_agent,
                    "event_query": future_query,
                    "answer": response.answer,
                    "public_sources": [],
                    "private_archive_used": False,
                }
            )
            return _chat_payload(response)

    if not chunks:
        response = ChatResponse(
            answer="I couldn't find relevant Green Builder Media content for that question.",
            sources=[],
        )
        append_log_everywhere(
            {
                "question": req.question,
                "session_id": req.session_id,
                "page_url": req.page_url,
                "referrer": req.referrer,
                "user_agent": req.user_agent,
                "event_query": future_query,
                "answer": response.answer,
                "public_sources": [],
                "private_archive_used": False,
            }
        )
        return _chat_payload(response)

    try:
        answer = answer_question(req.question, chunks)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc

    private_used, attribution_note = summarize_private_usage(chunks)

    # Build clean, deduplicated public source list.
    # Blogs are deduplicated by URL.
    # Magazine PDFs are deduplicated by PDF URL so each issue appears only once.
    seen = set()
    sources = []
    for chunk in chunks:
        if not _is_public_chunk(chunk):
            continue
        visibility = "public"

        url = chunk.get("url")
        if not url:
            continue

        if url in seen:
            continue
        seen.add(url)

        is_magazine = _is_magazine_chunk(chunk)

        if is_magazine:
            clean_title = (
                chunk.get("source_name")
                or chunk.get("title")
                or chunk.get("pdf_filename")
                or "Green Builder Magazine Archive"
            )

            page = chunk.get("page")
            if page is not None:
                try:
                    clean_title = f"{clean_title} (PDF, p. {int(page)})"
                except Exception:
                    clean_title = f"{clean_title} (PDF)"
            elif not clean_title.lower().endswith("(pdf)"):
                clean_title = f"{clean_title} (PDF)"

            attribution_label = "Magazine archive"
        else:
            clean_title = chunk.get("title", "Untitled")
            attribution_label = chunk.get("attribution_label")

        sources.append(
            SourceItem(
                title=clean_title,
                url=url,
                published_at=chunk.get("published_at"),
                excerpt=chunk.get("text", "")[:240].strip(),
                score=float(chunk.get("score", 0.0)),
                visibility=visibility,
                attribution_label=attribution_label,
                surface_policy=chunk.get("surface_policy"),
            )
        )

    # Ensure magazine PDF sources appear if magazine chunks were used.
    # This fallback matters because PDFs are public archive content and must not
    # be hidden like private draft HTML, even when private archive material also
    # influenced the answer.
    blog_sources = [s for s in sources if _detect_source_type_from_url(s.url) == "blog"]
    web_sources = [s for s in sources if _detect_source_type_from_url(s.url) == "webpage"]
    pdf_sources = [s for s in sources if _detect_source_type_from_url(s.url) == "magazine"]

    if not pdf_sources:
        seen_pdf_urls = {s.url for s in pdf_sources}
        for chunk in chunks:
            pdf_source = _magazine_source_from_chunk(chunk)
            if pdf_source and pdf_source.url not in seen_pdf_urls:
                pdf_sources.append(pdf_source)
                seen_pdf_urls.add(pdf_source.url)
            if len(pdf_sources) >= 3:
                break

    # Final public source caps:
    # - no more than 3 blog citations
    # - no more than 3 webpage / HubSpot landing-page links
    # - keep one magazine/PDF citation when relevant
    final_sources = []
    final_sources.extend(blog_sources[:3])
    final_sources.extend(web_sources[:3])

    if pdf_sources:
        final_sources.append(pdf_sources[0])

    if not final_sources:
        final_sources = sources[:7]

    response = ChatResponse(
        answer=answer,
        sources=final_sources[:7],
        private_archive_used=private_used,
        attribution_note=attribution_note,
    )

    append_log_everywhere(
        {
            "question": req.question,
            "session_id": req.session_id,
            "page_url": req.page_url,
            "referrer": req.referrer,
            "user_agent": req.user_agent,
            "event_query": future_query,
            "answer": response.answer,
            "public_sources": _public_sources_payload(response.sources, chunks),
            "private_archive_used": private_used,
            "attribution_note": attribution_note,
        }
    )
    return _chat_payload(response, chunks)


@app.get("/admin", response_class=HTMLResponse)
def admin_page(_: str = Depends(admin_auth)) -> HTMLResponse:
    return HTMLResponse(ADMIN_HTML)


@app.get("/api/admin/logs", response_model=LogListResponse)
def admin_logs(_: str = Depends(admin_auth)) -> LogListResponse:
    return LogListResponse(logs=load_logs())


@app.get("/api/admin/corrections", response_model=CorrectionListResponse)
def admin_corrections(_: str = Depends(admin_auth)) -> CorrectionListResponse:
    return CorrectionListResponse(corrections=load_corrections())


@app.post("/api/admin/corrections")
def admin_create_correction(
    payload: CorrectionCreate, username: str = Depends(admin_auth)
) -> dict:
    saved = save_correction(
        {**payload.model_dump(), "editor_name": payload.editor_name or username}
    )
    return {"ok": True, "message": "Correction saved", "correction": saved}


@app.post("/api/admin/rebuild-index")
async def admin_rebuild_index(_: str = Depends(admin_auth)) -> dict:
    global rebuild_task

    if rebuild_task and not rebuild_task.done():
        return {"ok": True, "message": "Index rebuild already running"}

    rebuild_task = asyncio.create_task(run_rebuild_once())
    return {"ok": True, "message": "Index rebuild started"}


@app.get("/api/admin/rebuild-index-status")
def admin_rebuild_index_status(_: str = Depends(admin_auth)) -> dict:
    global rebuild_task

    if rebuild_task is None:
        return {"status": "idle"}

    if rebuild_task.done():
        exc = rebuild_task.exception()
        if exc:
            return {"status": "failed", "error": str(exc)}
        return {"status": "completed"}

    return {"status": "running"}


@app.get("/")
def root() -> Response:
    return Response(
        "Green Builder Media Retrieval Bot is running.",
        media_type="text/plain",
    )


# === Safe Magazine PDF Upload + Controlled Ingest Endpoints ===
from fastapi import UploadFile, File
from fastapi.staticfiles import StaticFiles
import shutil

MAGAZINE_DIR = Path("/data/magazines")
MAGAZINE_DIR.mkdir(parents=True, exist_ok=True)

# Safe upload folders. Uploads land in pdf_inbox only.
# They do NOT automatically ingest or touch the live chatbot index.
PDF_INBOX_DIR = Path("/data/pdf_inbox")
PDF_PROCESSING_DIR = Path("/data/pdf_processing")
PDF_DONE_DIR = Path("/data/pdf_done")
PDF_FAILED_DIR = Path("/data/pdf_failed")

for _folder in [PDF_INBOX_DIR, PDF_PROCESSING_DIR, PDF_DONE_DIR, PDF_FAILED_DIR]:
    _folder.mkdir(parents=True, exist_ok=True)

MAGAZINE_INGEST_STATUS_FILE = Path("/data/magazine_ingest_status.json")
PDF_INGEST_LOCK_FILE = Path("/data/pdf_ingest.lock")
PDF_INGEST_SKIP_FILE = Path("/data/pdf_ingest_skip.flag")
PDF_INGEST_PAUSE_FILE = Path("/data/pdf_ingest_pause.flag")
PDF_INGEST_DEFAULT_PAUSE_SECONDS = int(os.getenv("PDF_INGEST_PAUSE_SECONDS", "20"))
CURRENT_PDF_PROCESS: subprocess.Popen | None = None


def require_data_disk_space(min_free_gb: float = 1.0) -> None:
    total, used, free = shutil.disk_usage("/data")
    min_free_bytes = int(min_free_gb * 1024 * 1024 * 1024)

    if free < min_free_bytes:
        raise HTTPException(
            status_code=507,
            detail=(
                f"Not enough free space on /data. "
                f"Need at least {min_free_gb} GB free before accepting or ingesting PDF uploads."
            ),
        )


def write_magazine_ingest_status(payload: dict) -> None:
    MAGAZINE_INGEST_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {**payload, "updated_at_utc": datetime.utcnow().isoformat()}
    MAGAZINE_INGEST_STATUS_FILE.write_text(json.dumps(payload, indent=2))


def read_magazine_ingest_status() -> dict:
    if not MAGAZINE_INGEST_STATUS_FILE.exists():
        return {
            "status": "idle",
            "message": "Safe upload mode is ON. PDFs are stored in /data/pdf_inbox. Auto-ingest is OFF.",
            "current_file": "",
            "processed": 0,
            "total": 0,
            "succeeded": [],
            "skipped": [],
            "failed": [],
            "recovered": [],
        }
    try:
        return json.loads(MAGAZINE_INGEST_STATUS_FILE.read_text())
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Could not read ingest status: {exc}",
            "current_file": "",
            "processed": 0,
            "total": 0,
            "succeeded": [],
            "skipped": [],
            "failed": [],
            "recovered": [],
        }


def pdf_file_info(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
        size_mb = round(stat.st_size / (1024 * 1024), 2)
        modified_at_utc = datetime.utcfromtimestamp(stat.st_mtime).isoformat()
    except Exception:
        size_mb = 0
        modified_at_utc = ""
    return {"name": path.name, "size_mb": size_mb, "modified_at_utc": modified_at_utc}


def list_pdf_folder(folder: Path, pattern: str = "*.pdf") -> list[dict[str, Any]]:
    return [pdf_file_info(path) for path in sorted(folder.glob(pattern))]


def recover_interrupted_processing_files() -> list[dict[str, str]]:
    """Move PDFs left in /data/pdf_processing back to inbox so the next ingest can resume."""
    recovered: list[dict[str, str]] = []
    for path in sorted(PDF_PROCESSING_DIR.glob("*.pdf")):
        target = PDF_INBOX_DIR / path.name
        try:
            if target.exists():
                target = PDF_INBOX_DIR / f"recovered-{int(time.time())}-{path.name}"
            shutil.move(str(path), str(target))
            recovered.append({"file": path.name, "moved_to": str(target)})
        except Exception as exc:
            recovered.append({"file": path.name, "error": str(exc)})
    return recovered



def pdf_ingest_paused() -> bool:
    return PDF_INGEST_PAUSE_FILE.exists()


def pdf_ingest_skip_requested() -> bool:
    return PDF_INGEST_SKIP_FILE.exists()


def clear_pdf_ingest_skip_request() -> None:
    PDF_INGEST_SKIP_FILE.unlink(missing_ok=True)


def wait_for_pdf_ingest_resume(status_payload: dict) -> None:
    """Hold between files or before a new file when the admin UI has paused ingest."""
    while pdf_ingest_paused():
        write_magazine_ingest_status({
            **status_payload,
            "status": "paused",
            "message": "PDF ingest paused. Click Resume PDF Ingest to continue.",
            "paused": True,
            "skip_requested": pdf_ingest_skip_requested(),
        })
        time.sleep(2)


def pause_between_pdfs(seconds: int, status_payload: dict) -> None:
    """Pause in small ticks so pause/skip controls remain responsive."""
    for remaining in range(max(0, int(seconds)), 0, -1):
        wait_for_pdf_ingest_resume(status_payload)
        write_magazine_ingest_status({
            **status_payload,
            "status": "running",
            "message": f"Pausing {remaining} seconds before next PDF.",
            "pause_remaining_seconds": remaining,
            "paused": False,
            "skip_requested": pdf_ingest_skip_requested(),
        })
        time.sleep(1)


def run_pdf_inbox_ingest(pause_seconds: int = PDF_INGEST_DEFAULT_PAUSE_SECONDS) -> None:
    """Process PDFs from /data/pdf_inbox one at a time with admin pause/skip controls."""
    global CURRENT_PDF_PROCESS

    PDF_INGEST_LOCK_FILE.write_text(datetime.utcnow().isoformat())
    clear_pdf_ingest_skip_request()
    recovered = recover_interrupted_processing_files()
    pdfs = sorted(PDF_INBOX_DIR.glob("*.pdf"))
    total = len(pdfs)

    if total == 0:
        write_magazine_ingest_status({
            "status": "idle",
            "message": "No PDFs waiting in /data/pdf_inbox.",
            "current_file": "",
            "processed": 0,
            "total": 0,
            "succeeded": [],
            "skipped": [],
            "failed": [],
            "recovered": recovered,
            "paused": False,
            "skip_requested": False,
            "pause_seconds": pause_seconds,
        })
        PDF_INGEST_LOCK_FILE.unlink(missing_ok=True)
        return

    succeeded: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []

    try:
        write_magazine_ingest_status({
            "status": "running",
            "message": f"Starting controlled ingest for {total} PDF(s) from /data/pdf_inbox.",
            "current_file": "",
            "processed": 0,
            "total": total,
            "succeeded": succeeded,
            "skipped": skipped,
            "failed": failed,
            "recovered": recovered,
            "paused": False,
            "skip_requested": False,
            "pause_seconds": pause_seconds,
        })

        for index, inbox_file in enumerate(pdfs, start=1):
            filename = inbox_file.name
            processing_file = PDF_PROCESSING_DIR / filename
            magazine_file = MAGAZINE_DIR / filename
            failed_file = PDF_FAILED_DIR / filename
            done_marker = PDF_DONE_DIR / f"{filename}.done.txt"

            base_status = {
                "current_file": filename,
                "processed": index - 1,
                "total": total,
                "succeeded": succeeded,
                "skipped": skipped,
                "failed": failed,
                "recovered": recovered,
                "pause_seconds": pause_seconds,
            }

            wait_for_pdf_ingest_resume(base_status)
            clear_pdf_ingest_skip_request()

            write_magazine_ingest_status({
                **base_status,
                "status": "running",
                "message": f"Ingesting {filename} ({index}/{total})",
                "paused": False,
                "skip_requested": False,
            })

            try:
                require_data_disk_space(1.0)
                if inbox_file.exists():
                    shutil.move(str(inbox_file), str(processing_file))

                if magazine_file.exists() and magazine_file.stat().st_size > 0:
                    skipped.append({
                        "file": filename,
                        "reason": "A PDF with this filename already exists in /data/magazines. Skipped to avoid duplicate ingest.",
                    })
                    if processing_file.exists():
                        processing_file.unlink()
                    done_marker.write_text(
                        f"Skipped duplicate on {datetime.utcnow().isoformat()} UTC. Existing file: {magazine_file}\n"
                    )
                else:
                    # Existing ingest script expects the PDF in /data/magazines and receives only filename.
                    shutil.move(str(processing_file), str(magazine_file))
                    CURRENT_PDF_PROCESS = subprocess.Popen(
                        ["python", "scripts/ingest_one_magazine.py", filename],
                        cwd=Path(__file__).resolve().parents[1],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )

                    timed_out = False
                    skipped_by_editor = False
                    started_at = time.time()
                    timeout_seconds = 1800

                    while CURRENT_PDF_PROCESS.poll() is None:
                        if pdf_ingest_skip_requested():
                            skipped_by_editor = True
                            CURRENT_PDF_PROCESS.terminate()
                            try:
                                CURRENT_PDF_PROCESS.wait(timeout=10)
                            except subprocess.TimeoutExpired:
                                CURRENT_PDF_PROCESS.kill()
                                CURRENT_PDF_PROCESS.wait(timeout=5)
                            break

                        if time.time() - started_at > timeout_seconds:
                            timed_out = True
                            CURRENT_PDF_PROCESS.kill()
                            CURRENT_PDF_PROCESS.wait(timeout=5)
                            break

                        write_magazine_ingest_status({
                            **base_status,
                            "status": "running",
                            "message": f"Ingesting {filename} ({index}/{total}) — {int(time.time() - started_at)} seconds elapsed",
                            "paused": False,
                            "skip_requested": False,
                        })
                        time.sleep(5)

                    stdout, stderr = CURRENT_PDF_PROCESS.communicate()
                    returncode = CURRENT_PDF_PROCESS.returncode
                    CURRENT_PDF_PROCESS = None

                    if skipped_by_editor:
                        skipped.append({
                            "file": filename,
                            "reason": "Skipped by editor from admin console.",
                            "stdout": (stdout or "")[-1000:],
                            "stderr": (stderr or "")[-1000:],
                        })
                        clear_pdf_ingest_skip_request()
                        if magazine_file.exists():
                            shutil.move(str(magazine_file), str(failed_file))
                    elif timed_out:
                        failed.append({
                            "file": filename,
                            "error": "Timed out after 1800 seconds.",
                            "stdout": (stdout or "")[-2000:],
                            "stderr": (stderr or "")[-2000:],
                        })
                        if magazine_file.exists():
                            shutil.move(str(magazine_file), str(failed_file))
                    elif returncode != 0:
                        failed.append({
                            "file": filename,
                            "returncode": str(returncode),
                            "stdout": (stdout or "")[-2000:],
                            "stderr": (stderr or "")[-2000:],
                        })
                        if magazine_file.exists():
                            shutil.move(str(magazine_file), str(failed_file))
                    else:
                        succeeded.append({"file": filename, "stored_at": str(magazine_file)})
                        done_marker.write_text(
                            f"Ingested successfully on {datetime.utcnow().isoformat()} UTC. Stored at: {magazine_file}\n"
                        )

            except Exception as exc:
                CURRENT_PDF_PROCESS = None
                failed.append({"file": filename, "error": str(exc)})
                try:
                    if processing_file.exists():
                        shutil.move(str(processing_file), str(failed_file))
                    elif magazine_file.exists() and filename not in {item.get("file") for item in succeeded}:
                        shutil.move(str(magazine_file), str(failed_file))
                except Exception as move_exc:
                    failed.append({"file": filename, "error": f"Also failed while moving bad PDF to failed folder: {move_exc}"})

            write_magazine_ingest_status({
                "status": "running",
                "message": f"Finished {filename}. Pausing before next PDF." if index < total else f"Finished {filename}.",
                "current_file": filename,
                "processed": index,
                "total": total,
                "succeeded": succeeded,
                "skipped": skipped,
                "failed": failed,
                "recovered": recovered,
                "paused": False,
                "skip_requested": False,
                "pause_seconds": pause_seconds,
            })
            if index < total:
                pause_between_pdfs(pause_seconds, {
                    "current_file": filename,
                    "processed": index,
                    "total": total,
                    "succeeded": succeeded,
                    "skipped": skipped,
                    "failed": failed,
                    "recovered": recovered,
                    "pause_seconds": pause_seconds,
                })

        final_status = "completed" if not failed else "completed_with_errors"
        write_magazine_ingest_status({
            "status": final_status,
            "message": f"Controlled ingest finished. {len(succeeded)} succeeded; {len(skipped)} skipped; {len(failed)} failed.",
            "current_file": "",
            "processed": total,
            "total": total,
            "succeeded": succeeded,
            "skipped": skipped,
            "failed": failed,
            "recovered": recovered,
            "paused": False,
            "skip_requested": False,
            "pause_seconds": pause_seconds,
        })
    finally:
        CURRENT_PDF_PROCESS = None
        clear_pdf_ingest_skip_request()
        PDF_INGEST_LOCK_FILE.unlink(missing_ok=True)

def get_indexed_magazine_filenames() -> set[str]:
    """Return PDF filenames that are already referenced by the live LanceDB index."""
    try:
        import lancedb
        from urllib.parse import unquote

        db = lancedb.connect("/data/lancedb")
        table = db.open_table("greenbuilder_chunks")
        df = table.to_pandas()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read LanceDB index: {exc}") from exc

    indexed: set[str] = set()
    if "url" not in df.columns:
        return indexed

    for raw_url in df["url"].dropna().unique():
        url = str(raw_url)
        if "/magazines/" not in url:
            continue
        filename = Path(unquote(url.split("/magazines/", 1)[1])).name
        if filename.lower().endswith(".pdf"):
            indexed.add(filename)
    return indexed


def get_unused_magazine_pdfs() -> list[dict[str, object]]:
    """List PDFs in /data/magazines that are not indexed and not waiting in /data/pdf_inbox."""
    indexed = get_indexed_magazine_filenames()
    inbox = {p.name for p in PDF_INBOX_DIR.glob("*.pdf")}
    unused = []

    for path in sorted(MAGAZINE_DIR.glob("*.pdf")):
        if path.name in indexed:
            continue
        if path.name in inbox:
            continue
        unused.append(pdf_file_info(path))

    return unused


@app.get("/admin/unused-pdf-preview")
def unused_pdf_preview(_: str = Depends(admin_auth)) -> dict:
    unused = get_unused_magazine_pdfs()
    indexed = get_indexed_magazine_filenames()
    on_disk = list(MAGAZINE_DIR.glob("*.pdf"))
    return {
        "ok": True,
        "message": f"Found {len(unused)} unused PDF(s) safe to delete.",
        "unused": unused,
        "indexed_count": len(indexed),
        "magazines_on_disk_count": len(on_disk),
    }


@app.post("/admin/clean-unused-pdfs")
def clean_unused_pdfs(_: str = Depends(admin_auth)) -> dict:
    unused = get_unused_magazine_pdfs()
    deleted = []
    failed = []

    for item in unused:
        name = str(item.get("name", ""))
        path = MAGAZINE_DIR / name
        try:
            if path.exists() and path.is_file():
                path.unlink()
                deleted.append(item)
        except Exception as exc:
            failed.append({"name": name, "error": str(exc)})

    return {
        "ok": len(failed) == 0,
        "message": f"Deleted {len(deleted)} unused PDF(s). {len(failed)} failed.",
        "deleted": deleted,
        "failed": failed,
    }


@app.post("/admin/upload-magazine")
async def upload_magazine(files: List[UploadFile] = File(...)):
    uploaded = []
    skipped = []
    require_data_disk_space(1.0)

    for file in files:
        filename = file.filename or ""
        if not filename.lower().endswith(".pdf"):
            skipped.append(filename)
            continue
        target = PDF_INBOX_DIR / filename
        if target.exists():
            skipped.append(f"{filename} (already in inbox)")
            continue
        with target.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        uploaded.append(filename)

    return {
        "ok": True,
        "message": f"Uploaded {len(uploaded)} PDF(s) safely to /data/pdf_inbox. Auto-ingest is OFF.",
        "files": uploaded,
        "skipped": skipped,
    }


@app.get("/admin/pdf-inbox-status")
def pdf_inbox_status(_: str = Depends(admin_auth)) -> dict:
    total, used, free = shutil.disk_usage("/data")
    return {
        "ok": True,
        "disk": {
            "total_gb": round(total / (1024 ** 3), 2),
            "used_gb": round(used / (1024 ** 3), 2),
            "free_gb": round(free / (1024 ** 3), 2),
        },
        "inbox": list_pdf_folder(PDF_INBOX_DIR),
        "processing": list_pdf_folder(PDF_PROCESSING_DIR),
        "done": [pdf_file_info(path) for path in sorted(PDF_DONE_DIR.glob("*.done.txt"))],
        "failed": list_pdf_folder(PDF_FAILED_DIR),
        "status": read_magazine_ingest_status(),
        "lock_exists": PDF_INGEST_LOCK_FILE.exists(),
        "paused": PDF_INGEST_PAUSE_FILE.exists(),
        "skip_requested": PDF_INGEST_SKIP_FILE.exists(),
        "pause_seconds": PDF_INGEST_DEFAULT_PAUSE_SECONDS,
    }


@app.post("/admin/ingest-pdf-inbox")
async def ingest_pdf_inbox(background_tasks: BackgroundTasks, _: str = Depends(admin_auth)) -> dict:
    current_status = read_magazine_ingest_status()
    if current_status.get("status") == "running" and PDF_INGEST_LOCK_FILE.exists():
        return {"ok": True, "message": "PDF ingest is already running."}

    # If the prior service died mid-ingest, recover PDFs that were left in processing.
    recovered = recover_interrupted_processing_files()
    pdf_count = len(list(PDF_INBOX_DIR.glob("*.pdf")))

    if pdf_count == 0:
        write_magazine_ingest_status({
            "status": "idle",
            "message": "No PDFs waiting in /data/pdf_inbox.",
            "current_file": "",
            "processed": 0,
            "total": 0,
            "succeeded": [],
            "skipped": [],
            "failed": [],
            "recovered": recovered,
        })
        return {"ok": True, "message": "No PDFs waiting in /data/pdf_inbox."}

    require_data_disk_space(1.0)
    background_tasks.add_task(run_pdf_inbox_ingest, PDF_INGEST_DEFAULT_PAUSE_SECONDS)
    write_magazine_ingest_status({
        "status": "running",
        "message": f"Controlled ingest queued for {pdf_count} PDF(s).",
        "current_file": "",
        "processed": 0,
        "total": pdf_count,
        "succeeded": [],
        "skipped": [],
        "failed": [],
        "recovered": recovered,
    })
    return {
        "ok": True,
        "message": f"Controlled ingest started for {pdf_count} PDF(s). Files will process one at a time with a 20-second pause between PDFs.",
    }


@app.post("/admin/pause-pdf-ingest")
def pause_pdf_ingest(_: str = Depends(admin_auth)) -> dict:
    PDF_INGEST_PAUSE_FILE.write_text(datetime.utcnow().isoformat())
    return {"ok": True, "message": "PDF ingest pause requested. It will pause between files."}


@app.post("/admin/resume-pdf-ingest")
def resume_pdf_ingest(_: str = Depends(admin_auth)) -> dict:
    PDF_INGEST_PAUSE_FILE.unlink(missing_ok=True)
    return {"ok": True, "message": "PDF ingest resumed."}


@app.post("/admin/skip-current-pdf")
def skip_current_pdf(_: str = Depends(admin_auth)) -> dict:
    PDF_INGEST_SKIP_FILE.write_text(datetime.utcnow().isoformat())
    return {"ok": True, "message": "Skip requested for the current PDF."}


@app.get("/admin/magazine-ingest-status")
def magazine_ingest_status(_: str = Depends(admin_auth)) -> dict:
    return read_magazine_ingest_status()


# === Draft HTML / ZIP Upload Endpoint ===
@app.post("/admin/upload-draft-html")
async def upload_draft_html(files: List[UploadFile] = File(...), _: str = Depends(admin_auth)) -> dict:
    """Upload saved HubSpot/HTML draft files or ZIP archives to /data/draft_html.

    - Individual .html/.htm files are stored directly.
    - .zip files are saved temporarily, safely extracted, and then removed.
    - This only stores/extracts files. It does not parse them, ingest them, or rebuild the index.
    """
    target_dir = Path("/data/draft_html")
    target_dir.mkdir(parents=True, exist_ok=True)

    uploaded: list[str] = []
    extracted: list[str] = []
    skipped: list[str] = []
    failed: list[dict[str, str]] = []

    def safe_extract_zip(zip_path: Path, destination: Path) -> list[str]:
        """Extract a ZIP file while preventing path traversal attacks."""
        extracted_files: list[str] = []
        destination_resolved = destination.resolve()

        with zipfile.ZipFile(zip_path, "r") as archive:
            for member in archive.infolist():
                member_name = member.filename

                if member.is_dir():
                    continue
                if not member_name.lower().endswith((".html", ".htm")):
                    continue

                # Flatten nested folders so every HTML file lands directly in /data/draft_html.
                clean_name = Path(member_name).name
                if not clean_name:
                    continue

                target_path = destination / clean_name
                target_resolved = target_path.resolve()

                if not str(target_resolved).startswith(str(destination_resolved)):
                    raise RuntimeError(f"Unsafe ZIP path skipped: {member_name}")

                # Avoid silent overwrites.
                if target_path.exists():
                    stem = target_path.stem
                    suffix = target_path.suffix
                    target_path = destination / f"{stem}-{int(time.time())}{suffix}"

                with archive.open(member, "r") as source, target_path.open("wb") as output:
                    shutil.copyfileobj(source, output)

                extracted_files.append(target_path.name)

        return extracted_files

    for file in files:
        raw_filename = file.filename or ""
        filename = Path(raw_filename).name

        if not filename:
            skipped.append("unnamed file")
            continue

        try:
            lower_name = filename.lower()

            if lower_name.endswith(".zip"):
                temp_zip = target_dir / f"upload-{int(time.time())}-{filename}"

                with temp_zip.open("wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                extracted_files = safe_extract_zip(temp_zip, target_dir)
                temp_zip.unlink(missing_ok=True)

                uploaded.append(filename)
                extracted.extend(extracted_files)

            elif lower_name.endswith((".html", ".htm")):
                target = target_dir / filename

                if target.exists():
                    stem = target.stem
                    suffix = target.suffix
                    target = target_dir / f"{stem}-{int(time.time())}{suffix}"

                with target.open("wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                uploaded.append(target.name)

            else:
                skipped.append(filename)

        except Exception as exc:
            failed.append({"file": filename, "error": str(exc)})

    return {
        "ok": len(failed) == 0,
        "message": (
            f"Stored {len(uploaded)} uploaded item(s); "
            f"extracted {len(extracted)} HTML file(s) into /data/draft_html. "
            "This endpoint does not ingest or rebuild the index."
        ),
        "uploaded": uploaded,
        "extracted_count": len(extracted),
        "extracted_sample": extracted[:20],
        "skipped": skipped,
        "failed": failed,
    }


# === Serve Generated Assets and Magazine PDFs Already Ingested ===
ASSETS_DIR = Path("/data/assets")
(ASSETS_DIR / "thumbs").mkdir(parents=True, exist_ok=True)
(ASSETS_DIR / "covers").mkdir(parents=True, exist_ok=True)

# === Backup Download Endpoint ===
@app.get("/download-backup")
async def download_backup():
    backup_path = Path("/data/gbm-full-backup.tar.gz")

    if not backup_path.exists():
        return {"error": "Backup file not found"}

    return FileResponse(
        path=str(backup_path),
        filename="gbm-full-backup.tar.gz",
        media_type="application/gzip"
    )
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
app.mount("/magazines", StaticFiles(directory="/data/magazines"), name="magazines")
