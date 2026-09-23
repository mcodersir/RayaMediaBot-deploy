from __future__ import annotations

import time
import logging
from .bale_client import BaleClient

log = logging.getLogger(__name__)


class AdminGate:
    def __init__(self, client: BaleClient, admin_id: str, password: str):
        self.client = client
        self.admin_id = str(admin_id)
        self.password = password
        self.enabled = False
        self.running = True
        self.offset = 0
        self.admin_chat = None

    def wait(self):
        log.info("Waiting for admin activation")
        while not self.enabled and self.running:
            try:
                updates = self.client.get_updates(self.offset, 30)
                for upd in updates:
                    self.offset = int(upd.get('update_id', self.offset)) + 1
                    msg = upd.get('message') or {}
                    chat = msg.get('chat') or {}
                    uid = str((msg.get('from') or {}).get('id', ''))
                    text = (msg.get('text') or '').strip()

                    if uid != self.admin_id:
                        continue

                    self.admin_chat = chat.get('id')

                    if text == '/start':
                        self.client.send_text(self.admin_chat, 'مدیریت رایا مدیا فعال است. رمز فعال سازی را ارسال کنید.')
                    elif text == self.password:
                        self.enabled = True
                        self.client.send_text(self.admin_chat, 'ربات فعال شد. دریافت اخبار شروع شد.')
                    else:
                        self.client.send_text(self.admin_chat, 'رمز صحیح نیست.')
            except Exception:
                log.exception("admin gate error")
                time.sleep(3)
        return True

    def monitor(self):
        return
