from __future__ import annotations

import logging
import os
import sys
import threading
import time
from logging.handlers import RotatingFileHandler

from rayabot.admin_gate import AdminGate
from rayabot.admin_panel import AdminPanel
from rayabot.bale_client import BaleClient
from rayabot.config import load_config
from rayabot.health_server import serve as serve_health, start_keepalive
from rayabot.service import RayaMediaService


def configure_logging(level: str, log_path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Keep a small local log for diagnostics. Render's filesystem is ephemeral;
    # this is not application state or a cache.
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=2 * 1024 * 1024,
        backupCount=1,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _run_admin_panel(panel: AdminPanel) -> None:
    log = logging.getLogger(__name__)
    while True:
        try:
            panel.run_once()
        except Exception:
            log.exception("Admin panel cycle failed")
            time.sleep(3)
        else:
            time.sleep(1)


def main() -> int:
    cfg = load_config()
    configure_logging(cfg.log_level, cfg.log_path)

    threading.Thread(target=serve_health, name="health-server", daemon=True).start()
    start_keepalive()

    try:
        # Cloud deployments must recover without waiting for a password after
        # every Render restart/spin-up. Manual activation can still be enabled
        # explicitly with REQUIRE_ADMIN_ACTIVATION=true.
        if _env_flag("REQUIRE_ADMIN_ACTIVATION", False):
            admin = AdminGate(
                BaleClient(cfg.bale_bot_token),
                os.getenv("ADMIN_ID", "707142549"),
                os.getenv("ADMIN_PASSWORD", "591387"),
            )
            logging.getLogger(__name__).info("Waiting for admin activation")
            admin.wait()
        else:
            logging.getLogger(__name__).info("Automatic startup enabled")

        service = RayaMediaService(cfg)
        panel = AdminPanel(
            BaleClient(cfg.bale_bot_token),
            service.storage,
            os.getenv("ADMIN_ID", "707142549"),
            cfg.target_bale_channel,
            cfg.telegram_channels,
        )
        threading.Thread(
            target=_run_admin_panel,
            args=(panel,),
            name="admin-panel",
            daemon=True,
        ).start()
        while True:
            try:
                service.run_forever()
            except Exception:
                logging.getLogger(__name__).exception(
                    "Service loop crashed; restarting automatically in 5 seconds"
                )
                time.sleep(5)
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Stopped by user")
        return 0
    except Exception:
        logging.getLogger(__name__).exception("Fatal startup/runtime error")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
