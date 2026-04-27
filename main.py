"""
Módulo de entrada principal para el Bot de Música.

Este script es el punto de inicio de la aplicación. Se encarga de:
1. Configurar el sistema de registro (logging).
2. Inicializar la sesión del cliente de Telegram.
3. Mantener el bot en ejecución.
"""

import logging
from bot import app
from core.logger import setup_logging

def start_bot():
    """
    Configura el entorno de ejecución e inicia el cliente Pyrogram.
    
    Se asegura de que el sistema de logs esté activo antes de que 
    el bot intente conectar con los servidores de Telegram.
    """
    # 1. Inicializamos el sistema de logs profesional
    # Esto creará la carpeta /logs y el archivo bot.log si no existen.
    logger = setup_logging()
    
    # Obtenemos el logger específico de este módulo
    log = logging.getLogger(__name__)
    
    log.info("--- INICIANDO SERVICIOS DEL BOT ---")
    
    try:
        # 2. Ejecución del cliente Pyrogram (bot.py)
        # Este método bloquea el hilo y mantiene el bot escuchando mensajes.
        log.info("Cliente Pyrogram iniciado. Esperando mensajes...")
        app.run()
        
    except KeyboardInterrupt:
        log.warning("Bot detenido manualmente por el usuario (KeyboardInterrupt).")
    except Exception as e:
        log.critical(f"Error fatal al arrancar el bot: {str(e)}", exc_info=True)
    finally:
        log.info("--- SERVICIOS DEL BOT FINALIZADOS ---")

if __name__ == "__main__":
    # Punto de entrada estándar de Python
    start_bot()