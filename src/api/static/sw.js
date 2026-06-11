const CACHE = "divap-dashboard-v1";
const ASSETS = [
  "/dashboard",
  "/dashboard/static/dashboard.css",
  "/dashboard/static/dashboard.js",
  "/dashboard/static/icon.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/dashboard/data") || url.pathname.startsWith("/dashboard/alerts") || url.pathname.startsWith("/dashboard/trades") || url.pathname.startsWith("/dashboard/scan")) {
    return;
  }
  if (url.pathname.startsWith("/dashboard")) {
    event.respondWith(
      caches.match(event.request).then((cached) =>
        cached || fetch(event.request).then((res) => {
          const clone = res.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, clone));
          return res;
        })
      )
    );
  }
});
