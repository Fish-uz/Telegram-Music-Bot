import logging
import sys
import os
from logging.handlers import RotatingFileHandler

RESET = "\033[0m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"

class CustomFormatter(logging.Formatter):
    def format(self, record):
        if record.levelno == logging.INFO:
            prefix = f"{CYAN}[INFO]{RESET}"
        elif record.levelno == logging.WARNING:
            prefix = f"{YELLOW}[WARN]{RESET}"
        elif record.levelno == logging.ERROR or record.levelno == logging.CRITICAL:
            prefix = f"{RED}[ERROR]{RESET}"
        else:
            prefix = f"[{record.levelname}]"

        record.msg = f"{prefix} {record.msg}"
        return super().format(record)

def setup_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # 1. Manejador para la Terminal con colores
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(CustomFormatter('%(message)s'))
        logger.addHandler(console_handler)

        # 2. Manejador para Archivo con Auto-Rotación a los 50MB (50 * 1024 * 1024 bytes)
        os.makedirs("logs", exist_ok=True)
        file_handler = RotatingFileHandler(
            "logs/bot_activity.log", 
            maxBytes=52428800, 
            backupCount=3, 
            encoding="utf-8"
        )
        # Para el archivo usamos un formato estándar sin códigos de color ANSI
        file_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger

logger = setup_logger()