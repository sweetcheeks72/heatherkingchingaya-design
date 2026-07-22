import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const verification = path.join(root, "verification");
const profile = path.join(verification, `edge-profile-${Date.now()}`);
const url = "http://127.0.0.1:4173/";
const port = 9333;
const edgePath = ["C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "C:/Program Files/Microsoft/Edge/Application/msedge.exe"].find(existsSync);
if (!edgePath) throw new Error("Microsoft Edge was not found.");

await mkdir(verification, { recursive: true });
await rm(profile, { recursive: true, force: true });
const edge = spawn(edgePath, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--no-first-run", "--no-default-browser-check", "--disable-sync", "--disable-extensions", "--disable-gpu", "about:blank"], { windowsHide: true, stdio: "ignore" });
edge.unref();
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const check = (condition, message) => { if (!condition) throw new Error(message); };

async function pollJson(endpoint) {
  let lastError;
  for (let index = 0; index < 80; index += 1) {
    try { const response = await fetch(endpoint); if (response.ok) return await response.json(); }
    catch (error) { lastError = error; }
    await wait(100);
  }
  throw lastError || new Error(`Browser endpoint unavailable: ${endpoint}`);
}

try {
  const pages = await pollJson(`http://127.0.0.1:${port}/json/list`);
  const page = pages.find((candidate) => candidate.type === "page" && candidate.url === "about:blank") || pages.find((candidate) => candidate.type === "page");
  check(page?.webSocketDebuggerUrl, "No debuggable page target was available.");
  const socket = new WebSocket(page.webSocketDebuggerUrl);
  await Promise.race([new Promise((resolve, reject) => { socket.addEventListener("open", resolve, { once: true }); socket.addEventListener("error", reject, { once: true }); }), new Promise((_, reject) => setTimeout(() => reject(new Error("WebSocket connection timed out.")), 5000))]); console.log("CDP connected");

  let commandId = 0;
  const pending = new Map();
  const events = [];
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const handlers = pending.get(message.id); pending.delete(message.id);
      message.error ? handlers.reject(new Error(message.error.message)) : handlers.resolve(message.result);
    } else events.push(message);
  });
  // Every command is bounded. Without this a single unanswered CDP command leaves an
  // unsettled top-level await, and the run dies with a bare exit 13 naming nothing.
  const send = (method, params = {}, timeoutMs = 30000) => new Promise((resolve, reject) => {
    const id = ++commandId;
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error(`CDP command timed out after ${timeoutMs}ms: ${method}`));
    }, timeoutMs);
    const settle = (fn) => (value) => { clearTimeout(timer); fn(value); };
    pending.set(id, { resolve: settle(resolve), reject: settle(reject) });
    socket.send(JSON.stringify({ id, method, params }));
  });
  async function evaluate(expression) {
    const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "Page evaluation failed.");
    return result.result.value;
  }
  async function navigate(width, height) {
    await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width <= 700 });
    events.length = 0; await send("Page.navigate", { url });
    for (let index = 0; index < 100 && !events.some((entry) => entry.method === "Page.loadEventFired"); index += 1) await wait(50);
    // Images marked loading="lazy" sit far below the fold on this page and never fire a
    // load event, so an unbounded Promise.all here never settles and the run dies with
    // exit 13. Walk the document to trigger them, then bound the remaining wait.
    // Scrolling must be instant: smooth scrolling would not reach each step in time.
    await evaluate(`(async () => {
      const step = window.innerHeight;
      const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
        window.scrollTo({ top: y, behavior: 'instant' });
        await wait(60);
      }
      window.scrollTo({ top: 0, behavior: 'instant' });
      await wait(80);
      const pending = [...document.images].filter((image) => !image.complete || image.naturalWidth === 0);
      await Promise.race([
        Promise.all(pending.map((image) => new Promise((resolve) => {
          image.addEventListener('load', resolve, { once: true });
          image.addEventListener('error', resolve, { once: true });
        }))),
        wait(8000)
      ]);
      return true;
    })()`);
  }
  async function screenshot(name) {
    const result = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false, fromSurface: true });
    await writeFile(path.join(verification, name), Buffer.from(result.data, "base64"));
  }

  await send("Page.enable"); await send("Runtime.enable"); await send("Log.enable");
  const viewports = [
    { name: "desktop", width: 1440, height: 900, source: "hero-desktop.png" },
    { name: "mobile", width: 390, height: 844, source: "hero-mobile.png" },
    { name: "reflow", width: 320, height: 844, source: "hero-reflow.png" }
  ];
  const results = [];
  for (const viewport of viewports) { console.log(`Testing ${viewport.name}`);
    await navigate(viewport.width, viewport.height);
    const metrics = await evaluate(`(() => {
      const media = document.querySelector('.hero-media').getBoundingClientRect();
      const heroImage = document.querySelector('.hero-media img');
      const actions = [...document.querySelectorAll('a, button')].filter(node => node.getClientRects().length > 0).map(node => ({tag: node.tagName, label: (node.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 24), height: node.getBoundingClientRect().height}));
      return { width: innerWidth, height: innerHeight, scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth, mediaHeight: media.height, mediaRatio: media.height / innerHeight, heroSource: heroImage.currentSrc.split('/').pop(), h1: document.querySelector('h1').innerText.replace(/\\s+/g, ' ').trim(), imagesLoaded: [...document.images].every(image => image.complete && image.naturalWidth > 0), brokenAnchors: [...document.querySelectorAll('a[href^="#"]')].filter(link => !document.querySelector(link.hash)).map(link => link.hash), tinyActions: actions.filter(item => item.height < 44), documentHeight: document.documentElement.scrollHeight };
    })()`);
    // Compare against clientWidth, not innerWidth: innerWidth includes the classic
    // scrollbar, so an equality check against it fails on every scrollable page.
    check(metrics.scrollWidth <= metrics.clientWidth, `${viewport.name}: horizontal overflow (content ${metrics.scrollWidth}px in ${metrics.clientWidth}px).`);
    check(metrics.mediaRatio >= 0.70, `${viewport.name}: room image lost first-frame dominance (${metrics.mediaRatio}).`);
    check(metrics.heroSource === viewport.source, `${viewport.name}: incorrect hero source (${metrics.heroSource}).`);
    check(metrics.h1 === "Interior design for the way you live, work, and gather.", `${viewport.name}: hero heading drifted.`);
    check(metrics.imagesLoaded, `${viewport.name}: an image failed to load.`);
    check(metrics.brokenAnchors.length === 0, `${viewport.name}: broken internal navigation.`);
    check(metrics.tinyActions.length === 0, `${viewport.name}: undersized action target (44px minimum): ${metrics.tinyActions.map((item) => `${item.label || item.tag} ${Math.round(item.height)}px`).join(', ')}.`);
    await screenshot(`${viewport.name}-first-frame.png`); results.push({ viewport: `${viewport.width}x${viewport.height}`, ...metrics });
  }

  console.log("Testing inquiry"); await navigate(390, 844);
  const interaction = await evaluate(`(async () => {
    const form = document.querySelector('#inquiry-form'); form.scrollIntoView(); form.requestSubmit(); await new Promise(resolve => setTimeout(resolve, 0));
    const firstError = document.querySelector('#form-error').textContent; const firstFocus = document.activeElement.getAttribute('name');
    document.querySelector('[name="projectType"][value="Residential"]').checked = true;
    document.querySelector('[name="services"][value="Furnishing or styling"]').checked = true;
    document.querySelector('[name="budget"]').checked = true;
    document.querySelector('#name').value = 'Prototype Reviewer'; document.querySelector('#email').value = 'review@example.com'; document.querySelector('#location').value = 'Dallas, TX'; document.querySelector('#details').value = 'A warm room with accessible circulation.';
    form.requestSubmit(); await new Promise(resolve => setTimeout(resolve, 0));
    const reviewVisible = !document.querySelector('#review-panel').hidden; const summary = document.querySelector('#review-summary').innerText;
    document.querySelector('#edit-inquiry').click(); const editVisible = !document.querySelector('#form-fields').hidden; form.requestSubmit(); document.querySelector('#confirm-inquiry').click();
    return { firstError, firstFocus, reviewVisible, summary, editVisible, confirmationVisible: !document.querySelector('#confirmation-panel').hidden, confirmation: document.querySelector('#confirmation-panel').innerText, formAction: form.getAttribute('action'), localStorageLength: localStorage.length, sessionStorageLength: sessionStorage.length, scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth, width: innerWidth };
  })()`);
  check(interaction.firstError === "Choose a project type.", "Inquiry validation did not explain the first error.");
  check(interaction.firstFocus === "projectType", "Inquiry validation did not focus the first invalid field.");
  check(interaction.reviewVisible && interaction.summary.includes("Prototype Reviewer") && interaction.summary.includes("$500"), "Inquiry review state failed.");
  check(interaction.editVisible, "Inquiry edit path failed.");
  check(interaction.confirmationVisible && interaction.confirmation.includes("No message was sent"), "Inquiry confirmation was not transparent.");
  check(interaction.formAction === null, "Inquiry unexpectedly gained a delivery action.");
  check(interaction.localStorageLength === 0 && interaction.sessionStorageLength === 0, "Inquiry data was persisted.");
  check(interaction.scrollWidth <= interaction.clientWidth, "Inquiry state caused mobile overflow.");
  await screenshot("mobile-inquiry-confirmation.png");
  const browserErrors = events.filter((entry) => entry.method === "Runtime.exceptionThrown" || (entry.method === "Log.entryAdded" && ["error", "warning"].includes(entry.params?.entry?.level)));
  check(browserErrors.length === 0, `Browser reported ${browserErrors.length} errors or warnings.`);
  await writeFile(path.join(verification, "browser-report.json"), JSON.stringify({ status: "PASS", browser: "Microsoft Edge headless via CDP", url, viewports: results, inquiry: interaction, browserErrors: [] }, null, 2));
  console.log("PASS: desktop, mobile, 320px reflow, evidence images, navigation, and isolated inquiry states");
  socket.close();
} finally {
  edge.kill();
}
