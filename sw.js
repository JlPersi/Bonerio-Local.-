/* Service worker de la app instalada (anclada al inicio). Prioriza siempre lo nuevo:
   - Páginas, scripts y data/*.json: primero la red; la copia guardada solo se usa sin conexión. Así los datos y los cambios del sitio llegan igual que en el navegador.
   - Íconos e imágenes del sitio: la copia guardada al instante y se renueva por detrás.
   - Librerías de cdnjs y jsdelivr (tienen la versión en la URL): se guardan una vez.
   - Todo lo demás (precios en vivo de data912, login de Supabase, Google, etc.) no pasa por acá. */
var V = 'bl-v1', CDN = /^https:\/\/(cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net)\//;

self.addEventListener('install', function (e) {
  self.skipWaiting();
  e.waitUntil(caches.open(V).then(function (c) { return c.addAll(['/', '/manifest.webmanifest', '/favicon.svg?v=2', '/icon-192.png']).catch(function () {}); }));
});
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (ks) { return Promise.all(ks.filter(function (k) { return k !== V; }).map(function (k) { return caches.delete(k); })); }).then(function () { return self.clients.claim(); }));
});

function put(key, res) { if (res && (res.ok || res.type === 'opaque')) { var cp = res.clone(); caches.open(V).then(function (c) { c.put(key, cp); }); } return res; }

self.addEventListener('fetch', function (e) {
  var r = e.request; if (r.method !== 'GET') return;
  var u = new URL(r.url);
  if (u.origin === location.origin) {
    if (/\.(png|jpe?g|webp|svg|ico)$/.test(u.pathname)) { // imágenes: la guardada al instante y se renueva por detrás
      e.respondWith(caches.match(r).then(function (m) { var net = fetch(r).then(function (res) { return put(r, res); }); if (m) { e.waitUntil(net.catch(function () {})); return m; } return net; }));
    } else { // página, auth.js, data/*.json: primero la red. Se guarda por ruta, sin la query (?v=, ?code=, ?login), para tener una sola copia de cada cosa
      var key = u.pathname;
      e.respondWith(fetch(r).then(function (res) { return put(key, res); }).catch(function () { return caches.match(key).then(function (m) { return m || (r.mode === 'navigate' ? caches.match('/') : Response.error()); }); }));
    }
  } else if (CDN.test(r.url)) {
    e.respondWith(caches.match(r).then(function (m) { return m || fetch(r).then(function (res) { return put(r, res); }); }));
  }
});

// alertas: la notificación que manda scripts/alertas.py (web push). Al tocarla abre la pestaña Alertas.
self.addEventListener('push', function (e) {
  var d = {}; try { d = e.data ? e.data.json() : {}; } catch (x) { d = { title: 'Bonerio Local', body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || 'Bonerio Local', { body: d.body || '', icon: '/icon-192.png', badge: '/icon-192.png', tag: d.tag, data: { url: d.url || '/' } }));
});
self.addEventListener('notificationclick', function (e) {
  e.notification.close(); var url = (e.notification.data && e.notification.data.url) || '/';
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (cs) {
    for (var i = 0; i < cs.length; i++) if ('focus' in cs[i]) { cs[i].navigate(url).catch(function () {}); return cs[i].focus(); }
    return self.clients.openWindow(url);
  }));
});
