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


# Real footer/signature patterns observed on the configured Telegram sources.
# These are removed BEFORE URLs/handles/emojis are stripped, so no residue such
# as "Join us", "| #T", a bare brand name, or a lone footer emoji survives.
SOURCE_FOOTER_HANDLES = {
    "moghavematkhabar", "khabarfuri", "naya_press", "bazchishod",
    "alonews", "squad_iran", "iranian_militarism",
    "akhbartelfori", "snntv", "snn_sports", "snnuni",
    "newscenter", "irankhabar", "khabaronline_ir", "entekhab_ir",
    "eghtesadnews_com", "myasriran",
}

SOURCE_FOOTER_PHRASES = (
    "کانال خبر فوری مقاومت نیوز",
    "join us",
    "دریافت آخرین اخبار",
    "ما را دنبال کنید",
    "با ما همراه باشید",
    "عضو کانال شوید",
)

SOURCE_FOOTER_LINE_PATTERNS = (
    re.compile(r"(?i)^\s*[^\n]{0,20}@?moghavematkhabar[^\n]{0,20}\s*$"),
    re.compile(r"(?i)^\s*[^\n]{0,20}@?khabarfuri\s*\|\s*اخبار\s*$"),
    re.compile(r"(?i)^\s*[^\n]{0,20}@?naya_press[^\n]{0,10}\s*$"),
    re.compile(r"(?i)^\s*[^\n]{0,20}@?alonews[^\n]{0,10}\s*$"),
    re.compile(r"(?i)^\s*[^\n]{0,20}@?squad_iran\s*\|\s*#?[a-z0-9_]+\s*$"),
    re.compile(r"(?i)^\s*join\s+us\s*\|?\s*@?iranian_militarism\s*$"),
    re.compile(r"(?i)^\s*[^\n]{0,20}@?akhbartelfori[^\n]{0,10}\s*$"),
    re.compile(r"(?i)^\s*[^\n]{0,20}@?newscenter[^\n]{0,10}\s*$"),
    re.compile(r"(?i)^\s*[^\n]{0,20}@?irankhabar[^\n]{0,10}\s*$"),
    re.compile(r"(?i)^\s*[^\n]{0,20}@?khabaronline_ir\s*\|\s*(?:https?://)?(?:www\.)?khabaronline\.ir/?\s*$"),
    re.compile(r"(?i)^\s*[^\n]{0,20}@?entekhab_ir[^\n]{0,10}\s*$"),
    re.compile(r"(?i)^\s*[^\n]{0,20}@?eghtesadnews_com[^\n]{0,10}\s*$"),
    re.compile(r"(?i)^\s*(?:https?://)?(?:www\.)?asriran\.com/?\s*$"),
    re.compile(r"(?i)^\s*[^\n]{0,20}@?myasriran[^\n]{0,10}\s*$"),
    re.compile(r"(?i)^\s*[^\n]{0,20}@?snntv[^\n]{0,10}\s*$"),
)

TELEGRAM_LINK_RE = re.compile(
    r"(?i)(?:https?://)?(?:t\.me|telegram\.me)/(?:\+?[A-Za-z0-9_\-]+)(?:/\d+)?(?:\?[^\s]*)?"
)
GENERIC_URL_RE = re.compile(r"(?i)(?:https?://|www\.|tg://)\S+")
BARE_DOMAIN_RE = re.compile(
    r"(?i)(?<![\\w@])(?:[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?\\.)+"
    r"(?:ir|com|org|net|me|io|co|tv|news|info)(?:/[^\\s<>()\\[\\]{}]*)?"
)
SOURCE_HASHTAG_RE = re.compile(r"(?<!\\w)#[\\w\\u0600-\\u06FF\\u200c_-]+", re.UNICODE)
DECORATIVE_EMOJI_RE = re.compile(r"[\\U0001F000-\\U0001FAFF\\u25A0-\\u27BF]")
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
BULLET_EMOJIS = "🔴🟠🟡🟢🔵🟣⚫⚪🟥🟧🟨🟩🟦🟪✅☑❌🚨🔺🔻📌"
BULLET_RE = re.compile(f"([{re.escape(BULLET_EMOJIS)}])")
INLINE_CTA_RE = re.compile(
    r"(?i)\b(?:join\s+us|follow\s+us|subscribe(?:\s+now)?|click\s+here|read\s+more|our\s+channel)\b[!！.。…\s]*"
)

SOURCE_BRAND_LINE_RE = re.compile(
    r"(?i)^\s*(?:"
    r"(?:id\s*)?[a-z][a-z0-9_.-]{2,64}|"
    r"(?:[a-z0-9-]+\.)+(?:ir|com|org|net|me|io|co|tv|news|info)"
    r")\s*$"
)
SOURCE_CTA_FA_RE = re.compile(
    r"(?i)(?:"
    r"(?:در\s+)?کانال\s+(?:یوتیوب|تلگرام|ایتا|بله|روبیکا).*?(?:ببینید|بخوانید|دنبال\s+کنید)|"
    r"(?:خبر|متن|ویدئو|گزارش)\s+(?:کامل|بیشتر).*?(?:اینجا|ببینید|بخوانید)|"
    r"(?:کافه\s+خبر|خبرآنلاین).*?(?:اینجاست|ببینید|بخوانید)|"
    r"(?:عضو|همراه)\s+(?:کانال|ما)\s+شوید"
    r")"
)

PROMO_LINE_PATTERNS = [
    re.compile(r"(?i)کانال\s+خبر\s+فوری"),
    re.compile(r"(?i)عضویت\s+(?:در|محدود)"),
    re.compile(r"(?i)ارتباط\s*[،,:|]\s*تبلیغات"),
    re.compile(r"(?i)تبلیغات\s*[|:]"),
    re.compile(r"(?i)آدرس\s+عضویت"),
    re.compile(r"(?i)^\s*join\s+us\s*$"),
    re.compile(r"(?i)^\s*follow\s+us\s*$"),
    re.compile(r"(?i)^\s*subscribe\s*(?:now)?\s*$"),
    re.compile(r"(?i)^\s*click\s+here\s*$"),
    re.compile(r"(?i)^\s*read\s+more\s*$"),
    re.compile(r"(?i)^\s*our\s+channel\s*$"),
    re.compile(r"(?i)ترجمه\s+اختصاصی"),
    re.compile(r"(?i)دریافت\s+آخرین\s+اخبار"),
    re.compile(r"(?i)آخرین\s+اخبار\s*[:：]"),
    re.compile(r"(?i)ما\s+را\s+دنبال\s+کنید"),
    re.compile(r"(?i)با\s+ما\s+همراه\s+باشید"),
    re.compile(r"(?i)در\s+شبکه[‌\s-]*های\s+اجتماعی"),
    re.compile(r"(?i)لینک\s+(?:کانال|عضویت|خبر)"),
    re.compile(r"(?i)متن\s+(?:کامل\s+)?(?:گفت[\s‌-]*و[\s‌-]*گو|گفتگو).*?(?:اینجاست|اینجا|بخوانید|ببینید)"),
    re.compile(r"(?i)(?:این\s*ها|اینها).*?(?:بخوانید|ببینید)"),
    re.compile(r"(?i)(?:تحلیل|تأمل)(?:\s+و\s+(?:تحلیل|تأمل))?\s+بیشتر"),
    re.compile(r"(?i)خبر\s+از\s+دست\s+ندهید"),
    re.compile(r"(?i)جزئیات\s+(?:بیشتر\s+)?(?:در|اینجا)"),
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


def _remove_known_source_footer_lines(text: str) -> str:
    """Remove complete source signatures before destructive markup cleanup."""
    kept: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lower = line.lower()

        if not line:
            kept.append("")
            continue

        if any(pattern.search(line) for pattern in SOURCE_FOOTER_LINE_PATTERNS):
            continue

        if any(phrase in lower for phrase in SOURCE_FOOTER_PHRASES):
            # "دریافت آخرین اخبار" and similar lines are source UI/CTA, not news.
            continue

        handles = {match.lower() for match in re.findall(r"@([A-Za-z0-9_]{3,64})", line)}
        if handles & SOURCE_FOOTER_HANDLES:
            # Source signatures are short branding rows. Drop the whole row
            # before handle stripping, which otherwise leaves emoji/pipes/tags.
            if len(line) <= 140 or "|" in line or "｜" in line:
                continue

        # Typical source footer: a domain/brand plus a handle on adjacent rows.
        compact = DECORATIVE_EMOJI_RE.sub("", line).replace("\ufe0f", "").strip(" |｜—–-،,:؛")
        if re.fullmatch(
            r"(?i)(?:moghavematkhabar|khabarfuri|naya_press|bazchishod|alonews|"
            r"squad_iran|iranian_militarism|akhbartelfori|newscenter|irankhabar|"
            r"snntv|khabaronline_ir|entekhab_ir|eghtesadnews_com|myasriran)",
            compact,
        ):
            continue

        kept.append(raw_line)
    return "\n".join(kept)


def strip_source_links_and_branding(text: str) -> str:
    text = _remove_known_source_footer_lines(text)
    text = TELEGRAM_LINK_RE.sub("", text)
    text = GENERIC_URL_RE.sub("", text)
    text = BARE_DOMAIN_RE.sub("", text)
    text = TELEGRAM_QUERY_FRAGMENT_RE.sub("", text)
    # Source posts often carry decorative bullets, arrows and inline social
    # branding. RayaMedia adds its own clean footer later, so remove all source
    # hashtags/emojis here instead of forwarding their visual clutter.
    text = SOURCE_HASHTAG_RE.sub("", text)
    text = DECORATIVE_EMOJI_RE.sub("", text)
    text = text.replace("\\ufe0f", "").replace("\\u200d", "")

    def handle_repl(match: re.Match[str]) -> str:
        handle = match.group(1).lower()
        return match.group(0) if handle == "rayamedia" else ""

    text = HANDLE_RE.sub(handle_repl, text)

    kept: list[str] = []
    for line in text.splitlines():
        cleaned = line.strip(" \\t|｜—–-،,:؛")
        if not cleaned:
            kept.append("")
            continue
        lower = cleaned.lower()
        if any(f"@{h}" in lower for h in SOURCE_HANDLES):
            continue
        if any(p.search(cleaned) for p in PROMO_LINE_PATTERNS):
            continue
        if re.fullmatch(r"(?i)(?:join|follow|subscribe|channel|telegram|source)\s*(?:us|now)?[!\s]*", cleaned):
            continue
        # Telegram sources frequently append a plain Latin brand/ID after an
        # emoji or link. Once markup is stripped it looks like ordinary text.
        if SOURCE_BRAND_LINE_RE.fullmatch(cleaned):
            continue
        if SOURCE_CTA_FA_RE.search(cleaned):
            continue
        # Do not preserve source separators after their links/hashtags vanish.
        kept.append(cleaned)
    return "\n".join(kept)


def _cleanup_source_residue(text: str) -> str:
    """Remove source-channel CTA/branding residue after links/handles are stripped."""
    text = INLINE_CTA_RE.sub("", text)
    text = re.sub(r"(?im)^\s*(?:join|follow|subscribe|channel|telegram|source)\s*(?:us|now)?[!！.。…\s]*$", "", text)
    text = re.sub(r"(?im)^\s*(?:عضویت|ورود|لینک عضویت|کانال ما|منبع)\s*$", "", text)
    text = SOURCE_CTA_FA_RE.sub("", text)
    text = re.sub(
        r"(?im)^\s*(?:id\s*)?[a-z][a-z0-9_.-]{2,64}\s*$",
        "",
        text,
    )
    text = re.sub(
        r"(?im)^\s*(?:[a-z0-9-]+\.)+(?:ir|com|org|net|me|io|co|tv|news|info)\s*$",
        "",
        text,
    )

    patterns = [
        r"ترجمه\s+اختصاصی(?:\s+[A-Za-z0-9_.-]+)?",
        r"دریافت\s+آخرین\s+اخبار\s*[:：]?.*",
        r"آخرین\s+اخبار\s*[:：].*",
        r"ما\s+را\s+دنبال\s+کنید.*",
        r"با\s+ما\s+همراه\s+باشید.*",
        r"در\s+شبکه[‌\s-]*های\s+اجتماعی.*",
        r"لینک\s+(?:کانال|عضویت|خبر).*",
        r"متن\s+(?:کامل\s+)?(?:گفت[\s‌-]*و[\s‌-]*گو|گفتگو).*?(?:اینجاست|اینجا|بخوانید|ببینید).*",
        r"(?:این\s*ها|اینها).*?(?:بخوانید|ببینید).*",
        r"(?:برای\s+)?(?:تحلیل|تأمل)(?:\s+و\s+(?:تحلیل|تأمل))?\s+(?:بیشتر|بیشتر\s+بخوانید).*",
        r"خبر\s+از\s+دست\s+ندهید.*",
        r"جزئیات\s+(?:بیشتر\s+)?(?:در|اینجا).*",
        r"(?:سایت|ایتا|بله|روبیکا|سروش\s*پلاس)(?:\s*[|｜،,-]\s*(?:سایت|ایتا|بله|روبیکا|سروش\s*پلاس)){1,}",
    ]
    for pattern in patterns:
        text = re.sub(rf"(?im)^\s*[👉👈🔗📲📢•\-–—]*\s*(?:{pattern})\s*$", "", text)
    return text


def _strip_trailing_source_footer(text: str) -> str:
    """Drop trailing source branding blocks without touching the news body."""
    lines = text.splitlines()
    source_words = (
        "ترجمه اختصاصی", "دریافت آخرین اخبار", "آخرین اخبار:",
        "ما را دنبال کنید", "با ما همراه باشید", "شبکه های اجتماعی",
        "شبکه‌های اجتماعی", "سروش پلاس", "روبیکا", "ایتا",
        "join us", "follow us", "subscribe",
    )
    while lines:
        tail = lines[-1].strip()
        if not tail:
            lines.pop()
            continue
        low = tail.lower()
        if any(word.lower() in low for word in source_words):
            lines.pop()
            continue
        if re.fullmatch(r"[👉👈🔗📲📢•|｜\-–—\s]+", tail):
            lines.pop()
            continue
        break
    return "\n".join(lines)


def _structure_bullets(text: str) -> str:
    """Turn inline source bullet emojis into proper paragraphs and remove orphans."""
    # A bullet embedded in the middle of a sentence starts a new paragraph.
    text = re.sub(
        f"(?<=\\S)\\s*([{re.escape(BULLET_EMOJIS)}])\\s*(?=\\S)",
        r"\n\n\1 ",
        text,
    )

    lines = text.splitlines()
    output: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            if output and output[-1] != "":
                output.append("")
            i += 1
            continue

        # Source-channel buttons frequently leave a bare emoji after the URL is removed.
        if EMOJI_CLUSTER_RE.fullmatch(line):
            bullet_match = BULLET_RE.fullmatch(line.replace("\ufe0f", ""))
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if bullet_match and j < len(lines):
                nxt = lines[j].strip()
                # Keep only when there is actual following news text; otherwise drop it.
                if nxt and not EMOJI_CLUSTER_RE.fullmatch(nxt) and len(re.sub(r"\W+", "", nxt, flags=re.UNICODE)) >= 6:
                    output.append(f"{line} {nxt}")
                    i = j + 1
                    continue
            i += 1
            continue

        # A trailing bullet with no words after it is residue.
        line = re.sub(f"\\s*([{re.escape(BULLET_EMOJIS)}])\\s*$", "", line).strip()
        if line:
            output.append(line)
        i += 1

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
    text = strip_source_links_and_branding(text)
    text = _cleanup_source_residue(text)
    text = CHANNEL_JUNK_RE.sub("", text)
    text = TELEGRAM_SEARCH_JUNK_RE.sub("", text)
    text = _structure_bullets(text)
    text = normalize_political_terms(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?m)^\s*:\s*", "", text)
    text = re.sub(r"\s+:", ":", text)
    text = _format_paragraphs(text)
    # Final pass catches CTA/emoji residue revealed only after whitespace cleanup.
    text = _cleanup_source_residue(text)
    text = _structure_bullets(text)
    text = _strip_trailing_source_footer(text)
    # Remove separators left on otherwise-empty lines after URL/CTA stripping.
    text = re.sub(r"(?m)^[ \\t|｜—–\\-،,:؛]+$", "", text)
    text = MULTIBLANK_RE.sub("\n\n", text)
    return text.strip(" \n|｜—–-•،,:؛")


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
