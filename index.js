const { Client, GatewayIntentBits, Collection, Events, ActivityType } = require('discord.js');
const { getVoiceConnection } = require('@discordjs/voice');
const fs = require('fs');
const fsPromises = require('fs').promises;
const path = require('path');
const config = require('./config');
const PlayerStateManager = require('./src/PlayerStateManager');
const MusicPlayer = require('./src/MusicPlayer');
const chalk = require('chalk');

require("./src/commandLoader"); // Load and deploy commands

// Clean up audio cache directory on startup
async function cleanupAudioCache() {
    const cacheDir = path.join(__dirname, 'audio_cache');

    try {
        if (fs.existsSync(cacheDir)) {
            const files = await fsPromises.readdir(cacheDir);
            const protectedFiles = PlayerStateManager.getProtectedCacheFiles();
            
            let deletedCount = 0;
            let skippedCount = 0;

            for (const file of files) {
                const absolutePath = path.join(cacheDir, file);

                if (protectedFiles.has(path.resolve(absolutePath))) {
                    skippedCount++;
                    continue;
                }

                try {
                    await fsPromises.unlink(absolutePath);
                    deletedCount++;
                } catch (err) {
                    console.error(chalk.red(`❌ Failed to delete ${file}:`), err.message);
                }
            }
        } else {
            fs.mkdirSync(cacheDir, { recursive: true });
        }
    } catch (error) {
        console.error(chalk.red('❌ Failed to cleanup audio cache:'), error.message);
    }
}

async function restoreSavedPlayers(client) {
    const savedStates = PlayerStateManager.getAllStates();
    const entries = Object.entries(savedStates || {});
    if (entries.length === 0) return;

    console.log(chalk.cyan(`🔄 Found ${entries.length} saved session(s) to restore...`));

    for (const [guildId, state] of entries) {
        try {
            // Wait for guild to be available in cache
            let guild = client.guilds.cache.get(guildId);
            
            if (!guild) {
                // Try fetching with retry logic for sharding
                let retries = 3;
                while (!guild && retries > 0) {
                    try {
                        await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second
                        guild = await client.guilds.fetch(guildId).catch(() => null);
                        if (guild) break;
                    } catch (error) {
                        retries--;
                    }
                }
            }

            if (!guild) {
                console.log(chalk.yellow(`⚠️ Guild ${guildId} not found or not accessible, removing state...`));
                await PlayerStateManager.removeState(guildId);
                continue;
            }

            const voiceChannelId = state.voiceChannelId;
            const textChannelId = state.textChannelId;

            if (!voiceChannelId || !textChannelId) {
                await PlayerStateManager.removeState(guildId);
                continue;
            }

            let voiceChannel = guild.channels.cache.get(voiceChannelId) || null;
            if (!voiceChannel) {
                voiceChannel = await guild.channels.fetch(voiceChannelId).catch(() => null);
            }

            let textChannel = guild.channels.cache.get(textChannelId) || null;
            if (!textChannel) {
                textChannel = await guild.channels.fetch(textChannelId).catch(() => null);
            }

            const isVoiceValid = voiceChannel && typeof voiceChannel.isVoiceBased === 'function' && voiceChannel.isVoiceBased();
            const isTextValid = textChannel && typeof textChannel.isTextBased === 'function' && textChannel.isTextBased();

            if (!isVoiceValid || !isTextValid) {
                console.log(chalk.yellow(`⚠️ Invalid channels for guild ${guild.name}, removing state...`));
                await PlayerStateManager.removeState(guildId);
                continue;
            }

            const player = new MusicPlayer(guild, textChannel, voiceChannel);
            client.players.set(guildId, player);

            try {
                await player.restoreFromState(state);
                console.log(chalk.green(`✅ Successfully restored session for guild ${guild.name}`));
            } catch (error) {
                console.error(chalk.red(`❌ Failed to restore music session for guild ${guild.name} (${guildId}):`), error.message);
                client.players.delete(guildId);
                player.cleanup();
                await PlayerStateManager.removeState(guildId);
            }
        } catch (error) {
            console.error(chalk.red(`❌ Error during session restoration for guild ${guildId}:`), error.message);
            await PlayerStateManager.removeState(guildId);
        }
    }
}

// Don't cleanup audio cache yet - wait until after we check saved states
setTimeout(() => {
    const client = new Client({
        intents: [
            GatewayIntentBits.Guilds,
            GatewayIntentBits.GuildMessages,
            GatewayIntentBits.MessageContent,
            GatewayIntentBits.GuildVoiceStates,
            GatewayIntentBits.GuildMembers,
        ]
        // ShardingManager automatically sets shard ID and count via environment variables
        // No need to specify shards/shardCount here - they are auto-injected
    });

    // Collections for commands and music players
    client.commands = new Collection();
    client.players = new Collection();

    // Initialize Music Embed Manager
    const MusicEmbedManager = require('./src/MusicEmbedManager');
    client.musicEmbedManager = new MusicEmbedManager(client);

    // Global reference for MusicPlayer'dan erişim
    if (!global.clients) global.clients = {};
    global.clients.musicEmbedManager = client.musicEmbedManager;

    // Load command files
    const loadCommands = () => {
        const commandsPath = path.join(__dirname, 'commands');

        // Create commands directory if it doesn't exist
        if (!fs.existsSync(commandsPath)) {
            fs.mkdirSync(commandsPath, { recursive: true });
        }

        try {
            const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.js'));

            for (const file of commandFiles) {
                const filePath = path.join(commandsPath, file);
                const command = require(filePath);

                if ('data' in command && 'execute' in command) {
                    client.commands.set(command.data.name, command);
                    console.log(chalk.green(`✓ Loaded command: ${command.data.name}`));
                } else {
                    console.log(chalk.yellow(`⚠ Warning: ${file} is missing required "data" or "execute" property.`));
                }
            }
        } catch (error) {
            console.log(chalk.yellow('⚠ No commands directory found, skipping command loading.'));
        }
    };

    // Load event handlers
    const loadEvents = () => {
        const eventsPath = path.join(__dirname, 'events');

        // Create events directory if it doesn't exist
        if (!fs.existsSync(eventsPath)) {
            fs.mkdirSync(eventsPath, { recursive: true });
        }

        try {
            const eventFiles = fs.readdirSync(eventsPath).filter(file => file.endsWith('.js'));

            for (const file of eventFiles) {
                const filePath = path.join(eventsPath, file);
                const event = require(filePath);

                if (event.once) {
                    client.once(event.name, (...args) => event.execute(...args));
                } else {
                    client.on(event.name, (...args) => event.execute(...args));
                }
                console.log(chalk.green(`✓ Loaded event: ${event.name}`));
            }
        } catch (error) {
            console.log(chalk.yellow('⚠ No events directory found, using default events.'));
        }
    };

    // Basic ready event
    client.once(Events.ClientReady, async () => {
        console.log(chalk.green(`✅ [SHARD ${client.shard?.ids[0] ?? 0}] ${client.user.tag} is online and ready!`));
        console.log(chalk.cyan(`🎵 [SHARD ${client.shard?.ids[0] ?? 0}] Music bot serving ${client.guilds.cache.size} servers on this shard!`));
        
        // Log total guild count across all shards (only if running with sharding)
        // Wait a bit to ensure all shards are ready before fetching
        if (client.shard) {
            setTimeout(() => {
                client.shard.fetchClientValues('guilds.cache.size')
                    .then(results => {
                        const totalGuilds = results.reduce((acc, guildCount) => acc + guildCount, 0);
                        console.log(chalk.magenta(`🌐 [SHARD ${client.shard.ids[0]}] Total servers across all shards: ${totalGuilds}`));
                    })
                    .catch(err => {
                        // Silently fail if shards are still spawning
                        if (!err.message.includes('still being spawned')) {
                            console.error(chalk.red('Error fetching total guild count:'), err);
                        }
                    });
            }, 10000); // Wait 10 seconds for other shards to be ready
        }

        // Set bot activity
        setInterval(() => client.user.setActivity({ name: `${config.bot.status}`, type: ActivityType.Listening }), 10000);

        // Don't restore here in sharded mode - wait for shard manager to broadcast
        // For non-sharded mode, restore immediately
        if (!client.shard) {
            console.log(chalk.cyan('⏳ Non-sharded mode: waiting for guilds to be fully cached...'));
            await new Promise(resolve => setTimeout(resolve, 5000));
            await client.restoreSessions();
        }
    });

    // Add restore function to client for shard manager to call
    client.restoreSessions = async function() {
        console.log(chalk.cyan(`[SHARD ${client.shard?.ids?.[0] ?? 'N/A'}] 🔄 Starting session restore...`));
        await restoreSavedPlayers(client);
        await cleanupAudioCache();
        console.log(chalk.green(`[SHARD ${client.shard?.ids?.[0] ?? 'N/A'}] ✅ Session restore complete`));
    };

    // Handle interactions (slash commands)
    client.on(Events.InteractionCreate, async interaction => {
        if (!interaction.isChatInputCommand()) return;

        const command = client.commands.get(interaction.commandName);

        if (!command) {
            console.error(chalk.red(`❌ No command matching ${interaction.commandName} was found.`));
            return;
        }

        try {
            await command.execute(interaction, client);
        } catch (error) {
            console.error(chalk.red(`❌ Error executing ${interaction.commandName}:`), error);

            const errorMessage = '❌ An error occurred while executing this command!';

            if (interaction.replied || interaction.deferred) {
                await interaction.followUp({ content: errorMessage, ephemeral: true });
            } else {
                await interaction.reply({ content: errorMessage, ephemeral: true });
            }
        }
    });

    // Handle voice state updates for pause/resume and cleanup
    client.on(Events.VoiceStateUpdate, async (oldState, newState) => {
        const guild = oldState.guild;
        const player = client.players.get(guild.id);
        if (!player) return;

        const botMember = guild.members.me;
        const botId = botMember?.id ?? client.user.id;
        const involvesBot = oldState.id === botId || newState.id === botId;

        if (involvesBot) {
            const oldChannelId = oldState.channelId;
            const newChannelId = newState.channelId;

            if (oldChannelId && !newChannelId) {
                try {
                    const embedManager = client.musicEmbedManager || global.clients?.musicEmbedManager;

                    // Mark state as ended so UI reflects the change
                    player.pendingEndReason = 'forced-disconnect';
                    player.queue = [];
                    player.currentTrack = null;

                    if (embedManager) {
                        await embedManager.handlePlaybackEnd(player);
                    } else if (typeof player.showQueueCompleted === 'function') {
                        await player.showQueueCompleted();
                    }
                } catch (error) {
                    console.error('❌ Failed to update playback UI after forced disconnect:', error);
                } finally {
                    player.cleanup();
                    client.players.delete(guild.id);
                }
                return;
            }

            if (newChannelId && oldChannelId !== newChannelId) {
                if (newState.channel) {
                    await player.moveToChannel(newState.channel);
                    player.clearInactivityTimer(false);
                    if (client.musicEmbedManager) {
                        await client.musicEmbedManager.updateNowPlayingEmbed(player);
                    }
                }
            }

            const wasMuted = oldState.serverMute || oldState.serverDeaf || oldState.suppress;
            const isMuted = newState.serverMute || newState.serverDeaf || newState.suppress;

            if (!wasMuted && isMuted) {
                const paused = player.pauseFor('mute');
                if (paused && client.musicEmbedManager) {
                    await client.musicEmbedManager.updateNowPlayingEmbed(player);
                }
            } else if (wasMuted && !isMuted) {
                const resumed = player.resumeFor('mute');
                if (client.musicEmbedManager && (resumed || !player.pauseReasons.has('mute'))) {
                    await client.musicEmbedManager.updateNowPlayingEmbed(player);
                }
            }
        }

        const voiceChannelId = player.voiceChannel?.id;
        if (!voiceChannelId) return;

        if (oldState.channelId === voiceChannelId || newState.channelId === voiceChannelId) {
            const channel = guild.channels.cache.get(voiceChannelId);

            if (!channel) {
                player.cleanup();
                client.players.delete(guild.id);
                return;
            }

            const listeners = channel.members.filter(member => !member.user.bot).size;

            if (listeners === 0) {
                const alreadyPaused = player.pauseReasons.has('alone');
                player.startInactivityTimer();
                if (!alreadyPaused && client.musicEmbedManager && player.currentTrack) {
                    await client.musicEmbedManager.updateNowPlayingEmbed(player);
                }
            } else {
                const wasPausedForAlone = player.pauseReasons.has('alone');
                player.clearInactivityTimer(true);
                if (wasPausedForAlone && client.musicEmbedManager && player.currentTrack) {
                    await client.musicEmbedManager.updateNowPlayingEmbed(player);
                }
            }
        }
    });

    // Handle process termination
    process.on('SIGINT', () => {

        // Disconnect from all voice channels
        client.players.forEach((player, guildId) => {
            player.stop();
            const connection = getVoiceConnection(guildId);
            if (connection) connection.destroy();
        });

        client.destroy();
        process.exit(0);
    });

    // Error handling
    process.on('unhandledRejection', (reason, promise) => {
        console.error(chalk.red('❌ Unhandled Rejection at:'), promise, chalk.red('reason:'), reason);

        // Discord API error handling
        if (reason && reason.code) {
            switch (reason.code) {
                case 10062: // Unknown interaction
                    console.log(chalk.yellow('ℹ️ Interaction has expired, safely ignoring...'));
                    return;
                case 40060: // Interaction already acknowledged
                    console.log(chalk.yellow('ℹ️ Interaction already acknowledged, safely ignoring...'));
                    return;
                case 50013: // Missing permissions
                    console.error(chalk.red('❌ Missing permissions for Discord action'));
                    return;
            }
        }

        // Voice connection errors
        if (reason && reason.message && reason.message.includes('IP discovery')) {
            // Clean up any voice connections
            client.players.forEach(player => {
                if (player && player.cleanup) {
                    player.cleanup();
                }
            });
            client.players.clear();
            return;
        }
    });

    process.on('uncaughtException', (error) => {
        console.error(chalk.red('❌ Uncaught Exception:'), error);

        // Don't exit on Discord API errors
        if (error.code === 10062 || error.code === 40060) {
            console.log(chalk.yellow('ℹ️ Discord interaction error handled, continuing...'));
            return;
        }

        // Handle fetch/network termination errors - don't crash
        if (error.message && (error.message.includes('terminated') || 
            error.message.includes('ECONNRESET') || 
            error.message.includes('ETIMEDOUT'))) {
            console.log(chalk.yellow('⚠️ Network error occurred, but bot continues running...'));
            return;
        }

        // For other critical errors, graceful shutdown
        console.log(chalk.red('🛑 Critical error occurred, shutting down...'));

        // Clean up all music players
        if (client && client.players) {
            client.players.forEach(player => {
                if (player && player.cleanup) {
                    player.cleanup();
                }
            });
            client.players.clear();
        }

        process.exit(1);
    });

    // ── VoiceKeeper & Dashboard ────────────────────────────────────────────────
    const VoiceKeeper = require('./src/VoiceKeeper');
    const { startDashboard } = require('./src/Dashboard');
    const voiceKeeper = new VoiceKeeper(client);

    // Ready: join kênh voice mặc định + khởi động dashboard
    client.once(Events.ClientReady, async () => {
        // Join kênh voice mặc định nếu có
        const voiceChannelId = process.env.VOICE_CHANNEL_ID;
        if (voiceChannelId) {
            for (const guild of client.guilds.cache.values()) {
                const ch = guild.channels.cache.get(voiceChannelId);
                if (ch) { await voiceKeeper.joinChannel(ch); break; }
            }
        }
    });

    // Follow owner vào voice
    client.on(Events.VoiceStateUpdate, async (oldState, newState) => {
        await voiceKeeper.handleVoiceStateUpdate(oldState, newState);
    });

    // Xử lý button profile
    client.on(Events.InteractionCreate, async interaction => {
        if (interaction.isButton()) {
            const { customId } = interaction;
            if (customId.startsWith('profile_prev_') || customId.startsWith('profile_next_')) {
                const parts = customId.split('_');
                const targetId = parts[2]; const currentPage = parseInt(parts[3]) || 0;
                const isPrev = customId.startsWith('profile_prev_');
                const { loadDB } = require('./src/ProfileManager');
                const { buildEmbed, buildButtons } = require('./commands/profile');
                const db = loadDB(); const profile = db[targetId];
                if (!profile) return interaction.reply({ content: '❌ Profile không còn tồn tại!', ephemeral: true });
                const member = await interaction.guild.members.fetch(targetId).catch(() => null);
                if (!member) return interaction.reply({ content: '❌ Không tìm thấy thành viên!', ephemeral: true });
                const photos = profile.photos || [];
                const newPage = isPrev ? Math.max(0, currentPage - 1) : Math.min(photos.length - 1, currentPage + 1);
                return interaction.update({ embeds: [buildEmbed(profile, member, newPage)], components: [buildButtons(profile, newPage, targetId)] });
            }
            if (customId.startsWith('profile_rate_')) {
                const { ModalBuilder, TextInputBuilder, TextInputStyle, ActionRowBuilder } = require('discord.js');
                const targetId = customId.replace('profile_rate_', '');
                const modal = new ModalBuilder().setCustomId('rate_modal_' + targetId).setTitle('Đánh giá thành viên');
                const input = new TextInputBuilder().setCustomId('score').setLabel('Số điểm (1-5)').setStyle(TextInputStyle.Short).setPlaceholder('Nhập số từ 1 đến 5 (vd: 4.5)').setRequired(true).setMaxLength(3);
                modal.addComponents(new ActionRowBuilder().addComponents(input));
                return interaction.showModal(modal);
            }
        }
        if (interaction.isModalSubmit() && interaction.customId.startsWith('rate_modal_')) {
            const targetId = interaction.customId.replace('rate_modal_', '');
            const val = parseFloat(interaction.fields.getTextInputValue('score').replace(',', '.'));
            if (isNaN(val) || val < 1 || val > 5) return interaction.reply({ content: '❌ Điểm không hợp lệ!', ephemeral: true });
            if (interaction.user.id === targetId) return interaction.reply({ content: '❌ Không thể tự đánh giá!', ephemeral: true });
            const { loadDB, saveDB } = require('./src/ProfileManager');
            const { buildEmbed, buildButtons } = require('./commands/profile');
            const db = loadDB(); const p = db[targetId] || {};
            if (!p.votes) p.votes = {};
            p.votes[interaction.user.id] = val;
            p.rating = Object.values(p.votes).reduce((a,b)=>a+b,0)/Object.keys(p.votes).length;
            db[targetId] = p; saveDB(db);
            const member = await interaction.guild.members.fetch(targetId).catch(()=>null);
            if (member) return interaction.update({ embeds: [buildEmbed(p, member, 0)], components: [buildButtons(p, 0, targetId)] });
            return interaction.reply({ content: '✅ Đã đánh giá!', ephemeral: true });
        }
    });

    // Prefix commands
    client.on(Events.MessageCreate, async message => {
        if (message.author.bot || !message.content.startsWith('+')) return;
        const args = message.content.slice(1).trim().split(/\s+/);
        const cmd = args.shift().toLowerCase();
        if (cmd === 'ping') {
            const ms = Math.round(client.ws.ping);
            const st = voiceKeeper.getStatus();
            return message.reply({ embeds: [{ color: 0x5865F2, title: '🏓 Pong!', fields: [
                { name: '📶 Độ trễ', value: '`'+ms+'ms`', inline: true },
                { name: '⏱️ Uptime', value: '`'+st.uptime+'`', inline: true },
                { name: '🎙️ Voice', value: st.voice.length ? '#'+st.voice[0].channel+' ('+st.voice[0].guild+')' : '❌ Chưa vào kênh', inline: false },
            ], footer: { text: 'Bot: '+client.user.tag } }] });
        }
        if (cmd === 'help' || cmd === 'h') {
            return message.reply({ embeds: [{ color: 0x5865F2, title: '📖 Danh sách lệnh', fields: [
                { name: '🔧 Lệnh thường', value: '`+ping` — Kiểm tra bot\n`+help` — Danh sách lệnh', inline: false },
                { name: '🎵 Nhạc (Slash)', value: '`/play` `//nowplaying` `/search` `/help`', inline: false },
                { name: '👤 Profile (Slash)', value: '`/profile @user` `/profile_set` `/profile_addphoto` `/profile_delete`', inline: false },
            ], footer: { text: 'Prefix: + | Bot: '+client.user.tag } }] });
        }
    });

    // Initialize bot
    const init = async () => {
        try {
            console.log(chalk.blue('🤖 Starting Discord Music Bot...'));

            // Start dashboard
            const port = parseInt(process.env.PORT) || 8080;
            startDashboard(client, voiceKeeper, port);

            // Load commands and events
            loadCommands();
            loadEvents();

            // Graceful shutdown handler
            const gracefulShutdown = async (signal) => {
                // Save all active player states before shutdown
                const savePromises = [];
                for (const [guildId, player] of client.players) {
                    if (player && typeof player.persistState === 'function') {
                         // Use immediate=true to bypass debouncing
                        savePromises.push(player.persistState('shutdown', true).catch(err => {
                            console.error(chalk.red(`Failed to save state for guild ${guildId}:`), err);
                        }));
                    }
                }
                
                await Promise.all(savePromises);
                // Give time for saves to complete
                await new Promise(resolve => setTimeout(resolve, 1000));
                
                process.exit(0);
            };

            // Register shutdown handlers
            process.on('SIGINT', () => gracefulShutdown('SIGINT'));
            process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
            
            // Windows specific handlers
            if (process.platform === 'win32') {
                const readline = require('readline');
                if (process.stdin.isTTY) {
                    readline.createInterface({
                        input: process.stdin,
                        output: process.stdout
                    }).on('SIGINT', () => gracefulShutdown('SIGINT'));
                }
            }

            // Login to Discord
            await client.login(config.discord.token);

        } catch (error) {
            console.error(chalk.red('❌ Failed to start bot:'), error);
            process.exit(1);
        }
    };

    // Start the bot
    init();

    module.exports = client;
}, 5000);