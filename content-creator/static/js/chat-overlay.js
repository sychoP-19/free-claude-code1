/* JARVIS Chat Overlay v2 — proxy:8082 first, Ollama fallback, live diagnostics */
'use strict';

const ChatOverlay = (() => {
  const PROXY_URL  = 'http://localhost:8082/v1/messages';
  const OLLAMA_FALLBACK = '/api/llm/chat';
  const HEALTH_URL = '/api/system/llm-health';
  const START_PROXY_URL = '/api/system/start-proxy';
  const MODEL = 'claude-sonnet-4-6';
  const SYSTEM =
    'You are JARVIS, a multilingual AI assistant integrated into a content intelligence dashboard. ' +
    'Respond in the same language as the user (English, Arabic, Moroccan Darija). ' +
    'Be concise, direct, and professional.';

  let messages = [];
  let panel = null, input = null, log = null, toggleBtn = null;
  let statusDot = null, statusTip = null;
  let open = false, streaming = false;
  let lastHealth = { proxy: null, ollama: null };

  function init() {
    _buildDOM();
    panel     = document.getElementById('jarvis-chat-panel');
    input     = document.getElementById('jarvis-chat-input');
    log       = document.getElementById('jarvis-chat-log');
    toggleBtn = document.getElementById('jarvis-chat-toggle');
    statusDot = document.getElementById('jarvis-chat-status');
    statusTip = document.getElementById('jarvis-chat-status-tip');

    if (!panel) return;

    toggleBtn.addEventListener('click', _toggle);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); _submit(); }
    });
    document.getElementById('jarvis-chat-send').addEventListener('click', _submit);
    document.getElementById('jarvis-chat-close').addEventListener('click', _toggle);

    _setStatus('amber', 'Checking backends…');
    _checkHealth();
    _addMessage('jarvis', 'JARVIS online. How can I assist you, sir?');
  }

  function _buildDOM() {
    const root = document.createElement('div');
    root.id = 'jarvis-chat-root';

    const btn = document.createElement('button');
    btn.id = 'jarvis-chat-toggle';
    btn.title = 'Talk to JARVIS';
    btn.appendChild(_makeSvg('0 0 24 24', 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'));
    const badge = document.createElement('span');
    badge.className = 'chat-badge';
    badge.id = 'chat-badge';
    badge.style.display = 'none';
    badge.textContent = '1';
    btn.appendChild(badge);

    const chatPanel = document.createElement('div');
    chatPanel.id = 'jarvis-chat-panel';

    const header = document.createElement('div');
    header.className = 'chat-header';
    const titleDiv = document.createElement('div');
    titleDiv.className = 'chat-title';
    const dot = document.createElement('div');
    dot.className = 'chat-dot';
    titleDiv.appendChild(dot);
    titleDiv.appendChild(document.createTextNode('J.A.R.V.I.S INTERFACE'));

    const status = document.createElement('span');
    status.id = 'jarvis-chat-status';
    status.className = 'chat-status chat-status--amber';
    status.title = 'Backend status';
    const tip = document.createElement('span');
    tip.id = 'jarvis-chat-status-tip';
    tip.className = 'chat-status-tip';
    tip.textContent = 'checking…';
    status.appendChild(tip);
    titleDiv.appendChild(status);

    const closeBtn = document.createElement('button');
    closeBtn.id = 'jarvis-chat-close';
    closeBtn.textContent = '✕';
    header.appendChild(titleDiv);
    header.appendChild(closeBtn);

    const logDiv = document.createElement('div');
    logDiv.id = 'jarvis-chat-log';

    const inputRow = document.createElement('div');
    inputRow.className = 'chat-input-row';
    const textarea = document.createElement('textarea');
    textarea.id = 'jarvis-chat-input';
    textarea.placeholder = 'Ask JARVIS anything…';
    textarea.rows = 1;
    const sendBtn = document.createElement('button');
    sendBtn.id = 'jarvis-chat-send';
    sendBtn.appendChild(_makeSvg('0 0 24 24', 'M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z'));
    inputRow.appendChild(textarea);
    inputRow.appendChild(sendBtn);

    chatPanel.appendChild(header);
    chatPanel.appendChild(logDiv);
    chatPanel.appendChild(inputRow);
    root.appendChild(btn);
    root.appendChild(chatPanel);
    document.body.appendChild(root);
  }

  function _makeSvg(viewBox, pathD) {
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', viewBox);
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '1.5');
    svg.setAttribute('width', '20');
    svg.setAttribute('height', '20');
    const path = document.createElementNS(ns, 'path');
    path.setAttribute('d', pathD);
    svg.appendChild(path);
    return svg;
  }

  function _toggle() {
    open = !open;
    panel.classList.toggle('open', open);
    document.getElementById('chat-badge').style.display = 'none';
    if (open) { input.focus(); _checkHealth(); }
  }

  function _setStatus(level, text) {
    if (!statusDot) return;
    statusDot.className = 'chat-status chat-status--' + level;
    if (statusTip) statusTip.textContent = text;
    statusDot.title = text;
  }

  async function _checkHealth() {
    try {
      const r = await fetch(HEALTH_URL, { cache: 'no-store' });
      if (!r.ok) throw new Error('health ' + r.status);
      const j = await r.json();
      lastHealth = j;
      if (j.proxy && j.ollama)      _setStatus('green',  `proxy + ollama ok (${j.latency_ms}ms)`);
      else if (j.proxy)             _setStatus('green',  `proxy ok (${j.latency_ms}ms) • ollama down`);
      else if (j.ollama)            _setStatus('amber',  `ollama ok • proxy down`);
      else                          _setStatus('red',    'proxy + ollama both down');
    } catch (e) {
      _setStatus('amber', 'health check failed');
    }
  }

  async function _submit() {
    const text = input.value.trim();
    if (!text || streaming) return;
    input.value = '';
    await sendMessage(text, false);
  }

  async function sendMessage(text, fromVoice) {
    if (!text || streaming) return;
    _addMessage('user', text);
    messages.push({ role: 'user', content: text });

    streaming = true;
    const assistantEl = _addMessage('jarvis', '');
    const dotsEl = assistantEl.querySelector('.chat-dots');
    const textEl = assistantEl.querySelector('.chat-text');

    let proxyErrMsg = '';
    try {
      const resp = await fetch(PROXY_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-api-key': 'jarvis-local' },
        body: JSON.stringify({
          model: MODEL, max_tokens: 1024, system: SYSTEM,
          stream: true, messages: messages.slice(-12),
        }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let reply = '';
      if (dotsEl) dotsEl.style.display = 'none';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const line of decoder.decode(value).split('\n')) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6).trim();
          if (data === '[DONE]') continue;
          try {
            const ev = JSON.parse(data);
            const delta = ev.delta?.text || ev.delta?.content?.[0]?.text || '';
            if (delta) {
              reply += delta;
              textEl.textContent = reply;
              log.scrollTop = log.scrollHeight;
            }
          } catch { /* malformed SSE line */ }
        }
      }

      messages.push({ role: 'assistant', content: reply });
      _setStatus('green', 'proxy ok');
      if (fromVoice && window.Voice) Voice.speak(reply.slice(0, 300));
      return;

    } catch (e) {
      proxyErrMsg = e.message || 'proxy error';
      _setStatus('amber', `proxy down (${proxyErrMsg}) • trying ollama…`);
    }

    // Fallback: Ollama via local route
    try {
      const ollamaResp = await fetch(OLLAMA_FALLBACK, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history: messages.slice(-12) }),
      });
      if (!ollamaResp.ok) throw new Error(`HTTP ${ollamaResp.status}`);
      const ollamaData = await ollamaResp.json();
      if (dotsEl) dotsEl.style.display = 'none';
      const reply = ollamaData.response || ollamaData.message || ollamaData.reply || 'No response from Ollama.';
      textEl.textContent = reply;
      messages.push({ role: 'assistant', content: reply });
      _setStatus('amber', `ollama ok • proxy was: ${proxyErrMsg}`);
      if (fromVoice && window.Voice) Voice.speak(reply.slice(0, 300));
    } catch (oe) {
      if (dotsEl) dotsEl.style.display = 'none';
      _renderBothDown(assistantEl, proxyErrMsg, oe.message || 'ollama error');
      _setStatus('red', 'both backends down');
    } finally {
      streaming = false;
      if (!open) document.getElementById('chat-badge').style.display = 'flex';
    }
  }

  function _renderBothDown(assistantEl, proxyErr, ollamaErr) {
    const textEl = assistantEl.querySelector('.chat-text');
    textEl.textContent = '';
    textEl.style.color = '';

    const wrap = document.createElement('div');
    wrap.className = 'chat-error-card';

    const title = document.createElement('div');
    title.className = 'chat-error-title';
    title.textContent = 'Both backends are offline';

    const p1 = document.createElement('div');
    p1.className = 'chat-error-line';
    p1.textContent = `Proxy (:8082): ${proxyErr}`;

    const p2 = document.createElement('div');
    p2.className = 'chat-error-line';
    p2.textContent = `Ollama (/api/ollama/chat): ${ollamaErr}`;

    const startBtn = document.createElement('button');
    startBtn.className = 'chat-error-btn';
    startBtn.textContent = 'START PROXY';
    startBtn.addEventListener('click', async () => {
      startBtn.disabled = true;
      startBtn.textContent = 'Starting…';
      try {
        const r = await fetch(START_PROXY_URL, { method: 'POST' });
        const j = await r.json();
        startBtn.textContent = j.ok ? 'STARTED — try again in 5s' : 'Failed';
        if (j.ok) setTimeout(_checkHealth, 5000);
      } catch (e) {
        startBtn.textContent = 'Failed';
      }
    });

    wrap.appendChild(title);
    wrap.appendChild(p1);
    wrap.appendChild(p2);
    wrap.appendChild(startBtn);
    textEl.appendChild(wrap);
  }

  function _addMessage(role, text) {
    const div = document.createElement('div');
    div.className = `chat-msg chat-msg-${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'chat-avatar';
    avatar.textContent = role === 'jarvis' ? 'J' : 'U';

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';

    const textSpan = document.createElement('span');
    textSpan.className = 'chat-text';
    textSpan.textContent = text;
    bubble.appendChild(textSpan);

    if (role === 'jarvis' && !text) {
      const dots = document.createElement('span');
      dots.className = 'chat-dots';
      dots.textContent = '…';
      bubble.appendChild(dots);
    }

    div.appendChild(avatar);
    div.appendChild(bubble);
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  return { init, sendMessage, checkHealth: _checkHealth };
})();

window.ChatOverlay = ChatOverlay;
document.addEventListener('DOMContentLoaded', ChatOverlay.init);
