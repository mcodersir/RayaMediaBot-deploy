from __future__ import annotations

import hashlib
import html
import re
import unicodedata


SOURCE_HANDLES = {
    "moghavematkhabar",
    "khabarfuri",
    "naya_press",
    "BazChiShod",
    "alonews",
    "squad_iran",
    "Iranian_Militarism",
}

TELEGRAM_LINK_RE = re.compile(
    r"(?i)(?:https?://)?(?:t\.me|telegram\.me)/(?:\+?[A-Za-z0-9_\-]+)(?:/\d+)?(?:\?[^\s]*)?"
)
HANDLE_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_]{3,64})")
MULTISPACE_RE = re.compile(r"[ \t\u200c\u200f]+")
MULTIBLANK_RE = re.compile(r"\n{3,}")
CHANNEL_JUNK_RE = re.compile(r"(?im)^\s*[|｜]\s*(اخبار|news|خبرها)\s*$")
EMOJI_CLUSTER_RE = re.compile(r"^(?:[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D\u200B\u20E3\U0001F3FB-\U0001F3FF]|\s)+")

# Telegram channel headers often contain only emoji markers. They are source decorations, not news.
EMOJI_TOKEN_RE = re.compile(r"(?:\[[^\]]+\]\([^\)]+\)|:[a-zA-Z0-9_]+:)")


PROMO_LINE_PATTERNS = [
    re.compile(r"(?i)کانال\s+خبر\s+فوری"),
    re.compile(r"(?i)عضویت\s+(?:در|محدود)"),
    re.compile(r"(?i)ارتباط\s*[،,:|]\s*تبلیغات"),
    re.compile(r"(?i)تبلیغات\s*[|:]"),
    re.compile(r"(?i)آدرس\s+عضویت"),
]


def _normalize_chars(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    replacements = {
        "ي": "ی",
        "ى": "ی",
        "ك": "ک",
        "ة": "ه",
        "ۀ": "ه",
        "ؤ": "و",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def normalize_political_terms(text: str) -> str:
    # Normalize abbreviated forms such as ج.ا / ج ا / ج‌.ا to the requested full form.
    text = re.sub(r"(?<!\w)ج\s*[\.\-ـ‌]?\s*ا(?:\s*[\.\-ـ‌]?\s*ا)?(?!\w)", "جمهوری اسلامی ایران", text)
    # Avoid producing "جمهوری اسلامی ایران ایران" when already complete.
    text = re.sub(r"جمهوری\s+اسلامی(?!\s+ایران)", "جمهوری اسلامی ایران", text)
    text = re.sub(r"جمهوری\s+اسلامی\s+ایران\s+ایران", "جمهوری اسلامی ایران", text)
    return text


def strip_source_links_and_branding(text: str) -> str:
    text = TELEGRAM_LINK_RE.sub("", text)

    def handle_repl(match: re.Match[str]) -> str:
        handle = match.group(1).lower()
        # Incoming Telegram usernames are treated as source/channel promotion and removed.
        # The Raya Media footer is appended later by append_footer().
        return match.group(0) if handle == "rayamedia" else ""

    text = HANDLE_RE.sub(handle_repl, text)

    kept: list[str] = []
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            kept.append("")
            continue
        lower = cleaned.lower()
        if any(f"@{h}" in lower for h in SOURCE_HANDLES):
            continue
        if any(p.search(cleaned) for p in PROMO_LINE_PATTERNS):
            continue
        kept.append(line)
    return "\n".join(kept)


def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = _normalize_chars(text)
    text = strip_source_links_and_branding(text)
    # Remove Telegram/Bale markdown emoji links and reaction headers.
    text = EMOJI_TOKEN_RE.sub("", text)
    # Remove standalone reaction/header emoji clusters that appear before news titles.
    text = re.sub(r"(?m)^\s*[〰️~•·▪️◾️◽️]+\s*", "", text)
    lines = []
    for line in text.splitlines():
        if len(EMOJI_CLUSTER_RE.sub("", line).strip()) == 0:
            continue
        lines.append(line)
    text = "\n".join(lines)
    text = CHANNEL_JUNK_RE.sub("", text)
    text = normalize_political_terms(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = MULTISPACE_RE.sub(" ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = MULTIBLANK_RE.sub("\n\n", text)
    text = re.sub(r"(?m)^\s*:\s*", "", text)
    text = re.sub(r"([،,:])\s*\n\s*", r"\1 ", text)
    text = re.sub(r"\s+:", ":", text)
    return text.strip(" \n|—-•")


def content_hash(text: str) -> str:
    compact = re.sub(r"\W+", "", _normalize_chars(text).lower(), flags=re.UNICODE)
    return hashlib.sha256(compact.encode("utf-8")).hexdigest()


def append_footer(text: str, category: str) -> str:
    footer = f"صدای رسای امید و آگاهی، رایا مدیا:\n@rayamedia | #{category}"
    return f"{text.rstrip()}\n\n{footer}" if text.strip() else footer
