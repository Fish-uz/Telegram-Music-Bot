"""Composición y ciclo de vida de AllMusic."""

from __future__ import annotations

import asyncio
import math
import os
import time
from collections import defaultdict

from core.logger import logger
import yt_dlp
from aiohttp import web
from pyrogram import Client
from pyrogram.errors import RPCError
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, InlineQuery,
    InlineQueryResultArticle, InputTextMessageContent,
)

from core.config import Config
from dashboard import DashboardServer
from database.manager import DatabaseManager
from handlers.admin import init_admin_handlers
from handlers.callbacks import init_callbacks_handlers
from handlers.users import init_users_handlers
from services.downloader import MusicDownloader
from services.link_resolver import MusicLinkResolver
from services.searcher import MusicSearcher
from services.update_supervisor import YtDlpUpdateSupervisor

app = Client(
    Config.SESSION_NAME, api_id=Config.API_ID, api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
)
db = DatabaseManager(Config.DATABASE_PATH)
engine = MusicDownloader(Config.DOWNLOAD_DIR, Config.COOKIES_FILE)
searcher = MusicSearcher(Config.COOKIES_FILE)
link_resolver = MusicLinkResolver()
update_supervisor = YtDlpUpdateSupervisor(Config.UPDATE_FAILURE_THRESHOLD)
user_results: dict[int, dict] = {}
download_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
download_slots = asyncio.Semaphore(Config.MAX_SIMULTANEOUS_DOWNLOADS)
runtime_state = {
    "bot_online": False, "active_downloads": 0, "queue_depth": 0,
    "yt_dlp_version": yt_dlp.version.__version__,
}


def make_progress_bar(percentage: float) -> str:
    percentage = max(0, min(100, percentage))
    blocks = int(percentage // 10)
    return "▰" * blocks + "▱" * (10 - blocks)


@app.on_inline_query()
async def inline_search_handler(client, inline_query: InlineQuery):
    query = inline_query.query.strip()
    if not query or db.is_user_banned(inline_query.from_user.id):
        return
    try:
        resolved = await link_resolver.resolve(query)
        results = await searcher.search(resolved.query, limit=8)
        articles = [InlineQueryResultArticle(
            title=song["title"],
            description=f"Canal: {song.get('uploader', 'YouTube')}",
            input_message_content=InputTextMessageContent(
                message_text=f"🎵 **{song['title']}**\n\nAbre @AudioFz_bot para descargarla."
            ),
        ) for song in results]
        await inline_query.answer(articles, cache_time=10)
    except Exception:
        logger.exception("Falló la búsqueda inline")


RESULTS_PER_PAGE = 5


def create_search_keyboard(results, page, user_id):
    start = (page - 1) * RESULTS_PER_PAGE
    keyboard = [[InlineKeyboardButton(
        f"🎵 {song['title']}", callback_data=f"dl_{song['id']}"
    )] for song in results[start:start + RESULTS_PER_PAGE]]
    keyboard.append([InlineKeyboardButton("↕ Ordenar", callback_data="toggle_filter")])
    navigation = []
    if page > 1:
        navigation.append(InlineKeyboardButton("⬅ Anterior", callback_data=f"pg_{page - 1}"))
    navigation.append(InlineKeyboardButton("✕ Cerrar", callback_data="close_search"))
    if start + RESULTS_PER_PAGE < len(results):
        navigation.append(InlineKeyboardButton("Siguiente ➡", callback_data=f"pg_{page + 1}"))
    keyboard.append(navigation)
    return InlineKeyboardMarkup(keyboard)


async def send_search_results(message, query, results, page=1, user_id=None):
    total_pages = max(1, math.ceil(len(results) / RESULTS_PER_PAGE))
    await message.reply_text(
        f"🔎 Resultados para: **{query}**\nPágina {page} de {total_pages}",
        reply_markup=create_search_keyboard(results, page, user_id),
    )


async def edit_search_results(message, query, results, page=1, user_id=None):
    if page < 1 or (page - 1) * RESULTS_PER_PAGE >= len(results):
        return
    total_pages = max(1, math.ceil(len(results) / RESULTS_PER_PAGE))
    try:
        await message.edit_text(
            f"🔎 Resultados para: **{query}**\nPágina {page} de {total_pages}",
            reply_markup=create_search_keyboard(results, page, user_id),
        )
    except RPCError as error:
        if "MESSAGE_NOT_MODIFIED" not in str(error):
            logger.warning("No se pudo cambiar la página de resultados: %s", error)


async def _progress_updater(status, queue: asyncio.Queue):
    last_bucket = -1
    while True:
        percentage, stage = await queue.get()
        if percentage < 0:
            return
        bucket = int(percentage // 10)
        if bucket == last_bucket and stage == "download":
            continue
        last_bucket = bucket
        visible = 15 + percentage * 0.65 if stage == "download" else 82
        label = "Descargando audio" if stage == "download" else "Convirtiendo a MP3"
        try:
            await status.edit_text(f"📥 **{label}**\n{make_progress_bar(visible)} {visible:.0f}%")
        except RPCError:
            pass


def _log_value(value, fallback="-"):
    """Convierte datos externos en un campo de log breve y de una sola línea."""
    normalized = " ".join(str(value or fallback).split())
    return normalized[:120]


async def process_download(
    client, message, video_id, user_id, selected_title=None, username=None
):
    started_at = time.monotonic()
    status = None
    file_path = None
    progress_task = None
    result_info = user_results.get(user_id, {})
    username = username or result_info.get("username")
    selected_title = selected_title or next(
        (song.get("title") for song in result_info.get("results", []) if song.get("id") == video_id),
        video_id,
    )
    log_username = f"@{_log_value(username)}" if username else "-"
    log_title = _log_value(selected_title)
    lock = download_locks[video_id]
    queued = True
    active = False
    runtime_state["queue_depth"] += 1
    logger.info(
        "Solicitud en cola · user_id=%s username=%s title=%r video=%s",
        user_id, log_username, log_title, video_id,
    )
    try:
        async with lock:
            runtime_state["queue_depth"] = max(0, runtime_state["queue_depth"] - 1)
            queued = False
            cached = db.get_cached_file(video_id)
            if cached:
                file_id, title = cached
                if message.id:
                    status = await client.send_message(
                        message.chat.id, f"⚡ **Entregando desde caché**\n{make_progress_bar(95)} 95%"
                    )
                try:
                    await client.send_audio(message.chat.id, file_id, caption=f"🎵 {title}")
                    db.register_download(user_id, username, video_id, title, cache_hit=True)
                    logger.info(
                        "Caché entregada · user_id=%s username=%s title=%r video=%s elapsed=%.2fs",
                        user_id, log_username, log_title, video_id,
                        time.monotonic() - started_at,
                    )
                    if status:
                        await status.delete()
                    return True
                except RPCError:
                    logger.warning("file_id inválido para %s; se regenerará la caché", video_id)
                    db.remove_cached_file(video_id)

            status = await client.send_message(
                message.chat.id, f"⏳ **En cola**\n{make_progress_bar(5)} 5%"
            ) if message.id and not status else status
            if status:
                await status.edit_text(f"⏳ **En cola**\n{make_progress_bar(5)} 5%")
            async with download_slots:
                runtime_state["active_downloads"] += 1
                active = True
                if status:
                    await status.edit_text(f"🔎 **Preparando pista**\n{make_progress_bar(12)} 12%")
                loop = asyncio.get_running_loop()
                progress_queue = asyncio.Queue()
                if status:
                    progress_task = asyncio.create_task(_progress_updater(status, progress_queue))

                def progress(value, stage):
                    loop.call_soon_threadsafe(progress_queue.put_nowait, (value, stage))

                file_path, title = await engine.download(
                    f"https://www.youtube.com/watch?v={video_id}", selected_title, progress
                )
                if progress_task:
                    await progress_queue.put((-1, "done"))
                    await progress_task
                    progress_task = None
                if status:
                    await status.edit_text(f"📤 **Subiendo a Telegram**\n{make_progress_bar(92)} 92%")
                sent = await client.send_audio(
                    message.chat.id, audio=file_path, title=title, caption=f"🎵 {title}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔄 Compartir", switch_inline_query=title),
                        InlineKeyboardButton("🗑 Eliminar", callback_data="del_audio"),
                    ]]),
                )
                db.add_to_cache(video_id, sent.audio.file_id, title)
                db.register_download(user_id, username, video_id, title, cache_hit=False)
                logger.info(
                    "Descarga entregada · user_id=%s username=%s title=%r video=%s elapsed=%.2fs",
                    user_id, log_username, log_title, video_id,
                    time.monotonic() - started_at,
                )
                if status:
                    await status.edit_text(f"✅ **Completado**\n{make_progress_bar(100)} 100%")
                    await asyncio.sleep(1)
                    await status.delete()
                return True
    except Exception as error:
        logger.exception(
            "Descarga fallida · user_id=%s username=%s title=%r video=%s elapsed=%.2fs",
            user_id, log_username, log_title, video_id, time.monotonic() - started_at,
        )
        db.register_failure(video_id, user_id, type(error).__name__, str(error))
        if status:
            try:
                await status.edit_text("❌ No se pudo descargar esta pista. Intenta otro resultado.")
            except RPCError:
                pass
        if Config.AUTO_UPDATE_YTDLP and await update_supervisor.record_failure(error):
            await client.send_message(Config.OWNER_ID, "♻️ yt-dlp fue actualizado. Reiniciando AllMusic…")
            update_supervisor.restart_process()
        return False
    finally:
        if queued:
            runtime_state["queue_depth"] = max(0, runtime_state["queue_depth"] - 1)
        if active:
            runtime_state["active_downloads"] = max(0, runtime_state["active_downloads"] - 1)
        if progress_task:
            progress_task.cancel()
        if file_path and os.path.isfile(file_path):
            os.remove(file_path)
        engine.cleanup(video_id)
        if not lock.locked():
            download_locks.pop(video_id, None)


async def periodic_top_loop(client):
    interval = Config.TOP_BROADCAST_INTERVAL_HOURS * 3600
    await asyncio.sleep(interval)
    while True:
        top = db.get_top_songs(10)
        if top:
            lines = ["🏆 **Top global de AllMusic**", ""] + [
                f"{index}. **{title}** — {count}" for index, (title, count) in enumerate(top, 1)
            ]
            text = "\n".join(lines)
            for user_id in db.list_active_user_ids():
                try:
                    await client.send_message(user_id, text)
                except RPCError:
                    pass
                await asyncio.sleep(0.05)
        await asyncio.sleep(interval)


async def session_cleanup_loop():
    while True:
        await asyncio.sleep(300)
        cutoff = asyncio.get_running_loop().time() - Config.USER_SESSION_TTL
        expired = [user_id for user_id, data in user_results.items()
                   if data.get("created_at", 0) < cutoff]
        for user_id in expired:
            user_results.pop(user_id, None)


init_admin_handlers(app, db)
init_users_handlers(
    app, db, searcher, link_resolver, user_results,
    send_search_results, process_download,
)
init_callbacks_handlers(app, db, user_results, edit_search_results, process_download)


async def main():
    Config.validate()
    runner = None
    background_tasks = []
    try:
        await app.start()
        runtime_state["bot_online"] = True
        logger.info("AllMusic iniciado. Esperando mensajes.")
        dashboard = DashboardServer(db, runtime_state)
        runner = web.AppRunner(dashboard.create_app(), access_log=None)
        await runner.setup()
        await web.TCPSite(runner, Config.WEB_HOST, Config.WEB_PORT).start()
        logger.info("Dashboard disponible en %s:%s", Config.WEB_HOST, Config.WEB_PORT)
        if Config.TOP_BROADCAST_ENABLED:
            background_tasks.append(asyncio.create_task(periodic_top_loop(app)))
        background_tasks.append(asyncio.create_task(session_cleanup_loop()))
        await asyncio.Event().wait()
    finally:
        runtime_state["bot_online"] = False
        for task in background_tasks:
            task.cancel()
        if runner:
            await runner.cleanup()
        if app.is_connected:
            await app.stop()
        db.close()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
