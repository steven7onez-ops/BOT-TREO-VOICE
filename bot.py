import discord
from discord import app_commands
from discord.ext import commands
import asyncio, os, logging, json, re, tempfile, shutil, subprocess
from urllib.parse import urlparse
from aiohttp import web
import collections, random
from datetime import datetime, timezone
from pathlib import Path

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("Bot")

# ── Config ────────────────────────────────────────────────────────────────────
TOKEN          = os.environ["DISCORD_TOKEN"]
TARGET_GUILD   = int(os.environ.get("GUILD_ID", "0"))
TARGET_CHANNEL = int(os.environ.get("VOICE_CHANNEL_ID", "0"))
DASHBOARD_PORT = int(os.environ.get("PORT", "8080"))
DASHBOARD_KEY  = os.environ.get("DASHBOARD_KEY", "changeme")
OWNER_ID       = int(os.environ.get("OWNER_ID", "852834067044630558"))

# TikBot-like extras
TIKBOT_STATUS_TEXT = os.environ.get("TIKBOT_STATUS_TEXT", "🎙️ voice channel")
TIKBOT_VERSION = os.environ.get("TIKBOT_VERSION", "")
# space-separated list of domains to auto-detect in messages
TIKBOT_AUTO_DOMAINS = os.environ.get("TIKBOT_AUTO_DOMAINS", "youtube tiktok instagram reddit redd.it").split()
# domains for which the bot should be silent (don't post detection messages)
TIKBOT_SILENT_DOMAINS = os.environ.get("TIKBOT_SILENT_DOMAINS", "").split()
TIKBOT_MAX_UPLOAD_MB = int(os.environ.get("TIKBOT_MAX_UPLOAD_MB", "50"))

PROFILE_DB_FILE = Path("/tmp/profiles.json")
VC_STATE_FILE   = Path("/tmp/vc_state.json") # kênh nào đang có panel mở + message id

# ── JSON DB helpers ───────────────────────────────────────────────────────────
def load_json(path: Path) -> dict:
    if path.exists():
        try: return json.loads(path.read_text())
        except: pass
    return {}

def save_json(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def load_profiles():   return load_json(PROFILE_DB_FILE)
def save_profiles(db): save_json(PROFILE_DB_FILE, db)
def load_vc_state():   return load_json(VC_STATE_FILE)
def save_vc_state(d):  save_json(VC_STATE_FILE, d)

# ── Intents ───────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.guilds          = True
intents.voice_states    = True
intents.members         = True
intents.message_content = True

# ══════════════════════════════════════════════════════════════════════════════
#  BOT
# ══════════════════════════════════════════════════════════════════════════════
class VoiceBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="+", intents=intents, help_command=None)
        self.permanent_channel_id: int = TARGET_CHANNEL
        self.temp_channel_id: int      = 0
        self.auto_rejoin: bool         = True
        self.follow_owner: bool        = True
        self.start_time                = datetime.now(timezone.utc)

    async def setup_hook(self):
        guild = discord.Object(id=TARGET_GUILD)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        log.info("✅ Slash commands đã sync")

    async def on_ready(self):
        log.info(f"✅ Đã đăng nhập: {self.user} (ID: {self.user.id})")
        log.info(f"📡 Đang phục vụ {len(self.guilds)} server")
        # Presence: include optional version/status text (TikBot-style)
        status_text = TIKBOT_STATUS_TEXT
        if TIKBOT_VERSION:
            status_text = f"{status_text} | v{TIKBOT_VERSION}"
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=status_text))
        if self.permanent_channel_id:
            await self._join_by_id(self.permanent_channel_id, label="kênh vĩnh viễn")

    # ── Treo voice logic (giữ nguyên từ bản cũ) ──────────────────────────────
    async def on_voice_state_update(self, member, before, after):
        # Bot bị disconnect
        if member == self.user:
            if before.channel and not after.channel and self.auto_rejoin:
                log.warning("⚠️  Bot bị disconnect, rejoin sau 3 giây...")
                await asyncio.sleep(3)
                rejoined = False
                if self.temp_channel_id:
                    rejoined = await self._join_by_id(self.temp_channel_id, label="kênh tạm thời")
                if not rejoined and self.permanent_channel_id:
                    await self._join_by_id(self.permanent_channel_id, label="kênh vĩnh viễn")
            return

        # Follow chủ vào voice (tính năng treo voice cũ)
        if member.id == OWNER_ID and self.follow_owner:
            if after.channel and after.channel != before.channel:
                ch = after.channel
                log.info(f"👤 Chủ vào #{ch.name} — bot follow theo")
                if ch.id != self.permanent_channel_id:
                    self.temp_channel_id = ch.id
                await self._join_channel(ch)

    def _is_temp_channel(self, channel): return channel.id != self.permanent_channel_id

    async def _join_by_id(self, channel_id: int, label="") -> bool:
        ch = self.get_channel(channel_id)
        if not ch or not isinstance(ch, discord.VoiceChannel):
            log.error(f"❌ Không tìm thấy {label} ID={channel_id}"); return False
        return await self._join_channel(ch)

    async def _join_channel(self, channel: discord.VoiceChannel) -> bool:
        vc = channel.guild.voice_client
        try:
            if vc: await vc.move_to(channel); log.info(f"➡️  Chuyển sang: #{channel.name}")
            else: await channel.connect(self_deaf=True, self_mute=True); log.info(f"🎙️  Join: #{channel.name}")
            return True
        except Exception as e: log.error(f"❌ Lỗi join: {e}"); return False

    async def leave_all_voice(self):
        for vc in self.voice_clients:
            await vc.disconnect(force=True)
        self.temp_channel_id = 0

    def get_status(self):
        voice_info = [{"guild": vc.guild.name, "channel": vc.channel.name,
                       "members": len([m for m in vc.channel.members if not m.bot])}
                      for vc in self.voice_clients]
        uptime = datetime.now(timezone.utc) - self.start_time
        h, rem = divmod(int(uptime.total_seconds()), 3600); m, s = divmod(rem, 60)
        return {"online": self.is_ready(), "bot_name": str(self.user) if self.user else "—",
                "uptime": f"{h}h {m}m {s}s", "auto_rejoin": self.auto_rejoin,
                "follow_owner": self.follow_owner, "voice": voice_info}


bot = VoiceBot()

# ----- Music playback support -------------------------------------------------
try:
    import yt_dlp
except Exception:
    yt_dlp = None


import base64

# Build yt-dlp options and support cookie injection via env vars
YTDL_OPTS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'default_search': 'ytsearch',
}

# Cookie support: either provide a file path in YTDL_COOKIE_FILE, raw cookies in
# YTDL_COOKIES, or base64-encoded cookies in YTDL_COOKIES_BASE64. If provided,
# we write cookies to a temp file and pass it to yt-dlp via 'cookiefile'.
COOKIE_FILE = os.environ.get('YTDL_COOKIE_FILE')
cookie_raw = os.environ.get('YTDL_COOKIES')
cookie_b64 = os.environ.get('YTDL_COOKIES_BASE64')
if not COOKIE_FILE and (cookie_raw or cookie_b64):
    try:
        tmp_cf = Path(tempfile.mkdtemp(prefix='ytdl_cookies_')) / 'cookies.txt'
        if cookie_b64:
            data = base64.b64decode(cookie_b64)
            tmp_cf.write_bytes(data)
        else:
            tmp_cf.write_text(cookie_raw)
        COOKIE_FILE = str(tmp_cf)
        log.info('Using yt-dlp cookies from env, written to %s', COOKIE_FILE)
    except Exception as e:
        log.exception('Failed to write yt-dlp cookie file: %s', e)

if COOKIE_FILE:
    YTDL_OPTS['cookiefile'] = COOKIE_FILE


class YTDLSource:
    @classmethod
    async def create_source(cls, search: str):
        if yt_dlp is None:
            raise RuntimeError('yt-dlp is not installed')
        loop = asyncio.get_event_loop()
        def extract():
            with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
                return ydl.extract_info(search, download=False)
        try:
            data = await asyncio.to_thread(extract)
        except Exception as exc:
            s = str(exc)
            if 'Sign in to confirm' in s or 'cookies' in s.lower():
                raise RuntimeError(
                    'YouTube requires cookies to access this video.\n'
                    'Provide cookies via env `YTDL_COOKIE_FILE` (path) or `YTDL_COOKIES_BASE64` (base64-encoded cookies.txt).'
                )
            raise RuntimeError(f'yt-dlp error: {s}')
        if data is None:
            raise RuntimeError('No data from yt-dlp')
        if 'entries' in data:
            # playlist or search result — pick first entry
            entries = [e for e in data['entries'] if e]
            if not entries:
                raise RuntimeError('No entries found')
            info = entries[0]
        else:
            info = data
        return {
            'webpage_url': info.get('webpage_url'),
            'title': info.get('title'),
            'url': info.get('url') or info.get('webpage_url'),
            'duration': info.get('duration'),
        }


class MusicPlayer:
    def __init__(self, guild: discord.Guild):
        self.guild = guild
        self.bot = bot
        self.queue = collections.deque()
        self.next_event = asyncio.Event()
        self.play_task = self.bot.loop.create_task(self.player_loop())
        self.current = None
        self.loop_one = False
        self.loop_all = False

    async def player_loop(self):
        while True:
            if not self.queue:
                # wait until a new item is enqueued
                await asyncio.sleep(0.5)
                continue
            src = self.queue.popleft()
            self.current = src
            vc = self.guild.voice_client
            if not vc:
                # try to reconnect to the owner's voice channel if possible
                self.current = None
                continue
            before_opts = '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
            options = '-vn -ac 2 -ar 48000 -b:a 192k'
            audio = discord.FFmpegPCMAudio(src['url'], before_options=before_opts, options=options)
            play_done = asyncio.Event()
            def _after(err):
                if err:
                    log.error('Player error: %s', err)
                self.bot.loop.call_soon_threadsafe(play_done.set)
            try:
                vc.play(audio, after=_after)
            except Exception as e:
                log.exception('Failed to play: %s', e)
                self.current = None
                continue
            await play_done.wait()
            # handle looping
            if self.loop_one:
                # replay same song immediately
                self.queue.appendleft(src)
            elif self.loop_all:
                self.queue.append(src)
            self.current = None


players: dict[int, MusicPlayer] = {}

def get_player(guild: discord.Guild) -> MusicPlayer:
    pl = players.get(guild.id)
    if not pl:
        pl = MusicPlayer(guild)
        players[guild.id] = pl
    return pl



# ══════════════════════════════════════════════════════════════════════════════
#  VOICE MANAGER — Quản lý MỌI kênh voice, không cần bot tự vào voice
# ══════════════════════════════════════════════════════════════════════════════
# Bot KHÔNG tự join kênh voice để quản lý. Panel điều khiển được gọi bằng lệnh
# `+voice_control` trong khung chat của bất kỳ kênh voice nào — miễn người gõ
# lệnh đang ở trong kênh voice đó. Ai cũng dùng được mọi nút/dropdown trong
# panel, không giới hạn theo chủ kênh hay admin. Nhiều kênh có thể có panel
# hoạt động song song vì bot chỉ gọi Discord API để sửa kênh, không cần "ở"
# trong kênh nào cả.
#
# Trạng thái per-channel (VC_STATE_FILE):
#   { channel_id: { "panel_message_id": int|None } }

PANEL_TITLE = "⚙️ Bảng điều khiển kênh thoại"
PANEL_DESC = (
    "Điều khiển kênh bằng menu thả xuống bên dưới.\n"
    "**Mọi thành viên** trong kênh đều dùng được — không giới hạn chủ phòng."
)

def get_voice_state_flags(channel: discord.VoiceChannel) -> dict:
    """Suy ra trạng thái khoá/ẩn trực tiếp từ overwrites hiện tại của kênh,
    không cần lưu riêng — luôn đồng bộ với thực tế của kênh."""
    everyone = channel.guild.default_role
    ow = channel.overwrites_for(everyone)
    locked = ow.connect is False
    hidden = ow.view_channel is False
    return {"locked": locked, "hidden": hidden}


def build_panel_embed(channel: discord.VoiceChannel) -> discord.Embed:
    flags = get_voice_state_flags(channel)
    embed = discord.Embed(title=PANEL_TITLE, description=PANEL_DESC, color=0x5865F2)
    embed.add_field(name="🔊 Kênh", value=f"**{channel.name}**", inline=True)
    embed.add_field(name="👥 Giới hạn", value=str(channel.user_limit) if channel.user_limit else "Không giới hạn", inline=True)
    embed.add_field(name="🎚️ Bitrate", value=f"{channel.bitrate // 1000} kbps", inline=True)
    status = []
    status.append("🔒 Đã khoá" if flags["locked"] else "🔓 Đang mở")
    status.append("🙈 Đã ẩn" if flags["hidden"] else "👁️ Hiển thị")
    embed.add_field(name="📋 Trạng thái", value=" · ".join(status), inline=False)
    members = [m for m in channel.members if not m.bot]
    if members:
        embed.add_field(name="🎙️ Đang trong kênh", value=", ".join(m.mention for m in members[:10]), inline=False)
    embed.set_footer(text=f"Kênh ID: {channel.id} · Ai cũng dùng được panel này")
    return embed


# ── Dropdown "Đổi cài đặt kênh" ────────────────────────────────────────────────
class ChannelSettingsSelect(discord.ui.Select):
    def __init__(self, channel_id: int):
        self.channel_id = channel_id
        options = [
            discord.SelectOption(label="Tên", description="Đổi tên kênh", emoji="✏️", value="rename"),
            discord.SelectOption(label="Giới hạn", description="Đổi giới hạn số người", emoji="👥", value="limit"),
            discord.SelectOption(label="Tốc độ bit", description="Đổi bitrate kênh", emoji="🎚️", value="bitrate"),
        ]
        super().__init__(placeholder="Đổi cài đặt kênh", options=options, custom_id=f"vc_settings:{channel_id}")

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        # Người dùng phải đang ở trong đúng kênh voice để thao tác
        if not interaction.user.voice or interaction.user.voice.channel != channel:
            return await interaction.response.send_message("❌ Bạn cần đang ở trong kênh voice này để dùng panel!", ephemeral=True)

        choice = self.values[0]
        if choice == "rename":
            return await interaction.response.send_modal(RenameModal(channel.id))
        if choice == "limit":
            return await interaction.response.send_modal(LimitModal(channel.id))
        if choice == "bitrate":
            return await interaction.response.send_modal(BitrateModal(channel.id))


# ── Dropdown "Đổi quyền kênh" ──────────────────────────────────────────────────
class ChannelPermissionsSelect(discord.ui.Select):
    def __init__(self, channel_id: int):
        self.channel_id = channel_id
        options = [
            discord.SelectOption(label="Khoá", description="Khoá kênh (không ai vào được)", emoji="🔒", value="lock"),
            discord.SelectOption(label="Mở khoá", description="Mở khoá kênh", emoji="🔓", value="unlock"),
            discord.SelectOption(label="Ẩn", description="Ẩn kênh khỏi danh sách", emoji="🙈", value="hide"),
            discord.SelectOption(label="Hiện", description="Hiển thị lại kênh", emoji="👁️", value="show"),
            discord.SelectOption(label="Kick", description="Đuổi 1 thành viên khỏi kênh", emoji="🚫", value="kick"),
        ]
        super().__init__(placeholder="Đổi quyền kênh", options=options, custom_id=f"vc_perms:{channel_id}")

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        if not interaction.user.voice or interaction.user.voice.channel != channel:
            return await interaction.response.send_message("❌ Bạn cần đang ở trong kênh voice này để dùng panel!", ephemeral=True)

        choice = self.values[0]
        everyone = channel.guild.default_role
        ow = channel.overwrites_for(everyone)

        if choice == "lock":
            ow.connect = False
            await channel.set_permissions(everyone, overwrite=ow)
            await interaction.response.send_message("🔒 Đã khoá kênh!", ephemeral=True)
            return await voice_manager.refresh_panel(channel)

        if choice == "unlock":
            ow.connect = None
            await channel.set_permissions(everyone, overwrite=ow)
            await interaction.response.send_message("🔓 Đã mở khoá kênh!", ephemeral=True)
            return await voice_manager.refresh_panel(channel)

        if choice == "hide":
            ow.view_channel = False
            await channel.set_permissions(everyone, overwrite=ow)
            await interaction.response.send_message("🙈 Đã ẩn kênh!", ephemeral=True)
            return await voice_manager.refresh_panel(channel)

        if choice == "show":
            ow.view_channel = None
            await channel.set_permissions(everyone, overwrite=ow)
            await interaction.response.send_message("👁️ Đã hiện kênh!", ephemeral=True)
            return await voice_manager.refresh_panel(channel)

        if choice == "kick":
            members = [m for m in channel.members if not m.bot]
            if not members:
                return await interaction.response.send_message("❌ Không có ai trong kênh để kick!", ephemeral=True)
            select = KickSelect(channel.id, members)
            view = discord.ui.View(timeout=60); view.add_item(select)
            return await interaction.response.send_message("🚫 Chọn thành viên để kick khỏi kênh:", view=view, ephemeral=True)


class VoicePanelView(discord.ui.View):
    """View gắn với 1 kênh voice cụ thể — persistent, ai cũng dùng được."""
    def __init__(self, channel_id: int):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.add_item(ChannelSettingsSelect(channel_id))
        self.add_item(ChannelPermissionsSelect(channel_id))


class RenameModal(discord.ui.Modal, title="Đổi tên kênh"):
    new_name = discord.ui.TextInput(label="Tên kênh mới", max_length=100, required=True)
    def __init__(self, channel_id: int):
        super().__init__(); self.channel_id = channel_id
    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel: return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        await channel.edit(name=str(self.new_name)[:100])
        await interaction.response.send_message(f"✏️ Đã đổi tên kênh thành **{self.new_name}**!", ephemeral=True)
        await voice_manager.refresh_panel(channel)


class LimitModal(discord.ui.Modal, title="Đặt giới hạn số người"):
    limit = discord.ui.TextInput(label="Số người tối đa (0 = không giới hạn)", max_length=3, required=True, placeholder="Vd: 5")
    def __init__(self, channel_id: int):
        super().__init__(); self.channel_id = channel_id
    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel: return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        try:
            val = int(str(self.limit))
            if not (0 <= val <= 99): raise ValueError
        except:
            return await interaction.response.send_message("❌ Số không hợp lệ! (0-99)", ephemeral=True)
        await channel.edit(user_limit=val)
        await interaction.response.send_message(f"👥 Đã đặt giới hạn: **{val if val else 'Không giới hạn'}**!", ephemeral=True)
        await voice_manager.refresh_panel(channel)


class BitrateModal(discord.ui.Modal, title="Đặt Bitrate (kbps)"):
    bitrate = discord.ui.TextInput(label="Bitrate (8-96 kbps, tuỳ server boost)", max_length=3, required=True, placeholder="Vd: 64")
    def __init__(self, channel_id: int):
        super().__init__(); self.channel_id = channel_id
    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel: return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        try:
            val = int(str(self.bitrate))
            max_bitrate = channel.guild.bitrate_limit // 1000
            if not (8 <= val <= max_bitrate): raise ValueError
        except:
            return await interaction.response.send_message(f"❌ Bitrate không hợp lệ! (8-{channel.guild.bitrate_limit//1000})", ephemeral=True)
        await channel.edit(bitrate=val * 1000)
        await interaction.response.send_message(f"🎚️ Đã đặt bitrate: **{val}kbps**!", ephemeral=True)
        await voice_manager.refresh_panel(channel)


class KickSelect(discord.ui.UserSelect):
    def __init__(self, channel_id: int, members: list):
        super().__init__(placeholder="Chọn thành viên...", min_values=1, max_values=1)
        self.channel_id = channel_id
    async def callback(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel: return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        target = self.values[0]
        member = channel.guild.get_member(target.id)
        if member and member.voice and member.voice.channel == channel:
            await member.move_to(None)
            await interaction.response.send_message(f"🚫 Đã kick {target.mention} khỏi kênh!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Thành viên không còn trong kênh!", ephemeral=True)


class VoiceManagerImpl:
    """Quản lý panel cho nhiều kênh voice song song, không cần bot vào voice."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def open_panel(self, channel: discord.VoiceChannel):
        """Gửi panel mới vào khung chat của kênh voice, xoá panel cũ nếu có."""
        state_all = load_vc_state()
        key = str(channel.id)
        old_msg_id = state_all.get(key, {}).get("panel_message_id")
        if old_msg_id:
            try:
                old_msg = await channel.fetch_message(old_msg_id)
                await old_msg.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        embed = build_panel_embed(channel)
        view = VoicePanelView(channel.id)
        try:
            msg = await channel.send(embed=embed, view=view)
        except discord.Forbidden:
            log.warning(f"❌ Thiếu quyền gửi tin nhắn vào kênh chat của voice #{channel.name} (ID: {channel.id})")
            return
        state_all[key] = {"panel_message_id": msg.id}
        save_vc_state(state_all)
        log.info(f"📋 Đã mở panel cho #{channel.name}")

    async def repost_panel(self, channel: discord.VoiceChannel):
        """Xoá panel cũ, gửi panel mới xuống dưới cùng — gọi khi có tin nhắn mới."""
        state_all = load_vc_state()
        key = str(channel.id)
        if key not in state_all:
            return  # kênh này chưa từng mở panel, không tự động tạo
        await self.open_panel(channel)

    async def refresh_panel(self, channel: discord.VoiceChannel):
        """Cập nhật nội dung panel hiện có (không xoá/gửi lại) — dùng sau khi đổi cài đặt."""
        state_all = load_vc_state()
        state = state_all.get(str(channel.id))
        if not state or not state.get("panel_message_id"): return
        try:
            msg = await channel.fetch_message(state["panel_message_id"])
            view = VoicePanelView(channel.id)
            await msg.edit(embed=build_panel_embed(channel), view=view)
        except (discord.NotFound, discord.Forbidden):
            pass

    def is_managed_channel(self, channel_id: int) -> bool:
        state_all = load_vc_state()
        return str(channel_id) in state_all


voice_manager = VoiceManagerImpl(bot)


# ── Lệnh mở panel: +voice_control ─────────────────────────────────────────────
@bot.command(name="voice_control", aliases=["vc", "voicecontrol"])
async def voice_control_cmd(ctx: commands.Context):
    if not ctx.author.voice or not ctx.author.voice.channel:
        return await ctx.reply("❌ Bạn cần đang ở trong 1 kênh voice để dùng lệnh này!")
    channel = ctx.author.voice.channel
    await voice_manager.open_panel(channel)
    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.NotFound):
        pass


# ---------------- Music commands ------------------------------------------------
@bot.command(name='play', aliases=['p'])
async def play_cmd(ctx: commands.Context, *, query: str = None):
    if not query:
        return await ctx.reply("❌ Dùng: `+play <link or search>`")
    if not ctx.author.voice or not ctx.author.voice.channel:
        return await ctx.reply("❌ Bạn cần đang ở trong kênh voice để phát nhạc!")
    # ensure connected
    await bot._join_channel(ctx.author.voice.channel)
    try:
        src = await YTDLSource.create_source(query)
    except Exception as e:
        log.exception("yt-dlp extract failed: %s", e)
        return await ctx.reply(f"❌ Lỗi khi tìm/nạp track: {e}")
    player = get_player(ctx.guild)
    # play immediately: insert to left and stop current to switch
    player.queue.appendleft({'title': src['title'], 'url': src['url'], 'webpage_url': src['webpage_url'], 'requester': ctx.author.display_name})
    vc = ctx.guild.voice_client
    if vc and vc.is_playing():
        try:
            vc.stop()
        except Exception:
            pass
    await ctx.send(f"▶️ Đã phát ngay: **{src['title']}**")


@bot.command(name='queue')
async def queue_cmd(ctx: commands.Context, *, query: str = None):
    if not query:
        return await ctx.reply("❌ Dùng: `+queue <link or search>`")
    if not ctx.author.voice or not ctx.author.voice.channel:
        return await ctx.reply("❌ Bạn cần đang ở trong kênh voice để thêm vào queue!")
    await bot._join_channel(ctx.author.voice.channel)
    try:
        src = await YTDLSource.create_source(query)
    except Exception as e:
        log.exception("yt-dlp extract failed: %s", e)
        return await ctx.reply(f"❌ Lỗi khi thêm vào queue: {e}")
    player = get_player(ctx.guild)
    player.queue.append({'title': src['title'], 'url': src['url'], 'webpage_url': src['webpage_url'], 'requester': ctx.author.display_name})
    await ctx.send(f"➕ Đã thêm vào queue: **{src['title']}**")


@bot.command(name='checkqueue')
async def checkqueue_cmd(ctx: commands.Context):
    player = get_player(ctx.guild)
    if not player.queue and not player.current:
        return await ctx.reply("📭 Queue hiện đang trống")
    lines = []
    if player.current:
        lines.append(f"Now playing: **{player.current['title']}**")
    for i, item in enumerate(list(player.queue), start=1):
        lines.append(f"{i}. {item['title']} (by {item.get('requester','-')})")
    msg = "\n".join(lines)
    if len(msg) > 1900:
        msg = msg[:1900] + "..."
    await ctx.reply(msg)


@bot.command(name='pause')
async def pause_cmd(ctx: commands.Context):
    vc = ctx.guild.voice_client
    if not vc or not vc.is_playing():
        return await ctx.reply("❌ Không có nhạc đang phát")
    try:
        vc.pause()
        await ctx.reply("⏸️ Đã tạm dừng")
    except Exception as e:
        await ctx.reply(f"❌ Lỗi khi pause: {e}")


@bot.command(name='stop')
async def stop_cmd(ctx: commands.Context):
    vc = ctx.guild.voice_client
    player = get_player(ctx.guild)
    player.queue.clear()
    try:
        if vc:
            vc.stop()
            await ctx.reply("⏹️ Đã dừng và xoá queue")
        else:
            await ctx.reply("❌ Bot không có kết nối voice")
    except Exception as e:
        await ctx.reply(f"❌ Lỗi khi stop: {e}")


@bot.command(name='shuffle')
async def shuffle_cmd(ctx: commands.Context):
    player = get_player(ctx.guild)
    q = list(player.queue)
    random.shuffle(q)
    player.queue = collections.deque(q)
    await ctx.reply("🔀 Đã xáo trộn queue")


@bot.command(name='repeat')
async def repeat_cmd(ctx: commands.Context, *, mode: str = None):
    player = get_player(ctx.guild)
    if mode and mode.lower() in ('all','all'):
        player.loop_all = not player.loop_all
        await ctx.reply(f"🔁 Loop all: {'ON' if player.loop_all else 'OFF'}")
        return
    player.loop_one = not player.loop_one
    await ctx.reply(f"🔂 Loop single: {'ON' if player.loop_one else 'OFF'}")


@bot.command(name='playqueue')
async def playqueue_cmd(ctx: commands.Context, index: int = None):
    if index is None:
        return await ctx.reply("❌ Dùng: `+playqueue <số thứ tự>`")
    player = get_player(ctx.guild)
    if index < 1 or index > len(player.queue):
        return await ctx.reply("❌ Chỉ số ngoài phạm vi queue")
    # pop element at index (1-based) and play it next
    item = player.queue[index-1]
    # remove that item
    del player.queue[index-1]
    player.queue.appendleft(item)
    vc = ctx.guild.voice_client
    if vc and vc.is_playing():
        try:
            vc.stop()
        except Exception:
            pass
    await ctx.reply(f"▶️ Đã chuyển và phát: **{item['title']}**")


# ══════════════════════════════════════════════════════════════════════════════
#  AFK SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
afk_data: dict[int, dict] = {}

def fmt_duration(dt: datetime) -> str:
    diff = datetime.now(timezone.utc) - dt
    s = int(diff.total_seconds())
    if s < 60: return f"{s} giây"
    if s < 3600: return f"{s//60} phút"
    if s < 86400: return f"{s//3600} giờ {(s%3600)//60} phút"
    return f"{s//86400} ngày {(s%86400)//3600} giờ"


@bot.command(name="afk")
async def afk_cmd(ctx: commands.Context, *, reason: str = "Không có lý do"):
    uid = ctx.author.id
    if uid in afk_data:
        return await ctx.reply("⚠️ Bạn đang AFK rồi! Gõ bất kỳ tin nhắn nào để tắt AFK.")
    old_nick = ctx.author.nick
    afk_data[uid] = {
        "reason": reason[:100],
        "since": datetime.now(timezone.utc),
        "guild_id": ctx.guild.id,
        "old_nick": old_nick,
    }
    new_nick = f"[AFK] {ctx.author.display_name}"[:32]
    try:
        await ctx.author.edit(nick=new_nick)
    except discord.Forbidden:
        pass
    embed = discord.Embed(
        description=f"💤 **{ctx.author.display_name}** đã AFK\n📝 Lý do: **{reason}**",
        color=0x9090a8
    )
    await ctx.reply(embed=embed, delete_after=10)
    try: await ctx.message.delete()
    except: pass


# ── on_message tích hợp: AFK + Voice Manager repost panel ────────────────────
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    uid = message.author.id
    content = message.content.strip()

    # Tắt AFK khi gõ tin nhắn (trừ lệnh +afk chính nó)
    if uid in afk_data and not content.lower().startswith("+afk"):
        data = afk_data.pop(uid)
        duration = fmt_duration(data["since"])
        try:
            await message.author.edit(nick=data["old_nick"])
        except discord.Forbidden:
            pass
        embed = discord.Embed(
            description=f"✅ **{message.author.display_name}** đã trở lại sau **{duration}** AFK!",
            color=0x3ba55d
        )
        try:
            await message.channel.send(embed=embed, delete_after=8)
        except discord.Forbidden:
            log.warning(f"Không thể gửi thông báo AFK trở lại ở kênh {message.channel.id} — thiếu quyền")

    # Ai đó tag người đang AFK
    for mentioned in message.mentions:
        mid = mentioned.id
        if mid in afk_data and mid != uid:
            data = afk_data[mid]
            duration = fmt_duration(data["since"])
            embed = discord.Embed(
                description=(
                    f"💤 **{mentioned.display_name}** đang AFK!\n"
                    f"📝 Lý do: **{data['reason']}**\n"
                    f"⏱️ Đã AFK được: **{duration}**"
                ),
                color=0x9090a8
            )
            try:
                await message.channel.send(embed=embed, delete_after=10)
            except discord.Forbidden:
                log.warning(f"Không thể gửi thông báo AFK mention ở kênh {message.channel.id} — thiếu quyền")

    # Auto-link detection (TikBot-style): detect configured domains and post a short notice
    try:
        urls = re.findall(r'https?://\S+', content)
        if urls:
            sent = False
            for u in urls:
                netloc = urlparse(u).netloc.lower()
                for dom in TIKBOT_AUTO_DOMAINS:
                    if not dom: continue
                    if dom in netloc:
                        if dom in TIKBOT_SILENT_DOMAINS:
                            sent = True
                            break
                        try:
                            await message.channel.send(f"🔗 Detected {dom} link: {u}")
                        except Exception:
                            pass
                        sent = True
                        break
                if sent: break
    except Exception:
        pass

    # Voice Manager: repost panel khi có tin nhắn mới trong kênh voice
    if isinstance(message.channel, discord.VoiceChannel) and voice_manager.is_managed_channel(message.channel.id):
        if not (content.startswith("+voice_control") or content.startswith("+vc") or content.startswith("+voicecontrol")):
            try:
                await voice_manager.repost_panel(message.channel)
            except discord.Forbidden:
                log.warning(f"Không thể repost panel trong kênh {message.channel.id} — thiếu quyền")

    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx: commands.Context, error):
    # Handle missing permissions (Forbidden) gracefully — DM the invoker and log
    orig = getattr(error, 'original', error)
    if isinstance(orig, discord.Forbidden):
        try:
            await ctx.author.send(
                "⚠️ Bot thiếu quyền thực hiện hành động này trên server. "
                "Vui lòng cấp quyền `Send Messages`, `Embed Links`, `Attach Files`, `Manage Messages` hoặc liên hệ admin.")
        except Exception:
            log.warning("Không thể DM người dùng để thông báo lỗi quyền.")
        log.exception("Command failed due to missing permissions")
        return
    # Fall back to default handling for other errors (log)
    log.exception("Unhandled command error: %s", error)


def is_admin():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)


# ══════════════════════════════════════════════════════════════════════════════
#  PROFILE SYSTEM (giữ nguyên từ bản cũ)
# ══════════════════════════════════════════════════════════════════════════════
def make_stars(rating: float) -> str:
    full = int(rating); half = 1 if rating - full >= 0.5 else 0; empty = 5 - full - half
    return "⭐" * full + ("✨" if half else "") + "☆" * empty

def build_profile_embed(profile: dict, member: discord.Member, page: int) -> discord.Embed:
    photos = profile.get("photos", [])
    tags   = profile.get("tags", [])
    rating = profile.get("rating", 0)
    votes  = profile.get("votes", {})
    total  = len(votes)
    name   = profile.get("display_name") or member.display_name

    embed = discord.Embed(color=0x5865f2)
    embed.set_author(name=f"✦ {name}", icon_url=member.display_avatar.url)
    if tags: embed.description = "\n".join(f"✦ {t}" for t in tags)
    avg = round(rating, 1)
    embed.add_field(name="⭐ Đánh giá", value=f"{make_stars(avg)} **{avg}**/5.0\n`{total} lượt vote`", inline=True)
    if photos:
        idx = max(0, min(page, len(photos) - 1))
        embed.set_image(url=photos[idx])
        embed.set_footer(text=f"Ảnh {idx+1}/{len(photos)}")
    else:
        embed.set_footer(text="Chưa có ảnh")
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed


class ProfileView(discord.ui.View):
    def __init__(self, user_id: str, member: discord.Member):
        super().__init__(timeout=120)
        self.user_id = user_id; self.member = member; self.page = 0
        self._update_buttons()

    def _profile(self): return load_profiles().get(self.user_id, {})

    def _update_buttons(self):
        photos = self._profile().get("photos", [])
        total = len(photos)
        for child in self.children:
            if hasattr(child, "custom_id"):
                if child.custom_id == "prev": child.disabled = self.page <= 0
                if child.custom_id == "next": child.disabled = self.page >= total - 1
                if child.custom_id == "page_label": child.label = f"{self.page+1}/{max(total,1)}"

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.secondary, custom_id="prev")
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1); self._update_buttons()
        await interaction.response.edit_message(embed=build_profile_embed(self._profile(), self.member, self.page), view=self)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, custom_id="page_label", disabled=True)
    async def page_label(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        photos = self._profile().get("photos", [])
        self.page = min(len(photos) - 1, self.page + 1); self._update_buttons()
        await interaction.response.edit_message(embed=build_profile_embed(self._profile(), self.member, self.page), view=self)

    @discord.ui.button(label="⭐ Đánh giá", style=discord.ButtonStyle.primary, custom_id="rate_btn")
    async def rate_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RateModal(self.user_id, self.member, self))


class RateModal(discord.ui.Modal, title="Đánh giá thành viên"):
    score = discord.ui.TextInput(label="Số điểm (1-5)", placeholder="Nhập số từ 1 đến 5 (vd: 4.5)", max_length=3, required=True)
    def __init__(self, user_id: str, member: discord.Member, view: ProfileView):
        super().__init__(); self.user_id = user_id; self.member = member; self.pview = view
    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = float(str(self.score).replace(",", "."))
            if not (1 <= val <= 5): raise ValueError
        except:
            await interaction.response.send_message("❌ Điểm không hợp lệ! Nhập số từ 1 đến 5.", ephemeral=True); return
        voter = str(interaction.user.id)
        if voter == self.user_id:
            await interaction.response.send_message("❌ Không thể tự đánh giá bản thân!", ephemeral=True); return
        db = load_profiles(); p = db.setdefault(self.user_id, {})
        p.setdefault("votes", {})[voter] = val
        votes = p["votes"]; p["rating"] = round(sum(votes.values()) / len(votes), 2)
        save_profiles(db)
        self.pview._update_buttons()
        await interaction.response.edit_message(embed=build_profile_embed(p, self.member, self.pview.page), view=self.pview)


@bot.tree.command(name="profile", description="Xem profile của một thành viên")
@app_commands.describe(thanh_vien="Tag thành viên muốn xem")
async def profile_cmd(interaction: discord.Interaction, thanh_vien: discord.Member):
    uid = str(thanh_vien.id); db = load_profiles()
    if uid not in db:
        await interaction.response.send_message(f"❌ **{thanh_vien.display_name}** chưa có profile.", ephemeral=True); return
    view = ProfileView(uid, thanh_vien)
    embed = build_profile_embed(db[uid], thanh_vien, 0)
    await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name="profile_set", description="[Admin] Tạo/sửa thông tin profile")
@app_commands.describe(thanh_vien="Thành viên", ten_hien_thi="Tên hiển thị", tags="Tags cách nhau bằng | (vd: Hà Nội | Dễ tính)")
@is_admin()
async def profile_set(interaction: discord.Interaction, thanh_vien: discord.Member, ten_hien_thi: str = "", tags: str = ""):
    uid = str(thanh_vien.id); db = load_profiles(); p = db.setdefault(uid, {})
    if ten_hien_thi: p["display_name"] = ten_hien_thi.strip()
    if tags: p["tags"] = [t.strip() for t in tags.split("|") if t.strip()]
    save_profiles(db)
    await interaction.response.send_message(f"✅ Đã cập nhật profile của **{thanh_vien.display_name}**!", ephemeral=True)


@bot.tree.command(name="profile_addphoto", description="[Admin] Thêm ảnh vào gallery")
@app_commands.describe(thanh_vien="Thành viên", url_anh="URL ảnh")
@is_admin()
async def profile_addphoto(interaction: discord.Interaction, thanh_vien: discord.Member, url_anh: str):
    if not url_anh.startswith("http"):
        await interaction.response.send_message("❌ URL không hợp lệ!", ephemeral=True); return
    uid = str(thanh_vien.id); db = load_profiles(); p = db.setdefault(uid, {})
    p.setdefault("photos", []).append(url_anh); save_profiles(db)
    await interaction.response.send_message(f"✅ Đã thêm ảnh #{len(p['photos'])} cho **{thanh_vien.display_name}**!", ephemeral=True)


@bot.tree.command(name="profile_removephoto", description="[Admin] Xóa ảnh khỏi gallery")
@app_commands.describe(thanh_vien="Thành viên", so_thu_tu="Số thứ tự ảnh")
@is_admin()
async def profile_removephoto(interaction: discord.Interaction, thanh_vien: discord.Member, so_thu_tu: int):
    uid = str(thanh_vien.id); db = load_profiles(); p = db.get(uid, {})
    photos = p.get("photos", [])
    if not photos or so_thu_tu < 1 or so_thu_tu > len(photos):
        await interaction.response.send_message("❌ Số thứ tự không hợp lệ!", ephemeral=True); return
    photos.pop(so_thu_tu - 1); save_profiles(db)
    await interaction.response.send_message(f"✅ Đã xóa ảnh #{so_thu_tu} của **{thanh_vien.display_name}**!", ephemeral=True)


@bot.tree.command(name="profile_delete", description="[Admin] Xóa toàn bộ profile")
@app_commands.describe(thanh_vien="Thành viên")
@is_admin()
async def profile_delete(interaction: discord.Interaction, thanh_vien: discord.Member):
    uid = str(thanh_vien.id); db = load_profiles()
    if uid not in db:
        await interaction.response.send_message("❌ Thành viên này chưa có profile.", ephemeral=True); return
    del db[uid]; save_profiles(db)
    await interaction.response.send_message(f"✅ Đã xóa profile của **{thanh_vien.display_name}**!", ephemeral=True)


@profile_set.error
@profile_addphoto.error
@profile_removephoto.error
@profile_delete.error
async def admin_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("❌ Bạn cần quyền **Quản lý server** để dùng lệnh này!", ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
#  PREFIX COMMANDS
# ══════════════════════════════════════════════════════════════════════════════
@bot.command(name="ping")
async def ping(ctx: commands.Context):
    ms = round(bot.latency * 1000)
    uptime = datetime.now(timezone.utc) - bot.start_time
    h, rem = divmod(int(uptime.total_seconds()), 3600); m, s = divmod(rem, 60)
    voice_ch = f"🎙️ **#{bot.voice_clients[0].channel.name}**" if bot.voice_clients else "❌ Chưa vào kênh nào"
    embed = discord.Embed(title="🏓 Pong!", color=0x5865f2)
    embed.add_field(name="📶 Độ trễ", value=f"`{ms}ms`", inline=True)
    embed.add_field(name="⏱️ Uptime", value=f"`{h}h {m}m {s}s`", inline=True)
    embed.add_field(name="🎙️ Voice", value=voice_ch, inline=False)
    embed.set_footer(text=f"Bot: {bot.user}", icon_url=bot.user.display_avatar.url)
    await ctx.reply(embed=embed)


@bot.command(name="tiktok")
async def tiktok_cmd(ctx: commands.Context, url: str = ""):
    """+tiktok <link> — cố gắng tải video bằng yt-dlp nếu có, hoặc hướng dẫn cài đặt."""
    if not url or not url.startswith("http"):
        return await ctx.reply("❌ Vui lòng cung cấp link video, vd: `+tiktok https://www.tiktok.com/...`")
    netloc = urlparse(url).netloc.lower()
    if not any(dom in netloc for dom in TIKBOT_AUTO_DOMAINS):
        # vẫn cho phép nhưng cảnh báo (cảnh báo sẽ được gửi sau khi kiểm tra quyền)
        warn_non_auto = True
    else:
        warn_non_auto = False

    try:
        import yt_dlp
    except Exception:
        # try fallback: run pip install git+https... (non-blocking suggestion)
        return await ctx.reply("❌ Module `yt-dlp` chưa được cài. Hãy cập nhật yt-dlp bằng `pip install -U git+https://github.com/yt-dlp/yt-dlp.git` hoặc rebuild Docker image.")

    # --- Permission checks: make sure bot can send messages; if it can't, DM the invoker and abort
    guild_member = ctx.guild.me if ctx.guild else None
    perms = ctx.channel.permissions_for(guild_member) if guild_member else None
    can_send = True if perms is None else perms.send_messages
    can_attach = True if perms is None else perms.attach_files
    if not can_send:
        try:
            await ctx.author.send(f"⚠️ Bot hiện không có quyền `Send Messages` trong kênh {ctx.channel.name} (ID: {ctx.channel.id}). Vui lòng cấp quyền để dùng `+tiktok` ở kênh này.")
        except Exception:
            log.warning("Không thể DM user để thông báo thiếu quyền send_messages")
        return

    # send initial status message in channel (we know can_send==True)
    status_msg = await ctx.reply("⏳ Đang tải video, xin chờ... (có thể mất vài chục giây)")
    if warn_non_auto:
        try:
            await status_msg.edit(content="⚠️ Link không thuộc domain cấu hình auto-domains. Bot sẽ cố tải nhưng có thể thất bại.\n" + status_msg.content)
        except Exception:
            pass

    def dl_work(u: str):
        tmpdir = tempfile.mkdtemp(prefix="tikdl_")
        ydl_opts = {
            'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
            'format': 'bestvideo+bestaudio/best',
            'noplaylist': True,
            'merge_output_format': 'mp4',
        }
        ydl = yt_dlp.YoutubeDL(ydl_opts)
        info = ydl.extract_info(u, download=True)
        # prepare filename
        try:
            fname = ydl.prepare_filename(info)
        except Exception:
            # fallback: find any file in tmpdir
            files = os.listdir(tmpdir)
            if files:
                fname = os.path.join(tmpdir, files[0])
            else:
                fname = None
        return tmpdir, fname

    try:
        tmpdir, filepath = await asyncio.to_thread(dl_work, url)
    except Exception as e:
        log.exception("Lỗi yt-dlp extract: %s", e)
        # attempt fallback: try calling yt-dlp CLI to get more robust behaviour
        try:
            fallback_tmp = tempfile.mkdtemp(prefix="tikdlcli_")
            cli_out = os.path.join(fallback_tmp, 'out.%(ext)s')
            cmd = ["yt-dlp", "-o", cli_out, url]
            subprocess.run(cmd, check=True)
            files = os.listdir(fallback_tmp)
            if files:
                filepath = os.path.join(fallback_tmp, files[0])
                tmpdir = fallback_tmp
            else:
                raise RuntimeError("CLI yt-dlp didn't produce a file")
        except Exception as e2:
            log.exception("Fallback yt-dlp CLI failed: %s", e2)
            await status_msg.edit(content=f"❌ Lỗi khi tải (yt-dlp): {e}\nHãy cập nhật yt-dlp: `pip install -U git+https://github.com/yt-dlp/yt-dlp.git` và thử lại.`")
            return
        

    if not filepath or not os.path.exists(filepath):
        await status_msg.edit(content="❌ Không tìm thấy file sau khi tải.")
        shutil.rmtree(tmpdir, ignore_errors=True)
        return

    # check size (configurable via TIKBOT_MAX_UPLOAD_MB)
    size = os.path.getsize(filepath)
    max_bytes = TIKBOT_MAX_UPLOAD_MB * 1024 * 1024
    # helper: re-encode with ffmpeg to try to fit target size
    def reencode_to_target(inpath: str, outpath: str, duration: float, target_bytes: int) -> bool:
        # audio kbps we allocate
        audio_kbps = 96
        if duration and duration > 0:
            target_bps = (target_bytes * 8) / duration
            video_bps = max(32_000, int(target_bps - audio_kbps * 1000))
        else:
            video_bps = 300_000  # 300 kbps default
        video_k = max(64, video_bps // 1000)
        # ffmpeg command
        cmd = [
            'ffmpeg', '-y', '-i', inpath,
            '-c:v', 'libx264', '-preset', 'veryfast',
            '-b:v', f'{video_k}k', '-maxrate', f'{video_k}k', '-bufsize', f'{video_k*2}k',
            '-c:a', 'aac', '-b:a', f'{audio_kbps}k',
            '-movflags', '+faststart', outpath
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return os.path.exists(outpath)
        except Exception:
            return False
    if size <= max_bytes:
        try:
            await status_msg.edit(content="✅ Tải xong, gửi file...")
            # prefer sending in channel if bot can attach; otherwise DM the user
            if can_attach:
                try:
                    await ctx.reply(file=discord.File(filepath))
                    await status_msg.delete()
                except discord.Forbidden:
                    # fallback to DM
                    try:
                        await ctx.author.send("📩 Bot không có quyền đính kèm file trong kênh; gửi file qua DM:", file=discord.File(filepath))
                        await status_msg.delete()
                    except Exception as e:
                        await status_msg.edit(content=f"❌ Lỗi khi gửi file qua DM: {e}")
            else:
                # cannot attach in channel — send via DM
                try:
                    await ctx.author.send("📩 Bot không có quyền đính kèm file trong kênh; gửi file qua DM:", file=discord.File(filepath))
                    await status_msg.delete()
                except Exception as e:
                    await status_msg.edit(content=f"❌ Bot không thể gửi file ở kênh này và không thể DM: {e}")
        except Exception as e:
            await status_msg.edit(content=f"❌ Lỗi khi gửi file: {e}")
    else:
        # Attempt to re-encode to fit max_bytes
        duration = None
        try:
            import yt_dlp
            info_duration = None
            # try to read duration from downloaded info file if available
            # (yt_dlp returns info earlier; we didn't capture it here reliably), so fallback None
        except Exception:
            info_duration = None

        outpath = os.path.splitext(filepath)[0] + "_small.mp4"
        reok = await asyncio.to_thread(reencode_to_target, filepath, outpath, info_duration or 0, max_bytes)
        if reok and os.path.exists(outpath) and os.path.getsize(outpath) <= max_bytes:
            try:
                await status_msg.edit(content="✅ Đã nén và gửi file...")
                if can_attach:
                    try:
                        await ctx.reply(file=discord.File(outpath))
                        await status_msg.delete()
                    except discord.Forbidden:
                        try:
                            await ctx.author.send("📩 Bot không có quyền đính kèm file trong kênh; gửi file qua DM:", file=discord.File(outpath))
                            await status_msg.delete()
                        except Exception as e:
                            await status_msg.edit(content=f"❌ Lỗi khi gửi file đã nén qua DM: {e}")
                else:
                    try:
                        await ctx.author.send("📩 Bot không có quyền đính kèm file trong kênh; gửi file qua DM:", file=discord.File(outpath))
                        await status_msg.delete()
                    except Exception as e:
                        await status_msg.edit(content=f"❌ Bot không thể gửi file đã nén ở kênh này và không thể DM: {e}")
            except Exception as e:
                await status_msg.edit(content=f"❌ Lỗi khi gửi file đã nén: {e}")
        else:
            await status_msg.edit(content=f"⚠️ File quá lớn ({size//1024//1024} MB). Không thể gửi. File tạm: {filepath}")

    # cleanup tmpdir after a short delay
    try:
        await asyncio.sleep(2)
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass

@bot.command(name="help", aliases=["h"])
async def help_cmd(ctx: commands.Context):
    embed = discord.Embed(title="📖 Danh sách lệnh", color=0x5865f2)
    embed.add_field(name="🔧 Lệnh chung", value="`+ping` — Kiểm tra bot\n`+help` — Danh sách lệnh", inline=False)
    embed.add_field(name="🎙️ Voice Manager",
        value="`+voice_control` (`+vc`) — Mở bảng điều khiển cho kênh voice bạn đang ở\n"
              "Ai cũng dùng được panel, không giới hạn chủ phòng hay admin.",
        inline=False)
    embed.add_field(name="👤 Profile (Slash)",
        value="`/profile @user` — Xem profile\n"
              "`/profile_set` — Tạo/sửa *(Admin)*\n"
              "`/profile_addphoto` — Thêm ảnh *(Admin)*\n"
              "`/profile_removephoto` — Xóa ảnh *(Admin)*\n"
              "`/profile_delete` — Xóa profile *(Admin)*",
        inline=False)
    embed.add_field(name="⭕❌ Cờ Caro 10x10",
        value="`+caro @user` — Thách đấu 1 người\n"
              "`+caro` — Đấu với Bot (AI)\n"
              "`+danh <hàng> <cột>` (`+d`) — Đánh quân, vd: `+danh 5 7` hoặc `+danh E7`\n"
              "`+caro_end` — Huỷ ván đang chơi",
        inline=False)
    embed.add_field(name="💤 AFK",
        value="`+afk [lý do]` — Bật AFK, vd: `+afk đi ngủ`\n"
              "Tự tắt khi bạn gõ tin nhắn bất kỳ\n"
              "Bot sẽ báo mọi người khi có ai tag bạn lúc AFK",
        inline=False)
    embed.set_footer(text=f"Prefix: + | Bot: {bot.user}")
    await ctx.reply(embed=embed)



# ══════════════════════════════════════════════════════════════════════════════
#  CỜ CARO (GOMOKU) 10x10
# ══════════════════════════════════════════════════════════════════════════════
CARO_SIZE = 10
CARO_EMPTY, CARO_X, CARO_O = 0, 1, 2
CARO_SYMBOLS = {CARO_EMPTY: "⬜", CARO_X: "❌", CARO_O: "⭕"}
CARO_COLS = "ABCDEFGHIJ"  # cột A-J tương ứng 1-10

# games đang diễn ra, key = channel_id
caro_games: dict[int, dict] = {}

def caro_new_board():
    return [[CARO_EMPTY for _ in range(CARO_SIZE)] for _ in range(CARO_SIZE)]

def caro_render(game: dict) -> str:
    board = game["board"]
    header = "⬛" + "".join(f"{i+1:>2}"[-1] + "\u200b" for i in range(CARO_SIZE))
    # Dùng emoji số để căn đều hơn
    num_emoji = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = ["⬛" + "".join(num_emoji)]
    for r in range(CARO_SIZE):
        row_label = f"{CARO_COLS[r]}"
        row_str = "".join(CARO_SYMBOLS[board[r][c]] for c in range(CARO_SIZE))
        lines.append(f"🔹{row_str}")
    return "\n".join(lines)

def caro_in_bounds(r, c): return 0 <= r < CARO_SIZE and 0 <= c < CARO_SIZE

def caro_check_win(board, r, c, player) -> bool:
    directions = [(0,1), (1,0), (1,1), (1,-1)]
    for dr, dc in directions:
        count = 1
        for sign in (1, -1):
            rr, cc = r + dr*sign, c + dc*sign
            while caro_in_bounds(rr, cc) and board[rr][cc] == player:
                count += 1
                rr += dr*sign; cc += dc*sign
        if count >= 5:
            return True
    return False

def caro_is_full(board) -> bool:
    return all(cell != CARO_EMPTY for row in board for cell in row)

def caro_parse_pos(text: str):
    """Parse '5 7' hoặc 'A5' hoặc '5A' thành (row, col) 0-indexed. Trả None nếu sai."""
    text = text.strip().upper().replace(",", " ")
    parts = text.split()
    try:
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            row = int(parts[0]) - 1
            col = int(parts[1]) - 1
            if caro_in_bounds(row, col): return (row, col)
            return None
        if len(parts) == 1:
            s = parts[0]
            # dạng A5 hoặc 5A
            if s[0] in CARO_COLS and s[1:].isdigit():
                row = CARO_COLS.index(s[0]); col = int(s[1:]) - 1
                if caro_in_bounds(row, col): return (row, col)
            if s[-1] in CARO_COLS and s[:-1].isdigit():
                row = CARO_COLS.index(s[-1]); col = int(s[:-1]) - 1
                if caro_in_bounds(row, col): return (row, col)
    except Exception:
        return None
    return None

def caro_ai_move(board, ai_player, human_player):
    """AI đơn giản: ưu tiên (1) thắng ngay, (2) chặn đối thủ thắng, (3) đánh cạnh quân gần trung tâm nhất có điểm cao nhất theo heuristic."""
    empties = [(r, c) for r in range(CARO_SIZE) for c in range(CARO_SIZE) if board[r][c] == CARO_EMPTY]
    if not empties:
        return None

    # 1) Thử thắng ngay
    for (r, c) in empties:
        board[r][c] = ai_player
        if caro_check_win(board, r, c, ai_player):
            board[r][c] = CARO_EMPTY
            return (r, c)
        board[r][c] = CARO_EMPTY

    # 2) Chặn đối thủ thắng
    for (r, c) in empties:
        board[r][c] = human_player
        if caro_check_win(board, r, c, human_player):
            board[r][c] = CARO_EMPTY
            return (r, c)
        board[r][c] = CARO_EMPTY

    # 3) Heuristic: chấm điểm từng ô trống dựa trên số quân liền kề (bán kính 2)
    def score_cell(r, c, player):
        score = 0
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                if dr == 0 and dc == 0: continue
                rr, cc = r+dr, c+dc
                if caro_in_bounds(rr, cc) and board[rr][cc] == player:
                    dist = max(abs(dr), abs(dc))
                    score += (3 - dist) if dist <= 2 else 0
        return score

    best_cell, best_score = None, -1
    for (r, c) in empties:
        s = score_cell(r, c, ai_player) * 2 + score_cell(r, c, human_player)
        # ưu tiên gần trung tâm nếu bàn còn trống nhiều
        center_bonus = -(abs(r - 4.5) + abs(c - 4.5)) * 0.1
        s += center_bonus
        if s > best_score:
            best_score, best_cell = s, (r, c)
    return best_cell


@bot.command(name="caro", aliases=["gomoku"])
async def caro_start(ctx: commands.Context, doi_thu: discord.Member = None):
    """+caro @user để đấu người, +caro (không tag ai) để đấu bot."""
    channel_id = ctx.channel.id
    if channel_id in caro_games:
        return await ctx.reply("⚠️ Kênh này đang có 1 ván cờ chưa kết thúc! Dùng `+caro_end` để huỷ ván cũ trước.")

    vs_bot = doi_thu is None or doi_thu.bot
    if doi_thu and doi_thu.id == ctx.author.id:
        return await ctx.reply("❌ Không thể tự đấu với chính mình!")

    game = {
        "board": caro_new_board(),
        "players": {CARO_X: ctx.author.id, CARO_O: (bot.user.id if vs_bot else doi_thu.id)},
        "names": {CARO_X: ctx.author.display_name, CARO_O: ("🤖 Bot" if vs_bot else doi_thu.display_name)},
        "turn": CARO_X,
        "vs_bot": vs_bot,
        "channel_id": channel_id,
    }
    caro_games[channel_id] = game

    embed = discord.Embed(
        title="⭕❌ Cờ Caro 10x10 (Gomoku)",
        description=(
            f"{caro_render(game)}\n\n"
            f"❌ **{game['names'][CARO_X]}**  vs  ⭕ **{game['names'][CARO_O]}**\n"
            f"👉 Lượt của: **{game['names'][game['turn']]}**\n\n"
            f"Đánh bằng lệnh: `+danh <hàng> <cột>` (vd: `+danh 5 7`) hoặc `+danh E7`"
        ),
        color=0x5865F2
    )
    await ctx.reply(embed=embed)


@bot.command(name="danh", aliases=["move", "d"])
async def caro_move(ctx: commands.Context, *, pos: str = ""):
    channel_id = ctx.channel.id
    game = caro_games.get(channel_id)
    if not game:
        return await ctx.reply("❌ Không có ván cờ nào đang diễn ra trong kênh này! Dùng `+caro` để bắt đầu.")

    turn_player_id = game["players"][game["turn"]]
    if ctx.author.id != turn_player_id:
        return await ctx.reply(f"⏳ Chưa đến lượt bạn! Đang chờ **{game['names'][game['turn']]}**.")

    parsed = caro_parse_pos(pos)
    if not parsed:
        return await ctx.reply("❌ Vị trí không hợp lệ! Dùng dạng `+danh 5 7` (hàng cột, 1-10) hoặc `+danh E7`.")

    r, c = parsed
    if game["board"][r][c] != CARO_EMPTY:
        return await ctx.reply("❌ Ô này đã có quân rồi!")

    board = game["board"]
    player = game["turn"]
    board[r][c] = player

    if caro_check_win(board, r, c, player):
        embed = discord.Embed(
            title="🏆 Kết thúc ván cờ!",
            description=f"{caro_render(game)}\n\n🎉 **{game['names'][player]}** đã thắng!",
            color=0x3BA55D
        )
        del caro_games[channel_id]
        return await ctx.reply(embed=embed)

    if caro_is_full(board):
        embed = discord.Embed(
            title="🤝 Hoà!",
            description=f"{caro_render(game)}\n\nBàn cờ đã đầy, ván cờ kết thúc hoà!",
            color=0xFAA61A
        )
        del caro_games[channel_id]
        return await ctx.reply(embed=embed)

    # Chuyển lượt
    game["turn"] = CARO_O if player == CARO_X else CARO_X

    # Nếu đấu bot và đến lượt bot
    if game["vs_bot"] and game["turn"] == CARO_O:
        ai_pos = caro_ai_move(board, CARO_O, CARO_X)
        if ai_pos:
            ar, ac = ai_pos
            board[ar][ac] = CARO_O
            if caro_check_win(board, ar, ac, CARO_O):
                embed = discord.Embed(
                    title="🏆 Kết thúc ván cờ!",
                    description=f"{caro_render(game)}\n\n🤖 **Bot** đã thắng! Chúc may mắn lần sau 😄",
                    color=0xED4245
                )
                del caro_games[channel_id]
                return await ctx.reply(embed=embed)
            if caro_is_full(board):
                embed = discord.Embed(
                    title="🤝 Hoà!",
                    description=f"{caro_render(game)}\n\nBàn cờ đã đầy, ván cờ kết thúc hoà!",
                    color=0xFAA61A
                )
                del caro_games[channel_id]
                return await ctx.reply(embed=embed)
            game["turn"] = CARO_X

    embed = discord.Embed(
        title="⭕❌ Cờ Caro 10x10 (Gomoku)",
        description=(
            f"{caro_render(game)}\n\n"
            f"❌ **{game['names'][CARO_X]}**  vs  ⭕ **{game['names'][CARO_O]}**\n"
            f"👉 Lượt của: **{game['names'][game['turn']]}**"
        ),
        color=0x5865F2
    )
    await ctx.reply(embed=embed)


@bot.command(name="caro_end", aliases=["caro_huy"])
async def caro_end(ctx: commands.Context):
    channel_id = ctx.channel.id
    if channel_id not in caro_games:
        return await ctx.reply("❌ Không có ván cờ nào đang diễn ra trong kênh này!")
    game = caro_games[channel_id]
    if ctx.author.id not in game["players"].values() and not ctx.author.guild_permissions.manage_messages:
        return await ctx.reply("❌ Chỉ người chơi hoặc mod mới huỷ được ván cờ!")
    del caro_games[channel_id]
    await ctx.reply("🛑 Đã huỷ ván cờ trong kênh này.")



# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD HTML (giữ nguyên, đã hoạt động)
# ══════════════════════════════════════════════════════════════════════════════
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bot Dashboard</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.11.0/dist/tabler-icons.min.css">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0f0f14;--sur:#1a1a24;--sur2:#22222f;--bd:rgba(255,255,255,.08);--bd2:rgba(255,255,255,.14);--tx:#e8e8f0;--tx2:#9090a8;--tx3:#5a5a70;--ac:#5865f2;--ac-g:rgba(88,101,242,.18);--gr:#3ba55d;--gr-g:rgba(59,165,93,.12);--rd:#ed4245;--rd-g:rgba(237,66,69,.12);--yw:#faa61a;--r:10px;--rs:6px}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--tx);min-height:100vh}
.hd{display:flex;align-items:center;gap:12px;padding:14px 24px;border-bottom:1px solid var(--bd);background:var(--sur)}
.hd-logo{width:34px;height:34px;border-radius:50%;background:var(--ac);display:flex;align-items:center;justify-content:center}.hd-logo i{font-size:17px;color:#fff}
.hd-title{font-size:15px;font-weight:600}.hd-sub{font-size:11px;color:var(--tx2);margin-top:1px}
.pill{margin-left:auto;display:flex;align-items:center;gap:5px;padding:4px 11px;border-radius:20px;font-size:12px;font-weight:500}
.pill.on{background:var(--gr-g);color:var(--gr)}.pill.off{background:var(--rd-g);color:var(--rd)}
.dot{width:7px;height:7px;border-radius:50%;background:currentColor;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.auth-wrap{position:fixed;inset:0;background:rgba(10,10,16,.92);display:flex;align-items:center;justify-content:center;z-index:100;backdrop-filter:blur(4px)}
.auth-box{background:var(--sur);border:1px solid var(--bd2);border-radius:var(--r);padding:28px 24px;width:100%;max-width:380px}
.auth-title{font-size:16px;font-weight:600;margin-bottom:6px}.auth-sub{font-size:13px;color:var(--tx2);margin-bottom:18px}
.wrap{max-width:820px;margin:0 auto;padding:20px 16px}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:12px}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
@media(max-width:580px){.g3,.g2{grid-template-columns:1fr}}
.card{background:var(--sur);border:1px solid var(--bd);border-radius:var(--r);padding:16px 18px}
.card-title{font-size:10px;font-weight:600;color:var(--tx3);text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px}
.stat-val{font-size:24px;font-weight:700}.stat-lbl{font-size:12px;color:var(--tx2);margin-top:2px}.stat-ico{float:right;font-size:20px;color:var(--ac);opacity:.8}
.inp{width:100%;padding:9px 13px;border-radius:var(--rs);background:var(--sur2);border:1px solid var(--bd2);color:var(--tx);font-size:13px;outline:none;transition:border-color .2s;margin-bottom:10px}
.inp:focus{border-color:var(--ac)}.inp::placeholder{color:var(--tx3)}
.btn{padding:9px 16px;border-radius:var(--rs);border:none;font-size:13px;font-weight:500;cursor:pointer;transition:opacity .15s,transform .1s;display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.btn:active{transform:scale(.97)}.btn-ac{background:var(--ac);color:#fff;width:100%}.btn-gr{background:var(--gr);color:#fff;flex:1}.btn-rd{background:var(--rd);color:#fff;flex:1}.btn-gh{background:transparent;color:var(--tx2);border:1px solid var(--bd2);padding:4px 10px;font-size:12px}.btn:hover{opacity:.88}
.ch-list{display:flex;flex-direction:column;gap:7px;margin-top:8px;max-height:240px;overflow-y:auto}
.ch-item{display:flex;align-items:center;gap:9px;padding:8px 11px;border-radius:var(--rs);border:1px solid var(--bd);background:var(--sur2);cursor:pointer;transition:border-color .15s}
.ch-item:hover{border-color:var(--ac)}.ch-item.active{border-color:var(--ac);background:var(--ac-g)}
.ch-item i{color:var(--ac);font-size:15px}.ch-name{font-size:13px}.ch-guild{font-size:11px;color:var(--tx3)}.ch-cnt{margin-left:auto;font-size:11px;color:var(--tx2)}
.log{background:#0a0a10;border:1px solid var(--bd);border-radius:var(--rs);padding:10px 13px;font-family:'Menlo','Consolas',monospace;font-size:11.5px;color:#a0a0c0;max-height:170px;overflow-y:auto;line-height:1.7}
.log p{margin:0}.log .ok{color:var(--gr)}.log .err{color:var(--rd)}.log .info{color:var(--yw)}
.tgl-row{display:flex;align-items:center;justify-content:space-between;padding:10px 0}.tgl-row+.tgl-row{border-top:1px solid var(--bd)}
.tgl-lbl{font-size:13px}.tgl-desc{font-size:11px;color:var(--tx2);margin-top:2px}
.tgl{position:relative;width:40px;height:22px;flex-shrink:0}.tgl input{display:none}
.tgl-track{position:absolute;inset:0;border-radius:11px;background:var(--sur2);border:1px solid var(--bd2);cursor:pointer;transition:background .2s}
.tgl input:checked+.tgl-track{background:var(--ac);border-color:var(--ac)}
.tgl-thumb{position:absolute;top:3px;left:3px;width:16px;height:16px;border-radius:50%;background:#fff;transition:transform .2s;pointer-events:none}
.tgl input:checked~.tgl-thumb{transform:translateX(18px)}
.alert{padding:9px 13px;border-radius:var(--rs);font-size:12px;margin-bottom:12px;display:none;align-items:center;gap:7px}
.alert.show{display:flex}.alert.ok{background:var(--gr-g);color:var(--gr);border:1px solid rgba(59,165,93,.25)}.alert.err{background:var(--rd-g);color:var(--rd);border:1px solid rgba(237,66,69,.25)}
</style>
</head>
<body>
<div class="auth-wrap" id="auth-wrap">
  <div class="auth-box">
    <div class="auth-title">🎙️ Bot Dashboard</div>
    <div class="auth-sub">Nhập mật khẩu dashboard để tiếp tục</div>
    <input class="inp" id="inp-key" type="password" placeholder="Mật khẩu dashboard" onkeydown="if(event.key==='Enter')login()">
    <button class="btn btn-ac" onclick="login()"><i class="ti ti-login"></i> Đăng nhập</button>
    <div class="alert err" id="auth-err" style="margin-top:10px;display:none"><i class="ti ti-alert-circle"></i><span>Mật khẩu sai!</span></div>
  </div>
</div>
<div class="hd">
  <div class="hd-logo"><i class="ti ti-headphones"></i></div>
  <div><div class="hd-title" id="bot-name">Bot Dashboard</div><div class="hd-sub">Đang kết nối...</div></div>
  <span class="pill off" id="pill"><span class="dot"></span><span id="pill-txt">Ngoại tuyến</span></span>
</div>
<div class="wrap">
  <div class="alert" id="alert"><i class="ti ti-alert-circle"></i><span id="alert-msg"></span></div>
  <div class="g3">
    <div class="card"><i class="ti ti-clock stat-ico"></i><div class="card-title">Thời gian chạy</div><div class="stat-val" id="uptime">—</div><div class="stat-lbl">kể từ khi khởi động</div></div>
    <div class="card"><i class="ti ti-microphone stat-ico"></i><div class="card-title">Kênh hiện tại</div><div class="stat-val" style="font-size:16px;line-height:1.4" id="cur-ch">—</div><div class="stat-lbl" id="cur-guild">chưa vào kênh</div></div>
    <div class="card"><i class="ti ti-users stat-ico"></i><div class="card-title">Người trong kênh</div><div class="stat-val" id="cur-mem">—</div><div class="stat-lbl">người (không tính bot)</div></div>
  </div>
  <div class="g2">
    <div class="card">
      <div class="card-title">Chọn kênh voice</div>
      <div class="ch-list" id="ch-list"><div style="color:var(--tx3);font-size:13px">Đang tải...</div></div>
      <div style="display:flex;gap:8px;margin-top:12px">
        <button class="btn btn-gr" onclick="joinSel()"><i class="ti ti-player-play"></i> Vào kênh</button>
        <button class="btn btn-rd" onclick="leaveAll()"><i class="ti ti-door-exit"></i> Rời kênh</button>
      </div>
    </div>
    <div style="display:flex;flex-direction:column;gap:12px">
      <div class="card">
        <div class="card-title">Cài đặt</div>
        <div class="tgl-row"><div><div class="tgl-lbl">Tự động vào lại</div><div class="tgl-desc">Rejoin nếu bị kick</div></div><label class="tgl"><input type="checkbox" id="tgl-rejoin" checked onchange="setRejoin(this.checked)"><div class="tgl-track"></div><div class="tgl-thumb"></div></label></div>
        <div class="tgl-row"><div><div class="tgl-lbl">Follow chủ</div><div class="tgl-desc">Vào kênh khi chủ join</div></div><label class="tgl"><input type="checkbox" id="tgl-follow" checked onchange="setFollow(this.checked)"><div class="tgl-track"></div><div class="tgl-thumb"></div></label></div>
      </div>
      <div class="card" style="flex:1">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px"><div class="card-title" style="margin:0">Nhật ký</div><button class="btn btn-gh" onclick="clrLog()">Xóa</button></div>
        <div class="log" id="log"></div>
      </div>
    </div>
  </div>
</div>
<script>
const SK='__vbot_key__';let key='',sel=null,timer=null;
window.onload=()=>{const s=sessionStorage.getItem(SK);if(s){key=s;document.getElementById('auth-wrap').style.display='none';init();}};
async function login(){key=document.getElementById('inp-key').value.trim();try{await api('/status');sessionStorage.setItem(SK,key);document.getElementById('auth-wrap').style.display='none';init();}catch(e){document.getElementById('auth-err').style.display='flex';key='';}}
function init(){refresh();loadCh();timer=setInterval(refresh,7000);}
async function api(p,m='GET',b=null){const o={method:m,headers:{'Content-Type':'application/json','X-API-Key':key}};if(b)o.body=JSON.stringify(b);const r=await fetch(p,o);if(!r.ok)throw new Error(r.status);return r.json();}
function addLog(msg,t=''){const box=document.getElementById('log');const p=document.createElement('p');p.className=t;p.textContent='['+new Date().toLocaleTimeString('vi-VN')+'] '+msg;box.appendChild(p);box.scrollTop=box.scrollHeight;}
function clrLog(){document.getElementById('log').innerHTML='';}
function showAlert(msg,t='ok'){const el=document.getElementById('alert');el.className='alert show '+t;document.getElementById('alert-msg').textContent=msg;setTimeout(()=>el.classList.remove('show'),3000);}
async function refresh(){try{const s=await api('/status');document.getElementById('bot-name').textContent=s.bot_name||'Bot';const pill=document.getElementById('pill');pill.className='pill '+(s.online?'on':'off');document.getElementById('pill-txt').textContent=s.online?'Trực tuyến':'Ngoại tuyến';document.getElementById('uptime').textContent=s.uptime||'—';if(s.voice&&s.voice.length){const v=s.voice[0];document.getElementById('cur-ch').textContent='#'+v.channel;document.getElementById('cur-guild').textContent=v.guild;document.getElementById('cur-mem').textContent=v.members;}else{document.getElementById('cur-ch').textContent='—';document.getElementById('cur-guild').textContent='chưa vào kênh';document.getElementById('cur-mem').textContent='0';}document.getElementById('tgl-rejoin').checked=!!s.auto_rejoin;document.getElementById('tgl-follow').checked=!!s.follow_owner;}catch(e){document.getElementById('pill').className='pill off';document.getElementById('pill-txt').textContent='Ngoại tuyến';}}
async function loadCh(){try{const chs=await api('/channels');const list=document.getElementById('ch-list');list.innerHTML='';if(!chs.length){list.innerHTML='<div style="color:var(--tx3);font-size:13px">Không có kênh nào</div>';return;}chs.forEach(ch=>{const d=document.createElement('div');d.className='ch-item';d.innerHTML=`<i class="ti ti-volume"></i><div><div class="ch-name">${ch.channel_name}</div><div class="ch-guild">${ch.guild_name}</div></div><span class="ch-cnt">${ch.members}</span>`;d.onclick=()=>{document.querySelectorAll('.ch-item').forEach(i=>i.classList.remove('active'));d.classList.add('active');sel=ch.channel_id;};list.appendChild(d);});}catch(e){addLog('Lỗi tải kênh: '+e.message,'err');}}
async function joinSel(){if(!sel){showAlert('Chọn kênh trước!','err');return;}try{const r=await api('/join','POST',{channel_id:sel});if(r.success){addLog('Đã vào kênh','ok');showAlert('Bot đã vào kênh!');}else{addLog('Thất bại','err');showAlert('Thất bại','err');}await refresh();await loadCh();}catch(e){addLog('Lỗi: '+e.message,'err');}}
async function leaveAll(){try{await api('/leave','POST');addLog('Bot đã rời kênh','ok');showAlert('Bot đã rời kênh!');await refresh();}catch(e){addLog('Lỗi: '+e.message,'err');}}
async function setRejoin(v){try{await api('/auto_rejoin','POST',{enabled:v});addLog('Tự động vào lại: '+(v?'BẬT':'TẮT'),'info');}catch(e){}}
async function setFollow(v){try{await api('/follow_owner','POST',{enabled:v});addLog('Follow chủ: '+(v?'BẬT':'TẮT'),'info');}catch(e){}}
</script>
</body>
</html>"""

routes = web.RouteTableDef()

def check_key(req): return req.headers.get("X-API-Key") == DASHBOARD_KEY

@routes.get("/")
async def index(_): return web.Response(text=DASHBOARD_HTML, content_type="text/html")

@routes.get("/status")
async def status(req):
    if not check_key(req): raise web.HTTPUnauthorized()
    return web.json_response(bot.get_status())

@routes.post("/join")
async def join(req):
    if not check_key(req): raise web.HTTPUnauthorized()
    body = await req.json(); cid = int(body.get("channel_id", 0))
    ch = bot.get_channel(cid)
    if ch:
        if bot._is_temp_channel(ch): bot.temp_channel_id = cid
        else: bot.permanent_channel_id = cid
    ok = await bot._join_by_id(cid)
    return web.json_response({"success": ok})

@routes.post("/leave")
async def leave(req):
    if not check_key(req): raise web.HTTPUnauthorized()
    await bot.leave_all_voice(); return web.json_response({"success": True})

@routes.post("/auto_rejoin")
async def auto_rejoin(req):
    if not check_key(req): raise web.HTTPUnauthorized()
    body = await req.json(); bot.auto_rejoin = bool(body.get("enabled", True))
    return web.json_response({"auto_rejoin": bot.auto_rejoin})

@routes.post("/follow_owner")
async def follow_owner(req):
    if not check_key(req): raise web.HTTPUnauthorized()
    body = await req.json(); bot.follow_owner = bool(body.get("enabled", True))
    return web.json_response({"follow_owner": bot.follow_owner})

@routes.get("/channels")
async def channels(req):
    if not check_key(req): raise web.HTTPUnauthorized()
    result = []
    for g in bot.guilds:
        for ch in g.voice_channels:
            result.append({"guild_id": g.id, "guild_name": g.name,
                           "channel_id": ch.id, "channel_name": ch.name,
                           "members": len([m for m in ch.members if not m.bot])})
    return web.json_response(result)


async def run_web():
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", DASHBOARD_PORT).start()
    log.info(f"🌐 Dashboard chạy tại port {DASHBOARD_PORT}")


async def main():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(run_web())
        tg.create_task(bot.start(TOKEN))

if __name__ == "__main__":
    asyncio.run(main())
