import type { UserProfile, AppData } from '../../types';
import { useState } from 'react';
import { exportJSON, exportCSV } from '../../utils/calculations';
import './Profile.css';

const ACCENT_COLORS = ['#4F46E5', '#7C3AED', '#EC4899', '#EF4444', '#F97316', '#EAB308', '#10B981', '#06B6D4', '#3B82F6'];

interface Props {
  profile: UserProfile;
  data: AppData;
  onSave: (p: UserProfile) => void;
  onThemeChange: (theme: 'dark' | 'light' | 'system') => void;
  theme: 'dark' | 'light' | 'system';
}

export default function ProfileSetup({ profile, data, onSave, onThemeChange, theme }: Props) {
  const [step, setStep] = useState(profile.onboarded ? -1 : 1);
  const [name, setName] = useState(profile.name);
  const [height, setHeight] = useState(profile.heightCm || '');
  const [goal, setGoal] = useState(profile.goalWeightKg || '');
  const [calGoal, setCalGoal] = useState(profile.dailyCalorieGoal || 2000);
  const [waterGoal, setWaterGoal] = useState(profile.dailyWaterMl || 2500);
  const [stepsGoal, setStepsGoal] = useState(profile.dailyStepsGoal || 10000);
  const [accent, setAccent] = useState(profile.accentColor);
  const [saved, setSaved] = useState(false);

  function finish() {
    const p: UserProfile = {
      name: name.trim(), heightCm: Number(height), goalWeightKg: Number(goal),
      dailyCalorieGoal: Number(calGoal), dailyWaterMl: Number(waterGoal),
      dailyStepsGoal: Number(stepsGoal), accentColor: accent, onboarded: true,
    };
    onSave(p);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    if (step > 0) setStep(-1);
  }

  function handleExportJSON() {
    const blob = new Blob([exportJSON(data)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `health-tracker-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
  }

  function handleExportCSV() {
    const blob = new Blob([exportCSV(data)], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `health-tracker-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  }

  if (step === 1) return (
    <div className="profile wizard">
      <div className="wizard-progress"><div className="wizard-fill" style={{ width: '25%' }} /></div>
      <h2 className="section-title">Welcome! What's your name?</h2>
      <div className="profile-card">
        <div className="profile-field">
          <label>Your Name</label>
          <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Enter your name" autoFocus />
        </div>
        <button className="btn btn-primary" onClick={() => setStep(2)} disabled={!name.trim()}>Next →</button>
      </div>
    </div>
  );

  if (step === 2) return (
    <div className="profile wizard">
      <div className="wizard-progress"><div className="wizard-fill" style={{ width: '50%' }} /></div>
      <h2 className="section-title">Your Measurements</h2>
      <div className="profile-card">
        <div className="profile-field">
          <label>Height (cm)</label>
          <input type="number" value={height} onChange={e => setHeight(e.target.value)} placeholder="170" min="50" max="300" />
        </div>
        <div className="profile-field">
          <label>Goal Weight (kg)</label>
          <input type="number" value={goal} onChange={e => setGoal(e.target.value)} placeholder="70" min="20" max="500" />
        </div>
        <div className="wizard-nav">
          <button className="btn" onClick={() => setStep(1)}>← Back</button>
          <button className="btn btn-primary" onClick={() => setStep(3)} disabled={!height}>Next →</button>
        </div>
      </div>
    </div>
  );

  if (step === 3) return (
    <div className="profile wizard">
      <div className="wizard-progress"><div className="wizard-fill" style={{ width: '75%' }} /></div>
      <h2 className="section-title">Daily Goals</h2>
      <div className="profile-card">
        <div className="profile-field">
          <label>Calorie Goal (kcal)</label>
          <input type="number" value={calGoal} onChange={e => setCalGoal(Number(e.target.value))} min="500" max="10000" />
        </div>
        <div className="profile-field">
          <label>Water Goal (ml)</label>
          <input type="number" value={waterGoal} onChange={e => setWaterGoal(Number(e.target.value))} min="500" max="10000" step="100" />
        </div>
        <div className="profile-field">
          <label>Steps Goal</label>
          <input type="number" value={stepsGoal} onChange={e => setStepsGoal(Number(e.target.value))} min="1000" max="50000" step="1000" />
        </div>
        <div className="wizard-nav">
          <button className="btn" onClick={() => setStep(2)}>← Back</button>
          <button className="btn btn-primary" onClick={() => setStep(4)}>Next →</button>
        </div>
      </div>
    </div>
  );

  if (step === 4) return (
    <div className="profile wizard">
      <div className="wizard-progress"><div className="wizard-fill" style={{ width: '100%' }} /></div>
      <h2 className="section-title">Pick Your Style</h2>
      <div className="profile-card">
        <div className="profile-field">
          <label>Accent Color</label>
          <div className="color-picker">
            {ACCENT_COLORS.map(c => (
              <button key={c} className={`color-swatch ${accent === c ? 'active' : ''}`}
                style={{ background: c }} onClick={() => setAccent(c)} type="button" />
            ))}
          </div>
        </div>
        <div className="profile-field">
          <label>Theme</label>
          <div className="theme-picker">
            {(['system', 'light', 'dark'] as const).map(t => (
              <button key={t} className={`theme-btn ${theme === t ? 'active' : ''}`}
                onClick={() => onThemeChange(t)} type="button">
                {t === 'system' ? '💻' : t === 'light' ? '☀️' : '🌙'} {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <div className="wizard-nav">
          <button className="btn" onClick={() => setStep(3)}>← Back</button>
          <button className="btn btn-primary" onClick={finish}>Finish Setup ✓</button>
        </div>
      </div>
    </div>
  );

  // Normal profile view (already onboarded)
  return (
    <div className="profile">
      <h2 className="section-title">Profile Settings</h2>
      <div className="profile-avatar-row">
        <div className="profile-avatar" style={{ background: accent }}>{name ? name[0].toUpperCase() : '?'}</div>
        <div className="color-picker small">
          {ACCENT_COLORS.map(c => (
            <button key={c} className={`color-swatch ${accent === c ? 'active' : ''}`}
              style={{ background: c }} onClick={() => { setAccent(c); finish(); }} type="button" />
          ))}
        </div>
      </div>
      <div className="profile-card">
        <div className="profile-field">
          <label>Name</label>
          <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Your name" />
        </div>
        <div className="profile-field">
          <label>Height (cm)</label>
          <input type="number" value={height} onChange={e => setHeight(e.target.value)} placeholder="170" min="50" max="300" />
        </div>
        <div className="profile-field">
          <label>Goal Weight (kg)</label>
          <input type="number" value={goal} onChange={e => setGoal(e.target.value)} placeholder="70" min="20" max="500" />
        </div>
        <div className="profile-field">
          <label>Daily Calorie Goal (kcal)</label>
          <input type="number" value={calGoal} onChange={e => setCalGoal(Number(e.target.value))} placeholder="2000" min="500" max="10000" />
        </div>
        <div className="profile-field">
          <label>Daily Water Goal (ml)</label>
          <input type="number" value={waterGoal} onChange={e => setWaterGoal(Number(e.target.value))} placeholder="2500" min="500" max="10000" step="100" />
        </div>
        <div className="profile-field">
          <label>Daily Steps Goal</label>
          <input type="number" value={stepsGoal} onChange={e => setStepsGoal(Number(e.target.value))} placeholder="10000" min="1000" max="50000" step="1000" />
        </div>
        <div className="profile-field">
          <label>Theme</label>
          <div className="theme-picker">
            {(['system', 'light', 'dark'] as const).map(t => (
              <button key={t} className={`theme-btn ${theme === t ? 'active' : ''}`}
                onClick={() => onThemeChange(t)} type="button">
                {t === 'system' ? '💻' : t === 'light' ? '☀️' : '🌙'} {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <button className="btn btn-primary" onClick={finish}>
          {saved ? '✓ Saved!' : 'Save Profile'}
        </button>
      </div>

      <div className="profile-export">
        <h3 className="chart-title">Export Data</h3>
        <div className="export-btns">
          <button className="btn" onClick={handleExportJSON}>📦 Export JSON</button>
          <button className="btn" onClick={handleExportCSV}>📊 Export CSV</button>
        </div>
      </div>
    </div>
  );
}
