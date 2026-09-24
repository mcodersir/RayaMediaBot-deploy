"""Offline Persian NLP used by RayaMedia.

The project deliberately has no remote-AI dependency. This module combines
Persian normalization, a small tokenizer/stemmer, TF-IDF sentence salience,
TextRank-like sentence centrality, keyword extraction and confidence scoring.
It is deterministic, cheap enough for a small always-on host, and has no
network side effects.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass


STOP_WORDS = set(
    "از به در با و یا که این آن را برای یک است بود شد شده می اما اگر هم نیز خود ما"
    " آنها او وی گفت اعلام درباره روی تا بر هر چه همچنین دیگر پس زیرا توسط بدون".split()
)
PERSIAN_MAP = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه", "ؤ": "و", "إ": "ا", "أ": "ا"})
WORD_RE = re.compile(r"[\u0600-\u06ff\w]+", re.UNICODE)
SENTENCE_RE = re.compile(r"(?<=[.!؟!؛])\s+|\n+|(?<=\.{3})\s+")


def normalize_persian(text: str) -> str:
    """Normalize common Arabic/Persian variants without destroying the text."""
    text = (text or "").translate(PERSIAN_MAP)
    text = text.replace("\u200c", " ").replace("\u200d", " ").replace("ـ", "")
    text = re.sub(r"https?://\S+|www\.\S+", " ", text, flags=re.I)
    text = re.sub(r"[\u0660-\u0669]", lambda m: str(ord(m.group()) - 0x0660), text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def words(text: str) -> list[str]:
    normalized = normalize_persian(text).lower()
    return [w for w in WORD_RE.findall(normalized) if len(w) > 1 and w not in STOP_WORDS]


def _stem(word: str) -> str:
    """A deliberately conservative light stemmer for Persian news text."""
    for suffix in ("ترین", "تر", "های", "ها", "ان", "ات"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _sentences(text: str) -> list[str]:
    normalized = normalize_persian(text)
    return [part.strip(" ،,؛;\t") for part in SENTENCE_RE.split(normalized) if len(part.strip()) >= 12]


def _term_counts(sentence: str) -> Counter[str]:
    return Counter(_stem(w) for w in words(sentence))


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    common = set(left) & set(right)
    numerator = sum(left[k] * right[k] for k in common)
    denominator = math.sqrt(sum(v * v for v in left.values()) * sum(v * v for v in right.values()))
    return numerator / denominator if denominator else 0.0


def _rank_sentences(sentences: list[str]) -> list[tuple[float, int, str]]:
    if not sentences:
        return []
    counts = [_term_counts(sentence) for sentence in sentences]
    document_frequency = Counter(term for sentence in counts for term in sentence)
    weighted: list[Counter[str]] = []
    for count in counts:
        weighted.append(Counter({term: value * math.log((1 + len(sentences)) / (1 + document_frequency[term])) for term, value in count.items()}))

    # Four short PageRank-style relaxation passes give stable centrality while
    # keeping startup CPU and memory close to zero.
    scores = [1.0] * len(sentences)
    for _ in range(4):
        updated = [0.15] * len(sentences)
        for i in range(len(sentences)):
            links = [_cosine(weighted[i], weighted[j]) if i != j else 0.0 for j in range(len(sentences))]
            total = sum(links)
            if total:
                for j, link in enumerate(links):
                    if link:
                        updated[i] += 0.85 * link / total * scores[j]
        scores = updated

    ranked = []
    for i, (sentence, score) in enumerate(zip(sentences, scores)):
        length_prior = min(1.25, max(0.7, len(words(sentence)) / 14))
        lead_prior = 1.22 if i == 0 else 1.10 if i == 1 else 1.0
        factual_prior = 1.12 if re.search(r"[۰-۹0-9]", sentence) else 1.0
        attribution_prior = 1.10 if any(
            cue in sentence for cue in ("گفت", "اعلام", "گزارش", "تایید", "تأیید", "به نقل از")
        ) else 1.0
        ranked.append((score * length_prior * lead_prior * factual_prior * attribution_prior, i, sentence))
    return ranked


def textrank_summary(text: str, max_sentences: int = 3, max_chars: int = 260) -> str:
    """Return an extractive, deterministic summary bounded by ``max_chars``."""
    sentences = _sentences(text)
    if not sentences:
        return normalize_persian(text)[:max_chars].rstrip("، ")
    if len(sentences) == 1:
        return sentences[0][:max_chars].rstrip("، ")

    selected = sorted(_rank_sentences(sentences), reverse=True)[: max(1, max_sentences)]
    selected.sort(key=lambda item: item[1])
    result: list[str] = []
    used = 0
    for _, _, sentence in selected:
        separator = "\n" if result else ""
        if used + len(separator) + len(sentence) > max_chars:
            remaining = max_chars - used - len(separator)
            if remaining >= 24:
                result.append(separator + sentence[:remaining].rsplit(" ", 1)[0].rstrip("، "))
            break
        result.append(separator + sentence)
        used += len(separator) + len(sentence)
    return "".join(result).rstrip("، ")


def summarize(text: str, limit: int = 260) -> str:
    return textrank_summary(text, max_sentences=3, max_chars=limit)


@dataclass(frozen=True, slots=True)
class LocalAnalysis:
    summary: str
    keywords: tuple[str, ...]
    confidence: float
    sentence_count: int


def extract_keywords(text: str, limit: int = 8) -> list[str]:
    counts = Counter(_stem(word) for word in words(text))
    return [word for word, _ in counts.most_common(limit)]


def analyze(text: str, *, summary_chars: int = 260) -> LocalAnalysis:
    normalized = normalize_persian(text)
    tokens = words(normalized)
    if not tokens:
        return LocalAnalysis("", (), 0.0, 0)
    unique_ratio = len(set(tokens)) / len(tokens)
    length_confidence = min(1.0, len(tokens) / 18)
    confidence = round(min(0.99, 0.35 * length_confidence + 0.65 * unique_ratio), 3)
    return LocalAnalysis(
        summary=textrank_summary(normalized, max_sentences=3, max_chars=summary_chars),
        keywords=tuple(extract_keywords(normalized)),
        confidence=confidence,
        sentence_count=len(_sentences(normalized)),
    )


def build_digest(items: list[dict]) -> str:
    selected = items[:10]
    out = [f"🧠 جمع‌بندی هوشمند {len(selected)} خبر اخیر", ""]
    combined: list[str] = []

    for i, item in enumerate(selected, 1):
        source_text = item.get("clean_text", "")
        combined.append(source_text)
        analysis = analyze(source_text, summary_chars=220)
        category = item.get("category", "International")
        summary = analysis.summary.strip()
        out.append(f"{i}) {summary}\n#{category}")
        if i != len(selected):
            out.append("")

    themes = extract_keywords(" ".join(combined), limit=5)
    if themes:
        out.extend(["", "محورهای پرتکرار: " + "، ".join(themes)])
    return "\n".join(out)
