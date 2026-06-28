// src/MusicPlayer.js — stream bằng @distube/ytdl-core
const {
    joinVoiceChannel,
    createAudioPlayer,
    createAudioResource,
    AudioPlayerStatus,
    VoiceConnectionStatus,
    entersState,
    getVoiceConnection,
    StreamType,
} = require('@discordjs/voice');
const ytdl  = require('@distube/ytdl-core');
const chalk = require('chalk');
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
        this.loop         = false;
        this.queueLoop    = false;
        this.volume       = 1.0;

        this.pauseReasons      = new Set();
        this._inactivityTimer  = null;
        this.pendingEndReason  = null;

        this.audioPlayer.on(AudioPlayerStatus.Idle, () => this._onTrackEnd());
        this.audioPlayer.on('error', err => {
            console.error(chalk.red('❌ AudioPlayer error:'), err.message);
            this._onTrackEnd();
        });
    }

    // ── Kết nối voice ─────────────────────────────────────────────────────────

    async connect() {
        const existing = getVoiceConnection(this.guild.id);
        if (existing && existing.state.status === VoiceConnectionStatus.Ready) {
            this.connection = existing;
            this.connection.subscribe(this.audioPlayer);
            return;
        }

        this.connection = joinVoiceChannel({
            channelId:      this.voiceChannel.id,
            guildId:        this.guild.id,
            adapterCreator: this.guild.voiceAdapterCreator,
            selfDeaf:       true,
            selfMute:       false,
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
            await entersState(this.connection, VoiceConnectionStatus.Ready, 20_000);
        } catch {
            this.connection.destroy();
            throw new Error('Không thể kết nối voice channel sau 20 giây.');
        }
    }

    // ── Phát nhạc ─────────────────────────────────────────────────────────────

    async addTrack(track) {
        this.queue.push(track);
        if (this.audioPlayer.state.status === AudioPlayerStatus.Idle && !this.currentTrack) {
            await this._playNext();
        }
    }

    async _playNext() {
        if (this.queue.length === 0) {
            this.currentTrack = null;
            this.startInactivityTimer();
            const em = global.clients?.musicEmbedManager;
            if (em) await em.handlePlaybackEnd(this);
            return;
        }

        this.currentTrack = this.queue.shift();
        this.clearInactivityTimer(false);

        try {
            await this.connect();

            // Stream bằng ytdl-core
            const stream = ytdl(this.currentTrack.url, {
                filter:  'audioonly',
                quality: 'highestaudio',
                highWaterMark: 1 << 25, // 32MB buffer
            });

            const resource = createAudioResource(stream, {
                inputType:    StreamType.Arbitrary,
                inlineVolume: true,
            });
            resource.volume?.setVolume(this.volume);

            this.audioPlayer.play(resource);
            console.log(chalk.green(`▶ Đang phát: ${this.currentTrack.title}`));

            const em = global.clients?.musicEmbedManager;
            if (em) await em.updateNowPlayingEmbed(this);

            await this.persistState('play');
        } catch (err) {
            console.error(chalk.red(`❌ Lỗi phát: ${err.message}`));
            this.textChannel?.send(`❌ Không thể phát **${this.currentTrack?.title}**: ${err.message}`).catch(() => {});
            this.currentTrack = null;
            setTimeout(() => this._playNext(), 1000);
        }
    }

    _onTrackEnd() {
        if (this.loop && this.currentTrack) {
            this.queue.unshift(this.currentTrack);
        } else if (this.queueLoop && this.currentTrack) {
            this.queue.push(this.currentTrack);
        }
        this.currentTrack = null;
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
        this.queue        = [];
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
        const resource = this.audioPlayer.state?.resource;
        if (resource?.volume) resource.volume.setVolume(this.volume);
    }

    async moveToChannel(newChannel) {
        this.voiceChannel = newChannel;
        if (this.connection) {
            const newConn = joinVoiceChannel({
                channelId:      newChannel.id,
                guildId:        this.guild.id,
                adapterCreator: this.guild.voiceAdapterCreator,
                selfDeaf: true,
                selfMute: false,
            });
            newConn.subscribe(this.audioPlayer);
            this.connection = newConn;
        }
    }

    // ── Inactivity ─────────────────────────────────────────────────────────────

    startInactivityTimer() {
        this.clearInactivityTimer(false);
        this._inactivityTimer = setTimeout(async () => {
            console.log(chalk.yellow('⏰ Không có ai nghe — bot tự rời'));
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
            guildId:        this.guild.id,
            voiceChannelId: this.voiceChannel?.id,
            textChannelId:  this.textChannel?.id,
            currentTrack:   this.currentTrack,
            queue:          this.queue,
            loop:           this.loop,
            queueLoop:      this.queueLoop,
            volume:         this.volume,
            reason,
        };
        await PlayerStateManager.saveState(this.guild.id, state);
    }

    async restoreFromState(state) {
        this.loop      = state.loop      ?? false;
        this.queueLoop = state.queueLoop ?? false;
        this.volume    = state.volume    ?? 1.0;
        if (state.currentTrack) this.queue.unshift(state.currentTrack);
        this.queue.push(...(state.queue || []));
        if (this.queue.length > 0) await this._playNext();
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
