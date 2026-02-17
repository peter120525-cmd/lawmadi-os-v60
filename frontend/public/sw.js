// Lawmadi OS Service Worker v2
const CACHE_NAME = 'lawmadi-v60-20260217';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png',
  '/og-image.png'
];

// Install: cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// Activate: clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch: network-first for API, cache-first for static
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET and API requests
  if (event.request.method !== 'GET' || url.pathname.startsWith('/ask') || url.pathname.startsWith('/mcp')) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const fetchPromise = fetch(event.request).then((response) => {
        if (response && response.status === 200 && response.type === 'basic') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => {
        // Offline fallback for navigation requests
        if (event.request.mode === 'navigate') {
          return new Response(
            '<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Lawmadi OS - Offline</title><style>body{font-family:system-ui;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:#1a1a2e;color:#e0e0e0;text-align:center}.box{padding:2rem}h1{color:#2563eb;font-size:1.5rem}p{color:#999}</style></head><body><div class="box"><h1>Lawmadi OS</h1><p>현재 오프라인 상태입니다.<br>인터넷 연결 후 다시 시도해주세요.</p></div></body></html>',
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        }
        return cached;
      });
      return cached || fetchPromise;
    })
  );
});
