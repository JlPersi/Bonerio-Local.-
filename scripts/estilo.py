import re
# Arma estilo.html (prueba de estética) = preview.html + scripts/estilo_dhero.css. Uso: python3 scripts/estilo.py
R='/home/user/Bonerio-Local.-/'
s=open(R+'preview.html',encoding='utf-8').read()
css=open(R+'scripts/estilo_dhero.css',encoding='utf-8').read()
font='<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,600;12..96,700&display=swap" rel="stylesheet">\n'
js="""<script>
(function(){ /* prueba de estética: títulos en dos tonos y etiquetas tipo píldora */
  var h=document.querySelector('h1'); if(h&&h.textContent.indexOf(':')>0){var t=h.textContent.split(':');h.innerHTML='<span class="dim">'+t[0]+':</span>'+t.slice(1).join(':');}
  var two=function(el){ if(!el||el.dataset.two)return; var t=el.textContent.trim(), w=t.split(' '); if(w.length<3)return; var k=Math.ceil(w.length/2); el.dataset.two=1; el.innerHTML='<span class="dim">'+w.slice(0,k).join(' ')+'</span> '+w.slice(k).join(' '); };
  var ey=function(el,txt){ if(!el||el.previousElementSibling&&el.previousElementSibling.className==='eyebrow')return; var e=document.createElement('div'); e.className='eyebrow'; e.textContent=txt; el.parentNode.insertBefore(e,el); };
  var run=function(){ var h2=document.querySelector('#home .hm-hero h2'); if(h2){ ey(h2,'Renta fija argentina'); two(h2);} };
  run(); new MutationObserver(run).observe(document.body,{childList:true,subtree:true});
})();
</script>
"""
s=s.replace('</head>',font+'<style id="dhero">\n'+css+'</style>\n</head>',1)
s=s.replace('</body>',js+'</body>',1)
s=s.replace('<title>','<title>[Prueba estética] ',1)
if '<meta name="robots"' not in s: s=s.replace('<head>','<head>\n<meta name="robots" content="noindex">',1)
open(R+'estilo.html','w',encoding='utf-8').write(s)
print('ok', len(s))
