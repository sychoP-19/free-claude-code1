/* JARVIS mission-control live feed — WebSocket-driven agent event stream.
   - Exponential backoff reconnect
   - Live event cards per agent column (newest at top, max 10 shown)
   - Reactor SVG responds to active agent count
   - All DOM writes use createElement/textContent/appendChild only
*/
'use strict';

(function () {
  const COLS   = ['researcher', 'strategist', 'writer', 'designer', 'publisher'];
  const MAX_PER_COL = 10;

  // Per-column event buffers (newest first)
  const _buffers = {};
  COLS.forEach(c => { _buffers[c] = []; });

  // ── DOM builders ──────────────────────────────────────────────────────────

  function buildEventCard(ev) {
    const div = document.createElement('div');
    div.className = 'mc-event mc-event--' + (ev.kind || 'act');

    const ts = document.createElement('div');
    ts.className = 'mc-event__ts';
    const d = new Date((ev.ts || Date.now() / 1000) * 1000);
    const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    ts.textContent = timeStr + ' · ' + (ev.kind || '');

    const msg = document.createElement('div');
    msg.className = 'mc-event__msg';
    msg.textContent = ev.message || '';

    div.appendChild(ts);
    div.appendChild(msg);
    return div;
  }

  function renderColumn(colName) {
    const host = document.getElementById('mc-col-' + colName);
    if (!host) return;

    const events = _buffers[colName].slice(0, MAX_PER_COL);

    // Remove cards beyond limit
    while (host.children.length > MAX_PER_COL) {
      host.removeChild(host.lastChild);
    }

    if (!events.length) {
      if (!host.firstChild) {
        const empty = document.createElement('div');
        empty.style.cssText = 'opacity:0.35;font-size:11px;padding:8px;font-family:var(--font-data,monospace)';
        empty.textContent = 'no activity yet';
        host.appendChild(empty);
      }
      return;
    }

    // Clear empty state
    if (host.firstChild && host.firstChild.style && host.firstChild.style.opacity === '0.35') {
      host.textContent = '';
    }

    // Rebuild from buffer (newest at top)
    host.textContent = '';
    events.forEach(ev => host.appendChild(buildEventCard(ev)));
  }

  function prependEvent(colName, ev) {
    if (!_buffers[colName]) return;
    _buffers[colName].unshift(ev);
    if (_buffers[colName].length > MAX_PER_COL * 2) {
      _buffers[colName] = _buffers[colName].slice(0, MAX_PER_COL * 2);
    }

    const host = document.getElementById('mc-col-' + colName);
    if (!host) return;

    // Remove empty-state placeholder
    if (host.firstChild && host.firstChild.style && host.firstChild.style.opacity === '0.35') {
      host.textContent = '';
    }

    const card = buildEventCard(ev);
    card.style.opacity = '0';
    card.style.transform = 'translateY(-8px)';
    card.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    host.insertBefore(card, host.firstChild);

    // Animate in
    requestAnimationFrame(() => {
      card.style.opacity = '1';
      card.style.transform = 'translateY(0)';
    });

    // Trim overflow
    while (host.children.length > MAX_PER_COL) {
      host.removeChild(host.lastChild);
    }
  }

  // ── Reactor + agent heads ─────────────────────────────────────────────────

  function updateReactorState(activeSet) {
    const reactor = document.getElementById('mc-reactor');
    const label   = document.getElementById('mc-reactor-label');
    const count   = activeSet.size;

    if (reactor) {
      reactor.dataset.active = String(count);
      // Color: 0 → dim cyan, 1-3 → bright cyan, 4+ → plasma magenta
      if (count === 0) {
        reactor.style.borderColor  = 'rgba(0,212,255,0.25)';
        reactor.style.boxShadow    = '';
        reactor.style.animationDuration = '4s';
      } else if (count <= 3) {
        reactor.style.borderColor  = 'rgba(0,212,255,0.7)';
        reactor.style.boxShadow    = '0 0 40px rgba(0,212,255,0.35)';
        reactor.style.animationDuration = '1.8s';
      } else {
        reactor.style.borderColor  = 'rgba(255,46,195,0.8)';
        reactor.style.boxShadow    = '0 0 60px rgba(255,46,195,0.4)';
        reactor.style.animationDuration = '0.8s';
      }
    }

    if (label) {
      if (count === 0) {
        label.textContent = 'CORE ONLINE';
      } else {
        label.textContent = count + ' AGENT' + (count !== 1 ? 'S' : '') + ' ACTIVE';
      }
    }

    COLS.forEach(c => {
      const head = document.getElementById('mc-head-' + c);
      if (head) head.dataset.active = activeSet.has(c) ? '1' : '0';
    });
  }

  function computeActiveSet(events) {
    const cutoff = Date.now() / 1000 - 30;
    const active = new Set();
    events.forEach(ev => {
      if (ev.ts >= cutoff && (ev.kind === 'think' || ev.kind === 'act')) {
        if (COLS.includes(ev.agent)) active.add(ev.agent);
      }
    });
    return active;
  }

  // ── Full refresh (polling fallback) ───────────────────────────────────────

  async function refresh() {
    try {
      const r = await fetch('/api/agents/events?limit=200', { cache: 'no-store' });
      if (!r.ok) return;
      const j = await r.json();
      const events = (j.events || []).slice().reverse(); // oldest first

      // Rebuild buffers
      COLS.forEach(c => { _buffers[c] = []; });
      events.forEach(ev => {
        if (_buffers[ev.agent]) _buffers[ev.agent].unshift(ev);
      });
      COLS.forEach(renderColumn);
      updateReactorState(computeActiveSet(j.events || []));
    } catch (e) {
      console.warn('[mc] refresh failed', e);
    }
  }

  // ── WebSocket with exponential backoff ───────────────────────────────────

  let _ws         = null;
  let _retryDelay = 1000;
  const MAX_DELAY = 30000;
  let _retryTimer = null;

  function wireWS() {
    if (_retryTimer) { clearTimeout(_retryTimer); _retryTimer = null; }
    if (_ws && (_ws.readyState === WebSocket.OPEN || _ws.readyState === WebSocket.CONNECTING)) return;

    try {
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      _ws = new WebSocket(proto + '//' + location.host + '/ws');
    } catch (e) {
      scheduleReconnect();
      return;
    }

    _ws.addEventListener('open', () => {
      _retryDelay = 1000; // reset backoff on successful connection
      const dot = document.getElementById('ws-dot');
      if (dot) { dot.style.background = '#2effd5'; dot.style.boxShadow = '0 0 8px #2effd5'; }
      const txt = document.getElementById('ws-status');
      if (txt) txt.textContent = 'LIVE FEED';
    });

    _ws.addEventListener('message', (evt) => {
      try {
        const m = JSON.parse(evt.data);
        if (m.type === 'agent_event') {
          const ev = { agent: m.agent, kind: m.kind, message: m.message, ts: m.ts };
          if (_buffers[ev.agent] !== undefined) {
            prependEvent(ev.agent, ev);
            // Recompute active set from all recent events in buffers
            const allRecent = [];
            COLS.forEach(c => allRecent.push(..._buffers[c]));
            updateReactorState(computeActiveSet(allRecent));
          }
        } else if (m.type === 'pipeline_stage' || m.type === 'metric') {
          // trigger a refresh to capture new data
          refresh();
        }
      } catch { /* ignore parse errors */ }
    });

    _ws.addEventListener('close', () => {
      const dot = document.getElementById('ws-dot');
      if (dot) { dot.style.background = 'var(--yellow, #ffb547)'; dot.style.boxShadow = '0 0 8px var(--yellow, #ffb547)'; }
      const txt = document.getElementById('ws-status');
      if (txt) txt.textContent = 'RECONNECTING…';
      scheduleReconnect();
    });

    _ws.addEventListener('error', () => {
      if (_ws) { try { _ws.close(); } catch { /* ok */ } }
    });
  }

  function scheduleReconnect() {
    _retryTimer = setTimeout(() => {
      wireWS();
    }, _retryDelay);
    _retryDelay = Math.min(_retryDelay * 2, MAX_DELAY);
  }

  // ── Init ─────────────────────────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', () => {
    if (!document.getElementById('mc-grid')) return;
    refresh();
    wireWS();
    // Polling fallback every 6s in case WS drops events
    setInterval(refresh, 6000);
  });
})();
