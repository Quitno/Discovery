(() => {
  const menuButton = document.querySelector('[data-menu-toggle]');
  const nav = document.querySelector('[data-nav]');
  const homesSidebar = document.querySelector('[data-homes-sidebar]');
  const sidebarBackdrop = document.querySelector('[data-sidebar-close]');
  if (menuButton && homesSidebar) {
    const setSidebarOpen = (opened) => {
      homesSidebar.classList.toggle('is-open', opened);
      if (sidebarBackdrop) sidebarBackdrop.hidden = !opened;
      menuButton.setAttribute('aria-expanded', String(opened));
      menuButton.setAttribute('aria-label', opened ? 'Close categories' : 'Open categories');
    };
    menuButton.addEventListener('click', () => {
      if (window.matchMedia('(max-width: 900px)').matches) {
        setSidebarOpen(!homesSidebar.classList.contains('is-open'));
      } else {
        const layout = homesSidebar.closest('.browse-layout');
        const collapsed = layout && layout.classList.toggle('sidebar-collapsed');
        menuButton.setAttribute('aria-expanded', String(!collapsed));
        menuButton.setAttribute('aria-label', collapsed ? 'Show categories' : 'Hide categories');
      }
    });
    if (sidebarBackdrop) sidebarBackdrop.addEventListener('click', () => setSidebarOpen(false));
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && homesSidebar.classList.contains('is-open')) {
        setSidebarOpen(false);
        menuButton.focus();
      }
    });
    homesSidebar.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => setSidebarOpen(false)));
  } else if (menuButton && nav) {
    menuButton.addEventListener('click', () => {
      const opened = nav.classList.toggle('open');
      menuButton.setAttribute('aria-expanded', String(opened));
      menuButton.setAttribute('aria-label', opened ? 'Close menu' : 'Open menu');
    });
    nav.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => {
      nav.classList.remove('open'); menuButton.setAttribute('aria-expanded', 'false');
    }));
  }

  const moreMenuButton = document.querySelector('[data-more-toggle]');
  const moreMenu = document.querySelector('[data-more-menu]');
  if (moreMenuButton && moreMenu) {
    const setMoreMenuOpen = (opened) => {
      moreMenu.hidden = !opened;
      moreMenuButton.setAttribute('aria-expanded', String(opened));
    };
    moreMenuButton.addEventListener('click', () => setMoreMenuOpen(moreMenu.hidden));
    document.addEventListener('click', (event) => {
      if (!moreMenu.hidden && !event.target.closest('.site-header-actions')) setMoreMenuOpen(false);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') setMoreMenuOpen(false);
    });
    moreMenu.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => setMoreMenuOpen(false)));
  }

  const offlineBanner = document.getElementById('offlineBanner');
  const reflectConnection = () => { if (offlineBanner) offlineBanner.hidden = navigator.onLine; };
  window.addEventListener('online', reflectConnection);
  window.addEventListener('offline', reflectConnection);
  reflectConnection();

  if ('serviceWorker' in navigator && location.protocol.startsWith('http')) {
    window.addEventListener('load', () => navigator.serviceWorker.register('/service-worker.js').catch(() => {}));
  }

  let installPrompt = null;
  const installButtons = document.querySelectorAll('[data-install-pwa]');
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault(); installPrompt = event;
    installButtons.forEach((button) => { button.hidden = false; });
  });
  installButtons.forEach((button) => button.addEventListener('click', async () => {
    if (!installPrompt) {
      alert('On Android, open your browser menu and choose “Install app” or “Add to Home screen”.');
      return;
    }
    installPrompt.prompt();
    await installPrompt.userChoice;
    installPrompt = null;
    installButtons.forEach((node) => { node.hidden = true; });
  }));

  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.confirm || 'Continue?')) event.preventDefault();
    });
  });

  const postLocation = async (latitude, longitude) => {
    const response = await fetch('/api/location', {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.APP_CSRF || ''},
      body: JSON.stringify({latitude, longitude, consent: true})
    });
    if (!response.ok) throw new Error('Location could not be saved. Refresh the page and try again.');
    return response.json();
  };

  document.querySelectorAll('[data-location-search]').forEach((button) => {
    button.addEventListener('click', () => {
      const status = document.querySelector('[data-location-status]');
      if (!navigator.geolocation) { if (status) status.textContent = 'This browser does not support device location. Search by area instead.'; return; }
      button.disabled = true; button.textContent = 'Finding location…';
      if (status) status.textContent = 'Your browser will ask permission to use your location.';
      navigator.geolocation.getCurrentPosition(async (position) => {
        try {
          // The visitor has explicitly pressed “Use my location”. Browser permission is the consent gate.
          // Save only the approximate rounded location for the admin's consent-based analytics.
          await postLocation(position.coords.latitude, position.coords.longitude).catch(() => {});
          const url = new URL(window.location.href);
          url.pathname = '/homes';
          url.searchParams.set('lat', position.coords.latitude.toFixed(6));
          url.searchParams.set('lon', position.coords.longitude.toFixed(6));
          if (status) status.textContent = 'Location found. Showing nearby places first…';
          window.location.href = url.toString();
        } catch (error) {
          if (status) status.textContent = error.message || 'Could not use this location. Search by area instead.';
          button.disabled = false; button.textContent = 'Use my location';
        }
      }, (error) => {
        const messages = {1: 'Location permission was denied. Search by area instead.', 2: 'Your location is unavailable. Try again or search by area.', 3: 'Location request timed out. Try again.'};
        if (status) status.textContent = messages[error.code] || 'Location could not be read.';
        button.disabled = false; button.textContent = 'Use my location';
      }, {enableHighAccuracy: false, timeout: 20000, maximumAge: 120000});
    });
  });

  document.querySelectorAll('[data-share-visitor-location]').forEach((button) => {
    button.addEventListener('click', () => {
      const status = button.parentElement && button.parentElement.querySelector('[data-location-status]');
      if (!navigator.geolocation) { if (status) status.textContent = 'This browser does not support device location.'; return; }
      const accepted = window.confirm('Share your approximate location for site analytics? The site stores a rounded area for this visit that authorized administrators can see. Your choice is optional.');
      if (!accepted) { if (status) status.textContent = 'No location shared.'; return; }
      button.disabled = true; button.textContent = 'Finding location…';
      navigator.geolocation.getCurrentPosition(async (position) => {
        try {
          await postLocation(position.coords.latitude, position.coords.longitude);
          if (status) status.textContent = 'Approximate area shared. You can continue using the site.';
          button.textContent = 'Location shared';
        } catch (error) {
          if (status) status.textContent = error.message || 'Could not save location.';
          button.disabled = false; button.textContent = 'Share my approximate location';
        }
      }, (error) => {
        if (status) status.textContent = error.code === 1 ? 'Permission denied. No location was shared.' : 'Could not read location. Try again later.';
        button.disabled = false; button.textContent = 'Share my approximate location';
      }, {enableHighAccuracy: false, timeout: 12000, maximumAge: 60000});
    });
  });

  document.querySelectorAll('[data-directions-panel]').forEach((panel) => {
    const mode = panel.querySelector('[data-route-origin-mode]');
    const originInput = panel.querySelector('[data-route-origin-place]');
    const goButton = panel.querySelector('[data-route-go]');
    const status = panel.querySelector('[data-route-status]');
    const destination = panel.dataset.destination;
    const preview = panel.querySelector('[data-route-map-preview]');
    const frame = panel.querySelector('[data-route-map-frame]');
    const openLink = panel.querySelector('[data-route-open]');
    const syncMode = () => { if (originInput) originInput.hidden = !mode || mode.value !== 'place'; };
    if (mode) { mode.addEventListener('change', syncMode); syncMode(); }
    if (!goButton || !destination) return;

    const showRoute = (origin, originLabel) => {
      const embed = 'https://maps.google.com/maps?saddr=' + encodeURIComponent(origin) + '&daddr=' + encodeURIComponent(destination) + '&output=embed';
      const route = 'https://www.google.com/maps/dir/?api=1&origin=' + encodeURIComponent(origin) + '&destination=' + encodeURIComponent(destination) + '&travelmode=driving';
      if (frame) frame.src = embed;
      if (preview) preview.hidden = false;
      if (openLink) openLink.href = route;
      if (status) status.textContent = 'Route from ' + originLabel + ' to this property. Use the full directions link for turn-by-turn navigation.';
      goButton.disabled = false;
      goButton.textContent = 'Update route';
    };

    goButton.addEventListener('click', () => {
      if (mode && mode.value === 'place') {
        const origin = (originInput && originInput.value || '').trim();
        if (!origin) { if (status) status.textContent = 'Enter a starting place, estate or landmark.'; originInput && originInput.focus(); return; }
        showRoute(origin, origin);
        return;
      }
      if (!navigator.geolocation) { if (status) status.textContent = 'This browser does not support device location. Choose a starting place instead.'; return; }
      goButton.disabled = true; goButton.textContent = 'Finding your location…';
      if (status) status.textContent = 'Allow location access in your browser to draw the route from here.';
      navigator.geolocation.getCurrentPosition((position) => {
        const origin = position.coords.latitude.toFixed(6) + ',' + position.coords.longitude.toFixed(6);
        showRoute(origin, 'your current location');
      }, (error) => {
        if (status) status.textContent = error.code === 1 ? 'Location permission denied. Choose a starting place instead.' : 'Could not read location. Choose a starting place instead.';
        goButton.disabled = false; goButton.textContent = 'Draw route to this place';
      }, {enableHighAccuracy: false, timeout: 20000, maximumAge: 120000});
    });
  });

  document.querySelectorAll('[data-copy-url]').forEach((button) => {
    button.addEventListener('click', async () => {
      const value = button.getAttribute('data-copy-url') || window.location.origin + '/';
      const initialText = button.textContent;
      try {
        await navigator.clipboard.writeText(value);
        button.textContent = 'Link copied';
        button.setAttribute('aria-live', 'polite');
        window.setTimeout(() => { button.textContent = initialText; }, 1800);
      } catch (_) {
        window.prompt('Copy this invite link:', value);
      }
    });
  });

  const propertyLocationButton = document.querySelector('[data-property-location]');
  if (propertyLocationButton) {
    propertyLocationButton.addEventListener('click', () => {
      const status = document.querySelector('[data-property-location-status]');
      if (!navigator.geolocation) { if (status) status.textContent = 'This browser does not support device location.'; return; }
      if (status) status.textContent = 'Use only when physically at the property or setting its known pin. Waiting for permission…';
      propertyLocationButton.disabled = true;
      navigator.geolocation.getCurrentPosition((position) => {
        const lat = document.getElementById('latitudeInput');
        const lon = document.getElementById('longitudeInput');
        if (lat) lat.value = position.coords.latitude.toFixed(6);
        if (lon) lon.value = position.coords.longitude.toFixed(6);
        if (status) status.textContent = 'Coordinates filled. Confirm they point to the actual property before saving.';
        propertyLocationButton.disabled = false;
      }, (error) => {
        if (status) status.textContent = error.code === 1 ? 'Permission denied. You can type known coordinates manually.' : 'Could not read location. Type known coordinates manually.';
        propertyLocationButton.disabled = false;
      }, {enableHighAccuracy: true, timeout: 12000, maximumAge: 10000});
    });
  }


  // On the finder, open a property in an in-page sheet. Only same-origin listing
  // pages are fetched; external property portals are never followed from a card.
  const propertyResults = document.querySelector('.finder-results');
  if (propertyResults) {
    const previewDialog = document.createElement('dialog');
    previewDialog.className = 'property-preview-dialog';
    previewDialog.setAttribute('aria-label', 'Property details');
    previewDialog.innerHTML = `
      <div class="property-preview-frame">
        <div class="property-preview-top"><span class="property-preview-kicker">PROPERTY DETAILS</span><button type="button" class="property-preview-close" aria-label="Close property details" data-preview-close>×</button></div>
        <div class="property-preview-content" data-preview-content><p>Loading property details…</p></div>
      </div>`;
    document.body.appendChild(previewDialog);
    const content = previewDialog.querySelector('[data-preview-content]');
    previewDialog.querySelector('[data-preview-close]').addEventListener('click', () => previewDialog.close());
    previewDialog.addEventListener('click', (event) => {
      if (event.target === previewDialog) previewDialog.close();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && previewDialog.open) previewDialog.close();
    });

    const safeLocalImage = (source) => {
      try {
        const parsed = new URL(source, window.location.origin);
        return parsed.origin === window.location.origin ? parsed.href : '';
      } catch (_) { return ''; }
    };

    const plainTextSection = (title, value) => {
      if (!value) return null;
      const section = document.createElement('section');
      section.className = 'property-preview-section';
      const heading = document.createElement('h3');
      heading.textContent = title;
      const paragraph = document.createElement('p');
      paragraph.textContent = value;
      section.append(heading, paragraph);
      return section;
    };

    const buildPreview = (sourceDoc) => {
      content.replaceChildren();
      const gallery = document.createElement('div');
      gallery.className = 'property-preview-gallery';
      const mainFigure = document.createElement('div');
      mainFigure.className = 'property-preview-main-image';
      const mainImage = sourceDoc.querySelector('.gallery-main img');
      const thumbnails = [...sourceDoc.querySelectorAll('.gallery-thumbs img')];
      const imageSources = [mainImage, ...thumbnails].filter(Boolean)
        .map((image) => safeLocalImage(image.getAttribute('src'))).filter(Boolean)
        .filter((source, index, all) => all.indexOf(source) === index);
      if (imageSources.length) {
        const hero = document.createElement('img');
        hero.src = imageSources[0];
        hero.alt = 'Property photograph';
        hero.loading = 'eager';
        mainFigure.appendChild(hero);
        gallery.appendChild(mainFigure);
        if (imageSources.length > 1) {
          const rail = document.createElement('div');
          rail.className = 'property-preview-thumbnails';
          imageSources.forEach((source, index) => {
            const thumb = document.createElement('button');
            thumb.type = 'button';
            thumb.className = 'property-preview-thumb' + (index === 0 ? ' is-active' : '');
            thumb.setAttribute('aria-label', `View property photo ${index + 1}`);
            const image = document.createElement('img');
            image.src = source; image.alt = ''; image.loading = 'lazy';
            thumb.appendChild(image);
            thumb.addEventListener('click', () => {
              hero.src = source;
              rail.querySelectorAll('button').forEach((button) => button.classList.remove('is-active'));
              thumb.classList.add('is-active');
            });
            rail.appendChild(thumb);
          });
          gallery.appendChild(rail);
        }
      } else {
        const noPhoto = document.createElement('div');
        noPhoto.className = 'property-preview-no-photo';
        noPhoto.textContent = 'No property photographs available';
        gallery.appendChild(noPhoto);
      }
      content.appendChild(gallery);

      const detailHeading = sourceDoc.querySelector('.detail-heading');
      if (detailHeading) {
        const titleLine = document.createElement('div');
        titleLine.className = 'property-preview-title-line';
        const title = document.createElement('h2');
        title.textContent = detailHeading.querySelector('h1')?.textContent.trim() || 'Property';
        const price = detailHeading.querySelector('.detail-price');
        titleLine.appendChild(title);
        if (price) {
          const priceNode = document.createElement('div');
          priceNode.className = 'property-preview-price';
          priceNode.textContent = price.innerText.replace(/\s+/g, ' ').trim();
          titleLine.appendChild(priceNode);
        }
        content.appendChild(titleLine);
        const location = detailHeading.querySelector('.detail-location');
        if (location && location.textContent.trim()) {
          const area = document.createElement('p');
          area.className = 'property-preview-location';
          area.textContent = location.textContent.replace(/\s+/g, ' ').trim();
          content.appendChild(area);
        }
      }

      const facts = sourceDoc.querySelector('.facts-grid');
      if (facts) {
        const clone = facts.cloneNode(true);
        clone.classList.add('property-preview-facts');
        content.appendChild(clone);
      }

      const allowedSections = new Set(['About this place', 'Condition', 'Water supply', 'Amenities and other details']);
      sourceDoc.querySelectorAll('.detail-section').forEach((section) => {
        const label = section.querySelector('h2')?.textContent.trim() || '';
        if (!allowedSections.has(label)) return;
        const paragraph = section.querySelector('p');
        const built = plainTextSection(label, paragraph?.textContent.trim() || '');
        if (built) content.appendChild(built);
      });

      const partnerPhone = sourceDoc.querySelector('.property-contact-number a[href^="tel:"]');
      if (partnerPhone) {
        const contact = document.createElement('section');
        contact.className = 'property-preview-contact';
        const title = document.createElement('h3'); title.textContent = 'Contact owner or agent';
        const number = document.createElement('a');
        number.href = partnerPhone.getAttribute('href');
        number.textContent = partnerPhone.textContent.trim();
        number.className = 'property-preview-phone';
        contact.append(title, number);
        content.appendChild(contact);
      }
    };

    let previewRequest = 0;
    const openPropertyPreview = async (href) => {
      const target = new URL(href, window.location.origin);
      if (target.origin !== window.location.origin || !target.pathname.startsWith('/listing/')) return;
      const requestId = ++previewRequest;
      content.innerHTML = '<p class="property-preview-loading">Loading property details…</p>';
      if (typeof previewDialog.showModal === 'function' && !previewDialog.open) previewDialog.showModal();
      else if (!previewDialog.open) { window.location.href = target.href; return; }
      try {
        const response = await fetch(target.href, {credentials: 'same-origin', cache: 'no-store', headers: {'X-PataMahali-Preview': '1'}});
        if (!response.ok) throw new Error('Could not load property details.');
        const html = await response.text();
        if (requestId !== previewRequest || !previewDialog.open) return;
        const parsed = new DOMParser().parseFromString(html, 'text/html');
        if (!parsed.querySelector('.detail-layout')) throw new Error('Property page was not available.');
        buildPreview(parsed);
      } catch (_) {
        if (previewDialog.open && requestId === previewRequest) {
          content.replaceChildren();
          const error = document.createElement('p');
          error.className = 'property-preview-loading';
          error.textContent = 'Details could not be loaded.';
          const retryLink = document.createElement('a');
          retryLink.href = target.pathname + target.search;
          retryLink.textContent = ' Open property details on this site.';
          error.appendChild(retryLink);
          content.appendChild(error);
        }
      }
    };

    propertyResults.addEventListener('click', (event) => {
      const link = event.target.closest('a[data-property-preview]');
      if (!link || !propertyResults.contains(link)) return;
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const target = new URL(link.href, window.location.origin);
      if (target.origin !== window.location.origin || !target.pathname.startsWith('/listing/')) return;
      event.preventDefault();
      openPropertyPreview(target.href);
    });
  }



  // Filter the full county directory by counties, constituencies, wards and common local names.
  const countyFilter = document.querySelector('[data-county-filter]');
  const countyCards = Array.from(document.querySelectorAll('[data-county-card]'));
  const countyCount = document.querySelector('[data-county-result-count]');
  const countyEmpty = document.querySelector('[data-county-empty]');
  if (countyFilter && countyCards.length) {
    const applyCountyFilter = () => {
      const query = (countyFilter.value || '').trim().toLocaleLowerCase();
      let visible = 0;
      countyCards.forEach((card) => {
        const haystack = (card.getAttribute('data-search-text') || card.textContent || '').toLocaleLowerCase();
        const show = !query || haystack.includes(query);
        card.hidden = !show;
        if (show) visible += 1;
      });
      if (countyCount) countyCount.textContent = query ? `${visible} matching county${visible === 1 ? '' : 'ies'}` : `${countyCards.length} counties`;
      if (countyEmpty) countyEmpty.hidden = visible > 0;
    };
    countyFilter.addEventListener('input', applyCountyFilter);
    applyCountyFilter();
  }



  // Narrow each county/constituency page without forcing visitors through a long list.
  const placeFilter = document.querySelector('[data-place-filter]');
  const placeCards = Array.from(document.querySelectorAll('[data-place-card]'));
  const placeResultCount = document.querySelector('[data-place-result-count]');
  if (placeFilter && placeCards.length) {
    const applyPlaceFilter = () => {
      const query = (placeFilter.value || '').trim().toLocaleLowerCase();
      let visible = 0;
      placeCards.forEach((card) => {
        const haystack = (card.getAttribute('data-search-text') || card.textContent || '').toLocaleLowerCase();
        const show = !query || haystack.includes(query);
        card.hidden = !show;
        if (show) visible += 1;
      });
      document.querySelectorAll('[data-place-group]').forEach((group) => {
        group.hidden = !group.querySelector('[data-place-card]:not([hidden])');
      });
      document.querySelectorAll('[data-place-section]').forEach((section) => {
        section.hidden = !section.querySelector('[data-place-card]:not([hidden])');
      });
      if (placeResultCount) placeResultCount.textContent = `${visible} matching option${visible === 1 ? '' : 's'}`;
    };
    placeFilter.addEventListener('input', applyPlaceFilter);
    applyPlaceFilter();
  }

})();


// Gentle count-up animation to the real recorded value; never invents extra visitors.
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-count-up]').forEach((node) => {
    const target = Number.parseInt(node.getAttribute('data-count-up') || '0', 10);
    if (!Number.isFinite(target) || target < 1 || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const duration = Math.min(1800, Math.max(500, target * 2));
    const start = performance.now();
    const formatter = new Intl.NumberFormat();
    const tick = (now) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      node.textContent = formatter.format(Math.round(target * eased));
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
});


// Mobile-friendly Toror platform carousel: automatic, but pauses for touch, hover and keyboard use.
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-network-carousel]').forEach((carousel) => {
    const track = carousel.querySelector('[data-network-track]');
    const previous = carousel.querySelector('[data-network-prev]');
    const next = carousel.querySelector('[data-network-next]');
    if (!track || track.children.length < 2) return;

    const gapSize = () => {
      const styles = window.getComputedStyle(track);
      return Number.parseFloat(styles.columnGap || styles.gap || '0') || 0;
    };
    const stepSize = () => {
      const card = track.querySelector('.pm-network-card');
      return card ? card.getBoundingClientRect().width + gapSize() : track.clientWidth;
    };
    const move = (direction) => {
      const step = Math.max(180, stepSize());
      const end = Math.max(0, track.scrollWidth - track.clientWidth);
      if (direction > 0 && track.scrollLeft >= end - 12) {
        track.scrollTo({left: 0, behavior: 'smooth'});
      } else if (direction < 0 && track.scrollLeft <= 12) {
        track.scrollTo({left: end, behavior: 'smooth'});
      } else {
        track.scrollBy({left: direction * step, behavior: 'smooth'});
      }
    };
    previous?.addEventListener('click', () => move(-1));
    next?.addEventListener('click', () => move(1));

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let timer = 0;
    let resumeTimer = 0;
    const stop = () => {
      if (timer) window.clearInterval(timer);
      timer = 0;
      if (resumeTimer) window.clearTimeout(resumeTimer);
      resumeTimer = 0;
    };
    const start = () => {
      if (reduceMotion || timer || track.scrollWidth <= track.clientWidth + 8) return;
      timer = window.setInterval(() => move(1), 4400);
    };
    const pauseBriefly = () => {
      stop();
      if (!reduceMotion) resumeTimer = window.setTimeout(start, 9000);
    };
    carousel.addEventListener('mouseenter', stop);
    carousel.addEventListener('mouseleave', start);
    carousel.addEventListener('focusin', stop);
    carousel.addEventListener('focusout', start);
    track.addEventListener('touchstart', pauseBriefly, {passive: true});
    track.addEventListener('pointerdown', pauseBriefly);
    window.addEventListener('resize', () => {
      if (track.scrollWidth <= track.clientWidth + 8) stop();
      else start();
    }, {passive: true});
    start();
  });

  // Preview selected property photographs and explain the cover-photo order before upload.
  document.querySelectorAll('[data-listing-photo-input]').forEach((input) => {
    const preview = document.querySelector('[data-listing-photo-preview]');
    const grid = document.querySelector('[data-listing-photo-preview-grid]');
    const status = document.querySelector('[data-listing-photo-status]');
    if (!preview || !grid) return;
    const maxImages = Number(input.dataset.maxImages || 12);
    const originalCount = Number(input.dataset.existingCount || 0);
    const updateSelection = () => {
      const files = Array.from(input.files || []).filter((file) => file && file.type.startsWith('image/'));
      const removed = document.querySelectorAll('input[name="remove_images"]:checked').length;
      const currentCount = Math.max(0, originalCount - removed);
      const allowed = Math.max(0, maxImages - currentCount);
      const invalid = files.length > allowed;
      input.setCustomValidity(invalid ? `This property can have ${maxImages} photos in total. ${allowed} new photo${allowed === 1 ? '' : 's'} can still be added.` : '');
      if (status) status.textContent = invalid
        ? `Too many selected: ${currentCount} saved + ${files.length} new. Select no more than ${allowed} new photo${allowed === 1 ? '' : 's'}.`
        : files.length ? `${currentCount + files.length} of ${maxImages} photos selected. ${currentCount ? 'New photos will follow the saved photos.' : 'The first selected photo will be the cover.'}` : '';
      grid.replaceChildren();
      if (!files.length) { preview.hidden = true; return; }
      preview.hidden = false;
      files.forEach((file, index) => {
        const card = document.createElement('figure');
        card.className = 'listing-photo-preview-item';
        const image = document.createElement('img');
        const objectUrl = URL.createObjectURL(file);
        image.src = objectUrl;
        image.alt = `Selected property photo ${index + 1}`;
        image.onload = () => URL.revokeObjectURL(objectUrl);
        const badge = document.createElement('figcaption');
        badge.textContent = currentCount === 0 && index === 0 ? 'COVER PHOTO' : `PHOTO ${currentCount + index + 1}`;
        card.append(image, badge);
        grid.appendChild(card);
      });
    };
    input.addEventListener('change', updateSelection);
    document.querySelectorAll('input[name="remove_images"]').forEach((checkbox) => checkbox.addEventListener('change', updateSelection));
    updateSelection();
  });

  // Property detail viewer: the first uploaded photo is the cover; the rest open in one gallery.
  document.querySelectorAll('[data-property-gallery]').forEach((gallery) => {
    const dialog = gallery.querySelector('[data-property-gallery-dialog]');
    const mainLink = gallery.querySelector('[data-gallery-open]');
    const mainImage = mainLink?.querySelector('img');
    const viewerImage = dialog?.querySelector('[data-gallery-current-image]');
    const caption = dialog?.querySelector('[data-gallery-dialog-caption]');
    const thumbs = Array.from(gallery.querySelectorAll('[data-gallery-thumb]'));
    const photos = thumbs.map((thumb) => ({
      src: thumb.dataset.gallerySrc,
      alt: thumb.dataset.galleryAlt || 'Property photograph'
    })).filter((photo) => photo.src);
    if (!dialog || !mainLink || !mainImage || !viewerImage || !photos.length) return;
    let activeIndex = 0;
    const selectPhoto = (index) => {
      activeIndex = (index + photos.length) % photos.length;
      const selected = photos[activeIndex];
      mainImage.src = selected.src;
      mainImage.alt = selected.alt;
      mainLink.href = selected.src;
      mainLink.dataset.galleryIndex = String(activeIndex);
      viewerImage.src = selected.src;
      viewerImage.alt = selected.alt;
      if (caption) caption.textContent = `Photo ${activeIndex + 1} of ${photos.length}`;
      thumbs.forEach((thumb, thumbIndex) => {
        const active = thumbIndex === activeIndex;
        thumb.classList.toggle('is-active', active);
        thumb.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
    };
    const openAt = (index) => {
      selectPhoto(index);
      if (typeof dialog.showModal === 'function' && !dialog.open) dialog.showModal();
      else if (!dialog.open) window.open(photos[activeIndex].src, '_blank', 'noopener');
    };
    mainLink.addEventListener('click', (event) => { event.preventDefault(); openAt(Number(mainLink.dataset.galleryIndex || 0)); });
    thumbs.forEach((thumb, index) => thumb.addEventListener('click', () => openAt(index)));
    dialog.querySelector('[data-gallery-close]')?.addEventListener('click', () => dialog.close());
    dialog.querySelector('[data-gallery-prev]')?.addEventListener('click', () => selectPhoto(activeIndex - 1));
    dialog.querySelector('[data-gallery-next]')?.addEventListener('click', () => selectPhoto(activeIndex + 1));
    dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowLeft') { event.preventDefault(); selectPhoto(activeIndex - 1); }
      if (event.key === 'ArrowRight') { event.preventDefault(); selectPhoto(activeIndex + 1); }
    });
    selectPhoto(0);
  });
});
