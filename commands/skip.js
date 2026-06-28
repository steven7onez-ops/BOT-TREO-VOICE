// commands/skip.js
const { SlashCommandBuilder } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('skip')
        .setDescription('Bỏ qua bài hiện tại'),

    async execute(interaction, client) {
        const player = client.players.get(interaction.guildId);
        if (!player?.currentTrack) return interaction.reply({ content: '❌ Không có bài nào đang phát!', ephemeral: true });
        await player.skip();
        return interaction.reply('⏭ Đã bỏ qua bài!');
    },
};
