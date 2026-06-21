from __future__ import annotations

import html
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

TRANSCRIPT_HTML_DIR = Path(os.getenv("YOUTUBE_TRANSCRIPT_HTML_DIR", "/data/youtube_transcripts_html"))
TRANSCRIPT_HTML_STATUS_FILE = Path(os.getenv("YOUTUBE_TRANSCRIPT_HTML_STATUS_FILE", "/data/youtube_transcript_html_status.json"))

_TIMESTAMP_RANGE_RE = re.compile(
    r"^(?P<start>\d{1,2}:\d{2}:\d{2}(?::\d{1,2})?)\s*[-–—]\s*(?P<end>\d{1,2}:\d{2}:\d{2}(?::\d{1,2})?)$"
)


def _clean(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\r\n?", "\n", text)
    return text.strip()


def _safe_filename(value: str, fallback: str = "transcript") -> str:
    value = Path(value or fallback).stem
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return value or fallback


def _timestamp_to_seconds(raw: str) -> int:
    """Accept HH:MM:SS:FF, HH:MM:SS, or MM:SS and return seconds."""
    parts = [p for p in str(raw or "").split(":") if p != ""]
    try:
        nums = [int(float(p)) for p in parts]
    except Exception:
        return 0

    if len(nums) >= 4:
        h, m, s = nums[0], nums[1], nums[2]
    elif len(nums) == 3:
        h, m, s = nums
    elif len(nums) == 2:
        h, m, s = 0, nums[0], nums[1]
    else:
        return 0
    return max(h * 3600 + m * 60 + s, 0)


def _youtube_at(source_url: str, timestamp: str) -> str:
    source_url = str(source_url or "").strip()
    if not source_url:
        return "#"
    sep = "&" if "?" in source_url else "?"
    return f"{source_url}{sep}t={_timestamp_to_seconds(timestamp)}s"


def _parse_entries(raw_text: str) -> list[dict[str, str]]:
    lines = [line.rstrip() for line in (raw_text or "").splitlines()]
    entries: list[dict[str, str]] = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        match = _TIMESTAMP_RANGE_RE.match(line)
        if not match:
            i += 1
            continue

        start = match.group("start")
        end = match.group("end")
        speaker = ""
        if i + 1 < len(lines):
            speaker = lines[i + 1].strip()

        body: list[str] = []
        j = i + 2
        while j < len(lines):
            next_line = lines[j].strip()
            if _TIMESTAMP_RANGE_RE.match(next_line):
                break
            if next_line:
                body.append(next_line)
            j += 1

        text = " ".join(body).strip()
        if text:
            entries.append({"start": start, "end": end, "speaker": speaker, "text": text})
        i = j

    if entries:
        return entries

    # Fallback for plain text without timestamp blocks.
    cleaned = re.sub(r"\s+", " ", raw_text or "").strip()
    if not cleaned:
        return []
    paragraphs = [p.strip() for p in re.split(r"(?<=[.!?])\s+(?=[A-Z])", cleaned) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        candidate = f"{buf} {para}".strip()
        if len(candidate) > 900 and buf:
            chunks.append(buf)
            buf = para
        else:
            buf = candidate
    if buf:
        chunks.append(buf)

    return [
        {"start": "00:00:00:00", "end": "00:00:00:00", "speaker": "Transcript", "text": chunk}
        for chunk in chunks
    ]


def _speaker_classes(entries: list[dict[str, str]]) -> dict[str, str]:
    speakers: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        speaker = entry.get("speaker", "").strip() or "Speaker"
        if speaker not in seen:
            speakers.append(speaker)
            seen.add(speaker)
    return {speaker: f"speaker-{idx % 6}" for idx, speaker in enumerate(speakers)}


def _short_summary(entries: list[dict[str, str]], max_chars: int = 420) -> str:
    text = " ".join(entry.get("text", "") for entry in entries[:5])
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut + "..."


def _keyword_moments(entries: list[dict[str, str]], source_url: str) -> list[dict[str, str]]:
    topics = [
        ("carbon", "Carbon"),
        ("embodied", "Embodied carbon"),
        ("resilien", "Resilience"),
        ("solar", "Solar"),
        ("heat pump", "Heat pumps"),
        ("water", "Water"),
        ("afford", "Affordability"),
        ("tariff", "Tariffs"),
        ("AI", "AI"),
        ("policy", "Policy"),
        ("building", "Built environment"),
        ("sustainab", "Sustainability"),
    ]
    moments: list[dict[str, str]] = []
    used_labels: set[str] = set()
    for entry in entries:
        blob = f"{entry.get('speaker','')} {entry.get('text','')}".lower()
        for needle, label in topics:
            if needle.lower() in blob and label not in used_labels:
                excerpt = entry.get("text", "").strip()
                if len(excerpt) > 120:
                    excerpt = excerpt[:120].rsplit(" ", 1)[0] + "..."
                moments.append({
                    "label": label,
                    "time": entry.get("start", ""),
                    "href": _youtube_at(source_url, entry.get("start", "")),
                    "excerpt": excerpt,
                })
                used_labels.add(label)
                break
        if len(moments) >= 6:
            break
    return moments


def transcript_html_path_for_record(record: dict[str, Any]) -> Path:
    video_id = _clean(record.get("video_id"))
    if video_id:
        return TRANSCRIPT_HTML_DIR / f"{_safe_filename(video_id)}.html"
    filename = _clean(record.get("filename")) or _clean(record.get("title"))
    return TRANSCRIPT_HTML_DIR / f"{_safe_filename(filename)}.html"


def transcript_html_url_for_record(record: dict[str, Any]) -> str:
    video_id = _clean(record.get("video_id"))
    if video_id:
        return f"/api/youtube-transcript-html/{video_id}"
    return ""


def render_transcript_html(record: dict[str, Any]) -> str:
    title = _clean(record.get("title")) or "Green Builder Media Transcript"
    source_url = _clean(record.get("url"))
    speakers = _clean(record.get("speakers"))
    raw_text = _clean(record.get("text"))
    entries = _parse_entries(raw_text)
    speaker_classes = _speaker_classes(entries)
    duration = entries[-1].get("end", "") if entries else ""
    summary = _short_summary(entries)
    moments = _keyword_moments(entries, source_url)
    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    speaker_filters = []
    for speaker in speaker_classes:
        speaker_filters.append(
            f'<button type="button" class="filter-btn" data-speaker="{html.escape(speaker)}">{html.escape(speaker)}</button>'
        )

    moments_html = "".join(
        f'''
        <a class="moment-card" href="{html.escape(moment["href"])}" target="_blank" rel="noopener">
          <span>{html.escape(moment["time"][3:8] if len(moment["time"]) >= 8 else moment["time"])}</span>
          <strong>{html.escape(moment["label"])}</strong>
          <em>{html.escape(moment["excerpt"])}</em>
        </a>
        '''
        for moment in moments
    ) or '<p class="muted">Use search to find specific terms in this transcript.</p>'

    entries_html = []
    for entry in entries:
        speaker = entry.get("speaker", "").strip() or "Speaker"
        cls = speaker_classes.get(speaker, "speaker-0")
        start = entry.get("start", "")
        end = entry.get("end", "")
        entries_html.append(
            f'''
            <article class="transcript-entry" data-speaker="{html.escape(speaker)}">
              <a class="timestamp" href="{html.escape(_youtube_at(source_url, start))}" target="_blank" rel="noopener">{html.escape(start)} – {html.escape(end)}</a>
              <div class="entry-body">
                <div class="speaker-pill {cls}">{html.escape(speaker)}</div>
                <p>{html.escape(entry.get("text", ""))}</p>
              </div>
            </article>
            '''
        )

    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} | Transcript</title>
  <style>
    :root {{
      --gbm-blue: #00839a; --gbm-navy: #123044; --gbm-green: #184d42;
      --paper: #f6f8f7; --card: #ffffff; --line: #dbe7e4;
      --text: #172233; --muted: #62707a; --shadow: 0 18px 45px rgba(18,48,68,.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: linear-gradient(180deg,#eef7f5 0%,#f8faf9 42%,#fff 100%); color: var(--text); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.6; }}
    .page {{ max-width: 1120px; margin: 0 auto; padding: 36px 22px 70px; }}
    .hero {{ background: var(--card); border: 1px solid var(--line); border-radius: 28px; box-shadow: var(--shadow); overflow: hidden; }}
    .hero-top {{ padding: 28px 32px; background: linear-gradient(135deg,var(--gbm-blue),#0b657b); color: #fff; }}
    .label {{ display: inline-flex; padding: 6px 12px; border-radius: 999px; background: rgba(255,255,255,.16); font-size: 12px; letter-spacing: .12em; text-transform: uppercase; font-weight: 800; }}
    h1 {{ max-width: 880px; margin: 18px 0 12px; font-size: clamp(30px,4vw,54px); line-height: 1.03; letter-spacing: -.04em; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 10px 18px; color: rgba(255,255,255,.92); font-size: 15px; }}
    .hero-actions {{ display: flex; flex-wrap: wrap; gap: 12px; padding: 20px 32px; border-bottom: 1px solid var(--line); background: #fff; }}
    .btn {{ appearance: none; border: 0; border-radius: 999px; padding: 12px 18px; font-weight: 800; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; background: var(--gbm-blue); color: #fff; }}
    .btn.secondary {{ background: #e8f4f2; color: var(--gbm-green); border: 1px solid #c9e3dd; }}
    .toolbar {{ display: grid; grid-template-columns: 1fr auto; gap: 14px; padding: 22px 32px; align-items: center; }}
    .search {{ width: 100%; border: 1px solid var(--line); border-radius: 18px; padding: 14px 16px; font-size: 16px; outline: none; }}
    .search:focus {{ border-color: var(--gbm-blue); box-shadow: 0 0 0 4px rgba(0,131,154,.12); }}
    .summary-grid {{ display: grid; grid-template-columns: 1.2fr .8fr; gap: 18px; padding: 0 32px 30px; }}
    .panel {{ background: #f8fbfa; border: 1px solid var(--line); border-radius: 22px; padding: 20px; }}
    .panel h2 {{ margin: 0 0 10px; color: var(--gbm-green); line-height: 1.1; }}
    .panel p, .muted {{ margin: 0; color: var(--muted); }}
    .moment-list {{ display: grid; gap: 10px; }}
    .moment-card {{ display: grid; grid-template-columns: 54px 1fr; gap: 10px; align-items: start; padding: 12px; border-radius: 16px; background: #fff; border: 1px solid var(--line); color: var(--text); text-decoration: none; }}
    .moment-card span {{ font-weight: 900; color: var(--gbm-blue); }}
    .moment-card strong {{ line-height: 1.1; }}
    .moment-card em {{ grid-column: 2; margin-top: -4px; color: var(--muted); font-size: 13px; font-style: normal; }}
    .filters {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .filter-btn {{ border: 1px solid var(--line); background: #fff; color: var(--gbm-green); border-radius: 999px; padding: 9px 12px; font-weight: 800; cursor: pointer; }}
    .filter-btn.active {{ background: var(--gbm-green); color: #fff; border-color: var(--gbm-green); }}
    .transcript {{ margin-top: 28px; display: grid; gap: 14px; }}
    .transcript-entry {{ display: grid; grid-template-columns: 170px 1fr; gap: 16px; background: #fff; border: 1px solid var(--line); border-radius: 22px; padding: 18px; box-shadow: 0 10px 30px rgba(18,48,68,.06); }}
    .timestamp {{ color: var(--gbm-blue); font-weight: 900; text-decoration: none; font-variant-numeric: tabular-nums; padding-top: 4px; }}
    .entry-body p {{ margin: 10px 0 0; font-size: 17px; }}
    .speaker-pill {{ display: inline-flex; border-radius: 999px; padding: 5px 11px; font-size: 13px; font-weight: 900; letter-spacing: .02em; color: #fff; }}
    .speaker-0 {{ background: #006f87; }} .speaker-1 {{ background: #184d42; }} .speaker-2 {{ background: #7a3b56; }} .speaker-3 {{ background: #715c1f; }} .speaker-4 {{ background: #48546a; }} .speaker-5 {{ background: #6a4c93; }}
    .hidden {{ display: none !important; }}
    .no-results {{ display: none; margin: 22px 0; padding: 20px; border: 1px dashed var(--line); border-radius: 18px; color: var(--muted); text-align: center; background: #fff; }}
    footer {{ margin-top: 28px; text-align: center; color: var(--muted); font-size: 13px; }}
    @media (max-width: 760px) {{ .page {{ padding: 16px 12px 44px; }} .hero-top,.hero-actions,.toolbar,.summary-grid {{ padding-left: 18px; padding-right: 18px; }} .summary-grid {{ grid-template-columns: 1fr; }} .toolbar {{ grid-template-columns: 1fr; }} .transcript-entry {{ grid-template-columns: 1fr; gap: 8px; }} .entry-body p {{ font-size: 16px; }} h1 {{ font-size: 31px; }} }}
    @media print {{ body {{ background: #fff; }} .hero-actions,.toolbar,.moment-list,.btn {{ display: none !important; }} .hero,.transcript-entry {{ box-shadow: none; }} .transcript-entry {{ break-inside: avoid; }} a {{ color: inherit; }} }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="hero-top">
        <span class="label">Green Builder Media Transcript</span>
        <h1>{html.escape(title)}</h1>
        <div class="meta">
          <span><strong>Speakers:</strong> {html.escape(speakers or ', '.join(speaker_classes.keys()) or 'Not listed')}</span>
          <span><strong>Duration:</strong> {html.escape(duration or 'Not listed')}</span>
          <span><strong>Sections:</strong> {len(entries)}</span>
        </div>
      </div>
      <div class="hero-actions">
        {f'<a class="btn" href="{html.escape(source_url)}" target="_blank" rel="noopener">Watch on YouTube</a>' if source_url else ''}
        <button class="btn secondary" onclick="window.print()">Print / Save PDF</button>
        <button class="btn secondary" id="copyLink">Copy transcript link</button>
      </div>
      <div class="toolbar">
        <input class="search" id="searchBox" type="search" placeholder="Search this transcript...">
        <div class="filters"><button type="button" class="filter-btn active" data-speaker="all">All speakers</button>{''.join(speaker_filters)}</div>
      </div>
      <div class="summary-grid">
        <div class="panel"><h2>Transcript overview</h2><p>{html.escape(summary or 'This transcript has been formatted for easier reading, search, printing, and source-video navigation.')}</p></div>
        <div class="panel"><h2>Key moments</h2><div class="moment-list">{moments_html}</div></div>
      </div>
    </section>
    <section class="transcript" id="transcript">{''.join(entries_html)}</section>
    <div class="no-results" id="noResults">No matching transcript sections found.</div>
    <footer>Generated {html.escape(generated)} from Green Builder Media transcript text. Timestamps open the source video at the selected moment.</footer>
  </main>
  <script>
    const searchBox = document.getElementById('searchBox');
    const entries = [...document.querySelectorAll('.transcript-entry')];
    const filters = [...document.querySelectorAll('.filter-btn')];
    const noResults = document.getElementById('noResults');
    let activeSpeaker = 'all';
    function applyFilters() {{
      const q = (searchBox.value || '').toLowerCase().trim(); let visible = 0;
      entries.forEach(entry => {{
        const text = entry.innerText.toLowerCase(); const speaker = entry.dataset.speaker;
        const show = (activeSpeaker === 'all' || speaker === activeSpeaker) && (!q || text.includes(q));
        entry.classList.toggle('hidden', !show); if (show) visible++;
      }});
      noResults.style.display = visible ? 'none' : 'block';
    }}
    searchBox.addEventListener('input', applyFilters);
    filters.forEach(btn => btn.addEventListener('click', () => {{ filters.forEach(b => b.classList.remove('active')); btn.classList.add('active'); activeSpeaker = btn.dataset.speaker; applyFilters(); }}));
    document.getElementById('copyLink').addEventListener('click', async () => {{
      try {{ await navigator.clipboard.writeText(window.location.href); const b = document.getElementById('copyLink'); b.textContent = 'Copied'; setTimeout(() => b.textContent = 'Copy transcript link', 1600); }}
      catch (e) {{ alert('Copy failed. You can copy the page URL from your browser.'); }}
    }});
  </script>
</body>
</html>'''


def build_transcript_html_file(record: dict[str, Any], force: bool = False) -> dict[str, Any]:
    TRANSCRIPT_HTML_DIR.mkdir(parents=True, exist_ok=True)
    path = transcript_html_path_for_record(record)
    raw_path = Path(str(record.get("path") or "")) if record.get("path") else None
    source_mtime = 0.0
    if raw_path and raw_path.exists():
        source_mtime = raw_path.stat().st_mtime

    if path.exists() and not force:
        if not source_mtime or path.stat().st_mtime >= source_mtime:
            return {"ok": True, "status": "skipped_current", "file": path.name, "path": str(path)}

    html_text = render_transcript_html(record)
    path.write_text(html_text, encoding="utf-8")
    return {"ok": True, "status": "built", "file": path.name, "path": str(path)}


def build_all_transcript_html(transcript_cache: dict[str, Any] | None = None, cache_file: str | Path = "/data/youtube_transcripts.json", force: bool = False) -> dict[str, Any]:
    if transcript_cache is None:
        try:
            transcript_cache = json.loads(Path(cache_file).read_text(encoding="utf-8"))
        except Exception as exc:
            return {"ok": False, "message": f"Could not read transcript cache: {exc}", "built": 0, "skipped": 0, "failed": []}

    transcripts = transcript_cache.get("transcripts", []) if isinstance(transcript_cache, dict) else []
    built = 0
    skipped = 0
    failed: list[dict[str, str]] = []
    files: list[str] = []

    for record in transcripts:
        if not isinstance(record, dict):
            continue
        try:
            result = build_transcript_html_file(record, force=force)
            if result.get("status") == "built":
                built += 1
            else:
                skipped += 1
            files.append(str(result.get("file") or ""))
        except Exception as exc:
            failed.append({"title": str(record.get("title") or record.get("filename") or "unknown"), "error": str(exc)})

    status = {
        "ok": len(failed) == 0,
        "message": f"Built {built} transcript HTML file(s); skipped {skipped} current file(s); {len(failed)} failed.",
        "html_dir": str(TRANSCRIPT_HTML_DIR),
        "built": built,
        "skipped": skipped,
        "failed": failed,
        "total_transcripts": len(transcripts),
        "html_file_count": len(list(TRANSCRIPT_HTML_DIR.glob("*.html"))) if TRANSCRIPT_HTML_DIR.exists() else 0,
        "updated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sample": files[:5],
    }
    TRANSCRIPT_HTML_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRANSCRIPT_HTML_STATUS_FILE.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


if __name__ == "__main__":
    print(json.dumps(build_all_transcript_html(force="--force" in os.sys.argv), indent=2))
