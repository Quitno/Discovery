'use strict';
const CACHE_VERSION = 'discovery-hub-shell-v2';
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
  if (url.pathname.startsWith('/admin') || url.pathname.startsWith('/go/') || url.pathname === '/search' || url.pathname === '/health' || url.pathname === '/service-worker.js' || url.pathname === '/build-a-website-or-app') return;

  if (url.pathname.startsWith('/static/')) {
    event.respondWith(caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      if (response && response.ok) {
        const clone = response.clone();
        caches.open(CACHE_VERSION).then((cache) => cache.put(request, clone));
      }
      return response;
    })));
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).then((response) => {
      if (response && response.ok && url.pathname === '/' && !url.search) {
        const clone = response.clone();
        caches.open(CACHE_VERSION).then((cache) => cache.put('/', clone));
      }
      return response;
    }).catch(async () => (await caches.match(request)) || (await caches.match('/')) || (await caches.match('/offline'))));
  }
});
