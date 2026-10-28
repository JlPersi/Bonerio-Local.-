/* Datos y gráficos del reporte diario sacados de la propia página: la abre en Chromium (servida desde el repo, con los data/*.json
   recién guardados por el cierre y los precios en vivo de data912) y lee sus pestañas, así las curvas y los números son los mismos que se ven.
     Variación diaria   curvas de hoy contra el cierre anterior (Globales y Bonares, Lecaps, CER, TAMAR, dólar linked, duales, ONs y
                        provinciales en dólares) con el gráfico de la pestaña, y las acciones del panel líder
     Dólar              variaciones (última, 1 rueda) de MEP, CCL, oficial, brecha y canje
     Futuros            tabla de contratos (ajuste, variación, volumen, interés abierto, tasa) y la curva
     Expectativas       inflación y devaluación breakeven de cada bono, implícitas a plazo fijo y forwards entre vencimientos de Lecaps
   Uso: node scripts/reporte_web.js [salida.json]   (por defecto /tmp/reporte_web.json; los gráficos van como PNG en base64)
   Lo llama scripts/reporte.py. Necesita playwright con Chromium (en el Action: npm i playwright && npx playwright install chromium). */
const http = require('http'), fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..');
// emisoras con deuda emitida en Nueva York: de sus ONs en dólares van al reporte las más operadas (la página no guarda la ley de cada ON)
const EM_NY = ['YPF', 'YPF Luz', 'Vista', 'Pan American Energy', 'Pampa Energía', 'Telecom', 'IRSA', 'Tecpetrol', 'CGC', 'Edenor', 'Genneia', 'Arcor',
  'Capex', 'AA2000', 'TGS', 'MSU Energy', 'Pluspetrol', 'Generación Mediterránea'];
const PV_FUERA = ['Tierra del Fuego']; // provinciales en dólares con ley local
const TOP = 12;

function serve() {
  const MIME = { '.html': 'text/html', '.js': 'application/javascript', '.json': 'application/json', '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml', '.webp': 'image/webp', '.ico': 'image/x-icon' };
  return new Promise(ok => {
    const s = http.createServer((q, r) => {
      const f = path.join(ROOT, decodeURIComponent(q.url.split('?')[0]));
      if (!f.startsWith(ROOT) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { r.writeHead(404); return r.end(); }
      r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); fs.createReadStream(f).pipe(r);
    }).listen(0, '127.0.0.1', () => ok(s));
  });
}

// sesión iniciada de mentira: la página pide cuenta para mostrarse
const STUB = `window.supabase={createClient:function(){var q={};['upsert','select','neq','limit','gte','order','eq','delete','insert','update'].forEach(function(m){q[m]=function(){return q}});q.then=function(ok){ok({error:null,data:[]})};return {auth:{onAuthStateChange:function(cb){setTimeout(function(){cb('SIGNED_IN',{user:{id:'reporte',email:'reporte@boneriolocal.com.ar',user_metadata:{}}})},50);return {data:{subscription:{unsubscribe:function(){}}}}},getSession:function(){return Promise.resolve({data:{session:null}})},signOut:function(){return Promise.resolve()}},from:function(){return q},channel:function(){return {on:function(){return this},subscribe:function(){return this}}}}}};`;

const wait = ms => new Promise(r => setTimeout(r, ms));
async function until(page, fn, arg, ms) { const t = Date.now(); while (Date.now() - t < ms) { if (await page.evaluate(fn, arg).catch(() => false)) return true; await wait(500); } return false; }

// en la página: un canvas a PNG sobre el fondo de las tarjetas, y una tabla a filas de texto
const HELP = () => {
  window.__png = function (id) { var c = document.getElementById(id); if (!c || !c.width || c.width < 50) return null; var o = document.createElement('canvas'); o.width = c.width; o.height = c.height; var x = o.getContext('2d'); x.fillStyle = getComputedStyle(document.body).getPropertyValue('--card').trim() || '#131314'; x.fillRect(0, 0, o.width, o.height); x.drawImage(c, 0, 0); return o.toDataURL('image/png').split(',')[1]; };
  window.__tbl = function (el) { if (typeof el === 'string') el = document.getElementById(el); if (!el) return null; var R = [].slice.call(el.querySelectorAll('tr')).map(function (tr) { return [].slice.call(tr.children).map(function (td) { return td.innerText.replace(/\s+/g, ' ').trim(); }); }); return { head: R[0] || [], rows: R.slice(1).filter(function (r) { return r.length > 1; }) }; };
};

async function extract(page, log = console.log) {
  await page.evaluate(HELP);
  const out = { t: new Date().toISOString(), cur: {} };

  // ---------- Variación diaria ----------
  await page.evaluate(() => window.switchTab('vard')); await wait(2500);
  const G = { usd: 'r => r.law === "NY" || r.law === "Local"', fija: '', cer: '', tamar: '', dl: '', dual: '', on: 'ny', pv: 'pv' };
  for (const g of Object.keys(G)) {
    const corp = g === 'on' || g === 'pv';
    await page.evaluate(([g, f, EM, PVF, TOP]) => {
      var fil = null;
      if (f === 'ny' || f === 'pv') { // las más operadas (monto en dólares de hoy, data912) de las emisoras elegidas
        var mon = function () { return 0; };
        var R = window.vardData().filter(function (r) { return r.grp === g && (f === 'ny' ? EM.indexOf(r.em) >= 0 : PVF.indexOf(r.em) < 0) && r.y1 != null && r.y1 > -5 && r.y1 < 30; });
        var top = R.map(function (r) { return [r.k, mon(r.k)]; }).sort(function (a, b) { return b[1] - a[1]; }).slice(0, TOP).map(function (x) { return x[0]; });
        fil = function (r) { return top.indexOf(r.k) >= 0; };
      } else if (f) fil = eval(f);
      window.vardFilter = fil; window.__fil = fil;
      var s = document.getElementById('vdG'); s.value = g; s.onchange();
    }, [g, G[g], EM_NY, PV_FUERA, TOP]);
    if (corp) { // las ONs y los provinciales se cargan cuando se eligen
      await until(page, g => window.vardData().some(r => r.grp === g), g, 25000);
      await page.evaluate(async ([g, f, EM, PVF, TOP]) => { // ya con datos: recalcula la selección y redibuja
        var J = await fetch(g === 'pv' ? 'data/pvs.json' : 'data/ons.json').then(function (r) { return r.json(); }).catch(function () { return {}; });
        var mon = function (k) { var o = (J.on || {})[k] || {}, s = 0; [o.d || k + 'D', o.c || k + 'C'].forEach(function (sym) { var q = (window.PXQ || {})[sym]; if (q && q.c > 0 && q.v > 0) s += q.v * q.c / (q.c < 5 ? 1 : 100); }); return s; }; // especies MEP y cable (los provinciales tienen las suyas en pvs.json)
        var R = window.vardData().filter(function (r) { return r.grp === g && (f === 'ny' ? EM.indexOf(r.em) >= 0 : PVF.indexOf(r.em) < 0) && r.y1 != null && r.y1 > -5 && r.y1 < 30; });
        var top = R.map(function (r) { return [r.k, mon(r.k)]; }).sort(function (a, b) { return b[1] - a[1]; }).slice(0, TOP);
        window.__mon = {}; top.forEach(function (x) { window.__mon[x[0]] = x[1]; });
        window.vardFilter = window.__fil = function (r) { return r.k in window.__mon; }; window.renderVarDiaria();
      }, [g, G[g], EM_NY, PV_FUERA, TOP]);
    }
    await wait(1500);
    const r = await page.evaluate(g => {
      var f = window.__fil || function () { return true; }, mon = window.__mon || {};
      var rows = window.vardData().filter(function (r) { return r.grp === g && f(r); }).map(function (r) {
        var q = window.PXQ || {}, v = null; if (r.grp === 'usd' || r.grp === 'on' || r.grp === 'pv') v = mon[r.k] != null ? mon[r.k] : null;
        return { k: r.k, em: r.em || '', law: r.law || '', d: r.days, x: r.x1, md: r.md1, y0: r.y0, y1: r.y1, dpb: r.dpb, dpct: r.dpct, P0: r.P0, P1: r.P1, yl: r.yl, src: r.src, usdv: v, tf: !!r.dualTf };
      });
      window.__mon = null;
      return { rows: rows, png: rows.length > 1 ? window.__png('vdChart') : null, info: (document.getElementById('vdInfo') || {}).textContent || '' };
    }, g);
    out.cur[g] = r; log('curva', g, r.rows.length, r.png ? 'con gráfico' : 'sin gráfico');
  }
  await page.evaluate(() => { window.vardFilter = null; window.__fil = null; });

  // ---------- acciones del panel líder ----------
  await page.evaluate(() => { var s = document.getElementById('vdG'); s.value = 'acc'; s.onchange(); });
  await until(page, () => document.querySelectorAll('#vdAccT tr').length > 3, null, 30000); await wait(1500);
  out.acc = await page.evaluate(() => ({ tbl: window.__tbl('vdAccT'), png: window.__png('vdAccC'), info: (document.getElementById('vdInfo') || {}).textContent || '', sum: (document.getElementById('vdAccS') || {}).textContent || '' }));
  log('acciones', out.acc.tbl ? out.acc.tbl.rows.length : 0);

  // ---------- dólar ----------
  await page.evaluate(() => window.switchTab('dol'));
  await until(page, () => document.querySelectorAll('#dxS5 tr').length > 3, null, 25000); await wait(800);
  out.dol = await page.evaluate(() => window.__tbl(document.querySelector('#dxS5 table')));
  log('dólar', out.dol ? out.dol.rows.length : 0);

  // ---------- futuros ----------
  await page.evaluate(() => window.switchTab('tfut'));
  await until(page, () => [].some.call(document.querySelectorAll('#tfut table'), t => /CONTRATO|Contrato/.test(t.innerText) && t.querySelectorAll('tr').length > 2), null, 25000); await wait(1500);
  out.fut = await page.evaluate(() => {
    var t = [].filter.call(document.querySelectorAll('#tfut table'), function (t) { return /Contrato/i.test((t.querySelector('tr') || {}).innerText || '') && /DLR/.test(t.innerText); })[0];
    return { tbl: window.__tbl(t), png: window.__png('tfCh1') };
  });
  log('futuros', out.fut.tbl ? out.fut.tbl.rows.length : 0);

  // ---------- inflación y devaluación implícitas, forwards ----------
  for (const [tab, sx, cv] of [['expi', 'i', 'psCB2'], ['expd', 'd', 'psCB4']]) {
    await page.evaluate(t => window.switchTab(t), tab);
    await until(page, sx => document.querySelectorAll('#thBB' + sx + ' tr').length > 2 && document.querySelectorAll('#thBE' + sx + ' tr').length > 1, sx, 25000);
    await page.evaluate(sx => { var b = document.getElementById('bePjSw' + sx); if (b && b.getAttribute('aria-pressed') !== 'true' && window.BEPJT) window.BEPJT(sx); }, sx); await wait(1500); // con el REM en el gráfico
    out['be' + sx] = await page.evaluate(([sx, cv]) => {
      var ts = document.querySelectorAll('#thBE' + sx + ' table'), plz = ts.length ? window.__tbl(ts[ts.length - 1]) : null, ch = window.Chart && Chart.getChart && Chart.getChart('thBEC' + sx), ayer = {};
      if (ch) ch.data.datasets.forEach(function (d) { var p = d.data.filter(function (x) { return x && x.y != null; }); if (p.length > 1 && d.label && !/promedio|desv/i.test(d.label)) ayer[d.label] = [p[p.length - 1].y, p[p.length - 2].y]; }); // hoy y la rueda anterior de cada plazo
      return { bonos: window.__tbl(document.querySelector('#thBB' + sx + ' table')), plazos: plz, ayer: ayer, png: window.__png(cv) };
    }, [sx, cv]);
    log('breakeven', sx, out['be' + sx].bonos ? out['be' + sx].bonos.rows.length : 0);
  }
  await page.evaluate(() => window.switchTab('expf'));
  await until(page, () => !!(document.getElementById('psFwR1') || {}).textContent, null, 20000); await wait(1500);
  out.fw = await page.evaluate(() => ({ txt: (document.getElementById('psFwR1') || {}).textContent || '', tbl: window.__tbl('psFwT1'), png: window.__png('psFwC1') }));
  log('forwards', out.fw.tbl ? out.fw.tbl.rows.length : 0);
  return out;
}

async function main() {
  const { chromium } = require('playwright');
  const srv = await serve(), base = 'http://127.0.0.1:' + srv.address().port;
  const b = await chromium.launch();
  const page = await b.newPage({ viewport: { width: 760, height: 1300 }, deviceScaleFactor: 2, colorScheme: 'dark', serviceWorkers: 'block' });
  await page.route('**/supabase-js@*/**', r => r.fulfill({ body: STUB, contentType: 'application/javascript' }));
  page.on('pageerror', e => console.log('error en la página:', e.message));
  await page.goto(base + '/index.html');
  await until(page, () => window.vardData && window.PXQ && Object.keys(window.PXQ).length > 50, null, 60000); await wait(4000);
  const out = await extract(page);
  fs.writeFileSync(process.argv[2] || '/tmp/reporte_web.json', JSON.stringify(out));
  await b.close(); srv.close();
}

module.exports = { extract, STUB };
if (require.main === module) main().catch(e => { console.error(e); process.exit(1); });
