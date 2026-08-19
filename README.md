# 🎙️ Bot Discord — Voice Manager + Treo Voice + Profile

Bot Python (discord.py 2.4+) với 3 tính năng chính:

1. **Voice Manager** — tự tạo kênh voice tạm thời kiểu VoiceMaster, panel điều khiển luôn nằm dưới cùng khi có chat mới
2. **Treo Voice 24/7** — bot follow chủ vào voice, ở lại giữ kênh
3. **Profile System** — card giới thiệu thành viên + rating
4. **Anti-nuke Monitoring** — theo dõi Audit Log và hạn chế hành vi phá server hàng loạt

---

## 🆕 Có gì mới so với bản cũ?

- ✅ **Nghe nhạc từ YouTube, Spotify và SoundCloud** bằng lệnh prefix
- ✅ **Nâng cấp Python 3.13 + discord.py 2.4+**
- ✅ **Thêm Voice Manager** — thay thế bot VoiceMaster

---

## 🎛️ Cách hoạt động Voice Manager

1. Admin chạy `/voice_setup` để tạo kênh **hub** (vd: "➕ Tạo kênh thoại")
2. Ai join vào hub → bot tự tạo 1 kênh voice riêng cho họ + di chuyển họ vào
3. Bot gửi **panel điều khiển** (embed + buttons) vào khung chat của kênh voice đó
4. Khi có ai **nhắn tin mới** trong kênh voice → panel cũ bị xoá, panel mới được gửi xuống dưới cùng (không bị trôi)
5. Khi kênh trống (không còn ai) → bot tự xoá kênh

**Nút trên panel:**
| Nút | Chức năng | Ai dùng được |
|---|---|---|
| 🔒 Khoá/Mở | Khoá không cho người khác vào | Chủ kênh / Admin |
| 🙈 Ẩn/Hiện | Ẩn kênh khỏi danh sách | Chủ kênh / Admin |
| ✏️ Đổi tên | Đổi tên kênh | Chủ kênh / Admin |
| 👥 Giới hạn | Đặt số người tối đa | Chủ kênh / Admin |
| 🎚️ Bitrate | Đổi chất lượng âm thanh | Chủ kênh / Admin |
| 👑 Chuyển chủ | Chuyển quyền chủ kênh cho người khác | Chủ kênh / Admin |
| 🚫 Kick | Đuổi người khỏi kênh | Chủ kênh / Admin |

---

## 🚀 Setup

### Bước 1 — Upload lên GitHub
Upload toàn bộ file trong thư mục này lên repo GitHub hiện có (ghi đè `bot.py`, `requirements.txt`, `Dockerfile`).

### Bước 2 — Railway tự động redeploy
Railway sẽ tự build lại với Python 3.13 + code mới.

### Bước 3 — Setup Voice Manager trong Discord
Sau khi bot online, chạy lệnh:
```
/voice_setup ten_hub:➕ Tạo kênh thoại mau_ten:🔊 Kênh của {user}
```

Xong! Giờ ai join vào kênh "➕ Tạo kênh thoại" sẽ tự có kênh riêng.

### Bước 4 (tuỳ chọn) — Sửa cấu hình sau này
```
/voice_config mau_ten:🎮 Phòng của {user}
```

---

## 📋 Danh sách lệnh

### Prefix (+)
| Lệnh | Chức năng |
|---|---|
| `+ping` | Kiểm tra bot |
| `+help` | Danh sách lệnh |
| `+play <link|từ khoá>` / `+p` | Phát nhạc từ YouTube, Spotify hoặc SoundCloud |
| `+queue <link|từ khoá>` | Thêm nhạc vào queue |
| `+checkqueue` | Xem queue hiện tại |
| `+pause` / `+stop` | Tạm dừng / dừng nhạc |
| `+shuffle` / `+repeat [all]` | Xáo trộn / lặp bài hoặc toàn bộ queue |

### 🛡️ Anti-nuke Monitoring

Anti-nuke theo dõi việc xóa kênh, xóa role, ban/kick hàng loạt và tạo/xóa webhook qua Discord Audit Log. Khi một executor vượt ngưỡng trong thời gian ngắn, bot mặc định tước các role quản trị có thể tước được. Đặt `ANTI_NUKE_ACTION=ban` nếu muốn bot ban executor thay vì tước role.

Bot không thể xử lý Server Owner, user có role cao hơn bot, hoặc hành động xảy ra khi bot đã bị mất quyền/kick.

### 🎵 Nghe nhạc

Bot hỗ trợ link bài hát Spotify (bao gồm link chia sẻ `spotify.link`) và link track/playlist SoundCloud:
```text
+play https://open.spotify.com/track/...
+play https://soundcloud.com/artist/track
+queue <link hoặc từ khoá>
```
Spotify chỉ cung cấp thông tin bài hát nên bot sẽ tìm bản phát tương ứng trên YouTube; SoundCloud được yt-dlp lấy stream trực tiếp. Người dùng cần ở trong kênh voice khi dùng `+play` hoặc `+queue`.

### Slash — Voice Manager
| Lệnh | Ai dùng | Chức năng |
|---|---|---|
| `/voice_setup` | Admin | Tạo hub tạo kênh tạm thời |
| `/voice_config` | Admin | Sửa cấu hình hub hiện tại |

### Slash — Profile
| Lệnh | Ai dùng | Chức năng |
|---|---|---|
| `/profile @user` | Tất cả | Xem profile |
| `/profile_set` | Admin | Tạo/sửa tên + tags |
| `/profile_addphoto` | Admin | Thêm ảnh |
| `/profile_removephoto` | Admin | Xóa ảnh |
| `/profile_delete` | Admin | Xóa profile |

---

## ⚙️ Biến môi trường (Railway Variables)

| Tên | Bắt buộc | Mô tả |
|---|---|---|
| `DISCORD_TOKEN` | ✅ | Token bot |
| `GUILD_ID` | ✅ | ID server |
| `VOICE_CHANNEL_ID` | ⬜ | ID kênh vĩnh viễn (treo voice cũ) |
| `OWNER_ID` | ⬜ | ID người bot sẽ follow (mặc định có sẵn) |
| `DASHBOARD_KEY` | ✅ | Mật khẩu dashboard web |
| `PORT` | ⬜ | Port dashboard (Railway tự set) |

### Biến Anti-nuke

| Tên | Mặc định | Mô tả |
|---|---:|---|
| `ANTI_NUKE_ENABLED` | `true` | Bật/tắt giám sát |
| `ANTI_NUKE_ACTION` | `strip` | `strip` tước role; `ban` ban executor |
| `ANTI_NUKE_LOG_CHANNEL_ID` | `0` | ID kênh nhận cảnh báo; `0` chỉ ghi log container |
| `ANTI_NUKE_TRUSTED_IDS` | `OWNER_ID` | Danh sách user ID tin cậy, cách nhau bằng dấu cách |
| `ANTI_NUKE_WINDOW_SECONDS` | `30` | Cửa sổ tính hành vi |
| `ANTI_NUKE_CHANNEL_LIMIT` | `3` | Số kênh bị xóa để kích hoạt |
| `ANTI_NUKE_ROLE_LIMIT` | `3` | Số role bị xóa để kích hoạt |
| `ANTI_NUKE_BAN_LIMIT` / `ANTI_NUKE_KICK_LIMIT` | `5` | Số ban/kick để kích hoạt |
| `ANTI_NUKE_WEBHOOK_LIMIT` | `3` | Số webhook tạo/xóa để kích hoạt |

### Biến bổ sung cho TikBot-style upload
| `TIKBOT_STATUS_TEXT` | ⬜ | Text hiển thị trong presence (mặc định: "🎙️ voice channel") |
| `TIKBOT_VERSION` | ⬜ | Phiên bản để hiển thị trong presence (ví dụ: `1.0.0`) |
| `TIKBOT_AUTO_DOMAINS` | ⬜ | Space-separated domains để bot tự phát hiện link (mặc định: `youtube tiktok instagram reddit redd.it`) |
| `TIKBOT_SILENT_DOMAINS` | ⬜ | Domain nào bot im lặng (space-separated) |
| `TIKBOT_MAX_UPLOAD_MB` | ⬜ | Kích thước tối đa (MB) bot sẽ gửi trực tiếp; mặc định `50`. Bot sẽ cố nén bằng `ffmpeg` nếu lớn hơn |

### Yêu cầu hệ thống
- `ffmpeg` phải có trong PATH nếu chạy local (Dockerfile đã cài trong container)
- `yt-dlp` được liệt kê trong `requirements.txt` và sẽ được cài khi chạy `pip install -r requirements.txt`

### Chạy local (Linux / macOS / Windows WSL)
1. Cài Python 3.11+ hoặc 3.13 và `ffmpeg`.
2. Cài dependencies:
```bash
pip install -r requirements.txt
```
3. Thiết lập biến môi trường (ví dụ Linux/macOS):
```bash
export DISCORD_TOKEN="your-token"
export GUILD_ID="123456789012345678"
export DASHBOARD_KEY="changeme"
export TIKBOT_MAX_UPLOAD_MB=50
```
4. Chạy bot:
```bash
python bot.py
```

### YouTube cookies (khi yt-dlp báo "Sign in to confirm you're not a bot")

Một số video YouTube yêu cầu cookie (ví dụ video age-restricted, region-restricted hoặc khi YouTube bật kiểm tra bot). Nếu bạn thấy lỗi như "Sign in to confirm you're not a bot" hoặc hướng dẫn dùng `--cookies-from-browser`, thực hiện một trong các cách sau:

- Xuất cookies từ trình duyệt thành file `cookies.txt` bằng extension `cookies.txt` hoặc `EditThisCookie`.
- Đặt cookie cho bot bằng một trong 2 cách:
	- Upload file `cookies.txt` vào container và set biến môi trường `YTDL_COOKIE_FILE` trỏ tới đường dẫn file trong container (ví dụ `/app/cookies.txt`).
	- Hoặc base64-encode nội dung `cookies.txt` rồi set vào biến môi trường `YTDL_COOKIES_BASE64` (an toàn hơn để lưu dưới dạng secret). Bot sẽ giải mã và ghi tạm file cookies khi cần.

Ví dụ mã hóa file trên Linux/macOS:
```bash
base64 cookies.txt | tr -d '\n'  # copy kết quả đặt vào YTDL_COOKIES_BASE64
```
Ví dụ trên Windows PowerShell:
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes('cookies.txt'))
```

Sau đó trong Railway/GitHub Actions/ENV thêm biến `YTDL_COOKIES_BASE64` (secret) với giá trị base64 thu được, hoặc upload `cookies.txt` và set `YTDL_COOKIE_FILE`.

Lưu ý: Cookies có thể hết hạn; nếu lỗi quay lại, xuất cookies mới và cập nhật secret.

### Triển khai nhanh (Railway / Docker)
- Repo đã có `Dockerfile` (cài `ffmpeg` + Python deps). Push lên GitHub và kết nối repo với Railway; Railway sẽ build Docker image tự động.
- Trên Railway (hoặc môi trường deploy khác) set các Variables tương ứng (DISCORD_TOKEN, GUILD_ID, DASHBOARD_KEY, v.v.).

### Đẩy code lên GitHub (nhanh)
1. Khởi tạo git trong thư mục (nếu chưa):
```bash
git init
git add .
git commit -m "Initial bot commit"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```
2. (Tuỳ chọn) Thêm secrets trên GitHub (Settings → Secrets) nếu bạn muốn GH Actions push Docker image:
	- `DOCKERHUB_USERNAME`
	- `DOCKERHUB_TOKEN`
	- Thêm `DOCKERHUB_REPOSITORY` dưới `Repository > Settings > Environments` hoặc qua `Actions` env.

Sau khi push, GitHub Actions `CI` sẽ chạy: kiểm tra syntax, cài dependencies và (nếu cấu hình) build/push image.
---

## 🔑 Quyền bot cần thêm

Vào **Server Settings → Integrations → [Tên bot]**, bật:
- ✅ Quản Lý Kênh *(để tạo/xoá kênh voice tạm thời)*
- ✅ Xem Nhật ký kiểm toán *(bắt buộc cho Anti-nuke)*
- ✅ Quản lý Vai trò *(để tước role executor khi vượt ngưỡng)*
- ✅ Di Chuyển Thành Viên *(để đưa người vào kênh mới, kick)*
- ✅ Gửi Tin Nhắn, Nhúng Liên Kết *(panel điều khiển)*
- ✅ Kết Nối, Nói *(voice)*
