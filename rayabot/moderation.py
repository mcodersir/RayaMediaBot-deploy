from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ModerationResult:
    allowed: bool
    reason: str | None = None
    score: int = 0


BASE = Path(__file__).parent.parent / "data" / "ai_datasets"


def load(name: str, default: list[str]) -> list[str]:
    try:
        value = json.loads((BASE / name).read_text(encoding="utf-8"))
        return [str(item) for item in value]
    except Exception:
        return default


ADS = load("ads_patterns.json", [])
INSULTS = load("insult_patterns.json", [])
RISK = load("risk_terms.json", [])
NEWS = load("news_labels.json", [])
SPAM_PHRASES = ("عضویت", "پیش بینی فوتبال", "کانال")


def normalize(text: str) -> str:
    text = (text or "").replace("ي", "ی").replace("ى", "ی").replace("ك", "ک")
    text = text.replace("\u200c", " ").replace("ـ", "")
    text = re.sub(r"https?://\S+|www\.\S+", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def hit(text: str, patterns: list[str]) -> list[str]:
    lowered = text.lower()
    return [pattern for pattern in patterns if pattern and pattern.lower() in lowered]


def moderate(text: str, **options: bool) -> ModerationResult:
    """Score a post using the local lexicons and honor each safety switch."""
    normalized = normalize(text)
    score = 0
    reasons: list[str] = []

    if options.get("skip_advertisements", True):
        matches = hit(normalized, ADS)
        if all(part in normalized for part in SPAM_PHRASES):
            matches.extend(["عضویت + پیش بینی فوتبال"] * 3)
        if matches:
            score += min(100, 55 + 10 * len(matches))
            reasons.append("advertisement")
    if options.get("skip_profanity", True):
        matches = hit(normalized, INSULTS)
        if matches:
            score += min(100, 55 + 10 * len(matches))
            reasons.append("toxicity")
    if options.get("skip_incitement", True):
        matches = list(dict.fromkeys(hit(normalized, RISK)))
        direct = any(
            term in normalized
            for term in ("بکشید", "بکشند", "قتل عام", "قتل‌عام", "کشتار", "حمله کنید", "آسیب بزنید", "تهدید کنید")
        )
        if direct:
            matches.extend(["direct_incitation"] * 3)
        if matches:
            score += 65 if direct else min(45, 25 + 5 * len(matches))
            reasons.append("risk")
    if len(normalized) < 25:
        score += 20
        reasons.append("too_short")

    return ModerationResult(score < 80, ",".join(reasons) or None, score)
