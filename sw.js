const CACHE = "bolso-v1";
const NUCLEO = ["https://reboclbrank-max.github.io/site/comite.html"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(NUCLEO)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
// rede-primeiro: a página é sempre fresca; cache só salva quando o sinal cai
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    fetch(e.request).then((r) => {
      const copia = r.clone();
      if (e.request.url.includes("comite.html")) caches.open(CACHE).then((c) => c.put(e.request, copia));
      return r;
    }).catch(() => caches.match(e.request).then((x) => x || caches.match(NUCLEO[0])))
  );
});