// src/PlayerStateManager.js — lưu/khôi phục trạng thái player qua restart
const fs   = require('fs');
const path = require('path');
const chalk = require('chalk');

const STATE_FILE = path.join(__dirname, '..', 'database', 'player_states.json');

// Đảm bảo thư mục tồn tại
const dbDir = path.dirname(STATE_FILE);
if (!fs.existsSync(dbDir)) fs.mkdirSync(dbDir, { recursive: true });

function _load() {
    try {
        if (!fs.existsSync(STATE_FILE)) return {};
        return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    } catch {
        return {};
    }
}

function _save(data) {
    try {
        fs.writeFileSync(STATE_FILE, JSON.stringify(data, null, 2), 'utf8');
    } catch (err) {
        console.error(chalk.red('❌ PlayerStateManager: lỗi lưu state:'), err.message);
    }
}

const PlayerStateManager = {
    getAllStates() {
        return _load();
    },

    getState(guildId) {
        return _load()[guildId] || null;
    },

    async saveState(guildId, state) {
        const all = _load();
        all[guildId] = { ...state, savedAt: Date.now() };
        _save(all);
    },

    async removeState(guildId) {
        const all = _load();
        delete all[guildId];
        _save(all);
    },

    /** Trả về Set<string> các đường dẫn cache cần giữ lại */
    getProtectedCacheFiles() {
        const states = _load();
        const protected_ = new Set();
        for (const state of Object.values(states)) {
            if (state.currentTrack?.cachePath) {
                protected_.add(path.resolve(state.currentTrack.cachePath));
            }
            for (const t of (state.queue || [])) {
                if (t.cachePath) protected_.add(path.resolve(t.cachePath));
            }
        }
        return protected_;
    },
};

module.exports = PlayerStateManager;
