from __future__ import annotations

import asyncio
import json
import random
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

from app.config import get_settings

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
DEBUG_TARGET_PATTERNS = [
    "green-builder-sustainable-brand-index-2026",
    "sustainable-brand-index-2026",
]

# Seed pages used to discover HubSpot landing/resource pages that may not appear
# in the XML sitemap. Keep this list public-site only to avoid draft/preview URLs.
LANDING_DISCOVERY_SEED_PATHS = [
    "/resources",
    "/ebooks",
    "/webinars",
    "/events",
    "/offers",
    "/vision-house",
    "/todays-homeowner",
    "/green-builder-magazine",
]

FULL_CRAWL_INTERVAL_DAYS = 5
RECENT_LOOKBACK_HOURS = 24
CRAWL_STATE_FILE_NAME = "crawl_state.json"


@dataclass
class SitemapEntry:
    url: str
    lastmod: Optional[str] = None


@dataclass
class Doc:
    url: str
    title: str
    text: str
    published_at: Optional[str]
    category: Optional[str]
    image: Optional[str] = None
    og_image: Optional[str] = None
    featured_image: Optional[str] = None
    thumbnail: Optional[str] = None
    visibility: str = "public"
    attribution_label: str = "Green Builder Media"
    surface_policy: str = "public"
    source_type: str = "article"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: str | None) -> Optional[datetime]:
    if not value:
        return None

    value = value.strip()
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def iso_now() -> str:
    return utc_now().isoformat()


def normalize_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def looks_like_debug_target(url: str) -> bool:
    lower_url = (url or "").lower()
    return any(pattern in lower_url for pattern in DEBUG_TARGET_PATTERNS)


def crawl_state_path(settings) -> Path:
    return settings.data_dir / CRAWL_STATE_FILE_NAME


def load_crawl_state(settings) -> dict:
    path = crawl_state_path(settings)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_crawl_state(settings, state: dict) -> None:
    path = crawl_state_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def should_run_full_crawl(settings) -> bool:
    state = load_crawl_state(settings)
    last_full = parse_dt(state.get("last_full_crawl_at"))
    if not last_full:
        return True
    return utc_now() - last_full >= timedelta(days=FULL_CRAWL_INTERVAL_DAYS)


def is_recent_entry(entry: SitemapEntry) -> bool:
    lastmod_dt = parse_dt(entry.lastmod)
    if not lastmod_dt:
        return False
    return utc_now() - lastmod_dt <= timedelta(hours=RECENT_LOOKBACK_HOURS)


def choose_entries_for_this_run(entries: List[SitemapEntry], full_crawl: bool) -> List[SitemapEntry]:
    if full_crawl:
        return sorted(
            entries,
            key=lambda e: parse_dt(e.lastmod) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
    recent_entries = [e for e in entries if is_recent_entry(e)]
    return sorted(
        recent_entries,
        key=lambda e: parse_dt(e.lastmod) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )


def allow_url(url: str) -> bool:
    """Return True for public GBM content pages worth indexing.

    This deliberately includes HubSpot-style landing/resource pages in addition
    to blog and magazine content, while blocking system/archive/junk pages that
    create duplicate or low-value search results.
    """
    parsed = urlparse(url)

    if parsed.netloc not in {"www.greenbuildermedia.com", "greenbuildermedia.com"}:
        return False

    url_lower = (url or "").lower()
    path_lower = parsed.path.lower()

    blocked = [
        "/_hcms/preview/",
        "/hs/manage-preferences/",
        "/hs/preferences-center/",
        "/tag/",
        "/author/",
        "/page/",
        "mailto:",
        "tel:",
        "#",
    ]
    if any(part in url_lower for part in blocked):
        return False

    allowed = [
        "/blog",
        "/magazine",
        "/ebooks",
        "/podcasts",
        "/vision-house",
        "/todays-homeowner",

        # HubSpot / landing-page / marketing-resource paths
        "/resources",
        "/lp/",
        "/landing-pages",
        "/offers",
        "/webinars",
        "/events",
        "/guides",
        "/reports",
        "/white-papers",
        "/whitepapers",
        "/case-studies",
        "/case-study",
        "/sustainable-products",
    ]
    return any(part in path_lower for part in allowed)




def is_public_indexable_url(url: str) -> bool:
    """Final safety gate for URLs saved into the public index.

    This intentionally reuses allow_url() so HubSpot preview/draft/system URLs
    are not reintroduced through canonical or og:url metadata.
    """
    if not url:
        return False

    lowered = url.lower()
    draft_or_system_markers = [
        "/_hcms/preview/",
        "/_hcms/mem/",
        "/_hcms/",
        "hs_preview=",
        "preview_key=",
        "preview=true",
        "hs_preview_key=",
        "portalid=",
        "contentid=",
        "/hs/manage-preferences/",
        "/hs/preferences-center/",
    ]
    if any(marker in lowered for marker in draft_or_system_markers):
        return False

    return allow_url(url)


def detect_source_type_from_url(url: str) -> str:
    """Classify crawled public URLs for downstream weighting and source caps."""
    u = (url or "").lower()

    if "/blog/" in u or u.rstrip("/").endswith("/blog"):
        return "blog"

    if "/magazines/" in u or "/magazine" in u or u.endswith(".pdf"):
        return "magazine"

    if any(p in u for p in [
        "/lp/",
        "/landing-pages/",
        "/resources/",
        "/ebooks/",
        "/webinars/",
        "/offers/",
        "/events/",
        "/guides/",
        "/reports/",
        "/vision-house/",
        "/todays-homeowner/",
    ]):
        return "webpage"

    return "webpage"


async def fetch_text(client: httpx.AsyncClient, url: str) -> str:
    retries = 3
    base_delay_seconds = 2.0
    for attempt in range(1, retries + 1):
        try:
            resp = await client.get(url, follow_redirects=True, timeout=30)
            if resp.status_code == 403 and attempt < retries:
                wait = base_delay_seconds * attempt + random.uniform(0.25, 1.0)
                print(f"403 on {url} (attempt {attempt}/{retries}), retrying in {wait:.1f}s")
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPStatusError:
            if attempt >= retries:
                raise
            wait = base_delay_seconds * attempt + random.uniform(0.25, 1.0)
            await asyncio.sleep(wait)
        except httpx.HTTPError:
            if attempt >= retries:
                raise
            wait = base_delay_seconds * attempt + random.uniform(0.25, 1.0)
            await asyncio.sleep(wait)
    raise RuntimeError(f"Failed to fetch {url}")


async def fetch_sitemap_urls(client: httpx.AsyncClient, sitemap_url: str) -> List[SitemapEntry]:
    xml_text = await fetch_text(client, sitemap_url)
    root = ET.fromstring(xml_text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    entries: List[SitemapEntry] = []
    if root.tag.endswith("sitemapindex"):
        sitemap_nodes = root.findall("sm:sitemap", ns)
        nested_urls = []
        for node in sitemap_nodes:
            loc_node = node.find("sm:loc", ns)
            if loc_node is not None and loc_node.text:
                nested_urls.append(loc_node.text.strip())
        for nested_url in nested_urls:
            entries.extend(await fetch_sitemap_urls(client, nested_url))
        return entries
    url_nodes = root.findall("sm:url", ns)
    for node in url_nodes:
        loc_node = node.find("sm:loc", ns)
        if loc_node is None or not loc_node.text:
            continue
        lastmod_node = node.find("sm:lastmod", ns)
        entries.append(
            SitemapEntry(
                url=loc_node.text.strip(),
                lastmod=lastmod_node.text.strip() if lastmod_node is not None and lastmod_node.text else None,
            )
        )
    return entries


def extract_best_title(soup: BeautifulSoup, extracted_title: str) -> str:
    if extracted_title:
        return extracted_title.strip()
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        return og_title["content"].strip()
    twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
    if twitter_title and twitter_title.get("content"):
        return twitter_title["content"].strip()
    h1 = soup.find("h1")
    if h1:
        h1_text = h1.get_text(" ", strip=True)
        if h1_text:
            return h1_text
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return "Untitled"


def extract_fallback_text(soup: BeautifulSoup) -> str:
    for node in [soup.find("article"), soup.find("main"), soup.find(attrs={"role": "main"}), soup.body]:
        if node:
            text = normalize_text(node.get_text("\n", strip=True))
            if text:
                return text
    return ""


def meta_content(soup: BeautifulSoup, *, property_name: str | None = None, name: str | None = None) -> str:
    if property_name:
        tag = soup.find("meta", attrs={"property": property_name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    if name:
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""




def first_nonempty(*values: str | None) -> str:
    """Return the first non-empty string value."""
    for value in values:
        if value:
            clean = str(value).strip()
            if clean:
                return clean
    return ""


def extract_json_ld_values(html: str) -> list[dict]:
    """Extract JSON-LD objects from script blocks.

    HubSpot blog pages often store datePublished/dateModified in JSON-LD,
    even when article:published_time meta tags are absent.
    """
    soup = BeautifulSoup(html, "html.parser")
    values: list[dict] = []

    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        raw = raw.strip()
        try:
            parsed = json.loads(raw)
        except Exception:
            fallback: dict[str, str] = {}
            for key in ("datePublished", "dateModified", "headline", "image"):
                match = re.search(rf'"{key}"\s*:\s*"([^"]+)"', raw)
                if match:
                    fallback[key] = match.group(1).strip()
            if fallback:
                values.append(fallback)
            continue

        if isinstance(parsed, dict):
            values.append(parsed)
            graph = parsed.get("@graph")
            if isinstance(graph, list):
                values.extend([item for item in graph if isinstance(item, dict)])
        elif isinstance(parsed, list):
            values.extend([item for item in parsed if isinstance(item, dict)])

    return values


def extract_published_at(html: str, soup: BeautifulSoup) -> str | None:
    """Extract a real publication date from HubSpot/standard article HTML."""
    for item in extract_json_ld_values(html):
        for key in ("datePublished", "dateCreated", "uploadDate", "dateModified"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    meta_candidates = [
        meta_content(soup, property_name="article:published_time"),
        meta_content(soup, name="article:published_time"),
        meta_content(soup, property_name="og:published_time"),
        meta_content(soup, name="publish_date"),
        meta_content(soup, name="published_date"),
        meta_content(soup, name="date"),
        meta_content(soup, property_name="datePublished"),
        meta_content(soup, name="datePublished"),
    ]
    for value in meta_candidates:
        if value:
            return value.strip()

    for time_tag in soup.find_all("time"):
        value = first_nonempty(
            time_tag.get("datetime"),
            time_tag.get("content"),
            time_tag.get_text(" ", strip=True),
        )
        if value:
            return value.strip()

    for pattern in [
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'"dateModified"\s*:\s*"([^"]+)"',
    ]:
        match = re.search(pattern, html, re.I | re.S)
        if match:
            return match.group(1).strip()

    return None


def extract_canonical_url(soup: BeautifulSoup, fallback_url: str) -> str:
    """Prefer the public canonical/og URL when available."""
    canonical = soup.find("link", attrs={"rel": lambda value: value and "canonical" in value})
    canonical_url = canonical.get("href", "").strip() if canonical else ""
    og_url = meta_content(soup, property_name="og:url")
    chosen = first_nonempty(og_url, canonical_url, fallback_url)
    if chosen.startswith("../../") or chosen.startswith("../"):
        return fallback_url
    return urljoin(fallback_url, chosen)

def normalize_image_url(image_url: str, page_url: str) -> str:
    image_url = (image_url or "").strip()
    if not image_url:
        return ""
    if image_url.startswith("//"):
        return "https:" + image_url
    return urljoin(page_url, image_url)


def extract_best_image(soup: BeautifulSoup, page_url: str) -> dict[str, str]:
    """Extract the best available public thumbnail image for a crawled page.

    HubSpot often lazy-loads images or stores them in srcset/picture/source tags.
    This function prioritizes explicit social-card images, then scans content
    images while filtering logos/icons/avatars/tracking pixels. It returns empty
    strings when no real image URL is found; the UI layer should handle fallback
    art. Avoiding a fake fallback here makes verification much easier.
    """

    def clean(raw_url: str | None) -> str:
        if not raw_url:
            return ""
        value = str(raw_url).strip().strip('"\'')
        if not value:
            return ""
        if value.startswith("data:"):
            return ""
        if value.startswith("//"):
            value = "https:" + value
        return urljoin(page_url, value)

    def from_srcset(srcset: str | None) -> str:
        if not srcset:
            return ""
        # Prefer the first listed candidate; HubSpot commonly puts valid URLs here.
        first = srcset.split(",")[0].strip()
        if not first:
            return ""
        return first.split(" ")[0].strip()

    def looks_like_bad_image(candidate: str) -> bool:
        if not candidate:
            return True
        c = candidate.lower()
        bad_markers = [
            "logo",
            "icon",
            "avatar",
            "gravatar",
            "sprite",
            "pixel",
            "tracking",
            "transparent",
            "spacer",
            "blank.gif",
            "favicon",
            "loader",
        ]
        return any(marker in c for marker in bad_markers)

    def candidate_from_img(img) -> str:
        if not img:
            return ""
        raw = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-lazy-src")
            or img.get("data-original")
            or img.get("data-ll-src")
            or img.get("data-hs-cos-general-type")
            or from_srcset(img.get("srcset"))
            or from_srcset(img.get("data-srcset"))
            or ""
        )
        return clean(raw)

    def candidate_from_source(source) -> str:
        if not source:
            return ""
        raw = (
            source.get("srcset")
            or source.get("data-srcset")
            or source.get("src")
            or source.get("data-src")
            or ""
        )
        return clean(from_srcset(raw) or raw)

    og_image = clean(
        meta_content(soup, property_name="og:image")
        or meta_content(soup, property_name="og:image:secure_url")
    )
    twitter_image = clean(
        meta_content(soup, name="twitter:image")
        or meta_content(soup, property_name="twitter:image")
    )

    json_ld_image = ""
    for item in extract_json_ld_values(str(soup)):
        raw_image = item.get("image")
        if isinstance(raw_image, str):
            json_ld_image = clean(raw_image)
        elif isinstance(raw_image, list) and raw_image:
            first = raw_image[0]
            if isinstance(first, str):
                json_ld_image = clean(first)
            elif isinstance(first, dict):
                json_ld_image = clean(first.get("url") or first.get("contentUrl"))
        elif isinstance(raw_image, dict):
            json_ld_image = clean(raw_image.get("url") or raw_image.get("contentUrl"))
        if json_ld_image and not looks_like_bad_image(json_ld_image):
            break

    def find_best_content_image(container) -> str:
        if not container:
            return ""

        for source in container.find_all("source"):
            candidate = candidate_from_source(source)
            if candidate and not looks_like_bad_image(candidate):
                return candidate

        for img in container.find_all("img"):
            candidate = candidate_from_img(img)
            if candidate and not looks_like_bad_image(candidate):
                return candidate

        # Last-chance HubSpot/CMS pattern: image URLs embedded in inline styles.
        for node in container.find_all(style=True):
            style = node.get("style") or ""
            match = re.search(r"url\((['\"]?)(.*?)\1\)", style)
            if match:
                candidate = clean(match.group(2))
                if candidate and not looks_like_bad_image(candidate):
                    return candidate

        return ""

    article = soup.find("article")
    main = soup.find("main")
    role_main = soup.find(attrs={"role": "main"})
    body = soup.body

    featured_image = (
        find_best_content_image(article)
        or find_best_content_image(main)
        or find_best_content_image(role_main)
        or find_best_content_image(body)
    )

    best = ""
    for candidate in [og_image, twitter_image, json_ld_image, featured_image]:
        if candidate and not looks_like_bad_image(candidate):
            best = candidate
            break

    return {
        "image": best,
        "og_image": og_image if og_image and not looks_like_bad_image(og_image) else "",
        "featured_image": featured_image if featured_image and not looks_like_bad_image(featured_image) else "",
        "thumbnail": best,
    }


def extract_metadata(html: str, url: str) -> Doc | None:
    downloaded = trafilatura.extract(html, include_links=False, include_comments=False, output_format="json")
    soup = BeautifulSoup(html, "html.parser")
    extracted_title = ""
    extracted_text = ""
    if downloaded:
        try:
            data = json.loads(downloaded)
            extracted_title = (data.get("title") or "").strip()
            extracted_text = normalize_text((data.get("text") or "").strip())
        except Exception:
            extracted_title = ""
            extracted_text = ""
    title = extract_best_title(soup, extracted_title)
    text = extracted_text
    if not text or len(text) < 500:
        fallback_text = extract_fallback_text(soup)
        if len(fallback_text) > len(text):
            text = fallback_text
    if not text or len(text) < 500:
        return None
    published_at = extract_published_at(html, soup)
    canonical_url = extract_canonical_url(soup, url)

    # Do not let HubSpot preview/draft/system URLs back into the public index
    # through canonical or og:url metadata. This preserves the earlier fix that
    # stopped unpublished draft blog links from appearing in chatbot answers.
    if not is_public_indexable_url(canonical_url):
        return None

    category = None
    og_section = soup.find("meta", attrs={"property": "article:section"})
    if og_section and og_section.get("content"):
        category = og_section["content"].strip()
    images = extract_best_image(soup, canonical_url)
    return Doc(
        url=canonical_url,
        title=title,
        text=text,
        published_at=published_at,
        category=category,
        image=images.get("image") or None,
        og_image=images.get("og_image") or None,
        featured_image=images.get("featured_image") or None,
        thumbnail=images.get("thumbnail") or None,
        visibility="public",
        attribution_label="Green Builder Media",
        surface_policy="public",
        source_type=detect_source_type_from_url(canonical_url),
    )


def load_existing_docs(docs_path: Path) -> Dict[str, Doc]:
    if not docs_path.exists():
        return {}
    docs: Dict[str, Doc] = {}
    with docs_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
                url = raw.get("url", "")
                if not url or not is_public_indexable_url(url):
                    continue
                docs[url] = Doc(
                    url=url,
                    title=raw.get("title", "Untitled"),
                    text=raw.get("text", ""),
                    published_at=raw.get("published_at"),
                    category=raw.get("category"),
                    image=raw.get("image"),
                    og_image=raw.get("og_image"),
                    featured_image=raw.get("featured_image"),
                    thumbnail=raw.get("thumbnail"),
                    visibility=raw.get("visibility", "public"),
                    attribution_label=raw.get("attribution_label", "Green Builder Media"),
                    surface_policy=raw.get("surface_policy", "public"),
                    source_type=detect_source_type_from_url(url),
                )
            except Exception:
                continue
    return docs


def save_docs(docs_path: Path, docs_by_url: Dict[str, Doc]) -> None:
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    with docs_path.open("w", encoding="utf-8") as f:
        for url in sorted(docs_by_url.keys()):
            if not is_public_indexable_url(url):
                continue
            doc = docs_by_url[url]
            doc.source_type = detect_source_type_from_url(doc.url)
            f.write(json.dumps(asdict(doc), ensure_ascii=False) + "\n")




async def discover_landing_links(client: httpx.AsyncClient, base_url: str) -> list[SitemapEntry]:
    """Discover public landing/resource URLs from known GBM hub pages.

    The XML sitemap is blog-heavy, so this light link crawl finds public HubSpot
    landing pages, resource pages, offers, webinar pages, and VISION House pages
    that would otherwise be underrepresented. Draft/preview links are still
    blocked by is_public_indexable_url().
    """
    discovered: dict[str, SitemapEntry] = {}
    root = (base_url or "https://www.greenbuildermedia.com").rstrip("/")

    for path in LANDING_DISCOVERY_SEED_PATHS:
        seed_url = urljoin(root + "/", path.lstrip("/"))
        if not is_public_indexable_url(seed_url):
            continue
        try:
            html = await fetch_text(client, seed_url)
        except Exception as exc:
            print(f"Seed discovery skipped {seed_url}: {exc}")
            continue

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href:
                continue
            absolute = urljoin(seed_url, href).split("#", 1)[0]
            if not is_public_indexable_url(absolute):
                continue
            # Prefer landing/resource-ish pages, but keep VISION/Today pages too.
            if detect_source_type_from_url(absolute) == "webpage":
                discovered[absolute] = SitemapEntry(url=absolute, lastmod=None)

        await asyncio.sleep(random.uniform(0.4, 0.9))

    return list(discovered.values())

async def main() -> None:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    docs_path: Path = settings.docs_file
    full_crawl = should_run_full_crawl(settings)
    state = load_crawl_state(settings)
    headers = {
        "User-Agent": settings.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": settings.site_base_url,
    }
    async with httpx.AsyncClient(headers=headers) as client:
        sitemap_entries = await fetch_sitemap_urls(client, settings.sitemap_url)
        sitemap_entries = [e for e in sitemap_entries if allow_url(e.url)]
        discovered_entries = await discover_landing_links(client, settings.site_base_url)
        if discovered_entries:
            print(f"Landing/resource URLs discovered from seed pages: {len(discovered_entries)}")
            sitemap_entries.extend(discovered_entries)
        deduped: Dict[str, SitemapEntry] = {}
        for entry in sitemap_entries:
            deduped[entry.url] = entry
        all_entries = list(deduped.values())
        webpage_candidates = sum(1 for e in all_entries if detect_source_type_from_url(e.url) == "webpage")
        entries_to_crawl = choose_entries_for_this_run(all_entries, full_crawl)
        mode = "FULL" if full_crawl else "RECENT"
        print(f"Crawl mode: {mode}")
        print(f"Candidate URLs total: {len(all_entries)}")
        print(f"Candidate webpage/landing URLs: {webpage_candidates}")
        print(f"URLs selected this run: {len(entries_to_crawl)}")
        existing_docs = load_existing_docs(docs_path)
        results_by_url: Dict[str, Doc] = existing_docs.copy()
        kept_count = 0
        image_count = 0
        for idx, entry in enumerate(entries_to_crawl, start=1):
            url = entry.url
            try:
                if looks_like_debug_target(url):
                    print(f"DEBUG TARGET URL REACHED: {url}")
                html = await fetch_text(client, url)
                doc = extract_metadata(html, url)
                if doc:
                    # Store by canonical public URL so preview/redirect variants do not linger.
                    results_by_url[doc.url] = doc
                    kept_count += 1
                    if doc.image and str(doc.image).startswith("http"):
                        image_count += 1
                    print(f"[{idx}/{len(entries_to_crawl)}] kept {url}" + (" [image]" if doc.image else ""))
                    if looks_like_debug_target(url):
                        print(f"DEBUG TARGET TITLE: {doc.title}")
                        print(f"DEBUG TARGET TEXT LENGTH: {len(doc.text)}")
                        print(f"DEBUG TARGET PUBLISHED_AT: {doc.published_at}")
                        print(f"DEBUG TARGET IMAGE: {doc.image}")
                        print(f"DEBUG TARGET TEXT PREVIEW: {doc.text[:500]}")
                else:
                    print(f"[{idx}/{len(entries_to_crawl)}] skipped {url}")
                    if looks_like_debug_target(url):
                        print("DEBUG TARGET WAS SKIPPED AFTER EXTRACTION")
                await asyncio.sleep(random.uniform(0.6, 1.2))
            except Exception as exc:
                print(f"[{idx}/{len(entries_to_crawl)}] error {url}: {exc}")
                await asyncio.sleep(random.uniform(1.5, 3.0))
    save_docs(docs_path, results_by_url)
    state["last_crawl_at"] = iso_now()
    state["last_crawl_mode"] = "full" if full_crawl else "recent"
    state["last_candidate_url_count"] = len(all_entries)
    state["last_selected_url_count"] = len(entries_to_crawl)
    state["last_saved_doc_count"] = len(results_by_url)
    state["last_kept_this_run"] = kept_count
    state["last_with_image_this_run"] = image_count
    if full_crawl:
        state["last_full_crawl_at"] = iso_now()
    save_crawl_state(settings, state)
    print(f"Saved {len(results_by_url)} documents to {docs_path}")
    print(f"Kept this run: {kept_count}")
    print(f"Records with images this run: {image_count}")


if __name__ == "__main__":
    asyncio.run(main())
