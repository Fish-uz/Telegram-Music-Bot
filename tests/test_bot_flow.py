import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import bot
from database.manager import DatabaseManager


class FakeStatus:
    async def edit_text(self, text): self.text = text
    async def delete(self): self.deleted = True


class FakeClient:
    def __init__(self):
        self.uploads = []

    async def send_message(self, chat_id, text):
        return FakeStatus()

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
