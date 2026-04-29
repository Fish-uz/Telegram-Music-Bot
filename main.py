import logging
import os
import shutil
from bot import app
from services.downloader import MusicDownloader
from core.logger import setup_logging

def start_bot():
    cookies_content = os.getenv("YOUTUBE_COOKIES")
    if cookies_content and len(cookies_content.strip()) > 0:
        try:
            with open("cookies.txt", "w", encoding="utf-8") as f:
                f.write(cookies_content)
            print("✅ Archivo cookies.txt generado exitosamente.")
        except Exception as e:
            print(f"❌ Error al crear cookies.txt: {e}")
    else:
        print("⚠️ Advertencia: No se encontró la variable YOUTUBE_COOKIES. Algunas descargas podrían fallar.")

    engine = MusicDownloader(
        download_dir="downloads", 
        cookies_path="cookies.txt"  # <--- Esto es lo que recibirá self.cookies_path
    )

    # 2. Inicializamos el sistema de logs profesional
    logger = setup_logging()
    log = logging.getLogger(__name__)
    
    log.info("--- INICIANDO SERVICIOS DEL BOT ---")
    
    try:
        # 3. Ejecución del cliente Pyrogram
        log.info("Cliente Pyrogram iniciado. Esperando mensajes...")
        app.run()
        
    except KeyboardInterrupt:
        log.warning("Bot detenido manualmente.")
    except Exception as e:
        log.critical(f"Error fatal: {str(e)}", exc_info=True)
    finally:
        log.info("--- SERVICIOS DEL BOT FINALIZADOS ---")

if __name__ == "__main__":
    start_bot()