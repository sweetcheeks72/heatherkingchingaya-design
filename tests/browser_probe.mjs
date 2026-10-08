// Browser gate for the Feedback 1 (latest) revision.
//
//   python3 -m http.server 4184 --bind 127.0.0.1      (from the site directory)
//   SITE_URL=http://127.0.0.1:4184 node tests/browser_probe.mjs
//
// Uses Playwright Chromium with the Chromium sandbox ENABLED (chromiumSandbox: true; no
// --no-sandbox flag). Reuses an already installed Playwright/Chrome; it installs nothing.
// Optional env:
//   PLAYWRIGHT_MODULE  absolute path to a playwright / playwright-core package entry
//   BROWSER_PATH       Chromium/Chrome executable to use instead of Playwright's bundled one
// Output (report + screenshots) goes ONLY to verification/latest/. Prior reports in
// verification/feedback-2/ and verification/feedback-3/ are preserved and never touched.
// Exits non-zero if any check fails.
//
// Feedback 1 (latest) behaviour under test:
//   - opening screen shows the diagonal floor plan only (header hidden, no visible name or caption,
//     no "Step inside" button); entry by clicking the plan, keyboard, wheel, swipe or deep link;
//   - scene people in EVERY scene (user request, 3 October 2026): the hero and all nine gallery studies carry a generated
//     decorative overlay (scripts/build_scene_overlays.py from assets/people/scenes.json) placing Blender renders of the
//     licensed Renderpeople scans Nathan and Carla in the raster's own pixel space; each actor is a one-frame viewport
//     of its own strip measured with its own metadata; every overlay plays its single 4.4 s sequence once when it
//     intersects (IntersectionObserver), pauses while the page is hidden, and rests on the last frame at the end
//     position, which is also the static no-JS / reduced-motion pose; the hero people walk INTO the backyard during
//     the first half, then stand still and chat (frames keep changing, position does not); the lightbox shows the same
//     people on a letterboxed clone that replays on open/change and is removed on close; people are verified as
//     painted pixels (screenshot diffs with the overlay hidden), captured at three time points for review;
//   - floor plan is inline SVG root .floor-plan, aria-hidden=true focusable=false, with stage groups
//     .plan-shell, .plan-fixtures, .plan-furniture; staged reveal finishes <= 4.5s;
//   - custom Enter cursor on fine pointer: .enter-cursor only visible over plan, native cursor hidden
//     only while replacement is visible, pointerleave restores; clicking enters, hover does not;
//   - white live name inside main in the expanded sage band: one line, unclipped, taller (scaleY >= 1.15),
//     contrast >= 3:1;
//   - green header & navigation bar in sage green (#78926d), small text contrast >= 4.5:1;
//   - thinner vine strand and hanging flower clusters; finite growth/bloom, no infinite sway;
//   - full-plan and pause-motion controls removed from marketing DOM;
//   - standalone floor-plan.html tested directly as an unlinked review artifact, external SVG aspect
//     derives from viewBox;
//   - larger plain headings (Design philosophy, Gallery, About me, Working together, Services, Start a project),
//     no section/accordion numbers, removed philosophy taglines;
//   - nine title-only gallery studies with descriptive alt text, uncropped aspect, airy layout, overlap <= 15%,
//     no caption overlap.

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { inflateSync } from 'node:zlib';

const root = path.resolve(import.meta.dirname, '..');
// Shared scene contract (research-people/all-scenes-contract.txt): assets/people/scenes.json lists the nine studies and
// their actors; each actor's strip metadata is read here at Node level and passed into page.evaluate keyed by strip path,
// so every placed figure is measured against the metadata of the render it actually shows.
const SCENES = await readFile(path.join(root, 'assets', 'people', 'scenes.json'), 'utf8').then(JSON.parse).catch((error) => {
  throw new Error(`assets/people/scenes.json is missing or invalid; render the scene strips, then run scripts/build_scene_overlays.py --write (${error.message})`);
});
const STRIP_METAS = {};
for (const scene of SCENES.scenes) for (const actor of scene.actors) {
  if (STRIP_METAS[actor.strip]) continue;
  const meta = await readFile(path.join(root, actor.metadata), 'utf8').then(JSON.parse);
  if (meta.file !== path.basename(actor.strip)) throw new Error(`${actor.metadata} describes ${meta.file}, expected ${path.basename(actor.strip)}`);
  STRIP_METAS[actor.strip] = meta;
}
const SCENE_BY_ID = Object.fromEntries(SCENES.scenes.map((s) => [s.id, s]));
const SCENE_MS = Math.round(SCENES.duration * 1000);
const SCENE_TIMES = [0, Math.round(SCENE_MS / 2), SCENE_MS]; // review captures: start, stop-and-turn, seated rest pose
const output = path.join(root, 'verification', 'latest');
if (path.basename(output) !== 'latest' || path.basename(path.dirname(output)) !== 'verification') throw new Error('Refusing to write outside verification/latest.');
const SITE_URL = new URL(process.env.SITE_URL || 'http://127.0.0.1:4184').href.replace(/#.*$/, '');
const ORIGIN = new URL(SITE_URL).origin;

const VIEWPORTS = [
  { width: 1440, height: 900 },
  { width: 1024, height: 768 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
  { width: 320, height: 700 },
];
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
const JASMINE = '/assets/brand/jasmine-vines-v1.png';
const JASMINE_SIZE = { width: 2172, height: 724 }; // the unmodified raster
const PLAN_SVG = '/assets/brand/entry-floor-plan.svg';
const PLAN_ASPECT = 1600 / 1040;
const BRAND_ANIMATIONS = ['vine-grow', 'cluster-bloom'];

const report = {
  status: 'RUNNING', revision: 'Feedback 1 (latest)', url: SITE_URL, startedAt: new Date().toISOString(), sandbox: 'chromiumSandbox: true',
  browser: null, checks: [], failures: [], requests: [], errors: [], screenshots: [], viewports: {},
};

function hexRgb(hex) {
  const clean = hex.replace('#', '');
  const full = clean.length === 3 ? clean.split('').map((c) => c + c).join('') : clean;
  return [parseInt(full.slice(0, 2), 16), parseInt(full.slice(2, 4), 16), parseInt(full.slice(4, 6), 16)];
}
function parseRgb(color) {
  const m = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  return m ? [parseInt(m[1]), parseInt(m[2]), parseInt(m[3])] : hexRgb(color);
}
function luminance(rgb) {
  const linear = rgb.map((v) => {
    const s = v / 255;
    return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}
function contrastRatio(c1, c2) {
  const l1 = luminance(parseRgb(c1)), l2 = luminance(parseRgb(c2));
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

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
const note = (label, data) => { report.viewports[label] = { ...(report.viewports[label] || {}), ...data }; };

async function loadPlaywright() {
  const candidates = [process.env.PLAYWRIGHT_MODULE, 'playwright', 'playwright-core', '@playwright/test'].filter(Boolean);
  for (const spec of candidates) {
    try {
      const mod = await import(path.isAbsolute(spec) ? pathToFileURL(spec).href : spec);
      const chromium = mod.chromium || mod.default?.chromium;
      if (chromium) return chromium;
    } catch { /* try next */ }
  }
  throw new Error('Playwright not found. Point PLAYWRIGHT_MODULE at an installed playwright/playwright-core entry (this probe installs nothing).');
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
async function shot(page, name, locator, options = {}) {
  const file = path.join(output, `${name}.png`);
  if (locator) await locator.screenshot({ path: file });
  else await page.screenshot({ path: file, ...options });
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
// Wait for the brand images and for the entry growth/bloom animations to finish (bounded).
async function settleBrand(page) {
  await page.waitForFunction(() => [...document.querySelectorAll('.brand-band img')].every((i) => i.complete), null, { timeout: 8000 }).catch(() => {});
  await page.evaluate((names) => Promise.race([
    Promise.all(document.getAnimations().filter((a) => names.includes(a.animationName)).map((a) => a.finished.catch(() => null))),
    new Promise((resolve) => setTimeout(resolve, 8000)),
  ]).then(() => true), BRAND_ANIMATIONS);
  await page.waitForTimeout(50);
}
const fullyRevealedClip = (clip) => clip === 'none' || /^inset\(0(?:px|%)?(?:\s+0(?:px|%)?){0,3}\)$/.test(clip);

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

// The live name inside the sage band: real glyph bounds, line count, scale, colour and hit-testing.
const wordmarkMetrics = (page) => page.evaluate(() => {
  const el = document.querySelector('#entrance-title');
  const band = document.querySelector('.brand-band');
  const range = document.createRange();
  range.selectNodeContents(el);
  const rects = [...range.getClientRects()].filter((r) => r.width > 0);
  const glyph = range.getBoundingClientRect();
  const box = el.getBoundingClientRect();
  const b = band.getBoundingClientRect();
  const style = getComputedStyle(el);
  const matrix = style.transform.match(/^matrix\(([^)]+)\)$/);
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const cx = Math.min(Math.max(glyph.left + glyph.width / 2, 0), vw - 1), cy = glyph.top + glyph.height * 0.55;
  const hit = cy >= 0 && cy < vh ? document.elementFromPoint(cx, cy) : null;
  return {
    text: el.textContent.trim(), tag: el.tagName, inMain: !!el.closest('#main'), lines: new Set(rects.map((r) => Math.round(r.top))).size,
    layoutHeight: el.offsetHeight, lineHeight: parseFloat(style.lineHeight), boxHeight: box.height,
    scaleY: matrix ? Number(matrix[1].split(',')[3]) : 1, transform: style.transform, transformOrigin: style.transformOrigin,
    glyph: { left: glyph.left, right: glyph.right, top: glyph.top, bottom: glyph.bottom, width: glyph.width, height: glyph.height },
    band: { left: b.left, right: b.right, top: b.top, bottom: b.bottom, height: b.height },
    spaceAbove: glyph.top - b.top, spaceBelow: b.bottom - glyph.bottom,
    fontSize: parseFloat(style.fontSize), fontWeight: style.fontWeight, color: style.color, fontFamily: style.fontFamily,
    bandColor: getComputedStyle(band).backgroundColor, bandOverflow: getComputedStyle(band).overflow,
    visible: style.visibility !== 'hidden' && Number(style.opacity) > 0, hitIsTitle: !!hit && (hit === el || el.contains(hit)), hit: hit ? hit.className || hit.tagName : null,
    clientWidth: vw,
  };
});
const vineMetrics = (page) => page.evaluate((jasmine) => {
  const range = document.createRange();
  range.selectNodeContents(document.querySelector('#entrance-title'));
  const title = range.getBoundingClientRect();
  const band = document.querySelector('.brand-band').getBoundingClientRect();
  const vw = document.documentElement.clientWidth;
  const layers = ['.vine-strand.vine-back', '.vine-strand.vine-front'].map((sel) => {
    const layer = document.querySelector(sel);
    if (!layer) return { sel, present: false };
    const r = layer.getBoundingClientRect();
    const imgs = [...layer.querySelectorAll('img')];
    return {
      sel, present: true, inBand: !!layer.closest('.brand-band'), ariaHidden: layer.getAttribute('aria-hidden'), pointerEvents: getComputedStyle(layer).pointerEvents,
      clipPath: getComputedStyle(layer).clipPath,
      overlapsTitle: r.top < title.bottom && r.bottom > title.top && r.left < title.right && r.right > title.left,
      images: imgs.map((img) => ({ src: new URL(img.currentSrc || img.src).pathname, complete: img.complete, naturalWidth: img.naturalWidth, alt: img.getAttribute('alt'), ariaHidden: img.getAttribute('aria-hidden') })),
    };
  });
  const wrap = document.querySelector('.brand-band .vine-clusters');
  const clusters = [...document.querySelectorAll('.brand-band .vine-cluster')].map((c) => {
    const r = c.getBoundingClientRect(), s = getComputedStyle(c);
    const imgs = [...c.querySelectorAll('img')];
    const img = imgs[0];
    const ir = img?.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    return {
      cls: c.className, imgCount: imgs.length, width: r.width, height: r.height, left: r.left, right: r.right,
      centreInBand: cx >= band.left && cx <= band.right && cy >= band.top && cy <= band.bottom,
      inViewportX: r.left >= -1 && r.right <= vw + 1,
      overflow: s.overflow, opacity: Number(s.opacity), pointerEvents: s.pointerEvents, decorative: !!c.closest('[aria-hidden="true"]'),
      img: img ? {
        cls: img.className, src: new URL(img.currentSrc || img.src).pathname, loaded: img.complete && img.naturalWidth > 0,
        naturalWidth: img.naturalWidth, naturalHeight: img.naturalHeight, alt: img.getAttribute('alt'), ariaHidden: img.getAttribute('aria-hidden'),
        renderedWidth: ir.width, renderedHeight: ir.height,
      } : null,
    };
  });
  const lockupImgs = [...document.querySelectorAll('.brand-band img')].map((img) => new URL(img.currentSrc || img.src).pathname);
  const backgrounds = [...document.querySelectorAll('.brand-band, .brand-band *')].map((el) => getComputedStyle(el).backgroundImage).filter((bg) => bg && bg !== 'none');
  return { layers, clusters, wrapAriaHidden: wrap?.getAttribute('aria-hidden') ?? null, lockupImgs, backgrounds, jasmine, bandWidth: band.width };
}, JASMINE);
const planMetrics = (page) => page.evaluate(() => {
  const link = document.querySelector('.enter-plan');
  const planEl = link?.querySelector('.floor-plan');
  const cta = document.querySelector('.enter-button');
  const lr = link?.getBoundingClientRect();
  const pr = planEl?.getBoundingClientRect();
  const cr = cta?.getBoundingClientRect();
  if (!link || !planEl) return null;
  const isSvg = planEl.tagName.toLowerCase() === 'svg';
  const vb = planEl.getAttribute('viewBox');
  const vbParts = vb ? vb.trim().split(/[\s,]+/).map(Number) : null;
  const imgSrc = !isSvg && (planEl.currentSrc || planEl.src) ? new URL(planEl.currentSrc || planEl.src).pathname : null;
  return {
    isSvg,
    tagName: planEl.tagName.toLowerCase(),
    ariaHidden: planEl.getAttribute('aria-hidden'),
    focusable: planEl.getAttribute('focusable'),
    viewBox: vb,
    viewBoxAspect: vbParts && vbParts.length === 4 && vbParts[3] > 0 ? vbParts[2] / vbParts[3] : null,
    hasShell: !!planEl.querySelector('.plan-shell'),
    hasFixtures: !!planEl.querySelector('.plan-fixtures'),
    hasFurniture: !!planEl.querySelector('.plan-furniture'),
    loaded: isSvg ? (pr.width > 0 && pr.height > 0) : (planEl.complete && planEl.naturalWidth > 0),
    imgSrc,
    href: link.getAttribute('href'),
    label: link.getAttribute('aria-label'),
    linkWidth: lr.width,
    linkHeight: lr.height,
    planWidth: pr.width,
    planHeight: pr.height,
    clientWidth: document.documentElement.clientWidth,
    overflow: getComputedStyle(link).overflow,
    transform: getComputedStyle(planEl).transform,
    ctaOverPlan: !!cr && cr.left >= lr.left - 1 && cr.right <= lr.right + 1 && cr.top >= lr.top - 1 && cr.bottom <= lr.bottom + 1,
    ctaHref: cta?.getAttribute('href') ?? null,
    mapElements: document.querySelectorAll('.enter-map, .map-frame, .dallas-map, img[src*="dallas-map"]').length,
  };
});

// Plan-only opening screen: no header, no visible name/caption, just the plan and "Step inside".
async function entryChecks(page, label) {
  const g = await geometry(page);
  check(g.scrollWidth <= g.clientWidth, `${label}: entry has no horizontal overflow`, { scrollWidth: g.scrollWidth, clientWidth: g.clientWidth });
  check(!g.smallTargets.length, `${label}: entry controls are at least 44px`, g.smallTargets);
  check(await page.evaluate(() => document.querySelector('#main').hidden && document.querySelector('#site-footer').hidden && document.documentElement.classList.contains('entry-active') && document.body.classList.contains('is-entrance')), `${label}: entrance precedes main content`);

  const e = await page.evaluate(() => {
    const vw = document.documentElement.clientWidth, vh = window.innerHeight;
    const rendered = (el) => !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
    const texts = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const parent = node.parentElement;
      if (!node.textContent.trim() || !parent || parent.closest('.sr-only, script, style, noscript, svg, [aria-hidden="true"]')) continue;
      if (parent.checkVisibility && !parent.checkVisibility({ opacityProperty: true, visibilityProperty: true })) continue;
      const range = document.createRange(); range.selectNodeContents(node);
      const onScreen = [...range.getClientRects()].some((r) => r.width > 1 && r.height > 1 && r.right > 0 && r.left < vw && r.bottom > 0 && r.top < vh);
      if (onScreen) texts.push(node.textContent.trim());
    }
    const entrance = document.querySelector('#entrance').getBoundingClientRect();
    const label = document.querySelector('#entrance-label');
    return {
      visibleText: texts.join(' ').replace(/\s+/g, ' '),
      headerShown: rendered(document.querySelector('.site-header')),
      navShown: rendered(document.querySelector('#site-nav')),
      titleShown: rendered(document.querySelector('#entrance-title')),
      srLabel: label ? { text: label.textContent.trim(), srOnly: label.classList.contains('sr-only'), labels: document.querySelector('#entrance').getAttribute('aria-labelledby') === 'entrance-label' } : null,
      entranceTop: entrance.top, entranceHeight: entrance.height, vh,
    };
  });
  note(label, { entry: e });
  check(!e.headerShown && !e.navShown, `${label}: header and navigation are hidden before entry`, { header: e.headerShown, nav: e.navShown });
  check(!/king|chingaya|design/i.test(e.visibleText), `${label}: no company name, caption or slogan is visible on the opening screen`, e.visibleText);
  check(!e.visibleText || e.visibleText.trim() === '', `${label}: opening screen has no visible marketing copy`, e.visibleText);
  check(!e.titleShown, `${label}: brand name waits inside main`, { title: e.titleShown });
  check(e.srLabel && e.srLabel.text.length > 0 && e.srLabel.srOnly && e.srLabel.labels, `${label}: entrance keeps a screen-reader-only label`, e.srLabel);
  check(Math.abs(e.entranceTop) <= 1 && e.entranceHeight >= e.vh - 1, `${label}: the plan fills the first screen`, { top: e.entranceTop, height: e.entranceHeight, vh: e.vh });

  const p = await planMetrics(page);
  check(p && p.href === '#main' && (p.label || '').length >= 10, `${label}: .enter-plan links to #main with an accessible name`, p && { href: p.href, label: p.label });
  if (p?.isSvg) {
    check(p.ariaHidden === 'true' && p.focusable === 'false', `${label}: inline SVG plan has aria-hidden=true and focusable=false`, { ariaHidden: p.ariaHidden, focusable: p.focusable });
    check(p.hasShell && p.hasFixtures && p.hasFurniture, `${label}: inline SVG plan contains stage groups .plan-shell, .plan-fixtures, .plan-furniture`, { shell: p.hasShell, fixtures: p.hasFixtures, furniture: p.hasFurniture });
    check(p.loaded, `${label}: inline floor-plan SVG rendered with non-zero bounds`, { width: p.planWidth, height: p.planHeight });
  } else {
    check(p && p.loaded, `${label}: floor-plan placeholder loaded`, p && p.imgSrc);
  }
  check(p && p.linkWidth >= 0.95 * p.clientWidth, `${label}: floor plan spans the page`, p && { linkWidth: p.linkWidth, clientWidth: p.clientWidth });
  check(p && p.overflow === 'hidden' && p.planWidth > p.linkWidth && p.transform !== 'none', `${label}: floor plan is rotated and cropped`, p && { overflow: p.overflow, planWidth: p.planWidth, linkWidth: p.linkWidth, transform: p.transform });
  check(await page.evaluate(() => !document.querySelector('.enter-button')), `${label}: Step inside button removed from entrance`);
  check(p && p.mapElements === 0, `${label}: no Dallas map elements remain`);
}

// Custom Enter cursor finepointer check
async function enterCursorChecks(page, label) {
  const cursorInfo = await page.evaluate(() => {
    const cursor = document.querySelector('.enter-cursor');
    const entrance = document.querySelector('#entrance');
    const plan = document.querySelector('.enter-plan');
    const cStyle = cursor ? getComputedStyle(cursor) : null;
    const pStyle = plan ? getComputedStyle(plan) : null;
    return {
      exists: !!cursor,
      ariaHidden: cursor?.getAttribute('aria-hidden'),
      text: cursor?.textContent.trim(),
      cursorDisplay: cStyle?.display,
      entranceHasLive: entrance?.classList.contains('cursor-live'),
      planCursor: pStyle?.cursor,
      pointerEvents: cStyle?.pointerEvents,
      width: cStyle ? parseFloat(cStyle.width) : 0,
      height: cStyle ? parseFloat(cStyle.height) : 0,
    };
  });
  check(cursorInfo.exists && cursorInfo.ariaHidden === 'true' && cursorInfo.text.startsWith('Enter'), `${label}: Enter cursor is aria-hidden decoration reading 'Enter'`, cursorInfo);
  check(!cursorInfo.entranceHasLive && cursorInfo.cursorDisplay === 'none', `${label}: Enter cursor initially hidden`);
  check(cursorInfo.pointerEvents === 'none', `${label}: Enter cursor ignores pointer events`);
  check(cursorInfo.width >= cursorInfo.height * 1.5, `${label}: Enter cursor is oval (noticeably width > height)`, { width: cursorInfo.width, height: cursorInfo.height });

  const planBox = await page.locator('.enter-plan').boundingBox();
  if (planBox) {
    await page.mouse.move(planBox.x + planBox.width / 2, planBox.y + planBox.height / 3);
    await page.waitForTimeout(50);
    const hovered = await page.evaluate(() => {
      const cursor = document.querySelector('.enter-cursor');
      const entrance = document.querySelector('#entrance');
      const plan = document.querySelector('.enter-plan');
      return {
        cursorDisplay: cursor ? getComputedStyle(cursor).display : null,
        entranceHasLive: entrance?.classList.contains('cursor-live'),
        planCursor: plan ? getComputedStyle(plan).cursor : null,
        stillHidden: document.querySelector('#main').hidden,
      };
    });
    check(hovered.entranceHasLive && hovered.cursorDisplay === 'flex', `${label}: Enter cursor visible when hovering over plan`, hovered);
    check(hovered.planCursor === 'none', `${label}: native cursor hidden while replacement cursor is visible`, hovered);
    check(hovered.stillHidden, `${label}: hovering over plan does not enter site`);

    await page.mouse.move(-50, -50).catch(() => {});
    await page.evaluate(() => {
      const plan = document.querySelector('.enter-plan');
      plan?.dispatchEvent(new PointerEvent('pointerleave', { bubbles: false, cancelable: true, pointerType: 'mouse' }));
    });
    await page.waitForTimeout(50);
    const left = await page.evaluate(() => {
      const cursor = document.querySelector('.enter-cursor');
      const entrance = document.querySelector('#entrance');
      const plan = document.querySelector('.enter-plan');
      return {
        cursorDisplay: cursor ? getComputedStyle(cursor).display : null,
        entranceHasLive: entrance?.classList.contains('cursor-live'),
        planCursor: plan ? getComputedStyle(plan).cursor : null,
      };
    });
    check(!left.entranceHasLive && left.cursorDisplay === 'none', `${label}: Enter cursor hides when pointer leaves plan`, left);
    check(left.planCursor !== 'none', `${label}: native cursor restored when pointer leaves`, left);
  }
}

// Fresh load, before any scrolling or screenshots: entrance plan visible, no Step inside button.
async function ctaFirstScreenCheck(page, label) {
  const hasButton = await page.evaluate(() => !!document.querySelector('.enter-button'));
  check(!hasButton, `${label}: Step inside button removed from entrance`);
}

// Immediately after entering: header back, name visible without scrolling.
async function afterEntryChecks(page, label) {
  const a = await page.evaluate(() => {
    const rendered = (el) => !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
    const header = document.querySelector('.site-header');
    const band = document.querySelector('.brand-band').getBoundingClientRect();
    const range = document.createRange(); range.selectNodeContents(document.querySelector('#entrance-title'));
    const glyph = range.getBoundingClientRect();
    return {
      focus: document.activeElement?.id, entryActive: document.documentElement.classList.contains('entry-active'), isEntrance: document.body.classList.contains('is-entrance'),
      headerShown: rendered(header), wordmarkShown: rendered(header?.querySelector('.wordmark')),
      firstInMain: document.querySelector('#main').firstElementChild?.id, bandTop: band.top, titleTop: glyph.top, titleBottom: glyph.bottom, vh: window.innerHeight,
      reduced: matchMedia('(prefers-reduced-motion: reduce)').matches,
    };
  });
  note(label, { afterEntry: a });
  check(a.focus === 'main', `${label}: focus moves to main on entry`, a.focus);
  check(!a.entryActive && !a.isEntrance && a.headerShown && a.wordmarkShown, `${label}: header is revealed after entry`, { entryActive: a.entryActive, header: a.headerShown, wordmark: a.wordmarkShown });
  check(a.firstInMain === 'brand', `${label}: the sage brand band is the first section of main`, a.firstInMain);
  check(a.bandTop >= -2 && a.titleTop >= 0 && a.titleBottom <= a.vh + 1, `${label}: the name is in view right after entering`, { bandTop: a.bandTop, titleTop: a.titleTop, titleBottom: a.titleBottom, vh: a.vh });
}

// Brand band after the entry growth has settled.
async function brandChecks(page, label) {
  await page.evaluate(() => document.querySelector('#brand').scrollIntoView({ block: 'start', behavior: 'instant' }));
  await page.waitForTimeout(100);
  const w = await wordmarkMetrics(page);
  note(label, { wordmark: w });
  check(w.text === 'King Chingaya Design' && w.tag === 'P' && w.inMain, `${label}: brand name is live text inside main`, w.text);
  check(w.lines === 1 && w.layoutHeight <= w.lineHeight * 1.5, `${label}: brand name stays on one line`, { lines: w.lines, layoutHeight: w.layoutHeight, lineHeight: w.lineHeight });
  check(w.glyph.left >= -1 && w.glyph.right <= w.clientWidth + 1, `${label}: brand name fits within the viewport`, { left: w.glyph.left, right: w.glyph.right, clientWidth: w.clientWidth });
  check(w.glyph.top >= w.band.top - 1 && w.glyph.bottom <= w.band.bottom + 1 && w.glyph.left >= w.band.left - 1 && w.glyph.right <= w.band.right + 1,
    `${label}: brand name is not clipped by the band`, { glyph: w.glyph, band: w.band, overflow: w.bandOverflow });
  if (label.startsWith('1440')) check(w.glyph.width >= 0.8 * w.clientWidth, `${label}: brand name spans at least ~80% of the viewport`, { width: w.glyph.width, clientWidth: w.clientWidth });
  check(w.scaleY >= 1.15 && w.boxHeight / w.layoutHeight >= 1.15, `${label}: letters are drawn taller (vertical scale >= 1.15)`, { scaleY: w.scaleY, rendered: w.boxHeight, layout: w.layoutHeight });
  check(w.spaceAbove > w.spaceBelow && (w.glyph.top + w.glyph.bottom) / 2 > (w.band.top + w.band.bottom) / 2,
    `${label}: brand name sits toward the bottom of the band`, { above: w.spaceAbove, below: w.spaceBelow });
  check(Number(w.fontWeight) >= 700 && w.color === 'rgb(255, 255, 255)' && /Instrument/.test(w.fontFamily), `${label}: brand name is bold white Instrument`, { weight: w.fontWeight, color: w.color, family: w.fontFamily });
  check(w.bandColor === 'rgb(120, 146, 109)', `${label}: brand name sits on the solid sage band (#78926d)`, w.bandColor);
  check(w.visible && w.hitIsTitle, `${label}: brand name is visible and not covered`, { hit: w.hit });

  // Contrast checks: sage header nav text >= 4.5:1, brand name on sage >= 3:1
  const headerNav = await page.evaluate(() => {
    const header = document.querySelector('.site-header');
    const navLink = document.querySelector('.site-nav a');
    return {
      headerBg: header ? getComputedStyle(header).backgroundColor : null,
      navColor: navLink ? getComputedStyle(navLink).color : null,
    };
  });
  if (headerNav.headerBg && headerNav.navColor) {
    const navContrast = contrastRatio(headerNav.navColor, headerNav.headerBg);
    check(navContrast >= 4.5, `${label}: green header/nav text contrast >= 4.5:1`, { contrast: navContrast.toFixed(2), ...headerNav });
  }
  const nameContrast = contrastRatio(w.color, w.bandColor);
  check(nameContrast >= 3.0, `${label}: large white brand name contrast on sage >= 3:1`, { contrast: nameContrast.toFixed(2) });

  const v = await vineMetrics(page);
  note(label, { vine: { layers: v.layers.map((l) => ({ sel: l.sel, clipPath: l.clipPath })), clusters: v.clusters.map((c) => ({ cls: c.cls, width: c.width, height: c.height, left: c.left })) } });
  check(v.layers.every((l) => l.present && l.inBand), `${label}: back and front vine layers present in the band`, v.layers.map((l) => l.sel));
  check(v.layers.every((l) => l.ariaHidden === 'true' && l.pointerEvents === 'none'), `${label}: vine layers are decorative and ignore pointer input`);
  check(v.layers.every((l) => l.images?.length === 1 && l.images.every((i) => i.complete && i.naturalWidth > 0 && i.src.endsWith(JASMINE) && i.alt === '' && i.ariaHidden === 'true')), `${label}: vine layer images loaded`, v.layers.map((l) => l.images));
  check(v.layers.every((l) => l.overlapsTitle), `${label}: vine strand runs through the name`);
  check(v.layers.every((l) => fullyRevealedClip(l.clipPath)), `${label}: vine strand is fully revealed after growth`, v.layers.map((l) => l.clipPath));

  // Thinner vine strand check (aspect-ratio narrower than full band)
  const strandStyle = await page.evaluate(() => {
    const s = document.querySelector('.vine-strand');
    return s ? { width: getComputedStyle(s).width, aspectRatio: getComputedStyle(s).aspectRatio } : null;
  });
  check(strandStyle && strandStyle.aspectRatio !== 'none', `${label}: thinner vine strand geometry defined`, strandStyle);

  // Clusters: count and positions are design choices; verified dynamically without hardcoding 5 clusters
  check(v.clusters.length >= 1 && v.wrapAriaHidden === 'true', `${label}: hanging flower clusters present and decorative (dynamic count)`, { count: v.clusters.length, wrapAriaHidden: v.wrapAriaHidden });
  const badCrop = v.clusters.filter((c) => !(c.imgCount === 1 && c.img && /\bjasmine-cluster\b/.test(c.img.cls) && c.img.src.endsWith(JASMINE) && c.img.loaded
    && c.img.naturalWidth === JASMINE_SIZE.width && c.img.naturalHeight === JASMINE_SIZE.height && c.img.alt === '' && c.img.ariaHidden === 'true'));
  check(!badCrop.length, `${label}: every cluster is the unchanged jasmine raster, loaded`, badCrop);
  const notCropped = v.clusters.filter((c) => !(['hidden', 'clip'].includes(c.overflow) && c.img && c.img.renderedWidth > c.width * 1.5 && c.width < v.bandWidth * 0.5));
  check(!notCropped.length, `${label}: clusters show cropped portions of the raster, not the whole image`, notCropped);
  const badBounds = v.clusters.filter((c) => !(c.width >= 4 && c.height >= 4 && c.centreInBand && c.inViewportX));
  check(!badBounds.length, `${label}: clusters have real size, sit in the band and stay within the viewport`, badBounds);
  check(v.clusters.every((c) => c.decorative && c.pointerEvents === 'none'), `${label}: clusters ignore pointer input`);
  check(v.clusters.every((c) => c.opacity > 0.99), `${label}: clusters are fully open after the bloom`, v.clusters.map((c) => c.opacity));
  check(v.lockupImgs.length === 2 + v.clusters.length && v.lockupImgs.every((p) => p.endsWith(JASMINE)), `${label}: brand band uses only jasmine-vines-v1.png`, v.lockupImgs);
  check(!v.backgrounds.length, `${label}: no extra background imagery in the brand band`, v.backgrounds);
}

// Scene people in EVERY scene (user request, 3 October 2026): the hero and all nine gallery studies carry a generated
// decorative overlay (scripts/build_scene_overlays.py from assets/people/scenes.json) placing Blender renders of
// licensed Renderpeople scans Nathan and Carla in the raster's own pixel space.
async function sceneChecks(page, label) {
  const sceneData = await page.evaluate(async ({ SCENES_DEF, METAS_MAP }) => {
    const near = (a, b, tol = 2) => Math.abs(a - b) <= tol;
    const box = (el) => {
      const r = el.getBoundingClientRect();
      return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height };
    };

    // Hero overlay: .hero-image-stage .scene-overlay
    const heroFig = document.querySelector('.hero-model');
    const heroImg = heroFig?.querySelector('img');
    const heroStage = heroFig?.querySelector('.hero-image-stage');
    const heroOverlay = heroStage?.querySelector('svg.scene-overlay');
    const heroCap = heroFig?.querySelector('figcaption');
    const capTexts = heroCap ? [...heroCap.querySelectorAll('span')].map((s) => s.textContent.trim()) : [];
    const heroIr = heroImg ? box(heroImg) : null;
    const heroOr = heroOverlay ? box(heroOverlay) : null;
    const heroVb = heroOverlay?.viewBox?.baseVal;
    const heroActors = heroOverlay ? [...heroOverlay.querySelectorAll('g.scene-actor')] : [];

    const heroDetails = {
      present: !!heroOverlay,
      src: heroImg?.getAttribute('src'),
      loaded: heroImg ? heroImg.complete && heroImg.naturalWidth > 0 : false,
      sceneId: heroOverlay?.getAttribute('data-scene'),
      ariaHidden: heroOverlay?.getAttribute('aria-hidden'),
      focusable: heroOverlay?.getAttribute('focusable'),
      aspect: heroOverlay?.getAttribute('preserveAspectRatio'),
      viewBoxMatchesRaster: !!heroVb && !!heroImg && heroVb.width === heroImg.naturalWidth && heroVb.height === heroImg.naturalHeight,
      overlayMatchesImage: !!heroIr && !!heroOr && near(heroIr.left, heroOr.left) && near(heroIr.top, heroOr.top) && near(heroIr.width, heroOr.width) && near(heroIr.height, heroOr.height),
      capTexts,
      actorCount: heroActors.length,
      actors: heroActors.map((aEl) => {
        const aid = aEl.getAttribute('data-actor');
        const person = aEl.getAttribute('data-person');
        const sprite = aEl.querySelector('svg.actor-sprite');
        const image = sprite?.querySelector('image.actor-strip');
        const href = image?.getAttribute('href') || '';
        const meta = METAS_MAP[href];
        const shadow = aEl.querySelector('ellipse.actor-shadow');
        const move = aEl.querySelector('g.actor-move');
        const frames = aEl.querySelector('g.actor-frames');
        const s = getComputedStyle(aEl);
        const svb = sprite?.viewBox?.baseVal;
        const sW = sprite ? sprite.width.baseVal.value : 0;
        const sH = sprite ? sprite.height.baseVal.value : 0;
        const unit = svb && svb.width > 0 ? sW / svb.width : 0;
        const bodySourcePx = meta ? meta.visible_body_height * unit : 0;
        return {
          aid, person, href, metaFound: !!meta,
          framesVar: parseInt(s.getPropertyValue('--frames'), 10),
          sceneSec: parseFloat(s.getPropertyValue('--scene-seconds')),
            delaySec: parseFloat(s.getPropertyValue('--scene-delay')),
          moveSec: parseFloat(s.getPropertyValue('--move-seconds')),
          tx: parseFloat(s.getPropertyValue('--tx')),
          ty: parseFloat(s.getPropertyValue('--ty')),
          hasMove: !!move, hasFrames: !!frames, hasSprite: !!sprite, hasImage: !!image, hasShadow: !!shadow,
          spriteVb: svb ? [svb.width, svb.height] : null,
          imageDims: image ? [parseFloat(image.getAttribute('width')), parseFloat(image.getAttribute('height'))] : null,
          bodySourcePx: Math.round(bodySourcePx * 10) / 10,
        };
      }),
    };

    // Gallery overlays: 9 studies
    const galleryDetails = [];
    for (let i = 1; i <= 9; i++) {
      const sid = `study-${i}`;
      const fig = document.querySelector(`.study.study-${i}`);
      const link = fig?.querySelector('.study-image');
      const img = link?.querySelector('img');
      const overlay = link?.querySelector('svg.scene-overlay');
      const ir = img ? box(img) : null;
      const or = overlay ? box(overlay) : null;
      const vb = overlay?.viewBox?.baseVal;
      const spec = SCENES_DEF.scenes.find((s) => s.id === sid);
      const actorEls = overlay ? [...overlay.querySelectorAll('g.scene-actor')] : [];

      galleryDetails.push({
        sid,
        present: !!overlay,
        sceneId: overlay?.getAttribute('data-scene'),
        ariaHidden: overlay?.getAttribute('aria-hidden'),
        focusable: overlay?.getAttribute('focusable'),
        aspect: overlay?.getAttribute('preserveAspectRatio'),
        viewBoxValid: !!vb && !!spec && vb.width === spec.width && vb.height === spec.height,
        overlayMatchesImage: !!ir && !!or && near(ir.left, or.left) && near(ir.top, or.top) && near(ir.width, or.width) && near(ir.height, or.height),
        actorCount: actorEls.length,
        actors: actorEls.map((aEl) => {
          const aid = aEl.getAttribute('data-actor');
          const person = aEl.getAttribute('data-person');
          const sprite = aEl.querySelector('svg.actor-sprite');
          const image = sprite?.querySelector('image.actor-strip');
          const href = image?.getAttribute('href') || '';
          const meta = METAS_MAP[href];
          const shadow = aEl.querySelector('ellipse.actor-shadow');
          const clipRef = aEl.getAttribute('clip-path');
          const clipNode = clipRef ? overlay.querySelector(clipRef.replace(/^url\(#([\w-]+)\)$/, '#$1')) : null;
          const s = getComputedStyle(aEl);
          return {
            aid, person, href, metaFound: !!meta,
            framesVar: parseInt(s.getPropertyValue('--frames'), 10),
            sceneSec: parseFloat(s.getPropertyValue('--scene-seconds')),
            delaySec: parseFloat(s.getPropertyValue('--scene-delay')),
            moveSec: parseFloat(s.getPropertyValue('--move-seconds')),
            hasShadow: !!shadow,
            hasSprite: !!sprite,
            hasImage: !!image,
            clipRef,
            clipPrefixValid: clipRef ? clipRef.includes(`gallery-${sid}-${aid}`) : true,
            clipEvenOdd: clipNode ? clipNode.querySelector('path')?.getAttribute('clip-rule') === 'evenodd' : true,
          };
        }),
      });
    }

    // Strip load check
    const stripHrefs = Object.keys(METAS_MAP);
    const stripLoads = await Promise.all(stripHrefs.map((href) => new Promise((resolve) => {
      const probe = new Image();
      probe.onload = () => resolve({
        href, ok: probe.naturalWidth === METAS_MAP[href].strip_width && probe.naturalHeight === METAS_MAP[href].strip_height,
        width: probe.naturalWidth, height: probe.naturalHeight,
      });
      probe.onerror = () => resolve({ href, ok: false });
      probe.src = href;
    })));

    return { hero: heroDetails, gallery: galleryDetails, stripLoads };
  }, { SCENES_DEF: SCENES, METAS_MAP: STRIP_METAS });

  note(label, { sceneData: { hero: { ...sceneData.hero, actors: sceneData.hero.actors.length }, galleryCount: sceneData.gallery.length } });

  // Hero checks
  check(sceneData.hero.src === 'assets/brief/architectural-model.webp' && sceneData.hero.loaded, `${label}: hero image uses architectural-model.webp, loaded`, sceneData.hero.src);
  check(sceneData.hero.capTexts.includes('Architecture in miniature') && sceneData.hero.capTexts.includes('Architectural model'), `${label}: hero caption simplified to Architecture in miniature / Architectural model`, sceneData.hero.capTexts);
  check(sceneData.hero.present && sceneData.hero.sceneId === 'study-1', `${label}: hero scene overlay present with study-1 scene configuration`);
  check(sceneData.hero.ariaHidden === 'true' && sceneData.hero.aspect === 'xMidYMid slice', `${label}: hero overlay is aria-hidden and uses xMidYMid slice`);
  check(sceneData.hero.viewBoxMatchesRaster && sceneData.hero.overlayMatchesImage, `${label}: hero overlay matches image viewBox 1800x1092 and covers the image box`);
  check(sceneData.hero.actorCount === 2, `${label}: hero scene has exactly 2 actors (Nathan and Carla)`, sceneData.hero.actorCount);
  check(sceneData.hero.actors.every((a) => a.metaFound && a.hasMove && a.hasFrames && a.hasSprite && a.hasImage && a.hasShadow), `${label}: hero actors have sprites, strip images, shadows and known metadata`);
  check(sceneData.hero.actors.every((a,i) => a.framesVar === 160 && a.sceneSec === SCENES.scenes[0].actors[i].duration && a.delaySec === SCENES.scenes[0].actors[i].delay && Math.abs(a.moveSec-a.sceneSec*.5)<.01 && a.sceneSec+a.delaySec<=8.801), `${label}: hero actors have 160 frames with individual duration/delay, half-take walk and final hold within 8.8s`, sceneData.hero.actors.map((a) => [a.framesVar, a.sceneSec, a.moveSec]));
  check(sceneData.hero.actors.every((a) => a.bodySourcePx >= 75 && a.bodySourcePx <= 115), `${label}: hero figures are believable adults in source pixels`, sceneData.hero.actors.map((a) => a.bodySourcePx));

  // Gallery checks (9 studies)
  check(sceneData.gallery.length === 9 && sceneData.gallery.every((g) => g.present && g.sceneId === g.sid), `${label}: all 9 gallery studies have scene overlays in a.study-image`);
  check(sceneData.gallery.every((g) => g.ariaHidden === 'true' && g.aspect === 'xMidYMid meet'), `${label}: gallery overlays are aria-hidden and preserveAspectRatio xMidYMid meet`);
  check(sceneData.gallery.every((g) => g.viewBoxValid && g.overlayMatchesImage), `${label}: gallery overlays align with photo rasters`);
  check(sceneData.gallery.every((g) => g.actorCount >= 1), `${label}: every gallery scene has at least 1 actor`);
  const allGalleryActors = sceneData.gallery.flatMap((g) => g.actors);
  check(allGalleryActors.every((a) => a.metaFound && a.hasSprite && a.hasImage && a.clipPrefixValid && a.clipEvenOdd), `${label}: gallery actors valid with unique clipPath prefixes and evenodd masks`);
  const personsSeen = new Set(allGalleryActors.map((a) => a.person));
  check(personsSeen.has('Nathan') && personsSeen.has('Carla'), `${label}: diverse group across gallery scenes (both Nathan and Carla appear)`);

  // Strip loads
  check(sceneData.stripLoads.length >= 2 && sceneData.stripLoads.every((s) => s.ok), `${label}: all rendered scene strips load at declared dimensions`, sceneData.stripLoads);
}

async function siteChecks(page, label, width) {
  await eagerImages(page);

  // Scenes first, before any other gallery scrolling, so every observer trigger is exercised here rather than as a side effect.
  await sceneChecks(page, label);

  // Scroll through all 9 studies to trigger real reveal/load
  const studiesCount = await page.locator('.featured-studies .study').count();
  for (let i = 0; i < studiesCount; i++) {
    await page.locator('.featured-studies .study').nth(i).scrollIntoViewIfNeeded();
    await page.waitForTimeout(50);
  }
  await page.waitForFunction(() => {
    const studies = [...document.querySelectorAll('.featured-studies .study')];
    return studies.every((s) => s.classList.contains('is-visible') || !document.documentElement.classList.contains('motion-ready'));
  }, null, { timeout: 4000 }).catch(() => {});

  const g = await geometry(page);
  check(g.scrollWidth <= g.clientWidth, `${label}: site has no horizontal overflow`, { scrollWidth: g.scrollWidth, clientWidth: g.clientWidth });
  check(!g.brokenAnchors.length, `${label}: no broken anchors`, g.brokenAnchors);
  check(!g.smallTargets.length, `${label}: site controls are at least 44px`, g.smallTargets);
  check(g.fonts, `${label}: bundled Instrument font available`);
  const images = await page.evaluate(() => [...document.querySelectorAll('img[src]')].filter((i) => !(i.complete && i.naturalWidth > 0)).map((i) => i.getAttribute('src')));
  check(!images.length, `${label}: all images loaded`, images);

  const logoCheck = await page.evaluate(() => {
    const el = document.querySelector('.site-header .wordmark');
    return {
      hasPlaceholder: el?.getAttribute('data-placeholder') === 'logo',
      label: el?.getAttribute('aria-label'),
      href: el?.getAttribute('href'),
    };
  });
  check(logoCheck.hasPlaceholder && logoCheck.href === '#top', `${label}: header has logo placeholder linking to #top`, logoCheck);
  check(logoCheck.label && /King Chingaya Design/i.test(logoCheck.label), `${label}: logo placeholder has accessible home brand label`, logoCheck);

  // Section headings check: larger plain titles in order, no numbers, removed philosophy taglines absent
  const headings = await page.evaluate(() => {
    const titles = [...document.querySelectorAll('.section-title')].map((el) => el.textContent.trim());
    const removedCopy = ['grounded in people', 'considered in every detail', 'made to become your own', 'a love of people', 'a lifelong love of design'];
    const bodyText = document.body.innerText.toLowerCase();
    const foundRemoved = removedCopy.filter((c) => bodyText.includes(c));
    const numbersInSummaries = [...document.querySelectorAll('summary .row-title')].filter((el) => /\d/.test(el.textContent));
    return { titles, foundRemoved, numbersInSummaries: numbersInSummaries.length };
  });
  check(headings.titles.length === 6 && headings.titles[0] === 'Design philosophy' && headings.titles[1] === 'Gallery' && headings.titles[2] === 'About me' && headings.titles[3] === 'Working together' && headings.titles[4] === 'Services' && headings.titles[5] === 'Start a project',
    `${label}: plain section titles in page order (Design philosophy, Gallery, About me, Working together, Services, Start a project)`, headings.titles);
  check(!headings.foundRemoved.length, `${label}: removed philosophy taglines absent`, headings.foundRemoved);
  check(headings.numbersInSummaries === 0, `${label}: no numbers beside accordion row titles`);

  await checkGalleryLayout(page, label, width);

  // Scroll to document top, then capture gallery with clip from document coordinates using fullPage: true
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.waitForTimeout(150);
  await shot(page, `main-${label}`);
  const galleryBox = await page.evaluate(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
    const el = document.querySelector('#projects');
    const r = el.getBoundingClientRect();
    return { x: Math.max(0, Math.floor(r.left + window.scrollX)), y: Math.max(0, Math.floor(r.top + window.scrollY)), width: Math.ceil(r.width), height: Math.ceil(r.height) };
  });
  if (galleryBox) {
    await shot(page, `gallery-${label}`, null, { fullPage: true, clip: galleryBox });
  }

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

async function checkGalleryLayout(page, label, width) {
  const g = await geometry(page);
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

    // Text Range client rects for figcaptions (measures visible glyphs, ignoring empty padding)
    const caps = [...document.querySelectorAll('.study figcaption')];
    const capTextRects = caps.map((cap) => {
      const textRects = [];
      const walker = document.createTreeWalker(cap, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (!node.textContent.trim()) continue;
        const range = document.createRange();
        range.selectNodeContents(node);
        for (const cr of range.getClientRects()) {
          if (cr.width > 0 && cr.height > 0) textRects.push(cr);
        }
      }
      return textRects;
    });

    const captionHits = [];
    capTextRects.forEach((textRects, ci) => {
      textRects.forEach((cr) => {
        rects.forEach((ir, ii) => {
          if (ii === ci) return;
          if (cr.left < ir.right - 1 && cr.right > ir.left + 1 && cr.top < ir.bottom - 1 && cr.bottom > ir.top + 1) {
            captionHits.push({ caption: ci + 1, image: ii + 1 });
          }
        });
      });
    });

    // Caption text vs caption text collision check
    const captionCaptionHits = [];
    for (let a = 0; a < capTextRects.length; a++) {
      for (let b = a + 1; b < capTextRects.length; b++) {
        for (const r1 of capTextRects[a]) {
          for (const r2 of capTextRects[b]) {
            const w = Math.min(r1.right, r2.right) - Math.max(r1.left, r2.left);
            const h = Math.min(r1.bottom, r2.bottom) - Math.max(r1.top, r2.top);
            if (w > 0 && h > 0) {
              captionCaptionHits.push({ a: a + 1, b: b + 1 });
            }
          }
        }
      }
    }

    // Uncropped aspect check
    const aspectMatches = imgs.map((img) => {
      const renderedAspect = img.getBoundingClientRect().width / img.getBoundingClientRect().height;
      const naturalAspect = img.naturalWidth / img.naturalHeight;
      return Math.abs(renderedAspect - naturalAspect) / naturalAspect <= 0.05;
    });

    // Whitespace / varied horizontal positions on desktop
    const uniqueLefts = new Set(rects.map((r) => Math.round(r.left))).size;
    return {
      hrefs: links.map((a) => a.getAttribute('href')),
      loaded: imgs.map((i) => i.complete && i.naturalWidth > 0),
      overlaps,
      captionHits,
      captionCaptionHits,
      aspectMatches,
      uniqueLefts,
    };
  });

  check(gallery.hrefs.length === 9 && JSON.stringify(gallery.hrefs) === JSON.stringify(EXPECTED_GALLERY), `${label}: nine gallery images in order`, gallery.hrefs);
  check(gallery.loaded.every(Boolean), `${label}: nine gallery images loaded`, gallery.loaded);
  check(gallery.overlaps.every((o) => o.ratio <= 0.15), `${label}: gallery images overlap only slightly (<= 15%)`, gallery.overlaps);
  check(!gallery.captionHits.length, `${label}: no image covers another study's caption`, gallery.captionHits);
  check(!gallery.captionCaptionHits.length, `${label}: no caption covers another study's caption`, gallery.captionCaptionHits);
  check(gallery.aspectMatches.every(Boolean), `${label}: uncropped image aspect ratio preserved`, gallery.aspectMatches);
  if (width >= 768) {
    check(gallery.uniqueLefts >= 3, `${label}: varied positions and whitespace across gallery studies`, { uniqueLefts: gallery.uniqueLefts });
  }
  if (width >= 1024) {
    const cluster = await page.evaluate(() => {
      const s7 = document.querySelector('.study-7')?.getBoundingClientRect();
      const s8 = document.querySelector('.study-8')?.getBoundingClientRect();
      const s9 = document.querySelector('.study-9')?.getBoundingClientRect();
      if (!s7 || !s8 || !s9) return null;
      return {
        s7Left: s7.left, s8Left: s8.left,
        s7Top: s7.top, s8Top: s8.top,
        s9Top: s9.top, s7Bottom: s7.bottom, s8Bottom: s8.bottom,
        s9Width: s9.width, s7Width: s7.width,
        s7s8SideBySide: s7.bottom > s8.top && s8.bottom > s7.top,
        s8Offset: s8.top > s7.top,
        s9Underneath: s9.top >= Math.min(s7.bottom, s8.bottom) - 80,
      };
    });
    if (cluster) {
      check(cluster.s7s8SideBySide && cluster.s8Offset, `${label}: restaurant views (studies 7 & 8) side by side with vertical offset`, cluster);
      check(cluster.s9Underneath, `${label}: restaurant counter (study 9) positioned underneath cluster`, cluster);
    }
  }
  const captionColor = await page.evaluate(() => {
    const el = document.querySelector('.study figcaption');
    return el ? getComputedStyle(el).color : null;
  });
  check(captionColor === 'rgb(17, 17, 17)' || captionColor === 'rgb(0, 0, 0)', `${label}: gallery captions are delicate black`, captionColor);

  const arrowCheck = await page.evaluate(() => {
    const btn = document.querySelector('.image-open');
    if (!btn) return null;
    const cs = getComputedStyle(btn);
    const bg = cs.backgroundColor;
    const match = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
    const alpha = match ? (match[4] !== undefined ? parseFloat(match[4]) : 1.0) : 1.0;
    const rect = btn.getBoundingClientRect();
    const bd = cs.backdropFilter || cs.webkitBackdropFilter || '';
    const hasHeavyBlur = bd.includes('blur') && !bd.includes('blur(0');
    return {
      bg,
      alpha,
      width: rect.width,
      height: rect.height,
      hasHeavyBlur: !!hasHeavyBlur,
      fontWeight: parseInt(cs.fontWeight, 10) || 400,
    };
  });
  if (arrowCheck) {
    check(arrowCheck.alpha >= 0.25 && arrowCheck.alpha <= 0.45, `${label}: gallery arrow background is see-through (~0.30-0.40 opacity)`, arrowCheck);
    check(!arrowCheck.hasHeavyBlur, `${label}: gallery arrow heavy blur removed`, arrowCheck);
    check(arrowCheck.width >= 44 && arrowCheck.height >= 44, `${label}: gallery arrow preserves 44px hit target`, arrowCheck);
    check(arrowCheck.fontWeight <= 400, `${label}: gallery arrow preserves thin glyph`, arrowCheck);
  }

  note(label, { geometry: { scrollWidth: g.scrollWidth, clientWidth: g.clientWidth }, galleryOverlaps: gallery.overlaps });
  return gallery;
}

// 320px: narrow site checks with gallery scroll, collision checks, and top-clipping.
async function narrowSiteChecks(page, label) {
  await eagerImages(page);
  await sceneChecks(page, label);
  const studiesCount = await page.locator('.featured-studies .study').count();
  for (let i = 0; i < studiesCount; i++) {
    await page.locator('.featured-studies .study').nth(i).scrollIntoViewIfNeeded({ timeout: 5000 }).catch(() => {});
    await page.waitForTimeout(50);
  }
  await page.waitForFunction(() => {
    const studies = [...document.querySelectorAll('.featured-studies .study')];
    return studies.every((s) => s.classList.contains('is-visible') || !document.documentElement.classList.contains('motion-ready'));
  }, null, { timeout: 4000 }).catch(() => {});

  const g = await geometry(page);
  check(g.scrollWidth <= g.clientWidth, `${label}: site has no horizontal overflow`, { scrollWidth: g.scrollWidth, clientWidth: g.clientWidth });
  check(!g.smallTargets.length, `${label}: site controls are at least 44px`, g.smallTargets);
  const images = await page.evaluate(() => [...document.querySelectorAll('img[src]')].filter((i) => !(i.complete && i.naturalWidth > 0)).map((i) => i.getAttribute('src')));
  check(!images.length, `${label}: all images loaded`, images);

  await checkGalleryLayout(page, label, 320);

  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.waitForTimeout(150);
  const galleryBox = await page.evaluate(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
    const el = document.querySelector('#projects');
    const r = el.getBoundingClientRect();
    return { x: Math.max(0, Math.floor(r.left + window.scrollX)), y: Math.max(0, Math.floor(r.top + window.scrollY)), width: Math.ceil(r.width), height: Math.ceil(r.height) };
  });
  if (galleryBox) {
    await shot(page, `gallery-${label}`, null, { fullPage: true, clip: galleryBox });
  }
  await page.evaluate(() => document.querySelectorAll('.accordion details').forEach((d) => { d.open = true; }));
  const expanded = await geometry(page);
  check(expanded.scrollWidth <= expanded.clientWidth, `${label}: expanded accordions do not overflow`);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.waitForTimeout(150);
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
  note(label, { footer: f });
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
    check(await page.evaluate(() => document.querySelector('.site-header').getClientRects().length === 0), `${label}: header stays hidden while the plan has focus`);
    await shot(page, `entry-plan-focus-${label}`);
    await page.keyboard.press('Enter');
    await section(`${label}: keyboard entry`, async () => {
      await waitEntered(page);
      const s = await page.evaluate(() => ({ focus: document.activeElement.id, header: document.querySelector('.site-header').getClientRects().length > 0, title: document.querySelector('#entrance-title').getClientRects().length > 0 }));
      check(s.focus === 'main' && s.header && s.title, `${label}: Enter on .enter-plan enters, reveals header and name, and focuses #main`, s);
    });
  }
  await page.close();
}

// Step inside button is removed from entrance; entrance link is .enter-plan.
async function stepInsideChecks(context, label) {
  const page = await openPage(context);
  check(await page.evaluate(() => !document.querySelector('.enter-button')), `${label}: .enter-button removed from entrance`);
  await page.click('.enter-plan');
  await waitEntered(page);
  check(await page.evaluate(() => document.activeElement.id === 'main'), `${label}: clicking plan enters and focuses #main`);
  await page.close();
}

// Standalone floor-plan.html unlinked review artifact tested directly; external SVG aspect derives viewBox.
async function fullPlanChecks(context, label, probeDownload) {
  const planUrl = new URL('floor-plan.html', SITE_URL).href;
  const page = await context.newPage();
  await page.goto(planUrl, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready.then(() => true));
  await page.waitForFunction(() => {
    const i = document.querySelector('main#plan img, main#plan svg');
    return i && (i.complete || i.tagName.toLowerCase() === 'svg');
  }, null, { timeout: 8000 }).catch(() => {});

  const extAspect = await page.evaluate(async () => {
    try {
      const res = await fetch('assets/brand/entry-floor-plan.svg');
      const text = await res.text();
      const m = text.match(/viewBox=["']\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*["']/);
      if (m && parseFloat(m[4]) > 0) return parseFloat(m[3]) / parseFloat(m[4]);
    } catch {}
    return 1600 / 1200;
  });

  const m = await page.evaluate((svg) => {
    const vw = document.documentElement.clientWidth;
    const visible = (el) => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
    const imgs = [...document.querySelectorAll('main#plan img')].filter((i) => new URL(i.currentSrc || i.src).pathname.endsWith(svg));
    const svgs = [...document.querySelectorAll('main#plan svg')];
    const planNode = imgs[0] || svgs[0];
    const r = planNode?.getBoundingClientRect();
    const chain = [];
    for (let el = planNode; el; el = el.parentElement) {
      const s = getComputedStyle(el);
      chain.push({ tag: el.tagName, cls: el.className, transform: s.transform, rotate: s.rotate, scale: s.scale, overflow: s.overflow, rect: el.getBoundingClientRect().toJSON() });
    }
    const transformed = chain.filter((c) => c.transform !== 'none' || (c.rotate && c.rotate !== 'none') || (c.scale && c.scale !== 'none')).map((c) => c.tag);
    const clippers = chain.slice(1).filter((c) => c.overflow !== 'visible' && (c.rect.left > r.left + 1 || c.rect.right < r.right - 1 || c.rect.top > r.top + 1 || c.rect.bottom < r.bottom - 1)).map((c) => `${c.tag}.${c.cls}`);
    const links = [...document.querySelectorAll('a')].map((a) => ({ href: a.getAttribute('href'), download: a.getAttribute('download'), cls: a.className, text: a.textContent.trim(), visible: visible(a) }));
    const noteText = document.querySelector('main .plan-note')?.textContent || document.querySelector('main')?.textContent || '';
    return {
      count: imgs.length + svgs.length,
      loaded: planNode ? (planNode.tagName.toLowerCase() === 'svg' || (planNode.complete && planNode.naturalWidth > 0)) : false,
      naturalWidth: imgs[0]?.naturalWidth ?? null,
      naturalHeight: imgs[0]?.naturalHeight ?? null,
      alt: planNode?.getAttribute('alt') || '',
      objectFit: planNode ? getComputedStyle(planNode).objectFit : null,
      width: r?.width,
      height: r?.height,
      left: r?.left,
      right: r?.right,
      clientWidth: vw,
      scrollWidth: document.documentElement.scrollWidth,
      transformed,
      clippers,
      h1: document.querySelector('h1')?.textContent.trim(),
      dimensionedConcept: /dimensioned(?:\s+architectural)?\s+concept/i.test(noteText),
      reviewsPending: /reviews?\s+pending/i.test(noteText),
      noComplianceClaim: !/certified(?:\s+code)?\s+complian(?:ce|t)|guaranteed\s+code/i.test(noteText),
      returnLinks: links.filter((a) => (a.href === 'index.html#main' || a.href?.endsWith('index.html#main')) && a.visible),
      planReturn: links.some((a) => /\bplan-return\b/.test(a.cls) && a.visible && a.text.includes('Return to site')),
      downloads: links.filter((a) => a.download !== null && (a.href || '').endsWith('entry-floor-plan.svg') && a.visible),
      openLinks: links.filter((a) => a.download === null && (a.href || '').endsWith('entry-floor-plan.svg') && a.visible),
      scripts: document.querySelectorAll('script').length,
    };
  }, PLAN_SVG);
  note(label, { fullPlan: m });
  check(m.count === 1 && m.loaded, `${label}: full plan loads once on floor-plan.html`, m);
  check(m.width > 0 && Math.abs(m.width / m.height - extAspect) <= 0.02 * extAspect, `${label}: full plan keeps its natural viewBox aspect ratio`, { width: m.width, height: m.height, aspect: m.width / m.height, expected: extAspect });
  check(!m.transformed.length, `${label}: full plan is not rotated or transformed`, m.transformed);
  check(!m.clippers.length && m.left >= -1 && m.right <= m.clientWidth + 1, `${label}: full plan is uncropped and fully within the page width`, { clippers: m.clippers, left: m.left, right: m.right, clientWidth: m.clientWidth });
  check(m.width >= 0.6 * m.clientWidth, `${label}: full plan is shown large`, { width: m.width, clientWidth: m.clientWidth });
  check(m.scrollWidth <= m.clientWidth, `${label}: full-plan page has no horizontal overflow`, { scrollWidth: m.scrollWidth, clientWidth: m.clientWidth });
  check(m.h1 === 'Conceptual floor plan' && m.dimensionedConcept && m.reviewsPending && m.noComplianceClaim, `${label}: full-plan page is titled, described as a dimensioned concept without certified compliance claims`, { h1: m.h1, dimensionedConcept: m.dimensionedConcept, reviewsPending: m.reviewsPending, noComplianceClaim: m.noComplianceClaim });
  check(m.planReturn && m.returnLinks.length >= 1, `${label}: full-plan page has visible return-to-site links`, m.returnLinks);
  check(m.downloads.length >= 1 && m.openLinks.length >= 1, `${label}: full-plan page offers download and open-on-its-own links`, { downloads: m.downloads, open: m.openLinks });
  check(m.scripts === 0, `${label}: full-plan page runs no scripts`);
  const g = await geometry(page);
  check(!g.smallTargets.length && !g.brokenAnchors.length, `${label}: full-plan page targets are at least 44px and anchors resolve`, { small: g.smallTargets, broken: g.brokenAnchors });
  await shot(page, `full-plan-${label}`, null, { fullPage: true });
  if (probeDownload) {
    const response = await page.request.get(new URL('assets/brand/entry-floor-plan.svg', page.url()).href);
    check(response.ok() && /svg/.test(response.headers()['content-type'] || ''), 'full plan: the SVG review artifact is served for download', { status: response.status(), type: response.headers()['content-type'] });
  }
  await Promise.all([page.waitForURL(/\/index\.html#main$/, { timeout: 8000 }), page.locator('.plan-return').first().click()]);
  await page.waitForLoadState('load');
  await section(`${label}: return from full plan`, async () => {
    await waitEntered(page);
    check(await page.evaluate(() => document.activeElement.id === 'main' && document.querySelector('.site-header').getClientRects().length > 0), `${label}: Return to site lands in main, past the entrance`);
  });
  await page.close();
}

async function lightboxChecks(page, label, exhaustiveKeyboard) {
  await revealStudies(page);
  const first = page.locator('[data-lightbox]').first();
  await first.scrollIntoViewIfNeeded();
  await first.click();
  const count = () => page.evaluate(() => document.querySelector('#viewer-count').textContent.trim());
  const viewerState = () => page.evaluate(() => {
    const i = document.querySelector('#viewer-image');
    const stage = document.querySelector('.viewer-stage');
    const overlay = stage?.querySelector('svg.scene-overlay.viewer-scene');
    const actors = overlay ? [...overlay.querySelectorAll('g.scene-actor')] : [];
    const ids = overlay ? [...overlay.querySelectorAll('[id]')].map((el) => el.id) : [];
    const clipRefs = overlay ? [...overlay.querySelectorAll('[clip-path]')].map((el) => el.getAttribute('clip-path')) : [];
    const vb = overlay?.viewBox?.baseVal;
    return {
      src: i?.getAttribute('src'),
      loaded: i ? i.complete && i.naturalWidth > 0 : false,
      alt: i?.alt || '',
      hasOverlay: !!overlay,
      sceneId: overlay?.getAttribute('data-scene'),
      aspect: overlay?.getAttribute('preserveAspectRatio'),
      active: overlay?.classList.contains('scene-active'),
      ariaHidden: overlay?.getAttribute('aria-hidden'),
      viewBox: vb ? [vb.x, vb.y, vb.width, vb.height] : null,
      actorCount: actors.length,
      allIdsPrefixed: ids.length > 0 ? ids.every((id) => id.startsWith('viewer-')) : true,
      allClipsPrefixed: clipRefs.length > 0 ? clipRefs.every((ref) => /^url\(#viewer-[\w-]+\)$/.test(ref)) : true,
    };
  });
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
    const expectedScene = SCENE_BY_ID[`study-${n}`];
    check(await count() === `${n} / 9` && state.src === EXPECTED_GALLERY[n - 1] && state.loaded && state.alt.trim().length > 0, `${label}: viewer shows study ${n} / 9`, { count: await count(), ...state });
    check(state.hasOverlay && state.sceneId === `study-${n}`, `${label}: viewer study ${n} has cloned scene overlay for study-${n}`, { hasOverlay: state.hasOverlay, sceneId: state.sceneId });
    check(state.aspect === 'xMidYMid meet' && state.ariaHidden === 'true' && state.active, `${label}: viewer study ${n} overlay uses xMidYMid meet, aria-hidden, and scene-active`, { aspect: state.aspect, ariaHidden: state.ariaHidden, active: state.active });
    check(state.actorCount === expectedScene.actors.length, `${label}: viewer study ${n} overlay has ${expectedScene.actors.length} actors`, { actors: state.actorCount });
    check(state.allIdsPrefixed && state.allClipsPrefixed, `${label}: viewer study ${n} clip IDs rewritten with viewer- prefix without collision`, { allIds: state.allIdsPrefixed, allClips: state.allClipsPrefixed });
  }
  await page.click('#viewer-next');
  check(await count() === '1 / 9', `${label}: Next from 9 wraps to 1 (after full pass)`, await count());
  await page.keyboard.press('Escape');
  await page.waitForTimeout(150);
  const closedCheck = await page.evaluate(() => ({
    open: document.querySelector('#study-viewer').open,
    leftoverOverlays: document.querySelectorAll('.viewer-stage .scene-overlay').length,
    focusedOpener: document.activeElement === document.querySelector('[data-lightbox]'),
  }));
  check(!closedCheck.open && closedCheck.leftoverOverlays === 0 && closedCheck.focusedOpener, `${label}: Escape closes viewer, removes cloned overlay, and restores focus to opener`, closedCheck);

  if (exhaustiveKeyboard) {
    for (let n = 1; n <= 9; n++) {
      const link = page.locator('[data-lightbox]').nth(n - 1);
      await link.focus();
      await page.keyboard.press('Enter');
      await page.waitForFunction(() => document.querySelector('#study-viewer').open, null, { timeout: 3000 }).catch(() => {});
      const openState = await viewerState();
      check(await count() === `${n} / 9` && openState.hasOverlay && openState.sceneId === `study-${n}` && openState.active, `${label}: study ${n} opens from the keyboard with replaying scene overlay`, { count: await count(), ...openState });
      await page.keyboard.press('Escape');
      await page.waitForTimeout(100);
      const keyboardClosed = await page.evaluate((i) => ({
        open: document.querySelector('#study-viewer').open,
        leftover: document.querySelectorAll('.viewer-stage .scene-overlay').length,
        focused: document.activeElement === document.querySelectorAll('[data-lightbox]')[i],
      }), n - 1);
      check(!keyboardClosed.open && keyboardClosed.leftover === 0 && keyboardClosed.focused, `${label}: focus returns to study ${n} and cloned overlay removed`);
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

// Snapshot of the brand animations (growth and bloom) on the entered page.
const brandAnimations = (page) => page.evaluate(() => document.getAnimations()
  .filter((a) => ['vine-grow', 'cluster-bloom'].includes(a.animationName))
  .map((a) => {
    const el = a.effect.target, timing = a.effect.getTiming(), r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return {
      name: a.animationName, cls: String(el.className), state: a.playState, delay: Number(timing.delay) || 0, duration: Number(timing.duration) || 0,
      current: a.currentTime == null ? null : Number(a.currentTime), clip: s.clipPath, opacity: Number(s.opacity), centerX: r.left + r.width / 2,
    };
  }));

try {
  await mkdir(output, { recursive: true });
  const chromium = await loadPlaywright();
  browser = await chromium.launch({ headless: true, chromiumSandbox: true, ...(process.env.BROWSER_PATH ? { executablePath: process.env.BROWSER_PATH } : {}) });
  report.browser = `${browser.browserType().name()} ${browser.version()}`;
  console.log(`Probing ${SITE_URL} with ${report.browser} (sandboxed)`);

  for (const vp of VIEWPORTS) {
    const label = `${vp.width}x${vp.height}`;
    const context = await newContext({ viewport: vp });
    await section(label, async () => {
      const page = await openPage(context);
      await page.waitForFunction(() => {
        const el = document.querySelector('.enter-plan .floor-plan');
        return el ? (el.tagName.toLowerCase() === 'svg' || el.complete) : true;
      }, null, { timeout: 8000 }).catch(() => {});
      await ctaFirstScreenCheck(page, label);
      await entryChecks(page, label);
      if (vp.width >= 1024) await enterCursorChecks(page, label);
      await shot(page, `entry-${label}`);
      await page.click('.enter-plan');
      await waitEntered(page);
      check(await page.evaluate(() => document.activeElement.id === 'main' && !document.documentElement.classList.contains('entry-active')), `${label}: mouse click on floor plan enters the site`);
      await afterEntryChecks(page, label);
      await settleBrand(page);
      await brandChecks(page, label);
      await shot(page, `brand-${label}`, page.locator('#brand'));
      if (vp.width === 320) await narrowSiteChecks(page, label);
      else await siteChecks(page, label, vp.width);
      if ([1440, 390, 320].includes(vp.width)) await footerChecks(page, label);
      if (vp.width === 1440 || vp.width === 390) await lightboxChecks(page, label, vp.width === 1440);
      await page.close();
    });
    await section(`${label} keyboard`, () => keyboardEntry(context, label));
    if (vp.width === 1024 || vp.width === 390) await section(`${label} Step inside`, () => stepInsideChecks(context, label));
    await section(`${label} full plan`, () => fullPlanChecks(context, label, vp.width === 1440));
    await context.close();
  }

  await section('hash navigation', async () => {
    const context = await newContext({ viewport: { width: 1024, height: 768 } });
    const deep = await openPage(context, '#projects');
    const d = await deep.evaluate(() => ({ entered: !document.querySelector('#main').hidden && document.querySelector('#entrance').hidden, focus: document.activeElement.id, header: document.querySelector('.site-header').getClientRects().length > 0 }));
    check(d.entered && d.focus === 'projects' && d.header, 'hash: deep link to #projects skips the entrance and focuses the section', d);
    await deep.close();
    const top = await openPage(context, '#top');
    check(await top.evaluate(() => document.documentElement.classList.contains('entry-active') && document.querySelector('#main').hidden), 'hash: #top shows the plan-only entrance');
    await top.evaluate(() => { location.hash = '#about'; });
    await waitEntered(top);
    check(await top.evaluate(() => document.activeElement.id === 'about'), 'hash: a hash change on the entrance enters the site at that section');
    await top.close();
    await context.close();
  });

  await section('touch context: no custom cursor', async () => {
    const context = await newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
    const page = await openPage(context);
    const planBox = await page.locator('.enter-plan').boundingBox();
    if (planBox) {
      await page.mouse.move(planBox.x + planBox.width / 2, planBox.y + planBox.height / 2);
      await page.waitForTimeout(50);
    }
    const touchState = await page.evaluate(() => {
      const cursor = document.querySelector('.enter-cursor');
      const entrance = document.querySelector('#entrance');
      const plan = document.querySelector('.enter-plan');
      return {
        entranceHasLive: entrance?.classList.contains('cursor-live'),
        cursorDisplay: cursor ? getComputedStyle(cursor).display : null,
        planCursor: plan ? getComputedStyle(plan).cursor : null,
      };
    });
    check(!touchState.entranceHasLive && touchState.cursorDisplay === 'none', 'touch context: no replacement cursor shown on touch devices', touchState);
    check(touchState.planCursor !== 'none', 'touch context: native cursor retained on touch devices', touchState);
    await context.close();
  });

  await section('alternative entry: keys, wheel, swipe', async () => {
    const context = await newContext({ viewport: { width: 1024, height: 768 } });

    // ArrowDown entry
    const keyPage = await openPage(context);
    await keyPage.keyboard.press('ArrowDown');
    await waitEntered(keyPage);
    check(await keyPage.evaluate(() => document.activeElement.id === 'main'), 'entry: ArrowDown enters and focuses #main');
    await keyPage.close();

    // Wheel entry
    const wheelPage = await openPage(context);
    await wheelPage.mouse.wheel(0, 100);
    await waitEntered(wheelPage);
    check(await wheelPage.evaluate(() => document.activeElement.id === 'main'), 'entry: wheel scroll enters and focuses #main');
    await wheelPage.close();

    // Touch swipe entry in dedicated touch context with valid Touch objects
    const touchContext = await newContext({ viewport: { width: 1024, height: 768 }, hasTouch: true });
    const swipePage = await openPage(touchContext);
    await swipePage.evaluate(() => {
      const target = document.body;
      const t1 = new Touch({ identifier: 1, target, clientX: 100, clientY: 200, pageX: 100, pageY: 200, screenX: 100, screenY: 200 });
      const t2 = new Touch({ identifier: 1, target, clientX: 100, clientY: 100, pageX: 100, pageY: 100, screenX: 100, screenY: 100 });
      window.dispatchEvent(new TouchEvent('touchstart', { touches: [t1], targetTouches: [t1], changedTouches: [t1], bubbles: true, cancelable: true }));
      window.dispatchEvent(new TouchEvent('touchmove', { touches: [t2], targetTouches: [t2], changedTouches: [t2], bubbles: true, cancelable: true }));
    });
    await waitEntered(swipePage);
    check(await swipePage.evaluate(() => document.activeElement.id === 'main'), 'entry: touch swipe enters and focuses #main');
    await swipePage.close();
    await touchContext.close();

    await context.close();
  });

  await section('motion: staged plan reveal and finite vine growth', async () => {
    const context = await newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'no-preference' });
    const page = await openPage(context);

    // Staged floor plan animation checks on the entrance screen
    const stagedCheck = await page.evaluate(async () => {
      const plan = document.querySelector('.floor-plan');
      const shell = plan?.querySelector('.plan-shell');
      const fixtures = plan?.querySelector('.plan-fixtures');
      const furniture = plan?.querySelector('.plan-furniture');
      if (!shell || !fixtures || !furniture) {
        return { hasStages: false };
      }
      // Sample 1: immediate / ~100ms
      const s1Shell = parseFloat(getComputedStyle(shell).opacity);
      const s1Fixtures = parseFloat(getComputedStyle(fixtures).opacity);
      const s1Furniture = parseFloat(getComputedStyle(furniture).opacity);

      // Sample 2: at ~1000ms (after .55s fixtures delay, before 1.65s furniture delay)
      await new Promise((r) => setTimeout(r, 900));
      const s2Shell = parseFloat(getComputedStyle(shell).opacity);
      const s2Fixtures = parseFloat(getComputedStyle(fixtures).opacity);
      const s2Furniture = parseFloat(getComputedStyle(furniture).opacity);

      // Sample 3: at ~2600ms (after all stages finish, within 4.5s)
      await new Promise((r) => setTimeout(r, 1600));
      const s3Shell = parseFloat(getComputedStyle(shell).opacity);
      const s3Fixtures = parseFloat(getComputedStyle(fixtures).opacity);
      const s3Furniture = parseFloat(getComputedStyle(furniture).opacity);

      return {
        hasStages: true,
        s1: { shell: s1Shell, fixtures: s1Fixtures, furniture: s1Furniture },
        s2: { shell: s2Shell, fixtures: s2Fixtures, furniture: s2Furniture },
        s3: { shell: s3Shell, fixtures: s3Fixtures, furniture: s3Furniture },
      };
    });

    if (stagedCheck.hasStages) {
      check(stagedCheck.s1.shell >= 0.9 && stagedCheck.s1.fixtures <= 0.1 && stagedCheck.s1.furniture <= 0.1,
        'staged plan: walls/trees visible at start, fixtures and furniture wait', stagedCheck.s1);
      check(stagedCheck.s2.shell >= 0.9 && stagedCheck.s2.fixtures >= 0.5 && stagedCheck.s2.furniture <= 0.1,
        'staged plan: fixtures revealed after .55s, furniture still waits', stagedCheck.s2);
      check(stagedCheck.s3.shell >= 0.9 && stagedCheck.s3.fixtures >= 0.9 && stagedCheck.s3.furniture >= 0.9,
        'staged plan: all stages fully visible and settled within 4.5s', stagedCheck.s3);
    } else {
      // Inline SVG with stages pending generator; verify CSS rules match stage group names
      const cssRules = await page.evaluate(() => {
        const text = [...document.styleSheets].flatMap((s) => {
          try { return [...s.cssRules].map((r) => r.cssText); } catch { return []; }
        }).join('\n');
        return {
          fixtures: text.includes('.plan-fixtures') && text.includes('0.55s'),
          furniture: text.includes('.plan-furniture') && text.includes('1.65s'),
        };
      });
      check(cssRules.fixtures && cssRules.furniture, 'staged plan: CSS defines staged delays for .plan-fixtures (.55s) and .plan-furniture (1.65s)', cssRules);
    }

    // Now enter the site to test vine growth
    await page.click('.enter-plan');
    await waitEntered(page);
    const s0 = await brandAnimations(page);
    const clusterCount = await page.locator('.brand-band .vine-cluster').count();
    const grow = s0.filter((a) => a.name === 'vine-grow');
    const bloom = s0.filter((a) => a.name === 'cluster-bloom');
    report.motion = { initial: s0, clusterCount };
    check(grow.length >= 1 && grow.every((a) => a.cls.includes('vine-strand') && ['running', 'pending'].includes(a.state)), 'motion: vine growth runs on the strand after entry', grow);
    check(grow.every((a) => a.duration >= 1000), 'motion: growth is gradual (>= 1s)', grow.map((a) => a.duration));
    check(clusterCount >= 1 && bloom.length === clusterCount, 'motion: every flower cluster has a bloom animation', { clusters: clusterCount, blooms: bloom.length });

    // Wait for brand animations to settle (bounded, <= 4.5s)
    await settleBrand(page);
    const settled = await page.evaluate(() => {
      const anims = document.getAnimations();
      const infinite = anims.filter((a) => a.effect?.getTiming()?.iterations === Infinity);
      const running = anims.filter((a) => a.playState === 'running');
      const strands = [...document.querySelectorAll('.brand-band .vine-strand')].map((el) => getComputedStyle(el).clipPath);
      const opacities = [...document.querySelectorAll('.brand-band .vine-cluster')].map((el) => Number(getComputedStyle(el).opacity));
      return {
        infiniteCount: infinite.length,
        runningCount: running.length,
        strandsFullyRevealed: strands.every((c) => c === 'none' || /^inset\(0(?:px|%)?(?:\s+0(?:px|%)?){0,3}\)$/.test(c)),
        clustersVisible: opacities.every((o) => o > 0.99),
      };
    });
    check(settled.infiniteCount === 0, 'motion: no infinite animations once settled');
    check(settled.strandsFullyRevealed && settled.clustersVisible, 'motion: growth ends with whole vine and all clusters visible', settled);
    await shot(page, 'brand-grown-1440x900', page.locator('#brand'));
    await context.close();
  });

  // Scene people: hero walk and chat sequence (Feedback 1 revision, 3 October 2026).
  // Nathan and Carla walk INTO the backyard during the first half (move_until: 0.5, first half of each finite take),
  // then complete turning steps and a foot-planted sit inside the sprite while CSS travel holds.
  // Verified with observer trigger, first-half travel, second-half stationary chat, hidden-page pause/resume,
  // finite finish <= 8.8s, 3 hero timepoint screenshots, and the 9 gallery scene screenshots.
  await section('motion: hero walk and chat sequence', async () => {
    const context = await newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'no-preference' });
    const page = await openPage(context);
    await page.click('.enter-plan');
    await waitEntered(page);
    await settleBrand(page);

    const before = await page.evaluate(async () => {
      window.scrollTo({ top: 0, behavior: 'instant' });
      await new Promise((r) => setTimeout(r, 300));
      const stage = document.querySelector('.hero-image-stage');
      const overlay = stage?.querySelector('svg.scene-overlay');
      const r = stage.getBoundingClientRect();
      const vh = window.innerHeight;
      const visible = Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0));
      const actors = overlay ? [...overlay.querySelectorAll('g.scene-actor')] : [];
      return {
        active: overlay?.classList.contains('scene-active') || false,
        visibleRatio: r.height ? visible / r.height : 0,
        stageTop: r.top,
        vh,
        transforms: actors.map((a) => ({
          move: getComputedStyle(a.querySelector('.actor-move')).transform,
          frames: getComputedStyle(a.querySelector('.actor-frames')).transform,
        })),
        sceneAnimations: document.querySelector('.hero-image-stage .scene-overlay').getAnimations({subtree:true}).filter((a) => /^scene-/.test(a.animationName)).length,
      };
    });
    check(before.visibleRatio < 0.15, 'hero motion: at the top of the entered page the stage is below the observer threshold (precondition)', before);
    check(!before.active && before.transforms.every((t) => t.move === 'none' && t.frames === 'none') && before.sceneAnimations === 0,
      'hero motion: scene actors wait static on first frame at start position until stage intersects (no entry-time or timer trigger)', before);

    // Scroll stage into view to trigger observer
    await page.evaluate(() => {
      const stage = document.querySelector('.hero-image-stage');
      stage.scrollIntoView({ block: 'center', behavior: 'instant' });
    });

    // Wait until .scene-active is added
    const started = await page.evaluate(async () => {
      const stage = document.querySelector('.hero-image-stage');
      const overlay = stage.querySelector('svg.scene-overlay');
      const t0 = performance.now();
      while (!overlay.classList.contains('scene-active') && performance.now() - t0 < 2000) {
        await new Promise((r) => setTimeout(r, 50));
      }
      const waited = Math.round(performance.now() - t0);
      const travelAnims = document.querySelector('.hero-image-stage .scene-overlay').getAnimations({subtree:true}).filter((a) => a.animationName === 'scene-travel');
      const framesAnims = document.querySelector('.hero-image-stage .scene-overlay').getAnimations({subtree:true}).filter((a) => a.animationName === 'scene-frames');
      return {
        active: overlay.classList.contains('scene-active'),
        waited,
        travelCount: travelAnims.length,
        framesCount: framesAnims.length,
        travelStates: travelAnims.map((a) => a.playState),
        framesStates: framesAnims.map((a) => a.playState),
        travelTimings: travelAnims.map((a) => ({
          duration: Number(a.effect.getTiming().duration),
          delay: Number(a.effect.getTiming().delay) || 0,
          iterations: a.effect.getTiming().iterations,
        })),
        framesTimings: framesAnims.map((a) => ({
          duration: Number(a.effect.getTiming().duration),
          delay: Number(a.effect.getTiming().delay) || 0,
          iterations: a.effect.getTiming().iterations,
        })),
      };
    });
    check(started.active && started.waited < 2000, 'hero motion: IntersectionObserver adds scene-active when hero scrolls into view', started);
    check(started.travelCount === 2 && started.framesCount === 2 && started.travelStates.every((s) => s === 'running') && started.framesStates.every((s) => s === 'running'),
      'hero motion: scene-travel and scene-frames animations running on both actors', started);
    check(started.travelTimings.every((t,i) => Math.abs(t.duration-SCENES.scenes[0].actors[i].duration*500)<1 && t.iterations === 1) && started.framesTimings.every((t,i) => Math.abs(t.duration-SCENES.scenes[0].actors[i].duration*1000)<1 && t.iterations === 1),
      'hero motion: each actor follows its own finite walk and full-take timing', started);

    // Capture t0
    await shot(page, 'hero-scene-t0', page.locator('.hero-image-stage'));

    await page.waitForTimeout(700); // let both staggered actors begin before comparing advancing frames
    // First half: movement and frames both advance
    const firstHalfMotion = await page.evaluate(async () => {
      const stage = document.querySelector('.hero-image-stage');
      const actors = [...stage.querySelectorAll('svg.scene-overlay g.scene-actor')];
      const sample = () => actors.map((a) => ({
        move: getComputedStyle(a.querySelector('.actor-move')).transform,
        frames: getComputedStyle(a.querySelector('.actor-frames')).transform,
      }));
      const t1 = sample();
      await new Promise((r) => setTimeout(r, 500));
      const t2 = sample();
      return {
        t1,
        t2,
        movesChanged: t1.every((s, i) => s.move !== t2[i].move),
        framesChanged: t1.every((s, i) => s.frames !== t2[i].frames),
      };
    });
    check(firstHalfMotion.movesChanged && firstHalfMotion.framesChanged,
      'hero motion: during the first half (walk into backyard), both position and sprite frames advance over time', firstHalfMotion);

    // Test visibilitychange: hiding the page pauses the animations in place, restoring resumes
    const paused = await page.evaluate(async () => {
      const getAnims = () => document.querySelector('.hero-image-stage .scene-overlay').getAnimations({subtree:true}).filter((a) => /^scene-/.test(a.animationName));
      Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
      document.dispatchEvent(new Event('visibilitychange'));
      await new Promise((r) => setTimeout(r, 100));
      const hiddenClass = document.documentElement.classList.contains('document-hidden');
      const animsHidden = getAnims();
      const statesHidden = animsHidden.map((a) => a.playState);
      const timesHidden = animsHidden.map((a) => Number(a.currentTime));
      await new Promise((r) => setTimeout(r, 400));
      const timesHiddenLater = getAnims().map((a) => Number(a.currentTime));
      delete document.hidden;
      document.dispatchEvent(new Event('visibilitychange'));
      await new Promise((r) => setTimeout(r, 100));
      const animsRestored = getAnims();
      const statesRestored = animsRestored.map((a) => a.playState);
      const timesRestored = animsRestored.map((a) => Number(a.currentTime));
      return {
        hiddenClass,
        statesHidden,
        timesHidden,
        timesHiddenLater,
        restoredClass: document.documentElement.classList.contains('document-hidden'),
        statesRestored,
        timesRestored,
        pausedInPlace: timesHidden.every((t, i) => Math.abs(timesHiddenLater[i] - t) < 50),
        resumedSameTime: timesRestored.every((t, i) => t >= timesHidden[i] - 1),
      };
    });
    check(paused.hiddenClass && paused.statesHidden.every((s) => s === 'paused') && paused.pausedInPlace,
      'hero motion: hiding the page pauses travel and sprite animations in place', paused);
    check(!paused.restoredClass && paused.statesRestored.every((s) => s === 'running') && paused.resumedSameTime,
      'hero motion: restoring the page resumes the animations where they paused (no restart)', paused);

    // Wait until travel finishes
    await page.evaluate(async () => {
      const travels = document.querySelector('.hero-image-stage .scene-overlay').getAnimations({subtree:true}).filter((a) => a.animationName === 'scene-travel');
      await Promise.race([Promise.all(travels.map((a) => a.finished.catch(() => null))), new Promise((r) => setTimeout(r, 4000))]);
    });

    // Capture t2200 (arrival at chat spot / turn)
    await shot(page, 'hero-scene-t2200', page.locator('.hero-image-stage'));

    // Second half: actors have stopped (ZERO position change), but chat frames continue to change
    const secondHalfChat = await page.evaluate(async () => {
      const stage = document.querySelector('.hero-image-stage');
      const actors = [...stage.querySelectorAll('svg.scene-overlay g.scene-actor')];
      const sample = () => actors.map((a) => ({
        move: getComputedStyle(a.querySelector('.actor-move')).transform,
        frames: getComputedStyle(a.querySelector('.actor-frames')).transform,
      }));
      const t3 = sample();
      await new Promise((r) => setTimeout(r, 600));
      const t4 = sample();
      const travelAnims = document.querySelector('.hero-image-stage .scene-overlay').getAnimations({subtree:true}).filter((a) => a.animationName === 'scene-travel');
      const framesAnims = document.querySelector('.hero-image-stage .scene-overlay').getAnimations({subtree:true}).filter((a) => a.animationName === 'scene-frames');
      return {
        t3,
        t4,
        travelFinished: travelAnims.every((a) => a.playState === 'finished'),
        framesRunning: framesAnims.some((a) => a.playState === 'running'),
        movesEqual: t3.every((s, i) => s.move === t4[i].move),
        framesChanged: t3.every((s, i) => s.frames !== t4[i].frames),
      };
    });
    check(secondHalfChat.movesEqual, 'hero motion: during the second half the actors hold position (ZERO position change after arrival)', secondHalfChat);
    check(secondHalfChat.framesChanged, 'hero motion: during the second half the sprite frames continue to change (turn and sit)', secondHalfChat);

    // Wait for all scene animations to finish (total <= 8.8s active time)
    const done = await page.evaluate(async ({ SCENE_SPECS, METAS }) => {
      const all = document.querySelector('.hero-image-stage .scene-overlay').getAnimations({subtree:true}).filter((a) => /^scene-/.test(a.animationName));
      await Promise.race([Promise.all(all.map((a) => a.finished.catch(() => null))), new Promise((r) => setTimeout(r, 6000))]);
      const stage = document.querySelector('.hero-image-stage');
      const overlay = stage.querySelector('svg.scene-overlay');
      const actors = [...overlay.querySelectorAll('g.scene-actor')];
      const actorData = actors.map((g) => {
        const aid = g.getAttribute('data-actor');
        const spec = SCENE_SPECS.actors.find((a) => a.id === aid);
        const meta = METAS[spec.strip];
        const moveMatrix = getComputedStyle(g.querySelector('.actor-move')).transform.match(/^matrix\(([^)]+)\)$/);
        const moveParts = moveMatrix ? moveMatrix[1].split(',').map(Number) : null;
        const framesMatrix = getComputedStyle(g.querySelector('.actor-frames')).transform.match(/^matrix\(([^)]+)\)$/);
        const framesParts = framesMatrix ? framesMatrix[1].split(',').map(Number) : null;
        const expectedRest = -(meta.frame_count - 1) * meta.frame_width;
        return {
          aid,
          person: g.getAttribute('data-person'),
          actualMove: moveParts ? { x: moveParts[4], y: moveParts[5] } : null,
          expectedMove: { x: spec.travel[0], y: spec.travel[1] },
          actualRestX: framesParts ? framesParts[4] : null,
          expectedRestX: expectedRest,
        };
      });
      return {
        active: overlay.classList.contains('scene-active'),
        states: all.map((a) => {
          const t = a.effect.getTiming();
          return { name: a.animationName, state: a.playState, iterations: Number(t.iterations), duration: Number(t.duration) };
        }),
        actorData,
      };
    }, { SCENE_SPECS: SCENE_BY_ID['study-1'], METAS: STRIP_METAS });

    check(done.active, 'hero motion: scene-active remains set once triggered (no re-trigger)', done.active);
    check(done.states.length >= 4 && done.states.every((s) => s.state === 'finished' && s.iterations === 1 && s.duration <= 8800),
      'hero motion: every scene animation finishes within 8.8s with iterations: 1', done.states);
    check(done.actorData.every((a) => a.actualMove && Math.abs(a.actualMove.x - a.expectedMove.x) < 1 && Math.abs(a.actualMove.y - a.expectedMove.y) < 1),
      'hero motion: actors rest at their final backyard positions (--tx, --ty)', done.actorData);
    check(done.actorData.every((a) => a.actualRestX !== null && Math.abs(a.actualRestX - a.expectedRestX) < 1),
      'hero motion: actors rest on their last frame (seated rest pose)', done.actorData);

    // Capture t4400 (final settled chat pose)
    await shot(page, 'hero-scene-t4400', page.locator('.hero-image-stage'));

    // Capture the 9 gallery study scene figures
    for (let i = 1; i <= 9; i++) {
      const studyImage = page.locator(`.study.study-${i} .study-image`);
      await studyImage.scrollIntoViewIfNeeded();
      await page.waitForTimeout(50);
      await shot(page, `scene-study-${i}`, studyImage);
    }

    await context.close();
  });

  await section('scene pacing and visibility', async () => {
    const context = await newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'no-preference' });
    const page = await openPage(context);
    await page.click('.enter-plan'); await waitEntered(page);
    const study = page.locator('.study-7 .study-image');
    await study.scrollIntoViewIfNeeded(); await page.waitForTimeout(850);
    const sample = () => page.evaluate(() => {
      const overlay = document.querySelector('.study-7 .scene-overlay');
      return { paused: overlay.classList.contains('scene-paused'), active: overlay.classList.contains('scene-active'),
        animations: overlay.getAnimations({subtree:true}).map(a=>({name:a.animationName,time:a.currentTime,state:a.playState,delay:a.effect.getTiming().delay,duration:a.effect.getTiming().duration})) };
    });
    const visible=await sample();
    check(visible.active && !visible.paused && visible.animations.every(a=>a.state==='running'), 'scene visibility: visible café take starts and runs',visible);
    const frames=visible.animations.filter(a=>a.name==='scene-frames');
    check(frames.length===2 && frames[0].delay!==frames[1].delay && frames[0].duration!==frames[1].duration && frames.every(a=>a.delay+a.duration<=8801), 'scene pacing: café actors have distinct starts and durations with a finite shared budget',frames);
    await page.locator('footer').scrollIntoViewIfNeeded(); await page.waitForTimeout(300);
    const hidden=await sample(); await page.waitForTimeout(250); const held=await sample();
    check(hidden.paused && held.animations.every((a,i)=>a.state==='paused' && Math.abs(a.time-hidden.animations[i].time)<30), 'scene visibility: offscreen take pauses in place', {hidden,held});
    await study.scrollIntoViewIfNeeded();
    // Wait for an actual composited advance after the observer resumes playback.
    await page.waitForFunction(times => {
      const overlay=document.querySelector('.study-7 .scene-overlay');
      const animations=overlay.getAnimations({subtree:true});
      return !overlay.classList.contains('scene-paused') && animations.length===times.length &&
        animations.every((a,i)=>a.playState==='running' && a.currentTime>times[i]);
    }, held.animations.map(a=>a.time), {timeout:2000});
    const resumed=await sample();
    check(!resumed.paused && resumed.animations.every((a,i)=>a.state==='running' && a.time>held.animations[i].time && a.time-held.animations[i].time<700), 'scene visibility: returning resumes without restarting', {held,resumed});
    await study.click(); await page.waitForTimeout(150);
    const covered=await sample();
    const viewer=await page.evaluate(()=>({paused:document.querySelector('.viewer-scene').classList.contains('scene-paused'),states:document.querySelector('.viewer-scene').getAnimations({subtree:true}).map(a=>a.playState)}));
    check(covered.animations.every(a=>a.state==='paused') && !viewer.paused && viewer.states.every(s=>s==='running'), 'scene visibility: lightbox pauses the covered gallery while its clone plays', {covered,viewer});
    await page.keyboard.press('Escape'); await page.waitForTimeout(100);
    check((await sample()).animations.every(a=>a.state==='running'), 'scene visibility: closing lightbox resumes the gallery take');
    await context.close();
  });

  await section('motion: reduced', async () => {
    const context = await newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
    const page = await openPage(context);
    const entry = await page.evaluate(() => ({
      running: document.getAnimations().filter((a) => a.playState === 'running').length,
      motionReady: document.documentElement.classList.contains('motion-ready'),
      header: document.querySelector('.site-header').getClientRects().length > 0,
    }));
    check(entry.running === 0 && !entry.motionReady, 'motion: reduced-motion entrance has no animation and no motion class', entry);
    check(!entry.header, 'motion: reduced-motion entrance still hides the header', entry);

    // Verify custom cursor is hidden under reduced motion
    const cursorReduced = await page.evaluate(() => {
      const cursor = document.querySelector('.enter-cursor');
      const plan = document.querySelector('.enter-plan');
      return {
        cursorDisplay: cursor ? getComputedStyle(cursor).display : null,
        planCursor: plan ? getComputedStyle(plan).cursor : null,
      };
    });
    check(cursorReduced.cursorDisplay === 'none', 'motion: reduced motion hides custom cursor');
    check(cursorReduced.planCursor !== 'none', 'motion: reduced motion retains native cursor on plan');

    await shot(page, 'entry-reduced-motion-390x844');
    await page.click('.enter-plan');
    check(await page.evaluate(() => !document.querySelector('#main').hidden && document.querySelector('#entrance').hidden && document.activeElement.id === 'main'), 'motion: reduced-motion entry is immediate and focuses main');
    await page.waitForTimeout(200);
    const state = await page.evaluate(() => ({
      running: document.getAnimations().filter((a) => a.playState === 'running').length,
      names: [...document.querySelectorAll('.jasmine-vines, .vine-strand, .vine-cluster, .scene-overlay .actor-move, .scene-overlay .actor-frames')].map((el) => getComputedStyle(el).animationName),
      strands: [...document.querySelectorAll('.brand-band .vine-strand')].map((el) => getComputedStyle(el).clipPath),
      clusters: [...document.querySelectorAll('.brand-band .vine-cluster')].map((el) => Number(getComputedStyle(el).opacity)),
      title: document.querySelector('#entrance-title').getClientRects().length > 0,
      heroOverlayVisible: document.querySelector('.hero-image-stage .scene-overlay')?.getClientRects().length > 0,
    }));
    check(state.running === 0 && state.names.every((n) => n === 'none'), 'motion: no running animations under reduced motion', state);
    check(state.strands.every(fullyRevealedClip) && state.clusters.length >= 1 && state.clusters.every((o) => o > 0.99) && state.title, 'motion: reduced motion shows the whole vine, all clusters and the name at once', state);
    check(state.heroOverlayVisible, 'motion: hero scene overlay visible under reduced motion');

    const heroReduced = await page.evaluate(async ({ SCENE_SPECS, METAS }) => {
      const stage = document.querySelector('.hero-image-stage');
      stage.scrollIntoView({ block: 'center', behavior: 'instant' });
      await new Promise((r) => setTimeout(r, 400));
      const overlay = stage.querySelector('svg.scene-overlay');
      const actors = [...overlay.querySelectorAll('g.scene-actor')];
      const actorData = actors.map((g) => {
        const aid = g.getAttribute('data-actor');
        const spec = SCENE_SPECS.actors.find((a) => a.id === aid);
        const meta = METAS[spec.strip];
        const move = g.querySelector('.actor-move');
        const frames = g.querySelector('.actor-frames');
        const sprite = g.querySelector('.actor-sprite');
        const m = getComputedStyle(move).transform.match(/^matrix\(([^)]+)\)$/);
        const fm = getComputedStyle(frames).transform.match(/^matrix\(([^)]+)\)$/);
        return {
          aid,
          moveAnim: getComputedStyle(move).animationName,
          framesAnim: getComputedStyle(frames).animationName,
          spriteVisible: sprite ? sprite.getClientRects().length > 0 : false,
          actualMove: m ? { x: Number(m[1].split(',')[4]), y: Number(m[1].split(',')[5]) } : null,
          expectedMove: { x: spec.travel[0], y: spec.travel[1] },
          actualRestX: fm ? Number(fm[1].split(',')[4]) : null,
          expectedRestX: -(meta.frame_count - 1) * meta.frame_width,
        };
      });
      return {
        actorCount: actors.length,
        running: document.getAnimations().filter((a) => a.playState === 'running').length,
        actorData,
      };
    }, { SCENE_SPECS: SCENE_BY_ID['study-1'], METAS: STRIP_METAS });

    check(heroReduced.actorCount === 2 && heroReduced.running === 0, 'motion: reduced motion has 0 running animations on hero scene', heroReduced);
    check(heroReduced.actorData.every((a) => a.moveAnim === 'none' && a.framesAnim === 'none' && a.spriteVisible),
      'motion: reduced motion actors have animation: none and visible sprites', heroReduced.actorData);
    check(heroReduced.actorData.every((a) => a.actualMove && Math.abs(a.actualMove.x - a.expectedMove.x) < 1 && Math.abs(a.actualMove.y - a.expectedMove.y) < 1),
      'motion: reduced motion shows actors at END position (--tx, --ty)', heroReduced.actorData);
    check(heroReduced.actorData.every((a) => a.actualRestX !== null && Math.abs(a.actualRestX - a.expectedRestX) < 1),
      'motion: reduced motion shows actors resting on LAST frame (seated rest pose)', heroReduced.actorData);

    await shot(page, 'brand-reduced-motion-390x844', page.locator('#brand'));
    await context.close();
  });

  await section('no JavaScript', async () => {
    for (const vp of [{ width: 320, height: 700 }, { width: 1440, height: 900 }]) {
      const label = `nojs-${vp.width}x${vp.height}`;
      const context = await newContext({ viewport: vp, javaScriptEnabled: false });
      const page = await context.newPage();
      await page.goto(SITE_URL, { waitUntil: 'load' });
      check(await page.locator('#main').isVisible(), `${label}: main content visible`);
      check(await page.locator('.site-header').isVisible(), `${label}: header and navigation remain available without JS`);
      check(await page.locator('#site-footer').isVisible() && await page.locator('.footer-mark-text').isVisible(), `${label}: footer visible`);
      check(await page.locator('#entrance-title').isVisible(), `${label}: brand name visible`);
      check(await page.locator('.hero-image-stage .scene-overlay').isVisible(), `${label}: hero scene overlay visible without JS`);
      const nojsHero = await page.evaluate(({ SCENE_SPECS, METAS }) => {
        const stage = document.querySelector('.hero-image-stage');
        const overlay = stage?.querySelector('svg.scene-overlay');
        const actors = overlay ? [...overlay.querySelectorAll('g.scene-actor')] : [];
        const actorData = actors.map((g) => {
          const aid = g.getAttribute('data-actor');
          const spec = SCENE_SPECS.actors.find((a) => a.id === aid);
          const meta = METAS[spec.strip];
          const move = g.querySelector('.actor-move');
          const frames = g.querySelector('.actor-frames');
          const sprite = g.querySelector('.actor-sprite');
          const m = move ? getComputedStyle(move).transform.match(/^matrix\(([^)]+)\)$/) : null;
          const fm = frames ? getComputedStyle(frames).transform.match(/^matrix\(([^)]+)\)$/) : null;
          return {
            aid,
            moveAnim: move ? getComputedStyle(move).animationName : null,
            framesAnim: frames ? getComputedStyle(frames).animationName : null,
            spriteVisible: sprite ? sprite.getClientRects().length > 0 : false,
            actualMove: m ? { x: Number(m[1].split(',')[4]), y: Number(m[1].split(',')[5]) } : null,
            expectedMove: { x: spec.travel[0], y: spec.travel[1] },
            actualRestX: fm ? Number(fm[1].split(',')[4]) : null,
            expectedRestX: -(meta.frame_count - 1) * meta.frame_width,
          };
        });
        return {
          active: overlay ? overlay.classList.contains('scene-active') : false,
          actorCount: actors.length,
          actorData,
        };
      }, { SCENE_SPECS: SCENE_BY_ID['study-1'], METAS: STRIP_METAS });
      check(nojsHero.actorCount === 2 && !nojsHero.active, `${label}: hero scene overlay has 2 actors and no scene-active class without JS`, nojsHero);
      check(nojsHero.actorData.every((a) => a.moveAnim === 'none' && a.framesAnim === 'none' && a.spriteVisible),
        `${label}: hero actors have no animations running and visible sprites without JS`, nojsHero.actorData);
      check(nojsHero.actorData.every((a) => a.actualMove && Math.abs(a.actualMove.x - a.expectedMove.x) < 1 && Math.abs(a.actualMove.y - a.expectedMove.y) < 1),
        `${label}: hero actors rest at END position without JS`, nojsHero.actorData);
      check(nojsHero.actorData.every((a) => a.actualRestX !== null && Math.abs(a.actualRestX - a.expectedRestX) < 1),
        `${label}: hero actors rest on LAST frame (seated rest pose) without JS`, nojsHero.actorData);
      const vine = await page.evaluate(() => ({
        strands: [...document.querySelectorAll('.brand-band .vine-strand')].map((el) => getComputedStyle(el).clipPath),
        clusters: [...document.querySelectorAll('.brand-band .vine-cluster')].map((el) => Number(getComputedStyle(el).opacity)),
      }));
      check(vine.strands.length === 2 && vine.strands.every(fullyRevealedClip) && vine.clusters.length >= 1 && vine.clusters.every((o) => o > 0.99), `${label}: vine and clusters fully visible without JS`, vine);
      check(await page.locator('[data-lightbox][href]').count() === 9, `${label}: nine gallery links remain plain links`);
      check(await page.locator('#form-fields').getAttribute('disabled') !== null && await page.locator('#form-fields button[type=submit]').isDisabled(), `${label}: form is disabled without JS`);
      check(await page.locator('#inquiry-form .preview-note').first().isVisible(), `${label}: no-JS form note visible`);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth).catch(() => null);
      check(overflow === false, `${label}: no horizontal overflow`, overflow);
      await shot(page, `entry-${label}`);
      await shot(page, `brand-${label}`, page.locator('#brand'));
      await page.click('.enter-plan');
      check(page.url().endsWith('#main'), `${label}: floor-plan link navigates to #main natively`, page.url());
      if (vp.width === 1440) {
        // Native CSS smooth scrolling to #main is still in progress right after the click; wait (bounded)
        // until scrollY is stable for consecutive samples and #main is in the viewport.
        const mainTarget = page.locator('#main');
        let settled = null;
        let lastY = null;
        let stable = 0;
        for (const deadline = Date.now() + 5000; Date.now() < deadline;) {
          const y = await page.evaluate(() => window.scrollY);
          const box = await mainTarget.boundingBox();
          stable = y === lastY ? stable + 1 : 0;
          lastY = y;
          const inView = !!box && box.y >= -100 && box.y <= vp.height;
          if (stable >= 3 && inView) { settled = { scrollY: y, mainTop: box.y }; break; }
          await page.waitForTimeout(100);
        }
        check(settled !== null, `${label}: native anchor scroll settles with #main in viewport`, settled ?? { lastY });
        const planUrl = new URL('floor-plan.html', SITE_URL).href;
        await page.goto(planUrl, { waitUntil: 'load' });
        check(await page.evaluate(() => { const i = document.querySelector('main#plan img, main#plan svg'); return !!i && (i.complete || i.tagName.toLowerCase() === 'svg'); }), `${label}: full-plan page works without JS`);
      }
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
  await finalizeReport();
  process.exitCode = report.failures.length ? 1 : 0;
}

async function finalizeReport() {
  try {
    report.finishedAt = new Date().toISOString();
    report.status = report.failures.length ? 'FAIL' : 'PASS';
    report.summary = { total: report.checks.length, failed: report.failures.length };
    report.requests = report.requests.map((r) => ({ ...r, url: r.url.startsWith('data:') ? 'data:…' : r.url }));
    await mkdir(output, { recursive: true });
    await writeFile(path.join(output, 'browser-report.json'), JSON.stringify(report, null, 2));
    console.log(`${report.status}: ${report.checks.length - report.failures.length}/${report.checks.length} checks passed. Report: ${path.relative(root, path.join(output, 'browser-report.json'))}`);
  } catch (err) {
    console.error('Failed to write report:', err);
  }
}

process.on('uncaughtException', async (error) => {
  check(false, 'uncaught exception', String(error?.stack || error));
  await finalizeReport();
  process.exit(1);
});

process.on('unhandledRejection', async (reason) => {
  check(false, 'unhandled rejection', String(reason?.stack || reason));
  await finalizeReport();
  process.exit(1);
});
