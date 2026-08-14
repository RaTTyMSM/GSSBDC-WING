// GSSBDC WING service worker
// Strategy: cache ONLY static assets (CSS, icons). Every page and every
// piece of data (donors, requests, statistics, notices...) always goes to
// the network -- this is a blood-request app, showing a stale "Open"
// request after it's actually been fulfilled would be actively harmful.
// The only thing the cache buys us is: the app shell (styling/icons) loads
// instantly, and a friendly offline page instead of a browser error when
// there's truly no connection.

const CACHE_NAME = "gssbdc-wing-shell-v1";
const SHELL_ASSETS = [
"/static/style.css",
"/static/icons/icon-192.png",
"/static/icons/icon-512.png",
"/static/manifest.json",
"/static/offline.html"
];

self.addEventListener("install", (event) => {
event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
);
self.skipWaiting();
});

self.addEventListener("activate", (event) => {
event.waitUntil(
    caches.keys().then((names) =>
    Promise.all(
        names
        .filter((name) => name !== CACHE_NAME)
        .map((name) => caches.delete(name))
    )
    )
);
self.clients.claim();
});

self.addEventListener("fetch", (event) => {
const req = event.request;
const url = new URL(req.url);

  // Only ever handle GET requests -- never touch POST (form submissions,
  // login, adding donors/requests etc must always go straight to network).
if (req.method !== "GET") return;

const isShellAsset = SHELL_ASSETS.some((path) => url.pathname === path);

if (isShellAsset) {
    // Cache-first for the shell: instant load, refresh cache in background.
    event.respondWith(
    caches.match(req).then((cached) => {
        const fetchPromise = fetch(req).then((res) => {
        caches.open(CACHE_NAME).then((cache) => cache.put(req, res.clone()));
        return res;
        }).catch(() => cached);
        return cached || fetchPromise;
    })
    );
    return;
}

  // Everything else (pages, /api/*, socket.io) -- network only, no caching.
  // If there's genuinely no connection and it's a page navigation, show a
  // simple offline page instead of the browser's default error.
if (req.mode === "navigate") {
    event.respondWith(
    fetch(req).catch(() => caches.match("/static/offline.html"))
    );
}
  // Non-navigation, non-shell requests (e.g. socket.io polling) are left
  // completely alone -- just let the network request happen normally.
});