// Bonerío entero adentro del panel lateral; cuando el panel de Matriz pide una ficha o una curva, cambia el # de la página.
const F = document.getElementById('f'), BASE = 'https://boneriolocal.com.ar/';
const ir = (h) => { if (h) F.src = BASE + '#' + h; };
chrome.storage.session.get('ir', (o) => ir(o.ir));
chrome.storage.onChanged.addListener((c) => c.ir && ir(c.ir.newValue));
