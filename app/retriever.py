import os
from pathlib import Path
import re

# If DEMO_MODE=1, read docs from docs_demo, else read from docs
BASE_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = BASE_DIR / ("docs_demo" if os.getenv("DEMO_MODE") == "1" else "docs")


def load_docs():
    docs = []
    for name in ["faq.md", "policies.md", "hours_location.md", "seasonality.md"]:
        p = DOCS_DIR / name
        if p.exists():
            docs.append({"name": name, "text": p.read_text(encoding="utf-8", errors="ignore")})
    return docs


def chunk_text(text, max_chars=700):
    sections = re.split(r"\n(?=##\s+)", text)
    chunks = []

    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue

        lines = sec.splitlines()
        title = lines[0].lstrip("# ").strip().lower() if lines else ""
        body = "\n".join(lines[1:]).strip()

        if not body:
            chunks.append({"title": title, "text": ""})
            continue

        parts = re.split(r"\n{2,}", body)
        buf = ""

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if len(buf) + len(part) + 2 <= max_chars:
                buf = (buf + "\n\n" + part).strip()
            else:
                if buf:
                    chunks.append({"title": title, "text": buf})
                buf = part

        if buf:
            chunks.append({"title": title, "text": buf})

    return chunks


def score(query, item):
    q = query.lower()
    title = (item.get("title") or "").lower()
    text = (item.get("chunk") or "").lower()

    intent_title_keywords = {
        "refund": ["refund"],
        "return": ["refund"],
        "delivery": ["delivery"],
        "pickup": ["pickup"],
        "hour": ["hour", "hours"],
        "time": ["hour", "hours"],
        "quality": ["quality"],
        "fresh": ["quality"],
        "substitution": ["substitution"],
        "substitute": ["substitution"],
        "order": ["order"],
        "ordering": ["order"],
        "purchase": ["order"],
    }

    for intent, kws in intent_title_keywords.items():
        if intent in q:
            for kw in kws:
                if kw in title:
                    return 20

    if "policy" in q:
        q_words = set(re.findall(r"[a-z0-9]+", q))
        title_words = set(re.findall(r"[a-z0-9]+", title))
        overlap = len(q_words.intersection(title_words))
        if overlap > 0:
            return 15 + overlap

    words = [w for w in re.findall(r"[a-z0-9]+", q) if len(w) >= 4]
    hits = sum(1 for w in words if w in text)
    return hits


def retrieve_top(query, top_k=3):
    docs = load_docs()
    all_items = []

    for d in docs:
        for ch in chunk_text(d["text"]):
            all_items.append({"source": d["name"], "title": ch["title"], "chunk": ch["text"]})

    scored = []
    for item in all_items:
        s = score(query, item)
        scored.append({**item, "score": s})

    def sort_key(item):
        s = item["score"]
        if item["source"] == "policies.md":
            s += 5
        return s

    scored.sort(key=sort_key, reverse=True)
    return scored[:top_k]
