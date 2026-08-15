"""Configuración central de logs operativos, errores y auditoría."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

LOG_DIR = "logs"
GENERAL_LOG = os.path.join(LOG_DIR, "allmusic.log")
ERROR_LOG = os.path.join(LOG_DIR, "errors.log")
AUDIT_LOG = os.path.join(LOG_DIR, "audit.log")


class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[90m",
        logging.INFO: "\033[36m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[1;31m",
    }

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = self.COLORS.get(record.levelno, "")
        return f"{color}{message}\033[0m" if color else message


class MaximumLevelFilter(logging.Filter):
    def __init__(self, maximum: int):
        super().__init__()
        self.maximum = maximum

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno <= self.maximum


def _rotating_handler(path: str, level: int, formatter: logging.Formatter) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


def setup_logging() -> None:
    """Configura una sola vez el árbol de logging de todo el proceso."""
    root = logging.getLogger()
    if getattr(root, "_allmusic_configured", False):
        return

    os.makedirs(LOG_DIR, exist_ok=True)
    root.handlers.clear()
    root.setLevel(logging.INFO)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.addFilter(MaximumLevelFilter(logging.CRITICAL))
    console.setFormatter(ColorFormatter(
        "[%(asctime)s] %(levelname)-8s %(name_short)-12s %(message)s",
        datefmt="%H:%M:%S",
    ))

    general_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s · %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    error_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s [%(filename)s:%(lineno)d]\n%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    general = _rotating_handler(GENERAL_LOG, logging.INFO, general_formatter)
    general.addFilter(MaximumLevelFilter(logging.WARNING))
    errors = _rotating_handler(ERROR_LOG, logging.ERROR, error_formatter)

    root.addHandler(console)
    root.addHandler(general)
    root.addHandler(errors)

    audit = logging.getLogger("allmusic.audit")
    audit.handlers.clear()
    audit.setLevel(logging.INFO)
    audit.propagate = False
    audit.addHandler(_rotating_handler(
        AUDIT_LOG,
        logging.INFO,
        logging.Formatter(
            "[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        ),
    ))

    # Oculta la telemetría rutinaria; yt-dlp conserva warnings porque suelen ser accionables.
    for name in (
        "pyrogram", "pyrogram.connection", "pyrogram.session",
        "aiohttp.access", "aiohttp.server", "asyncio",
    ):
        logging.getLogger(name).setLevel(logging.ERROR)
    logging.getLogger("yt_dlp").setLevel(logging.WARNING)

    # Campo compacto para consola sin acortar el nombre conservado en archivos.
    factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = factory(*args, **kwargs)
        record.name_short = record.name.removeprefix("allmusic.").split(".")[-1][:12]
        return record

    logging.setLogRecordFactory(record_factory)
    root._allmusic_configured = True


setup_logging()
logger = logging.getLogger("allmusic.bot")
audit_logger = logging.getLogger("allmusic.audit")
