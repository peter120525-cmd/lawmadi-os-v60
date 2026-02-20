// Lawmadi OS — Service Worker Self-Cleanup
// PWA 앱 설치 방식 제거됨. 기존 캐시를 정리하고 자체 해제합니다.

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
      .then(() => self.registration.unregister())
  );
});
