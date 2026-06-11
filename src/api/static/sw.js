const CACHE = "divap-dashboard-v4";
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
  "/dashboard/push/status",
  "/dashboard/strategy/insights",
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

self.addEventListener("push", (event) => {
  let data = { title: "DIVAP Trader", body: "Novo sinal", url: "/dashboard" };
  try {
    if (event.data) data = { ...data, ...event.data.json() };
  } catch (_) { /* keep defaults */ }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/dashboard/static/icon.svg",
      badge: "/dashboard/static/icon.svg",
      tag: "divap-high-signal",
      data: { url: data.url || "/dashboard" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/dashboard";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes("/dashboard") && "focus" in client) {
          return client.focus();
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
