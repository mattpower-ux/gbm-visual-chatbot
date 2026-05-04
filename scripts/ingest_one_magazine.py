from __future__ import annotations

import hashlib
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

try:
    from PIL import Image
except Exception:  # Optional dependency; cover generation fails open.
    Image = None

import lancedb
from openai import OpenAI
from pypdf import PdfReader

MAGAZINE_DIR = Path(os.getenv("MAGAZINE_DIR", "/data/magazines"))
ASSETS_DIR = Path(os.getenv("ASSETS_DIR", "/data/assets"))
COVERS_DIR = ASSETS_DIR / "covers"
LANCEDB_DIR = os.getenv("LANCEDB_DIR", "/data/lancedb")
TABLE_NAME = os.getenv("LANCEDB_TABLE", "greenbuilder_chunks")
PUBLIC_MAGAZINE_PREFIX = os.getenv("PUBLIC_MAGAZINE_PREFIX", "/magazines")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
BATCH_SIZE = int(os.getenv("MAGAZINE_INGEST_BATCH_SIZE", "20"))

# Chunk tuning. Smaller chunks make PDF page citations more precise.
PDF_CHUNK_SIZE = int(os.getenv("PDF_CHUNK_SIZE", "850"))
PDF_CHUNK_OVERLAP = int(os.getenv("PDF_CHUNK_OVERLAP", "120"))
PDF_MIN_CHUNK_CHARS = int(os.getenv("PDF_MIN_CHUNK_CHARS", "180"))

# Keep junk filtering on by default. Set PDF_SKIP_JUNK=false if you need a full archive ingest.
PDF_SKIP_JUNK = os.getenv("PDF_SKIP_JUNK", "true").strip().lower() in {"1", "true", "yes", "on"}

# OCR fallback for image-heavy PDFs/flyers. Requires PyMuPDF + pytesseract
# and the tesseract system binary to be available in the Render environment.
PDF_ENABLE_OCR = os.getenv("PDF_ENABLE_OCR", "true").strip().lower() in {"1", "true", "yes", "on"}
PDF_OCR_MIN_CHARS = int(os.getenv("PDF_OCR_MIN_CHARS", "500"))
PDF_OCR_DPI_SCALE = float(os.getenv("PDF_OCR_DPI_SCALE", "2.0"))

client = OpenAI()


def log(message: str) -> None:
    print(message, flush=True)


def clean_text(text: str) -> str:
    """Normalize PDF-extracted text while preserving useful paragraph boundaries."""
    text = text or ""
    text = text.replace("\x00", " ")
    text = text.replace("\u00ad", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def compact_text(text: str) -> str:
    """Compact chunk text for embedding and card excerpts."""
    return re.sub(r"\s+", " ", text or "").strip()


JUNK_PATTERNS = [
    r"whirlpoolpro\.com",
    r"count on us\s+means",
    r"communities\s+century\s+building",
    r"paid advertisement",
    r"advertisement",
    r"sponsored by",
    r"sponsor message",
    r"visit us at",
    r"learn more at",
    r"booth\s+#?\d+",
    r"circle reader service",
    r"©\s*\d{4}",
]

# Repeated fragments that can be removed without losing editorial article content.
BOILERPLATE_PATTERNS = [
    r"whirlpoolpro\.com/\S*",
    r"count on us means.*?(?:thriving|building)\.?”?",
    r"visit us at\s+\S+",
    r"learn more at\s+\S+",
]

TOPIC_TERMS = [
    "wall", "walls", "wall system", "wall systems", "wall assembly", "wall assemblies",
    "insulation", "continuous insulation", "exterior insulation", "r-value", "r value",
    "framing", "sheathing", "rainscreen", "air barrier", "vapor barrier", "water barrier",
    "wrb", "weather resistant barrier", "sips", "sip", "structural insulated panels",
    "icf", "insulated concrete forms", "panelized", "modular", "building envelope",
    "hvac", "heat pump", "solar", "storage", "resilience", "flood", "wildfire",
    "building science", "decarbonization", "net zero", "energy efficiency", "air sealing",
]


def strip_boilerplate(text: str) -> str:
    cleaned = text or ""
    for pattern in BOILERPLATE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def uppercase_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if c.isupper()) / len(letters)


def is_junk_page(text: str) -> bool:
    """Detect ad/boilerplate pages that hurt retrieval quality."""
    t = compact_text(text).lower()
    if not t:
        return True

    # Very short pages are usually ads, covers, fragments, or extraction noise.
    if len(t) < 180:
        return True

    hits = sum(1 for pattern in JUNK_PATTERNS if re.search(pattern, t, re.IGNORECASE | re.DOTALL))
    if hits >= 1 and len(t) < 900:
        return True
    if hits >= 2:
        return True

    # Pages with mostly all-caps marketing fragments are usually ads.
    if uppercase_ratio(text) > 0.58 and len(t) < 1200:
        return True

    # Pages with many URLs and little prose are usually ad/resource pages.
    url_count = len(re.findall(r"(?:https?://|www\.|\.com\b|\.org\b)", t))
    sentence_count = len(re.findall(r"[.!?]", t))
    if url_count >= 3 and sentence_count <= 4:
        return True

    return False


def split_paragraphs(text: str) -> list[str]:
    """Split PDF text into paragraph-ish units, with fallbacks for extracted line noise."""
    raw = clean_text(text)
    if not raw:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    if len(paragraphs) <= 1:
        # Fallback: join short lines into paragraph-like blocks.
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        paragraphs = []
        current: list[str] = []
        for line in lines:
            current.append(line)
            joined = " ".join(current)
            if len(joined) >= 280 and re.search(r"[.!?]['\"]?$", line):
                paragraphs.append(joined)
                current = []
        if current:
            paragraphs.append(" ".join(current))

    return [compact_text(p) for p in paragraphs if compact_text(p)]


def chunk_text(text: str, chunk_size: int = PDF_CHUNK_SIZE, overlap: int = PDF_CHUNK_OVERLAP) -> list[str]:
    """Create smaller, semantically cleaner chunks than full-page indexing."""
    paragraphs = split_paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        # If one paragraph is very long, split it by sentence/character window.
        if len(paragraph) > chunk_size * 1.4:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(sliding_chunks(paragraph, chunk_size, overlap))
            continue

        proposed = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(proposed) <= chunk_size:
            current = proposed
        else:
            if current:
                chunks.append(current.strip())
            current = paragraph

    if current:
        chunks.append(current.strip())

    # Remove tiny fragments unless no better chunks exist.
    filtered = [c for c in chunks if len(c) >= PDF_MIN_CHUNK_CHARS]
    return filtered or chunks


def sliding_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = compact_text(text)
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def relevance_hint(text: str) -> int:
    """Lightweight topic signal stored with rows when schema allows it."""
    t = compact_text(text).lower()
    score = 0
    for term in TOPIC_TERMS:
        if term in t:
            score += 1
    # Reward article-like chunks with enough prose and sentence structure.
    if len(t) > 450:
        score += 1
    if len(re.findall(r"[.!?]", t)) >= 3:
        score += 1
    return score


def safe_title_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    stem = stem.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", stem).strip() or filename




def pdf_year_from_filename(filename: str) -> str:
    """Extract a four-digit issue year from a magazine PDF filename."""
    match = re.search(r"\b(20\d{2}|19\d{2})\b", filename or "")
    return match.group(1) if match else ""


def pdf_issue_from_filename(filename: str) -> str:
    """Extract a readable issue label from filenames such as '032 Green Builder May-Jun 2019.pdf'."""
    stem = Path(filename or "").stem
    stem = re.sub(r"^\d+\s+", "", stem).strip()
    stem = re.sub(r"\s+", " ", stem)
    return stem


def expanded_issue_label(filename: str) -> str:
    """Create a search-friendly issue label with expanded month names.

    Example:
    '024 Green Builder Sep-Oct 2020.pdf' ->
    'Green Builder Magazine September October 2020 Sep Oct 2020 024 Green Builder Sep-Oct 2020.pdf'
    """
    issue = pdf_issue_from_filename(filename)
    year = pdf_year_from_filename(filename)
    label = f"Green Builder Magazine {issue}".strip()

    month_map = {
        "jan": "January", "feb": "February", "mar": "March",
        "apr": "April", "may": "May", "jun": "June",
        "jul": "July", "aug": "August", "sep": "September",
        "sept": "September", "oct": "October", "nov": "November",
        "dec": "December",
    }

    expanded_parts: list[str] = []
    for token in re.split(r"[^A-Za-z]+", issue):
        key = token.lower().strip()
        if key in month_map:
            expanded_parts.append(month_map[key])

    pieces = [label]
    if expanded_parts:
        pieces.append(" ".join(expanded_parts))
    if year:
        pieces.append(year)
    pieces.append(filename)

    return " | ".join(dict.fromkeys([p for p in pieces if p]))


def safe_cover_stem(filename: str) -> str:
    """Create a URL-safe cover filename that StaticFiles can serve reliably."""
    stem = Path(filename or "magazine").stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-")
    return stem or "magazine"


def public_cover_path_for_pdf(filename: str) -> str:
    """Return the public cover URL used by main.py/card UI for this PDF."""
    return f"/assets/covers/{safe_cover_stem(filename)}.jpg"


def local_cover_path_for_pdf(filename: str) -> Path:
    return COVERS_DIR / f"{safe_cover_stem(filename)}.jpg"


def generate_pdf_cover(pdf_path: Path) -> str:
    """Generate a JPEG cover thumbnail from page 1 of a PDF when possible.

    This uses PyMuPDF if available. It fails open and returns the expected public
    cover path even if rendering is unavailable, so the UI can still fall back.
    """
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    output = local_cover_path_for_pdf(pdf_path.name)
    public_path = public_cover_path_for_pdf(pdf_path.name)

    if output.exists() and output.stat().st_size > 0:
        return public_path

    try:
        import fitz  # PyMuPDF

        with fitz.open(str(pdf_path)) as doc:
            if len(doc) == 0:
                return public_path
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False)
            if Image is not None:
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img.thumbnail((640, 900))
                img.save(output, "JPEG", quality=86)
            else:
                pix.save(str(output))
        log(f"Generated magazine cover: {output}")
    except Exception as exc:
        log(f"Warning: could not generate cover for {pdf_path.name}: {exc}")

    return public_path

def row_id(pdf_filename: str, page_num: int, chunk_index: int, text: str) -> str:
    raw = f"{pdf_filename}|{page_num}|{chunk_index}|{text[:120]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def embed_batch(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in response.data]


def url_already_ingested(table, pdf_url: str) -> bool:
    try:
        df = table.to_pandas()
        if "url" not in df.columns:
            return False
        return pdf_url in set(df["url"].astype(str).unique())
    except Exception as exc:
        log(f"Warning: could not check existing URLs: {exc}")
        return False


def table_field_names(table) -> set[str]:
    """Return current LanceDB field names so this script works with old and new schemas."""
    try:
        return set(table.schema.names)
    except Exception:
        try:
            return set(table.to_pandas().columns)
        except Exception:
            return set()


def _schema_safe_value(key: str, value):
    """Return values in a form compatible with the existing LanceDB schema.

    Important: the vector column must stay a list[float] of length 1536.
    Do not JSON-encode or stringify it. Metadata lists/dicts, however, should
    be stored as simple strings for older tables whose schema expects text.
    """
    if key == "vector":
        if not isinstance(value, list):
            raise TypeError(f"vector must be list[float], got {type(value).__name__}")
        if len(value) != 1536:
            raise ValueError(f"vector length must be 1536, got {len(value)}")
        return [float(x) for x in value]

    if key == "stale_reasons":
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set)):
            return "; ".join(str(x) for x in value)
        return str(value)

    if key == "governance_note" and value is None:
        return ""

    # Older LanceDB schemas often cannot accept arbitrary list/dict metadata.
    # Keep only vector as a list; stringify other complex metadata.
    if isinstance(value, (list, tuple, set, dict)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)

    return value


def normalize_row_for_table(row: dict, fields: set[str]) -> dict:
    """Drop unsupported fields and coerce supported fields to schema-safe values.

    Older GBM LanceDB tables may not yet have pdf_filename/page/source_type columns.
    This function keeps ingest from failing while still using richer fields on a rebuilt schema.
    """
    # Match the older build_index schema when present.
    defaults = {
        "embed_text": f"Title: {row.get('title', '')}\nCategory: {row.get('category', '')}\nText: {row.get('text', '')}",
        "published_at": "",
        "category": "Magazine archive",
        "source_type": "magazine",
        "image": None,
        "thumbnail": None,
        "og_image": None,
        "featured_image": None,
        "thumbnail_url": row.get("thumbnail_url"),
        "pdf_year": row.get("pdf_year"),
        "pdf_issue": row.get("pdf_issue"),
        "cover_url": row.get("cover_url"),
        "page": row.get("page"),
        "source_name": row.get("source_name"),
        "pdf_filename": row.get("pdf_filename"),
        "relevance_hint": row.get("relevance_hint"),
        "visibility": "public",
        "attribution_label": "Magazine archive",
        "surface_policy": "show_source",
        "stale": False,
        "stale_reasons": "",
        "governance_note": "",
        "chunk_count": row.get("chunk_count"),
        "chunk_index": row.get("chunk_index"),
    }
    full = {**defaults, **row}

    if fields:
        keys = [key for key in fields if key in full]
    else:
        keys = list(full.keys())

    normalized = {}
    for key in keys:
        normalized[key] = _schema_safe_value(key, full.get(key))

    return normalized


def flush_rows(table, rows: list[dict]) -> int:
    if not rows:
        return 0

    fields = table_field_names(table)
    normalized = [normalize_row_for_table(row, fields) for row in rows]
    table.add(normalized)
    count = len(rows)
    rows.clear()
    return count



def extract_text_with_pymupdf(pdf_path: Path, page_index_zero_based: int) -> str:
    """Optional PyMuPDF text fallback for pages where pypdf extracts little text."""
    try:
        import fitz  # PyMuPDF

        with fitz.open(str(pdf_path)) as doc:
            if page_index_zero_based >= len(doc):
                return ""
            page = doc[page_index_zero_based]
            return clean_text(page.get_text("text") or "")
    except Exception as exc:
        log(f"  PyMuPDF text fallback unavailable/failed on page {page_index_zero_based + 1}: {exc}")
        return ""


def ocr_page_with_pymupdf(pdf_path: Path, page_index_zero_based: int) -> str:
    """OCR a PDF page by rendering it with PyMuPDF and reading it with pytesseract.

    This is intended for one-page flyers, speaker sheets, scans, and pages whose
    text is embedded in images rather than extractable PDF text. If OCR
    dependencies are unavailable, it fails open and returns an empty string so
    normal magazine ingest still works.
    """
    if not PDF_ENABLE_OCR:
        return ""

    try:
        import fitz  # PyMuPDF
        import pytesseract
        from PIL import Image

        with fitz.open(str(pdf_path)) as doc:
            if page_index_zero_based >= len(doc):
                return ""
            page = doc[page_index_zero_based]
            matrix = fitz.Matrix(PDF_OCR_DPI_SCALE, PDF_OCR_DPI_SCALE)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img, lang="eng")
            return clean_text(text)
    except Exception as exc:
        log(f"  OCR unavailable/failed on page {page_index_zero_based + 1}: {exc}")
        return ""


def extract_page_text(pdf_path: Path, pypdf_page, page_num: int) -> tuple[str, str]:
    """Extract page text using pypdf, PyMuPDF fallback, then OCR fallback.

    Returns (text, method). OCR is used only when extractable text is shorter
    than PDF_OCR_MIN_CHARS, so full magazines are not slowed down unnecessarily.
    """
    methods: list[str] = []
    candidates: list[str] = []

    try:
        text = clean_text(pypdf_page.extract_text() or "")
        if text:
            candidates.append(text)
            methods.append(f"pypdf:{len(text)}")
    except Exception as exc:
        log(f"  pypdf extraction failed on page {page_num}: {exc}")

    best = max(candidates, key=len, default="")

    if len(best) < PDF_OCR_MIN_CHARS:
        pymupdf_text = extract_text_with_pymupdf(pdf_path, page_num - 1)
        if pymupdf_text:
            candidates.append(pymupdf_text)
            methods.append(f"pymupdf:{len(pymupdf_text)}")
            best = max(candidates, key=len, default="")

    if len(best) < PDF_OCR_MIN_CHARS:
        ocr_text = ocr_page_with_pymupdf(pdf_path, page_num - 1)
        if ocr_text:
            candidates.append(ocr_text)
            methods.append(f"ocr:{len(ocr_text)}")
            best = max(candidates, key=len, default="")

    method = "+".join(methods) if methods else "none"
    return best, method


def low_text_fallback_chunk(pdf_filename: str, source_title: str, page_num: int, extracted_text: str) -> str:
    """Create a minimal searchable chunk when OCR/text extraction is still thin."""
    compact = compact_text(extracted_text)
    fallback = (
        f"{source_title}. Source PDF file: {pdf_filename}. Page {page_num}. "
        "This appears to be a low-text or image-heavy PDF page. "
    )
    if compact:
        fallback += compact
    return compact_text(fallback)

def ingest_one(filename: str) -> int:
    pdf_path = MAGAZINE_DIR / filename
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # IMPORTANT: Do not move this file after ingest. FastAPI serves magazine PDFs
    # directly from /data/magazines via app.mount("/magazines", ...).

    db = lancedb.connect(LANCEDB_DIR)
    table = db.open_table(TABLE_NAME)

    # Keep the public URL browser-safe while leaving the physical PDF in /data/magazines.
    pdf_url = f"{PUBLIC_MAGAZINE_PREFIX}/{quote(pdf_path.name)}"
    pdf_year = pdf_year_from_filename(pdf_path.name)
    pdf_issue = pdf_issue_from_filename(pdf_path.name)
    cover_url = generate_pdf_cover(pdf_path)

    if url_already_ingested(table, pdf_url):
        log(f"SKIP already ingested: {pdf_path.name}")
        return 0

    source_title = safe_title_from_filename(pdf_path.name)
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)

    log(f"Processing {pdf_path.name} ({total_pages} pages)")
    log(f"Junk-page filtering: {'ON' if PDF_SKIP_JUNK else 'OFF'}")
    log(f"Chunk size: {PDF_CHUNK_SIZE}; overlap: {PDF_CHUNK_OVERLAP}; min chars: {PDF_MIN_CHUNK_CHARS}")
    log(f"OCR fallback: {'ON' if PDF_ENABLE_OCR else 'OFF'}; threshold: {PDF_OCR_MIN_CHARS} chars; scale: {PDF_OCR_DPI_SCALE}")

    pending_texts: list[tuple[int, int, int, str]] = []
    pending_rows: list[dict] = []
    chunks_added = 0
    pages_skipped = 0

    def flush_pending() -> int:
        nonlocal pending_texts, pending_rows

        if not pending_texts:
            return 0

        # Embed strong issue-aware text so queries like "Sept Oct 2020 issue"
        # directly match the correct PDF, not only whatever article text appears
        # on an individual page.
        enhanced_items: list[tuple[int, int, int, str, str]] = []
        issue_label = expanded_issue_label(pdf_path.name)
        for page_num, chunk_index, chunk_count, text in pending_texts:
            enhanced_text = (
                f"{issue_label}\n"
                f"Issue: {pdf_issue}\n"
                f"Year: {pdf_year}\n"
                f"File: {pdf_path.name}\n"
                f"Page: {page_num}\n\n"
                f"{text}"
            ).strip()
            enhanced_items.append((page_num, chunk_index, chunk_count, text, enhanced_text))

        texts = [x[4] for x in enhanced_items]
        vectors = embed_batch(texts)

        for (page_num, chunk_index, chunk_count, original_text, enhanced_text), vector in zip(enhanced_items, vectors):
            title = f"{source_title} (PDF, p. {page_num})"
            row = {
                "id": row_id(pdf_path.name, page_num, chunk_index, enhanced_text),
                "title": title,
                "url": pdf_url,
                "text": enhanced_text,
                "embed_text": enhanced_text,
                "page": page_num,
                "published_at": pdf_year or "",
                "category": "Magazine archive",
                "visibility": "public",
                "attribution_label": "Magazine archive",
                "surface_policy": "show_source",
                "source_type": "magazine",
                "source_name": source_title,
                "pdf_filename": pdf_path.name,
                "pdf_year": pdf_year,
                "pdf_issue": pdf_issue,
                "cover_url": cover_url,
                "image": cover_url,
                "thumbnail": cover_url,
                "thumbnail_url": cover_url,
                "chunk_index": chunk_index - 1,
                "chunk_count": chunk_count,
                "relevance_hint": relevance_hint(original_text),
                "stale": False,
                "stale_reasons": [],
                "governance_note": None,
                "vector": vector,
            }
            pending_rows.append(row)

        pending_texts.clear()
        return flush_rows(table, pending_rows)

    for page_num, page in enumerate(reader.pages, start=1):
        raw_page_text, extraction_method = extract_page_text(pdf_path, page, page_num)
        log(f"  Page {page_num}/{total_pages}: extracted {len(raw_page_text)} chars via {extraction_method}")

        # Do not junk-skip extremely short PDFs/flyers too aggressively. A one-page
        # event flyer may be the whole document and should still be searchable.
        if PDF_SKIP_JUNK and total_pages > 1 and is_junk_page(raw_page_text):
            pages_skipped += 1
            log(f"  Skipping likely junk/ad page {page_num}/{total_pages}")
            continue

        page_text = strip_boilerplate(raw_page_text)
        chunks = chunk_text(page_text)

        # If extraction/OCR still produced a short fragment, keep a fallback chunk
        # so names, dates, event titles, and file identity remain searchable.
        if not chunks and compact_text(page_text):
            chunks = [low_text_fallback_chunk(pdf_path.name, source_title, page_num, page_text)]
        elif not chunks and total_pages <= 2:
            chunks = [low_text_fallback_chunk(pdf_path.name, source_title, page_num, "")]

        log(f"  Page {page_num}/{total_pages}: {len(chunks)} chunks")

        chunk_count = len(chunks)
        for chunk_index, chunk in enumerate(chunks, start=1):
            # Avoid indexing residual boilerplate fragments.
            if PDF_SKIP_JUNK and is_junk_page(chunk):
                continue

            pending_texts.append((page_num, chunk_index, chunk_count, chunk))

            if len(pending_texts) >= BATCH_SIZE:
                written = flush_pending()
                chunks_added += written
                log(f"    Wrote {written} chunks; total: {chunks_added}")
                time.sleep(1)

    written = flush_pending()
    chunks_added += written

    log(f"DONE {pdf_path.name}: added {chunks_added} chunks; skipped {pages_skipped} likely junk/ad pages")
    return chunks_added


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python scripts/ingest_one_magazine.py 'filename.pdf'")

    ingest_one(sys.argv[1])
