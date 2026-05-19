/* JARVIS Reel Producer - Real-time pipeline orchestration
   - Topic selection state management (max 2)
   - WebSocket connection for real-time pipeline updates
   - Stage progress rendering (pending->running->completed)
   - Script preview modal with approve/reject buttons
   - Voice command integration (window.jarvisVoice.speak)
   - Download handler for platform packages
   - Published toggle state persistence (localStorage)
*/
'use strict';

(function () {
  const MAX_TOPICS = 2;
  const STORAGE_KEY = 'reel-producer-published';
  const STAGES = ['topic-discovery', 'script-generation', 'asset-generation', 'video-assembly', 'platform-export'];

  let _ws = null;
  let _retryDelay = 1000;
  const MAX_DELAY = 30000;
  let _retryTimer = null;
  let _pipelineId = null;

  // ── Topic Selection ──────────────────────────────────────────────────────

  function toggleCard(card) {
    const isSelected = card.classList.contains('selected');
    const selectedCount = document.querySelectorAll('.card.selected').length;

    if (!isSelected && selectedCount >= MAX_TOPICS) {
      _voiceFeedback('Maximum of ' + MAX_TOPICS + ' topics allowed');
      return;
    }

    card.classList.toggle('selected');
    const checkbox = card.querySelector('.custom-checkbox');
    if (checkbox) checkbox.classList.toggle('checked');

    const topic = _getTopicFromCard(card);
    _persistSelection(topic, !isSelected);

    if (!isSelected) {
      _voiceFeedback('Topic selected: ' + topic.topic);
    } else {
      _voiceFeedback('Topic deselected');
    }
  }

  function _getTopicFromCard(card) {
    const title = card.querySelector('.card-title');
    const platform = card.querySelector('.platform-youtube') ? 'youtube'
      : card.querySelector('.platform-tiktok') ? 'tiktok'
        : card.querySelector('.platform-instagram') ? 'instagram' : 'unknown';

    return {
      id: card.dataset.id || String(Date.now() + Math.random()),
      topic: title ? title.textContent.trim() : 'Unknown',
      platform: platform,
      selected: card.classList.contains('selected')
    };
  }

  function _persistSelection(topic, selected) {
    let selections = _loadSelections();

    if (selected) {
      const existingIdx = selections.findIndex(t => t.id === topic.id);
      if (existingIdx === -1) {
        selections.push(topic);
      }
    } else {
      selections = selections.filter(t => t.id !== topic.id);
    }

    localStorage.setItem(STORAGE_KEY + '-selections', JSON.stringify(selections));
  }

  function _loadSelections() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY + '-selections');
      return stored ? JSON.parse(stored) : [];
    } catch (e) {
      return [];
    }
  }

  function _restoreSelections() {
    const selections = _loadSelections();
    const cards = document.querySelectorAll('.card');

    selections.forEach(topic => {
      cards.forEach(card => {
        const cardTitle = card.querySelector('.card-title');
        if (cardTitle && cardTitle.textContent.trim() === topic.topic) {
          if (!card.classList.contains('selected')) {
            card.classList.add('selected');
            const checkbox = card.querySelector('.custom-checkbox');
            if (checkbox) checkbox.classList.add('checked');
          }
        }
      });
    });
  }

  // ── WebSocket Connection ─────────────────────────────────────────────────

  function wireWS() {
    if (_retryTimer) { clearTimeout(_retryTimer); _retryTimer = null; }
    if (_ws && (_ws.readyState === WebSocket.OPEN || _ws.readyState === WebSocket.CONNECTING)) return;

    try {
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      _ws = new WebSocket(proto + '//' + location.host + '/ws/reel');
    } catch (e) {
      scheduleReconnect();
      return;
    }

    _ws.addEventListener('open', () => {
      _retryDelay = 1000;
      _logToConsole('INFO', 'WebSocket connected to pipeline events');
    });

    _ws.addEventListener('message', (evt) => {
      try {
        const m = JSON.parse(evt.data);

        if (m.type === 'pipeline_stage') {
          _handlePipelineStage(m);
        } else if (m.type === 'script_ready') {
          _handleScriptReady(m);
        } else if (m.type === 'reel_complete') {
          _handleReelComplete(m);
        } else if (m.type === 'log') {
          _logToConsole('LOG', m.message);
        }
      } catch (e) {
        _logToConsole('WARN', 'Parse error: ' + e.message);
      }
    });

    _ws.addEventListener('close', () => {
      _logToConsole('WARN', 'WebSocket disconnected, reconnecting...');
      scheduleReconnect();
    });

    _ws.addEventListener('error', () => {
      if (_ws) {
        try { _ws.close(); } catch { /* ok */ }
      }
    });
  }

  function scheduleReconnect() {
    _retryTimer = setTimeout(() => {
      wireWS();
    }, _retryDelay);
    _retryDelay = Math.min(_retryDelay * 2, MAX_DELAY);
  }

  function _handlePipelineStage(m) {
    const stageIndex = STAGES.indexOf(m.stage_id || m.stage);
    if (stageIndex === -1) return;

    const status = m.status || 'running';
    const progress = m.progress || (status === 'completed' ? 100 : 0);

    _updateStageUI(stageIndex, status, progress);

    if (status === 'completed') {
      _voiceFeedback('Stage completed: ' + m.stage_name || m.stage);
    } else if (status === 'running') {
      _logToConsole('INFO', 'Starting: ' + m.stage_name || m.stage);
    }
  }

  function _handleScriptReady(m) {
    _showScriptPreview(m.script || m.content, m.script_id);
  }

  function _handleReelComplete(m) {
    const reel = m.reel || m;
    _addToQueue(reel);
    _voiceFeedback('Reel ready: ' + reel.topic);
  }

  // ── Stage Progress Rendering ─────────────────────────────────────────────

  function _updateStageUI(stageIndex, status, progress) {
    const stages = document.querySelectorAll('.stage-card');
    const targetStage = stages[stageIndex];
    if (!targetStage) return;

    // Clear all stage classes
    stages.forEach(s => {
      s.classList.remove('completed', 'running', 'pending', 'stage-completed', 'stage-running', 'stage-pending', 'active-running');
    });

    // Set target stage status
    targetStage.classList.add('stage-' + status, status);
    if (status === 'running') {
      targetStage.classList.add('active-running');
    }

    // Update status text
    const statusEl = targetStage.querySelector('.stage-name').nextElementSibling;
    if (statusEl) {
      let statusText = 'Pending';
      let statusClass = 'status-pending';

      if (status === 'completed') {
        statusText = 'Completed';
        statusClass = 'status-completed';
      } else if (status === 'running') {
        statusText = 'Processing';
        statusClass = 'status-running';
      }

      statusEl.innerHTML = '<span class="status-indicator ' + statusClass + '">' + statusText + '</span>';
    }

    // Update progress bar
    const progressBar = targetStage.querySelector('.progress-fill');
    if (progressBar) {
      progressBar.style.width = progress + '%';
      if (status === 'running') {
        progressBar.classList.add('animating');
      } else {
        progressBar.classList.remove('animating');
      }
    }

    // Update icon for completed
    const icon = targetStage.querySelector('.stage-icon');
    if (status === 'completed' && icon) {
      icon.innerHTML = '&#10003;';
    }
  }

  // ── Script Preview Modal ─────────────────────────────────────────────────

  function _showScriptPreview(script, scriptId) {
    if (document.getElementById('script-preview-modal')) return;

    const overlay = document.createElement('div');
    overlay.id = 'script-preview-modal';
    overlay.className = 'script-preview-overlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.85);display:flex;align-items:center;justify-content:center;z-index:1000;';

    const box = document.createElement('div');
    box.className = 'script-preview-box';
    box.style.cssText = 'background:#121212;border:1px solid rgba(255,255,255,0.1);border-radius:16px;max-width:600px;max-height:80vh;overflow:hidden;';

    const header = document.createElement('div');
    header.style.cssText = 'padding:20px;border-bottom:1px solid rgba(255,255,255,0.1);';
    const h3 = document.createElement('h3');
    h3.style.cssText = 'margin:0;font-size:14px;text-transform:uppercase;letter-spacing:0.5px;color:#00f0ff;';
    h3.textContent = 'Script Preview';
    header.appendChild(h3);

    const content = document.createElement('div');
    content.style.cssText = 'padding:20px;overflow-y:auto;max-height:400px;font-family:monospace;font-size:12px;line-height:1.6;color:#a1a1aa;white-space:pre-wrap;';
    content.textContent = script || 'No script content available';

    const actions = document.createElement('div');
    actions.style.cssText = 'padding:16px 20px;border-top:1px solid rgba(255,255,255,0.1);display:flex;gap:12px;justify-content:flex-end;';

    const rejectBtn = document.createElement('button');
    rejectBtn.className = 'btn btn-small';
    rejectBtn.style.cssText = 'padding:8px 16px;font-size:11px;border-radius:6px;border:1px solid rgba(239,68,68,0.3);background:rgba(239,68,68,0.1);color:#ef4444;cursor:pointer;';
    rejectBtn.textContent = 'Reject';
    rejectBtn.onclick = () => {
      document.body.removeChild(overlay);
      _rejectScript(scriptId);
    };

    const approveBtn = document.createElement('button');
    approveBtn.className = 'btn btn-small btn-primary';
    approveBtn.style.cssText = 'padding:8px 16px;font-size:11px;border-radius:6px;background:linear-gradient(135deg,#00f0ff,#7c3aed);color:#000;border:none;cursor:pointer;';
    approveBtn.textContent = 'Approve';
    approveBtn.onclick = () => {
      document.body.removeChild(overlay);
      _approveScript(scriptId);
    };

    actions.appendChild(rejectBtn);
    actions.appendChild(approveBtn);

    box.appendChild(header);
    box.appendChild(content);
    box.appendChild(actions);
    overlay.appendChild(box);
    document.body.appendChild(overlay);

    _voiceFeedback('Script ready for review. Please approve or reject.');
  }

  function _approveScript(scriptId) {
    _logToConsole('SUCCESS', 'Script approved');
    _sendPipelineCommand('approve_script', { script_id: scriptId });
  }

  function _rejectScript(scriptId) {
    _logToConsole('WARN', 'Script rejected');
    _sendPipelineCommand('reject_script', { script_id: scriptId });
  }

  // ── Download Handler ─────────────────────────────────────────────────────

  function handleDownload(reelId, platform) {
    const url = '/api/reel/download/' + reelId + '?platform=' + encodeURIComponent(platform);

    const link = document.createElement('a');
    link.href = url;
    link.download = 'reel-' + reelId + '-' + platform + '.mp4';
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    _logToConsole('SUCCESS', 'Download started for ' + platform);
    _voiceFeedback('Download started for ' + platform);
  }

  // ── Published Toggle Persistence ─────────────────────────────────────────

  function togglePublished(reelId) {
    const stored = _loadPublishedState();
    stored[reelId] = !stored[reelId];
    localStorage.setItem(STORAGE_KEY + '-published', JSON.stringify(stored));

    _logToConsole('INFO', 'Published state changed for ' + reelId + ': ' + stored[reelId]);
  }

  function _loadPublishedState() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY + '-published');
      return stored ? JSON.parse(stored) : {};
    } catch (e) {
      return {};
    }
  }

  function _restorePublishedState() {
    const published = _loadPublishedState();
    const toggles = document.querySelectorAll('.toggle');

    toggles.forEach(toggle => {
      const parent = toggle.closest('.queue-item');
      if (parent) {
        const reelId = parent.dataset.reolId;
        if (reolId && published[reelId]) {
          toggle.classList.add('active');
        }
      }
    });
  }

  // ── Queue Panel Management ───────────────────────────────────────────────

  function _addToQueue(reel) {
    const container = document.getElementById('queue-content');
    if (!container) return;

    const emptyState = container.querySelector('.empty-state');
    if (emptyState) {
      container.innerHTML = '';
    }

    const item = document.createElement('div');
    item.className = 'queue-item';
    item.dataset.reelId = reel.id || String(Date.now());

    const topic = document.createElement('div');
    topic.className = 'queue-topic';
    topic.textContent = reel.topic || 'Unknown reel';

    const badge = document.createElement('span');
    badge.className = 'platform-badge ' + (reel.platform || 'youtube');
    badge.textContent = reel.platform || 'youtube';

    const downloadBtn = document.createElement('button');
    downloadBtn.className = 'btn btn-small btn-download';
    downloadBtn.textContent = '↓';
    downloadBtn.title = 'Download reel';
    downloadBtn.onclick = () => handleDownload(reel.id || Date.now(), reel.platform || 'youtube');

    const toggleWrapper = document.createElement('div');
    toggleWrapper.className = 'toggle-wrapper';

    const toggle = document.createElement('div');
    toggle.className = 'toggle';
    toggle.title = 'Mark as published';
    toggle.onclick = () => {
      toggle.classList.toggle('active');
      togglePublished(reel.id || Date.now());
    };

    toggleWrapper.appendChild(toggle);
    item.appendChild(topic);
    item.appendChild(badge);
    item.appendChild(downloadBtn);
    item.appendChild(toggleWrapper);

    container.appendChild(item);

    _logToConsole('SUCCESS', 'Added to queue: ' + (reel.topic || 'Reel'));
  }

  // ── Console Logging ──────────────────────────────────────────────────────

  function _logToConsole(level, message) {
    const consoleEl = document.getElementById('console');
    if (!consoleEl) return;

    const now = new Date();
    const time = now.toLocaleTimeString('en-US', { hour12: false });

    let levelClass = 'console-log';
    if (level === 'INFO') levelClass = 'console-info';
    if (level === 'SUCCESS') levelClass = 'console-success';
    if (level === 'WARN') levelClass = 'console-warning';

    const line = document.createElement('div');
    line.className = 'console-line';

    const timeSpan = document.createElement('span');
    timeSpan.className = 'console-time';
    timeSpan.textContent = '[' + time + '] ';

    const levelSpan = document.createElement('span');
    levelSpan.className = levelClass;
    levelSpan.textContent = level + ' ';

    const msgSpan = document.createElement('span');
    msgSpan.className = levelClass;
    msgSpan.textContent = message;

    consoleEl.appendChild(line);
    line.appendChild(timeSpan);
    line.appendChild(levelSpan);
    line.appendChild(msgSpan);
    consoleEl.scrollTop = consoleEl.scrollHeight;
  }

  // ── Voice Feedback ───────────────────────────────────────────────────────

  function _voiceFeedback(text) {
    if (window.jarvisVoice && window.jarvisVoice.speak) {
      window.jarvisVoice.speak(text);
    }
  }

  // ── Pipeline Commands ────────────────────────────────────────────────────

  function _sendPipelineCommand(command, payload) {
    if (_ws && _ws.readyState === WebSocket.OPEN) {
      _ws.send(JSON.stringify({
        type: 'pipeline_command',
        command: command,
        payload: payload
      }));
    } else {
      _logToConsole('WARN', 'WebSocket not connected, queued command: ' + command);
    }
  }

  // ── Start Production ─────────────────────────────────────────────────────

  function startProduction() {
    const selections = _loadSelections();

    if (selections.length === 0) {
      _logToConsole('WARN', 'No topics selected. Please select at least one topic.');
      _voiceFeedback('No topics selected. Please select at least one topic.');
      return;
    }

    _pipelineId = 'pipeline-' + Date.now();
    _logToConsole('INFO', 'Starting production for ' + selections.length + ' topic(s)...');
    _voiceFeedback('Starting production for ' + selections.length + ' topics.');

    _sendPipelineCommand('start_production', {
      pipeline_id: _pipelineId,
      topics: selections
    });
  }

  // ── Initialization ───────────────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', () => {
    if (!document.querySelector('.dashboard')) return;

    // Wire up card clicks
    document.querySelectorAll('.card').forEach(card => {
      card.onclick = () => toggleCard(card);
    });

    // Restore persisted state
    _restoreSelections();
    _restorePublishedState();

    // Connect WebSocket
    wireWS();

    // Expose public API
    window.ReelProducer = {
      startProduction: startProduction,
      handleDownload: handleDownload,
      togglePublished: togglePublished,
      logToConsole: _logToConsole
    };

    _logToConsole('INFO', 'Reel Producer initialized');
  });
})();