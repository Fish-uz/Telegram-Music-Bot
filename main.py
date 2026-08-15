import asyncio
import logging

from bot import main
from core.logger import logger

def start_bot():
    log = logging.getLogger(__name__)
    log.info("--- INICIANDO SERVICIOS DEL BOT ---")

    try:
        # Pyrogram conserva el bucle disponible cuando se crea el Client en
        # bot.py. Reutilizarlo evita que los HandlerTasks queden asociados a
        # un bucle distinto y el bot parezca conectado sin recibir mensajes.
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        log.warning("Bot detenido manualmente.")
    except Exception as e:
        log.critical(f"Error fatal: {str(e)}", exc_info=True)
        raise
    finally:
        log.info("--- SERVICIOS DEL BOT FINALIZADOS ---")

if __name__ == "__main__":
    start_bot()
