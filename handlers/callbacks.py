"""Acciones de los botones inline."""

import asyncio
import logging

from pyrogram.errors import RPCError

logger = logging.getLogger("allmusic.callbacks")
db = user_results = edit_search_results = process_download = None


async def _safe_answer(callback_query, text=None, show_alert=False):
    """El aviso del botón es auxiliar y nunca debe cancelar su acción principal."""
    try:
        await callback_query.answer(text, show_alert=show_alert)
    except RPCError as error:
        logger.warning("No se pudo confirmar callback expirado: %s", error)


async def handle_callbacks(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data or ""
    try:
        if db.is_user_banned(user_id):
            return await _safe_answer(callback_query, "Tu acceso está bloqueado.", show_alert=True)
        if data == "del_audio":
            return await callback_query.message.delete()
        if user_id not in user_results:
            return await _safe_answer(
                callback_query, "La búsqueda expiró. Escribe nuevamente.", show_alert=True
            )
        info = user_results[user_id]
        if data.startswith("pg_"):
            page = int(data.removeprefix("pg_"))
            await edit_search_results(callback_query.message, info["query"], info["results"], page, user_id)
            await _safe_answer(callback_query)
        elif data == "close_search":
            user_results.pop(user_id, None)
            await callback_query.message.delete()
        elif data.startswith("dl_"):
            await _safe_answer(callback_query, "Preparando descarga…")
            video_id = data.removeprefix("dl_")
            selected_title = next(
                (song.get("title") for song in info["results"] if song.get("id") == video_id),
                video_id,
            )
            asyncio.create_task(process_download(
                client, callback_query.message, video_id, user_id,
                selected_title=selected_title, username=info.get("username"),
                flow_started_at=info.get("flow_started_at"),
                results_ready_at=info.get("results_ready_at"),
                search_elapsed=info.get("search_elapsed"),
            ))
        elif data == "toggle_filter":
            field = "uploader" if info.get("filter") == "title" else "title"
            info["filter"] = field
            info["results"].sort(key=lambda item: str(item.get(field, "")).casefold())
            await edit_search_results(callback_query.message, info["query"], info["results"], 1, user_id)
            await _safe_answer(callback_query, f"Ordenado por {field}")
    except (RPCError, ValueError):
        logger.exception("Error procesando callback %s", data)
        await _safe_answer(callback_query, "No se pudo completar la acción.", show_alert=True)


def init_callbacks_handlers(app_instance, shared_db, shared_results, fn_edit, fn_download):
    global db, user_results, edit_search_results, process_download
    db, user_results = shared_db, shared_results
    edit_search_results, process_download = fn_edit, fn_download
    app_instance.on_callback_query()(handle_callbacks)
