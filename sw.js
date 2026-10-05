// 홈 화면 앱용 서비스 워커: 페이지·공고 목록은 항상 최신(네트워크 우선), 이미지는 캐시 우선
const VERSION = "v1";
const STATIC = "static-" + VERSION;
self.addEventListener("install", e => self.skipWaiting());
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== STATIC && k !== "pages").map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  if (/\.(png|webp|jpg|svg)$/.test(url.pathname)) {
    e.respondWith(caches.open(STATIC).then(c => c.match(req).then(hit => hit || fetch(req).then(res => { if (res.ok) c.put(req, res.clone()); return res; }))));
    return;
  }
  // HTML·JSON: 네트워크 우선, 오프라인일 때만 마지막 버전
  e.respondWith(fetch(req).then(res => {
    if (res.ok) { const copy = res.clone(); caches.open("pages").then(c => c.put(url.pathname, copy)); }
    return res;
  }).catch(() => caches.match(url.pathname)));
});
