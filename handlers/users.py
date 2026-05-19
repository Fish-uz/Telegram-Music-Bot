import asyncio
import logging
from pyrogram import Client, filters
from core.config import Config

logger = logging.getLogger(__name__)

db = None
searcher = None
user_results = None
send_search_results = None
process_download = None

async def show_top(client, message):
    user_id = message.from_user.id
    if db.is_user_banned(user_id): return
    top_songs = db.get_top_songs(10)
    if not top_songs:
        return await message.reply_text("📉 Aún no hay suficientes datos.")
    text = "🏆 **TOP 10 Canciones más descargadas:**\n\n"
    for i, (title, count) in enumerate(top_songs, 1):
        text += f"{i}. **{title}** — {count} veces\n"
    await message.reply_text(text)

async def show_profile(client, message):
    user_id = message.from_user.id
    if db.is_user_banned(user_id): return
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT u.total_downloads, u.last_song_title, u.last_download_date,
        (SELECT MIN(date) FROM history WHERE user_id = u.user_id)
        FROM users u WHERE u.user_id = ?
    ''', (user_id,))
    data = cursor.fetchone()
    if not data:
        return await message.reply_text("👤 No tienes estadísticas aún.")
    total, last_title, last_date, first_date = data
    text = (
        f"👤 **Tu Perfil Musical**\n\n"
        f"📊 **Total descargadas:** `{total}`\n"
        f"🎵 **Última canción:** `{last_title}`\n"
        f"⚡ **Última actividad:** `{last_date}`\n"
        f"📅 **Usuario desde:** `{first_date}`"
    )
    await message.reply_text(text)

async def help_command(client, message):
    if db.is_user_banned(message.from_user.id): return
    text = (
        "🎵 **Guía de Uso del Bot**\n\n"
        "1️⃣ **Buscar:** Escribe el nombre de la canción o artista.\n"
        "2️⃣ **Descargar:** Presiona el botón de la canción que quieras.\n"
        "3️⃣ **Filtros:** Usa 'Title/Artista' para ordenar los resultados.\n"
        "4️⃣ **Calidad:** Activa 'Lossless' para mayor fidelidad.\n\n"
        "📜 **Comandos:**\n"
        "• `/top`: Ver lo más escuchado.\n"
        "• `/perfil`: Tus estadísticas personales.\n"
        "• `/playlist [link]`: Descarga una lista de YouTube.\n"
        "• `/soporte [mensaje]`: Enviar mensaje al administrador."
    )
    await message.reply_text(text)

async def soporte_command(client, message):
    user_id = message.from_user.id
    if db.is_user_banned(user_id): return
    if len(message.command) < 2:
        return await message.reply_text("📩 **Modo de uso:** `/soporte [Tu mensaje aquí]`")

    mensaje_usuario = message.text.split(None, 1)[1]
    username = f" (@{message.from_user.username})" if message.from_user.username else ""
    
    reporte_admin = (
        f"📩 **[NUEVO MENSAJE DE SOPORTE]**\n"
        f"───────────────────────────\n"
        f"👤 **Usuario:** {message.from_user.first_name}{username}\n"
        f"🆔 **ID:** `{user_id}`\n\n"
        f"💬 **Mensaje:**\n_{mensaje_usuario}_"
    )
    try:
        await client.send_message(chat_id=Config.OWNER_ID, text=reporte_admin)
        await message.reply_text("✅ **Tu mensaje ha sido enviado al administrador.**")
    except Exception as e:
        logger.error(f"Error en soporte: {e}")
        await message.reply_text("❌ No se pudo enviar el mensaje.")

async def playlist_download(client, message):
    user_id = message.from_user.id
    if db.is_user_banned(user_id): return
    if len(message.command) < 2:
        return await message.reply_text("🔗 Envía el link así: `/playlist URL_DE_LA_LISTA`")

    url = message.command[1]
    status_msg = await message.reply_text("⏳ Analizando playlist... (Límite: 10 canciones)")
    try:
        ids = await searcher.get_playlist_ids(url, limit=10) 
        if not ids:
            return await status_msg.edit("❌ No se encontraron canciones o el link es privado.")
        await status_msg.edit(f"✅ Se encontraron {len(ids)} canciones. Descargando...")
        for vid_id in ids:
            await process_download(client, message, vid_id, user_id)
            await asyncio.sleep(2)
    except Exception as e:
        await status_msg.edit(f"❌ Error: {str(e)[:50]}")

async def handle_message(client, message):
    user_id = message.from_user.id
    query = message.text
    if db.is_user_banned(user_id): return

    status_msg = await message.reply_text("🔎 Buscando...")
    try:
        results = await searcher.search(query)
        if not results:
            await status_msg.edit("❌ No se encontraron resultados.")
            return

        user_results[user_id] = {"query": query, "results": results, "filter": "title", "lossless": False}
        await status_msg.delete()
        await send_search_results(message, query, results, page=1, user_id=user_id)
    except Exception as e:
        logger.error(f"Error en búsqueda directa: {e}")
        await status_msg.edit(f"❌ Error en búsqueda.")

def init_users_handlers(app_instance, shared_db, shared_searcher, shared_results, fn_send, fn_dl):
    global db, searcher, user_results, send_search_results, process_download
    db = shared_db
    searcher = shared_searcher
    user_results = shared_results
    send_search_results = fn_send
    process_download = fn_dl

    app_instance.on_message(filters.command("top") & filters.private)(show_top)
    app_instance.on_message(filters.command("perfil") & filters.private)(show_profile)
    app_instance.on_message(filters.command("help") & filters.private)(help_command)
    app_instance.on_message(filters.command("soporte") & filters.private)(soporte_command)
    app_instance.on_message(filters.command("playlist") & filters.private)(playlist_download)
    app_instance.on_message(
        filters.text & filters.private & 
        ~filters.command(["top", "perfil", "start", "ban", "unban", "admin", "banlist", "playlist", "help", "soporte"])
    )(handle_message)