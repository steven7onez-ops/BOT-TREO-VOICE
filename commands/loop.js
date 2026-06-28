// commands/loop.js
const { SlashCommandBuilder } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('loop')
        .setDescription('Bật/tắt lặp nhạc')
        .addStringOption(opt =>
            opt.setName('mode')
                .setDescription('Chế độ lặp')
                .setRequired(true)
                .addChoices(
                    { name: '🔂 Lặp bài hiện tại', value: 'track' },
                    { name: '🔁 Lặp hàng chờ',     value: 'queue' },
                    { name: '❌ Tắt lặp',           value: 'off'   },
                )
        ),

    async execute(interaction, client) {
        const player = client.players.get(interaction.guildId);
        if (!player) return interaction.reply({ content: '❌ Bot chưa phát nhạc!', ephemeral: true });

        const mode = interaction.options.getString('mode');
        player.loop      = mode === 'track';
        player.queueLoop = mode === 'queue';

        const msg = { track: '🔂 Lặp bài hiện tại: **BẬT**', queue: '🔁 Lặp hàng chờ: **BẬT**', off: '❌ Đã tắt lặp' }[mode];
        return interaction.reply(msg);
    },
};
