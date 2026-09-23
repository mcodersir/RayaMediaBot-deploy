from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


MediaKind = Literal["photo", "video"]
Category = Literal["Iran", "MiddleEast", "International"]


@dataclass(slots=True)
class MediaItem:
    kind: MediaKind
    url: str


@dataclass(slots=True)
class TelegramPost:
    channel: str
    post_id: int
    url: str
    text: str
    media: list[MediaItem] = field(default_factory=list)
    datetime: str | None = None


@dataclass(slots=True)
class ProcessedPost:
    source: TelegramPost
    clean_text: str
    category: Category
    content_hash: str
