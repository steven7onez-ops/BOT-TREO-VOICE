// src/ProfileManager.js — đọc/ghi database profile JSON
const fs = require('fs');
const path = require('path');

const DB_DIR  = path.join(__dirname, '..', 'database');
const DB_FILE = path.join(DB_DIR, 'profiles.json');

// Tạo thư mục database nếu chưa có
if (!fs.existsSync(DB_DIR)) fs.mkdirSync(DB_DIR, { recursive: true });

function loadDB() {
    try {
        if (!fs.existsSync(DB_FILE)) return {};
        return JSON.parse(fs.readFileSync(DB_FILE, 'utf8'));
    } catch {
        return {};
    }
}

function saveDB(data) {
    try {
        fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2), 'utf8');
    } catch (err) {
        console.error('❌ Lỗi lưu database:', err.message);
    }
}

/**
 * Tạo chuỗi sao từ rating
 * @param {number} rating - 0 đến 5
 * @returns {string}
 */
function makeStars(rating) {
    const full    = Math.floor(rating);
    const half    = rating % 1 >= 0.5 ? 1 : 0;
    const empty   = 5 - full - half;
    return '⭐'.repeat(full) + (half ? '✨' : '') + '☆'.repeat(empty);
}

module.exports = { loadDB, saveDB, makeStars };
