/* Portada de presentación y login con Supabase: Google, mail y contraseña (con recuperación) o link por mail.
   Con ENFORCE en true, toda persona tiene que entrar con su cuenta para usar la terminal (si se pone en false, solo aplica a quien la prueba con ?login).
   Va como primer hijo del <body>: la portada se pinta antes que el resto de la página, así no se ve la terminal por un instante. */
(function () {
  var CFG = { url: 'https://sbvebxqeltvkerrarzqn.supabase.co', key: 'sb_publishable_yhGb-WD_rjY-PohFtWjRig_g54LnhVf' }; // clave pública (publishable): va en la página a propósito
  var SB_JS = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.0/dist/umd/supabase.js';
  // ENFORCE false = prueba: el login solo aplica en el navegador que entró una vez con ?login (se apaga con ?login=0); true = para todos
  var ENFORCE = true, TEST = false;
  try { var lq = location.search.match(/[?&]login(=0)?\b/); if (lq) { if (lq[1]) localStorage.removeItem('blLoginTest'); else localStorage.setItem('blLoginTest', '1'); } TEST = localStorage.getItem('blLoginTest') === '1'; } catch (e) { }
  var ON = !!(CFG.url && CFG.key) && (ENFORCE || TEST), PREVIEW = /[?&]intro\b/.test(location.search);
  if (!ON && !PREVIEW) return;

  var REF = ON ? ((CFG.url.match(/^https:\/\/([^.]+)\./) || [])[1] || '') : '';
  if (window.top !== window && /[?&]emb=/.test(location.search) && stored()) { document.documentElement.classList.remove('blg'); return; } // widget del Dashboard: la página que lo contiene ya entró (sin portada ni presencia)
  var sb = null, user = null, ov = null;
  function stored() { // sesión guardada por supabase-js (para no mostrar la portada a quien ya entró)
    if (!ON) return false;
    try { var s = JSON.parse(localStorage.getItem('sb-' + REF + '-auth-token') || 'null'); return !!(s && s.refresh_token); } catch (e) { return false; }
  }
  var returning = /[?&]code=/.test(location.search); // vuelve del login de Google o del link del mail
  var RESET = returning && /[?&]reset=1\b/.test(location.search); // vuelve del link para elegir una contraseña nueva

  var css = '' +
    'html.blg,html.blg body{overflow:hidden!important}' +
    '#blIntro{position:fixed;inset:0;z-index:2147483000;overflow-y:auto;overflow-x:hidden;background:#0a0a0b;color:#f4f4f5;font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased;zoom:1}' +
    '#blIntro *{box-sizing:border-box}#blIntro .fh,#blIntro h1,#blIntro h2,#blIntro h3{font-family:"Bricolage Grotesque",Inter,system-ui,sans-serif}' +
    '#blIntro .gl{position:absolute;left:0;right:0;top:0;height:1150px;pointer-events:none;overflow:hidden;background:radial-gradient(640px 440px at 10% 6%,rgba(255,197,66,.14),transparent 70%),radial-gradient(760px 520px at 92% 14%,rgba(92,200,255,.12),transparent 70%),radial-gradient(560px 420px at 50% 78%,rgba(201,160,255,.07),transparent 70%)}' +
    '#blIntro .gl:after{content:"";position:absolute;inset:0;background-image:radial-gradient(rgba(255,255,255,.08) 1px,transparent 1.2px);background-size:24px 24px;-webkit-mask-image:radial-gradient(ellipse 80% 70% at 50% 0%,#000 25%,transparent 75%);mask-image:radial-gradient(ellipse 80% 70% at 50% 0%,#000 25%,transparent 75%)}' +
    '#blIntro .tp{position:relative;height:36px;overflow:hidden;border-bottom:1px solid #1f1f22;background:rgba(10,10,11,.6);white-space:nowrap;font:500 12px/36px Inter,system-ui,sans-serif;font-variant-numeric:tabular-nums;color:#a1a1aa}' +
    '#blIntro .tp>div{display:inline-block;padding-left:16px;animation:blTp 160s linear infinite}#blIntro .tp:hover>div{animation-play-state:paused}' +
    '#blIntro .tp span{margin-right:28px}#blIntro .tp b{color:#f4f4f5;font-weight:600;margin-right:6px}#blIntro .up{color:#34d399}#blIntro .dn{color:#ff6b8b}#blIntro .eq{color:#71717a}' +
    '@keyframes blTp{from{transform:translateX(-50%)}to{transform:translateX(0)}}' +
    '#blIntro .w{position:relative;max-width:1240px;margin:0 auto;padding:0 28px}' +
    '#blIntro .tb{display:flex;align-items:center;gap:12px;height:76px}#blIntro .tb .sp{flex:1}' +
    '#blIntro .lg{display:flex;align-items:center;gap:10px;font:700 14px Inter,system-ui,sans-serif;letter-spacing:.08em}#blIntro .lg img{width:30px;height:30px;border-radius:8px}' +
    '#blIntro .st{display:flex;align-items:center;gap:8px;height:34px;padding:0 14px;border-radius:99px;border:1px solid #232326;background:rgba(255,255,255,.03);font:600 12px Inter,system-ui,sans-serif;color:#a1a1aa}#blIntro .st i{width:7px;height:7px;border-radius:50%;background:#71717a}#blIntro .st i.ok{background:#34d399;box-shadow:0 0 10px rgba(52,211,153,.7)}#blIntro .st i.bad{background:#ff6b8b;box-shadow:0 0 10px rgba(255,107,139,.6)}#blIntro .st.ok,#blIntro .st.bad{color:#e4e4e7}' +
    '#blIntro .tb a{font:600 13px Inter,system-ui,sans-serif;color:#0a0a0b;background:#f4f4f5;border-radius:99px;padding:9px 18px;cursor:pointer;text-decoration:none;transition:.15s}#blIntro .tb a:hover{background:#fff}' +
    '#blIntro .mn{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:56px;align-items:start;padding:58px 0 20px}' +
    '#blIntro .ey{display:inline-flex;align-items:center;gap:9px;margin:0 0 26px;padding:6px 14px 6px 11px;border-radius:99px;border:1px solid #2a2a2e;background:rgba(255,255,255,.04);font:600 12px Inter,system-ui,sans-serif;letter-spacing:.02em;color:#d4d4d8}#blIntro .ey:before{content:"";width:6px;height:6px;border-radius:50%;background:#ffc542;box-shadow:0 0 10px #ffc542}' +
    '#blIntro h1{font-size:clamp(40px,5.3vw,72px);line-height:.98;letter-spacing:-.045em;font-weight:700;margin:0}#blIntro h3 .dm{color:#71717a}#blIntro h1 em{font-style:normal}' +
    '#blIntro .k1{color:#ffc542}#blIntro .k2{color:#b8e986}#blIntro .k3{color:#5cc8ff}' +
    '#blIntro .ld{margin:26px 0 0;font-size:17px;line-height:1.6;color:#a1a1aa;max-width:580px}' +
    '#blIntro .ct{display:flex;flex-wrap:wrap;gap:10px;margin-top:30px}#blIntro .ct button{border-radius:99px;padding:13px 22px;font:600 14px Inter,system-ui,sans-serif;cursor:pointer;transition:.15s;border:1px solid transparent}' +
    '#blIntro .ct .c1{background:#ffc542;color:#141414}#blIntro .ct .c1:hover{background:#ffd36b}#blIntro .ct .c2{background:rgba(255,255,255,.04);border-color:#2a2a2e;color:#f4f4f5}#blIntro .ct .c2:hover{background:rgba(255,255,255,.08)}' +
    '#blIntro .ti{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:40px}' +
    '#blIntro .t{--c:#a1a1aa;background:linear-gradient(160deg,color-mix(in srgb,var(--c) 13%,transparent),transparent 58%),#131314;border:1px solid #232326;border-radius:20px;padding:16px 18px;min-height:116px;position:relative;overflow:hidden}' +
    '#blIntro .t small{display:flex;align-items:center;gap:7px;font:600 11px Inter,system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:#a1a1aa}#blIntro .t small:before{content:"";width:6px;height:6px;border-radius:50%;background:var(--c)}' +
    '#blIntro .t b{display:block;margin-top:10px;font:700 28px "Bricolage Grotesque",Inter,sans-serif;letter-spacing:-.025em;font-variant-numeric:tabular-nums}#blIntro .t span{display:block;margin-top:4px;font:500 12px Inter,system-ui,sans-serif;color:#a1a1aa}' +
    '#blIntro .t svg{position:absolute;right:14px;bottom:14px;width:44%;height:44px}' +
    '#blIntro .src{margin:12px 0 0;font:500 12px Inter,system-ui,sans-serif;color:#71717a}' +
    '#blIntro .ac{position:sticky;top:28px;background:rgba(19,19,20,.86);-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px);border:1px solid #2a2a2e;border-radius:26px;padding:30px 28px 26px;box-shadow:0 40px 90px rgba(0,0,0,.55)}' +
    '#blIntro .ac:before{content:"";position:absolute;left:30px;right:30px;top:-1px;height:1px;background:linear-gradient(90deg,transparent,#ffc542 30%,#5cc8ff 70%,transparent)}' +
    '#blIntro .ac h2{margin:0;font-size:28px;font-weight:700;letter-spacing:-.03em}#blIntro .ac .sub{margin:6px 0 22px;font-size:14px;color:#a1a1aa;line-height:1.5}' +
    '#blIntro .ac .sw{display:flex;gap:4px;background:#0a0a0b;border:1px solid #232326;border-radius:99px;padding:4px;margin-bottom:20px}#blIntro .ac .sw button{flex:1;border:0;border-radius:99px;background:none;color:#a1a1aa;font:600 13px Inter,system-ui,sans-serif;padding:9px;cursor:pointer;transition:.15s}#blIntro .ac .sw button.on{background:#f4f4f5;color:#0a0a0b}' +
    '#blIntro .bt{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;border-radius:99px;font:600 14px Inter,system-ui,sans-serif;padding:13px 16px;cursor:pointer;border:1px solid #f4f4f5;background:#f4f4f5;color:#0a0a0b;transition:.15s}#blIntro .bt:hover{background:#fff}#blIntro .bt svg{width:18px;height:18px}' +
    '#blIntro .or{display:flex;align-items:center;gap:12px;margin:20px 0;font:600 11px Inter,system-ui,sans-serif;color:#71717a;text-transform:uppercase;letter-spacing:.1em}#blIntro .or:before,#blIntro .or:after{content:"";flex:1;height:1px;background:#232326}' +
    '#blIntro .lb{display:block;margin:0 0 12px;font-size:12px;font-weight:600;color:#d4d4d8}#blIntro .lb>span{display:block;margin-bottom:6px}' +
    '#blIntro .lb input{display:block;width:100%;padding:13px 16px;border-radius:14px;border:1px solid #2a2a2e;background:#0a0a0b;color:#f4f4f5;font:14px Inter,system-ui,sans-serif;outline:none;transition:.15s}#blIntro .lb input:focus{border-color:#ffc542;box-shadow:0 0 0 3px rgba(255,197,66,.16)}' +
    '#blIntro .pw{position:relative;display:block}#blIntro .pw input{padding-right:46px}#blIntro .pw button{position:absolute;top:0;right:0;bottom:0;width:46px;display:flex;align-items:center;justify-content:center;background:none;border:0;color:#a1a1aa;cursor:pointer}#blIntro .pw button:hover{color:#f4f4f5}#blIntro .pw svg{width:18px;height:18px}' +
    '#blIntro .ln{background:none;border:0;padding:0;color:#ffc542;font:500 12px Inter,system-ui,sans-serif;cursor:pointer;text-decoration:underline;text-underline-offset:3px}#blIntro .ln:hover{color:#ffd36b}#blIntro .fx{display:flex;justify-content:flex-end;margin:-4px 0 12px}#blIntro .ml{display:block;margin:14px auto 0}#blIntro [hidden]{display:none!important}' +
    '#blIntro .eb{margin-top:6px;background:#ffc542;border-color:#ffc542;color:#141414}#blIntro .eb:hover{background:#ffd36b}#blIntro .eb[disabled]{opacity:.6;cursor:default}' +
    '#blIntro .msg{margin:14px 0 0;font-size:13px;line-height:1.5;color:#d4d4d8}#blIntro .msg:empty{display:none}#blIntro .msg.err{color:#ff6b8b}#blIntro .msg.ok{color:#34d399}' +
    '#blIntro .lgl{margin:18px 0 0;font-size:11px;color:#71717a;line-height:1.5}#blIntro .lgl a,#blIntro footer a{color:#a1a1aa;text-underline-offset:2px}#blIntro .lgl a:hover,#blIntro footer a:hover{color:#ffc542}' +
    '#blIntro .sh{margin:0 0 8px;font-size:clamp(28px,3.4vw,46px);letter-spacing:-.04em;font-weight:700;line-height:1.02}#blIntro .shp{margin:0 0 30px;color:#a1a1aa;font-size:16px}' +
    '#blIntro .fm{padding:96px 0 0}#blIntro .fg{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}' +
    '#blIntro .f{--c:#a1a1aa;position:relative;overflow:hidden;min-height:214px;padding:22px 22px 0;border-radius:24px;border:1px solid color-mix(in srgb,var(--c) 24%,#232326);background:linear-gradient(165deg,color-mix(in srgb,var(--c) 17%,transparent),transparent 62%),#131314;transition:transform .2s,border-color .2s}#blIntro .f:hover{transform:translateY(-3px);border-color:color-mix(in srgb,var(--c) 50%,#232326)}' +
    '#blIntro .f i{display:inline-block;font:700 10.5px Inter,system-ui,sans-serif;font-style:normal;letter-spacing:.1em;text-transform:uppercase;color:var(--c);padding:4px 10px;border-radius:99px;border:1px solid color-mix(in srgb,var(--c) 40%,transparent);background:color-mix(in srgb,var(--c) 8%,transparent)}' +
    '#blIntro .f b{display:block;margin:14px 0 6px;font:700 22px "Bricolage Grotesque",Inter,sans-serif;letter-spacing:-.025em}#blIntro .f p{margin:0;font-size:13.5px;line-height:1.5;color:#a1a1aa;max-width:340px}' +
    '#blIntro .f svg{display:block;width:calc(100% + 44px);height:84px;margin:12px -22px 0}' +
    '#blIntro .cat{padding:96px 0 0}' +
    '#blIntro .cg{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.6fr);gap:26px;align-items:start}' +
    '#blIntro .ls button{display:grid;grid-template-columns:34px 1fr;gap:4px 10px;width:100%;text-align:left;background:none;border:1px solid transparent;margin:0 0 2px;padding:12px 14px;color:#d4d4d8;cursor:pointer;font-family:inherit;border-radius:16px;transition:background .15s}' +
    '#blIntro .ls button i{grid-row:span 2;font:700 12px/20px Inter,system-ui,sans-serif;font-variant-numeric:tabular-nums;font-style:normal;color:#52525b}#blIntro .ls button b{font-size:15px;font-weight:600;color:#e4e4e7}#blIntro .ls button span{font-size:13px;line-height:1.45;color:#a1a1aa;display:none}' +
    '#blIntro .ls button.on{background:#131314;border-color:#232326}#blIntro .ls button.on i{color:#ffc542}#blIntro .ls button.on b{color:#fff}#blIntro .ls button.on span{display:block}#blIntro .ls button:hover{background:#131314}' +
    '#blIntro .pv{position:sticky;top:28px;background:#131314;border:1px solid #232326;border-radius:26px;padding:10px;box-shadow:0 50px 120px rgba(0,0,0,.6),0 0 120px rgba(92,200,255,.06)}#blIntro .pv img{display:block;width:100%;aspect-ratio:1.6;object-fit:cover;object-position:top;border-radius:18px;background:#0a0a0b}' +
    '#blIntro .pv figcaption{display:flex;justify-content:space-between;gap:10px;padding:12px 8px 4px;font:500 12px Inter,system-ui,sans-serif;color:#71717a}' +
    '#blIntro footer{margin-top:96px;padding:26px 0 44px;border-top:1px solid #1f1f22;display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;font:500 12px/1.6 Inter,system-ui,sans-serif;color:#71717a}' +
    '@media(max-width:1000px){#blIntro .fg{grid-template-columns:repeat(2,minmax(0,1fr))}}' +
    '@media(max-width:900px){#blIntro .mn,#blIntro .cg{grid-template-columns:1fr;gap:30px}#blIntro .mn{padding-top:30px}#blIntro .ac,#blIntro .pv{position:static}#blIntro .pv{order:-1}#blIntro .w{padding:0 16px}#blIntro .st{display:none}#blIntro .t b{font-size:22px}#blIntro .t svg{width:38%;height:34px}#blIntro .fm,#blIntro .cat{padding-top:64px}#blIntro .ld{font-size:15.5px}#blIntro .fg{grid-template-columns:1fr}#blIntro .f{min-height:0}}' +
    '#blUser{position:relative}#blUser>button{width:40px;height:40px;border-radius:50%;border:1px solid var(--bd);background:var(--card);color:var(--tx);font:700 15px Inter,system-ui,sans-serif;cursor:pointer;display:flex;align-items:center;justify-content:center;overflow:hidden;padding:0}#blUser>button img{width:100%;height:100%;object-fit:cover}' +
    '#blUser .mn{display:none;position:absolute;right:0;top:48px;z-index:100;min-width:220px;background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:8px;box-shadow:0 10px 30px rgba(0,0,0,.35)}#blUser.on .mn{display:block}' +
    '#blUser .mn div{padding:8px 10px;font-size:13px;color:var(--mu);word-break:break-all}#blUser .mn button{width:100%;text-align:left;background:none;border:0;border-radius:6px;padding:9px 10px;color:var(--tx);font:500 14px Inter,system-ui,sans-serif;cursor:pointer}#blUser .mn button:hover{background:var(--bd)}' +
    '#blLive{position:fixed;inset:0;z-index:200;background:rgba(0,0,0,.55);display:flex;align-items:flex-start;justify-content:center;padding:70px 16px 16px;overflow:auto}#blLive .bx{width:100%;max-width:760px;background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:18px 20px;color:var(--tx);font:14px Inter,system-ui,sans-serif;box-shadow:0 20px 50px rgba(0,0,0,.4)}' +
    '#blLive h3{margin:0;font-size:18px}#blLive h4{margin:18px 0 8px;font-size:13px;color:var(--mu);text-transform:uppercase;letter-spacing:.04em}#blLive .hd{display:flex;justify-content:space-between;align-items:center;gap:12px}#blLive .x{background:none;border:1px solid var(--bd);border-radius:8px;color:var(--tx);width:34px;height:34px;cursor:pointer;font-size:18px}' +
    '#blLive .tw{overflow-x:auto}#blLive table{width:100%;border-collapse:collapse}#blLive td,#blLive th{padding:8px 6px;border-bottom:1px solid var(--bd);text-align:left;font-size:13px}#blLive th{color:var(--mu);font-weight:600;font-size:11px;text-transform:uppercase}#blLive .dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#22c55e;margin-right:6px}#blLive .mu{color:var(--mu);font-size:12px;margin:10px 0 0}';

  var EYE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
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
    ['Mercado de dinero', 'Caución, plazo fijo, TAMAR, BADLAR y Lecaps cortas en una sola curva de tasas, con la caución en dólares.', 'dinero'],
    ['Futuros', 'Los futuros de dólar de A3 con su tasa implícita y devaluación mensual, volumen, interés abierto y tasas forward.', 'futuros'],
    ['Sintéticos', 'Lecaps con futuro de dólar contra el dollar linked del mismo plazo: qué cobertura sale más barata.', 'sinteticos'],
    ['Licitaciones', 'El resultado de cada licitación del Tesoro contra el mercado y la curva, y los instrumentos del próximo llamado.', 'licitacion-proxima'],
    ['Expectativas', 'La inflación y la devaluación que descuentan los bonos, bono por bono y contra el REM, y las tasas forward entre plazos.', 'expectativas'],
    ['Historia y señales', 'La tasa de cada bono día por día y cuánto se aleja hoy de su curva contra lo habitual: las señales de rotación.', 'historia'],
    ['Portfolio', 'Tus bonos con sus nominales: valor, duración, escenarios de tasas, value at risk y el flujo de fondos que vas a cobrar.', 'portfolio']
  ];
  var NUM = ['', 'Una', 'Dos', 'Tres', 'Cuatro', 'Cinco', 'Seis', 'Siete', 'Ocho', 'Nueve', 'Diez', 'Once', 'Doce', 'Trece', 'Catorce', 'Quince', 'Dieciséis'];
  var html = '' +
    '<div class="gl" aria-hidden="true"></div><div class="tp" aria-hidden="true"><div data-tape><span class="eq">Cargando cierres…</span></div></div>' +
    '<div class="w"><div class="tb"><span class="lg"><img src="/favicon.svg?v=2" alt="">BONERÍO LOCAL</span><span class="sp"></span>' +
    '<span class="st"><i data-dot></i><span data-mk>Mercado</span></span><a data-login="in">Ingresar</a></div>' +
    '<div class="mn"><div>' +
    '<p class="ey">Terminal analítica · renta fija argentina</p>' +
    '<h1><span class="dm">Cada bono argentino,</span> con su <em class="k1">curva</em>, su <em class="k2">retorno</em> y su <em class="k3">volumen</em>.</h1>' +
    '<p class="ld">Hard dollar y pesos en una misma terminal: precios de cada rueda, curvas ajustadas, escenarios de retorno, rotaciones, el dólar de los bonos, las licitaciones del Tesoro, lo que descuenta el mercado de inflación y devaluación, y tu portfolio.</p>' +
    '<div class="ct"><button class="c1" data-login="up">Crear cuenta</button><button class="c2" data-cat>Ver las pantallas</button></div>' +
    '<div class="ti">' +
    '<div class="t" style="--c:#5cc8ff"><small>Dólar MEP · AL30</small><b data-k="mep">—</b><span data-k="ccl">&nbsp;</span></div>' +
    '<div class="t" style="--c:#e4e4e7"><small>Oficial · A3500</small><b data-k="ofi">—</b><span data-k="ofid">&nbsp;</span><svg data-k="ofis" viewBox="0 0 100 40" preserveAspectRatio="none"></svg></div>' +
    '<div class="t" style="--c:#ff8fb3"><small>TAMAR · TNA</small><b data-k="tam">—</b><span data-k="tamd">&nbsp;</span><svg data-k="tams" viewBox="0 0 100 40" preserveAspectRatio="none"></svg></div>' +
    '<div class="t" style="--c:#b8e986"><small>Riesgo país · pb</small><b data-k="rp">—</b><span data-k="rpd">&nbsp;</span><svg data-k="rps" viewBox="0 0 100 40" preserveAspectRatio="none"></svg></div>' +
    '</div><p class="src" data-k="src">&nbsp;</p></div>' +

    '<div class="ac" data-ac><h2 data-t>Entrá a la terminal</h2><p class="sub" data-s></p>' +
    '<div class="sw" data-v="sw"><button data-mode="in" class="on">Ingresar</button><button data-mode="up">Crear cuenta</button></div>' +
    '<div data-v="g"><button class="bt" data-g>' + G + 'Continuar con Google</button><div class="or">o con tu mail</div></div>' +
    '<form data-f novalidate><label class="lb" data-v="em"><span>Correo electrónico</span><input type="email" name="em" placeholder="tu@mail.com" autocomplete="email"></label>' +
    '<label class="lb" data-v="pw"><span data-pwl>Contraseña</span><span class="pw"><input type="password" name="pw" placeholder="Tu contraseña" autocomplete="current-password"><button type="button" data-eye aria-label="Mostrar contraseña" title="Mostrar contraseña">' + EYE + '</button></span></label>' +
    '<div class="fx" data-v="fg"><button type="button" class="ln" data-go="forgot">¿Olvidaste tu contraseña?</button></div>' +
    '<button class="bt eb" type="submit" data-sub>Ingresar</button></form>' +
    '<button type="button" class="ln ml" data-alt></button>' +
    '<p class="msg" data-m></p><p class="lgl">Al ingresar, aceptás los <a href="/terminos.html" target="_blank" rel="noopener">Términos y Condiciones</a> y confirmás que leíste la <a href="/privacidad.html" target="_blank" rel="noopener">Política de Privacidad</a>. La información es con fines informativos; no es una recomendación de inversión.</p></div></div>' +

    '<div class="fm"><h3 class="sh"><span class="dm">Toda la renta fija,</span> por familia.</h3><p class="shp">Cada familia tiene su color y lo mantiene en todas las pantallas.</p><div class="fg"><div class="f" style="--c:#b8e986"><i>Hard dollar</i><b>Globales y Bonares</b><p>Ley NY contra ley local por TIR y duración, el spread de legislación de cada par y el riesgo país.</p><svg viewBox="0 0 400 90" preserveAspectRatio="none" aria-hidden="true"><path d="M0,80.0 L25,71.4 L50,64.9 L75,59.5 L100,55.0 L125,51.0 L150,47.5 L175,44.3 L200,41.4 L225,38.7 L250,36.2 L275,33.9 L300,31.7 L325,29.6 L350,27.7 L375,25.8 L400,24.0 L400,90 L0,90 Z" style="fill:var(--c);opacity:.10"/><path d="M0,80.0 L25,71.4 L50,64.9 L75,59.5 L100,55.0 L125,51.0 L150,47.5 L175,44.3 L200,41.4 L225,38.7 L250,36.2 L275,33.9 L300,31.7 L325,29.6 L350,27.7 L375,25.8 L400,24.0" fill="none" style="stroke:var(--c)" stroke-width="1.6" stroke-dasharray="4 4" vector-effect="non-scaling-stroke"/><circle cx="50" cy="71.5" r="3" style="fill:var(--c)"/><circle cx="105" cy="50.6" r="3" style="fill:var(--c)"/><circle cx="120" cy="55.4" r="3" style="fill:var(--c)"/><circle cx="175" cy="37.7" r="3" style="fill:var(--c)"/><circle cx="230" cy="40.9" r="3" style="fill:var(--c)"/><circle cx="270" cy="25.1" r="3" style="fill:var(--c)"/><circle cx="300" cy="31.7" r="3" style="fill:var(--c)"/><circle cx="355" cy="36.5" r="3" style="fill:var(--c)"/></svg></div><div class="f" style="--c:#ffc542"><i>Tasa fija</i><b>Lecaps y Boncaps</b><p>La curva de tasa fija con sus desvíos: qué rinde más que la curva y qué rinde menos, en TNA, TEM o TEA.</p><svg viewBox="0 0 400 90" preserveAspectRatio="none" aria-hidden="true"><path d="M0,80.0 L25,73.8 L50,68.7 L75,64.2 L100,60.3 L125,56.7 L150,53.5 L175,50.5 L200,47.7 L225,45.1 L250,42.6 L275,40.3 L300,38.0 L325,35.9 L350,33.9 L375,31.9 L400,30.0 L400,90 L0,90 Z" style="fill:var(--c);opacity:.10"/><path d="M0,80.0 L25,73.8 L50,68.7 L75,64.2 L100,60.3 L125,56.7 L150,53.5 L175,50.5 L200,47.7 L225,45.1 L250,42.6 L275,40.3 L300,38.0 L325,35.9 L350,33.9 L375,31.9 L400,30.0" fill="none" style="stroke:var(--c)" stroke-width="1.6" stroke-dasharray="4 4" vector-effect="non-scaling-stroke"/><circle cx="55" cy="70.9" r="3" style="fill:var(--c)"/><circle cx="95" cy="51.5" r="3" style="fill:var(--c)"/><circle cx="125" cy="56.7" r="3" style="fill:var(--c)"/><circle cx="180" cy="59.3" r="3" style="fill:var(--c)"/><circle cx="220" cy="42.9" r="3" style="fill:var(--c)"/><circle cx="275" cy="46.9" r="3" style="fill:var(--c)"/><circle cx="305" cy="33.6" r="3" style="fill:var(--c)"/><circle cx="345" cy="38.3" r="3" style="fill:var(--c)"/></svg></div><div class="f" style="--c:#2fd4a7"><i>CER</i><b>Bonos CER</b><p>Tasa real, inflación breakeven contra la tasa fija y el precio de cada bono con tu propia proyección.</p><svg viewBox="0 0 400 90" preserveAspectRatio="none" aria-hidden="true"><path d="M0,80.0 L25,70.2 L50,63.4 L75,58.0 L100,53.5 L125,49.6 L150,46.2 L175,43.0 L200,40.1 L225,37.4 L250,34.9 L275,32.5 L300,30.2 L325,28.1 L350,26.0 L375,23.9 L400,22.0 L400,90 L0,90 Z" style="fill:var(--c);opacity:.10"/><path d="M0,80.0 L25,70.2 L50,63.4 L75,58.0 L100,53.5 L125,49.6 L150,46.2 L175,43.0 L200,40.1 L225,37.4 L250,34.9 L275,32.5 L300,30.2 L325,28.1 L350,26.0 L375,23.9 L400,22.0" fill="none" style="stroke:var(--c)" stroke-width="1.6" stroke-dasharray="4 4" vector-effect="non-scaling-stroke"/><circle cx="45" cy="61.2" r="3" style="fill:var(--c)"/><circle cx="100" cy="60.1" r="3" style="fill:var(--c)"/><circle cx="130" cy="45.2" r="3" style="fill:var(--c)"/><circle cx="170" cy="47.4" r="3" style="fill:var(--c)"/><circle cx="225" cy="30.8" r="3" style="fill:var(--c)"/><circle cx="280" cy="34.7" r="3" style="fill:var(--c)"/><circle cx="295" cy="21.4" r="3" style="fill:var(--c)"/><circle cx="350" cy="26.0" r="3" style="fill:var(--c)"/></svg></div><div class="f" style="--c:#ff8fb3"><i>TAMAR</i><b>Bonos TAMAR</b><p>El margen sobre TAMAR de cada bono y la TAMAR que lo iguala con una Lecap del mismo plazo.</p><svg viewBox="0 0 400 90" preserveAspectRatio="none" aria-hidden="true"><path d="M0,80.0 L25,76.6 L50,73.7 L75,71.1 L100,68.8 L125,66.7 L150,64.7 L175,62.9 L200,61.1 L225,59.5 L250,58.0 L275,56.5 L300,55.1 L325,53.7 L350,52.5 L375,51.2 L400,50.0 L400,90 L0,90 Z" style="fill:var(--c);opacity:.10"/><path d="M0,80.0 L25,76.6 L50,73.7 L75,71.1 L100,68.8 L125,66.7 L150,64.7 L175,62.9 L200,61.1 L225,59.5 L250,58.0 L275,56.5 L300,55.1 L325,53.7 L350,52.5 L375,51.2 L400,50.0" fill="none" style="stroke:var(--c)" stroke-width="1.6" stroke-dasharray="4 4" vector-effect="non-scaling-stroke"/><circle cx="50" cy="67.1" r="3" style="fill:var(--c)"/><circle cx="105" cy="71.0" r="3" style="fill:var(--c)"/><circle cx="120" cy="57.9" r="3" style="fill:var(--c)"/><circle cx="175" cy="62.9" r="3" style="fill:var(--c)"/><circle cx="230" cy="68.3" r="3" style="fill:var(--c)"/><circle cx="270" cy="54.3" r="3" style="fill:var(--c)"/><circle cx="300" cy="61.7" r="3" style="fill:var(--c)"/><circle cx="355" cy="48.1" r="3" style="fill:var(--c)"/></svg></div><div class="f" style="--c:#5cc8ff"><i>Dólar</i><b>Dólar linked y futuros</b><p>Devaluación implícita, futuros de A3, sintéticos, el MEP y el cable de los bonos día por día.</p><svg viewBox="0 0 400 90" preserveAspectRatio="none" aria-hidden="true"><path d="M0,80.0 L25,76.5 L50,73.0 L75,69.5 L100,66.0 L125,62.5 L150,59.0 L175,55.5 L200,52.0 L225,48.5 L250,45.0 L275,41.5 L300,38.0 L325,34.5 L350,31.0 L375,27.5 L400,24.0 L400,90 L0,90 Z" style="fill:var(--c);opacity:.10"/><path d="M0,80.0 L25,76.5 L50,73.0 L75,69.5 L100,66.0 L125,62.5 L150,59.0 L175,55.5 L200,52.0 L225,48.5 L250,45.0 L275,41.5 L300,38.0 L325,34.5 L350,31.0 L375,27.5 L400,24.0" fill="none" style="stroke:var(--c)" stroke-width="1.6" stroke-dasharray="4 4" vector-effect="non-scaling-stroke"/><circle cx="55" cy="81.8" r="3" style="fill:var(--c)"/><circle cx="95" cy="63.8" r="3" style="fill:var(--c)"/><circle cx="125" cy="69.1" r="3" style="fill:var(--c)"/><circle cx="180" cy="51.1" r="3" style="fill:var(--c)"/><circle cx="220" cy="52.9" r="3" style="fill:var(--c)"/><circle cx="275" cy="34.9" r="3" style="fill:var(--c)"/><circle cx="305" cy="40.2" r="3" style="fill:var(--c)"/><circle cx="345" cy="22.2" r="3" style="fill:var(--c)"/></svg></div><div class="f" style="--c:#c9a0ff"><i>Duales</i><b>Duales</b><p>Tasa fija contra TAMAR en un mismo bono: qué pata paga hoy y desde qué tasa conviene cada una.</p><svg viewBox="0 0 400 90" preserveAspectRatio="none" aria-hidden="true"><path d="M0,80.0 L25,74.2 L50,69.5 L75,65.6 L100,62.1 L125,59.0 L150,56.2 L175,53.6 L200,51.2 L225,49.0 L250,46.9 L275,44.8 L300,42.9 L325,41.1 L350,39.3 L375,37.6 L400,36.0 L400,90 L0,90 Z" style="fill:var(--c);opacity:.10"/><path d="M0,80.0 L25,74.2 L50,69.5 L75,65.6 L100,62.1 L125,59.0 L150,56.2 L175,53.6 L200,51.2 L225,49.0 L250,46.9 L275,44.8 L300,42.9 L325,41.1 L350,39.3 L375,37.6 L400,36.0" fill="none" style="stroke:var(--c)" stroke-width="1.6" stroke-dasharray="4 4" vector-effect="non-scaling-stroke"/><circle cx="45" cy="73.9" r="3" style="fill:var(--c)"/><circle cx="100" cy="55.5" r="3" style="fill:var(--c)"/><circle cx="130" cy="61.2" r="3" style="fill:var(--c)"/><circle cx="170" cy="44.8" r="3" style="fill:var(--c)"/><circle cx="225" cy="49.0" r="3" style="fill:var(--c)"/><circle cx="280" cy="53.6" r="3" style="fill:var(--c)"/><circle cx="295" cy="40.7" r="3" style="fill:var(--c)"/><circle cx="350" cy="45.9" r="3" style="fill:var(--c)"/></svg></div></div></div>' +

    '<div class="cat"><h3 class="sh"><span class="dm">' + (NUM[TABS.length] || TABS.length) + ' pantallas,</span> un mismo mercado.</h3><p class="shp">Pasá por cada una para ver qué hay adentro.</p><div class="cg"><div class="ls">' +
    TABS.map(function (t, i) { return '<button data-tab="' + i + '"' + (i ? '' : ' class="on"') + '><i>' + (i < 9 ? '0' : '') + (i + 1) + '</i><b>' + t[0] + '</b><span>' + t[1] + '</span></button>'; }).join('') +
    '</div><figure class="pv" style="margin:0"><img data-pv src="/intro/' + TABS[0][2] + '.webp?v=1" alt="' + TABS[0][0] + '" decoding="async"><figcaption><span data-pvn>01 · ' + TABS[0][0] + '</span><span>captura de la terminal</span></figcaption></figure></div></div>' +

    '<footer><span>© ' + new Date().getFullYear() + ' Bonerío Local. Todos los derechos reservados. <a href="/terminos.html" target="_blank" rel="noopener">Términos</a> · <a href="/privacidad.html" target="_blank" rel="noopener">Privacidad</a></span><span>Herramienta de análisis; no constituye recomendación de inversión.</span></footer></div>';

  var st = document.createElement('style'); st.id = 'blIntroCss'; st.textContent = css; document.head.appendChild(st);

  function build() {
    if (ov) return ov;
    ov = document.createElement('div'); ov.id = 'blIntro'; ov.setAttribute('data-html2canvas-ignore', 'true'); ov.innerHTML = html;
    document.body.insertBefore(ov, document.body.firstChild);
    ov.addEventListener('click', function (e) {
      var t = e.target.closest('[data-login]'); if (t) { e.preventDefault(); openLogin(t.getAttribute('data-login')); return; }
      var k = e.target.closest('[data-cat]'); if (k) { var c = ov.querySelector('.fm'); ov.scrollTo({ top: Math.max(0, c.getBoundingClientRect().top + ov.scrollTop - 20), behavior: 'smooth' }); return; }
      var m = e.target.closest('[data-mode]'); if (m) { mode(m.getAttribute('data-mode')); return; }
      var b = e.target.closest('[data-tab]'); if (b) pick(+b.getAttribute('data-tab'));
    });
    ov.querySelectorAll('[data-tab]').forEach(function (b) { b.addEventListener('mouseenter', function () { if (matchMedia('(hover:hover)').matches) pick(+b.getAttribute('data-tab')); }); });
    ov.querySelector('[data-g]').onclick = google;
    ov.querySelector('[data-f]').onsubmit = function (e) { e.preventDefault(); submit(this.em.value.trim(), this.pw.value); };
    ov.querySelector('[data-eye]').onclick = function () { var i = ov.querySelector('[data-f]').pw, v = i.type === 'password'; i.type = v ? 'text' : 'password'; this.title = v ? 'Ocultar contraseña' : 'Mostrar contraseña'; this.setAttribute('aria-label', this.title); };
    ov.querySelector('[data-go]').onclick = function () { view('forgot'); };
    ov.querySelector('[data-alt]').onclick = function () { if (V === 'reset') { RESET = false; if (user) { view('in'); unlock(); return; } } view(V === 'link' || V === 'forgot' || V === 'reset' ? 'in' : 'link'); };
    view('in');
    TABS.forEach(function (t) { var im = new Image(); im.src = '/intro/' + t[2] + '.webp?v=2'; }); // las capturas quedan listas para el cambio
    market();
    return ov;
  }
  function lock() { build(); ov.style.display = ''; document.documentElement.classList.add('blg'); }
  function unlock() {
    if (ov) ov.style.display = 'none'; document.documentElement.classList.remove('blg');
    try { window.dispatchEvent(new Event('resize')); } catch (e) { }
    chip(); live();
  }
  function er(t) { // errores de Supabase en castellano
    if (/email logins are disabled|provider is not enabled|unsupported provider/i.test(t)) return 'Este modo de ingreso todavía no está habilitado. Probá con el otro o escribinos.';
    if (/signups? not allowed/i.test(t)) return 'Por ahora no estamos sumando cuentas nuevas.';
    if (/invalid login credentials/i.test(t)) return 'Mail o contraseña incorrectos. Si tu cuenta es de Google o entraste con un link, tocá "¿Olvidaste tu contraseña?" para crear una.';
    if (/email not confirmed/i.test(t)) return 'Todavía no confirmaste tu mail: abrí el mail de confirmación que te mandamos (mirá en spam).';
    if (/already registered|already been registered/i.test(t)) return 'Ese mail ya tiene cuenta. Ingresá, o tocá "¿Olvidaste tu contraseña?" si no la recordás.';
    if (/weak|pwned|known to be|easy to guess/i.test(t)) return 'Esa contraseña es muy fácil de adivinar o apareció en filtraciones. Elegí otra.';
    if (/at least (\d+) char/i.test(t)) return 'La contraseña tiene que tener al menos ' + t.match(/at least (\d+)/i)[1] + ' caracteres.';
    if (/should be different|same as/i.test(t)) return 'La contraseña nueva tiene que ser distinta de la anterior.';
    if (/session missing|expired|code verifier|invalid flow|invalid grant/i.test(t)) return 'El link venció o se abrió en otro navegador. Pedí uno nuevo desde este navegador.';
    if (/rate limit|too many|seconds/i.test(t)) return 'Hubo varios intentos seguidos. Esperá un minuto y probá de nuevo.';
    if (/invalid.*email|email.*invalid/i.test(t)) return 'Revisá el mail.';
    if (/error sending|smtp|HTTP 5\d\d|gateway|timeout|timed out/i.test(t)) return 'No pudimos mandar el mail en este momento. Probá de nuevo en unos minutos.';
    if (/fetch|network/i.test(t)) return 'No se pudo conectar con el servicio de cuentas. Probá de nuevo en un rato.';
    return 'No se pudo completar el ingreso (' + t + ').';
  }
  function msg(t, k) { var m = ov.querySelector('[data-m]'); m.textContent = t || ''; m.className = 'msg' + (k ? ' ' + k : ''); }
  function pick(i) {
    ov.querySelectorAll('[data-tab]').forEach(function (b) { b.classList.toggle('on', +b.getAttribute('data-tab') === i); });
    var im = ov.querySelector('[data-pv]'); im.src = '/intro/' + TABS[i][2] + '.webp?v=2'; im.alt = TABS[i][0];
    ov.querySelector('[data-pvn]').textContent = (i < 9 ? '0' : '') + (i + 1) + ' · ' + TABS[i][0];
  }
  function mode(k) { view(k === 'up' ? 'up' : 'in'); }
  // vistas de la tarjeta: in (mail y contraseña), up (crear cuenta), link (link al mail), forgot (pedir link para cambiar la contraseña), reset (elegir la nueva)
  var V = 'in', VW = {
    in: ['Entrá a la terminal', 'Con tu cuenta de Google o con tu mail. Es gratis.', 'Ingresar', 'Prefiero que me manden un link al mail', 'sw g em pw fg'],
    up: ['Creá tu cuenta', 'Gratis. Con Google o con tu mail y una contraseña.', 'Crear cuenta', 'Prefiero que me manden un link al mail', 'sw g em pw'],
    link: ['Entrá con un link', 'Te mandamos un link al mail: lo abrís y entrás, sin contraseña.', 'Mandame el link para entrar', 'Prefiero usar contraseña', 'sw g em'],
    forgot: ['Recuperá tu contraseña', 'Te mandamos un link para elegir una contraseña nueva. Sirve también si tu cuenta es de Google o de link y querés sumarle una.', 'Mandame el link', 'Volver a ingresar', 'em'],
    reset: ['Elegí tu contraseña nueva', 'Es la que vas a usar desde ahora para entrar con tu mail.', 'Guardar y entrar', 'Ahora no, entrar igual', 'pw']
  };
  function view(k) {
    var c = VW[k]; V = k; build();
    ov.querySelectorAll('[data-mode]').forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-mode') === (k === 'up' ? 'up' : 'in')); });
    ov.querySelector('[data-t]').textContent = c[0]; ov.querySelector('[data-s]').textContent = c[1];
    ov.querySelector('[data-sub]').textContent = c[2]; ov.querySelector('[data-alt]').textContent = c[3];
    ov.querySelectorAll('[data-v]').forEach(function (e) { e.hidden = (' ' + c[4] + ' ').indexOf(' ' + e.getAttribute('data-v') + ' ') < 0; });
    var pw = ov.querySelector('[data-f]').pw, nw = k === 'up' || k === 'reset';
    pw.autocomplete = nw ? 'new-password' : 'current-password'; pw.placeholder = nw ? 'Al menos 6 caracteres' : 'Tu contraseña';
    ov.querySelector('[data-pwl]').textContent = k === 'reset' ? 'Contraseña nueva' : 'Contraseña';
    msg('');
  }
  function busy(on) { var b = ov.querySelector('[data-sub]'); b.disabled = on; if (on) msg(V === 'reset' ? 'Guardando…' : V === 'link' || V === 'forgot' ? 'Mandando…' : 'Entrando…'); }
  function submit(em, pw) {
    if (V !== 'reset' && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em)) { msg('Revisá el mail.', 'err'); return; }
    if (V === 'link') { mail(em); return; }
    if (V !== 'forgot' && pw.length < 6) { msg(pw ? 'La contraseña tiene que tener al menos 6 caracteres.' : 'Escribí tu contraseña.', 'err'); return; }
    if (!ON) { unlock(); return; } // vista previa
    if (!sb) { msg('No se pudo conectar con el servicio de cuentas. Probá de nuevo en un rato.', 'err'); return; }
    busy(true);
    if (V === 'forgot') sb.auth.resetPasswordForEmail(em, { redirectTo: back() + '?reset=1' }).then(function (r) {
      busy(false);
      if (r.error) msg(er(r.error.message), 'err');
      else msg('Si ' + em + ' tiene cuenta, te llega un link para elegir la contraseña nueva. Abrilo en este mismo navegador (si no llega, mirá en spam).', 'ok');
    });
    else if (V === 'reset') sb.auth.updateUser({ password: pw }).then(function (r) {
      busy(false);
      if (r.error) { msg(er(r.error.message), 'err'); return; }
      RESET = false; user = r.data.user || user; view('in'); unlock();
    });
    else if (V === 'up') sb.auth.signUp({ email: em, password: pw, options: { emailRedirectTo: back() } }).then(function (r) {
      busy(false);
      if (r.error) { msg(er(r.error.message), 'err'); return; }
      if (r.data.session) return; // sin confirmación por mail: entra directo
      var u = r.data.user; if (u && u.identities && !u.identities.length) { msg('Ese mail ya tiene cuenta. Ingresá, o tocá "¿Olvidaste tu contraseña?" si no la recordás.', 'err'); return; }
      msg('Listo: te mandamos un mail a ' + em + ' para confirmar la cuenta. Abrilo en este mismo navegador y ya entrás (si no llega, mirá en spam).', 'ok');
    });
    else sb.auth.signInWithPassword({ email: em, password: pw }).then(function (r) { busy(false); if (r.error) msg(er(r.error.message), 'err'); else msg(''); });
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
    var RPA = 'https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais', AMB = 'https://mercados.ambito.com//riesgopais/', iso = function (t) { return t.toISOString().slice(0, 10); }, t0 = new Date(Date.now() - 3 * 3600e3);
    Promise.all([q('/data/closes.json'), q('/data/closes_ars.json'), q('/data/indices.json'), q('/data/dolar.json'), q('/data/riesgo_pais.json'), q(RPA), q(RPA + '/ultimo'), q(AMB + 'historico-general/' + iso(new Date(t0 - 20 * 864e5)) + '/' + iso(t0)), q(AMB + 'variacion')]).then(function (R) {
      var cl = R[0], ar = R[1], ix = R[2], dl = R[3], $ = function (k) { return ov.querySelector('[data-k="' + k + '"]'); }, day = '';
      try { // tablero
        var dd = dl && dl.d && last(dl.d, 1)[0], mp = dd && dd[1].mep && dd[1].mep.AL30, pD = cl && cl.D && cl.D[dd && dd[0]], pC = cl && cl.C && cl.C[dd && dd[0]];
        if (mp) { $('mep').textContent = '$ ' + nf(mp.close, 2); day = dd[0]; if (pD && pC && pD.AL30 > 0 && pC.AL30 > 0) $('ccl').textContent = 'Cable $ ' + nf(mp.close * pD.AL30 / pC.AL30, 2) + ' (AL30C)'; } // el cable sale del mismo AL30 en pesos sobre su precio en cable
        var of = last(dl && dl.A3500, 60); if (of.length) { var a = of[of.length - 1][1], b = of.length > 1 ? of[of.length - 2][1] : null; $('ofi').textContent = '$ ' + nf(a, 2); $('ofid').innerHTML = chg(a, b, 2); spark($('ofis'), of.map(function (x) { return x[1]; }), '#e4e4e7'); }
        var tm = last(ix && ix.TAMAR, 40); if (tm.length) { var t1 = tm[tm.length - 1][1], t0 = tm.length > 1 ? tm[tm.length - 2][1] : null; $('tam').textContent = nf(t1, 2) + '%'; $('tamd').innerHTML = chg(t1, t0, 0, 'pb'); spark($('tams'), tm.map(function (x) { return x[1]; }), '#ff8fb3'); }
        var rm = {}; if (R[4] && R[4].d) Object.keys(R[4].d).forEach(function (f) { rm[f] = R[4].d[f]; }); // riesgo país: lo guardado cada noche más lo último de ArgentinaDatos y de Ámbito
        var ad = function (f) { var p = String(f || '').split('-'); return p.length === 3 && p[2].length === 4 ? p[2] + '-' + p[1] + '-' + p[0] : ''; }, an = function (v) { return parseFloat(String(v || '').replace(/\./g, '').replace(',', '.')); }; // Ámbito: las ruedas que ArgentinaDatos todavía no publicó y el dato del día en vivo (ArgentinaDatos lo carga al día siguiente)
        [R[5], R[6]].forEach(function (x) { if (x) (Array.isArray(x) ? x : [x]).forEach(function (r) { var f = String(r && r.fecha || '').slice(0, 10); if (f.length === 10 && r.valor > 0) rm[f] = r.valor; }); });
        if (Array.isArray(R[7])) R[7].forEach(function (r) { var f = ad(r && r[0]), v = an(r && r[1]); if (f && v > 0 && rm[f] == null) rm[f] = v; });
        if (R[8]) { var lf = ad(R[8].fecha), lv = an(R[8].ultimo), wd = lf && new Date(lf + 'T12:00:00Z').getUTCDay(); if (lf && lv > 0 && wd > 0 && wd < 6 && !Object.keys(rm).some(function (f) { return f >= lf; })) rm[lf] = lv; }
        var rp = last(rm, 90); if (rp.length) { var r1 = rp[rp.length - 1][1], r0 = rp.length > 1 ? rp[rp.length - 2][1] : null; $('rp').textContent = nf(r1, 0) + ' pb'; $('rpd').innerHTML = rpc(r1, r0); spark($('rps'), rp.map(function (x) { return x[1]; }), '#b8e986'); RP = [r1, r0]; }
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
    var mk = function () { try { if (typeof window.mktOpen === 'function') { var o = window.mktOpen(); ov.querySelector('[data-dot]').className = o ? 'ok' : 'bad'; ov.querySelector('.st').className = 'st ' + (o ? 'ok' : 'bad'); ov.querySelector('[data-mk]').textContent = o ? 'Mercado abierto' : 'Mercado cerrado'; } } catch (e) { } };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mk); else mk();
  }
  function back() { return location.origin + location.pathname; }
  function google() {
    if (!ON) { unlock(); return; } // vista previa
    if (!sb) { msg('No se pudo conectar con el servicio de cuentas. Probá de nuevo en un rato.', 'err'); return; }
    msg('Abriendo Google…');
    sb.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: back() } }).then(function (r) { if (r.error) msg(er(r.error.message), 'err'); });
  }
  function mail(em) {
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em)) { msg('Revisá el mail.', 'err'); return; }
    if (!ON) { unlock(); return; }
    if (!sb) { msg('No se pudo conectar con el servicio de cuentas. Probá de nuevo en un rato.', 'err'); return; }
    busy(true);
    sb.auth.signInWithOtp({ email: em, options: { emailRedirectTo: back() } }).then(function (r) {
      busy(false);
      if (r.error) msg(/rate|seconds/i.test(r.error.message) ? 'Ya te mandamos un link hace un momento: esperá un minuto antes de pedir otro.' : er(r.error.message), 'err');
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
    var al = document.createElement('button'); al.id = 'alBell'; al.className = 'icon-btn'; al.title = 'Alertas'; al.setAttribute('aria-label', 'Alertas'); al.setAttribute('data-html2canvas-ignore', 'true');
    al.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>';
    al.onclick = function () { if (window.switchTab) window.switchTab('alert'); };
    bar.insertBefore(al, d);
    document.addEventListener('click', function (e) { if (!d.contains(e.target)) d.classList.remove('on'); });
    if (LV.adm) lvBtn();
  }
  // presencia: mientras la página está a la vista, cada sesión avisa cada minuto qué pestaña mira (tabla public.presencia en Supabase).
  // La lectura la limita la base (RLS): cada uno ve solo su fila y el administrador ve todas; a él se le suma «Conectados ahora» en el menú de la cuenta.
  var LV = { t: null, since: new Date().toISOString(), ok: true, adm: false, rt: null };
  function lvTab() { var b = document.querySelector('.tab-btn.active') || document.querySelector('#sideNav .sn-it.on'); return b ? b.textContent.trim() : ''; } // la portada (Inicio) solo está en el menú lateral
  function ping() {
    if (!sb || !user || !LV.ok || document.visibilityState !== 'visible') return;
    var m = user.user_metadata || {};
    sb.from('presencia').upsert({ user_id: user.id, email: user.email || null, nombre: m.full_name || m.name || null, pestana: lvTab(), dispositivo: /iPhone|iPad|Android|Mobile/i.test(navigator.userAgent) ? 'Celular' : 'Compu', desde: LV.since, visto: new Date().toISOString() }, { onConflict: 'user_id' })
      .then(function (r) { // si falla no se apaga: guarda el error (se ve en «Conectados ahora») y vuelve a probar en el próximo aviso
        LV.err = r.error ? (r.error.message || r.error.code || 'error') + ' · ' + new Date().toLocaleTimeString('es-AR') : null; if (r.error) console.warn('presencia', r.error);
        if (!LV.ask) admin(); }, function (e) { LV.err = String(e && e.message || e); if (!LV.ask) admin(); });
  }
  function live() {
    if (!sb || !user || LV.t) return; ping(); LV.t = setInterval(ping, 60000);
    if (!LV.on) { LV.on = 1; document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'visible') ping(); });
      document.addEventListener('click', function (e) { if (e.target && e.target.closest && e.target.closest('.tab-btn') && Date.now() - (LV.lc || 0) > 10000) { LV.lc = Date.now(); setTimeout(ping, 100); } }); } // al cambiar de pestaña, como mucho un aviso cada 10 s
  }
  function admin() { // si la base le deja ver filas de otros, es el administrador (se pregunta una vez por sesión, no en cada aviso)
    LV.ask = 1; sb.from('presencia').select('user_id').neq('user_id', user.id).limit(1).then(function (r) { if (!r.error && r.data && r.data.length) { LV.adm = true; lvBtn(); } }, function () { });
  }
  function lvBtn() {
    var d = document.getElementById('blUser'); if (!d || d.querySelector('[data-live]')) return;
    var b = document.createElement('button'); b.setAttribute('data-live', ''); b.textContent = 'Conectados ahora'; d.querySelector('.mn').insertBefore(b, d.querySelector('[data-out]'));
    b.onclick = function () { d.classList.remove('on'); lvOpen(); };
  }
  function ago(t) { var m = Math.round((Date.now() - new Date(t).getTime()) / 60000); return m < 1 ? 'recién' : m < 60 ? 'hace ' + m + ' min' : m < 1440 ? 'hace ' + Math.floor(m / 60) + ' h ' + (m % 60) + ' min' : new Date(t).toLocaleDateString('es-AR'); }
  function hm(t) { return new Date(t).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' }); }
  function lvOpen() {
    var w = document.getElementById('blLive'); if (!w) { w = document.createElement('div'); w.id = 'blLive'; w.setAttribute('data-html2canvas-ignore', 'true'); document.body.appendChild(w);
      w.addEventListener('click', function (e) { if (e.target === w || (e.target.closest && e.target.closest('.x'))) { w.remove(); clearInterval(LV.rt); } }); }
    w.innerHTML = '<div class="bx"><div class="hd"><h3>Conectados ahora</h3><button class="x" title="Cerrar">×</button></div><div data-b><p class="mu">Cargando…</p></div></div>';
    var load = function () {
      sb.from('presencia').select('email,nombre,pestana,dispositivo,desde,visto').gte('visto', new Date(Date.now() - 864e5).toISOString()).order('visto', { ascending: false }).limit(300).then(function (r) {
        var b = w.querySelector('[data-b]'); if (!b) return; if (r.error) { b.innerHTML = '<p class="mu">No se pudo leer: ' + esc(r.error.message) + '</p>'; return; }
        var now = Date.now(), on = [], day = [];
        (r.data || []).forEach(function (x) { var age = now - new Date(x.visto).getTime(); if (age < 150000) on.push(x); else if (age < 864e5) day.push(x); });
        var who = function (x) { return '<b>' + esc(x.nombre || x.email || '—') + '</b>' + (x.nombre && x.email ? '<div class="mu" style="margin:2px 0 0">' + esc(x.email) + '</div>' : ''); };
        b.innerHTML = '<h4>En este momento: ' + on.length + '</h4>' + (on.length ? '<div class="tw"><table><tr><th>Usuario</th><th>Pestaña</th><th>Equipo</th><th>Entró</th></tr>' + on.map(function (x) { return '<tr><td><span class="dot"></span>' + who(x) + '</td><td>' + esc(x.pestana || '—') + '</td><td>' + esc(x.dispositivo || '') + '</td><td>' + ago(x.desde) + '</td></tr>'; }).join('') + '</table></div>' : '<p class="mu">Nadie más que vos.</p>') +
          '<h4>Últimas 24 horas: ' + day.length + '</h4>' + (day.length ? '<div class="tw"><table><tr><th>Usuario</th><th>Última pestaña</th><th>Equipo</th><th>Visto</th></tr>' + day.map(function (x) { return '<tr><td>' + who(x) + '</td><td>' + esc(x.pestana || '—') + '</td><td>' + esc(x.dispositivo || '') + '</td><td>' + hm(x.visto) + '<div class="mu" style="margin:2px 0 0">' + ago(x.visto) + '</div></td></tr>'; }).join('') + '</table></div>' : '<p class="mu">Nadie.</p>') +
          (LV.err ? '<p class="mu" style="color:#dc2626">Tu conexión no se pudo registrar: ' + esc(LV.err) + '</p>' : '') + '<p class="mu">Cuenta como conectado quien tiene la página a la vista (avisa cada minuto). Se actualiza solo cada 20 segundos.</p>';
      }, function () { });
    };
    load(); clearInterval(LV.rt); LV.rt = setInterval(function () { if (!document.getElementById('blLive')) { clearInterval(LV.rt); return; } load(); }, 20000);
  }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function logout() {
    ['blUser', 'alBell'].forEach(function (i) { var c = document.getElementById(i); if (c) c.remove(); });
    if (sb && user && LV.ok) { try { sb.from('presencia').delete().eq('user_id', user.id).then(function () { }, function () { }); } catch (e) { } }
    user = null; clearInterval(LV.t); LV.t = null;
    if (sb) sb.auth.signOut().then(function () { lock(); }); else lock();
  }

  // para la pestaña Alertas: el cliente de Supabase con la sesión del usuario (sus alertas, sus avisos y el reporte por mail; la base deja tocar solo lo propio)
  window.BLAUTH = function () { return sb && user ? { sb: sb, user: user } : null; };

  // arranque: quien ya entró ve la terminal directo; el resto, la portada
  if (RESET) { lock(); view('reset'); } else if (stored() || returning) document.documentElement.classList.remove('blg'); else lock();
  if (!ON) return;
  var s = document.createElement('script'); s.src = SB_JS; s.async = true;
  s.onload = function () {
    try { sb = window.supabase.createClient(CFG.url, CFG.key, { auth: { flowType: 'pkce', persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } }); } catch (e) { console.error(e); if (!stored()) lock(); return; }
    sb.auth.onAuthStateChange(function (ev, ses) {
      if (ses && /[?&](code|reset)=/.test(location.search)) history.replaceState(null, '', back() + location.hash);
      if (ses && ses.user && (RESET || ev === 'PASSWORD_RECOVERY')) { RESET = true; user = ses.user; lock(); if (V !== 'reset') view('reset'); return; } // primero elige la contraseña nueva
      if (ses && ses.user) { user = ses.user; unlock(); try { document.dispatchEvent(new Event('bl-auth')); } catch (e) { } }
      else if ((ev === 'SIGNED_OUT' || ev === 'INITIAL_SESSION') && !RESET) { user = null; ['blUser', 'alBell'].forEach(function (i) { var c = document.getElementById(i); if (c) c.remove(); }); lock(); }
    });
  };
  s.onerror = function () { if (!stored()) lock(); else unlock(); }; // sin el servicio de cuentas, quien ya había entrado sigue entrando
  document.head.appendChild(s);
})();
