from __future__ import annotations

import json
import math
import re
from pathlib import Path


HOT_TAKE_PATH = Path("/data/cognition_hot_takes.json")


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z0-9\-]{2,}", (text or "").lower())


def score_overlap(query_tokens: set[str], text: str) -> float:
    text_tokens = set(tokenize(text))

    if not text_tokens:
        return 0.0

    overlap = query_tokens.intersection(text_tokens)

    if not overlap:
        return 0.0

    return len(overlap) / math.sqrt(len(text_tokens))


def rank_graphic(query: str, graphic: dict) -> float:
    query_tokens = set(tokenize(query))

    score = 0.0

    score += score_overlap(
        query_tokens,
        graphic.get("article_title", "")
    ) * 6.0

    score += score_overlap(
        query_tokens,
        graphic.get("alt", "")
    ) * 5.0

    score += score_overlap(
        query_tokens,
        graphic.get("nearby_text", "")
    ) * 3.0

    keywords = " ".join(graphic.get("keywords", []))

    score += score_overlap(
        query_tokens,
        keywords
    ) * 8.0

    return score


def build_caption(query: str, graphic: dict) -> str:
    nearby = graphic.get("nearby_text", "")

    nearby = re.sub(r"\s+", " ", nearby).strip()

    if len(nearby) > 320:
        nearby = nearby[:317] + "..."

    title = graphic.get("article_title", "COGNITION SmartData")

    return (
        f"This COGNITION SmartData graphic from "
        f"“{title}” provides additional context related to "
        f"'{query}'. {nearby}"
    )


def best_hot_take(query: str) -> dict | None:
    if not HOT_TAKE_PATH.exists():
        return None

    data = json.loads(HOT_TAKE_PATH.read_text())

    graphics = data.get("graphics", [])

    if not graphics:
        return None

    ranked = []

    for g in graphics:
        s = rank_graphic(query, g)

        if s <= 0:
            continue

        ranked.append((s, g))

    if not ranked:
        return None

    ranked.sort(key=lambda x: x[0], reverse=True)

    best = ranked[0][1]

    return {
        "title": best.get("article_title"),
        "article_url": best.get("article_url"),
        "chart_image": best.get("image_url"),
        "caption": build_caption(query, best),
    }
