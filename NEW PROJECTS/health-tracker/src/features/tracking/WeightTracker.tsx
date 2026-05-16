import type { WeightEntry } from '../../types';
import { useState } from 'react';
import BarChart from '../../components/BarChart';
import './WeightTracker.css';

interface Props {
  entries: WeightEntry[];
  onAdd: (e: WeightEntry) => void;
  onDelete: (date: string) => void;
}

export default function WeightTracker({ entries, onAdd, onDelete }: Props) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [weight, setWeight] = useState('');

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!date || !weight || Number(weight) <= 0) return;
    onAdd({ date, weightKg: Number(weight) });
    setWeight('');
  }

  const sorted = [...entries].sort((a, b) => a.date.localeCompare(b.date));
  const chartData = sorted.slice(-14).map(e => ({
    label: e.date.slice(5),
    value: e.weightKg,
  }));

  return (
    <div className="tracker">
      <h2 className="section-title">Weight Tracking</h2>

      <form className="tracker-form" onSubmit={handleSubmit}>
        <div className="form-field">
          <label>Date</label>
          <input type="date" value={date} onChange={e => setDate(e.target.value)} />
        </div>
        <div className="form-field">
          <label>Weight (kg)</label>
          <input type="number" step="0.1" min="20" max="500" value={weight}
            onChange={e => setWeight(e.target.value)} placeholder="70.0" />
        </div>
        <button className="btn btn-primary" type="submit">Log Weight</button>
      </form>

      <div className="tracker-chart">
        <h3 className="chart-title">Last 14 entries</h3>
        <BarChart data={chartData} unit="kg" color="#4F46E5" />
      </div>

      <div className="tracker-history">
        <h3 className="chart-title">History</h3>
        {sorted.length === 0 && <p className="empty-msg">No weight entries yet</p>}
        <div className="history-list">
          {[...sorted].reverse().map(e => (
            <div key={e.date} className="history-row">
              <span className="history-date">{e.date}</span>
              <span className="history-value">{e.weightKg.toFixed(1)} kg</span>
              <button className="btn-delete" onClick={() => onDelete(e.date)} title="Delete">✕</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
