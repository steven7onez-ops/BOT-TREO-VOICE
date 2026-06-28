// src/Dashboard.js - Web dashboard
const express = require('express');
const path = require('path');

const DASHBOARD_KEY = process.env.DASHBOARD_KEY || 'changeme';

function checkKey(req, res, next) {
    if (req.headers['x-api-key'] !== DASHBOARD_KEY) {
        return res.status(401).json({ error: 'Invalid API key' });
    }
    next();
}

const DASHBOARD_HTML = `<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bot Dashboard</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.11.0/dist/tabler-icons.min.css">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0f0f14;--sur:#1a1a24;--sur2:#22222f;--bd:rgba(255,255,255,.08);--bd2:rgba(255,255,255,.14);--tx:#e8e8f0;--tx2:#9090a8;--tx3:#5a5a70;--ac:#5865f2;--ac-g:rgba(88,101,242,.18);--gr:#3ba55d;--gr-g:rgba(59,165,93,.12);--rd:#ed4245;--rd-g:rgba(237,66,69,.12);--yw:#faa61a;--r:10px;--rs:6px}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);color:var(--tx);min-height:100vh}
.hd{display:flex;align-items:center;gap:12px;padding:14px 24px;border-bottom:1px solid var(--bd);background:var(--sur)}
.hd-logo{width:34px;height:34px;border-radius:50%;background:var(--ac);display:flex;align-items:center;justify-content:center}.hd-logo i{font-size:17px;color:#fff}
.hd-title{font-size:15px;font-weight:600}.hd-sub{font-size:11px;color:var(--tx2);margin-top:1px}
.pill{margin-left:auto;display:flex;align-items:center;gap:5px;padding:4px 11px;border-radius:20px;font-size:12px;font-weight:500}
.pill.on{background:var(--gr-g);color:var(--gr)}.pill.off{background:var(--rd-g);color:var(--rd)}
.dot{width:7px;height:7px;border-radius:50%;background:currentColor;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.auth-wrap{position:fixed;inset:0;background:rgba(10,10,16,.92);display:flex;align-items:center;justify-content:center;z-index:100;backdrop-filter:blur(4px)}
.auth-box{background:var(--sur);border:1px solid var(--bd2);border-radius:var(--r);padding:28px 24px;width:100%;max-width:380px}
.auth-title{font-size:16px;font-weight:600;margin-bottom:6px}.auth-sub{font-size:13px;color:var(--tx2);margin-bottom:18px}
.wrap{max-width:820px;margin:0 auto;padding:20px 16px}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:12px}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
@media(max-width:580px){.g3,.g2{grid-template-columns:1fr}}
.card{background:var(--sur);border:1px solid var(--bd);border-radius:var(--r);padding:16px 18px}
.card-title{font-size:10px;font-weight:600;color:var(--tx3);text-transform:uppercase;letter-spacing:.07em;margin-bottom:10px}
.stat-val{font-size:24px;font-weight:700}.stat-lbl{font-size:12px;color:var(--tx2);margin-top:2px}.stat-ico{float:right;font-size:20px;color:var(--ac);opacity:.8}
.inp{width:100%;padding:9px 13px;border-radius:var(--rs);background:var(--sur2);border:1px solid var(--bd2);color:var(--tx);font-size:13px;outline:none;transition:border-color .2s;margin-bottom:10px}
.inp:focus{border-color:var(--ac)}.inp::placeholder{color:var(--tx3)}
.btn{padding:9px 16px;border-radius:var(--rs);border:none;font-size:13px;font-weight:500;cursor:pointer;transition:opacity .15s,transform .1s;display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.btn:active{transform:scale(.97)}.btn-ac{background:var(--ac);color:#fff;width:100%}.btn-gr{background:var(--gr);color:#fff;flex:1}.btn-rd{background:var(--rd);color:#fff;flex:1}.btn-gh{background:transparent;color:var(--tx2);border:1px solid var(--bd2);padding:4px 10px;font-size:12px}.btn:hover{opacity:.88}
.ch-list{display:flex;flex-direction:column;gap:7px;margin-top:8px;max-height:240px;overflow-y:auto}
.ch-item{display:flex;align-items:center;gap:9px;padding:8px 11px;border-radius:var(--rs);border:1px solid var(--bd);background:var(--sur2);cursor:pointer;transition:border-color .15s}
.ch-item:hover{border-color:var(--ac)}.ch-item.active{border-color:var(--ac);background:var(--ac-g)}
.ch-item i{color:var(--ac);font-size:15px}.ch-name{font-size:13px}.ch-guild{font-size:11px;color:var(--tx3)}.ch-cnt{margin-left:auto;font-size:11px;color:var(--tx2)}
.log{background:#0a0a10;border:1px solid var(--bd);border-radius:var(--rs);padding:10px 13px;font-family:'Menlo','Consolas',monospace;font-size:11.5px;color:#a0a0c0;max-height:170px;overflow-y:auto;line-height:1.7}
.log p{margin:0}.log .ok{color:var(--gr)}.log .err{color:var(--rd)}.log .info{color:var(--yw)}
.tgl-row{display:flex;align-items:center;justify-content:space-between;padding:10px 0}.tgl-row+.tgl-row{border-top:1px solid var(--bd)}
.tgl-lbl{font-size:13px}.tgl-desc{font-size:11px;color:var(--tx2);margin-top:2px}
.tgl{position:relative;width:40px;height:22px;flex-shrink:0}.tgl input{display:none}
.tgl-track{position:absolute;inset:0;border-radius:11px;background:var(--sur2);border:1px solid var(--bd2);cursor:pointer;transition:background .2s}
.tgl input:checked+.tgl-track{background:var(--ac);border-color:var(--ac)}
.tgl-thumb{position:absolute;top:3px;left:3px;width:16px;height:16px;border-radius:50%;background:#fff;transition:transform .2s;pointer-events:none}
.tgl input:checked~.tgl-thumb{transform:translateX(18px)}
.alert{padding:9px 13px;border-radius:var(--rs);font-size:12px;margin-bottom:12px;display:none;align-items:center;gap:7px}
.alert.show{display:flex}.alert.ok{background:var(--gr-g);color:var(--gr);border:1px solid rgba(59,165,93,.25)}.alert.err{background:var(--rd-g);color:var(--rd);border:1px solid rgba(237,66,69,.25)}
</style>
</head>
<body>
<div class="auth-wrap" id="auth-wrap">
  <div class="auth-box">
    <div class="auth-title">🎙️ Bot Dashboard</div>
    <div class="auth-sub">Nhập mật khẩu để tiếp tục</div>
    <input class="inp" id="inp-key" type="password" placeholder="Mật khẩu dashboard" onkeydown="if(event.key==='Enter')login()">
    <button class="btn btn-ac" onclick="login()"><i class="ti ti-login"></i> Đăng nhập</button>
    <div class="alert err" id="auth-err" style="margin-top:10px;display:none"><i class="ti ti-alert-circle"></i><span>Mật khẩu sai!</span></div>
  </div>
</div>
<div class="hd">
  <div class="hd-logo"><i class="ti ti-headphones"></i></div>
  <div><div class="hd-title" id="bot-name">Bot Dashboard</div><div class="hd-sub">Đang kết nối...</div></div>
  <span class="pill off" id="pill"><span class="dot"></span><span id="pill-txt">Ngoại tuyến</span></span>
</div>
<div class="wrap">
  <div class="alert" id="alert"><i class="ti ti-alert-circle"></i><span id="alert-msg"></span></div>
  <div class="g3">
    <div class="card"><i class="ti ti-clock stat-ico"></i><div class="card-title">Thời gian chạy</div><div class="stat-val" id="uptime">—</div><div class="stat-lbl">kể từ khi khởi động</div></div>
    <div class="card"><i class="ti ti-microphone stat-ico"></i><div class="card-title">Kênh hiện tại</div><div class="stat-val" style="font-size:16px;line-height:1.4" id="cur-ch">—</div><div class="stat-lbl" id="cur-guild">chưa vào kênh</div></div>
    <div class="card"><i class="ti ti-users stat-ico"></i><div class="card-title">Người trong kênh</div><div class="stat-val" id="cur-mem">—</div><div class="stat-lbl">người (không tính bot)</div></div>
  </div>
  <div class="g2">
    <div class="card">
      <div class="card-title">Chọn kênh voice</div>
      <div class="ch-list" id="ch-list"><div style="color:var(--tx3);font-size:13px">Đang tải...</div></div>
      <div style="display:flex;gap:8px;margin-top:12px">
        <button class="btn btn-gr" onclick="joinSel()"><i class="ti ti-player-play"></i> Vào kênh</button>
        <button class="btn btn-rd" onclick="leaveAll()"><i class="ti ti-door-exit"></i> Rời kênh</button>
      </div>
    </div>
    <div style="display:flex;flex-direction:column;gap:12px">
      <div class="card">
        <div class="card-title">Cài đặt</div>
        <div class="tgl-row"><div><div class="tgl-lbl">Tự động vào lại</div><div class="tgl-desc">Rejoin nếu bị kick</div></div><label class="tgl"><input type="checkbox" id="tgl-rejoin" checked onchange="setRejoin(this.checked)"><div class="tgl-track"></div><div class="tgl-thumb"></div></label></div>
        <div class="tgl-row"><div><div class="tgl-lbl">Follow chủ</div><div class="tgl-desc">Vào kênh khi chủ join</div></div><label class="tgl"><input type="checkbox" id="tgl-follow" checked onchange="setFollow(this.checked)"><div class="tgl-track"></div><div class="tgl-thumb"></div></label></div>
      </div>
      <div class="card" style="flex:1">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px"><div class="card-title" style="margin:0">Nhật ký</div><button class="btn btn-gh" onclick="clrLog()">Xóa</button></div>
        <div class="log" id="log"></div>
      </div>
    </div>
  </div>
</div>
<script>
const SK='__vbot_key__';let key='',sel=null,timer=null;
window.onload=()=>{const s=sessionStorage.getItem(SK);if(s){key=s;document.getElementById('auth-wrap').style.display='none';init();}};
async function login(){key=document.getElementById('inp-key').value.trim();try{await api('/status');sessionStorage.setItem(SK,key);document.getElementById('auth-wrap').style.display='none';init();}catch(e){document.getElementById('auth-err').style.display='flex';key='';}}
function init(){refresh();loadCh();timer=setInterval(refresh,7000);}
async function api(p,m='GET',b=null){const o={method:m,headers:{'Content-Type':'application/json','X-API-Key':key}};if(b)o.body=JSON.stringify(b);const r=await fetch(p,o);if(!r.ok)throw new Error(r.status);return r.json();}
function addLog(msg,t=''){const box=document.getElementById('log');const p=document.createElement('p');p.className=t;p.textContent='['+new Date().toLocaleTimeString('vi-VN')+'] '+msg;box.appendChild(p);box.scrollTop=box.scrollHeight;}
function clrLog(){document.getElementById('log').innerHTML='';}
function showAlert(msg,t='ok'){const el=document.getElementById('alert');el.className='alert show '+t;document.getElementById('alert-msg').textContent=msg;setTimeout(()=>el.classList.remove('show'),3000);}
async function refresh(){try{const s=await api('/status');document.getElementById('bot-name').textContent=s.bot_name||'Bot';const pill=document.getElementById('pill');pill.className='pill '+(s.online?'on':'off');document.getElementById('pill-txt').textContent=s.online?'Trực tuyến':'Ngoại tuyến';document.getElementById('uptime').textContent=s.uptime||'—';if(s.voice&&s.voice.length){const v=s.voice[0];document.getElementById('cur-ch').textContent='#'+v.channel;document.getElementById('cur-guild').textContent=v.guild;document.getElementById('cur-mem').textContent=v.members;}else{document.getElementById('cur-ch').textContent='—';document.getElementById('cur-guild').textContent='chưa vào kênh';document.getElementById('cur-mem').textContent='0';}document.getElementById('tgl-rejoin').checked=!!s.auto_rejoin;document.getElementById('tgl-follow').checked=!!s.follow_owner;}catch(e){document.getElementById('pill').className='pill off';document.getElementById('pill-txt').textContent='Ngoại tuyến';}}
async function loadCh(){try{const chs=await api('/channels');const list=document.getElementById('ch-list');list.innerHTML='';if(!chs.length){list.innerHTML='<div style="color:var(--tx3);font-size:13px">Không có kênh nào</div>';return;}chs.forEach(ch=>{const d=document.createElement('div');d.className='ch-item';d.innerHTML='<i class="ti ti-volume"></i><div><div class="ch-name">'+ch.channel_name+'</div><div class="ch-guild">'+ch.guild_name+'</div></div><span class="ch-cnt">'+ch.members+'</span>';d.onclick=()=>{document.querySelectorAll('.ch-item').forEach(i=>i.classList.remove('active'));d.classList.add('active');sel=ch.channel_id;};list.appendChild(d);});}catch(e){addLog('Lỗi tải kênh: '+e.message,'err');}}
async function joinSel(){if(!sel){showAlert('Chọn kênh trước!','err');return;}try{const r=await api('/join','POST',{channel_id:sel});if(r.success){addLog('Đã vào kênh','ok');showAlert('Bot đã vào kênh!');}else{addLog('Thất bại','err');showAlert('Thất bại','err');}await refresh();await loadCh();}catch(e){addLog('Lỗi: '+e.message,'err');}}
async function leaveAll(){try{await api('/leave','POST');addLog('Bot đã rời kênh','ok');showAlert('Bot đã rời kênh!');await refresh();}catch(e){addLog('Lỗi: '+e.message,'err');}}
async function setRejoin(v){try{await api('/auto_rejoin','POST',{enabled:v});addLog('Tự động vào lại: '+(v?'BẬT':'TẮT'),'info');}catch(e){}}
async function setFollow(v){try{await api('/follow_owner','POST',{enabled:v});addLog('Follow chủ: '+(v?'BẬT':'TẮT'),'info');}catch(e){}}
</script>
</body>
</html>`;

function startDashboard(client, voiceKeeper, port) {
    const app = express();
    app.use(express.json());

    app.get('/', (req, res) => res.send(DASHBOARD_HTML));

    app.get('/status', checkKey, (req, res) => {
        res.json(voiceKeeper.getStatus());
    });

    app.post('/join', checkKey, async (req, res) => {
        const { channel_id } = req.body;
        let success = false;
        for (const guild of client.guilds.cache.values()) {
            const channel = guild.channels.cache.get(channel_id);
            if (channel) {
                await voiceKeeper.joinChannel(channel);
                success = true;
                break;
            }
        }
        res.json({ success });
    });

    app.post('/leave', checkKey, (req, res) => {
        voiceKeeper.leaveAll();
        res.json({ success: true });
    });

    app.post('/auto_rejoin', checkKey, (req, res) => {
        voiceKeeper.autoRejoin = !!req.body.enabled;
        res.json({ auto_rejoin: voiceKeeper.autoRejoin });
    });

    app.post('/follow_owner', checkKey, (req, res) => {
        voiceKeeper.followOwner = !!req.body.enabled;
        res.json({ follow_owner: voiceKeeper.followOwner });
    });

    app.get('/channels', checkKey, (req, res) => {
        const result = [];
        for (const guild of client.guilds.cache.values()) {
            for (const channel of guild.channels.cache.values()) {
                if (channel.type === 2) { // GUILD_VOICE
                    result.push({
                        guild_id: guild.id,
                        guild_name: guild.name,
                        channel_id: channel.id,
                        channel_name: channel.name,
                        members: channel.members.filter(m => !m.user.bot).size,
                    });
                }
            }
        }
        res.json(result);
    });

    app.listen(port, () => {
        console.log(`🌐 Dashboard chạy tại port ${port}`);
    });
}

module.exports = { startDashboard };
