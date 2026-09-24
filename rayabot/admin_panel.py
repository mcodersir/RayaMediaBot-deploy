from __future__ import annotations

import logging
import re

from .bale_client import BaleApiError, BaleClient
from .local_ai import build_digest
from .storage import Storage


log = logging.getLogger(__name__)


class AdminPanel:
    def __init__(
        self,
        client: BaleClient,
        storage: Storage,
        admin_id: str,
        target_channel: str,
        default_channels: list[str],
    ):
        self.client = client
        self.storage = storage
        self.admin_id = str(admin_id)
        self.target_channel = target_channel
        self.default_channels = list(default_channels)
        self.offset = 0
        self.awaiting: str | None = None

    def keyboard(self):
        return {
            "inline_keyboard": [
                [
                    {"text": "📡 کانال‌ها", "callback_data": "channels"},
                    {"text": "➕ افزودن کانال", "callback_data": "add"},
                ],
                [
                    {"text": "🗑 حذف کانال", "callback_data": "del"},
                    {"text": "🧠 خلاصه ۱۰ خبر", "callback_data": "summary"},
                ],
                [
                    {"text": "📊 وضعیت ربات", "callback_data": "status"},
                    {"text": "❓ راهنما", "callback_data": "help"},
                ],
            ]
        }

    def _active_channels(self) -> list[str]:
        disabled = {x.lower() for x in self.storage.list_disabled_channels()}
        combined = [*self.default_channels, *self.storage.list_channels()]
        result: list[str] = []
        seen: set[str] = set()
        for channel in combined:
            key = channel.lower()
            if key in disabled or key in seen:
                continue
            seen.add(key)
            result.append(channel)
        return result

    @staticmethod
    def _normalize_channel(value: str) -> str:
        value = (value or "").strip()
        value = re.sub(r"(?i)^https?://t\.me/", "", value)
        value = value.lstrip("@").strip().strip("/")
        return value

    def menu(self, cid) -> None:
        self.client.send_text(
            cid,
            "پنل مدیریت رایا مدیا\nیک گزینه را انتخاب کنید یا /help را بفرستید.",
            self.keyboard(),
        )

    def help_text(self) -> str:
        return (
            "راهنمای مدیریت رایا مدیا\n\n"
            "/admin یا /panel — باز کردن پنل مدیریت\n"
            "/status — وضعیت ربات و آخرین خبر ثبت‌شده\n"
            "/channels — فهرست کانال‌های فعال\n"
            "/add — افزودن یا فعال‌کردن کانال تلگرام\n"
            "/del — حذف/غیرفعال‌کردن کانال\n"
            "/ssy — ساخت و انتشار فوری خلاصه هوشمند ۱۰ خبر اخیر در کانال بله\n"
            "/summary — همان دستور /ssy\n"
            "/cancel — لغو عملیات افزودن/حذف\n"
            "/help — نمایش همین راهنما"
        )

    def _send_channels(self, cid) -> None:
        channels = self._active_channels()
        if not channels:
            self.client.send_text(cid, "هیچ کانال فعالی ثبت نشده است.")
            return
        self.client.send_text(
            cid,
            "کانال‌های فعال:\n" + "\n".join(f"{i}. @{name}" for i, name in enumerate(channels, 1)),
        )

    def _send_status(self, cid) -> None:
        latest = self.storage.latest_published(1)
        channels = self._active_channels()
        last_line = "هنوز خبری در این اجرای ربات ثبت نشده است."
        if latest:
            item = latest[0]
            last_line = (
                f"آخرین خبر: @{item.get('source_channel', '?')}/{item.get('source_post_id', '?')} "
                f"— #{item.get('category', '?')}"
            )
        self.client.send_text(
            cid,
            "✅ ربات فعال است\n"
            f"📡 منابع فعال: {len(channels)}\n"
            f"🎯 مقصد: {self.target_channel}\n"
            f"{last_line}",
        )

    def _publish_summary(self, cid) -> None:
        items = self.storage.latest_published(10)
        if not items:
            self.client.send_text(cid, "هنوز خبر کافی برای خلاصه‌سازی وجود ندارد.")
            return
        items.reverse()
        digest = build_digest(items)
        self.client.send_text(self.target_channel, digest)
        self.client.send_text(cid, f"✅ خلاصه {len(items)} خبر اخیر در {self.target_channel} منتشر شد.")

    def _ack(self, callback_id: str, text: str = "") -> None:
        try:
            self.client.answer_callback_query(callback_id, text)
        except Exception:
            # Some Bale API revisions acknowledge callbacks implicitly. Never
            # break the admin panel only because answerCallbackQuery differs.
            log.debug("Callback acknowledgement failed", exc_info=True)

    def _handle_action(self, action: str, cid) -> None:
        if action == "channels":
            self._send_channels(cid)
        elif action == "add":
            self.awaiting = "add"
            self.client.send_text(cid, "نام کانال را با @ یا لینک t.me بفرستید. برای لغو: /cancel")
        elif action == "del":
            self.awaiting = "del"
            self.client.send_text(cid, "نام کانالی که باید غیرفعال شود را بفرستید. برای لغو: /cancel")
        elif action == "summary":
            self._publish_summary(cid)
        elif action == "status":
            self._send_status(cid)
        elif action == "help":
            self.client.send_text(cid, self.help_text(), self.keyboard())

    def _handle_message(self, msg: dict) -> None:
        chat = msg.get("chat") or {}
        sender = msg.get("from") or {}
        uid = str(sender.get("id", ""))
        cid = chat.get("id")
        if uid != self.admin_id or cid is None:
            return

        text = (msg.get("text") or "").strip()
        if not text:
            return

        if text in {"/cancel", "لغو"}:
            self.awaiting = None
            self.client.send_text(cid, "عملیات لغو شد.")
            return

        if self.awaiting == "add" and not text.startswith("/"):
            channel = self._normalize_channel(text)
            if not channel:
                self.client.send_text(cid, "نام کانال معتبر نیست.")
                return
            self.storage.add_channel(channel)
            self.awaiting = None
            self.client.send_text(cid, f"✅ @{channel} فعال شد.")
            self.menu(cid)
            return

        if self.awaiting == "del" and not text.startswith("/"):
            channel = self._normalize_channel(text)
            if not channel:
                self.client.send_text(cid, "نام کانال معتبر نیست.")
                return
            self.storage.remove_channel(channel)
            self.awaiting = None
            self.client.send_text(cid, f"✅ @{channel} غیرفعال شد.")
            self.menu(cid)
            return

        command = text.split(maxsplit=1)[0].lower()
        if command in {"/start", "/admin", "/panel"} or text == "پنل":
            self.menu(cid)
        elif command == "/help":
            self.client.send_text(cid, self.help_text(), self.keyboard())
        elif command == "/status":
            self._send_status(cid)
        elif command == "/channels":
            self._send_channels(cid)
        elif command == "/add":
            self._handle_action("add", cid)
        elif command in {"/del", "/remove"}:
            self._handle_action("del", cid)
        elif command in {"/ssy", "/summary"}:
            self._publish_summary(cid)
        else:
            self.client.send_text(cid, "دستور شناخته نشد. /help را بفرستید.")

    def run_once(self) -> None:
        for upd in self.client.get_updates(self.offset, 2):
            self.offset = int(upd.get("update_id", self.offset)) + 1

            callback = upd.get("callback_query") or {}
            if callback:
                sender = callback.get("from") or {}
                uid = str(sender.get("id", ""))
                message = callback.get("message") or {}
                cid = (message.get("chat") or {}).get("id")
                callback_id = str(callback.get("id", ""))
                action = (callback.get("data") or "").strip()
                if uid == self.admin_id and cid is not None:
                    self._ack(callback_id)
                    self._handle_action(action, cid)
                continue

            msg = upd.get("message") or {}
            if msg:
                self._handle_message(msg)
