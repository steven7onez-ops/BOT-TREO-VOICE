import discord
from discord import app_commands
from discord.ext import commands
import asyncio, os, logging, json
from aiohttp import web
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

PROFILE_DB_FILE = Path("/tmp/profiles.json")
VC_CONFIG_FILE  = Path("/tmp/vc_hub.json")   # cấu hình hub tạo kênh tạm thời
VC_STATE_FILE   = Path("/tmp/vc_state.json") # kênh tạm thời đang tồn tại + panel message id

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
def load_vc_config():  return load_json(VC_CONFIG_FILE)
def save_vc_config(d): save_json(VC_CONFIG_FILE, d)
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
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="🎙️ voice channel"))
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

        # Voice Manager: xử lý tạo/xoá kênh tạm thời
        await voice_manager.handle_voice_state_update(member, before, after)

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


# ══════════════════════════════════════════════════════════════════════════════
#  VOICE MANAGER — Kênh tạm thời kiểu VoiceMaster
# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
#  VOICE MANAGER — Kênh tạm thời kiểu VoiceMaster
# ══════════════════════════════════════════════════════════════════════════════
# Cấu hình per-guild (VC_CONFIG_FILE):
#   { guild_id: { "hub_channel_id": int, "category_id": int|None, "name_template": str } }
# Trạng thái per-channel (VC_STATE_FILE):
#   { channel_id: { "owner_id": int, "panel_message_id": int|None, "locked": bool, "hidden": bool } }

voice_manager = None  # khởi tạo bên dưới, sau khi định nghĩa VoiceManagerImpl


PANEL_TITLE = "⚙️ Chào mừng đến kênh thoại tạm thời của bạn"
PANEL_DESC = (
    "Điều khiển kênh bằng bảng bên dưới.\n"
    "Kênh sẽ **tự động biến mất** khi trống."
)

def build_panel_embed(channel: discord.VoiceChannel, owner: discord.Member, state: dict) -> discord.Embed:
    embed = discord.Embed(title=PANEL_TITLE, description=PANEL_DESC, color=0x5865F2)
    embed.add_field(name="🔊 Kênh", value=f"**{channel.name}**", inline=True)
    embed.add_field(name="👑 Chủ kênh", value=owner.mention, inline=True)
    embed.add_field(name="👥 Giới hạn", value=str(channel.user_limit) if channel.user_limit else "Không giới hạn", inline=True)
    status = []
    status.append("🔒 Đã khoá" if state.get("locked") else "🔓 Đang mở")
    status.append("🙈 Đã ẩn" if state.get("hidden") else "👁️ Hiển thị")
    embed.add_field(name="📋 Trạng thái", value=" · ".join(status), inline=False)
    embed.set_thumbnail(url=owner.display_avatar.url)
    embed.set_footer(text=f"Kênh ID: {channel.id}")
    return embed


class VoicePanelView(discord.ui.View):
    """View gắn với 1 kênh voice tạm thời cụ thể."""
    def __init__(self, channel_id: int):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        # gán custom_id động cho từng nút để persistent view hoạt động đúng
        for item in self.children:
            if hasattr(item, "custom_id") and item.custom_id:
                item.custom_id = f"{item.custom_id}:{channel_id}"

    def _get_channel(self) -> discord.VoiceChannel | None:
        return bot.get_channel(self.channel_id)

    def _check_owner(self, interaction: discord.Interaction, state: dict) -> bool:
        return interaction.user.id == state.get("owner_id") or interaction.user.guild_permissions.manage_channels

    async def _deny(self, interaction: discord.Interaction):
        await interaction.response.send_message("❌ Chỉ chủ kênh hoặc admin mới dùng được nút này!", ephemeral=True)

    @discord.ui.button(emoji="🔒", label="Khoá/Mở", style=discord.ButtonStyle.secondary, custom_id="vc_lock")
    async def lock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self._get_channel()
        if not channel: return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        state_all = load_vc_state()
        state = state_all.get(str(channel.id), {})
        if not self._check_owner(interaction, state): return await self._deny(interaction)

        locked = not state.get("locked", False)
        state["locked"] = locked
        state_all[str(channel.id)] = state
        save_vc_state(state_all)

        overwrite = channel.overwrites_for(channel.guild.default_role)
        overwrite.connect = not locked
        await channel.set_permissions(channel.guild.default_role, overwrite=overwrite)

        owner = channel.guild.get_member(state.get("owner_id"))
        await interaction.response.edit_message(embed=build_panel_embed(channel, owner, state), view=self)

    @discord.ui.button(emoji="🙈", label="Ẩn/Hiện", style=discord.ButtonStyle.secondary, custom_id="vc_hide")
    async def hide_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self._get_channel()
        if not channel: return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        state_all = load_vc_state()
        state = state_all.get(str(channel.id), {})
        if not self._check_owner(interaction, state): return await self._deny(interaction)

        hidden = not state.get("hidden", False)
        state["hidden"] = hidden
        state_all[str(channel.id)] = state
        save_vc_state(state_all)

        overwrite = channel.overwrites_for(channel.guild.default_role)
        overwrite.view_channel = not hidden
        await channel.set_permissions(channel.guild.default_role, overwrite=overwrite)

        owner = channel.guild.get_member(state.get("owner_id"))
        await interaction.response.edit_message(embed=build_panel_embed(channel, owner, state), view=self)

    @discord.ui.button(emoji="✏️", label="Đổi tên", style=discord.ButtonStyle.secondary, custom_id="vc_rename")
    async def rename_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self._get_channel()
        if not channel: return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        state_all = load_vc_state()
        state = state_all.get(str(channel.id), {})
        if not self._check_owner(interaction, state): return await self._deny(interaction)
        await interaction.response.send_modal(RenameModal(channel.id))

    @discord.ui.button(emoji="👥", label="Giới hạn", style=discord.ButtonStyle.secondary, custom_id="vc_limit")
    async def limit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self._get_channel()
        if not channel: return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        state_all = load_vc_state()
        state = state_all.get(str(channel.id), {})
        if not self._check_owner(interaction, state): return await self._deny(interaction)
        await interaction.response.send_modal(LimitModal(channel.id))

    @discord.ui.button(emoji="🎚️", label="Bitrate", style=discord.ButtonStyle.secondary, custom_id="vc_bitrate")
    async def bitrate_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self._get_channel()
        if not channel: return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        state_all = load_vc_state()
        state = state_all.get(str(channel.id), {})
        if not self._check_owner(interaction, state): return await self._deny(interaction)
        await interaction.response.send_modal(BitrateModal(channel.id))

    @discord.ui.button(emoji="👑", label="Chuyển chủ", style=discord.ButtonStyle.secondary, custom_id="vc_transfer")
    async def transfer_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self._get_channel()
        if not channel: return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        state_all = load_vc_state()
        state = state_all.get(str(channel.id), {})
        if not self._check_owner(interaction, state): return await self._deny(interaction)

        members = [m for m in channel.members if not m.bot and m.id != state.get("owner_id")]
        if not members:
            return await interaction.response.send_message("❌ Không có ai khác trong kênh để chuyển chủ!", ephemeral=True)

        select = TransferSelect(channel.id, members)
        view = discord.ui.View(timeout=60); view.add_item(select)
        await interaction.response.send_message("👑 Chọn thành viên để chuyển quyền chủ kênh:", view=view, ephemeral=True)

    @discord.ui.button(emoji="🚫", label="Kick", style=discord.ButtonStyle.danger, custom_id="vc_kick")
    async def kick_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self._get_channel()
        if not channel: return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        state_all = load_vc_state()
        state = state_all.get(str(channel.id), {})
        if not self._check_owner(interaction, state): return await self._deny(interaction)

        members = [m for m in channel.members if not m.bot and m.id != state.get("owner_id")]
        if not members:
            return await interaction.response.send_message("❌ Không có ai khác trong kênh để kick!", ephemeral=True)

        select = KickSelect(channel.id, members)
        view = discord.ui.View(timeout=60); view.add_item(select)
        await interaction.response.send_message("🚫 Chọn thành viên để kick khỏi kênh:", view=view, ephemeral=True)


class RenameModal(discord.ui.Modal, title="Đổi tên kênh"):
    new_name = discord.ui.TextInput(label="Tên kênh mới", max_length=100, required=True)
    def __init__(self, channel_id: int):
        super().__init__(); self.channel_id = channel_id
    async def on_submit(self, interaction: discord.Interaction):
        channel = bot.get_channel(self.channel_id)
        if not channel: return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        await channel.edit(name=str(self.new_name)[:100])
        state_all = load_vc_state(); state = state_all.get(str(channel.id), {})
        owner = channel.guild.get_member(state.get("owner_id"))
        view = VoicePanelView(channel.id)
        await interaction.response.edit_message(embed=build_panel_embed(channel, owner, state), view=view)


class LimitModal(discord.ui.Modal, title="Đặt giới hạn số người"):
    limit = discord.ui.TextInput(label="Số người tối đa (0 = không giới hạn)", max_length=3, required=True, placeholder="Vd: 5")
    def __init__(self, channel_id: int):
        super().__init__(); self.channel_id = channel_id
    async def on_submit(self, interaction: discord.Interaction):
        channel = bot.get_channel(self.channel_id)
        if not channel: return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        try:
            val = int(str(self.limit))
            if not (0 <= val <= 99): raise ValueError
        except:
            return await interaction.response.send_message("❌ Số không hợp lệ! (0-99)", ephemeral=True)
        await channel.edit(user_limit=val)
        state_all = load_vc_state(); state = state_all.get(str(channel.id), {})
        owner = channel.guild.get_member(state.get("owner_id"))
        view = VoicePanelView(channel.id)
        await interaction.response.edit_message(embed=build_panel_embed(channel, owner, state), view=view)


class BitrateModal(discord.ui.Modal, title="Đặt Bitrate (kbps)"):
    bitrate = discord.ui.TextInput(label="Bitrate (8-96 kbps, tuỳ server boost)", max_length=3, required=True, placeholder="Vd: 64")
    def __init__(self, channel_id: int):
        super().__init__(); self.channel_id = channel_id
    async def on_submit(self, interaction: discord.Interaction):
        channel = bot.get_channel(self.channel_id)
        if not channel: return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        try:
            val = int(str(self.bitrate))
            max_bitrate = channel.guild.bitrate_limit // 1000
            if not (8 <= val <= max_bitrate): raise ValueError
        except:
            return await interaction.response.send_message(f"❌ Bitrate không hợp lệ! (8-{channel.guild.bitrate_limit//1000})", ephemeral=True)
        await channel.edit(bitrate=val * 1000)
        state_all = load_vc_state(); state = state_all.get(str(channel.id), {})
        owner = channel.guild.get_member(state.get("owner_id"))
        view = VoicePanelView(channel.id)
        await interaction.response.edit_message(embed=build_panel_embed(channel, owner, state), view=view)


class TransferSelect(discord.ui.UserSelect):
    def __init__(self, channel_id: int, members: list):
        super().__init__(placeholder="Chọn thành viên...", min_values=1, max_values=1)
        self.channel_id = channel_id
    async def callback(self, interaction: discord.Interaction):
        channel = bot.get_channel(self.channel_id)
        if not channel: return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        new_owner = self.values[0]
        state_all = load_vc_state(); state = state_all.get(str(channel.id), {})
        state["owner_id"] = new_owner.id
        state_all[str(channel.id)] = state
        save_vc_state(state_all)
        await interaction.response.send_message(f"✅ Đã chuyển quyền chủ kênh cho {new_owner.mention}!", ephemeral=True)
        # cập nhật panel nếu còn tồn tại
        await voice_manager.refresh_panel(channel)


class KickSelect(discord.ui.UserSelect):
    def __init__(self, channel_id: int, members: list):
        super().__init__(placeholder="Chọn thành viên...", min_values=1, max_values=1)
        self.channel_id = channel_id
    async def callback(self, interaction: discord.Interaction):
        channel = bot.get_channel(self.channel_id)
        if not channel: return await interaction.response.send_message("❌ Kênh không còn tồn tại!", ephemeral=True)
        target = self.values[0]
        member = channel.guild.get_member(target.id)
        if member and member.voice and member.voice.channel == channel:
            await member.move_to(None)
            await interaction.response.send_message(f"✅ Đã kick {target.mention} khỏi kênh!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Thành viên không còn trong kênh!", ephemeral=True)


class VoiceManagerImpl:
    """
    Tự động phát hiện MỌI kênh voice mới được tạo trong server (kể cả qua nút
    "Create Channel" có sẵn của Discord, không chỉ qua hub do bot tạo), rồi
    gửi panel điều khiển ngay khi có người đầu tiên vào kênh đó.

    Cách hoạt động:
    - on_guild_channel_create: ghi nhớ kênh voice vừa tạo (chưa gửi panel vội,
      vì lúc này channel có thể chưa có ai / people chưa join xong)
    - on_voice_state_update: khi phát hiện có người vào 1 kênh voice mà kênh đó
      "mới tinh" (chưa từng có panel, và không phải kênh vĩnh viễn/hub cấu hình
      riêng) → gán người đó làm chủ, gửi panel lần đầu
    - Khi kênh trống lại (0 người thật) → xoá state (không xoá kênh, vì đây là
      kênh Discord tự quản lý qua tính năng Create Channel, nó tự dọn hoặc giữ
      tuỳ cấu hình server, bot không nên tự ý xoá kênh gốc)
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Cache các channel ID KHÔNG áp dụng panel (kênh vĩnh viễn treo voice, v.v.)
        self._excluded_ids: set[int] = set()

    def _is_excluded(self, channel_id: int) -> bool:
        if channel_id == bot.permanent_channel_id:
            return True
        return channel_id in self._excluded_ids

    async def handle_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        guild = member.guild

        # ── Có người vào 1 kênh voice ──────────────────────────────────────────
        if after.channel and after.channel != before.channel:
            channel = after.channel
            if not self._is_excluded(channel.id):
                state_all = load_vc_state()
                key = str(channel.id)
                if key not in state_all:
                    # Kênh này chưa từng có panel → coi là kênh mới, gán panel lần đầu
                    await self._init_panel(channel, member)

        # ── Rời khỏi 1 kênh đang được quản lý → nếu trống thì dọn state ───────
        if before.channel and before.channel != after.channel:
            state_all = load_vc_state()
            key = str(before.channel.id)
            if key in state_all:
                real_members = [m for m in before.channel.members if not m.bot]
                if len(real_members) == 0:
                    await self._cleanup_channel(before.channel)

    async def _init_panel(self, channel: discord.VoiceChannel, first_member: discord.Member):
        """Gán chủ kênh = người đầu tiên vào, gửi panel lần đầu."""
        state_all = load_vc_state()
        state_all[str(channel.id)] = {
            "owner_id": first_member.id,
            "panel_message_id": None,
            "locked": False,
            "hidden": False,
        }
        save_vc_state(state_all)
        await self._send_panel(channel, first_member)
        log.info(f"🆕 Phát hiện kênh mới: {channel.name} — chủ: {first_member}")

    async def _cleanup_channel(self, channel: discord.VoiceChannel):
        """Kênh trống — dọn dữ liệu panel. Không xoá kênh vì đây là kênh do
        tính năng Create Channel gốc của Discord quản lý vòng đời."""
        state_all = load_vc_state()
        state_all.pop(str(channel.id), None)
        save_vc_state(state_all)
        log.info(f"🧹 Dọn dữ liệu panel: {channel.name} (kênh trống)")

    async def _send_panel(self, channel: discord.VoiceChannel, owner: discord.Member):
        try:
            state_all = load_vc_state()
            state = state_all.get(str(channel.id), {})
            embed = build_panel_embed(channel, owner, state)
            view = VoicePanelView(channel.id)
            msg = await channel.send(embed=embed, view=view)
            state["panel_message_id"] = msg.id
            state_all[str(channel.id)] = state
            save_vc_state(state_all)
        except discord.Forbidden:
            log.error(f"❌ Bot thiếu quyền gửi tin nhắn trong #{channel.name}")
        except Exception as e:
            log.error(f"❌ Lỗi gửi panel: {e}")

    async def repost_panel(self, channel: discord.VoiceChannel):
        """Xoá panel cũ, gửi panel mới xuống dưới cùng — gọi khi có tin nhắn mới."""
        state_all = load_vc_state()
        state = state_all.get(str(channel.id))
        if not state: return

        owner = channel.guild.get_member(state.get("owner_id"))
        if not owner: return

        old_msg_id = state.get("panel_message_id")
        if old_msg_id:
            try:
                old_msg = await channel.fetch_message(old_msg_id)
                await old_msg.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        embed = build_panel_embed(channel, owner, state)
        view = VoicePanelView(channel.id)
        msg = await channel.send(embed=embed, view=view)
        state["panel_message_id"] = msg.id
        state_all[str(channel.id)] = state
        save_vc_state(state_all)

    async def refresh_panel(self, channel: discord.VoiceChannel):
        state_all = load_vc_state()
        state = state_all.get(str(channel.id))
        if not state or not state.get("panel_message_id"): return
        try:
            msg = await channel.fetch_message(state["panel_message_id"])
            owner = channel.guild.get_member(state.get("owner_id"))
            view = VoicePanelView(channel.id)
            await msg.edit(embed=build_panel_embed(channel, owner, state), view=view)
        except (discord.NotFound, discord.Forbidden):
            pass

    def is_temp_channel(self, channel_id: int) -> bool:
        state_all = load_vc_state()
        return str(channel_id) in state_all

    def exclude_channel(self, channel_id: int):
        """Đánh dấu 1 kênh KHÔNG bao giờ nhận panel (dùng cho kênh vĩnh viễn treo voice)."""
        self._excluded_ids.add(channel_id)


voice_manager = VoiceManagerImpl(bot)


# ── Lắng nghe chat trong voice channel tạm thời để re-post panel ─────────────
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    # Nếu tin nhắn được gửi trong 1 voice channel đang được quản lý
    if isinstance(message.channel, discord.VoiceChannel) and voice_manager.is_temp_channel(message.channel.id):
        await voice_manager.repost_panel(message.channel)
    await bot.process_commands(message)


# ══════════════════════════════════════════════════════════════════════════════
#  SLASH COMMANDS — Voice Manager setup
# ══════════════════════════════════════════════════════════════════════════════
def is_admin():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)


@bot.tree.command(name="voice_exclude", description="[Admin] Loại trừ 1 kênh khỏi Voice Manager (không tự gửi panel)")
@app_commands.describe(kenh="Kênh voice cần loại trừ (vd: kênh AFK, kênh vĩnh viễn)")
@is_admin()
async def voice_exclude(interaction: discord.Interaction, kenh: discord.VoiceChannel):
    voice_manager.exclude_channel(kenh.id)
    await interaction.response.send_message(f"✅ Đã loại trừ {kenh.mention} khỏi Voice Manager!", ephemeral=True)


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
@voice_exclude.error
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

@bot.command(name="help", aliases=["h"])
async def help_cmd(ctx: commands.Context):
    embed = discord.Embed(title="📖 Danh sách lệnh", color=0x5865f2)
    embed.add_field(name="🔧 Lệnh chung", value="`+ping` — Kiểm tra bot\n`+help` — Danh sách lệnh", inline=False)
    embed.add_field(name="🎙️ Voice Manager",
        value="Tự động! Ai vào kênh voice mới (kể cả qua nút Create Channel gốc "
              "của Discord) sẽ tự nhận panel điều khiển ngay.\n"
              "`/voice_exclude` — Loại trừ 1 kênh khỏi Voice Manager *(Admin)*",
        inline=False)
    embed.add_field(name="👤 Profile (Slash)",
        value="`/profile @user` — Xem profile\n"
              "`/profile_set` — Tạo/sửa *(Admin)*\n"
              "`/profile_addphoto` — Thêm ảnh *(Admin)*\n"
              "`/profile_removephoto` — Xóa ảnh *(Admin)*\n"
              "`/profile_delete` — Xóa profile *(Admin)*",
        inline=False)
    embed.set_footer(text=f"Prefix: + | Bot: {bot.user}")
    await ctx.reply(embed=embed)


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
