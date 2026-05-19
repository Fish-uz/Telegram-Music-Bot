import logging
import sys

# Definición de colores para la terminal (estilo MINGW64 / Bash)
RESET = "\033[0m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"

class CustomFormatter(logging.Formatter):
    """Formateador personalizado para imitar los logs detallados de la captura."""
    def format(self, record):
        # Seleccionar el prefijo según el nivel del log
        if record.levelno == logging.INFO:
            prefix = f"{CYAN}[INFO]{RESET}"
        elif record.levelno == logging.WARNING:
            prefix = f"{YELLOW}[WARN]{RESET}"
        elif record.levelno == logging.ERROR or record.levelno == logging.CRITICAL:
            prefix = f"{RED}[ERROR]{RESET}"
        else:
            prefix = f"[{record.levelname}]"

        # Formato del mensaje final
        record.msg = f"{prefix} {record.msg}"
        return super().format(record)

def setup_logger():
    """Configura el logger global del sistema."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Evitar duplicados si ya tiene manejadores
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        # Formato limpio: solo el mensaje modificado por el formateador
        formatter = CustomFormatter('%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

# Inicializamos al importar
logger = setup_logger()