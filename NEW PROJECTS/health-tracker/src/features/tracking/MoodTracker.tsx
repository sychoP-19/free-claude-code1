import type { MoodEntry } from '../../types';
import { useState } from 'react';
import './MoodTracker.css';

const MOODS: { emoji: MoodEntry['mood']; label: string; color: string }[] = [
  { emoji: '😴', label: 'Tired', color: '#6366F1' },
  { emoji: '😐', label: 'Meh', color: '#94A3B8' },
  { emoji: '😊', label: 'Good', color: '#10B981' },
  { emoji: '⚡', label: 'Energized', color: '#F59E0B' },
];

const ENERGY_LABELS = ['', 'Very Low', 'Low', 'Medium', 'High', 'Very High'];

interface Props {
  entries: MoodEntry[];
  onAdd: (e: MoodEntry) => void;
  onDelete: (timestamp: string) => void;
}

export default function MoodTracker({ entries, onAdd, onDelete }: Props) {
  const [mood, setMood] = useState<MoodEntry['mood']>('😊');
  const [energy, setEnergy] = useState<1 | 2 | 3 | 4 | 5>(3);
  const today = new Date().toISOString().slice(0, 10);

  const todayEntries = entries.filter(e => e.date === today);
  const recent = [...entries].sort((a, b) => b.timestamp.localeCompare(a.timestamp)).slice(0, 10);

  function handleAdd() {
    onAdd({ date: today, mood, energy, timestamp: new Date().toISOString() });
    setEnergy(3);
  }

  function avgEnergy() {
    if (recent.length === 0) return 0;
    return recent.reduce((s, e) => s + e.energy, 0) / recent.length;
  }

  const avg = avgEnergy();
  const energyColor = avg >= 4 ? '#10B981' : avg >= 3 ? '#F59E0B' : '#EF4444';

  return (
    <div className="mood-tracker">
      <h2 className="section-title">Mood & Energy</h2>

      <div className="mood-summary">
        <div className="mood-energy-ring">
          <svg viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="52" fill="none" stroke="var(--surface2)" strokeWidth="10" />
            <circle cx="60" cy="60" r="52" fill="none" stroke={energyColor} strokeWidth="10"
              strokeDasharray={`${(avg / 5) * 327} 327`} strokeLinecap="round"
              transform="rotate(-90 60 60)" style={{ transition: 'stroke-dasharray 0.6s ease' }} />
            <text x="60" y="55" textAnchor="middle" fill="var(--text)" fontSize="22" fontWeight="700">
              {avg > 0 ? avg.toFixed(1) : '—'}
            </text>
            <text x="60" y="72" textAnchor="middle" fill="var(--text2)" fontSize="10">avg energy</text>
          </svg>
        </div>
        <div className="mood-summary-right">
          <span className="mood-summary-label">Today's entries</span>
          <span className="mood-summary-value">{todayEntries.length}</span>
          <div className="mood-today-emojis">
            {todayEntries.map((e, i) => <span key={i} className="mood-today-emoji">{e.mood}</span>)}
          </div>
        </div>
      </div>

      <div className="mood-form">
        <div className="mood-picker-section">
          <label className="mood-form-label">How are you feeling?</label>
          <div className="mood-picker">
            {MOODS.map(m => (
              <button key={m.emoji}
                className={`mood-pick-btn ${mood === m.emoji ? 'active' : ''}`}
                onClick={() => setMood(m.emoji)} type="button"
                style={mood === m.emoji ? { borderColor: m.color, background: `${m.color}18` } : {}}>
                <span className="mood-pick-emoji">{m.emoji}</span>
                <span className="mood-pick-label">{m.label}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="energy-section">
          <label className="mood-form-label">Energy Level</label>
          <div className="energy-slider-row">
            <span className="energy-low">1</span>
            <input type="range" min="1" max="5" value={energy}
              onChange={e => setEnergy(Number(e.target.value) as 1 | 2 | 3 | 4 | 5)}
              className="energy-slider" />
            <span className="energy-high">5</span>
          </div>
          <span className="energy-value">{energy}/5 — {ENERGY_LABELS[energy]}</span>
        </div>
        <button className="btn btn-primary mood-submit" onClick={handleAdd}>Log Mood</button>
      </div>

      <div className="mood-history">
        <h3 className="chart-title">Recent Moods</h3>
        {recent.length === 0 && <p className="empty-msg">No mood entries yet</p>}
        <div className="mood-history-list">
          {recent.map((e, i) => {
            const m = MOODS.find(x => x.emoji === e.mood);
            return (
              <div key={i} className="mood-history-row" style={{ borderLeftColor: m?.color ?? 'var(--text3)' }}>
                <span className="mood-history-emoji">{e.mood}</span>
                <div className="mood-history-info">
                  <span className="mood-history-energy">Energy: {e.energy}/5</span>
                  <span className="mood-history-time">
                    {new Date(e.timestamp).toLocaleDateString()} {new Date(e.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
                <button className="btn-delete" onClick={() => onDelete(e.timestamp)}>✕</button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
