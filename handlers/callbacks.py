import asyncio
from pyrogram import Client

db = None
user_results = None
edit_search_results = None
process_download = None

async def handle_callbacks(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if db.is_user_banned(user_id):
        return await callback_query.answer("Estás baneado.", show_alert=True)

    if user_id not in user_results and data != "del_audio":
        await callback_query.answer("Sesión expirada, busca de nuevo.")
        return

    if data.startswith("pg_"):
        page = int(data.split("_")[1])
        info = user_results[user_id]
        await edit_search_results(callback_query.message, info["query"], info["results"], page, user_id)
    elif data == "close_search":
        await callback_query.message.delete()
        user_results.pop(user_id, None)
    elif data.startswith("dl_"):
        video_id = data.split("_", 1)[1]
        await callback_query.answer("Preparando descarga...")
        asyncio.create_task(process_download(client, callback_query.message, video_id, user_id))
    elif data == "del_audio":
        await callback_query.message.delete()
    elif data == "toggle_filter":
        current_filter = user_results[user_id].get("filter", "title")
        new_filter = "uploader" if current_filter == "title" else "title"
        user_results[user_id]["filter"] = new_filter
        user_results[user_id]["results"].sort(key=lambda x: str(x.get(new_filter, "")).lower())
        await edit_search_results(callback_query.message, user_results[user_id]["query"], user_results[user_id]["results"], 1, user_id)
    elif data == "toggle_lossless":
        val = not user_results[user_id].get("lossless", False)
        user_results[user_id]["lossless"] = val
        await edit_search_results(callback_query.message, user_results[user_id]["query"], user_results[user_id]["results"], 1, user_id)

def init_callbacks_handlers(app_instance, shared_db, shared_results, fn_edit, fn_dl):
    global db, user_results, edit_search_results, process_download
    db = shared_db
    user_results = shared_results
    edit_search_results = fn_edit
    process_download = fn_dl
    app_instance.on_callback_query()(handle_callbacks)