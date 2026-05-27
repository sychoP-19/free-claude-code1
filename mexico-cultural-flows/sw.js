// Mexico Cultural Flows - Service Worker
// Offline-first PWA with intelligent caching strategies

const CACHE_VERSION = 'mexico-cf-2026-v2';
const PRECACHE_CACHE = `precache-${CACHE_VERSION}`;
const RUNTIME_CACHE = `runtime-${CACHE_VERSION}`;
const FONTS_CACHE = `fonts-${CACHE_VERSION}`;

// Primary app shell is index-2026.html; index.html kept as fallback
const APP_SHELL = '/index-2026.html';

// Precache budget: ~500KB for core assets (inline CSS/JS in HTML)
const PRECACHE_ASSETS = [
  '/',
  APP_SHELL,
  '/index.html',
  '/manifest.json',
];

// Runtime cache budgets
const IMAGE_CACHE_BUDGET = 5 * 1024 * 1024; // 5MB
const API_CACHE_TTL = 5 * 60 * 1000; // 5 minutes

// Install event - precache core assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(PRECACHE_CACHE)
      .then((cache) => cache.addAll(PRECACHE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean old caches
self.addEventListener('activate', (event) => {
  const currentCaches = [PRECACHE_CACHE, RUNTIME_CACHE, FONTS_CACHE];
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((name) => !currentCaches.includes(name))
            .map((name) => caches.delete(name))
        );
      })
      .then(() => self.clients.claim())
  );
});

// Fetch event - routing strategy
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip cross-origin requests
  if (url.origin !== self.location.origin) {
    return;
  }

  // Route requests by type
  if (request.destination === 'image') {
    event.respondWith(cacheFirst(request, RUNTIME_CACHE));
    return;
  }

  if (request.destination === 'font') {
    event.respondWith(staleWhileRevalidate(request, FONTS_CACHE));
    return;
  }

  if (request.destination === 'style' || request.destination === 'script') {
    event.respondWith(cacheFirst(request, PRECACHE_CACHE));
    return;
  }

  // API requests - network first with fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request, RUNTIME_CACHE));
    return;
  }

  // Navigation requests - serve index-2026.html (network first, precached app shell fallback)
  if (request.mode === 'navigate') {
    event.respondWith(navigateToAppShell(request));
    return;
  }

  // Default - cache first
  event.respondWith(cacheFirst(request, RUNTIME_CACHE));
});

// Navigation handler - tries network first, falls back to precached app shell
async function navigateToAppShell(request) {
  const cache = await caches.open(PRECACHE_CACHE);

  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    // Offline: serve the precached app shell for any navigation request
    const cached = await cache.match(APP_SHELL);
    if (cached) {
      return cached;
    }
    // Last resort: try index.html
    const fallback = await cache.match('/index.html');
    if (fallback) {
      return fallback;
    }
    return new Response('Offline - app unavailable', { status: 503 });
  }
}

// Cache-first strategy for static assets
async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  if (cached) {
    return cached;
  }

  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
      // Enforce budget for runtime cache
      await enforceCacheBudget(cacheName, IMAGE_CACHE_BUDGET);
    }
    return response;
  } catch (error) {
    return new Response('Offline - cached version unavailable', { status: 503 });
  }
}

// Network-first strategy for dynamic content
async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);

  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) {
      return cached;
    }
    return new Response(JSON.stringify({ error: 'Offline' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}

// Stale-while-revalidate for fonts
async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  const fetchPromise = fetch(request)
    .then((response) => {
      if (response.ok) {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => cached);

  return cached || fetchPromise;
}

// Enforce cache budget
async function enforceCacheBudget(cacheName, budget) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();

  let totalSize = 0;
  const sizes = await Promise.all(
    keys.map(async (request) => {
      const response = await cache.match(request);
      const blob = await response.blob();
      return blob.size;
    })
  );

  keys.forEach((request, index) => {
    totalSize += sizes[index];
  });

  // Remove oldest entries when over budget
  if (totalSize > budget) {
    await Promise.all(keys.slice(0, keys.length - 5).map((req) => cache.delete(req)));
  }
}

// Background sync for preferences
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-preferences') {
    event.waitUntil(syncPreferences());
  }
});

async function syncPreferences() {
  // Sync user preferences to server when back online
  const clients = await self.clients.matchAll();
  clients.forEach((client) => {
    client.postMessage({ type: 'PREFS_SYNCED' });
  });
}

// Push notification support
self.addEventListener('push', (event) => {
  const options = {
    body: event.data ? event.data.text() : 'New cultural update available',
    icon: '/icons/icon-192x192.png',
    badge: '/icons/badge-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1,
    },
    actions: [
      { action: 'explore', title: 'Explore', icon: '/icons/explore.png' },
      { action: 'close', title: 'Close', icon: '/icons/close.png' },
    ],
  };

  event.waitUntil(
    self.registration.showNotification('Mexico Cultural Flows', options)
  );
});

// Notification click handler
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'explore') {
    event.waitUntil(clients.openWindow('/'));
  }
});

// Message handler for PWA comms
self.addEventListener('message', (event) => {
  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }

  if (event.data.type === 'CACHE_URLS') {
    event.waitUntil(
      caches.open(RUNTIME_CACHE).then((cache) => cache.addAll(event.data.urls))
    );
  }
});