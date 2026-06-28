// src/MusicEmbedManager.js — quản lý embed now-playing & nút điều khiển
const { EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const chalk = require('chalk');

class MusicEmbedManager {
    constructor(client) {
        this.client = client;
        // Map<guildId, { messageId, channelId }>
        this.activeEmbeds = new Map();
    }

    /** Tạo embed now-playing từ player */
    buildEmbed(player) {
        const track = player.currentTrack;
        if (!track) return null;

        const isPaused = player.isPaused?.() ?? false;
        const color    = parseInt((process.env.EMBED_COLOR || '#5865F2').replace('#', ''), 16);

        const embed = new EmbedBuilder()
            .setColor(color)
            .setTitle(isPaused ? '⏸ Đang tạm dừng' : '🎵 Đang phát')
            .setDescription(`**[${track.title}](${track.url})**`)
            .addFields(
                { name: '👤 Yêu cầu bởi', value: track.requestedBy || 'Không rõ', inline: true },
                { name: '⏱ Thời lượng',   value: track.duration   || '—',        inline: true },
                { name: '📋 Hàng chờ',     value: `${player.queue?.length ?? 0} bài`, inline: true },
            )
            .setFooter({ text: `🎙 ${player.voiceChannel?.name || 'Voice channel'}` })
            .setTimestamp();

        if (track.thumbnail) embed.setThumbnail(track.thumbnail);
        return embed;
    }

    /** Tạo hàng nút điều khiển */
    buildButtons(player) {
        const isPaused  = player.isPaused?.() ?? false;
        const hasQueue  = (player.queue?.length ?? 0) > 0;

        return new ActionRowBuilder().addComponents(
            new ButtonBuilder()
                .setCustomId('music_playpause')
                .setEmoji(isPaused ? '▶️' : '⏸')
                .setStyle(ButtonStyle.Primary),
            new ButtonBuilder()
                .setCustomId('music_skip')
                .setEmoji('⏭')
                .setStyle(ButtonStyle.Secondary)
                .setDisabled(!hasQueue),
            new ButtonBuilder()
                .setCustomId('music_stop')
                .setEmoji('⏹')
                .setStyle(ButtonStyle.Danger),
            new ButtonBuilder()
                .setCustomId('music_shuffle')
                .setEmoji('🔀')
                .setStyle(ButtonStyle.Secondary)
                .setDisabled(!hasQueue),
        );
    }

    /** Gửi hoặc cập nhật embed now-playing */
    async updateNowPlayingEmbed(player) {
        if (!player?.currentTrack) return;
        const guildId = player.guild?.id;
        if (!guildId) return;

        const embed   = this.buildEmbed(player);
        const buttons = this.buildButtons(player);
        if (!embed) return;

        const existing = this.activeEmbeds.get(guildId);

        try {
            if (existing) {
                const channel = await this.client.channels.fetch(existing.channelId).catch(() => null);
                if (channel) {
                    const msg = await channel.messages.fetch(existing.messageId).catch(() => null);
                    if (msg) {
                        await msg.edit({ embeds: [embed], components: [buttons] });
                        return;
                    }
                }
            }
        } catch {}

        // Gửi mới nếu không tìm thấy tin nhắn cũ
        try {
            const textChannel = player.textChannel;
            if (!textChannel) return;
            const msg = await textChannel.send({ embeds: [embed], components: [buttons] });
            this.activeEmbeds.set(guildId, { messageId: msg.id, channelId: textChannel.id });
        } catch (err) {
            console.error(chalk.red('❌ MusicEmbedManager: lỗi gửi embed:'), err.message);
        }
    }

    /** Xử lý khi nhạc kết thúc — ẩn nút điều khiển */
    async handlePlaybackEnd(player) {
        const guildId  = player.guild?.id;
        if (!guildId) return;
        const existing = this.activeEmbeds.get(guildId);
        if (!existing) return;

        try {
            const channel = await this.client.channels.fetch(existing.channelId).catch(() => null);
            if (channel) {
                const msg = await channel.messages.fetch(existing.messageId).catch(() => null);
                if (msg) {
                    const embed = new EmbedBuilder()
                        .setColor(0x2b2d31)
                        .setDescription('✅ Hàng chờ đã hết — bot đã dừng phát nhạc.')
                        .setTimestamp();
                    await msg.edit({ embeds: [embed], components: [] });
                }
            }
        } catch {}

        this.activeEmbeds.delete(guildId);
    }

    /** Xử lý button interaction từ embed */
    async handleButtonInteraction(interaction, players) {
        const { customId, guildId } = interaction;
        const player = players.get(guildId);

        if (!player) {
            return interaction.reply({ content: '❌ Bot chưa phát nhạc!', ephemeral: true });
        }

        await interaction.deferUpdate();

        switch (customId) {
            case 'music_playpause':
                if (player.isPaused?.()) player.resumeFor?.('button');
                else                     player.pauseFor?.('button');
                break;
            case 'music_skip':
                await player.skip?.();
                break;
            case 'music_stop':
                player.queue = [];
                await player.skip?.();
                break;
            case 'music_shuffle':
                player.shuffle?.();
                break;
        }

        await this.updateNowPlayingEmbed(player);
    }
}

module.exports = MusicEmbedManager;
