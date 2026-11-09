/* Bonerío Inside: lee el ticker que el usuario tiene abierto en Matriz y muestra al lado los datos de Bonerío Local.
   El precio sale de la pantalla del propio usuario; Bonerío pone solo cierres, TIRs, duration y la curva (data/api/curvas.json). */
(() => {
  if (window.__bnr) return; window.__bnr = 1;
  const URL_CURVAS = 'https://boneriolocal.com.ar/data/api/curvas.json';
  const CURVA = { usd: 'curva', fija: 'pesos', cer: 'pesos', tamar: 'pesos', dl: 'pesos', dual: 'dsim', on: 'ons', pv: 'pvs' }; // pestaña de Bonerío de cada grupo
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
    if (Math.abs(r - 1) > 0.2) return null; // muy lejos del cierre: otra especie u otra unidad, no se estima
    return bono.tir - ((r - 1) / bono.md) * 100;
  }

  const tk = (w) => { // AL30D / GD30C de Matriz -> [AL30, 'D']
    w = (w || '').toUpperCase(); if (DB[w]) return [w, ''];
    const x = w.slice(-1); return (x === 'D' || x === 'C') && DB[w.slice(0, -1)] ? [w.slice(0, -1), x] : null;
  };
  const DOLAR = { usd: 1, on: 1, pv: 1 };
  const precioVale = (k, suf) => !DOLAR[DB[k].grupo] || suf === 'D'; // en los de dólares Bonerío usa el precio MEP: solo sirve el recuadro de la especie D

  // ---------- lectura de la pantalla de Matriz (heurística: sin selectores fijos, porque Matriz cambia clases) ----------
  function tickerEn(el) {
    for (let i = 0; el && i < 5; i++, el = el.parentElement) {
      const t = (el.innerText || el.value || '').trim();
      if (!t || t.length > 80) continue;
      const m = t.toUpperCase().match(/[A-Z0-9]{3,6}/g) || [];
      for (const w of m) { const r = tk(w); if (r) return r[0]; }
    }
    return null;
  }
  function tickerBoleta() { for (const i of document.querySelectorAll('input')) { if (i.closest('#bnr-panel')) continue; const r = tk((i.value || '').trim().split(/\s|-/)[0]); if (r) return r[0]; } return null; }
  function tickerVisible() { // boleta "Instrumento" o encabezado del panel del bono
    const k = tickerBoleta(); if (k) return k;
    for (const el of document.querySelectorAll('div,span,h1,h2,h3,td')) {
      if (el.children.length > 2 || el.closest('#bnr-panel')) continue;
      const r = tk((el.textContent || '').trim()); if (r && el.offsetParent) return r[0];
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
  function recuadros() { // cada recuadro de Matriz con libro ("Cierre Ant."): el primer ticker que aparece al subir es su título
    const out = [];
    for (const lab of document.querySelectorAll('div,span,td,th')) {
      if (lab.children.length || !/^Cierre Ant\.?:?$/.test((lab.textContent || '').trim()) || lab.closest('#bnr-panel,#bnr-win')) continue;
      let a = lab.parentElement, hit = null;
      for (let i = 0; a && i < 8 && !hit; i++, a = a.parentElement) for (const w of (a.innerText || a.textContent || '').toUpperCase().match(/[A-Z0-9]{3,7}/g) || []) { const r = tk(w); if (r) { hit = { el: a, k: r[0], suf: r[1] }; break; } }
      if (hit && !out.some((o) => o.el === hit.el)) out.push(hit);
    }
    return out;
  }
  function precioDe(c) {
    const u = valorJunto(c.el, /^Cierre:?$/); if (u > 0) return [u, 'último'];
    const v = valorJunto(c.el, /^Cierre Ant\.?:?$/); if (v > 0) return [v, 'cierre anterior'];
    return [NaN, ''];
  }
  function precioPantalla(k) {
    if (tickerBoleta() === k) for (const lab of document.querySelectorAll('label,div,span')) { // boleta: campo "Precio" con valor cargado
      if (lab.children.length || (lab.textContent || '').trim() !== 'Precio') continue;
      const inp = lab.parentElement && lab.parentElement.querySelector('input'); const v = inp && num(inp.value);
      if (v > 0) return [v, 'boleta'];
    }
    const c = recuadros().find((r) => r.k === k && precioVale(k, r.suf));
    return c ? precioDe(c) : [NaN, ''];
  }

  // ---------- filas de Bonerío adentro de cada recuadro de Matriz, debajo de "Pos / P&L" (copian su estilo) ----------
  const CORTA = { TIR: 'TIR', TEA: 'TEA', 'TNA real': 'TIR real', 'Margen s/ TAMAR': 'Margen', 'TNA USD': 'TNA USD' };
  const MET = {
    tir: ['TIR a este precio', (b, x) => [CORTA[b.unidad] || 'TIR', fmt(x.tir) + '%']],
    tirc: ['TIR al cierre', (b) => [(CORTA[b.unidad] || 'TIR') + ' cierre', fmt(b.tir) + '%']],
    md: ['Duration modificada', (b) => ['DM', fmt(b.md)]],
    curva: ['Contra la curva (pb)', (b, x) => ['vs curva', x.res == null ? '-' : (x.res > 0 ? '+' : '') + fmt(x.res, 0) + ' pb', x.res == null || Math.abs(x.res) < 25 ? '' : x.res > 0 ? '#3ddc84' : '#ff6b6b']],
    dias: ['Días al vencimiento', (b) => ['Días', String(b.dias)]],
  };
  let CFG = { on: true, m: ['tir', 'md', 'curva', 'dias'] };
  try { CFG = Object.assign(CFG, JSON.parse(localStorage.getItem('bnrCfg') || '{}')); } catch (e) { }
  const guardar = () => { try { localStorage.setItem('bnrCfg', JSON.stringify(CFG)); } catch (e) { } };
  function calc(b, p) {
    const t = p > 0 ? tirA(b, p) : null, tir = t == null ? b.tir : t, f = ajuste(b.grupo, b.ley);
    return { tir, res: f && b.dias > 30 ? (tir - f(b.dias)) * 100 : null };
  }
  function inyectar() {
    for (const c of recuadros()) {
      const viejas = [...c.el.querySelectorAll('[data-bnr]')];
      if (!CFG.on || !CFG.m.length) { viejas.forEach((r) => r.remove()); continue; }
      const lab = [...c.el.querySelectorAll('div,span,td')].find((e) => !e.children.length && /^P&L:?$/.test((e.textContent || '').trim()) && !e.closest('[data-bnr]'));
      let row = lab && lab.parentElement; while (row && row !== c.el && !/Pos/.test(row.textContent || '')) row = row.parentElement;
      if (!row || row === c.el) continue;
      const b = DB[c.k], [p] = precioVale(c.k, c.suf) ? precioDe(c) : [NaN], x = calc(b, p), cel = CFG.m.map((m) => MET[m][1](b, x)), n = Math.ceil(cel.length / 2);
      if (viejas.length !== n) { viejas.forEach((r) => r.remove()); let ant = row; for (let i = 0; i < n; i++) { const r = row.cloneNode(true); r.setAttribute('data-bnr', '1'); r.title = 'Bonerío Local'; ant.after(r); ant = r; } }
      [...c.el.querySelectorAll('[data-bnr]')].forEach((r, i) => {
        const hojas = [...r.querySelectorAll('*')].filter((e) => !e.children.length); if (hojas.length < 4) return;
        [cel[2 * i], cel[2 * i + 1]].forEach((v, j) => {
          const [l, val, col] = v || ['', '']; const L = hojas[2 * j], V = hojas[2 * j + 1];
          if (L.textContent !== (l ? l + ':' : '')) L.textContent = l ? l + ':' : '';
          if (V.textContent !== val) V.textContent = val; if (V.style.color !== (col || '')) V.style.color = col || '';
        });
      });
    }
  }

  // ---------- panel ----------
  const P = document.createElement('div'); P.id = 'bnr-panel';
  P.innerHTML = '<header><span>Bonerío Inside</span><span><button class="cf" title="Datos en los recuadros de Matriz">⚙</button><button class="mn" title="Minimizar">–</button></span></header><div class="cfg" hidden></div><div class="q"><input class="bus" placeholder="Escribí un bono (AL30, TMVE8…)" list="bnr-tk"><datalist id="bnr-tk"></datalist></div><div class="b">Cargando curvas…</div>';
  document.body.appendChild(P);
  const B = P.querySelector('.b');
  P.querySelector('.mn').onclick = () => P.classList.toggle('min');
  const CF = P.querySelector('.cfg');
  function pintarCfg() {
    CF.innerHTML = `<label><input type="checkbox" data-on ${CFG.on ? 'checked' : ''}> Mostrar en los recuadros de Matriz</label>` +
      Object.keys(MET).map((k) => `<label><input type="checkbox" data-m="${k}" ${CFG.m.includes(k) ? 'checked' : ''}> ${MET[k][0]}</label>`).join('');
    CF.querySelectorAll('input').forEach((i) => (i.onchange = () => {
      if (i.hasAttribute('data-on')) CFG.on = i.checked; else CFG.m = Object.keys(MET).filter((k) => CF.querySelector(`[data-m="${k}"]`).checked);
      guardar(); inyectar();
    }));
  }
  P.querySelector('.cf').onclick = () => { CF.hidden = !CF.hidden; if (!CF.hidden) pintarCfg(); };
  const arrastrar = (W) => { // mover desde el encabezado
    const h = W.querySelector('header'); let dx, dy;
    h.onmousedown = (e) => { if (e.target.tagName === 'BUTTON') return; dx = e.clientX - W.offsetLeft; dy = e.clientY - W.offsetTop; document.onmousemove = (m) => { W.style.left = m.clientX - dx + 'px'; W.style.top = m.clientY - dy + 'px'; W.style.right = W.style.bottom = 'auto'; }; document.onmouseup = () => (document.onmousemove = null); };
  };
  arrastrar(P);
  const BUS = P.querySelector('.bus');
  BUS.onkeydown = (e) => { if (e.key === 'Enter') BUS.onchange(); };
  BUS.onchange = () => { const k = BUS.value.toUpperCase().trim(); if (!k) return; activo = k; precioManual = false; BUS.value = ''; pintar(); };

  // ---------- ventana flotante con la ficha, la curva o el portfolio de Bonerío (la sección sola, como en el Dashboard) ----------
  const SITE = 'https://boneriolocal.com.ar/', VIS = { ficha: 'Ficha', curva: 'Curva', port: 'Portfolio' };
  let W = null, vista = 'ficha';
  function ventana(v) {
    vista = v || vista;
    if (!W) {
      W = document.createElement('div'); W.id = 'bnr-win';
      W.innerHTML = '<header><span class="tt"></span><span class="tabs"></span><button class="x" title="Cerrar">✕</button></header><div class="wb"><iframe allow="clipboard-write"></iframe></div>';
      document.body.appendChild(W); arrastrar(W);
      W.querySelector('.x').onclick = () => { W.remove(); W = null; };
    }
    const g = DB[activo] && DB[activo].grupo, tab = vista === 'ficha' ? 'bono' : vista === 'curva' ? CURVA[g] || 'curva' : 'port';
    W.querySelector('.tt').textContent = activo || '';
    W.querySelector('.tabs').innerHTML = Object.keys(VIS).filter((x) => x !== 'curva' || g).map((x) => `<button data-v="${x}" class="${x === vista ? 'on' : ''}">${VIS[x]}</button>`).join('');
    W.querySelectorAll('.tabs button').forEach((x) => (x.onclick = () => ventana(x.dataset.v)));
    W.querySelector('iframe').src = SITE + '?emb=sec&tab=' + tab + '&id=' + tab + (vista === 'ficha' && activo ? '#ficha=' + activo + '&n=' + Date.now() : '');
  }

  function pintar() {
    if (!activo) { B.innerHTML = '<span class="m">Abrí un bono en Matriz (o hacé clic en una fila) y aparece acá.</span>'; return; }
    const BT = (c) => `<div class="bt">${c ? '<button data-v="ficha">Ficha</button><button data-v="curva">Curva</button>' : '<button data-v="ficha">Ficha</button>'}<button data-v="port">Portfolio</button></div>`;
    const enlazar = () => B.querySelectorAll('.bt button').forEach((x) => (x.onclick = () => ventana(x.dataset.v)));
    if (!DB[activo]) { B.innerHTML = `<div class="t">${activo}</div><div class="m">Sin datos de curva para este bono: abrí su ficha.</div>` + BT(false); enlazar(); if (W && W.querySelector('.tt').textContent !== activo) ventana(); return; }
    const b = DB[activo], f = ajuste(b.grupo, b.ley);
    const inp = B.querySelector('input'); let p = precioManual && inp ? num(inp.value) : NaN, fuente = 'manual';
    if (!(p > 0)) { [p, fuente] = precioPantalla(activo); precioManual = false; }
    const t0 = p > 0 ? tirA(b, p) : null, tir = t0 == null ? b.tir : t0, res = f && b.dias > 30 ? (tir - f(b.dias)) * 100 : null;
    const sem = res == null ? '' : Math.abs(res) < 25 ? ['neutral', 'En línea con la curva'] : res > 0 ? ['cheap', 'Barato'] : ['rich', 'Caro'];
    B.innerHTML = `<div class="t">${activo}</div><div class="m">${b.unidad} · cierre Bonerío ${FECHA}</div>
      <div class="g"><span>${b.unidad} al cierre</span><span>${fmt(b.tir)}%</span>
      <span>${b.unidad} a este precio</span><span>${fmt(tir)}%</span>
      <span>Duration mod.</span><span>${fmt(b.md)}</span><span>Días al vto.</span><span>${b.dias}</span></div>
      ${sem ? `<div class="sem ${sem[0]}">${sem[1]}: ${fmt(Math.abs(res), 0)} pb ${res > 0 ? 'arriba' : 'abajo'} de la curva</div>` : ''}
      <label class="m">Precio (${fuente || 'sin precio en pantalla'}): si salgo a…</label>
      <input value="${p > 0 ? fmt(p, 3) : ''}" placeholder="Precio">
      <div class="m" style="margin-top:4px">Estimado con la duration (sin convexidad).</div>
      ${BT(true)}`;
    enlazar();
    if (W && W.querySelector('.tt').textContent !== activo) ventana(); // la ventana sigue al bono
    const ni = B.querySelector('input');
    ni.onchange = () => { precioManual = true; pintar(); };
  }

  let t, ultBoleta = null; const revisar = (muts) => {
    const nuestro = (m) => { const e = m.target.nodeType === 1 ? m.target : m.target.parentElement; return !e || P.contains(e) || (W && W.contains(e)) || e.closest('[data-bnr]'); };
    if (muts.every(nuestro)) return; // cambios del propio panel o de nuestras filas
    clearTimeout(t); t = setTimeout(() => {
      const k = tickerBoleta(); if (k && k !== ultBoleta) { ultBoleta = activo = k; precioManual = false; } // cargó otro bono en la boleta
      if (!activo) activo = tickerVisible();
      if (!precioManual && document.activeElement !== B.querySelector('input')) pintar();
      inyectar();
    }, 400);
  };
  document.addEventListener('input', (e) => { if (!P.contains(e.target)) revisar([{ target: e.target }]); }, true);
  document.addEventListener('click', (e) => { if (e.target.closest('#bnr-panel')) return; const k = tickerEn(e.target); if (k) { activo = k; precioManual = false; pintar(); } }, true);

  fetch(URL_CURVAS).then((r) => r.json()).then((d) => {
    FECHA = d.fecha;
    for (const [g, l] of Object.entries(d.grupos)) { GRP[g] = l; l.forEach((b) => (DB[b.ticker] = Object.assign({ grupo: g }, b))); }
    P.querySelector('#bnr-tk').innerHTML = Object.keys(DB).sort().map((k) => `<option value="${k}">`).join('');
    activo = tickerVisible(); pintar(); inyectar();
    new MutationObserver(revisar).observe(document.body, { childList: true, subtree: true, characterData: true });
  }).catch(() => (B.textContent = 'No pude traer las curvas de Bonerío.'));
})();
