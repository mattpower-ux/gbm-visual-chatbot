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
        return YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=["en", "en-US", "en-GB"],
        )
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


def get_best_transcript(video_id: str, whisper_budget: dict[str, int]) -> tuple[list[dict[str, Any]], str]:
    rows = fetch_transcript_api(video_id)
    if rows:
        return rows, "youtube_transcript_api"

    rows = fetch_transcript_ytdlp_captions(video_id)
    if rows:
        return rows, "yt_dlp_captions"

    if ENABLE_WHISPER_FALLBACK and whisper_budget["used"] < MAX_WHISPER_VIDEOS_PER_RUN:
        whisper_budget["used"] += 1
        rows = transcribe_audio_with_openai(video_id)
        if rows:
            return rows, "openai_whisper"

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
) -> tuple[list[dict[str, Any]], str]:
    video_id = video.get("video_id") or ""
    if not video_id:
        return [], "missing_video_id"

    transcript, method = get_best_transcript(video_id, whisper_budget)
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

    blocks = transcript_to_blocks(transcript)
    rows: list[dict[str, Any]] = []

    for idx, block in enumerate(blocks):
        row_id = f"youtube-{source_type}-{video_id}#chunk-{idx}"
        if row_id in existing_ids:
            continue

        start = int(block["start"])
        timestamp_url = f"https://www.youtube.com/watch?v={video_id}&t={start}s"

        full_text = clean_text(
            f"{title}\n\n"
            f"{description[:800]}\n\n"
            f"Transcript excerpt starting at {start} seconds:\n{block['text']}"
        )

        rows.append(
            {
                "id": row_id,
                "url": timestamp_url,
                "title": title,
                "published_at": video.get("published_at"),
                "category": "Podcast transcript" if source_type == "podcast" else "Video transcript",
                "source_type": source_type,
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

    existing_ids = existing_transcript_ids()
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
            rows, method = make_rows_for_video(item, source_type, existing_ids, whisper_budget)

            if not rows:
                skipped.append(
                    {
                        "title": title,
                        "video_id": video_id,
                        "source_type": source_type,
                        "reason": "No transcript rows",
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
        "chunks_prepared": len(all_rows),
        "chunks_added": added,
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
