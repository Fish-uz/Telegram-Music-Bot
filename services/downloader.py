"""
Módulo encargado de la descarga y procesamiento de audio desde múltiples fuentes.
Utiliza yt-dlp como motor principal y FFmpeg para la conversión de formatos.
"""

import os
import asyncio
import yt_dlp
import logging
from typing import Tuple

class MusicDownloader:
    """
    Clase que gestiona la descarga de medios con sistema de fallback automático.
    
    Atributos:
        download_dir (str): Directorio donde se guardarán temporalmente los archivos.
        cookies_path (str): Ruta al archivo de cookies para evitar bloqueos en YouTube.
    """
    
    def __init__(self, download_dir: str, cookies_path: str):
        # Logger específico para el módulo de descargas
        self.logger = logging.getLogger("downloader")
        self.download_dir = download_dir
        self.cookies_path = cookies_path

        # Garantiza que el directorio de descargas exista al iniciar el servicio
        if not os.makedirs(self.download_dir, exist_ok=True):
            self.logger.debug(f"Directorio verificado: {self.download_dir}")

    async def download(self, url: str, query: str) -> Tuple[str, str]:
        """
        Contrato principal de descarga. Intenta obtener el audio usando una lista
        priorizada de métodos (YouTube, SoundCloud, Bandcamp).
        
        Args:
            url (str): Enlace directo proporcionado por el usuario.
            query (str): Término de búsqueda para los métodos de respaldo.

        Returns:
            Tuple[str, str]: Ruta absoluta del archivo MP3 y el título de la canción.
            
        Raises:
            Exception: Si todos los métodos de descarga agotan sus intentos sin éxito.
        """
        # Lista de métodos a intentar en orden de prioridad
        methods = [
            (self._sync_download_youtube, url),      # Prioridad 1: Enlace directo o búsqueda en YT
            (self._sync_download_soundcloud, query), # Prioridad 2: Respaldo en SoundCloud
            (self._sync_download_bandcamp, query),   # Prioridad 3: Respaldo en Bandcamp
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
                self.logger.warning(f"⚠️ El método [{method_name}] falló. Razón: {str(e)[:150]}")
                continue 

        # Si el bucle termina sin un 'return', significa que todo falló
        self.logger.critical(f"❌ Fallo total: No se pudo descargar '{query}' por ningún medio.")
        raise Exception("❌ Todos los servicios de descarga fallaron.")

    # --- MÉTODOS PRIVADOS (LÓGICA SÍNCRONA DE YT-DLP) ---

    def _get_common_opts(self, out_prefix: str) -> dict:
        """
        Configura las opciones base para yt-dlp compartidas entre plataformas.
        
        Args:
            out_prefix (str): Prefijo para identificar la fuente (yt, sc, bc).
        """
        return {
            'format': 'bestaudio/best',
            'outtmpl': f'{self.download_dir}/{out_prefix}_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                },
                {
                    'key': 'EmbedThumbnail', # Incrusta la carátula en los metadatos del MP3
                } 
            ],
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
            return filename, info['title']

    def _sync_download_soundcloud(self, query: str) -> Tuple[str, str]:
        """Descarga desde SoundCloud usando el primer resultado de búsqueda."""
        opts = self._get_common_opts("sc")
        self.logger.debug(f"Buscando en SoundCloud: {query}")
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"scsearch1:{query}", download=True)
            entry = info['entries'][0]
            filename = ydl.prepare_filename(entry).rsplit('.', 1)[0] + ".mp3"
            return filename, entry['title']

    def _sync_download_bandcamp(self, query: str) -> Tuple[str, str]:
        """Descarga desde Bandcamp usando el primer resultado de búsqueda."""
        opts = self._get_common_opts("bc")
        self.logger.debug(f"Buscando en Bandcamp: {query}")
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"bcsearch1:{query}", download=True)
            entry = info['entries'][0]
            filename = ydl.prepare_filename(entry).rsplit('.', 1)[0] + ".mp3"
            return filename, entry['title']