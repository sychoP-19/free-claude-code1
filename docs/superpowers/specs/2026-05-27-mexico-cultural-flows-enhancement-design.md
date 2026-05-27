# Mexico Cultural Flows Enhancement Design

Date: 2026-05-27

## Context

Working file: `mexico-cultural-flows/index.html` (823 lines, canvas map, 10 cities, 6 categories, bezier particles, timeline slider, category filters, detail panel). Previous rewrite (`index-2026.html`, 2777 lines) broke. Enhance incrementally.

Existing external files: `personalization-engine.js` (944 lines), `sw.js`, `pwa-registration.js`, `manifest.json`, icons/, OG image.

## Decisions

| Decision | Choice |
|----------|--------|
| Cities | 50+ (32 state capitals + cultural hubs) |
| City detail | Full-screen overlay, solid dark panel |
| Detail tabs | Overview, Flows & Connections, Historical Timeline, Routes & Recommendations |
| i18n | EN/ES only, toggle switch in header |
| Gamification | 15 badges, toast on unlock, localStorage tracking |
| Routes | Quiz modal + top 3 results + "Surprise Me" wildcard |
| PWA | Wire existing sw.js/manifest/pwa-registration.js |
| Accessibility | Full WCAG 2.1 AA |
| Build | Incremental surgical edits to index.html + gamification.js external |

## Phase 1: Data Expansion

Expand CITIES array from 10 to 50+.

### City object shape
```js
{
  id: 'cdmx',
  name: 'Ciudad de México',
  nameEn: 'Mexico City',
  state: 'CDMX',
  region: 'Centro',
  lon: -99.13, lat: 19.43,
  categories: ['arte','musica','gastro','danza','historia'],
  yearFrom: 1300,
  flows: [
    { cat:'arte', icon:'🎨', name:'Muralismo Mexicano',
      nameEn:'Mexican Muralism',
      desc:'Rivera, Orozco, Siqueiros revolucionaron el arte del siglo XX.',
      descEn:'Rivera, Orozco, Siqueiros revolutionized 20th century art.',
      to:['gdl','oax','ver'] }
  ],
  stats: { cultural_sites: 187, unesco: 3, traditions: 42 },
  events: [
    { era:'precolombina', year:1325, title:'Fundación de Tenochtitlan' },
    { era:'colonia', year:1521, title:'Caída de Tenochtitlan' },
    { era:'contemporaneo', year:1968, title:'Movimiento Estudiantil' }
  ],
  description: 'Capital cultural de América Latina...',
  descriptionEn: 'Cultural capital of Latin America...'
}
```

### Categories (8 total)
arte, musica, gastro, danza, artesania, historia, arquitectura, espiritualidad

### City list (50+)
32 state capitals + 20 cultural hubs:
- State capitals: CDMX, Guadalajara, Monterrey, Puebla, Mérida, Veracruz, Toluca, Morelia, Guanajuato, Querétaro, Aguascalientes, Zacatecas, San Luis Potosí, Chihuahua, Hermosillo, Villahermosa, Tuxtla Gutiérrez, Oaxaca, Cuernavaca, Tlaxcala, Colima, Durango, Mérida, Campeche, Chetumal, La Paz, Culiacán, Tepic, Xalapa, Saltillo, Victoria
- Cultural hubs: San Cristóbal de las Casas, Taxco, Tijuana, Cancún, Ciudad Juárez, Acapulco, San Miguel de Allende, León, Mérida, Palenque, Teotihuacán, Tula, Patzcuaro, Real de Catorce, Chiapa de Corzo, Izamal, Valladolid, Comitán, Mazatlán, Puerto Vallarta

## Phase 2: Full-Screen City Detail Overlay

### Trigger
Click a city dot (not hover — hover keeps current tooltip behavior)

### Structure
- Full-screen overlay covering entire viewport
- Solid dark background (#0a0918)
- Top bar: city name (Playfair Display), region tag, close button (X), ESC to close
- Tab bar: Overview | Flows | Timeline | Routes
- Content area below tabs

### Overview tab
- City name + state + region
- 3 stat cards (cultural sites, UNESCO, traditions)
- Category badges with colors
- Short description paragraph

### Flows & Connections tab
- Outgoing flows: icon, name, category color, target cities
- Incoming flows: from other cities
- Visual: flow cards with direction arrows

### Timeline tab
- Era-filtered events for this city
- Precolombina, Colonia, Independencia, Revolución, Contemporáneo
- Event cards with year + title

### Routes tab
- AI-recommended routes including this city (from personalization-engine.js)
- If quiz completed: show match score
- "Take Quiz" button if not completed
- Manual route browse

### DOM approach
- Use createElement/textContent/appendChild (no innerHTML with dynamic data)

## Phase 3: i18n (EN/ES)

### Implementation
- `data-i18n` attribute on all UI elements
- `I18N` object: `{ en: {...}, es: {...} }`
- `applyI18N()` walks DOM, sets textContent from dictionary
- City names: `nameEn` field per city, fallback to `name`
- Flow names/descriptions: `nameEn`/`descEn` per flow
- Toggle button in header: shows "EN" or "ES", click switches
- Default: ES (Spanish — this is about Mexico)

### Translation keys (~80)
Header, sidebar labels, category names, timeline labels, overlay tab names, badge names, quiz questions, route descriptions, tooltips

## Phase 4: Gamification

### External file: `gamification.js`
Creates `window.Gamification` with:
- 15 badge definitions
- localStorage persistence (key: `mexFlows_gamification`)
- `checkUnlock(action, detail)` — checks if action triggers badge
- `getBadges()` — returns all badges with unlock status
- `getStats()` — returns cities explored, flows viewed, quiz completed

### 15 Badges
1. Primer Paso — visit first city
2. Explorador — visit 5 cities
3. Viajero — visit 10 cities
4. Conquistador — visit 25 cities
5. Cartógrafo — visit all cities
6. Melómano — activate only Musica category
7. Gourmet — activate only Gastro category
8. Historiador — use timeline across 4+ eras
9. Cronista — play full timeline
10. Connoisseur — view flows for 10+ cities
11. Navegante — toggle all categories on/off
12. Roterista — complete AI quiz
13. Sorprendido — use "Surprise Me" route
14. Bilingüe — switch language
15. Maestro — unlock all other badges

### Toast notification
- Slide-in from top-right
- Badge icon + name + "Unlocked!"
- Auto-dismiss after 4 seconds
- CSS animation (no alerts)

### Badge panel
- Collapsible section in sidebar
- Grid of badge icons (locked = gray, unlocked = color)
- Progress bar (% complete)

## Phase 5: AI Route Personalization

### Integration
- Load `personalization-engine.js` via `<script>` tag (already built)
- "Find Your Route" button in header (gold accent)

### Quiz modal
- Full-screen overlay (same style as city detail)
- 5 questions with progress bar
- Option buttons per question
- Results page: top 3 routes with scores + "Surprise Me" wildcard

### Route display
- Route card: name, icon, score, match reason
- Cities on route listed
- "View on Map" highlights route cities

## Phase 6: PWA + Accessibility + Polish

### PWA
- Add `<link rel="manifest" href="manifest.json">`
- Add `<script src="pwa-registration.js"></script>`
- Add meta tags: theme-color, apple-mobile-web-app-capable
- og:image pointing to existing asset

### Accessibility
- `role="application"` on main canvas
- `aria-label` on all buttons, sliders, tabs
- Tab navigation: header buttons → sidebar → overlay controls
- ESC closes overlays
- Focus rings (3px gold outline)
- `aria-live="polite"` region for badge toasts
- `role="tablist"`, `role="tab"`, `role="tabpanel"` for detail tabs
- Screen reader: announce city name on hover via live region

### Performance
- Keep particle count proportional to flow count (avoid 2000+ particles with 50 cities)
- Throttle detail panel updates
- Use requestAnimationFrame (already in place)

## File Structure After Enhancement
```
mexico-cultural-flows/
├── index.html           (main app, ~1500 lines)
├── personalization-engine.js  (existing, 944 lines)
├── gamification.js      (new, ~350 lines)
├── sw.js                (existing, 258 lines)
├── pwa-registration.js  (existing, 321 lines)
├── manifest.json        (existing)
├── icons/               (existing 8 sizes)
└── assets/
    └── og-image.png     (existing)
```

## Execution Order
1. Phase 1: Expand CITIES data (50+ cities, events, bilingual fields)
2. Phase 2: Full-screen overlay + 4 tabs
3. Phase 3: i18n EN/ES toggle
4. Phase 4: Create gamification.js, wire into index.html
5. Phase 5: Wire personalization-engine.js, build quiz modal
6. Phase 6: PWA, accessibility, polish

## Verification (after EACH phase)
- Open index.html in browser
- Canvas renders all cities
- Click city → overlay opens with tabs
- Language toggle works
- Quiz returns recommendations
- Badges unlock on actions
- No console errors
