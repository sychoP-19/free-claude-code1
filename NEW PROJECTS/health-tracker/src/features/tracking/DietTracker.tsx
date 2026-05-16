import type { MealEntry } from '../../types';
import type { FoodItem } from '../../food_db';
import { useState, useMemo } from 'react';
import { FOOD_DB, searchFood } from '../../food_db';
import { dayTotals } from '../../utils/calculations';
import BarChart from '../../components/BarChart';
import './DietTracker.css';

const MEAL_TYPES: { id: MealEntry['mealType']; label: string; icon: string }[] = [
  { id: 'breakfast', label: 'Breakfast', icon: '🌅' },
  { id: 'lunch', label: 'Lunch', icon: '☀️' },
  { id: 'dinner', label: 'Dinner', icon: '🌙' },
  { id: 'snack', label: 'Snack', icon: '🍎' },
];

interface Props {
  meals: MealEntry[];
  dailyCalorieGoal: number;
  onAdd: (e: MealEntry) => void;
  onDelete: (id: string) => void;
}

export default function DietTracker({ meals, dailyCalorieGoal, onAdd, onDelete }: Props) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [mealType, setMealType] = useState<MealEntry['mealType']>('breakfast');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<FoodItem | null>(null);
  const [servings, setServings] = useState('1');
  const [mode, setMode] = useState<'search' | 'custom'>('search');

  // Custom food form
  const [cName, setCName] = useState('');
  const [cCal, setCCal] = useState('');
  const [cProt, setCProt] = useState('');
  const [cCarb, setCCarb] = useState('');
  const [cFat, setCFat] = useState('');

  const filtered = useMemo(() => searchFood(search), [search]);
  const todayMeals = meals.filter(m => m.date === date);
  const totals = dayTotals(meals, date);

  // Chart: last 14 days
  const byDate = new Map<string, number>();
  for (const m of meals) {
    byDate.set(m.date, (byDate.get(m.date) ?? 0) + m.calories);
  }
  const chartData = [...byDate.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-14)
    .map(([d, v]) => ({ label: d.slice(5), value: v }));

  function handleAddFood() {
    if (!selected) return;
    const s = Number(servings) || 1;
    onAdd({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      date,
      mealType,
      foodId: selected.id,
      foodName: selected.name,
      servings: s,
      calories: Math.round(selected.calories * s),
      protein: Math.round(selected.protein * s * 10) / 10,
      carbs: Math.round(selected.carbs * s * 10) / 10,
      fat: Math.round(selected.fat * s * 10) / 10,
      waterMl: Math.round(selected.waterMl * s),
    });
    setSelected(null);
    setServings('1');
    setSearch('');
  }

  function handleAddCustom() {
    if (!cName.trim() || !cCal) return;
    onAdd({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      date,
      mealType,
      foodId: 'custom',
      foodName: cName.trim(),
      servings: 1,
      calories: Number(cCal),
      protein: Number(cProt) || 0,
      carbs: Number(cCarb) || 0,
      fat: Number(cFat) || 0,
      waterMl: 0,
    });
    setCName(''); setCCal(''); setCProt(''); setCCarb(''); setCFat('');
  }

  return (
    <div className="diet-tracker">
      <h2 className="section-title">Diet & Meal Tracker</h2>

      {/* Today's macro summary */}
      <div className="macro-bar">
        <div className="macro-item">
          <span className="macro-val">{totals.calories}</span>
          <span className="macro-label">kcal</span>
          <span className="macro-goal">/ {dailyCalorieGoal}</span>
        </div>
        <div className="macro-item prot">
          <span className="macro-val">{totals.protein.toFixed(0)}g</span>
          <span className="macro-label">Protein</span>
        </div>
        <div className="macro-item carb">
          <span className="macro-val">{totals.carbs.toFixed(0)}g</span>
          <span className="macro-label">Carbs</span>
        </div>
        <div className="macro-item fat">
          <span className="macro-val">{totals.fat.toFixed(0)}g</span>
          <span className="macro-label">Fat</span>
        </div>
      </div>

      {/* Macro ring */}
      <div className="macro-ring-container">
        <div className="macro-ring">
          <svg viewBox="0 0 36 36">
            <circle className="ring-bg" cx="18" cy="18" r="15.9" />
            <circle className="ring-prot" cx="18" cy="18" r="15.9"
              strokeDasharray={`${Math.min((totals.protein * 4 / (totals.calories || 1)) * 100, 100)} 100`} />
            <circle className="ring-carb" cx="18" cy="18" r="15.9"
              strokeDasharray={`${Math.min((totals.carbs * 4 / (totals.calories || 1)) * 100, 100)} 100`}
              strokeDashoffset={`-${Math.min((totals.protein * 4 / (totals.calories || 1)) * 100, 100)}`} />
            <circle className="ring-fat" cx="18" cy="18" r="15.9"
              strokeDasharray={`${Math.min((totals.fat * 9 / (totals.calories || 1)) * 100, 100)} 100`}
              strokeDashoffset={`-${Math.min(((totals.protein * 4 + totals.carbs * 4) / (totals.calories || 1)) * 100, 100)}`} />
          </svg>
          <div className="macro-ring-center">
            <span className="ring-pct">{dailyCalorieGoal > 0 ? Math.round((totals.calories / dailyCalorieGoal) * 100) : 0}%</span>
            <span className="ring-sub">of goal</span>
          </div>
        </div>
        <div className="macro-ring-legend">
          <span className="legend-item"><span className="legend-dot prot"></span>Protein</span>
          <span className="legend-item"><span className="legend-dot carb"></span>Carbs</span>
          <span className="legend-item"><span className="legend-dot fat"></span>Fat</span>
        </div>
      </div>

      {/* Add food form */}
      <div className="add-food-section">
        <div className="add-food-header">
          <div className="form-field">
            <label>Date</label>
            <input type="date" value={date} onChange={e => setDate(e.target.value)} />
          </div>
          <div className="form-field">
            <label>Meal</label>
            <div className="meal-type-btns">
              {MEAL_TYPES.map(mt => (
                <button key={mt.id}
                  className={`meal-type-btn ${mealType === mt.id ? 'active' : ''}`}
                  onClick={() => setMealType(mt.id)}>
                  {mt.icon} {mt.label}
                </button>
              ))}
            </div>
          </div>
          <div className="mode-toggle">
            <button className={`mode-btn ${mode === 'search' ? 'active' : ''}`} onClick={() => setMode('search')}>Food DB</button>
            <button className={`mode-btn ${mode === 'custom' ? 'active' : ''}`} onClick={() => setMode('custom')}>Custom</button>
          </div>
        </div>

        {mode === 'search' ? (
          <div className="food-search">
            <input type="text" value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search food or drink..." className="food-search-input" />
            {search && !selected && (
              <div className="food-results">
                {filtered.slice(0, 12).map(f => (
                  <button key={f.id} className="food-result-btn" onClick={() => setSelected(f)}>
                    <span className="food-result-name">{f.name}</span>
                    <span className="food-result-meta">{f.calories} kcal · {f.servingSize}</span>
                  </button>
                ))}
              </div>
            )}
            {selected && (
              <div className="food-selected">
                <div className="food-selected-info">
                  <strong>{selected.name}</strong>
                  <span>{selected.calories} kcal · P:{selected.protein}g C:{selected.carbs}g F:{selected.fat}g</span>
                </div>
                <div className="food-servings">
                  <label>Servings</label>
                  <input type="number" min="0.25" step="0.25" value={servings}
                    onChange={e => setServings(e.target.value)} />
                  <span className="serving-size">{selected.servingSize}</span>
                </div>
                <div className="food-selected-actions">
                  <button className="btn btn-primary" onClick={handleAddFood}>Add to {mealType}</button>
                  <button className="btn btn-ghost" onClick={() => { setSelected(null); setSearch(''); }}>Cancel</button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="custom-food-form">
            <div className="form-field"><label>Name</label><input type="text" value={cName} onChange={e => setCName(e.target.value)} placeholder="Homemade soup" /></div>
            <div className="custom-row">
              <div className="form-field"><label>Calories</label><input type="number" value={cCal} onChange={e => setCCal(e.target.value)} placeholder="0" /></div>
              <div className="form-field"><label>Protein (g)</label><input type="number" value={cProt} onChange={e => setCProt(e.target.value)} placeholder="0" /></div>
              <div className="form-field"><label>Carbs (g)</label><input type="number" value={cCarb} onChange={e => setCCarb(e.target.value)} placeholder="0" /></div>
              <div className="form-field"><label>Fat (g)</label><input type="number" value={cFat} onChange={e => setCFat(e.target.value)} placeholder="0" /></div>
            </div>
            <button className="btn btn-primary" onClick={handleAddCustom}>Add to {mealType}</button>
          </div>
        )}
      </div>

      {/* Today's meals organized by meal type */}
      <div className="meals-by-type">
        {MEAL_TYPES.map(mt => {
          const items = todayMeals.filter(m => m.mealType === mt.id);
          if (items.length === 0) return null;
          const subCal = items.reduce((s, m) => s + m.calories, 0);
          return (
            <div key={mt.id} className="meal-type-group">
              <div className="meal-type-header">
                <span>{mt.icon} {mt.label}</span>
                <span className="meal-type-cal">{subCal} kcal</span>
              </div>
              {items.map(m => (
                <div key={m.id} className="meal-entry">
                  <div className="meal-entry-info">
                    <span className="meal-entry-name">{m.foodName}</span>
                    <span className="meal-entry-meta">
                      {m.servings > 1 ? `${m.servings}x ` : ''}{m.calories} kcal
                    </span>
                    <span className="meal-entry-macros">
                      P:{m.protein.toFixed(0)}g · C:{m.carbs.toFixed(0)}g · F:{m.fat.toFixed(0)}g
                    </span>
                  </div>
                  <button className="btn-delete" onClick={() => onDelete(m.id)}>✕</button>
                </div>
              ))}
            </div>
          );
        })}
      </div>

      {/* Chart */}
      <div className="tracker-chart" style={{ marginTop: 20 }}>
        <h3 className="chart-title">Daily calories (last 14 days)</h3>
        <BarChart data={chartData} target={dailyCalorieGoal} unit="kcal" color="#10B981" targetColor="#F59E0B" />
      </div>
    </div>
  );
}
