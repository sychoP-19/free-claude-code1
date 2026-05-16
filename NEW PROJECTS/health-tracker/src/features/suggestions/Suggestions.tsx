import type { Suggestion, View } from '../../types';
import './Suggestions.css';

interface Props {
  suggestions: Suggestion[];
  onNavigate: (v: View) => void;
}

const CATEGORY_META: Record<string, { icon: string; label: string; color: string }> = {
  hydration: { icon: '💧', label: 'Hydration', color: '#3B82F6' },
  nutrition: { icon: '🥗', label: 'Nutrition', color: '#10B981' },
  weight: { icon: '⚖️', label: 'Weight', color: '#F59E0B' },
  sleep: { icon: '😴', label: 'Sleep', color: '#6366F1' },
  activity: { icon: '🚶', label: 'Activity', color: '#F97316' },
};

const TYPE_BG: Record<Suggestion['type'], string> = {
  info: 'rgba(59,130,246,0.06)',
  success: 'rgba(16,185,129,0.06)',
  warning: 'rgba(245,158,11,0.06)',
  danger: 'rgba(239,68,68,0.08)',
};

export default function Suggestions({ suggestions, onNavigate }: Props) {
  const grouped = suggestions.reduce<Record<string, Suggestion[]>>((acc, s) => {
    const key = s.category;
    if (!acc[key]) acc[key] = [];
    acc[key].push(s);
    return acc;
  }, {});

  return (
    <div className="suggestions">
      <h2 className="section-title">Personalized Tips</h2>
      {suggestions.length === 0 && (
        <p className="empty-msg">Log some data to get personalized advice.</p>
      )}
      {Object.entries(grouped).map(([cat, items]) => {
        const meta = CATEGORY_META[cat] ?? { icon: '📌', label: cat, color: '#94A3B8' };
        return (
          <div key={cat} className="suggestion-group">
            <div className="suggestion-group-header">
              <span className="suggestion-group-icon">{meta.icon}</span>
              <span className="suggestion-group-label" style={{ color: meta.color }}>{meta.label}</span>
            </div>
            {items.map((s, i) => (
              <div key={i} className="suggestion-card"
                style={{ borderLeftColor: meta.color, background: TYPE_BG[s.type] }}>
                <div className="suggestion-icon">{s.icon}</div>
                <div className="suggestion-body">
                  <h4 className="suggestion-title">{s.title}</h4>
                  <p className="suggestion-text">{s.text}</p>
                  {s.cta && (
                    <button className="suggestion-cta" onClick={() => onNavigate(s.cta!.view)}
                      style={{ color: meta.color }}>
                      {s.cta.label}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
