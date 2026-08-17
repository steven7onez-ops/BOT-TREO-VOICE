# 🍪 Setup YouTube Cookies để Bypass Rate-Limit

YouTube rate-limit session khi bot request quá nhanh. **Dùng cookies từ real YouTube account sẽ bypass tất cả!**

---

## **Cách 1: Export cookies từ Chrome (Dễ nhất)**

### Bước 1: Mở Chrome DevTools
```
1. Mở YouTube.com
2. Nhấn F12 hoặc Ctrl+Shift+I
3. Đi tới Application → Cookies → https://www.youtube.com
```

### Bước 2: Tìm cookie "SIDCAR"
```
Tìm cookie name "SIDCAR" hoặc "__Secure-3PSIDTS"
Copy giá trị nó
```

### Bước 3: Tạo cookies.txt
Tạo file `cookies.txt` với nội dung (Netscape format):
```
# Netscape HTTP Cookie File
.youtube.com	TRUE	/	TRUE	0	SIDCAR	YOUR_SIDCAR_VALUE_HERE
.youtube.com	TRUE	/	TRUE	0	__Secure-3PSIDTS	YOUR_SIDTS_VALUE_HERE
```

---

## **Cách 2: Export từ Browser Extension (Tự động hơn)**

### Bước 1: Cài Cookie Editor Chrome
- Tìm trên Chrome Web Store: "Cookie Editor"
- Cài vào Chrome

### Bước 2: Export cookies
```
1. Vào YouTube.com
2. Nhấn icon Cookie Editor
3. Nhấn "Export" → chọn format Netscape
4. Lưu file as cookies.txt
```

### Bước 3: Dùng ngay (local) hoặc Upload (Railway)

---

## **Cách 3: Dùng yt-dlp để Extract Cookies**

Chạy lệnh này:
```bash
yt-dlp --cookies-from-browser chrome https://www.youtube.com/watch?v=dQw4w9WgXcQ -J > /dev/null
```

---

## **Upload lên Railway**

### Cách A: Dùng File Upload
```
1. Vào Railway dashboard
2. Files → Upload cookies.txt
3. Set env var: YTDL_COOKIE_FILE=/app/cookies.txt
```

### Cách B: Dùng Base64 (Khuyên dùng)
```bash
# Trên Windows (PowerShell):
[Convert]::ToBase64String([System.IO.File]::ReadAllBytes("cookies.txt")) | Set-Clipboard

# Trên Linux/Mac:
cat cookies.txt | base64

# Copy output
```

Paste vào Railway:
```
YTDL_COOKIES_BASE64=<giá_trị_base64_ở_trên>
```

---

## **Test nó hoạt động**

Gửi YouTube link vào Discord. Bot sẽ:
- ✅ Không bị rate-limit nữa
- ✅ Load video nhanh hơn
- ✅ Có thể phát video Private/Age-restricted

---

## **Troubleshoot**

| Problem | Solution |
|---------|----------|
| Cookies hết hạn | Refresh YouTube trong Chrome, export lại cookies |
| Vẫn bị 403 Forbidden | Chắc chắn cookies.txt format đúng, test local trước |
| Bot không tìm thấy cookies | Kiểm tra env var `YTDL_COOKIE_FILE` hoặc `YTDL_COOKIES_BASE64` |

---

## **Cách kiểm tra cookies hoạt động (Local)**

```bash
# Test với cookies.txt
yt-dlp --cookies cookies.txt "https://www.youtube.com/watch?v=VIDEO_ID" -J

# Nếu thành công → Ready push lên Railway!
```

---

**Done! Sau khi setup cookies, bot sẽ hoạt động mà không rate-limit.** 🎯
