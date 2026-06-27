import discord
from discord import app_commands
from discord.ext import commands
import asyncio, os, logging, json
from aiohttp import web
from datetime import datetime, timezone
from pathlib import Path

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("VoiceBot")

# ── Config ────────────────────────────────────────────────────────────────────
TOKEN          = os.environ["DISCORD_TOKEN"]
TARGET_GUILD   = int(os.environ.get("GUILD_ID", "0"))
TARGET_CHANNEL = int(os.environ.get("VOICE_CHANNEL_ID", "0"))
DASHBOARD_PORT = int(os.environ.get("PORT", "8080"))
DASHBOARD_KEY  = os.environ.get("DASHBOARD_KEY", "changeme")
OWNER_ID       = int(os.environ.get("OWNER_ID", "852834067044630558"))
DATA_FILE      = Path("/tmp/profiles.json")

# ── Profile DB ────────────────────────────────────────────────────────────────
def load_db() -> dict:
    if DATA_FILE.exists():
        try: return json.loads(DATA_FILE.read_text())
        except: pass
    return {}

def save_db(db: dict):
    DATA_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2))

# ── Intents ───────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.guilds       = True
intents.voice_states = True
intents.members      = True
intents.message_content = True

# ── Bot ───────────────────────────────────────────────────────────────────────
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

    async def on_voice_state_update(self, member, before, after):
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

# ══════════════════════════════════════════════════════════════════════════════
#  PROFILE VIEW — Embed + Buttons
# ══════════════════════════════════════════════════════════════════════════════
def make_stars(rating: float) -> str:
    full = int(rating); half = 1 if rating - full >= 0.5 else 0; empty = 5 - full - half
    return "⭐" * full + ("✨" if half else "") + "☆" * empty

def build_embed(profile: dict, member: discord.Member, page: int) -> discord.Embed:
    photos = profile.get("photos", [])
    tags   = profile.get("tags", [])
    rating = profile.get("rating", 0)
    votes  = profile.get("votes", {})
    total  = len(votes)
    name   = profile.get("display_name") or member.display_name

    embed = discord.Embed(color=0x5865f2)
    embed.set_author(name=f"✦ {name}", icon_url=member.display_avatar.url)

    # Tags
    if tags:
        embed.description = "\n".join(f"✦ {t}" for t in tags)

    # Rating
    avg = round(rating, 1)
    embed.add_field(name="⭐ Đánh giá", value=f"{make_stars(avg)} **{avg}**/5.0\n`{total} lượt vote`", inline=True)

    # Ảnh
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
        self.user_id = user_id
        self.member  = member
        self.page    = 0
        self._update_buttons()

    def _profile(self): return load_db().get(self.user_id, {})

    def _update_buttons(self):
        photos = self._profile().get("photos", [])
        total  = len(photos)
        for child in self.children:
            if hasattr(child, "custom_id"):
                if child.custom_id == "prev": child.disabled = self.page <= 0
                if child.custom_id == "next": child.disabled = self.page >= total - 1
                if child.custom_id == "page_label": child.label = f"{self.page+1}/{max(total,1)}"

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.secondary, custom_id="prev")
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=build_embed(self._profile(), self.member, self.page), view=self)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, custom_id="page_label", disabled=True)
    async def page_label(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        photos = self._profile().get("photos", [])
        self.page = min(len(photos) - 1, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=build_embed(self._profile(), self.member, self.page), view=self)

    @discord.ui.button(label="⭐ Đánh giá", style=discord.ButtonStyle.primary, custom_id="rate_btn")
    async def rate_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RateModal(self.user_id, self.member, self))


class RateModal(discord.ui.Modal, title="Đánh giá thành viên"):
    score = discord.ui.TextInput(
        label="Số điểm (1-5)",
        placeholder="Nhập số từ 1 đến 5 (vd: 4.5)",
        max_length=3, required=True
    )

    def __init__(self, user_id: str, member: discord.Member, view: ProfileView):
        super().__init__()
        self.user_id = user_id
        self.member  = member
        self.pview   = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = float(str(self.score).replace(",", "."))
            if not (1 <= val <= 5): raise ValueError
        except:
            await interaction.response.send_message("❌ Điểm không hợp lệ! Nhập số từ 1 đến 5.", ephemeral=True); return

        voter = str(interaction.user.id)
        if voter == self.user_id:
            await interaction.response.send_message("❌ Không thể tự đánh giá bản thân!", ephemeral=True); return

        db = load_db()
        p  = db.setdefault(self.user_id, {})
        p.setdefault("votes", {})[voter] = val
        votes = p["votes"]
        p["rating"] = round(sum(votes.values()) / len(votes), 2)
        save_db(db)

        self.pview._update_buttons()
        await interaction.response.edit_message(embed=build_embed(p, self.member, self.pview.page), view=self.pview)
        log.info(f"⭐ {interaction.user} đánh giá {self.member}: {val}/5")


# ══════════════════════════════════════════════════════════════════════════════
#  SLASH COMMANDS
# ══════════════════════════════════════════════════════════════════════════════
def is_admin():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.manage_guild or \
               interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)


# ── Prefix commands ────────────────────────────────────────────────────────────
@bot.command(name="ping")
async def ping(ctx: commands.Context):
    ms = round(bot.latency * 1000)
    uptime = datetime.now(timezone.utc) - bot.start_time
    h, rem = divmod(int(uptime.total_seconds()), 3600); m, s = divmod(rem, 60)
    voice_ch = ""
    if bot.voice_clients:
        vc = bot.voice_clients[0]
        voice_ch = f"🎙️ **#{vc.channel.name}** ({vc.guild.name})"
    else:
        voice_ch = "❌ Chưa vào kênh nào"
    embed = discord.Embed(title="🏓 Pong!", color=0x5865f2)
    embed.add_field(name="📶 Độ trễ",  value=f"`{ms}ms`",          inline=True)
    embed.add_field(name="⏱️ Uptime",  value=f"`{h}h {m}m {s}s`", inline=True)
    embed.add_field(name="🎙️ Voice",   value=voice_ch,             inline=False)
    embed.set_footer(text=f"Bot: {bot.user}", icon_url=bot.user.display_avatar.url)
    await ctx.reply(embed=embed)

@bot.command(name="help", aliases=["h"])
async def help_cmd(ctx: commands.Context):
    embed = discord.Embed(title="📖 Danh sách lệnh", color=0x5865f2)
    embed.add_field(name="🔧 Lệnh chung",
        value="`+ping` — Kiểm tra bot còn sống không\n`+help` — Xem danh sách lệnh",
        inline=False)
    embed.add_field(name="🎵 Nhạc",
        value="`+play [tên/link]` — Phát nhạc từ YouTube\n"
              "`+skip` — Bỏ qua bài hiện tại\n"
              "`+queue` (`+q`) — Xem hàng đợi\n"
              "`+nowplaying` (`+np`) — Bài đang phát\n"
              "`+pause` / `+resume` — Tạm dừng / Tiếp tục\n"
              "`+volume [0-150]` (`+vol`) — Chỉnh âm lượng\n"
              "`+remove [số]` — Xóa bài khỏi hàng đợi\n"
              "`+stop` — Dừng nhạc & xóa hàng đợi",
        inline=False)
    embed.add_field(name="👤 Profile",
        value="`+profile @user` (`+p`) — Xem profile thành viên\n"
              "`+profile_set @user ten:Tên tags:Tag1 | Tag2` (`+pset`) — Tạo/sửa *(Admin)*\n"
              "`+profile_addphoto @user https://url` (`+padd`) — Thêm ảnh *(Admin)*\n"
              "`+profile_removephoto @user 1` (`+pdel`) — Xóa ảnh *(Admin)*\n"
              "`+profile_delete @user` (`+pdelete`) — Xóa profile *(Admin)*",
        inline=False)
    embed.set_footer(text=f"Prefix: + | Bot: {bot.user}")
    await ctx.reply(embed=embed)


# ── Profile prefix commands ────────────────────────────────────────────────────
@bot.command(name="profile", aliases=["p"])
async def profile_cmd(ctx: commands.Context, thanh_vien: discord.Member = None):
    if not thanh_vien:
        await ctx.reply("❌ Cú pháp: `+profile @user`"); return
    uid = str(thanh_vien.id)
    db  = load_db()
    if uid not in db:
        await ctx.reply(f"❌ **{thanh_vien.display_name}** chưa có profile."); return
    view = ProfileView(uid, thanh_vien)
    embed = build_embed(db[uid], thanh_vien, 0)
    await ctx.reply(embed=embed, view=view)


@bot.command(name="profile_set", aliases=["pset"])
@commands.has_permissions(manage_guild=True)
async def profile_set(ctx: commands.Context, thanh_vien: discord.Member = None, *, args: str = ""):
    if not thanh_vien:
        await ctx.reply("❌ Cú pháp: `+profile_set @user ten:Tên | tags:Tag1 | Tag2`"); return
    uid = str(thanh_vien.id)
    db  = load_db()
    p   = db.setdefault(uid, {})
    # Parse: ten:Tên tags:Tag1 | Tag2 | Tag3
    ten = ""; tags_raw = ""
    if "tags:" in args:
        parts = args.split("tags:", 1)
        ten_part = parts[0].strip()
        tags_raw = parts[1].strip()
        if "ten:" in ten_part:
            ten = ten_part.replace("ten:", "").strip()
    elif "ten:" in args:
        ten = args.replace("ten:", "").strip()
    if ten: p["display_name"] = ten
    if tags_raw:
        p["tags"] = [t.strip() for t in tags_raw.split("|") if t.strip()]
    save_db(db)
    await ctx.reply(f"✅ Đã cập nhật profile của **{thanh_vien.display_name}**!")


@bot.command(name="profile_addphoto", aliases=["pphoto", "padd"])
@commands.has_permissions(manage_guild=True)
async def profile_addphoto(ctx: commands.Context, thanh_vien: discord.Member = None, *, url_anh: str = ""):
    if not thanh_vien or not url_anh:
        await ctx.reply("❌ Cú pháp: `+profile_addphoto @user https://link-anh.jpg`"); return
    if not url_anh.startswith("http"):
        await ctx.reply("❌ URL không hợp lệ!"); return
    uid = str(thanh_vien.id)
    db  = load_db()
    p   = db.setdefault(uid, {})
    p.setdefault("photos", []).append(url_anh)
    save_db(db)
    total = len(p["photos"])
    await ctx.reply(f"✅ Đã thêm ảnh #{total} cho **{thanh_vien.display_name}**!")


@bot.command(name="profile_removephoto", aliases=["premove", "pdel"])
@commands.has_permissions(manage_guild=True)
async def profile_removephoto(ctx: commands.Context, thanh_vien: discord.Member = None, so_thu_tu: int = 0):
    if not thanh_vien or not so_thu_tu:
        await ctx.reply("❌ Cú pháp: `+profile_removephoto @user 1`"); return
    uid = str(thanh_vien.id)
    db  = load_db()
    p   = db.get(uid, {})
    photos = p.get("photos", [])
    if not photos or so_thu_tu < 1 or so_thu_tu > len(photos):
        await ctx.reply("❌ Số thứ tự không hợp lệ!"); return
    photos.pop(so_thu_tu - 1)
    save_db(db)
    await ctx.reply(f"✅ Đã xóa ảnh #{so_thu_tu} của **{thanh_vien.display_name}**!")


@bot.command(name="profile_delete", aliases=["pdelete"])
@commands.has_permissions(manage_guild=True)
async def profile_delete(ctx: commands.Context, thanh_vien: discord.Member = None):
    if not thanh_vien:
        await ctx.reply("❌ Cú pháp: `+profile_delete @user`"); return
    uid = str(thanh_vien.id)
    db  = load_db()
    if uid not in db:
        await ctx.reply("❌ Thành viên này chưa có profile."); return
    del db[uid]
    save_db(db)
    await ctx.reply(f"✅ Đã xóa profile của **{thanh_vien.display_name}**!")


# Error handler cho prefix commands
@profile_set.error
@profile_addphoto.error
@profile_removephoto.error
@profile_delete.error
async def admin_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("❌ Bạn cần quyền **Quản lý server** để dùng lệnh này!")


# ══════════════════════════════════════════════════════════════════════════════
#  MUSIC SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
import yt_dlp
from collections import deque

YTDL_OPTS = {
    'format': 'bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extractor_args': {'youtube': {'player_client': ['ios']}},
    'http_headers': {
        'User-Agent': 'com.google.ios.youtube/19.29.1 (iPhone16,2; U; CPU iOS 17_5_1 like Mac OS X;)',
    },
}
FFMPEG_OPTS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

music_queues: dict = {}
now_playing:  dict = {}

def get_queue(guild_id):
    if guild_id not in music_queues:
        music_queues[guild_id] = deque()
    return music_queues[guild_id]

async def search_yt(query: str):
    loop = asyncio.get_event_loop()
    def _search():
        # Ghi cookies từ biến môi trường ra file tạm nếu có
        import tempfile, os
        cookies_content = os.environ.get("YOUTUBE_COOKIES", "")
        opts = dict(YTDL_OPTS)
        if cookies_content:
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
            tmp.write(cookies_content)
            tmp.close()
            opts['cookiefile'] = tmp.name
            log.info(f"🍪 Dùng cookies từ env var")
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(query, download=False)
                if 'entries' in info: info = info['entries'][0]
                return {'url': info['url'], 'title': info.get('title','Không rõ'),
                        'duration': info.get('duration',0), 'webpage': info.get('webpage_url',''),
                        'thumbnail': info.get('thumbnail',''), 'uploader': info.get('uploader','')}
            except Exception as e:
                log.error(f"yt-dlp: {e}"); return None
            finally:
                if cookies_content:
                    try: os.unlink(opts['cookiefile'])
                    except: pass
    return await loop.run_in_executor(None, _search)

def fmt_dur(sec):
    if not sec: return '?:??'
    m, s = divmod(sec, 60); h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def play_next(guild_id, vc):
    q = get_queue(guild_id)
    if not q: now_playing.pop(guild_id, None); return
    track = q.popleft()
    now_playing[guild_id] = track
    src = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(track['url'], **FFMPEG_OPTS), volume=0.7)
    def after(err):
        if err: log.error(f"Player: {err}")
        asyncio.run_coroutine_threadsafe(_play_after(guild_id), bot.loop)
    vc.play(src, after=after)

async def _play_after(guild_id):
    guild = bot.get_guild(guild_id)
    if not guild: return
    vc = guild.voice_client
    if vc and not vc.is_playing(): play_next(guild_id, vc)

@bot.command(name="play", aliases=["ph"])
async def play_cmd(ctx: commands.Context, *, query: str = ""):
    if not query: await ctx.reply("❌ Cú pháp: `+play [tên bài/link YouTube]`"); return
    if not ctx.author.voice: await ctx.reply("❌ Bạn cần vào kênh voice trước!"); return
    vc = ctx.guild.voice_client
    if not vc: vc = await ctx.author.voice.channel.connect()
    elif vc.channel != ctx.author.voice.channel: await vc.move_to(ctx.author.voice.channel)
    msg = await ctx.reply("🔍 Đang tìm kiếm...")
    track = await search_yt(query)
    if not track: await msg.edit(content="❌ Không tìm thấy bài hát!"); return
    track['requester'] = ctx.author.display_name
    q = get_queue(ctx.guild.id)
    if vc.is_playing() or vc.is_paused():
        q.append(track)
        embed = discord.Embed(title="➕ Thêm vào hàng đợi", description=f"[{track['title']}]({track['webpage']})", color=0x5865f2)
        embed.add_field(name="⏱️", value=fmt_dur(track['duration']), inline=True)
        embed.add_field(name="📋 Vị trí", value=f"#{len(q)}", inline=True)
        embed.add_field(name="👤", value=track['requester'], inline=True)
        if track['thumbnail']: embed.set_thumbnail(url=track['thumbnail'])
        await msg.edit(content=None, embed=embed)
    else:
        q.appendleft(track)
        play_next(ctx.guild.id, vc)
        embed = discord.Embed(title="▶️ Đang phát", description=f"[{track['title']}]({track['webpage']})", color=0x3ba55d)
        embed.add_field(name="⏱️", value=fmt_dur(track['duration']), inline=True)
        embed.add_field(name="👤", value=track['requester'], inline=True)
        if track['thumbnail']: embed.set_thumbnail(url=track['thumbnail'])
        await msg.edit(content=None, embed=embed)

@bot.command(name="skip", aliases=["s", "next"])
async def skip_cmd(ctx: commands.Context):
    vc = ctx.guild.voice_client
    if not vc or not vc.is_playing(): await ctx.reply("❌ Không có bài nào đang phát!"); return
    vc.stop(); await ctx.reply("⏭️ Đã bỏ qua!")

@bot.command(name="queue", aliases=["q", "ds"])
async def queue_cmd(ctx: commands.Context):
    q = get_queue(ctx.guild.id); current = now_playing.get(ctx.guild.id)
    if not current and not q: await ctx.reply("📋 Hàng đợi trống!"); return
    embed = discord.Embed(title="📋 Hàng đợi nhạc", color=0x5865f2)
    if current:
        embed.add_field(name="▶️ Đang phát", value=f"[{current['title']}]({current['webpage']}) `{fmt_dur(current['duration'])}` — {current.get('requester','')}", inline=False)
    if q:
        lines = [f"`{i}.` [{t['title']}]({t['webpage']}) `{fmt_dur(t['duration'])}` — {t.get('requester','')}" for i,t in enumerate(list(q)[:10],1)]
        if len(q)>10: lines.append(f"*... và {len(q)-10} bài nữa*")
        embed.add_field(name=f"⏳ Hàng đợi ({len(q)} bài)", value="\n".join(lines), inline=False)
    await ctx.reply(embed=embed)

@bot.command(name="pause")
async def pause_cmd(ctx: commands.Context):
    vc = ctx.guild.voice_client
    if vc and vc.is_playing(): vc.pause(); await ctx.reply("⏸️ Đã tạm dừng!")
    else: await ctx.reply("❌ Không có bài nào đang phát!")

@bot.command(name="resume", aliases=["tieptuc"])
async def resume_cmd(ctx: commands.Context):
    vc = ctx.guild.voice_client
    if vc and vc.is_paused(): vc.resume(); await ctx.reply("▶️ Tiếp tục phát!")
    else: await ctx.reply("❌ Nhạc không bị tạm dừng!")

@bot.command(name="stop", aliases=["dung"])
async def stop_cmd(ctx: commands.Context):
    q = get_queue(ctx.guild.id); q.clear(); now_playing.pop(ctx.guild.id, None)
    vc = ctx.guild.voice_client
    if vc: vc.stop()
    await ctx.reply("⏹️ Đã dừng nhạc và xóa hàng đợi!")

@bot.command(name="nowplaying", aliases=["np", "dangphat"])
async def np_cmd(ctx: commands.Context):
    current = now_playing.get(ctx.guild.id)
    if not current: await ctx.reply("❌ Không có bài nào đang phát!"); return
    embed = discord.Embed(title="▶️ Đang phát", description=f"[{current['title']}]({current['webpage']})", color=0x3ba55d)
    embed.add_field(name="⏱️", value=fmt_dur(current['duration']), inline=True)
    embed.add_field(name="👤", value=current.get('requester','?'), inline=True)
    if current['thumbnail']: embed.set_thumbnail(url=current['thumbnail'])
    await ctx.reply(embed=embed)

@bot.command(name="volume", aliases=["vol", "am"])
async def volume_cmd(ctx: commands.Context, vol: int = None):
    vc = ctx.guild.voice_client
    if not vc or not vc.source: await ctx.reply("❌ Không có bài nào đang phát!"); return
    if vol is None: await ctx.reply(f"🔊 Âm lượng: **{int(vc.source.volume*100)}%**"); return
    if not 0 <= vol <= 150: await ctx.reply("❌ Âm lượng từ 0-150!"); return
    vc.source.volume = vol/100; await ctx.reply(f"🔊 Âm lượng: **{vol}%**")

@bot.command(name="remove", aliases=["xoa2"])
async def remove_cmd(ctx: commands.Context, vi_tri: int = None):
    if not vi_tri: await ctx.reply("❌ Cú pháp: `+remove [số thứ tự]`"); return
    q = get_queue(ctx.guild.id)
    if vi_tri < 1 or vi_tri > len(q): await ctx.reply("❌ Số thứ tự không hợp lệ!"); return
    lst = list(q); removed = lst.pop(vi_tri-1)
    music_queues[ctx.guild.id] = deque(lst)
    await ctx.reply(f"🗑️ Đã xóa: **{removed['title']}**")


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD HTML
# ══════════════════════════════════════════════════════════════════════════════
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bot Treo Voice</title>
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
    <div class="auth-title">🎙️ Bot Treo Voice</div>
    <div class="auth-sub">Nhập mật khẩu dashboard để tiếp tục</div>
    <input class="inp" id="inp-key" type="password" placeholder="Mật khẩu dashboard" onkeydown="if(event.key==='Enter')login()">
    <button class="btn btn-ac" onclick="login()"><i class="ti ti-login"></i> Đăng nhập</button>
    <div class="alert err" id="auth-err" style="margin-top:10px;display:none"><i class="ti ti-alert-circle"></i><span>Mật khẩu sai!</span></div>
  </div>
</div>
<div class="hd">
  <div class="hd-logo"><i class="ti ti-headphones"></i></div>
  <div><div class="hd-title" id="bot-name">Bot Treo Voice</div><div class="hd-sub">Đang kết nối...</div></div>
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
async function loadCh(){try{const chs=await api('/channels');const list=document.getElementById('ch-list');list.innerHTML='';if(!chs.length){list.innerHTML='<div style="color:var(--tx3);font-size:13px">Không có kênh nào</div>';return;}chs.forEach(ch=>{const d=document.createElement('div');d.className='ch-item';d.innerHTML=`<i class="ti ti-volume"></i><div><div class="ch-name">${ch.channel_name}</div><div class="ch-guild">${ch.guild_name}</div></div><span class="ch-cnt"><i class="ti ti-users" style="font-size:11px;vertical-align:-1px;margin-right:2px"></i>${ch.members}</span>`;d.onclick=()=>{document.querySelectorAll('.ch-item').forEach(i=>i.classList.remove('active'));d.classList.add('active');sel=ch.channel_id;};list.appendChild(d);});}catch(e){addLog('Lỗi tải kênh: '+e.message,'err');}}
async function joinSel(){if(!sel){showAlert('Chọn kênh trước!','err');return;}try{const r=await api('/join','POST',{channel_id:sel});if(r.success){addLog('Đã vào kênh','ok');showAlert('Bot đã vào kênh!');}else{addLog('Vào kênh thất bại','err');showAlert('Thất bại','err');}await refresh();await loadCh();}catch(e){addLog('Lỗi: '+e.message,'err');}}
async function leaveAll(){try{await api('/leave','POST');addLog('Bot đã rời kênh','ok');showAlert('Bot đã rời kênh!');await refresh();}catch(e){addLog('Lỗi: '+e.message,'err');}}
async function setRejoin(v){try{await api('/auto_rejoin','POST',{enabled:v});addLog('Tự động vào lại: '+(v?'BẬT':'TẮT'),'info');}catch(e){addLog('Lỗi: '+e.message,'err');}}
async function setFollow(v){try{await api('/follow_owner','POST',{enabled:v});addLog('Follow chủ: '+(v?'BẬT':'TẮT'),'info');}catch(e){addLog('Lỗi: '+e.message,'err');}}
</script>
</body>
</html>"""

# ══════════════════════════════════════════════════════════════════════════════
#  HTTP API
# ══════════════════════════════════════════════════════════════════════════════
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
