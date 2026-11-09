/* Bonerío Inside: lee el ticker que el usuario tiene abierto en Matriz y muestra al lado los datos de Bonerío Local.
   El precio sale de la pantalla del propio usuario; Bonerío pone solo cierres, TIRs, duration y la curva (data/api/curvas.json). */
(() => {
  if (window.__bnr) return; window.__bnr = 1;
  const URL_CURVAS = 'https://boneriolocal.com.ar/data/api/curvas.json';
  let DB = {}, GRP = {}, FECHA = '', activo = null, precioManual = false;

  const fmt = (x, d = 2) => (x == null || isNaN(x) ? '-' : x.toLocaleString('es-AR', { minimumFractionDigits: d, maximumFractionDigits: d }));
  const num = (s) => { // "147.000,000" -> 147000 ; "102,45" -> 102.45
    if (!s) return NaN; s = String(s).replace(/[^\d.,-]/g, '');
    if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.');
    else if ((s.match(/\./g) || []).length > 1) s = s.replace(/\./g, '');
    return parseFloat(s);
  };

  // Curva del grupo: TIR = a + b·ln(días), por mínimos cuadrados. Residuo en pb (+ = rinde más que la curva = barato).
  function ajuste(g, ley) { // con la misma ley (Local / NY) si alcanza
    let p = GRP[g].filter((b) => b.dias > 30 && isFinite(b.tir));
    if (ley && p.filter((b) => b.ley === ley).length >= 4) p = p.filter((b) => b.ley === ley);
    if (p.length < 4) return null;
    const xs = p.map((b) => Math.log(b.dias)), ys = p.map((b) => b.tir), n = p.length;
    const mx = xs.reduce((a, b) => a + b) / n, my = ys.reduce((a, b) => a + b) / n;
    let sxy = 0, sxx = 0; xs.forEach((x, i) => { sxy += (x - mx) * (ys[i] - my); sxx += (x - mx) ** 2; });
    const b = sxy / sxx; return (d) => my + b * (Math.log(d) - mx);
  }

  // TIR estimada a otro precio: ΔTIR ≈ −(ΔP/P)/MD, con el precio de Matriz llevado a la escala del de Bonerío.
  function tirA(bono, p) {
    if (!(p > 0) || !(bono.md > 0)) return null;
    let r = p / bono.precio; while (r > 3) r /= 10; while (r < 0.3) r *= 10;
    return bono.tir - ((r - 1) / bono.md) * 100;
  }

  // ---------- lectura de la pantalla de Matriz (heurística: sin selectores fijos, porque Matriz cambia clases) ----------
  function tickerEn(el) {
    for (let i = 0; el && i < 5; i++, el = el.parentElement) {
      const t = (el.innerText || el.value || '').trim();
      if (!t || t.length > 80) continue;
      const m = t.toUpperCase().match(/[A-Z0-9]{3,6}/g) || [];
      const k = m.find((w) => DB[w]); if (k) return k;
    }
    return null;
  }
  function tickerBoleta() { for (const i of document.querySelectorAll('input')) { if (i.closest('#bnr-panel')) continue; const v = (i.value || '').toUpperCase().trim().split(/\s|-/)[0]; if (DB[v]) return v; } return null; }
  function tickerVisible() { // boleta "Instrumento" o encabezado del panel del bono
    const k = tickerBoleta(); if (k) return k;
    for (const el of document.querySelectorAll('div,span,h1,h2,h3,td')) {
      if (el.children.length > 2 || el.closest('#bnr-panel')) continue;
      const t = (el.textContent || '').trim().toUpperCase(); if (DB[t] && el.offsetParent) return t;
    }
    return null;
  }
  function valorJunto(raiz, re) { // busca la etiqueta (p.ej. "Cierre Ant.:") y toma el número de la celda de al lado
    for (const el of raiz.querySelectorAll('div,span,td,th,label')) {
      if (el.children.length || !re.test((el.textContent || '').trim())) continue;
      const s = el.nextElementSibling || (el.parentElement && el.parentElement.nextElementSibling);
      const v = s && num(s.textContent); if (v > 0) return v;
    }
    return NaN;
  }
  function libroDe(k) { // el recuadro del bono: el ancestro del título que también tiene "Cierre Ant."
    for (const el of document.querySelectorAll('div,span,td,h1,h2,h3')) {
      if (el.children.length > 2 || el.closest('#bnr-panel') || !(el.textContent || '').trim().toUpperCase().startsWith(k)) continue;
      let a = el; for (let i = 0; a && i < 6; i++, a = a.parentElement) { const t = a.textContent || ''; if (((t.toUpperCase().match(/[A-Z0-9]{3,6}/g) || []).filter((w) => DB[w] && w !== k)).length) break; if (/Cierre Ant/.test(t)) return a; }
    }
    return null;
  }
  function precioPantalla(k) {
    if (tickerBoleta() === k) for (const lab of document.querySelectorAll('label,div,span')) { // boleta: campo "Precio" con valor cargado
      if (lab.children.length || (lab.textContent || '').trim() !== 'Precio') continue;
      const inp = lab.parentElement && lab.parentElement.querySelector('input'); const v = inp && num(inp.value);
      if (v > 0) return [v, 'boleta'];
    }
    const L = libroDe(k); if (!L) return [NaN, ''];
    const u = valorJunto(L, /^Cierre:?$/); if (u > 0) return [u, 'último'];
    const c = valorJunto(L, /^Cierre Ant\.?:?$/); if (c > 0) return [c, 'cierre anterior'];
    return [NaN, ''];
  }

  // ---------- panel ----------
  const P = document.createElement('div'); P.id = 'bnr-panel';
  P.innerHTML = '<header><span>Bonerío Inside</span><button title="Minimizar">–</button></header><div class="b">Cargando curvas…</div>';
  document.body.appendChild(P);
  const B = P.querySelector('.b');
  P.querySelector('button').onclick = () => P.classList.toggle('min');
  (() => { // arrastrar desde el encabezado
    const h = P.querySelector('header'); let dx, dy;
    h.onmousedown = (e) => { dx = e.clientX - P.offsetLeft; dy = e.clientY - P.offsetTop; document.onmousemove = (m) => { P.style.left = m.clientX - dx + 'px'; P.style.top = m.clientY - dy + 'px'; P.style.right = P.style.bottom = 'auto'; }; document.onmouseup = () => (document.onmousemove = null); };
  })();

  function pintar() {
    if (!activo) { B.innerHTML = '<span class="m">Abrí un bono en Matriz (o hacé clic en una fila) y aparece acá.</span>'; return; }
    const b = DB[activo], f = ajuste(b.grupo, b.ley);
    const inp = B.querySelector('input'); let p = precioManual && inp ? num(inp.value) : NaN, fuente = 'manual';
    if (!(p > 0)) { [p, fuente] = precioPantalla(activo); precioManual = false; }
    const tir = p > 0 ? tirA(b, p) : b.tir, res = f && b.dias > 30 ? (tir - f(b.dias)) * 100 : null;
    const sem = res == null ? '' : Math.abs(res) < 25 ? ['neutral', 'En línea con la curva'] : res > 0 ? ['cheap', 'Barato'] : ['rich', 'Caro'];
    B.innerHTML = `<div class="t">${activo}</div><div class="m">${b.unidad} · cierre Bonerío ${FECHA}</div>
      <div class="g"><span>${b.unidad} al cierre</span><span>${fmt(b.tir)}%</span>
      <span>${b.unidad} a este precio</span><span>${fmt(tir)}%</span>
      <span>Duration mod.</span><span>${fmt(b.md)}</span><span>Días al vto.</span><span>${b.dias}</span></div>
      ${sem ? `<div class="sem ${sem[0]}">${sem[1]}: ${fmt(Math.abs(res), 0)} pb ${res > 0 ? 'arriba' : 'abajo'} de la curva</div>` : ''}
      <label class="m">Precio (${fuente || 'sin precio en pantalla'}): si salgo a…</label>
      <input value="${p > 0 ? fmt(p, 3) : ''}" placeholder="Precio">
      <div class="m" style="margin-top:6px">Estimado con la duration (sin convexidad). <a href="https://boneriolocal.com.ar/#${activo}" target="_blank">Ver en Bonerío</a></div>`;
    const ni = B.querySelector('input');
    ni.onchange = () => { precioManual = true; pintar(); };
  }

  let t, ultBoleta = null; const revisar = (muts) => {
    if (muts.every((m) => P.contains(m.target))) return; // cambios del propio panel
    clearTimeout(t); t = setTimeout(() => {
      const k = tickerBoleta(); if (k && k !== ultBoleta) { ultBoleta = activo = k; precioManual = false; } // cargó otro bono en la boleta
      if (!activo) activo = tickerVisible();
      if (!precioManual && document.activeElement !== B.querySelector('input')) pintar();
    }, 400);
  };
  document.addEventListener('input', (e) => { if (!P.contains(e.target)) revisar([{ target: e.target }]); }, true);
  document.addEventListener('click', (e) => { if (e.target.closest('#bnr-panel')) return; const k = tickerEn(e.target); if (k) { activo = k; precioManual = false; pintar(); } }, true);

  fetch(URL_CURVAS).then((r) => r.json()).then((d) => {
    FECHA = d.fecha;
    for (const [g, l] of Object.entries(d.grupos)) { GRP[g] = l; l.forEach((b) => (DB[b.ticker] = Object.assign({ grupo: g }, b))); }
    activo = tickerVisible(); pintar();
    new MutationObserver(revisar).observe(document.body, { childList: true, subtree: true, characterData: true });
  }).catch(() => (B.textContent = 'No pude traer las curvas de Bonerío.'));
})();
