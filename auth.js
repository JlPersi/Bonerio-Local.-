/* Portada de presentación y login (Google o link por mail, con Supabase).
   Mientras ENFORCE sea false, solo aplica a quien la prueba con ?login; con ?intro se ve la portada en vista previa (los botones entran directo).
   Va como primer hijo del <body>: la portada se pinta antes que el resto de la página, así no se ve la terminal por un instante. */
(function () {
  var CFG = { url: 'https://sbvebxqeltvkerrarzqn.supabase.co', key: 'sb_publishable_yhGb-WD_rjY-PohFtWjRig_g54LnhVf' }; // clave pública (publishable): va en la página a propósito
  var SB_JS = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.0/dist/umd/supabase.js';
  // ENFORCE false = prueba: el login solo aplica en el navegador que entró una vez con ?login (se apaga con ?login=0); true = para todos
  var ENFORCE = false, TEST = false;
  try { var lq = location.search.match(/[?&]login(=0)?\b/); if (lq) { if (lq[1]) localStorage.removeItem('blLoginTest'); else localStorage.setItem('blLoginTest', '1'); } TEST = localStorage.getItem('blLoginTest') === '1'; } catch (e) { }
  var ON = !!(CFG.url && CFG.key) && (ENFORCE || TEST), PREVIEW = /[?&]intro\b/.test(location.search);
  if (!ON && !PREVIEW) return;

  var REF = ON ? ((CFG.url.match(/^https:\/\/([^.]+)\./) || [])[1] || '') : '';
  var sb = null, user = null, ov = null;
  function stored() { // sesión guardada por supabase-js (para no mostrar la portada a quien ya entró)
    if (!ON) return false;
    try { var s = JSON.parse(localStorage.getItem('sb-' + REF + '-auth-token') || 'null'); return !!(s && s.refresh_token); } catch (e) { return false; }
  }
  var returning = /[?&]code=/.test(location.search); // vuelve del login de Google o del link del mail

  var css = '' +
    'html.blg,html.blg body{overflow:hidden!important}' +
    '#blIntro{position:fixed;inset:0;z-index:2147483000;overflow-y:auto;overflow-x:hidden;background:#1c1917;color:#f5f5f4;font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased;zoom:1;' +
      'background-image:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:44px 44px}' +
    '#blIntro *{box-sizing:border-box}#blIntro .mo{font-family:"JetBrains Mono",ui-monospace,Menlo,Consolas,monospace}' +
    '#blIntro .tp{height:34px;overflow:hidden;border-bottom:1px solid #44403c;background:#0c0a09;white-space:nowrap;font:500 12px/34px "JetBrains Mono",ui-monospace,monospace;color:#d6d3d1}' +
    '#blIntro .tp>div{display:inline-block;padding-left:16px;animation:blTp 160s linear infinite}#blIntro .tp:hover>div{animation-play-state:paused}' +
    '#blIntro .tp span{margin-right:26px}#blIntro .tp b{color:#f5f5f4;font-weight:700;margin-right:6px}#blIntro .up{color:#34d399}#blIntro .dn{color:#fb7185}#blIntro .eq{color:#a8a29e}' +
    '@keyframes blTp{from{transform:translateX(-50%)}to{transform:translateX(0)}}' +
    '#blIntro .w{max-width:1200px;margin:0 auto;padding:0 28px}' +
    '#blIntro .tb{display:flex;align-items:center;gap:14px;height:64px}#blIntro .tb .sp{flex:1}' +
    '#blIntro .lg{display:flex;align-items:center;gap:10px;font:700 15px "JetBrains Mono",ui-monospace,monospace;letter-spacing:.02em}#blIntro .lg img{width:30px;height:30px;border-radius:7px}' +
    '#blIntro .st{display:flex;align-items:center;gap:8px;font:500 12px "JetBrains Mono",ui-monospace,monospace;color:#a8a29e}#blIntro .st i{width:8px;height:8px;border-radius:50%;background:#78716c}#blIntro .st i.ok{background:#34d399;box-shadow:0 0 0 4px rgba(52,211,153,.15)}' +
    '#blIntro .tb a{font:600 13px Inter,system-ui,sans-serif;color:#1c1917;background:#f6b40e;border-radius:6px;padding:8px 14px;cursor:pointer;text-decoration:none}#blIntro .tb a:hover{background:#fbbf24}' +
    '#blIntro .mn{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:40px;align-items:start;padding:52px 0 20px}' +
    '#blIntro .ey{font:600 12px "JetBrains Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:#75aadb;margin:0 0 18px}' +
    '#blIntro h1{font-size:clamp(32px,4.4vw,52px);line-height:1.06;letter-spacing:-.035em;font-weight:700;margin:0}#blIntro h1 em{font-style:normal;color:#f6b40e}' +
    '#blIntro .ld{margin:20px 0 0;font-size:16px;line-height:1.6;color:#a8a29e;max-width:560px}' +
    '#blIntro .ti{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:34px}' +
    '#blIntro .t{background:#292524;border:1px solid #44403c;border-radius:12px;padding:14px 16px;min-height:104px;position:relative;overflow:hidden}' +
    '#blIntro .t small{display:block;font:600 11px "JetBrains Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;color:#a8a29e}' +
    '#blIntro .t b{display:block;margin-top:8px;font:700 24px "JetBrains Mono",ui-monospace,monospace;letter-spacing:-.02em}#blIntro .t span{display:block;margin-top:4px;font:500 12px "JetBrains Mono",ui-monospace,monospace;color:#a8a29e}' +
    '#blIntro .t svg{position:absolute;right:12px;bottom:12px;width:44%;height:42px}' +
    '#blIntro .src{margin:12px 0 0;font:500 11px "JetBrains Mono",ui-monospace,monospace;color:#78716c}' +
    '#blIntro .ac{position:sticky;top:24px;background:#292524;border:1px solid #44403c;border-radius:16px;padding:28px 26px 24px;box-shadow:0 24px 60px rgba(0,0,0,.35)}' +
    '#blIntro .ac:before{content:"";position:absolute;left:26px;right:26px;top:-1px;height:3px;border-radius:0 0 3px 3px;background:linear-gradient(90deg,#75aadb 0 33%,#f5f5f4 33% 66%,#75aadb 66%)}' +
    '#blIntro .ac h2{margin:0;font-size:22px;font-weight:700;letter-spacing:-.02em}#blIntro .ac .sub{margin:6px 0 22px;font-size:13px;color:#a8a29e;line-height:1.5}' +
    '#blIntro .ac .sw{display:flex;gap:4px;background:#1c1917;border:1px solid #44403c;border-radius:9px;padding:3px;margin-bottom:20px}#blIntro .ac .sw button{flex:1;border:0;border-radius:6px;background:none;color:#a8a29e;font:600 13px Inter,system-ui,sans-serif;padding:8px;cursor:pointer}#blIntro .ac .sw button.on{background:#44403c;color:#f5f5f4}' +
    '#blIntro .bt{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;border-radius:9px;font:600 14px Inter,system-ui,sans-serif;padding:12px 14px;cursor:pointer;border:1px solid #57534e;background:#f5f5f4;color:#1c1917;transition:.15s}#blIntro .bt:hover{background:#fff}#blIntro .bt svg{width:18px;height:18px}' +
    '#blIntro .or{display:flex;align-items:center;gap:12px;margin:18px 0;font:500 11px "JetBrains Mono",ui-monospace,monospace;color:#78716c;text-transform:uppercase;letter-spacing:.08em}#blIntro .or:before,#blIntro .or:after{content:"";flex:1;height:1px;background:#44403c}' +
    '#blIntro input[type=email]{width:100%;padding:12px 14px;border-radius:9px;border:1px solid #57534e;background:#1c1917;color:#f5f5f4;font:14px Inter,system-ui,sans-serif;outline:none}#blIntro input[type=email]:focus{border-color:#f6b40e}' +
    '#blIntro .eb{margin-top:10px;background:#f6b40e;border-color:#f6b40e}#blIntro .eb:hover{background:#fbbf24}#blIntro .eb[disabled]{opacity:.6;cursor:default}' +
    '#blIntro .msg{margin:14px 0 0;font-size:13px;line-height:1.5;color:#d6d3d1}#blIntro .msg:empty{display:none}#blIntro .msg.err{color:#fb7185}#blIntro .msg.ok{color:#34d399}' +
    '#blIntro .lgl{margin:18px 0 0;font-size:11px;color:#78716c;line-height:1.5}' +
    '#blIntro .cat{padding:70px 0 0}#blIntro .cat h3{margin:0 0 6px;font-size:clamp(24px,2.6vw,32px);letter-spacing:-.025em;font-weight:700}#blIntro .cat>p{margin:0 0 26px;color:#a8a29e;font-size:15px}' +
    '#blIntro .cg{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.55fr);gap:24px;align-items:start}' +
    '#blIntro .ls{border-top:1px solid #44403c}#blIntro .ls button{display:grid;grid-template-columns:38px 1fr;gap:4px 10px;width:100%;text-align:left;background:none;border:0;border-bottom:1px solid #44403c;padding:13px 10px;color:#d6d3d1;cursor:pointer;font-family:inherit;border-radius:0;transition:background .15s}' +
    '#blIntro .ls button i{grid-row:span 2;font:700 12px/20px "JetBrains Mono",ui-monospace,monospace;font-style:normal;color:#78716c}#blIntro .ls button b{font-size:15px;font-weight:600;color:#f5f5f4}#blIntro .ls button span{font-size:13px;line-height:1.45;color:#a8a29e;display:none}' +
    '#blIntro .ls button.on{background:#292524}#blIntro .ls button.on i{color:#f6b40e}#blIntro .ls button.on span{display:block}#blIntro .ls button:hover{background:#292524}' +
    '#blIntro .pv{position:sticky;top:24px;background:#0c0a09;border:1px solid #44403c;border-radius:14px;padding:10px}#blIntro .pv img{display:block;width:100%;aspect-ratio:1.6;object-fit:cover;object-position:top;border-radius:8px}' +
    '#blIntro .pv figcaption{display:flex;justify-content:space-between;gap:10px;padding:10px 4px 2px;font:500 11px "JetBrains Mono",ui-monospace,monospace;color:#78716c}' +
    '#blIntro footer{margin-top:80px;padding:24px 0 40px;border-top:1px solid #44403c;display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;font:500 11px/1.6 "JetBrains Mono",ui-monospace,monospace;color:#78716c}' +
    '@media(max-width:900px){#blIntro .mn,#blIntro .cg{grid-template-columns:1fr;gap:28px}#blIntro .mn{padding-top:30px}#blIntro .ac,#blIntro .pv{position:static}#blIntro .pv{order:-1}#blIntro .w{padding:0 16px}#blIntro .st{display:none}#blIntro .t b{font-size:20px}#blIntro .t svg{width:38%;height:34px}#blIntro .cat{padding-top:50px}#blIntro .ld{font-size:15px}}' +
    '#blUser{position:relative}#blUser>button{width:40px;height:40px;border-radius:50%;border:1px solid var(--bd);background:var(--card);color:var(--tx);font:700 15px Inter,system-ui,sans-serif;cursor:pointer;display:flex;align-items:center;justify-content:center;overflow:hidden;padding:0}#blUser>button img{width:100%;height:100%;object-fit:cover}' +
    '#blUser .mn{display:none;position:absolute;right:0;top:48px;z-index:100;min-width:220px;background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:8px;box-shadow:0 10px 30px rgba(0,0,0,.35)}#blUser.on .mn{display:block}' +
    '#blUser .mn div{padding:8px 10px;font-size:13px;color:var(--mu);word-break:break-all}#blUser .mn button{width:100%;text-align:left;background:none;border:0;border-radius:6px;padding:9px 10px;color:var(--tx);font:500 14px Inter,system-ui,sans-serif;cursor:pointer}#blUser .mn button:hover{background:var(--bd)}';

  var G = '<svg viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>';

  var TABS = [ // pestaña, descripción, captura
    ['Tabla de retornos', 'Cuánto rinde cada bono hasta tu fecha de corte según la TIR a la que lo vendas, con cupones reinvertidos o no.', 'retornos'],
    ['Flujos y total return', 'El cronograma de renta y amortización de cada bono, y cuánto cobrás hasta el corte por los nominales que pongas.', 'flujos'],
    ['Globales / Bonares', 'La curva hard dollar por TIR y duración, ley NY contra ley local, y el spread de legislación de cada par.', 'hero'],
    ['Curva pesos', 'Lecaps, Boncaps, CER, TAMAR, dólar linked y duales contra su curva ajustada, con breakevens de inflación y devaluación.', 'curva-pesos'],
    ['Variación diaria', 'Qué subió y qué bajó contra el cierre anterior, en precio y en puntos básicos de tasa, sobre la curva de ayer.', 'variacion'],
    ['Rotación', 'Los pares de bonos que conviene rotar después de costos, con el colchón de tasa que tiene cada salto.', 'rotacion'],
    ['Volumen', 'Cada rueda desde 2023, por bono, familia y plazo, con la rueda de hoy en vivo y para qué lado empujó el precio.', 'volumen'],
    ['Dólar', 'MEP, cable y oficial día por día, la brecha, el canje y cuánta plata pasó de pesos a dólares en el mercado de bonos.', 'dolar'],
    ['Licitaciones', 'El resultado de cada licitación del Tesoro contra el mercado y la curva, y los instrumentos del próximo llamado.', 'licitacion-proxima']
  ];
  var html = '' +
    '<div class="tp" aria-hidden="true"><div data-tape><span class="eq">Cargando cierres…</span></div></div>' +
    '<div class="w"><div class="tb"><span class="lg"><img src="/favicon.svg?v=2" alt="">BONERÍO LOCAL</span><span class="sp"></span>' +
    '<span class="st"><i data-dot></i><span data-mk>Mercado</span></span><a data-login="in">Ingresar</a></div>' +
    '<div class="mn"><div>' +
    '<p class="ey">Terminal analítica · renta fija soberana</p>' +
    '<h1>Cada bono argentino, con su <em>curva</em>, su <em>retorno</em> y su <em>volumen</em>.</h1>' +
    '<p class="ld">Hard dollar y pesos en una misma terminal: precios de cada rueda, curvas ajustadas, escenarios de retorno, rotaciones, el dólar de los bonos y las licitaciones del Tesoro.</p>' +
    '<div class="ti">' +
    '<div class="t"><small>Dólar MEP · AL30</small><b data-k="mep">—</b><span data-k="ccl">&nbsp;</span></div>' +
    '<div class="t"><small>Oficial · A3500</small><b data-k="ofi">—</b><span data-k="ofid">&nbsp;</span><svg data-k="ofis" viewBox="0 0 100 40" preserveAspectRatio="none"></svg></div>' +
    '<div class="t"><small>TAMAR · TNA</small><b data-k="tam">—</b><span data-k="tamd">&nbsp;</span><svg data-k="tams" viewBox="0 0 100 40" preserveAspectRatio="none"></svg></div>' +
    '<div class="t"><small>Riesgo país · pb</small><b data-k="rp">—</b><span data-k="rpd">&nbsp;</span><svg data-k="rps" viewBox="0 0 100 40" preserveAspectRatio="none"></svg></div>' +
    '</div><p class="src" data-k="src">&nbsp;</p></div>' +

    '<div class="ac" data-ac><h2 data-t>Entrá a la terminal</h2><p class="sub" data-s>Con tu cuenta de Google o con un link que te llega al mail. Es gratis.</p>' +
    '<div class="sw"><button data-mode="in" class="on">Ingresar</button><button data-mode="up">Crear cuenta</button></div>' +
    '<button class="bt" data-g>' + G + 'Continuar con Google</button><div class="or">o con tu mail</div>' +
    '<form data-f><input type="email" required placeholder="tu@mail.com" autocomplete="email"><button class="bt eb" type="submit">Mandame el link para entrar</button></form>' +
    '<p class="msg" data-m></p><p class="lgl">Información de mercado con fines informativos; no es una recomendación de inversión. Solo usamos tu mail para el acceso.</p></div></div>' +

    '<div class="cat"><h3>Nueve pantallas, un mismo mercado.</h3><p>Pasá por cada una para ver qué hay adentro.</p><div class="cg"><div class="ls">' +
    TABS.map(function (t, i) { return '<button data-tab="' + i + '"' + (i ? '' : ' class="on"') + '><i>' + (i < 9 ? '0' : '') + (i + 1) + '</i><b>' + t[0] + '</b><span>' + t[1] + '</span></button>'; }).join('') +
    '</div><figure class="pv" style="margin:0"><img data-pv src="/intro/' + TABS[0][2] + '.webp?v=1" alt="' + TABS[0][0] + '" decoding="async"><figcaption><span data-pvn>01 · ' + TABS[0][0] + '</span><span>captura de la terminal</span></figcaption></figure></div></div>' +

    '<footer><span>© ' + new Date().getFullYear() + ' Bonerío Local. Todos los derechos reservados.</span><span>Cierres propios de cada rueda · índices del BCRA · riesgo país de ArgentinaDatos · no es recomendación de inversión</span></footer></div>';

  var st = document.createElement('style'); st.id = 'blIntroCss'; st.textContent = css; document.head.appendChild(st);

  function build() {
    if (ov) return ov;
    ov = document.createElement('div'); ov.id = 'blIntro'; ov.setAttribute('data-html2canvas-ignore', 'true'); ov.innerHTML = html;
    document.body.insertBefore(ov, document.body.firstChild);
    ov.addEventListener('click', function (e) {
      var t = e.target.closest('[data-login]'); if (t) { e.preventDefault(); openLogin(t.getAttribute('data-login')); return; }
      var m = e.target.closest('[data-mode]'); if (m) { mode(m.getAttribute('data-mode')); return; }
      var b = e.target.closest('[data-tab]'); if (b) pick(+b.getAttribute('data-tab'));
    });
    ov.querySelectorAll('[data-tab]').forEach(function (b) { b.addEventListener('mouseenter', function () { if (matchMedia('(hover:hover)').matches) pick(+b.getAttribute('data-tab')); }); });
    ov.querySelector('[data-g]').onclick = google;
    ov.querySelector('[data-f]').onsubmit = function (e) { e.preventDefault(); mail(this.querySelector('input').value.trim()); };
    TABS.forEach(function (t) { var im = new Image(); im.src = '/intro/' + t[2] + '.webp?v=1'; }); // las capturas quedan listas para el cambio
    market();
    return ov;
  }
  function lock() { build(); ov.style.display = ''; document.documentElement.classList.add('blg'); }
  function unlock() {
    if (ov) ov.style.display = 'none'; document.documentElement.classList.remove('blg');
    try { window.dispatchEvent(new Event('resize')); } catch (e) { }
    chip();
  }
  function msg(t, k) { var m = ov.querySelector('[data-m]'); m.textContent = t || ''; m.className = 'msg' + (k ? ' ' + k : ''); }
  function pick(i) {
    ov.querySelectorAll('[data-tab]').forEach(function (b) { b.classList.toggle('on', +b.getAttribute('data-tab') === i); });
    var im = ov.querySelector('[data-pv]'); im.src = '/intro/' + TABS[i][2] + '.webp?v=1'; im.alt = TABS[i][0];
    ov.querySelector('[data-pvn]').textContent = (i < 9 ? '0' : '') + (i + 1) + ' · ' + TABS[i][0];
  }
  function mode(k) {
    ov.querySelectorAll('[data-mode]').forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-mode') === k); });
    ov.querySelector('[data-t]').textContent = k === 'up' ? 'Creá tu cuenta' : 'Entrá a la terminal';
    ov.querySelector('[data-s]').textContent = k === 'up' ? 'Gratis. Elegí Google o tu mail: la cuenta se crea la primera vez que entrás.' : 'Con tu cuenta de Google o con un link que te llega al mail. Es gratis.';
    msg('');
  }
  function openLogin(k) {
    build(); mode(k || 'in'); var a = ov.querySelector('[data-ac]');
    ov.scrollTo({ top: Math.max(0, a.getBoundingClientRect().top + ov.scrollTop - 20), behavior: 'smooth' });
    setTimeout(function () { var i = a.querySelector('input'); if (i && window.innerWidth > 900) i.focus(); }, 300);
  }

  // datos del tablero: los cierres que guarda la terminal cada rueda (no hace falta la cuenta para verlos)
  function nf(v, d) { return v == null || !isFinite(v) ? '—' : v.toLocaleString('es-AR', { minimumFractionDigits: d, maximumFractionDigits: d }); }
  function chg(a, b, d, u) { if (!(a > 0) || !(b > 0)) return '<span class="eq">&nbsp;</span>'; var x = u === 'pb' ? (a - b) * 100 : (a / b - 1) * 100, c = Math.abs(x) < (u === 'pb' ? 0.5 : 0.005) ? 'eq' : x > 0 ? 'up' : 'dn'; return '<span class="' + c + '">' + (x > 0 ? '▲ +' : x < 0 ? '▼ ' : '') + nf(x, d) + (u === 'pb' ? ' pb' : '%') + '</span>'; }
  function rpc(a, b) { if (!(a > 0) || !(b > 0)) return '<span class="eq">&nbsp;</span>'; var x = a - b, c = !x ? 'eq' : x > 0 ? 'dn' : 'up'; return '<span class="' + c + '">' + (x > 0 ? '▲ +' : x < 0 ? '▼ ' : '') + nf(x, 0) + ' pb</span>'; } // riesgo país: subir es malo (rojo)
  var RP = null;
  function spark(svg, ys, col) {
    ys = ys.filter(function (y) { return y > 0; }); if (!svg || ys.length < 2) return;
    var lo = Math.min.apply(null, ys), hi = Math.max.apply(null, ys), r = hi - lo || 1, pts = ys.map(function (y, i) { return (i / (ys.length - 1) * 100).toFixed(1) + ',' + (36 - (y - lo) / r * 32).toFixed(1); }).join(' ');
    svg.innerHTML = '<polyline points="' + pts + '" fill="none" stroke="' + col + '" stroke-width="1.6" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>';
  }
  function last(o, n) { var k = Object.keys(o || {}).sort(); return k.slice(-n).map(function (d) { return [d, o[d]]; }); }
  function market() {
    var q = function (u) { return fetch(u, { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }); };
    var RPA = 'https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais';
    Promise.all([q('/data/closes.json'), q('/data/closes_ars.json'), q('/data/indices.json'), q('/data/dolar.json'), q('/data/riesgo_pais.json'), q(RPA), q(RPA + '/ultimo')]).then(function (R) {
      var cl = R[0], ar = R[1], ix = R[2], dl = R[3], $ = function (k) { return ov.querySelector('[data-k="' + k + '"]'); }, day = '';
      try { // tablero
        var dd = dl && dl.d && last(dl.d, 1)[0], mp = dd && dd[1].mep && dd[1].mep.AL30, pD = cl && cl.D && cl.D[dd && dd[0]], pC = cl && cl.C && cl.C[dd && dd[0]];
        if (mp) { $('mep').textContent = '$ ' + nf(mp.close, 2); day = dd[0]; if (pD && pC && pD.AL30 > 0 && pC.AL30 > 0) $('ccl').textContent = 'Cable $ ' + nf(mp.close * pD.AL30 / pC.AL30, 2) + ' (AL30C)'; } // el cable sale del mismo AL30 en pesos sobre su precio en cable
        var of = last(dl && dl.A3500, 60); if (of.length) { var a = of[of.length - 1][1], b = of.length > 1 ? of[of.length - 2][1] : null; $('ofi').textContent = '$ ' + nf(a, 2); $('ofid').innerHTML = chg(a, b, 2); spark($('ofis'), of.map(function (x) { return x[1]; }), '#75aadb'); }
        var tm = last(ix && ix.TAMAR, 40); if (tm.length) { var t1 = tm[tm.length - 1][1], t0 = tm.length > 1 ? tm[tm.length - 2][1] : null; $('tam').textContent = nf(t1, 2) + '%'; $('tamd').innerHTML = chg(t1, t0, 0, 'pb'); spark($('tams'), tm.map(function (x) { return x[1]; }), '#f6b40e'); }
        var rm = {}; if (R[4] && R[4].d) Object.keys(R[4].d).forEach(function (f) { rm[f] = R[4].d[f]; }); // riesgo país: lo guardado cada noche más lo último de ArgentinaDatos
        [R[5], R[6]].forEach(function (x) { if (x) (Array.isArray(x) ? x : [x]).forEach(function (r) { var f = String(r && r.fecha || '').slice(0, 10); if (f.length === 10 && r.valor > 0) rm[f] = r.valor; }); });
        var rp = last(rm, 90); if (rp.length) { var r1 = rp[rp.length - 1][1], r0 = rp.length > 1 ? rp[rp.length - 2][1] : null; $('rp').textContent = nf(r1, 0) + ' pb'; $('rpd').innerHTML = rpc(r1, r0); spark($('rps'), rp.map(function (x) { return x[1]; }), '#fb7185'); RP = [r1, r0]; }
        var lc = last(cl && cl.D, 1)[0]; if (lc && lc[0] > day) day = lc[0];
        if (day) $('src').textContent = 'Cierre del ' + day.slice(8, 10) + '/' + day.slice(5, 7) + '/' + day.slice(0, 4) + ' · cierres propios e índices del BCRA';
      } catch (e) { console.error(e); }
      try { // cinta: variación de cada bono contra la rueda anterior
        var it = [], two = function (o) { var k = Object.keys(o || {}).sort(); return k.length > 1 ? [o[k[k.length - 1]], o[k[k.length - 2]]] : null; };
        var hd = two(cl && cl.D), pe = two(ar);
        if (RP) it.push(['RIESGO PAÍS', RP[0], RP[1], 0, 1]);
        if (hd) Object.keys(hd[0]).sort().forEach(function (t) { it.push([t + 'D', hd[0][t], hd[1][t], 2]); });
        if (pe) Object.keys(pe[0]).filter(function (t) { return /^(S\d|T\d|TX|TZX|TZV|TM|X\d|D\d)/.test(t); }).sort().forEach(function (t) { it.push([t, pe[0][t], pe[1][t], pe[0][t] >= 1000 ? 0 : 2]); });
        if (it.length) { var tx = it.map(function (x) { return '<span><b>' + x[0] + '</b>' + nf(x[1], x[3]) + (x[4] ? ' pb ' + rpc(x[1], x[2]) : ' ' + chg(x[1], x[2], 2)) + '</span>'; }).join(''); ov.querySelector('[data-tape]').innerHTML = tx + tx; } // dos veces: la cinta da la vuelta sin cortes
      } catch (e) { console.error(e); }
    });
    var mk = function () { try { if (typeof window.mktOpen === 'function') { var o = window.mktOpen(); ov.querySelector('[data-dot]').className = o ? 'ok' : ''; ov.querySelector('[data-mk]').textContent = o ? 'Mercado abierto' : 'Mercado cerrado'; } } catch (e) { } };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mk); else mk();
  }
  function back() { return location.origin + location.pathname; }
  function google() {
    if (!ON) { unlock(); return; } // vista previa
    if (!sb) { msg('No se pudo conectar con el servicio de cuentas. Probá de nuevo en un rato.', 'err'); return; }
    msg('Abriendo Google…');
    sb.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: back() } }).then(function (r) { if (r.error) msg(r.error.message, 'err'); });
  }
  function mail(em) {
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em)) { msg('Revisá el mail.', 'err'); return; }
    if (!ON) { unlock(); return; }
    if (!sb) { msg('No se pudo conectar con el servicio de cuentas. Probá de nuevo en un rato.', 'err'); return; }
    var b = ov.querySelector('.eb'); b.disabled = true; msg('Mandando…');
    sb.auth.signInWithOtp({ email: em, options: { emailRedirectTo: back() } }).then(function (r) {
      b.disabled = false;
      if (r.error) msg(/rate|seconds/i.test(r.error.message) ? 'Ya te mandamos un link hace un momento: esperá un minuto antes de pedir otro.' : r.error.message, 'err');
      else msg('Listo: te mandamos un link a ' + em + '. Abrilo en este mismo navegador para entrar (si no llega, mirá en spam).', 'ok');
    });
  }
  function chip() {
    var bar = document.getElementById('themeBtn'); bar = bar && bar.parentNode;
    if (!bar) { if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', chip); return; }
    if (document.getElementById('blUser')) return;
    var u = user || {}, m = u.user_metadata || {}, name = m.full_name || m.name || u.email || 'Vista previa', pic = m.avatar_url || m.picture;
    var d = document.createElement('div'); d.id = 'blUser'; d.setAttribute('data-html2canvas-ignore', 'true');
    d.innerHTML = '<button title="' + esc(name) + '">' + (pic ? '<img src="' + esc(pic) + '" alt="" referrerpolicy="no-referrer">' : esc((name || '?').charAt(0).toUpperCase())) + '</button>' +
      '<div class="mn"><div>' + esc(u.email || name) + '</div><button data-out>Cerrar sesión</button></div>';
    bar.appendChild(d);
    d.firstChild.onclick = function (e) { e.stopPropagation(); d.classList.toggle('on'); };
    d.querySelector('[data-out]').onclick = function () { d.classList.remove('on'); logout(); };
    document.addEventListener('click', function (e) { if (!d.contains(e.target)) d.classList.remove('on'); });
  }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function logout() {
    var c = document.getElementById('blUser'); if (c) c.remove(); user = null;
    if (sb) sb.auth.signOut().then(function () { lock(); }); else lock();
  }

  // arranque: quien ya entró ve la terminal directo; el resto, la portada
  if (stored() || returning) document.documentElement.classList.remove('blg'); else lock();
  if (!ON) return;
  var s = document.createElement('script'); s.src = SB_JS; s.async = true;
  s.onload = function () {
    try { sb = window.supabase.createClient(CFG.url, CFG.key, { auth: { flowType: 'pkce', persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } }); } catch (e) { console.error(e); if (!stored()) lock(); return; }
    sb.auth.onAuthStateChange(function (ev, ses) {
      if (ses && ses.user) { user = ses.user; unlock(); if (/[?&]code=/.test(location.search)) history.replaceState(null, '', back() + location.hash); }
      else if (ev === 'SIGNED_OUT' || ev === 'INITIAL_SESSION') { user = null; var c = document.getElementById('blUser'); if (c) c.remove(); lock(); }
    });
  };
  s.onerror = function () { if (!stored()) lock(); else unlock(); }; // sin el servicio de cuentas, quien ya había entrado sigue entrando
  document.head.appendChild(s);
})();
