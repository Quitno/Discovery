'use strict';
const CACHE_VERSION = 'discovery-hub-shell-v6';
const APP_SHELL = [
  '/',
  '/offline',
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/icons/favicon.svg',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_VERSION).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_VERSION).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/admin') || url.pathname.startsWith('/account/') || url.pathname === '/my-projects' || url.pathname.startsWith('/go/') || url.pathname === '/search' || url.pathname === '/health' || url.pathname === '/service-worker.js' || url.pathname === '/build-a-website-or-app' || url.pathname.startsWith('/download-file/')) return;

  if (url.pathname.startsWith('/static/')) {
    event.respondWith(caches.match(request).then((cached) => cached || fetch(request).then(async (response) => {
      if (response && response.ok) {
        try {
          const cache = await caches.open(CACHE_VERSION);
          await cache.put(request, response.clone());
        } catch (_) { /* The current page still works if storage is full or blocked. */ }
      }
      return response;
    })));
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).then(async (response) => {
      if (response && response.ok && !url.search && (url.pathname === '/' || url.pathname.startsWith('/service/') || url.pathname.startsWith('/service-group/') || url.pathname === '/downloads' || url.pathname.startsWith('/downloads/'))) {
        try {
          const cache = await caches.open(CACHE_VERSION);
          await cache.put(request, response.clone());
        } catch (_) { /* Online browsing should not fail because a cache write failed. */ }
      }
      return response;
    }).catch(async () => (await caches.match(request)) || (await caches.match('/')) || (await caches.match('/offline'))));
  }
});
