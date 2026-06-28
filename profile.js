// commands/profile.js
const { SlashCommandBuilder, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, ModalBuilder, TextInputBuilder, TextInputStyle } = require('discord.js');
const { loadDB, saveDB, makeStars } = require('../src/ProfileManager');

function buildEmbed(profile, member, page) {
    const photos = profile.photos || [];
    const tags = profile.tags || [];
    const votes = profile.votes || {};
    const rating = profile.rating || 0;
    const total = Object.keys(votes).length;
    const name = profile.display_name || member.displayName;

    const embed = new EmbedBuilder()
        .setColor(0x5865F2)
        .setAuthor({ name: `✦ ${name}`, iconURL: member.displayAvatarURL() })
        .setThumbnail(member.displayAvatarURL({ size: 256 }));

    if (tags.length > 0) {
        embed.setDescription(tags.map(t => `✦ ${t}`).join('\n'));
    }

    embed.addFields({
        name: '⭐ Đánh giá',
        value: `${makeStars(Math.round(rating * 10) / 10)} **${Math.round(rating * 10) / 10}**/5.0\n\`${total} lượt vote\``,
        inline: true
    });

    if (photos.length > 0) {
        const idx = Math.max(0, Math.min(page, photos.length - 1));
        embed.setImage(photos[idx]);
        embed.setFooter({ text: `Ảnh ${idx + 1}/${photos.length}` });
    } else {
        embed.setFooter({ text: 'Chưa có ảnh' });
    }

    return embed;
}

function buildButtons(profile, page, targetId) {
    const photos = profile.photos || [];
    const row = new ActionRowBuilder().addComponents(
        new ButtonBuilder()
            .setCustomId(`profile_prev_${targetId}_${page}`)
            .setEmoji('⏮')
            .setStyle(ButtonStyle.Secondary)
            .setDisabled(page <= 0),
        new ButtonBuilder()
            .setCustomId(`profile_page_${targetId}_${page}`)
            .setLabel(`${page + 1}/${Math.max(photos.length, 1)}`)
            .setStyle(ButtonStyle.Secondary)
            .setDisabled(true),
        new ButtonBuilder()
            .setCustomId(`profile_next_${targetId}_${page}`)
            .setEmoji('⏭')
            .setStyle(ButtonStyle.Secondary)
            .setDisabled(page >= photos.length - 1),
        new ButtonBuilder()
            .setCustomId(`profile_rate_${targetId}`)
            .setLabel('⭐ Đánh giá')
            .setStyle(ButtonStyle.Primary)
    );
    return row;
}

module.exports = {
    data: new SlashCommandBuilder()
        .setName('profile')
        .setDescription('Xem profile của một thành viên')
        .addUserOption(opt => opt.setName('thanh_vien').setDescription('Thành viên muốn xem').setRequired(true)),

    async execute(interaction) {
        const member = interaction.options.getMember('thanh_vien');
        const uid = member.id;
        const db = loadDB();

        if (!db[uid]) {
            return interaction.reply({ content: `❌ **${member.displayName}** chưa có profile.`, ephemeral: true });
        }

        const embed = buildEmbed(db[uid], member, 0);
        const row = buildButtons(db[uid], 0, uid);
        await interaction.reply({ embeds: [embed], components: [row] });
    },

    buildEmbed,
    buildButtons,
};
