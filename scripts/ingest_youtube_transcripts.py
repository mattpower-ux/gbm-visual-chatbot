from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

import lancedb
from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

from app.config import get_settings
from app.build_index import build_embed_text, embed_batch_with_retry

TABLE_NAME = "greenbuilder_chunks"

YOUTUBE_CACHE_FILE = Path("/data/youtube_videos.json")
PODCAST_CACHE_FILE = Path("/data/podcast_videos.json")
TRANSCRIPT_STATUS_FILE = Path("/data/youtube_transcript_ingest_status.json")
TRANSCRIPT_CACHE_FILE = Path("/data/youtube_transcripts.json")
ONLY_INGEST_CACHED_TRANSCRIPTS = os.getenv("ONLY_INGEST_CACHED_TRANSCRIPTS", "true").lower() in {"1", "true", "yes", "on"}
CAPTION_DIR = Path("/data/youtube_captions")
AUDIO_DIR = Path("/data/youtube_audio")

EMBED_BATCH_SIZE = 16
PAUSE_BETWEEN_VIDEOS_SECONDS = float(os.getenv("YOUTUBE_TRANSCRIPT_PAUSE_SECONDS", "1"))

ENABLE_WHISPER_FALLBACK = os.getenv("ENABLE_WHISPER_FALLBACK", "true").lower() in {
    "1", "true", "yes", "on"
}
MAX_WHISPER_VIDEOS_PER_RUN = int(os.getenv("MAX_WHISPER_VIDEOS_PER_RUN", "10"))
MAX_AUDIO_MB = int(os.getenv("MAX_AUDIO_MB", "24"))
TRANSCRIPTION_MODEL = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1")


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        print(f"Missing cache file: {path}")
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as exc:
        print(f"Could not read {path}: {exc}")
        return []


def load_json_any(path: Path) -> Any:
    if not path.exists():
        print(f"Missing cache file: {path}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Could not read {path}: {exc}")
        return None


def normalize_video_id(raw: Any) -> str:
    return str(raw or "").strip()


def load_cached_transcript_index(path: Path = TRANSCRIPT_CACHE_FILE) -> dict[str, dict[str, Any]]:
    """
    Loads locally scraped transcripts from /data/youtube_transcripts.json.

    This is the important bridge for the browser-assisted transcript scraper.
    The scraper output observed on Render stores full transcript content in
    transcript["text"], not transcript["rows"]. This index lets the ingestion
    pipeline use that already-scraped text before trying YouTube's public API.
    """
    data = load_json_any(path)
    if not data:
        return {}

    candidates: list[dict[str, Any]] = []

    if isinstance(data, list):
        candidates = [x for x in data if isinstance(x, dict)]
    elif isinstance(data, dict):
        for key in (
            "transcripts",
            "items",
            "videos",
            "results",
            "data",
        ):
            value = data.get(key)
            if isinstance(value, list):
                candidates.extend(x for x in value if isinstance(x, dict))

        # Some status/cache files also contain lookup maps.
        for key in ("by_video_id", "by_title"):
            value = data.get(key)
            if isinstance(value, dict):
                candidates.extend(x for x in value.values() if isinstance(x, dict))

        # If the dict itself looks like one transcript object, include it.
        if data.get("video_id") or data.get("text") or data.get("rows"):
            candidates.append(data)

    index: dict[str, dict[str, Any]] = {}
    for item in candidates:
        video_id = normalize_video_id(item.get("video_id") or item.get("id"))
        if not video_id:
            url = str(item.get("url") or item.get("youtube_url") or "")
            match = re.search(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{6,})", url)
            if match:
                video_id = match.group(1)

        if video_id and item.get("text"):
            index[video_id] = item

    print(f"Loaded {len(index)} cached scraped transcripts from {path}.")
    return index


def timestamp_label(seconds: float | int) -> str:
    seconds_int = max(int(seconds or 0), 0)
    h = seconds_int // 3600
    m = (seconds_int % 3600) // 60
    s = seconds_int % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def rows_from_plain_transcript_text(text: str) -> list[dict[str, Any]]:
    """
    Converts a full scraped transcript string into timestamp-ish rows.

    Supports transcript text with explicit timestamps like 00:31, 1:02:15,
    or plain text with no timestamps. If no timestamps are found, it still
    returns one row so transcript_to_blocks can chunk it for semantic search.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    timestamp_re = re.compile(r"(?P<ts>\b\d{1,2}:\d{2}(?::\d{2})?\b)")

    rows: list[dict[str, Any]] = []
    current_start: float | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_start, current_lines
        row_text = clean_text(" ".join(current_lines))
        if row_text:
            rows.append(
                {
                    "text": row_text,
                    "start": float(current_start or 0.0),
                    "duration": 1.0,
                }
            )
        current_start = None
        current_lines = []

    for line in lines:
        match = timestamp_re.search(line)
        if match:
            if current_lines:
                flush()
            current_start = seconds_from_timestamp(match.group("ts"))
            line = timestamp_re.sub(" ", line, count=1).strip(" -â€“â€”\t")
        elif current_start is None:
            current_start = 0.0

        if line:
            current_lines.append(line)

    if current_lines:
        flush()

    if rows:
        # Estimate durations from the next row start when possible.
        for i, row in enumerate(rows):
            if i + 1 < len(rows):
                row["duration"] = max(float(rows[i + 1]["start"]) - float(row["start"]), 0.1)
        return rows

    return [{"text": clean_text(cleaned), "start": 0.0, "duration": 1.0}]


def cached_transcript_to_rows(transcript_obj: dict[str, Any]) -> list[dict[str, Any]]:
    rows = transcript_obj.get("rows")
    if isinstance(rows, list):
        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            text = clean_text(str(row.get("text") or ""))
            if not text:
                continue
            normalized_rows.append(
                {
                    "text": text,
                    "start": float(row.get("start") or row.get("start_seconds") or 0.0),
                    "duration": float(row.get("duration") or 1.0),
                }
            )
        if normalized_rows:
            return normalized_rows

    # This is the known current scraper format: one transcript object with "text".
    return rows_from_plain_transcript_text(str(transcript_obj.get("text") or ""))


def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def seconds_from_timestamp(raw: str) -> float:
    parts = raw.replace(",", ".").split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        if len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
    except Exception:
        return 0.0
    return 0.0


def fetch_transcript_api(video_id: str) -> list[dict[str, Any]]:
    try:
        api = YouTubeTranscriptApi()

        transcript = api.fetch(
            video_id,
            languages=["en", "en-US", "en-GB"],
        )

        rows: list[dict[str, Any]] = []

        for item in transcript:
            rows.append(
                {
                    "text": clean_text(getattr(item, "text", "")),
                    "start": float(getattr(item, "start", 0.0)),
                    "duration": float(getattr(item, "duration", 0.0)),
                }
            )

        return rows

    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as exc:
        print(f"No public transcript API rows for {video_id}: {exc}")
        return []

    except Exception as exc:
        print(f"Transcript API failed for {video_id}: {exc}")
        return []


def run_command(cmd: list[str]) -> bool:
    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=900,
        )
        if result.returncode != 0:
            print("Command failed:", " ".join(cmd))
            print((result.stderr or "")[-1000:])
            return False
        return True
    except Exception as exc:
        print(f"Command exception: {exc}")
        return False


def fetch_transcript_ytdlp_captions(video_id: str) -> list[dict[str, Any]]:
    CAPTION_DIR.mkdir(parents=True, exist_ok=True)

    url = f"https://www.youtube.com/watch?v={video_id}"
    outtmpl = str(CAPTION_DIR / f"{video_id}.%(ext)s")

    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        "en,en-US,en.*",
        "--sub-format",
        "vtt",
        "-o",
        outtmpl,
        url,
    ]

    ok = run_command(cmd)
    if not ok:
        return []

    files = list(CAPTION_DIR.glob(f"{video_id}*.vtt"))
    if not files:
        return []

    return parse_vtt(files[0])


def parse_vtt(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()

    entries: list[dict[str, Any]] = []
    current_start: float | None = None
    current_end: float | None = None
    buffer: list[str] = []

    timestamp_re = re.compile(
        r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3})\s+-->\s+"
        r"(?P<end>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3})"
    )

    def flush():
        nonlocal buffer, current_start, current_end
        text = clean_text(" ".join(buffer))
        if text and current_start is not None:
            entries.append(
                {
                    "text": text,
                    "start": current_start,
                    "duration": max((current_end or current_start) - current_start, 0.1),
                }
            )
        buffer = []
        current_start = None
        current_end = None

    for line in lines:
        line = line.strip()
        if not line or line == "WEBVTT" or line.startswith("Kind:") or line.startswith("Language:"):
            continue

        match = timestamp_re.search(line)
        if match:
            flush()
            current_start = seconds_from_timestamp(match.group("start"))
            current_end = seconds_from_timestamp(match.group("end"))
            continue

        if current_start is not None:
            buffer.append(line)

    flush()

    deduped: list[dict[str, Any]] = []
    seen = set()
    for item in entries:
        key = item["text"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return deduped


def download_audio(video_id: str) -> Path | None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    for existing in AUDIO_DIR.glob(f"{video_id}.*"):
        existing.unlink(missing_ok=True)

    url = f"https://www.youtube.com/watch?v={video_id}"
    outtmpl = str(AUDIO_DIR / f"{video_id}.%(ext)s")

    cmd = [
        "yt-dlp",
        "-f",
        "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
        "--no-playlist",
        "--max-filesize",
        f"{MAX_AUDIO_MB}m",
        "-o",
        outtmpl,
        url,
    ]

    if not run_command(cmd):
        return None

    files = list(AUDIO_DIR.glob(f"{video_id}.*"))
    if not files:
        return None

    audio = files[0]
    size_mb = audio.stat().st_size / (1024 * 1024)
    if size_mb > MAX_AUDIO_MB:
        print(f"Audio too large for transcription: {audio.name} {size_mb:.1f} MB")
        return None

    return audio


def transcribe_audio_with_openai(video_id: str) -> list[dict[str, Any]]:
    audio_path = download_audio(video_id)
    if not audio_path:
        return []

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    try:
        with audio_path.open("rb") as audio_file:
            result = client.audio.transcriptions.create(
                model=TRANSCRIPTION_MODEL,
                file=audio_file,
                response_format="verbose_json",
            )

        segments = getattr(result, "segments", None)
        if segments is None and isinstance(result, dict):
            segments = result.get("segments")

        if segments:
            return [
                {
                    "text": clean_text(seg.get("text", "") if isinstance(seg, dict) else getattr(seg, "text", "")),
                    "start": float(seg.get("start", 0) if isinstance(seg, dict) else getattr(seg, "start", 0)),
                    "duration": max(
                        float(seg.get("end", 0) if isinstance(seg, dict) else getattr(seg, "end", 0))
                        - float(seg.get("start", 0) if isinstance(seg, dict) else getattr(seg, "start", 0)),
                        0.1,
                    ),
                }
                for seg in segments
                if clean_text(seg.get("text", "") if isinstance(seg, dict) else getattr(seg, "text", ""))
            ]

        text = clean_text(getattr(result, "text", "") or "")
        if text:
            return [{"text": text, "start": 0.0, "duration": 1.0}]

    except Exception as exc:
        print(f"OpenAI transcription failed for {video_id}: {exc}")
        return []
    finally:
        audio_path.unlink(missing_ok=True)

    return []


def get_best_transcript(
    video_id: str,
    whisper_budget: dict[str, int],
    cached_transcripts: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], str]:

    cached = (cached_transcripts or {}).get(video_id)
    if cached:
        rows = cached_transcript_to_rows(cached)
        if rows:
            return rows, "cached_youtube_transcripts_json"

    if ONLY_INGEST_CACHED_TRANSCRIPTS:
        return [], "cached_only_no_local_transcript"

    rows = fetch_transcript_api(video_id)
    if rows:
        return rows, "youtube_transcript_api"

    rows = fetch_transcript_ytdlp_captions(video_id)
    if rows:
        return rows, "yt_dlp_captions"

    if ENABLE_WHISPER_FALLBACK and whisper_budget.get("used", 0) < MAX_WHISPER_VIDEOS_PER_RUN:
        whisper_budget["used"] = whisper_budget.get("used", 0) + 1
        rows = transcribe_audio_with_openai(video_id)
        if rows:
            return rows, "openai_whisper_fallback"

    return [], "none"


def transcript_to_blocks(
    transcript: list[dict[str, Any]],
    max_chars: int = 1800,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    current_text: list[str] = []
    current_start: float | None = None
    current_end: float | None = None

    for item in transcript:
        text = clean_text(item.get("text", ""))
        if not text:
            continue

        start = float(item.get("start", 0.0))
        duration = float(item.get("duration", 0.0))
        end = start + duration

        if current_start is None:
            current_start = start

        current_text.append(text)
        current_end = end

        joined = clean_text(" ".join(current_text))

        if len(joined) >= max_chars:
            blocks.append(
                {
                    "text": joined,
                    "start": int(current_start or 0),
                    "end": int(current_end or current_start or 0),
                }
            )
            current_text = []
            current_start = None
            current_end = None

    if current_text:
        blocks.append(
            {
                "text": clean_text(" ".join(current_text)),
                "start": int(current_start or 0),
                "end": int(current_end or current_start or 0),
            }
        )

    return blocks



def format_transcript_timestamp(seconds: int | float | str | None) -> str:
    """Convert transcript start seconds into M:SS or H:MM:SS."""
    if seconds is None or seconds == "":
        return ""

    try:
        total = int(float(seconds))
    except Exception:
        return ""

    if total < 0:
        return ""

    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60

    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def normalize_speaker_label(value: Any) -> str:
    """Return a clean speaker label for transcript chunks."""
    if value is None:
        return ""

    if isinstance(value, list):
        value = ", ".join(str(v).strip() for v in value if str(v).strip())

    text = clean_text(str(value))
    return text.strip()


def source_label(source_type: str) -> str:
    return "Green Builder Media Network" if source_type == "podcast" else "Green Builder Media YouTube"


def existing_transcript_ids() -> set[str]:
    try:
        settings = get_settings()
        db = lancedb.connect(str(settings.lancedb_dir))
        table = db.open_table(TABLE_NAME)
        df = table.to_pandas()
        if "id" not in df.columns:
            return set()
        return {
            str(v)
            for v in df["id"].dropna().tolist()
            if str(v).startswith("youtube-")
        }
    except Exception as exc:
        print(f"Could not check existing transcript IDs: {exc}")
        return set()


def make_rows_for_video(
    video: dict[str, Any],
    source_type: str,
    existing_ids: set[str],
    whisper_budget: dict[str, int],
    cached_transcripts: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    video_id = video.get("video_id") or ""
    if not video_id:
        return [], "missing_video_id"

    transcript, method = get_best_transcript(video_id, whisper_budget, cached_transcripts)
    if not transcript:
        return [], method

    title = video.get("title") or "Green Builder Media Video"
    description = video.get("description") or ""
    thumbnail = (
        video.get("thumbnail_url")
        or video.get("thumbnail")
        or video.get("image")
        or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    )

    speaker_label = normalize_speaker_label(
        video.get("speakers")
        or video.get("speaker")
        or video.get("guest")
        or video.get("host")
        or video.get("presenter")
        or ""
    )

    blocks = transcript_to_blocks(transcript)
    rows: list[dict[str, Any]] = []

    for idx, block in enumerate(blocks):
        row_id = f"youtube-{source_type}-{video_id}#chunk-{idx}"
        if row_id in existing_ids:
            continue

        start = int(block["start"])
        timestamp = format_transcript_timestamp(start)
        timestamp_url = f"https://www.youtube.com/watch?v={video_id}&t={start}s"

        full_text = clean_text(
            f"{title}\n\n"
            f"{description[:800]}\n\n"
            f"Transcript excerpt starting at {timestamp_label(start)} ({start} seconds):\n{block['text']}"
        )

        rows.append(
            {
                "id": row_id,
                "url": timestamp_url,
                "title": title,
                "published_at": video.get("published_at"),
                "speakers": speaker_label,
                "speaker": speaker_label,
                "timestamp": timestamp,
                "timestamp_seconds": start,
                "transcript_start": start,
                "content_type": "Interview Transcript",
                "category": "Podcast transcript" if source_type == "podcast" else "Video transcript",
                "source_type": source_type,
                "is_transcript": True,
                "image": thumbnail,
                "thumbnail": thumbnail,
                "og_image": thumbnail,
                "featured_image": thumbnail,
                "thumbnail_url": thumbnail,
                "page": None,
                "source_name": title,
                "pdf_filename": None,
                "relevance_hint": None,
                "text": full_text,
                "embed_text": "",
                "chunk_index": idx,
                "chunk_count": len(blocks),
                "visibility": "public",
                "attribution_label": source_label(source_type),
                "surface_policy": "show_source",
                "stale": False,
                "stale_reasons": "[]",
                "governance_note": None,
            }
        )

    return rows, method


def embed_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    embed_inputs = []
    for row in rows:
        embed_text = build_embed_text(
            title=row.get("title", ""),
            category=row.get("category"),
            chunk=row.get("text", ""),
            url=row.get("url", ""),
        )
        row["embed_text"] = embed_text
        embed_inputs.append(embed_text)

    embedded_rows: list[dict[str, Any]] = []
    batches = [
        embed_inputs[i:i + EMBED_BATCH_SIZE]
        for i in range(0, len(embed_inputs), EMBED_BATCH_SIZE)
    ]

    row_index = 0

    for batch_num, batch in enumerate(batches, start=1):
        vectors = embed_batch_with_retry(
            client=client,
            model=settings.openai_embedding_model,
            batch=batch,
            batch_num=batch_num,
            total_batches=len(batches),
        )

        for vector in vectors:
            row = dict(rows[row_index])
            row["vector"] = vector
            embedded_rows.append(row)
            row_index += 1

        time.sleep(1)

    return embedded_rows


def append_to_lancedb(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    settings = get_settings()
    db = lancedb.connect(str(settings.lancedb_dir))
    table = db.open_table(TABLE_NAME)
    table.add(rows)
    return len(rows)


def main() -> None:
    videos = load_json_list(YOUTUBE_CACHE_FILE)
    podcasts = load_json_list(PODCAST_CACHE_FILE)

    media_items: list[tuple[dict[str, Any], str]] = []
    media_items.extend((item, "video") for item in videos)
    media_items.extend((item, "podcast") for item in podcasts)

    print(f"Loaded {len(videos)} videos and {len(podcasts)} podcasts.")
    if ONLY_INGEST_CACHED_TRANSCRIPTS:
        print("Cached-only transcript ingest is ON. Videos without local /data/youtube_transcripts.json records will be skipped without YouTube API, yt-dlp, or audio fallback.")

    existing_ids = existing_transcript_ids()
    cached_transcripts = load_cached_transcript_index()
    whisper_budget = {"used": 0}

    all_rows: list[dict[str, Any]] = []
    succeeded = []
    failed = []
    skipped = []

    seen_video_ids = set()

    for index, (item, source_type) in enumerate(media_items, start=1):
        video_id = item.get("video_id")
        title = item.get("title", "Untitled")

        if not video_id:
            skipped.append({"title": title, "reason": "Missing video_id"})
            continue

        key = f"{source_type}:{video_id}"
        if key in seen_video_ids:
            skipped.append({"title": title, "video_id": video_id, "reason": "Duplicate"})
            continue

        seen_video_ids.add(key)

        print(f"[{index}/{len(media_items)}] Processing: {title}")

        try:
            rows, method = make_rows_for_video(
                item,
                source_type,
                existing_ids,
                whisper_budget,
                cached_transcripts,
            )

            if not rows:
                skipped.append(
                    {
                        "title": title,
                        "video_id": video_id,
                        "source_type": source_type,
                        "reason": "No transcript text or rows",
                        "method": method,
                    }
                )
                continue

            all_rows.extend(rows)
            succeeded.append(
                {
                    "title": title,
                    "video_id": video_id,
                    "source_type": source_type,
                    "method": method,
                    "chunks": len(rows),
                }
            )

        except Exception as exc:
            failed.append(
                {
                    "title": title,
                    "video_id": video_id,
                    "source_type": source_type,
                    "error": str(exc),
                }
            )

        time.sleep(PAUSE_BETWEEN_VIDEOS_SECONDS)

    print(f"Transcript chunks prepared: {len(all_rows)}")

    embedded_rows = embed_rows(all_rows)
    added = append_to_lancedb(embedded_rows)

    status = {
        "ok": True,
        "videos_loaded": len(videos),
        "podcasts_loaded": len(podcasts),
        "cached_transcripts_loaded": len(cached_transcripts),
        "chunks_prepared": len(all_rows),
        "chunks_added": added,
        "only_ingest_cached_transcripts": ONLY_INGEST_CACHED_TRANSCRIPTS,
        "whisper_fallback_enabled": ENABLE_WHISPER_FALLBACK,
        "whisper_videos_used": whisper_budget["used"],
        "max_whisper_videos_per_run": MAX_WHISPER_VIDEOS_PER_RUN,
        "succeeded": succeeded,
        "skipped": skipped,
        "failed": failed,
        "updated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    TRANSCRIPT_STATUS_FILE.write_text(
        json.dumps(status, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
