// Puente: carga la sección de Bonerío que pide el # y pasa la altura que manda la página a la ventana de Matriz.
const F = document.getElementById('f');
const ir = () => { const u = decodeURIComponent(location.hash.slice(1)); if (u.startsWith('https://boneriolocal.com.ar/')) F.src = u; };
addEventListener('hashchange', ir); ir();
addEventListener('message', (e) => {
  if (e.source !== F.contentWindow || !e.data || e.data.t !== 'bnrH') return;
  F.style.height = e.data.h + 'px'; parent.postMessage({ t: 'bnrH', h: e.data.h }, '*');
});
