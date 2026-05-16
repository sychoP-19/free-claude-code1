import type { UserProfile, WeightEntry, MealEntry, WaterEntry, SleepEntry, MoodEntry, StepsEntry, Suggestion, View } from '../types';

export function calcBMI(w: number, h: number): number { if (h <= 0 || w <= 0) return 0; const m = h / 100; return w / (m * m); }
export function bmiCat(bmi: number): { label: string; color: string } {
  if (bmi === 0) return { label: 'N/A', color: '#64748B' };
  if (bmi < 18.5) return { label: 'Underweight', color: '#F59E0B' };
  if (bmi < 25) return { label: 'Normal', color: '#10B981' };
  if (bmi < 30) return { label: 'Overweight', color: '#F97316' };
  return { label: 'Obese', color: '#EF4444' };
}

export function weightTrend(e: WeightEntry[]): 'losing' | 'gaining' | 'stable' | 'none' {
  if (e.length < 2) return 'none';
  const s = [...e].sort((a, b) => a.date.localeCompare(b.date)).slice(-7);
  const d = s[s.length - 1].weightKg - s[0].weightKg;
  if (d < -0.3) return 'losing'; if (d > 0.3) return 'gaining'; return 'stable';
}

export function dayTotals(meals: MealEntry[], date: string) {
  const d = meals.filter(m => m.date === date);
  return { calories: d.reduce((s, m) => s + m.calories, 0), protein: d.reduce((s, m) => s + m.protein, 0), carbs: d.reduce((s, m) => s + m.carbs, 0), fat: d.reduce((s, m) => s + m.fat, 0), waterMl: d.reduce((s, m) => s + m.waterMl, 0) };
}

export function avgCal(meals: MealEntry[], days: number): number {
  const cut = new Date(); cut.setDate(cut.getDate() - days); const cs = cut.toISOString().slice(0, 10);
  const m = new Map<string, number>(); for (const e of meals) { if (e.date >= cs) m.set(e.date, (m.get(e.date) ?? 0) + e.calories); }
  if (m.size === 0) return 0; return [...m.values()].reduce((s, v) => s + v, 0) / m.size;
}

export function dayWater(w: WaterEntry[], date: string): number { return w.filter(e => e.date === date).reduce((s, e) => s + e.ml, 0); }

export function latestSleep(e: SleepEntry[]): SleepEntry | null {
  return e.length ? [...e].sort((a, b) => b.date.localeCompare(a.date))[0] : null;
}

export function avgSleep(e: SleepEntry[], days: number): number {
  const cut = new Date(); cut.setDate(cut.getDate() - days); const cs = cut.toISOString().slice(0, 10);
  const r = e.filter(x => x.date >= cs);
  return r.length ? r.reduce((s, x) => s + x.hours, 0) / r.length : 0;
}

export function daySteps(e: StepsEntry[], date: string): number {
  return e.filter(x => x.date === date).reduce((s, x) => s + x.steps, 0);
}

export function generateSuggestions(
  profile: UserProfile, weight: WeightEntry[], meals: MealEntry[],
  water: WaterEntry[], sleep: SleepEntry[], mood: MoodEntry[], steps: StepsEntry[],
): Suggestion[] {
  const sug: Suggestion[] = [];
  const today = new Date().toISOString().slice(0, 10);
  const latest = weight.length ? [...weight].sort((a, b) => b.date.localeCompare(a.date))[0] : null;
  const totals = dayTotals(meals, today);
  const todayW = dayWater(water, today) + totals.waterMl;

  if (!profile.onboarded) {
    sug.push({ icon: '📋', title: 'Complete setup', text: 'Finish the onboarding wizard to unlock all features.', type: 'info', category: 'weight', cta: { label: 'Set up now →', view: 'profile' } });
    return sug;
  }
  if (!latest) {
    sug.push({ icon: '⚖️', title: 'Log your first weight', text: 'We need a weight entry to calculate BMI and trends.', type: 'info', category: 'weight', cta: { label: 'Log weight →', view: 'weight' } });
  }

  // BMI
  if (latest && profile.heightCm > 0) {
    const bmi = calcBMI(latest.weightKg, profile.heightCm); const cat = bmiCat(bmi);
    if (bmi < 18.5) sug.push({ icon: '⚠️', title: 'Underweight', text: `BMI ${bmi.toFixed(1)} — increase calories with nutrient-dense foods.`, type: 'warning', category: 'weight' });
    else if (bmi < 25) sug.push({ icon: '✅', title: 'Healthy BMI', text: `BMI ${bmi.toFixed(1)} — great range, keep it up!`, type: 'success', category: 'weight' });
    else if (bmi < 30) sug.push({ icon: '🔶', title: 'Above healthy range', text: `BMI ${bmi.toFixed(1)} — a 300-500 kcal deficit + exercise helps.`, type: 'warning', category: 'nutrition', cta: { label: 'Log diet →', view: 'diet' } });
    else sug.push({ icon: '🔴', title: 'High BMI', text: `BMI ${bmi.toFixed(1)} — consider medical guidance for weight management.`, type: 'danger', category: 'weight' });

    const trend = weightTrend(weight); const gd = latest.weightKg - profile.goalWeightKg;
    if (trend === 'gaining' && gd > 0) sug.push({ icon: '📈', title: 'Weight trending up', text: `${gd.toFixed(1)} kg above goal. Review calories.`, type: 'warning', category: 'weight', cta: { label: 'Log diet →', view: 'diet' } });
    else if (trend === 'losing' && gd > 0) sug.push({ icon: '📉', title: 'Good progress', text: `${gd.toFixed(1)} kg above goal but trending down.`, type: 'success', category: 'weight' });
    else if (trend === 'stable' && Math.abs(gd) < 0.5) sug.push({ icon: '🎯', title: 'At goal weight!', text: 'Within 0.5 kg of target — maintain your routine.', type: 'success', category: 'weight' });
  }

  // Calories
  const ac = avgCal(meals, 7);
  if (ac > 0) {
    const d = ac - profile.dailyCalorieGoal;
    if (d > 300) sug.push({ icon: '🍔', title: 'Over calorie target', text: `7d avg ${Math.round(ac)} kcal — ${Math.round(d)} over. Cut snacks or portions.`, type: 'warning', category: 'nutrition', cta: { label: 'Log diet →', view: 'diet' } });
    else if (d < -300) sug.push({ icon: '🥗', title: 'Under calorie target', text: `7d avg ${Math.round(ac)} kcal — ${Math.round(Math.abs(d))} under. Eat enough.`, type: 'info', category: 'nutrition', cta: { label: 'Log diet →', view: 'diet' } });
    else sug.push({ icon: '🍽️', title: 'On track with calories', text: `7d avg ${Math.round(ac)} kcal — close to target.`, type: 'success', category: 'nutrition' });
  } else if (meals.length === 0) {
    sug.push({ icon: '📝', title: 'Start logging meals', text: 'Track what you eat for accountability.', type: 'info', category: 'nutrition', cta: { label: 'Log diet →', view: 'diet' } });
  }

  // Protein
  if (latest && meals.length > 0) {
    const ps = meals.filter(m => m.date >= new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10));
    const ap = ps.length ? ps.reduce((s, m) => s + m.protein, 0) / new Set(ps.map(m => m.date)).size : 0;
    const rec = latest.weightKg * 1.6;
    if (ap > 0 && ap < rec * 0.7) sug.push({ icon: '💪', title: 'Low protein', text: `Avg ${ap.toFixed(0)}g/day — aim for ~${rec.toFixed(0)}g.`, type: 'warning', category: 'nutrition', cta: { label: 'Log diet →', view: 'diet' } });
  }

  // Hydration
  const wp = profile.dailyWaterMl > 0 ? (todayW / profile.dailyWaterMl) * 100 : 0;
  if (wp < 50 && profile.dailyWaterMl > 0) sug.push({ icon: '💧', title: 'Drink more water', text: `${todayW}ml today — only ${Math.round(wp)}% of goal.`, type: 'warning', category: 'hydration', cta: { label: 'Log water →', view: 'water' } });
  else if (wp >= 100) sug.push({ icon: '💧', title: 'Hydration goal reached!', text: `${todayW}ml — great hydration!`, type: 'success', category: 'hydration' });

  // Sleep
  const ls = latestSleep(sleep);
  const as = avgSleep(sleep, 7);
  if (as > 0 && as < 6) sug.push({ icon: '😴', title: 'Low sleep average', text: `7d avg ${as.toFixed(1)}h — aim for 7-9h. Poor sleep hurts recovery and appetite.`, type: 'warning', category: 'sleep', cta: { label: 'Log sleep →', view: 'sleep' } });
  else if (as >= 7) sug.push({ icon: '🛌', title: 'Good sleep pattern', text: `7d avg ${as.toFixed(1)}h — solid rest!`, type: 'success', category: 'sleep' });
  else if (sleep.length === 0) sug.push({ icon: '🛌', title: 'Track your sleep', text: 'Log sleep to see how it affects your weight and energy.', type: 'info', category: 'sleep', cta: { label: 'Log sleep →', view: 'sleep' } });

  if (ls && ls.quality <= 2) sug.push({ icon: '😰', title: 'Poor sleep quality', text: `Last night rated ${ls.quality}/5. Consider reducing screen time and caffeine before bed.`, type: 'warning', category: 'sleep' });

  // Steps
  const ts = daySteps(steps, today);
  if (ts === 0 && steps.length === 0) sug.push({ icon: '🚶', title: 'Start tracking steps', text: 'Even a short walk boosts mood and burns calories.', type: 'info', category: 'activity', cta: { label: 'Log steps →', view: 'steps' } });
  else if (ts > 0 && ts < profile.dailyStepsGoal * 0.5) sug.push({ icon: '🚶', title: 'Get moving!', text: `${ts.toLocaleString()} steps today — try a 15-min walk to reach ${profile.dailyStepsGoal.toLocaleString()}.`, type: 'info', category: 'activity', cta: { label: 'Log steps →', view: 'steps' } });
  else if (ts >= profile.dailyStepsGoal) sug.push({ icon: '🏃', title: 'Step goal reached!', text: `${ts.toLocaleString()} steps today — excellent!`, type: 'success', category: 'activity' });

  // Mood correlation
  if (mood.length >= 3) {
    const recent = [...mood].sort((a, b) => b.timestamp.localeCompare(a.timestamp)).slice(0, 3);
    const lowMood = recent.filter(m => m.mood === '😴' || m.mood === '😐').length;
    if (lowMood >= 2 && wp < 70) sug.push({ icon: '🧠', title: 'Mood & hydration link', text: 'Low mood days may link to dehydration. Try drinking more water when energy dips.', type: 'info', category: 'hydration', cta: { label: 'Log water →', view: 'water' } });
  }

  return sug;
}

export function exportJSON(data: unknown): string { return JSON.stringify(data, null, 2); }

export function exportCSV(data: { weightEntries: WeightEntry[]; mealEntries: MealEntry[]; waterEntries: WaterEntry[]; sleepEntries: SleepEntry[]; moodEntries: MoodEntry[]; stepsEntries: StepsEntry[] }): string {
  const sections = [
    { name: 'Weight', rows: data.weightEntries.map(e => ({ date: e.date, value: e.weightKg, unit: 'kg' })) },
    { name: 'Meals', rows: data.mealEntries.map(e => ({ date: e.date, value: e.calories, unit: 'kcal', detail: e.foodName })) },
    { name: 'Water', rows: data.waterEntries.map(e => ({ date: e.date, value: e.ml, unit: 'ml' })) },
    { name: 'Sleep', rows: data.sleepEntries.map(e => ({ date: e.date, value: e.hours, unit: 'hours', detail: `quality:${e.quality}` })) },
    { name: 'Mood', rows: data.moodEntries.map(e => ({ date: e.date, value: e.energy, unit: 'energy', detail: e.mood })) },
    { name: 'Steps', rows: data.stepsEntries.map(e => ({ date: e.date, value: e.steps, unit: 'steps' })) },
  ];
  let csv = 'Section,Date,Value,Unit,Detail\n';
  for (const s of sections) for (const r of s.rows) csv += `${s.name},${r.date},${r.value},${r.unit},${r.detail ?? ''}\n`;
  return csv;
}
