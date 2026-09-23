from __future__ import annotations

import logging
from pathlib import Path

import requests


log = logging.getLogger(__name__)


class BaleApiError(RuntimeError):
    pass


class BaleClient:
    def __init__(self, token: str, *, timeout: int = 45):
        self.base_url = f"https://tapi.bale.ai/bot{token}"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "RayaMediaBot/1.0"})

    def _call(self, method: str, *, data: dict | None = None, files: dict | None = None) -> dict:
        url = f"{self.base_url}/{method}"
        response = self.session.post(url, data=data or {}, files=files, timeout=self.timeout)
        try:
            payload = response.json()
        except ValueError as exc:
            raise BaleApiError(f"Bale returned non-JSON response ({response.status_code})") from exc
        if not response.ok or not payload.get("ok", False):
            raise BaleApiError(payload.get("description") or f"Bale API error: HTTP {response.status_code}")
        return payload

    def get_me(self) -> dict:
        return self._call("getMe").get("result", {})

    def get_updates(self, offset: int = 0, timeout: int = 20) -> list:
        return self._call("getUpdates", data={"offset": offset, "timeout": timeout}).get("result", [])

    def get_chat(self, chat_id: str) -> dict:
        return self._call("getChat", data={"chat_id": chat_id}).get("result", {})

    def send_text(self, chat_id: str, text: str, markup=None) -> None:
        for chunk in self._split_text(text, max_chars=3800):
            self._call("sendMessage", data={"chat_id": chat_id, "text": chunk, **({"reply_markup": __import__("json").dumps(markup, ensure_ascii=False)} if markup else {})})

    def send_media(self, chat_id: str, kind: str, path: Path, caption: str = "") -> None:
        method = "sendPhoto" if kind == "photo" else "sendVideo"
        field = "photo" if kind == "photo" else "video"
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption[:1000]

        try:
            with path.open("rb") as fh:
                self._call(method, data=data, files={field: (path.name, fh)})
        except BaleApiError:
            log.warning("%s failed for %s; falling back to sendDocument", method, path.name, exc_info=True)
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption[:1000]
            with path.open("rb") as fh:
                self._call("sendDocument", data=data, files={"document": (path.name, fh)})


    def send_media_group(self, chat_id: str, items: list[dict]) -> None:
        import json
        self._call("sendMediaGroup", data={"chat_id": chat_id, "media": json.dumps(items, ensure_ascii=False)})

    @staticmethod
    def _split_text(text: str, max_chars: int = 3800) -> list[str]:
        text = text.strip()
        if len(text) <= max_chars:
            return [text]

        chunks: list[str] = []
        current = ""
        for paragraph in text.split("\n"):
            candidate = f"{current}\n{paragraph}".strip() if current else paragraph
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                chunks.append(current)
                current = ""
            while len(paragraph) > max_chars:
                cut = paragraph.rfind(" ", 0, max_chars)
                if cut < max_chars // 2:
                    cut = max_chars
                chunks.append(paragraph[:cut].strip())
                paragraph = paragraph[cut:].strip()
            current = paragraph
        if current:
            chunks.append(current)
        return chunks
