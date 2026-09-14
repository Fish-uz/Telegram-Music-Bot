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
    destination_chat_id = Config.BACKUP_CHAT_ID or Config.OWNER_ID
    # utf-8-sig acepta tanto UTF-8 normal como archivos exportados con BOM.
    with open(path, encoding="utf-8-sig") as source:
        queries = [line.strip() for line in source if line.strip()]
    # Preserva el orden original y evita gastar recursos en líneas repetidas.
    queries = list(dict.fromkeys(queries))
    db = DatabaseManager(Config.DATABASE_PATH)
    searcher = MusicSearcher(Config.COOKIES_FILE)
    downloader = MusicDownloader(Config.DOWNLOAD_DIR, Config.COOKIES_FILE)
    client = Client(
        f"{Config.SESSION_NAME}_ingestor", api_id=Config.API_ID,
        api_hash=Config.API_HASH, bot_token=Config.BOT_TOKEN,
    )
    await client.start()
    succeeded = skipped = failed = 0
    try:
        for index, query in enumerate(queries, 1):
            file_path = None
            try:
                results = await searcher.search(query, 1)
                if not results:
                    failed += 1
                    print(f"[{index}/{len(queries)}] Sin resultado: {query}")
                    continue
                video_id = results[0]["id"]
                cached = db.get_cached_file(video_id)
                if cached:
                    file_id, title = cached
                    await client.send_audio(destination_chat_id, file_id, caption=f"🎵 {title}")
                    skipped += 1
                    print(f"[{index}/{len(queries)}] Caché enviada: {title}")
                    continue
                file_path, title = await downloader.download(
                    f"https://www.youtube.com/watch?v={video_id}", query
                )
                sent = await client.send_audio(
                    destination_chat_id, file_path, title=title, caption=f"🎵 {title}"
                )
                db.add_to_cache(video_id, sent.audio.file_id, title)
                succeeded += 1
                print(f"[{index}/{len(queries)}] OK: {title}")
            except Exception as error:
                failed += 1
                print(f"[{index}/{len(queries)}] ERROR: {query} · {type(error).__name__}: {error}")
            finally:
                if file_path and os.path.isfile(file_path):
                    os.remove(file_path)
                if index < len(queries) and Config.INGEST_DELAY_SECONDS:
                    await asyncio.sleep(Config.INGEST_DELAY_SECONDS)
    finally:
        await client.stop()
        print(
            f"Finalizado · nuevas={succeeded} caché_enviada={skipped} "
            f"fallidas={failed} total={len(queries)}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestor privado de caché AllMusic")
    parser.add_argument("file", help="Archivo TXT con una búsqueda por línea")
    args = parser.parse_args()
    asyncio.get_event_loop().run_until_complete(ingest(args.file))
