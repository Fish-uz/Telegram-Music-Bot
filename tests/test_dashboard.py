import tempfile
from pathlib import Path

from aiohttp.test_utils import AioHTTPTestCase

from core.config import Config
from dashboard import DashboardServer
from database.manager import DatabaseManager


class DashboardTests(AioHTTPTestCase):
    async def get_application(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(str(Path(self.temp.name) / "dashboard.db"))
        self.db.add_to_cache("video", "file", "Canción")
        self.db.register_download(1, "tester", "video", "Canción")
        self.original_token = Config.DASHBOARD_TOKEN
        Config.DASHBOARD_TOKEN = ""
        return DashboardServer(
            self.db, {"bot_online": True, "active_downloads": 0,
                      "queue_depth": 0, "yt_dlp_version": "test"}
        ).create_app()

    async def asyncTearDown(self):
        await super().asyncTearDown()
        Config.DASHBOARD_TOKEN = self.original_token
        self.temp.cleanup()

    async def test_frontend_and_all_read_endpoints(self):
        response = await self.client.get("/")
        self.assertEqual(response.status, 200)
        self.assertIn("AllMusic", await response.text())
        for endpoint in ("/api/health", "/api/stats", "/api/users", "/api/songs",
                         "/api/history", "/api/system", "/api/users/1"):
            response = await self.client.get(endpoint)
            self.assertEqual(response.status, 200, endpoint)

    async def test_ban_action(self):
        response = await self.client.post("/api/users/1/ban", json={"banned": True})
        self.assertEqual(response.status, 200)
        self.assertTrue(self.db.is_user_banned(1))
