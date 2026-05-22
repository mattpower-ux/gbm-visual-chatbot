from __future__ import annotations

import io
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


HOT_TAKE_CATEGORY_URL = "https://www.greenbuildermedia.com/blog/topic/cognition-weekly-hot-take"
SMART_DATA_URL = "https://www.greenbuildermedia.com/cognition-smart-data"

DATA_DIR = Path("/data")
OUT_PATH = DATA_DIR / "cognition_hot_takes.json"
ALLOWLIST_PATH = DATA_DIR / "cognition_hot_take_image_allowlist.json"
OCR_CACHE_DIR = DATA_DIR / "cognition_hot_take_ocr_cache"

ENABLE_HOT_TAKE_OCR = os.getenv("ENABLE_HOT_TAKE_OCR", "true").strip().lower() in {
    "1", "true", "yes", "on",
}
HOT_TAKE_OCR_MAX_IMAGE_BYTES = int(os.getenv("HOT_TAKE_OCR_MAX_IMAGE_BYTES", str(8 * 1024 * 1024)))
HOT_TAKE_OCR_TIMEOUT_SECONDS = int(os.getenv("HOT_TAKE_OCR_TIMEOUT_SECONDS", "45"))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


@dataclass
class HotTakeGraphic:
    article_title: str
    article_url: str
    image_url: str
    alt: str
    nearby_text: str
    keywords: list[str]
    ocr_text: str = ""
    ocr_keywords: list[str] | None = None
    chart_title: str = ""
    ocr_error: str = ""
    smart_data_url: str = SMART_DATA_URL


def fetch(url: str) -> str:
    with httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_url(url: str) -> str:
    """
    Normalize HubSpot image URLs so different width/height query variants match.
    Example:
    image.png?width=1200&name=image.png
    image.png?width=2400&height=1500&name=image.png
    both become:
    image.png
    """
    raw = (url or "").strip()
    parsed = urlparse(raw)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def cache_key_for_url(url: str) -> str:
    import hashlib

    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()[:24]


def load_allowlist() -> set[str]:
    if not ALLOWLIST_PATH.exists():
        return set()

    try:
        data = json.loads(ALLOWLIST_PATH.read_text())
        return {normalize_url(u) for u in data.get("allowed_image_urls", []) if u}
    except Exception as exc:
        print(f"WARNING: Could not read allowlist: {exc}")
        return set()


def extract_category_article_urls(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])

        if "/blog/" not in href:
            continue

        if "/blog/topic/" in href:
            continue

        if "/blog/author/" in href:
            continue

        parsed = urlparse(href)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        if clean_url not in urls:
            urls.append(clean_url)

    return urls


def nearby_text_for_image(img) -> str:
    chunks: list[str] = []
    parent = img.find_parent()

    for _ in range(4):
        if not parent:
            break

        text = clean_text(parent.get_text(" ", strip=True))
        if text:
            chunks.append(text)

        parent = parent.find_parent()

    return clean_text(" ".join(chunks))[:1200]


def extract_keywords(*parts: str, limit: int = 28) -> list[str]:
    text = " ".join(parts).lower()
    words = re.findall(r"[a-z][a-z0-9\-]{2,}", text)

    stop = {
        "with", "that", "this", "from", "have", "will", "your", "more",
        "about", "green", "builder", "media", "cognition", "smart", "data",
        "home", "homes", "house", "housing", "buyers", "buyer", "consumer", "consumers",
        "chart", "graphic", "figure", "percent", "share", "respondents", "most",
        "interested", "features", "feature", "sustainable", "sustainability",
    }

    counts: dict[str, int] = {}
    for w in words:
        if w in stop:
            continue
        if len(w) < 3:
            continue
        counts[w] = counts.get(w, 0) + 1

    return [
        word for word, _count in sorted(
            counts.items(),
            key=lambda kv: kv[1],
            reverse=True,
        )[:limit]
    ]


def best_chart_title_from_ocr(ocr_text: str) -> str:
    """Return the most title-like OCR line without overcomplicating chart parsing."""
    lines = [clean_text(line) for line in (ocr_text or "").splitlines()]
    lines = [line for line in lines if len(line) >= 8]

    if not lines:
        return ""

    # Prefer early, title-like lines with letters and without too many numbers.
    for line in lines[:8]:
        alpha_count = len(re.findall(r"[A-Za-z]", line))
        digit_count = len(re.findall(r"\d", line))
        if alpha_count >= 8 and digit_count <= max(3, alpha_count // 2):
            return line[:180]

    return lines[0][:180]


def run_ocr_on_image_url(image_url: str) -> tuple[str, str, str]:
    """OCR an image URL and return (ocr_text, chart_title, ocr_error).

    This is intentionally optional. If pytesseract or the system tesseract binary
    is unavailable, the crawler still writes the Hot Take JSON and records the
    OCR error so the admin sync does not fail.
    """
    if not ENABLE_HOT_TAKE_OCR:
        return "", "", "OCR disabled by ENABLE_HOT_TAKE_OCR."

    OCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = OCR_CACHE_DIR / f"{cache_key_for_url(image_url)}.json"

    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            return (
                clean_text(cached.get("ocr_text", "")),
                clean_text(cached.get("chart_title", "")),
                clean_text(cached.get("ocr_error", "")),
            )
        except Exception:
            pass

    try:
        import pytesseract
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    except Exception as exc:
        msg = (
            "OCR libraries unavailable. Add Pillow and pytesseract to requirements; "
            "install the tesseract system package if Render supports apt.txt. "
            f"Original error: {exc}"
        )
        cache_file.write_text(json.dumps({"ocr_text": "", "chart_title": "", "ocr_error": msg}, indent=2), encoding="utf-8")
        return "", "", msg

    try:
        with httpx.Client(
            timeout=HOT_TAKE_OCR_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = client.get(image_url)
            response.raise_for_status()
            image_bytes = response.content

        if len(image_bytes) > HOT_TAKE_OCR_MAX_IMAGE_BYTES:
            msg = f"Image too large for OCR: {len(image_bytes)} bytes."
            cache_file.write_text(json.dumps({"ocr_text": "", "chart_title": "", "ocr_error": msg}, indent=2), encoding="utf-8")
            return "", "", msg

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Light preprocessing helps chart text without distorting graphics too much.
        gray = ImageOps.grayscale(image)
        gray = ImageEnhance.Contrast(gray).enhance(1.8)
        gray = gray.filter(ImageFilter.SHARPEN)

        ocr_raw = pytesseract.image_to_string(gray, config="--psm 6")
        ocr_text = clean_text(ocr_raw)
        chart_title = best_chart_title_from_ocr(ocr_raw)

        cache_file.write_text(
            json.dumps(
                {
                    "image_url": image_url,
                    "ocr_text": ocr_text,
                    "chart_title": chart_title,
                    "ocr_error": "",
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return ocr_text, chart_title, ""

    except Exception as exc:
        msg = str(exc)
        cache_file.write_text(json.dumps({"ocr_text": "", "chart_title": "", "ocr_error": msg}, indent=2), encoding="utf-8")
        return "", "", msg


def extract_graphics_from_article(
    article_url: str,
    allowlist: set[str],
) -> list[HotTakeGraphic]:
    html = fetch(article_url)
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    h1 = soup.find("h1")
    if h1:
        title = clean_text(h1.get_text(" ", strip=True))

    if not title:
        og = soup.find("meta", property="og:title")
        title = clean_text(og.get("content", "")) if og else article_url

    graphics: list[HotTakeGraphic] = []

    for img in soup.find_all("img"):
        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-lazy-src")
            or ""
        )

        if not src:
            continue

        image_url = normalize_url(urljoin(article_url, src))

        if image_url.startswith("data:"):
            continue

        # STRICT MODE:
        # If the allowlist has entries, keep ONLY images in that allowlist.
        if allowlist and image_url not in allowlist:
            continue

        alt = clean_text(img.get("alt", ""))
        nearby = nearby_text_for_image(img)

        # If no allowlist exists, fall back to a conservative hard-reject list.
        if not allowlist:
            blob = " ".join([image_url, alt, nearby]).lower()

            hard_reject = [
                "logo",
                "headshot",
                "author",
                "avatar",
                "profile",
                "facebook",
                "twitter",
                "linkedin",
                "instagram",
                "youtube",
                "icon",
                "button",
                "advertisement",
                "sponsor",
                "sustainable product of the year",
                "product of the year",
                "sustainable brand index",
                "brand index",
                "vision house",
                "guest columnist",
            ]

            if any(term in blob for term in hard_reject):
                continue

        ocr_text, chart_title, ocr_error = run_ocr_on_image_url(image_url)
        combined_keywords = extract_keywords(title, nearby, alt, ocr_text, chart_title)
        ocr_keywords = extract_keywords(ocr_text, chart_title, limit=24)

        graphics.append(
            HotTakeGraphic(
                article_title=title,
                article_url=article_url,
                image_url=image_url,
                alt=alt,
                nearby_text=nearby,
                keywords=combined_keywords,
                ocr_text=ocr_text,
                ocr_keywords=ocr_keywords,
                chart_title=chart_title,
                ocr_error=ocr_error,
            )
        )

    return graphics


def crawl_all_pages(max_pages: int = 5) -> list[str]:
    all_urls: list[str] = []

    for page in range(1, max_pages + 1):
        if page == 1:
            url = HOT_TAKE_CATEGORY_URL
        else:
            url = f"{HOT_TAKE_CATEGORY_URL}/page/{page}"

        print(f"Fetching category page: {url}")

        try:
            html = fetch(url)
        except Exception as exc:
            print(f"Stopped at page {page}: {exc}")
            break

        urls = extract_category_article_urls(html, url)

        if not urls:
            break

        for u in urls:
            if u not in all_urls:
                all_urls.append(u)

        time.sleep(0.5)

    return all_urls


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    allowlist = load_allowlist()

    print(f"Loaded allowlist with {len(allowlist)} image(s)")
    if allowlist:
        print("STRICT ALLOWLIST MODE: only allowlisted images will be kept.")
    else:
        print("NO ALLOWLIST FOUND: crawler will use broad fallback filtering.")

    print(f"Hot Take OCR enabled: {ENABLE_HOT_TAKE_OCR}")

    article_urls = crawl_all_pages(max_pages=5)

    print(f"Found {len(article_urls)} Hot Take article URLs")

    graphics: list[HotTakeGraphic] = []

    for i, article_url in enumerate(article_urls, start=1):
        print(f"[{i}/{len(article_urls)}] Extracting graphics from {article_url}")

        try:
            found = extract_graphics_from_article(article_url, allowlist)
            with_ocr = sum(1 for g in found if g.ocr_text)
            print(f"  found {len(found)} approved image(s); OCR text found for {with_ocr}")
            graphics.extend(found)
        except Exception as exc:
            print(f"  failed: {exc}")

        time.sleep(0.5)

    payload = {
        "source": HOT_TAKE_CATEGORY_URL,
        "strict_allowlist_mode": bool(allowlist),
        "allowlist_count": len(allowlist),
        "ocr_enabled": ENABLE_HOT_TAKE_OCR,
        "ocr_cache_dir": str(OCR_CACHE_DIR),
        "count": len(graphics),
        "graphics": [asdict(g) for g in graphics],
    }

    OUT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Wrote {len(graphics)} graphics to {OUT_PATH}")


if __name__ == "__main__":
    main()
