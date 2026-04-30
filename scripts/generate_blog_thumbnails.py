from pathlib import Path
from urllib.parse import urlparse, urljoin
import re
import html
import requests
import lancedb
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO

THUMB_DIR = Path("/data/assets/thumbs")
THUMB_DIR.mkdir(parents=True, exist_ok=True)

BAD = [
    "logo", "cta", "icon", "avatar", "headshot", "pixel", "spacer",
    "team_photos", "author", "profile"
]

def slug_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    slug = Path(path).name or "article"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", slug).strip("-") or "article"
    return f"{slug}.jpg"

def clean_url(u: str, base: str) -> str:
    if not u:
        return ""
    u = html.unescape(u).strip()
    if "," in u and " " in u:
        u = u.split(",")[0].strip().split(" ")[0]
    elif " " in u:
        u = u.split(" ")[0]
    return urljoin(base, u)

def looks_bad(u: str) -> bool:
    low = u.lower()
    return any(b in low for b in BAD)

def score_image(kind: str, u: str) -> int:
    low = u.lower()
    score = 0

    if kind == "meta":
        score += 100
    if "featured" in low:
        score += 80
    if "/hubfs/" in low:
        score += 40
    if "hs-fs" in low:
        score += 25
    if ".jpg" in low or ".jpeg" in low:
        score += 15
    if ".webp" in low:
        score += 10
    if "width=" in low:
        score += 5

    if looks_bad(u):
        score -= 500
    if re.search(r"/blog/\d+$", low):
        score -= 500

    return score

def find_best_image(url: str) -> str:
    r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    found = []

    for tag in soup.find_all("meta"):
        k = (tag.get("property") or tag.get("name") or "").lower()
        v = tag.get("content")
        if v and "image" in k:
            found.append(("meta", clean_url(v, url)))

    for img in soup.find_all("img"):
        for attr in ["src", "data-src", "data-lazy-src", "data-original"]:
            if img.get(attr):
                found.append((attr, clean_url(img.get(attr), url)))

        for attr in ["srcset", "data-srcset"]:
            if img.get(attr):
                parts = [p.strip().split(" ")[0] for p in img.get(attr).split(",")]
                for p in parts:
                    found.append((attr, clean_url(p, url)))

    raw = re.findall(
        r'https?://[^"\')\s<>]+?\.(?:webp|jpg|jpeg|png)(?:\?[^"\')\s<>]*)?',
        r.text,
        re.I,
    )
    for u in raw:
        found.append(("raw", clean_url(u, url)))

    dedup = []
    seen = set()

    for kind, u in found:
        if not u or u in seen:
            continue

        seen.add(u)

        if looks_bad(u):
            continue

        if not re.search(r"\.(webp|jpg|jpeg|png)(\?|$)", u, re.I):
            continue

        dedup.append((score_image(kind, u), kind, u))

    if not dedup:
        return ""

    dedup.sort(reverse=True)
    return dedup[0][2]

def save_thumb(image_url: str, dest: Path) -> bool:
    r = requests.get(image_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()

    img = Image.open(BytesIO(r.content)).convert("RGB")
    img.thumbnail((640, 360))

    canvas = Image.new("RGB", (640, 360), (240, 240, 240))
    x = (640 - img.width) // 2
    y = (360 - img.height) // 2
    canvas.paste(img, (x, y))
    canvas.save(dest, "JPEG", quality=82, optimize=True)

    return True

def main():
    db = lancedb.connect("/data/lancedb")
    table = db.open_table("greenbuilder_chunks")
    df = table.to_pandas()

    urls = sorted(set(
        str(u) for u in df["url"].dropna()
        if str(u).startswith("https://www.greenbuildermedia.com/blog/")
    ))

    print(f"Found {len(urls)} blog URLs")

    made = 0
    skipped = 0
    failed = 0

    for i, url in enumerate(urls, start=1):
        filename = slug_from_url(url)
        dest = THUMB_DIR / filename

        if dest.exists() and dest.stat().st_size > 1000:
            skipped += 1
            continue

        try:
            image_url = find_best_image(url)

            if not image_url:
                print(f"[{i}/{len(urls)}] no usable image: {url}")
                failed += 1
                continue

            save_thumb(image_url, dest)
            made += 1
            print(f"[{i}/{len(urls)}] saved {filename} <- {image_url}")

        except Exception as exc:
            failed += 1
            print(f"[{i}/{len(urls)}] failed {url}: {exc}")

    print({
        "made": made,
        "skipped": skipped,
        "failed": failed,
        "thumb_dir": str(THUMB_DIR),
    })

if __name__ == "__main__":
    main()
