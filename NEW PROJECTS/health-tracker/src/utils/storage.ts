import type { AppData } from '../types';

const STORAGE_KEY = 'healthTrackerData';

const DEFAULT: AppData = {
  profile: { name: '', heightCm: 0, goalWeightKg: 0, dailyCalorieGoal: 2000, dailyWaterMl: 2500, dailyStepsGoal: 10000, accentColor: '#4F46E5', onboarded: false },
  weightEntries: [], mealEntries: [], waterEntries: [], sleepEntries: [], moodEntries: [], stepsEntries: [],
  theme: 'system',
};

export function loadData(): AppData {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return structuredClone(DEFAULT);
    const p = JSON.parse(raw) as Partial<AppData>;
    return {
      profile: { ...DEFAULT.profile, ...p.profile },
      weightEntries: p.weightEntries ?? [], mealEntries: p.mealEntries ?? [],
      waterEntries: p.waterEntries ?? [], sleepEntries: p.sleepEntries ?? [],
      moodEntries: p.moodEntries ?? [], stepsEntries: p.stepsEntries ?? [],
      theme: p.theme ?? 'system',
    };
  } catch { return structuredClone(DEFAULT); }
}

export function saveData(data: AppData): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}
