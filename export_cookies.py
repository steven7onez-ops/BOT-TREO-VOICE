#!/usr/bin/env python3
"""
🍪 Export YouTube Cookies từ Chrome
Chạy script này để tự động export cookies từ Chrome
"""

import os
import sys
import json
import sqlite3
import shutil
from pathlib import Path
import base64

def get_browser_cookie_path(browser_type="chrome"):
    """Tìm đường dẫn Cookies database cho Chrome hoặc Edge"""
    system = sys.platform
    
    if browser_type.lower() == "edge":
        # Microsoft Edge
        if system == "win32":
            path = Path.home() / "AppData/Local/Microsoft/Edge/User Data/Default/Cookies"
        elif system == "darwin":
            path = Path.home() / "Library/Application Support/Microsoft Edge/Default/Cookies"
        elif system == "linux":
            path = Path.home() / ".config/microsoft-edge/Default/Cookies"
        else:
            return None
    else:
        # Chrome (default)
        if system == "win32":
            path = Path.home() / "AppData/Local/Google/Chrome/User Data/Default/Cookies"
        elif system == "darwin":
            path = Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies"
        elif system == "linux":
            path = Path.home() / ".config/google-chrome/Default/Cookies"
        else:
            return None
    
    return path if path.exists() else None

def export_youtube_cookies_from_browser(browser_type="chrome"):
    """Export YouTube cookies từ Chrome hoặc Edge database"""
    cookies_path = get_browser_cookie_path(browser_type)
    browser_name = "Edge" if browser_type.lower() == "edge" else "Chrome"
    
    if not cookies_path:
        print(f"❌ {browser_name} Cookies database không tìm thấy.")
        print(f"   Chắc chắn {browser_name} đã cài và có profile Default?")
        return None
    
    # Browser lock cookies file khi đang chạy - copy ra temp trước
    temp_cookies = Path("cookies_temp.db")
    try:
        shutil.copy(cookies_path, temp_cookies)
    except PermissionError:
        print(f"❌ Không thể copy {browser_name} Cookies - {browser_name} đang chạy?")
        print(f"   ✅ Sửa: Đóng {browser_name} hoàn toàn rồi thử lại")
        return None
    
    try:
        conn = sqlite3.connect(temp_cookies)
        cursor = conn.cursor()
        
        # Query cookies cho youtube.com
        cursor.execute("""
            SELECT name, value, domain, path, expires_utc, secure, httponly
            FROM cookies
            WHERE host_key LIKE '%.youtube.com'
            ORDER BY name
        """)
        
        cookies = cursor.fetchall()
        conn.close()
        
        if not cookies:
            print(f"❌ Không tìm thấy YouTube cookies trong {browser_name}")
            print(f"   ✅ Sửa: Mở youtube.com trong {browser_name} trước, sau đó thử lại")
            return None
        
        # Tạo Netscape format cookies file
        netscape_cookies = "# Netscape HTTP Cookie File\n"
        netscape_cookies += f"# Generated from {browser_name} by export_cookies.py\n\n"
        
        for name, value, domain, path, expires, secure, httponly in cookies:
            # Netscape format: domain, flag, path, secure, expiration, name, value
            domain_flag = "TRUE"
            secure_flag = "TRUE" if secure else "FALSE"
            expiration = int(expires) if expires else "0"
            
            netscape_cookies += f"{domain}\t{domain_flag}\t{path}\t{secure_flag}\t{expiration}\t{name}\t{value}\n"
        
        return netscape_cookies
    
    except Exception as e:
        print(f"❌ Lỗi khi đọc {browser_name} Cookies: {e}")
        return None
    finally:
        temp_cookies.unlink(missing_ok=True)

def main():
    print("🍪 YouTube Cookies Exporter for Railway")
    print("=" * 50)
    print()
    
    print("🌐 Chọn browser:")
    print("   1. Chrome")
    print("   2. Microsoft Edge")
    browser_choice = input("Nhập số (1 hoặc 2): ").strip()
    
    browser_type = "edge" if browser_choice == "2" else "chrome"
    browser_name = "Edge" if browser_choice == "2" else "Chrome"
    print()
    
    print("⚠️  Yêu cầu:")
    print(f"   1. {browser_name} phải ĐÓNG hoàn toàn (không có process nào)")
    print("   2. Phải đã đăng nhập YouTube trong browser")
    print()
    
    input("💡 Nhấn Enter để tiếp tục...")
    print()
    
    # Export cookies
    print(f"📝 Exporting YouTube cookies từ {browser_name}...")
    cookies_content = export_youtube_cookies_from_browser(browser_type)
    
    if not cookies_content:
        print(f"\n❌ Export thất bại!")
        sys.exit(1)
    
    # Lưu cookies.txt
    cookies_file = Path("cookies.txt")
    cookies_file.write_text(cookies_content)
    print(f"✅ Đã lưu: {cookies_file.absolute()}")
    print()
    
    # Encode base64
    print("🔐 Encoding thành base64 cho Railway...")
    cookies_b64 = base64.b64encode(cookies_content.encode()).decode()
    
    b64_file = Path("COOKIES_BASE64.txt")
    b64_file.write_text(cookies_b64)
    print(f"✅ Đã lưu: {b64_file.absolute()}")
    print()
    
    print("=" * 50)
    print("🎯 SETUP RAILWAY:")
    print("=" * 50)
    print()
    print("1️⃣  Vào Railway Dashboard")
    print("2️⃣  Chọn Project → Variables")
    print("3️⃣  Thêm biến mới:")
    print()
    print("   Name: YTDL_COOKIES_BASE64")
    print("   Value: <Paste nội dung dưới đây>")
    print()
    print("-" * 50)
    print(cookies_b64)
    print("-" * 50)
    print()
    print("4️⃣  Nhấn Save")
    print("5️⃣  Bot sẽ restart tự động")
    print("6️⃣  ✅ Xong! YouTube rate-limit sẽ bypass!")
    print()
    
    print("💾 Backup:")
    print(f"   Lưu file COOKIES_BASE64.txt ở chỗ an toàn")
    print(f"   (Nếu cookies hết hạn, thay mới bằng file này)")
    print()

if __name__ == "__main__":
    main()
