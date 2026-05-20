import asyncio
import logging
import time
import platform
from pyrogram import Client, filters
from core.config import Config

logger = logging.getLogger(__name__)

db = None
searcher = None
user_results = None
send_search_results = None
process_download = None

# Sistemas de control en memoria
user_requests = {}  # { user_id: [timestamps] }
user_warnings = {}  # { user_id: cantidad_de_advertencias }

async def show_top(client, message):
    if db.is_user_banned(message.from_user.id): return
    top_songs = db.get_top_songs(10)
    if not top_songs: return await message.reply_text("📉 Sin datos aún.")
    text = "🏆 **TOP 10 Más Escuchadas:**\n\n"
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
    if not data: return await message.reply_text("👤 Sin estadísticas.")
    total, last_title, last_date, first_date = data
    text = (
        f"👤 **Tu Perfil Musical**\n\n"
        f"📊 **Descargas totales:** `{total}`\n"
        f"🎵 **Última pista:** `{last_title}`\n"
        f"⚡ **Actividad:** `{last_date}`"
    )
    await message.reply_text(text)

async def show_history(client, message):
    """Muestra las últimas 5 canciones descargadas por el usuario."""
    user_id = message.from_user.id
    if db.is_user_banned(user_id): return
    
    cursor = db.conn.cursor()
    # Buscamos en el historial las últimas 5 descargas únicas de este usuario
    cursor.execute('''
        SELECT DISTINCT title FROM history 
        WHERE user_id = ? 
        ORDER BY date DESC LIMIT 5
    ''', (user_id,))
    rows = cursor.fetchall()
    
    if not rows:
        return await message.reply_text("📋 **Tu historial está vacío.** ¡Empieza a buscar música ahora!")
        
    text = "📜 **Tus últimas 5 descargas recientes:**\n\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}️⃣ `{row[0]}`\n"
    text += "\n💡 _Puedes volver a escribir el nombre de cualquiera de ellas para descargarlas de nuevo._"
    await message.reply_text(text)

async def start_command(client, message):
    user_id = message.from_user.id
    db.register_user(user_id)
    await help_command(client, message)
    
async def help_command(client, message):
    if db.is_user_banned(message.from_user.id): return
    text = (
        "🎵 **Guía de Uso Rápido**\n\n"
        "1️⃣ Escribe el nombre de la canción o artista directamente.\n"
        "2️⃣ Usa los botones del panel para cambiar de página o descargar.\n"
        "3️⃣ Filtros: Usa 'Title/Artista' para ordenar los resultados. (Opcional)\n"
        "4️⃣ Calidad: Activa 'Lossless' para mayor fidelidad. (Opcional)\n\n"
        "📜 **Comandos públicos:**\n"
        "• `/top` — Lo más escuchado en el bot.\n"
        "• `/perfil` — Tus números personales.\n"
        "• `/historial` — Tus últimas 5 canciones.\n"
        "• `/soporte [texto]` — Contactar al administrador."
    )
    await message.reply_text(text)

async def soporte_command(client, message):
    user_id = message.from_user.id
    if db.is_user_banned(user_id): return
    if len(message.command) < 2:
        return await message.reply_text("📩 Uso: `/soporte [Tu mensaje]`")

    mensaje_usuario = message.text.split(None, 1)[1]
    username = f" (@{message.from_user.username})" if message.from_user.username else ""
    
    reporte = (
        f"📩 **[SOPORTE]** de {message.from_user.first_name}{username}\n"
        f"🆔 ID: `{user_id}`\n💬 Mensaje: _{mensaje_usuario}_"
    ) 
    try:
        await client.send_message(chat_id=Config.OWNER_ID, text=reporte)
        await message.reply_text("✅ Mensaje enviado al administrador.")
    except Exception:
        await message.reply_text("❌ Error al enviar.")

async def playlist_download(client, message):
    user_id = message.from_user.id
    if db.is_user_banned(user_id): return
    if len(message.command) < 2: return await message.reply_text("🔗 Uso: `/playlist URL`")

    url = message.command[1]
    status_msg = await message.reply_text("⏳ Procesando lista (Máx 10)...")
    try:
        ids = await searcher.get_playlist_ids(url, limit=10) 
        if not ids: return await status_msg.edit("❌ Error. Lista vacía o privada.")
        await status_msg.edit(f"✅ Descargando {len(ids)} canciones...")
        for vid_id in ids:
            await process_download(client, message, vid_id, user_id)
            await asyncio.sleep(2)
    except Exception as e:
        await status_msg.edit(f"❌ Error: {str(e)[:50]}")

async def handle_message(client, message):
    user_id = message.from_user.id
    username = message.from_user.username or "SinNick" # Captura el nick o pone un valor por defecto
    query = message.text
    if db.is_user_banned(user_id): return

    logger.info(f"🔎 Búsqueda de '{query}' realizada por Usuario: {message.from_user.first_name} ID: {user_id} | (@{username})")

    # --- ALGORITMO ANTI-FLOOD CON AUTO-BANEO (3 OPORTUNIDADES) ---
    now = time.time()
    if user_id not in user_requests: user_requests[user_id] = []
    
    user_requests[user_id] = [t for t in user_requests[user_id] if now - t < 10]
    user_requests[user_id].append(now)
    
    if len(user_requests[user_id]) > 15:
        user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
        oportunidades_restantes = 3 - user_warnings[user_id]
        
        if oportunidades_restantes <= 0:
            db.set_user_ban(user_id, True)
            logger.critical(f"🔥 AUTO-BAN: Usuario {user_id} fue bloqueado permanentemente por ignorar el Anti-Flood.")
            await client.send_message(
                chat_id=Config.OWNER_ID, 
                text=f"🔥 **[AUTO-BAN DE SEGURIDAD]**\nEl usuario `{user_id}` ha sido bloqueado automáticamente por ataque de Spam continuo."
            )
            return await message.reply_text("🚫 **Has sido bloqueado permanentemente del bot debido al abuso continuo del sistema de búsquedas.**")
        
        logger.warning(f"⚠️ Anti-Flood activado para {user_id} (Advertencia {user_warnings[user_id]}/3)")
        return await message.reply_text(
            f"⚠️ **¡Detección de Spam!** Estás enviando demasiadas solicitudes.\n"
            f"Oportunidades antes de baneo permanente: **{oportunidades_restantes}**"
        )

    status_msg = await message.reply_text("🔎 Buscando...")
    try:
        results = await searcher.search(query)
        if not results:
            await status_msg.edit("❌ No se encontraron resultados.")

            logger.warning(f"❌ Búsqueda fallida: '{query}' por {message.from_user.first_name} (@{username}) | ID: {user_id}")
            
            # NOTIFICACIÓN DE FALLO AL ADMIN
            await client.send_message(
                chat_id=Config.OWNER_ID,
                text=f"⚠️ **[ALERTA DE BÚSQUEDA FALLIDA]**\n🆔 Usuario: `{user_id}`\n🔍 Query: `{query}`"
            )
            logger.warning(f"Búsqueda fallida registrada: '{query}' por usuario {user_id}")
            return

        user_results[user_id] = {"query": query, "results": results, "filter": "title", "lossless": False}
        await status_msg.delete()
        await send_search_results(message, query, results, page=1, user_id=user_id)
    except Exception as e:
        logger.error(f"Error en búsqueda: {e}")
        await status_msg.edit(f"❌ Error en búsqueda.")

async def dashboard_command(client, message):
    # Verificación de seguridad
    if message.from_user.id != Config.OWNER_ID:
        return await message.reply_text("🚫 Acceso denegado.")

    # Obtenemos los datos (Asegúrate de tener estos métodos en tu DatabaseManager)
    total_users = db.get_total_users()
    total_downloads = db.get_total_downloads()
    total_banned = db.get_total_banned()
    failed_downloads = db.get_failed_downloads()
    os_info = f"{platform.system()} {platform.release()}"
    
    text = (
        "📊 **Dashboard del Sistema**\n\n"
        f"👥 **Usuarios registrados:** `{total_users}`\n"
        f"📥 **Descargas totales:** `{total_downloads}`\n"
        f"🚫 **Usuarios baneados:** `{total_banned}`\n"
        f"⚠️ **Descargas fallidas:** `{failed_downloads}`\n"
        f"🖥 **Sistema Operativo:** `{os_info}`\n\n"
        "✅ _Estado: Online_"
    )
    await message.reply_text(text)

def init_users_handlers(app_instance, shared_db, shared_searcher, shared_results, fn_send, fn_dl):
    global db, searcher, user_results, send_search_results, process_download
    db = shared_db
    searcher = shared_searcher
    user_results = shared_results
    send_search_results = fn_send
    process_download = fn_dl

    app_instance.on_message(filters.command("start") & filters.private)(start_command)
    app_instance.on_message(filters.command("top") & filters.private)(show_top)
    app_instance.on_message(filters.command("perfil") & filters.private)(show_profile)
    app_instance.on_message(filters.command("historial") & filters.private)(show_history)
    app_instance.on_message(filters.command("help") & filters.private)(help_command)
    app_instance.on_message(filters.command("soporte") & filters.private)(soporte_command)
    app_instance.on_message(filters.command("playlist") & filters.private)(playlist_download)
    app_instance.on_message(filters.command("dashboard") & filters.private)(dashboard_command)
    
    app_instance.on_message(
        filters.text & filters.private & 
        ~filters.command([
            "start", "help", "top", "perfil", "historial", "soporte", "playlist", 
            "admin", "broadcast", "banlist", "ban", "unban" , "dashboard"
        ])
    )(handle_message)