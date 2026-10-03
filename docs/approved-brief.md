# Website direction — 2 October 2026

## Feedback 2 — newest direct feedback (`Feedback 2.pdf`, 3 October 2026)

Source: `Feedback 2.pdf`, Library ID `libfile_c995d2cdade88191b4ccdd1534fec23e`, version 0
(SHA256 `1e77c5cd…77af8e`). This feedback supersedes every earlier visual choice below where
they conflict, including the Dallas-map entry and the six-image gallery.

### Requirements, as written by Heather

1. **Vine:** a single vine crawling through the letters of “King Chingaya Design”, not a halo around it.
2. **Name:** larger and bolder, in a font like the supplied “auren” reference; white type on a light-green solid background.
3. **Map:** remove the map concept.
4. **Floor plan:** bring back the floor plan for entry — a little larger and more complex, with exterior information such as a courtyard and tree placement; spanning the page, turned diagonally so part of it is cut off.
5. **Plan colours:** creamy off-white background with green plan lines, like the attached exploded axonometric.
6. **Gallery:** pictures overlap only slightly; add the three supplied restaurant images.
7. **Footer:** end with a footer like the “auren” example — “King Chingaya Design” stretched across the page and slightly cut off at the bottom, in two shades of the same brand colour.

### Implementation

| Requirement | Where | What was done |
| --- | --- | --- |
| 1 Vine | `index.html` (`.brand-lockup`), `styles.css` (`.vine-strand`, `.vine-back`, `.vine-front`) | Two layers of the **unmodified** `assets/brand/jasmine-vines-v1.png`, cropped by CSS to its top strand. The back layer sits behind the name; the front layer is masked in bands so the strand passes in front of some letters and behind others. Both are `aria-hidden`, `alt=""`, `pointer-events:none`. No new raster asset. |
| 2 Name | `index.html` (`p.entrance-title#entrance-title`), `styles.css` (`.brand-band`, `.entrance-title`, `--sage-band`, `--name-size`) | Live text “King Chingaya Design”, bundled Instrument Sans weight 700, white, one line (`white-space:nowrap`, `font-size:9.6vw`) on a solid sage band `#78926d`. The entrance section is labelled by this text. |
| 3 Map | `index.html`, `styles.css`, `app.js` | Map markup and `.map-frame`/`.dallas-map`/`.enter-map` rules removed; `app.js` wires `.enter-plan`. `assets/brand/dallas-map.jpeg` is preserved on disk (unchanged hash) and still listed in `assets/brand/manifest.json`, but is not used. |
| 4–5 Floor plan | `assets/brand/entry-floor-plan.svg`, `index.html` (`a.enter-plan[href="#main"]`), `styles.css` (`.enter-plan`, `.floor-plan`, `--plan-paper`) | New hand-authored vector plan (provenance in `assets/brand/manifest.json`): house around a central courtyard with tree, bench and basin; living, entry/stair, kitchen, dining, bedroom, bath, closet, garden room; door swings, windows, hedges, terrace, side gardens, street trees; labelled “Conceptual plan — not to scale”. Green lines on cream `#f3efe0`. It spans the full width, is rotated −11° and cropped by `overflow:hidden`. The whole plan is a link to `#main` with an accessible name; the “Step inside” button is kept. Works without JavaScript as a plain anchor. |
| 6 Gallery | `index.html` (`.study-1` … `.study-9`), `styles.css` | Nine borderless studies: the six numbered selections (01, 02, 08, 11, 14, 18) followed by `assets/brief/restaurant-window.png`, `restaurant-booths.png`, `restaurant-counter.png`. Overlap reduced to a slight edge (`margin-left:-4%`), never across captions. New captions describe them only as spatial visualizations. Provenance and hashes: `assets/brief/feedback-2-manifest.json` (original embedded PNGs, not resized or retouched). |
| 7 Footer | `index.html` (`footer#site-footer > .footer-inner` then `.footer-mark`), `styles.css` (`.footer-mark*`) | Contact, social handles, back-to-top and copyright first; then live text “King Chingaya Design” at the entrance size, in `--green` (#466b45) and `--sage-band` (#78926d), with the wrapper `height:.78em; overflow:hidden` cropping the bottom of the letters. Not `aria-hidden`. |

Site-wide: `--ink` changed from the provisional blue `#284d70` to dark green `#233d2a`
(≈10.9:1 on the paper colour). Obsolete: the earlier “use the Dallas map”, “show only six
images” and “provisional blue text” instructions in the section below.

### Risks and open points

- **Sage band colour.** `#78926d` is darker than the light green in the reference so white
  text keeps roughly 3.4:1 contrast (passes WCAG AA for large text only). A lighter green would
  look closer to the reference but would fail contrast. Heather may want to choose.
- **Name width and crop are estimates.** `9.6vw` was chosen to fill about 85–90% of the width.
  The footer crop (`.78em`) was judged by eye. Actual glyph widths depend on font rendering; the
  browser probe measures both.
- **SVG labels use a system font.** The floor-plan labels use Arial/Helvetica, because an `<img>` SVG cannot use the page’s
  bundled web font. Rendering varies slightly between platforms.
- **`--ink` changed site-wide.** All body text, buttons and outlines that used `--ink` are now
  dark green. Sections not mentioned in the feedback look different as a result.
- The floor plan is conceptual. It is not a real project, site or measured drawing, and is labelled that way.

### Verification status — final pass, 3 October 2026

| Check | Command | Outcome |
| --- | --- | --- |
| Static gate | `python3 tests/test_site.py` (or `python3 -m pytest tests/test_site.py`) | Passed |
| Script syntax | `node --check app.js` and `node --check tests/browser_probe.mjs` | Passed |
| Browser gate | `SITE_URL=http://127.0.0.1:4184 node tests/browser_probe.mjs` | 276/276 passed, including the first-screen CTA checks |

The desktop (`min-width:801px`) `.enter-plan` height adapts to the available screen height:
`clamp(220px, min(40vw, calc(100svh - 252px - 23.6vw)), 640px)`, and the probe gained a
fresh-load check that the button is fully in view at 1440×900 and 1024×768. Both checks passed.
The phone layout retains its original plan height.

The browser probe used an already-installed Playwright package (`PLAYWRIGHT_MODULE`) and system
Chrome (`BROWSER_PATH`), with the Chromium sandbox enabled. No installation was performed. The
site remains dependency-free; the browser test is not.

Browser report and screenshots: `verification/feedback-2/` (`browser-report.json`, `entry-*`,
`main-*`, `gallery-*`, `footer-*`, `viewer-*`, `inquiry-*`, `entry-nojs-*`). Earlier
`verification/` output is inherited and left untouched.

---

## Superseded: direct feedback — 3 October 2026 (before Feedback 2)

> **Obsolete where marked.** Kept for history; Feedback 2 above takes precedence.

The feedback below superseded the earlier floor-plan, plum, serif and 20-image proposals:

- ~~Use the supplied pale-green Dallas map as the entry graphic in place of the floor plan. The map itself and the Step inside button both enter the site.~~ **Obsolete:** Feedback 2 removes the map and restores a larger diagonal floor plan. The Step inside button remains.
- Set the complete name “King Chingaya Design” in one font, on one line, including the entry, header and footer. “One don't” is interpreted as “one font.” *(Still applies.)*
- Use photorealistic green jasmine vines with white flowers, rather than the schematic illustration. The generated transparent asset is in `assets/brand`, with its prompt and provenance. *(Still applies; now a single strand through the letters.)*
- ~~Show only review-image numbers **01, 02, 08, 11, 14 and 18** in the selected gallery~~ **Superseded:** those six are still shown first, directly after the design philosophy (filenames in `assets/brand/manifest.json`), followed by the three Feedback 2 restaurant images, nine in total.
- Add no borders or matting to portfolio images. Keep a light shadow and layered placement, with gentle scroll reveals and reduced-motion support. Preserve all original image assets. *(Still applies; overlap is now only slight.)*
- Follow the prior Feedback.pdf direction: predominantly cream backgrounds, ample white space, no plum; colored process/services sections are permitted. *(Still applies.)*

~~The exact typeface and primary text color have not yet been chosen. The current local preview uses bundled Instrument Sans and blue as provisional styling.~~ **Updated:** text colour is now dark green (`#233d2a`). Instrument Sans remains a bundled stand-in; this does not assert approval or licensing of Diatype, Suisse Int'l or the “auren” reference face.

## Earlier source and proposals

The authoritative source is `Website Details (compressed).pdf`, Library ID
`libfile_e844cc862b348191b169c6f8e6309df2`, version 0. Its supplied copy and imagery
were reviewed in full. Source provenance is in `assets/brief/manifest.json`.

The subsequent direct user feedback resolves these choices:

- Logo and professional portrait will follow. Reserve places for them; do not invent either.
- Combine the two supplied palettes, with green an important part of the result.
- Suggest typography using the listed fonts as inspiration.
- Create an imaginative click-to-enter image, possibly a floor plan or clouds; an interior photograph is not required.
- Use first-person singular throughout. The suggested grammar corrections are approved:
  “I’d love,” “complimentary discovery call,” and “determine whether this is the right fit.”

Original local implementation (since revised): a conceptual floor-plan entrance among soft clouds; pale sage,
olive-green, lavender, plum, warm stone and paper. This was a proposed visual implementation
for review, not a claim of final visual approval.

Typography proposal: locally served Fraunces and Instrument Sans, with the unmodified
SIL Open Font License notices in `assets/fonts`. Public typeface sources:
https://github.com/undercasetype/Fraunces and https://github.com/Instrument/instrument-sans.
The WOFF2 assets are the existing Fontsource variable distributions, Fraunces 5.2.9
and Instrument Sans 5.3.0. These are suggestions, not licensed versions of the commercial
reference fonts. The site makes no third-party font requests.

Keep the form a clearly labeled local preview. The supplied email is real contact copy,
but there is no verified sending backend. No submissions, deployment, push or domain changes
are authorized. No project names, outcomes, testimonials or credentials may be invented.

The approved copy and imagery supersede old fixed-headline, image-count, budget-field and
palette assertions. Preserve the meaningful accessibility, motion, no-transmission and
asset-integrity checks when adapting tests.
