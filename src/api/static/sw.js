const CACHE = "divap-dashboard-v2";
const SHELL = ["/dashboard/static/icon.svg"];

const NETWORK_ONLY_PREFIXES = [
  "/dashboard/data",
  "/dashboard/market",
  "/dashboard/balance",
  "/dashboard/strategy",
  "/dashboard/trading-readiness",
  "/dashboard/alerts",
  "/dashboard/trades",
  "/dashboard/scan",
  "/dashboard/auth",
  "/dashboard/bankroll",
];

function isStaticAsset(pathname) {
  return pathname.startsWith("/dashboard/static/") &&
    (pathname.endsWith(".js") || pathname.endsWith(".css") || pathname.endsWith("sw.js"));
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  const url = new URL(event.request.url);
  if (!url.pathname.startsWith("/dashboard")) return;

  if (NETWORK_ONLY_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
    return;
  }

  if (isStaticAsset(url.pathname)) {
    event.respondWith(networkFirst(event.request));
    return;
  }

  if (url.pathname === "/dashboard" || url.pathname === "/dashboard/") {
    event.respondWith(networkFirst(event.request));
  }
});

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (_) {
    const cached = await caches.match(request);
    if (cached) return cached;
    throw _;
  }
}
