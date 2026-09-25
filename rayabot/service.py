from __future__ import annotations

import logging
import re
import tempfile
import time
import random
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

from .bale_client import BaleClient
from .classifier import classify
from .config import AppConfig
from .local_ai import build_digest
from .moderation import moderate
from .storage import Storage
from .telegram_public import TelegramPublicReader
from .text_processing import append_footer, apply_news_label, clean_text, content_hash


log = logging.getLogger(__name__)


class RayaMediaService:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.storage = Storage(cfg.db_path)
        self.telegram = TelegramPublicReader(
            timeout=cfg.request_timeout_seconds,
            proxy=cfg.telegram_http_proxy,
        )
        self.bale = BaleClient(cfg.bale_bot_token, timeout=max(45, cfg.request_timeout_seconds))

    def validate(self) -> None:
        me = self.bale.get_me()
        username = me.get("username") or me.get("first_name") or "unknown"
        log.info("Connected to Bale bot: %s", username)
        chat = self.bale.get_chat(self.cfg.target_bale_channel)
        log.info("Target Bale channel resolved: %s", chat.get("title") or self.cfg.target_bale_channel)

    @staticmethod
    def _similarity_text(text: str) -> str:
        text = re.sub(r"#[A-Za-z]+", "", text)
        text = re.sub(r"\W+", " ", text.lower(), flags=re.UNICODE)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _duplicate_tokens(text: str) -> set[str]:
        normalized = RayaMediaService._similarity_text(text)
        stop = {
            "از", "به", "در", "با", "و", "یا", "که", "این", "آن", "را", "برای",
            "یک", "است", "بود", "شد", "شده", "می", "هم", "نیز", "اما", "اگر",
            "گفت", "اعلام", "کرد", "خبر", "گزارش", "بر", "تا", "خود",
        }
        return {w for w in normalized.split() if len(w) > 1 and w not in stop}

    @staticmethod
    def _event_signature(text: str) -> tuple[set[str], set[str]]:
        """Extract stable event clues: numbers and longer content-bearing tokens."""
        normalized = RayaMediaService._similarity_text(text)
        numbers = set(re.findall(r"[۰-۹0-9]+", normalized))
        keywords = {
            w for w in RayaMediaService._duplicate_tokens(normalized)
            if len(w) >= 4
        }
        return numbers, keywords

    def _is_duplicate(self, text: str) -> bool:
        candidate = self._similarity_text(text)
        if len(candidate) < 24:
            return False
        candidate_tokens = self._duplicate_tokens(candidate)
        candidate_numbers, candidate_keywords = self._event_signature(candidate)
        for old in self.storage.recent_clean_texts(self.cfg.duplicate_window_hours):
            old_norm = self._similarity_text(old)
            if not old_norm:
                continue

            sequence_ratio = SequenceMatcher(None, candidate, old_norm, autojunk=False).ratio()
            if sequence_ratio >= self.cfg.duplicate_similarity_threshold:
                return True

            old_tokens = self._duplicate_tokens(old_norm)
            if not candidate_tokens or not old_tokens:
                continue
            intersection = candidate_tokens & old_tokens
            union = candidate_tokens | old_tokens
            jaccard = len(intersection) / len(union)
            containment = len(intersection) / min(len(candidate_tokens), len(old_tokens))
            old_numbers, old_keywords = self._event_signature(old_norm)
            keyword_overlap = candidate_keywords & old_keywords
            number_overlap = candidate_numbers & old_numbers

            # Event signature catches paraphrases across different sources.
            if len(keyword_overlap) >= 5 and (number_overlap or containment >= 0.52):
                return True
            if len(keyword_overlap) >= 4 and number_overlap and containment >= 0.44:
                return True
            # Same named event across two outlets: enough distinctive long
            # keywords plus strong containment is a duplicate even without a number.
            if len(keyword_overlap) >= 4 and containment >= 0.60:
                return True

            # Reworded reports of the same event often have a modest sequence
            # ratio but retain the same names, places and event vocabulary.
            if jaccard >= 0.46 and len(intersection) >= 4:
                return True
            if containment >= 0.60 and len(intersection) >= 4:
                return True
            if sequence_ratio >= 0.68 and containment >= 0.56:
                return True

            # Short breaking-news rewrites often differ mainly in attribution
            # or wording while preserving the event's distinctive vocabulary.
            if len(candidate_tokens) <= 18 and len(old_tokens) <= 18:
                if containment >= 0.60 and len(intersection) >= 3:
                    return True
        return False

    def _smart_label(self, text: str) -> str:
        t = text.lower()
        if any(x in t for x in ["فوری", "همین لحظه", "لحظاتی پیش"]):
            return "فوری"
        if any(x in t for x in ["تحلیل", "بررسی", "ارزیابی"]):
            return "تحلیل"
        if any(x in t for x in ["تکمیلی", "جزئیات بیشتر", "ادامه خبر"]):
            return "تکمیلی"
        return ""

    def _publish_post(self, text: str, media_items) -> None:
        target = self.cfg.target_bale_channel
        media_items = list(media_items)[: self.cfg.max_media_per_post]
        # Media without a real news caption is never published.
        if media_items and len(text.strip()) < 20:
            log.info("Skipping media-only post")
            return
        if not media_items:
            self.bale.send_text(target, text)
            return

        with tempfile.TemporaryDirectory(prefix="rayamedia_") as tmp:
            tmp_path = Path(tmp)
            downloaded = []
            try:
                for media in media_items:
                    local_path = self.telegram.download_media(media, tmp_path)
                    downloaded.append((media, local_path))

                # Albums stay albums: first item gets the caption.
                if len(downloaded) > 1:
                    group = []
                    for idx, (media, path) in enumerate(downloaded):
                        group.append({
                            "type": media.kind,
                            "media": str(path),
                            **({"caption": text[:1000]} if idx == 0 else {})
                        })
                    self.bale.send_media_group(target, group)
                else:
                    media, path = downloaded[0]
                    self.bale.send_media(target, media.kind, path, caption=text[:1000])
            except Exception:
                log.exception("Media transfer failed; falling back to text")
                self.bale.send_text(target, text)

    def _process_channel(self, channel: str) -> None:
        posts = self.telegram.fetch_posts(channel)
        if not posts:
            log.warning("No public posts parsed from @%s", channel)
            return

        initialized, last_seen = self.storage.get_channel_state(channel)
        if initialized:
            candidates = [p for p in posts if p.post_id > last_seen]
        else:
            # Render Free has an ephemeral filesystem. After a restart/deploy the
            # local SQLite DB can be empty even though the channel already contains
            # posts RayaMedia published earlier. Baseline at the newest currently
            # visible source post and publish only posts that arrive afterwards.
            newest = max((p.post_id for p in posts), default=0)
            if newest:
                self.storage.initialize_channel(channel, newest)
                log.info("Cold-start baseline @%s -> %s (historical posts skipped)", channel, newest)
            return

        for post in candidates:
            if self.storage.is_seen(channel, post.post_id):
                continue

            # Moderate the original post before cleaning. Cleaning removes source
            # handles and links, which are valuable evidence for detecting ads/bots.
            moderation = moderate(
                post.text,
                skip_profanity=self.cfg.skip_profanity,
                skip_incitement=self.cfg.skip_incitement,
                skip_advertisements=self.cfg.skip_advertisements,
                skip_non_news=True,
            )

            cleaned = clean_text(post.text)
            # Defense in depth: re-check the publishable text too. This catches
            # commercial payloads even if Telegram changes link/HTML markup.
            cleaned_moderation = moderate(
                cleaned,
                skip_profanity=self.cfg.skip_profanity,
                skip_incitement=self.cfg.skip_incitement,
                skip_advertisements=self.cfg.skip_advertisements,
                skip_non_news=True,
            )
            if moderation.allowed and not cleaned_moderation.allowed:
                moderation = cleaned_moderation
            category = classify(cleaned)
            digest_hash = content_hash(cleaned)
            if len(cleaned.strip()) < 18:
                self.storage.save_post(channel=channel, post_id=post.post_id, source_url=post.url, original_text=post.text, clean_text=cleaned, category=category, content_hash=digest_hash, status="filtered:empty_or_short", published=False)
                continue
            if self.storage.has_content_hash(digest_hash):
                log.info("Skipped exact duplicate @%s/%s", channel, post.post_id)
                self.storage.save_post(channel=channel, post_id=post.post_id, source_url=post.url, original_text=post.text, clean_text=cleaned, category=category, content_hash=digest_hash, status="duplicate", published=False)
                continue
            if not moderation.allowed:
                log.info("Skipped @%s/%s: %s", channel, post.post_id, moderation.reason)
                self.storage.save_post(
                    channel=channel,
                    post_id=post.post_id,
                    source_url=post.url,
                    original_text=post.text,
                    clean_text=cleaned,
                    category=category,
                    content_hash=digest_hash,
                    status=f"filtered:{moderation.reason}",
                    published=False,
                )
                continue

            if self._is_duplicate(cleaned):
                log.info("Skipped duplicate @%s/%s", channel, post.post_id)
                self.storage.save_post(
                    channel=channel,
                    post_id=post.post_id,
                    source_url=post.url,
                    original_text=post.text,
                    clean_text=cleaned,
                    category=category,
                    content_hash=digest_hash,
                    status="duplicate",
                    published=False,
                )
                continue

            label = self._smart_label(cleaned)
            if label:
                cleaned = apply_news_label(cleaned, label)

            final_text = append_footer(cleaned, category)
            self._publish_post(final_text, post.media)
            self.storage.save_post(
                channel=channel,
                post_id=post.post_id,
                source_url=post.url,
                original_text=post.text,
                clean_text=cleaned,
                category=category,
                content_hash=digest_hash,
                status="published",
                published=True,
            )
            log.info("Published @%s/%s -> #%s", channel, post.post_id, category)
            # Keep a small anti-burst pause without creating multi-minute
            # backlogs when several channels publish at the same time.
            time.sleep(random.uniform(4, 10))

    def _summary_due(self) -> bool:
        raw = self.storage.get_state("last_digest_at")
        now = datetime.now(timezone.utc)
        if not raw:
            self.storage.set_state("last_digest_at", now.isoformat())
            return False
        try:
            last = datetime.fromisoformat(raw)
        except ValueError:
            last = now - timedelta(minutes=self.cfg.summary_interval_minutes)
        return now - last >= timedelta(minutes=self.cfg.summary_interval_minutes)

    def _publish_digest_if_due(self) -> None:
        if not self._summary_due():
            return
        now = datetime.now(timezone.utc)
        items = self.storage.latest_published(max(self.cfg.summary_item_count * 4, 30))
        # Historical rows may contain ads that slipped through an older filter.
        # Never let those reappear in an automatic digest.
        items = [
            item for item in items
            if moderate(
                item.get("clean_text", ""),
                skip_profanity=False,
                skip_incitement=False,
                skip_advertisements=True,
                skip_non_news=True,
            ).allowed
        ][: self.cfg.summary_item_count]
        if items:
            items.reverse()  # chronological order inside the digest
            self.bale.send_text(self.cfg.target_bale_channel, build_digest(items))
            log.info("Published ad-safe local digest for %s items", len(items))
        self.storage.set_state("last_digest_at", now.isoformat())

    def run_forever(self) -> None:
        self.validate()
        log.info("RayaMedia bridge started. Sources: %s", ", ".join("@" + c for c in self.cfg.telegram_channels))
        while True:
            cycle_started = time.monotonic()
            if self.storage.is_paused():
                log.info("Publishing is paused by admin")
                time.sleep(max(2.0, min(10.0, self.cfg.poll_seconds)))
                continue
            dynamic_channels = self.storage.list_channels()
            disabled = {x.lower() for x in self.storage.list_disabled_channels()}
            channels = [
                channel
                for channel in dict.fromkeys([*self.cfg.telegram_channels, *dynamic_channels])
                if channel.lower() not in disabled
            ]
            # Higher-priority sources are polled first so first-hand reports win
            # the cross-source duplicate race.
            channels.sort(
                key=lambda name: self.cfg.source_priorities.get(name.lower(), 0),
                reverse=True,
            )
            for channel in channels:
                try:
                    self._process_channel(channel)
                except Exception:
                    log.exception("Channel cycle failed for @%s", channel)
            try:
                self._publish_digest_if_due()
            except Exception:
                log.exception("Digest publishing failed")

            elapsed = time.monotonic() - cycle_started
            sleep_for = max(1.0, self.cfg.poll_seconds - elapsed)
            time.sleep(sleep_for)
