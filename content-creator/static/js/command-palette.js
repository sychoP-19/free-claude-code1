/* JARVIS command palette — Ctrl/Cmd+K → fuzzy nav + actions. */
'use strict';

(function () {
  const ROUTES = [
    { label: 'Dashboard',          href: '/' },
    { label: 'Mission Control',    href: '/mission-control' },
    { label: 'Shorts pipeline',    href: '/shorts' },
    { label: 'Long-form pipeline', href: '/longform' },
    { label: 'Podcast pipeline',   href: '/podcast' },
    { label: 'Blog pipeline',      href: '/blog' },
    { label: 'Carousel pipeline',  href: '/carousel' },
    { label: 'Research briefs',    href: '/research' },
    { label: 'Idea inbox',         href: '/ideas' },
    { label: 'Asset library',      href: '/library' },
    { label: 'Costs & tokens',     href: '/costs' },
    { label: 'Brand voice',        href: '/brand' },
    { label: 'Schedules',          href: '/schedule' },
    { label: 'Repos & services',   href: '/repos' },
    { label: 'GitHub hub',         href: '/github-hub' },
    { label: 'Skills dashboard',   href: '/skills' },
    { label: 'Revenue',            href: '/revenue' },
    { label: 'Portfolio',          href: '/portfolio' },
    { label: 'Director',           href: '/director' },
    { label: 'Trends',             href: '/trends' },
    { label: 'Spy',                href: '/spy' },
    { label: 'Money',              href: '/money' },
    { label: 'Orchestration',      href: '/orchestration' },
    { label: 'Session',            href: '/session' },
    { label: 'Command line',       href: '/command' },
    { label: 'Content hub',        href: '/content-hub' },
    { label: 'Media lab',          href: '/media-lab' },
    { label: 'Pipeline',           href: '/pipeline' },
    { label: 'Factory',            href: '/factory' },
    { label: 'AI studio',          href: '/ai-studio' },
    { label: 'Ollama studio',      href: '/ollama-studio' },
  ];

  let overlay = null, input = null, list = null;
  let items = ROUTES.slice();
  let cursor = 0;

  function build() {
    overlay = document.createElement('div');
    overlay.className = 'command-palette';

    const box = document.createElement('div');
    box.className = 'command-palette__box';

    input = document.createElement('input');
    input.className = 'command-palette__input';
    input.placeholder = 'Where to, sir?';
    input.spellcheck = false;

    list = document.createElement('div');
    list.className = 'command-palette__list';

    box.appendChild(input);
    box.appendChild(list);
    overlay.appendChild(box);
    document.body.appendChild(overlay);

    input.addEventListener('input', () => { cursor = 0; render(); });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') { cursor = Math.min(items.length - 1, cursor + 1); e.preventDefault(); render(); }
      else if (e.key === 'ArrowUp') { cursor = Math.max(0, cursor - 1); e.preventDefault(); render(); }
      else if (e.key === 'Enter') { go(); }
      else if (e.key === 'Escape') { close(); }
    });
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  }

  function fuzzy(q) {
    if (!q) return ROUTES.slice();
    q = q.toLowerCase();
    return ROUTES
      .map(r => ({ r, s: score(r.label.toLowerCase(), q) }))
      .filter(x => x.s > 0)
      .sort((a, b) => b.s - a.s)
      .map(x => x.r);
  }

  function score(label, q) {
    let i = 0, s = 0;
    for (const c of q) {
      const idx = label.indexOf(c, i);
      if (idx < 0) return 0;
      s += (idx === i ? 2 : 1);
      i = idx + 1;
    }
    return s;
  }

  function render() {
    items = fuzzy(input.value);
    list.textContent = '';
    items.slice(0, 30).forEach((r, i) => {
      const row = document.createElement('div');
      row.className = 'command-palette__item' + (i === cursor ? ' active' : '');
      const label = document.createElement('span');
      label.textContent = r.label;
      const kbd = document.createElement('span');
      kbd.className = 'command-palette__kbd';
      kbd.textContent = r.href;
      row.appendChild(label);
      row.appendChild(kbd);
      row.addEventListener('click', () => { cursor = i; go(); });
      list.appendChild(row);
    });
  }

  function open() {
    if (!overlay) build();
    overlay.classList.add('open');
    input.value = '';
    cursor = 0;
    render();
    setTimeout(() => input.focus(), 50);
  }

  function close() {
    if (overlay) overlay.classList.remove('open');
  }

  function go() {
    const target = items[cursor];
    if (target) window.location.href = target.href;
  }

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if (overlay && overlay.classList.contains('open')) close();
      else open();
    }
  });

  window.CommandPalette = { open, close };
  document.addEventListener('DOMContentLoaded', build);
})();
