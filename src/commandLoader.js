// src/commandLoader.js — deploy slash commands lên Discord API
const { REST, Routes } = require('discord.js');
const fs = require('fs');
const path = require('path');
const chalk = require('chalk');
const config = require('../config');

const commands = [];
const commandsPath = path.join(__dirname, '..', 'commands');

// Tạo thư mục commands nếu chưa có
if (!fs.existsSync(commandsPath)) {
    fs.mkdirSync(commandsPath, { recursive: true });
}

try {
    const commandFiles = fs.readdirSync(commandsPath).filter(f => f.endsWith('.js'));
    for (const file of commandFiles) {
        const cmd = require(path.join(commandsPath, file));
        if (cmd?.data?.toJSON) {
            commands.push(cmd.data.toJSON());
            console.log(chalk.cyan(`📦 Queued command: ${cmd.data.name}`));
        }
    }
} catch (err) {
    console.log(chalk.yellow('⚠ Không tìm thấy commands nào để deploy.'));
}

if (commands.length > 0) {
    const rest = new REST().setToken(config.discord.token);

    (async () => {
        try {
            console.log(chalk.blue(`🔄 Deploying ${commands.length} slash command(s)...`));

            const target = config.discord.guildId
                ? Routes.applicationGuildCommands(config.discord.clientId, config.discord.guildId)
                : Routes.applicationCommands(config.discord.clientId);

            await rest.put(target, { body: commands });
            console.log(chalk.green(`✅ Slash commands deployed thành công!`));
        } catch (err) {
            console.error(chalk.red('❌ Lỗi deploy commands:'), err.message);
        }
    })();
}

module.exports = { commands };
