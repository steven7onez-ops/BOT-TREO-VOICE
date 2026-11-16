import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("DASHBOARD_KEY", "test-dashboard")
os.environ.setdefault("GUILD_ID", "0")
os.environ.setdefault("VOICE_CHANNEL_ID", "0")
os.environ.setdefault("OWNER_ID", "0")

import bot


class YtdlFallbackTest(unittest.TestCase):
    def test_help_shows_all_categories_by_default(self):
        embed = bot.build_help_embed()

        self.assertEqual(len(embed.fields), len(bot.HELP_CATEGORIES))
        self.assertEqual(
            [field.name for field in embed.fields],
            [name for name, _ in bot.HELP_CATEGORIES.values()],
        )

    def test_music_source_names(self):
        self.assertEqual(bot.YTDLSource.source_name("https://open.spotify.com/track/abc"), "Spotify")
        self.assertEqual(bot.YTDLSource.source_name("https://spotify.link/abc"), "Spotify")
        self.assertEqual(bot.YTDLSource.source_name("https://soundcloud.com/artist/track"), "SoundCloud")
        self.assertEqual(bot.YTDLSource.source_name("never gonna give you up"), "YouTube")

    def test_spotify_query_uses_track_and_artist(self):
        self.assertEqual(
            bot.YTDLSource._spotify_search_query({"track": "Track", "artist": "Artist"}),
            "ytsearch1:Artist - Track",
        )

    def test_spotify_oembed_query_uses_metadata(self):
        self.assertEqual(
            bot.YTDLSource._spotify_search_query({"title": "Track", "author_name": "Artist"}),
            "ytsearch1:Artist - Track",
        )

    def test_googlevideo_url_requires_local_download(self):
        url = "https://rr4---sn-ojn4v5-55.googlevideo.com/videoplayback?expire=123&sig=abc"
        self.assertTrue(bot.YTDLSource.should_use_local_download(url))

    def test_regular_http_url_is_not_forced_to_download(self):
        url = "https://example.com/audio.mp3"
        self.assertFalse(bot.YTDLSource.should_use_local_download(url))

    def test_rate_limit_detection_matches_ytdlp_message(self):
        self.assertTrue(
            bot.YTDLSource.is_rate_limited_error(
                "This content isn't available, try again later"
            )
        )
        self.assertTrue(bot.YTDLSource.is_rate_limited_error("HTTP Error 429: Too Many Requests"))
        self.assertFalse(bot.YTDLSource.is_rate_limited_error("Sign in to confirm you're not a bot"))


class MusicVoiceJoinTest(unittest.IsolatedAsyncioTestCase):
    async def test_music_join_unmutes_existing_voice_connection(self):
        voice_client = SimpleNamespace(channel=None, move_to=AsyncMock())
        guild = SimpleNamespace(
            voice_client=voice_client,
            change_voice_state=AsyncMock(),
        )
        channel = SimpleNamespace(guild=guild, name="music")
        voice_client.channel = channel

        joined = await bot._join_channel(channel, self_mute=False)

        self.assertTrue(joined)
        guild.change_voice_state.assert_awaited_once_with(
            channel=channel,
            self_deaf=True,
            self_mute=False,
        )


if __name__ == "__main__":
    unittest.main()
