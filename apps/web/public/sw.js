/* AnyGet service worker: makes the app installable and keeps the app shell's static
   files (scripts, styles, fonts, icons) for fast and offline starts.
   It never caches API answers or downloads: those always come from your server. */
const VERSION = "anyget-static-v1";
const STATIC = /^\/(_next\/static\/|icons\/|favicon\.png$)/;

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  if (STATIC.test(url.pathname)) {
    // Fingerprinted files never change: cache first.
    event.respondWith(
      caches.open(VERSION).then(async (cache) => {
        const hit = await cache.match(request);
        if (hit) return hit;
        const response = await fetch(request);
        if (response.ok) cache.put(request, response.clone());
        return response;
      }),
    );
    return;
  }

  if (request.mode === "navigate") {
    // Pages: always the network; a short offline note only when the server is unreachable.
    event.respondWith(
      fetch(request).catch(
        () =>
          new Response(
            "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>" +
              "<title>AnyGet</title><body style='font:16px system-ui;padding:2rem'>" +
              "<h1>AnyGet is offline</h1><p>Your AnyGet server can't be reached. " +
              "Check that it is running, then reload.</p>",
            { headers: { "Content-Type": "text/html; charset=utf-8" } },
          ),
      ),
    );
  }
});
