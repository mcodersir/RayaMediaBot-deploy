from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


class Storage:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_channel TEXT NOT NULL,
                    source_post_id INTEGER NOT NULL,
                    source_url TEXT NOT NULL,
                    original_text TEXT NOT NULL,
                    clean_text TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    published_at TEXT,
                    UNIQUE(source_channel, source_post_id)
                );
                CREATE INDEX IF NOT EXISTS idx_posts_published_at ON posts(published_at DESC);
                CREATE INDEX IF NOT EXISTS idx_posts_content_hash ON posts(content_hash);

                CREATE TABLE IF NOT EXISTS channel_state (
                    source_channel TEXT PRIMARY KEY,
                    initialized INTEGER NOT NULL DEFAULT 0,
                    last_seen_post_id INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS dynamic_channels (
                    channel TEXT PRIMARY KEY
                );

                CREATE TABLE IF NOT EXISTS disabled_channels (
                    channel TEXT PRIMARY KEY
                );
                """
            )

    def has_content_hash(self, value: str) -> bool:
        with self._conn() as conn:
            return conn.execute("SELECT 1 FROM posts WHERE content_hash=? LIMIT 1", (value,)).fetchone() is not None

    def is_seen(self, channel: str, post_id: int) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM posts WHERE source_channel=? AND source_post_id=?",
                (channel, post_id),
            ).fetchone()
            return row is not None

    def save_post(
        self,
        *,
        channel: str,
        post_id: int,
        source_url: str,
        original_text: str,
        clean_text: str,
        category: str,
        content_hash: str,
        status: str,
        published: bool,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        published_at = now if published else None
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO posts(
                    source_channel, source_post_id, source_url, original_text,
                    clean_text, category, content_hash, status, created_at, published_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    channel, post_id, source_url, original_text, clean_text,
                    category, content_hash, status, now, published_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO channel_state(source_channel, initialized, last_seen_post_id)
                VALUES (?, 1, ?)
                ON CONFLICT(source_channel) DO UPDATE SET
                    initialized=1,
                    last_seen_post_id=MAX(last_seen_post_id, excluded.last_seen_post_id)
                """,
                (channel, post_id),
            )

    def get_channel_state(self, channel: str) -> tuple[bool, int]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT initialized, last_seen_post_id FROM channel_state WHERE source_channel=?",
                (channel,),
            ).fetchone()
            if not row:
                return False, 0
            return bool(row["initialized"]), int(row["last_seen_post_id"])

    def recent_clean_texts(self, hours: int, limit: int = 300) -> list[str]:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT clean_text FROM posts
                WHERE created_at >= ? AND status IN ('published','duplicate')
                ORDER BY id DESC LIMIT ?
                """,
                (cutoff, limit),
            ).fetchall()
            return [str(row["clean_text"]) for row in rows if row["clean_text"]]

    def latest_published(self, limit: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT clean_text, category, source_channel, source_post_id, published_at
                FROM posts
                WHERE status='published' AND published_at IS NOT NULL
                ORDER BY published_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_state(self, key: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM app_state WHERE key=?", (key,)).fetchone()
            return str(row["value"]) if row else None

    def set_state(self, key: str, value: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO app_state(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (key, value),
            )

    def add_channel(self, channel: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM disabled_channels WHERE channel=?", (channel,))
            conn.execute("INSERT OR IGNORE INTO dynamic_channels(channel) VALUES (?)", (channel,))

    def remove_channel(self, channel: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM dynamic_channels WHERE channel=?", (channel,))
            conn.execute("INSERT OR IGNORE INTO disabled_channels(channel) VALUES (?)", (channel,))

    def list_channels(self) -> list[str]:
        with self._conn() as conn:
            return [str(r[0]) for r in conn.execute("SELECT channel FROM dynamic_channels ORDER BY channel").fetchall()]

    def list_disabled_channels(self) -> list[str]:
        with self._conn() as conn:
            return [str(r[0]) for r in conn.execute("SELECT channel FROM disabled_channels ORDER BY channel").fetchall()]
