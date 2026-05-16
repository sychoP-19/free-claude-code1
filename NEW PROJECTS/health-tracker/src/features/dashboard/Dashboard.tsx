import type { AppData } from '../../types';
import { calcBMI, bmiCat, weightTrend, dayTotals, dayWater, latestSleep, avgSleep, daySteps, avgCal } from '../../utils/calculations';
import './Dashboard.css';

interface Props { data: AppData; onChangeView: (v: string) => void; }

export default function Dashboard({ data, onChangeView }: Props) {
  const { profile, weightEntries, mealEntries, waterEntries, sleepEntries, moodEntries, stepsEntries } = data;
  const today = new Date().toISOString().slice(0, 10);

  const sorted = [...weightEntries].sort((a, b) => b.date.localeCompare(a.date));
  const latest = sorted[0] ?? null;
  const totals = dayTotals(mealEntries, today);
  const todayWater = dayWater(waterEntries, today) + totals.waterMl;
  const todaySteps = daySteps(stepsEntries, today);

  const bmi = latest && profile.heightCm > 0 ? calcBMI(latest.weightKg, profile.heightCm) : 0;
  const cat = bmiCat(bmi);
  const trend = weightTrend(weightEntries);
  const trendIcon = trend === 'losing' ? '📉' : trend === 'gaining' ? '📈' : trend === 'stable' ? '➡️' : '❓';
  const trendLabel = trend === 'losing' ? 'Losing' : trend === 'gaining' ? 'Gaining' : trend === 'stable' ? 'Stable' : 'No data';

  const calPct = profile.dailyCalorieGoal > 0 ? Math.round((totals.calories / profile.dailyCalorieGoal) * 100) : 0;
  const waterPct = profile.dailyWaterMl > 0 ? Math.min(Math.round((todayWater / profile.dailyWaterMl) * 100), 100) : 0;
  const stepsPct = profile.dailyStepsGoal > 0 ? Math.min(Math.round((todaySteps / profile.dailyStepsGoal) * 100), 100) : 0;

  const lastSleep = latestSleep(sleepEntries);
  const avg7Sleep = avgSleep(sleepEntries, 7);
  const avg7Cal = avgCal(mealEntries, 7);
  const recentMood = [...moodEntries].sort((a, b) => b.timestamp.localeCompare(a.timestamp))[0];

  const circ = 2 * Math.PI * 52;

  function ringSvg(pct: number, color: string, value: string, sub: string) {
    const dash = `${(pct / 100) * circ} ${circ}`;
    return (
      <svg className="dash-ring" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="52" fill="none" stroke="var(--surface2)" strokeWidth="10" />
        <circle cx="60" cy="60" r="52" fill="none" stroke={color} strokeWidth="10"
          strokeDasharray={dash} strokeLinecap="round" transform="rotate(-90 60 60)"
          style={{ transition: 'stroke-dasharray 0.6s ease' }} />
        <text x="60" y="56" textAnchor="middle" fill="var(--text)" fontSize="18" fontWeight="700">{value}</text>
        <text x="60" y="72" textAnchor="middle" fill="var(--text2)" fontSize="9">{sub}</text>
      </svg>
    );
  }

  return (
    <div className="dashboard">
      <div className="dash-header">
        <div className="dash-header-left">
          <div className="dash-avatar" style={{ background: profile.accentColor }}>
            {profile.name ? profile.name[0].toUpperCase() : '?'}
          </div>
          <div>
            <h2 className="dash-greeting-main">{profile.name ? `Hello, ${profile.name}` : 'Welcome'}</h2>
            <span className="dash-greeting-sub">{profile.onboarded ? "Here's your overview" : 'Complete setup to unlock features'}</span>
          </div>
        </div>
      </div>

      {/* BMI Gauge */}
      {bmi > 0 && (
        <div className="dash-bmi-card">
          <div className="dash-bmi-gauge">
            <div className="dash-bmi-bar">
              <div className="dash-bmi-fill" style={{ width: `${Math.min((bmi / 40) * 100, 100)}%`, background: cat.color }} />
            </div>
            <div className="dash-bmi-marker" style={{ left: `${Math.min((bmi / 40) * 100, 100)}%` }}>
              <span className="dash-bmi-val">{bmi.toFixed(1)}</span>
            </div>
          </div>
          <div className="dash-bmi-labels">
            <span style={{ color: '#F59E0B' }}>Under</span>
            <span style={{ color: '#10B981' }}>Normal</span>
            <span style={{ color: '#F97316' }}>Over</span>
            <span style={{ color: '#EF4444' }}>Obese</span>
          </div>
          <span className="dash-bmi-cat" style={{ color: cat.color }}>{cat.label}</span>
        </div>
      )}

      {/* Ring Row */}
      <div className="dash-rings">
        <div className="dash-ring-card" onClick={() => onChangeView('diet')}>
          {ringSvg(Math.min(calPct, 100), calPct >= 100 ? '#10B981' : '#3B82F6', `${totals.calories}`, `${calPct}% cal`)}
          <span className="dash-ring-label">Calories</span>
        </div>
        <div className="dash-ring-card" onClick={() => onChangeView('water')}>
          {ringSvg(waterPct, waterPct >= 100 ? '#10B981' : '#3B82F6', `${waterPct}%`, 'hydration')}
          <span className="dash-ring-label">Water</span>
        </div>
        <div className="dash-ring-card" onClick={() => onChangeView('steps')}>
          {ringSvg(stepsPct, stepsPct >= 100 ? '#10B981' : '#F59E0B', `${(todaySteps / 1000).toFixed(1)}k`, `${stepsPct}% goal`)}
          <span className="dash-ring-label">Steps</span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="dash-grid">
        <div className="stat-card">
          <span className="stat-icon">⚖️</span>
          <div className="stat-content">
            <span className="stat-value">{latest ? `${latest.weightKg.toFixed(1)} kg` : '—'}</span>
            <span className="stat-label">Current Weight</span>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-icon">{trendIcon}</span>
          <div className="stat-content">
            <span className="stat-value">{trendLabel}</span>
            <span className="stat-label">Weight Trend</span>
          </div>
        </div>
        <div className="stat-card" onClick={() => onChangeView('sleep')}>
          <span className="stat-icon">🛌</span>
          <div className="stat-content">
            <span className="stat-value">{lastSleep ? `${lastSleep.hours}h` : '—'}</span>
            <span className="stat-label">Last Sleep {lastSleep ? `(${lastSleep.quality}/5)` : ''}</span>
          </div>
        </div>
        <div className="stat-card" onClick={() => onChangeView('mood')}>
          <span className="stat-icon">{recentMood ? recentMood.mood : '😶'}</span>
          <div className="stat-content">
            <span className="stat-value">{recentMood ? `${recentMood.energy}/5` : '—'}</span>
            <span className="stat-label">Energy Level</span>
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-icon">🎯</span>
          <div className="stat-content">
            <span className="stat-value">{profile.goalWeightKg > 0 ? `${profile.goalWeightKg} kg` : '—'}</span>
            <span className="stat-label">Goal Weight</span>
            {latest && profile.goalWeightKg > 0 && (
              <span className="stat-sub">{(latest.weightKg - profile.goalWeightKg).toFixed(1)} kg to go</span>
            )}
          </div>
        </div>
        <div className="stat-card">
          <span className="stat-icon">📊</span>
          <div className="stat-content">
            <span className="stat-value">{avg7Cal > 0 ? Math.round(avg7Cal) : '—'}</span>
            <span className="stat-label">7d Avg Calories</span>
          </div>
        </div>
      </div>

      {/* Macros */}
      {totals.calories > 0 && (
        <div className="dash-macros">
          <h3 className="chart-title" style={{ marginBottom: 10 }}>Today's Macros</h3>
          <div className="dash-macro-bar">
            <span className="dash-macro prot" style={{ flex: totals.protein * 4 || 1 }}>Protein {totals.protein.toFixed(0)}g</span>
            <span className="dash-macro carb" style={{ flex: totals.carbs * 4 || 1 }}>Carbs {totals.carbs.toFixed(0)}g</span>
            <span className="dash-macro fat" style={{ flex: totals.fat * 9 || 1 }}>Fat {totals.fat.toFixed(0)}g</span>
          </div>
        </div>
      )}

      {avg7Sleep > 0 && (
        <div className="dash-sleep-summary" onClick={() => onChangeView('sleep')}>
          <span>🛌 7d sleep avg: <strong>{avg7Sleep.toFixed(1)}h</strong></span>
        </div>
      )}

      {!profile.onboarded && (
        <div className="dash-notice" onClick={() => onChangeView('profile')}>
          <span>👤</span>
          <span>Complete your profile setup to unlock BMI, suggestions, and trend tracking.</span>
        </div>
      )}
    </div>
  );
}
