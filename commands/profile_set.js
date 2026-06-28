// commands/profile_set.js — đặt tên hiển thị và tags cho profile
const { SlashCommandBuilder } = require('discord.js');
const { loadDB, saveDB } = require('../src/ProfileManager');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('profile_set')
        .setDescription('Cập nhật thông tin profile của bạn')
        .addStringOption(opt =>
            opt.setName('ten').setDescription('Tên hiển thị').setRequired(false)
        )
        .addStringOption(opt =>
            opt.setName('tags').setDescription('Tags (phân cách bởi dấu phẩy, vd: gamer, coder)').setRequired(false)
        ),

    async execute(interaction) {
        const uid  = interaction.user.id;
        const db   = loadDB();
        if (!db[uid]) db[uid] = { photos: [], tags: [], votes: {}, rating: 0 };

        const ten  = interaction.options.getString('ten');
        const tags = interaction.options.getString('tags');

        if (ten)  db[uid].display_name = ten.trim();
        if (tags) db[uid].tags = tags.split(',').map(t => t.trim()).filter(Boolean).slice(0, 10);

        saveDB(db);
        return interaction.reply({ content: '✅ Đã cập nhật profile!', ephemeral: true });
    },
};
