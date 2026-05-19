import asyncio
import logging
from pyrogram import Client, filters
from core.config import Config

logger = logging.getLogger(__name__)
db = None

async def admin_panel(client, message):
    """Muestra el panel de control interactivo con estadísticas reales."""
    if message.from_user.id != Config.OWNER_ID: return
    
    logger.info("📊 Admin solicitó el Dashboard Estadístico.")
    cursor = db.conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users")
        total_usuarios = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(total_downloads) FROM users")
        total_descargas = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM cache")
        total_cache = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
        total_baneados = cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error al recopilar estadísticas: {e}")
        return await message.reply_text("❌ Error al leer las estadísticas de la base de datos.")

    dashboard_text = (
        "📊 **[DASHBOARD DE ADMINISTRACIÓN]**\n"
        "───────────────────────────\n\n"
        f"👥 **Usuarios Totales:** `{total_usuarios}`\n"
        f"📥 **Descargas Totales:** `{total_descargas}` canciones\n"
        f"⚡ **Pistas en Caché:** `{total_cache}` (Ahorro de Banda)\n"
        f"🚫 **Usuarios Baneados:** `{total_baneados}`\n\n"
        "───────────────────────────\n"
        "📢 **Comandos Disponibles:**\n"
        "• `/broadcast [mensaje]` — Enviar anuncio masivo.\n"
        "• `/banlist` — Ver lista de bloqueados.\n"
        "• `/unban [ID]` — Desbanear por ID."
    )
    await message.reply_text(dashboard_text)

async def broadcast_command(client, message):
    """Envía un anuncio masivo con pausas cada 3 mensajes para evitar el baneo de Telegram."""
    if message.from_user.id != Config.OWNER_ID: return

    if len(message.command) < 2:
        return await message.reply_text("📢 **Modo de uso:** `/broadcast [Tu mensaje aquí]`")

    mensaje_global = message.text.split(None, 1)[1]
    cursor = db.conn.cursor()
    
    try:
        cursor.execute("SELECT DISTINCT user_id FROM users")
        usuarios = cursor.fetchall()
    except Exception as e:
        logger.error(f"Error en broadcast: {e}")
        return await message.reply_text("❌ Error al leer la base de datos.")

    if not usuarios:
        return await message.reply_text("📉 No hay usuarios registrados.")

    total_usuarios = len(usuarios)
    status_msg = await message.reply_text(f"🚀 **Iniciando envío masivo...**\n👥 Destinatarios: `{total_usuarios}`")

    exitosos, fallidos = 0, 0
    for row in usuarios:
        target_id = row[0]
        try:
            await client.send_message(chat_id=target_id, text=mensaje_global)
            exitosos += 1
        except Exception as e:
            fallidos += 1
            logger.debug(f"No se pudo enviar broadcast a ID {target_id}: {e}")

        # Control Anti-Spam estricto: Pausa de 1 segundo cada 3 envíos
        if (exitosos + fallidos) % 3 == 0:
            await asyncio.sleep(1)

    await status_msg.edit_text(
        f"📢 **[BROADCAST COMPLETO]**\n\n"
        f"✅ Entregados con éxito: `{exitosos}`\n"
        f"❌ Fallidos/Bloqueados: `{fallidos}`\n"
        f"✨ Total procesados: `{total_usuarios}`"
    )

async def show_banlist(client, message):
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

async def ban_user(client, message):
    if message.from_user.id != Config.OWNER_ID: return
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        db.set_user_ban(target_id, True)
        logger.info(f"ADMIN: Usuario {target_id} ha sido baneado")
        await message.reply_text(f"🚫 Usuario {target_id} baneado.")

async def unban_user(client, message):
    if message.from_user.id != Config.OWNER_ID: return
    if len(message.command) > 1:
        target_id = int(message.command[1])
        db.set_user_ban(target_id, False)
        logger.info(f"ADMIN: Usuario {target_id} ha sido desbaneado")
        await message.reply_text(f"✅ Usuario {target_id} desbaneado.")

def init_admin_handlers(app_instance, shared_db):
    global db
    db = shared_db
    
    app_instance.on_message(filters.command("admin") & filters.private, group=-1)(admin_panel)
    app_instance.on_message(filters.command("broadcast") & filters.private, group=-1)(broadcast_command)
    app_instance.on_message(filters.command("banlist") & filters.private, group=-1)(show_banlist)
    app_instance.on_message(filters.command("ban") & filters.private, group=-1)(ban_user)
    app_instance.on_message(filters.command("unban") & filters.private, group=-1)(unban_user)