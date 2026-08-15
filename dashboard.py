"""Servidor HTTP y API administrativa de AllMusic."""

from __future__ import annotations

import hmac
import ipaddress
import platform
from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web

from core.config import Config
from core.logger import audit_logger


class DashboardServer:
    def __init__(self, database, runtime_state: dict):
        self.db = database
        self.state = runtime_state
        self.frontend = Path(__file__).parent / "frontend"

    @web.middleware
    async def auth_middleware(self, request, handler):
        if not request.path.startswith("/api/") or request.path == "/api/health":
            return await handler(request)
        if not Config.DASHBOARD_TOKEN:
            try:
                private_client = request.remote is None or ipaddress.ip_address(request.remote).is_private
            except ValueError:
                private_client = False
            if private_client:
                return await handler(request)
            raise web.HTTPServiceUnavailable(
                text="DASHBOARD_TOKEN es obligatorio para acceso remoto al dashboard."
            )
        supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not hmac.compare_digest(supplied, Config.DASHBOARD_TOKEN):
            raise web.HTTPUnauthorized(text="Token de administración inválido.")
        return await handler(request)

    def create_app(self) -> web.Application:
        app = web.Application(middlewares=[self.auth_middleware])
        app.router.add_get("/", self.index)
        app.router.add_get("/api/health", self.health)
        app.router.add_get("/api/stats", self.stats)
        app.router.add_get("/api/users", self.users)
        app.router.add_get("/api/users/{user_id}", self.user_detail)
        app.router.add_post("/api/users/{user_id}/ban", self.ban_user)
        app.router.add_get("/api/songs", self.songs)
        app.router.add_get("/api/history", self.history)
        app.router.add_get("/api/system", self.system)
        app.router.add_static("/assets", self.frontend, show_index=False)
        return app

    async def index(self, request):
        return web.FileResponse(self.frontend / "index.html")

    async def health(self, request):
        return web.json_response({"status": "ok", "bot": bool(self.state.get("bot_online"))})

    async def stats(self, request):
        stats = self.db.get_dashboard_stats()
        downloads = stats["total_downloads"]
        stats["cache_rate"] = round(stats["cache_hits"] / downloads * 100, 1) if downloads else 0
        return web.json_response({"summary": stats, "top": self.db.get_top_songs(10)})

    async def users(self, request):
        return web.json_response(self.db.list_users())

    async def user_detail(self, request):
        user_id = int(request.match_info["user_id"])
        profile = self.db.get_user_profile(user_id)
        if not profile:
            raise web.HTTPNotFound(text="Usuario no encontrado")
        return web.json_response({"info": profile, "history": self.db.get_user_history(user_id, 100)})

    async def ban_user(self, request):
        user_id = int(request.match_info["user_id"])
        payload = await request.json()
        banned = payload.get("banned")
        if not isinstance(banned, bool):
            raise web.HTTPBadRequest(text="El campo 'banned' debe ser booleano.")
        self.db.set_user_ban(user_id, banned)
        audit_logger.info("DASHBOARD_%s user_id=%s", "BAN" if banned else "UNBAN", user_id)
        return web.json_response({"ok": True, "user_id": user_id, "banned": banned})

    async def songs(self, request):
        return web.json_response(self.db.list_songs())

    async def history(self, request):
        return web.json_response(self.db.list_recent_history())

    async def system(self, request):
        database_size = self.db.db_path.stat().st_size if self.db.db_path.exists() else 0
        return web.json_response({
            "brand": "AllMusic", "bot_online": bool(self.state.get("bot_online")),
            "active_downloads": self.state.get("active_downloads", 0),
            "queue_depth": self.state.get("queue_depth", 0),
            "platform": f"{platform.system()} {platform.release()}",
            "yt_dlp_version": self.state.get("yt_dlp_version", "unknown"),
            "python_version": platform.python_version(),
            "database_size_bytes": database_size,
            "process_id": str(self.state.get("process_id", "—")),
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
