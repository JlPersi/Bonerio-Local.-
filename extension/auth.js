// En boneriolocal.com.ar: copia la sesión de Bonerío al almacenamiento de la extensión, así la ventana de Matriz entra con la misma cuenta
// (adentro de Matriz la página es un iframe de otro sitio: Chrome le da otro localStorage y Google no deja iniciar sesión en un iframe).
(() => {
  const leer = () => { try { for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); if (/^sb-[\w-]+-auth-token$/.test(k)) return { k, v: localStorage.getItem(k) }; } } catch (e) { } return null; };
  let ult = '';
  const sync = () => { const s = leer(), j = JSON.stringify(s); if (j === ult) return; ult = j; try { chrome.storage.local.set({ bnrTok: s }); } catch (e) { } };
  sync(); setInterval(sync, 3000); addEventListener('storage', sync);
})();
