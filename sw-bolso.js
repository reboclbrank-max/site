/* Service worker do Comitê no Bolso — network-first (a página nova SEMPRE entra),
   cai pro cache só se a internet sumir. Não guarda conversas nem chaves (isso é do localStorage). */
const CACHE = 'bolso-v1';
const CASCA = ['./', './comite.html'];
self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CASCA)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((chaves) => Promise.all(chaves.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.hostname === 'api.github.com' || url.hostname !== location.hostname) return;
  e.respondWith(
    fetch(e.request).then((r) => {
      if (url.pathname.endsWith('comite.html') || url.pathname === './') {
        const copia = r.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copia));
      }
      return r;
    }).catch(() => caches.match(e.request).then((m) => m || caches.match('./comite.html')))
  );
});
