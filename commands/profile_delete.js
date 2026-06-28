// commands/profile_delete.js — xoá profile
const { SlashCommandBuilder } = require('discord.js');
const { loadDB, saveDB } = require('../src/ProfileManager');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('profile_delete')
        .setDescription('Xoá toàn bộ profile của bạn'),

    async execute(interaction) {
        const uid = interaction.user.id;
        const db  = loadDB();
        if (!db[uid]) return interaction.reply({ content: '❌ Bạn chưa có profile!', ephemeral: true });
        delete db[uid];
        saveDB(db);
        return interaction.reply({ content: '🗑️ Đã xoá profile!', ephemeral: true });
    },
};
