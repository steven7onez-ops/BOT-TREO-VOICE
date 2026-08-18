import os
import unittest

os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("DASHBOARD_KEY", "test-dashboard")
os.environ.setdefault("GUILD_ID", "0")
os.environ.setdefault("VOICE_CHANNEL_ID", "0")
os.environ.setdefault("OWNER_ID", "0")

import bot


class YtdlFallbackTest(unittest.TestCase):
    def test_googlevideo_url_requires_local_download(self):
        url = "https://rr4---sn-ojn4v5-55.googlevideo.com/videoplayback?expire=123&sig=abc"
        self.assertTrue(bot.YTDLSource.should_use_local_download(url))

    def test_regular_http_url_is_not_forced_to_download(self):
        url = "https://example.com/audio.mp3"
        self.assertFalse(bot.YTDLSource.should_use_local_download(url))


if __name__ == "__main__":
    unittest.main()
