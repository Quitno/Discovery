(() => {
  const form = document.querySelector('.admin-form-layout');
  if (!form) return;
  const headline = form.querySelector('[name="headline"]');
  const body = form.querySelector('[name="body"]');
  const cta = form.querySelector('[name="cta_label"]');
  const style = form.querySelector('[name="style"]');
  const preview = document.getElementById('ad-form-preview');
  const show = () => {
    const h = document.getElementById('preview-headline');
    const b = document.getElementById('preview-body');
    const c = document.getElementById('preview-cta');
    if (h && headline) h.textContent = headline.value || 'Your headline will appear here.';
    if (b && body) b.textContent = body.value || 'Your promotional message will appear here.';
    if (c && cta) c.textContent = cta.value || 'Explore';
    if (preview && style) {
      Array.from(preview.classList).filter((x) => x.startsWith('motion-ad--')).forEach((x) => preview.classList.remove(x));
      preview.classList.add('motion-ad--' + style.value);
    }
  };
  [headline, body, cta, style].filter(Boolean).forEach((el) => el.addEventListener('input', show));
  show();
})();
