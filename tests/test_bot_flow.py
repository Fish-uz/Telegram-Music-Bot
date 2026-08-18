import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import bot
from core.config import Config
from database.manager import DatabaseManager
from handlers import users as user_handlers


class FakeStatus:
    def __init__(self, text=""):
        self.text = text

    async def edit_text(self, text):
        if text == self.text:
            raise AssertionError("No se debe editar un estado con contenido idéntico")
        self.text = text

    async def delete(self): self.deleted = True


class FakeClient:
    def __init__(self):
        self.uploads = []
        self.messages = []

    async def send_message(self, chat_id, text):
        self.messages.append(text)
        return FakeStatus(text)

    async def send_audio(self, chat_id, audio, **kwargs):
        self.uploads.append(audio)
        return SimpleNamespace(audio=SimpleNamespace(file_id="new-telegram-file"))


class FakeMessage:
    id = 1
    chat = SimpleNamespace(id=123)


class FakeDownloader:
    def __init__(self, path): self.path = path
    async def download(self, url, query, progress=None):
        Path(self.path).write_bytes(b"fake mp3")
        if progress: progress(100, "convert")
        return self.path, "Pista nueva"
    def cleanup(self, video_id): pass


class BotFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        bot.db = DatabaseManager(str(Path(self.temp.name) / "flow.db"))
        bot.user_results.clear()
        bot.download_locks.clear()
        bot.runtime_state.update(active_downloads=0, queue_depth=0)

    async def asyncTearDown(self):
        self.temp.cleanup()

    async def test_cache_hit_sends_telegram_file_without_downloading(self):
        bot.db.add_to_cache("cached", "existing-file", "Pista cacheada")
        client = FakeClient()
        success = await bot.process_download(client, FakeMessage(), "cached", 7)
        self.assertTrue(success)
        self.assertEqual(client.uploads, ["existing-file"])
        self.assertFalse(any("caché" in text.casefold() for text in client.messages))
        self.assertEqual(bot.db.get_dashboard_stats()["cache_hits"], 1)

    async def test_new_download_is_uploaded_and_cached(self):
        path = str(Path(self.temp.name) / "track.mp3")
        original = bot.engine
        bot.engine = FakeDownloader(path)
        try:
            client = FakeClient()
            success = await bot.process_download(client, FakeMessage(), "new-video", 7)
            self.assertTrue(success)
            self.assertEqual(bot.db.get_cached_file("new-video")[0], "new-telegram-file")
            self.assertFalse(os.path.exists(path))
        finally:
            bot.engine = original

    async def test_search_navigation_reaches_page_twenty(self):
        results = [{"id": str(index), "title": f"Pista {index}"} for index in range(100)]
        keyboard = bot.create_search_keyboard(results, 20, 7).inline_keyboard
        labels = [button.text for row in keyboard for button in row]

        self.assertEqual(Config.SEARCH_RESULTS_LIMIT, 100)
        self.assertEqual(len(keyboard) - 2, 5)
        self.assertIn("⬅ Anterior", labels)
        self.assertNotIn("Siguiente ➡", labels)

    async def test_log_values_cannot_insert_extra_lines(self):
        self.assertEqual(bot._log_value("Canción\n  oficial\tHD"), "Canción oficial HD")
        self.assertEqual(len(bot._log_value("x" * 200)), 120)

    async def test_outgoing_messages_never_start_searches(self):
        message = SimpleNamespace(outgoing=True, from_user=SimpleNamespace(id=8148530554))
        self.assertIsNone(await user_handlers.handle_message(None, message))

    async def test_messages_from_bots_never_start_searches(self):
        message = SimpleNamespace(
            outgoing=False, from_user=SimpleNamespace(id=8148530554, is_bot=True)
        )
        self.assertIsNone(await user_handlers.handle_message(None, message))
