// Puente: carga la sección de Bonerío que pide el # y pasa la altura que manda la página a la ventana de Matriz.
const F = document.getElementById('f');
const ir = () => { const u = decodeURIComponent(location.hash.slice(1)); if (u.startsWith('https://boneriolocal.com.ar/')) F.src = u; };
addEventListener('hashchange', ir); ir();
addEventListener('message', (e) => {
  if (e.source !== F.contentWindow || !e.data) return;
  if (e.data.t === 'bnrH') { F.style.height = e.data.h + 'px'; parent.postMessage({ t: 'bnrH', h: e.data.h }, '*'); }
  if (e.data.t === 'bnrPata' && /^[A-Z0-9\/]{3,10}$/.test(e.data.k) && /^(ci|24)$/.test(e.data.pz) && /^[cv]$/.test(e.data.sd)) parent.postMessage({ t: 'bnrPata', k: e.data.k, pz: e.data.pz, sd: e.data.sd, q: +e.data.q > 0 ? +e.data.q : 0 }, '*'); // una pata del pase
  if (e.data.t === 'bnrPaseAl' && Array.isArray(e.data.a)) parent.postMessage({ t: 'bnrPaseAl', a: e.data.a.slice(0, 20).filter((x) => x && /^[A-Z0-9\/]{3,10}$/.test(x.t) && (x.tp === 1 || x.tp === 2)).map((x) => ({ t: x.t, tp: x.tp, g: +x.g || 0, c: +x.c || 0, n: +x.n || 0 })) }, '*'); // pases que convienen en tus especies
  if (e.data.t === 'bnrPro') parent.postMessage({ t: 'bnrPro', p: e.data.p }, '*'); // si la cuenta tiene Bonerío PRO
  if (e.data.t === 'bnrDat') parent.postMessage({ t: 'bnrDat', k: e.data.k, d: e.data.d }, '*'); // datos del bono para la calculadora del panel
  if (e.data.t === 'bnrTk' && /^[A-Z0-9\/]{3,10}$/.test(e.data.k)) parent.postMessage({ t: 'bnrTk', k: e.data.k }, '*'); // tocó un bono en Bonerío
});
addEventListener('message', (e) => { // la ventana de Matriz pide otra sección: va directo a la página, sin recargar
  if (e.source === parent && e.data && /^bnr(Sec|Datos|CvH|Sel|Px)$/.test(e.data.t) && F.contentWindow) F.contentWindow.postMessage(e.data, '*');
});
