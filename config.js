// config.js — đọc toàn bộ biến môi trường, validate bắt buộc
require('dotenv').config();

const required = ['DISCORD_TOKEN', 'CLIENT_ID'];
for (const key of required) {
    if (!process.env[key]) {
        console.error(`❌ Thiếu biến môi trường bắt buộc: ${key}`);
        process.exit(1);
    }
}

module.exports = {
    discord: {
        token: process.env.DISCORD_TOKEN,
        clientId: process.env.CLIENT_ID,
        guildId: process.env.GUILD_ID || null,
    },
    bot: {
        status: process.env.STATUS || '🎵 Music Bot | /play',
        embedColor: process.env.EMBED_COLOR || '#5865F2',
        ownerId: process.env.OWNER_ID || null,
        prefix: process.env.PREFIX || '+',
    },
    voice: {
        channelId: process.env.VOICE_CHANNEL_ID || null,
    },
    dashboard: {
        key: process.env.DASHBOARD_KEY || 'changeme',
        port: parseInt(process.env.PORT) || 8080,
    },
    youtube: {
        cookies: process.env.YOUTUBE_COOKIES || null,
        cookiesFile: process.env.COOKIES_FILE || null,
    },
    spotify: {
        clientId: process.env.SPOTIFY_CLIENT_ID || null,
        clientSecret: process.env.SPOTIFY_CLIENT_SECRET || null,
    },
};
