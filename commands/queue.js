// commands/queue.js — xem hàng chờ
const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('queue')
        .setDescription('Xem hàng chờ phát nhạc')
        .addIntegerOption(opt =>
            opt.setName('trang').setDescription('Số trang').setMinValue(1)
        ),

    async execute(interaction, client) {
        const player = client.players.get(interaction.guildId);
        if (!player) return interaction.reply({ content: '❌ Bot chưa phát nhạc!', ephemeral: true });

        const page     = (interaction.options.getInteger('trang') || 1) - 1;
        const perPage  = 10;
        const queue    = player.queue;
        const total    = queue.length;
        const pages    = Math.max(1, Math.ceil(total / perPage));
        const safeP    = Math.min(page, pages - 1);

        const slice = queue.slice(safeP * perPage, safeP * perPage + perPage);
        const lines = slice.map((t, i) => `\`${safeP * perPage + i + 1}.\` [${t.title}](${t.url}) — ${t.duration || '—'}`);

        const embed = new EmbedBuilder()
            .setColor(0x5865F2)
            .setTitle('📋 Hàng chờ')
            .setDescription(
                (player.currentTrack
                    ? `**Đang phát:** [${player.currentTrack.title}](${player.currentTrack.url})\n\n`
                    : '') +
                (lines.length ? lines.join('\n') : 'Hàng chờ trống')
            )
            .setFooter({ text: `Trang ${safeP + 1}/${pages} • Tổng ${total} bài` });

        return interaction.reply({ embeds: [embed] });
    },
};
