"""Logging de consola y archivo sin alterar los registros originales."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


class ConsoleFormatter(logging.Formatter):
    COLORS = {
        logging.INFO: "\033[36m", logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m", logging.CRITICAL: "\033[31m",
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno, "")
        reset = "\033[0m" if color else ""
        message = super().format(record)
        return f"{color}[{record.levelname}]{reset} {message}"


def setup_logger() -> logging.Logger:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if getattr(root, "_allmusic_configured", False):
        return root
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(ConsoleFormatter("%(message)s"))
    root.addHandler(console)
    os.makedirs("logs", exist_ok=True)
    file_handler = RotatingFileHandler(
        "logs/bot_activity.log", maxBytes=10 * 1024 * 1024,
        backupCount=5, encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(file_handler)
    root._allmusic_configured = True
    return root


logger = setup_logger()
