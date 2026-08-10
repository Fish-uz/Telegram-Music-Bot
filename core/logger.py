import logging
import os
import sys
from logging.handlers import RotatingFileHandler

RESET = "\033[0m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"


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

        logger_name = f"[{record.name}]" if record.name not in {"root", "bot"} else ""
        record.msg = f"{prefix}{logger_name} {record.msg}"
        return super().format(record)


def setup_logger():
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, os.getenv("BOT_LOG_LEVEL", "INFO").upper(), logging.INFO))
    logger.propagate = False

    if logger.handlers:
        return logger

    os.makedirs("logs", exist_ok=True)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(CustomFormatter("%(message)s"))
    logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        "logs/bot_activity.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


def setup_logging():
    return setup_logger()


logger = setup_logger()