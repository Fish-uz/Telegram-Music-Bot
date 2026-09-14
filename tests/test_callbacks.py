import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pyrogram.errors import QueryIdInvalid

from handlers import callbacks


class CallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_expired_answer_does_not_cancel_download(self):
        original = (callbacks.db, callbacks.user_results, callbacks.process_download)
        download = AsyncMock()
        callbacks.db = SimpleNamespace(is_user_banned=lambda _user_id: False)
        callbacks.user_results = {
            7: {
                "results": [{"id": "video", "title": "Canción"}],
                "username": "tester",
            }
        }
        callbacks.process_download = download
        query = SimpleNamespace(
            from_user=SimpleNamespace(id=7),
            data="dl_video",
            message=SimpleNamespace(),
            answer=AsyncMock(side_effect=QueryIdInvalid()),
        )
        try:
            await callbacks.handle_callbacks(SimpleNamespace(), query)
            await asyncio.sleep(0)
            download.assert_awaited_once()
        finally:
            callbacks.db, callbacks.user_results, callbacks.process_download = original
