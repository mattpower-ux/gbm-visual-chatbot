from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Iterable


HOT_TAKE_PATH = Path(os.getenv("HOT_TAKE_PATH", "/data/cognition_hot_takes.json"))

# A score below this returns no Hot Take. This prevents the UI from showing
# a weak but visually prominent chart just because something matched loosely.
HOT_TAKE_MIN_SCORE = float(os.getenv("HOT_TAKE_MIN_SCORE", "7.5"))
HOT_TAKE_MIN_STRONG_OVERLAP = int(os.getenv("HOT_TAKE_MIN_STRONG_OVERLAP", "1"))

STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "what", "which",
    "about", "into", "over", "past", "years", "year", "green", "builder",
    "media", "cognition", "smart", "data", "home", "homes", "house",
    "housing", "tell", "give", "show", "explain", "changes", "changed",
    "technology", "technologies", "query", "need", "want",
    # These words are too generic for retrieval scoring. They can appear in
    # almost every GBM/COGNITION item and should not make a weak result look relevant.
    "sustainable", "sustainability", "greenest", "best", "better", "material", "materials",
    "product", "products", "building", "buildings", "residential", "consumer", "consumers",
}

PHRASE_ALIASES: dict[str, set[str]] = {
    "heat pump": {"heat pump", "heat pumps", "hvac", "heating", "cooling", "compressor", "inverter", "cold climate"},
    "thermostat": {"thermostat", "thermostats", "smart thermostat", "connected thermostat", "controls"},
    "electrification": {"electrification", "electric", "electric-ready", "all-electric", "decarbonization", "decarbonisation"},
    "solar": {"solar", "photovoltaic", "pv", "battery", "storage", "inverter", "microgrid"},
    "resilience": {"resilience", "resilient", "wildfire", "storm", "flood", "hurricane", "climate-resilient"},
    "water": {"water", "leak", "leaks", "irrigation", "shutoff", "conservation", "efficiency"},
    "indoor air": {"indoor air", "iaq", "ventilation", "humidity", "dehumidifier", "air quality", "mold", "mildew"},
    "outdoor living": {"outdoor", "outdoor living", "outdoor spaces", "yard", "patio", "landscape"},
    "affordability": {"affordability", "affordable", "cost", "price", "mortgage", "rent", "income"},
    "countertop": {
        "countertop", "countertops", "counter top", "counter tops", "worktop", "worktops",
        "kitchen counter", "kitchen counters", "surface", "surfaces", "solid surface",
        "quartz", "granite", "marble", "laminate", "butcher block", "wood counter",
        "paperstone", "richlite", "recycled glass", "porcelain slab", "stainless steel",
        "engineered stone", "sintered stone", "soapstone", "concrete countertop",
    },
    "cabinet": {"cabinet", "cabinets", "cabinetry", "kitchen cabinet", "kitchen cabinets"},
    "flooring": {"flooring", "floor", "floors", "hardwood", "bamboo", "cork", "vinyl", "tile", "carpet"},
    "appliance": {"appliance", "appliances", "refrigerator", "dishwasher", "range", "oven", "induction"},
}

NEGATIVE_CLUSTERS: dict[str, set[str]] = {
    "heat pump": {"outdoor living", "outdoor spaces", "patio", "kitchen", "bath", "interior", "finishes", "luxury"},
    "hvac": {"outdoor living", "outdoor spaces", "patio", "kitchen", "bath", "interior", "finishes", "luxury"},
    "thermostat": {"outdoor living", "outdoor spaces", "patio", "kitchen", "bath", "interior", "finishes", "luxury"},
    "solar": {"outdoor living", "kitchen", "bath", "interior", "finishes"},
    "countertop": {"heat pump", "hvac", "thermostat", "solar", "battery", "water heater", "insulation", "window", "windows", "roof", "roofing"},
    "countertops": {"heat pump", "hvac", "thermostat", "solar", "battery", "water heater", "insulation", "window", "windows", "roof", "roofing"},
    "kitchen counter": {"heat pump", "hvac", "thermostat", "solar", "battery", "water heater", "insulation"},
}


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z][a-z0-9\-]{2,}", (text or "").lower())
    return [t for t in tokens if t not in STOP_WORDS]


def query_phrases(query: str) -> set[str]:
    q = (query or "").lower()
    found: set[str] = set()
    for phrase, aliases in PHRASE_ALIASES.items():
        if phrase in q or any(alias in q for alias in aliases):
            found.add(phrase)
            found.update(aliases)
    return found


def score_overlap(query_tokens: set[str], text: str) -> float:
    text_tokens = set(tokenize(text))

    if not text_tokens:
        return 0.0

    overlap = query_tokens.intersection(text_tokens)

    if not overlap:
        return 0.0

    return len(overlap) / math.sqrt(len(text_tokens))


def phrase_hits(phrases: Iterable[str], text: str) -> set[str]:
    blob = (text or "").lower()
    return {phrase for phrase in phrases if phrase and phrase in blob}


def high_value_query_terms(query: str) -> set[str]:
    """Return query terms that should be treated as hard relevance anchors.

    Generic terms such as sustainable/sustainability are intentionally removed
    by STOP_WORDS. For a query like "which countertop is most sustainable",
    "countertop" becomes the anchor that must appear in the matched content
    or one of its aliases must appear.
    """
    terms = set(tokenize(query))
    expanded = set(terms)

    q = (query or "").lower()
    for phrase, aliases in PHRASE_ALIASES.items():
        if phrase in q or any(alias in q for alias in aliases):
            expanded.add(phrase)
            expanded.update(aliases)

    return {t for t in expanded if t and t not in STOP_WORDS}


def has_anchor_match(query: str, text: str) -> bool:
    anchors = high_value_query_terms(query)
    if not anchors:
        return True

    blob = (text or "").lower()
    text_tokens = set(tokenize(blob))

    for anchor in anchors:
        if " " in anchor:
            if anchor in blob:
                return True
        elif anchor in text_tokens:
            return True

    return False


def anchor_match_count(query: str, text: str) -> int:
    anchors = high_value_query_terms(query)
    if not anchors:
        return 0

    blob = (text or "").lower()
    text_tokens = set(tokenize(blob))

    count = 0
    for anchor in anchors:
        if " " in anchor:
            if anchor in blob:
                count += 1
        elif anchor in text_tokens:
            count += 1
    return count


def graphic_text_blob(graphic: dict) -> str:
    return " ".join(
        str(graphic.get(key, "") or "")
        for key in (
            "article_title",
            "chart_title",
            "alt",
            "nearby_text",
            "ocr_text",
        )
    ) + " " + " ".join(graphic.get("keywords", []) or []) + " " + " ".join(graphic.get("ocr_keywords", []) or [])


def strong_overlap_count(query: str, graphic: dict) -> int:
    q_tokens = set(tokenize(query))
    q_phrases = query_phrases(query)

    strong_text = " ".join(
        str(graphic.get(key, "") or "")
        for key in ("chart_title", "ocr_text", "alt")
    )
    strong_tokens = set(tokenize(strong_text))

    count = len(q_tokens.intersection(strong_tokens))
    count += len(phrase_hits(q_phrases, strong_text))
    return count


def category_penalty(query: str, graphic: dict) -> float:
    q = (query or "").lower()
    blob = graphic_text_blob(graphic).lower()

    penalty = 0.0
    for trigger, negatives in NEGATIVE_CLUSTERS.items():
        if trigger in q:
            for term in negatives:
                if term in blob:
                    penalty += 3.0

    return penalty


def rank_graphic(query: str, graphic: dict) -> float:
    query_tokens = set(tokenize(query))
    q_phrases = query_phrases(query)

    if not query_tokens and not q_phrases:
        return 0.0

    score = 0.0

    # OCR/chart text is the most important signal because it describes what the
    # user actually sees in the graphic.
    score += score_overlap(query_tokens, graphic.get("ocr_text", "")) * 13.0
    score += score_overlap(query_tokens, graphic.get("chart_title", "")) * 12.0
    score += score_overlap(query_tokens, " ".join(graphic.get("ocr_keywords", []) or [])) * 10.0

    # Article context remains useful, but it is intentionally secondary so a
    # broad article intro does not force an unrelated chart into the first card.
    score += score_overlap(query_tokens, graphic.get("article_title", "")) * 5.0
    score += score_overlap(query_tokens, graphic.get("alt", "")) * 4.0
    score += score_overlap(query_tokens, graphic.get("nearby_text", "")) * 1.5
    score += score_overlap(query_tokens, " ".join(graphic.get("keywords", []) or [])) * 4.0

    # Phrase aliases help bridge terms like heat pump -> HVAC/heating/cooling.
    blob = graphic_text_blob(graphic)
    strong_blob = " ".join(str(graphic.get(k, "") or "") for k in ("ocr_text", "chart_title", "alt"))

    score += len(phrase_hits(q_phrases, strong_blob)) * 5.0
    score += len(phrase_hits(q_phrases, blob)) * 2.0

    # Require at least a little real connection to the visible chart/alt text.
    # Otherwise, the score is discounted heavily even if article text overlaps.
    strong_overlap = strong_overlap_count(query, graphic)
    if strong_overlap < HOT_TAKE_MIN_STRONG_OVERLAP:
        score *= 0.35

    # New stricter guard:
    # A broad sustainability query should not pull a chart unless the user's
    # actual subject anchor is present somewhere in the chart/title/alt/OCR/body.
    # Example: "which countertop is most sustainable" must match countertop,
    # quartz, granite, recycled glass, etc.; "sustainable" alone is not enough.
    blob = graphic_text_blob(graphic)
    strong_blob = " ".join(str(graphic.get(k, "") or "") for k in ("ocr_text", "chart_title", "alt"))

    if not has_anchor_match(query, blob):
        return 0.0

    # Visible chart/alt text gets an additional anchor bonus. This favors charts
    # that actually display the subject over articles that merely mention it nearby.
    score += anchor_match_count(query, strong_blob) * 6.0
    score += anchor_match_count(query, blob) * 1.5

    score -= category_penalty(query, graphic)
    return max(score, 0.0)


def relevant_lines_from_ocr(query: str, ocr_text: str) -> list[str]:
    q_tokens = set(tokenize(query))
    q_phrases = query_phrases(query)
    lines = [re.sub(r"\s+", " ", line).strip() for line in (ocr_text or "").splitlines()]
    lines = [line for line in lines if line]

    scored: list[tuple[int, str]] = []
    for line in lines:
        line_tokens = set(tokenize(line))
        hits = len(q_tokens.intersection(line_tokens)) + len(phrase_hits(q_phrases, line))
        if hits > 0:
            scored.append((hits, line))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [line for _hits, line in scored[:3]]


def build_caption(query: str, graphic: dict) -> str:
    title = graphic.get("article_title") or "COGNITION SmartData"
    chart_title = graphic.get("chart_title") or ""
    ocr_text = graphic.get("ocr_text") or ""

    if chart_title:
        base = f"This COGNITION SmartData chart is titled “{chart_title}.”"
    else:
        base = f"This COGNITION SmartData graphic from “{title}” matched the query."

    lines = relevant_lines_from_ocr(query, ocr_text)
    if lines:
        detail = " Relevant chart text includes: " + "; ".join(lines)
    else:
        nearby = re.sub(r"\s+", " ", graphic.get("nearby_text", "") or "").strip()
        if len(nearby) > 240:
            nearby = nearby[:237] + "..."
        detail = f" {nearby}" if nearby else ""

    return (base + detail).strip()


def best_hot_take(query: str) -> dict | None:
    if not HOT_TAKE_PATH.exists():
        return None

    data = json.loads(HOT_TAKE_PATH.read_text(encoding="utf-8"))
    graphics = data.get("graphics", [])

    if not graphics:
        return None

    ranked: list[tuple[float, dict]] = []

    for g in graphics:
        s = rank_graphic(query, g)

        if s < HOT_TAKE_MIN_SCORE:
            continue

        ranked.append((s, g))

    if not ranked:
        return None

    ranked.sort(key=lambda x: x[0], reverse=True)
    score, best = ranked[0]

    return {
        "title": best.get("article_title"),
        "article_url": best.get("article_url"),
        "chart_image": best.get("image_url"),
        "caption": build_caption(query, best),
        "score": round(score, 3),
        "chart_title": best.get("chart_title", ""),
        "ocr_available": bool(best.get("ocr_text")),
    }
