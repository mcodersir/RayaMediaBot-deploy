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
try:
    NEWS_SIGNALS = json.loads((BASE / "news_signals.json").read_text(encoding="utf-8"))
except Exception:
    NEWS_SIGNALS = {"strong_news": [], "news_style": [], "non_news": [], "engagement_bait": []}

BOT_HANDLE_RE = re.compile(r"(?i)(?:@|(?:https?://)?t\.me/)[A-Za-z0-9_]{3,64}bot\b")
LINK_RE = re.compile(r"(?i)(?:https?://|www\.|t\.me/|tg://|ble\.ir/|bale\.ai/)")
GAMBLING_LINK_RE = re.compile(
    r"(?i)(?:https?://|www\.|t\.me/|tg://|@)[^\s]*(?:marcbet|markbet|1xbet|melbet|betwinner|22bet|bet365|parimatch|casino|sportsbet|bet)[^\s]*"
)

EXPLICIT_AD_PHRASES = (
    "تبلیغات", "آگهی", "اسپانسر", "رپورتاژ", "کد تخفیف",
    "تخفیف ویژه", "فروش ویژه", "پیشنهاد ویژه", "جهت تبلیغ", "برای تبلیغ",
)
CTA_PHRASES = (
    "عضو شوید", "عضو شو", "عضویت", "ثبت نام", "ثبت‌نام", "کلیک کنید",
    "کلیک کن", "سفارش دهید", "سفارش بده", "برای خرید", "خرید کنید",
    "خرید کن", "دایرکت", "پیام دهید", "پیام بدهید", "لینک ورود",
    "لینک عضویت", "همین حالا بخرید", "وارد سایت", "ورود به سایت",
)
COMMERCIAL_PHRASES = (
    "خرید", "فروش", "تخفیف", "قیمت ویژه", "اشتراک", "اکانت", "فیلترشکن",
    "vpn", "قرعه کشی", "قرعه‌کشی", "جایزه", "درآمد تضمینی",
    "سرمایه گذاری تضمینی", "سرمایه‌گذاری تضمینی", "کانفیگ", "کانفینگ",
    "پشتیبانی", "تضمین", "ضمانت", "سرویس ویژه", "سرویس اختصاصی",
    "تک کاربر", "دو کاربر", "سه کاربر", "نامحدود", "ip ثابت",
    "آی پی ثابت", "آی‌پی ثابت", "گیگ", "گیگابایت",
)
SERVICE_SALE_PHRASES = (
    "کانفیگ", "کانفینگ", "فیلترشکن", "vpn", "پروکسی", "سرور",
    "سرویس", "اشتراک", "اکانت", "گیگ", "گیگابایت", "تک کاربر",
    "دو کاربر", "سه کاربر", "نامحدود", "ip ثابت", "آی پی ثابت",
    "پشتیبانی", "تضمین", "ضمانت",
)
PRICE_RE = re.compile(r"(?i)(?:[۰-۹0-9][۰-۹0-9,.٬]*\s*(?:هزار\s*)?تومان|تومان\s*[۰-۹0-9])")
PRICE_LIST_RE = re.compile(r"(?:[۰-۹0-9][۰-۹0-9,.٬]*\s*(?:هزار\s*)?تومان.*?){2,}", re.I | re.S)
GAMBLING_PHRASES = (
    "شرط بندی", "شرط‌بندی", "پیش بینی فوتبال", "پیش‌بینی فوتبال",
    "پیش بینی بازی", "پیش‌بینی بازی", "کازینو", "ضریب بازی", "ضریب برد",
    "برد تضمینی", "marcbet", "markbet", "1xbet", "melbet", "betwinner",
    "22bet", "bet365", "parimatch",
)
SPORTS_BAIT_PHRASES = (
    "این بازی فقط", "بزن بریم", "کی می بره", "کی می‌بره",
    "می برن یا", "می‌برن یا", "پیش بینی کن", "پیش‌بینی کن",
)
SPORTS_TERMS = (
    "فوتبال", "بازی", "تیم", "گل", "برد", "باخت", "مساوی",
    "لیگ", "جام", "بازیکن", "مربی",
)

GAMBLING_PROMO_PHRASES = (
    "سایت بت", "ژتون بت", "فری بت", "freebet", "بونوس", "شارژ حساب",
    "شارژ از طریق", "تسویه حساب", "برداشت آنی", "برداشت سریع",
    "واریز اول", "واریز اولیه", "بدون احراز هویت", "ضریب بالا",
    "پیش بینی آنلاین", "پیش‌بینی آنلاین", "کازینو آنلاین",
    "شرطبندی", "شرط بندی", "شرط‌بندی",
)
VPN_PROMO_PHRASES = (
    "فیلتر شکن", "فیلترشکن", "v2ray", "vless", "vmess", "wireguard",
    "openvpn", "hiddify", "outline", "کانفیگ", "کانفینگ",
    "سرور اختصاصی", "آی پی ثابت", "آی‌پی ثابت", "ip ثابت",
    "تک کاربر", "دو کاربر", "سه کاربر", "نامحدود",
)
TRANSACTION_PHRASES = (
    "خرید", "فروش", "سفارش", "ثبت سفارش", "قیمت", "تومان", "اشتراک",
    "اکانت", "تمدید", "پشتیبانی", "ضمانت", "تضمین", "واریز", "شارژ",
    "پرداخت", "کارت بانکی", "درگاه", "هدیه", "تخفیف", "بونوس",
)
PERCENT_RE = re.compile(r"[۰-۹0-9]+\s*%")



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
    service_sale = hit(normalized, SERVICE_SALE_PHRASES)
    gambling = hit(normalized, GAMBLING_PHRASES)
    sports_bait = hit(normalized, SPORTS_BAIT_PHRASES)
    sports_terms = hit(normalized, SPORTS_TERMS)
    gambling_promo = hit(normalized, GAMBLING_PROMO_PHRASES)
    vpn_promo = hit(normalized, VPN_PROMO_PHRASES)
    transaction = hit(normalized, TRANSACTION_PHRASES)
    lexicon = list(dict.fromkeys(hit(normalized, ADS)))
    has_bot = BOT_HANDLE_RE.search(raw) is not None
    link_count = len(LINK_RE.findall(raw))
    gambling_link = GAMBLING_LINK_RE.search(raw) is not None
    price_count = len(PRICE_RE.findall(normalized))
    price_list = PRICE_LIST_RE.search(normalized) is not None
    percent_offer = PERCENT_RE.search(normalized) is not None

    if explicit:
        score = max(score, 90)
    if gambling or gambling_link:
        score = max(score, 100)
    if gambling_promo and (transaction or percent_offer or has_bot or link_count):
        score = 100
    if len(set(gambling_promo)) >= 2:
        score = 100
    if vpn_promo and (transaction or price_count or has_bot or link_count):
        score = 100
    if len(set(vpn_promo)) >= 3:
        score = 100
    if has_bot:
        score += 55
    if cta:
        score += min(35, 15 + 5 * len(cta))
    if commercial:
        score += min(40, 10 + 6 * len(commercial))
    if service_sale and price_count:
        score = max(score, 95)
    if len(set(service_sale)) >= 3:
        score = max(score, 90)
    if price_list or price_count >= 2:
        score = max(score, 92)
    if price_count:
        score += min(30, 10 * price_count)
    if link_count:
        score += min(20, 10 + 5 * min(link_count, 2))
    if lexicon:
        score += min(30, 10 + 5 * len(lexicon))
    if has_bot and (cta or commercial or link_count):
        score = max(score, 90)
    if sports_bait and len(set(sports_terms)) >= 2:
        # Sports engagement bait from news sources is commonly an embedded
        # betting/promo post rather than a news item.
        score = max(score, 90)
    if commercial and cta:
        score = max(score, 90)
    if has_bot and (service_sale or price_count):
        score = 100
    return min(100, score)


def news_likelihood(text: str) -> tuple[int, str | None]:
    """Conservative local news-vs-noise classifier.

    It rejects obvious social/engagement filler while allowing short breaking
    headlines. Political names and viewpoints are intentionally not used as
    positive or negative signals.
    """
    normalized = normalize(text)
    if not normalized:
        return 0, "empty"

    strong = hit(normalized, NEWS_SIGNALS.get("strong_news", []))
    style = hit(normalized, NEWS_SIGNALS.get("news_style", []))
    non_news = hit(normalized, NEWS_SIGNALS.get("non_news", []))
    bait = hit(normalized, NEWS_SIGNALS.get("engagement_bait", []))

    score = 35
    score += min(45, 18 * len(set(strong)))
    score += min(25, 10 * len(set(style)))
    if re.search(r"[۰-۹0-9]", normalized):
        score += 5
    if len(normalized) >= 55:
        score += 8
    if len(normalized) >= 120:
        score += 5
    score -= min(60, 25 * len(set(non_news)))
    score -= min(45, 20 * len(set(bait)))

    # A short factual breaking headline can still be valid news.
    if strong and len(normalized) >= 18:
        score = max(score, 62)
    score = max(0, min(100, score))
    return score, None if score >= 48 else "non_news"


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

    news_score, news_reason = news_likelihood(raw)
    category_scores.append(100 - news_score)
    if options.get("skip_non_news", True) and news_reason:
        reasons.append(news_reason)

    score = max(category_scores, default=0)
    return ModerationResult(not reasons, ",".join(reasons) or None, score)
