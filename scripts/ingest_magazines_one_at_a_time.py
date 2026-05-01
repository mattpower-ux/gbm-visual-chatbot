from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

# Render disk folders
MAGAZINE_DIR = Path("/data/magazines")
QUEUE_DIR = Path("/data/magazines_queue")
DONE_DIR = Path("/data/magazines_done")
FAILED_DIR = Path("/data/magazines_failed")
DOCUMENTS_FILE = Path("/data/documents.jsonl")

# Legacy ingest script. Optional now.
INGEST_COMMAND = ["python", "scripts/ingest_magazines.py"]

PAUSE_SECONDS = int(os.getenv("PDF_BATCH_PAUSE_SECONDS", "20"))
MAX_FILES = int(os.getenv("PDF_BATCH_MAX_FILES", "0"))
RUN_LEGACY_PDF_INGEST = os.getenv("RUN_LEGACY_PDF_INGEST", "false").lower() in {
    "1", "true", "yes", "on"
}


def log(msg: str) -> None:
    print(msg, flush=True)


def ensure_dirs() -> None:
    MAGAZINE_DIR.mkdir(parents=True, exist_ok=True)
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)
    DOCUMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DOCUMENTS_FILE.touch(exist_ok=True)


def magazine_url(filename: str) -> str:
    return f"/magazines/{filename}"


def remove_existing_pdf_records(filename: str) -> int:
    """Remove old records for this PDF from documents.jsonl to prevent duplicates."""
    if not DOCUMENTS_FILE.exists():
        return 0

    kept: list[str] = []
    removed = 0

    with DOCUMENTS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue

            try:
                record = json.loads(raw)
            except Exception:
                kept.append(raw)
                continue

            if (
                record.get("pdf_filename") == filename
                or filename in str(record.get("url", ""))
                or filename in str(record.get("title", ""))
            ):
                removed += 1
                continue

            kept.append(json.dumps(record, ensure_ascii=False))

    with DOCUMENTS_FILE.open("w", encoding="utf-8") as f:
        for item in kept:
            f.write(item + "\n")

    return removed


def extract_pdf_pages(pdf_path: Path) -> list[dict]:
    """Extract one citeable public document record per PDF page."""
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError("Missing dependency: add pymupdf to requirements.txt") from exc

    filename = pdf_path.name
    source_name = pdf_path.stem
    records: list[dict] = []

    pdf = fitz.open(pdf_path)

    try:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()
            if not text:
                continue

            records.append(
                {
                    "url": magazine_url(filename),
                    "title": f"{source_name} (PDF, p. {page_number})",
                    "source_name": source_name,
                    "text": text,
                    "published_at": None,
                    "category": "Magazine archive",
                    "visibility": "public",
                    "surface_policy": "show_source",
                    "attribution_label": "Magazine archive",
                    "source_type": "pdf",
                    "pdf_filename": filename,
                    "page": page_number,
                }
            )
    finally:
        pdf.close()

    return records


def append_pdf_records_to_documents(pdf_path: Path) -> int:
    filename = pdf_path.name

    removed = remove_existing_pdf_records(filename)
    if removed:
        log(f"Removed {removed} old record(s) for {filename}")

    records = extract_pdf_pages(pdf_path)

    if not records:
        raise RuntimeError(f"No extractable text found in {filename}")

    with DOCUMENTS_FILE.open("a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    log(f"Appended {len(records)} public PDF page record(s) for {filename}")
    return len(records)


def move_current_uploads_to_queue() -> None:
    """
    Move only new PDFs from /data/magazines into /data/magazines_queue.

    /data/magazines is the public serving folder. PDFs already ingested/done
    must remain there so /magazines/<filename>.pdf links keep working. If a
    matching done copy exists, leave the public file in place.
    """
    for pdf in sorted(MAGAZINE_DIR.glob("*.pdf")):
        done_copy = DONE_DIR / pdf.name
        if done_copy.exists():
            log(f"Keeping already-ingested public PDF in active folder: {pdf.name}")
            continue

        target = QUEUE_DIR / pdf.name
        if target.exists():
            log(f"Queue already has {pdf.name}; keeping active public copy in place.")
            continue

        shutil.move(str(pdf), str(target))
        log(f"Queued new PDF for ingest: {pdf.name}")


def clear_active_folder() -> None:
    """Legacy no-op.

    Older versions emptied /data/magazines between files. That broke public PDF
    links because the FastAPI app serves magazine downloads from /data/magazines.
    Keep successful PDFs in place permanently.
    """
    return


def run_ingest_for_one(pdf_path: Path) -> bool:
    active_path = MAGAZINE_DIR / pdf_path.name

    # Move the queued PDF into the public serving folder and KEEP it there.
    # The chatbot's PDF links resolve through app.mount('/magazines', ...),
    # which points at /data/magazines.
    if active_path.exists():
        log(f"Active public PDF already exists, replacing with queued copy: {active_path.name}")
        active_path.unlink()

    shutil.move(str(pdf_path), str(active_path))
    log(f"\n=== INGESTING ONE ISSUE: {active_path.name} ===")

    try:
        append_pdf_records_to_documents(active_path)

        if RUN_LEGACY_PDF_INGEST:
            result = subprocess.run(INGEST_COMMAND)
            if result.returncode != 0:
                raise RuntimeError(f"Legacy ingest failed with return code {result.returncode}")

        log(f"SUCCESS: {active_path.name}")

        # Optional audit/backup copy only. Do NOT remove from /data/magazines.
        DONE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(active_path), str(DONE_DIR / active_path.name))
        return True

    except Exception as exc:
        log(f"FAILED: {active_path.name}: {exc}")
        FAILED_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(active_path), str(FAILED_DIR / active_path.name))
        return False


def main() -> None:
    ensure_dirs()

    log("Preparing queue...")
    move_current_uploads_to_queue()
    # Do not clear /data/magazines; it is the public PDF serving folder.

    queue = sorted(QUEUE_DIR.glob("*.pdf"))
    if MAX_FILES > 0:
        queue = queue[:MAX_FILES]

    log(f"PDFs queued for this run: {len(queue)}")
    log(f"Pause between issues: {PAUSE_SECONDS} seconds")
    log(f"Run legacy PDF ingest: {RUN_LEGACY_PDF_INGEST}")

    processed = 0
    succeeded = 0
    failed = 0

    for pdf in queue:
        processed += 1
        ok = run_ingest_for_one(pdf)

        if ok:
            succeeded += 1
            try:
                pdf.unlink()
            except Exception:
                pass
        else:
            failed += 1

        log(
            f"Progress: {processed}/{len(queue)} processed; "
            f"{succeeded} succeeded; {failed} failed"
        )

        if processed < len(queue):
            log(f"Pausing {PAUSE_SECONDS} seconds before next PDF...")
            time.sleep(PAUSE_SECONDS)

    # Do not clear /data/magazines here; it is the public PDF serving folder.

    log("\n=== BATCH INGEST COMPLETE ===")
    log(f"Processed: {processed}")
    log(f"Succeeded: {succeeded}")
    log(f"Failed: {failed}")
    log(f"Remaining queued: {len(list(QUEUE_DIR.glob('*.pdf')))}")
    log(f"Done folder: {DONE_DIR}")
    log(f"Failed folder: {FAILED_DIR}")


if __name__ == "__main__":
    main()
