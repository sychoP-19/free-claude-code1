export interface UserProfile {
  name: string;
  heightCm: number;
  goalWeightKg: number;
  dailyCalorieGoal: number;
  dailyWaterMl: number;
  dailyStepsGoal: number;
  accentColor: string;
  onboarded: boolean;
}

export interface WeightEntry { date: string; weightKg: number; }
export interface MealEntry {
  id: string; date: string; mealType: 'breakfast' | 'lunch' | 'dinner' | 'snack';
  foodId: string; foodName: string; servings: number; calories: number;
  protein: number; carbs: number; fat: number; waterMl: number;
}
export interface WaterEntry { date: string; ml: number; timestamp: string; }
export interface SleepEntry { date: string; hours: number; quality: 1 | 2 | 3 | 4 | 5; }
export interface MoodEntry { date: string; mood: '😴' | '😐' | '😊' | '⚡'; energy: 1 | 2 | 3 | 4 | 5; timestamp: string; }
export interface StepsEntry { date: string; steps: number; }

export interface AppData {
  profile: UserProfile;
  weightEntries: WeightEntry[];
  mealEntries: MealEntry[];
  waterEntries: WaterEntry[];
  sleepEntries: SleepEntry[];
  moodEntries: MoodEntry[];
  stepsEntries: StepsEntry[];
  theme: 'dark' | 'light' | 'system';
}

export type SuggestionCategory = 'hydration' | 'nutrition' | 'weight' | 'sleep' | 'activity';

export interface Suggestion {
  icon: string; title: string; text: string;
  type: 'info' | 'warning' | 'success' | 'danger';
  category: SuggestionCategory;
  cta?: { label: string; view: View };
}

export type View = 'dashboard' | 'weight' | 'diet' | 'water' | 'sleep' | 'mood' | 'steps' | 'suggestions' | 'profile';
