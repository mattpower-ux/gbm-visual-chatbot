from __future__ import annotations

import json
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


def image_looks_like_data_graphic(img_url: str, alt: str, nearby_text: str) -> bool:
    blob = " ".join([img_url, alt, nearby_text]).lower()

    reject_terms = [
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
        "ad-",
        "advertisement",
        "sponsor",
        "hero",
        "thumbnail",

        # Product award imagery
        "sustainable product of the year",
        "product of the year",
        "award winner",
        "winner",
        "best product",
        "top product",

        # Brand index scorecards / logos
        "sustainable brand index",
        "brand index",
        "brand survey",
        "brand rankings",
        "manufacturer rankings",

        # Known non-Hot-Take / non-chart article imagery
        "arctic cold",
        "vision house",
        "transcend",
        "guest columnist",

        # Typical non-chart photography
        "kitchen",
        "bathroom",
        "window",
        "hvac",
        "heat pump",
        "solar panel",
        "roofing",
        "appliance",
        "home exterior",
        "builder",
        "family",
        "living room",
    ]

    prefer_terms = [
        "chart",
        "graph",
        "bar",
        "pie",
        "line",
        "data",
        "survey",
        "responses",
        "percent",
        "percentage",
        "smart data",
        "cognition",
        "trend",
        "ranking",
        "index",
        "table",
        "figure",
        "infographic",
    ]

    if any(term in blob for term in reject_terms):
        return False

    if any(term in blob for term in prefer_terms):
        return True

    return False


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


def extract_keywords(title: str, nearby_text: str, alt: str) -> list[str]:
    text = f"{title} {nearby_text} {alt}".lower()

    words = re.findall(r"[a-z][a-z\-]{3,}", text)

    stop = {
        "with", "that", "this", "from", "have", "will", "your", "more",
        "about", "green", "builder", "media", "cognition", "smart", "data",
        "home", "homes", "house", "housing", "buyers", "consumer", "consumers",
    }

    counts: dict[str, int] = {}
    for w in words:
        if w in stop:
            continue
        counts[w] = counts.get(w, 0) + 1

    return [
        word for word, _count in sorted(
            counts.items(),
            key=lambda kv: kv[1],
            reverse=True,
        )[:20]
    ]


def extract_graphics_from_article(article_url: str) -> list[HotTakeGraphic]:
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

        image_url = urljoin(article_url, src)

        if image_url.startswith("data:"):
            continue

        alt = clean_text(img.get("alt", ""))
        nearby = nearby_text_for_image(img)

        if not image_looks_like_data_graphic(image_url, alt, nearby):
            continue

        graphics.append(
            HotTakeGraphic(
                article_title=title,
                article_url=article_url,
                image_url=image_url,
                alt=alt,
                nearby_text=nearby,
                keywords=extract_keywords(title, nearby, alt),
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

    article_urls = crawl_all_pages(max_pages=5)

    print(f"Found {len(article_urls)} Hot Take article URLs")

    graphics: list[HotTakeGraphic] = []

    for i, article_url in enumerate(article_urls, start=1):
        print(f"[{i}/{len(article_urls)}] Extracting graphics from {article_url}")

        try:
            found = extract_graphics_from_article(article_url)
            print(f"  found {len(found)} likely data graphic(s)")
            graphics.extend(found)
        except Exception as exc:
            print(f"  failed: {exc}")

        time.sleep(0.5)

    payload = {
        "source": HOT_TAKE_CATEGORY_URL,
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
