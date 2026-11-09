// El ícono abre Bonerío en el panel lateral de Chrome. El panel flotante de Matriz pide abrirlo en una ficha o una curva.
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
chrome.runtime.onMessage.addListener((m, s) => {
  if (m.t !== 'ir' || !s.tab) return;
  chrome.sidePanel.open({ tabId: s.tab.id }); // va primero, mientras dura el clic del usuario
  chrome.storage.session.set({ ir: m.hash + '&n=' + Date.now() });
});
