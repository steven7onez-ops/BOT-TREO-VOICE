# 🎙️ Bot Discord — Voice Manager + Treo Voice + Profile

Bot Python (discord.py 2.4+) với 3 tính năng chính:

1. **Voice Manager** — tự tạo kênh voice tạm thời kiểu VoiceMaster, panel điều khiển luôn nằm dưới cùng khi có chat mới
2. **Treo Voice 24/7** — bot follow chủ vào voice, ở lại giữ kênh
3. **Profile System** — card giới thiệu thành viên + rating

---

## 🆕 Có gì mới so với bản cũ?

- ❌ **Đã bỏ hoàn toàn tính năng nghe nhạc YouTube** (không còn lỗi cookies/format)
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

---

## 🔑 Quyền bot cần thêm

Vào **Server Settings → Integrations → [Tên bot]**, bật:
- ✅ Quản Lý Kênh *(để tạo/xoá kênh voice tạm thời)*
- ✅ Di Chuyển Thành Viên *(để đưa người vào kênh mới, kick)*
- ✅ Gửi Tin Nhắn, Nhúng Liên Kết *(panel điều khiển)*
- ✅ Kết Nối, Nói *(voice)*
