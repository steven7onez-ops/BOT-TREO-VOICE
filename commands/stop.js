// commands/stop.js
const { SlashCommandBuilder } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('stop')
        .setDescription('Dừng nhạc và xóa hàng chờ'),

    async execute(interaction, client) {
        const player = client.players.get(interaction.guildId);
        if (!player) return interaction.reply({ content: '❌ Bot chưa phát nhạc!', ephemeral: true });
        player.stop();
        player.cleanup();
        client.players.delete(interaction.guildId);
        return interaction.reply('⏹ Đã dừng và rời kênh!');
    },
};
