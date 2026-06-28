// commands/nowplaying.js — xem bài đang phát
const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const { makeStars } = require('../src/ProfileManager');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('nowplaying')
        .setDescription('Xem bài nhạc đang phát'),

    async execute(interaction, client) {
        const player = client.players.get(interaction.guildId);

        if (!player?.currentTrack) {
            return interaction.reply({ content: '❌ Bot không đang phát nhạc nào!', ephemeral: true });
        }

        const t = player.currentTrack;
        const embed = new EmbedBuilder()
            .setColor(0x5865F2)
            .setTitle(player.isPaused() ? '⏸ Đang tạm dừng' : '🎵 Đang phát')
            .setDescription(`**[${t.title}](${t.url})**`)
            .addFields(
                { name: '⏱ Thời lượng',  value: t.duration || '—',                  inline: true },
                { name: '👤 Yêu cầu bởi', value: t.requestedBy || '—',               inline: true },
                { name: '📋 Hàng chờ',    value: `${player.queue.length} bài tiếp`, inline: true },
                { name: '🔁 Lặp',          value: player.loop ? 'Bật (bài)' : player.queueLoop ? 'Bật (hàng)' : 'Tắt', inline: true },
            )
            .setFooter({ text: `🎙 ${player.voiceChannel?.name || '—'}` })
            .setTimestamp();

        if (t.thumbnail) embed.setThumbnail(t.thumbnail);
        return interaction.reply({ embeds: [embed] });
    },
};
