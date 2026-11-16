# Link Security Configuration Guide

## Overview
The bot includes an integrated link security system that automatically detects and blocks malicious/scam URLs. When a malicious link is detected:

1. **User is permanently banned** from the server
2. **Message is deleted** automatically
3. **User receives DM** with ban details and source of detection
4. **Moderators are notified** in the channel

## Supported Detection Sources

### 1. Google Safe Browsing API (Recommended)
- Detects: Malware, Social Engineering, Unwanted Software, Potentially Harmful Applications
- Coverage: Global
- Speed: Fast
- Cost: Free (requires API key registration)

**Setup:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable "Safe Browsing API"
4. Create an API key (type: Browser/Restricted to Safe Browsing API)
5. Set environment variable:
   ```
   GOOGLE_SAFE_BROWSING_KEY=your_api_key_here
   ```

### 2. Kaspersky Klookup API
- Detects: Phishing, Malware, Trojan, etc.
- Coverage: Global
- Speed: Very Fast
- Cost: Limited free tier available

**Setup:**
1. Visit [Kaspersky Klookup](https://opentips.kaspersky.com/)
2. Register for API access
3. Get your API key
4. Set environment variable:
   ```
   KASPERSKY_API_KEY=your_api_key_here
   ```

### 3. URLhaus API (Free - No API Key Needed)
- Detects: Malware URLs, Phishing
- Coverage: Community-sourced
- Speed: Very Fast
- Cost: Completely Free
- Enabled by default

**Setup:**
Already enabled by default. To disable:
```
URLHAUS_ENABLED=false
```

### 4. ChongLuaDao.vn (Vietnamese Anti-Scam)
- Detects: Vietnamese scam sites, fraud links
- Coverage: Vietnam-focused
- Speed: Moderate
- Cost: Free
- Fallback: Graceful degradation if service is down

**Note:** This is the primary Vietnamese anti-scam database. No setup needed — automatically checked.

## Environment Variables

```bash
# Google Safe Browsing API (recommended)
GOOGLE_SAFE_BROWSING_KEY=sk_live_xxxxxxxxxxxxx

# Kaspersky API
KASPERSKY_API_KEY=your_kaspersky_key

# URLhaus (enabled by default)
URLHAUS_ENABLED=true

# Other bot variables (existing)
DISCORD_TOKEN=your_token
GUILD_ID=your_guild_id
VOICE_CHANNEL_ID=your_voice_channel_id
# ... etc
```

## Docker Setup Example

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

ENV DISCORD_TOKEN=${DISCORD_TOKEN}
ENV GUILD_ID=${GUILD_ID}
ENV VOICE_CHANNEL_ID=${VOICE_CHANNEL_ID}
ENV GOOGLE_SAFE_BROWSING_KEY=${GOOGLE_SAFE_BROWSING_KEY}
ENV KASPERSKY_API_KEY=${KASPERSKY_API_KEY}
ENV URLHAUS_ENABLED=true

CMD ["python", "bot.py"]
```

## Railway.toml Example

```toml
[build]
builder = "dockerfile"

[deploy]
restartPolicyType = "always"
numReplicas = 1
```

## Set Environment Variables on Railway

1. Go to your Railway project
2. Go to **Variables** section
3. Add the following:
   ```
   DISCORD_TOKEN=your_bot_token
   GUILD_ID=123456789
   VOICE_CHANNEL_ID=987654321
   GOOGLE_SAFE_BROWSING_KEY=your_key_here
   KASPERSKY_API_KEY=your_key_here (optional)
   URLHAUS_ENABLED=true
   ```

## How It Works

1. **On every message:** Bot extracts all URLs
2. **For each URL:** Checks against detection sources in order:
   - Google Safe Browsing (if API key provided)
   - URLhaus (free, always on)
   - Kaspersky (if API key provided)
   - ChongLuaDao Vietnamese DB (free, always on)
3. **If malicious detected:**
   - User is permanently banned with auto-delete of 7 days of messages
   - User receives DM with:
     - Ban reason: "Link lừa đảo / scam"
     - Source: Which service detected it
     - Details: Why it was flagged
   - Channel gets notification for 30 seconds
   - Original message deleted
4. **If safe:** Normal message processing continues

## URL Caching

- Checked URLs are cached in memory for 24-hour session
- Same URL won't be checked twice in same session
- Reduces API calls and improves performance

## Logs

Monitor detection in logs:
```bash
# Successful detections
🚨 MALICIOUS LINK DETECTED: https://... | Source: Google Safe Browsing
✅ Đã ban vĩnh viễn: username#1234

# API failures (graceful)
⚠️ Google Safe Browsing check failed: Connection timeout
```

## Troubleshooting

**No links being detected?**
- Check that `message_content` intent is enabled ✅ (already set in bot.py)
- Verify bot has DM permissions
- Check bot has permission to ban users

**Getting rate-limited?**
- URLhaus rate limits: ~100 requests/hour per IP
- Kaspersky rate limits: Check Kaspersky documentation
- Google Safe Browsing: ~600k lookups/day free tier
- Add caching or reduce URL checks

**DM not sending to banned users?**
- User has DMs disabled — message silently fails (logged)
- Bot still bans the user regardless

## Cost Estimation

| Service | Cost | Limits | Recommended |
|---------|------|--------|-------------|
| Google Safe Browsing | Free | 600k/day | ✅ Yes |
| Kaspersky | Limited Free | Varies | Optional |
| URLhaus | Free | 100/hr/IP | ✅ Always On |
| ChongLuaDao | Free | Unlimited | ✅ Always On |

**Optimal Setup:** Use URLhaus + ChongLuaDao (free) + add Google Safe Browsing for global coverage.

## Testing

To test if link detection is working:

1. Send a known malicious URL (e.g., from URLhaus sample)
2. Check bot logs for detection
3. Verify user is banned (check Discord)
4. Verify user received DM

Example test URL (URLhaus):
```
http://malware-domain-example.com
```

**Note:** Use with caution — this will actually ban the user! Test in a private server first.
