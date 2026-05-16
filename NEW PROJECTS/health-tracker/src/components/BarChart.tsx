import './BarChart.css';

interface Props {
  data: { label: string; value: number }[];
  target?: number;
  unit: string;
  color: string;
  targetColor?: string;
}

export default function BarChart({ data, target, unit, color, targetColor = '#F59E0B' }: Props) {
  if (data.length === 0) {
    return <div className="chart-empty">No data yet</div>;
  }

  const maxVal = Math.max(
    ...data.map(d => d.value),
    target ?? 0,
  ) * 1.15 || 1;

  return (
    <div className="bar-chart">
      <div className="bar-chart-bars">
        {target != null && (
          <div className="bar-target-line" style={{ bottom: `${(target / maxVal) * 100}%` }}>
            <span className="bar-target-label">Goal: {target} {unit}</span>
          </div>
        )}
        {data.map((d, i) => (
          <div key={i} className="bar-col">
            <div className="bar-wrapper">
              <div
                className="bar-fill"
                style={{
                  height: `${(d.value / maxVal) * 100}%`,
                  background: d.value >= (target ?? 0) ? color : `${color}99`,
                  border: target != null && d.value >= target ? `2px solid ${targetColor}` : 'none',
                }}
              >
                <span className="bar-value">{d.value}</span>
              </div>
            </div>
            <span className="bar-label">{d.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
