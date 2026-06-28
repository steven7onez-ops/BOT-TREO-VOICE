// commands/profile_addphoto.js — thêm ảnh vào profile
const { SlashCommandBuilder } = require('discord.js');
const { loadDB, saveDB } = require('../src/ProfileManager');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('profile_addphoto')
        .setDescription('Thêm ảnh vào profile (tối đa 10 ảnh)')
        .addStringOption(opt =>
            opt.setName('url').setDescription('URL ảnh trực tiếp (jpg/png/gif)').setRequired(true)
        ),

    async execute(interaction) {
        const uid = interaction.user.id;
        const url = interaction.options.getString('url');

        // Validate URL cơ bản
        try { new URL(url); } catch {
            return interaction.reply({ content: '❌ URL không hợp lệ!', ephemeral: true });
        }

        const db = loadDB();
        if (!db[uid]) db[uid] = { photos: [], tags: [], votes: {}, rating: 0 };
        if (db[uid].photos.length >= 10) {
            return interaction.reply({ content: '❌ Tối đa 10 ảnh — hãy xóa bớt trước!', ephemeral: true });
        }

        db[uid].photos.push(url);
        saveDB(db);
        return interaction.reply({ content: `✅ Đã thêm ảnh thứ **${db[uid].photos.length}**!`, ephemeral: true });
    },
};
