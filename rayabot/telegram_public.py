from __future__ import annotations

import html
import logging
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import MediaItem, TelegramPost


log = logging.getLogger(__name__)
PHOTO_STYLE_RE = re.compile(r"background-image\s*:\s*url\((?:'|\")?(.*?)(?:'|\")?\)", re.I)


class TelegramPublicReader:
    def __init__(self, *, timeout: int = 30, proxy: str | None = None):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
                ),
                "Accept-Language": "fa,en;q=0.8",
            }
        )
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        if proxy:
            self.session.proxies.update({"http": proxy, "https": proxy})

    def fetch_posts(self, channel: str) -> list[TelegramPost]:
        channel = channel.lstrip("@")
        url = f"https://t.me/s/{channel}"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return self.parse_posts(channel, response.text)

    @staticmethod
    def parse_posts(channel: str, page_html: str) -> list[TelegramPost]:
        soup = BeautifulSoup(page_html, "html.parser")
        posts: list[TelegramPost] = []

        for node in soup.select(".tgme_widget_message[data-post]"):
            data_post = (node.get("data-post") or "").strip()
            if "/" not in data_post:
                continue
            source_channel, raw_id = data_post.rsplit("/", 1)
            try:
                post_id = int(raw_id)
            except ValueError:
                continue

            text_node = node.select_one(".tgme_widget_message_text")
            text = text_node.get_text("\n", strip=True) if text_node else ""

            media: list[MediaItem] = []
            seen_urls: set[str] = set()

            for photo in node.select(".tgme_widget_message_photo_wrap"):
                style = html.unescape(photo.get("style") or "")
                match = PHOTO_STYLE_RE.search(style)
                if match:
                    media_url = match.group(1).strip()
                    if media_url and media_url not in seen_urls:
                        media.append(MediaItem("photo", media_url))
                        seen_urls.add(media_url)

            for video in node.select("video"):
                media_url = (video.get("src") or "").strip()
                if not media_url:
                    source = video.select_one("source[src]")
                    media_url = (source.get("src") or "").strip() if source else ""
                media_url = html.unescape(media_url)
                if media_url and media_url not in seen_urls:
                    media.append(MediaItem("video", media_url))
                    seen_urls.add(media_url)

            time_node = node.select_one("time[datetime]")
            dt = (time_node.get("datetime") or "").strip() if time_node else None

            posts.append(
                TelegramPost(
                    channel=source_channel or channel,
                    post_id=post_id,
                    url=f"https://t.me/{source_channel or channel}/{post_id}",
                    text=text,
                    media=media,
                    datetime=dt or None,
                )
            )

        posts.sort(key=lambda p: p.post_id)
        return posts

    def download_media(
        self,
        item: MediaItem,
        destination_dir: Path,
        *,
        max_bytes: int = 49 * 1024 * 1024,
    ) -> Path:
        destination_dir.mkdir(parents=True, exist_ok=True)
        response = self.session.get(item.url, timeout=self.timeout, stream=True)
        response.raise_for_status()

        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            response.close()
            raise ValueError(f"media too large: {content_length} bytes")

        content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip()
        ext = mimetypes.guess_extension(content_type) or Path(urlparse(item.url).path).suffix
        if item.kind == "photo" and ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            ext = ".jpg"
        if item.kind == "video" and ext not in {".mp4", ".mov", ".m4v", ".webm"}:
            ext = ".mp4"

        out = destination_dir / f"media_{abs(hash(item.url))}{ext}"
        total = 0
        try:
            with out.open("wb") as f:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("media exceeded Bale upload limit")
                    f.write(chunk)
            return out
        except Exception:
            out.unlink(missing_ok=True)
            raise
        finally:
            response.close()
