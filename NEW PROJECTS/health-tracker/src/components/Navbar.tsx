import type { View } from '../types';
import './Navbar.css';

const NAV_ITEMS: { id: View; icon: string; label: string }[] = [
  { id: 'dashboard', icon: '📊', label: 'Home' },
  { id: 'weight', icon: '⚖️', label: 'Weight' },
  { id: 'diet', icon: '🍽️', label: 'Diet' },
  { id: 'water', icon: '💧', label: 'Water' },
  { id: 'sleep', icon: '🛌', label: 'Sleep' },
  { id: 'mood', icon: '😊', label: 'Mood' },
  { id: 'steps', icon: '🚶', label: 'Steps' },
  { id: 'suggestions', icon: '💡', label: 'Tips' },
  { id: 'profile', icon: '👤', label: 'Profile' },
];

interface Props {
  current: View;
  onChange: (v: View) => void;
}

export default function Navbar({ current, onChange }: Props) {
  return (
    <nav className="bottom-nav">
      {NAV_ITEMS.map(item => (
        <button
          key={item.id}
          className={`bottom-nav-btn ${current === item.id ? 'active' : ''}`}
          onClick={() => onChange(item.id)}
        >
          <span className="bottom-nav-icon">{item.icon}</span>
          <span className="bottom-nav-label">{item.label}</span>
        </button>
      ))}
    </nav>
  );
}
