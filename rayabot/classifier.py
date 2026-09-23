from __future__ import annotations

import re
from dataclasses import dataclass

from .local_ai import normalize_persian
from .models import Category


IRAN_TERMS = {
    "ایران": 6,
    "ایرانی": 4,
    "تهران": 4,
    "جمهوری اسلامی ایران": 8,
    "سپاه": 5,
    "ارتش ایران": 6,
    "مجلس": 3,
    "پزشکیان": 5,
    "خامنه ای": 5,
    "خامنه‌ای": 5,
    "وزارت خارجه ایران": 6,
    "وزارت امور خارجه ایران": 6,
    "تنگه هرمز": 4,
    "خلیج فارس": 4,
    "اصفهان": 3,
    "شیراز": 3,
    "مشهد": 3,
    "تبریز": 3,
    "قم": 3,
    "کرج": 3,
    "رشت": 3,
    "یزد": 3,
    "کرمان": 3,
    "وزارت کشور": 4,
    "بانک مرکزی": 3,
    "انتخابات ایران": 5,
}

MIDDLE_EAST_TERMS = {
    "اسرائیل": 6,
    "فلسطین": 6,
    "غزه": 6,
    "لبنان": 5,
    "حزب الله": 6,
    "حزب‌الله": 6,
    "حماس": 6,
    "سوریه": 5,
    "دمشق": 4,
    "عراق": 5,
    "بغداد": 4,
    "یمن": 5,
    "انصارالله": 6,
    "حوثی": 5,
    "عربستان": 5,
    "ریاض": 4,
    "امارات": 5,
    "قطر": 5,
    "اردن": 5,
    "عمان": 4,
    "بحرین": 4,
    "کویت": 4,
    "تل آویو": 5,
    "تل‌آویو": 5,
    "بیروت": 4,
    "کرانه باختری": 5,
    "خاورمیانه": 4,
    "مقاومت": 3,
    "کرانه باختری": 5,
    "رود اردن": 3,
    "مدیترانه شرقی": 3,
}

INTERNATIONAL_TERMS = {
    "آمریکا": 3,
    "ایالات متحده": 3,
    "واشنگتن": 3,
    "روسیه": 4,
    "اوکراین": 4,
    "چین": 4,
    "اروپا": 4,
    "اتحادیه اروپا": 4,
    "ناتو": 4,
    "فرانسه": 4,
    "آلمان": 4,
    "بریتانیا": 4,
    "انگلیس": 4,
    "هند": 4,
    "پاکستان": 3,
    "سازمان ملل": 2,
    "گرینلند": 4,
    "دانمارک": 4,
    "سودان": 4,
    "ژاپن": 4,
    "کره جنوبی": 4,
    "هند": 4,
    "آفریقا": 3,
    "آمریکای لاتین": 3,
    "کاخ سفید": 4,
}


@dataclass(frozen=True, slots=True)
class Classification:
    category: Category
    confidence: float
    scores: dict[str, int]


def _score(text: str, terms: dict[str, int]) -> int:
    normalized = re.sub(r"\s+", " ", normalize_persian(text).lower())
    return sum(weight * normalized.count(term.lower()) for term, weight in terms.items())


def classify_with_confidence(text: str) -> Classification:
    iran = _score(text, IRAN_TERMS)
    middle = _score(text, MIDDLE_EAST_TERMS)
    international = _score(text, INTERNATIONAL_TERMS)

    # Iran-specific stories remain under #Iran even when they mention another regional actor.
    if iran >= 5 and iran >= middle - 2:
        category: Category = "Iran"
    elif middle >= 5 and middle >= international:
        category = "MiddleEast"
    else:
        category = "International"

    ordered = sorted((iran, middle, international), reverse=True)
    top, second = ordered[0], ordered[1]
    evidence = min(1.0, top / 18)
    margin = min(1.0, max(0, top - second) / 10)
    confidence = round(0.35 + 0.4 * evidence + 0.25 * margin, 3)
    return Classification(category, confidence, {"Iran": iran, "MiddleEast": middle, "International": international})


def classify(text: str) -> Category:
    return classify_with_confidence(text).category
