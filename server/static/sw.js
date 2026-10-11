// Minimal service worker: makes the PWA installable. Always goes to the network,
// because the gate and quests must never show stale data.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
