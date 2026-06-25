import discord
import asyncio
import os
import logging
from aiohttp import web
from datetime import datetime, timezone

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("VoiceBot")

# ── Config ────────────────────────────────────────────────────────────────────
TOKEN          = os.environ["DISCORD_TOKEN"]
TARGET_GUILD   = int(os.environ.get("GUILD_ID", "0"))
TARGET_CHANNEL = int(os.environ.get("VOICE_CHANNEL_ID", "0"))  # kênh vĩnh viễn (tuỳ chọn)
DASHBOARD_PORT = int(os.environ.get("PORT", "8080"))
DASHBOARD_KEY  = os.environ.get("DASHBOARD_KEY", "changeme")
OWNER_ID       = int(os.environ.get("OWNER_ID", "852834067044630558"))

# ── Intents ───────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.guilds      = True
intents.voice_states = True
intents.members     = True


class VoiceBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.permanent_channel_id: int  = TARGET_CHANNEL  # kênh vĩnh viễn
        self.temp_channel_id: int       = 0               # kênh tạm thời đang giữ
        self.auto_rejoin: bool          = True
        self.follow_owner: bool         = True
        self.start_time                 = datetime.now(timezone.utc)

    # ── Ready ──────────────────────────────────────────────────────────────────
    async def on_ready(self):
        log.info(f"✅ Đã đăng nhập: {self.user} (ID: {self.user.id})")
        log.info(f"📡 Đang phục vụ {len(self.guilds)} server")
        log.info(f"👤 Theo dõi chủ ID: {OWNER_ID}")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="🎙️ voice channel"
            )
        )
        # Join kênh vĩnh viễn lúc khởi động (nếu có cấu hình)
        if self.permanent_channel_id:
            await self._join_by_id(self.permanent_channel_id, label="kênh vĩnh viễn")

    # ── Voice state update ─────────────────────────────────────────────────────
    async def on_voice_state_update(self, member, before, after):

        # ── Bot bị kick/disconnect ─────────────────────────────────────────────
        if member == self.user:
            if before.channel and not after.channel:
                if self.auto_rejoin:
                    log.warning("⚠️  Bot bị disconnect, thử rejoin sau 3 giây...")
                    await asyncio.sleep(3)
                    # Ưu tiên rejoin kênh tạm thời trước, rồi mới kênh vĩnh viễn
                    rejoined = False
                    if self.temp_channel_id:
                        rejoined = await self._join_by_id(self.temp_channel_id, label="kênh tạm thời")
                    if not rejoined and self.permanent_channel_id:
                        await self._join_by_id(self.permanent_channel_id, label="kênh vĩnh viễn")
            return

        # ── Chủ join vào kênh voice ────────────────────────────────────────────
        if member.id == OWNER_ID and self.follow_owner:
            if after.channel and after.channel != before.channel:
                ch = after.channel
                log.info(f"👤 Chủ vào #{ch.name} — bot follow theo")

                # Phân loại: kênh tạm thời hay vĩnh viễn?
                is_temp = self._is_temp_channel(ch)
                if is_temp:
                    self.temp_channel_id = ch.id
                    log.info(f"🔄 Ghi nhận kênh tạm thời: #{ch.name} (ID={ch.id})")
                else:
                    self.permanent_channel_id = ch.id
                    log.info(f"📌 Ghi nhận kênh vĩnh viễn: #{ch.name} (ID={ch.id})")

                await self._join_channel(ch)

            # Chủ rời voice → bot ở lại giữ kênh (không làm gì)
            if before.channel and not after.channel:
                log.info(f"👤 Chủ rời #{before.channel.name} — bot ở lại giữ kênh")

        # ── Kênh tạm thời trống (chỉ còn bot) → xóa kênh tạm thời ID ──────────
        if before.channel and before.channel.id == self.temp_channel_id:
            real_members = [m for m in before.channel.members if not m.bot]
            if len(real_members) == 0:
                # Kênh tạm thời không còn người thật
                # Bot vẫn ở lại — đây là mục đích chính (giữ kênh tồn tại)
                log.info(f"🏠 Chỉ còn bot trong #{before.channel.name} — đang giữ kênh tạm thời")

    # ── Kiểm tra kênh có phải tạm thời không ─────────────────────────────────
    def _is_temp_channel(self, channel: discord.VoiceChannel) -> bool:
        # Kênh tạm thời thường: user_limit nhỏ, hoặc tên chứa số/emoji/tên người
        # Cách đơn giản nhất: nếu không phải kênh vĩnh viễn đã biết thì coi là tạm
        if channel.id == self.permanent_channel_id:
            return False
        # Kênh được tạo bởi bot "create a voice channel" thường có category đặc biệt
        # Hoặc đơn giản: tất cả kênh chủ join mà không phải kênh vĩnh viễn → tạm thời
        return True

    # ── Join kênh theo ID ──────────────────────────────────────────────────────
    async def _join_by_id(self, channel_id: int, label: str = "") -> bool:
        channel = self.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            log.error(f"❌ Không tìm thấy {label} ID={channel_id}")
            return False
        return await self._join_channel(channel)

    # ── Join kênh voice ────────────────────────────────────────────────────────
    async def _join_channel(self, channel: discord.VoiceChannel) -> bool:
        guild = channel.guild
        vc = guild.voice_client
        try:
            if vc:
                await vc.move_to(channel)
                log.info(f"➡️  Đã chuyển sang: #{channel.name}")
            else:
                await channel.connect(self_deaf=True, self_mute=True)
                log.info(f"🎙️  Đã join: #{channel.name} trong '{guild.name}'")
            return True
        except Exception as e:
            log.error(f"❌ Lỗi join voice: {e}")
            return False

    # ── Leave tất cả ──────────────────────────────────────────────────────────
    async def leave_all_voice(self):
        for vc in self.voice_clients:
            await vc.disconnect(force=True)
            log.info(f"👋 Đã rời voice trong '{vc.guild.name}'")
        self.temp_channel_id = 0

    # ── Trạng thái ────────────────────────────────────────────────────────────
    def get_status(self):
        voice_info = []
        for vc in self.voice_clients:
            voice_info.append({
                "guild":   vc.guild.name,
                "channel": vc.channel.name,
                "members": len([m for m in vc.channel.members if not m.bot]),
            })
        uptime = datetime.now(timezone.utc) - self.start_time
        h, rem = divmod(int(uptime.total_seconds()), 3600)
        m, s   = divmod(rem, 60)
        return {
            "online":            self.is_ready(),
            "bot_name":          str(self.user) if self.user else "—",
            "uptime":            f"{h}h {m}m {s}s",
            "auto_rejoin":       self.auto_rejoin,
            "follow_owner":      self.follow_owner,
            "voice":             voice_info,
            "permanent_channel": self.permanent_channel_id,
            "temp_channel":      self.temp_channel_id,
        }


# ── Khởi tạo bot ──────────────────────────────────────────────────────────────
bot = VoiceBot()

# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD HTTP API
# ══════════════════════════════════════════════════════════════════════════════
routes = web.RouteTableDef()

def check_key(request):
    return request.headers.get("X-API-Key") == DASHBOARD_KEY

@routes.get("/")
async def index(_):
    return web.Response(text="Discord Voice Bot is running ✅", content_type="text/plain")

@routes.get("/status")
async def status(request):
    if not check_key(request): raise web.HTTPUnauthorized(text="Invalid API key")
    return web.json_response(bot.get_status())

@routes.post("/join")
async def join(request):
    if not check_key(request): raise web.HTTPUnauthorized(text="Invalid API key")
    body = await request.json()
    channel_id = int(body.get("channel_id", 0))
    channel = bot.get_channel(channel_id)
    if channel:
        is_temp = bot._is_temp_channel(channel)
        if is_temp:
            bot.temp_channel_id = channel_id
        else:
            bot.permanent_channel_id = channel_id
    ok = await bot._join_by_id(channel_id, label="kênh được chọn")
    return web.json_response({"success": ok})

@routes.post("/leave")
async def leave(request):
    if not check_key(request): raise web.HTTPUnauthorized(text="Invalid API key")
    await bot.leave_all_voice()
    return web.json_response({"success": True})

@routes.post("/auto_rejoin")
async def toggle_rejoin(request):
    if not check_key(request): raise web.HTTPUnauthorized(text="Invalid API key")
    body = await request.json()
    bot.auto_rejoin = bool(body.get("enabled", True))
    return web.json_response({"auto_rejoin": bot.auto_rejoin})

@routes.post("/follow_owner")
async def toggle_follow(request):
    if not check_key(request): raise web.HTTPUnauthorized(text="Invalid API key")
    body = await request.json()
    bot.follow_owner = bool(body.get("enabled", True))
    log.info(f"👤 Follow chủ: {'BẬT' if bot.follow_owner else 'TẮT'}")
    return web.json_response({"follow_owner": bot.follow_owner})

@routes.get("/channels")
async def channels(request):
    if not check_key(request): raise web.HTTPUnauthorized(text="Invalid API key")
    result = []
    for guild in bot.guilds:
        for ch in guild.voice_channels:
            result.append({
                "guild_id":     guild.id,
                "guild_name":   guild.name,
                "channel_id":   ch.id,
                "channel_name": ch.name,
                "members":      len([m for m in ch.members if not m.bot]),
            })
    return web.json_response(result)


async def run_web():
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", DASHBOARD_PORT)
    await site.start()
    log.info(f"🌐 Dashboard API chạy tại port {DASHBOARD_PORT}")


async def main():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(run_web())
        tg.create_task(bot.start(TOKEN))


if __name__ == "__main__":
    asyncio.run(main())
