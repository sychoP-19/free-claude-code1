/* JARVIS Sound Alerts — Web Audio API synthesized tones, no external files needed */
'use strict';

const SoundAlerts = (() => {
  let ctx = null;
  let muted = localStorage.getItem('jarvis-sound-muted') === 'true';

  const PROFILES = {
    success:       { freq: [523, 784], dur: [0.08, 0.15], gap: 0.06, type: 'sine', vol: 0.25 },
    error:         { freq: [440, 330], dur: [0.1, 0.2],  gap: 0.08, type: 'sawtooth', vol: 0.18 },
    warning:       { freq: [660, 660], dur: [0.06, 0.06], gap: 0.1,  type: 'triangle', vol: 0.2 },
    info:          { freq: [880],      dur: [0.06],       gap: 0,    type: 'sine', vol: 0.12 },
    ws_connect:    { freq: [440, 660, 880], dur: [0.04, 0.04, 0.08], gap: 0.02, type: 'sine', vol: 0.2 },
    ws_disconnect: { freq: [880, 660, 440], dur: [0.08, 0.04, 0.04], gap: 0.02, type: 'triangle', vol: 0.18 },
    chat_incoming: { freq: [1047],     dur: [0.05],       gap: 0,    type: 'sine', vol: 0.1 },
  };

  function _getCtx() {
    if (!ctx) {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }

  function _playTone(audioCtx, freq, duration, type, volume, startTime) {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, startTime);
    gain.gain.setValueAtTime(volume, startTime);
    gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start(startTime);
    osc.stop(startTime + duration + 0.02);
  }

  function play(name) {
    if (muted) return;
    const p = PROFILES[name];
    if (!p) return;
    try {
      const ac = _getCtx();
      let t = ac.currentTime + 0.01;
      for (let i = 0; i < p.freq.length; i++) {
        _playTone(ac, p.freq[i], p.dur[i], p.type, p.vol, t);
        t += p.dur[i] + p.gap;
      }
    } catch { /* Web Audio unavailable — silent fallback */ }
  }

  function toggleMute() {
    muted = !muted;
    localStorage.setItem('jarvis-sound-muted', String(muted));
    _updateBtn();
    if (!muted) play('info');
  }

  function isMuted() { return muted; }

  function _updateBtn() {
    const btn = document.getElementById('sound-toggle');
    if (!btn) return;
    btn.classList.toggle('sound-muted', muted);
    btn.title = muted ? 'Sound off — click to enable' : 'Sound on — click to mute';
    btn.setAttribute('aria-label', muted ? 'Enable sound alerts' : 'Mute sound alerts');
    const off = btn.querySelector('.sound-off');
    const on = btn.querySelector('.sound-on');
    if (off) off.style.display = muted ? '' : 'none';
    if (on) on.style.display = muted ? 'none' : '';
  }

  function init() {
    _updateBtn();
    const btn = document.getElementById('sound-toggle');
    if (btn) btn.addEventListener('click', toggleMute);
  }

  return { init, play, toggleMute, isMuted };
})();

window.SoundAlerts = SoundAlerts;
document.addEventListener('DOMContentLoaded', SoundAlerts.init);

/* Patch toast to auto-play sound */
(function () {
  const origToast = window.toast;
  if (typeof origToast !== 'function') return;
  window.toast = function (opts) {
    origToast(opts);
    const level = (opts && opts.level) || 'info';
    const map = { error: 'error', warning: 'warning', success: 'success', info: 'info' };
    if (SoundAlerts && map[level]) SoundAlerts.play(map[level]);
  };
})();
