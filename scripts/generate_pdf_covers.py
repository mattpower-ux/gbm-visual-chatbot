from __future__ import annotations

import os
import re
from pathlib import Path

PDF_DIRS = [
    Path("/data/magazines"),
    Path("/data/magazines_done"),
    Path("/data/pdf_done"),
]
COVERS_DIR = Path(os.getenv("COVERS_DIR", "/data/assets/covers"))
MAX_WIDTH = int(os.getenv("PDF_COVER_MAX_WIDTH", "420"))
JPEG_QUALITY = int(os.getenv("PDF_COVER_JPEG_QUALITY", "82"))


def safe_stem(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-")
    return stem or "magazine"


def main() -> None:
    try:
        import fitz
        from PIL import Image
    except ImportError as exc:
        raise SystemExit("Missing dependency. Add pymupdf and pillow to requirements.txt.") from exc

    COVERS_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = []
    seen = set()

    for folder in PDF_DIRS:
        if not folder.exists():
            continue
        for pdf in sorted(folder.glob("*.pdf")):
            if pdf.name not in seen:
                pdfs.append(pdf)
                seen.add(pdf.name)

    print(f"Found {len(pdfs)} PDFs across PDF folders")

    created = skipped = failed = 0

    for pdf_path in pdfs:
        out_path = COVERS_DIR / f"{safe_stem(pdf_path.name)}.jpg"

        if out_path.exists() and out_path.stat().st_size > 0:
            skipped += 1
            continue

        try:
            doc = fitz.open(pdf_path)
            page = doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            if img.width > MAX_WIDTH:
                ratio = MAX_WIDTH / img.width
                img = img.resize((MAX_WIDTH, int(img.height * ratio)), Image.LANCZOS)

            img.save(out_path, "JPEG", quality=JPEG_QUALITY, optimize=True)
            doc.close()

            print(f"Created cover: {out_path.name}")
            created += 1

        except Exception as exc:
            print(f"FAILED {pdf_path.name}: {exc}")
            failed += 1

    print(f"Created: {created}")
    print(f"Skipped existing: {skipped}")
    print(f"Failed: {failed}")
