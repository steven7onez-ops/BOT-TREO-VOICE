// src/MusicPlayer.js — lõi phát nhạc (play-dl + @discordjs/voice)
const {
    joinVoiceChannel,
    createAudioPlayer,
    createAudioResource,
    AudioPlayerStatus,
    VoiceConnectionStatus,
    entersState,
    getVoiceConnection,
} = require('@discordjs/voice');
const playdl = require('play-dl');
const chalk  = require('chalk');
const PlayerStateManager = require('./PlayerStateManager');

const INACTIVITY_TIMEOUT = 5 * 60 * 1000; // 5 phút

class MusicPlayer {
    constructor(guild, textChannel, voiceChannel) {
        this.guild        = guild;
        this.textChannel  = textChannel;
        this.voiceChannel = voiceChannel;

        this.queue        = [];
        this.currentTrack = null;
        this.audioPlayer  = createAudioPlayer();
        this.connection   = null;
        this.loop         = false;  // lặp bài
        this.queueLoop    = false;  // lặp hàng chờ
        this.volume       = 1.0;

        this.pauseReasons = new Set();
        this._inactivityTimer = null;
        this.pendingEndReason = null;

        this.audioPlayer.on(AudioPlayerStatus.Idle, () => this._onTrackEnd());
        this.audioPlayer.on('error', err => {
            console.error(chalk.red('❌ AudioPlayer error:'), err.message);
            this._onTrackEnd();
        });
    }

    // ── Kết nối voice ─────────────────────────────────────────────────────────

    async connect() {
        if (this.connection?.state?.status === VoiceConnectionStatus.Ready) return;

        this.connection = joinVoiceChannel({
            channelId: this.voiceChannel.id,
            guildId:   this.guild.id,
            adapterCreator: this.guild.voiceAdapterCreator,
            selfDeaf:  true,
            selfMute:  false,
        });

        this.connection.subscribe(this.audioPlayer);

        this.connection.on(VoiceConnectionStatus.Disconnected, async () => {
            try {
                await Promise.race([
                    entersState(this.connection, VoiceConnectionStatus.Signalling, 5_000),
                    entersState(this.connection, VoiceConnectionStatus.Connecting, 5_000),
                ]);
            } catch {
                this.cleanup();
            }
        });

        try {
            await entersState(this.connection, VoiceConnectionStatus.Ready, 15_000);
        } catch {
            this.connection.destroy();
            throw new Error('Không thể kết nối voice channel sau 15 giây.');
        }
    }

    // ── Thêm bài / phát ────────────────────────────────────────────────────────

    /**
     * Thêm bài vào hàng chờ và phát nếu đang rảnh
     * @param {Object} track - { title, url, duration, thumbnail, requestedBy }
     */
    async addTrack(track) {
        this.queue.push(track);
        if (this.audioPlayer.state.status === AudioPlayerStatus.Idle) {
            await this._playNext();
        }
    }

    async _playNext() {
        if (this.queue.length === 0) {
            this.currentTrack = null;
            this.startInactivityTimer();
            const embedManager = global.clients?.musicEmbedManager;
            if (embedManager) await embedManager.handlePlaybackEnd(this);
            return;
        }

        this.currentTrack = this.queue.shift();
        this.clearInactivityTimer(false);

        try {
            await this.connect();
            const stream = await playdl.stream(this.currentTrack.url, { quality: 2 });
            const resource = createAudioResource(stream.stream, {
                inputType: stream.type,
                inlineVolume: true,
            });
            resource.volume?.setVolume(this.volume);
            this.audioPlayer.play(resource);

            console.log(chalk.green(`▶ Đang phát: ${this.currentTrack.title}`));

            const embedManager = global.clients?.musicEmbedManager;
            if (embedManager) await embedManager.updateNowPlayingEmbed(this);

            await this.persistState('play');
        } catch (err) {
            console.error(chalk.red(`❌ Lỗi phát nhạc: ${err.message}`));
            this.textChannel?.send(`❌ Không thể phát **${this.currentTrack?.title}**: ${err.message}`).catch(() => {});
            this.currentTrack = null;
            await this._playNext();
        }
    }

    _onTrackEnd() {
        if (this.loop && this.currentTrack) {
            this.queue.unshift(this.currentTrack);
        } else if (this.queueLoop && this.currentTrack) {
            this.queue.push(this.currentTrack);
        }
        this._playNext();
    }

    // ── Điều khiển ─────────────────────────────────────────────────────────────

    pauseFor(reason) {
        this.pauseReasons.add(reason);
        if (this.audioPlayer.state.status !== AudioPlayerStatus.Paused) {
            this.audioPlayer.pause(true);
            return true;
        }
        return false;
    }

    resumeFor(reason) {
        this.pauseReasons.delete(reason);
        if (this.pauseReasons.size === 0 && this.audioPlayer.state.status === AudioPlayerStatus.Paused) {
            this.audioPlayer.unpause();
            return true;
        }
        return false;
    }

    isPaused() {
        return this.audioPlayer.state.status === AudioPlayerStatus.Paused;
    }

    async skip() {
        this.audioPlayer.stop(true);
    }

    stop() {
        this.queue = [];
        this.currentTrack = null;
        this.audioPlayer.stop(true);
    }

    shuffle() {
        for (let i = this.queue.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [this.queue[i], this.queue[j]] = [this.queue[j], this.queue[i]];
        }
    }

    setVolume(pct) {
        this.volume = Math.max(0, Math.min(2, pct / 100));
        // Áp dụng ngay nếu đang phát
        const resource = this.audioPlayer.state?.resource;
        if (resource?.volume) resource.volume.setVolume(this.volume);
    }

    async moveToChannel(newChannel) {
        this.voiceChannel = newChannel;
        if (this.connection) {
            const newConn = joinVoiceChannel({
                channelId: newChannel.id,
                guildId:   this.guild.id,
                adapterCreator: this.guild.voiceAdapterCreator,
                selfDeaf: true,
                selfMute: false,
            });
            newConn.subscribe(this.audioPlayer);
            this.connection = newConn;
        }
    }

    // ── Inactivity timer ───────────────────────────────────────────────────────

    startInactivityTimer() {
        this.clearInactivityTimer(false);
        this._inactivityTimer = setTimeout(async () => {
            console.log(chalk.yellow(`⏰ Không có ai nghe nhạc — bot tự rời kênh`));
            this.textChannel?.send('⏰ Không có ai trong kênh, bot tự rời sau 5 phút.').catch(() => {});
            this.cleanup();
        }, INACTIVITY_TIMEOUT);
    }

    clearInactivityTimer(resumeIfPaused = true) {
        if (this._inactivityTimer) {
            clearTimeout(this._inactivityTimer);
            this._inactivityTimer = null;
        }
        if (resumeIfPaused) this.resumeFor('alone');
    }

    // ── State persistence ──────────────────────────────────────────────────────

    async persistState(reason = 'update', immediate = false) {
        if (!this.guild) return;
        const state = {
            guildId:       this.guild.id,
            voiceChannelId: this.voiceChannel?.id,
            textChannelId:  this.textChannel?.id,
            currentTrack:  this.currentTrack,
            queue:         this.queue,
            loop:          this.loop,
            queueLoop:     this.queueLoop,
            volume:        this.volume,
            reason,
        };
        await PlayerStateManager.saveState(this.guild.id, state);
    }

    async restoreFromState(state) {
        this.loop      = state.loop      ?? false;
        this.queueLoop = state.queueLoop ?? false;
        this.volume    = state.volume    ?? 1.0;

        if (state.currentTrack) {
            this.queue.unshift(state.currentTrack);
        }
        this.queue.push(...(state.queue || []));

        if (this.queue.length > 0) {
            await this._playNext();
        }
    }

    // ── Cleanup ────────────────────────────────────────────────────────────────

    cleanup() {
        this.clearInactivityTimer(false);
        this.audioPlayer.stop(true);
        try {
            const conn = getVoiceConnection(this.guild.id);
            if (conn) conn.destroy();
        } catch {}
        if (this.connection) {
            try { this.connection.destroy(); } catch {}
            this.connection = null;
        }
        PlayerStateManager.removeState(this.guild.id).catch(() => {});
    }
}

module.exports = MusicPlayer;
