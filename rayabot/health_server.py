from __future__ import annotations

import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen


log = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in {"/", "/health", "/healthz"}:
            self.send_error(404)
            return
        payload = json.dumps({"ok": True, "service": "rayamedia-bot"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args) -> None:
        return


def serve() -> None:
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


def _keepalive_loop() -> None:
    url = (os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
    if not url:
        log.info("Render self keep-alive disabled outside Render")
        return
    target = f"{url}/healthz"
    time.sleep(60)
    while True:
        try:
            req = Request(target, headers={"User-Agent": "RayaMediaBot-KeepAlive/1.0"})
            with urlopen(req, timeout=15) as response:
                if response.status != 200:
                    log.warning("Keep-alive returned HTTP %s", response.status)
        except Exception as exc:
            log.warning("Keep-alive ping failed: %s", exc)
        time.sleep(7 * 60)


def start_keepalive() -> None:
    threading.Thread(target=_keepalive_loop, name="render-keepalive", daemon=True).start()
