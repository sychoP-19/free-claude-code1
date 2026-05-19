/* JARVIS toast/notify system — global window.toast({text, level}). */
'use strict';

(function () {
  function ensureRoot() {
    let root = document.getElementById('toast-root');
    if (!root) {
      root = document.createElement('div');
      root.id = 'toast-root';
      document.body.appendChild(root);
    }
    return root;
  }

  function show(opts) {
    const text  = typeof opts === 'string' ? opts : (opts && opts.text) || '';
    const level = (opts && opts.level) || 'info';
    const ttl   = (opts && opts.ttl)   || 5000;
    if (!text) return;
    const root = ensureRoot();
    const div = document.createElement('div');
    div.className = 'toast' + (level && level !== 'info' ? ' toast--' + level : '');
    const dot = document.createElement('span');
    dot.className = 'toast__dot';
    const span = document.createElement('span');
    span.textContent = text;
    div.appendChild(dot);
    div.appendChild(span);
    root.appendChild(div);
    setTimeout(() => {
      div.style.transition = 'opacity 0.3s ease';
      div.style.opacity = '0';
      setTimeout(() => div.remove(), 320);
    }, ttl);
  }

  window.toast = show;
  window.notify = show; // alias for legacy callers
  document.addEventListener('DOMContentLoaded', ensureRoot);
})();
