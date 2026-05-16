import type { CalorieEntry } from '../../types';
import { useState } from 'react';
import BarChart from '../../components/BarChart';
import './CalorieTracker.css';

interface Props {
  entries: CalorieEntry[];
  dailyGoal: number;
  onAdd: (e: CalorieEntry) => void;
  onDelete: (date: string, idx: number) => void;
}

export default function CalorieTracker({ entries, dailyGoal, onAdd, onDelete }: Props) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [calories, setCalories] = useState('');
  const [note, setNote] = useState('');

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!date || !calories || Number(calories) <= 0) return;
    onAdd({ date, calories: Number(calories), note: note.trim() || undefined });
    setCalories('');
    setNote('');
  }

  // Aggregate by date for chart
  const byDate = new Map<string, number>();
  for (const e of entries) {
    byDate.set(e.date, (byDate.get(e.date) ?? 0) + e.calories);
  }
  const dailyList = [...byDate.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-14)
    .map(([d, v]) => ({ label: d.slice(5), value: v }));

  const today = new Date().toISOString().slice(0, 10);
  const todayTotal = entries.filter(e => e.date === today).reduce((s, e) => s + e.calories, 0);
  const remaining = dailyGoal - todayTotal;

  return (
    <div className="tracker">
      <h2 className="section-title">Calorie Tracking</h2>

      <div className="cal-today-bar">
        <div className="cal-today-info">
          <span>Today: <strong>{todayTotal}</strong> / {dailyGoal} kcal</span>
          <span className={remaining < 0 ? 'cal-over' : 'cal-left'}>
            {remaining >= 0 ? `${remaining} remaining` : `${Math.abs(remaining)} over`}
          </span>
        </div>
        <div className="cal-progress-track">
          <div
            className="cal-progress-fill"
            style={{
              width: `${Math.min((todayTotal / dailyGoal) * 100, 100)}%`,
              background: todayTotal > dailyGoal ? '#EF4444' : '#4F46E5',
            }}
          />
        </div>
      </div>

      <form className="tracker-form" onSubmit={handleSubmit}>
        <div className="form-field">
          <label>Date</label>
          <input type="date" value={date} onChange={e => setDate(e.target.value)} />
        </div>
        <div className="form-field">
          <label>Calories (kcal)</label>
          <input type="number" min="1" max="10000" value={calories}
            onChange={e => setCalories(e.target.value)} placeholder="500" />
        </div>
        <div className="form-field">
          <label>Note (optional)</label>
          <input type="text" value={note} onChange={e => setNote(e.target.value)} placeholder="Lunch, snack..." />
        </div>
        <button className="btn btn-primary" type="submit">Log Calories</button>
      </form>

      <div className="tracker-chart">
        <h3 className="chart-title">Daily totals (last 14 days)</h3>
        <BarChart data={dailyList} target={dailyGoal} unit="kcal" color="#10B981" targetColor="#F59E0B" />
      </div>

      <div className="tracker-history">
        <h3 className="chart-title">Today's entries</h3>
        {entries.filter(e => e.date === today).length === 0 && <p className="empty-msg">No entries for today</p>}
        <div className="history-list">
          {entries
            .filter(e => e.date === today)
            .map((e, i) => (
              <div key={i} className="history-row">
                <span className="history-value">{e.calories} kcal</span>
                <span className="history-note">{e.note || '—'}</span>
                <button className="btn-delete" onClick={() => onDelete(e.date, i)} title="Delete">✕</button>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
