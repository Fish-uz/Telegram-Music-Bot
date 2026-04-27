"""
Módulo de gestión de base de datos persistente.
Utiliza SQLite para manejar la caché de archivos, estadísticas de usuarios e historial.
"""

import sqlite3
import os
import logging
from datetime import datetime

class DatabaseManager:
    """
    Controlador de persistencia para el bot. 
    Gestiona la integridad de los datos y el almacenamiento de metadatos.
    """
    
    def __init__(self, db_path="database/music_bot.db"):
        # Logger específico para base de datos
        self.logger = logging.getLogger("database")
        
        # Asegura la existencia de la carpeta de base de datos
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # check_same_thread=False es necesario para que SQLite funcione con asyncio (Pyrogram)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()
        self.logger.info("Conexión a base de datos establecida y tablas verificadas.")

    def create_tables(self):
        """Inicializa la estructura de la base de datos si no existe."""
        cursor = self.conn.cursor()
        
        # 1. Tabla de Caché: Almacena file_ids de Telegram para evitar re-descargas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                video_id TEXT PRIMARY KEY,
                file_id TEXT,
                title TEXT,
                download_count INTEGER DEFAULT 1
            )
        ''')
        
        # 2. Tabla de Usuarios: Registra actividad y estado de acceso
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                total_downloads INTEGER DEFAULT 0,
                last_download_date TEXT,
                last_song_title TEXT,
                is_banned INTEGER DEFAULT 0
            )
        ''')
        
        # 3. Tabla de Historial: Auditoría de descargas por fecha
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                video_id TEXT,
                title TEXT,
                date TEXT
            )
        ''')
        self.conn.commit()

    # --- FUNCIONES DE CACHÉ ---

    def get_cached_file(self, video_id):
        """Busca un video en la caché mediante su identificador único."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT file_id, title FROM cache WHERE video_id = ?', (video_id,))
        result = cursor.fetchone()
        if result:
            self.logger.debug(f"HIT en caché: {video_id}")
        return result

    def add_to_cache(self, video_id, file_id, title):
        """Añade un nuevo recurso a la tabla de caché una vez subido a Telegram."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO cache (video_id, file_id, title, download_count) 
                VALUES (?, ?, ?, 1)
            ''', (video_id, file_id, title))
            self.conn.commit()
            self.logger.info(f"Nuevo recurso añadido a la caché: {video_id}")
        except Exception as e:
            self.logger.error(f"Error al añadir a caché {video_id}: {e}")

    # --- REGISTRO Y ESTADÍSTICAS ---

    def register_download(self, user_id, username, video_id, title):
        """Registra la descarga, actualiza perfil de usuario e incrementa contadores."""
        cursor = self.conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            # Actualización o Inserción de usuario (UPSERT)
            cursor.execute('''
                INSERT INTO users (user_id, username, total_downloads, last_download_date, last_song_title)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    total_downloads = total_downloads + 1,
                    last_download_date = ?,
                    last_song_title = ?
            ''', (user_id, username, now, title, now, title))

            # Insertar registro en historial
            cursor.execute('INSERT INTO history (user_id, video_id, title, date) VALUES (?, ?, ?, ?)',
                           (user_id, video_id, title, now))

            # Incrementar contador global de la canción
            cursor.execute('UPDATE cache SET download_count = download_count + 1 WHERE video_id = ?', (video_id,))
            
            self.conn.commit()
            self.logger.info(f"Registro completo: Usuario {user_id} descargó '{title}'")
        except Exception as e:
            self.logger.error(f"Error registrando descarga para usuario {user_id}: {e}")

    def get_top_songs(self, limit=10):
        """Retorna el ranking de las canciones con más demanda."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT title, download_count FROM cache ORDER BY download_count DESC LIMIT ?', (limit,))
        return cursor.fetchall()

    def is_user_banned(self, user_id):
        """Verifica si un usuario tiene restringido el uso del bot."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] == 1 if result else False

    def set_user_ban(self, user_id, status: bool):
        """Actualiza el estado de baneo de un usuario."""
        cursor = self.conn.cursor()
        val = 1 if status else 0
        cursor.execute('UPDATE users SET is_banned = ? WHERE user_id = ?', (val, user_id))
        self.conn.commit()
        
        action = "BANEADO" if status else "DESBANEADO"
        self.logger.warning(f"ADMIN: Usuario {user_id} ha sido {action}")
        return cursor.rowcount > 0