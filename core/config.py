"""Configuración validada desde variables de entorno."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _integer(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default


def _boolean(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.lower() in {"1", "true", "yes", "on"}


class Config:
    API_ID = _integer("API_ID", 0)
    API_HASH = os.getenv("API_HASH", "").strip()
    BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
    OWNER_ID = _integer("OWNER_ID", 0)

    DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
    COOKIES_FILE = os.getenv("YOUTUBE_COOKIES", "youtube_cookies.txt")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "database/music_bot.db")
    SESSION_NAME = os.getenv("SESSION_NAME", "music_session")

    WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT = _integer("PORT", _integer("WEB_PORT", 8080))
    DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN", "").strip()

    MAX_SIMULTANEOUS_DOWNLOADS = max(1, _integer("MAX_SIMULTANEOUS_DOWNLOADS", 3))
    # Cinco resultados por página: 100 resultados permiten navegar hasta 20 páginas.
    SEARCH_RESULTS_LIMIT = max(5, min(100, _integer("SEARCH_RESULTS_LIMIT", 100)))
    PLAYLIST_LIMIT = max(1, min(20, _integer("PLAYLIST_LIMIT", 10)))
    USER_SESSION_TTL = max(300, _integer("USER_SESSION_TTL", 7200))
    BACKUP_CHAT_ID = _integer("BACKUP_CHAT_ID", 0)

    TOP_BROADCAST_ENABLED = _boolean("TOP_BROADCAST_ENABLED", True)
    TOP_BROADCAST_INTERVAL_HOURS = max(1, _integer("TOP_BROADCAST_INTERVAL_HOURS", 24))
    AUTO_UPDATE_YTDLP = _boolean("AUTO_UPDATE_YTDLP", True)
    UPDATE_FAILURE_THRESHOLD = max(3, _integer("UPDATE_FAILURE_THRESHOLD", 3))

    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
    DEEZER_APP_ID = os.getenv("DEEZER_APP_ID", "").strip()
    DEEZER_SECRET = os.getenv("DEEZER_SECRET", "").strip()

    @classmethod
    def validate(cls) -> None:
        missing = []
        if cls.API_ID <= 0: missing.append("API_ID")
        if not cls.API_HASH: missing.append("API_HASH")
        if not cls.BOT_TOKEN: missing.append("BOT_TOKEN")
        if cls.OWNER_ID <= 0: missing.append("OWNER_ID")
        if missing:
            raise RuntimeError("Faltan variables obligatorias en .env: " + ", ".join(missing))
        Path(cls.DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
