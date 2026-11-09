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
      if (lab.children.length || !/^Cierre\s+Ant\.?\s*:?$/i.test((lab.textContent || '').trim()) || lab.closest('#bnr-panel,#bnr-win')) continue;
      let a = lab.parentElement, hit = null;
      for (let i = 0; a && i < 16 && !hit; i++, a = a.parentElement) for (const w of (a.innerText || a.textContent || '').toUpperCase().match(TOK) || []) { const r = tk(w); if (r) { hit = { el: a, k: r[0], suf: r[1] }; break; } }
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
      const b = DB[c.k], [p] = precioVale(c.k, c.suf) ? precioDe(c) : [NaN], cel = filas(b, p), n = Math.ceil(cel.length / 2);
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
  if (chrome.runtime && chrome.runtime.onMessage) chrome.runtime.onMessage.addListener((m) => { if (m && m.t === 'toggle') { const v = P.style.display === 'none'; P.style.display = v ? '' : 'none'; if (W && !v) W.style.display = 'none'; } }); // el ícono de la extensión
  const BUS = P.querySelector('.bus');
  BUS.onkeydown = (e) => { if (e.key === 'Enter') BUS.onchange(); };
  BUS.onchange = () => { const k = BUS.value.toUpperCase().trim(); if (!k) return; activo = k; precioManual = false; BUS.value = ''; pintar(); };

  // ---------- ventana flotante con la ficha, la curva o el portfolio de Bonerío (la sección sola, como en el Dashboard) ----------
  const SITE = 'https://boneriolocal.com.ar/';
  const CURVAS = { fut: ['tfut', 'tfS1'], usd: ['curva', 'yieldCurveContainer'], fija: ['pesos', 'pcard1'], cer: ['pesos', 'pcard3'], tamar: ['pesos', 'pcard4'], dl: ['pesos', 'pcard5'], dual: ['pesos', 'pcard6'], on: ['ons', 'onsC'], pv: ['pvs', 'pvsC'] };
  // solapas de la ventana: [nombre, [[subsolapa, pestaña de Bonerío, sección, subpestaña interna]]]; la sección se muestra sola (modo ?emb=sec del Dashboard)
  const VIS = {
    ficha: ['Ficha', (g) => (g === 'acc' ? [['', 'acc', 'accF', 'ficha']] : [['', 'bono', 'bono']])],
    curva: ['Curva', (g) => [['', ...(CURVAS[g] || CURVAS.usd)]]],
    vol: ['Volumen', () => [['', 'vol', 'vlS1']]],
    acc: ['Acciones', () => [['', 'acc', 'accP', 'pares']]],
    brc: ['Brecha y canje', () => [['Ratios', 'brc', 'brA'], ['Todos ahora', 'brc', 'brB']]],
    tfut: ['Futuros', () => [['', 'tfut', 'tfS1']]],
    sint: ['Sintéticos', () => [['', 'sint', 'syA']]],
    cim: ['Pases', () => [['', 'cim', 'cimC1']]],
    exp: ['Expectativas', () => [['Inflación', 'expi', 'thBBi'], ['Devaluación', 'expd', 'thBBd'], ['Forwards', 'expf', 'thF']]],
  };
  const SIGUE = { ficha: 1, curva: 1 }; // las que cambian con el bono
  let W = null, vista = 'curva', sub = 0, tamManual = false, LISTO = false;
  function ventana(v, j, oculta) {
    if (v && v !== vista) sub = 0; vista = v || vista; if (j != null) sub = j;
    if (!W) {
      W = document.createElement('div'); W.id = 'bnr-win'; tamManual = false; LISTO = false;
      W.innerHTML = '<header><span class="tt"></span><span class="tabs"></span><button class="x" title="Cerrar">✕</button></header><div class="subs"></div><div class="wb"><iframe allow="clipboard-write"></iframe></div>';
      document.body.appendChild(W); arrastrar(W);
      W.querySelector('.x').onclick = () => (W.style.display = 'none'); // se oculta, no se cierra: la próxima vez abre al instante
      W.addEventListener('mouseup', (e) => { if (e.target === W) tamManual = true; }); // lo agrandó desde la esquina: no lo ajustamos más
    }
    if (!oculta) W.style.display = '';
    const g = DB[activo] && DB[activo].grupo, L = VIS[vista][1](g), [, tab, id, sg] = L[sub] || L[0];
    W.querySelector('.tt').textContent = activo || '';
    W.querySelector('.tabs').innerHTML = Object.keys(VIS).filter((x) => (x !== 'curva' || (CURVAS[g] && g !== 'acc')) && (x !== 'ficha' || g !== 'fut')).map((x) => `<button data-v="${x}" class="${x === vista ? 'on' : ''}">${VIS[x][0]}</button>`).join('');
    W.querySelectorAll('.tabs button').forEach((x) => (x.onclick = () => ventana(x.dataset.v)));
    const S = W.querySelector('.subs'); S.hidden = L.length < 2;
    S.innerHTML = L.length < 2 ? '' : L.map((x, i) => `<button data-i="${i}" class="${i === sub ? 'on' : ''}">${x[0]}</button>`).join('');
    S.querySelectorAll('button').forEach((x) => (x.onclick = () => ventana(vista, +x.dataset.i)));
    const F = W.querySelector('iframe'), k = vista === 'ficha' && activo && g !== 'acc' ? activo : '';
    if (LISTO) { F.contentWindow.postMessage({ t: 'bnrSec', tab, id, g: sg || '', k }, '*'); return; } // la página ya está cargada: solo cambia de sección
    F.style.height = '2600px';
    const url = SITE + '?emb=sec&ht=*&tab=' + tab + '&id=' + id + (sg ? '&g=' + sg : '') + (k ? '#ficha=' + k + '&n=' + Date.now() : '');
    F.src = chrome.runtime.getURL('frame.html') + '#' + encodeURIComponent(url); // Bonerío va adentro de una página de la extensión: así no la frena la regla frame-src de Matriz
  }
  P.addEventListener('mouseenter', () => { if (!W && activo) ventana(null, null, true); }, { once: true }); // la carga empieza al acercarse al panel: cuando tocás, ya está

  // ---------- cargar un ticker en la boleta de Matriz (campo "Instrumento"); no manda ninguna orden ----------
  function aBoleta(k) {
    const vis = (e) => e && e.offsetParent && !e.closest('#bnr-panel,#bnr-win');
    let inp = [...document.querySelectorAll('input')].find((i) => vis(i) && /instrumento/i.test(i.placeholder || ''));
    if (!inp) for (const el of document.querySelectorAll('body *')) { // el texto "Buscar instrumento" o la etiqueta "Instrumento" suelen ser un div aparte (selectores tipo react-select): el input está en el mismo bloque
      if (el.children.length || !vis(el) || !/^(Buscar instrumento|Instrumento)$/i.test((el.textContent || '').trim())) continue;
      for (let a = el.parentElement, i = 0; a && i < 4 && !inp; i++, a = a.parentElement) inp = [...a.querySelectorAll('input')].find((x) => vis(x) && x.type !== 'hidden' && x.type !== 'checkbox');
      if (inp) break;
    }
    const cand = () => [...document.querySelectorAll('li,[role=option],mat-option,a,span,div')].filter((o) => !o.children.length && o.getClientRects().length && !o.closest('#bnr-panel,#bnr-win') && (o.textContent || '').trim().toUpperCase().startsWith(k));
    const antes = new Set(cand()); // solo vale una sugerencia que aparezca después de escribir (no una fila del panel de precios)
    const box = inp.closest('div') || inp; ['mousedown', 'mouseup', 'click'].forEach((t) => box.dispatchEvent(new MouseEvent(t, { bubbles: true }))); // abre el buscador
    inp.focus(); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(inp, k);
    inp.dispatchEvent(new Event('input', { bubbles: true })); inp.dispatchEvent(new Event('change', { bubbles: true })); inp.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: k.slice(-1) }));
    let n = 0; const iv = setInterval(() => { // elige la primera sugerencia nueva (en 24 hs si la hay)
      if (++n > 16) { clearInterval(iv); ['ArrowDown', 'Enter'].forEach((key) => inp.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key, code: key, keyCode: key === 'Enter' ? 13 : 40 }))); return; } // sin sugerencia reconocible: Enter elige la primera
      const ops = cand().filter((o) => !antes.has(o)), t = (x) => (x.textContent || '').trim().toUpperCase(), o = ops.find((x) => t(x) === k) || ops.find((x) => /24/.test(t(x))) || ops.find((x) => !/\(CI\)|\bCI\b/.test(t(x))) || ops[0]; // 24 hs: el ticker solo (Matriz pone «(CI)» al contado)
      if (o) { clearInterval(iv); const tg = o.closest('li,[role=option],mat-option') || o; ['mousedown', 'mouseup', 'click'].forEach((ev) => tg.dispatchEvent(new MouseEvent(ev, { bubbles: true, cancelable: true, view: window }))); }
    }, 250);
    return true;
  }
  window.addEventListener('message', (e) => { // la página manda la altura de la sección (la ventana queda justa) o el bono que se tocó
    if (!W || !e.data || e.source !== W.querySelector('iframe').contentWindow) return;
    if (e.data.t === 'bnrTk') { const k = String(e.data.k).toUpperCase(); aBoleta(k); const r = tk(k); if (r) { activo = r[0]; precioManual = false; pintar(); } return; }
    if (e.data.t !== 'bnrH') return;
    LISTO = true;
    const h = Math.max(150, +e.data.h || 0), F = W.querySelector('iframe'), top = W.querySelector('.wb').offsetTop + 2;
    const max = tamManual ? W.clientHeight - top : Math.min(Math.round(innerHeight * 0.55), innerHeight - W.offsetTop - 10) - top; // como mucho media pantalla: no tapa la operatoria
    const z = Math.max(0.6, Math.min(1, max / h)); // si no entra, se achica entera (como un zoom) en vez de cortarse
    Object.assign(F.style, { height: h + 'px', width: 100 / z + '%', transform: z < 1 ? `scale(${z})` : '', transformOrigin: '0 0' });
    if (!tamManual) W.style.height = Math.ceil(h * z) + top + 'px';
  });

  function pintar() {
    if (!activo) { B.innerHTML = '<span class="m">Abrí un bono en Matriz (o hacé clic en una fila) y aparece acá.</span>'; return; }
    const BT = (c) => `<div class="bt">${c ? '<button data-v="ficha">Ficha</button><button data-v="curva">Curva</button>' : '<button data-v="ficha">Ficha</button>'}<button data-v="mas">Más…</button><button data-v="boleta" title="Cargar en la boleta de Matriz">Boleta</button></div>`;
    const enlazar = () => B.querySelectorAll('.bt button').forEach((x) => (x.onclick = () => (x.dataset.v === 'boleta' ? aBoleta(activo) : ventana(x.dataset.v === 'mas' ? (SIGUE[vista] ? 'vol' : vista) : x.dataset.v))));
    const seguir = () => { if (W && W.querySelector('.tt').textContent !== activo) SIGUE[vista] ? ventana(null, null, W.style.display === 'none') : (W.querySelector('.tt').textContent = activo); }; // la ventana sigue al bono
    if (!DB[activo]) { B.innerHTML = `<div class="t">${activo}</div><div class="m">Sin datos en Bonerío para este ticker todavía; probá su ficha.</div>` + BT(false); enlazar(); if (W && W.querySelector('.tt').textContent !== activo) SIGUE[vista] ? ventana(null, null, W.style.display === 'none') : (W.querySelector('.tt').textContent = activo); return; }
    const b = DB[activo];
    if (b.tipo === 'acc') {
      ratios(); const r = b.ret || {}, pc = (x) => (x == null ? '-' : fmt(x * 100) + '%');
      B.innerHTML = `<div class="t">${activo}</div><div class="m">Acción · cierre ${b.fecha}</div>
        <div class="g"><span>Precio</span><span>$ ${fmt(b.precio)}</span><span>Var. día</span><span>${pc(r['1d'])}</span><span>1 mes</span><span>${pc(r['1m'])}</span><span>En el año</span><span>${pc(r.ytd)}</span>
        <span>P/E</span><span>${fmt(b.pe)}</span><span>P/VL</span><span>${fmt(b.pvl)}</span><span>EV/EBITDA</span><span>${fmt(b.ev)}</span><span>Beta</span><span>${fmt(b.beta)}</span></div>
        <div class="bt"><button data-v="ficha">Acciones</button><button data-v="mas">Más…</button><button data-v="boleta" title="Cargar en la boleta de Matriz">Boleta</button></div>`;
      enlazar(); seguir(); return;
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
    const f = ajuste(b.grupo, b.ley);
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
    if (W && W.querySelector('.tt').textContent !== activo) SIGUE[vista] ? ventana(null, null, W.style.display === 'none') : (W.querySelector('.tt').textContent = activo); // la ventana sigue al bono
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
    new MutationObserver(revisar).observe(document.body, { childList: true, subtree: true, characterData: true });
  }).catch(() => (B.textContent = 'No pude traer las curvas de Bonerío.'));
})();
