/* Portada de presentación y login (Google o link por mail, con Supabase).
   Sin las claves de Supabase no hace nada, salvo con ?intro en la dirección (vista previa: los botones entran directo).
   Va como primer hijo del <body>: la portada se pinta antes que el resto de la página, así no se ve la terminal por un instante. */
(function () {
  var CFG = { url: '', key: '' }; // Supabase → Project Settings → API: Project URL y la clave "anon public"
  var SB_JS = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.0/dist/umd/supabase.js';
  var ON = !!(CFG.url && CFG.key), PREVIEW = /[?&]intro\b/.test(location.search);
  if (!ON && !PREVIEW) return;

  var REF = ON ? ((CFG.url.match(/^https:\/\/([^.]+)\./) || [])[1] || '') : '';
  var sb = null, user = null, ov = null, md = null;
  function stored() { // sesión guardada por supabase-js (para no mostrar la portada a quien ya entró)
    if (!ON) return false;
    try { var s = JSON.parse(localStorage.getItem('sb-' + REF + '-auth-token') || 'null'); return !!(s && s.refresh_token); } catch (e) { return false; }
  }
  var returning = /[?&]code=/.test(location.search); // vuelve del login de Google o del link del mail

  var css = '' +
    'html.blg,html.blg body{overflow:hidden!important}' +
    '#blIntro{position:fixed;inset:0;z-index:2147483000;overflow-y:auto;overflow-x:hidden;background:#0c0a09;color:#fafaf9;font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased;zoom:1}' +
    '#blIntro *{box-sizing:border-box}#blIntro a{color:inherit;text-decoration:none}' +
    '#blIntro .w{max-width:1160px;margin:0 auto;padding:0 28px}' +
    '#blIntro nav{position:sticky;top:0;z-index:5;background:rgba(12,10,9,.82);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid #1c1917}' +
    '#blIntro nav .w{display:flex;align-items:center;gap:28px;height:60px}' +
    '#blIntro .lg{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px;letter-spacing:-.01em}#blIntro .lg img{width:26px;height:26px;border-radius:6px}' +
    '#blIntro .lk{display:flex;gap:22px;font-size:13px;font-weight:500;color:#d6d3d1}#blIntro .lk a:hover{color:#fff}' +
    '#blIntro .sp{flex:1}#blIntro .in{font-size:13px;font-weight:500;color:#e7e5e4;background:none;border:0;cursor:pointer;font-family:inherit}#blIntro .in:hover{color:#fff}' +
    '#blIntro .bt{display:inline-flex;align-items:center;justify-content:center;gap:8px;background:#fafaf9;color:#0c0a09;border:0;border-radius:8px;font:600 13px Inter,system-ui,sans-serif;padding:9px 14px;cursor:pointer;transition:.15s}#blIntro .bt:hover{background:#fff;transform:translateY(-1px)}' +
    '#blIntro .bt.lgb{font-size:15px;padding:13px 20px;border-radius:10px}' +
    '#blIntro h1{font-size:clamp(34px,5.2vw,58px);line-height:1.08;letter-spacing:-.03em;font-weight:600;margin:96px 0 0;max-width:980px}' +
    '#blIntro h2{font-size:clamp(28px,3.6vw,42px);line-height:1.12;letter-spacing:-.025em;font-weight:600;margin:0}' +
    '#blIntro .g{color:#78716c}#blIntro .o{color:#f59e0b}' +
    '#blIntro .cta{display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin-top:34px;font-size:13px;color:#a8a29e}#blIntro .cta b{color:#fafaf9;font-weight:600;cursor:pointer}' +
    '#blIntro .fr{margin-top:56px;padding:22px;border-radius:22px;background:radial-gradient(120% 90% at 50% 0%,#b45309 0%,#78350f 32%,#1c1917 72%);box-shadow:0 30px 80px -30px rgba(245,158,11,.35)}' +
    '#blIntro .fr img{display:block;width:100%;height:auto;border-radius:12px;border:1px solid rgba(255,255,255,.08)}' +
    '#blIntro .cap{margin:16px 0 0;font-size:13px;color:#d6d3d1}' +
    '#blIntro section{padding:110px 0 0}#blIntro .hd{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:40px;align-items:end}' +
    '#blIntro .hd p{margin:0;font-size:14px;line-height:1.6;color:#a8a29e;max-width:380px}' +
    '#blIntro .pair{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:40px}' +
    '#blIntro .sh{margin-top:40px;padding:14px;border-radius:18px;background:#1c1917;border:1px solid #292524}#blIntro .pair .sh{margin-top:0}' +
    '#blIntro .sh img{display:block;width:100%;height:auto;border-radius:10px}' +
    '#blIntro .st{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,2fr);gap:40px}#blIntro .sts{display:grid;grid-template-columns:repeat(3,1fr);gap:28px}' +
    '#blIntro .sts div{font-size:13px;line-height:1.55;color:#a8a29e}#blIntro .sts i{display:block;font-style:normal;color:#57534e;font-size:12px;margin-bottom:10px}#blIntro .sts b{display:block;color:#fafaf9;font-weight:600;margin-bottom:6px;font-size:14px}' +
    '#blIntro details{border-top:1px solid #292524}#blIntro details:last-child{border-bottom:1px solid #292524}' +
    '#blIntro summary{list-style:none;cursor:pointer;padding:18px 0;font-size:14px;font-weight:500;display:flex;justify-content:space-between;gap:16px}#blIntro summary::-webkit-details-marker{display:none}' +
    '#blIntro summary:after{content:"+";color:#78716c;font-size:18px;line-height:1}#blIntro details[open] summary:after{content:"−"}' +
    '#blIntro details p{margin:-4px 0 18px;font-size:14px;line-height:1.6;color:#a8a29e;max-width:640px}' +
    '#blIntro .fin{margin:120px 0 0;padding:64px 28px;text-align:center;border-radius:22px;background:radial-gradient(90% 120% at 50% 100%,#92400e 0%,#1c1917 70%)}#blIntro .fin h2{margin-bottom:26px}' +
    '#blIntro footer{padding:40px 0 48px;font-size:12px;color:#57534e;line-height:1.6}' +
    '#blIntro .md{position:fixed;inset:0;z-index:10;display:none;align-items:center;justify-content:center;padding:20px;background:rgba(0,0,0,.6);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px)}#blIntro .md.on{display:flex}' +
    '#blIntro .bx{position:relative;width:100%;max-width:400px;background:#1c1917;border:1px solid #292524;border-radius:16px;padding:30px 28px 26px;box-shadow:0 30px 80px rgba(0,0,0,.6)}' +
    '#blIntro .bx h3{margin:12px 0 6px;font-size:22px;font-weight:600;letter-spacing:-.02em}#blIntro .bx .sub{margin:0 0 22px;font-size:13px;color:#a8a29e;line-height:1.5}' +
    '#blIntro .x{position:absolute;top:12px;right:12px;width:32px;height:32px;border:0;border-radius:8px;background:none;color:#a8a29e;font-size:20px;cursor:pointer}#blIntro .x:hover{background:#292524;color:#fff}' +
    '#blIntro .gb{width:100%;padding:12px 14px;font-size:14px}#blIntro .gb svg{width:18px;height:18px}' +
    '#blIntro .or{display:flex;align-items:center;gap:12px;margin:18px 0;font-size:12px;color:#78716c}#blIntro .or:before,#blIntro .or:after{content:"";flex:1;height:1px;background:#292524}' +
    '#blIntro input[type=email]{width:100%;padding:12px 14px;border-radius:8px;border:1px solid #44403c;background:#0c0a09;color:#fafaf9;font:14px Inter,system-ui,sans-serif;outline:none}#blIntro input[type=email]:focus{border-color:#f59e0b}' +
    '#blIntro .eb{width:100%;margin-top:10px;padding:12px 14px;font-size:14px;background:#f59e0b;color:#0c0a09}#blIntro .eb:hover{background:#fbbf24}#blIntro .eb[disabled]{opacity:.6;cursor:default;transform:none}' +
    '#blIntro .msg{margin:14px 0 0;font-size:13px;line-height:1.5;color:#d6d3d1;min-height:0}#blIntro .msg.err{color:#fb7185}#blIntro .msg.ok{color:#34d399}' +
    '#blIntro .lgl{margin:18px 0 0;font-size:11px;color:#57534e;line-height:1.5}' +
    '@media(max-width:860px){#blIntro .lk{display:none}#blIntro .hd,#blIntro .st,#blIntro .pair{grid-template-columns:1fr}#blIntro .hd{gap:16px}#blIntro .sts{grid-template-columns:1fr;gap:22px}#blIntro h1{margin-top:56px}#blIntro section{padding-top:80px}#blIntro .fr{padding:10px;border-radius:16px;margin-top:40px}#blIntro .w{padding:0 18px}#blIntro nav .w{gap:14px}#blIntro .fin{margin-top:80px;padding:44px 20px}#blIntro h1{font-size:clamp(28px,8vw,40px)}#blIntro .lg,#blIntro .in,#blIntro nav .bt{white-space:nowrap}#blIntro nav .bt{padding:8px 12px}}' +
    '#blUser{position:relative}#blUser>button{width:40px;height:40px;border-radius:50%;border:1px solid var(--bd);background:var(--card);color:var(--tx);font:700 15px Inter,system-ui,sans-serif;cursor:pointer;display:flex;align-items:center;justify-content:center;overflow:hidden;padding:0}#blUser>button img{width:100%;height:100%;object-fit:cover}' +
    '#blUser .mn{display:none;position:absolute;right:0;top:48px;z-index:100;min-width:220px;background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:8px;box-shadow:0 10px 30px rgba(0,0,0,.35)}#blUser.on .mn{display:block}' +
    '#blUser .mn div{padding:8px 10px;font-size:13px;color:var(--mu);word-break:break-all}#blUser .mn button{width:100%;text-align:left;background:none;border:0;border-radius:6px;padding:9px 10px;color:var(--tx);font:500 14px Inter,system-ui,sans-serif;cursor:pointer}#blUser .mn button:hover{background:var(--bd)}';

  var G = '<svg viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>';

  function shot(src, alt) { return '<div class="sh"><img src="/intro/' + src + '.webp?v=1" alt="' + alt + '" loading="lazy" decoding="async"></div>'; }
  var html = '' +
    '<nav><div class="w"><a class="lg" href="#" data-top><img src="/favicon.svg?v=2" alt="">Bonerío Local</a>' +
    '<div class="lk"><a href="#bl-curvas">Curvas</a><a href="#bl-retornos">Retornos</a><a href="#bl-volumen">Volumen</a><a href="#bl-licitaciones">Licitaciones</a><a href="#bl-arrancar">Cómo arrancar</a><a href="#bl-preguntas">Preguntas</a></div>' +
    '<span class="sp"></span><button class="in" data-login="in">Ingresar</button><button class="bt" data-login="up">Crear cuenta</button></div></nav>' +
    '<div class="w">' +
    '<h1>Bonos argentinos, <span class="o">en una sola pantalla</span>: mirás la curva, ves qué está barato y decidís. <span class="g">Curvas, retornos, volumen y licitaciones, ya calculados y actualizados en cada rueda.</span></h1>' +
    '<div class="cta"><button class="bt lgb" data-login="up">Crear cuenta gratis</button><span>Con Google o con tu mail. <b data-login="in">Ya tengo cuenta</b></span></div>' +
    '<div class="fr"><img src="/intro/hero.webp?v=1" alt="Curva soberana hard dollar en Bonerío Local" fetchpriority="high"></div>' +
    '<p class="cap">Una terminal para toda la renta fija soberana, en dólares y en pesos.</p>' +

    '<section id="bl-curvas"><div class="hd"><h2>Curvas. <span class="g">Qué bono rinde de más, cuál de menos y cuánto.</span></h2>' +
    '<p>Globales y Bonares por TIR y duración, y la curva en pesos con Lecaps, CER, TAMAR, dólar linked y duales. Cada bono contra la curva ajustada, en puntos básicos.</p></div>' +
    '<div class="pair">' + shot('curva-pesos', 'Curva de Lecaps y bonos a tasa fija') + shot('variacion', 'Variación diaria de la curva hard dollar') + '</div></section>' +

    '<section id="bl-retornos"><div class="hd"><h2>Retornos. <span class="g">Cuánto ganás según dónde termine la tasa.</span></h2>' +
    '<p>La tabla de retornos por escenario de TIR, los flujos y el total return de cada bono, y las rotaciones entre bonos que convienen después de costos.</p></div>' +
    '<div class="pair">' + shot('retornos', 'Tabla de retornos por TIR de salida') + shot('rotacion', 'Ranking de rotaciones entre bonos') + '</div></section>' +

    '<section id="bl-volumen"><div class="hd"><h2>Volumen. <span class="g">Dónde se operó y para dónde fue la plata.</span></h2>' +
    '<p>Todas las ruedas desde 2023 guardadas, por bono, por familia y por plazo, con la rueda de hoy en vivo y la lectura de qué lado empujó el precio.</p></div>' +
    shot('volumen', 'Volumen operado por familia y por rueda') + '</section>' +

    '<section id="bl-licitaciones"><div class="hd"><h2>Licitaciones. <span class="g">Cómo salió cada una y qué viene en la próxima.</span></h2>' +
    '<p>El corte de cada instrumento contra el mercado y contra la curva, el rollover, y los bonos del próximo llamado sobre su curva, para ver si vienen baratos o caros.</p></div>' +
    '<div class="pair">' + shot('licitacion-proxima', 'Instrumentos de la próxima licitación sobre su curva') + shot('licitacion-resultado', 'Resultado de la última licitación') + '</div></section>' +

    '<section id="bl-arrancar"><div class="st"><h2>Cómo arrancar. <span class="g">En un minuto.</span></h2><div class="sts">' +
    '<div><i>1</i><b>Creá la cuenta</b>Con Google o con tu mail. No pedimos datos de tu bróker ni de tu cuenta comitente.</div>' +
    '<div><i>2</i><b>Elegí la sección</b>Retornos, curvas, variación diaria, rotación, volumen, dólar o licitaciones: todo arriba, a un clic.</div>' +
    '<div><i>3</i><b>Llevátelo</b>Cualquier gráfico o tabla se descarga en HD o se manda directo por WhatsApp.</div>' +
    '</div></div></section>' +

    '<section id="bl-preguntas"><div class="st"><h2>Preguntas frecuentes. <span class="g">Antes de crear la cuenta.</span></h2><div>' +
    '<details><summary>¿Cuesta algo?</summary><p>No. Crear la cuenta y usar la terminal es gratis.</p></details>' +
    '<details><summary>¿De dónde salen los precios?</summary><p>De los precios de mercado en vivo durante la rueda, y de los cierres de cada día, que guardamos en un historial propio. El CER, la TAMAR y el dólar A3500 salen del BCRA.</p></details>' +
    '<details><summary>¿Opera por mí?</summary><p>No. No se conecta con tu bróker ni toca tu plata: te muestra los números para que decidas vos.</p></details>' +
    '<details><summary>¿Es una recomendación de inversión?</summary><p>No. Es información y cálculo sobre datos de mercado. Las decisiones y sus riesgos son de cada uno.</p></details>' +
    '<details><summary>¿Qué bonos tiene?</summary><p>Globales y Bonares en dólares; Lecaps, Boncaps, CER, TAMAR, dólar linked y duales en pesos; y los Bopreal.</p></details>' +
    '<details><summary>¿Anda en el teléfono?</summary><p>Sí. Toda la terminal se adapta a la pantalla del celular, con las mismas tablas y gráficos.</p></details>' +
    '<details><summary>¿Qué datos me piden?</summary><p>Solo tu mail, o tu cuenta de Google, para entrar.</p></details>' +
    '</div></div></section>' +

    '<div class="fin"><h2>Toda la renta fija argentina. <span class="g">En un solo lugar.</span></h2><button class="bt lgb" data-login="up">Crear cuenta gratis</button></div>' +
    '<footer>Bonerío Local · boneriolocal.com.ar<br>La información es de carácter informativo y no constituye una recomendación de inversión.</footer>' +
    '</div>' +

    '<div class="md" role="dialog" aria-modal="true"><div class="bx"><button class="x" aria-label="Cerrar">×</button>' +
    '<img src="/favicon.svg?v=2" alt="" style="width:34px;height:34px;border-radius:8px"><h3 data-t>Creá tu cuenta</h3><p class="sub" data-s>Gratis, con Google o con tu mail.</p>' +
    '<button class="bt gb" data-g>' + G + 'Continuar con Google</button><div class="or">o con tu mail</div>' +
    '<form data-f><input type="email" required placeholder="tu@mail.com" autocomplete="email"><button class="bt eb" type="submit">Mandame el link para entrar</button></form>' +
    '<p class="msg" data-m></p><p class="lgl">Al entrar aceptás que la información es de carácter informativo y no es una recomendación de inversión.</p></div></div>';

  var st = document.createElement('style'); st.id = 'blIntroCss'; st.textContent = css; document.head.appendChild(st);

  function build() {
    if (ov) return ov;
    ov = document.createElement('div'); ov.id = 'blIntro'; ov.setAttribute('data-html2canvas-ignore', 'true'); ov.innerHTML = html;
    document.body.insertBefore(ov, document.body.firstChild);
    md = ov.querySelector('.md');
    ov.addEventListener('click', function (e) {
      var t = e.target.closest('[data-login]'); if (t) { e.preventDefault(); openLogin(t.getAttribute('data-login')); return; }
      var a = e.target.closest('a[href^="#bl-"],a[data-top]'); if (a) { e.preventDefault(); var id = a.getAttribute('href').slice(1), el = id && document.getElementById(id); ov.scrollTo({ top: el ? el.offsetTop - 70 : 0, behavior: 'smooth' }); return; }
      if (e.target === md || e.target.closest('.x')) closeLogin();
    });
    ov.querySelector('[data-g]').onclick = google;
    ov.querySelector('[data-f]').onsubmit = function (e) { e.preventDefault(); mail(this.querySelector('input').value.trim()); };
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeLogin(); });
    return ov;
  }
  function lock() { build(); ov.style.display = ''; document.documentElement.classList.add('blg'); }
  function unlock() {
    if (ov) ov.style.display = 'none'; document.documentElement.classList.remove('blg');
    try { window.dispatchEvent(new Event('resize')); } catch (e) { }
    chip();
  }
  function msg(t, k) { var m = ov.querySelector('[data-m]'); m.textContent = t || ''; m.className = 'msg' + (k ? ' ' + k : ''); }
  function openLogin(kind) {
    build(); msg('');
    ov.querySelector('[data-t]').textContent = kind === 'in' ? 'Entrá a Bonerío Local' : 'Creá tu cuenta';
    ov.querySelector('[data-s]').textContent = kind === 'in' ? 'Con la misma cuenta de Google o el mismo mail con el que te registraste.' : 'Gratis, con Google o con tu mail.';
    md.classList.add('on'); setTimeout(function () { var i = md.querySelector('input'); if (i && window.innerWidth > 700) i.focus(); }, 50);
  }
  function closeLogin() { if (md) md.classList.remove('on'); }
  function back() { return location.origin + location.pathname; }
  function google() {
    if (!ON) { closeLogin(); unlock(); return; } // vista previa
    if (!sb) { msg('No se pudo conectar con el servicio de cuentas. Probá de nuevo en un rato.', 'err'); return; }
    msg('Abriendo Google…');
    sb.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: back() } }).then(function (r) { if (r.error) msg(r.error.message, 'err'); });
  }
  function mail(em) {
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em)) { msg('Revisá el mail.', 'err'); return; }
    if (!ON) { closeLogin(); unlock(); return; }
    if (!sb) { msg('No se pudo conectar con el servicio de cuentas. Probá de nuevo en un rato.', 'err'); return; }
    var b = md.querySelector('.eb'); b.disabled = true; msg('Mandando…');
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
