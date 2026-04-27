import asyncio
import os
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from core.config import Config
from services.downloader import MusicDownloader
from services.searcher import MusicSearcher  
from database.manager import DatabaseManager

# Configuración del logger para este módulo
logger = logging.getLogger(__name__)

# --- INICIALIZACIÓN DE COMPONENTES ---

# Cliente principal de Pyrogram
app = Client(
    "music_session",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

# Instancias de servicios globales
db = DatabaseManager()
engine = MusicDownloader(Config.DOWNLOAD_DIR, Config.COOKIES_FILE)
searcher = MusicSearcher() 

# Almacenamiento temporal de resultados de búsqueda por usuario
user_results = {}

# --- COMANDOS DE USUARIO (TOP Y PERFIL) ---

@app.on_message(filters.command("top") & filters.private)
async def show_top(client, message):
    """Muestra el ranking de las 10 canciones más descargadas."""
    user_id = message.from_user.id
    if db.is_user_banned(user_id):
        logger.warning(f"Usuario baneado {user_id} intentó usar /top")
        return
    
    logger.info(f"Usuario {user_id} solicitó el TOP 10")
    top_songs = db.get_top_songs(10)
    if not top_songs:
        return await message.reply_text("📉 Aún no hay suficientes datos.")

    text = "🏆 **TOP 10 Canciones más descargadas:**\n\n"
    for i, (title, count) in enumerate(top_songs, 1):
        text += f"{i}. **{title}** — {count} veces\n"
    await message.reply_text(text)

@app.on_message(filters.command("perfil") & filters.private)
async def show_profile(client, message):
    """Genera y muestra las estadísticas individuales del usuario."""
    user_id = message.from_user.id
    if db.is_user_banned(user_id): return

    logger.info(f"Usuario {user_id} consultó su perfil")
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

@app.on_message(filters.command("help") & filters.private)
async def help_command(client, message):
    """Muestra la guía de ayuda y comandos disponibles."""
    if db.is_user_banned(message.from_user.id): return
    logger.info(f"Usuario {message.from_user.id} solicitó /help")
    text = (
        "🎵 **Guía de Uso del Bot**\n\n"
        "1️⃣ **Buscar:** Escribe el nombre de la canción o artista.\n"
        "2️⃣ **Descargar:** Presiona el botón de la canción que quieras.\n"
        "3️⃣ **Filtros:** Usa 'Title/Artista' para ordenar los resultados.\n"
        "4️⃣ **Calidad:** Activa 'Lossless' para mayor fidelidad.\n\n"
        "📜 **Comandos:**\n"
        "• `/top`: Ver lo más escuchado.\n"
        "• `/perfil`: Tus estadísticas personales.\n"
        "• `/playlist [link]`: Descarga una lista de YouTube."
    )
    await message.reply_text(text)

# --- DESCARGAR PLAYLIST ---

@app.on_message(filters.command("playlist") & filters.private)
async def playlist_download(client, message):
    """Maneja la extracción y descarga secuencial de listas de reproducción."""
    user_id = message.from_user.id
    if db.is_user_banned(user_id): return
    
    if len(message.command) < 2:
        return await message.reply_text("🔗 Envía el link así: `/playlist URL_DE_LA_LISTA`")

    url = message.command[1]
    logger.info(f"Usuario {user_id} inició descarga de playlist: {url}")
    status_msg = await message.reply_text("⏳ Analizando playlist... (Límite: 10 canciones)")

    try:
        ids = await searcher.get_playlist_ids(url, limit=10) 
        if not ids:
            logger.warning(f"No se obtuvieron IDs de la playlist para el usuario {user_id}")
            return await status_msg.edit("❌ No se encontraron canciones o el link es privado.")

        await status_msg.edit(f"✅ Se encontraron {len(ids)} canciones. Iniciando descarga...")
        
        for vid_id in ids:
            logger.info(f"Procesando canción {vid_id} de la playlist (User: {user_id})")
            await process_download(client, message, vid_id, user_id)
            await asyncio.sleep(2) # Pausa de seguridad
            
    except Exception as e:
        logger.error(f"Error procesando playlist de usuario {user_id}: {str(e)}", exc_info=True)
        await status_msg.edit(f"❌ Error en playlist: {str(e)[:50]}")

# --- COMANDOS DE ADMIN ---

@app.on_message(filters.command("admin") & filters.private)
async def admin_panel(client, message):
    """Muestra el panel de control para el administrador."""
    if message.from_user.id != Config.OWNER_ID: return
    text = (
        "🛠 **Panel de Administrador**\n\n"
        "• `/ban` (respondiendo a un mensaje): Bloquea al usuario.\n"
        "• `/unban ID`: Desbloquea al usuario por su ID.\n"
        "• `/banlist`: Lista de usuarios bloqueados."
    )
    await message.reply_text(text)

@app.on_message(filters.command("banlist") & filters.private)
async def show_banlist(client, message):
    """Lista todos los IDs de usuarios con restricción de acceso."""
    if message.from_user.id != Config.OWNER_ID: return
    cursor = db.conn.cursor()
    cursor.execute('SELECT user_id, username FROM users WHERE is_banned = 1')
    banned = cursor.fetchall()
    if not banned:
        return await message.reply_text("✅ No hay usuarios baneados.")
    
    text = "🚫 **Usuarios Baneados:**\n\n"
    for uid, name in banned:
        text += f"• `{uid}` | {name}\n"
    await message.reply_text(text)

@app.on_message(filters.command("ban") & filters.private)
async def ban_user(client, message):
    """Banea a un usuario basándose en la respuesta a su mensaje."""
    if message.from_user.id != Config.OWNER_ID: return
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        db.set_user_ban(target_id, True)
        logger.info(f"ADMIN: Usuario {target_id} ha sido baneado")
        await message.reply_text(f"🚫 Usuario {target_id} baneado.")

@app.on_message(filters.command("unban") & filters.private)
async def unban_user(client, message):
    """Desbloquea a un usuario mediante su ID numérico."""
    if message.from_user.id != Config.OWNER_ID: return
    if len(message.command) > 1:
        target_id = int(message.command[1])
        db.set_user_ban(target_id, False)
        logger.info(f"ADMIN: Usuario {target_id} ha sido desbaneado")
        await message.reply_text(f"✅ Usuario {target_id} desbaneado.")

# --- MANEJADOR DE BÚSQUEDAS ---

@app.on_message(filters.text & filters.private & ~filters.command(["top", "perfil", "start", "ban", "unban", "admin", "banlist","playlist","help"]))
async def handle_message(client, message):
    """Gestiona las peticiones de búsqueda de música."""
    user_id = message.from_user.id
    query = message.text

    if db.is_user_banned(user_id):
        logger.warning(f"Intento de búsqueda de usuario baneado {user_id}")
        return await message.reply_text("🚫 Banned User.")
    
    logger.info(f"Búsqueda recibida de {user_id}: '{query}'")
    status_msg = await message.reply_text("🔎 Buscando...")

    try:
        results = await searcher.search(query)
        if not results:
            logger.info(f"Sin resultados para la búsqueda: '{query}' (User: {user_id})")
            await status_msg.edit("❌ No se encontraron resultados.")
            return

        user_results[user_id] = {
            "query": query, 
            "results": results, 
            "filter": "title", 
            "lossless": False
        }
        
        await status_msg.delete()
        await send_search_results(message, query, results, page=1, user_id=user_id)

    except Exception as e:
        logger.error(f"Error en búsqueda '{query}' (User {user_id}): {str(e)}", exc_info=True)
        await status_msg.edit(f"❌ Error en búsqueda: {str(e)[:50]}")

# --- MANEJADOR DE CALLBACKS ---

@app.on_callback_query()
async def handle_callbacks(client, callback_query):
    """Procesa todas las interacciones con botones en línea."""
    user_id = callback_query.from_user.id
    data = callback_query.data

    if db.is_user_banned(user_id):
        return await callback_query.answer("🚫 Estás baneado.", show_alert=True)

    if user_id not in user_results and data != "del_audio":
        logger.info(f"Sesión expirada para usuario {user_id}")
        await callback_query.answer("⚠️ Sesión expirada, busca de nuevo.")
        return

    # Lógica de paginación
    if data.startswith("pg_"):
        page = int(data.split("_")[1])
        info = user_results[user_id]
        await edit_search_results(callback_query.message, info["query"], info["results"], page, user_id)
    
    # Cerrar panel de búsqueda
    elif data == "close_search":
        await callback_query.message.delete()
        user_results.pop(user_id, None)

    # Iniciar descarga
    elif data.startswith("dl_"):
        video_id = data.split("_", 1)[1]
        logger.info(f"Usuario {user_id} seleccionó descarga: {video_id}")
        await callback_query.answer("📥 Preparando descarga...")
        asyncio.create_task(process_download(client, callback_query.message, video_id, user_id))

    # Eliminar mensaje de audio
    elif data == "del_audio":
        await callback_query.message.delete()

    # Cambiar filtros (Título/Artista)
    elif data == "toggle_filter":
        current_filter = user_results[user_id].get("filter", "title")
        new_filter = "uploader" if current_filter == "title" else "title"
        user_results[user_id]["filter"] = new_filter
        user_results[user_id]["results"].sort(key=lambda x: str(x.get(new_filter, "")).lower())
        logger.info(f"Usuario {user_id} cambió filtro a: {new_filter}")
        await edit_search_results(callback_query.message, user_results[user_id]["query"], user_results[user_id]["results"], 1, user_id)

    # Cambiar calidad (Lossless)
    elif data == "toggle_lossless":
        val = not user_results[user_id].get("lossless", False)
        user_results[user_id]["lossless"] = val
        logger.info(f"Usuario {user_id} cambió modo Lossless a: {val}")
        await edit_search_results(callback_query.message, user_results[user_id]["query"], user_results[user_id]["results"], 1, user_id)

# --- FUNCIONES AUXILIARES ---

async def send_search_results(message, query, results, page=1, user_id=None):
    """Envía un nuevo mensaje con los resultados de búsqueda formateados."""
    markup = create_search_keyboard(results, page, user_id)
    await message.reply_text(f"🔎 Resultados para: **{query}**\n📄 Página {page}", reply_markup=markup)

async def edit_search_results(message, query, results, page=1, user_id=None):
    """Edita un mensaje existente de resultados (útil para paginación)."""
    if page < 1 or (page - 1) * 5 >= len(results): return
    markup = create_search_keyboard(results, page, user_id)
    await message.edit_text(f"🔎 Resultados para: **{query}**\n📄 Página {page}", reply_markup=markup)

def create_search_keyboard(results, page, user_id):
    """Construye el teclado Inline para los resultados de búsqueda."""
    start = (page - 1) * 5
    end = start + 5
    current_results = results[start:end]
    user_state = user_results.get(user_id, {})

    keyboard = []
    # Botones de canciones
    for song in current_results:
        keyboard.append([InlineKeyboardButton(f"🎵 {song['title']}", callback_data=f"dl_{song['id']}")])

    # Botones de navegación
    keyboard.append([
        InlineKeyboardButton("⬅️ Ant.", callback_data=f"pg_{page-1}"),
        InlineKeyboardButton("❌ Canc", callback_data="close_search"),
        InlineKeyboardButton("➡️ Sig.", callback_data=f"pg_{page+1}")
    ])

    # Botones de ajustes
    l_state = "✅" if user_state.get("lossless") else "❓"
    f_text = "👤 Artista" if user_state.get("filter") == "uploader" else "🎵 Title"
    keyboard.append([
        InlineKeyboardButton(f"{l_state} Lossless", callback_data="toggle_lossless"),
        InlineKeyboardButton(f"{f_text}", callback_data="toggle_filter")
    ])
    return InlineKeyboardMarkup(keyboard)

async def process_download(client, message, video_id, user_id):
    """Gestiona el flujo completo desde la verificación en caché hasta la subida a Telegram."""
    try:
        # 1. Verificar Caché
        cached_data = db.get_cached_file(video_id)
        if cached_data:
            file_id, title = cached_data
            logger.info(f"Caché HIT: Enviando {video_id} instantáneamente (User {user_id})")
            await client.edit_message_text(message.chat.id, message.id, "⚡ **¡Encontrado!...**")
            await client.send_audio(message.chat.id, audio=file_id, caption=f"🎵 {title}", 
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Eliminar", callback_data="del_audio")]]))
            db.register_download(user_id, "User", video_id, title)
            await client.delete_messages(message.chat.id, message.id)
            return

        # 2. Descarga de YouTube
        logger.info(f"Caché MISS: Descargando {video_id} desde YouTube (User {user_id})")
        await client.edit_message_text(message.chat.id, message.id, "⏳ **Iniciando descarga...**")
        file_path, title = await engine.download(f"https://www.youtube.com/watch?v={video_id}", video_id)
        
        # 3. Preparación y Subida
        await client.edit_message_text(message.chat.id, message.id, "📤 **Subiendo a Telegram...**")
        thumb_path = file_path.rsplit('.', 1)[0] + ".jpg"
        actual_thumb = thumb_path if os.path.exists(thumb_path) else None

        sent_audio = await client.send_audio(
            chat_id=message.chat.id, audio=file_path, thumb=actual_thumb, title=title, caption=f"🎵 {title}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Eliminar", callback_data="del_audio")]])
        )

        # 4. Registro y Limpieza
        db.register_download(user_id, "User", video_id, title)
        db.add_to_cache(video_id, sent_audio.audio.file_id, title)
        logger.info(f"Descarga completada y cacheada: {title} (User {user_id})")
        
        await client.delete_messages(message.chat.id, message.id)
        if os.path.exists(file_path): os.remove(file_path)
        if actual_thumb and os.path.exists(actual_thumb): os.remove(actual_thumb)
            
    except Exception as e:
        logger.error(f"Fallo crítico en proceso de descarga {video_id}: {str(e)}", exc_info=True)
        await client.edit_message_text(message.chat.id, message.id, f"❌ **Error:** {str(e)[:50]}")

if __name__ == "__main__":
    # Registro de inicio en consola
    print("🚀 Bot iniciado exitosamente...")
    app.run()