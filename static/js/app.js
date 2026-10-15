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


  // Public gateway sharing controls. Kept in the local script so the site's CSP can remain strict.
  const shareFeedback = document.getElementById('share-feedback');
  const shareHubButton = document.getElementById('share-hub-button');
  const copyHubButton = document.getElementById('copy-hub-button');
  const copyHubUrl = async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(window.location.href);
        if (shareFeedback) shareFeedback.textContent = 'Website link copied.';
      } else if (shareFeedback) shareFeedback.textContent = window.location.href;
    } catch (_) {
      if (shareFeedback) shareFeedback.textContent = window.location.href;
    }
  };
  if (shareHubButton) {
    shareHubButton.addEventListener('click', async () => {
      const data = { title: document.title, text: 'Explore this gateway to connected websites and digital services.', url: window.location.href };
      try {
        if (navigator.share) await navigator.share(data);
        else await copyHubUrl();
      } catch (error) {
        if (error && error.name !== 'AbortError' && shareFeedback) shareFeedback.textContent = 'Copy the website link to share this gateway.';
      }
    });
  }
  if (copyHubButton) copyHubButton.addEventListener('click', copyHubUrl);

  // Transparent, indicative project estimate; the server recalculates the same range on submission.
  const projectForm = document.getElementById('project-form');
  const estimateAmount = document.getElementById('estimate-amount');
  if (projectForm && estimateAmount) {
    const base = {
      'business-website': [10000, 20000], 'online-store': [25000, 60000], 'web-app': [50000, 120000],
      'mobile-app': [60000, 150000], 'redesign': [8000, 22000], 'automation': [15000, 45000],
      'seo': [5000, 20000], 'other': [12000, 45000]
    };
    const pages = { '1-5': [0, 0], '6-10': [5000, 9000], '11-20': [12000, 22000], '21+': [25000, 50000] };
    const features = { simple: [0, 0], standard: [5000, 15000], advanced: [15000, 40000] };
    const content = { ready: [0, 0], 'need-help': [3000, 10000], 'full-service': [6000, 18000] };
    const timing = { flexible: [1, 1], month: [1, 1.08], 'two-weeks': [1.08, 1.15], 'one-week': [1.18, 1.30] };
    const money = (n) => 'KSh ' + Math.round(n).toLocaleString('en-KE');
    const updateEstimate = () => {
      const data = new FormData(projectForm);
      let lowHigh = base[data.get('project_type')] || base.other;
      let add = pages[data.get('pages_count')] || pages['1-5']; lowHigh = [lowHigh[0] + add[0], lowHigh[1] + add[1]];
      add = features[data.get('feature_level')] || features.standard; lowHigh = [lowHigh[0] + add[0], lowHigh[1] + add[1]];
      add = content[data.get('content_status')] || content['need-help']; lowHigh = [lowHigh[0] + add[0], lowHigh[1] + add[1]];
      const factors = timing[data.get('timeline')] || timing.flexible;
      const round500 = (n) => Math.round(n / 500) * 500;
      estimateAmount.textContent = money(round500(lowHigh[0] * factors[0])) + ' – ' + money(round500(lowHigh[1] * factors[1]));
      const caption = document.getElementById('estimate-caption');
      if (caption) caption.textContent = data.get('timeline') === 'one-week'
        ? 'This range includes a planning allowance for the urgent timeline.'
        : 'Indicative estimate updated from the selected project type, scale, features and content support.';
    };
    projectForm.addEventListener('change', updateEstimate);
    updateEstimate();
  }
  // Optional, visitor-initiated ambient sound for the motion advert. Audio never autoplays.
  document.querySelectorAll('[data-ambient-toggle]').forEach((button) => {
    let audioContext = null;
    let master = null;
    let oscillators = [];
    let running = false;
    const start = () => {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return false;
      audioContext = audioContext || new Ctx();
      if (audioContext.state === 'suspended') audioContext.resume();
      master = audioContext.createGain();
      master.gain.value = 0.018;
      master.connect(audioContext.destination);
      [130.81, 164.81, 196.00].forEach((frequency, index) => {
        const oscillator = audioContext.createOscillator();
        const gain = audioContext.createGain();
        oscillator.type = 'sine';
        oscillator.frequency.value = frequency;
        gain.gain.value = index === 0 ? 0.50 : 0.24;
        oscillator.connect(gain); gain.connect(master); oscillator.start(); oscillators.push(oscillator);
      });
      running = true; button.setAttribute('aria-pressed', 'true'); button.innerHTML = '<span aria-hidden="true">♫</span> Soft sound on';
      return true;
    };
    const stop = () => {
      if (master && audioContext) { try { master.gain.setTargetAtTime(0, audioContext.currentTime, 0.15); } catch (_) {} }
      oscillators.forEach((oscillator) => { try { oscillator.stop(audioContext.currentTime + 0.4); } catch (_) {} });
      oscillators = []; master = null; running = false; button.setAttribute('aria-pressed', 'false'); button.innerHTML = '<span aria-hidden="true">♫</span> Soft sound off';
    };
    button.addEventListener('click', () => {
      if (running) stop(); else if (!start()) { button.textContent = 'Sound unavailable'; }
    });
    window.addEventListener('pagehide', () => { if (audioContext) audioContext.close().catch(() => {}); });
  });

})();
