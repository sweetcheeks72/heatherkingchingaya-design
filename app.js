(() => {
  'use strict';
  const root = document.documentElement;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');
  const entrance = document.querySelector('#entrance');
  const main = document.querySelector('#main');
  const footer = document.querySelector('#site-footer');
  const plan = document.querySelector('.enter-plan');
  const entryLinks = [plan].filter(Boolean);
  const cursor = document.querySelector('.enter-cursor');
  let entering = false;
  let entryTimer;
  root.classList.add('js-ready');

  // Discreet oval "Enter" cursor over the plan. It is aria-hidden decoration with no pointer
  // events; the plan is the entrance link. It is used only with a fine, hovering pointer
  // and when motion is allowed, and the native cursor is hidden only while this one is
  // actually shown (.cursor-live on the entrance).
  const cursorAllowed = () => !!cursor && finePointer.matches && !reduced.matches && !entering && !entrance.hidden;
  function hideCursor() {
    entrance.classList.remove('cursor-live');
  }
  function moveCursor(event) {
    if (event.pointerType !== 'mouse' || !cursorAllowed()) { hideCursor(); return; }
    const box = entrance.getBoundingClientRect();
    cursor.style.transform = `translate3d(${Math.round(event.clientX - box.left)}px, ${Math.round(event.clientY - box.top)}px, 0)`;
    entrance.classList.add('cursor-live');
  }
  plan.addEventListener('pointerenter', moveCursor);
  plan.addEventListener('pointermove', moveCursor);
  plan.addEventListener('pointerleave', hideCursor);
  plan.addEventListener('pointercancel', hideCursor);
  window.addEventListener('blur', hideCursor);
  finePointer.addEventListener('change', () => { if (!finePointer.matches) hideCursor(); });

  function syncMotion() {
    root.classList.toggle('motion-ready', !reduced.matches);
    if (reduced.matches) hideCursor();
  }
  syncMotion();
  reduced.addEventListener('change', syncMotion);
  // Hidden page: CSS pauses every running animation (.document-hidden), resuming in place when the page returns.
  const syncHidden = () => root.classList.toggle('document-hidden', document.hidden);
  syncHidden();
  document.addEventListener('visibilitychange', syncHidden);

  // Install entry handlers before hiding content. Without JS the plan is a normal
  // anchor and the header and complete website remain readable below the entrance.
  // Entrance state (.entry-active on <html>, .is-entrance on <body>): only the floor
  // plan is shown and the header is hidden. It is only ever set by this script.
  const setEntryState = (on) => {
    root.classList.toggle('entry-active', on);
    document.body.classList.toggle('is-entrance', on);
  };
  const inEntry = () => root.classList.contains('entry-active') && !entering;
  const isEntryHash = (hash) => !hash || hash === '#top' || hash === '#entrance';
  function showSite(target = '#main', animated = false) {
    hideCursor();
    const finish = () => {
      clearTimeout(entryTimer);
      main.hidden = false; footer.hidden = false; entrance.hidden = true;
      setEntryState(false); root.classList.remove('entering'); entering = false;
      const destination = document.getElementById(target.slice(1)) || main;
      destination.setAttribute('tabindex', '-1');
      destination.focus({ preventScroll: true });
      destination.scrollIntoView({ behavior: 'instant', block: 'start' });
    };
    // The short zoom/fade runs only when motion is allowed (CSS gates it on .motion-ready).
    if (animated && root.classList.contains('motion-ready') && !reduced.matches) {
      entering = true; root.classList.add('entering'); entryTimer = setTimeout(finish, 550);
    } else finish();
  }
  entryLinks.forEach((link) => link.addEventListener('click', (event) => {
    event.preventDefault(); if (!entering) showSite('#main', true);
  }));
  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    if (entryLinks.includes(link)) return;
    link.addEventListener('click', (event) => {
      const target = link.getAttribute('href');
      if (main.hidden && target !== '#top') { event.preventDefault(); showSite(target); }
    });
  });
  window.addEventListener('hashchange', () => {
    if (main.hidden && !isEntryHash(location.hash)) showSite(location.hash);
  });
  // Leaving the entrance by intent: tabbing past the plan, scrolling down with a
  // wheel or touch swipe, or the usual scroll keys all enter the site.
  document.addEventListener('keydown', (event) => {
    if (!inEntry() || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === 'Tab') {
      if (!event.shiftKey && document.activeElement === plan) { event.preventDefault(); showSite('#main', true); }
      return;
    }
    if (['PageDown', 'ArrowDown', 'End', ' '].includes(event.key) && !event.target.closest?.('button, input, textarea, select')) {
      event.preventDefault(); showSite('#main', true);
    }
  });
  window.addEventListener('wheel', (event) => { if (inEntry() && event.deltaY > 0) showSite('#main', true); }, { passive: true });
  let touchStartY = null;
  window.addEventListener('touchstart', (event) => { touchStartY = event.touches[0] ? event.touches[0].clientY : null; }, { passive: true });
  window.addEventListener('touchmove', (event) => {
    if (!inEntry() || touchStartY === null || !event.touches[0]) return;
    if (touchStartY - event.touches[0].clientY > 40) { touchStartY = null; showSite('#main', true); }
  }, { passive: true });
  if (isEntryHash(location.hash)) {
    setEntryState(true); main.hidden = true; footer.hidden = true;
  } else showSite(location.hash);

  const menu = document.querySelector('.menu-button');
  const nav = document.querySelector('#site-nav');
  menu.hidden = false;
  const setMenu = (open) => {
    menu.setAttribute('aria-expanded', String(open)); nav.classList.toggle('is-open', open);
    menu.innerHTML = open ? 'Close <span aria-hidden="true">−</span>' : 'Menu <span aria-hidden="true">+</span>';
  };
  menu.addEventListener('click', () => setMenu(menu.getAttribute('aria-expanded') !== 'true'));
  nav.addEventListener('click', (event) => { if (event.target.closest('a')) setMenu(false); });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && menu.getAttribute('aria-expanded') === 'true') { setMenu(false); menu.focus(); }
  });
  window.matchMedia('(min-width: 801px)').addEventListener('change', () => setMenu(false));

  // Reveal only after an observer exists; content stays readable without JS.
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(({ target, isIntersecting }) => {
        if (isIntersecting) { target.classList.add('is-visible'); observer.unobserve(target); }
      });
    }, { threshold: 0.08 });
    document.querySelectorAll('.featured-studies .study').forEach((study) => {
      study.classList.add('reveal'); observer.observe(study);
    });

    // Scene people (hero and every gallery study): each generated overlay plays its single sequence once, the first
    // time it actually intersects the viewport (not on entry or on a timer), so a reader who scrolls down later still
    // sees it. Keep observing so an offscreen take pauses and resumes in place; scene-active is never removed,
    // so returning to a finished scene holds its final pose. Hidden pages and covered gallery scenes pause too.
    const sceneObserver = new IntersectionObserver((entries) => {
      entries.forEach(({ target, isIntersecting }) => {
        if (isIntersecting) { target.classList.add('scene-active'); }
        target.classList.toggle('scene-paused', !isIntersecting);
      });
    }, { threshold: 0.15 });
    document.querySelectorAll('.hero-image-stage .scene-overlay, .study-image .scene-overlay').forEach((overlay) => sceneObserver.observe(overlay));
  }

  // Image viewer: shows the title only; the image keeps its descriptive alt text.
  const dialog = document.querySelector('#study-viewer');
  const links = [...document.querySelectorAll('[data-lightbox]')];
  const viewerImage = document.querySelector('#viewer-image');
  const viewerTitle = document.querySelector('#viewer-title');
  const viewerCount = document.querySelector('#viewer-count');
  const viewerStage = document.querySelector('.viewer-stage');
  let activeIndex = 0;
  let opener;
  const clearViewerScene = () => viewerStage?.querySelectorAll('.scene-overlay').forEach((el) => el.remove());
  function showStudy(index) {
    activeIndex = (index + links.length) % links.length;
    const link = links[activeIndex];
    viewerImage.src = link.getAttribute('href'); viewerImage.alt = link.querySelector('img').alt;
    viewerTitle.textContent = link.dataset.title;
    viewerCount.textContent = `${activeIndex + 1} / ${links.length}`;
    // The enlarged view shows the same people: a trusted DOM clone of this study's generated overlay (never markup
    // built from input) sits over #viewer-image in .viewer-stage; both letterbox identically (object-fit: contain and
    // xMidYMid meet on the same box). Its ids are re-prefixed so clip paths never collide with the gallery copy, and
    // opening or changing the image is an explicit request to watch the scene, so the fresh clone replays it once.
    clearViewerScene();
    const scene = link.querySelector('svg.scene-overlay');
    if (scene && viewerStage) {
      const copy = scene.cloneNode(true);
      copy.classList.remove('scene-active', 'scene-paused');
      copy.classList.add('viewer-scene');
      copy.querySelectorAll('[id]').forEach((el) => { el.id = `viewer-${el.id.replace(/^(?:gallery|hero)-/, '')}`; });
      copy.querySelectorAll('[clip-path]').forEach((el) => {
        const ref = el.getAttribute('clip-path').match(/^url\(#(?:gallery|hero)-([\w-]+)\)$/);
        if (ref) el.setAttribute('clip-path', `url(#viewer-${ref[1]})`);
      });
      viewerStage.append(copy);
      copy.classList.add('scene-active');
    }
  }
  if (typeof dialog.showModal === 'function') {
    links.forEach((link, index) => link.addEventListener('click', (event) => {
      event.preventDefault(); opener = link; showStudy(index); dialog.showModal(); document.body.classList.add('viewer-open');
    }));
    document.querySelector('.viewer-close').addEventListener('click', () => dialog.close());
    document.querySelector('#viewer-prev').addEventListener('click', () => showStudy(activeIndex - 1));
    document.querySelector('#viewer-next').addEventListener('click', () => showStudy(activeIndex + 1));
    dialog.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); showStudy(activeIndex + (event.key === 'ArrowRight' ? 1 : -1)); }
    });
    dialog.addEventListener('click', (event) => {
      if (event.target !== dialog) return;
      const r = dialog.getBoundingClientRect();
      if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close();
    });
    // Closing removes the viewer's clone (its animations stop with it); the gallery overlay keeps its own finished state.
    dialog.addEventListener('close', () => { clearViewerScene(); document.body.classList.remove('viewer-open'); opener?.focus({ preventScroll: true }); });
  }

  const form = document.querySelector('#inquiry-form');
  const fields = document.querySelector('#form-fields');
  const review = document.querySelector('#review-panel');
  const confirmation = document.querySelector('#confirmation-panel');
  const error = document.querySelector('#form-error');
  const summary = document.querySelector('#review-summary');
  const clearInvalid = () => form.querySelectorAll('[aria-invalid]').forEach((el) => { el.removeAttribute('aria-invalid'); el.removeAttribute('aria-errormessage'); });
  function validate() {
    clearInvalid();
    const rules = [
      [form.querySelector('[name="projectType"]'), () => !!form.querySelector('[name="projectType"]:checked'), 'Choose a project type.'],
      [form.querySelector('#name'), () => !!form.querySelector('#name').value.trim(), 'Enter your name.'],
      [form.querySelector('#email'), () => form.querySelector('#email').checkValidity(), 'Enter a valid email address.']
    ];
    for (const [field, valid, message] of rules) {
      if (!valid()) { error.textContent = message; error.hidden = false; field.setAttribute('aria-invalid', 'true'); field.setAttribute('aria-errormessage', 'form-error'); field.focus(); return false; }
    }
    error.hidden = true; error.textContent = ''; return true;
  }
  form.addEventListener('submit', (event) => {
    event.preventDefault(); if (!validate()) return;
    const values = new FormData(form);
    const items = [
      ['Project type', values.get('projectType')], ['Support', values.getAll('services').join(', ') || 'Not specified'],
      ['Name', String(values.get('name')).trim()], ['Email', String(values.get('email')).trim()],
      ['Project location', values.get('location') || 'Not specified'], ['Space notes', values.get('details') || 'Not specified']
    ];
    summary.replaceChildren();
    items.forEach(([label, value]) => {
      const row = document.createElement('div'); const dt = document.createElement('dt'); const dd = document.createElement('dd');
      dt.textContent = label; dd.textContent = value; row.append(dt, dd); summary.append(row);
    });
    fields.hidden = true; review.hidden = false; review.focus();
  });
  document.querySelector('#edit-inquiry').addEventListener('click', () => { review.hidden = true; fields.hidden = false; form.querySelector('#name').focus(); });
  document.querySelector('#confirm-inquiry').addEventListener('click', () => { review.hidden = true; confirmation.hidden = false; confirmation.focus(); });
  document.querySelector('#start-over').addEventListener('click', () => { form.reset(); clearInvalid(); error.hidden = true; confirmation.hidden = true; fields.hidden = false; form.querySelector('[name="projectType"]').focus(); });
  fields.disabled = false;
})();
