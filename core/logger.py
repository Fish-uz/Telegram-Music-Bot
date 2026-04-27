"""
Módulo de configuración del sistema de registros (Logging).
Establece cómo y dónde se guardarán los eventos del bot para facilitar la depuración.
"""

import logging
import sys

def setup_logging():
    """
    Configura el motor de logging global.
    Define el formato de los mensajes y los destinos (Consola y Archivo).
    
    Returns:
        logging.Logger: Instancia del logger principal.
    """
    
    # Definición del formato de línea: Fecha - Módulo - Nivel - Mensaje
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configuración base del sistema
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            # 1. Archivo físico en la raíz para persistencia
            logging.FileHandler("bot_activity.log", encoding="utf-8"),
            # 2. Salida estándar para visualización en tiempo real (consola/Docker)
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # --- FILTROS DE RUIDO ---
    # Elevamos el nivel a WARNING para librerías ruidosas.
    # Solo veremos sus logs si ocurre un error real.
    logging.getLogger("pyrogram").setLevel(logging.WARNING)
    logging.getLogger("yt_dlp").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Logger raíz del proyecto
    logger = logging.getLogger("main")
    logger.info("Sistema de logging inicializado correctamente.")
    
    return logger