/* JARVIS topbar arc-reactor pulse — reflects active agent count.
   Polls /api/agents/active every 8 seconds.
   data-active bucket → CSS animation speed + border color via inline style:
     0 agents  : dim cyan, paused pulse
     1-3 agents: bright cyan, 1.5s pulse
     4+ agents : plasma magenta, 0.8s pulse
   Click navigates to /mission-control.
*/
'use strict';

(function () {
  const COLORS = {
    idle:   { border: 'rgba(0,212,255,0.35)',  shadow: 'none',                           ring: 'rgba(0,212,255,0.15)' },
    active: { border: 'rgba(0,212,255,0.8)',   shadow: '0 0 14px rgba(0,212,255,0.5)',   ring: 'rgba(0,212,255,0.4)' },
    plasma: { border: 'rgba(255,46,195,0.9)',  shadow: '0 0 18px rgba(255,46,195,0.55)', ring: 'rgba(255,46,195,0.35)' },
  };

  function applyState(el, total) {
    const bucket = total === 0 ? 0 : total <= 3 ? 1 : 2;
    el.dataset.active = String(bucket); // drives CSS animation-duration

    let scheme;
    if (total === 0)      scheme = COLORS.idle;
    else if (total <= 3)  scheme = COLORS.active;
    else                  scheme = COLORS.plasma;

    el.style.borderColor = scheme.border;
    el.style.boxShadow   = scheme.shadow;

    // Update ::after pseudo-element colour via CSS custom property workaround:
    // inject inline var override on the element itself
    el.style.setProperty('--arc-ring-color', scheme.ring);

    const n = el.querySelector('.topbar-arc__num');
    if (n) {
      n.textContent = total > 0 ? String(total) : '';
      n.style.color = total === 0 ? 'var(--blue,#00d4ff)' : (total <= 3 ? '#00d4ff' : '#ff2ec3');
    }
  }

  async function tick() {
    const el = document.getElementById('topbar-arc');
    if (!el) return;
    try {
      const r = await fetch('/api/agents/active', { cache: 'no-store' });
      if (!r.ok) return;
      const j = await r.json();
      const total = (j && typeof j.total === 'number') ? j.total : 0;
      applyState(el, total);
    } catch { /* offline — keep current state */ }
  }

  document.addEventListener('DOMContentLoaded', () => {
    tick();
    setInterval(tick, 8000);
  });
})();
