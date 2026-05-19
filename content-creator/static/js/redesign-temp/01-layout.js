/* PHASE 1: Layout & Navigation - Sidebar State Management */
'use strict';

// ─── Sidebar Collapse Controller ─────────────────────────────────────────────
const SidebarController = {
  isCollapsed: false,

  init() {
    // Load saved state
    const saved = localStorage.getItem('jarvis-sidebar-collapsed');
    this.isCollapsed = saved === 'true';

    // Create toggle button
    this.createToggle();

    // Apply initial state
    this.applyState();

    // Bind keyboard shortcut
    document.addEventListener('keydown', (e) => {
      if (e.key === 'b' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        this.toggle();
      }
    });
  },

  createToggle() {
    const btn = document.createElement('button');
    btn.className = 'sidebar-toggle';
    btn.title = 'Toggle sidebar (Ctrl+B)';
    btn.setAttribute('aria-label', 'Toggle sidebar');

    // Create SVG safely
    const svgNS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '1.5');
    svg.setAttribute('width', '20');
    svg.setAttribute('height', '20');

    const rect = document.createElementNS(svgNS, 'rect');
    rect.setAttribute('x', '3');
    rect.setAttribute('y', '3');
    rect.setAttribute('width', '18');
    rect.setAttribute('height', '18');
    rect.setAttribute('rx', '2');

    const line = document.createElementNS(svgNS, 'line');
    line.setAttribute('x1', '9');
    line.setAttribute('y1', '3');
    line.setAttribute('x2', '9');
    line.setAttribute('y2', '21');

    svg.appendChild(rect);
    svg.appendChild(line);
    btn.appendChild(svg);

    btn.addEventListener('click', () => this.toggle());
    document.body.appendChild(btn);
  },

  toggle() {
    this.isCollapsed = !this.isCollapsed;
    localStorage.setItem('jarvis-sidebar-collapsed', this.isCollapsed);
    this.applyState();
  },

  applyState() {
    const shell = document.querySelector('.app-shell');
    const toggle = document.querySelector('.sidebar-toggle');

    if (this.isCollapsed) {
      shell?.classList.add('sidebar-collapsed');
      toggle?.classList.add('visible');
    } else {
      shell?.classList.remove('sidebar-collapsed');
      toggle?.classList.remove('visible');
    }
  }
};

// ─── Contextual Navigation Controller ────────────────────────────────────────
const ContextualNav = {
  hasActiveGeneration: false,
  isExploring: false,

  init() {
    // Check generation status
    this.checkGenerationStatus();

    // Check URL for exploration mode
    this.isExploring = location.pathname.includes('/github-hub') ||
                       location.pathname.includes('/skills') ||
                       location.pathname.includes('/research');

    this.applyContextualState();
  },

  async checkGenerationStatus() {
    try {
      const res = await fetch('/api/repos/services');
      const data = await res.json();
      // If any service is running, hide God Mode less
      const hasActive = Object.values(data.services || {}).some(
        (s) => s.status === 'running'
      );
      this.hasActiveGeneration = hasActive;
    } catch {
      this.hasActiveGeneration = false;
    }

    this.applyContextualState();
  },

  applyContextualState() {
    const shell = document.querySelector('.app-shell');
    if (!shell) return;

    // Toggle sections based on context
    if (!this.hasActiveGeneration) {
      shell.classList.add('no-generation');
    }

    if (!this.isExploring) {
      shell.classList.add('not-exploring');
    }
  }
};

// ─── Init ────────────────────────────────────────────────────────────────────
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    SidebarController.init();
    ContextualNav.init();
  });
} else {
  SidebarController.init();
  ContextualNav.init();
}
