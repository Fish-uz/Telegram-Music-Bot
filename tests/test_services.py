import unittest

from services.link_resolver import MusicLinkResolver
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
        self.assertFalse(supervisor.is_recoverable(RuntimeError("Video privado")))
