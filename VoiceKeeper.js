// src/VoiceKeeper.js - Tự động treo voice 24/7
const { joinVoiceChannel, VoiceConnectionStatus, entersState } = require('@discordjs/voice');
const chalk = require('chalk');

class VoiceKeeper {
    constructor(client) {
        this.client = client;
        this.targetChannelId = process.env.VOICE_CHANNEL_ID || null;
        this.ownerId = process.env.OWNER_ID || null;
        this.autoRejoin = true;
        this.followOwner = true;
        this.connections = new Map(); // guildId -> VoiceConnection
        this.startTime = Date.now();
    }

    // Join kênh voice theo ID
    async joinChannel(channel) {
        try {
            const connection = joinVoiceChannel({
                channelId: channel.id,
                guildId: channel.guild.id,
                adapterCreator: channel.guild.voiceAdapterCreator,
                selfDeaf: true,
                selfMute: true,
            });

            this.connections.set(channel.guild.id, connection);

            connection.on(VoiceConnectionStatus.Disconnected, async () => {
                if (!this.autoRejoin) return;
                console.log(chalk.yellow(`⚠️ Bot bị disconnect, rejoin sau 3 giây...`));
                await new Promise(r => setTimeout(r, 3000));
                try {
                    await entersState(connection, VoiceConnectionStatus.Connecting, 5000);
                } catch {
                    connection.destroy();
                    this.connections.delete(channel.guild.id);
                    // Thử join lại
                    await this.joinById(channel.id, channel.guild);
                }
            });

            console.log(chalk.green(`🎙️ Đã join: #${channel.name} trong '${channel.guild.name}'`));
            return connection;
        } catch (err) {
            console.error(chalk.red(`❌ Lỗi join voice: ${err.message}`));
            return null;
        }
    }

    // Join theo channel ID
    async joinById(channelId, guild) {
        if (!channelId || !guild) return null;
        const channel = guild.channels.cache.get(channelId);
        if (!channel) {
            console.error(chalk.red(`❌ Không tìm thấy kênh ID=${channelId}`));
            return null;
        }
        return await this.joinChannel(channel);
    }

    // Rời tất cả voice
    leaveAll() {
        for (const [guildId, conn] of this.connections) {
            try { conn.destroy(); } catch {}
        }
        this.connections.clear();
        console.log(chalk.yellow('👋 Đã rời tất cả voice channels'));
    }

    // Xử lý voice state update
    async handleVoiceStateUpdate(oldState, newState) {
        // Follow owner
        if (this.followOwner && this.ownerId && newState.member?.id === this.ownerId) {
            if (newState.channel && newState.channel !== oldState.channel) {
                console.log(chalk.cyan(`👤 Chủ vào #${newState.channel.name} — bot follow theo`));
                await this.joinChannel(newState.channel);
            }
        }
    }

    // Lấy trạng thái
    getStatus() {
        const uptime = Math.floor((Date.now() - this.startTime) / 1000);
        const h = Math.floor(uptime / 3600);
        const m = Math.floor((uptime % 3600) / 60);
        const s = uptime % 60;
        const voiceInfo = [];
        for (const [guildId, conn] of this.connections) {
            const guild = this.client.guilds.cache.get(guildId);
            if (guild) {
                const channel = guild.members.me?.voice?.channel;
                if (channel) {
                    voiceInfo.push({
                        guild: guild.name,
                        channel: channel.name,
                        members: channel.members.filter(m => !m.user.bot).size
                    });
                }
            }
        }
        return {
            online: this.client.isReady(),
            bot_name: this.client.user?.tag || '—',
            uptime: `${h}h ${m}m ${s}s`,
            auto_rejoin: this.autoRejoin,
            follow_owner: this.followOwner,
            voice: voiceInfo,
        };
    }
}

module.exports = VoiceKeeper;
