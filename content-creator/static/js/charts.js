/* JARVIS Charts Engine — Pure Canvas, No Dependencies */
'use strict';

// ─── UTILITIES ─────────────────────────────────────────────────────────────
const ease = (t) => t < 0.5 ? 2*t*t : -1+(4-2*t)*t;
const lerp  = (a, b, t) => a + (b - a) * t;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1,3), 16);
  const g = parseInt(hex.slice(3,5), 16);
  const b = parseInt(hex.slice(5,7), 16);
  return { r, g, b };
}

// ─── BASE CHART ────────────────────────────────────────────────────────────
class JarvisChart {
  constructor(canvas, opts = {}) {
    this.canvas  = typeof canvas === 'string' ? document.getElementById(canvas) : canvas;
    this.ctx     = this.canvas.getContext('2d');
    this.opts    = opts;
    this.frame   = 0;
    this.animPct = 0;
    this._resize();
    window.addEventListener('resize', () => this._resize());
    this._tick();
  }

  _resize() {
    const r = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width  = r.width  || this.canvas.offsetWidth  || 400;
    this.canvas.height = this.canvas.offsetHeight || 200;
    this.W = this.canvas.width;
    this.H = this.canvas.height;
  }

  _tick() {
    this.animPct = Math.min(this.animPct + 0.018, 1);
    this.frame++;
    this.draw(ease(this.animPct));
    requestAnimationFrame(() => this._tick());
  }

  draw(p) {}

  _clear() {
    this.ctx.clearRect(0, 0, this.W, this.H);
  }

  _text(txt, x, y, color = '#00d4ff', size = 10, align = 'center') {
    this.ctx.fillStyle = color;
    this.ctx.font = `${size}px 'JetBrains Mono', monospace`;
    this.ctx.textAlign = align;
    this.ctx.fillText(txt, x, y);
  }
}

// ─── LINE CHART ────────────────────────────────────────────────────────────
class LineChart extends JarvisChart {
  constructor(canvas, data, opts = {}) {
    super(canvas, opts);
    this.data    = data;       // [{ label, values: [], color }]
    this.labels  = opts.labels || [];
    this.padding = { top: 20, right: 20, bottom: 30, left: 40 };
  }

  draw(p) {
    this._clear();
    const { ctx, W, H, padding: pad } = this;
    const cW = W - pad.left - pad.right;
    const cH = H - pad.top - pad.bottom;

    const allVals = this.data.flatMap(s => s.values);
    const maxV = Math.max(...allVals, 1);
    const minV = Math.min(...allVals, 0);
    const range = maxV - minV || 1;

    const toX = (i) => pad.left + (i / (this.data[0].values.length - 1)) * cW;
    const toY = (v) => pad.top + (1 - (v - minV) / range) * cH;

    // Grid
    ctx.strokeStyle = 'rgba(0,212,255,0.08)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + (cH / 4) * i;
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + cW, y); ctx.stroke();
      const val = maxV - (range / 4) * i;
      this._text(val >= 1000 ? (val/1000).toFixed(1)+'K' : val.toFixed(0), pad.left - 5, y + 3, 'rgba(0,212,255,0.4)', 9, 'right');
    }

    // Series
    this.data.forEach(series => {
      const vals   = series.values;
      const color  = series.color || '#00d4ff';
      const rgb    = hexToRgb(color);
      const pts    = Math.max(2, Math.floor(vals.length * p));

      // Gradient fill
      const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + cH);
      grad.addColorStop(0, `rgba(${rgb.r},${rgb.g},${rgb.b},0.3)`);
      grad.addColorStop(1, `rgba(${rgb.r},${rgb.g},${rgb.b},0)`);

      ctx.beginPath();
      ctx.moveTo(toX(0), toY(vals[0]));
      for (let i = 1; i < pts; i++) ctx.lineTo(toX(i), toY(vals[i]));
      ctx.lineTo(toX(pts - 1), pad.top + cH);
      ctx.lineTo(toX(0), pad.top + cH);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();

      // Line
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.shadowBlur = 8;
      ctx.shadowColor = color;
      ctx.moveTo(toX(0), toY(vals[0]));
      for (let i = 1; i < pts; i++) ctx.lineTo(toX(i), toY(vals[i]));
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Live dot
      if (pts > 0) {
        const lx = toX(pts - 1), ly = toY(vals[pts - 1]);
        ctx.beginPath(); ctx.arc(lx, ly, 4, 0, Math.PI * 2);
        ctx.fillStyle = color; ctx.shadowBlur = 12; ctx.shadowColor = color;
        ctx.fill(); ctx.shadowBlur = 0;
      }
    });

    // X labels
    this.labels.forEach((lbl, i) => {
      if (i % Math.ceil(this.labels.length / 6) === 0)
        this._text(lbl, toX(i), H - 5, 'rgba(0,212,255,0.4)', 9);
    });
  }
}

// ─── DONUT CHART ───────────────────────────────────────────────────────────
class DonutChart extends JarvisChart {
  constructor(canvas, segments, opts = {}) {
    super(canvas, opts);
    this.segments = segments;  // [{ label, value, color }]
  }

  draw(p) {
    this._clear();
    const { ctx, W, H } = this;
    const cx = W / 2, cy = H / 2;
    const r  = Math.min(cx, cy) - 20;
    const ir = r * 0.58;
    const total = this.segments.reduce((a, s) => a + s.value, 0) || 1;

    let angle = -Math.PI / 2;
    this.segments.forEach((seg, i) => {
      const sweep = (seg.value / total) * Math.PI * 2 * p;
      const rgb   = hexToRgb(seg.color || '#00d4ff');
      const mid   = angle + sweep / 2;

      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, r, angle, angle + sweep);
      ctx.closePath();
      ctx.fillStyle = `rgba(${rgb.r},${rgb.g},${rgb.b},0.85)`;
      ctx.shadowBlur = 12; ctx.shadowColor = seg.color;
      ctx.fill(); ctx.shadowBlur = 0;

      // Label line
      if (p > 0.8) {
        const lx = cx + Math.cos(mid) * (r + 16);
        const ly = cy + Math.sin(mid) * (r + 16);
        const pct = Math.round(seg.value / total * 100);
        ctx.fillStyle = seg.color || '#00d4ff';
        ctx.font = '9px JetBrains Mono,monospace';
        ctx.textAlign = lx > cx ? 'left' : 'right';
        ctx.fillText(pct + '%', lx, ly);
      }
      angle += sweep;
    });

    // Hole
    ctx.beginPath(); ctx.arc(cx, cy, ir, 0, Math.PI * 2);
    ctx.fillStyle = '#09090b'; ctx.fill();

    // Center label
    const best = this.segments.reduce((a, b) => b.value > a.value ? b : a, this.segments[0]);
    this._text(best.label, cx, cy - 6, best.color, 10);
    this._text(Math.round(best.value / total * 100) + '%', cx, cy + 10, '#fff', 16);
  }
}

// ─── BAR CHART ─────────────────────────────────────────────────────────────
class BarChart extends JarvisChart {
  constructor(canvas, data, opts = {}) {
    super(canvas, opts);
    this.data    = data;    // [{ label, value, color }]
    this.padding = { top: 20, right: 20, bottom: 30, left: 40 };
  }

  draw(p) {
    this._clear();
    const { ctx, W, H, padding: pad } = this;
    const cW  = W - pad.left - pad.right;
    const cH  = H - pad.top - pad.bottom;
    const maxV = Math.max(...this.data.map(d => d.value), 1);
    const bW   = cW / this.data.length * 0.6;
    const gap  = cW / this.data.length;

    // Grid
    ctx.strokeStyle = 'rgba(0,212,255,0.08)'; ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + cH * (1 - i / 4);
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + cW, y); ctx.stroke();
    }

    this.data.forEach((item, i) => {
      const x   = pad.left + gap * i + (gap - bW) / 2;
      const h   = (item.value / maxV) * cH * p;
      const y   = pad.top + cH - h;
      const rgb = hexToRgb(item.color || '#00d4ff');
      const grad = ctx.createLinearGradient(0, y, 0, pad.top + cH);
      grad.addColorStop(0, `rgba(${rgb.r},${rgb.g},${rgb.b},0.9)`);
      grad.addColorStop(1, `rgba(${rgb.r},${rgb.g},${rgb.b},0.2)`);

      ctx.fillStyle = grad;
      ctx.shadowBlur = 6; ctx.shadowColor = item.color || '#00d4ff';
      ctx.fillRect(x, y, bW, h);
      ctx.shadowBlur = 0;

      this._text(item.label, x + bW / 2, H - 5, 'rgba(0,212,255,0.5)', 9);
      if (p > 0.9) this._text(
        item.value >= 1000 ? '$'+(item.value/1000).toFixed(1)+'K' : '$'+item.value,
        x + bW / 2, y - 4, item.color || '#00d4ff', 9
      );
    });
  }
}

// ─── RADAR SWEEP CHART ─────────────────────────────────────────────────────
class RadarSweep extends JarvisChart {
  constructor(canvas, items, opts = {}) {
    super(canvas, opts);
    this.items  = items;  // [{ label, value (0-1), color }]
    this.sweep  = 0;
  }

  draw(p) {
    this._clear();
    const { ctx, W, H, frame } = this;
    const cx = W / 2, cy = H / 2;
    const r  = Math.min(cx, cy) - 24;
    this.sweep = (frame * 0.012) % (Math.PI * 2);

    // Rings
    [0.25, 0.5, 0.75, 1].forEach(frac => {
      ctx.beginPath(); ctx.arc(cx, cy, r * frac, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(0,212,255,0.12)'; ctx.lineWidth = 1; ctx.stroke();
    });

    // Spokes
    const n = this.items.length;
    this.items.forEach((item, i) => {
      const a = (i / n) * Math.PI * 2 - Math.PI / 2;
      ctx.beginPath(); ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r);
      ctx.strokeStyle = 'rgba(0,212,255,0.15)'; ctx.stroke();
    });

    // Sweep gradient
    const g = ctx.createConicalGradient ? null : null;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(this.sweep);
    const sweepGrad = ctx.createLinearGradient(0, -r, 0, 0);
    sweepGrad.addColorStop(0, 'rgba(0,212,255,0)');
    sweepGrad.addColorStop(1, 'rgba(0,212,255,0.15)');
    ctx.beginPath(); ctx.moveTo(0, 0);
    ctx.arc(0, 0, r, -Math.PI / 6, 0);
    ctx.closePath();
    ctx.fillStyle = sweepGrad;
    ctx.fill();
    ctx.restore();

    // Sweep line
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(this.sweep - Math.PI / 2) * r, cy + Math.sin(this.sweep - Math.PI / 2) * r);
    ctx.strokeStyle = 'rgba(0,212,255,0.7)'; ctx.lineWidth = 1.5;
    ctx.shadowBlur = 8; ctx.shadowColor = '#00d4ff'; ctx.stroke(); ctx.shadowBlur = 0;

    // Data polygon
    ctx.beginPath();
    this.items.forEach((item, i) => {
      const a  = (i / n) * Math.PI * 2 - Math.PI / 2;
      const rv = item.value * r * p;
      const x  = cx + Math.cos(a) * rv;
      const y  = cy + Math.sin(a) * rv;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.fillStyle = 'rgba(0,212,255,0.1)';
    ctx.strokeStyle = '#00d4ff'; ctx.lineWidth = 1.5;
    ctx.shadowBlur = 6; ctx.shadowColor = '#00d4ff';
    ctx.fill(); ctx.stroke(); ctx.shadowBlur = 0;

    // Blips (dots on data points)
    this.items.forEach((item, i) => {
      const a  = (i / n) * Math.PI * 2 - Math.PI / 2;
      const rv = item.value * r * p;
      const x  = cx + Math.cos(a) * rv;
      const y  = cy + Math.sin(a) * rv;
      // Pulse when swept
      const diff = Math.abs(((this.sweep - (a + Math.PI / 2) + Math.PI * 3) % (Math.PI * 2)) - Math.PI * 2);
      const glow = diff < 0.3 ? 20 : 4;
      ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = item.color || '#00d4ff';
      ctx.shadowBlur = glow; ctx.shadowColor = item.color || '#00d4ff';
      ctx.fill(); ctx.shadowBlur = 0;

      // Labels
      const lx = cx + Math.cos(a) * (r + 14);
      const ly = cy + Math.sin(a) * (r + 14);
      ctx.fillStyle = 'rgba(0,212,255,0.7)';
      ctx.font = '9px JetBrains Mono,monospace';
      ctx.textAlign = lx > cx ? 'left' : (lx < cx ? 'right' : 'center');
      ctx.fillText(item.label, lx, ly + 3);
    });
  }
}

// ─── NEURAL GRAPH ──────────────────────────────────────────────────────────
class NeuralGraph extends JarvisChart {
  constructor(canvas, nodes, opts = {}) {
    super(canvas, opts);
    this.nodes = nodes.map(n => ({
      ...n,
      x:   Math.random() * 0.8 + 0.1,
      y:   Math.random() * 0.8 + 0.1,
      vx:  (Math.random() - 0.5) * 0.001,
      vy:  (Math.random() - 0.5) * 0.001,
      pulse: Math.random() * Math.PI * 2,
    }));
  }

  draw(p) {
    this._clear();
    const { ctx, W, H, nodes, frame } = this;

    // Update positions
    nodes.forEach(n => {
      n.x = clamp(n.x + n.vx, 0.05, 0.95);
      n.y = clamp(n.y + n.vy, 0.05, 0.95);
      if (n.x <= 0.05 || n.x >= 0.95) n.vx *= -1;
      if (n.y <= 0.05 || n.y >= 0.95) n.vy *= -1;
      n.pulse += 0.04;
    });

    // Connections
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        const dx = (a.x - b.x) * W, dy = (a.y - b.y) * H;
        const dist = Math.sqrt(dx*dx + dy*dy);
        if (dist < 180) {
          const alpha = (1 - dist / 180) * 0.25 * p;
          ctx.beginPath();
          ctx.strokeStyle = `rgba(0,212,255,${alpha})`;
          ctx.lineWidth = 1;
          ctx.moveTo(a.x * W, a.y * H);
          ctx.lineTo(b.x * W, b.y * H);
          ctx.stroke();
        }
      }
    }

    // Nodes
    nodes.forEach(n => {
      const x   = n.x * W, y = n.y * H;
      const r   = (n.size || 6) + Math.sin(n.pulse) * 2;
      const rgb = hexToRgb(n.color || '#00d4ff');
      ctx.beginPath(); ctx.arc(x, y, r * p, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${rgb.r},${rgb.g},${rgb.b},0.9)`;
      ctx.shadowBlur = 12 + Math.sin(n.pulse) * 6;
      ctx.shadowColor = n.color || '#00d4ff';
      ctx.fill(); ctx.shadowBlur = 0;
      if (p > 0.7 && n.label) {
        ctx.fillStyle = 'rgba(255,255,255,0.7)';
        ctx.font = '9px JetBrains Mono,monospace';
        ctx.textAlign = 'center';
        ctx.fillText(n.label, x, y + r + 12);
      }
    });
  }
}

// ─── WAVEFORM ──────────────────────────────────────────────────────────────
class Waveform extends JarvisChart {
  constructor(canvas, opts = {}) {
    super(canvas, opts);
    this.waves = [
      { freq: 0.02, amp: 0.3, phase: 0,    speed: 0.015, color: '#00d4ff' },
      { freq: 0.035, amp: 0.2, phase: 1.5,  speed: 0.022, color: '#3b82f6' },
      { freq: 0.015, amp: 0.15, phase: 3.0, speed: 0.01,  color: '#10b981' },
    ];
  }

  draw(p) {
    this._clear();
    const { ctx, W, H } = this;
    const cy = H / 2;
    this.waves.forEach(w => {
      w.phase += w.speed;
      const rgb = hexToRgb(w.color);
      ctx.beginPath();
      for (let x = 0; x < W; x++) {
        const y = cy + Math.sin(x * w.freq + w.phase) * H * w.amp * p;
        x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.strokeStyle = `rgba(${rgb.r},${rgb.g},${rgb.b},0.5)`;
      ctx.lineWidth = 1.5;
      ctx.shadowBlur = 8; ctx.shadowColor = w.color;
      ctx.stroke(); ctx.shadowBlur = 0;
    });
  }
}

// ─── EXPORTS ───────────────────────────────────────────────────────────────
window.JarvisCharts = { LineChart, DonutChart, BarChart, RadarSweep, NeuralGraph, Waveform };
