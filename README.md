# King Chingaya Design — local website

A dependency-free HTML/CSS/JavaScript website, updated from Heather’s supplied PDF
and subsequent feedback. The current direction, most recently **Feedback 2**
(`Feedback 2.pdf`), is recorded in [`docs/approved-brief.md`](docs/approved-brief.md).

## Current design (Feedback 2)

- **Entrance:** “King Chingaya Design” as live white text in bold Instrument Sans on a solid
  sage band (`#78926d`), with a single strand of the existing photorealistic jasmine
  (`assets/brand/jasmine-vines-v1.png`, unmodified) woven through the letters in two CSS layers.
- **Entry graphic:** a new hand-authored, green-on-cream conceptual floor plan
  (`assets/brand/entry-floor-plan.svg`, provenance in `assets/brand/manifest.json`). It shows
  a courtyard, trees, gardens and a terrace, spans the page, is rotated diagonally and is cropped.
  The plan itself (`a.enter-plan`, links to `#main`) and the “Step inside” button both enter the site.
  The Dallas map is **no longer used**. `assets/brand/dallas-map.jpeg` is kept unchanged on disk.
- **Gallery:** nine borderless studies with only slight overlap. The six numbered selections
  (01, 02, 08, 11, 14, 18) come first, followed by `assets/brief/restaurant-window.png`,
  `restaurant-booths.png` and `restaurant-counter.png`. These are original PNGs from Feedback 2; provenance is in
  `assets/brief/feedback-2-manifest.json`.
- **Footer:** contact, socials, back-to-top and copyright; then a full-width
  “King Chingaya Design” in two greens, cropped at the bottom.
- **Colour:** body text `--ink` is now dark green `#233d2a` site-wide; the provisional blue is gone.

Changed files: `index.html`, `styles.css`, `app.js`, `assets/brand/entry-floor-plan.svg`,
`assets/brand/manifest.json`, the three restaurant images and their provenance manifest,
plus the tests and docs.

Five process steps and six services remain. Logo and portrait spaces are reserved.
Fonts are bundled with their licences. Instrument Sans is a stand-in for the reference face.

## Run locally

```sh
python3 -m http.server 4184 --bind 127.0.0.1
```

Open <http://127.0.0.1:4184/>. These changes have not been pushed or deployed.

## Verify

```sh
python3 tests/test_site.py                 # static gate; requires Pillow
# or: python3 -m pytest tests/test_site.py
node --check app.js
SITE_URL=http://127.0.0.1:4184 node tests/browser_probe.mjs
```

**Status.** Final verification passed on 3 October 2026: the static gate, syntax checks for
`app.js` and the browser probe, and **276/276 browser checks**. The desktop “Step inside”
button is fully visible and clickable on the first screen at 1440×900 and 1024×768.
The report and rendered screenshots are in `verification/feedback-2/`.

The **static gate** checks:

- semantics, navigation, services and process copy
- the nine-image gallery: order, sizes, alt text and honest captions
- the floor-plan link and the SVG: well-formed, vector only, green lines, no external references, enough detail
- the live-text wordmark and footer mark, and the vine assets
- the green ink colour, with the map and blue removed
- motion opt-in, reduced-motion and pause rules
- inquiry isolation and privacy copy
- asset hashes against the pre-redesign baseline (`../baseline-manifest.json` when present, otherwise hashes hardcoded in the test)
- Feedback 2 PNG hashes and dimensions (from the IHDR chunk), and that no new raster assets were added

The **browser gate** needs Node 22+ with Playwright (`playwright` or `playwright-core`, or
`PLAYWRIGHT_MODULE=/abs/path`) and a running local server. It launches Chromium with the
sandbox enabled (`chromiumSandbox: true`); `BROWSER_PATH` may point to another Chromium
executable. The site itself stays dependency-free, but this browser test does not: it needs a
Playwright package. The recorded run used an already-installed Playwright via
`PLAYWRIGHT_MODULE` and system Chrome via `BROWSER_PATH`; nothing was installed for it. It checks:

- layouts at 1440×900, 1024×768, 768×1024 and 390×844, plus a 320px overflow check
- on a fresh load at 1440×900 and 1024×768, before any scrolling, the “Step inside” button is fully inside the first screen
- the single-line wordmark: its width and that it fits the viewport
- vine layers and loading
- floor-plan click and keyboard (Tab + Enter) entry, with visible focus
- the gallery: 9 images, “1 / 9”, Previous/Next wrap, Escape with focus restore, and every image reachable
- footer crop and unobstructed contact/nav/copyright at 1440 and 390
- reduced motion and the pause control
- the no-JavaScript fallback
- inquiry preview with no storage, no non-local or non-GET requests, no “sent” claims, and privacy copy unchanged
- 44px targets

The report and screenshots are written only to `verification/feedback-2/`. The older
`verification/` output is inherited and is not overwritten.

## Inquiry and content status

The form previews information only. It never sends or stores an inquiry.
The user-supplied email is available as a direct mail link. Choosing and
verifying a delivery backend remains a separate decision.

Image captions describe supplied drawings, moodboards and visualizations;
they are not asserted project names or construction outcomes. The floor plan is
conceptual and not to scale. Asset provenance and integrity hashes are in
`assets/brief/manifest.json`, `assets/brief/feedback-2-manifest.json` and
`assets/brand/manifest.json`.
