import asyncio
import logging
from pyrogram import Client, filters
from core.config import Config

logger = logging.getLogger(__name__)
db = None

async def admin_panel(client, message):
    if message.from_user.id != Config.OWNER_ID: return
    
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
        return await message.reply_text("❌ Error en la base de datos.")

    dashboard_text = (
        "📊 **[DASHBOARD DE ADMINISTRACIÓN]**\n"
        "───────────────────────────\n\n"
        f"👥 **Usuarios Totales:** `{total_usuarios}`\n"
        f"📥 **Descargas Totales:** `{total_descargas}` canciones\n"
        f"⚡ **Pistas en Caché:** `{total_cache}`\n"
        f"🚫 **Usuarios Baneados:** `{total_baneados}`\n\n"
        "───────────────────────────\n"
        "📢 **Comandos de Control Remoto:**\n"
        "• `/ban [ID]` (o respondiendo a un mensaje) — Banear\n"
        "• `/unban [ID]` — Desbanear usuario\n"
        "• `/broadcast [mensaje]` — Anuncio global"
    )
    await message.reply_text(dashboard_text)

async def ban_user(client, message):
    if message.from_user.id != Config.OWNER_ID: return
    target_id = None

    # Opción 1: Viene por ID directo (/ban 12345)
    if len(message.command) > 1:
        try:
            target_id = int(message.command[1])
        except ValueError:
            return await message.reply_text("❌ El ID debe ser un número entero.")
    # Opción 2: Viene respondiendo a un mensaje
    elif message.reply_to_message:
        target_id = message.reply_to_message.from_user.id

    if not target_id:
        return await message.reply_text("📋 **Modo de uso:** `/ban [ID_Usuario]` o responde a su mensaje con `/ban`")

    db.set_user_ban(target_id, True)
    logger.info(f"ADMIN: El usuario {target_id} ha sido baneado de forma remota.")
    await message.reply_text(f"🚫 **Usuario `{target_id}` baneado exitosamente.**")

async def unban_user(client, message):
    if message.from_user.id != Config.OWNER_ID: return
    if len(message.command) < 2:
        return await message.reply_text("📋 **Modo de uso:** `/unban [ID_Usuario]`")
    
    try:
        target_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ El ID debe ser numérico.")

    db.set_user_ban(target_id, False)
    logger.info(f"ADMIN: El usuario {target_id} ha sido desbaneado.")
    await message.reply_text(f"✅ **Usuario `{target_id}` desbaneado.**")

async def broadcast_command(client, message):
    if message.from_user.id != Config.OWNER_ID: return
    if len(message.command) < 2:
        return await message.reply_text("📢 **Modo de uso:** `/broadcast [Mensaje]`")

    mensaje_global = message.text.split(None, 1)[1]
    cursor = db.conn.cursor()
    cursor.execute("SELECT DISTINCT user_id FROM users")
    usuarios = cursor.fetchall()

    if not usuarios: return await message.reply_text("No hay usuarios.")

    total = len(usuarios)
    status_msg = await message.reply_text(f"🚀 Enviando broadcast a `{total}` usuarios...")
    exitosos, fallidos = 0, 0

    for row in usuarios:
        try:
            await client.send_message(chat_id=row[0], text=mensaje_global)
            exitosos += 1
        except Exception:
            fallidos += 1
        if (exitosos + fallidos) % 3 == 0: await asyncio.sleep(1)

    await status_msg.edit_text(f"📢 **Broadcast Completo**\n\n✅ Éxito: `{exitosos}`\n❌ Fallidos: `{fallidos}`")

def init_admin_handlers(app_instance, shared_db):
    global db
    db = shared_db
    app_instance.on_message(filters.command("admin") & filters.private)(admin_panel)
    app_instance.on_message(filters.command("ban") & filters.private)(ban_user)
    app_instance.on_message(filters.command("unban") & filters.private)(unban_user)
    app_instance.on_message(filters.command("broadcast") & filters.private)(broadcast_command)