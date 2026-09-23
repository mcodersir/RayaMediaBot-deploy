from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from rayabot.config import load_config
from rayabot.service import RayaMediaService
from rayabot.bale_client import BaleClient
from rayabot.admin_gate import AdminGate
from rayabot.admin_panel import AdminPanel
from rayabot.health_server import serve as serve_health
import threading
import os


def configure_logging(level: str, log_path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


def main() -> int:
    cfg = load_config()
    configure_logging(cfg.log_level, cfg.log_path)
    threading.Thread(target=serve_health, name="health-server", daemon=True).start()
    try:
        admin = AdminGate(BaleClient(cfg.bale_bot_token), os.getenv("ADMIN_ID", "707142549"), os.getenv("ADMIN_PASSWORD", "591387"))
        logging.getLogger(__name__).info("Waiting for admin activation")
        admin.wait()
        service = RayaMediaService(cfg)
        panel = AdminPanel(BaleClient(cfg.bale_bot_token), service.storage, os.getenv("ADMIN_ID", "707142549"))
        threading.Thread(target=lambda: [panel.run_once() or __import__("time").sleep(1) for _ in iter(int, 1)], daemon=True).start()
        service.run_forever()
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Stopped by user")
        return 0
    except Exception:
        logging.getLogger(__name__).exception("Fatal startup/runtime error")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
