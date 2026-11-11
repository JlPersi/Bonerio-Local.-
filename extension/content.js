/* Bonerío Inside: lee el ticker que el usuario tiene abierto en Matriz y muestra al lado los datos de Bonerío Local.
   El precio sale de la pantalla del propio usuario; Bonerío pone solo cierres, TIRs, duration y la curva (data/api/curvas.json). */
(() => {
  if (window.__bnr) return; window.__bnr = 1;
  const URL_CURVAS = 'https://boneriolocal.com.ar/data/api/curvas.json', DATA = 'https://boneriolocal.com.ar/data/';
  const TOK = /[A-Z]{3}\/[A-Z]{3}\d{2}|[A-Z0-9]{3,7}/g; // tickers: DLR/NOV26 o AL30, GGAL, TMVE8…
  const MESES = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC'];
  const diasA = (f) => Math.max(1, Math.round((new Date(f + 'T12:00:00') - new Date()) / 864e5));
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
  const aMatriz = (k) => { // futuros con el nombre de Matriz: DLR/NOV26 (el gráfico de Bonerío dice «NOV26» o «DLR NOV26»; el archivo, DLR112026)
    k = String(k || '').toUpperCase().trim(); let m = /^(?:DLR[ \/])?([A-Z]{3})(\d{2})$/.exec(k);
    if (m && MESES.includes(m[1]) && !DB[k]) return 'DLR/' + m[1] + m[2];
    m = /^DLR(\d\d)(\d{4})$/.exec(k); return m && +m[1] >= 1 && +m[1] <= 12 ? 'DLR/' + MESES[+m[1] - 1] + m[2].slice(2) : k;
  };
  const precioVale = (k, suf) => (DB[k].tipo === 'acc' ? !suf : !DOLAR[DB[k].grupo] || suf === 'D'); // en los de dólares Bonerío usa el precio MEP: solo sirve el recuadro de la especie D

  // ---------- lectura de la pantalla de Matriz (heurística: sin selectores fijos, porque Matriz cambia clases) ----------
  function tickerEn(el) {
    for (let i = 0; el && i < 5; i++, el = el.parentElement) {
      const t = (el.innerText || el.value || '').trim();
      if (!t || t.length > 80) continue;
      const m = t.toUpperCase().match(TOK) || [];
      for (const w of m) { const r = tk(w); if (r) return r[0]; }
    }
    return null;
  }
  function tickerBoleta() { for (const i of document.querySelectorAll('input')) { if (i.closest('#bnr-panel')) continue; const r = tk((i.value || '').trim().split(/\s|-/)[0]); if (r) return r[0]; } return null; }
  function tickerVisible() { // boleta "Instrumento" o encabezado del panel del bono
    const k = tickerBoleta(); if (k) return k;
    let acc = null;
    for (const el of document.querySelectorAll('div,span,h1,h2,h3,td')) {
      if (el.children.length > 2 || el.closest('#bnr-panel')) continue;
      const r = tk((el.textContent || '').trim()); if (r && el.offsetParent) { if (DB[r[0]].tipo !== 'acc') return r[0]; acc = acc || r[0]; }
    }
    return acc; // una acción solo si no hay bonos ni futuros a la vista (BYMA también es un botón de Matriz)
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
    for (const lab of document.querySelectorAll('body *')) {
      if (lab.children.length || !/^Cierre\s+Ant\.?\s*:?$/i.test((lab.textContent || '').trim()) || lab.closest('#bnr-panel,#bnr-win,.bnr-pin')) continue;
      let a = lab.parentElement, hit = null;
      for (let i = 0; a && i < 16 && !hit; i++, a = a.parentElement) { // sube hasta el recuadro: sin salir a otro recuadro ni al resto de Matriz, y sin leer botones (BYMA, MERV… son botones de Matriz)
        const tx = a.innerText || a.textContent || ''; if (tx.length > 3000 || (i && [...a.querySelectorAll('*')].filter((x) => !x.children.length && /^Cierre\s+Ant\.?\s*:?$/i.test((x.textContent || '').trim())).length > 1)) break;
        for (const el of a.querySelectorAll('*')) { if (el.children.length || el.closest('button,a,nav,#bnr-panel,#bnr-win,.bnr-pin,[data-bnr]')) continue; const w = ((el.textContent || '').trim().toUpperCase().match(TOK) || [])[0], r = w && tk(w); if (r) { hit = { el: a, k: r[0], suf: r[1] }; break; } }
      }
      if (hit && !out.some((o) => o.el === hit.el)) out.push(hit);
    }
    return out;
  }
  function precioDe(c) {
    const u = valorJunto(c.el, /^Cierre:?$/); if (u > 0) return [u, 'último'];
    const v = valorJunto(c.el, /^Cierre Ant\.?:?$/); if (v > 0) return [v, 'cierre anterior'];
    return [NaN, ''];
  }
  function libro(c, ref) { // la mejor punta del libro del recuadro: [compra, venta]. Columnas por el encabezado (Compra / Venta) o, si no hay, Cant. | Compra | Venta | Cant.
    let bi = 1, ai = 2;
    for (const row of c.el.querySelectorAll('tr,div')) {
      const ch = [...row.children]; if (ch.length < 4 || ch.length > 6 || ch.some((x) => x.children.length > 1)) continue;
      const t = ch.map((x) => (x.textContent || '').trim());
      if (t.some((x) => /[a-z]/i.test(x))) { const B = t.findIndex((x) => /^(precio\s*)?compra$|^bid$/i.test(x)), A = t.findIndex((x) => /^(precio\s*)?venta$|^ask$|^oferta$/i.test(x)); if (B >= 0 && A >= 0) { bi = B; ai = A; } continue; }
      const v = t.map((x) => (/^[\d.,]+$/.test(x) ? num(x) : NaN)), ok = (x) => x > 0 && (!(ref > 0) || Math.abs(x / ref - 1) < 0.2), b = v[bi], a = v[ai];
      if (!ok(b) && !ok(a)) continue; if (ok(b) && ok(a) && b > a) continue;
      return [ok(b) ? b : NaN, ok(a) ? a : NaN];
    }
    return [NaN, NaN];
  }
  function pantalla() { // los precios que muestra tu Matriz, en vivo: {AL30: {ci: [último, compra, venta], h: [...]}}; recuadros con libro y, si no, el Mini-Panel (24 hs)
    const o = {};
    for (const c of recuadros()) {
      const s = c.k + c.suf, pz = plazoDe(c.el) === 'ci' ? 'ci' : 'h', u = valorJunto(c.el, /^Cierre:?$/), [b, a] = libro(c, u > 0 ? u : valorJunto(c.el, /^Cierre Ant\.?:?$/));
      if (u > 0 || b > 0 || a > 0) (o[s] = o[s] || {})[pz] = [u > 0 ? u : 0, b > 0 ? b : 0, a > 0 ? a : 0];
    }
    for (const el of document.querySelectorAll('body *')) {
      if (el.children.length) continue; const w = (el.textContent || '').trim().toUpperCase(); if (w.length < 3 || w.length > 8 || !tk(w) || (o[w] && o[w].h)) continue;
      if (!el.getClientRects().length || el.closest('#bnr-panel,#bnr-win,.bnr-pin,.bnr-sens,[data-bnr],[role=listbox],[role=option]')) continue;
      const v = num(ultimoDe(el, w)); if (v > 0) (o[w] = o[w] || {}).h = [v, 0, 0];
    }
    return o;
  }
  function precioPantalla(k) {
    if (tickerBoleta() === k) for (const lab of document.querySelectorAll('label,div,span')) { // boleta: campo "Precio" con valor cargado
      if (lab.children.length || (lab.textContent || '').trim() !== 'Precio') continue;
      const inp = lab.parentElement && lab.parentElement.querySelector('input'); const v = inp && num(inp.value);
      if (v > 0) return [v, 'boleta'];
    }
    const c = recuadros().find((r) => r.k === k && precioVale(k, r.suf));
    if (c) return precioDe(c);
    const m = !DOLAR[DB[k].grupo] || DB[k].tipo === 'acc' ? num(ultimoFila(k)) : NaN; return m > 0 ? [m, 'último'] : [NaN, '']; // si no hay recuadro, el Mini-Panel
  }

  // ---------- filas de Bonerío adentro de cada recuadro de Matriz, debajo de "Pos / P&L" (copian su estilo) ----------
  const CORTA = { TIR: 'TIR', TEA: 'TEA', 'TNA real': 'TIR real', 'Margen s/ TAMAR': 'Margen', 'TNA USD': 'TNA USD' };
  const MET = {
    tir: ['TIR a este precio', (b, x) => [CORTA[b.unidad] || 'TIR', fmt(x.tir) + '%']],
    tirc: ['TIR al cierre', (b) => [(CORTA[b.unidad] || 'TIR') + ' cierre', fmt(b.tir) + '%']],
    md: ['Duration modificada', (b) => ['DM', fmt(b.md)]],
    curva: ['Contra la curva (pb)', (b, x) => ['vs curva', x.res == null ? '-' : (x.res > 0 ? '+' : '') + fmt(x.res, 0) + ' pb', '']], // solo el dato: caro o barato depende de la curva que uno tome
    dias: ['Días al vencimiento', (b) => ['Días', String(b.dias)]],
  };
  let CFG = { on: true, m: ['tir', 'md', 'curva', 'dias'] };
  try { CFG = Object.assign(CFG, JSON.parse(localStorage.getItem('bnrCfg') || '{}')); } catch (e) { }
  const guardar = () => { try { localStorage.setItem('bnrCfg', JSON.stringify(CFG)); } catch (e) { } };
  function calc(b, p) {
    const t = p > 0 ? tirA(b, p) : null, tir = t == null ? b.tir : t, f = ajuste(b.grupo, b.ley);
    return { tir, res: f && b.dias > 30 ? (tir - f(b.dias)) * 100 : null };
  }
  function fut(b, p) { const r = (p > 0 ? p : b.precio) / b.spot, d = diasA(b.vto); return { tna: (r - 1) * 365 / d * 100, dev: (Math.pow(r, 30 / d) - 1) * 100, d }; }
  function filas(b, p) {
    if (b.tipo === 'fut') { const x = fut(b, p); return [['TNA impl.', fmt(x.tna) + '%'], ['Dev. mens.', fmt(x.dev) + '%'], ['Días', String(x.d)], ['A3500', fmt(b.spot)]]; }
    if (b.tipo === 'acc') { ratios(); return [['P/E', fmt(b.pe)], ['P/VL', fmt(b.pvl)], ['EV/EBITDA', fmt(b.ev)], ['Beta', fmt(b.beta)]]; }
    const x = calc(b, p); return CFG.m.map((m) => MET[m][1](b, x));
  }
  let RAT = null; function ratios() { // P/E, P/VL y EV/EBITDA: el archivo es grande, se trae solo cuando aparece una acción
    if (RAT) return; RAT = fetch(DATA + 'acciones/ratios.json').then((r) => r.json()).then((d) => {
      for (const [k, v] of Object.entries(d.t || {})) { const u = (v.serie || [])[v.serie.length - 1]; if (DB[k] && u) Object.assign(DB[k], { pe: u[1], pvl: u[2], ev: u[3] }); }
      pintar(); inyectar();
    }).catch(() => {});
  }
  function inyectar() {
    for (const c of recuadros()) {
      const viejas = [...c.el.querySelectorAll('[data-bnr]')];
      if (!CFG.on || !CFG.m.length) { viejas.forEach((r) => r.remove()); continue; }
      const lab = [...c.el.querySelectorAll('*')].find((e) => !e.children.length && /^P\s*&\s*L\s*:?$/i.test((e.textContent || '').trim()) && !e.closest('[data-bnr]'));
      let row = lab && lab.parentElement; while (row && row !== c.el && !/Pos/.test(row.textContent || '')) row = row.parentElement;
      if (!row || row === c.el || /Cierre/.test(row.textContent || '')) continue; // la fila de Pos / P&L sola, no el recuadro entero
      const b = DB[c.k], [p] = precioVale(c.k, c.suf) || (c.suf === 'C' && DOLAR[DB[c.k].grupo]) ? precioDe(c) : [NaN] /* D (MEP) y C (cable): la TIR a ese precio en dólares; en pesos, la del cierre */, cel = filas(b, p), n = Math.ceil(cel.length / 2);
      if (!n) continue;
      if (viejas.length !== n) { viejas.forEach((r) => r.remove()); let ant = row; for (let i = 0; i < n; i++) { const r = row.cloneNode(true); r.setAttribute('data-bnr', '1'); r.style.borderTop = '1px solid rgba(255,255,255,.45)'; r.title = 'Bonerío Local'; ant.after(r); ant = r; } }
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
  P.innerHTML = '<header><span>Bonerío Inside</span><span><button class="pin" title="Fijar este bono en una ficha aparte (podés abrir varias)">📌</button><button class="cf" title="Datos en los recuadros de Matriz">⚙</button><button class="mn" title="Minimizar">–</button></span></header><div class="cfg" hidden></div><div class="q"><input class="bus" placeholder="Escribí un bono (AL30, TMVE8…)" list="bnr-tk"><datalist id="bnr-tk"></datalist></div><div class="b">Cargando curvas…</div><div class="est" hidden></div>';
  document.body.appendChild(P);
  const B = P.querySelector('.b');
  P.querySelector('.mn').onclick = () => P.classList.toggle('min');
  const CF = P.querySelector('.cfg');
  function pintarCfg() {
    CF.innerHTML = `<label><input type="checkbox" data-on ${CFG.on ? 'checked' : ''}> Mostrar en los recuadros de Matriz</label>` +
      Object.keys(MET).map((k) => `<label><input type="checkbox" data-m="${k}" ${CFG.m.includes(k) ? 'checked' : ''}> ${MET[k][0]}</label>`).join('') +
      `<label style="margin-top:4px">Cantidad por defecto en la boleta <input type="number" min="0" data-q value="${CFG.qty || ''}" ${CFG.qm === 'm' ? 'disabled' : ''} style="width:90px;margin-left:auto"></label>` +
      `<label><input type="checkbox" data-qm ${CFG.qm === 'm' ? 'checked' : ''}> No cargar la cantidad (la pongo a mano)</label>` +
      `<label><input type="checkbox" data-pm ${CFG.pm === 'm' ? 'checked' : ''}> No cargar el precio de mercado (lo pongo a mano)</label>` +
      `<label><input type="checkbox" data-alp ${CFG.alp !== false ? 'checked' : ''}> Avisarme (con sonido) cuando convenga un pase en mis especies de Pases</label>` +
      `<label>Moneda en la boleta (bonos en dólares) <select data-mon style="margin-left:auto">${[['', 'Pesos'], ['D', 'MEP (D)'], ['C', 'CCL (C)']].map(([v, t]) => `<option value="${v}" ${(CFG.mon || '') === v ? 'selected' : ''}>${t}</option>`).join('')}</select></label>`;
    CF.querySelectorAll('input,select').forEach((i) => (i.onchange = () => {
      if (i.hasAttribute('data-alp')) { CFG.alp = i.checked; if (i.checked) { sonar(); if (!W) ventana(null, null, true); } } else if (i.hasAttribute('data-mon')) CFG.mon = i.value; else if (i.hasAttribute('data-q')) CFG.qty = +i.value || 0; else if (i.hasAttribute('data-pm')) CFG.pm = i.checked ? 'm' : ''; else if (i.hasAttribute('data-qm')) { CFG.qm = i.checked ? 'm' : ''; CF.querySelector('[data-q]').disabled = i.checked; } else if (i.hasAttribute('data-on')) CFG.on = i.checked; else CFG.m = Object.keys(MET).filter((k) => CF.querySelector(`[data-m="${k}"]`).checked);
      guardar(); inyectar(); phPins(); if (W) W.querySelectorAll('.subs .mon button').forEach((y) => y.classList.toggle('on', y.dataset.mon === (CFG.mon || '')));
    }));
  }
  P.querySelector('.cf').onclick = () => { CF.hidden = !CF.hidden; if (!CF.hidden) pintarCfg(); };
  const arrastrar = (W) => { // mover desde el encabezado
    const h = W.querySelector('header'); let dx, dy;
    h.onmousedown = (e) => { if (e.target.tagName === 'BUTTON' || e.target.tagName === 'SELECT' || W.classList.contains('fijo')) return; dx = e.clientX - W.offsetLeft; dy = e.clientY - W.offsetTop; document.onmousemove = (m) => { W.style.left = m.clientX - dx + 'px'; W.style.top = m.clientY - dy + 'px'; W.style.right = W.style.bottom = 'auto'; }; document.onmouseup = () => { document.onmousemove = document.onmouseup = null; if (W.id === 'bnr-win') recordar(); }; };
  };
  arrastrar(P);
  // ---------- fichas fijas: un bono por ficha, todas las que quieras; se actualizan con el precio de la pantalla ----------
  const PINS = new Map();
  function fichaHTML(k, pf) { // pf: el precio escrito en la ficha fija (si vale para la cuenta de Bonerío: pesos, o MEP en los de dólares)
    const b = DB[k]; if (!b) return '<div class="m">Sin datos en Bonerío</div>';
    if (b.tipo === 'acc') return `<div class="g"><span>Cierre</span><span>$ ${fmt(b.precio)}</span><span>Beta</span><span>${fmt(b.beta)}</span></div>`;
    const [p] = pf > 0 && (!DOLAR[b.grupo] || CFG.mon === 'D') ? [pf] : precioPantalla(k);
    if (b.tipo === 'fut') { const x = fut(b, p); return `<div class="g"><span>Precio</span><span>${p > 0 ? fmt(p, 2) : '-'}</span><span>TNA impl.</span><span>${fmt(x.tna)}%</span><span>Dev. mens.</span><span>${fmt(x.dev)}%</span><span>Días</span><span>${x.d}</span></div>`; }
    const f = ajuste(b.grupo, b.ley), t0 = p > 0 ? tirA(b, p) : null, tir = t0 == null ? b.tir : t0, res = f && b.dias > 30 ? (tir - f(b.dias)) * 100 : null;
    return `<div class="g"><span>Precio</span><span>${p > 0 ? fmt(p, 3) : '-'}</span><span>${b.unidad} a este precio</span><span>${fmt(tir)}%</span><span>${b.unidad} al cierre</span><span>${fmt(b.tir)}%</span><span>Duration mod.</span><span>${fmt(b.md)}</span></div>`;
  }
  const guardarPins = () => { try { localStorage.setItem('bnrPins', JSON.stringify([...PINS].map(([k, D]) => ({ k, q: +D.querySelector('.pq').value || 0, p: pinP(D), l: D.offsetLeft, t: D.offsetTop })))); } catch (er) { } };
  const pinP = (D) => { const v = num((D.querySelector('.pp') || {}).value); return v > 0 ? v : 0; }; // precio escrito en la ficha (Matriz: coma decimal)
  const phPins = () => PINS.forEach((D) => { // vacío = lo que diga ⚙: la cantidad por defecto o a mano; el precio de mercado o a mano
    D.querySelector('.pq').placeholder = CFG.qm !== 'm' && CFG.qty > 0 ? 'por def. ' + CFG.qty : 'a mano'; D.querySelector('.pp').placeholder = CFG.pm === 'm' ? 'a mano' : 'mercado'; });
  function fijar(k, q, pos) {
    if (!k) return; if (PINS.has(k)) { PINS.get(k).style.outline = '2px solid #ffc107'; setTimeout(() => (PINS.get(k).style.outline = ''), 600); return; }
    const D = document.createElement('div'), n = PINS.size; D.className = 'bnr-pin';
    D.style.top = 70 + (n % 6) * 28 + 'px'; D.style.right = 280 + (n % 6) * 24 + 'px';
    D.innerHTML = `<header><span class="pk" title="Ver en el panel">${k}</span><button class="x" title="Cerrar">✕</button></header><div class="pb"></div><label class="pql">Nominales <input class="pq" type="number" min="0" step="1" value="${q > 0 ? q : ''}"></label><label class="pql">Precio <input class="pp" type="text" inputmode="decimal" value="${pos && pos.p > 0 ? String(pos.p).replace('.', ',') : ''}"></label><div class="bt"><button data-v="datos" title="Datos del bono y calculadora">Datos ▾</button><button data-v="curva">Curva</button><button data-v="boleta" title="Cargar en la boleta de Matriz">Boleta</button></div><div class="dx" hidden></div>`;
    if (pos) Object.assign(D.style, { left: pos.l + 'px', top: pos.t + 'px', right: 'auto' });
    document.body.appendChild(D); arrastrar(D); PINS.set(k, D); guardarPins();
    D.querySelector('.pq').onchange = guardarPins; D.addEventListener('mouseup', guardarPins); phPins();
    D.querySelector('.pp').onchange = () => { guardarPins(); D.querySelector('.pb').innerHTML = fichaHTML(k, pinP(D)); }; // la TIR de la ficha, a ese precio
    D.querySelector('.pb').innerHTML = fichaHTML(k, pinP(D));
    D.querySelector('.x').onclick = () => { D.remove(); PINS.delete(k); guardarPins(); };
    D.querySelector('.pk').onclick = () => { activo = k; precioManual = false; pintar(); };
    D.querySelector('[data-v=datos]').onclick = (e) => { const x = D.querySelector('.dx'); x.hidden = !x.hidden; e.target.textContent = x.hidden ? 'Datos ▾' : 'Datos ▴'; if (!x.hidden) montarDatos(x, k); };
    D.querySelector('[data-v=boleta]').onclick = () => aBoleta(k, +D.querySelector('.pq').value || 0); // con los nominales y el precio de esta ficha (si están escritos)
    D.querySelector('[data-v=curva]').onclick = () => { activo = k; precioManual = false; curvaG = null; pintar(); ventana('curva'); };
  }
  const refrescarPins = () => PINS.forEach((D, k) => { const h = fichaHTML(k, pinP(D)), pb = D.querySelector('.pb'); if (pb.innerHTML !== h) pb.innerHTML = h; });
  P.querySelector('.pin').onclick = () => fijar(activo);
  if (chrome.runtime && chrome.runtime.onMessage) chrome.runtime.onMessage.addListener((m) => { if (m && m.t === 'toggle') { const v = P.style.display === 'none'; P.style.display = v ? '' : 'none'; if (W && !v) W.style.display = 'none'; } }); // el ícono de la extensión
  const BUS = P.querySelector('.bus');
  BUS.onkeydown = (e) => { if (e.key === 'Enter') BUS.onchange(); };
  BUS.onchange = () => { const k = BUS.value.toUpperCase().trim(); if (!k) return; activo = k; precioManual = false; BUS.value = ''; pintar(); };

  // ---------- ventana flotante con la ficha, la curva o el portfolio de Bonerío (la sección sola, como en el Dashboard) ----------
  const SITE = 'https://boneriolocal.com.ar/';
  const CURVAS = { fut: ['tfut', 'tfS1'], usd: ['curva', 'yieldCurveContainer'], fija: ['pesos', 'pcard1'], cer: ['pesos', 'pcard3'], tamar: ['pesos', 'pcard4'], dl: ['pesos', 'pcard5'], dual: ['pesos', 'pcard6'], on: ['ons', 'onsC'], pv: ['pvs', 'pvsC'] };
  // solapas de la ventana: [nombre, [[subsolapa, pestaña de Bonerío, sección, subpestaña interna]]]; la sección se muestra sola (modo ?emb=sec del Dashboard)
  const VIS = {
    curva: ['Curva', (g) => [['', ...(CURVAS[g] || CURVAS.usd)]]],
    brc: ['Brecha y canje', () => [['Ratios', 'brc', 'brA'], ['Todos ahora', 'brc', 'brB']]],
    cim: ['Pases', () => [['', 'cim', 'cim']]], // el monitor y la tabla de especies (con un botón por pata)
    exp: ['Expectativas', () => [['Inflación', 'expi', 'thBBi'], ['Devaluación', 'expd', 'thBBd'], ['Fwd tasa fija', 'expf', 'expfW1'], ['Fwd CER', 'expf', 'expfW2'], ['Fwd TAMAR', 'expf', 'expfW3'], ['Fwd DL', 'expf', 'expfW4']]],
  };
  const NOM_CURVA = { usd: 'Soberanos USD', fija: 'Lecaps / Boncaps', cer: 'CER', tamar: 'TAMAR', dl: 'Dollar linked', dual: 'Duales', on: 'ONs', pv: 'Provinciales', fut: 'Futuros de dólar' };
  let curvaG = null; // la curva elegida en el desplegable (null: la del bono activo)
  const PLAZO = { fija: 'psX1', cer: 'psX2', tamar: 'psX3', dl: 'psX4', dual: 'psX5' }; // el «Plazo máximo» de cada curva en pesos
  const MODELO = { usd: 'usdCurveModel', fija: 'psK1', cer: 'psK2', tamar: 'psK3', dl: 'psK4', dual: 'psK5' }; // el «Modelo de curva» de cada una
  const AJUSTES = [['auto', 'Mejor ajuste'], ['log', 'Logarítmica'], ['sqrt', 'Raíz cuadrada'], ['lin', 'Lineal'], ['quad', 'Cuadrática'], ['ns', 'Nelson-Siegel']];
  const plazo = (g) => { // al cargar una curva: plazo máximo (por defecto todos los bonos: DICP, PARP…), modelo elegido y burbujas de volumen
    const f = W && LISTO && W.querySelector('iframe'); if (!f) return; const w = f.contentWindow;
    if (PLAZO[g]) w.postMessage({ t: 'bnrSel', id: PLAZO[g], v: (CFG.px || {})[g] || '99999' }, '*');
    const m = (CFG.mdl || {})[g]; if (MODELO[g] && m) w.postMessage({ t: 'bnrSel', id: MODELO[g], v: m }, '*');
    w.postMessage({ t: 'bnrBub', on: !!CFG.bub }, '*');
  };
  const SOLO_GRAF = { curva: 1, tfut: 1, sint: 1, exp: 1 };
  const SIGUE = { ficha: 1, curva: 1 }; // las que cambian con el bono
  let W = null, vista = 'curva', sub = 0, tamManual = false, LISTO = false;
  function ventana(v, j, oculta) {
    if (v && v !== vista) sub = 0; vista = v || vista; if (j != null) sub = j;
    if (!W) {
      W = document.createElement('div'); W.id = 'bnr-win'; tamManual = false; LISTO = false;
      W.innerHTML = '<header><span class="tt"></span><span class="tabs"></span><button class="lk" title="Fijar la ventana (no se mueve ni cambia de tamaño)">🔓</button><button class="x" title="Cerrar">✕</button></header><div class="subs"></div><div class="wb"><div class="zs"><iframe allow="clipboard-write"></iframe></div></div>';
      if (oculta) W.style.visibility = 'hidden'; // se carga escondida (visibility, no display: así la página igual se dibuja y mide)
      document.body.appendChild(W); arrastrar(W);
      W.querySelector('.x').onclick = () => (W.style.display = 'none'); // se oculta, no se cierra: la próxima vez abre al instante
      W.addEventListener('mouseup', (e) => { if (e.target === W) { tamManual = true; encajar(); recordar(); } }); // la agrandó o achicó desde la esquina: el contenido se acomoda a ese tamaño
      W.querySelector('header').ondblclick = (e) => { if (e.target.tagName !== 'BUTTON' && !W.classList.contains('fijo')) { tamManual = false; W.style.width = ''; FIJ = null; encajar(); recordar(); } }; // doble clic: vuelve al tamaño justo
      const lk = W.querySelector('.lk'); lk.onclick = () => { const f = W.classList.toggle('fijo'); lk.textContent = f ? '🔒' : '🔓'; recordar(); };
      try { const g = JSON.parse(localStorage.getItem('bnrWin') || 'null'); if (g) { Object.assign(W.style, { left: g.l + 'px', top: g.t + 'px' }); if (g.m) { tamManual = true; Object.assign(W.style, { width: g.w + 'px', height: g.h + 'px' }); } if (g.f) { W.classList.add('fijo'); lk.textContent = '🔒'; } } } catch (er) { }
    }
    if (!oculta) { W.style.display = ''; W.style.visibility = ''; }
    const g0 = DB[activo] && DB[activo].grupo, g = vista === 'curva' ? (curvaG || (CURVAS[g0] && g0 !== 'acc' ? g0 : 'usd')) : g0, L = VIS[vista][1](g), [, tab, id, sg] = L[sub] || L[0];
    W.querySelector('.tt').textContent = activo || '';
    W.dataset.g = g || '';
    W.querySelector('.tabs').innerHTML = Object.keys(VIS).filter(() => true) /* curva, brecha y canje, pases y expectativas; lo de la ficha está en el panel (Datos) */.map((x) => `<button data-v="${x}" class="${x === vista ? 'on' : ''}">${VIS[x][0]}</button>`).join('');
    W.querySelectorAll('.tabs button').forEach((x) => (x.onclick = () => ventana(x.dataset.v)));
    const S = W.querySelector('.subs'); S.hidden = L.length < 2 && vista !== 'curva';
    if (vista === 'curva') { // desplegable: cualquier curva sin tocar Matriz
      S.innerHTML = `<select class="selc">${Object.keys(NOM_CURVA).map((x) => `<option value="${x}" ${x === g ? 'selected' : ''}>${NOM_CURVA[x]}</option>`).join('')}</select>`;
      S.querySelector('select').onchange = (e) => { curvaG = e.target.value; ventana('curva'); };
      if (MODELO[g]) { const v = (CFG.mdl || {})[g] || 'log'; S.insertAdjacentHTML('beforeend', `<select class="selc mdl" title="Tipo de curva (ajuste)">${AJUSTES.filter(([a]) => g !== 'usd' || a !== 'auto').map(([a, b]) => `<option value="${a}" ${a === v ? 'selected' : ''}>${b}</option>`).join('')}</select>`); S.querySelector('.mdl').onchange = (e) => { CFG.mdl = Object.assign({}, CFG.mdl, { [g]: e.target.value }); guardar(); plazo(g); }; }
      if (DOLAR[g]) { // en qué especie se abre en la boleta el punto que tocás (la misma opción que en ⚙)
        S.insertAdjacentHTML('beforeend', `<span class="mon" title="Al tocar un punto, la boleta se abre en esta moneda">${[['', 'Pesos'], ['D', 'MEP'], ['C', 'CCL']].map(([v, t]) => `<button data-mon="${v}" class="${(CFG.mon || '') === v ? 'on' : ''}">${t}</button>`).join('')}</span>`);
        S.querySelectorAll('.mon button').forEach((x) => (x.onclick = () => { CFG.mon = x.dataset.mon; guardar(); S.querySelectorAll('.mon button').forEach((y) => y.classList.toggle('on', y === x)); if (!CF.hidden) pintarCfg(); }));
      }
      S.insertAdjacentHTML('beforeend', `<button class="bub${CFG.bub ? ' on' : ''}" title="Burbujas de volumen: el tamaño de cada punto es el monto operado hoy">◉ Volumen</button>`);
      S.querySelector('.bub').onclick = (e) => { CFG.bub = !CFG.bub; guardar(); e.currentTarget.classList.toggle('on', CFG.bub); plazo(g); };
      const px = PLAZO[g]; if (px) { const v = (CFG.px || {})[g] || '99999'; S.insertAdjacentHTML('beforeend', `<select class="selc px" title="Plazo máximo de la curva">${[['365', '1 año'], ['730', '2 años'], ['1000', '1.000 días'], ['1500', '4 años'], ['99999', 'Todos los plazos']].map(([a, b]) => `<option value="${a}" ${a === v ? 'selected' : ''}>${b}</option>`).join('')}</select>`); S.querySelector('.px').onchange = (e) => { CFG.px = Object.assign({}, CFG.px, { [g]: e.target.value }); guardar(); plazo(g); }; }
    } else {
      S.innerHTML = L.length < 2 ? '' : L.map((x, i) => `<button data-i="${i}" class="${i === sub ? 'on' : ''}">${x[0]}</button>`).join('');
      S.querySelectorAll('button').forEach((x) => (x.onclick = () => ventana(vista, +x.dataset.i)));
    }
    const F = W.querySelector('iframe'), k = vista === 'ficha' && activo && g !== 'acc' ? activo : '';
    const cv = SOLO_GRAF[vista] && !/^expfW/.test(id) ? 1 : 0; // en las curvas, solo el gráfico (como la curva USD)
    const ctl = vista === 'curva' && /^(on|pv)$/.test(g) ? 1 : 0; // ONs y provinciales: con sus filtros (tipo, sector, liquidez…)
    const clave = [tab, id, sg, k, ctl, cv].join('|');
    if (LISTO && clave === W.dataset.sec) return; // ya muestra eso (por ejemplo, tocaste otro punto de la misma curva): no se vuelve a dibujar
    W.dataset.sec = clave;
    cargando(true);
    if (LISTO) { setTimeout(() => { esperaH = Date.now(); F.contentWindow.postMessage({ t: 'bnrSec', tab, id, g: sg || '', k, cv, ctl, cmp: 1 }, '*'); }, 110); return; } // la página ya está cargada: solo cambia de sección (primero se desvanece lo anterior, así no se ve el cambio)
    esperaH = 0; F.style.height = '2600px';
    const url = SITE + '?emb=sec&cmp=1&tab=' + tab + '&id=' + id + (sg ? '&g=' + sg : '') + (cv ? '&cv=1' : '') + (ctl ? '&ctl=1' : '') + '&v=' + ((chrome.runtime.getManifest && chrome.runtime.getManifest().version) || '') + (k ? '#ficha=' + k + '&n=' + Date.now() : '');
    F.src = chrome.runtime.getURL('frame.html') + '#' + encodeURIComponent(url); // Bonerío va adentro de una página de la extensión: así no la frena la regla frame-src de Matriz
  }
  P.addEventListener('mouseenter', () => { if (!W && activo) ventana(null, null, true); }, { once: true }); // la carga empieza al acercarse al panel: cuando tocás, ya está

  // ---------- cargar un ticker en la boleta de Matriz (campo "Instrumento"); no manda ninguna orden ----------
  function campo(nombre) { // el input de la boleta que está bajo la etiqueta "Precio" o "Cantidad"
    for (const el of document.querySelectorAll('body *')) {
      if (el.children.length || !el.getClientRects().length || el.closest('#bnr-panel,#bnr-win,.bnr-pin') || (el.textContent || '').trim().toLowerCase() !== nombre) continue;
      for (let a = el.parentElement, i = 0; a && i < 3; i++, a = a.parentElement) { const x = [...a.querySelectorAll('input')].find((n) => n.getClientRects().length && n.type !== 'hidden'); if (x) return x; }
    }
    return null;
  }
  function poner(inp, v) { if (!inp || v == null || v === '') return; inp.focus(); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(inp, String(v)); ['input', 'change'].forEach((t) => inp.dispatchEvent(new Event(t, { bubbles: true }))); inp.dispatchEvent(new Event('blur', { bubbles: true })); }
  function ultimoFila(k) { // Mini-Panel de precios: la fila «AL30 … Últ Var.%»; devuelve el «Últ» como lo pide la boleta (81250,5), o '' si no operó
    for (const el of document.querySelectorAll('body *')) {
      if (el.children.length || (el.textContent || '').trim().toUpperCase() !== k || !el.getClientRects().length || el.closest('#bnr-panel,#bnr-win,.bnr-pin,[data-bnr],[role=listbox],[role=option]')) continue;
      const v = ultimoDe(el, k); if (v != null) return v;
    }
    return '';
  }
  function ultimoDe(el, k) { // el «Últ» de la fila del Mini-Panel donde está ese ticker (null: no es una fila del Mini-Panel)
      for (let a = el.parentElement, i = 0; a && i < 5; i++, a = a.parentElement) {
        const tx = a.innerText || ''; if (/Cierre/i.test(tx)) break; // un recuadro con libro: su precio lo lee precioDe
        const t = tx.trim().split(/\s+/), j = t.findIndex((x) => x.toUpperCase() === k);
        if (j < 0 || t.some((x, m) => m !== j && /^[A-Z]{2,}\d/.test(x))) break; // ya abarca otra fila
        const n = t[j + 1]; if (n == null) continue; // la columna que sigue al ticker es «Últ»; en Matriz la coma es decimal y el punto separa miles
        const v = /^[\d.,]+$/.test(n) ? num(n.includes(',') ? n : n.replace(/\./g, '')) : NaN; return v > 0 ? String(v).replace('.', ',') : '';
      }
    return null;
  }

  const especie = (k) => { // la especie que se carga en la boleta según la moneda elegida en ⚙ (pesos, MEP o CCL)
    const r = tk(k); if (!r || r[1] || !CFG.mon || !DOLAR[DB[r[0]].grupo]) return k;
    return DB[r[0]].grupo === 'on' && /O$/.test(k) ? k.slice(0, -1) + CFG.mon : k + CFG.mon;
  };
  const plazoDe = (el) => { const x = el.innerText || ''; return /\(CI\)|\bCI\b|contado inmediato/i.test(x) ? 'ci' : /24\s*hs|\b24H\b/i.test(x) ? '24' : ''; }; // el plazo de un recuadro de Matriz
  function completar(k, cant, pz) { // después de elegir el instrumento: precio de mercado que muestra Matriz y la cantidad por defecto (si hay). Comprar/Vender lo aprieta el usuario.
    setTimeout(() => {
      const r = tk(k), cs = r ? recuadros().filter((x) => x.k === r[0] && x.suf === r[1]) : [], c = pz ? cs.find((x) => plazoDe(x.el) === pz) || cs.find((x) => !plazoDe(x.el) && pz === '24') : cs[0], [p] = c ? precioDe(c) : [NaN];
      const lv = pz ? (PXP.k === k && PXP.pz === pz ? PXP.p : 0) : PXV[k] || 0; // el último operado en Primary (el mismo que muestra Matriz), si la ventana lo tiene en vivo
      const q0 = p > 0 ? String(p).replace('.', ',') : pz === 'ci' ? '' : ultimoFila(k), q = q0 || (lv > 0 ? String(lv).replace('.', ',') : ''); // siempre el ÚLTIMO operado: del recuadro (en un pase, el de ese plazo), del Mini-Panel o, si no está a la vista, de Primary
      const pf = PFIJO; PFIJO = 0; if (pf > 0) { poner(campo('precio'), String(pf).replace('.', ',')); } // el precio escrito en la ficha fija
      const PM = CFG.pm === 'm' || pf > 0, QM = CFG.qm === 'm' && !(cant > 0); // en ⚙: precio y/o cantidad a mano (queda el cursor ahí para tipear); lo escrito en la ficha fija gana
      if (PM || QM) { if (!PM && q) poner(campo('precio'), q); const n = cant > 0 ? cant : CFG.qty; if (!QM && n > 0) poner(campo('cantidad'), n); const pa = PM && !(pf > 0); // falta a mano: el precio (si no vino de la ficha) y/o la cantidad
        const x = pa ? campo('precio') : QM ? campo('cantidad') : null; if (x) { x.focus(); x.select && x.select(); }
        aviso(pz ? msgPase : 'Boleta: ' + k + ' cargado' + (pf > 0 ? ' a $ ' + fmt(pf, 2) + ' (precio de la ficha)' : '') + (pa || QM ? '; completá ' + (pa && QM ? 'precio y cantidad' : pa ? 'el precio' : 'la cantidad') + ' a mano' : '')); return; }
      if (pz) { if (q) poner(campo('precio'), q); const n = cant > 0 ? cant : CFG.qty; if (n > 0) poner(campo('cantidad'), n); aviso(q ? msgPase : 'Sin precio de ' + k + ' en ' + (pz === 'ci' ? 'CI' : '24 hs') + ' en pantalla (abrí su recuadro): completalo a mano. ' + msgPase, !q); return; } // del recuadro con libro o, si no, del Mini-Panel de precios
      const b = !q && r && DB[r[0]], qc = b && b.precio > 0 && precioVale(r[0], r[1]) ? String(b.precio).replace('.', ',') : ''; // sin precio en pantalla: el cierre de Bonerío (BYMA), avisando
      if (q || qc) poner(campo('precio'), q || qc);
      const n = cant > 0 ? cant : CFG.qty; if (n > 0) poner(campo('cantidad'), n);
      if (qc) aviso('Boleta: ' + k + ' sin precio en pantalla; puse el cierre de Bonerío (' + (b.fecha || FECHA) + '): revisalo antes de mandar', 1);
      else if (!q0 && q) aviso('Boleta: ' + k + ' con el último operado en Primary (no está en un recuadro ni en el Mini-Panel)');
      else if (!q) aviso('Boleta: ' + k + ' cargado; sin precio en pantalla (no operó o no está en un recuadro ni en el Mini-Panel)');
    }, 500);
  }
  let tEst = 0, PXV = {}, PXP = {}, PFIJO = 0;
  function aviso(t, mal) { const E = P.querySelector('.est'); E.textContent = t; E.className = 'est' + (mal ? ' mal' : ''); E.hidden = false; console.log('[Bonerío Inside]', t); clearTimeout(tEst); tEst = setTimeout(() => (E.hidden = true), 8000); }
  function aBoleta(k, cant, pz, crudo) {
    try { return aBoleta1(k, cant, pz, crudo); } catch (er) { aviso('Boleta: error ' + er.message, 1); }
  }
  function aBoleta1(k, cant, pz, crudo) {
    k = crudo ? k : especie(aMatriz(k)); // crudo: la especie tal cual (la tabla de Pases ya trae la D del MEP)
    { const r = tk(k), D = (r && PINS.get(r[0])) || PINS.get(k); PFIJO = D && !pz ? pinP(D) : 0; if (D && !(cant > 0)) cant = +D.querySelector('.pq').value || 0; } // si el bono tiene ficha fija, van sus nominales y su precio (los escritos ganan sobre ⚙) // si el bono tiene ficha fija, van sus nominales aviso('Boleta: buscando ' + k + '…');
    const vis = (e) => e && e.offsetParent && !e.closest('#bnr-panel,#bnr-win,.bnr-pin');
    let inp = [...document.querySelectorAll('input')].find((i) => vis(i) && /instrumento/i.test(i.placeholder || ''));
    if (!inp) for (const el of document.querySelectorAll('body *')) { // el texto "Buscar instrumento" o la etiqueta "Instrumento" suelen ser un div aparte (selectores tipo react-select): el input está en el mismo bloque
      if (el.children.length || !vis(el) || !/^(Buscar instrumento|Instrumento)$/i.test((el.textContent || '').trim())) continue;
      for (let a = el.parentElement, i = 0; a && i < 4 && !inp; i++, a = a.parentElement) inp = [...a.querySelectorAll('input')].find((x) => vis(x) && x.type !== 'hidden' && x.type !== 'checkbox');
      if (inp) break;
    }
    if (!inp) { aviso('Boleta: no encontré el campo «Instrumento» de Matriz', 1); return false; }
    const propio = inp.parentElement && inp.parentElement.parentElement; // el propio campo (los buscadores tipo react-select repiten el texto en un div invisible para medirlo)
    const seve = (o) => { const r = o.getBoundingClientRect(); return r.width > 4 && r.height > 4 && getComputedStyle(o).visibility !== 'hidden'; };
    const cand = () => [...document.querySelectorAll('li,[role=option],mat-option,a,span,div')].filter((o) => !o.children.length && (o.textContent || '').trim().toUpperCase().startsWith(k) && seve(o) && !(propio && propio.contains(o)) && !o.closest('#bnr-panel,#bnr-win,.bnr-pin'));
    const antes = new Set(cand()); // solo vale una sugerencia que aparezca después de escribir (no una fila del panel de precios)
    const box = inp.closest('div') || inp; ['mousedown', 'mouseup', 'click'].forEach((t) => box.dispatchEvent(new MouseEvent(t, { bubbles: true }))); // abre el buscador
    inp.focus(); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(inp, k);
    inp.dispatchEvent(new Event('input', { bubbles: true })); inp.dispatchEvent(new Event('change', { bubbles: true })); inp.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: k.slice(-1) }));
    let n = 0; const iv = setInterval(() => { // elige la primera sugerencia nueva (en 24 hs si la hay)
      if (++n > 16) { clearInterval(iv); ['ArrowDown', 'Enter'].forEach((key) => inp.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key, code: key, keyCode: key === 'Enter' ? 13 : 40 }))); aviso('Boleta: escribí ' + k + ' pero no vi la lista de sugerencias (probé con Enter)', 1); completar(k, cant, pz); return; } // sin sugerencia reconocible: Enter elige la primera
      const ops = cand().filter((o) => !antes.has(o)), t = (x) => (x.textContent || '').trim().toUpperCase(), o = pz === 'ci' ? ops.find((x) => /\(CI\)|\bCI\b/.test(t(x))) : ops.find((x) => t(x) === k) || ops.find((x) => /24/.test(t(x))) || ops.find((x) => !/\(CI\)|\bCI\b/.test(t(x))) || ops[0]; // 24 hs: el ticker solo (Matriz pone «(CI)» al contado)
      if (o) { clearInterval(iv); const tg = o.closest('li,[role=option],mat-option') || o; ['pointerover', 'mouseover', 'mousemove', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach((ev) => tg.dispatchEvent(new (ev.startsWith('pointer') ? PointerEvent : MouseEvent)(ev, { bubbles: true, cancelable: true, view: window, button: 0 }))); aviso('Boleta: elegí ' + t(o)); completar(k, cant, pz); }
    }, 250);
    return true;
  }
  window.addEventListener('message', (e) => { // la página manda la altura de la sección (la ventana queda justa) o el bono que se tocó
    if (!W || !e.data || e.source !== W.querySelector('iframe').contentWindow) return;
    if (e.data.t === 'bnrDat') { if (/^[A-Z0-9]{3,10}$/.test(e.data.k || '')) { if (!e.data.d) { if ((NUL[e.data.k] = (NUL[e.data.k] || 0) + 1) < 20) setTimeout(() => { if (!DAT[e.data.k]) { delete DAT[e.data.k]; pedirDatos(e.data.k); } }, 1000); return; } DAT[e.data.k] = e.data.d; /* sin datos todavía (la página no terminó de cargar): se vuelve a pedir */ if (e.data.k === activo) { dxK = null; pintarDatos(); } const D = PINS.get(e.data.k), x = D && D.querySelector('.dx'); if (x && !x.hidden) montarDatos(x, e.data.k); } return; }
    if (e.data.t === 'bnrPro') { const ant = PRO; PRO = e.data.p === true ? true : e.data.p === false ? false : null; if (ant !== PRO) pintar(); return; }
    if (e.data.t === 'bnrTk' && bloqueado()) return;
    if (e.data.t === 'bnrPaseAl') { if (!bloqueado() && CFG.alp !== false) avisarPases(e.data.a || []); return; }
    if (e.data.t === 'bnrPata') { if (bloqueado()) return; const { k, pz, sd } = e.data, q = +e.data.q > 0 ? +e.data.q : 0, r = tk(k); if (r) { activo = r[0]; precioManual = false; pintar(); } PXP = { k, pz, p: +e.data.px > 0 ? +e.data.px : 0 }; msgPase = `${k} en ${pz === 'ci' ? 'CI' : '24 hs'}: revisá y apretá ${sd === 'c' ? 'COMPRAR' : 'VENDER'}.`; aBoleta(k, q, pz, 1); return; } // una pata del pase (con los nominales en cartera, si los cargaste en Pases), desde la tabla de Pases
    if (e.data.t === 'bnrTk') { PXV = e.data.px && typeof e.data.px === 'object' ? e.data.px : {}; const k = aMatriz(e.data.k), r = tk(k); if (r) { activo = r[0]; precioManual = false; pintar(); } aBoleta(k); return; }
    if (e.data.t !== 'bnrH') return;
    if (!LISTO) setTimeout(darTok, 0); else if (reSec && Date.now() - reSec > 300 && Date.now() - reSec < 20000) { reSec = 0; W.dataset.sec = ''; setTimeout(() => ventana(null, null, W.style.display === 'none' || W.style.visibility === 'hidden'), 0); } /* la página se recargó con tu sesión: vuelve a la sección que estabas mirando */ LISTO = true; encajar(Math.max(150, +e.data.h || 0));
    if (Date.now() - esperaH > 40) { setTimeout(() => cargando(false), 50); if (vista === 'curva') plazo(W.dataset.g); } // la sección nueva ya está: aparece con un fundido
  });
  let reSec = 0, ultH = 0, FIJ = null, esperaH = 0, cgT = 0, SES = null;
  const darTok = () => { const f = W && LISTO && W.querySelector('iframe'); if (f && f.contentWindow && SES) reSec = Date.now(), f.contentWindow.postMessage({ t: 'bnrTok', k: SES.k, v: SES.v }, '*'); }; // la sesión de Bonerío (copiada por auth.js desde boneriolocal.com.ar) a la ventana
  try { chrome.storage.local.get('bnrTok', (o) => { SES = (o && o.bnrTok) || null; darTok(); }); chrome.storage.onChanged.addListener((c) => { if (c.bnrTok) { SES = c.bnrTok.newValue || null; darTok(); } }); } catch (er) { }
  setInterval(() => { // los precios de tu Matriz (recuadros y Mini-Panel) van a la ventana: curvas, bonos y pases se calculan con lo que ves, en tiempo real
    const f = W && LISTO && W.querySelector('iframe'); if (!f || !f.contentWindow) return;
    try { f.contentWindow.postMessage({ t: 'bnrPx', px: pantalla() }, '*'); } catch (er) {}
  }, 2000);
  function cargando(si) { // fundido entre secciones y una barrita dorada mientras carga
    if (!W) return; const Z = W.querySelector('.zs'); clearTimeout(cgT);
    Z.classList.toggle('cg', si); if (si) esperaH = 1e15, cgT = setTimeout(() => Z.classList.remove('cg'), 3000);
  }
  function encajar(h) { // sin escalar (se ve nítido y los desplegables salen en su lugar): la página se acomoda al ancho de la ventana y lo que sobra se desplaza
    if (h) ultH = h; h = ultH; if (!W || !h) return;
    const F = W.querySelector('iframe'), Z = W.querySelector('.zs'), wb = W.querySelector('.wb'), top = wb.offsetTop + 2;
    const cap = Math.min(Math.round(innerHeight * 0.55), innerHeight - W.offsetTop - 10); // automático: como mucho media pantalla, no tapa la operatoria
    Object.assign(F.style, { width: '100%', height: h + 'px', transform: '' }); Z.style.width = ''; Z.style.height = h + 'px';
    if (!FIJ || FIJ.c !== W.dataset.sec || FIJ.m !== tamManual) FIJ = { c: W.dataset.sec, m: tamManual, hw: 0, cvh: 0 };
    if (!tamManual) { const hw = Math.max(FIJ.hw, Math.min(cap, h + top)); if (W.style.height !== hw + 'px') { FIJ.hw = hw; W.classList.add('anim'); W.style.height = hw + 'px'; setTimeout(() => W.classList.remove('anim'), 260); } } // dentro de la misma solapa solo crece (no salta)
    const cv = W.dataset.sec.endsWith('|1'), want = tamManual && cv ? W.clientHeight - top - 6 : 0; // solo el gráfico: con tamaño a mano, el gráfico llena la ventana
    if (Math.abs(want - FIJ.cvh) > 6) { FIJ.cvh = want; F.contentWindow.postMessage({ t: 'bnrCvH', h: want }, '*'); }
  }
  function recordar() { try { localStorage.setItem('bnrWin', JSON.stringify({ l: W.offsetLeft, t: W.offsetTop, w: W.offsetWidth, h: W.offsetHeight, m: tamManual, f: W.classList.contains('fijo') })); } catch (er) { } }

  // ---------- acceso: abierta para todos hasta el martes 10/11; después, cuentas con Bonerío PRO (o en sus 5 días de prueba) ----------
  const LIBRE_HASTA = '2026-11-11', hoyAR = () => new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10);
  let PRO; // lo dice la página de Bonerío con la sesión de la cuenta: true, false o null (sin sesión)
  const bloqueado = () => hoyAR() >= LIBRE_HASTA && PRO !== true;
  function candado() {
    document.documentElement.classList.add('bnr-lock'); if (!W) ventana(null, null, true); // la página de Bonerío dice si la cuenta tiene PRO
    B.innerHTML = PRO === undefined ? '<div class="m">Verificando tu cuenta de Bonerío…</div>'
      : `<div class="t">Bonerío PRO</div><div class="m">${PRO === null ? 'Entrá con tu cuenta de Bonerío Local para usar Bonerío Inside.' : 'Bonerío Inside es parte de Bonerío PRO y tu cuenta no lo tiene activo.'}</div>
        <div class="bt">${PRO === null ? '<button data-l="in">Entrar</button>' : ''}<button data-l="pl">Ver planes</button></div>`;
    B.querySelectorAll('[data-l]').forEach((x) => (x.onclick = () => { if (x.dataset.l === 'in') { window.open('https://boneriolocal.com.ar/', '_blank'); B.querySelector('.m').textContent = 'Entrá con tu cuenta en la pestaña de Bonerío que se abrió y volvé: acá se habilita solo.'; } else window.open('https://boneriolocal.com.ar/#tab=planes', '_blank'); })); // se entra en la página (no se puede iniciar sesión con Google adentro de un iframe); la sesión llega por auth.js
    if (W && PRO === false) W.style.display = 'none'; try { DX.hidden = true; } catch (er) { } /* DX todavía no existe en la primera pintada */
  }
  function pintar() {
    if (bloqueado()) return candado(); document.documentElement.classList.remove('bnr-lock');
    if (!activo) { B.innerHTML = '<span class="m">Abrí un bono en Matriz (o hacé clic en una fila) y aparece acá.</span>'; return; }
    const BT = (c) => `<div class="bt">${c ? '<button data-v="curva">Curva</button>' : ''}<button data-v="mas">Más…</button><button data-v="boleta" title="Cargar en la boleta de Matriz">Boleta</button></div>`;
    const enlazar = () => B.querySelectorAll('.bt button').forEach((x) => (x.onclick = () => (x.dataset.v === 'datos' ? (CFG.dat = !CFG.dat, guardar(), dxK = null, pintar()) : x.dataset.v === 'boleta' ? aBoleta(activo) : (x.dataset.v === 'curva' && (curvaG = null), ventana(x.dataset.v === 'mas' ? (vista === 'curva' ? 'brc' : vista) : x.dataset.v)))));
    const seguir = () => { if (W && W.querySelector('.tt').textContent !== activo) SIGUE[vista] ? ventana(null, null, W.style.display === 'none') : (W.querySelector('.tt').textContent = activo); }; // la ventana sigue al bono
    if (!DB[activo]) { B.innerHTML = `<div class="t">${activo}</div><div class="m">Sin datos en Bonerío para este ticker todavía.</div>` + BT(false); enlazar(); if (W && W.querySelector('.tt').textContent !== activo) SIGUE[vista] ? ventana(null, null, W.style.display === 'none') : (W.querySelector('.tt').textContent = activo); return; }
    const b = DB[activo];
    if (b.tipo === 'acc') {
      ratios(); const r = b.ret || {}, pc = (x) => (x == null ? '-' : fmt(x * 100) + '%');
      B.innerHTML = `<div class="t">${activo}</div><div class="m">Acción · cierre ${b.fecha}</div>
        <div class="g"><span>Precio</span><span>$ ${fmt(b.precio)}</span><span>Var. día</span><span>${pc(r['1d'])}</span><span>1 mes</span><span>${pc(r['1m'])}</span><span>En el año</span><span>${pc(r.ytd)}</span>
        <span>P/E</span><span>${fmt(b.pe)}</span><span>P/VL</span><span>${fmt(b.pvl)}</span><span>EV/EBITDA</span><span>${fmt(b.ev)}</span><span>Beta</span><span>${fmt(b.beta)}</span></div>
        <div class="bt"><button data-v="mas">Más…</button><button data-v="boleta" title="Cargar en la boleta de Matriz">Boleta</button></div>${paseHTML()}`;
      enlazar(); enlazarPase(); seguir(); return;
    }
    if (b.tipo === 'fut') {
      const inp = B.querySelector('input'); let p = precioManual && inp ? num(inp.value) : NaN, fuente = 'manual';
      if (!(p > 0)) { [p, fuente] = precioPantalla(activo); precioManual = false; }
      const x = fut(b, p);
      B.innerHTML = `<div class="t">${activo}</div><div class="m">Futuro de dólar · vence ${b.vto.split('-').reverse().join('/')}</div>
        <div class="g"><span>Cierre</span><span>$ ${fmt(b.precio)}</span><span>A3500 (${b.fspot.slice(5).split('-').reverse().join('/')})</span><span>$ ${fmt(b.spot)}</span>
        <span>TNA implícita</span><span>${fmt(x.tna)}%</span><span>Devaluación mensual</span><span>${fmt(x.dev)}%</span><span>Días al vto.</span><span>${x.d}</span></div>
        <label class="m">Precio (${fuente || 'cierre'}): si compro a…</label><input value="${p > 0 ? fmt(p, 2) : ''}" placeholder="Precio">
        <div class="bt"><button data-v="curva">Curva</button><button data-v="mas">Más…</button><button data-v="boleta" title="Cargar en la boleta de Matriz">Boleta</button></div>`;
      enlazar(); seguir(); B.querySelector('input').onchange = () => { precioManual = true; pintar(); }; return;
    }
    const [p] = precioPantalla(activo), t0 = p > 0 ? tirA(b, p) : null, tir = t0 == null ? b.tir : t0;
    B.innerHTML = `<div class="t">${activo}</div><div class="m">${b.unidad} · cierre Bonerío ${FECHA}</div>
      <div class="g"><span>${b.unidad} al cierre</span><span>${fmt(b.tir)}%</span>
      <span>${b.unidad} a este precio</span><span>${fmt(tir)}%</span>
      <span>Duration mod.</span><span>${fmt(b.md)}</span><span>Días al vto.</span><span>${b.dias}</span></div>
      <div class="bt"><button data-v="datos" class="${CFG.dat ? 'on' : ''}" title="Datos del bono y calculadora">Datos ${CFG.dat ? '▴' : '▾'}</button><button data-v="curva">Curva</button><button data-v="mas">Más…</button><button data-v="boleta" title="Cargar en la boleta de Matriz">Boleta</button></div>${paseHTML()}`;
    enlazar(); enlazarPase();
    if (W && W.querySelector('.tt').textContent !== activo) SIGUE[vista] ? ventana(null, null, W.style.display === 'none') : (W.querySelector('.tt').textContent = activo); // la ventana sigue al bono
    pintarDatos();
  }

  // ---------- alerta de pases: cuando en tus especies de Pases conviene colocar o tomar, suena un «check» y aparece un aviso con las dos patas ----------
  let AC = null; const AVISADO = new Map();
  function sonar() { // dos notas cortas y suaves, sin archivos
    try { AC = AC || new (window.AudioContext || window.webkitAudioContext)(); if (AC.state === 'suspended') AC.resume();
      [[880, 0], [1320, 0.12]].forEach(([f, t0]) => { const o = AC.createOscillator(), g = AC.createGain(), t = AC.currentTime + t0; o.type = 'sine'; o.frequency.value = f; g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.18, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.22); o.connect(g).connect(AC.destination); o.start(t); o.stop(t + 0.25); });
    } catch (er) { }
  }
  document.addEventListener('pointerdown', () => { try { AC = AC || new (window.AudioContext || window.webkitAudioContext)(); if (AC.state === 'suspended') AC.resume(); } catch (er) { } }, { capture: true, once: true }); // el navegador habilita el sonido después del primer clic
  const pct = (x) => fmt(x * 100) + '%';
  function avisarPases(A) {
    const ahora = Date.now(), nuevos = A.filter((x) => { const k = x.t + '|' + x.tp, u = AVISADO.get(k); return !u || ahora - u > 30 * 60e3; }); // cada pase avisa una vez cada 30 minutos
    if (!nuevos.length) return; nuevos.forEach((x) => AVISADO.set(x.t + '|' + x.tp, ahora)); sonar();
    let T = document.getElementById('bnr-alp'); if (!T) { T = document.createElement('div'); T.id = 'bnr-alp'; document.body.appendChild(T); }
    T.innerHTML = '<header><b>Pases que convienen</b><button class="x" title="Cerrar">✕</button></header>' + nuevos.map((x) => { const pt = PATAS[x.tp === 2 ? 'col' : 'tom']; return `<div class="it"><div><b>${x.t}</b> · ${x.tp === 2 ? 'colocar' : 'tomar'} a ${pct(x.g)} <small>(caución ${pct(x.c)}${x.n ? ' · ' + fmt(x.n, 0) + ' VN' : ''})</small></div><div class="bt">${pt.map(([pz, lado, nom]) => `<button data-k="${x.t}" data-pz="${pz}" data-sd="${lado === 'COMPRAR' ? 'c' : 'v'}" data-n="${x.n || 0}">${lado === 'COMPRAR' ? 'Comprar' : 'Vender'} ${nom}</button>`).join('')}</div></div>`; }).join('');
    T.hidden = false; clearTimeout(T._t); T._t = setTimeout(() => (T.hidden = true), 120e3);
    T.onclick = (e) => { const b = e.target.closest('button'); if (!b) return; if (b.classList.contains('x')) { T.hidden = true; return; } T.querySelectorAll('.bt button.on').forEach((x) => x.classList.remove('on')); b.classList.add('on'); const k = b.dataset.k, pz = b.dataset.pz, r = tk(k); if (r) { activo = r[0]; precioManual = false; pintar(); } msgPase = `${k} en ${pz === 'ci' ? 'CI' : '24 hs'}: revisá y apretá ${b.dataset.sd === 'c' ? 'COMPRAR' : 'VENDER'}.`; aBoleta(k, +b.dataset.n || 0, pz, 1); };
  }
  setTimeout(() => { if (!W && CFG.alp !== false) ventana(null, null, true); }, 5000); // para vigilar los pases la página de Bonerío se carga escondida al entrar

  // ---------- pase CI ↔ 24 hs: carga las dos patas en la boleta, una por vez (Comprar/Vender lo aprieta el usuario) ----------
  let PASE = null, msgPase = ''; // { k, d: 'col' | 'tom', pata: 2 } cuando falta la segunda pata
  const PATAS = { col: [['ci', 'COMPRAR', 'CI'], ['24', 'VENDER', '24 hs']], tom: [['ci', 'VENDER', 'CI'], ['24', 'COMPRAR', '24 hs']] };
  const paseHTML = () => { const p2 = PASE && PASE.k === activo; return `<div class="ps"><span title="Pase entre contado inmediato y 24 hs">Pase CI ↔ 24</span>${['col', 'tom'].map((d) => `<button data-p="${d}" class="${p2 && PASE.d === d ? 'on' : ''}" title="${d === 'col' ? 'Colocás pesos: comprás en CI y vendés en 24 hs' : 'Tomás pesos: vendés en CI y comprás en 24 hs'}">${p2 && PASE.d === d ? 'Pata 2: ' + PATAS[d][1][1].toLowerCase() + ' 24 hs' : d === 'col' ? 'Colocar' : 'Tomar'}</button>`).join('')}</div>`; };
  function enlazarPase() {
    B.querySelectorAll('.ps button').forEach((x) => (x.onclick = () => {
      const d = x.dataset.p, dos = PASE && PASE.k === activo && PASE.d === d, [pz, lado, nom] = PATAS[d][dos ? 1 : 0];
      msgPase = `Pase ${d === 'col' ? 'colocador' : 'tomador'} · pata ${dos ? 2 : 1}: ${activo} en ${nom}. Revisá y apretá ${lado}.${dos ? '' : ' Después tocá «Pata 2».'}`;
      PASE = dos ? null : { k: activo, d }; aBoleta(activo, 0, pz);
      pintar();
    }));
  }

  // ---------- datos y calculadora del bono, en el panel (los mismos cálculos de la ficha de Bonerío: la página los manda) ----------
  const DX = document.createElement('div'); DX.className = 'dx'; DX.hidden = true; B.after(DX);
  const DAT = {}, NUL = {}; let dxK = null, pideN = 0;
  function pedirDatos(k) {
    if (DAT[k]) return; if (!W) ventana(null, null, true); // la página de Bonerío se carga escondida
    if (!LISTO) { if (++pideN < 60) setTimeout(() => pedirDatos(k), 500); return; }
    pideN = 0; W.querySelector('iframe').contentWindow.postMessage({ t: 'bnrDatos', k }, '*');
  }
  const pvY = (fl, s, y) => fl.reduce((a, f) => a + f[1] / Math.pow(1 + y, (f[0] - s) / 365), 0);
  const tirP = (fl, s, P) => { let lo = -0.95, hi = 20; if (!(P > 0) || !fl.length) return null; for (let i = 0; i < 200; i++) { const m = (lo + hi) / 2; if (pvY(fl, s, m) > P) lo = m; else hi = m; } return (lo + hi) / 2; };
  const durY = (fl, s, y) => { let pv = 0, tw = 0; fl.forEach((f) => { const t = (f[0] - s) / 365, v = f[1] / Math.pow(1 + y, t); pv += v; tw += v * t; }); return pv > 0 ? tw / pv / (1 + y) : null; };
  function pintarDatos() {
    const b = DB[activo]; if (!CFG.dat || !b || b.tipo) { DX.hidden = true; return; }
    DX.hidden = false; if (dxK === activo && DX.querySelector('.cx')) return; // ya está (no se pisa lo que escribiste en la calculadora)
    if (montarDatos(DX, activo)) dxK = activo;
  }
  function sensAl(DX) { // el cuadro de sensibilidad va al costado del panel o de la ficha (a la derecha si entra; si no, a la izquierda)
    if (DX._fl) return DX._fl;
    const FL = DX._fl = document.createElement('div'); FL.className = 'bnr-sens'; FL.hidden = true; document.body.appendChild(FL);
    FL.addEventListener('click', (e) => { if (e.target.closest('.sh button')) { DX._sx = false; FL.hidden = true; const b = DX.querySelector('.sxb'); if (b) b.classList.remove('on'); if (DX.parentElement === P) { CFG.sx = false; guardar(); } } });
    FL._ubicar = () => {
      const host = DX.closest('#bnr-panel,.bnr-pin'); if (!host || DX.hidden || !document.body.contains(DX)) { FL.hidden = true; return; }
      const r = host.getBoundingClientRect(), w = FL.offsetWidth || 270, h = FL.offsetHeight || 260;
      FL.style.left = (r.right + 8 + w <= innerWidth ? r.right + 8 : Math.max(8, r.left - 8 - w)) + 'px';
      FL.style.top = Math.max(8, Math.min(r.top, innerHeight - h - 8)) + 'px';
    };
    setInterval(() => { if (!FL.hidden) FL._ubicar(); else if (DX._sx && !DX.hidden && document.body.contains(DX)) { FL.hidden = false; FL._ubicar(); } }, 300); // sigue al panel si lo movés
    return FL;
  }
  function montarDatos(DX, k) { // los datos de la ficha y la calculadora, en el panel o en una ficha fija
    const d = DAT[k];
    if (d === undefined) { DX.innerHTML = '<div class="m">Cargando los datos de Bonerío…</div>'; pedirDatos(k); return false; }
    if (!d) { DX.innerHTML = '<div class="m">Sin datos de Bonerío para este bono.</div>'; return false; }
    const u = d.usd ? 'US$ ' : '$ ', pc = (x) => (x == null ? '—' : fmt(x * 100) + '%'), f2 = (x, n) => (x == null ? '—' : fmt(x, n == null ? 2 : n));
    const [ps] = precioPantalla(k), P0 = ps > 0 ? ps : d.P, pin = PINS.get(k), vn0 = (pin && +pin.querySelector('.pq').value) || CFG.qty || 100;
    DX.innerHTML = `<div class="g">
      <span>Precio Bonerío</span><span>${u}${f2(d.P)}</span><span>${d.yl}</span><span>${pc(d.y)}</span>
      <span>Duración Macaulay</span><span>${f2(d.mac)}</span><span>Duración modificada</span><span>${f2(d.md)}</span>
      <span>Convexidad</span><span>${f2(d.cx)}</span><span>Cambio por 1 pb (100 VN)</span><span>${d.md != null ? u + f2(d.P * d.md / 1e4, 4) : '—'}</span>
      <span>Valor técnico</span><span>${d.vt != null ? u + f2(d.vt) : '—'}</span><span>Intereses corridos</span><span>${d.acc != null ? u + f2(d.acc, 4) : '—'}</span>
      <span>Valor residual</span><span>${d.res != null ? f2(d.res) + '%' : '—'}</span><span>Paridad</span><span>${d.vt > 0 ? pc(d.P / d.vt) : '—'}</span>
      ${d.cpn != null ? `<span>${d.cpnL || 'Cupón'}</span><span>${pc(d.cpn)}</span>` : ''}</div>
      <div class="cx"><label>Precio<input data-c="p" value="${f2(P0)}"></label><label>${d.yl} %<input data-c="y"></label><label>Nominales<input data-c="n" value="${vn0}"></label></div>
      <div class="g co"></div>
      <button class="sxb">Sensibilidad a la ${d.yl} <span>▸</span></button>`;
    const I = (c) => DX.querySelector(`[data-c="${c}"]`);
    const FL = sensAl(DX), SB = DX.querySelector('.sxb'), abrir = (on) => { DX._sx = on; SB.classList.toggle('on', on); FL.hidden = !on; if (on) FL._ubicar(); };
    if (DX._sx == null) DX._sx = DX.parentElement === P && !!CFG.sx; abrir(DX._sx);
    SB.onclick = () => { abrir(!DX._sx); if (DX.parentElement === P) { CFG.sx = DX._sx; guardar(); } };
    const sens = (y, vn) => { // cuánto cambia el precio si la TIR se mueve, desde el precio de la calculadora (se abre al costado)
      const box = FL; if (!isFinite(y)) { box.innerHTML = ''; return; }
      const p0 = pvY(d.fl, d.s, y) * d.kq;
      box.innerHTML = `<div class="sh"><b>${k}</b> · sensibilidad a la ${d.yl} desde ${f2(p0)}<button title="Cerrar">✕</button></div><table><tr><th title="Cuánto se mueve la ${d.yl}">Δ ${d.yl}</th><th>Precio</th><th>Var.</th><th>Resultado</th></tr>${[-200, -100, -50, -25, 25, 50, 100, 200].map((b) => { const y1 = y + b / 1e4, p1 = pvY(d.fl, d.s, y1) * d.kq, v = p1 / p0 - 1; return `<tr class="${v >= 0 ? 'up' : 'dn'}"><td title="${d.yl} ${pc(y1)}">${b > 0 ? '+' : ''}${b} pb</td><td>${f2(p1)}</td><td>${v >= 0 ? '+' : ''}${fmt(v * 100)}%</td><td>${v >= 0 ? '+' : '−'}${u}${f2(Math.abs((p1 - p0) * vn / 100))}</td></tr>`; }).join('')}</table>`;
    };
    let out = () => {
      const P = num(I('p').value), y = num(I('y').value) / 100, vn = num(I('n').value) || 0, tot = d.nom.reduce((a, f) => a + f[1], 0), pay = P * vn / 100, get = tot * vn / 100, md = isFinite(y) ? durY(d.fl, d.s, y) : null;
      DX.querySelector('.co').innerHTML = `<span>Pagás</span><span>${u}${f2(pay)}</span><span>Cobrás en total</span><span>${u}${f2(get)}</span><span>Ganancia nominal</span><span>${u}${f2(get - pay)}</span><span>Duración modificada</span><span>${f2(md)}</span><span>Cambio por 1 pb</span><span>${md != null ? u + f2(pay * md / 1e4) : '—'}</span>`;
    };
    const out0 = out; out = () => { out0(); sens(num(I('y').value) / 100, num(I('n').value) || 0); };
    const desdeP = () => { const P = num(I('p').value), y = tirP(d.fl, d.s, P / d.kq); I('y').value = y == null ? '' : fmt(y * 100); out(); };
    I('p').oninput = desdeP; I('n').oninput = out;
    I('y').oninput = () => { const y = num(I('y').value) / 100; if (isFinite(y) && y > -0.95) I('p').value = fmt(pvY(d.fl, d.s, y) * d.kq); out(); };
    desdeP(); return true;
  }

  let t, ultBoleta = null; const revisar = (muts) => {
    const nuestro = (m) => { const e = m.target.nodeType === 1 ? m.target : m.target.parentElement; return !e || P.contains(e) || (W && W.contains(e)) || e.closest('[data-bnr],.bnr-pin'); };
    if (muts.every(nuestro)) return; // cambios del propio panel o de nuestras filas
    clearTimeout(t); t = setTimeout(() => {
      const k = tickerBoleta(); if (k && k !== ultBoleta) { ultBoleta = activo = k; precioManual = false; } // cargó otro bono en la boleta
      if (!activo) activo = tickerVisible();
      if (!precioManual && document.activeElement !== B.querySelector('input')) pintar();
      if (bloqueado()) document.querySelectorAll('[data-bnr]').forEach((x) => x.remove()); else { inyectar(); refrescarPins(); }
    }, 400);
  };
  document.addEventListener('input', (e) => { if (!P.contains(e.target)) revisar([{ target: e.target }]); }, true);
  let pIni = null; document.addEventListener('mousedown', (e) => (pIni = [e.clientX, e.clientY]), true);
  const tickerClic = (el) => { // solo si se tocó el ticker mismo (su texto), no cualquier parte del recuadro: así mover la tarjeta no cambia el bono
    for (let i = 0; el && i < 2; i++, el = el.parentElement) { const t = (el.innerText || '').trim().toUpperCase(); if (!t || t.length > 14) return null; const r = /^[A-Z]{3}\/[A-Z]{3}\d{2}$|^[A-Z0-9]{3,7}$/.test(t) && tk(t); if (r) return r[0]; }
    return null;
  };
  document.addEventListener('click', (e) => { if (e.target.closest('#bnr-panel,#bnr-win,.bnr-pin') || (pIni && Math.hypot(e.clientX - pIni[0], e.clientY - pIni[1]) > 4)) return; const k = tickerClic(e.target); if (k) { activo = k; precioManual = false; pintar(); } }, true);

  fetch(URL_CURVAS).then((r) => r.json()).then((d) => {
    FECHA = d.fecha;
    for (const [g, l] of Object.entries(d.grupos)) { GRP[g] = l; l.forEach((b) => (DB[b.ticker] = Object.assign({ grupo: g }, b))); }
    return Promise.all([
      fetch(DATA + 'tasas.json').then((r) => r.json()).then((t) => { // futuros de dólar: último cierre y el A3500
        const fs = Object.keys(t.fut || {}).sort().pop(), as = Object.keys(t.a3500 || {}).sort().pop(); if (!fs || !as) return;
        for (const r of t.fut[fs]) {
          const m = /^DLR(\d\d)(\d{4})$/.exec(r[0]); if (!m || !(r[2] > 0) || r[1] < new Date().toISOString().slice(0, 10)) continue;
          const e = { tipo: 'fut', grupo: 'fut', ticker: r[0], vto: r[1], precio: r[2], spot: t.a3500[as], fspot: as };
          DB[r[0]] = e; DB['DLR/' + MESES[+m[1] - 1] + m[2].slice(2)] = e; // Matriz los llama DLR/NOV26
        }
      }).catch(() => {}),
      fetch(DATA + 'acciones/metricas.json').then((r) => r.json()).then((d) => { // acciones: precio, rendimientos y beta
        for (const [k, v] of Object.entries(d.t || {})) if (v.ars && !DB[k]) DB[k] = { tipo: 'acc', grupo: 'acc', ticker: k, precio: v.ars.precio, fecha: v.ars.fecha, ret: v.ars.ret, beta: v.ars.beta };
      }).catch(() => {}),
    ]);
  }).then(() => {
    P.querySelector('#bnr-tk').innerHTML = Object.keys(DB).sort().map((k) => `<option value="${k}">`).join('');
    activo = tickerVisible(); pintar(); inyectar();
    try { (JSON.parse(localStorage.getItem('bnrPins') || '[]') || []).forEach((x) => fijar(x.k, x.q, x)); } catch (er) { } // las fichas fijas quedan de una vez para la otra
    new MutationObserver(revisar).observe(document.body, { childList: true, subtree: true, characterData: true });
  }).catch(() => (B.textContent = 'No pude traer las curvas de Bonerío.'));
})();
