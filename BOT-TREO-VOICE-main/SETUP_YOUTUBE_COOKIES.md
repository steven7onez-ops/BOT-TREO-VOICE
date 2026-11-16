# YouTube cookies for yt-dlp

Public YouTube videos normally do not require cookies. Do not configure cookies
to work around rate limits, CAPTCHA, PO Token requirements, or anti-bot checks.
yt-dlp warns that using an account with yt-dlp may result in temporary or
permanent account restrictions.

Only use cookies you own and are authorized to use, and only when a video
requires account access. Never commit or share the cookie file.

If account access is genuinely required, follow yt-dlp's official cookie
documentation and use only an account and cookies you are authorized to use.
Do not use cookies to get around verification, anti-bot measures, or rate
limits. Cookies can expire and may result in account restrictions.

## Configure the bot

Provide the file directly:

```text
YTDL_COOKIE_FILE=/app/cookies.txt
```

Or store its Base64 contents as the secret `YTDL_COOKIES_BASE64`. The bot writes
the decoded file to a temporary directory when it starts.

Official references:

- [yt-dlp YouTube extractor guide](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#youtube)
- [yt-dlp FAQ: passing cookies](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)
- [yt-dlp PO Token guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)
