from __future__ import annotations

from .bale_client import BaleClient
from .config import load_config
from .telegram_public import TelegramPublicReader


def main() -> int:
    cfg = load_config()
    print("[1/3] Bale bot...")
    bale = BaleClient(cfg.bale_bot_token, timeout=cfg.request_timeout_seconds)
    me = bale.get_me()
    print("  OK:", me.get("username") or me.get("first_name") or me.get("id"))

    print("[2/3] Bale target channel...")
    chat = bale.get_chat(cfg.target_bale_channel)
    print("  OK:", chat.get("title") or cfg.target_bale_channel)

    print("[3/3] Telegram public sources...")
    reader = TelegramPublicReader(timeout=cfg.request_timeout_seconds, proxy=cfg.telegram_http_proxy)
    for channel in cfg.telegram_channels:
        posts = reader.fetch_posts(channel)
        media_count = sum(len(x.media) for x in posts)
        print(f"  @{channel}: {len(posts)} posts, {media_count} media items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
