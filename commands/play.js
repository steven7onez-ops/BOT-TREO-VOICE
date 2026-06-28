// commands/play.js — lệnh /play tìm & phát nhạc
const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const playdl = require('play-dl');
const MusicPlayer = require('../src/MusicPlayer');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('play')
        .setDescription('Phát nhạc từ YouTube / SoundCloud / Spotify')
        .addStringOption(opt =>
            opt.setName('bai')
                .setDescription('Tên bài hát hoặc URL')
                .setRequired(true)
        ),

    async execute(interaction, client) {
        const query = interaction.options.getString('bai');
        const member = interaction.member;

        // Kiểm tra user có trong voice không
        const voiceChannel = member.voice?.channel;
        if (!voiceChannel) {
            return interaction.reply({ content: '❌ Bạn cần vào kênh voice trước!', ephemeral: true });
        }

        await interaction.deferReply();

        try {
            let trackInfo;

            // Xác định loại input
            const urlType = await playdl.validate(query).catch(() => 'search');

            if (urlType === 'yt_video') {
                const info = await playdl.video_info(query);
                const det  = info.video_details;
                trackInfo = {
                    title:       det.title,
                    url:         det.url,
                    duration:    fmtDuration(det.durationInSec),
                    thumbnail:   det.thumbnails?.[0]?.url,
                    requestedBy: member.displayName,
                };
            } else if (urlType === 'yt_playlist') {
                return interaction.editReply('⚠️ Playlist chưa được hỗ trợ, hãy gửi link bài đơn lẻ.');
            } else {
                // Tìm kiếm
                const results = await playdl.search(query, { source: { youtube: 'video' }, limit: 1 });
                if (!results.length) return interaction.editReply('❌ Không tìm thấy bài hát nào!');
                const vid = results[0];
                trackInfo = {
                    title:       vid.title,
                    url:         vid.url,
                    duration:    fmtDuration(vid.durationInSec),
                    thumbnail:   vid.thumbnails?.[0]?.url,
                    requestedBy: member.displayName,
                };
            }

            // Lấy hoặc tạo MusicPlayer
            let player = client.players.get(interaction.guildId);
            if (!player) {
                player = new MusicPlayer(interaction.guild, interaction.channel, voiceChannel);
                client.players.set(interaction.guildId, player);
            }

            // Thêm bài vào hàng chờ
            await player.addTrack(trackInfo);

            const isPlaying = player.currentTrack?.url === trackInfo.url;
            const embed = new EmbedBuilder()
                .setColor(0x5865F2)
                .setTitle(isPlaying ? '🎵 Đang phát' : '✅ Đã thêm vào hàng chờ')
                .setDescription(`**[${trackInfo.title}](${trackInfo.url})**`)
                .addFields(
                    { name: '⏱ Thời lượng', value: trackInfo.duration || '—', inline: true },
                    { name: '📋 Vị trí',     value: isPlaying ? 'Phát ngay' : `#${player.queue.length + 1}`, inline: true },
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
