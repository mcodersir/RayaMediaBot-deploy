from __future__ import annotations
from .bale_client import BaleClient
from .storage import Storage

class AdminPanel:
    def __init__(self, client: BaleClient, storage: Storage, admin_id: str):
        self.client=client; self.storage=storage; self.admin_id=str(admin_id); self.offset=0; self.awaiting=None

    def keyboard(self):
        return {
            "inline_keyboard": [
                [{"text":"📡 کانال‌ها","callback_data":"channels"},{"text":"➕ افزودن کانال","callback_data":"add"}],
                [{"text":"🗑 حذف کانال","callback_data":"del"},{"text":"🧠 خلاصه فوری","callback_data":"summary"}],
                [{"text":"⏯ وضعیت ربات","callback_data":"status"}]
            ]
        }

    def menu(self, cid):
        self.client.send_text(cid,'پنل مدیریت رایا مدیا\nدستورات: /admin /status /channels\nیک گزینه را انتخاب کنید:', self.keyboard())

    def run_once(self):
        for upd in self.client.get_updates(self.offset,2):
            self.offset=int(upd.get('update_id',self.offset))+1
            msg=upd.get('message') or {}; chat=msg.get('chat') or {}; uid=str((msg.get('from') or {}).get('id','')); cid=chat.get('id')
            if uid!=self.admin_id: continue
            text=(msg.get('text') or '').strip()
            if text in ['/admin','/panel','پنل']:
                self.menu(cid)
            elif self.awaiting=='add':
                self.storage.add_channel(text.replace('@','')); self.awaiting=None; self.client.send_text(cid,'کانال اضافه شد'); self.menu(cid)
            elif self.awaiting=='del':
                self.storage.remove_channel(text.replace('@','')); self.awaiting=None; self.client.send_text(cid,'کانال حذف شد'); self.menu(cid)
            elif text=='/channels':
                self.client.send_text(cid,'\n'.join('@'+x for x in self.storage.list_channels()) or 'خالی')
