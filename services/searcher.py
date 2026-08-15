"""Búsqueda ligera de música y playlists exclusivamente en YouTube."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil

import yt_dlp


class MusicSearcher:
    def __init__(self, cookies_path: str = ""):
        self.logger = logging.getLogger("allmusic.searcher")
        self.cookies_path = cookies_path

    def _options(self) -> dict:
        opts = {"extract_flat": True, "quiet": True, "no_warnings": True}
        if self.cookies_path and os.path.isfile(self.cookies_path):
            opts["cookiefile"] = self.cookies_path
        if shutil.which("deno"):
            opts["js_runtimes"] = {"deno": {}}
        elif shutil.which("node"):
            opts["js_runtimes"] = {"node": {}}
        return opts

    async def search(self, query: str, limit: int = 15):
        query = " ".join(query.split())[:200]
        if not query:
            return []
        target = query if query.startswith(("https://youtube.com/", "https://www.youtube.com/", "https://youtu.be/")) else f"ytsearch{limit}:{query}"
        return await asyncio.to_thread(self._sync_search, target)

    def _sync_search(self, target: str):
        with yt_dlp.YoutubeDL(self._options()) as ydl:
            info = ydl.extract_info(target, download=False)
        entries = (info or {}).get("entries")
        if entries is None and info:
            entries = [info]
        results = []
        for entry in entries or []:
            if not entry or not entry.get("id"):
                continue
            results.append({
                "id": entry["id"],
                "title": (entry.get("title") or "Sin título")[:80],
                "duration": entry.get("duration"),
                "uploader": entry.get("uploader") or "Artista desconocido",
            })
        return results

    async def get_playlist_ids(self, url: str, limit: int = 10):
        return await asyncio.to_thread(self._sync_playlist, url, limit)

    def _sync_playlist(self, url: str, limit: int):
        opts = self._options() | {"playlistend": limit, "extract_flat": "in_playlist"}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return [entry["id"] for entry in (info or {}).get("entries", []) if entry and entry.get("id")]
