# mexico-cultural-flows 2026 - Architecture Document

## Vision
Interactive cultural discovery platform celebrating México's 500-year heritage through dynamic data visualization, AI-powered personalization, and immersive storytelling.

## Target Score: 9.90/10

## Core Features

### 1. Enhanced City Database (22 cities)
- Current: 10 cities → Expanded: 22 cities
- Each city: 15 cultural categories, era metadata, news, events, images
- UNESCO site integration, festival calendars

### 2. Five-Era Timeline
- Precolombina (antes 1521)
- Colonia (1521-1810)
- Independencia (1810-1910)
- Revolución (1910-1980)
- Contemporáneo (1980-2026)

### 3. AI Route Personalization
- 5-question preference quiz
- Interest scoring (category weights 0-100)
- Cosine similarity route matching
- 10 curated cultural routes
- 10% serendipity factor

### 4. Multi-Language (EN/ES/PT)
- Instant toggle
- All UI elements translated
- Fallback to Spanish

### 5. PWA Support
- Service Worker (offline-first caching)
- manifest.json (app installation)
- Background sync for preferences
- ~5MB first-load cache

### 6. Gamification
- 15 badges (Explorer, Connoisseur, Historian, etc.)
- Unlock animations (canvas confetti)
- Progress tracking (localStorage)
- 10 mini-quiz questions

### 7. Social Sharing
- Canvas-based share card generation
- City photo + cultural fact + hashtags
- Copy to clipboard / Share API

### 8. Advanced Interactions
- Search (full-text across cities, flows, categories)
- Compare mode (side-by-side city analysis)
- Export PDF (canvas capture + summary)

### 9. Accessibility (WCAG 2.1 AA)
- ARIA labels on all interactive elements
- Keyboard navigation (Tab, Enter, Arrows)
- Skip links
- Focus rings (3px, ≥3:1 contrast)
- Reduced motion support
- Screen reader live regions

### 10. Visual Enhancements
- 15 category colors (accessible, culturally significant)
- Responsive typography (clamp())
- Adobe/Google Fonts: Playfair Display + DM Sans
- Particle system (500-2000 particles, 60fps)
- Era badge animations
- Dark/light mode toggle

## File Structure

```
mexico-cultural-flows/
├── index.html (original, backup)
├── index-2026.html (NEW: full 9.90 overhaul)
├── sw.js (Service Worker)
├── manifest.json (PWA manifest)
└── assets/
    ├── images/ (city photos, cultural artifacts)
    └── audio/ (cultural flow sounds)
```

## Technical Stack
- Vanilla JavaScript (ES6+)
- HTML5 Canvas (2D context)
- CSS3 (custom properties, clamp(), grid)
- Web Animations API
- Service Worker API
- File System Access API (export)

## Performance Targets
- First paint: <1s
- Time to interactive: <2s
- Animation FPS: 60
- Bundle size: <100KB (code), ~5MB (cached)
- Offline: Full functionality after first load

## Browser Support
- Chrome 80+
- Firefox 75+
- Safari 14+
- Edge 80+

## SEO
- Meta tags: title, description, og:image
- Structured data: Organization, Event, Place
- Sitemap: Cultural cities, routes