/* Campus 24/7 service worker.
 *
 * Does two things only: it shows an "offline" page when a page cannot be loaded, and it keeps the build's hashed static files so
 * the app opens faster. It never stores anything from the API, anything with cookies, or anything the server marked no-store,
 * so signing out or switching accounts cannot leave another person's data on the device.
 */
const VERSION = "campus247-sw-v1";
const STATIC_CACHE = `${VERSION}-static`;
const PAGE_CACHE = `${VERSION}-pages`;
const PRECACHE = ["/offline", "/icons/icon-192.png", "/icons/icon-512.png"];

/** Never answered from or written to a cache: the API, the health endpoints, downloads (Range requests) and anything not GET. */
function isUncacheable(request, url) {
  return (
    request.method !== "GET" ||
    url.origin !== self.location.origin ||
    url.pathname.startsWith("/v1/") ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/health") ||
    url.pathname === "/metrics" ||
    request.headers.has("range")
  );
}

/** A response that is safe to keep: it succeeded, and the server did not ask for it to stay private or set a cookie. */
function isStorable(response) {
  if (!response || response.status !== 200 || response.type === "opaque") return false;
  const control = (response.headers.get("cache-control") || "").toLowerCase();
  return !control.includes("no-store") && !control.includes("private") && !response.headers.has("set-cookie");
}

self.addEventListener("install", (event) => {
  // One missing file must not stop the worker from installing: keep what can be fetched, skip the rest.
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE).catch(() => Promise.all(PRECACHE.map((path) => cache.add(path).catch(() => undefined)))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) => Promise.all(names.filter((name) => !name.startsWith(VERSION)).map((name) => caches.delete(name))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (isUncacheable(request, url)) return; // the browser handles it as if there were no service worker

  if (request.mode === "navigate") {
    // Pages: always try the network; offline, show the offline page. Pages themselves are never stored (they can hold personal data).
    event.respondWith(fetch(request).catch(() => caches.match("/offline").then((page) => page || Response.error())));
    return;
  }

  if (url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icons/")) {
    event.respondWith(
      caches.match(request).then(
        (hit) =>
          hit ||
          fetch(request).then((response) => {
            if (isStorable(response)) {
              const copy = response.clone();
              caches.open(STATIC_CACHE).then((cache) => cache.put(request, copy));
            }
            return response;
          }),
      ),
    );
  }
});

/** The page tells the worker to forget everything, for example when a person signs out. */
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "campus247:clear-caches") {
    event.waitUntil(caches.keys().then((names) => Promise.all(names.map((name) => caches.delete(name)))));
  }
});
