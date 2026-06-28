// commands/play.js — dùng @distube/ytdl-core để lấy info, play-dl để stream
const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const ytdl = require('@distube/ytdl-core');
const playdl = require('play-dl');
const MusicPlayer = require('../src/MusicPlayer');

// Regex nhận diện URL YouTube
const YT_REGEX = /^(https?:\/\/)?(www\.)?(youtube\.com\/(watch\?v=|shorts\/)|youtu\.be\/)[\w-]+/;

module.exports = {
    data: new SlashCommandBuilder()
        .setName('play')
        .setDescription('Phát nhạc từ YouTube')
        .addStringOption(opt =>
            opt.setName('bai')
                .setDescription('Tên bài hát hoặc URL YouTube')
                .setRequired(true)
        ),

    async execute(interaction, client) {
        const query   = interaction.options.getString('bai');
        const member  = interaction.member;

        const voiceChannel = member.voice?.channel;
        if (!voiceChannel) {
            return interaction.reply({ content: '❌ Bạn cần vào kênh voice trước!', ephemeral: true });
        }

        await interaction.deferReply();

        try {
            let trackInfo;

            if (YT_REGEX.test(query)) {
                // --- URL trực tiếp: dùng ytdl lấy info ---
                const info = await ytdl.getInfo(query);
                const det  = info.videoDetails;
                trackInfo = {
                    title:       det.title,
                    url:         det.video_url,
                    duration:    fmtDuration(parseInt(det.lengthSeconds)),
                    thumbnail:   det.thumbnails?.slice(-1)[0]?.url,
                    requestedBy: member.displayName,
                };
            } else {
                // --- Tìm kiếm theo tên ---
                const results = await playdl.search(query, { source: { youtube: 'video' }, limit: 5 });
                if (!results || results.length === 0) {
                    return interaction.editReply('❌ Không tìm thấy bài hát nào! Thử dùng URL YouTube trực tiếp.');
                }
                const vid = results[0];
                trackInfo = {
                    title:       vid.title,
                    url:         vid.url,
                    duration:    fmtDuration(vid.durationInSec),
                    thumbnail:   vid.thumbnails?.[0]?.url,
                    requestedBy: member.displayName,
                };
            }

            if (!trackInfo?.url) {
                return interaction.editReply('❌ Không lấy được thông tin bài hát!');
            }

            // Lấy hoặc tạo MusicPlayer
            let player = client.players.get(interaction.guildId);
            if (!player) {
                player = new MusicPlayer(interaction.guild, interaction.channel, voiceChannel);
                client.players.set(interaction.guildId, player);
            }

            await player.addTrack(trackInfo);

            const wasEmpty   = player.queue.length === 0;
            const isPlaying  = player.currentTrack?.url === trackInfo.url;

            const embed = new EmbedBuilder()
                .setColor(0x5865F2)
                .setTitle(isPlaying ? '🎵 Đang phát' : '✅ Đã thêm vào hàng chờ')
                .setDescription(`**[${trackInfo.title}](${trackInfo.url})**`)
                .addFields(
                    { name: '⏱ Thời lượng', value: trackInfo.duration || '—', inline: true },
                    { name: '📋 Vị trí',     value: isPlaying ? 'Phát ngay' : `#${player.queue.length}`, inline: true },
                )
                .setFooter({ text: `Yêu cầu bởi ${trackInfo.requestedBy}` });

            if (trackInfo.thumbnail) embed.setThumbnail(trackInfo.thumbnail);
            return interaction.editReply({ embeds: [embed] });

        } catch (err) {
            console.error('❌ /play error:', err);
            return interaction.editReply(`❌ Lỗi: ${err.message}`);
        }
    },
};

function fmtDuration(sec) {
    if (!sec || isNaN(sec)) return '—';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return h > 0
        ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
        : `${m}:${String(s).padStart(2, '0')}`;
}
