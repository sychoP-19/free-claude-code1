/* JARVIS Voice Interface v2.1 — Web Speech API + Whisper fallback */
'use strict';

const Voice = (() => {
let recognition = null;
const synth = window.speechSynthesis;
let listening = false;
let voiceBtn = null;
let statusEl = null;
let currentLang = 'en-US';
let pttActive = false;
let pttDownAt = 0;

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

function init() {
voiceBtn = document.getElementById('voice-btn');
statusEl = document.getElementById('voice-status');

if (!SpeechRecognition) {
if (voiceBtn) {
voiceBtn.title = 'Voice not supported in this browser';
voiceBtn.style.opacity = '0.3';
}
_showStatus('voice unavailable in this browser');
return;
}

_buildRecognition();
if (voiceBtn) voiceBtn.addEventListener('click', toggle);
_wirePTT();
_wireLangSelect();
}

function _buildRecognition() {
recognition = new SpeechRecognition();
recognition.continuous = false;
recognition.interimResults = false;
recognition.lang = currentLang;

recognition.onresult = (e) => {
const text = e.results[0][0].transcript;
_showStatus('heard: ' + text.slice(0, 60), 'ok');
_onVoiceInput(text);
};

recognition.onstart = () => {
listening = true;
if (voiceBtn) { voiceBtn.classList.add('listening'); voiceBtn.title = 'Listening…'; }
_showStatus('listening…');
};

recognition.onend = () => {
listening = false;
if (voiceBtn) { voiceBtn.classList.remove('listening'); voiceBtn.title = 'Speak to JARVIS'; }
};

recognition.onerror = (e) => {
listening = false;
if (voiceBtn) {
voiceBtn.classList.remove('listening');
voiceBtn.classList.add('mic-error');
setTimeout(() => voiceBtn.classList.remove('mic-error'), 1000);
}
_handleError(e.error);
};
}

async function _handleError(code) {
const map = {
'no-speech': ['', null],
'aborted': ['', null],
'audio-capture': ['no mic detected', 'err'],
'network': ['speech service unreachable - using text chat', 'warn'],
'not-allowed': ['mic blocked - click to re-request', 'err'],
'service-not-allowed': ['mic blocked at OS level', 'err'],
'bad-grammar': ['grammar error', 'err'],
'language-not-supported': ['language ' + currentLang + ' not supported', 'err'],
};
const [msg, kind] = map[code] || ['voice error: ' + code, 'err'];
if (!msg) return;
_showStatus(msg, kind);
if (code === 'not-allowed') _showPermissionModal();
}

function _showStatus(msg, kind) {
if (!statusEl) return;
statusEl.textContent = msg;
statusEl.className = 'voice-status' + (kind ? ' voice-status--' + kind : '');
statusEl.style.opacity = msg ? '1' : '0';
if (msg && kind === 'ok') setTimeout(() => { statusEl.style.opacity = '0'; }, 4000);
}

function _showPermissionModal() {
if (document.getElementById('voice-perm-modal')) return;
const overlay = document.createElement('div');
overlay.id = 'voice-perm-modal';
overlay.className = 'voice-perm-overlay';

const box = document.createElement('div');
box.className = 'voice-perm-box';

const h = document.createElement('div');
h.className = 'voice-perm-title';
h.textContent = 'Microphone access needed';

const p1 = document.createElement('div');
p1.className = 'voice-perm-text';
p1.textContent = 'JARVIS needed microphone permission to listen. Click below to re-request.';

const p2 = document.createElement('div');
p2.className = 'voice-perm-text voice-perm-text--muted';
p2.textContent = 'Note: Web Speech API only works on https:// or http://localhost.';

const row = document.createElement('div');
row.className = 'voice-perm-row';

const okBtn = document.createElement('button');
okBtn.className = 'voice-perm-btn voice-perm-btn--primary';
okBtn.textContent = 'Request access';
okBtn.addEventListener('click', async () => {
try {
const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
stream.getTracks().forEach(t => t.stop());
_showStatus('mic ok - try again', 'ok');
document.body.removeChild(overlay);
} catch (err) {
_showStatus('mic denied: ' + err.message, 'err');
}
});

const cancelBtn = document.createElement('button');
cancelBtn.className = 'voice-perm-btn';
cancelBtn.textContent = 'Close';
cancelBtn.addEventListener('click', () => document.body.removeChild(overlay));

row.appendChild(okBtn);
row.appendChild(cancelBtn);
box.appendChild(h);
box.appendChild(p1);
box.appendChild(p2);
box.appendChild(row);
overlay.appendChild(box);
document.body.appendChild(overlay);
}

function _wireLangSelect() {
const sel = document.getElementById('jarvis-lang-select');
if (!sel) return;
sel.value = currentLang;
sel.addEventListener('change', () => setLang(sel.value));
}

function setLang(lang) {
currentLang = lang;
if (recognition) recognition.lang = lang;
const sel = document.getElementById('jarvis-lang-select');
if (sel) sel.value = lang;
_showStatus('lang: ' + lang, 'ok');
}

function toggle() {
if (!recognition) return;
try {
if (listening) recognition.stop();
else recognition.start();
} catch (e) {
_showStatus('recognition busy - please wait', 'err');
}
}

function _isArabic(text) { return /[؀-ۿ]/.test(text); }

function _onVoiceInput(text) {
if (window.ChatOverlay && window.ChatOverlay.sendMessage) {
window.ChatOverlay.sendMessage(text, true);
} else {
speak('You said: ' + text);
}
}

function speak(text) {
if (!synth || !text) return;
synth.cancel();
const utt = new SpeechSynthesisUtterance(text);
utt.rate = 0.92;
utt.pitch = 0.85;
utt.volume = 0.9;

const arabic = _isArabic(text);
utt.lang = arabic ? 'ar-SA' : 'en-US';

const voices = synth.getVoices();
if (voices.length) {
const preferred = arabic
? voices.find(v => v.lang.startsWith('ar'))
: voices.find(v => v.lang === 'en-US' && /google/i.test(v.name)) || voices.find(v => v.lang === 'en-US');
if (preferred) utt.voice = preferred;
}
synth.speak(utt);
}

function _wirePTT() {
document.addEventListener('keydown', (e) => {
if (e.code !== 'Space') return;
if (e.repeat) return;
const tag = (e.target && e.target.tagName) || '';
if (tag === 'INPUT' || tag === 'TEXTAREA' || (e.target && e.target.isContentEditable)) return;
if (pttActive) return;
pttActive = true;
pttDownAt = Date.now();
e.preventDefault();
_showStatus('PTT listening - release Space to send');
try { recognition && recognition.start(); } catch { /* already started */ }
}, true);

document.addEventListener('keyup', (e) => {
if (e.code !== 'Space' || !pttActive) return;
pttActive = false;
const held = Date.now() - pttDownAt;
try { recognition && recognition.stop(); } catch { /* already stopped */ }
if (held < 300) _showStatus('PTT too short - hold Space longer', 'err');
}, true);
}

if (typeof speechSynthesis !== 'undefined') {
speechSynthesis.onvoiceschanged = () => { /* voices ready */ };
}

return { init, toggle, speak, setLang };
})();

window.Voice = Voice;
window.jarvisVoice = Voice;
document.addEventListener('DOMContentLoaded', Voice.init);
