#!/usr/bin/env node
/* Carga el RESULTADO de una licitación del Tesoro en licitaciones.html en segundos.
 *
 *   node scripts/licitacion/cargar.js --texto resultado.txt            (texto del comunicado o del posteo del MECON)
 *   node scripts/licitacion/cargar.js --json resultado.json            (los mismos datos ya armados, ver abajo)
 *   opciones: --c AAAA-MM-DD (fecha de la licitación; por defecto la del texto o hoy) · --seco (calcula y muestra, no escribe)
 *
 * JSON: {"c":"2026-10-14","adj":6.61,"ofr":9.49,"roll":136.14,"src":"texto oficial 14/10",
 *        "ins":[{"t":"S29E7","adj":2.71,"tirea":27.47,"tem":2.04},{"t":"TMG28","adj":1.16,"margen":9.32},
 *               {"t":"TXMD9","adj":1.70,"tirea":6.99},{"t":"TMVE8","adj":1.04,"tirea":4.35}]}
 *   montos en billones de $; tasas en %. Por instrumento: tirea (fija: nominal; CER: real; DL y duales: la de la otra pata),
 *   o margen (TAMAR, o la pata TAMAR de un dual), o tna (fija, si solo dan la TNA). TAMAR sin margen: precio (por 100 VN) y se despeja.
 *
 * Qué hace: lee el llamado (LLAM) y el cronograma (CAL) de licitaciones.html, abre index.html con Playwright y calcula con el
 * mismo código de Curva Pesos (PSX.yieldAt, PSX.snap, PSX.fairFit): precio de corte, tasa en la unidad de cada familia, yields
 * del secundario al cierre del día de la licitación (o el último cierre guardado; si data912 responde y el día no está
 * guardado, con los precios en vivo), curvas por familia y premios. Escribe RES, LD.AUC, ADJ, ROLL, L2C, CUTAVG, PREM y
 * PERFIL (lo de la licitación anterior pasa a la base). Corregí el vencimiento del llamado si no coincide con la ficha.
 * Si es reapertura no hay que tocar nada más; si hay un bono NUEVO, primero darlo de alta (ver .claude/skills/licitacion).
 */
const fs = require('fs'), path = require('path'), cp = require('child_process'), os = require('os');
const ROOT = path.resolve(__dirname, '..', '..'), LIC = path.join(ROOT, 'licitaciones.html');
const arg = k => { const i = process.argv.indexOf('--' + k); return i < 0 ? null : (process.argv[i + 1] && !process.argv[i + 1].startsWith('--') ? process.argv[i + 1] : true); };
const die = m => { console.error('ERROR: ' + m); process.exit(1); };
const num = s => { s = String(s).trim(); if (s.includes('.') && s.includes(',')) s = s.indexOf('.') < s.indexOf(',') ? s.replace(/\./g, '').replace(',', '.') : s.replace(/,/g, ''); else s = s.replace(',', '.'); return parseFloat(s); };
const iso = d => d.toISOString().slice(0, 10);
const hoyAR = () => iso(new Date(Date.now() - 3 * 36e5));

/* ---------- 1. datos del resultado ---------- */
function parseTexto(tx) {
  const amt = (s, u) => { const v = num(s); return /mil millones/i.test(u) ? v / 1000 : /millones/i.test(u) ? v / 1e6 : v; };
  const out = { ins: [] };
  let m = /adjudic[óo] un total de \$\s*([\d.,]+)\s*(billones|mil millones|millones)/i.exec(tx); if (m) out.adj = amt(m[1], m[2]);
  m = /ofertas por un total de \$\s*([\d.,]+)\s*(billones|mil millones|millones)/i.exec(tx); if (m) out.ofr = amt(m[1], m[2]);
  m = /rollover de\s*([\d.,]+)\s*%/i.exec(tx); if (m) out.roll = num(m[1]);
  const re = /\(([A-Z0-9]{4,6})\)/g, hits = []; while ((m = re.exec(tx))) hits.push([m[1], m.index]);
  hits.forEach(([t, i], k) => {
    const seg = tx.slice(i, k + 1 < hits.length ? hits[k + 1][1] : tx.length).split(/\n\s*(?:✅|➡)/)[0], o = { t };
    let q = /\$\s*([\d.,]+)\s*(billones|mil millones|millones)/i.exec(seg); if (q) o.adj = amt(q[1], q[2]);
    q = /margen de\s*([\d.,]+)\s*%/i.exec(seg) || /([\d.,]+)\s*%\s*(?:de\s*)?margen/i.exec(seg); if (q) o.margen = num(q[1]);
    q = /([\d.,]+)\s*%\s*TIREA/i.exec(seg); if (q) o.tirea = num(q[1]);
    q = /([\d.,]+)\s*%\s*TEM/i.exec(seg); if (q) o.tem = num(q[1]);
    q = /([\d.,]+)\s*%\s*TNA/i.exec(seg); if (q) o.tna = num(q[1]);
    if (!out.ins.some(x => x.t === t)) out.ins.push(o);
  });
  return out;
}
let R;
if (arg('json')) R = JSON.parse(fs.readFileSync(arg('json'), 'utf8'));
else if (arg('texto')) R = parseTexto(fs.readFileSync(arg('texto'), 'utf8'));
else die('falta --texto archivo o --json archivo');
if (arg('c')) R.c = arg('c');
let S = fs.readFileSync(LIC, 'utf8');
const grab = (name, open, close) => { const i = S.indexOf('const ' + name + '='); if (i < 0) die('no encuentro ' + name); const a = S.indexOf(open, i); let dep = 0, j = a; for (; j < S.length; j++) { if (S[j] === open) dep++; else if (S[j] === close && --dep === 0) break; } return { i, a, b: j + 1, src: S.slice(a, j + 1) }; };
const CAL = Function('return ' + grab('CAL', '[', ']').src)(), LLAM = Function('return ' + grab('LLAM', '{', '}').src)();
if (!R.c) { const t = hoyAR(), c = CAL.find(x => x[1] === t) || CAL.filter(x => x[1] <= t && LLAM[x[1]]).pop(); R.c = c && c[1]; }
const CR = CAL.find(x => x[1] === R.c); if (!CR) die('la fecha ' + R.c + ' no está en CAL');
const Q = CR[2], LL = LLAM[R.c] || [];
if (!R.ins.length) die('no encontré instrumentos en el texto');
R.ins.forEach(x => { const l = LL.find(y => y.t === x.t); if (!l) console.warn('aviso: ' + x.t + ' no está en el llamado del ' + R.c); Object.assign(x, { f: l ? l.f : x.f, k: l ? l.k : x.k, ve: l ? l.ve : x.ve }); if (x.adj == null) die('sin monto adjudicado para ' + x.t); });
if (R.adj == null) R.adj = +R.ins.reduce((a, x) => a + x.adj, 0).toFixed(3);
R.src = R.src || 'texto oficial ' + R.c.slice(8, 10) + '/' + R.c.slice(5, 7);
console.log('Licitación ' + R.c + ' · liquida ' + Q + ' · ' + R.ins.map(x => x.t).join(', '));

/* ---------- 2. cálculo con el código del sitio ---------- */
function lib(name, ver, file) { // Chart.js y html2canvas desde npm (cdnjs no siempre está habilitado)
  const dir = path.join(os.tmpdir(), 'bl-libs', name + '-' + ver), f = path.join(dir, 'package', file);
  if (!fs.existsSync(f)) { fs.mkdirSync(dir, { recursive: true }); cp.execSync(`npm pack ${name}@${ver} --silent`, { cwd: dir, stdio: 'pipe' }); cp.execSync(`tar xzf ${name}-${ver}.tgz`, { cwd: dir }); }
  return fs.readFileSync(f);
}
function live() { // precios en vivo de data912 (si responde) para el día que todavía no está guardado
  const m = {}; for (const u of ['https://data912.com/live/arg_bonds', 'https://data912.com/live/arg_notes']) {
    try { JSON.parse(cp.execFileSync('curl', ['-sS', '--max-time', '20', u], { maxBuffer: 1e8 }).toString()).forEach(r => { if (r.symbol && r.c > 0) m[r.symbol] = r.c; }); } catch (e) { }
  } return Object.keys(m).length > 20 ? m : null;
}
(async () => {
  let pw; try { pw = require('playwright'); } catch (e) { pw = require('/opt/node22/lib/node_modules/playwright'); }
  const CLP = path.join(ROOT, 'data', 'closes_ars.json'), CL = JSON.parse(fs.readFileSync(CLP, 'utf8'));
  let REF = Object.keys(CL).filter(d => d <= R.c).sort().pop(), viv = false;
  if (REF !== R.c && !arg('sin-vivo')) { const L = live(); if (L) { const tk = JSON.parse(fs.readFileSync(path.join(ROOT, 'scripts', 'pesos_tickers.json'), 'utf8')); CL[R.c] = {}; tk.forEach(t => { if (L[t] != null) CL[R.c][t] = L[t]; }); REF = R.c; viv = true; } }
  console.log('Mercado: ' + (viv ? 'precios en vivo de hoy' : 'cierre guardado del ' + REF) + (REF === R.c ? '' : ' (no está el del día de la licitación)'));
  const br = await pw.chromium.launch(), ctx = await br.newContext({ viewport: { width: 1300, height: 900 } }), pg = await ctx.newPage();
  pg.on('pageerror', e => console.warn('error en la página: ' + e.message));
  const CH = lib('chart.js', '4.4.1', 'dist/chart.umd.js'), H2 = lib('html2canvas', '1.4.1', 'dist/html2canvas.min.js');
  await ctx.route(u => !/bonerio\.test/.test(u.href), r => { const u = r.request().url(); if (/Chart\.js|chart\.umd/i.test(u)) return r.fulfill({ body: CH, contentType: 'application/javascript' }); if (/html2canvas/.test(u)) return r.fulfill({ body: H2, contentType: 'application/javascript' }); r.abort(); });
  await ctx.route('http://bonerio.test/**', r => { const u = new URL(r.request().url()), f = path.join(ROOT, u.pathname);
    if (/auth\.js|sw\.js/.test(f)) return r.fulfill({ body: '', contentType: 'application/javascript' });
    if (/closes_ars\.json$/.test(f)) return r.fulfill({ body: JSON.stringify(CL), contentType: 'application/json' });
    if (!fs.existsSync(f)) return r.fulfill({ status: 404, body: '' });
    r.fulfill({ body: fs.readFileSync(f), contentType: /\.html$/.test(f) ? 'text/html' : /\.json$/.test(f) ? 'application/json' : 'application/javascript' }); });
  await pg.goto('http://bonerio.test/index.html'); await pg.waitForFunction(() => window.PSX && window.PSX.INST, null, { timeout: 60000 });
  await pg.evaluate(() => window.switchTab && window.switchTab('pesos')); await pg.waitForTimeout(2500);
  const out = await pg.evaluate(calc, { R, REF, Q, CL: CL[REF] });
  await br.close();
  if (out.err) die(out.err);
  write(out, REF);
})().catch(e => die(e.stack || e));

function calc({ R, REF, Q, CL }) { // corre dentro de index.html
  const day = s => Date.parse(s + 'T00:00:00Z') / 864e5, wd = t => new Date(t * 864e5).getUTCDay();
  const nxt = t => { t++; while (wd(t) === 0 || wd(t) === 6) t++; return t; }, prv = t => { t--; while (wd(t) === 0 || wd(t) === 6) t--; return t; };
  const tR = day(REF), q = day(Q), tC = prv(q), sR = nxt(tR), I = PSX.INST;
  const miss = R.ins.filter(x => !I[x.t]).map(x => x.t); if (miss.length) return { err: 'bono(s) nuevo(s) sin alta en data/flujos.xlsx: ' + miss.join(', ') + ' (ver .claude/skills/licitacion, punto 4)' };
  const d0 = document.getElementById('d0'), isoD = t => new Date(t * 864e5).toISOString().slice(0, 10), snapAt = t => { d0.value = isoD(t); const o = {}; PSX.snap(5).S.forEach(x => o[x.k] = x); return o; };
  const SR = snapAt(sR), SQ = snapAt(q);
  const tnas = (tea, d) => (Math.pow(1 + tea, d / 365) - 1) * 365 / d * 100, tna30 = tea => (Math.pow(1 + tea, 30 / 365) - 1) * 365 / 30 * 100, tea30 = y => Math.pow(1 + y / 100 * 30 / 365, 365 / 30) - 1;
  const r3 = v => v == null || !isFinite(v) ? null : Math.round(v * 1000) / 1000, r2 = v => v == null ? null : Math.round(v * 100) / 100;
  const matOf = k => I[k].r[I[k].r.length - 1][0];
  const m360 = (a, b) => { const x = new Date(a * 864e5), y = new Date(b * 864e5), d1 = Math.min(x.getUTCDate(), 30), d2 = d1 === 30 ? Math.min(y.getUTCDate(), 30) : y.getUTCDate(); return ((y.getUTCFullYear() - x.getUTCFullYear()) * 360 + (y.getUTCMonth() - x.getUTCMonth()) * 30 + d2 - d1) / 30; }; // meses 30/360
  // puntos del secundario por familia: [ticker, días desde la liquidación, yield, atípico, tipo (0, 1 dual, 2 cupones/amortiza), precio, yield pata 2, pata]
  const fam = {}, SEC = {};
  for (const k of Object.keys(I)) { const P = CL[k]; if (P == null) continue; const ins = I[k], mat = matOf(k), x = mat - q, dS = mat - sR; if (x <= 0) continue;
    let g, y, y2 = null, rama = null, ty = 0; const kd = ins.k, yv = PSX.yieldAt(k, tR, P); if (yv == null) continue;
    if (kd === 'cap' || kd === 'cpn') { g = 'fija'; y = tnas(yv / 100, dS); ty = kd === 'cpn' || ins.r.length > 1 ? 2 : 0; SEC[k] = yv; }
    else if (kd === 'cer0' || kd === 'cerc') { g = 'cer'; y = yv; ty = ins.r.filter(r => r[0] > sR).length > 1 ? 2 : 0; SEC[k] = tea30(yv) * 100; }
    else if (kd === 'tamar') { g = 'tamar'; y = yv; ty = ins.r.filter(r => r[0] > sR).length > 1 ? 2 : 0; SEC[k] = yv; }
    else if (kd === 'dl') { g = 'dl'; y = tnas(tea30(yv), dS); SEC[k] = tea30(yv) * 100; }
    else if (kd === 'dual') { g = 'tamar'; y = yv; ty = 1; const o = SR[k]; if (!o) continue; if (o.isCer) { y2 = o.realTna30 * 100; rama = 'CER'; SEC[k] = o.realTea * 100; } else { y2 = o.usdTnas * 100; rama = 'DL'; SEC[k] = o.usdTea * 100; } }
    else continue;
    (fam[g] = fam[g] || []).push([k, x, r3(y), ty === 2 ? 3 : 0, ty, P, r3(y2), rama]);
  }
  const samp = (lo, hi, f) => { const a = []; for (let i = 0; i <= 60; i++) { const x = lo + (hi - lo) * Math.pow(i / 60, 1.4); a.push([Math.round(x * 10) / 10, r3(f(x))]); } a[60][0] = hi; return a; };
  const seg = (pp, du) => { if (pp.length < 2) return null; pp = pp.slice().sort((u, v) => u[1] - v[1]); const lo = pp[0][1], hi = pp[pp.length - 1][1];
    if (pp.length === 2) { const [a, b] = pp; return { lo, hi, cu: samp(lo, hi, x => a[2] + (b[2] - a[2]) * (x - a[1]) / (b[1] - a[1])), nm: 'Recta entre 2 bonos', du }; }
    const F = PSX.fairFit(pp.map(p => ({ x: p[1], y: p[2], k: p[0] }))); return F ? { lo, hi, cu: samp(lo, hi, F.f), nm: F.name, du } : null; };
  const AF = {};
  for (const g in fam) { const pts = fam[g].sort((a, b) => a[1] - b[1]), ok = pts.filter(p => !p[3] && p[1] >= 30); let sg;
    if (g === 'tamar') sg = [seg(ok.filter(p => p[4] === 0), 0), seg(ok.filter(p => p[4] === 1), 1)];
    else if (g === 'dl') sg = [seg(ok.filter(p => p[1] < 400), 0), seg(ok.filter(p => p[1] >= 400), 0)];
    else sg = [seg(ok, 0)];
    AF[g] = { pts, minD: 30, segs: sg.filter(Boolean) }; }
  const fitAt = (g, x, du) => { const ss = (AF[g] ? AF[g].segs : []).filter(s => s.du === du); if (!ss.length) return null;
    const s = ss.find(s => x >= s.lo && x <= s.hi) || ss.sort((a, b) => Math.min(Math.abs(x - a.lo), Math.abs(x - a.hi)) - Math.min(Math.abs(x - b.lo), Math.abs(x - b.hi)))[0], c = s.cu; let v;
    if (x <= c[0][0]) v = c[0][1]; else if (x >= c[60][0]) v = c[60][1]; else for (let i = 1; i <= 60; i++) if (x <= c[i][0]) { const w = (x - c[i - 1][0]) / (c[i][0] - c[i - 1][0]); v = c[i - 1][1] + w * (c[i][1] - c[i - 1][1]); break; }
    return { v, ext: x < s.lo || x > s.hi ? 1 : 0 }; };
  const solve = (k, target) => { const f = P => PSX.yieldAt(k, tC, P) - target; let a = 1, b = 5e5; for (let i = 0; i < 200; i++) { const m = (a + b) / 2, v = f(m); if (v == null || isNaN(v)) b = m; else if (v > 0) a = m; else b = m; } return (a + b) / 2; };
  const cuts = [], res = [], pay = [];
  for (const it of R.ins) { const k = it.t, ins = I[k], kd = ins.k, mat = matOf(k), d = mat - q, oq = SQ[k] || {}, g = kd === 'dual' ? 'dual' : (kd === 'cap' || kd === 'cpn') ? 'fija' : (kd === 'cer0' || kd === 'cerc') ? 'cer' : kd === 'dl' ? 'dl' : 'tamar';
    const z = { t: k, g, x: d, v: it.adj, y: null, y2: null, l2: null, yt: null, P: null, du: g === 'dual' ? 1 : 0 }, r = { t: k, f: g, adj: it.adj };
    let Pa;
    if (g === 'fija') { let T = it.tirea != null ? it.tirea / 100 : it.tna != null ? Math.pow(1 + it.tna / 100 * d / 365, 365 / d) - 1 : null; if (T == null && it.tem == null) return { err: k + ': falta la TIREA o TNA' };
      // con la TEM de corte y una Lecap (un solo pago): precio = pago final / (1 + TEM) ^ meses 30/360 de la liquidación al vencimiento. La TIREA del
      // comunicado es (1 + TEM)^12 − 1, no la de días corridos: sacada de ahí, el precio de una Lecap nueva daba 99,91 en vez de 100
      if (it.tem != null && kd === 'cap' && ins.r.length === 1) { Pa = ins.r[0][1] / Math.pow(1 + it.tem / 100, m360(q, mat)); T = PSX.yieldAt(k, tC, Pa) / 100; } else Pa = solve(k, T * 100);
      z.y = tnas(T, d); z.P = Pa; Object.assign(r, { tasa: it.tirea != null ? it.tirea : +(T * 100).toFixed(2), u: 'TIREA', x: it.tem != null ? 'TEM ' + String(it.tem).replace('.', ',') + '%' : undefined }); }
    else if (g === 'cer') { if (it.tirea == null) return { err: k + ': falta la TIREA real' }; Pa = solve(k, tna30(it.tirea / 100)); z.y = tna30(it.tirea / 100); z.P = Pa; Object.assign(r, { tasa: it.tirea, u: 'TIREA real (CER)' }); }
    else if (g === 'tamar') { if (it.margen == null && it.precio != null) { let a = -30, b = 60; for (let i = 0; i < 80; i++) { const m = (a + b) / 2; if (solve(k, m) > it.precio) a = m; else b = m; } it.margen = +((a + b) / 2).toFixed(2); } // el comunicado da precio y no margen
      if (it.margen == null) return { err: k + ': falta el margen' }; Pa = solve(k, it.margen); z.y = it.margen; z.P = Pa; Object.assign(r, { tasa: it.margen, u: 'margen s/ TAMAR' }); }
    else if (g === 'dl') { if (it.tirea == null) return { err: k + ': falta la TIREA en USD' }; const T = it.tirea / 100; Pa = solve(k, tna30(T)); z.y = tnas(T, d); z.yt = it.tirea; z.P = 100 / Math.pow(1 + T, d / 365); Object.assign(r, { tasa: it.tirea, u: 'TIREA USD' }); }
    else { // dual: la pata TAMAR (margen) en y; la otra pata en y2
      const cer = !!oq.isCer || ins.f === 'cer+tamar'; z.l2 = cer ? 'CER' : 'DL';
      const dv = cer ? (oq.coef || 1) : oq.fx0; let pr; // pr: precio de la otra pata (real en CER; en USD en DL), por 100 VN
      if (it.tirea != null) { const T = it.tirea / 100; pr = 100 / Math.pow(1 + T, d / 365); Pa = pr * dv; z.y = PSX.yieldAt(k, tC, Pa); }
      else if (it.margen != null) { Pa = solve(k, it.margen); z.y = it.margen; pr = Pa / dv; }
      else return { err: k + ': falta la tasa' };
      const T2 = Math.pow(100 / pr, 365 / d) - 1; z.y2 = cer ? tna30(T2) : tnas(T2, d);
      z.P = cer ? Pa : pr; Object.assign(r, it.tirea != null ? { tasa: it.tirea, u: cer ? 'TIREA real (CER)' : 'TIREA USD', x: 'margen s/ TAMAR ' + z.y.toFixed(2).replace('.', ',') + '%' } : { tasa: it.margen, u: 'margen s/ TAMAR' });
    }
    const fg = g === 'dual' ? 'tamar' : g, sp = (AF[fg] ? AF[fg].pts : []).find(p => p[0] === k), cv = fitAt(fg, d, z.du);
    Object.assign(z, { s: sp ? sp[2] : null, ps: sp ? (g === 'dl' || z.l2 === 'DL' ? r2(sp[5] / (Pa / z.P)) : sp[5]) : null, po: null, pc: null, cv: cv ? r3(cv.v) : null, so: 0, ext: cv ? cv.ext : 0, cd: z.du });
    z.y = r3(z.y); z.y2 = r3(z.y2); z.P = r2(z.P); if (z.s != null) z.po = Math.round((z.y - z.s) * 100); if (z.cv != null) z.pc = Math.round((z.y - z.cv) * 100); if (z.po == null && z.pc == null) z.nc = 1;
    cuts.push(z);
    const sec = SEC[k]; Object.assign(r, { pP: r2(Pa), pD: sp ? sp[5] : null, secP: null, secD: sec == null ? null : r2(sec) }); res.push(r);
    // pago al vencimiento con los índices de hoy (como el resto del perfil): VN adjudicado × valor de rescate
    const vn = it.adj / Pa * 100, pv = g === 'fija' ? vn * (oq.M || 100) / 100 : g === 'tamar' ? vn * (oq.A || Pa / 100) : g === 'cer' || (g === 'dual' && z.l2 === 'CER') ? vn * (oq.coef || Pa / 100) : it.adj * 100 / z.P;
    const md = new Date(mat * 864e5).toISOString().slice(0, 7); pay.push([md >= '2029-01' ? '2029+' : md, g, Math.round(pv * 1000) / 1000]);
  }
  return { fam: AF, cuts, res, pay, mats: R.ins.map(x => [x.t, new Date(matOf(x.t) * 864e5).toISOString().slice(0, 10)]) };
}

/* ---------- 3. escritura en licitaciones.html ---------- */
function write(o, REF) {
  const ve = s => s.slice(8, 10) + '/' + s.slice(5, 7) + '/' + s.slice(0, 4);
  // vencimientos del llamado según la ficha del bono
  o.mats.forEach(([t, m]) => { const l = (LLAM[R.c] || []).find(y => y.t === t); if (l && l.ve !== ve(m)) { const a = `{t:"${t}",f:"${l.f}",k:"${l.k}",ve:"${l.ve}"}`; if (S.includes(a)) { S = S.replace(a, a.replace(l.ve, ve(m))); console.log('corregí el vencimiento de ' + t + ' en el llamado: ' + ve(m)); } } R.ins.find(x => x.t === t).ve = ve(m); });
  // RES
  const rs = o.res.map(r => { const x = R.ins.find(y => y.t === r.t); return ` {t:"${r.t}",f:"${r.f}",k:"${x.k || ''}",ve:"${x.ve}",adj:${r.adj},tasa:${r.tasa},u:"${r.u}"${r.x ? `,x:"${r.x}"` : ''},pP:${r.pP},pD:${r.pD},secP:${r.secP},secD:${r.secD}}`; }).join(',\n');
  const entry = `"${R.c}":{adjTotal:${R.adj},oferTotal:${R.ofr == null ? null : R.ofr},rollover:${R.roll == null ? null : R.roll},instrumentos:[\n${rs}]},\n`;
  const re = new RegExp(`"${R.c}":\\{adjTotal[\\s\\S]*?\\]\\},\\n`); S = re.test(S) ? S.replace(re, entry) : S.replace('const RES={\n', 'const RES={\n' + entry);
  // LD
  const i = S.indexOf('const LD=') + 9, j = S.indexOf('\n', i), LD = JSON.parse(S.slice(i, j).replace(/;\s*$/, ''));
  const cuts = o.cuts, F = {}; cuts.forEach(c => F[c.g] = Math.round(((F[c.g] || 0) + c.v) * 1e4) / 1e4);
  const A = { c: R.c, q: Q, ref: REF, same: REF === R.c ? 1 : 0, adj: R.adj, ofr: R.ofr, fam: Object.fromEntries(Object.keys(o.fam).sort().map(g => [g, o.fam[g]])), cuts };
  const ai = LD.AUC.findIndex(a => a.c === R.c); if (ai >= 0) LD.AUC[ai] = A; else { LD.AUC.push(A); LD.AUC.sort((a, b) => a.c < b.c ? -1 : 1); }
  const vw = cuts.reduce((a, c) => a + c.v, 0), p = cuts.reduce((a, c) => a + c.x * c.v, 0) / vw;
  const adj = { l: Q, a: R.adj, f: F, p: Math.round(p * 10) / 10, mn: Math.min(...cuts.map(c => c.x)), mx: Math.max(...cuts.map(c => c.x)), n: cuts.length, src: R.src };
  const di = LD.ADJ.findIndex(a => a.l === Q); if (di >= 0) LD.ADJ[di] = adj; else { LD.ADJ.push(adj); LD.ADJ.sort((a, b) => a.l < b.l ? -1 : 1); }
  if (R.roll != null) LD.ROLL[Q] = [R.roll, 'MECON']; LD.L2C[Q] = R.c;
  const ca = {}, pr = { l: Q, c: R.c };
  ['fija', 'cer', 'tamar', 'dual', 'dl'].forEach(g => { const cc = cuts.filter(c => c.g === g); if (!cc.length) return; const v = cc.reduce((a, c) => a + c.v, 0); ca[g] = Math.round(cc.reduce((a, c) => a + c.y * c.v, 0) / v * 100) / 100;
    const pp = cc.filter(c => (c.po != null ? c.po : c.pc) != null); if (pp.length) { pr[g] = Math.round(pp.reduce((a, c) => a + (c.po != null ? c.po : c.pc) * c.v, 0) / pp.reduce((a, c) => a + c.v, 0)); pr['n_' + g] = pp.length; } });
  LD.CUTAVG[Q] = ca; const pi = LD.PREM.findIndex(x => x.l === Q); if (pi >= 0) LD.PREM[pi] = pr; else LD.PREM.push(pr);
  // perfil: si "new" es de otra licitación pasa a la base; si es de esta (otra corrida), se reemplaza
  const PF = LD.PERFIL, same = LD.PFN && LD.PFN.c === R.c;
  PF.forEach(e => { if (!same) Object.entries(e.new).forEach(([g, v]) => e.pre[g] = Math.round(((e.pre[g] || 0) + v) * 1000) / 1000); e.new = {}; });
  o.pay.forEach(([m, g, v]) => { let e = PF.find(x => x.m === m); if (!e) { e = { m, pre: {}, new: {} }; PF.push(e); PF.sort((a, b) => a.m === '2029+' ? 1 : b.m === '2029+' ? -1 : a.m < b.m ? -1 : 1); } e.new[g] = Math.round(((e.new[g] || 0) + v) * 1000) / 1000; });
  LD.PFN = { c: R.c };
  if (arg('seco')) { console.log(JSON.stringify({ cuts, ca, pr, adj }, null, 1)); return; }
  S = S.slice(0, i) + JSON.stringify(LD) + ';' + S.slice(j);
  fs.writeFileSync(LIC, S);
  // control de sintaxis de los scripts de la página
  let n = 0; for (const m of S.matchAll(/<script>([\s\S]*?)<\/script>/g)) { new Function(m[1]); n++; }
  console.log('\nlicitaciones.html actualizado (' + n + ' scripts OK). Mercado: ' + (REF === R.c ? 'cierre del día' : 'cierre del ' + REF));
  console.log('Adjudicado $' + R.adj + ' bill. · ofertado $' + R.ofr + ' bill. · rollover ' + R.roll + '% · plazo prom. ' + Math.round(p) + ' días');
  cuts.forEach(c => console.log(`  ${c.t.padEnd(6)} corte ${c.y.toFixed(2)}%${c.y2 != null ? ' (pata ' + c.l2 + ' ' + c.y2.toFixed(2) + '%)' : ''} · mercado ${c.s == null ? 's/d' : c.s.toFixed(2) + '%'} · premio ${c.po == null ? '—' : (c.po > 0 ? '+' : '') + c.po + ' pb'} vs bono, ${c.pc == null ? '—' : (c.pc > 0 ? '+' : '') + c.pc + ' pb'} vs curva`));
  console.log('Premio promedio por familia (pb): ' + JSON.stringify(pr));
}
