import type { SleepEntry } from '../../types';
import { useState } from 'react';
import { latestSleep, avgSleep } from '../../utils/calculations';
import './SleepTracker.css';

const QUALITY_STARS = [1, 2, 3, 4, 5] as const;
const QUALITY_LABELS: Record<number, string> = { 1: 'Very Poor', 2: 'Poor', 3: 'Fair', 4: 'Good', 5: 'Excellent' };

interface Props {
  entries: SleepEntry[];
  onAdd: (e: SleepEntry) => void;
  onDelete: (date: string) => void;
}

export default function SleepTracker({ entries, onAdd, onDelete }: Props) {
  const [hours, setHours] = useState('');
  const [quality, setQuality] = useState<1 | 2 | 3 | 4 | 5>(3);
  const today = new Date().toISOString().slice(0, 10);

  const last = latestSleep(entries);
  const avg7 = avgSleep(entries, 7);
  const todayEntry = entries.find(e => e.date === today);
  const recent = [...entries].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 7);

  function handleAdd() {
    const h = Number(hours);
    if (!h || h <= 0 || h > 24) return;
    onAdd({ date: today, hours: h, quality });
    setHours('');
    setQuality(3);
  }

  const avgPct = Math.min((avg7 / 9) * 100, 100);
  const avgColor = avg7 >= 7 ? '#10B981' : avg7 >= 6 ? '#F59E0B' : '#EF4444';

  return (
    <div className="sleep-tracker">
      <h2 className="section-title">Sleep Tracker</h2>

      <div className="sleep-summary">
        <div className="sleep-ring-container">
          <svg className="sleep-ring" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="52" fill="none" stroke="var(--surface2)" strokeWidth="10" />
            <circle cx="60" cy="60" r="52" fill="none" stroke={avgColor} strokeWidth="10"
              strokeDasharray={`${avgPct * 3.27} 327`} strokeLinecap="round"
              transform="rotate(-90 60 60)" style={{ transition: 'stroke-dasharray 0.6s ease' }} />
            <text x="60" y="55" textAnchor="middle" fill="var(--text)" fontSize="22" fontWeight="700">
              {avg7 > 0 ? avg7.toFixed(1) : '—'}
            </text>
            <text x="60" y="72" textAnchor="middle" fill="var(--text2)" fontSize="10">avg hrs</text>
          </svg>
        </div>
        <div className="sleep-summary-stats">
          <div className="sleep-stat">
            <span className="sleep-stat-label">Last Night</span>
            <span className="sleep-stat-value">{last ? `${last.hours}h` : '—'}</span>
            {last && <span className="sleep-stat-quality">{'★'.repeat(last.quality)}{'☆'.repeat(5 - last.quality)}</span>}
          </div>
          <div className="sleep-stat">
            <span className="sleep-stat-label">7-Day Average</span>
            <span className="sleep-stat-value" style={{ color: avgColor }}>{avg7 > 0 ? `${avg7.toFixed(1)}h` : '—'}</span>
          </div>
        </div>
      </div>

      <div className="sleep-form">
        <div className="form-field">
          <label>Hours Slept</label>
          <input type="number" value={hours} onChange={e => setHours(e.target.value)}
            placeholder="7.5" min="0" max="24" step="0.5" />
        </div>
        <div className="form-field sleep-quality-field">
          <label>Sleep Quality</label>
          <div className="quality-stars">
            {QUALITY_STARS.map(s => (
              <button key={s} className={`quality-star ${quality >= s ? 'active' : ''}`}
                onClick={() => setQuality(s)} type="button">
                {quality >= s ? '★' : '☆'}
              </button>
            ))}
          </div>
          <span className="quality-label">{QUALITY_LABELS[quality]}</span>
        </div>
        <button className="btn btn-primary" onClick={handleAdd} disabled={!hours}>
          {todayEntry ? 'Update' : 'Log Sleep'}
        </button>
      </div>

      <div className="sleep-history">
        <h3 className="chart-title">Recent Sleep</h3>
        {recent.length === 0 && <p className="empty-msg">No sleep data yet</p>}
        <div className="history-list">
          {recent.map(e => (
            <div key={e.date} className="history-row">
              <span className="history-date">{e.date}</span>
              <span className="history-value">{e.hours}h</span>
              <span className="sleep-quality-badge">{e.quality}/5 {'★'.repeat(e.quality)}</span>
              <button className="btn-delete" onClick={() => onDelete(e.date)}>✕</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
