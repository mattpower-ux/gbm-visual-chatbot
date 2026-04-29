from __future__ import annotations

import json
import os
import re
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DOCUMENTS_FILE = Path(os.getenv("DOCUMENTS_FILE", "/data/documents.jsonl"))
THUMBS_DIR = Path(os.getenv("THUMBS_DIR", "/data/assets/thumbs"))
MAX_WIDTH = int(os.getenv("BLOG_THUMB_MAX_WIDTH", "640"))
MAX_HEIGHT = int(os.getenv("BLOG_THUMB_MAX_HEIGHT", "360"))
JPEG_QUALITY = int(os.getenv("BLOG_THUMB_JPEG_QUALITY", "80"))
LIMIT = int(os.getenv("BLOG_THUMB_LIMIT", "0"))
TIMEOUT = int(os.getenv("BLOG_THUMB_TIMEOUT", "15"))
HEADERS = {"User-Agent": "GreenBuilderMediaBot/1.0 (+https://www.greenbuildermedia.com)"}


def safe_slug_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    slug = Path(path).name or "article"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", slug).strip("-")
    return slug or "article"


def is_public_blog_record(doc: dict) -> bool:
    url = str(doc.get("url", ""))
    visibility = doc.get("visibility", "public")
    source_type = str(doc.get("source_type", "")).lower()

    return (
        visibility == "public"
        and url.startswith("http")
        and "/magazines/" not in url
        and source_type != "pdf"
    )


def discover_image_url(article_url: str) -> str:
    try:
        res = requests.get(article_url, headers=HEADERS, timeout=TIMEOUT)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        for attr, value in [
            ("property", "og:image"),
            ("name", "twitter:image"),
            ("property", "twitter:image"),
        ]:
            tag = soup.find("meta", attrs={attr: value})
            if tag and tag.get("content"):
                return urljoin(article_url, tag["content"].strip())

        img = soup.find("img")
        if img and img.get("src"):
            return urljoin(article_url, img["src"].strip())

    except Exception as exc:
        print(f"Image discovery failed for {article_url}: {exc}")

    return ""


def download_and_save(image_url: str, out_path: Path) -> bool:
    try:
        from PIL import Image

        res = requests.get(image_url, headers=HEADERS, timeout=TIMEOUT)
        res.raise_for_status()

        img = Image.open(BytesIO(res.content)).convert("RGB")
        img.thumbnail((MAX_WIDTH, MAX_HEIGHT), Image.LANCZOS)

        canvas = Image.new("RGB", (MAX_WIDTH, MAX_HEIGHT), (238, 242, 247))
        x = (MAX_WIDTH - img.width) // 2
        y = (MAX_HEIGHT - img.height) // 2
        canvas.paste(img, (x, y))

        out_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out_path, "JPEG", quality=JPEG_QUALITY, optimize=True)
        return True

    except Exception as exc:
        print(f"Image download/save failed for {image_url}: {exc}")
        return False


def load_unique_blog_urls() -> list[str]:
    urls = []
    seen = set()

    if not DOCUMENTS_FILE.exists():
        raise FileNotFoundError(f"Could not find {DOCUMENTS_FILE}")

    with DOCUMENTS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                doc = json.loads(line)
            except Exception:
                continue

            if not is_public_blog_record(doc):
                continue

            url = str(doc.get("url", "")).strip()
            if not url or url in seen:
                continue

            seen.add(url)
            urls.append(url)

            if LIMIT > 0 and len(urls) >= LIMIT:
                break

    return urls


def main() -> None:
    try:
        import PIL  # noqa
    except ImportError as exc:
        raise SystemExit("Missing dependency. Add pillow, beautifulsoup4, and requests to requirements.txt.") from exc

    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    urls = load_unique_blog_urls()
    print(f"Found {len(urls)} public blog/article URLs")

    created = skipped = failed = no_image = 0

    for idx, url in enumerate(urls, start=1):
        out_path = THUMBS_DIR / f"{safe_slug_from_url(url)}.jpg"

        if out_path.exists() and out_path.stat().st_size > 0:
            skipped += 1
            continue

        print(f"[{idx}/{len(urls)}] {url}")
        image_url = discover_image_url(url)

        if not image_url:
            no_image += 1
            print("  No image found.")
            continue

        if download_and_save(image_url, out_path):
            created += 1
            print(f"  Created thumbnail: {out_path.name}")
        else:
            failed += 1

    print("\n=== BLOG THUMBNAIL GENERATION COMPLETE ===")
    print(f"Created: {created}")
    print(f"Skipped existing: {skipped}")
    print(f"No image found: {no_image}")
    print(f"Failed: {failed}")
    print(f"Output folder: {THUMBS_DIR}")


if __name__ == "__main__":
    main()
