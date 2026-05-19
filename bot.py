import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)

from core.config import Config
from services.downloader import MusicDownloader
from services.searcher import MusicSearcher  
from database.manager import DatabaseManager
from core.logger import logger

from handlers.admin import init_admin_handlers
from handlers.users import init_users_handlers
from handlers.callbacks import init_callbacks_handlers

app = Client(
    "music_session",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

db = DatabaseManager()
engine = MusicDownloader(Config.DOWNLOAD_DIR, "cookies.txt")
searcher = MusicSearcher() 
user_results = {}

TXT_DIR = "downloads/archivostxt"
BACKUP_CHAT_ID = -1003950302665  

# --- INGESTOR MASIVO OCULTO (FolderWatcher) ---
async def watch_folder_loop():
    if not os.path.exists(TXT_DIR): os.makedirs(TXT_DIR, exist_ok=True)
    while True:
        try:
            for file_name in os.listdir(TXT_DIR):
                if file_name.endswith(".txt"):
                    file_path = os.path.join(TXT_DIR, file_name)
                    logger.info(f"Ingestor procesando archivo silencioso: {file_name}")
                    with open(file_path, "r", encoding="utf-8") as f: lines = f.readlines()
                    
                    for line in lines:
                        query = line.strip()
                        if not query: continue
                        try:
                            results = await searcher.search(query)
                            if results:
                                video_id = results[0]['id']
                                class FakeMessage:
                                    def __init__(self):
                                        class FakeChat: id = BACKUP_CHAT_ID
                                        self.chat = FakeChat()
                                        self.id = 0
                                await process_download(app, FakeMessage(), video_id, Config.OWNER_ID)
                        except Exception as ie:
                            logger.error(f"Fallo en ingestor para '{query}': {ie}")
                        await asyncio.sleep(3)
                    os.remove(file_path)
                    logger.info(f"[ OK ] Lista {file_name} ingerida en la caché.")
        except Exception as e: logger.error(f"Error en FolderWatcher: {e}")
        await asyncio.sleep(5)

# --- SCRIPT DE BARRA DE PROGRESO UX ANIMADA ---
def make_progress_bar(percentage):
    blocks = int(percentage / 10)
    bar = "▰" * blocks + "▱" * (10 - blocks)
    return bar

# --- BÚSQUEDA MODO INLINE (COMPARTIR EN CUALQUIER CHAT) ---
@app.on_inline_query()
async def inline_search_handler(client, inline_query: InlineQuery):
    query = inline_query.query.strip()
    if not query: return
    if db.is_user_banned(inline_query.from_user.id): return

    try:
        results = await searcher.search(query)
        inline_results = []
        
        for song in results[:8]:
            inline_results.append(
                InlineQueryResultArticle(
                    title=song['title'],
                    description=f"Canal: {song.get('uploader', 'YouTube')}",
                    input_message_content=InputTextMessageContent(
                        message_text=f"🎵 **{song['title']}**\n\n💡 _Para descargar esta canción, copia el título, entra a nuestro chat privado y pégalo directamente en el buscador._"
                    ),
                    thumb_url="https://cdn-icons-png.flaticon.com/512/3043/3043663.png"
                )
            )
        await inline_query.answer(inline_results, cache_time=5)
    except Exception as e:
        logger.error(f"Error en buscador inline: {e}")

# --- KEYBOARDS ---
def create_search_keyboard(results, page, user_id):
    start = (page - 1) * 5
    end = start + 5
    current_results = results[start:end]

    keyboard = []
    for song in current_results:
        keyboard.append([InlineKeyboardButton(f"🎵 {song['title']}", callback_data=f"dl_{song['id']}")])

    keyboard.append([
        InlineKeyboardButton("⬅️ Ant.", callback_data=f"pg_{page-1}"),
        InlineKeyboardButton("❌ Cancelar", callback_data="close_search"),
        InlineKeyboardButton("➡️ Sig.", callback_data=f"pg_{page+1}")
    ])
    return InlineKeyboardMarkup(keyboard)

async def send_search_results(message, query, results, page=1, user_id=None):
    markup = create_search_keyboard(results, page, user_id)
    await message.reply_text(f"🔎 Resultados para: **{query}**\n📄 Página {page}", reply_markup=markup)

async def edit_search_results(message, query, results, page=1, user_id=None):
    if page < 1 or (page - 1) * 5 >= len(results): return
    markup = create_search_keyboard(results, page, user_id)
    await message.edit_text(f"🔎 Resultados para: **{query}**\n📄 Página {page}", reply_markup=markup)

# --- PROCESADOR DE DESCARGA CON NUEVO DISEÑO DE BARRA ---
async def process_download(client, message, video_id, user_id):
    status = None
    try:
        # 1. Verificación rápida en Caché Local
        cached_data = db.get_cached_file(video_id)
        if cached_data:
            file_id, title = cached_data
            if message.id != 0: 
                status = await client.send_message(message.chat.id, "⚡ **Encontrado... Enviando audio**")
            await client.send_audio(message.chat.id, audio=file_id, caption=f"🎵 {title}")
            db.register_download(user_id, "User", video_id, title)
            if message.id != 0 and status: await status.delete()
            return

        # 2. Descarga fluida de YouTube con diseño de barra solicitado
        if message.id != 0: 
            status = await client.send_message(message.chat.id, f"📥 **Iniciando descarga** ({make_progress_bar(10)}) 10%")

        query_fallback = video_id
        if user_id in user_results:
            for song in user_results[user_id]["results"]:
                if song['id'] == video_id:
                    query_fallback = song['title']
                    break

        if status:
            await asyncio.sleep(0.7)
            await status.edit_text(f"📥 **Descargando Audio** ({make_progress_bar(40)}) 40%")
            await asyncio.sleep(0.7)
            await status.edit_text(f"📥 **Procesando frecuencias de Audio** ({make_progress_bar(75)}) 75%")

        file_path, title = await engine.download(f"https://www.youtube.com/watch?v={video_id}", query_fallback)
        
        if status: 
            await status.edit_text(f"📤 **Subiendo archivo a Telegram** ({make_progress_bar(95)}) 95%")
            
        thumb_path = file_path.rsplit('.', 1)[0] + ".jpg"
        actual_thumb = thumb_path if os.path.exists(thumb_path) else None

        sent_audio = await client.send_audio(
            chat_id=message.chat.id, audio=file_path, thumb=actual_thumb, title=title, caption=f"🎵 {title}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Eliminar", callback_data="del_audio")]])
        )

        db.register_download(user_id, "User", video_id, title)
        db.add_to_cache(video_id, sent_audio.audio.file_id, title)
        
        if status: await status.delete()
        if os.path.exists(file_path): os.remove(file_path)
        if actual_thumb and os.path.exists(actual_thumb): os.remove(actual_thumb)
            
        # Panel dura 2 horas flotando activo antes de borrarse
        if message.id != 0:
            async def auto_delete_panel(msg, uid):
                await asyncio.sleep(7200)
                try:
                    await msg.delete()
                    user_results.pop(uid, None)
                except Exception: pass
            asyncio.create_task(auto_delete_panel(message, user_id))
            
    except Exception as e:
        if status: await status.edit_text("❌ **Error: Esta pista no se encuentra disponible actualmente.**")
        raise Exception(str(e))

init_admin_handlers(app, db)
init_users_handlers(app, db, searcher, user_results, send_search_results, process_download)
init_callbacks_handlers(app, db, user_results, edit_search_results, process_download)

async def main():
    await app.start()
    logger.info("[ OK ] Bot iniciado exitosamente...")
    asyncio.create_task(watch_folder_loop())
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())