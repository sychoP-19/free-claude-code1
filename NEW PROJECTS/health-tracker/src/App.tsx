import { useState, useCallback, useEffect } from 'react';
import type { View, AppData, WeightEntry, MealEntry, WaterEntry, SleepEntry, MoodEntry, StepsEntry } from './types';
import { loadData, saveData } from './utils/storage';
import { generateSuggestions } from './utils/calculations';
import Navbar from './components/Navbar';
import Dashboard from './features/dashboard/Dashboard';
import WeightTracker from './features/tracking/WeightTracker';
import DietTracker from './features/tracking/DietTracker';
import WaterTracker from './features/tracking/WaterTracker';
import SleepTracker from './features/tracking/SleepTracker';
import MoodTracker from './features/tracking/MoodTracker';
import StepsTracker from './features/tracking/StepsTracker';
import ProfileSetup from './features/profile/ProfileSetup';
import Suggestions from './features/suggestions/Suggestions';
import './App.css';

function applyTheme(theme: 'dark' | 'light' | 'system', accent: string) {
  const root = document.documentElement;
  const isDark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  root.setAttribute('data-theme', isDark ? 'dark' : 'light');
  root.style.setProperty('--primary', accent);
  root.style.setProperty('--primary-hover', accent + 'CC');
}

export default function App() {
  const [data, setData] = useState<AppData>(loadData);
  const [view, setView] = useState<View>(!data.profile.onboarded ? 'profile' : 'dashboard');

  useEffect(() => {
    applyTheme(data.theme, data.profile.accentColor);
  }, [data.theme, data.profile.accentColor]);

  const persist = useCallback((next: AppData) => {
    setData(next);
    saveData(next);
  }, []);

  const handleSaveProfile = useCallback((p: typeof data.profile) => {
    persist({ ...data, profile: p });
  }, [data, persist]);

  const handleThemeChange = useCallback((theme: 'dark' | 'light' | 'system') => {
    persist({ ...data, theme });
  }, [data, persist]);

  const handleAddWeight = useCallback((e: WeightEntry) => {
    const next = { ...data, weightEntries: [...data.weightEntries.filter(x => x.date !== e.date), e] };
    persist(next);
  }, [data, persist]);

  const handleDeleteWeight = useCallback((date: string) => {
    persist({ ...data, weightEntries: data.weightEntries.filter(e => e.date !== date) });
  }, [data, persist]);

  const handleAddMeal = useCallback((e: MealEntry) => {
    persist({ ...data, mealEntries: [...data.mealEntries, e] });
  }, [data, persist]);

  const handleDeleteMeal = useCallback((id: string) => {
    persist({ ...data, mealEntries: data.mealEntries.filter(m => m.id !== id) });
  }, [data, persist]);

  const handleAddWater = useCallback((e: WaterEntry) => {
    persist({ ...data, waterEntries: [...data.waterEntries, e] });
  }, [data, persist]);

  const handleDeleteWater = useCallback((timestamp: string) => {
    persist({ ...data, waterEntries: data.waterEntries.filter(w => w.timestamp !== timestamp) });
  }, [data, persist]);

  const handleAddSleep = useCallback((e: SleepEntry) => {
    persist({ ...data, sleepEntries: [...data.sleepEntries.filter(x => x.date !== e.date), e] });
  }, [data, persist]);

  const handleDeleteSleep = useCallback((date: string) => {
    persist({ ...data, sleepEntries: data.sleepEntries.filter(e => e.date !== date) });
  }, [data, persist]);

  const handleAddMood = useCallback((e: MoodEntry) => {
    persist({ ...data, moodEntries: [...data.moodEntries, e] });
  }, [data, persist]);

  const handleDeleteMood = useCallback((timestamp: string) => {
    persist({ ...data, moodEntries: data.moodEntries.filter(e => e.timestamp !== timestamp) });
  }, [data, persist]);

  const handleAddSteps = useCallback((e: StepsEntry) => {
    persist({ ...data, stepsEntries: [...data.stepsEntries.filter(x => x.date !== e.date), e] });
  }, [data, persist]);

  const handleDeleteSteps = useCallback((date: string) => {
    persist({ ...data, stepsEntries: data.stepsEntries.filter(e => e.date !== date) });
  }, [data, persist]);

  const suggestions = generateSuggestions(data.profile, data.weightEntries, data.mealEntries, data.waterEntries, data.sleepEntries, data.moodEntries, data.stepsEntries);

  return (
    <div className="app">
      <main className="main">
        {view === 'dashboard' && <Dashboard data={data} onChangeView={v => setView(v as View)} />}
        {view === 'weight' && <WeightTracker entries={data.weightEntries} onAdd={handleAddWeight} onDelete={handleDeleteWeight} />}
        {view === 'diet' && <DietTracker meals={data.mealEntries} dailyCalorieGoal={data.profile.dailyCalorieGoal} onAdd={handleAddMeal} onDelete={handleDeleteMeal} />}
        {view === 'water' && <WaterTracker entries={data.waterEntries} dailyGoal={data.profile.dailyWaterMl} onAdd={handleAddWater} onDelete={handleDeleteWater} />}
        {view === 'sleep' && <SleepTracker entries={data.sleepEntries} onAdd={handleAddSleep} onDelete={handleDeleteSleep} />}
        {view === 'mood' && <MoodTracker entries={data.moodEntries} onAdd={handleAddMood} onDelete={handleDeleteMood} />}
        {view === 'steps' && <StepsTracker entries={data.stepsEntries} dailyGoal={data.profile.dailyStepsGoal} onAdd={handleAddSteps} onDelete={handleDeleteSteps} />}
        {view === 'suggestions' && <Suggestions suggestions={suggestions} onNavigate={setView} />}
        {view === 'profile' && <ProfileSetup profile={data.profile} data={data} onSave={handleSaveProfile} onThemeChange={handleThemeChange} theme={data.theme} />}
      </main>
      <Navbar current={view} onChange={setView} />
    </div>
  );
}
