from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

import json
import re
import time
from typing import Any

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

EMBED_BATCH_SIZE = 16
PAUSE_BETWEEN_VIDEOS_SECONDS = 1.0


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
    text = text or ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_transcript(video_id: str) -> list[dict[str, Any]]:
    try:
        return YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=["en", "en-US", "en-GB"],
        )
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as exc:
        print(f"No transcript for {video_id}: {exc}")
        return []
    except Exception as exc:
        print(f"Transcript fetch failed for {video_id}: {exc}")
        return []


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
    if source_type == "podcast":
        return "Green Builder Media Network"
    return "Green Builder Media YouTube"


def make_rows_for_video(video: dict[str, Any], source_type: str) -> list[dict[str, Any]]:
    video_id = video.get("video_id") or ""
    if not video_id:
        return []

    transcript = fetch_transcript(video_id)
    if not transcript:
        return []

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
        start = int(block["start"])
        text = block["text"]

        timestamp_url = f"https://www.youtube.com/watch?v={video_id}&t={start}s"

        full_text = clean_text(
            f"{title}\n\n"
            f"{description[:800]}\n\n"
            f"Transcript excerpt starting at {start} seconds:\n{text}"
        )

        rows.append(
            {
                "id": f"youtube-{source_type}-{video_id}#chunk-{idx}",
                "url": timestamp_url,
                "title": title,
                "published_at": video.get("published_at"),
                "category": "Video transcript" if source_type == "video" else "Podcast transcript",
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
                "visibility": "public",
                "attribution_label": source_label(source_type),
                "surface_policy": "show_source",
                "stale": False,
                "stale_reasons": "[]",
                "governance_note": None,
                "video_id": video_id,
                "media_start_seconds": start,
                "media_end_seconds": int(block.get("end") or start),
            }
        )

    return rows


def embed_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    embed_inputs = [
        build_embed_text(
            title=row.get("title", ""),
            category=row.get("category"),
            chunk=row.get("text", ""),
            url=row.get("url", ""),
        )
        for row in rows
    ]

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

    try:
        table = db.open_table(TABLE_NAME)
    except Exception as exc:
        raise RuntimeError(
            f"LanceDB table '{TABLE_NAME}' not found. Run build_index.py first."
        ) from exc

    table.add(rows)
    return len(rows)


def main() -> None:
    videos = load_json_list(YOUTUBE_CACHE_FILE)
    podcasts = load_json_list(PODCAST_CACHE_FILE)

    media_items: list[tuple[dict[str, Any], str]] = []
    media_items.extend((item, "video") for item in videos)
    media_items.extend((item, "podcast") for item in podcasts)

    print(f"Loaded {len(videos)} videos and {len(podcasts)} podcasts.")

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

        print(f"[{index}/{len(media_items)}] Fetching transcript: {title}")

        try:
            rows = make_rows_for_video(item, source_type)
            if not rows:
                skipped.append(
                    {
                        "title": title,
                        "video_id": video_id,
                        "source_type": source_type,
                        "reason": "No transcript rows",
                    }
                )
                continue

            all_rows.extend(rows)
            succeeded.append(
                {
                    "title": title,
                    "video_id": video_id,
                    "source_type": source_type,
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
