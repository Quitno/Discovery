const CACHE_NAME = 'patamahali-shell-v13-mobile-photo-dedup';
const SHELL_ASSETS = [
  '/static/css/style.css?v=20261028-mobile-photo-dedup-r10',
  '/static/js/app.js?v=20261028-mobile-photo-dedup-r10',
  '/icon.svg',
  '/static/img/property-scenes/neighbourhood-hero.webp',
  '/static/img/property-scenes/modern-interior.webp',
  '/static/img/property-scenes/apartment-building.webp',
  '/static/img/property-scenes/residential-land.webp'
];
self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  const path = url.pathname;
  // Never cache account pages, admin paths, personal documents, payment actions, or APIs.
  if (path.startsWith('/partner/') || path.startsWith('/manage-admin/') || path === '/promise212324' || path.startsWith('/api/') || path.startsWith('/login') || path.startsWith('/join') || path.startsWith('/logout')) return;
  if (path.startsWith('/static/') || path === '/icon.svg' || path === '/manifest.webmanifest') {
    event.respondWith(caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      if (response.ok) caches.open(CACHE_NAME).then((cache) => cache.put(request, response.clone()));
      return response;
    })));
    return;
  }
  if (request.mode === 'navigate' && (path === '/' || path === '/homes' || path.startsWith('/listing/') || path === '/partners')) {
    event.respondWith(fetch(request).then((response) => {
      if (response.ok) caches.open(CACHE_NAME).then((cache) => cache.put(request, response.clone()));
      return response;
    }).catch(async () => {
      const cached = await caches.match(request);
      if (cached) return cached;
      return new Response('<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Offline</title><body style="font:16px system-ui;max-width:36rem;margin:3rem auto;padding:1rem;color:#182235"><h1>You are offline</h1><p>Reconnect to view current listings and confirm availability. Saved page information may be out of date.</p><a href="/">Try the home page</a></body></html>', {headers: {'Content-Type': 'text/html; charset=utf-8'}});
    }));
  }
});
