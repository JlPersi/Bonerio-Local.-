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
   Precios con demora: quien no es PRO (?t=<token de Supabase> sin pro_hasta vigente ni prueba) recibe en /stream y /live la foto de hace 20 minutos,
   en /caucion solo BYMA (datos abiertos) y en /book y /merv un 403. Hasta FREE_HASTA todos son PRO (igual que la página).
   Sin el Durable Object (FEED), cada respuesta se guarda 15 segundos: muchos visitantes a la vez = una sola consulta a Primary. */

const D912 = 'https://data912.com/live/';
const EPS = ['arg_bonds', 'arg_notes', 'arg_corp', 'arg_stocks', 'arg_cedears'];
const SEPS = EPS.filter((e) => e !== 'arg_cedears'); // lo que va por la conexión permanente: los CEDEARs no los usa la página y son la mayoría de los mensajes de Primary (cada mensaje que recibe el Durable Object cuenta para el límite diario)
const BYMA = 'https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/cauciones';
const TTL = 15;
const SB = 'https://sbvebxqeltvkerrarzqn.supabase.co', SBK = 'sb_publishable_yhGb-WD_rjY-PohFtWjRig_g54LnhVf'; // la clave pública de la página (auth.js), no es un secreto
const FREE_HASTA = '2026-11-11', DEMORA = 20 * 60e3;
const PROC = new Map();
async function esPro(t) { // el mismo criterio que la página (BLPRO): prueba abierta, cuenta nueva de menos de 5 días o pro_hasta vigente; se guarda 10 minutos por token
  if (hoyBA() < FREE_HASTA) return true;
  if (!t || t.length > 4000) return false;
  const c = PROC.get(t); if (c && Date.now() - c.t < 10 * 60e3) return c.ok;
  let ok = false;
  try {
    const r = await fetch(SB + '/auth/v1/user', { headers: { apikey: SBK, Authorization: 'Bearer ' + t } });
    if (r.status >= 500) return true; // Supabase caído: no se le corta el vivo a quien paga (no se guarda)
    if (r.ok) { const us = await r.json(), m = (us && us.app_metadata) || {}; ok = !!(us && ((us.created_at && Date.now() < Date.parse(us.created_at) + 5 * 864e5) || (m.pro_hasta && String(m.pro_hasta).slice(0, 10) >= hoyBA()))); }
  } catch (e) { return true; }
  if (PROC.size > 5000) PROC.clear(); PROC.set(t, { t: Date.now(), ok }); return ok;
}
const cerrado = () => { const d = new Date(Date.now() - 3 * 3600e3), w = d.getUTCDay(), mi = d.getUTCHours() * 60 + d.getUTCMinutes(); return w === 0 || w === 6 || mi < 600 || mi > 1050; }; // fuera de 10 a 17:30 (hora de Buenos Aires)
const sym = (s) => 'MERV - XMEV - ' + s + ' - 24hs'; // precios de 24 hs, como data912

const MEM = {};
let LASTERR = '';
let TOK = null, TOKT = 0, WSST = 0; // el token de Primary vence al final del día: uno por día (buenas prácticas de Primary) o uno nuevo si lo rechaza (como mucho uno por minuto)
const diaBA = (t) => new Date(t - 3 * 3600e3).toISOString().slice(0, 10);
const base = (env) => String(env.ROFEX_URL || 'https://api.bull.xoms.com.ar').trim().replace(/\/+$/, '');
async function token(env, force) {
  if (TOK && diaBA(TOKT) === diaBA(Date.now()) && (!force || Date.now() - TOKT < 60e3)) return TOK;
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
    for (let i = 0; i < syms.length; i += 1000) {
      ws.send(JSON.stringify({ type: 'smd', level: 1, depth: 1, entries: ents || ['BI', 'OF', 'LA', 'CL', 'EV'], products: syms.slice(i, i + 1000).map((s) => ({ symbol: s, marketId: 'ROFX' })) }));
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
  constructor(ctx, env) { this.ctx = ctx; this.env = env; this.rows = {}; this.idx = {}; this.md = {}; this.ws = null; this.cl = new Set(); this.cd = new Set(); this.hist = []; this.md5 = {}; this.a5 = {}; this.t5 = {}; this.w5 = {}; this.dirty = new Set(); this.seen = Date.now(); this.lt = 0; this.lists_t = 0; }
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
  sub(list) { for (let i = 0; i < list.length; i += 1000) this.ws.send(JSON.stringify({ type: 'smd', level: 1, depth: 1, entries: ['BI', 'OF', 'LA', 'CL', 'EV'], products: list.slice(i, i + 1000).map((s) => ({ symbol: s, marketId: 'ROFX' })) })); }
  async connect() {
    let ws;
    for (const force of [false, true]) { const r = await fetch(base(this.env) + '/', { headers: { Upgrade: 'websocket', 'X-Auth-Token': await token(this.env, force) } }); if (r.webSocket) { ws = r.webSocket; break; } }
    if (!ws) throw new Error('websocket de Primary rechazado');
    ws.accept(); this.ws = ws; this.md5 = {}; this.a5 = {}; this.t5 = {}; // conexión nueva: las suscripciones a demanda se vuelven a pedir
    ws.addEventListener('message', (e) => this.onMd(e.data));
    const lost = () => { if (this.ws !== ws) return; this.ws = null; if (this.alive()) setTimeout(() => this.connect().catch((x) => (LASTERR = String(x.message || x))), 3000); };
    ws.addEventListener('close', lost); ws.addEventListener('error', lost);
    this.sub(Object.keys(this.idx));
  }
  alive() { return this.cl.size > 0 || this.cd.size > 0 || Date.now() - this.seen < 10 * 60e3; }
  start() {
    if (!this.go) this.go = (async () => { await this.lists(); await this.connect(); await this.ctx.storage.setAlarm(Date.now() + 60e3); })().catch((e) => { LASTERR = String(e.message || e); this.go = null; });
    return this.go;
  }
  onMd(data) {
    let m; try { m = JSON.parse(data); } catch (x) { return; }
    if (m.type !== 'Md' || !m.instrumentId) return;
    const k = m.instrumentId.symbol, md = m.marketData || {}; this.md[k] = Object.assign(this.md[k] || {}, md); this.lt = Date.now();
    if (this.a5[k]) { // pedido a demanda (caja de puntas, caución, MERV): 5 niveles; si el mismo papel llega también con 1 nivel (la suscripción general), no pisa la profundidad reciente
      const o = this.md5[k] || (this.md5[k] = {}), deep = ['BI', 'OF'].some((e) => Array.isArray(md[e]) && md[e].length > 1);
      Object.keys(md).forEach((e) => { if ((e === 'BI' || e === 'OF') && !deep && Array.isArray(o[e]) && o[e].length > 1 && Date.now() - (this.t5[k] || 0) < 15000) return; o[e] = md[e]; });
      if (deep) this.t5[k] = Date.now(); const w = this.w5[k]; if (w) { delete this.w5[k]; w.forEach((f) => f()); } }
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
  dsnap() { // la foto de hace 20 minutos (se toma una por minuto); sin foto tan vieja, la actual solo si no se movió nada en 20 minutos o el mercado está cerrado
    const lim = Date.now() - DEMORA; for (let i = this.hist.length - 1; i >= 0; i--) if (this.hist[i].t <= lim) return this.hist[i];
    if (!this.lt || this.lt <= lim || cerrado()) { const s = {}; SEPS.forEach((ep) => (s[ep] = this.merged(ep))); return { t: Math.max(this.lt || 0, this.lists_t || 0), s }; }
    return null;
  }
  shot() { // una foto por minuto (35 minutos) y la de hace 20 minutos a los conectados sin PRO
    if (this.ok()) { const s = {}; SEPS.forEach((ep) => (s[ep] = this.merged(ep))); this.hist.push({ t: Date.now(), s }); }
    const lim = Date.now() - 35 * 60e3; while (this.hist.length && this.hist[0].t < lim) this.hist.shift();
    if (!this.cd.size) return; const d = this.dsnap(); if (!d || d.t === this.dlt) return; this.dlt = d.t;
    const msg = JSON.stringify({ s: d.s, d: 1 }); this.cd.forEach((c) => { try { c.send(msg); } catch (e) { this.cd.delete(c); } });
  }
  merged(ep) { return (this.rows[ep] || []).map((r) => patch(r, this.md[sym(r.symbol)])); }
  async alarm() {
    if (!this.alive()) { const w = this.ws; this.ws = null; this.go = null; try { w && w.close(1000, 'sin visitantes'); } catch (e) {} return; }
    if (Date.now() - this.lists_t > 10 * 60e3) await this.lists();
    try { this.shot(); } catch (e) { LASTERR = String(e.message || e); }
    if (!this.ws && this.go) await this.connect().catch((x) => (LASTERR = String(x.message || x)));
    await this.ctx.storage.setAlarm(Date.now() + 60e3);
  }
  async fetch(req) {
    const u = new URL(req.url); this.seen = Date.now(); await this.start();
    if (u.pathname === '/stream') {
      if (req.headers.get('Upgrade') !== 'websocket') return new Response('websocket', { status: 426 });
      const [c, s] = Object.values(new WebSocketPair()); s.accept(); const dm = u.searchParams.get('d') === '1'; (dm ? this.cd : this.cl).add(s);
      const bye = () => { this.cl.delete(s); this.cd.delete(s); this.seen = Date.now(); }; s.addEventListener('close', bye); s.addEventListener('error', bye);
      if (dm) { const d = this.dsnap(); s.send(JSON.stringify(d ? { s: d.s, d: 1 } : { d: 0 })); } // sin PRO: la foto de hace 20 minutos y después una por minuto
      else { const snap = {}; SEPS.forEach((ep) => (snap[ep] = this.merged(ep))); s.send(JSON.stringify({ s: snap })); }
      return new Response(null, { status: 101, webSocket: c });
    }
    if (u.pathname === '/md') { // cotizaciones a demanda por la misma conexión permanente (Primary pide websocket, no REST): {s: listados, x: fuera de la lista (de a uno), ms}
      const q = await req.json(), L = (q.s || []).slice(0, 1500), X = (q.x || []).slice(0, 10), all = L.concat(X), ms = Math.min(+q.ms || 3000, 6000);
      if (!this.ws) return new Response('{}', { status: 503 });
      const nu = L.filter((k) => !this.a5[k]), nx = X.filter((k) => !this.a5[k]), E = ['BI', 'OF', 'LA', 'CL', 'SE', 'OI', 'EV'], t0 = Date.now();
      all.forEach((k) => { if (!this.a5[k]) this.a5[k] = t0; });
      try { for (let i = 0; i < nu.length; i += 500) this.ws.send(JSON.stringify({ type: 'smd', level: 1, depth: 5, entries: E, products: nu.slice(i, i + 500).map((s) => ({ symbol: s, marketId: 'ROFX' })) }));
        nx.forEach((s) => this.ws.send(JSON.stringify({ type: 'smd', level: 1, depth: 5, entries: E, products: [{ symbol: s, marketId: 'ROFX' }] }))); } catch (e) { return new Response('{}', { status: 503 }); }
      const pend = all.filter((k) => !this.md5[k] && Date.now() - this.a5[k] < ms); // los que nunca mandaron nada se esperan solo la primera vez
      if (pend.length) await Promise.race([Promise.all(pend.map((k) => new Promise((ok) => (this.w5[k] = (this.w5[k] || []).concat([ok]))))), new Promise((ok) => setTimeout(ok, ms))]);
      const out = {}; all.forEach((k) => { if (this.md5[k]) out[k] = this.md5[k]; }); return new Response(JSON.stringify(out));
    }
    if (u.pathname === '/stats') return new Response(JSON.stringify({ dia: this.nd || null, mensajes: this.nm || 0, visitantes: this.cl.size, demorados: this.cd.size, simbolos: Object.keys(this.idx).length }));
    const ep = u.pathname.replace(/^\/live\//, '');
    if (u.searchParams.get('d') === '1') { const d = SEPS.includes(ep) && this.dsnap(); return d && d.s[ep] ? new Response(JSON.stringify(d.s[ep])) : new Response('', { status: 204 }); }
    if (!this.ok() || !this.rows[ep] || !SEPS.includes(ep)) return new Response('', { status: 204 });
    return new Response(JSON.stringify(this.merged(ep)));
  }
}

// caución por Primary: los símbolos 'MERV - XMEV - <moneda> - <n>D' (la lista de instrumentos se pide una vez por día) y una foto por websocket
let CSY = null, CSYT = 0, INS = null, INST = 0, INSERR = '';
async function instruments(env) { // la lista de instrumentos de Primary (una vez por día)
  if (INS && INST && diaBA(INST) === diaBA(Date.now())) return INS; // una vez por día (buenas prácticas de Primary)
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
async function wsmd(env, L, X, ms) { // cotizaciones por el websocket permanente del Feed (sin REST)
  if (!env.FEED || (!L.length && !(X || []).length)) return {};
  const r = await env.FEED.get(env.FEED.idFromName('main')).fetch(new Request('https://feed/md', { method: 'POST', body: JSON.stringify({ s: L, x: X || [], ms: ms || 3000 }) }));
  return r.ok ? await r.json() : {};
}
async function merv(env) {
  const L = await mervIns(env), md = {}, E = ['BI', 'OF', 'LA', 'CL', 'SE', 'OI']; let err = null; SNAPERR = null;
  // por websocket solo los que figuran en la lista de Primary (un símbolo inexistente puede tirar toda la suscripción)
  try { Object.assign(md, await wsmd(env, L.filter((x) => x.cfi).map((x) => x.s), L.filter((x) => !x.cfi).map((x) => x.s), 4000)); } catch (e) { err = String(e.message || e); } // todo por el websocket (los que no figuran en la lista de Primary, de a uno)
  const rest = L.filter((x) => !md[x.s] || !Object.keys(md[x.s]).length);
  const p = (o) => (o && o.price > 0 ? o.price : null), lv = (a) => { a = Array.isArray(a) ? a[0] : a; return a && a.price > 0 ? [a.price, a.size] : null; };
  const has = (x) => md[x.s] && Object.keys(md[x.s]).length, L2 = L.filter((x) => !x.fb || has(x)); // de los formatos probados del índice, solo el que respondió
  return { ts: Date.now(), err: err, ws: L.length - rest.length, ins: L2.map((x) => { const m = md[x.s] || {}; return Object.assign({}, x, { BI: lv(m.BI), OF: lv(m.OF), LA: m.LA && m.LA.price > 0 ? [m.LA.price, m.LA.size, m.LA.date || null] : null, CL: p(m.CL), SE: p(m.SE), OI: m.OI && (m.OI.size || m.OI.price) || null, EV: m.EV || null, NV: m.NV || null }); }) };
}
async function cauSyms(env) {
  if (CSY && diaBA(CSYT) === diaBA(Date.now())) return CSY;
  const L = await instruments(env), out = {};
  L.forEach((i) => {
    const s = (i.instrumentId || {}).symbol || '', m = /^MERV - XMEV - (.+) - (\d+)D$/.exec(s); if (!m || +m[2] > 35) return;
    const c = String(i.currency || '').toUpperCase(), n = m[1].toUpperCase();
    out[s] = [n === 'PESOS' || c === 'ARS' ? 'ARS' : c === 'EXT' || /EXT|CABLE/.test(n) ? 'EXT' : 'USD', +m[2]];
  });
  CSY = out; CSYT = Date.now(); return out;
}
async function cauPrimary(env) { // por el websocket permanente del Feed (a demanda), no por REST
  const S = await cauSyms(env), syms = Object.keys(S); if (!syms.length) return null;
  const pick = [], md = await wsmd(env, syms, [], 3000), out = { ARS: [], USD: [], EXT: [] }, has = (d) => d && (px(Array.isArray(d.BI) ? d.BI[0] : d.BI) || px(Array.isArray(d.OF) ? d.OF[0] : d.OF) || (d.LA && deHoy(d.LA.date)));
  ['ARS', 'USD', 'EXT'].forEach((m) => { // de cada moneda, del plazo más corto para arriba: los primeros 4 con puntas u operaciones de hoy (como la caja de puntas)
    let n = 0; syms.filter((s) => S[s][0] === m).sort((a, b) => S[a][1] - S[b][1]).forEach((s) => { if (n < 4 && has(md[s])) { pick.push(s); n++; } });
  });
  pick.forEach((s) => { const d = md[s]; if (!d) return; const lv = (a) => px(Array.isArray(a) ? a[0] : a);
    const row = [S[s][1], lv(d.BI), lv(d.OF), d.LA && deHoy(d.LA.date) ? px(d.LA) : null, px(d.CL), null, null];
    if (row.slice(1).some((v) => v != null)) out[S[s][0]].push(row); });
  ['ARS', 'USD', 'EXT'].forEach((m) => out[m].sort((a, b) => a[0] - b[0]));
  return out;
}
async function caucion(env) {
  let P = null; // primero Primary; BYMA (datos abiertos) completa los plazos que Primary no trae y la moneda que Primary no tenga con operaciones de hoy
  if (env && env.ROFEX_USER) try { P = await cauPrimary(env); } catch (e) { LASTERR = String(e.message || e); }
  let B = null; try { B = await cauByma(); } catch (e) { }
  const live = (rows) => (rows || []).some((r) => r[3] != null);
  const out = { ts: new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 16), src: {}, ARS: [], USD: [], EXT: [] };
  ['ARS', 'USD', 'EXT'].forEach((m) => { const p = P && P[m], b = B && B[m]; const usp = live(p) || (p && p.length && !live(b));
    out[m] = usp ? p.concat((b || []).filter((r) => r[0] > p[p.length - 1][0])) : b || []; out.src[m] = usp ? 'Primary' : 'BYMA'; }); // BYMA (atrasado) solo completa los plazos más largos que los de Primary
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

/* ---------- API REST (/v1) y servidor MCP (/mcp): solo datos propios (cierres, TIRs y curvas que publica la página), nada en vivo de Primary ----------
   La key va en X-API-Key o en Authorization: Bearer. Se guarda solo su SHA-256 en Supabase (tabla api_keys) y la valida la función api_key_uso,
   que además cuenta el uso del día y devuelve la cuota (PRO 1.000 por día, el resto 50; app_metadata.api_cuota la cambia). */
const SITE = 'https://boneriolocal.com.ar/';
const API_H = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Authorization, X-API-Key, Content-Type, Mcp-Session-Id, MCP-Protocol-Version', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' };
const GRUPOS = ['usd', 'fija', 'cer', 'tamar', 'dl', 'dual', 'on', 'pv'];
const ajson = (o, st, x) => new Response(JSON.stringify(o), { status: st || 200, headers: Object.assign({}, API_H, x || {}) });
async function sha256(t) { const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(t)); return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, '0')).join(''); }
async function keyUso(key, contar) { // {ok, scopes, cuota, usados} o null si la función todavía no existe en Supabase
  const r = await fetch(SB + '/rest/v1/rpc/api_key_uso', { method: 'POST', headers: { apikey: SBK, 'Content-Type': 'application/json' }, body: JSON.stringify({ p_hash: await sha256(key), p_contar: contar }) });
  if (r.status === 404) return null; if (!r.ok) throw new Error('supabase ' + r.status); return r.json();
}
async function sitio(path) { const k = 'site:' + path, m = MEM[k]; if (m && Date.now() - m.t < 10 * 60e3) return m.b; const r = await fetch(SITE + path); if (!r.ok) throw new Error(path + ' ' + r.status); const b = await r.json(); MEM[k] = { t: Date.now(), b }; return b; }
const desdeOk = (d) => (/^\d{4}-\d{2}-\d{2}$/.test(d || '') ? d : null);
const API = { // cada consulta: [scope, función(parámetros)]
  curvas: ['curvas', async (q) => { const c = await sitio('data/api/curvas.json'), g = (q.grupo || '').toLowerCase(); if (g && !GRUPOS.includes(g)) throw { st: 400, m: 'grupo: ' + GRUPOS.join(', ') };
    return g ? { fecha: c.fecha, grupo: g, bonos: c.grupos[g] || [] } : c; }],
  bono: ['curvas', async (q) => { const t = String(q.ticker || '').toUpperCase(), c = await sitio('data/api/curvas.json'), H = await sitio('data/api/tir_hist.json'); let row = null, grupo = null;
    GRUPOS.forEach((g) => (c.grupos[g] || []).forEach((r) => { if (r.ticker === t) { row = r; grupo = g; } })); const h = H.t[t];
    if (!row && !h) throw { st: 404, m: 'No tenemos ' + t + ' en las curvas (probá /v1/curvas para ver los tickers)' };
    return { ticker: t, fecha: c.fecha, grupo, ultimo: row, historial_tir: h ? H.fechas.map((f, i) => [f, h[i]]).filter((x) => x[1] != null) : [] }; }],
  cierres: ['cierres', async (q) => { const t = String(q.ticker || '').toUpperCase(), U = await sitio('data/closes.json'), A = await sitio('data/closes_ars.json'), ser = (o, k) => Object.keys(o || {}).sort().filter((f) => o[f][k] != null).map((f) => [f, o[f][k]]);
    const out = { ticker: t, pesos: ser(A, t), mep: ser(U.D, t), cable: ser(U.C, t) }; if (!out.pesos.length && !out.mep.length && !out.cable.length) throw { st: 404, m: 'Sin cierres de ' + t }; return out; }],
  riesgo_pais: ['mercado', async (q) => { const R = (await sitio('data/riesgo_pais.json')).d, d0 = desdeOk(q.desde) || new Date(Date.now() - 365 * 864e5).toISOString().slice(0, 10); return { unidad: 'pb', serie: Object.keys(R).sort().filter((f) => f >= d0).map((f) => [f, R[f]]) }; }],
  dolar: ['mercado', async (q) => { const J = await sitio('data/dolar.json'), d0 = desdeOk(q.desde) || new Date(Date.now() - 90 * 864e5).toISOString().slice(0, 10), x = (o, a) => (o && o[a] && o[a].close) || null;
    return { serie: Object.keys(J.d || {}).sort().filter((f) => f >= d0).map((f) => ({ fecha: f, a3500: (J.A3500 || {})[f] || null, mep_al30: x(J.d[f].mep, 'AL30'), ccl: (J.d[f].ccl && (J.d[f].ccl.vw || J.d[f].ccl.med)) || null })) }; }],
};
const TOOLS = [
  { name: 'curvas', description: 'Curvas de bonos argentinos al último cierre: TIR, duración modificada, días al vencimiento y precio de cada bono. Grupos: usd (hard dollar), fija (Lecaps/Boncaps), cer, tamar, dl (dólar linked), dual, on (ONs), pv (provinciales).', inputSchema: { type: 'object', properties: { grupo: { type: 'string', enum: GRUPOS } } } },
  { name: 'bono', description: 'Un bono: su último cierre en la curva (TIR, duración, precio) y el historial de su TIR.', inputSchema: { type: 'object', properties: { ticker: { type: 'string', description: 'Ej.: AL30, GD30, S30N6, TZX27' } }, required: ['ticker'] } },
  { name: 'cierres', description: 'Precios de cierre recientes de una especie en pesos, MEP (D) y cable (C).', inputSchema: { type: 'object', properties: { ticker: { type: 'string' } }, required: ['ticker'] } },
  { name: 'riesgo_pais', description: 'Serie diaria del riesgo país en puntos básicos.', inputSchema: { type: 'object', properties: { desde: { type: 'string', description: 'AAAA-MM-DD (por defecto, un año atrás)' } } } },
  { name: 'dolar', description: 'Dólar oficial A3500, MEP de AL30 y CCL (promedio de acciones ponderado por volumen) al cierre de cada día.', inputSchema: { type: 'object', properties: { desde: { type: 'string', description: 'AAAA-MM-DD (por defecto, 90 días atrás)' } } } },
];
async function api(req, u) {
  if (req.method === 'OPTIONS') return new Response(null, { headers: API_H });
  const ah = req.headers.get('Authorization') || '', key = (req.headers.get('X-API-Key') || (/^Bearer\s+(.+)$/i.exec(ah) || [])[1] || u.searchParams.get('key') || '').trim();
  if (u.pathname === '/v1' || u.pathname === '/v1/') return ajson({ api: 'Bonerío Local', docs: SITE + '#api', rutas: ['/v1/curvas?grupo=', '/v1/bonos/{ticker}', '/v1/cierres/{ticker}', '/v1/riesgo-pais?desde=', '/v1/dolar?desde=', '/mcp'] });
  if (!/^bl_[A-Za-z0-9_-]{20,80}$/.test(key)) return ajson({ error: 'Falta la API key (header X-API-Key o Authorization: Bearer). La generás en boneriolocal.com.ar › API y MCP.' }, 401);
  const rpc = u.pathname === '/mcp' && req.method === 'POST' ? await req.json().catch(() => null) : null, cuenta = u.pathname !== '/mcp' || (rpc && rpc.method === 'tools/call');
  let K; try { K = await keyUso(key, cuenta); } catch (e) { return ajson({ error: 'No se pudo validar la key' }, 503); }
  if (K === null) return ajson({ error: 'La API todavía no está activada' }, 503);
  if (!K.ok) return ajson({ error: 'API key inválida o revocada' }, 401);
  const lim = { 'X-RateLimit-Limit': String(K.cuota), 'X-RateLimit-Remaining': String(Math.max(0, K.cuota - K.usados)) };
  if (K.usados > K.cuota) return ajson({ error: 'Llegaste a la cuota del día (' + K.cuota + ' consultas). Se renueva a las 0 hs de Buenos Aires.' }, 429, lim);
  const run = async (n, q) => { const f = API[n]; if (!f) throw { st: 404, m: 'No existe ' + n }; if (!(K.scopes || []).includes(f[0])) throw { st: 403, m: 'La key no tiene el permiso «' + f[0] + '»' }; return f[1](q || {}); };
  if (u.pathname === '/mcp') { // MCP por HTTP (JSON-RPC 2.0, sin streaming)
    if (req.method !== 'POST') return ajson({ error: 'Usá POST' }, 405);
    if (!rpc || rpc.jsonrpc !== '2.0') return ajson({ jsonrpc: '2.0', id: null, error: { code: -32700, message: 'JSON-RPC inválido' } }, 400);
    const ok = (result) => ajson({ jsonrpc: '2.0', id: rpc.id, result }, 200, lim), er = (code, message) => ajson({ jsonrpc: '2.0', id: rpc.id, error: { code, message } }, 200, lim);
    if (rpc.id === undefined) return new Response(null, { status: 202, headers: API_H }); // notificaciones (notifications/initialized)
    if (rpc.method === 'initialize') return ok({ protocolVersion: (rpc.params && rpc.params.protocolVersion) || '2025-03-26', capabilities: { tools: {} }, serverInfo: { name: 'bonerio-local', version: '1.0.0' }, instructions: 'Datos de renta fija argentina de Bonerío Local: curvas, TIRs y cierres. No son precios en vivo ni recomendaciones de inversión.' });
    if (rpc.method === 'ping') return ok({});
    if (rpc.method === 'tools/list') return ok({ tools: TOOLS.filter((t) => (K.scopes || []).includes(API[t.name][0])) });
    if (rpc.method === 'tools/call') { const p = rpc.params || {}; try { return ok({ content: [{ type: 'text', text: JSON.stringify(await run(p.name, p.arguments)) }] }); } catch (e) { return ok({ content: [{ type: 'text', text: e.m || String(e.message || e) }], isError: true }); } }
    return er(-32601, 'Método no soportado: ' + rpc.method);
  }
  const m = /^\/v1\/(curvas|bonos|cierres|riesgo-pais|dolar)(?:\/([A-Za-z0-9]{2,12}))?\/?$/.exec(u.pathname); if (!m) return ajson({ error: 'Ruta desconocida: mirá /v1' }, 404, lim);
  const q = Object.fromEntries(u.searchParams); if (m[2]) q.ticker = m[2];
  const n = { curvas: 'curvas', bonos: 'bono', cierres: 'cierres', 'riesgo-pais': 'riesgo_pais', dolar: 'dolar' }[m[1]];
  if ((n === 'bono' || n === 'cierres') && !q.ticker) return ajson({ error: 'Falta el ticker: /v1/' + m[1] + '/AL30' }, 400, lim);
  try { return ajson(await run(n, q), 200, lim); } catch (e) { return ajson({ error: e.m || String(e.message || e) }, e.st || 502, lim); }
}

function cors(req, env) {
  const o = req.headers.get('Origin') || '', ok = (env.ORIGINS || 'https://boneriolocal.com.ar').split(',').map((s) => s.trim());
  return { 'Access-Control-Allow-Origin': ok.includes(o) || /^http:\/\/localhost(:\d+)?$/.test(o) ? o : ok[0], Vary: 'Origin', 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'public, max-age=' + TTL };
}

export default {
  async fetch(req, env) {
    const u = new URL(req.url), h = cors(req, env);
    if (u.pathname === '/v1' || u.pathname.startsWith('/v1/') || u.pathname === '/mcp') return api(req, u); // API pública con key (ver arriba)
    if (req.method === 'OPTIONS') return new Response(null, { headers: h });
    if (u.pathname === '/diag') { // chequeo: login, websocket y una foto de AL30 y GD30 (no muestra la clave)
      const d = { usuario: !!env.ROFEX_USER, clave: !!env.ROFEX_PASS, url: base(env), ultimoError: LASTERR };
      try { await token(env); d.login = 'ok'; } catch (e) { d.login = String(e.message || e); return new Response(JSON.stringify(d, null, 1), { headers: h }); }
      try { const md = await snapshot(env, [sym('AL30'), sym('GD30')], 5000); d.websocket = 'ok'; d.precios = md; } catch (e) { d.websocket = String(e.message || e); }
      try { const P = await pextra(env); d.nuevos = {}; await Promise.all(EPS.map(async (ep) => { let r = []; try { r = await (await fetch(D912 + ep)).json(); } catch (e) { } const a = addP(Array.isArray(r) ? r : [], P[ep]); d.nuevos[ep] = { data912: Array.isArray(r) ? r.length : 0, dePrimary: a.length - (Array.isArray(r) ? r.length : 0), ej: a.filter((x) => x.src === 'primary').slice(0, 25).map((x) => x.symbol) }; })); } catch (e) { d.nuevos = String(e.message || e); } // papeles que suma Primary
      if (env.FEED) try { d.stream = await (await env.FEED.get(env.FEED.idFromName('main')).fetch(new Request(u.origin + '/stats'))).json(); } catch (e) { d.stream = String(e.message || e); } // mensajes de Primary recibidos hoy por la conexión permanente
      return new Response(JSON.stringify(d, null, 1), { headers: h });
    }
    const P = await esPro(u.pathname === '/cim' && !u.searchParams.has('s') ? null : u.searchParams.get('t')); // en /cim las especies van en ?s= (antes iban en ?t= y pisaban el token) // quien no es PRO: precios de hace 20 minutos (ver arriba)
    if (!P && (u.pathname.startsWith('/book/') || u.pathname.startsWith('/merv') || u.pathname === '/cim')) return new Response('{"error":"pro"}', { status: 403, headers: Object.assign({}, h, { 'Cache-Control': 'no-store' }) });
    if (u.pathname === '/cim') { // monitor CI vs 24 hs: la mejor punta y el último de las dos liquidaciones, hasta 60 especies, por el websocket (se guarda 3 segundos)
      const hb = Object.assign({}, h, { 'Cache-Control': 'no-store' }), T = [...new Set((u.searchParams.get('s') || '').toUpperCase().split(','))].filter((x) => /^[A-Z0-9]{2,10}$/.test(x)).slice(0, 60), k = '/cim?' + T.join(','), m = MEM[k];
      if (m && Date.now() - m.t < 3000) return new Response(m.b, { headers: hb });
      try {
        const VS = new Set((await instruments(env)).map((i) => (i.instrumentId || {}).symbol)), sy = (t, z) => 'MERV - XMEV - ' + t + z, L = [];
        T.forEach((t) => [' - CI', ' - 24hs'].forEach((z) => { if (VS.has(sy(t, z))) L.push(sy(t, z)); }));
        const md = await wsmd(env, L, [], 3000), p1 = (a) => { const x = (Array.isArray(a) ? a : a ? [a] : []).find((y) => y && y.price > 0); return x ? [x.price, x.size] : null; }, o = {};
        T.forEach((t) => { const f = (z) => { const q = md[sy(t, z)]; return q ? [p1(q.BI), p1(q.OF), q.LA && q.LA.price > 0 ? q.LA.price : null] : null; }, c = f(' - CI'), d = f(' - 24hs'); if (c || d) o[t] = { ci: c, h: d }; });
        const body = JSON.stringify({ t: Date.now(), d: o }); MEM[k] = { t: Date.now(), b: body }; return new Response(body, { headers: hb });
      } catch (e) { return new Response(JSON.stringify({ error: String(e.message || e) }), { status: 502, headers: hb }); }
    }
    const bk = /^\/book\/((?:DLR|CAUC)(?:\/|%2F)[A-Z]{3}\d{2}|CAU-(?:ARS|USD|EXT)(?:-\d+)?|[A-Z0-9]{2,10})$/i.exec(u.pathname); // también la caución: CAU-<moneda>[-<días>] // un bono o acción (MERV - XMEV - <t> - 24hs) o un futuro de A3 (DLR/NOV26)
    if (bk) bk[1] = decodeURIComponent(bk[1]).toUpperCase();
    if (bk) { // caja de puntas a pedido (al pasar el mouse por un bono): se guarda 2 segundos
      const ci = u.searchParams.get('s') === 'ci', k = u.pathname + (ci ? '?ci' : ''), m = MEM[k], hb = Object.assign({}, h, { 'Cache-Control': 'no-store' });
      if (m && Date.now() - m.t < 2000) return new Response(m.b, { headers: hb });
      try {
        const pz = ci ? ' - CI' : ' - 24hs', lv = (a) => (Array.isArray(a) ? a : a ? [a] : []).filter((x) => x && x.price > 0).slice(0, 5).map((x) => [x.price, x.size]);
        const VS = new Set((await instruments(env)).map((i) => (i.instrumentId || {}).symbol)), full = (t) => (t.includes('/') || t.startsWith('MERV - ') ? t : 'MERV - XMEV - ' + t + pz);
        const getM = async (ts) => { const f = ts.map(full), md = await wsmd(env, f.filter((x) => VS.has(x)), [], 2500); return f.map((x) => md[x] || {}); }; // por el websocket del Feed; solo símbolos de la lista de Primary
        const get = async (t) => (await getM([t]))[0]; // ?s=ci: contado inmediato (la ficha, con su switch CI / 24 hs)
        let t = bk[1], md;
        const cm = /^CAU-(ARS|USD|EXT)(?:-(\d+))?$/.exec(t);
        if (cm) { // la caución de esa moneda: el plazo pedido o, si no, el más corto con puntas
          const S = await cauSyms(env), L = Object.keys(S).filter((s) => S[s][0] === cm[1] && (!cm[2] || S[s][1] === +cm[2])).sort((a, b) => S[a][1] - S[b][1]); md = {};
          const M2 = await getM(L); for (let q = 0; q < L.length; q++) { const s = L[q], m2 = M2[q]; if (lv(m2.BI).length || lv(m2.OF).length) { md = m2; t = 'Caución ' + { ARS: 'en pesos', USD: 'MEP', EXT: 'cable' }[cm[1]] + ' · ' + S[s][1] + (S[s][1] === 1 ? ' día' : ' días'); break; } }
        } else md = await get(t);
        if (!cm && !t.includes('/') && !lv(md.BI).length && !lv(md.OF).length) { // sin puntas en pesos (BOPREAL y otros que operan en dólares o con otro nombre en Primary): la especie D, la C o el nombre de Primary
          const al = []; try { (await instruments(env)).forEach((i) => { const m = /^MERV - XMEV - (.+) - (24hs|CI)$/.exec((i.instrumentId || {}).symbol || ''); if (m && m[2] === pz.slice(3) && m[1] !== t && m[1].replace(/^BPO/, 'BP').replace(/[DC]$/, '') === t) al.push(m[1]); }); } catch (e) { }
          const C = [t + 'D', t + 'C'].concat(al.filter((x) => x !== t + 'D' && x !== t + 'C')), MC = await getM(C); for (let q = 0; q < C.length; q++) { const m2 = MC[q]; if (lv(m2.BI).length || lv(m2.OF).length) { t = C[q]; md = m2; break; } }
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
    if (!P && u.pathname === '/caucion') { // sin PRO: la caución de BYMA (datos abiertos, con demora)
      const m = MEM['/caucion?d']; if (m && Date.now() - m.t < 60e3) return new Response(m.b, { headers: h });
      try { const B = await cauByma(); B.src = { ARS: 'BYMA', USD: 'BYMA', EXT: 'BYMA' }; const body = JSON.stringify(B); MEM['/caucion?d'] = { t: Date.now(), b: body }; return new Response(body, { headers: h }); }
      catch (e) { return new Response(JSON.stringify({ error: String(e.message || e) }), { status: 502, headers: h }); }
    }
    if (!P && u.pathname === '/stream') return feed ? feed.fetch(new Request(u.origin + '/stream?d=1', req)) : new Response('sin Feed', { status: 503 });
    if (!P) { // /live/<ep> sin PRO: la foto de hace 20 minutos; si no hay, 503 y la página usa data912
      if (feed) try { const r = await feed.fetch(new Request(u.origin + u.pathname + '?d=1')); if (r.status === 200) return new Response(r.body, { headers: Object.assign({}, h, { 'Cache-Control': 'no-store' }) }); } catch (e) {}
      return new Response('{"error":"demora"}', { status: 503, headers: Object.assign({}, h, { 'Cache-Control': 'no-store' }) });
    }
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
