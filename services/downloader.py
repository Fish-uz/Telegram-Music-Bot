"""
Módulo encargado de la descarga y procesamiento de audio desde múltiples fuentes.
Utiliza yt-dlp como motor principal y FFmpeg para la conversión de formatos.
"""
import os
import asyncio
import yt_dlp
import logging
import shutil
from typing import Tuple


def _resolve_ffmpeg_path() -> str | None:
    candidates = [
        os.getenv("FFMPEG_PATH"),
        shutil.which("ffmpeg"),
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None

class MusicDownloader:

    def __init__(self, download_dir: str, cookies_path: str):
        # Logger específico para el módulo de descargas
        self.logger = logging.getLogger("downloader")
        self.download_dir = download_dir
        self.cookies_path = cookies_path

        # Garantiza que el directorio de descargas exista al iniciar el servicio
        if not os.makedirs(self.download_dir, exist_ok=True):
            self.logger.debug(f"Directorio verificado: {self.download_dir}")

    # --- LÓGICA DE RENOMBRADO SEGURO ---
    def _sanitize_and_rename(self, current_path: str, title: str) -> str:

        # Limpiar caracteres prohibidos para sistemas de archivos
        clean_title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip()
        new_path = os.path.join(self.download_dir, f"{clean_title}.mp3")

        # Renombrar el archivo
        if os.path.exists(current_path):
            os.replace(current_path, new_path)

        return new_path

    async def download(self, url: str, query: str) -> Tuple[str, str]:
        """
        Contrato principal de descarga. Intenta obtener el audio usando una lista
        priorizada de métodos YouTube
        """
        methods = [
            (self._sync_download_youtube, url),
        ]

        self.logger.info(f"--- Iniciando proceso de descarga para: '{query}' ---")

        for method, target in methods:
            method_name = method.__name__.replace('_sync_download_', '').upper()

            try:

                self.logger.info(f"Ejecutando Flujo [{method_name}] con objetivo: {target}")

                # Ejecución en hilo separado para no bloquear el bucle de eventos del bot
                file_path, title = await asyncio.to_thread(method, target)

                self.logger.info(f"✅ Descarga exitosa vía [{method_name}]: {title}")

                return file_path, title

            except Exception as e:
                # Log detallado del error antes de saltar al siguiente método
                self.logger.warning(f"El método [{method_name}] falló. Razón: {str(e)[:150]}")
                continue

        # Si el bucle termina sin un 'return', significa que todo falló
        self.logger.critical(f"fallo total: No se pudo descargar '{query}'.")
        raise Exception("Todos los servicios de descarga fallaron.")

    # --- MÉTODOS PRIVADOS (LÓGICA SÍNCRONA DE YT-DLP) ---
    def _get_common_opts(self, out_prefix: str) -> dict:
        ffmpeg_bin = _resolve_ffmpeg_path()

        if ffmpeg_bin is None:
            self.logger.error("FFmpeg NO ha sido encontrado en el sistema.")
        else:
            self.logger.debug(f"FFmpeg encontrado en: {ffmpeg_bin}")

        return {
            'format': 'bestaudio/best',
            'outtmpl': f'{self.download_dir}/{out_prefix}_%(id)s.%(ext)s',
            'cookiefile': self.cookies_path,
            'source_address': '0.0.0.0',
            'nocheckcertificate': True,
            'ffmpeg_location': ffmpeg_bin,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.youtube.com/'
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['configs', 'webplayer']
                }
            },
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                },
                {
                    'key': 'EmbedThumbnail',
                }
            ],
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'default_search': 'auto',
            'retries': 3,
            'retry_sleep_functions': {'http': 2, 'fragment': 2},
        }

    def _sync_download_youtube(self, url_or_query: str) -> Tuple[str, str]:

        """Descarga desde YouTube usando link o búsqueda interna."""

        opts = self._get_common_opts("yt")
        opts['cookiefile'] = self.cookies_path
        target = url_or_query

        if not url_or_query.startswith("http"):
            target = f"ytsearch1:{url_or_query}"

        self.logger.debug(f"Extrayendo info de YouTube: {target}")

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(target, download=True)

            if 'entries' in info:
                info = info['entries'][0]

            filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + ".mp3"
            clean_filename = self._sanitize_and_rename(filename, info['title'])
            return clean_filename, info['title']