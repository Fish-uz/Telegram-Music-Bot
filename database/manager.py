"""Persistencia SQLite transaccional para AllMusic."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class DatabaseManager:
    """Expone operaciones breves y seguras para múltiples tareas asíncronas."""

    def __init__(self, db_path: str = "database/music_bot.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.RLock()
        self.create_tables()

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.db_path, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 20000")
        try:
            yield connection
        finally:
            connection.close()

    def create_tables(self) -> None:
        with self._write_lock, self._connection() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS cache (
                    video_id TEXT PRIMARY KEY, file_id TEXT NOT NULL, title TEXT NOT NULL,
                    download_count INTEGER NOT NULL DEFAULT 0, created_at TEXT, last_used_at TEXT
                );
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY, username TEXT,
                    total_downloads INTEGER NOT NULL DEFAULT 0, last_download_date TEXT,
                    last_song_title TEXT, is_banned INTEGER NOT NULL DEFAULT 0, created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                    video_id TEXT NOT NULL, title TEXT NOT NULL, date TEXT NOT NULL,
                    cache_hit INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );
                CREATE TABLE IF NOT EXISTS download_failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, video_id TEXT, user_id INTEGER,
                    error_type TEXT NOT NULL, message TEXT NOT NULL, date TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_history_user_date ON history(user_id, date DESC);
                CREATE INDEX IF NOT EXISTS idx_history_date ON history(date DESC);
                CREATE INDEX IF NOT EXISTS idx_failures_date ON download_failures(date DESC);
                """
            )
            self._ensure_column(connection, "cache", "created_at", "TEXT")
            self._ensure_column(connection, "cache", "last_used_at", "TEXT")
            self._ensure_column(connection, "users", "created_at", "TEXT")
            self._ensure_column(connection, "history", "cache_hit", "INTEGER NOT NULL DEFAULT 0")
            connection.commit()

    @staticmethod
    def _ensure_column(connection, table: str, column: str, definition: str) -> None:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def get_cached_file(self, video_id: str):
        with self._connection() as connection:
            row = connection.execute(
                "SELECT file_id, title FROM cache WHERE video_id = ?", (video_id,)
            ).fetchone()
            return (row["file_id"], row["title"]) if row else None

    def add_to_cache(self, video_id: str, file_id: str, title: str) -> None:
        now = self._now()
        with self._write_lock, self._connection() as connection:
            connection.execute(
                """INSERT INTO cache(video_id, file_id, title, download_count, created_at, last_used_at)
                   VALUES (?, ?, ?, 0, ?, ?)
                   ON CONFLICT(video_id) DO UPDATE SET file_id=excluded.file_id,
                   title=excluded.title, last_used_at=excluded.last_used_at""",
                (video_id, file_id, title, now, now),
            )
            connection.commit()

    def remove_cached_file(self, video_id: str) -> None:
        with self._write_lock, self._connection() as connection:
            connection.execute("DELETE FROM cache WHERE video_id = ?", (video_id,))
            connection.commit()

    def register_user(self, user_id: int, username: str | None = None) -> None:
        with self._write_lock, self._connection() as connection:
            connection.execute(
                """INSERT INTO users(user_id, username, created_at) VALUES (?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET username=COALESCE(excluded.username, users.username)""",
                (user_id, username, self._now()),
            )
            connection.commit()

    def register_download(
        self, user_id: int, username: str, video_id: str, title: str, cache_hit: bool = False
    ) -> None:
        now = self._now()
        with self._write_lock, self._connection() as connection:
            connection.execute(
                """INSERT INTO users(user_id, username, total_downloads, last_download_date,
                   last_song_title, created_at) VALUES (?, ?, 1, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,
                   total_downloads=users.total_downloads+1,
                   last_download_date=excluded.last_download_date,
                   last_song_title=excluded.last_song_title""",
                (user_id, username, now, title, now),
            )
            connection.execute(
                "INSERT INTO history(user_id, video_id, title, date, cache_hit) VALUES (?, ?, ?, ?, ?)",
                (user_id, video_id, title, now, int(cache_hit)),
            )
            connection.execute(
                "UPDATE cache SET download_count=download_count+1, last_used_at=? WHERE video_id=?",
                (now, video_id),
            )
            connection.commit()

    def register_failure(self, video_id: str, user_id: int, error_type: str, message: str) -> None:
        with self._write_lock, self._connection() as connection:
            connection.execute(
                "INSERT INTO download_failures(video_id,user_id,error_type,message,date) VALUES (?,?,?,?,?)",
                (video_id, user_id, error_type, message[:500], self._now()),
            )
            connection.commit()

    def is_user_banned(self, user_id: int) -> bool:
        with self._connection() as connection:
            row = connection.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,)).fetchone()
            return bool(row[0]) if row else False

    def set_user_ban(self, user_id: int, status: bool) -> bool:
        self.register_user(user_id)
        with self._write_lock, self._connection() as connection:
            cursor = connection.execute(
                "UPDATE users SET is_banned=? WHERE user_id=?", (int(status), user_id)
            )
            connection.commit()
            return cursor.rowcount > 0

    def get_top_songs(self, limit: int = 10):
        with self._connection() as connection:
            return [tuple(row) for row in connection.execute(
                "SELECT title,download_count FROM cache ORDER BY download_count DESC,title LIMIT ?",
                (limit,),
            )]

    def get_user_profile(self, user_id: int):
        with self._connection() as connection:
            row = connection.execute(
                "SELECT user_id,username,total_downloads,last_download_date,last_song_title,is_banned,created_at FROM users WHERE user_id=?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_user_history(self, user_id: int, limit: int = 20):
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT video_id,title,date,cache_hit FROM history WHERE user_id=? ORDER BY date DESC LIMIT ?",
                (user_id, limit),
            )]

    def list_users(self, limit: int = 500, offset: int = 0):
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT user_id,username,total_downloads,last_download_date,last_song_title,is_banned FROM users ORDER BY total_downloads DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )]

    def list_active_user_ids(self):
        with self._connection() as connection:
            return [row[0] for row in connection.execute("SELECT user_id FROM users WHERE is_banned=0")]

    def list_songs(self, limit: int = 500):
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                "SELECT video_id,title,download_count,created_at,last_used_at FROM cache ORDER BY download_count DESC LIMIT ?",
                (limit,),
            )]

    def list_recent_history(self, limit: int = 100):
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(
                """SELECT h.user_id,u.username,h.video_id,h.title,h.date,h.cache_hit
                   FROM history h LEFT JOIN users u ON u.user_id=h.user_id
                   ORDER BY h.date DESC LIMIT ?""",
                (limit,),
            )]

    def get_dashboard_stats(self):
        with self._connection() as connection:
            row = connection.execute(
                """SELECT (SELECT COUNT(*) FROM users) total_users,
                   (SELECT COALESCE(SUM(total_downloads),0) FROM users) total_downloads,
                   (SELECT COUNT(*) FROM users WHERE is_banned=1) banned_users,
                   (SELECT COUNT(*) FROM cache) cached_songs,
                   (SELECT COUNT(*) FROM download_failures) failed_downloads,
                   (SELECT COUNT(*) FROM history WHERE cache_hit=1) cache_hits"""
            ).fetchone()
            return dict(row)

    def get_total_users(self): return self.get_dashboard_stats()["total_users"]
    def get_total_downloads(self): return self.get_dashboard_stats()["total_downloads"]
    def get_total_banned(self): return self.get_dashboard_stats()["banned_users"]
    def get_failed_downloads(self): return self.get_dashboard_stats()["failed_downloads"]
    def close(self) -> None: pass
