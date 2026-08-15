"""Descarga de audio de YouTube con progreso y nombres resistentes a colisiones."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Callable

import yt_dlp

ProgressHook = Callable[[float, str], None]


class MusicDownloader:
    def __init__(self, download_dir: str, cookies_path: str):
        self.logger = logging.getLogger("downloader")
        self.download_dir = Path(download_dir)
        self.cookies_path = cookies_path
        self.download_dir.mkdir(parents=True, exist_ok=True)

    async def download(self, url: str, query: str, progress: ProgressHook | None = None):
        self.logger.info("Iniciando descarga: %s", query)
        try:
            return await asyncio.to_thread(self._sync_download_youtube, url, progress)
        except Exception as error:
            self.logger.warning("Descarga de YouTube fallida: %s", str(error)[:300])
            raise

    def _get_common_opts(self, progress: ProgressHook | None = None) -> dict:
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg no está instalado o no está disponible en PATH.")

        runtimes = {}
        if shutil.which("deno"):
            runtimes["deno"] = {}
        elif shutil.which("node"):
            runtimes["node"] = {}

        def hook(data):
            if not progress:
                return
            status = data.get("status")
            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                downloaded = data.get("downloaded_bytes") or 0
                percentage = (downloaded / total * 100) if total else 0
                progress(percentage, "download")
            elif status == "finished":
                progress(100, "convert")

        opts = {
            "format": "bestaudio[acodec!=none]/best[acodec!=none]",
            "outtmpl": str(self.download_dir / "yt_%(id)s.%(ext)s"),
            "source_address": "0.0.0.0",
            "nocheckcertificate": True,
            "ffmpeg_location": ffmpeg_bin,
            "postprocessors": [{
                "key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"
            }],
            "progress_hooks": [hook],
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": False,
            "noplaylist": True,
        }
        if runtimes:
            opts["js_runtimes"] = runtimes
        if self.cookies_path and os.path.isfile(self.cookies_path):
            opts["cookiefile"] = self.cookies_path
        else:
            self.logger.warning("Cookies de YouTube no disponibles; se intentará acceso anónimo.")
        return opts

    def _sync_download_youtube(self, url: str, progress: ProgressHook | None):
        with yt_dlp.YoutubeDL(self._get_common_opts(progress)) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise RuntimeError("YouTube no devolvió información descargable.")
            if "entries" in info:
                info = next((entry for entry in info["entries"] if entry), None)
            if not info:
                raise RuntimeError("La búsqueda no devolvió una pista válida.")
            video_id = info["id"]
            output = self.download_dir / f"yt_{video_id}.mp3"
            if not output.is_file():
                raise FileNotFoundError(f"FFmpeg no generó el MP3 esperado: {output}")
            return str(output), info.get("title") or video_id

    def cleanup(self, video_id: str) -> None:
        """Elimina fragmentos y formatos intermedios pertenecientes a una pista."""
        for candidate in self.download_dir.glob(f"yt_{video_id}.*"):
            if candidate.is_file():
                candidate.unlink(missing_ok=True)
