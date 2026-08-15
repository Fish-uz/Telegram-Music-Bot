import tempfile
import unittest
from pathlib import Path

from database.manager import DatabaseManager


class DatabaseManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(str(Path(self.temp.name) / "test.db"))

    def tearDown(self):
        self.temp.cleanup()

    def test_cache_history_and_statistics(self):
        self.db.add_to_cache("video", "telegram-file", "Canción")
        self.assertEqual(self.db.get_cached_file("video"), ("telegram-file", "Canción"))
        self.db.register_download(7, "tester", "video", "Canción", cache_hit=True)
        stats = self.db.get_dashboard_stats()
        self.assertEqual(stats["total_users"], 1)
        self.assertEqual(stats["total_downloads"], 1)
        self.assertEqual(stats["cache_hits"], 1)
        self.assertEqual(self.db.get_top_songs(1)[0], ("Canción", 1))

    def test_invalid_cache_can_be_removed(self):
        self.db.add_to_cache("video", "old-file", "Canción")
        self.db.remove_cached_file("video")
        self.assertIsNone(self.db.get_cached_file("video"))

    def test_ban_creates_unknown_user(self):
        self.assertTrue(self.db.set_user_ban(99, True))
        self.assertTrue(self.db.is_user_banned(99))
