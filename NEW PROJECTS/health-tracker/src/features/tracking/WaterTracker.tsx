import type { WaterEntry } from '../../types';
import { useState } from 'react';
import { dayWater } from '../../utils/calculations';
import './WaterTracker.css';

const QUICK_AMTS = [
  { label: '1 Glass', ml: 250, icon: '🥛' },
  { label: 'Bottle', ml: 500, icon: '🍶' },
  { label: 'Large', ml: 750, icon: '🧴' },
  { label: '1 Liter', ml: 1000, icon: '💧' },
];

interface Props {
  entries: WaterEntry[];
  dailyGoal: number;
  onAdd: (e: WaterEntry) => void;
  onDelete: (timestamp: string) => void;
}

export default function WaterTracker({ entries, dailyGoal, onAdd, onDelete }: Props) {
  const [customMl, setCustomMl] = useState('');
  const today = new Date().toISOString().slice(0, 10);
  const todayMl = dayWater(entries, today);
  const pct = dailyGoal > 0 ? Math.min((todayMl / dailyGoal) * 100, 100) : 0;
  const todayEntries = entries.filter(e => e.date === today);

  function handleQuick(ml: number) {
    onAdd({ date: today, ml, timestamp: new Date().toISOString() });
  }

  function handleCustom() {
    const ml = Number(customMl);
    if (!ml || ml <= 0) return;
    onAdd({ date: today, ml, timestamp: new Date().toISOString() });
    setCustomMl('');
  }

  return (
    <div className="water-tracker">
      <h2 className="section-title">Hydration Tracker</h2>

      <div className="water-progress">
        <div className="water-visual">
          <div className="water-bottle">
            <div className="water-fill" style={{ height: `${pct}%` }}>
              <div className="water-wave"></div>
            </div>
            <div className="water-bottle-cap"></div>
          </div>
          <div className="water-stats">
            <span className="water-amount">{todayMl.toLocaleString()} ml</span>
            <span className="water-goal">of {dailyGoal.toLocaleString()} ml</span>
            <span className="water-pct">{Math.round(pct)}%</span>
          </div>
        </div>
      </div>

      <div className="water-quick">
        <span className="water-quick-label">Quick add:</span>
        {QUICK_AMTS.map(q => (
          <button key={q.ml} className="water-quick-btn" onClick={() => handleQuick(q.ml)}>
            <span className="water-quick-icon">{q.icon}</span>
            <span className="water-quick-text">{q.label}<br/><small>{q.ml}ml</small></span>
          </button>
        ))}
      </div>

      <div className="water-custom">
        <input type="number" value={customMl} onChange={e => setCustomMl(e.target.value)}
          placeholder="Custom ml" min="1" />
        <button className="btn btn-primary" onClick={handleCustom}>Add</button>
      </div>

      <div className="water-log">
        <h3 className="chart-title">Today's log</h3>
        {todayEntries.length === 0 && <p className="empty-msg">No water logged today</p>}
        {todayEntries.map((e, i) => (
          <div key={i} className="water-log-row">
            <span className="water-log-icon">💧</span>
            <span className="water-log-ml">{e.ml} ml</span>
            <span className="water-log-time">
              {new Date(e.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
            <button className="btn-delete" onClick={() => onDelete(e.timestamp)}>✕</button>
          </div>
        ))}
      </div>
    </div>
  );
}
