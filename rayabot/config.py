from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class AppConfig:
    root: Path
    telegram_channels: list[str]
    source_priorities: dict[str, int]
    target_bale_channel: str
    bale_bot_token: str
    telegram_http_proxy: str | None
    poll_seconds: int
    summary_interval_minutes: int
    summary_item_count: int
    initial_posts_per_channel: int
    max_media_per_post: int
    request_timeout_seconds: int
    duplicate_similarity_threshold: float
    duplicate_window_hours: int
    skip_advertisements: bool
    skip_profanity: bool
    skip_incitement: bool
    log_level: str

    @property
    def db_path(self) -> Path:
        return self.root / "data" / "rayamedia.sqlite3"

    @property
    def log_path(self) -> Path:
        return self.root / "logs" / "rayamedia.log"



def load_config(root: Path | None = None) -> AppConfig:
    root = root or Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")

    raw = json.loads((root / "config.json").read_text(encoding="utf-8"))
    token = os.getenv("BALE_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BALE_BOT_TOKEN is missing in .env")

    target = os.getenv("BALE_TARGET_CHANNEL", raw.get("target_bale_channel", "@rayamedia")).strip()
    if not target:
        raise RuntimeError("BALE_TARGET_CHANNEL is missing")

    proxy = os.getenv("TELEGRAM_HTTP_PROXY", "").strip() or None

    return AppConfig(
        root=root,
        telegram_channels=[str(x).lstrip("@").strip() for x in raw["telegram_channels"]],
        source_priorities={
            str(k).lstrip("@").strip().lower(): int(v)
            for k, v in (raw.get("source_priorities") or {}).items()
        },
        target_bale_channel=target,
        bale_bot_token=token,
        telegram_http_proxy=proxy,
        poll_seconds=max(15, int(raw.get("poll_seconds", 60))),
        summary_interval_minutes=max(1, int(raw.get("summary_interval_minutes", 30))),
        summary_item_count=max(1, int(raw.get("summary_item_count", 10))),
        initial_posts_per_channel=max(0, int(raw.get("initial_posts_per_channel", 3))),
        max_media_per_post=max(0, int(raw.get("max_media_per_post", 4))),
        request_timeout_seconds=max(5, int(raw.get("request_timeout_seconds", 30))),
        duplicate_similarity_threshold=float(raw.get("duplicate_similarity_threshold", 0.88)),
        duplicate_window_hours=max(1, int(raw.get("duplicate_window_hours", 12))),
        skip_advertisements=bool(raw.get("skip_advertisements", True)),
        skip_profanity=bool(raw.get("skip_profanity", True)),
        skip_incitement=bool(raw.get("skip_incitement", True)),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
