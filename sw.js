// Golómetro · service worker
// - Fotos, escudos, avatares, iconos y la fuente: se guardan en el móvil la primera vez y después salen al instante
//   (sus nombres cambian cuando cambia la imagen, así que no se quedan viejos).
// - Página y datos (.html, .json): siempre se piden a internet; la copia guardada solo se usa sin conexión.
const IMG = "golometro-img-v1", PAG = "golometro-pag-v1";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== IMG && k !== PAG).map(k => caches.delete(k)))).then(() => self.clients.claim())
));

self.addEventListener("fetch", e => {
  const req = e.request, u = new URL(req.url);
  if (req.method !== "GET" || u.origin !== location.origin) return;
  if (/\.(png|jpe?g|webp|svg|gif|woff2?)$/i.test(u.pathname)) {
    e.respondWith(caches.open(IMG).then(c => c.match(req).then(r => r || fetch(req).then(res => {
      if (res.ok) c.put(req, res.clone());
      return res;
    }))));
    return;
  }
  // red primero; se guarda sin la parte «?t=...» para poder usarla sin conexión
  const clave = u.origin + u.pathname;
  e.respondWith(fetch(req).then(res => {
    if (res.ok) { const copia = res.clone(); caches.open(PAG).then(c => c.put(clave, copia)); }
    return res;
  }).catch(() => caches.open(PAG).then(c => c.match(clave)).then(r => r || Response.error())));
});
