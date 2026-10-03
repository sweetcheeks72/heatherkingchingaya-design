# King Chingaya Design — local website

A dependency-free HTML/CSS/JavaScript website, updated from Heather’s supplied PDF
and subsequent feedback. The current direction is recorded in
[`docs/approved-brief.md`](docs/approved-brief.md).

The local preview uses a cream canvas, the supplied Dallas map for entry,
a single-line company name with photorealistic jasmine, and the six selected
borderless portfolio images (review numbers 01, 02, 08, 11, 14 and 18).
Instrument Sans and blue text are provisional while Heather selects the final
font and text color. Five process steps and six services remain. Logo and
portrait spaces are reserved. Fonts are bundled with their licenses.

## Run locally

```sh
python3 -m http.server 4173 --bind 127.0.0.1
```

Open <http://127.0.0.1:4173/>. These changes have not been pushed or deployed.

## Verify

```sh
python3 tests/test_site.py  # requires Pillow
node --check app.js
node tests/browser_probe.mjs
```

The browser check needs Node 22+ and a running local server. It detects Chrome
or Edge on macOS/Windows and Chromium on Linux; use `BROWSER_PATH` for another
Chromium executable. It starts an isolated temporary profile and removes it
when finished. No existing browser session is used.

It checks 1440, 768, 390 and 320px layouts; images and fonts; keyboard entry,
menu, accordions and viewer; reduced motion and pause; no-JavaScript fallbacks;
and inquiry validation, editing, confirmation, reset, safe text and isolation.
Screenshots and the report are in `verification/approved-brief/`.
Optionally set `AXE_PATH` to a local axe-core `axe.min.js` file to include WCAG
2.1 AA automated checks. The recorded verification includes those checks;
automation does not establish complete accessibility conformance.

## Inquiry and content status

The form previews information only. It never sends or stores an inquiry.
The user-supplied email is available as a direct mail link. Choosing and
verifying a delivery backend remains a separate decision.

Image captions describe supplied drawings, moodboards and visualizations;
they are not asserted project names or construction outcomes. Asset provenance
and integrity hashes are in `assets/brief/manifest.json`.
