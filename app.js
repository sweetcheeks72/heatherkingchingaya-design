(() => {
  'use strict';
  const root = document.documentElement;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const entrance = document.querySelector('#entrance');
  const main = document.querySelector('#main');
  const footer = document.querySelector('#site-footer');
  const enter = document.querySelector('.enter-button');
  const entryLinks = [enter, document.querySelector('.enter-map')];
  const motion = document.querySelector('.motion-toggle');
  let entering = false;
  let entryTimer;
  root.classList.add('js-ready');
  function syncMotion() {
    root.classList.toggle('motion-ready', !reduced.matches);
    motion.hidden = reduced.matches;
  }
  syncMotion();
  reduced.addEventListener('change', syncMotion);
  motion.addEventListener('click', () => {
    const paused = root.classList.toggle('motion-paused');
    motion.setAttribute('aria-pressed', String(paused));
    motion.innerHTML = paused ? 'Resume motion <span aria-hidden="true">▷</span>' : 'Pause motion <span aria-hidden="true">Ⅱ</span>';
  });
  document.addEventListener('visibilitychange', () => root.classList.toggle('document-hidden', document.hidden));

  // Install entry handlers before hiding content. Without JS this is a normal
  // anchor and the complete website remains readable below the entrance.
  function showSite(target = '#main', animated = false) {
    const finish = () => {
      clearTimeout(entryTimer);
      main.hidden = false; footer.hidden = false; entrance.hidden = true;
      root.classList.remove('entry-active', 'entering'); entering = false;
      const destination = document.getElementById(target.slice(1)) || main;
      destination.setAttribute('tabindex', '-1');
      destination.focus({ preventScroll: true });
      destination.scrollIntoView({ behavior: 'instant', block: 'start' });
    };
    if (animated && !reduced.matches && !root.classList.contains('motion-paused')) {
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
    if (main.hidden && location.hash && location.hash !== '#top') showSite(location.hash);
  });
  if (!location.hash || location.hash === '#top') {
    root.classList.add('entry-active'); main.hidden = true; footer.hidden = true;
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
  }

  const dialog = document.querySelector('#study-viewer');
  const links = [...document.querySelectorAll('[data-lightbox]')];
  const viewerImage = document.querySelector('#viewer-image');
  let activeIndex = 0;
  let opener;
  function showStudy(index) {
    activeIndex = (index + links.length) % links.length;
    const link = links[activeIndex];
    viewerImage.src = link.getAttribute('href'); viewerImage.alt = link.querySelector('img').alt;
    document.querySelector('#viewer-title').textContent = link.dataset.title;
    document.querySelector('#viewer-kind').textContent = link.dataset.kind;
    document.querySelector('#viewer-count').textContent = `${activeIndex + 1} / ${links.length}`;
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
    dialog.addEventListener('close', () => { document.body.classList.remove('viewer-open'); opener?.focus({ preventScroll: true }); });
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
