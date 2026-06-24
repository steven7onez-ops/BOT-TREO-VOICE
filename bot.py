import discord
import asyncio
import os
import logging
from aiohttp import web
import json
from datetime import datetime, timezone

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("VoiceBot")

# ── Config từ biến môi trường ──────────────────────────────────────────────────
TOKEN          = os.environ["DISCORD_TOKEN"]
TARGET_GUILD   = int(os.environ.get("GUILD_ID", "0"))       # ID server
TARGET_CHANNEL = int(os.environ.get("VOICE_CHANNEL_ID", "0"))  # ID kênh voice
DASHBOARD_PORT = int(os.environ.get("PORT", "8080"))
DASHBOARD_KEY  = os.environ.get("DASHBOARD_KEY", "changeme")   # mật khẩu dashboard

# ── Bot intents ────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True

class VoiceBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.target_channel_id: int = TARGET_CHANNEL
        self.auto_rejoin: bool = True
        self.start_time = datetime.now(timezone.utc)

    # ── Sự kiện ready ─────────────────────────────────────────────────────────
    async def on_ready(self):
        log.info(f"✅ Đã đăng nhập: {self.user} (ID: {self.user.id})")
        log.info(f"📡 Đang phục vụ {len(self.guilds)} server")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="🎙️ voice channel"
            )
        )
        if self.target_channel_id:
            await self.join_target_channel()

    # ── Tự động rejoin nếu bị kick khỏi voice ─────────────────────────────────
    async def on_voice_state_update(self, member, before, after):
        if member != self.user:
            return
        # Bot bị disconnect khỏi voice
        if before.channel and not after.channel:
            if self.auto_rejoin and self.target_channel_id:
                log.warning("⚠️  Bot bị disconnect, đang rejoin sau 3 giây...")
                await asyncio.sleep(3)
                await self.join_target_channel()

    # ── Join kênh voice ────────────────────────────────────────────────────────
    async def join_target_channel(self):
        channel = self.get_channel(self.target_channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            log.error(f"❌ Không tìm thấy voice channel ID={self.target_channel_id}")
            return False
        # Nếu đang trong kênh khác → move; nếu chưa → join
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
            log.error(f"❌ Lỗi khi join voice: {e}")
            return False

    # ── Leave tất cả voice ─────────────────────────────────────────────────────
    async def leave_all_voice(self):
        for vc in self.voice_clients:
            await vc.disconnect(force=True)
            log.info(f"👋 Đã rời voice trong '{vc.guild.name}'")

    # ── Lấy trạng thái hiện tại ───────────────────────────────────────────────
    def get_status(self):
        voice_info = []
        for vc in self.voice_clients:
            voice_info.append({
                "guild":   vc.guild.name,
                "channel": vc.channel.name,
                "members": len(vc.channel.members) - 1,  # trừ chính bot
            })
        uptime = datetime.now(timezone.utc) - self.start_time
        h, rem = divmod(int(uptime.total_seconds()), 3600)
        m, s   = divmod(rem, 60)
        return {
            "online":      self.is_ready(),
            "bot_name":    str(self.user) if self.user else "—",
            "uptime":      f"{h}h {m}m {s}s",
            "auto_rejoin": self.auto_rejoin,
            "voice":       voice_info,
            "target_id":   self.target_channel_id,
        }


# ── Khởi tạo bot ──────────────────────────────────────────────────────────────
bot = VoiceBot()

# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD HTTP API  (aiohttp)
# ══════════════════════════════════════════════════════════════════════════════
routes = web.RouteTableDef()

def check_key(request: web.Request) -> bool:
    return request.headers.get("X-API-Key") == DASHBOARD_KEY

@routes.get("/")
async def index(_):
    return web.Response(text="Discord Voice Bot is running ✅", content_type="text/plain")

@routes.get("/status")
async def status(request):
    if not check_key(request):
        raise web.HTTPUnauthorized(text="Invalid API key")
    return web.json_response(bot.get_status())

@routes.post("/join")
async def join(request):
    if not check_key(request):
        raise web.HTTPUnauthorized(text="Invalid API key")
    body = await request.json()
    channel_id = int(body.get("channel_id", bot.target_channel_id))
    bot.target_channel_id = channel_id
    ok = await bot.join_target_channel()
    return web.json_response({"success": ok})

@routes.post("/leave")
async def leave(request):
    if not check_key(request):
        raise web.HTTPUnauthorized(text="Invalid API key")
    await bot.leave_all_voice()
    return web.json_response({"success": True})

@routes.post("/set_channel")
async def set_channel(request):
    if not check_key(request):
        raise web.HTTPUnauthorized(text="Invalid API key")
    body = await request.json()
    bot.target_channel_id = int(body["channel_id"])
    return web.json_response({"channel_id": bot.target_channel_id})

@routes.post("/auto_rejoin")
async def toggle_rejoin(request):
    if not check_key(request):
        raise web.HTTPUnauthorized(text="Invalid API key")
    body = await request.json()
    bot.auto_rejoin = bool(body.get("enabled", True))
    return web.json_response({"auto_rejoin": bot.auto_rejoin})

# ── Danh sách voice channel trong server ──────────────────────────────────────
@routes.get("/channels")
async def channels(request):
    if not check_key(request):
        raise web.HTTPUnauthorized(text="Invalid API key")
    result = []
    for guild in bot.guilds:
        for ch in guild.voice_channels:
            result.append({
                "guild_id":    guild.id,
                "guild_name":  guild.name,
                "channel_id":  ch.id,
                "channel_name": ch.name,
                "members":     len(ch.members),
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
