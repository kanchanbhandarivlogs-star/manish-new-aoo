// Minimal service worker — required for PWA installability.
// We intentionally do NOT cache app shell (network-first) because the React
// build hash changes on every deploy.  This SW exists so PWABuilder /
// Lighthouse mark the site as PWA-ready.
const CACHE_NAME = 'ads-studio-v1';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
    // Always go to network — let the browser cache headers do their job
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
