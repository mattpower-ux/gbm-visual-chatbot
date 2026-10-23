"""Private, evidence-linked editorial leads; no public model or archive access."""
import re
from collections import Counter, defaultdict
from app.reader_data import read_events, logging_status, redact

TOPICS = {
    "Heat pumps": (r"heat pump|mini.?split|geothermal", "Which heat pump tradeoffs are readers struggling to resolve?"),
    "Electrification": (r"electrif|electric panel|panel upgrade|induction", "The practical obstacles between wanting an electric home and building one"),
    "Healthy homes": (r"healthy home|indoor air|ventilat|mold|iaq|voc", "Which healthy-home improvements solve readers' specific concerns?"),
    "Housing affordability": (r"afford|housing cost|mortgage|rent", "What does affordable housing mean after all the monthly costs?"),
    "Resilience": (r"resilien|wildfire|flood|hurricane|insurance", "Where resilience advice meets insurance and retrofit costs"),
    "Solar and storage": (r"solar|battery|batteries|storage", "The decisions holding readers back from solar and storage"),
    "Building materials": (r"insulat|window|concrete|timber|floor|cabinet|countertop", "How to compare materials when cost, health and performance conflict"),
    "Codes and incentives": (r"building code|tax credit|rebate|incentive|permit", "Which rules and incentives are readers finding hardest to navigate?"),
}
CONSTRAINTS = {"Cost": r"cost|budget|expens|afford|price", "Climate": r"cold|hot|climate|humid", "Existing homes": r"retrofit|existing|old home|renovat", "Installation": r"install|contractor|panel|wiring", "Health": r"asthma|allerg|health|air quality", "Timing": r"when|deadline|how long|wait"}


def build_report(days=30):
    records = read_events(limit=20001, days=days)
    truncated = len(records) > 20000
    records = records[:20000]
    excluded = Counter()
    sessions = Counter(row.get("session_id") for row in records)
    bursts = Counter((row.get("session_id"), row.get("created_at", "")[:16]) for row in records)
    groups = defaultdict(list)
    seen = set()
    accepted = []
    for row in records:
        traffic = row.get("traffic_class", "legacy")
        if traffic in {"test", "legacy"}:
            excluded[traffic] += 1
            continue
        sid = row.get("session_id") or row["id"]
        if sessions[sid] > 100 * max(1, days):
            excluded["high_volume"] += 1
            continue
        if bursts[(row.get("session_id"), row.get("created_at", "")[:16])] > 8:
            excluded["rapid_queries"] += 1
            continue
        question = redact(row.get("question", ""))
        normalized = re.sub(r"\W+", " ", question.lower()).strip()
        key = (sid, normalized)
        if key in seen:
            excluded["repeat"] += 1
            continue
        seen.add(key)
        row = dict(row, question=question)
        accepted.append(row)
        matches = [topic for topic, (pattern, _) in TOPICS.items() if re.search(pattern, question, re.I)]
        for topic in matches or ["Other reader questions"]:
            groups[topic].append(row)
    themes = []
    for topic, rows in groups.items():
        distinct = len({row.get("session_id") or row["id"] for row in rows})
        constraints = Counter(name for row in rows for name, pattern in CONSTRAINTS.items() if re.search(pattern, row["question"], re.I))
        sources = Counter(source.get("url", "") for row in rows for source in row.get("public_sources", []) if source.get("url"))
        themes.append({"topic": topic, "questions": len(rows), "sessions": distinct,
                       "signal": "Repeated across sessions" if distinct >= 3 else "Early signal - limited sample",
                       "angle": TOPICS.get(topic, ("", "Review these questions for a new reporting theme"))[1],
                       "constraints": dict(constraints),
                       "weak_answers": sum(not row.get("public_sources") or bool(re.search(r"couldn't find|not seeing|insufficient|not specifically|don't have", row.get("answer", ""), re.I)) for row in rows),
                       "examples": [{"question": row["question"], "id": row["id"], "date": row["created_at"]} for row in rows[:5]],
                       "coverage": [{"url": url, "count": n} for url, n in sources.most_common(4)]})
    themes.sort(key=lambda item: (item["sessions"], item["questions"]), reverse=True)
    by_session = defaultdict(list)
    for row in accepted:
        by_session[row.get("session_id") or row["id"]].append(row)
    journeys = [[{"question": row["question"], "date": row["created_at"]} for row in sorted(rows, key=lambda item: item["created_at"])[:6]] for rows in by_session.values() if len(rows) > 1][:10]
    return {"days": days, "questions": len(accepted), "sessions": len(by_session), "excluded": dict(excluded), "truncated": truncated,
            "themes": themes, "journeys": journeys, "logging": logging_status(),
            "note": "Counts describe anonymous chatbot sessions, not unique people or a representative survey. Automation can evade detection. Angles are reporting prompts, not findings. Personal-detail redaction is best effort; review examples before sharing."}
