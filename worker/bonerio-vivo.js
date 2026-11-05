/* Bonerío en vivo: Cloudflare Worker entre la página y Primary (cuenta de Bull).
   La clave queda acá como secret (ROFEX_USER, ROFEX_PASS); la página nunca la ve.
   Rutas (todas GET, con CORS para la página):
   - /live/<ep>  (arg_bonds, arg_notes, arg_corp, arg_stocks, arg_cedears): el mismo formato que data912.com/live/<ep>, con precio, puntas
                 y volumen de Primary en tiempo real. La lista es la de data912 más lo que Primary tiene y data912 todavía no (papeles nuevos,
                 que así aparecen el mismo día). Si Primary falla, devuelve la de data912 tal cual; si falla data912, la de Primary sola.
   - /caucion    caución por plazo, de Primary (y BYMA donde Primary no tenga): { ts, src, ARS, USD, EXT }, cada fila [días, compra, venta, última, cierre, vwap, monto].
   - /stream     websocket: al conectarse manda { s: {ep: filas} } y después { u: {ticker: [último, var %, compra, cant., venta, cant.]} } con cada cambio.
   - /merv/buscar?q=MERV  diagnóstico: los instrumentos de Primary que contienen ese texto (símbolo, subyacente, cfi, vencimiento).
   - /merv       el ETF del MSCI Merval (MERV), sus futuros y sus opciones, con puntas, último, cierre, ajuste e interés abierto: { ts, ins: [...] }.
   - /book/<ticker>  caja de puntas de Primary (hasta 5 niveles, 24 hs; con ?s=ci, contado inmediato): { t, BI: [[precio, cantidad], ...], OF: [...], LA: [precio, cantidad] }.
   Sin el Durable Object (FEED), cada respuesta se guarda 15 segundos: muchos visitantes a la vez = una sola consulta a Primary. */

const D912 = 'https://data912.com/live/';
const EPS = ['arg_bonds', 'arg_notes', 'arg_corp', 'arg_stocks', 'arg_cedears'];
const SEPS = EPS.filter((e) => e !== 'arg_cedears'); // lo que va por la conexión permanente: los CEDEARs no los usa la página y son la mayoría de los mensajes de Primary (cada mensaje que recibe el Durable Object cuenta para el límite diario)
const BYMA = 'https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/cauciones';
const TTL = 15;
const sym = (s) => 'MERV - XMEV - ' + s + ' - 24hs'; // precios de 24 hs, como data912

const MEM = {};
let LASTERR = '';
let TOK = null, TOKT = 0, WSST = 0; // el token de Primary dura un día; se renueva cada 6 horas o si lo rechaza
const base = (env) => String(env.ROFEX_URL || 'https://api.bull.xoms.com.ar').trim().replace(/\/+$/, '');
async function token(env, force) {
  if (!force && TOK && Date.now() - TOKT < 6 * 3600e3) return TOK;
  const r = await fetch(base(env) + '/auth/getToken', { method: 'POST', headers: { 'X-Username': String(env.ROFEX_USER || '').trim(), 'X-Password': String(env.ROFEX_PASS || '').trim() } });
  const t = r.headers.get('X-Auth-Token');
  if (!t) throw new Error('login Primary: ' + r.status);
  TOK = t; TOKT = Date.now(); return t;
}

// foto de muchos símbolos en una sola conexión: se suscribe por websocket, junta el primer mensaje de cada uno y cierra
let SNAPERR = null;
async function snapshot(env, syms, ms, ents) {
  let ws;
  for (const force of [false, true]) {
    const r = await fetch(base(env) + '/', { headers: { Upgrade: 'websocket', 'X-Auth-Token': await token(env, force) } });
    if (r.webSocket) { ws = r.webSocket; break; }
    WSST = r.status;
  }
  if (!ws) throw new Error('websocket de Primary rechazado: ' + WSST);
  ws.accept();
  const out = {}, want = new Set(syms);
  await new Promise((done) => {
    const end = setTimeout(done, ms);
    ws.addEventListener('message', (e) => {
      let m; try { m = JSON.parse(e.data); } catch (x) { return; }
      if (m.status === 'ERROR' || m.type === 'error') { SNAPERR = String(m.description || m.message || JSON.stringify(m)).slice(0, 300); return; }
      if (m.type !== 'Md' || !m.instrumentId) return;
      out[m.instrumentId.symbol] = m.marketData || {};
      want.delete(m.instrumentId.symbol);
      if (!want.size) { clearTimeout(end); done(); }
    });
    ws.addEventListener('close', () => { clearTimeout(end); done(); });
    for (let i = 0; i < syms.length; i += 100) {
      ws.send(JSON.stringify({ type: 'smd', level: 1, depth: 1, entries: ents || ['BI', 'OF', 'LA', 'CL', 'EV'], products: syms.slice(i, i + 100).map((s) => ({ symbol: s, marketId: 'ROFX' })) }));
    }
  });
  try { ws.close(1000, 'ok'); } catch (x) {}
  return out;
}

const hoyBA = () => new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10);
const deHoy = (ms) => ms && new Date(ms - 3 * 3600e3).toISOString().slice(0, 10) === hoyBA();
const px = (o) => (o && o.price > 0 ? o.price : null);

// la lista de papeles de Primary (24 hs) por tipo, según el código CFI: E acciones (ED: CEDEAR), C fondos y ETF, D deuda (S + fecha: letras; obligaciones negociables)
let PEX = null, PEXT = 0;
async function pextra(env) {
  if (PEX && Date.now() - PEXT < 3600e3) return PEX;
  const L = await instruments(env), out = {}; EPS.forEach((e) => (out[e] = []));
  L.forEach((i) => {
    const m = /^MERV - XMEV - ([A-Z0-9.]+) - 24hs$/.exec((i.instrumentId || {}).symbol || ''); if (!m) return;
    const c = String(i.cficode || '').toUpperCase(), d = String(i.securityDescription || i.description || '').toUpperCase(), t = m[1];
    const ep = c[0] === 'E' || c[0] === 'C' ? (c[1] === 'D' && c[0] === 'E' || /CEDEAR/.test(d) ? 'arg_cedears' : 'arg_stocks') : c[0] === 'D' ? (/^S\d{2}[A-Z]\d$/.test(t) ? 'arg_notes' : /OBLIGACI|(^|[^A-Z])O\.? ?N\.?([^A-Z]|$)/.test(d) ? 'arg_corp' : 'arg_bonds') : null;
    if (ep) out[ep].push(t);
  });
  if (L.length) { PEX = out; PEXT = Date.now(); }
  return out;
}
// suma a la lista de data912 lo que Primary tiene y data912 todavía no (con el nombre de Primary: BPOA7 es el BPA7 de data912)
function addP(rows, P) {
  if (!P || !P.length) return rows;
  const have = new Set(rows.map((x) => x.symbol)), add = P.filter((t) => !have.has(t) && !have.has(t.replace(/^BPO/, 'BP'))).map((t) => ({ symbol: t, src: 'primary' }));
  return add.length ? rows.concat(add) : rows;
}

async function live(env, ep) {
  let rows = null; try { rows = await (await fetch(D912 + ep, { cf: { cacheTtl: 10 } })).json(); } catch (e) { } // data912: la lista base y el volumen donde Primary no lo mande
  if (!env.ROFEX_USER) return rows;
  if (!Array.isArray(rows)) rows = [];
  try { rows = addP(rows, (await pextra(env))[ep]); } catch (e) { LASTERR = String(e.message || e); }
  if (!rows.length) throw new Error('sin lista: fallaron data912 y Primary');
  let md = {};
  try { md = await snapshot(env, rows.map((r) => sym(r.symbol)), 3500); } catch (e) { LASTERR = String(e.message || e); return rows; }
  if (!Object.keys(md).length) LASTERR = 'Primary no mandó precios en 3,5 s';
  return rows.map((r) => patch(r, md[sym(r.symbol)]));
}

// la fila de data912 con lo que mandó Primary: último de hoy, variación contra el cierre anterior, las puntas y el monto operado hoy
const num = (v) => { v = v && typeof v === 'object' ? v.size || v.price : v; return +v > 0 ? +v : 0; };
function patch(r, m) {
  if (!m) return r;
  const bi = (m.BI || [])[0], of = (m.OF || [])[0], la = deHoy(m.LA && m.LA.date) ? px(m.LA) : null, cl = px(m.CL), o = Object.assign({}, r, { src: 'primary' });
  if (la) { o.c = la; if (cl) o.pct_change = (la / cl - 1) * 100; } else if (!(r.c > 0) && cl) { o.c = cl; o.pct_change = 0; } // papel que data912 no tiene: sin operaciones hoy, el cierre anterior
  const ev = la ? num(m.EV) : 0; if (ev && r.v > 0 && ev > r.v && ev / r.v < 1.5) o.v = ev; // monto de Primary solo si confirma el de data912 (en deuda puede venir en otra escala: por cada 100 nominales o en la moneda del bono)
  if (bi) { o.px_bid = bi.price; o.q_bid = bi.size; }
  if (of) { o.px_ask = of.price; o.q_ask = of.size; }
  return o;
}

/* Feed: un Durable Object con UNA conexión permanente a Primary suscripta a todos los tickers.
   Cada cambio se empuja a los navegadores conectados a /stream (websocket) en tandas de 250 ms.
   Si nadie mira durante 10 minutos, corta la conexión con Primary y se apaga. */
export class Feed {
  constructor(ctx, env) { this.ctx = ctx; this.env = env; this.rows = {}; this.idx = {}; this.md = {}; this.ws = null; this.cl = new Set(); this.dirty = new Set(); this.seen = Date.now(); this.lt = 0; this.lists_t = 0; }
  ok() { return !!(this.ws && this.lt && Date.now() - this.lt < 15 * 60e3); }
  async lists() { // la lista de data912 más los papeles que Primary tiene y data912 todavía no; si data912 falla, queda la anterior (o la de Primary sola)
    const nu = []; let P = null; try { P = await pextra(this.env); } catch (e) { LASTERR = String(e.message || e); }
    await Promise.all(EPS.map(async (ep) => { let r = null; try { r = await (await fetch((this.env.D912 || D912) + ep)).json(); } catch (e) {}
      if (!Array.isArray(r) || !r.length) r = this.rows[ep] || [];
      r = addP(r, P && P[ep]); if (!r.length) return;
      this.rows[ep] = r; if (SEPS.includes(ep)) r.forEach((x) => { const k = sym(x.symbol); if (!this.idx[k]) nu.push(k); this.idx[k] = x.symbol; }); }));
    this.lists_t = Date.now(); this.by = {}; EPS.forEach((ep) => (this.rows[ep] || []).forEach((x) => (this.by[x.symbol] = x)));
    if (this.ws && nu.length) this.sub(nu);
  }
  sub(list) { for (let i = 0; i < list.length; i += 100) this.ws.send(JSON.stringify({ type: 'smd', level: 1, depth: 1, entries: ['BI', 'OF', 'LA', 'CL', 'EV'], products: list.slice(i, i + 100).map((s) => ({ symbol: s, marketId: 'ROFX' })) })); }
  async connect() {
    let ws;
    for (const force of [false, true]) { const r = await fetch(base(this.env) + '/', { headers: { Upgrade: 'websocket', 'X-Auth-Token': await token(this.env, force) } }); if (r.webSocket) { ws = r.webSocket; break; } }
    if (!ws) throw new Error('websocket de Primary rechazado');
    ws.accept(); this.ws = ws;
    ws.addEventListener('message', (e) => this.onMd(e.data));
    const lost = () => { if (this.ws !== ws) return; this.ws = null; if (this.alive()) setTimeout(() => this.connect().catch((x) => (LASTERR = String(x.message || x))), 3000); };
    ws.addEventListener('close', lost); ws.addEventListener('error', lost);
    this.sub(Object.keys(this.idx));
  }
  alive() { return this.cl.size > 0 || Date.now() - this.seen < 10 * 60e3; }
  start() {
    if (!this.go) this.go = (async () => { await this.lists(); await this.connect(); await this.ctx.storage.setAlarm(Date.now() + 60e3); })().catch((e) => { LASTERR = String(e.message || e); this.go = null; });
    return this.go;
  }
  onMd(data) {
    let m; try { m = JSON.parse(data); } catch (x) { return; }
    if (m.type !== 'Md' || !m.instrumentId) return;
    const k = m.instrumentId.symbol; this.md[k] = Object.assign(this.md[k] || {}, m.marketData || {}); this.lt = Date.now();
    const dd = new Date().toISOString().slice(0, 10); if (this.nd !== dd) { this.nd = dd; this.nm = 0; } this.nm++; // mensajes de hoy (UTC), para ver el consumo en /diag
    if (!this.cl.size) return;
    this.dirty.add(k); if (!this.tm) this.tm = setTimeout(() => this.flush(), 250);
  }
  flush() {
    this.tm = null; const u = {};
    this.dirty.forEach((k) => { const t = this.idx[k], r = t && this.by[t]; if (!r) return; const o = patch(r, this.md[k]); u[t] = [o.c, o.pct_change, o.px_bid, o.q_bid, o.px_ask, o.q_ask]; });
    this.dirty.clear(); if (!Object.keys(u).length) return;
    const msg = JSON.stringify({ u }); this.cl.forEach((c) => { try { c.send(msg); } catch (e) { this.cl.delete(c); } });
  }
  merged(ep) { return (this.rows[ep] || []).map((r) => patch(r, this.md[sym(r.symbol)])); }
  async alarm() {
    if (!this.alive()) { const w = this.ws; this.ws = null; this.go = null; try { w && w.close(1000, 'sin visitantes'); } catch (e) {} return; }
    if (Date.now() - this.lists_t > 10 * 60e3) await this.lists();
    if (!this.ws && this.go) await this.connect().catch((x) => (LASTERR = String(x.message || x)));
    await this.ctx.storage.setAlarm(Date.now() + 60e3);
  }
  async fetch(req) {
    const u = new URL(req.url); this.seen = Date.now(); await this.start();
    if (u.pathname === '/stream') {
      if (req.headers.get('Upgrade') !== 'websocket') return new Response('websocket', { status: 426 });
      const [c, s] = Object.values(new WebSocketPair()); s.accept(); this.cl.add(s);
      const bye = () => { this.cl.delete(s); this.seen = Date.now(); }; s.addEventListener('close', bye); s.addEventListener('error', bye);
      const snap = {}; SEPS.forEach((ep) => (snap[ep] = this.merged(ep))); s.send(JSON.stringify({ s: snap }));
      return new Response(null, { status: 101, webSocket: c });
    }
    if (u.pathname === '/stats') return new Response(JSON.stringify({ dia: this.nd || null, mensajes: this.nm || 0, visitantes: this.cl.size, simbolos: Object.keys(this.idx).length }));
    const ep = u.pathname.replace(/^\/live\//, '');
    if (!this.ok() || !this.rows[ep] || !SEPS.includes(ep)) return new Response('', { status: 204 });
    return new Response(JSON.stringify(this.merged(ep)));
  }
}

// caución por Primary: los símbolos 'MERV - XMEV - <moneda> - <n>D' (la lista de instrumentos se guarda 6 horas) y una foto por websocket
let CSY = null, CSYT = 0, INS = null, INST = 0, INSERR = '';
async function instruments(env) { // la lista de instrumentos de Primary (se guarda 6 horas)
  if (INS && Date.now() - INST < 3 * 3600e3) return INS;
  let r = await fetch(base(env) + '/rest/instruments/details', { headers: { 'X-Auth-Token': await token(env) } });
  if (r.status === 401 || r.status === 403) r = await fetch(base(env) + '/rest/instruments/details', { headers: { 'X-Auth-Token': await token(env, true) } });
  const j = await r.json(); INS = j.instruments || []; INST = INS.length ? Date.now() : 0; INSERR = INS.length ? '' : String(j.description || j.message || j.status || 'lista vacía'); return INS; // vacía: no se guarda
}
// el ETF del MSCI Merval (MERV), sus futuros y sus opciones: se buscan en la lista de Primary por el subyacente y el código CFI, no por el nombre
const nm = (x) => String(x || '').toUpperCase().replace(/^MERV - XMEV - /, '').replace(/ - (24HS|CI|48HS)$/, '').trim();
let MVI = null, MVIT = 0;
async function mervIns(env, again) {
  if (MVI && MVI.length && Date.now() - MVIT < 3600e3) return MVI;
  const L = await instruments(env), out = [], seen = {};
  L.forEach((i) => {
    const s = (i.instrumentId || {}).symbol || '', n = nm(s), u = nm(i.underlying), cfi = String(i.cficode || '').toUpperCase();
    if (/ - CI$/.test(s) || / - 48hs$/i.test(s)) return; // de BYMA, solo 24 hs
    const ms = /MSCI MERVAL|GFORCE/.test(u), isE = ms && cfi[0] !== 'O' && cfi[0] !== 'F' && cfi[0] !== 'M', etf = (n === 'MERV' && /^MERV - XMEV - /.test(s)) || (isE && !/[DC]$/.test(n)); // el ETF en pesos (MERVD/MERVC, en dólares, quedan como etfx)
    const ix = /^(I\.)?MMSCI$/.test(n), rel = ix || etf || ms || /(^|[^A-Z])MERV([^A-Z]|$)/.test(u) || /^(MERV|MVL)\//.test(s) || /^(I\.)?MERV[ /]/.test(n) || (/^MERV - XMEV - /.test(s) && /^(MER|MVL)[CV]\d/.test(n));
    if (!rel || seen[s]) return; seen[s] = 1;
    const k = ix || cfi[0] === 'M' ? 'idx' : etf ? 'etf' : isE ? 'etfx' : cfi[0] === 'O' ? (cfi[1] === 'P' ? 'put' : 'call') : cfi[0] === 'F' ? 'fut' : /C\d|CALL/.test(n) ? 'call' : /V\d|PUT/.test(n) ? 'put' : 'otro';
    out.push({ s: s, n: n, k: k, cfi: cfi, u: i.underlying || null, mat: i.maturityDate || null, K: i.strikePrice || null, mult: i.contractMultiplier || 1, ccy: i.currency || null, tick: i.minPriceIncrement || null, seg: (i.segment || {}).marketSegmentId || null });
  });
  if (!out.length && !again && Date.now() - INST > 15 * 60e3) { INS = null; return mervIns(env, true); }
  if (out.length && !out.some((x) => x.k === 'idx')) ['MERV - XMEV - MMSCI', 'MMSCI', 'I.MMSCI'].forEach((s) => out.push({ s: s, n: 'MMSCI', k: 'idx', cfi: null, u: null, mat: null, K: null, mult: 1, ccy: 'ARS', tick: null, seg: 'MERV', fb: 1 })); // el índice MSCI Merval (MMSCI en Primary) si no figura en la lista: se prueba por REST con cada formato y queda el que responda
  if (out.length && !out.some((x) => x.k === 'etf')) out.push({ s: 'MERV - XMEV - MERV - 24hs', n: 'MERV', k: 'etf', cfi: null, u: null, mat: null, K: null, mult: 1, ccy: 'ARS', tick: null, seg: 'MERV' }); // el ETF no figura en la lista: se pide igual por su ticker // instrumentos nuevos: la lista guardada puede ser vieja
  MVI = out; MVIT = Date.now(); return out;
}
async function buscar(env, q) { // diagnóstico: qué tiene Primary con ese texto (símbolo, subyacente, descripción), sin datos de la cuenta
  const L = await instruments(env), Q = String(q || 'MERV').toUpperCase(), hits = [];
  L.forEach((i) => { const s = (i.instrumentId || {}).symbol || '', t = [nm(s), i.underlying].join(' ').toUpperCase(); if (t.indexOf(Q) >= 0 && hits.length < 300) hits.push({ s: s, u: i.underlying || null, cfi: i.cficode || null, mat: i.maturityDate || null, K: i.strikePrice || null, seg: (i.segment || {}).marketSegmentId || null, d: i.securityDescription || i.description || null }); });
  return { total: L.length, err: INSERR || null, q: Q, n: hits.length, hits: hits };
}
async function merv(env) {
  const L = await mervIns(env), md = {}, E = ['BI', 'OF', 'LA', 'CL', 'SE', 'OI']; let err = null; SNAPERR = null;
  // por websocket solo los que figuran en la lista de Primary (un símbolo inexistente puede tirar toda la suscripción)
  try { Object.assign(md, await snapshot(env, L.filter((x) => x.cfi).map((x) => x.s), 4000, E)); } catch (e) { err = String(e.message || e); }
  if (SNAPERR) err = SNAPERR;
  // lo que no llegó por websocket, uno por uno por REST (primero el ETF y el índice, después las opciones)
  const rest = L.filter((x) => !md[x.s] || !Object.keys(md[x.s]).length).sort((a, b) => (a.k === 'etf' || a.k === 'idx' ? 0 : 1) - (b.k === 'etf' || b.k === 'idx' ? 0 : 1)).slice(0, 42);
  if (rest.length) { const tk = await token(env); await Promise.all(rest.map(async (x) => { try { const r = await fetch(base(env) + '/rest/marketdata/get?marketId=ROFX&symbol=' + encodeURIComponent(x.s) + '&entries=' + E.join(',') + '&depth=1', { headers: { 'X-Auth-Token': tk } }); const j = await r.json(); if (j && j.marketData) md[x.s] = j.marketData; else if (j && j.status === 'ERROR' && !err && !x.fb) err = x.n + ': ' + String(j.description || '').slice(0, 200); } catch (e) { } })); }
  const p = (o) => (o && o.price > 0 ? o.price : null), lv = (a) => { a = Array.isArray(a) ? a[0] : a; return a && a.price > 0 ? [a.price, a.size] : null; };
  const has = (x) => md[x.s] && Object.keys(md[x.s]).length, L2 = L.filter((x) => !x.fb || has(x)); // de los formatos probados del índice, solo el que respondió
  return { ts: Date.now(), err: err, ws: L.length - rest.length, ins: L2.map((x) => { const m = md[x.s] || {}; return Object.assign({}, x, { BI: lv(m.BI), OF: lv(m.OF), LA: m.LA && m.LA.price > 0 ? [m.LA.price, m.LA.size, m.LA.date || null] : null, CL: p(m.CL), SE: p(m.SE), OI: m.OI && (m.OI.size || m.OI.price) || null, EV: m.EV || null, NV: m.NV || null }); }) };
}
async function cauSyms(env) {
  if (CSY && Date.now() - CSYT < 6 * 3600e3) return CSY;
  const L = await instruments(env), out = {};
  L.forEach((i) => {
    const s = (i.instrumentId || {}).symbol || '', m = /^MERV - XMEV - (.+) - (\d+)D$/.exec(s); if (!m || +m[2] > 35) return;
    const c = String(i.currency || '').toUpperCase(), n = m[1].toUpperCase();
    out[s] = [n === 'PESOS' || c === 'ARS' ? 'ARS' : c === 'EXT' || /EXT|CABLE/.test(n) ? 'EXT' : 'USD', +m[2]];
  });
  CSY = out; CSYT = Date.now(); return out;
}
async function cauPrimary(env) {
  const S = await cauSyms(env), syms = Object.keys(S); if (!syms.length) return null;
  const md = await snapshot(env, syms, 4000), out = { ARS: [], USD: [], EXT: [] };
  syms.forEach((s) => { const d = md[s]; if (!d) return; const lv = (a) => px(Array.isArray(a) ? a[0] : a);
    const row = [S[s][1], lv(d.BI), lv(d.OF), d.LA && deHoy(d.LA.date) ? px(d.LA) : null, px(d.CL), null, null];
    if (row.slice(1).some((v) => v != null)) out[S[s][0]].push(row); });
  ['ARS', 'USD', 'EXT'].forEach((m) => out[m].sort((a, b) => a[0] - b[0]));
  return out;
}
async function caucion(env) {
  let P = null; // primero Primary; BYMA (datos abiertos) completa la moneda que Primary no tenga con operaciones de hoy
  if (env && env.ROFEX_USER) try { P = await cauPrimary(env); } catch (e) { LASTERR = String(e.message || e); }
  let B = null; try { B = await cauByma(); } catch (e) { }
  const live = (rows) => (rows || []).some((r) => r[3] != null);
  const out = { ts: new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 16), src: {}, ARS: [], USD: [], EXT: [] };
  ['ARS', 'USD', 'EXT'].forEach((m) => { const p = P && P[m], b = B && B[m]; const usp = live(p) || (p && p.length && !live(b));
    out[m] = (usp ? p : b) || []; out.src[m] = usp ? 'Primary' : 'BYMA'; });
  return out;
}

async function cauByma() {
  const r = await fetch(BYMA, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json', Origin: 'https://open.bymadata.com.ar', Referer: 'https://open.bymadata.com.ar/' },
    body: JSON.stringify({ excludeZeroPxAndQty: false, T2: true, T1: true, T0: true }) });
  let l = await r.json(); l = Array.isArray(l) ? l : l.data || [];
  const pc = (v) => (v > 0 ? Math.round(v * 1e6) / 1e4 : null), out = { ts: new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 16), ARS: [], USD: [], EXT: [] };
  l.forEach((x) => { const m = x.denominationCcy, d = x.daysToMaturity; if (!out[m] || !(d > 0 && d <= 35)) return;
    const row = [d, pc(x.bidPrice), pc(x.offerPrice), pc(x.trade), pc(x.closingPrice), pc(x.vwap), x.volumeAmount > 0 ? x.volumeAmount : null];
    if (row.slice(1).some((v) => v != null)) out[m].push(row); });
  ['ARS', 'USD', 'EXT'].forEach((m) => out[m].sort((a, b) => a[0] - b[0]));
  return out;
}

function cors(req, env) {
  const o = req.headers.get('Origin') || '', ok = (env.ORIGINS || 'https://boneriolocal.com.ar').split(',').map((s) => s.trim());
  return { 'Access-Control-Allow-Origin': ok.includes(o) || /^http:\/\/localhost(:\d+)?$/.test(o) ? o : ok[0], Vary: 'Origin', 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'public, max-age=' + TTL };
}

export default {
  async fetch(req, env) {
    const u = new URL(req.url), h = cors(req, env);
    if (req.method === 'OPTIONS') return new Response(null, { headers: h });
    if (u.pathname === '/diag') { // chequeo: login, websocket y una foto de AL30 y GD30 (no muestra la clave)
      const d = { usuario: !!env.ROFEX_USER, clave: !!env.ROFEX_PASS, url: base(env), ultimoError: LASTERR };
      try { await token(env, true); d.login = 'ok'; } catch (e) { d.login = String(e.message || e); return new Response(JSON.stringify(d, null, 1), { headers: h }); }
      try { const md = await snapshot(env, [sym('AL30'), sym('GD30')], 5000); d.websocket = 'ok'; d.precios = md; } catch (e) { d.websocket = String(e.message || e); }
      try { const P = await pextra(env); d.nuevos = {}; await Promise.all(EPS.map(async (ep) => { let r = []; try { r = await (await fetch(D912 + ep)).json(); } catch (e) { } const a = addP(Array.isArray(r) ? r : [], P[ep]); d.nuevos[ep] = { data912: Array.isArray(r) ? r.length : 0, dePrimary: a.length - (Array.isArray(r) ? r.length : 0), ej: a.filter((x) => x.src === 'primary').slice(0, 25).map((x) => x.symbol) }; })); } catch (e) { d.nuevos = String(e.message || e); } // papeles que suma Primary
      if (env.FEED) try { d.stream = await (await env.FEED.get(env.FEED.idFromName('main')).fetch(new Request(u.origin + '/stats'))).json(); } catch (e) { d.stream = String(e.message || e); } // mensajes de Primary recibidos hoy por la conexión permanente
      return new Response(JSON.stringify(d, null, 1), { headers: h });
    }
    const bk = /^\/book\/((?:DLR|CAUC)(?:\/|%2F)[A-Z]{3}\d{2}|CAU-(?:ARS|USD|EXT)(?:-\d+)?|[A-Z0-9]{2,10})$/i.exec(u.pathname); // también la caución: CAU-<moneda>[-<días>] // un bono o acción (MERV - XMEV - <t> - 24hs) o un futuro de A3 (DLR/NOV26)
    if (bk) bk[1] = decodeURIComponent(bk[1]).toUpperCase();
    if (bk) { // caja de puntas a pedido (al pasar el mouse por un bono): se guarda 2 segundos
      const ci = u.searchParams.get('s') === 'ci', k = u.pathname + (ci ? '?ci' : ''), m = MEM[k], hb = Object.assign({}, h, { 'Cache-Control': 'no-store' });
      if (m && Date.now() - m.t < 2000) return new Response(m.b, { headers: hb });
      try {
        const pz = ci ? ' - CI' : ' - 24hs', lv = (a) => (Array.isArray(a) ? a : a ? [a] : []).filter((x) => x && x.price > 0).slice(0, 5).map((x) => [x.price, x.size]);
        const get = async (t) => { // ?s=ci: contado inmediato (la ficha, con su switch CI / 24 hs)
          const q = base(env) + '/rest/marketdata/get?marketId=ROFX&symbol=' + encodeURIComponent(t.includes('/') || t.startsWith('MERV - ') ? t : 'MERV - XMEV - ' + t + pz) + '&entries=BI,OF,LA,CL,SE&depth=5';
          let r = await fetch(q, { headers: { 'X-Auth-Token': await token(env) } });
          if (r.status === 401 || r.status === 403) r = await fetch(q, { headers: { 'X-Auth-Token': await token(env, true) } });
          const j = await r.json(); return (j && j.marketData) || {};
        };
        let t = bk[1], md;
        const cm = /^CAU-(ARS|USD|EXT)(?:-(\d+))?$/.exec(t);
        if (cm) { // la caución de esa moneda: el plazo pedido o, si no, el más corto con puntas
          const S = await cauSyms(env), L = Object.keys(S).filter((s) => S[s][0] === cm[1] && (!cm[2] || S[s][1] === +cm[2])).sort((a, b) => S[a][1] - S[b][1]); md = {};
          for (const s of L) { const m2 = await get(s); if (lv(m2.BI).length || lv(m2.OF).length) { md = m2; t = 'Caución ' + { ARS: 'en pesos', USD: 'MEP', EXT: 'cable' }[cm[1]] + ' · ' + S[s][1] + (S[s][1] === 1 ? ' día' : ' días'); break; } }
        } else md = await get(t);
        if (!cm && !t.includes('/') && !lv(md.BI).length && !lv(md.OF).length) { // sin puntas en pesos (BOPREAL y otros que operan en dólares o con otro nombre en Primary): la especie D, la C o el nombre de Primary
          const al = []; try { (await instruments(env)).forEach((i) => { const m = /^MERV - XMEV - (.+) - (24hs|CI)$/.exec((i.instrumentId || {}).symbol || ''); if (m && m[2] === pz.slice(3) && m[1] !== t && m[1].replace(/^BPO/, 'BP').replace(/[DC]$/, '') === t) al.push(m[1]); }); } catch (e) { }
          for (const c of [t + 'D', t + 'C'].concat(al.filter((x) => x !== t + 'D' && x !== t + 'C'))) { const m2 = await get(c); if (lv(m2.BI).length || lv(m2.OF).length) { t = c; md = m2; break; } }
        }
        const body = JSON.stringify({ t: Date.now(), s: t, BI: lv(md.BI), OF: lv(md.OF), LA: md.LA && md.LA.price > 0 ? [md.LA.price, md.LA.size, md.LA.date || null] : null, CL: md.CL && md.CL.price > 0 ? md.CL.price : md.SE && md.SE.price > 0 ? md.SE.price : null });
        MEM[k] = { t: Date.now(), b: body };
        return new Response(body, { headers: hb });
      } catch (e) { LASTERR = String(e.message || e); return new Response(JSON.stringify({ error: LASTERR }), { status: 502, headers: hb }); }
    }
    if (u.pathname === '/merv/buscar') { const hb = Object.assign({}, h, { 'Cache-Control': 'no-store' }); try { return new Response(JSON.stringify(await buscar(env, u.searchParams.get('q'))), { headers: hb }); } catch (e) { return new Response(JSON.stringify({ error: String(e.message || e) }), { status: 502, headers: hb }); } }
    if (u.pathname === '/merv') { // ETF MERV, futuros y opciones (se guarda 10 segundos)
      const m = MEM['/merv'], hb = Object.assign({}, h, { 'Cache-Control': 'no-store' });
      if (m && Date.now() - m.t < 10000) return new Response(m.b, { headers: hb });
      try { const body = JSON.stringify(await merv(env)); MEM['/merv'] = { t: Date.now(), b: body }; return new Response(body, { headers: hb }); }
      catch (e) { LASTERR = String(e.message || e); return new Response(JSON.stringify({ error: LASTERR }), { status: 502, headers: hb }); }
    }
    const ep = u.pathname.replace(/^\/live\//, ''), feed = env.FEED && env.ROFEX_USER ? env.FEED.get(env.FEED.idFromName('main')) : null;
    if (u.pathname === '/stream') return feed ? feed.fetch(req) : new Response('sin Feed', { status: 503 }); // precios empujados al instante
    if (u.pathname !== '/caucion' && !EPS.includes(ep)) return new Response('{"error":"ruta"}', { status: 404, headers: h });
    if (feed && u.pathname !== '/caucion') { // con la conexión permanente ya abierta, la lista sale al instante
      try { const r = await feed.fetch(req); if (r.status === 200) return new Response(r.body, { headers: Object.assign({}, h, { 'Cache-Control': 'no-store' }) }); } catch (e) {}
    }
    const m = MEM[u.pathname]; // en memoria (en workers.dev la caché de Cloudflare no guarda nada)
    if (m && Date.now() - m.t < TTL * 1000) return new Response(m.b, { headers: h });
    try {
      const body = JSON.stringify(u.pathname === '/caucion' ? await caucion(env) : await live(env, ep));
      MEM[u.pathname] = { t: Date.now(), b: body };
      return new Response(body, { headers: h });
    } catch (e) {
      return new Response(JSON.stringify({ error: String(e.message || e) }), { status: 502, headers: h });
    }
  },
};
