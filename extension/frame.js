// Puente: carga la sección de Bonerío que pide el # y pasa la altura que manda la página a la ventana de Matriz.
const F = document.getElementById('f');
const ir = () => { const u = decodeURIComponent(location.hash.slice(1)); if (u.startsWith('https://boneriolocal.com.ar/')) F.src = u; };
addEventListener('hashchange', ir); ir();
addEventListener('message', (e) => {
  if (e.source !== F.contentWindow || !e.data) return;
  if (e.data.t === 'bnrH') { F.style.height = e.data.h + 'px'; parent.postMessage({ t: 'bnrH', h: e.data.h }, '*'); }
  if (e.data.t === 'bnrTk' && /^[A-Z0-9\/]{3,10}$/.test(e.data.k)) parent.postMessage({ t: 'bnrTk', k: e.data.k }, '*'); // tocó un bono en Bonerío
});
addEventListener('message', (e) => { // la ventana de Matriz pide otra sección: va directo a la página, sin recargar
  if (e.source === parent && e.data && e.data.t === 'bnrSec' && F.contentWindow) F.contentWindow.postMessage(e.data, '*');
});
