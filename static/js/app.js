(() => {
  const body = document.body;
  const toggle = document.getElementById('menu-toggle');
  const scrim = document.getElementById('sidebar-scrim');
  const sidebar = document.getElementById('sidebar');

  const closeSidebar = () => {
    body.classList.remove('sidebar-open');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
  };
  if (toggle && sidebar) {
    toggle.addEventListener('click', () => {
      const open = !body.classList.contains('sidebar-open');
      body.classList.toggle('sidebar-open', open);
      toggle.setAttribute('aria-expanded', String(open));
    });
    if (scrim) scrim.addEventListener('click', closeSidebar);
    sidebar.querySelectorAll('a').forEach((link) => link.addEventListener('click', closeSidebar));
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeSidebar();
    });
  }

  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.confirm || 'Are you sure?')) event.preventDefault();
    });
  });

  // Add-to-home-screen support. Do not show an install button unless the browser says
  // installation is available; the browser remains responsible for the install flow.
  let deferredInstallPrompt = null;
  const topbarActions = document.querySelector('.topbar-actions');
  let installButton = null;
  const createInstallButton = () => {
    if (!topbarActions || installButton) return;
    installButton = document.createElement('button');
    installButton.type = 'button';
    installButton.className = 'topbar-link pwa-install-button';
    installButton.textContent = 'Install app ↓';
    installButton.setAttribute('aria-label', 'Install this discovery hub as an app');
    installButton.addEventListener('click', async () => {
      if (!deferredInstallPrompt) return;
      deferredInstallPrompt.prompt();
      try { await deferredInstallPrompt.userChoice; } catch (_) { /* Browser may dismiss the prompt. */ }
      deferredInstallPrompt = null;
      installButton.hidden = true;
    });
    topbarActions.insertBefore(installButton, topbarActions.firstChild);
  };
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    createInstallButton();
    if (installButton) installButton.hidden = false;
  });
  window.addEventListener('appinstalled', () => {
    deferredInstallPrompt = null;
    if (installButton) installButton.hidden = true;
  });

  // Keep public pages available as a light PWA shell. The service worker deliberately
  // does not cache admin pages, searches, tracking redirects, or other sensitive/dynamic paths.
  if ('serviceWorker' in navigator && window.isSecureContext) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/service-worker.js', { scope: '/' }).catch(() => {
        // The site remains usable if a browser or host disallows service workers.
      });
    });
  }
})();
