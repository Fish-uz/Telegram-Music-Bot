import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from services.downloader import MusicDownloader
from services.link_resolver import MusicLinkResolver
from services.searcher import MusicSearcher
from services.update_supervisor import YtDlpUpdateSupervisor


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_plain_query_is_preserved(self):
        result = await MusicLinkResolver().resolve("  artista   canción  ")
        self.assertEqual(result.source, "Texto")
        self.assertEqual(result.query, "artista   canción")

    async def test_youtube_link_is_normalized(self):
        result = await MusicLinkResolver().resolve("https://youtu.be/QrqjLoPbnyY?t=2")
        self.assertEqual(result.source, "YouTube")
        self.assertEqual(result.query, "https://www.youtube.com/watch?v=QrqjLoPbnyY")

    def test_supported_links_are_detected(self):
        resolver = MusicLinkResolver()
        self.assertTrue(resolver.SPOTIFY_RE.search("https://open.spotify.com/track/abc123"))
        self.assertTrue(resolver.DEEZER_RE.search("https://www.deezer.com/es/track/123"))

    def test_update_supervisor_classifies_only_technical_failures(self):
        supervisor = YtDlpUpdateSupervisor()
        self.assertTrue(supervisor.is_recoverable(RuntimeError("HTTP Error 403: Forbidden")))
        self.assertTrue(supervisor.is_recoverable(RuntimeError("The page needs to be reloaded")))
        self.assertFalse(supervisor.is_recoverable(RuntimeError("Video privado")))

    def test_authenticated_youtube_uses_supported_player_clients(self):
        with tempfile.TemporaryDirectory() as temporary:
            cookies = Path(temporary) / "cookies.txt"
            cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
            expected = ["default", "web_embedded"]

            search_opts = MusicSearcher(str(cookies))._options()
            with patch("services.downloader.shutil.which", return_value="ffmpeg"):
                download_opts = MusicDownloader(temporary, str(cookies))._get_common_opts()

            self.assertEqual(
                search_opts["extractor_args"]["youtube"]["player_client"], expected
            )
            self.assertEqual(
                download_opts["extractor_args"]["youtube"]["player_client"], expected
            )
