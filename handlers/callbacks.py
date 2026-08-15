"""Acciones de los botones inline."""

import asyncio
import logging

from pyrogram.errors import RPCError

logger = logging.getLogger(__name__)
db = user_results = edit_search_results = process_download = None


async def handle_callbacks(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data or ""
    try:
        if db.is_user_banned(user_id):
            return await callback_query.answer("Tu acceso está bloqueado.", show_alert=True)
        if data == "del_audio":
            return await callback_query.message.delete()
        if user_id not in user_results:
            return await callback_query.answer("La búsqueda expiró. Escribe nuevamente.", show_alert=True)
        info = user_results[user_id]
        if data.startswith("pg_"):
            page = int(data.removeprefix("pg_"))
            await edit_search_results(callback_query.message, info["query"], info["results"], page, user_id)
            await callback_query.answer()
        elif data == "close_search":
            user_results.pop(user_id, None)
            await callback_query.message.delete()
        elif data.startswith("dl_"):
            await callback_query.answer("Preparando descarga…")
            asyncio.create_task(process_download(
                client, callback_query.message, data.removeprefix("dl_"), user_id
            ))
        elif data == "toggle_filter":
            field = "uploader" if info.get("filter") == "title" else "title"
            info["filter"] = field
            info["results"].sort(key=lambda item: str(item.get(field, "")).casefold())
            await edit_search_results(callback_query.message, info["query"], info["results"], 1, user_id)
            await callback_query.answer(f"Ordenado por {field}")
    except (RPCError, ValueError):
        logger.exception("Error procesando callback %s", data)
        try: await callback_query.answer("No se pudo completar la acción.", show_alert=True)
        except RPCError: pass


def init_callbacks_handlers(app_instance, shared_db, shared_results, fn_edit, fn_download):
    global db, user_results, edit_search_results, process_download
    db, user_results = shared_db, shared_results
    edit_search_results, process_download = fn_edit, fn_download
    app_instance.on_callback_query()(handle_callbacks)
