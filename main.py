import logging
import os
from core.config import validate_required_credentials
from core.logger import setup_logging


def start_bot():
    try:
        validate_required_credentials()
    except ValueError as exc:
        print(f"Error de configuración: {exc}")
        raise SystemExit(1) from exc

    from bot import app
    from services.downloader import MusicDownloader

    cookies_content = os.getenv("YOUTUBE_COOKIES")
    if cookies_content and len(cookies_content.strip()) > 0:
        try:
            with open("cookies.txt", "w", encoding="utf-8") as f:
                f.write(cookies_content)
            print("Archivo cookies.txt generado exitosamente.")
        except Exception as e:
            print(f"Error al crear cookies.txt: {e}")
    else:
        print("Advertencia: No se encontró la variable YOUTUBE_COOKIES. Algunas descargas podrían fallar.")

    engine = MusicDownloader(
        download_dir="downloads",
        cookies_path="cookies.txt"
    )

    logger = setup_logging()
    log = logging.getLogger(__name__)

    log.info("--- INICIANDO SERVICIOS DEL BOT ---")

    try:
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