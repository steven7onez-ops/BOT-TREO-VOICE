"""
Mô-đun Bảo vệ Liên kết: Phát hiện URL độc hại/lừa đảo bằng nhiều API
- Google Safe Browsing API
- Kaspersky Klookup API  
- URLhaus API (chống phần mềm độc hại)
"""

import aiohttp
import logging
import os
from typing import Optional, Tuple

log = logging.getLogger("LinkSecurity")

# ── Khóa API ──────────────────────────────────────────────────────────────────
GOOGLE_SAFE_BROWSING_KEY = os.environ.get("GOOGLE_SAFE_BROWSING_KEY", "")
KASPERSKY_API_KEY = os.environ.get("KASPERSKY_API_KEY", "")
URLHAUS_ENABLED = os.environ.get("URLHAUS_ENABLED", "true").lower() == "true"

# URL kiểm tra chống lừa đảo Việt Nam
CHONGLUADAO_API = "https://safe.chongluadao.vn/api/check"  # Cơ sở dữ liệu chống lừa đảo Việt Nam


class LinkChecker:
    """Kiểm tra URL có phải là link lừa đảo/phần mềm độc hại hay không"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache = {}  # Bộ đệm trong bộ nhớ cho URL
        
    async def init_session(self):
        """Khởi tạo phiên aiohttp"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
    async def close_session(self):
        """Đóng phiên aiohttp"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def check_url(self, url: str) -> Tuple[bool, str, str]:
        """
        Kiểm tra xem URL có phải là độc hại/lừa đảo không
        
        Trả về:
            (is_malicious: bool, source: str, reason: str)
            - is_malicious: True nếu URL nguy hiểm
            - source: Nơi phát hiện (ví dụ: "Google Safe Browsing", "Kaspersky", "ChongLuaDao")
            - reason: Lý do phát hiện ngắn gọn
        """
        if not url:
            return False, "", ""
        
        # Kiểm tra bộ đệm trước
        if url in self.cache:
            return self.cache[url]
        
        await self.init_session()
        
        # Thử từng dịch vụ theo thứ tự
        result = await self._check_google_safe_browsing(url)
        if result[0]:
            self.cache[url] = result
            return result
        
        result = await self._check_urlhaus(url)
        if result[0]:
            self.cache[url] = result
            return result
            
        result = await self._check_kaspersky(url)
        if result[0]:
            self.cache[url] = result
            return result
        
        result = await self._check_chongluadao(url)
        if result[0]:
            self.cache[url] = result
            return result
        
        # URL an toàn
        result = (False, "Sạch", "URL an toàn")
        self.cache[url] = result
        return result
    
    async def _check_google_safe_browsing(self, url: str) -> Tuple[bool, str, str]:
        """Kiểm tra Google Safe Browsing API"""
        if not GOOGLE_SAFE_BROWSING_KEY:
            return False, "", ""
        
        try:
            payload = {
                "client": {"clientId": "Discord-Bot-Security", "clientVersion": "1.0"},
                "threatInfo": {
                    "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
                    "platformTypes": ["ANY_PLATFORM"],
                    "threatEntryTypes": ["URL"],
                    "threatEntries": [{"url": url}]
                }
            }
            
            api_url = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={GOOGLE_SAFE_BROWSING_KEY}"
            
            async with self.session.post(api_url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("matches"):
                        match = data["matches"][0]
                        threat_type = match.get("threatType", "UNKNOWN")
                        return True, "Google Safe Browsing", threat_type
        except Exception as e:
            log.warning(f"❌ Kiểm tra Google Safe Browsing thất bại: {e}")
        
        return False, "", ""
    
    async def _check_kaspersky(self, url: str) -> Tuple[bool, str, str]:
        """Kiểm tra Kaspersky Klookup API"""
        if not KASPERSKY_API_KEY:
            return False, "", ""
        
        try:
            # Điểm cuối Kaspersky Klookup API
            api_url = "https://opentips.kaspersky.com/api/v1/get/ip"
            headers = {
                "x-api-key": KASPERSKY_API_KEY,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
            
            async with self.session.get(
                api_url, 
                params={"request": url},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    reputation = data.get("reputation", 0)
                    if reputation < -50:  # Danh tiếng âm = đáng ngờ
                        return True, "Kaspersky", f"Điểm danh tiếng: {reputation}"
        except Exception as e:
            log.warning(f"❌ Kiểm tra Kaspersky thất bại: {e}")
        
        return False, "", ""
    
    async def _check_urlhaus(self, url: str) -> Tuple[bool, str, str]:
        """Kiểm tra URLhaus API - cơ sở dữ liệu URL phần mềm độc hại miễn phí"""
        if not URLHAUS_ENABLED:
            return False, "", ""
        
        try:
            api_url = "https://urlhaus-api.abuse.ch/v1/url/"
            
            async with self.session.post(
                api_url,
                data={"url": url},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("query_status") == "ok":
                        result = data.get("result")
                        if result == "blacklisted":
                            threat_type = data.get("threat", "MALWARE")
                            return True, "URLhaus", threat_type
        except Exception as e:
            log.warning(f"❌ Kiểm tra URLhaus thất bại: {e}")
        
        return False, "", ""
    
    async def _check_chongluadao(self, url: str) -> Tuple[bool, str, str]:
        """Cơ sở dữ liệu Chống Lừa Đảo Việt Nam (ChongLuaDao.vn)"""
        try:
            async with self.session.post(
                CHONGLUADAO_API,
                json={"url": url},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") == "dangerous" or data.get("is_scam"):
                        reason = data.get("reason", "Link lừa đảo")
                        return True, "ChongLuaDao", reason
        except Exception as e:
            log.debug(f"⚠️ Kiểm tra ChongLuaDao thất bại (bình thường nếu offline): {e}")
        
        return False, "", ""


# Thể hiện toàn cục
link_checker = LinkChecker()
