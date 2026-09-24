from __future__ import annotations

import hashlib
import html
import re
import unicodedata


SOURCE_HANDLES = {
    "moghavematkhabar",
    "khabarfuri",
    "naya_press",
    "bazchishod",
    "alonews",
    "squad_iran",
    "iranian_militarism",
}

TELEGRAM_LINK_RE = re.compile(
    r"(?i)(?:https?://)?(?:t\.me|telegram\.me)/(?:\+?[A-Za-z0-9_\-]+)(?:/\d+)?(?:\?[^\s]*)?"
)
GENERIC_URL_RE = re.compile(r"(?i)(?:https?://|www\.|tg://)\S+")
TELEGRAM_SEARCH_JUNK_RE = re.compile(
    r"(?im)^\s*(?:[|｜]\s*)?#?[A-Za-z]\s*$|^\s*\??q\s*=\s*%23[A-Za-z0-9_%+.-]+\s*$"
)
TELEGRAM_QUERY_FRAGMENT_RE = re.compile(r"(?i)(?:\?|&)q=%23[A-Za-z0-9_%+.-]+")
HANDLE_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_]{3,64})")
MULTISPACE_RE = re.compile(r"[ \t\u200c\u200f]+")
MULTIBLANK_RE = re.compile(r"\n{3,}")
CHANNEL_JUNK_RE = re.compile(r"(?im)^\s*[|｜]\s*(اخبار|news|خبرها)\s*$")
EMOJI_CLUSTER_RE = re.compile(
    r"^(?:[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D\u200B\u20E3\U0001F3FB-\U0001F3FF]|\s)+$"
)
EMOJI_TOKEN_RE = re.compile(r"(?:\[[^\]]+\]\([^\)]+\)|:[a-zA-Z0-9_]+:)")

PROMO_LINE_PATTERNS = [
    re.compile(r"(?i)کانال\s+خبر\s+فوری"),
    re.compile(r"(?i)عضویت\s+(?:در|محدود)"),
    re.compile(r"(?i)ارتباط\s*[،,:|]\s*تبلیغات"),
    re.compile(r"(?i)تبلیغات\s*[|:]"),
    re.compile(r"(?i)آدرس\s+عضویت"),
]

LABEL_PATTERNS = {
    "فوری": re.compile(r"^(?:(?:#\s*)?فوری\s*(?:[|｜:：\-—–]\s*)?)+", re.I),
    "تحلیل": re.compile(r"^(?:(?:#\s*)?تحلیل\s*(?:[|｜:：\-—–]\s*)?)+", re.I),
    "تکمیلی": re.compile(r"^(?:(?:#\s*)?تکمیلی\s*(?:[|｜:：\-—–]\s*)?)+", re.I),
}


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
    text = re.sub(r"(?<!\w)ج\s*[\.\-ـ‌]?\s*ا(?:\s*[\.\-ـ‌]?\s*ا)?(?!\w)", "جمهوری اسلامی ایران", text)
    text = re.sub(r"جمهوری\s+اسلامی(?!\s+ایران)", "جمهوری اسلامی ایران", text)
    text = re.sub(r"جمهوری\s+اسلامی\s+ایران\s+ایران", "جمهوری اسلامی ایران", text)
    return text


def strip_source_links_and_branding(text: str) -> str:
    text = TELEGRAM_LINK_RE.sub("", text)
    text = GENERIC_URL_RE.sub("", text)
    text = TELEGRAM_QUERY_FRAGMENT_RE.sub("", text)

    def handle_repl(match: re.Match[str]) -> str:
        handle = match.group(1).lower()
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


def _merge_emoji_header_lines(text: str) -> str:
    """Join a standalone emoji marker to the following text line."""
    output: list[str] = []
    pending_emoji: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if pending_emoji:
                continue
            if output and output[-1] != "":
                output.append("")
            continue

        if EMOJI_CLUSTER_RE.fullmatch(line):
            pending_emoji.append(line)
            continue

        if pending_emoji:
            line = f"{' '.join(pending_emoji)} {line}"
            pending_emoji.clear()
        output.append(line)

    return "\n".join(output)


def _format_paragraphs(text: str) -> str:
    """Preserve source paragraphs and create a readable Bale news layout."""
    text = MULTIBLANK_RE.sub("\n\n", text)
    raw_parts = [part.strip() for part in text.split("\n\n") if part.strip()]
    paragraphs: list[str] = []
    for part in raw_parts:
        lines = [MULTISPACE_RE.sub(" ", line).strip() for line in part.splitlines() if line.strip()]
        if not lines:
            continue
        # A real Telegram <br> is meaningful. Keep it as a paragraph boundary
        # instead of flattening the entire post into one dense block.
        paragraphs.extend(lines)
    return "\n\n".join(paragraphs)


def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = _normalize_chars(text)
    text = EMOJI_TOKEN_RE.sub("", text)
    text = _merge_emoji_header_lines(text)
    text = strip_source_links_and_branding(text)
    text = CHANNEL_JUNK_RE.sub("", text)
    text = TELEGRAM_SEARCH_JUNK_RE.sub("", text)
    text = normalize_political_terms(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?m)^\s*:\s*", "", text)
    text = re.sub(r"([،,:])\s*\n\s*", r"\1 ", text)
    text = re.sub(r"\s+:", ":", text)
    text = _format_paragraphs(text)
    return text.strip(" \n|｜—-•")


def apply_news_label(text: str, label: str) -> str:
    """Guarantee exactly one leading label and keep it on the news text line."""
    body = (text or "").strip()
    pattern = LABEL_PATTERNS.get(label)
    if pattern:
        body = pattern.sub("", body).lstrip(" |｜:：-—–")
    if not body:
        return f"#{label}"
    return f"#{label}\n\n{body}"


def content_hash(text: str) -> str:
    compact = re.sub(r"\W+", "", _normalize_chars(text).lower(), flags=re.UNICODE)
    return hashlib.sha256(compact.encode("utf-8")).hexdigest()


def append_footer(text: str, category: str) -> str:
    footer = f"صدای رسای امید و آگاهی، رایا مدیا:\n@rayamedia | #{category}"
    return f"{text.rstrip()}\n\n\n{footer}" if text.strip() else footer
