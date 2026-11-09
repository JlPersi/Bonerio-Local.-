// El ícono de la extensión muestra u oculta el panel de Bonerío en la pestaña de Matriz.
chrome.action.onClicked.addListener((tab) => chrome.tabs.sendMessage(tab.id, { t: 'toggle' }).catch(() => {}));
