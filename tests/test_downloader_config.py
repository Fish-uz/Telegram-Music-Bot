import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.downloader import MusicDownloader


def test_common_options_include_browser_headers_and_retries():
    downloader = MusicDownloader("downloads", "cookies.txt")
    opts = downloader._get_common_opts("yt")

    assert "http_headers" in opts
    assert opts["http_headers"]["User-Agent"].startswith("Mozilla/")
    assert opts["extractor_args"]["youtube"]["player_client"]
    assert opts["retries"] == 3
    assert opts["retry_sleep_functions"]["http"] == 2
