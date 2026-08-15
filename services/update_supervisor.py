"""Recuperación controlada ante cambios incompatibles de YouTube."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import time
from collections import deque

import yt_dlp


class YtDlpUpdateSupervisor:
    RECOVERABLE_MARKERS = (
        "http error 403", "signature", "n challenge", "requested format is not available",
        "sign in to confirm", "player response", "unable to download video data",
    )

    def __init__(self, threshold: int = 3, window_seconds: int = 1800, cooldown: int = 21600):
        self.threshold = threshold
        self.window_seconds = window_seconds
        self.cooldown = cooldown
        self.failures: deque[float] = deque()
        self.last_check = 0.0
        self.lock = asyncio.Lock()
        self.logger = logging.getLogger("yt_dlp_supervisor")

    def is_recoverable(self, error: Exception) -> bool:
        message = str(error).lower()
        return any(marker in message for marker in self.RECOVERABLE_MARKERS)

    async def record_failure(self, error: Exception) -> bool:
        """Actualiza yt-dlp tras fallos técnicos repetidos; devuelve True si cambió la versión."""
        if not self.is_recoverable(error):
            return False
        now = time.monotonic()
        self.failures.append(now)
        while self.failures and now - self.failures[0] > self.window_seconds:
            self.failures.popleft()
        if len(self.failures) < self.threshold or now - self.last_check < self.cooldown:
            return False
        async with self.lock:
            self.last_check = time.monotonic()
            old_version = yt_dlp.version.__version__
            command = [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp[default]"]
            self.logger.warning("Comprobando actualización de yt-dlp tras %s fallos recuperables.", len(self.failures))
            result = await asyncio.to_thread(
                subprocess.run, command, capture_output=True, text=True, timeout=180, check=False
            )
            if result.returncode != 0:
                self.logger.error("No se pudo actualizar yt-dlp: %s", result.stderr[-500:])
                return False
            check = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-c", "import yt_dlp; print(yt_dlp.version.__version__)"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            new_version = check.stdout.strip()
            changed = bool(new_version and new_version != old_version)
            self.logger.info("Comprobación yt-dlp terminada: %s -> %s", old_version, new_version or old_version)
            return changed

    @staticmethod
    def restart_process() -> None:
        os.execv(sys.executable, [sys.executable, *sys.argv])
