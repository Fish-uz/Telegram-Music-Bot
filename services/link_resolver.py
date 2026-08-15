"""Convierte enlaces musicales en consultas buscables en YouTube."""

from __future__ import annotations

import re
import ssl
from dataclasses import dataclass
from urllib.parse import urlparse

import aiohttp
import certifi


@dataclass(frozen=True)
class ResolvedQuery:
    query: str
    source: str


class MusicLinkResolver:
    SPOTIFY_RE = re.compile(r"https?://open\.spotify\.com/(?:intl-[^/]+/)?track/([A-Za-z0-9]+)")
    DEEZER_RE = re.compile(r"https?://(?:www\.)?deezer\.com/(?:[a-z]{2}/)?track/(\d+)")
    YOUTUBE_RE = re.compile(r"https?://(?:www\.)?(?:youtube\.com/watch\?[^\s]*v=|youtu\.be/)([\w-]{11})")

    async def resolve(self, text: str) -> ResolvedQuery:
        text = text.strip()
        host = urlparse(text).hostname or ""
        if host in {"spotify.link", "deezer.page.link"}:
            text = await self._expand(text)
        youtube = self.YOUTUBE_RE.search(text)
        if youtube:
            return ResolvedQuery(f"https://www.youtube.com/watch?v={youtube.group(1)}", "YouTube")
        spotify = self.SPOTIFY_RE.search(text)
        if spotify:
            return ResolvedQuery(await self._spotify(text), "Spotify")
        deezer = self.DEEZER_RE.search(text)
        if deezer:
            return ResolvedQuery(await self._deezer(deezer.group(1)), "Deezer")
        return ResolvedQuery(text, "Texto")

    async def _expand(self, url: str) -> str:
        async with self._session() as session:
            async with session.get(url, allow_redirects=True) as response:
                response.raise_for_status()
                return str(response.url)

    async def _spotify(self, url: str) -> str:
        endpoint = "https://open.spotify.com/oembed"
        async with self._session() as session:
            async with session.get(endpoint, params={"url": url}) as response:
                response.raise_for_status()
                data = await response.json()
        title = str(data.get("title", "")).strip()
        if not title:
            raise ValueError("Spotify no devolvió metadatos para ese enlace.")
        return title

    async def _deezer(self, track_id: str) -> str:
        async with self._session() as session:
            async with session.get(f"https://api.deezer.com/track/{track_id}") as response:
                response.raise_for_status()
                data = await response.json()
        title = str(data.get("title", "")).strip()
        artist = str((data.get("artist") or {}).get("name", "")).strip()
        if not title:
            raise ValueError("Deezer no devolvió metadatos para ese enlace.")
        return f"{artist} - {title}" if artist else title

    @staticmethod
    def _session() -> aiohttp.ClientSession:
        context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=context)
        return aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=12), connector=connector
        )
