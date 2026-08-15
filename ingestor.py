"""Carga bajo demanda una lista de búsquedas en la caché de Telegram."""

from __future__ import annotations

import argparse
import asyncio
import os

from pyrogram import Client

from core.config import Config
from database.manager import DatabaseManager
from services.downloader import MusicDownloader
from services.searcher import MusicSearcher


async def ingest(path: str) -> None:
    Config.validate()
    if not Config.BACKUP_CHAT_ID:
        raise RuntimeError("Define BACKUP_CHAT_ID en .env antes de usar el ingestor.")
    queries = [line.strip() for line in open(path, encoding="utf-8") if line.strip()]
    db = DatabaseManager(Config.DATABASE_PATH)
    searcher = MusicSearcher(Config.COOKIES_FILE)
    downloader = MusicDownloader(Config.DOWNLOAD_DIR, Config.COOKIES_FILE)
    client = Client(
        f"{Config.SESSION_NAME}_ingestor", api_id=Config.API_ID,
        api_hash=Config.API_HASH, bot_token=Config.BOT_TOKEN,
    )
    await client.start()
    try:
        for index, query in enumerate(queries, 1):
            results = await searcher.search(query, 1)
            if not results:
                print(f"[{index}/{len(queries)}] Sin resultado: {query}")
                continue
            video_id = results[0]["id"]
            if db.get_cached_file(video_id):
                print(f"[{index}/{len(queries)}] Ya existe: {query}")
                continue
            file_path = None
            try:
                file_path, title = await downloader.download(
                    f"https://www.youtube.com/watch?v={video_id}", query
                )
                sent = await client.send_audio(Config.BACKUP_CHAT_ID, file_path, title=title)
                db.add_to_cache(video_id, sent.audio.file_id, title)
                print(f"[{index}/{len(queries)}] OK: {title}")
            finally:
                if file_path and os.path.isfile(file_path):
                    os.remove(file_path)
    finally:
        await client.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestor privado de caché AllMusic")
    parser.add_argument("file", help="Archivo TXT con una búsqueda por línea")
    args = parser.parse_args()
    asyncio.get_event_loop().run_until_complete(ingest(args.file))
