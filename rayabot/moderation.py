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

BOT_HANDLE_RE = re.compile(r"(?i)(?:@|(?:https?://)?t\.me/)[A-Za-z0-9_]{3,64}bot\b")
LINK_RE = re.compile(r"(?i)(?:https?://|www\.|t\.me/|ble\.ir/|bale\.ai/)")

EXPLICIT_AD_PHRASES = (
    "تبلیغات", "آگهی", "اسپانسر", "رپورتاژ", "کد تخفیف",
    "تخفیف ویژه", "فروش ویژه", "پیشنهاد ویژه", "جهت تبلیغ", "برای تبلیغ",
)
CTA_PHRASES = (
    "عضو شوید", "عضو شو", "عضویت", "ثبت نام", "ثبت‌نام", "کلیک کنید",
    "کلیک کن", "سفارش دهید", "سفارش بده", "برای خرید", "خرید کنید",
    "خرید کن", "دایرکت", "پیام دهید", "پیام بدهید", "لینک ورود",
    "لینک عضویت", "همین حالا بخرید",
)
COMMERCIAL_PHRASES = (
    "خرید", "فروش", "تخفیف", "قیمت ویژه", "اشتراک", "اکانت", "فیلترشکن",
    "vpn", "قرعه کشی", "قرعه‌کشی", "جایزه", "پیش بینی فوتبال",
    "پیش‌بینی فوتبال", "شرط بندی", "شرط‌بندی", "کازینو", "درآمد تضمینی",
    "سرمایه گذاری تضمینی", "سرمایه‌گذاری تضمینی",
)


def normalize(text: str) -> str:
    text = (text or "").replace("ي", "ی").replace("ى", "ی").replace("ك", "ک")
    text = text.replace("\u200c", " ").replace("ـ", "")
    return re.sub(r"\s+", " ", text).strip()


def hit(text: str, patterns) -> list[str]:
    lowered = text.lower()
    return [pattern for pattern in patterns if pattern and pattern.lower() in lowered]


def _advertisement_score(raw: str, normalized: str) -> int:
    score = 0
    explicit = hit(normalized, EXPLICIT_AD_PHRASES)
    cta = hit(normalized, CTA_PHRASES)
    commercial = hit(normalized, COMMERCIAL_PHRASES)
    lexicon = list(dict.fromkeys(hit(normalized, ADS)))
    has_bot = BOT_HANDLE_RE.search(raw) is not None
    link_count = len(LINK_RE.findall(raw))

    if explicit:
        score = max(score, 90)
    if has_bot:
        score += 55
    if cta:
        score += min(35, 15 + 5 * len(cta))
    if commercial:
        score += min(30, 10 + 5 * len(commercial))
    if link_count:
        score += min(20, 10 + 5 * min(link_count, 2))
    if lexicon:
        score += min(30, 10 + 5 * len(lexicon))
    if has_bot and (cta or commercial or link_count):
        score = max(score, 90)
    if "عضویت" in normalized and ("پیش بینی فوتبال" in normalized or "پیش‌بینی فوتبال" in normalized):
        score = max(score, 100)
    if commercial and cta:
        score = max(score, 85)
    return min(100, score)


def moderate(text: str, **options: bool) -> ModerationResult:
    raw = text or ""
    normalized = normalize(raw)
    reasons: list[str] = []
    category_scores: list[int] = []

    if options.get("skip_advertisements", True):
        ad_score = _advertisement_score(raw, normalized)
        category_scores.append(ad_score)
        if ad_score >= 80:
            reasons.append("advertisement")

    if options.get("skip_profanity", True):
        insult_matches = list(dict.fromkeys(hit(normalized, INSULTS)))
        toxicity_score = min(100, 45 + 15 * len(insult_matches)) if insult_matches else 0
        category_scores.append(toxicity_score)
        if toxicity_score >= 80:
            reasons.append("toxicity")

    if options.get("skip_incitement", True):
        risk_matches = list(dict.fromkeys(hit(normalized, RISK)))
        direct = any(term in normalized for term in (
            "بکشید", "بکشند", "قتل عام کنید", "کشتار کنید",
            "حمله کنید", "آسیب بزنید", "تهدید کنید",
        ))
        risk_score = 90 if direct else min(70, 20 + 8 * len(risk_matches)) if risk_matches else 0
        category_scores.append(risk_score)
        if risk_score >= 80:
            reasons.append("risk")

    score = max(category_scores, default=0)
    return ModerationResult(not reasons, ",".join(reasons) or None, score)
