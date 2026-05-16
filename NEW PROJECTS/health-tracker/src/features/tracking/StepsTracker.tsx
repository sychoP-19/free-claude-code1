import type { StepsEntry } from '../../types';
import { useState } from 'react';
import { daySteps } from '../../utils/calculations';
import './StepsTracker.css';

interface Props {
  entries: StepsEntry[];
  dailyGoal: number;
  onAdd: (e: StepsEntry) => void;
  onDelete: (date: string) => void;
}

export default function StepsTracker({ entries, dailyGoal, onAdd, onDelete }: Props) {
  const [steps, setSteps] = useState('');
  const today = new Date().toISOString().slice(0, 10);
  const todaySteps = daySteps(entries, today);
  const pct = dailyGoal > 0 ? Math.min((todaySteps / dailyGoal) * 100, 100) : 0;
  const goalReached = todaySteps >= dailyGoal;

  const recent = [...entries].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 7);
  const weeklyAvg = recent.length > 0
    ? Math.round(recent.reduce((s, e) => s + e.steps, 0) / recent.length)
    : 0;

  const circumference = 2 * Math.PI * 52;
  const strokeDash = `${(pct / 100) * circumference} ${circumference}`;
  const ringColor = goalReached ? '#10B981' : pct >= 50 ? '#F59E0B' : '#3B82F6';

  function handleAdd() {
    const n = Number(steps);
    if (!n || n <= 0) return;
    onAdd({ date: today, steps: n });
    setSteps('');
  }

  return (
    <div className="steps-tracker">
      <h2 className="section-title">Steps Tracker</h2>

      <div className="steps-ring-card">
        <svg className="steps-ring" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="52" fill="none" stroke="var(--surface2)" strokeWidth="10" />
          <circle cx="60" cy="60" r="52" fill="none" stroke={ringColor} strokeWidth="10"
            strokeDasharray={strokeDash} strokeLinecap="round"
            transform="rotate(-90 60 60)" style={{ transition: 'stroke-dasharray 0.6s ease' }} />
          <text x="60" y="48" textAnchor="middle" fill="var(--text)" fontSize="18" fontWeight="700">
            {todaySteps.toLocaleString()}
          </text>
          <text x="60" y="64" textAnchor="middle" fill="var(--text2)" fontSize="9">of {dailyGoal.toLocaleString()}</text>
          <text x="60" y="78" textAnchor="middle" fill={ringColor} fontSize="11" fontWeight="600">
            {Math.round(pct)}%
          </text>
        </svg>
        <div className="steps-ring-stats">
          <div className="steps-stat">
            <span className="steps-stat-label">Weekly Average</span>
            <span className="steps-stat-value">{weeklyAvg.toLocaleString()}</span>
          </div>
          <div className="steps-stat">
            <span className="steps-stat-label">Remaining</span>
            <span className="steps-stat-value" style={{ color: goalReached ? 'var(--green)' : 'var(--text)' }}>
              {goalReached ? 'Goal reached!' : `${(dailyGoal - todaySteps).toLocaleString()} steps`}
            </span>
          </div>
        </div>
      </div>

      <div className="steps-form">
        <div className="form-field">
          <label>Steps</label>
          <input type="number" value={steps} onChange={e => setSteps(e.target.value)}
            placeholder="e.g. 5000" min="1" />
        </div>
        <button className="btn btn-primary" onClick={handleAdd} disabled={!steps}>
          {recent.find(e => e.date === today) ? 'Update Today' : 'Log Steps'}
        </button>
      </div>

      <div className="steps-quick">
        <span className="steps-quick-label">Quick add:</span>
        {[1000, 2000, 5000, 10000].map(n => (
          <button key={n} className="steps-quick-btn" onClick={() => { onAdd({ date: today, steps: n }); }}>
            {n.toLocaleString()}
          </button>
        ))}
      </div>

      <div className="steps-history">
        <h3 className="chart-title">Recent Steps</h3>
        {recent.length === 0 && <p className="empty-msg">No step entries yet</p>}
        <div className="history-list">
          {recent.map(e => {
            const ep = dailyGoal > 0 ? Math.min((e.steps / dailyGoal) * 100, 100) : 0;
            return (
              <div key={e.date} className="history-row">
                <span className="history-date">{e.date}</span>
                <span className="history-value">{e.steps.toLocaleString()} steps</span>
                <div className="steps-mini-bar">
                  <div className="steps-mini-fill" style={{ width: `${ep}%`, background: ep >= 100 ? 'var(--green)' : 'var(--primary)' }} />
                </div>
                <button className="btn-delete" onClick={() => onDelete(e.date)}>✕</button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
