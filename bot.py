import asyncio
import os
import logging
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.config import Config
from services.downloader import MusicDownloader
from services.searcher import MusicSearcher  
from database.manager import DatabaseManager

from handlers.admin import init_admin_handlers
from handlers.users import init_users_handlers
from handlers.callbacks import init_callbacks_handlers

logger = logging.getLogger(__name__)

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

# --- COPIADO LOCAL: ENTORNO VIGILANTE DE CARPETAS (FolderWatcher) ---
TXT_DIR = "downloads/archivostxt"
BACKUP_CHAT_ID = -1003950302665  # Tu grupo asignado

async def watch_folder_loop():
    """Servicio nativo en segundo plano para procesar archivos .txt masivos sin colgar el chat."""
    if not os.path.exists(TXT_DIR):
        os.makedirs(TXT_DIR, exist_ok=True)
        
    while True:
        try:
            for file_name in os.listdir(TXT_DIR):
                if file_name.endswith(".txt"):
                    file_path = os.path.join(TXT_DIR, file_name)
                    logger.info(f"📁 FolderWatcher detectó un archivo masivo: {file_name}")
                    
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    
                    for line in lines:
                        query = line.strip()
                        if not query: continue
                        
                        try:
                            # Buscar y descargar directo al canal de respaldo
                            results = await searcher.search(query)
                            if results:
                                video_id = results[0]['id']
                                title = results[0]['title']
                                
                                # Simulamos estructura mínima para process_download
                                class FakeMessage:
                                    def __init__(self):
                                        class FakeChat: id = BACKUP_CHAT_ID
                                        self.chat = FakeChat()
                                        self.id = 0
                                    async def reply_text(self, text, *args, **kwargs):
                                        return self
                                    async def edit_text(self, text, *args, **kwargs):
                                        return self
                                
                                # Ejecutar proceso nativo directo al chat de respaldo
                                fake_msg = FakeMessage()
                                await process_download(app, fake_msg, video_id, Config.OWNER_ID)
                        except Exception as inner_e:
                            logger.error(f"Error procesando línea '{query}' del TXT: {inner_e}")
                        await asyncio.sleep(3) # Pausa preventiva por cada canción
                        
                    os.remove(file_path)
                    logger.info(f"✅ Archivo masivo {file_name} procesado y eliminado.")
        except Exception as e:
            logger.error(f"Error en bucle del vigilante FolderWatcher: {e}")
            
        await asyncio.sleep(5) # Verifica la carpeta cada 5 segundos

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
    try:
        cached_data = db.get_cached_file(video_id)
        if cached_data:
            file_id, title = cached_data
            
            # Avisamos que se encontró pero NO alteramos ni borramos el panel de búsqueda
            if message.id != 0:
                status = await client.send_message(message.chat.id, "⚡ **¡Encontrado en la nube! Enviando...**")
            
            await client.send_audio(
                message.chat.id, audio=file_id, caption=f"🎵 {title}", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Eliminar", callback_data="del_audio")]])
            )
            db.register_download(user_id, "User", video_id, title)
            
            if message.id != 0:
                await status.delete()
            return

        # Si no está en caché, avisamos al usuario con un mensaje temporal separado
        status = None
        if message.id != 0:
            status = await client.send_message(message.chat.id, "⏳ **Iniciando descarga desde YouTube...**")

        query_fallback = video_id
        if user_id in user_results:
            for song in user_results[user_id]["results"]:
                if song['id'] == video_id:
                    query_fallback = song['title']
                    break

        file_path, title = await engine.download(f"https://www.youtube.com/watch?v={video_id}", query_fallback)
        
        if status:
            await status.edit_text("📤 **Subiendo archivo a Telegram...**")
            
        thumb_path = file_path.rsplit('.', 1)[0] + ".jpg"
        actual_thumb = thumb_path if os.path.exists(thumb_path) else None

        sent_audio = await client.send_audio(
            chat_id=message.chat.id, audio=file_path, thumb=actual_thumb, title=title, caption=f"🎵 {title}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Eliminar", callback_data="del_audio")]])
        )

        db.register_download(user_id, "User", video_id, title)
        db.add_to_cache(video_id, sent_audio.audio.file_id, title)
        
        # Limpiamos únicamente el mensaje de estado ("Subiendo...") 
        if status:
            await status.delete()
            
        if os.path.exists(file_path): os.remove(file_path)
        if actual_thumb and os.path.exists(actual_thumb): os.remove(actual_thumb)
            
        # --- TEMPORIZADOR DE AUTO-LIMPIEZA (2 HORAS) ---
        # Si es una interacción real de usuario, programamos la eliminación automática del panel para dentro de 2 horas.
        if message.id != 0:
            async def auto_delete_panel(msg_to_delete, uid):
                await asyncio.sleep(7200) # 2 horas en segundos
                try:
                    await msg_to_delete.delete()
                    user_results.pop(uid, None)
                    logger.info(f"⏰ Panel de búsqueda eliminado automáticamente tras 2 horas de inactividad (User {uid}).")
                except Exception:
                    pass # Si el usuario ya lo había borrado manualmente, ignoramos el error

            asyncio.create_task(auto_delete_panel(message, user_id))
            
    except Exception as e:
        logger.error(f"Fallo en descarga {video_id}: {str(e)}", exc_info=True)
        if status:
            await status.edit_text(f"❌ **Error en la descarga.**")

# --- CONEXIÓN DE MANEJAdores ---
init_admin_handlers(app, db)
init_users_handlers(app, db, searcher, user_results, send_search_results, process_download)
init_callbacks_handlers(app, db, user_results, edit_search_results, process_download)

async def main():
    # Iniciamos el Bot de Telegram de Pyrogram
    await app.start()
    logger.info("🚀 Bot activo.")
    print("🚀 Bot iniciado exitosamente...")
    
    # Encendemos el Vigilante de Carpetas locales en paralelo de forma asíncrona segura
    asyncio.create_task(watch_folder_loop())
    
    # Mantenemos vivo el hilo principal
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())