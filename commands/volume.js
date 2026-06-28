// commands/volume.js
const { SlashCommandBuilder } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('volume')
        .setDescription('Chỉnh âm lượng (0–200%)')
        .addIntegerOption(opt =>
            opt.setName('muc').setDescription('Âm lượng (0-200)').setMinValue(0).setMaxValue(200).setRequired(true)
        ),

    async execute(interaction, client) {
        const player = client.players.get(interaction.guildId);
        if (!player) return interaction.reply({ content: '❌ Bot chưa phát nhạc!', ephemeral: true });
        const vol = interaction.options.getInteger('muc');
        player.setVolume(vol);
        return interaction.reply(`🔊 Đã chỉnh âm lượng: **${vol}%**`);
    },
};
