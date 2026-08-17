"""Comandos y búsqueda para usuarios de AllMusic."""

from __future__ import annotations

import asyncio
import logging
import platform
import time
from collections import defaultdict, deque

from pyrogram import filters
from pyrogram.errors import RPCError
from pyrogram.types import KeyboardButton, ReplyKeyboardMarkup

from core.config import Config

logger = logging.getLogger("allmusic.users")
db = searcher = resolver = user_results = send_search_results = process_download = None
request_times = defaultdict(deque)
user_warnings = defaultdict(int)


def _menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🏆 Top global"), KeyboardButton("👤 Mi perfil")],
         [KeyboardButton("📜 Mi historial"), KeyboardButton("❓ Ayuda")]],
        resize_keyboard=True,
    )


async def start_command(client, message):
    db.register_user(message.from_user.id, message.from_user.username)
    await message.reply_text(
        "🎵 **Bienvenido a AllMusic**\n\n"
        "Escribe una canción, artista o pega un enlace de Spotify, Deezer o YouTube. "
        "Te mostraremos opciones y recibirás el audio directamente aquí.",
        reply_markup=_menu(),
    )


async def help_command(client, message):
    if db.is_user_banned(message.from_user.id): return
    await message.reply_text(
        "**Cómo usar AllMusic**\n\n"
        "• Escribe el nombre de una canción o artista.\n"
        "• Pega un enlace de Spotify o Deezer para encontrar su equivalente en YouTube.\n"
        "• Usa `/playlist URL` para descargar hasta el límite configurado.\n\n"
        "**Comandos**\n"
        "`/top` ranking global · `/perfil` estadísticas · `/historial` últimas pistas · "
        "`/soporte mensaje` contacto con administración."
    )


async def show_top(client, message):
    if db.is_user_banned(message.from_user.id): return
    top = db.get_top_songs(10)
    if not top:
        return await message.reply_text("📉 Todavía no hay descargas en el ranking.")
    text = "🏆 **Top global de AllMusic**\n\n" + "\n".join(
        f"{index}. **{title}** — {count}" for index, (title, count) in enumerate(top, 1)
    )
    await message.reply_text(text)


async def show_profile(client, message):
    if db.is_user_banned(message.from_user.id): return
    profile = db.get_user_profile(message.from_user.id)
    if not profile:
        return await message.reply_text("No hay estadísticas todavía.")
    await message.reply_text(
        "👤 **Tu perfil musical**\n\n"
        f"Descargas: `{profile['total_downloads']}`\n"
        f"Última pista: `{profile['last_song_title'] or 'Ninguna'}`\n"
        f"Actividad: `{profile['last_download_date'] or 'Sin actividad'}`"
    )


async def show_history(client, message):
    if db.is_user_banned(message.from_user.id): return
    rows = db.get_user_history(message.from_user.id, 5)
    if not rows:
        return await message.reply_text("📋 Tu historial está vacío.")
    await message.reply_text("📜 **Tus últimas pistas**\n\n" + "\n".join(
        f"{index}. `{row['title']}`" for index, row in enumerate(rows, 1)
    ))


async def support_command(client, message):
    if db.is_user_banned(message.from_user.id): return
    if len(message.command) < 2:
        return await message.reply_text("Uso: `/soporte describe tu problema`")
    text = message.text.split(None, 1)[1]
    user = message.from_user
    try:
        await client.send_message(
            Config.OWNER_ID,
            f"🛟 **Soporte AllMusic**\nUsuario: {user.first_name} (@{user.username or 'sin_usuario'})\n"
            f"ID: `{user.id}`\nMensaje: {text}",
        )
        await message.reply_text("✅ Mensaje enviado a administración.")
    except RPCError:
        logger.exception("No se pudo entregar una solicitud de soporte")
        await message.reply_text("No se pudo entregar el mensaje. Intenta más tarde.")


async def playlist_download(client, message):
    if db.is_user_banned(message.from_user.id): return
    if len(message.command) < 2:
        return await message.reply_text("Uso: `/playlist URL_DE_YOUTUBE`")
    status = await message.reply_text("🔎 Analizando playlist…")
    ids = await searcher.get_playlist_ids(message.command[1], Config.PLAYLIST_LIMIT)
    if not ids:
        return await status.edit_text("❌ La playlist está vacía, no es pública o no es válida.")
    await status.edit_text(f"📚 Se procesarán {len(ids)} pistas.")
    for index, video_id in enumerate(ids, 1):
        await status.edit_text(f"📚 Playlist: pista {index}/{len(ids)}")
        await process_download(client, message, video_id, message.from_user.id)
    await status.edit_text("✅ Playlist procesada.")


def _allowed(user_id: int) -> bool:
    now = time.monotonic()
    timestamps = request_times[user_id]
    while timestamps and now - timestamps[0] > 10:
        timestamps.popleft()
    timestamps.append(now)
    return len(timestamps) <= 8


async def handle_message(client, message):
    user = message.from_user
    if db.is_user_banned(user.id): return
    menu_actions = {
        "🏆 Top global": show_top, "👤 Mi perfil": show_profile,
        "📜 Mi historial": show_history, "❓ Ayuda": help_command,
    }
    if message.text in menu_actions:
        return await menu_actions[message.text](client, message)
    if not _allowed(user.id):
        user_warnings[user.id] += 1
        if user_warnings[user.id] >= 3:
            db.set_user_ban(user.id, True)
            await client.send_message(Config.OWNER_ID, f"🚫 Auto-ban anti-flood: `{user.id}`")
            return await message.reply_text("Tu acceso fue bloqueado por solicitudes abusivas.")
        return await message.reply_text("⚠️ Demasiadas solicitudes. Espera unos segundos.")

    db.register_user(user.id, user.username)
    logger.info("Búsqueda recibida · user=%s source=message", user.id)
    status = await message.reply_text("🔎 Buscando…")
    try:
        resolved = await resolver.resolve(message.text)
        if resolved.source != "Texto":
            logger.info("Enlace reconocido · user=%s source=%s", user.id, resolved.source)
            await status.edit_text(f"🔗 Enlace de {resolved.source} reconocido. Buscando `{resolved.query}`…")
        results = await searcher.search(resolved.query, Config.SEARCH_RESULTS_LIMIT)
        if not results:
            return await status.edit_text("No encontramos resultados. Prueba con artista y título.")
        user_results[user.id] = {
            "query": resolved.query, "source": resolved.source, "results": results,
            "filter": "title", "username": user.username,
            "created_at": time.monotonic(),
        }
        logger.info("Búsqueda completada · user=%s results=%s", user.id, len(results))
        await status.delete()
        await send_search_results(message, resolved.query, results, 1, user.id)
    except Exception as error:
        logger.exception("Error buscando %r", message.text)
        await status.edit_text(f"❌ No se pudo procesar la búsqueda: {str(error)[:120]}")


async def dashboard_command(client, message):
    if message.from_user.id != Config.OWNER_ID:
        return await message.reply_text("🚫 Acceso denegado.")
    stats = db.get_dashboard_stats()
    await message.reply_text(
        "📊 **AllMusic · Estado**\n\n"
        f"Usuarios: `{stats['total_users']}`\nDescargas: `{stats['total_downloads']}`\n"
        f"Caché: `{stats['cached_songs']}`\nFallos: `{stats['failed_downloads']}`\n"
        f"Sistema: `{platform.system()} {platform.release()}`"
    )


def init_users_handlers(app_instance, shared_db, shared_searcher, shared_resolver,
                        shared_results, fn_send, fn_download):
    global db, searcher, resolver, user_results, send_search_results, process_download
    db, searcher, resolver = shared_db, shared_searcher, shared_resolver
    user_results, send_search_results, process_download = shared_results, fn_send, fn_download
    commands = {
        "start": start_command, "help": help_command, "top": show_top,
        "perfil": show_profile, "historial": show_history, "soporte": support_command,
        "playlist": playlist_download, "dashboard": dashboard_command,
    }
    for name, handler in commands.items():
        app_instance.on_message(filters.command(name) & filters.private)(handler)
    excluded = list(commands) + ["admin", "broadcast", "ban", "unban"]
    app_instance.on_message(filters.text & filters.private & ~filters.command(excluded))(handle_message)
