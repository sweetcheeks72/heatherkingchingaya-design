// Browser gate for the Feedback 2 redesign.
//
//   python3 -m http.server 4184 --bind 127.0.0.1      (from the site directory)
//   SITE_URL=http://127.0.0.1:4184 node tests/browser_probe.mjs
//
// Uses Playwright Chromium with the Chromium sandbox ENABLED (chromiumSandbox: true; no
// --no-sandbox flag). Optional env:
//   PLAYWRIGHT_MODULE  absolute path to a playwright / playwright-core package entry
//   BROWSER_PATH       Chromium/Chrome executable to use instead of Playwright's bundled one
// Output (report + screenshots) goes ONLY to verification/feedback-2/.
// Exits non-zero if any check fails.

import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const root = path.resolve(import.meta.dirname, '..');
const output = path.join(root, 'verification', 'feedback-2');
if (path.basename(output) !== 'feedback-2') throw new Error('Refusing to write outside verification/feedback-2.');
const SITE_URL = new URL(process.env.SITE_URL || 'http://127.0.0.1:4184').href.replace(/#.*$/, '');
const ORIGIN = new URL(SITE_URL).origin;

const MAIN_VIEWPORTS = [
  { width: 1440, height: 900 },
  { width: 1024, height: 768 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
];
const NARROW = { width: 320, height: 700 };
const EXPECTED_GALLERY = [
  'assets/brief/architectural-model.webp',
  'assets/brief/sunken-living-room.webp',
  'assets/brief/hospitality-elevation.webp',
  'assets/brief/bedroom-terrace.webp',
  'assets/brief/bedroom-artwork.webp',
  'assets/brief/bathroom.webp',
  'assets/brief/restaurant-window.png',
  'assets/brief/restaurant-booths.png',
  'assets/brief/restaurant-counter.png',
];
const PRIVACY_COPY = [
  'This form is a preview. Nothing entered here is sent or stored. To get in touch now, email me directly.',
  'Local preview only. No message will be sent.',
  'This is a local preview. Confirming will not send or store your information.',
  'No message was sent and no information was stored. You can email me directly when you’re ready to talk.',
];
const SENT_CLAIM = /\b(has been sent|sent successfully|successfully sent|message sent|submitted successfully|we received your)\b/i;

const report = {
  status: 'RUNNING', url: SITE_URL, startedAt: new Date().toISOString(), sandbox: 'chromiumSandbox: true',
  browser: null, checks: [], failures: [], requests: [], errors: [], screenshots: [], viewports: {},
};
const check = (ok, name, detail) => {
  const entry = { name, ok: Boolean(ok) };
  if (detail !== undefined) entry.detail = detail;
  report.checks.push(entry);
  if (!ok) { report.failures.push(entry); console.error(`FAIL  ${name}${detail !== undefined ? ` — ${JSON.stringify(detail)}` : ''}`); }
  else console.log(`ok    ${name}`);
  return Boolean(ok);
};
async function section(name, fn) {
  try { await fn(); } catch (error) { check(false, `${name} (threw)`, String(error?.stack || error)); }
}

async function loadPlaywright() {
  const candidates = [process.env.PLAYWRIGHT_MODULE, 'playwright', 'playwright-core', '@playwright/test'].filter(Boolean);
  for (const spec of candidates) {
    try {
      const mod = await import(path.isAbsolute(spec) ? pathToFileURL(spec).href : spec);
      const chromium = mod.chromium || mod.default?.chromium;
      if (chromium) return chromium;
    } catch { /* try next */ }
  }
  throw new Error('Playwright not found. Install it (npm i -D playwright && npx playwright install chromium) or set PLAYWRIGHT_MODULE.');
}

// Instrumentation injected before any page script: records storage writes.
const INIT_SCRIPT = () => {
  window.__storageWrites = 0;
  for (const method of ['setItem', 'removeItem', 'clear']) {
    const original = Storage.prototype[method];
    Storage.prototype[method] = function (...args) { window.__storageWrites += 1; return original.apply(this, args); };
  }
};

let browser;
const contexts = [];
async function newContext(options = {}) {
  const context = await browser.newContext({ deviceScaleFactor: 1, reducedMotion: 'no-preference', ...options });
  contexts.push(context);
  if (options.javaScriptEnabled !== false) await context.addInitScript(INIT_SCRIPT);
  context.on('request', (request) => report.requests.push({ url: request.url(), method: request.method(), type: request.resourceType() }));
  return context;
}
async function openPage(context, hash = '') {
  const page = await context.newPage();
  page.on('pageerror', (error) => report.errors.push({ type: 'pageerror', text: String(error) }));
  page.on('console', (message) => { if (message.type() === 'error') report.errors.push({ type: 'console', text: message.text() }); });
  await page.goto(SITE_URL + hash, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready.then(() => true));
  await page.waitForTimeout(300);
  return page;
}
async function shot(page, name, locator) {
  const file = path.join(output, `${name}.png`);
  if (locator) await locator.screenshot({ path: file });
  else await page.screenshot({ path: file });
  report.screenshots.push(path.relative(root, file));
}
const isEntered = () => !document.querySelector('#main').hidden && document.querySelector('#entrance').hidden && !document.querySelector('#site-footer').hidden;
async function waitEntered(page) {
  await page.waitForFunction(isEntered, null, { timeout: 4000 });
  await page.waitForTimeout(100);
}
async function eagerImages(page) {
  await page.evaluate(async () => {
    document.querySelectorAll('img[src]').forEach((img) => { img.loading = 'eager'; });
    await Promise.race([
      Promise.all([...document.querySelectorAll('img[src]')].map((img) => img.decode().catch(() => false))),
      new Promise((resolve) => setTimeout(resolve, 8000)),
    ]);
  });
}
async function revealStudies(page) {
  await page.evaluate(() => document.querySelectorAll('.study').forEach((s) => s.classList.add('is-visible')));
  await page.waitForTimeout(1000);
}
const geometry = (page) => page.evaluate(() => ({
  scrollWidth: document.documentElement.scrollWidth,
  clientWidth: document.documentElement.clientWidth,
  brokenAnchors: [...document.querySelectorAll('a[href^="#"]')].filter((a) => a.hash && !document.getElementById(a.hash.slice(1))).map((a) => a.hash),
  smallTargets: [...document.querySelectorAll('a,button,summary')]
    .filter((el) => el.getClientRects().length && !el.classList.contains('skip-link') && getComputedStyle(el).visibility !== 'hidden')
    .map((el) => ({ el, r: el.getBoundingClientRect() }))
    .filter(({ el, r }) => r.height < 44 || (el.tagName === 'BUTTON' && r.width < 44))
    .map(({ el, r }) => ({ label: el.textContent.trim().slice(0, 40), width: Math.round(r.width), height: Math.round(r.height) })),
  fonts: document.fonts.check('700 16px Instrument'),
}));
const wordmarkMetrics = (page) => page.evaluate(() => {
  const el = document.querySelector('#entrance-title');
  const range = document.createRange();
  range.selectNodeContents(el);
  const rects = [...range.getClientRects()].filter((r) => r.width > 0);
  const box = range.getBoundingClientRect();
  const style = getComputedStyle(el);
  return {
    text: el.textContent.trim(), tag: el.tagName, lines: new Set(rects.map((r) => Math.round(r.top))).size,
    left: box.left, right: box.right, width: box.width, height: box.height,
    fontSize: parseFloat(style.fontSize), fontWeight: style.fontWeight, color: style.color, fontFamily: style.fontFamily,
    bandColor: getComputedStyle(document.querySelector('.brand-band')).backgroundColor,
    clientWidth: document.documentElement.clientWidth,
  };
});
const vineMetrics = (page) => page.evaluate(() => {
  const title = document.querySelector('#entrance-title').getBoundingClientRect();
  const layers = ['.vine-strand.vine-back', '.vine-strand.vine-front'].map((sel) => {
    const layer = document.querySelector(sel);
    if (!layer) return { sel, present: false };
    const r = layer.getBoundingClientRect();
    const imgs = [...layer.querySelectorAll('img')];
    return {
      sel, present: true, ariaHidden: layer.getAttribute('aria-hidden'), pointerEvents: getComputedStyle(layer).pointerEvents,
      overlapsTitle: r.top < title.bottom && r.bottom > title.top && r.left < title.right && r.right > title.left,
      images: imgs.map((img) => ({ src: new URL(img.currentSrc || img.src).pathname, complete: img.complete, naturalWidth: img.naturalWidth, alt: img.getAttribute('alt'), ariaHidden: img.getAttribute('aria-hidden') })),
    };
  });
  const lockupImgs = [...document.querySelectorAll('.brand-band img')].map((img) => new URL(img.currentSrc || img.src).pathname);
  const backgrounds = [...document.querySelectorAll('.brand-band, .brand-band *')].map((el) => getComputedStyle(el).backgroundImage).filter((bg) => bg && bg !== 'none');
  return { layers, lockupImgs, backgrounds };
});
const planMetrics = (page) => page.evaluate(() => {
  const link = document.querySelector('.enter-plan');
  const img = link?.querySelector('img.floor-plan');
  const lr = link?.getBoundingClientRect();
  const ir = img?.getBoundingClientRect();
  return link && img ? {
    href: link.getAttribute('href'), label: link.getAttribute('aria-label'), imgSrc: new URL(img.currentSrc || img.src).pathname,
    loaded: img.complete && img.naturalWidth > 0, linkWidth: lr.width, linkHeight: lr.height, imgWidth: ir.width, imgHeight: ir.height,
    clientWidth: document.documentElement.clientWidth, overflow: getComputedStyle(link).overflow, transform: getComputedStyle(img).transform,
    mapElements: document.querySelectorAll('.enter-map, .map-frame, .dallas-map, img[src*="dallas-map"]').length,
  } : null;
});

async function entryChecks(page, label) {
  const g = await geometry(page);
  check(g.scrollWidth <= g.clientWidth, `${label}: entry has no horizontal overflow`, { scrollWidth: g.scrollWidth, clientWidth: g.clientWidth });
  check(!g.smallTargets.length, `${label}: entry controls are at least 44px`, g.smallTargets);
  check(await page.evaluate(() => document.querySelector('#main').hidden && document.documentElement.classList.contains('entry-active')), `${label}: entrance precedes main content`);

  const w = await wordmarkMetrics(page);
  report.viewports[label] = { ...(report.viewports[label] || {}), wordmark: w };
  check(w.text === 'King Chingaya Design' && w.tag === 'P', `${label}: wordmark is live text`, w.text);
  check(w.lines === 1 && w.height < w.fontSize * 1.5, `${label}: wordmark stays on one line`, { lines: w.lines, height: w.height, fontSize: w.fontSize });
  check(w.left >= -1 && w.right <= w.clientWidth + 1, `${label}: wordmark fits within the viewport`, { left: w.left, right: w.right, clientWidth: w.clientWidth });
  if (label.startsWith('1440')) check(w.width >= 0.8 * w.clientWidth, `${label}: wordmark spans at least ~80% of the viewport`, { width: w.width, clientWidth: w.clientWidth });
  check(Number(w.fontWeight) >= 700 && w.color === 'rgb(255, 255, 255)', `${label}: wordmark is bold white`, { weight: w.fontWeight, color: w.color });
  check(w.bandColor === 'rgb(120, 146, 109)', `${label}: wordmark sits on the solid sage band (#78926d)`, w.bandColor);

  const v = await vineMetrics(page);
  check(v.layers.every((l) => l.present), `${label}: both vine layers present`, v.layers.map((l) => l.sel));
  check(v.layers.every((l) => l.ariaHidden === 'true' && l.pointerEvents === 'none'), `${label}: vine layers are decorative and ignore pointer input`);
  check(v.layers.every((l) => l.images?.length === 1 && l.images.every((i) => i.complete && i.naturalWidth > 0)), `${label}: vine images loaded`, v.layers.map((l) => l.images));
  check(v.lockupImgs.length === 2 && v.lockupImgs.every((p) => p.endsWith('/assets/brand/jasmine-vines-v1.png')), `${label}: vine uses only jasmine-vines-v1.png`, v.lockupImgs);
  check(!v.backgrounds.length, `${label}: no extra background imagery in the brand band`, v.backgrounds);
  check(v.layers.every((l) => l.overlapsTitle), `${label}: vine strand runs through the name`);

  const p = await planMetrics(page);
  check(p && p.href === '#main' && (p.label || '').length >= 10, `${label}: .enter-plan links to #main with an accessible name`, p && { href: p.href, label: p.label });
  check(p && p.imgSrc.endsWith('/assets/brand/entry-floor-plan.svg') && p.loaded, `${label}: floor-plan SVG loaded`, p && p.imgSrc);
  check(p && p.linkWidth >= 0.95 * p.clientWidth, `${label}: floor plan spans the page`, p && { linkWidth: p.linkWidth, clientWidth: p.clientWidth });
  check(p && p.overflow === 'hidden' && p.imgWidth > p.linkWidth && p.transform !== 'none', `${label}: floor plan is rotated and cropped`, p && { overflow: p.overflow, imgWidth: p.imgWidth, linkWidth: p.linkWidth, transform: p.transform });
  check(p && p.mapElements === 0, `${label}: no Dallas map elements remain`);
}

// Fresh load, before any scrolling or screenshots: "Step inside" must sit fully inside the first screen.
async function ctaFirstScreenCheck(page, label) {
  const c = await page.evaluate(() => {
    const el = document.querySelector('.enter-button');
    if (!el) return null;
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    const vw = document.documentElement.clientWidth, vh = window.innerHeight;
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const hit = cx >= 0 && cx < vw && cy >= 0 && cy < vh ? document.elementFromPoint(cx, cy) : null;
    return {
      text: el.textContent.trim(), scrollY: window.scrollY, top: r.top, bottom: r.bottom, left: r.left, right: r.right, vw, vh,
      visible: r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && Number(s.opacity) > 0 && !!hit && el.contains(hit),
    };
  });
  report.viewports[label] = { ...(report.viewports[label] || {}), stepInside: c };
  check(c && c.text.startsWith('Step inside') && c.scrollY === 0 && c.visible && c.top >= 0 && c.bottom <= c.vh && c.left >= 0 && c.right <= c.vw,
    `${label}: "Step inside" CTA is fully visible in the first screen on load`, c);
}

async function siteChecks(page, label, width) {
  await eagerImages(page);
  await revealStudies(page);
  const g = await geometry(page);
  check(g.scrollWidth <= g.clientWidth, `${label}: site has no horizontal overflow`, { scrollWidth: g.scrollWidth, clientWidth: g.clientWidth });
  check(!g.brokenAnchors.length, `${label}: no broken anchors`, g.brokenAnchors);
  check(!g.smallTargets.length, `${label}: site controls are at least 44px`, g.smallTargets);
  check(g.fonts, `${label}: bundled Instrument font available`);
  const images = await page.evaluate(() => [...document.querySelectorAll('img[src]')].filter((i) => !(i.complete && i.naturalWidth > 0)).map((i) => i.getAttribute('src')));
  check(!images.length, `${label}: all images loaded`, images);

  const gallery = await page.evaluate(() => {
    const links = [...document.querySelectorAll('[data-lightbox]')];
    const imgs = links.map((a) => a.querySelector('img'));
    const rects = imgs.map((i) => i.getBoundingClientRect());
    const overlaps = [];
    for (let a = 0; a < rects.length; a++) for (let b = a + 1; b < rects.length; b++) {
      const r1 = rects[a], r2 = rects[b];
      const w = Math.min(r1.right, r2.right) - Math.max(r1.left, r2.left);
      const h = Math.min(r1.bottom, r2.bottom) - Math.max(r1.top, r2.top);
      if (w > 0 && h > 0) overlaps.push({ a: a + 1, b: b + 1, ratio: (w * h) / Math.min(r1.width * r1.height, r2.width * r2.height) });
    }
    const captionHits = [];
    document.querySelectorAll('.study figcaption').forEach((cap, ci) => {
      // Measure the glyphs only (text nodes), not the blockified span boxes.
      const walker = document.createTreeWalker(cap, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (!node.textContent.trim()) continue;
        const range = document.createRange(); range.selectNodeContents(node);
        [...range.getClientRects()].forEach((cr) => rects.forEach((ir, ii) => {
          if (ii === ci || cr.width === 0) return;
          if (cr.left < ir.right - 1 && cr.right > ir.left + 1 && cr.top < ir.bottom - 1 && cr.bottom > ir.top + 1) captionHits.push({ caption: ci + 1, image: ii + 1 });
        }));
      }
    });
    return { hrefs: links.map((a) => a.getAttribute('href')), loaded: imgs.map((i) => i.complete && i.naturalWidth > 0), overlaps, captionHits };
  });
  check(gallery.hrefs.length === 9 && JSON.stringify(gallery.hrefs) === JSON.stringify(EXPECTED_GALLERY), `${label}: nine gallery images in order`, gallery.hrefs);
  check(gallery.loaded.every(Boolean), `${label}: nine gallery images loaded`, gallery.loaded);
  check(gallery.overlaps.every((o) => o.ratio <= 0.15), `${label}: gallery images overlap only slightly`, gallery.overlaps);
  check(!gallery.captionHits.length, `${label}: no image covers another study's caption`, gallery.captionHits);
  report.viewports[label] = { ...(report.viewports[label] || {}), geometry: { scrollWidth: g.scrollWidth, clientWidth: g.clientWidth }, galleryOverlaps: gallery.overlaps };

  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.waitForTimeout(150);
  await shot(page, `main-${label}`);
  await shot(page, `gallery-${label}`, page.locator('#projects'));

  if (width <= 800) {
    await page.click('.menu-button');
    check(await page.evaluate(() => document.querySelector('#site-nav').getBoundingClientRect().height > 0), `${label}: menu opens`);
    await page.keyboard.press('Escape');
    check(await page.evaluate(() => document.querySelector('.menu-button').getAttribute('aria-expanded') === 'false' && document.activeElement.classList.contains('menu-button')), `${label}: menu closes on Escape and restores focus`);
  } else {
    check(await page.evaluate(() => document.querySelector('.menu-button').getClientRects().length === 0), `${label}: desktop menu control hidden`);
  }
  await page.evaluate(() => document.querySelectorAll('.accordion details').forEach((d) => { d.open = true; }));
  const expanded = await geometry(page);
  check(expanded.scrollWidth <= expanded.clientWidth, `${label}: expanded accordions do not overflow`);
  await page.evaluate(() => document.querySelectorAll('.accordion details').forEach((d) => { d.open = false; }));
}

async function footerChecks(page, label) {
  await page.locator('#site-footer').scrollIntoViewIfNeeded();
  await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' }));
  await page.waitForTimeout(200);
  const f = await page.evaluate(() => {
    const footer = document.querySelector('#site-footer');
    const inner = footer.querySelector('.footer-inner');
    const wrap = footer.querySelector('.footer-mark');
    const text = footer.querySelector('.footer-mark-text');
    const vw = document.documentElement.clientWidth, vh = window.innerHeight;
    // Hit-test each contact/nav/copyright item after scrolling it into view; compare in document coordinates.
    const doc = (r) => ({ top: r.top + window.scrollY, bottom: r.bottom + window.scrollY, left: r.left, right: r.right, width: r.width, height: r.height });
    const items = [...inner.querySelectorAll('a, .footer-top > p, .socials > span, .footer-bottom > span')].map((el) => {
      el.scrollIntoView({ block: 'center', behavior: 'instant' });
      const r = el.getBoundingClientRect();
      const fr = doc(footer.getBoundingClientRect()), wr = doc(wrap.getBoundingClientRect()), dr = doc(r);
      const cx = Math.min(Math.max(r.left + Math.min(r.width / 2, 12), 0), vw - 1), cy = r.top + Math.min(r.height / 2, 10);
      const hit = cy >= 0 && cy < vh ? document.elementFromPoint(cx, cy) : null;
      return {
        label: el.textContent.trim().replace(/\s+/g, ' ').slice(0, 40),
        inViewportX: r.left >= -1 && r.right <= vw + 1,
        insideFooter: dr.top >= fr.top - 1 && dr.bottom <= fr.bottom + 1,
        aboveMark: dr.bottom <= wr.top + 1,
        notOverlapped: hit !== null && (el === hit || el.contains(hit)),
      };
    });
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' });
    const wr = wrap.getBoundingClientRect(), tr = text.getBoundingClientRect(), ir = inner.getBoundingClientRect();
    const range = document.createRange(); range.selectNodeContents(text);
    const glyphs = range.getBoundingClientRect();
    const lines = new Set([...range.getClientRects()].filter((r) => r.width > 0).map((r) => Math.round(r.top))).size;
    const colours = ['.footer-mark-a', '.footer-mark-b'].map((s) => getComputedStyle(footer.querySelector(s)).color);
    return {
      wrapOverflow: getComputedStyle(wrap).overflow, wrapTop: wr.top, wrapBottom: wr.bottom, textTop: tr.top, textBottom: tr.bottom,
      glyphWidth: glyphs.width, glyphLeft: glyphs.left, glyphRight: glyphs.right, lines, vw,
      innerBottom: ir.bottom, ariaHidden: [wrap, text].some((el) => el.closest('[aria-hidden="true"]')),
      text: text.textContent.replace(/\s+/g, ' ').trim(), colours, items,
    };
  });
  report.viewports[label] = { ...(report.viewports[label] || {}), footer: f };
  check(f.text === 'King Chingaya Design' && !f.ariaHidden, `${label}: footer mark is exposed live text`, f.text);
  check(f.wrapOverflow === 'hidden' && f.textBottom > f.wrapBottom + 1 && f.textTop >= f.wrapTop - 1, `${label}: footer mark is clipped at the bottom only`, { wrapTop: f.wrapTop, wrapBottom: f.wrapBottom, textTop: f.textTop, textBottom: f.textBottom });
  check(f.lines === 1 && f.glyphLeft >= -1 && f.glyphRight <= f.vw + 1, `${label}: footer mark is one line within the viewport`, { lines: f.lines, left: f.glyphLeft, right: f.glyphRight, vw: f.vw });
  check(f.glyphWidth >= 0.75 * f.vw, `${label}: footer mark stretches across the page`, { width: f.glyphWidth, vw: f.vw });
  check(f.colours[0] !== f.colours[1], `${label}: footer mark uses two shades`, f.colours);
  check(f.innerBottom <= f.wrapTop + 1, `${label}: contact/nav block sits above the mark`, { innerBottom: f.innerBottom, wrapTop: f.wrapTop });
  const hidden = f.items.filter((i) => !i.inViewportX || !i.insideFooter || !i.aboveMark || i.notOverlapped === false);
  check(f.items.length >= 5 && !hidden.length, `${label}: footer contact, nav and copyright fully visible and unobstructed`, hidden.length ? hidden : f.items.length);
  await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' }));
  await shot(page, `footer-viewport-${label}`);
  await shot(page, `footer-${label}`, page.locator('#site-footer'));
}

async function keyboardEntry(context, label) {
  const page = await openPage(context);
  let found = false;
  for (let i = 0; i < 30 && !found; i++) {
    await page.keyboard.press('Tab');
    found = await page.evaluate(() => document.activeElement?.classList.contains('enter-plan'));
  }
  check(found, `${label}: .enter-plan reachable with Tab`);
  if (found) {
    const focus = await page.evaluate(() => { const el = document.activeElement; const s = getComputedStyle(el); return { focusVisible: el.matches(':focus-visible'), style: s.outlineStyle, width: parseFloat(s.outlineWidth) }; });
    check(focus.focusVisible && focus.style !== 'none' && focus.width >= 2, `${label}: .enter-plan has a visible focus indicator`, focus);
    await shot(page, `entry-plan-focus-${label}`);
    await page.keyboard.press('Enter');
    await section(`${label}: keyboard entry`, async () => {
      await waitEntered(page);
      check(await page.evaluate(() => document.activeElement.id === 'main'), `${label}: Enter on .enter-plan enters and focuses #main`);
    });
  }
  await page.close();
}

async function lightboxChecks(page, label, exhaustiveKeyboard) {
  await revealStudies(page);
  const first = page.locator('[data-lightbox]').first();
  await first.scrollIntoViewIfNeeded();
  await first.click();
  const count = () => page.evaluate(() => document.querySelector('#viewer-count').textContent.trim());
  const viewerState = () => page.evaluate(() => { const i = document.querySelector('#viewer-image'); return { src: i.getAttribute('src'), loaded: i.complete && i.naturalWidth > 0, alt: i.alt }; });
  await page.waitForFunction(() => document.querySelector('#study-viewer').open);
  check(await count() === '1 / 9', `${label}: viewer opens at 1 / 9`, await count());
  await shot(page, `viewer-${label}`);
  await page.click('#viewer-prev');
  check(await count() === '9 / 9', `${label}: Previous from 1 wraps to 9`, await count());
  await page.click('#viewer-next');
  check(await count() === '1 / 9', `${label}: Next from 9 wraps to 1`, await count());
  for (let n = 1; n <= 9; n++) {
    if (n > 1) await page.click('#viewer-next');
    await page.waitForFunction(() => { const i = document.querySelector('#viewer-image'); return i.complete && i.naturalWidth > 0; }, null, { timeout: 8000 }).catch(() => {});
    const state = await viewerState();
    check(await count() === `${n} / 9` && state.src === EXPECTED_GALLERY[n - 1] && state.loaded && state.alt.trim().length > 0, `${label}: viewer shows study ${n} / 9`, { count: await count(), ...state });
  }
  await page.click('#viewer-next');
  check(await count() === '1 / 9', `${label}: Next from 9 wraps to 1 (after full pass)`, await count());
  await page.keyboard.press('Escape');
  await page.waitForTimeout(150);
  check(await page.evaluate(() => !document.querySelector('#study-viewer').open && document.activeElement === document.querySelector('[data-lightbox]')), `${label}: Escape closes viewer and restores focus to opener`);

  if (exhaustiveKeyboard) {
    for (let n = 1; n <= 9; n++) {
      const link = page.locator('[data-lightbox]').nth(n - 1);
      await link.focus();
      await page.keyboard.press('Enter');
      await page.waitForFunction(() => document.querySelector('#study-viewer').open, null, { timeout: 3000 }).catch(() => {});
      check(await count() === `${n} / 9`, `${label}: study ${n} opens from the keyboard`, await count());
      await page.keyboard.press('Escape');
      await page.waitForTimeout(100);
      check(await page.evaluate((i) => document.activeElement === document.querySelectorAll('[data-lightbox]')[i], n - 1), `${label}: focus returns to study ${n}`);
    }
  }
}

async function inquiryChecks(context) {
  const page = await openPage(context, '#inquiry');
  const before = report.requests.length;
  check(await page.evaluate(() => document.querySelector('#entrance').hidden), 'inquiry: deep link bypasses the entrance');
  const text = await page.evaluate(() => document.body.innerText + document.body.textContent);
  for (const copy of PRIVACY_COPY) check(text.includes(copy), `inquiry: privacy copy unchanged — ${copy.slice(0, 40)}…`);

  const validation = await page.evaluate(() => {
    const form = document.querySelector('#inquiry-form'); const q = (s) => document.querySelector(s);
    const state = () => ({ error: q('#form-error').textContent, focus: document.activeElement.id || document.activeElement.name });
    form.requestSubmit(); const empty = state();
    q('[name=projectType]').checked = true; q('#name').value = '  '; form.requestSubmit(); const blankName = state();
    q('#name').value = 'Preview Reviewer'; q('#email').value = 'invalid'; form.requestSubmit(); const badEmail = state();
    form.reset(); return { empty, blankName, badEmail };
  });
  check(validation.empty.error === 'Choose a project type.' && validation.empty.focus === 'projectType', 'inquiry: project type validation', validation.empty);
  check(validation.blankName.error === 'Enter your name.' && validation.blankName.focus === 'name', 'inquiry: whitespace name validation', validation.blankName);
  check(validation.badEmail.error === 'Enter a valid email address.' && validation.badEmail.focus === 'email', 'inquiry: email validation', validation.badEmail);

  await page.check('input[name=projectType][value=Residential]');
  await page.check('input[name=services][value="Virtual design"]');
  await page.fill('#name', 'Preview Reviewer');
  await page.fill('#email', 'review@example.com');
  await page.fill('#location', 'Dallas');
  await page.fill('#details', '<img src=x onerror=alert(1)> ' + 'longword'.repeat(80));
  await page.click('#form-fields button[type=submit]');
  const review = await page.evaluate(() => ({
    visible: !document.querySelector('#review-panel').hidden, focused: document.activeElement.id === 'review-panel',
    summary: document.querySelector('#review-summary').textContent, injected: document.querySelector('#review-summary img') !== null,
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
  }));
  check(review.visible && review.focused && review.summary.includes('Preview Reviewer') && review.summary.includes('review@example.com'), 'inquiry: preview shows entered details', review.summary.slice(0, 80));
  check(!review.injected, 'inquiry: entered markup is rendered as plain text');
  check(!review.overflow, 'inquiry: long input does not overflow');
  await shot(page, 'inquiry-preview-390');
  await page.click('#edit-inquiry');
  check(await page.inputValue('#name') === 'Preview Reviewer', 'inquiry: edit preserves values');
  await page.click('#form-fields button[type=submit]');
  await page.click('#confirm-inquiry');
  const confirmation = await page.evaluate(() => ({ visible: !document.querySelector('#confirmation-panel').hidden, text: document.querySelector('#confirmation-panel').textContent }));
  check(confirmation.visible && confirmation.text.includes('No message was sent'), 'inquiry: confirmation states nothing was sent');
  await shot(page, 'inquiry-confirmation-390');
  const bodyText = await page.evaluate(() => document.body.innerText);
  check(!SENT_CLAIM.test(bodyText), 'inquiry: page never claims a message was sent', bodyText.match(SENT_CLAIM)?.[0]);
  const storage = await page.evaluate(() => ({ writes: window.__storageWrites, length: localStorage.length + sessionStorage.length, cookie: document.cookie }));
  check(storage.writes === 0 && storage.length === 0 && storage.cookie === '', 'inquiry: no localStorage/sessionStorage/cookie writes', storage);
  check((await context.cookies()).length === 0, 'inquiry: no cookies set');
  const during = report.requests.slice(before);
  const bad = during.filter((r) => !(r.method === 'GET' && (r.url.startsWith(ORIGIN + '/') || r.url.startsWith('data:'))) || ['xhr', 'fetch', 'websocket', 'eventsource', 'ping', 'beacon'].includes(r.type));
  check(!bad.length, 'inquiry: no network requests other than same-origin static GETs', bad);
  await page.click('#start-over');
  check(await page.evaluate(() => !document.querySelector('#form-fields').hidden && document.querySelector('#name').value === '' && !document.querySelector('[name=projectType]:checked')), 'inquiry: start over resets the form');
  await page.evaluate(() => document.querySelector('.process-list summary').focus());
  await page.keyboard.press('Enter');
  check(await page.evaluate(() => document.querySelector('.process-list details').open), 'keyboard: accordion opens with Enter');
  await page.close();
}

try {
  await mkdir(output, { recursive: true });
  const chromium = await loadPlaywright();
  browser = await chromium.launch({ headless: true, chromiumSandbox: true, ...(process.env.BROWSER_PATH ? { executablePath: process.env.BROWSER_PATH } : {}) });
  report.browser = `${browser.browserType().name()} ${browser.version()}`;
  console.log(`Probing ${SITE_URL} with ${report.browser} (sandboxed)`);

  for (const vp of MAIN_VIEWPORTS) {
    const label = `${vp.width}x${vp.height}`;
    const context = await newContext({ viewport: vp });
    await section(label, async () => {
      const page = await openPage(context);
      await page.waitForFunction(() => [...document.querySelectorAll('.brand-band img, .enter-plan img')].every((i) => i.complete), null, { timeout: 8000 }).catch(() => {});
      if (label === '1440x900' || label === '1024x768') await ctaFirstScreenCheck(page, label);
      await entryChecks(page, label);
      await shot(page, `entry-${label}`);
      await page.click('.enter-plan');
      await waitEntered(page);
      check(await page.evaluate(() => document.activeElement.id === 'main' && !document.documentElement.classList.contains('entry-active')), `${label}: mouse click on floor plan enters the site`);
      await siteChecks(page, label, vp.width);
      if (vp.width === 1440 || vp.width === 390) await footerChecks(page, label);
      if (vp.width === 1440 || vp.width === 390) await lightboxChecks(page, label, vp.width === 1440);
      await page.close();
    });
    await section(`${label} keyboard`, () => keyboardEntry(context, label));
    await context.close();
  }

  await section('320 narrow', async () => {
    const label = `${NARROW.width}x${NARROW.height}`;
    const context = await newContext({ viewport: NARROW });
    const page = await openPage(context);
    await entryChecks(page, label);
    await shot(page, `entry-${label}`);
    await page.click('.enter-plan');
    await waitEntered(page);
    await eagerImages(page);
    await revealStudies(page);
    const g = await geometry(page);
    check(g.scrollWidth <= g.clientWidth, `${label}: site has no horizontal overflow`, { scrollWidth: g.scrollWidth, clientWidth: g.clientWidth });
    check(!g.smallTargets.length, `${label}: site controls are at least 44px`, g.smallTargets);
    await page.evaluate(() => document.querySelectorAll('.accordion details').forEach((d) => { d.open = true; }));
    const expanded = await geometry(page);
    check(expanded.scrollWidth <= expanded.clientWidth, `${label}: expanded accordions do not overflow`);
    await shot(page, `main-${label}`);
    await footerChecks(page, label);
    await context.close();
  });

  await section('motion: pause control', async () => {
    const context = await newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'no-preference' });
    const page = await openPage(context);
    const vineAnimations = () => page.evaluate(() => document.getAnimations().filter((a) => a.effect?.target?.classList?.contains('jasmine-vines')).map((a) => a.playState));
    const running = await vineAnimations();
    check(running.length === 2 && running.every((s) => s === 'running'), 'motion: vine sway runs when motion is allowed', running);
    const toggle = page.locator('.motion-toggle');
    check(await toggle.isVisible(), 'motion: pause control is visible');
    await toggle.click();
    await page.waitForTimeout(100);
    const paused = await page.evaluate(() => ({
      pressed: document.querySelector('.motion-toggle').getAttribute('aria-pressed'),
      cls: document.documentElement.classList.contains('motion-paused'),
      states: [...document.querySelectorAll('.jasmine-vines')].map((i) => getComputedStyle(i).animationPlayState),
    }));
    const pausedAnims = await vineAnimations();
    check(paused.pressed === 'true' && paused.cls && paused.states.every((s) => s === 'paused') && pausedAnims.every((s) => s === 'paused'), 'motion: pause control pauses the vine', { ...paused, pausedAnims });
    await toggle.click();
    check(await page.evaluate(() => document.querySelector('.motion-toggle').getAttribute('aria-pressed') === 'false'), 'motion: control resumes motion');
    await context.close();
  });

  await section('motion: reduced', async () => {
    const context = await newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
    const page = await openPage(context);
    const state = await page.evaluate(() => ({
      running: document.getAnimations().filter((a) => a.playState === 'running').length,
      vineRunning: document.getAnimations().filter((a) => a.effect?.target?.classList?.contains('jasmine-vines') && a.playState === 'running').length,
      vineAnimationName: [...document.querySelectorAll('.jasmine-vines')].map((i) => getComputedStyle(i).animationName),
      toggleHidden: document.querySelector('.motion-toggle').hidden,
      motionReady: document.documentElement.classList.contains('motion-ready'),
    }));
    check(state.running === 0 && state.vineRunning === 0 && state.vineAnimationName.every((n) => n === 'none'), 'motion: no running animations under reduced motion', state);
    check(state.toggleHidden && !state.motionReady, 'motion: pause control hidden and motion class absent under reduced motion', state);
    await shot(page, 'entry-reduced-motion-390x844');
    await page.click('.enter-plan');
    check(await page.evaluate(() => !document.querySelector('#main').hidden && document.querySelector('#entrance').hidden), 'motion: reduced-motion entry is immediate');
    await context.close();
  });

  await section('no JavaScript', async () => {
    for (const vp of [{ width: 320, height: 700 }, { width: 1440, height: 900 }]) {
      const label = `nojs-${vp.width}x${vp.height}`;
      const context = await newContext({ viewport: vp, javaScriptEnabled: false });
      const page = await context.newPage();
      await page.goto(SITE_URL, { waitUntil: 'load' });
      check(await page.locator('#main').isVisible(), `${label}: main content visible`);
      check(await page.locator('#site-footer').isVisible() && await page.locator('.footer-mark-text').isVisible(), `${label}: footer visible`);
      check(await page.locator('#entrance-title').isVisible(), `${label}: wordmark visible`);
      check(await page.locator('[data-lightbox][href]').count() === 9, `${label}: nine gallery links remain plain links`);
      check(await page.locator('#form-fields').getAttribute('disabled') !== null && await page.locator('#form-fields button[type=submit]').isDisabled(), `${label}: form is disabled without JS`);
      check(await page.locator('#inquiry-form .preview-note').first().isVisible(), `${label}: no-JS form note visible`);
      check(await page.locator('.motion-toggle').isHidden(), `${label}: motion control hidden without JS`);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth).catch(() => null);
      check(overflow === false, `${label}: no horizontal overflow`, overflow);
      await shot(page, `entry-${label}`);
      await page.click('.enter-plan');
      check(page.url().endsWith('#main'), `${label}: floor-plan link navigates to #main natively`, page.url());
      await context.close();
    }
  });

  await section('inquiry', async () => {
    const context = await newContext({ viewport: { width: 390, height: 844 } });
    await inquiryChecks(context);
    await context.close();
  });

  const nonLocal = report.requests.filter((r) => !(r.method === 'GET' && (r.url.startsWith(ORIGIN + '/') || r.url.startsWith('data:'))));
  check(!nonLocal.length, 'network: only same-origin GET requests across the whole run', nonLocal);
  check(!report.errors.length, 'browser: no page errors or console errors', report.errors);
} catch (error) {
  check(false, 'probe setup', String(error?.stack || error));
} finally {
  for (const context of contexts) await context.close().catch(() => {});
  await browser?.close().catch(() => {});
  report.finishedAt = new Date().toISOString();
  report.status = report.failures.length ? 'FAIL' : 'PASS';
  report.summary = { total: report.checks.length, failed: report.failures.length };
  report.requests = report.requests.map((r) => ({ ...r, url: r.url.startsWith('data:') ? 'data:…' : r.url }));
  await mkdir(output, { recursive: true });
  await writeFile(path.join(output, 'browser-report.json'), JSON.stringify(report, null, 2));
  console.log(`${report.status}: ${report.checks.length - report.failures.length}/${report.checks.length} checks passed. Report: ${path.relative(root, path.join(output, 'browser-report.json'))}`);
  process.exitCode = report.failures.length ? 1 : 0;
}
