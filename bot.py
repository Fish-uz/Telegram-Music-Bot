import asyncio
import os
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.config import Config
from services.downloader import MusicDownloader
from services.searcher import MusicSearcher  
from database.manager import DatabaseManager

# IMPORTACIÓN DESDE TU CARPETA CORE (Ajusta el nombre si se llama diferente)
from core.logger import logger

# Conectamos los módulos de handlers
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

# --- INGESTOR DE CARPETAS MASIVO (FolderWatcher) ---
TXT_DIR = "downloads/archivostxt"
BACKUP_CHAT_ID = -1003950302665  # Tu chat de respaldo asignado

async def watch_folder_loop():
    """Busca archivos .txt en downloads/archivostxt y los descarga automáticamente."""
    if not os.path.exists(TXT_DIR):
        os.makedirs(TXT_DIR, exist_ok=True)
        
    while True:
        try:
            for file_name in os.listdir(TXT_DIR):
                if file_name.endswith(".txt"):
                    file_path = os.path.join(TXT_DIR, file_name)
                    logger.info(f"Archivo masivo detectado en ruta: {file_name}")
                    
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    
                    for line in lines:
                        query = line.strip()
                        if not query: continue
                        
                        logger.info(f"Procesando línea de texto: '{query}'")
                        try:
                            # Buscamos en YouTube para obtener los metadatos correctos
                            results = await searcher.search(query)
                            if results:
                                video_id = results[0]['id']
                                
                                # Simulación de mensaje para desviar al grupo de respaldo
                                class FakeMessage:
                                    def __init__(self):
                                        class FakeChat: id = BACKUP_CHAT_ID
                                        self.chat = FakeChat()
                                        self.id = 0
                                
                                fake_msg = FakeMessage()
                                # Procesamos la descarga de forma segura
                                await process_download(app, fake_msg, video_id, Config.OWNER_ID)
                            else:
                                logger.warning(f"No se encontraron resultados en YouTube para: '{query}'")
                        except Exception as inner_e:
                            # Si process_download o la búsqueda fallan, se captura aquí de forma limpia
                            logger.error(f"No se pudo procesar la pista '{query}'. Razón: {inner_e}")
                        
                        await asyncio.sleep(3) # Pausa preventiva anti-bloqueos
                        
                    os.remove(file_path)
                    logger.info(f"[ OK ] Archivo masivo {file_name} eliminado tras ser procesado.")
        except Exception as e:
            logger.error(f"Error crítico en el bucle FolderWatcher: {e}")
            
        await asyncio.sleep(5)

# --- INTERFACES VISUALES ---

def create_search_keyboard(results, page, user_id):
    start = (page - 1) * 5
    end = start + 5
    current_results = results[start:end]
    user_state = user_results.get(user_id, {})

    keyboard = []
    for song in current_results:
        keyboard.append([InlineKeyboardButton(f"🎵 {song['title']}", callback_data=f"dl_{song['id']}")])

    keyboard.append([
        InlineKeyboardButton("⬅️ Ant.", callback_data=f"pg_{page-1}"),
        InlineKeyboardButton("❌ Canc", callback_data="close_search"),
        InlineKeyboardButton("➡️ Sig.", callback_data=f"pg_{page+1}")
    ])

    l_state = "✅" if user_state.get("lossless") else "❓"
    f_text = "👤 Artista" if user_state.get("filter") == "uploader" else "🎵 Title"
    keyboard.append([
        InlineKeyboardButton(f"{l_state} Lossless", callback_data="toggle_lossless"),
        InlineKeyboardButton(f"{f_text}", callback_data="toggle_filter")
    ])
    return InlineKeyboardMarkup(keyboard)

async def send_search_results(message, query, results, page=1, user_id=None):
    markup = create_search_keyboard(results, page, user_id)
    await message.reply_text(f"🔎 Resultados para: **{query}**\n📄 Página {page}", reply_markup=markup)

async def edit_search_results(message, query, results, page=1, user_id=None):
    if page < 1 or (page - 1) * 5 >= len(results): return
    markup = create_search_keyboard(results, page, user_id)
    await message.edit_text(f"🔎 Resultados para: **{query}**\n📄 Página {page}", reply_markup=markup)

# --- PROCESADOR DE DESCARGAS ---

async def process_download(client, message, video_id, user_id):
    status = None
    try:
        # 1. Comprobación en la Base de Datos (Caché)
        cached_data = db.get_cached_file(video_id)
        if cached_data:
            file_id, title = cached_data
            if message.id != 0:
                status = await client.send_message(message.chat.id, "⚡ **¡Encontrado en caché! Enviando...**")
            
            await client.send_audio(
                message.chat.id, audio=file_id, caption=f"🎵 {title}", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Eliminar", callback_data="del_audio")]])
            )
            db.register_download(user_id, "User", video_id, title)
            if message.id != 0 and status: await status.delete()
            return

        # 2. Descarga regular de YouTube
        if message.id != 0:
            status = await client.send_message(message.chat.id, "⏳ **Iniciando descarga...**")

        query_fallback = video_id
        if user_id in user_results:
            for song in user_results[user_id]["results"]:
                if song['id'] == video_id:
                    query_fallback = song['title']
                    break

        # Aquí es donde ytdlp puede fallar si el video fue borrado o es privado
        file_path, title = await engine.download(f"https://www.youtube.com/watch?v={video_id}", query_fallback)
        
        if status: await status.edit_text("📤 **Subiendo a Telegram...**")
            
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
            
        # Temporizador para que el panel dure 2 horas flotando activo
        if message.id != 0:
            async def auto_delete_panel(msg_to_delete, uid):
                await asyncio.sleep(7200)
                try:
                    await msg_to_delete.delete()
                    user_results.pop(uid, None)
                except Exception: pass

            asyncio.create_task(auto_delete_panel(message, user_id))
            
    except Exception as e:
        # Si ocurre un error, avisamos al usuario (si es chat directo) de forma amigable
        if message.id != 0 and status: 
            await status.edit_text(f"❌ **Esta pista no está disponible o no se pudo descargar.**")
        
        # Limpiamos el mensaje de error de la terminal: extraemos solo el texto relevante omitiendo el "Traceback"
        error_msg = str(e).split('\n')[-1]
        raise Exception(f"Video no disponible / Error en motor de descarga ({error_msg})")

# --- CONEXIÓN DE MANEJADORES ---
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