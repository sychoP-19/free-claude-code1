/**
 * Mexico Cultural Flows - PWA Registration & Install Handler
 * Self-contained: injects UI elements via createElement only (no innerHTML with variables).
 * Adds install button in header, update toast, and offline/online indicator.
 */
(function () {
  'use strict';

  var d = document;
  var w = window;

  // ── CSS injected once ──────────────────────────────────────────────
  var style = d.createElement('style');
  style.textContent = [
    /* Install button in header — matches year-badge aesthetic */
    '.pwa-install-btn{',
    '  display:inline-flex;align-items:center;gap:6px;',
    '  padding:5px 12px;border-radius:20px;',
    '  background:rgba(245,200,66,0.12);border:1px solid rgba(245,200,66,0.35);',
    '  color:var(--accent-gold,#f5c842);font-size:0.75rem;font-weight:600;',
    '  letter-spacing:0.06em;cursor:pointer;transition:all 0.2s;',
    '  font-family:"DM Sans",sans-serif;white-space:nowrap;',
    '}',
    '.pwa-install-btn:hover{background:rgba(245,200,66,0.22);border-color:rgba(245,200,66,0.55);}',
    '.pwa-install-btn:focus-visible{outline:3px solid var(--accent-gold,#f5c842);outline-offset:2px;}',
    '.pwa-install-btn[hidden]{display:none !important;}',
    '.pwa-install-btn svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;}',
    /* Offline indicator pill in header */
    '.pwa-status{',
    '  display:inline-flex;align-items:center;gap:5px;',
    '  padding:4px 10px;border-radius:20px;font-size:0.65rem;font-weight:600;',
    '  letter-spacing:0.04em;transition:all 0.3s;',
    '  font-family:"DM Sans",sans-serif;white-space:nowrap;',
    '}',
    '.pwa-status[hidden]{display:none !important;}',
    '.pwa-status--offline{',
    '  background:rgba(196,18,48,0.15);border:1px solid rgba(196,18,48,0.4);',
    '  color:var(--accent-red,#c41230);',
    '}',
    '.pwa-status--online{',
    '  background:rgba(0,168,107,0.15);border:1px solid rgba(0,168,107,0.4);',
    '  color:var(--accent-green,#00a86b);',
    '}',
    '.pwa-status-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;}',
    '.pwa-status--offline .pwa-status-dot{background:var(--accent-red,#c41230);}',
    '.pwa-status--online .pwa-status-dot{background:var(--accent-green,#00a86b);}',
    /* Toast notification (bottom-center, non-blocking) */
    '.pwa-toast{',
    '  position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(80px);',
    '  z-index:9999;display:flex;align-items:center;gap:10px;',
    '  padding:10px 20px;border-radius:12px;',
    '  background:var(--panel-glass,rgba(15,12,28,0.92));',
    '  border:1px solid var(--border,rgba(255,255,255,0.07));',
    '  box-shadow:var(--shadow-lg,0 12px 40px rgba(0,0,0,0.5));',
    '  backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);',
    '  color:var(--text,#f0ebe0);font-size:0.82rem;font-weight:500;',
    '  font-family:"DM Sans",sans-serif;white-space:nowrap;',
    '  opacity:0;transition:all 0.35s ease;pointer-events:none;',
    '}',
    '.pwa-toast--visible{transform:translateX(-50%) translateY(0);opacity:1;pointer-events:auto;}',
    '.pwa-toast-btn{',
    '  display:inline-flex;align-items:center;gap:4px;',
    '  padding:4px 12px;border-radius:8px;',
    '  background:var(--accent-gold,#f5c842);color:#07060f;',
    '  border:none;font-size:0.75rem;font-weight:700;cursor:pointer;',
    '  font-family:"DM Sans",sans-serif;transition:all 0.2s;',
    '}',
    '.pwa-toast-btn:hover{filter:brightness(1.1);}',
    '.pwa-toast-btn:focus-visible{outline:3px solid var(--accent-gold,#f5c842);outline-offset:2px;}',
    '.pwa-toast-dismiss{',
    '  background:none;border:none;color:var(--muted,rgba(240,235,224,0.45));',
    '  cursor:pointer;font-size:1.1rem;line-height:1;padding:0 2px;',
    '}',
    '.pwa-toast-dismiss:hover{color:var(--text,#f0ebe0);}',
    /* Responsive: shrink on mobile alongside hdr-btn rules */
    '@media(max-width:768px){.pwa-install-btn{padding:5px 8px;font-size:0.7rem;}}',
    '@media(max-width:480px){.pwa-install-btn{padding:4px 6px;font-size:0.65rem;}.pwa-status{font-size:0.6rem;padding:3px 8px;}}',
  ].join('\n');
  d.head.appendChild(style);

  // ── Install button (injected into header-controls) ─────────────────
  var installBtn = d.createElement('button');
  installBtn.className = 'pwa-install-btn';
  installBtn.setAttribute('hidden', '');
  installBtn.setAttribute('aria-label', 'Install app');

  var svg = d.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  var path1 = d.createElementNS('http://www.w3.org/2000/svg', 'path');
  path1.setAttribute('d', 'M12 3v12');
  svg.appendChild(path1);
  var path2 = d.createElementNS('http://www.w3.org/2000/svg', 'path');
  path2.setAttribute('d', 'M7 8l5-5 5 5');
  svg.appendChild(path2);
  var path3 = d.createElementNS('http://www.w3.org/2000/svg', 'path');
  path3.setAttribute('d', 'M3 13v6a2 2 0 002 2h14a2 2 0 002-2v-6');
  svg.appendChild(path3);

  var installLabel = d.createElement('span');
  installLabel.textContent = 'Install';
  installBtn.appendChild(svg);
  installBtn.appendChild(installLabel);

  // ── Offline / online indicator (injected into header) ──────────────
  var statusPill = d.createElement('span');
  statusPill.className = 'pwa-status pwa-status--online';
  statusPill.setAttribute('hidden', '');
  statusPill.setAttribute('role', 'status');

  var statusDot = d.createElement('span');
  statusDot.className = 'pwa-status-dot';
  var statusLabel = d.createElement('span');
  statusLabel.textContent = 'Online';
  statusPill.appendChild(statusDot);
  statusPill.appendChild(statusLabel);

  // Only show when offline; online state is implied default
  function updateOnlineStatus() {
    if (!navigator.onLine) {
      statusPill.className = 'pwa-status pwa-status--offline';
      statusLabel.textContent = 'Offline';
      statusPill.removeAttribute('hidden');
    } else {
      statusPill.className = 'pwa-status pwa-status--online';
      statusLabel.textContent = 'Online';
      statusPill.removeAttribute('hidden');
      // Auto-hide online pill after 3 seconds (offline stays visible)
      clearTimeout(statusPill._hideTimer);
      statusPill._hideTimer = setTimeout(function () {
        statusPill.setAttribute('hidden', '');
      }, 3000);
    }
  }

  w.addEventListener('online', updateOnlineStatus);
  w.addEventListener('offline', updateOnlineStatus);

  // ── Toast helper ───────────────────────────────────────────────────
  var currentToast = null;

  function showToast(message, actionLabel, actionFn) {
    // Remove any existing toast
    if (currentToast && currentToast.parentNode) {
      currentToast.parentNode.removeChild(currentToast);
    }

    var toast = d.createElement('div');
    toast.className = 'pwa-toast';
    toast.setAttribute('role', 'alert');

    var msg = d.createElement('span');
    msg.textContent = message;
    toast.appendChild(msg);

    if (actionLabel && actionFn) {
      var btn = d.createElement('button');
      btn.className = 'pwa-toast-btn';
      btn.textContent = actionLabel;
      btn.addEventListener('click', function () {
        dismissToast();
        actionFn();
      });
      toast.appendChild(btn);
    }

    var dismiss = d.createElement('button');
    dismiss.className = 'pwa-toast-dismiss';
    dismiss.setAttribute('aria-label', 'Dismiss');
    dismiss.textContent = '×'; // multiplication sign = ×
    dismiss.addEventListener('click', dismissToast);
    toast.appendChild(dismiss);

    d.body.appendChild(toast);
    currentToast = toast;

    // Trigger entrance animation
    requestAnimationFrame(function () {
      toast.classList.add('pwa-toast--visible');
    });

    // Auto-dismiss after 12 seconds
    toast._autoDismiss = setTimeout(dismissToast, 12000);
  }

  function dismissToast() {
    if (!currentToast) return;
    clearTimeout(currentToast._autoDismiss);
    currentToast.classList.remove('pwa-toast--visible');
    var ref = currentToast;
    setTimeout(function () {
      if (ref.parentNode) ref.parentNode.removeChild(ref);
    }, 400);
    currentToast = null;
  }

  // ── Service Worker Registration ────────────────────────────────────
  var swRegistration = null;
  var deferredPrompt = null;

  function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return;

    navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .then(function (registration) {
        swRegistration = registration;

        // Check for updates on load
        registration.update();

        // Handle update detection
        registration.addEventListener('updatefound', function () {
          var newWorker = registration.installing;
          if (!newWorker) return;

          newWorker.addEventListener('statechange', function () {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              // New version available — show toast with reload action
              showUpdateToast();
            }
          });
        });

        // Track controller change (SW took over after skipWaiting)
        navigator.serviceWorker.addEventListener('controllerchange', function () {
          // New SW activated — prompt reload if user hasn't already
          showToast('App updated. Reload to see changes.', 'Reload', function () {
            w.location.reload();
          });
        });
      })
      .catch(function (err) {
        console.warn('SW registration failed:', err);
      });
  }

  function showUpdateToast() {
    showToast('Update available', 'Reload', function () {
      // Tell the waiting SW to skipWaiting, then reload
      if (swRegistration && swRegistration.waiting) {
        swRegistration.waiting.postMessage({ type: 'SKIP_WAITING' });
      }
      w.location.reload();
    });
  }

  // ── Install Prompt ─────────────────────────────────────────────────
  function setupInstallPrompt() {
    // Already running as standalone PWA — no install needed
    if (w.matchMedia('(display-mode: standalone)').matches) return;

    // Respect user dismissal for 7 days
    var dismissedAt = localStorage.getItem('pwa-dismissed-at');
    if (dismissedAt && Date.now() - parseInt(dismissedAt, 10) < 604800000) return;

    w.addEventListener('beforeinstallprompt', function (e) {
      e.preventDefault();
      deferredPrompt = e;

      // Show install button in header
      installBtn.removeAttribute('hidden');
    });
  }

  installBtn.addEventListener('click', function () {
    if (!deferredPrompt) return;

    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(function (choiceResult) {
      if (choiceResult.outcome === 'accepted') {
        showToast('App installed! Launch from your home screen.', null, null);
      } else {
        // Remember dismissal for 7 days
        localStorage.setItem('pwa-dismissed-at', Date.now().toString());
      }
      deferredPrompt = null;
      installBtn.setAttribute('hidden', '');
    });
  });

  w.addEventListener('appinstalled', function () {
    deferredPrompt = null;
    installBtn.setAttribute('hidden', '');
    showToast('App installed successfully!', null, null);
  });

  // ── Inject UI into header ─────────────────────────────────────────
  function injectHeaderUI() {
    var controls = d.querySelector('.header-controls');
    if (!controls) return;

    // Insert install button as first item in controls
    if (controls.firstChild) {
      controls.insertBefore(installBtn, controls.firstChild);
    } else {
      controls.appendChild(installBtn);
    }

    // Insert status pill after year-badge
    var yearBadge = d.getElementById('hdr-year');
    if (yearBadge && yearBadge.parentNode) {
      yearBadge.parentNode.insertBefore(statusPill, yearBadge.nextSibling);
    } else {
      controls.appendChild(statusPill);
    }
  }

  // ── Initialize ─────────────────────────────────────────────────────
  function init() {
    injectHeaderUI();
    updateOnlineStatus();
    registerServiceWorker();
    setupInstallPrompt();
  }

  if (d.readyState === 'loading') {
    d.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
