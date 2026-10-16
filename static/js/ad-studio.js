(() => {
  const form = document.querySelector('.admin-form-layout');
  if (!form) return;
  const headline = form.querySelector('[name="headline"]');
  const subheadline = form.querySelector('[name="subheadline"]');
  const body = form.querySelector('[name="body"]');
  const cta = form.querySelector('[name="cta_label"]');
  const variants = form.querySelector('[name="headline_variants"]');
  const style = form.querySelector('[name="style"]');
  const artwork = form.querySelector('[name="ad_image"]');
  const preview = document.getElementById('ad-form-preview');
  const previewHeadline = document.getElementById('preview-headline');
  const previewBody = document.getElementById('preview-body');
  const previewCta = document.getElementById('preview-cta');
  const previewKicker = document.getElementById('preview-kicker');
  const previewImage = document.getElementById('ad-preview-image');
  let rotationTimer = null;
  let rotationIndex = 0;
  let imageObjectUrl = null;

  const listHeadlines = () => {
    const main = headline?.value?.trim() || '';
    const entered = (variants?.value || '').split(/[\n;|]+/).map((x) => x.trim()).filter(Boolean);
    const bodyLine = (body?.value || '').split(/[.!?\n]/)[0].trim().split(/\s+/).slice(0, 8).join(' ');
    const auto = entered.length ? [] : [bodyLine, 'Your next step starts here.'];
    return [...new Set([main, ...entered, ...auto].filter((x) => x && x.toLowerCase() !== main.toLowerCase()))].slice(0, 4).length
      ? [...new Set([main, ...entered, ...auto].filter(Boolean))].slice(0, 4)
      : [main || 'Discover what comes next.'];
  };

  const applyStyle = () => {
    if (!preview || !style) return;
    Array.from(preview.classList).filter((x) => x.startsWith('motion-ad--')).forEach((x) => preview.classList.remove(x));
    preview.classList.add('motion-ad--' + style.value);
  };

  const refreshText = () => {
    if (previewBody && body) previewBody.textContent = body.value || 'Your promotional message will appear here.';
    if (previewCta && cta) previewCta.textContent = cta.value || 'Explore';
    if (previewKicker && subheadline) previewKicker.textContent = subheadline.value || 'LIVE-STYLE PREVIEW · MOTION ENABLED';
    applyStyle();
    startHeadlineRotation();
  };

  const startHeadlineRotation = () => {
    if (rotationTimer) window.clearInterval(rotationTimer);
    rotationTimer = null;
    const titles = listHeadlines();
    if (!previewHeadline || !titles.length) return;
    rotationIndex = 0;
    previewHeadline.textContent = titles[0];
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || titles.length < 2) return;
    rotationTimer = window.setInterval(() => {
      const next = (rotationIndex + 1) % titles.length;
      previewHeadline.classList.add('ad-headline-exit');
      window.setTimeout(() => {
        rotationIndex = next;
        previewHeadline.textContent = titles[rotationIndex];
        previewHeadline.classList.remove('ad-headline-exit');
        previewHeadline.classList.remove('ad-headline-enter');
        void previewHeadline.offsetWidth;
        previewHeadline.classList.add('ad-headline-enter');
      }, 260);
    }, 2600);
  };

  [headline, subheadline, body, cta, variants, style].filter(Boolean).forEach((el) => {
    el.addEventListener('input', refreshText);
    el.addEventListener('change', refreshText);
  });

  if (artwork && previewImage) {
    artwork.addEventListener('change', () => {
      const file = artwork.files?.[0];
      if (!file) {
        if (imageObjectUrl) URL.revokeObjectURL(imageObjectUrl);
        imageObjectUrl = null;
        previewImage.removeAttribute('src');
        previewImage.hidden = true;
        return;
      }
      if (!/^image\/(png|jpeg|webp)$/.test(file.type) || file.size > 8 * 1024 * 1024) {
        artwork.setCustomValidity('Choose a PNG, JPG or WebP image smaller than 8 MB.');
        artwork.reportValidity();
        artwork.value = '';
        return;
      }
      artwork.setCustomValidity('');
      if (imageObjectUrl) URL.revokeObjectURL(imageObjectUrl);
      imageObjectUrl = URL.createObjectURL(file);
      previewImage.src = imageObjectUrl;
      previewImage.hidden = false;
    });
  }

  refreshText();
})();
