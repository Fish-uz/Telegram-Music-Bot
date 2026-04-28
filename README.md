# 🎵 AllMusic - Telegram Music Downloader

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Pyrogram](https://img.shields.io/badge/Library-Pyrogram-orange.svg)
![Docker](https://img.shields.io/badge/Deployment-Docker-blue.svg)

**AllMusic** es un bot de Telegram robusto diseñado para buscar, descargar y procesar música desde múltiples plataformas con un sistema de respaldo (fallback) automático. 

---

## 🚀 Características Principales

* **Búsqueda Multi-Plataforma:** Si no encuentra la canción en YouTube, intenta automáticamente en SoundCloud y Bandcamp.
* **Sistema de Caché Inteligente:** Utiliza una base de datos SQLite para almacenar `file_ids`. Si un usuario pide una canción que ya fue descargada, el bot la envía instantáneamente sin descargarla de nuevo.
* **Gestión de Playlists:** Soporta la extracción y descarga de listas de reproducción de YouTube (limitado a los primeros 10 elementos para optimizar recursos).
* **Metadatos Completos:** Incluye carátulas de álbum (thumbnails) y metadatos correctos en los archivos MP3 procesados.
* **Panel de Usuario:** Comando `/perfil` para ver estadísticas de descarga y `/top` para ver las canciones más populares entre los usuarios.

---

## 🛠️ Tecnologías Utilizadas

* **[Pyrogram](https://docs.pyrogram.org/):** Framework de Telegram MTProto para Python.
* **[yt-dlp](https://github.com/yt-dlp/yt-dlp):** Motor de descarga de medios versátil.
* **[FFmpeg](https://ffmpeg.org/):** Para la conversión de audio a MP3 de alta calidad (192kbps).
* **[SQLite](https://www.sqlite.org/index.html):** Base de datos ligera para persistencia de datos.

---

## 📦 Instalación y Configuración

### Requisitos Previos
* Python 3.10 o superior.
* FFmpeg instalado en el sistema.

### Pasos
1. **Clonar el repositorio:**
   ```bash
   git clone [https://github.com/TU_USUARIO/TU_REPOSITORIO.git](https://github.com/TU_USUARIO/TU_REPOSITORIO.git)
   cd TU_REPOSITORIO

2. **Instalar dependencias:**

Bash
pip install -r requirements.txt

3. **Configurar variables de entorno:**
Crea un archivo .env en la raíz con el siguiente contenido:

Fragmento de código
API_ID=tu_api_id
API_HASH=tu_api_hash
BOT_TOKEN=tu_bot_token

4. **Ejecutar el bot:**

Bash
python main.py