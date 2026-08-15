"""Controles privados del propietario de AllMusic."""

import asyncio
import logging

from pyrogram import filters
from pyrogram.errors import RPCError

from core.config import Config
from core.logger import audit_logger

logger = logging.getLogger("allmusic.admin")
db = None


def owner_only(message) -> bool:
    return bool(message.from_user and message.from_user.id == Config.OWNER_ID)


async def admin_panel(client, message):
    if not owner_only(message): return
    stats = db.get_dashboard_stats()
    await message.reply_text(
        "🛠 **AllMusic · Administración**\n\n"
        f"Usuarios: `{stats['total_users']}`\nDescargas: `{stats['total_downloads']}`\n"
        f"Pistas en caché: `{stats['cached_songs']}`\nBaneados: `{stats['banned_users']}`\n"
        f"Fallos: `{stats['failed_downloads']}`\n\n"
        "`/ban ID` · `/unban ID` · `/broadcast mensaje` · `/dashboard`"
    )


def _target_id(message):
    if len(message.command) > 1:
        try: return int(message.command[1])
        except ValueError: return None
    return message.reply_to_message.from_user.id if message.reply_to_message else None


async def ban_user(client, message):
    if not owner_only(message): return
    target = _target_id(message)
    if not target:
        return await message.reply_text("Uso: `/ban ID` o responde a un mensaje con `/ban`.")
    db.set_user_ban(target, True)
    audit_logger.info("BAN admin_id=%s target_id=%s", message.from_user.id, target)
    await message.reply_text(f"🚫 Usuario `{target}` baneado.")


async def unban_user(client, message):
    if not owner_only(message): return
    target = _target_id(message)
    if not target:
        return await message.reply_text("Uso: `/unban ID`.")
    db.set_user_ban(target, False)
    audit_logger.info("UNBAN admin_id=%s target_id=%s", message.from_user.id, target)
    await message.reply_text(f"✅ Usuario `{target}` desbaneado.")


async def broadcast_command(client, message):
    if not owner_only(message): return
    if len(message.command) < 2:
        return await message.reply_text("Uso: `/broadcast mensaje`.")
    text = message.text.split(None, 1)[1]
    users = db.list_active_user_ids()
    audit_logger.info("BROADCAST_START admin_id=%s recipients=%s", message.from_user.id, len(users))
    status = await message.reply_text(f"Enviando a {len(users)} usuarios…")
    success = failed = 0
    for user_id in users:
        try:
            await client.send_message(user_id, text)
            success += 1
        except RPCError:
            failed += 1
        await asyncio.sleep(0.05)
    await status.edit_text(f"✅ Broadcast terminado\nÉxitos: `{success}` · Fallos: `{failed}`")
    audit_logger.info(
        "BROADCAST_END admin_id=%s success=%s failed=%s",
        message.from_user.id, success, failed,
    )


def init_admin_handlers(app_instance, shared_db):
    global db
    db = shared_db
    for name, handler in {
        "admin": admin_panel, "ban": ban_user,
        "unban": unban_user, "broadcast": broadcast_command,
    }.items():
        app_instance.on_message(filters.command(name) & filters.private)(handler)
