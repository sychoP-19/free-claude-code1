/* JARVIS — Intelligence System JS Engine */
'use strict';

// ─── CLOCK ───────────────────────────────────────────────────────────────────
function updateClock() {
  const el = document.getElementById('clock');
  if (el) el.textContent = new Date().toLocaleTimeString('en-US', { hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

// ─── PARTICLE SYSTEM ─────────────────────────────────────────────────────────
(function initParticles() {
  const canvas = document.getElementById('particle-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  function resize() {
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  const particles = Array.from({ length: 60 }, () => ({
    x: Math.random() * window.innerWidth,
    y: Math.random() * window.innerHeight,
    vx: (Math.random() - 0.5) * 0.4,
    vy: (Math.random() - 0.5) * 0.4,
    r: Math.random() * 1.5 + 0.5,
    a: Math.random() * 0.5 + 0.1,
  }));

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx*dx + dy*dy);
        if (dist < 120) {
          ctx.beginPath();
          ctx.strokeStyle = `rgba(0,212,255,${0.12 * (1 - dist/120)})`;
          ctx.lineWidth = 0.5;
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.stroke();
        }
      }
    }
    particles.forEach(p => {
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0,212,255,${p.a})`;
      ctx.shadowBlur = 6;
      ctx.shadowColor = '#00d4ff';
      ctx.fill();
      ctx.shadowBlur = 0;
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > canvas.width)  p.vx *= -1;
      if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
    });
    requestAnimationFrame(draw);
  }
  draw();
})();

// ─── WEBSOCKET ────────────────────────────────────────────────────────────────
let ws = null;
let wsReconnectTimer = null;

function connectWebSocket() {
  try {
    ws = new WebSocket(`ws://${location.host}/ws`);
    ws.onopen = () => { setWsStatus(true); clearTimeout(wsReconnectTimer); notify('System connected', 'success'); };
    ws.onmessage = (e) => { try { handleServerMessage(JSON.parse(e.data)); } catch {} };
    ws.onclose = () => { setWsStatus(false); wsReconnectTimer = setTimeout(connectWebSocket, 3000); };
    ws.onerror = () => ws.close();
  } catch {
    setWsStatus(false);
    wsReconnectTimer = setTimeout(connectWebSocket, 3000);
  }
}

function setWsStatus(online) {
  const dot  = document.getElementById('ws-dot');
  const text = document.getElementById('ws-status');
  if (!dot || !text) return;
  dot.style.background = online ? 'var(--green)' : 'var(--yellow)';
  dot.style.boxShadow  = online ? '0 0 8px var(--green)' : '0 0 8px var(--yellow)';
  text.textContent     = online ? 'LIVE' : 'RECONNECTING...';
}

function handleServerMessage(msg) {
  if (msg.type === 'log')          appendFeed(msg.level || 'info', msg.text);
  if (msg.type === 'agent_update') updateAgentCard(msg.agent, msg.status, msg.progress);
  if (msg.type === 'metric')       updateMetric(msg.key, msg.value);
  if (msg.type === 'notify')       notify(msg.text, msg.level || 'info');
  if (msg.type === 'system')       updateSysStats(msg.cpu, msg.mem);
}

function sendWs(data) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(data));
}

// ─── LIVE FEED ─────────────────────────────────────────────────────────────
function appendFeed(level, text) {
  const feed = document.getElementById('live-feed');
  if (!feed) return;
  const now  = new Date().toLocaleTimeString('en-US', { hour12: false });

  const line    = document.createElement('div');
  line.className = 'feed-line';

  const timeSpan = document.createElement('span');
  timeSpan.className   = 'feed-time';
  timeSpan.textContent = now;

  const msgSpan = document.createElement('span');
  msgSpan.className   = 'feed-msg ' + level;
  msgSpan.textContent = text;          // textContent — no XSS risk

  line.appendChild(timeSpan);
  line.appendChild(msgSpan);
  feed.appendChild(line);
  feed.scrollTop = feed.scrollHeight;
  while (feed.children.length > 200) feed.removeChild(feed.firstChild);
}

// ─── AGENT CARDS ─────────────────────────────────────────────────────────────
function updateAgentCard(agentId, status, progress = 0) {
  const card    = document.getElementById('agent-' + agentId);
  const progBar = document.getElementById('prog-' + agentId);
  const statEl  = document.getElementById('stat-' + agentId);
  if (card)    card.classList.toggle('active', status === 'running');
  if (progBar) progBar.style.width  = progress + '%';
  if (statEl)  statEl.textContent   = status.toUpperCase();
}

// ─── METRICS ─────────────────────────────────────────────────────────────────
function updateMetric(key, value) {
  const el = document.getElementById('metric-' + key);
  if (el) el.textContent = value;
}

function updateSysStats(cpu, mem) {
  const cpuVal = document.getElementById('cpu-val');
  const cpuBar = document.getElementById('cpu-bar');
  const memVal = document.getElementById('mem-val');
  const memBar = document.getElementById('mem-bar');
  if (cpuVal) cpuVal.textContent = cpu + '%';
  if (cpuBar) cpuBar.style.width = cpu + '%';
  if (memVal) memVal.textContent = mem + '%';
  if (memBar) memBar.style.width = mem + '%';
}

// ─── NOTIFICATIONS ────────────────────────────────────────────────────────────
function notify(text, type, duration) {
  type     = type     || 'info';
  duration = duration || 4000;
  const container = document.getElementById('notifications');
  if (!container) return;
  const el = document.createElement('div');
  el.className   = 'notif ' + type;
  el.textContent = text;
  container.appendChild(el);
  setTimeout(() => {
    el.style.opacity    = '0';
    el.style.transition = 'opacity 0.3s';
    setTimeout(() => el.remove(), 300);
  }, duration);
}

// ─── PROGRESS RINGS ──────────────────────────────────────────────────────────
function setProgressRing(ringId, pct) {
  const ring = document.getElementById(ringId);
  if (!ring) return;
  const r = 54;
  const circumference = 2 * Math.PI * r;
  ring.style.strokeDasharray  = circumference;
  ring.style.strokeDashoffset = circumference * (1 - pct / 100);
}

// ─── PROFIT BARS ─────────────────────────────────────────────────────────────
function animateProfitBars() {
  document.querySelectorAll('.profit-bar-fill[data-pct]').forEach(bar => {
    setTimeout(() => { bar.style.width = bar.dataset.pct + '%'; }, 300);
  });
}

// ─── API HELPERS ─────────────────────────────────────────────────────────────
async function api(path, method, body) {
  method = method || 'GET';
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  try {
    const res = await fetch(path, opts);
    return await res.json();
  } catch (e) {
    notify('API error: ' + e.message, 'error');
    return null;
  }
}

// ─── AGENT RUNNER ─────────────────────────────────────────────────────────────
async function runAgent(agentName, params) {
  params = params || {};
  notify('Starting ' + agentName + '...', 'info');
  const btn = document.getElementById('btn-' + agentName);
  if (btn) { btn.disabled = true; btn.textContent = 'RUNNING...'; }
  const result = await api('/api/agents/' + agentName + '/run', 'POST', params);
  if (btn) { btn.disabled = false; btn.textContent = 'RUN'; }
  if (result && result.status === 'ok') notify(agentName + ' completed', 'success');
  return result;
}

// ─── REPO STATUS TABLE ────────────────────────────────────────────────────────
async function loadRepoStatus() {
  const data = await api('/api/repos/status');
  if (!data) return;
  const okCount = Object.values(data).filter(v => v.status === 'ok').length;
  const counter = document.getElementById('repos-count');
  if (counter) counter.textContent = okCount;

  const tbody = document.getElementById('repos-table-body');
  if (!tbody) return;
  tbody.textContent = '';   // clear safely

  Object.entries(data).forEach(([name, info]) => {
    const ok  = info.status === 'ok';
    const row = document.createElement('tr');

    const tdName = document.createElement('td');
    tdName.className   = 'text-mono';
    tdName.textContent = name;

    const tdStatus = document.createElement('td');
    const badge    = document.createElement('span');
    badge.className   = 'badge ' + (ok ? 'badge-green' : 'badge-red');
    badge.textContent = ok ? 'READY' : 'MISSING';
    tdStatus.appendChild(badge);

    const tdPath = document.createElement('td');
    tdPath.className   = 'text-mono text-xs text-muted';
    tdPath.textContent = info.path || '';

    row.appendChild(tdName);
    row.appendChild(tdStatus);
    row.appendChild(tdPath);
    tbody.appendChild(row);
  });
}

// ─── TYPING EFFECT ───────────────────────────────────────────────────────────
function typeText(el, text, speed) {
  speed = speed || 20;
  el.textContent = '';
  let i = 0;
  const timer = setInterval(() => {
    el.textContent += text[i++];
    if (i >= text.length) clearInterval(timer);
  }, speed);
}

// ─── COUNTER ANIMATION ───────────────────────────────────────────────────────
function animateCounter(el, target, duration) {
  duration = duration || 1500;
  const start = performance.now();
  function step(now) {
    const p = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.floor(target * eased).toLocaleString();
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ─── STORYBOARD ───────────────────────────────────────────────────────────────
function selectShot(index) {
  document.querySelectorAll('.storyboard-shot').forEach((s, i) => {
    s.classList.toggle('active', i === index);
  });
}

// ─── DASHBOARD REFRESH ────────────────────────────────────────────────────────
async function refreshDashboard() {
  const data = await api('/api/dashboard/metrics');
  if (!data) return;
  ['videos-generated', 'channels-analyzed', 'trends-found'].forEach(k => {
    if (data[k.replace(/-/g, '_')] !== undefined)
      updateMetric(k, data[k.replace(/-/g, '_')]);
  });
}

// ─── INIT ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  connectWebSocket();
  animateProfitBars();
  loadRepoStatus();

  document.querySelectorAll('[data-ring-pct]').forEach(el => {
    setProgressRing(el.id, parseInt(el.dataset.ringPct));
  });

  document.querySelectorAll('[data-count]').forEach(el => {
    animateCounter(el, parseInt(el.dataset.count));
  });

  document.querySelectorAll('.storyboard-shot').forEach((s, i) => {
    s.addEventListener('click', () => selectShot(i));
  });

  setInterval(refreshDashboard, 10000);
  refreshDashboard();

  // Heartbeat sim until real data
  setInterval(() => {
    updateSysStats(
      Math.floor(20 + Math.random() * 40),
      Math.floor(30 + Math.random() * 30)
    );
  }, 5000);
});
