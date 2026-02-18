// Lawmadi OS Service Worker v3 — Network-First + Auto Update
const CACHE_NAME = 'lawmadi-v60-20260218-stream';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png',
  '/og-image.png'
];

// Install: cache static assets + 즉시 활성화
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())  // 대기 없이 즉시 활성화
  );
});

// Activate: 이전 캐시 모두 삭제 + 즉시 제어권 획득
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())  // 열린 탭 즉시 제어
  );
});

// Fetch: Network-First (항상 최신 버전 우선)
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // API/스트리밍 요청은 SW 개입 없이 통과
  if (event.request.method !== 'GET' ||
      url.pathname.startsWith('/ask') ||
      url.pathname.startsWith('/mcp') ||
      url.pathname.startsWith('/api/')) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // 네트워크 성공 → 캐시 갱신 후 반환
        if (response && response.status === 200 && response.type === 'basic') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => {
        // 네트워크 실패 → 캐시 폴백 (오프라인)
        return caches.match(event.request).then((cached) => {
          if (cached) return cached;
          // 네비게이션 요청이면 오프라인 페이지
          if (event.request.mode === 'navigate') {
            return new Response(
              '<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Lawmadi OS - Offline</title><style>body{font-family:system-ui;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:#1a1a2e;color:#e0e0e0;text-align:center}.box{padding:2rem}h1{color:#2563eb;font-size:1.5rem}p{color:#999}</style></head><body><div class="box"><h1>Lawmadi OS</h1><p>현재 오프라인 상태입니다.<br>인터넷 연결 후 다시 시도해주세요.</p></div></body></html>',
              { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
            );
          }
        });
      })
  );
});
