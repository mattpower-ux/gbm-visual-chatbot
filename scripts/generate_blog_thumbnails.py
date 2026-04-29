from __future__ import annotations

import json
import os
import re
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DOCUMENTS_FILE = Path("/data/documents.jsonl")
THUMBS_DIR = Path("/data/assets/thumbs")
MAX_WIDTH = 640
MAX_HEIGHT = 360
JPEG_QUALITY = 80
TIMEOUT = 20
LIMIT = int(os.getenv("BLOG_THUMB_LIMIT", "0"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0"
}


def safe_slug_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    slug = Path(path).name or "article"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", slug).strip("-")
    return slug or "article"


def is_blog(doc: dict) -> bool:
    url = str(doc.get("url", ""))
    return (
        doc.get("visibility", "public") == "public"
        and url.startswith("http")
        and "/magazines/" not in url
        and str(doc.get("source_type", "")).lower() != "pdf"
    )


def stored_image(doc: dict) -> str:
    for key in ["image", "og_image", "featured_image", "thumbnail", "featuredImage"]:
        val = doc.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


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
        print(f"Live page image discovery failed for {article_url}: {exc}")

    return ""


def save_image(image_url: str, out_path: Path) -> bool:
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
        print(f"Image save failed for {image_url}: {exc}")
        return False


def load_records() -> list[dict]:
    records = []
    seen = set()

    with DOCUMENTS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                doc = json.loads(line)
            except Exception:
                continue

            if not is_blog(doc):
                continue

            url = str(doc.get("url", "")).strip()
            if not url or url in seen:
                continue

            seen.add(url)
            records.append(doc)

            if LIMIT > 0 and len(records) >= LIMIT:
                break

    return records


def main() -> None:
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    records = load_records()
    print(f"Found {len(records)} public blog/article records")

    created = skipped = failed = no_image = 0

    for idx, doc in enumerate(records, start=1):
        url = str(doc.get("url", ""))
        slug = safe_slug_from_url(url)
        out_path = THUMBS_DIR / f"{slug}.jpg"

        if out_path.exists() and out_path.stat().st_size > 0:
            skipped += 1
            continue

        print(f"[{idx}/{len(records)}] {url}")

        image_url = stored_image(doc)

        if not image_url:
            image_url = discover_image_url(url)

        if not image_url:
            no_image += 1
            print("  No image found.")
            continue

        if save_image(image_url, out_path):
            created += 1
            print(f"  Created thumbnail: {out_path.name}")
        else:
            failed += 1

    print("Created:", created)
    print("Skipped existing:", skipped)
    print("No image found:", no_image)
    print("Failed:", failed)

if __name__ == "__main__":
    main()
