"""
Módulo encargado de la búsqueda de contenido multimedia en diversas plataformas.
Gestiona la extracción de metadatos y la obtención de IDs de listas de reproducción.
"""

import yt_dlp
import asyncio
import logging

class MusicSearcher:
    """
    Clase que implementa motores de búsqueda para YouTube, SoundCloud y Bandcamp.
    Permite obtener resultados de búsqueda y procesar enlaces de listas de reproducción.
    """
    
    def __init__(self):
        # Logger específico para rastrear el proceso de búsqueda
        self.logger = logging.getLogger("searcher")
        self.opts = {
            'extract_flat': True,       # Solo extrae metadatos, no procesa el video/audio
            'quiet': True,              # Silencia la salida estándar de yt-dlp
            'no_warnings': True,        # Ignora avisos no críticos
            'playlist_items': '1-60',   # Límite de ítems a procesar en búsquedas
        }

    async def search(self, query: str, limit=60):
        """
        Realiza una búsqueda secuencial en múltiples fuentes hasta encontrar resultados.
        
        Args:
            query (str): Término de búsqueda (canción, artista, etc.).
            limit (int): Cantidad máxima de resultados a retornar.

        Returns:
            list: Lista de diccionarios con metadatos de las canciones encontradas.
        """
        # Fuentes de búsqueda ordenadas por prioridad
        sources = [
            (f"ytsearch{limit}:", "YouTube"),
            (f"scsearch{limit}:", "SoundCloud"),
            (f"bcsearch{limit}:", "Bandcamp")
        ]

        self.logger.info(f"--- Iniciando búsqueda global: '{query}' ---")

        for prefix, source_name in sources:
            try:
                self.logger.info(f"Consultando {source_name}...")
                # Ejecutamos la búsqueda síncrona en un hilo separado para no bloquear el bot
                results = await asyncio.to_thread(self._sync_search, f"{prefix}{query}")
                
                if results:
                    self.logger.info(f"✅ Se encontraron {len(results)} resultados en {source_name}")
                    return results
                
                self.logger.debug(f"Sin resultados en {source_name}, probando siguiente fuente...")
                
            except Exception as e:
                self.logger.error(f"❌ Error durante la búsqueda en {source_name}: {str(e)[:100]}")
                continue 

        self.logger.warning(f"Búsqueda finalizada: No se hallaron resultados para '{query}' en ninguna plataforma.")
        return []
    
    async def get_playlist_ids(self, url: str, limit=10):
        """
        Extrae los identificadores únicos de los videos dentro de una playlist.
        
        Args:
            url (str): Enlace a la lista de reproducción de YouTube.
            limit (int): Número máximo de canciones a extraer.

        Returns:
            list: Lista de IDs de video (strings).
        """
        self.logger.info(f"Iniciando extracción de IDs de playlist: {url}")
        
        ydl_opts = {
            'extract_flat': True,
            'force_generic_extractor': True,
            'playlistend': limit,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                loop = asyncio.get_event_loop()
                # Extracción de info de forma asíncrona
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
                
                if 'entries' in info:
                    # Filtramos entradas nulas para evitar errores en el procesamiento posterior
                    ids = [entry['id'] for entry in info['entries'] if entry]
                    self.logger.info(f"✅ Playlist procesada: {len(ids)} IDs obtenidos.")
                    return ids
                    
                self.logger.warning("La URL proporcionada no contiene entradas válidas.")
                return []
                
        except Exception as e:
            self.logger.error(f"❌ Error crítico extrayendo playlist: {str(e)}", exc_info=True)
            return []

    def _sync_search(self, search_target: str):
        """
        Lógica interna síncrona para interactuar con yt-dlp.
        
        Args:
            search_target (str): Cadena de búsqueda formateada para yt-dlp.

        Returns:
            list: Resultados formateados con ID, Título, Duración y Artista.
        """
        with yt_dlp.YoutubeDL(self.opts) as ydl:
            info = ydl.extract_info(search_target, download=False)
            results = []
            
            if 'entries' not in info:
                return []

            for entry in info['entries']:
                if not entry: 
                    continue
                
                # Limpieza y formateo de metadatos para la interfaz del bot
                results.append({
                    'id': entry.get('id'),
                    'title': entry.get('title', 'Sin título')[:50], # Límite para botones de Telegram
                    'duration': entry.get('duration'),
                    'uploader': entry.get('uploader', 'Artista desconocido')
                })
                
            return results