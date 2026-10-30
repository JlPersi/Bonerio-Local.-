/* Bonerío en vivo: Cloudflare Worker entre la página y Primary (cuenta de Bull).
   La clave queda acá como secret (ROFEX_USER, ROFEX_PASS); la página nunca la ve.
   Rutas (todas GET, con CORS para la página):
   - /live/<ep>  (arg_bonds, arg_notes, arg_corp, arg_stocks, arg_cedears): la misma lista y el mismo formato que data912.com/live/<ep>,
                 con precio, punta compradora y vendedora de Primary en tiempo real. Si Primary falla, devuelve la de data912 tal cual.
   - /caucion    caución de BYMA (datos abiertos) por plazo: { ts, ARS, USD, EXT }, cada fila [días, compra, venta, última, cierre, vwap, monto].
   Cada respuesta se guarda 15 segundos: muchos visitantes a la vez = una sola consulta a Primary. */

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
  return rows.map((r) => {
    const m = md[sym(r.symbol)]; if (!m) return r;
    const bi = (m.BI || [])[0], of = (m.OF || [])[0], la = deHoy(m.LA && m.LA.date) ? px(m.LA) : null, cl = px(m.CL), o = Object.assign({}, r, { src: 'primary' });
    if (la) { o.c = la; if (cl) o.pct_change = (la / cl - 1) * 100; }
    if (bi) { o.px_bid = bi.price; o.q_bid = bi.size; }
    if (of) { o.px_ask = of.price; o.q_ask = of.size; }
    return o;
  });
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
    const ep = u.pathname.replace(/^\/live\//, '');
    if (u.pathname !== '/caucion' && !EPS.includes(ep)) return new Response('{"error":"ruta"}', { status: 404, headers: h });
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
