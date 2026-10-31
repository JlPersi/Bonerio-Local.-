/* Bonerío en vivo: Cloudflare Worker entre la página y Primary (cuenta de Bull).
   La clave queda acá como secret (ROFEX_USER, ROFEX_PASS); la página nunca la ve.
   Rutas (todas GET, con CORS para la página):
   - /live/<ep>  (arg_bonds, arg_notes, arg_corp, arg_stocks, arg_cedears): la misma lista y el mismo formato que data912.com/live/<ep>,
                 con precio, punta compradora y vendedora de Primary en tiempo real. Si Primary falla, devuelve la de data912 tal cual.
   - /caucion    caución de BYMA (datos abiertos) por plazo: { ts, ARS, USD, EXT }, cada fila [días, compra, venta, última, cierre, vwap, monto].
   - /stream     websocket: al conectarse manda { s: {ep: filas} } y después { u: {ticker: [último, var %, compra, cant., venta, cant.]} } con cada cambio.
   - /book/<ticker>  caja de puntas de Primary (hasta 5 niveles, 24 hs): { t, BI: [[precio, cantidad], ...], OF: [...], LA: [precio, cantidad] }.
   Sin el Durable Object (FEED), cada respuesta se guarda 15 segundos: muchos visitantes a la vez = una sola consulta a Primary. */

const D912 = 'https://data912.com/live/';
const EPS = ['arg_bonds', 'arg_notes', 'arg_corp', 'arg_stocks', 'arg_cedears'];
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
async function snapshot(env, syms, ms) {
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
      if (m.type !== 'Md' || !m.instrumentId) return;
      out[m.instrumentId.symbol] = m.marketData || {};
      want.delete(m.instrumentId.symbol);
      if (!want.size) { clearTimeout(end); done(); }
    });
    ws.addEventListener('close', () => { clearTimeout(end); done(); });
    for (let i = 0; i < syms.length; i += 100) {
      ws.send(JSON.stringify({ type: 'smd', level: 1, depth: 1, entries: ['BI', 'OF', 'LA', 'CL'], products: syms.slice(i, i + 100).map((s) => ({ symbol: s, marketId: 'ROFX' })) }));
    }
  });
  try { ws.close(1000, 'ok'); } catch (x) {}
  return out;
}

const hoyBA = () => new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10);
const deHoy = (ms) => ms && new Date(ms - 3 * 3600e3).toISOString().slice(0, 10) === hoyBA();
const px = (o) => (o && o.price > 0 ? o.price : null);

async function live(env, ep) {
  const rows = await (await fetch(D912 + ep, { cf: { cacheTtl: 10 } })).json(); // la lista de tickers (y lo que Primary no tenga) sale de data912
  if (!Array.isArray(rows) || !env.ROFEX_USER) return rows;
  let md = {};
  try { md = await snapshot(env, rows.map((r) => sym(r.symbol)), 3500); } catch (e) { LASTERR = String(e.message || e); return rows; }
  if (!Object.keys(md).length) LASTERR = 'Primary no mandó precios en 3,5 s';
  return rows.map((r) => patch(r, md[sym(r.symbol)]));
}

// la fila de data912 con lo que mandó Primary: último de hoy, variación contra el cierre anterior y las puntas
function patch(r, m) {
  if (!m) return r;
  const bi = (m.BI || [])[0], of = (m.OF || [])[0], la = deHoy(m.LA && m.LA.date) ? px(m.LA) : null, cl = px(m.CL), o = Object.assign({}, r, { src: 'primary' });
  if (la) { o.c = la; if (cl) o.pct_change = (la / cl - 1) * 100; }
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
  async lists() { // la lista de tickers sale de data912 (y lo que Primary no tiene: volumen, operaciones)
    const nu = [];
    await Promise.all(EPS.map(async (ep) => { try { const r = await (await fetch((this.env.D912 || D912) + ep)).json(); if (!Array.isArray(r) || !r.length) return;
      this.rows[ep] = r; r.forEach((x) => { const k = sym(x.symbol); if (!this.idx[k]) nu.push(k); this.idx[k] = x.symbol; }); } catch (e) {} }));
    this.lists_t = Date.now(); this.by = {}; EPS.forEach((ep) => (this.rows[ep] || []).forEach((x) => (this.by[x.symbol] = x)));
    if (this.ws && nu.length) this.sub(nu);
  }
  sub(list) { for (let i = 0; i < list.length; i += 100) this.ws.send(JSON.stringify({ type: 'smd', level: 1, depth: 1, entries: ['BI', 'OF', 'LA', 'CL'], products: list.slice(i, i + 100).map((s) => ({ symbol: s, marketId: 'ROFX' })) })); }
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
      const snap = {}; EPS.forEach((ep) => (snap[ep] = this.merged(ep))); s.send(JSON.stringify({ s: snap }));
      return new Response(null, { status: 101, webSocket: c });
    }
    const ep = u.pathname.replace(/^\/live\//, '');
    if (!this.ok() || !this.rows[ep]) return new Response('', { status: 204 });
    return new Response(JSON.stringify(this.merged(ep)));
  }
}

async function caucion() {
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
      return new Response(JSON.stringify(d, null, 1), { headers: h });
    }
    const bk = /^\/book\/([A-Z0-9]{2,10})$/.exec(u.pathname);
    if (bk) { // caja de puntas a pedido (al pasar el mouse por un bono): se guarda 2 segundos
      const k = u.pathname, m = MEM[k], hb = Object.assign({}, h, { 'Cache-Control': 'no-store' });
      if (m && Date.now() - m.t < 2000) return new Response(m.b, { headers: hb });
      try {
        const q = base(env) + '/rest/marketdata/get?marketId=ROFX&symbol=' + encodeURIComponent(sym(bk[1])) + '&entries=BI,OF,LA&depth=5';
        let r = await fetch(q, { headers: { 'X-Auth-Token': await token(env) } });
        if (r.status === 401 || r.status === 403) r = await fetch(q, { headers: { 'X-Auth-Token': await token(env, true) } });
        const j = await r.json(), md = (j && j.marketData) || {}, lv = (a) => (Array.isArray(a) ? a : a ? [a] : []).filter((x) => x && x.price > 0).slice(0, 5).map((x) => [x.price, x.size]);
        const body = JSON.stringify({ t: Date.now(), BI: lv(md.BI), OF: lv(md.OF), LA: md.LA && md.LA.price > 0 ? [md.LA.price, md.LA.size] : null });
        MEM[k] = { t: Date.now(), b: body };
        return new Response(body, { headers: hb });
      } catch (e) { LASTERR = String(e.message || e); return new Response(JSON.stringify({ error: LASTERR }), { status: 502, headers: hb }); }
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
      const body = JSON.stringify(u.pathname === '/caucion' ? await caucion() : await live(env, ep));
      MEM[u.pathname] = { t: Date.now(), b: body };
      return new Response(body, { headers: h });
    } catch (e) {
      return new Response(JSON.stringify({ error: String(e.message || e) }), { status: 502, headers: h });
    }
  },
};
