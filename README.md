# King Chingaya Design — local website

A dependency-free HTML/CSS/JavaScript website, updated from Heather’s supplied PDF
and subsequent feedback. The current direction is **Feedback 1** (`Feedback 1.pdf`, 3 October 2026),
which supersedes Feedback 3 and Feedback 2 by explicit user confirmation. It is
recorded, with the earlier rounds, in [`docs/approved-brief.md`](docs/approved-brief.md).

## Current design (Feedback 1)

- **Opening screen: plan-only entrance & oval Enter cursor.** The first screen displays the conceptual Dallas
  residence floor plan. The former "Step inside" button has been completely removed. The floor-plan link
  (`a.enter-plan`) is the sole entrance control for pointer, touch, keyboard, and no-JS fallback. On desktop
  fine-pointer devices, a custom oval `.enter-cursor` (104×52px, noticeably width > height) appears when hovering
  over the plan, hiding the native cursor only while the replacement is active; `pointerleave` restores the native
  cursor immediately. Hovering does not trigger site entry; clicking the plan enters `#main`. Keyboard navigation
  (`Tab` + `Enter`, `ArrowDown`), mouse wheel scrolling (`deltaY > 0`), and touch gestures retain native interaction
  and full accessibility without any replacement cursor.
- **Staged entrance reveal.** Under `prefers-reduced-motion: no-preference` and script enhancement,
  the floor-plan elements reveal progressively: walls and trees appear at start (0s), fixtures and
  flooring after 0.55s, and furniture after 1.65s. All finite reveal animations conclude within
  4.5s, leaving clean static vectors without continuous loops. Under reduced motion or without
  JavaScript, the complete diagram displays statically from the start.
- **Inline SVG entry contract.** The entrance plan is staged between `<!-- FLOOR_PLAN_START -->`
  and `<!-- FLOOR_PLAN_END -->` as an inline `<svg class="floor-plan" aria-hidden="true" focusable="false">`
  with viewBox (typically 1600×1200 or derived) and stage groups `.plan-shell`, `.plan-fixtures`,
  and `.plan-furniture`. During model and generator integration, a placeholder `<img>` is safely
  accommodated until the generator phase runs.
- **Header logo placeholder and brand section.** In the top header navigation, the former black text
  wordmark is replaced with an explicit, elegant `[ LOGO ]` placeholder (`a.wordmark.logo-placeholder[data-placeholder="logo"]`)
  with an accessible home link brand label (`aria-label="King Chingaya Design, home"` and screen-reader text).
  Section `#brand` features the expanded sage band (`#78926d` / `--sage-band`), where the large live white title
  “King Chingaya Design” sits almost touching the bottom of the band within bounds readable with no unintended
  clipping at all widths (`padding: max(64px, 12vw) 0 max(4px, 0.5vw)`).
- **Stronger green typography & delicate black gallery titles.** Main page text uses a bolder, stronger green
  (`--ink: #1c4424;` font-weight 500 for body, 600 for headings and nav links). Computed WCAG contrast (relative
  luminance, same formula as `tests/test_site.py`): 10.1:1 on paper `#f8f5ee`, 8.9:1 on the pale sage process band
  `#e2e9d9`. As an intentional exception, gallery image titles are styled in delicate black (`#111111`, 17.3:1 on paper,
  font-weight 350, fine letterforms) with refined thin rules.
- **Scene people in EVERY scene with 64-frame hero walk/chat and 32-frame interior motion.** By the user's
  explicit direction (3 October 2026), animated realistic, diverse people appear across EVERY scene on the
  website: the hero architectural model and all nine gallery studies. Each scene receives a generated decorative
  inline SVG overlay (`.scene-overlay`, `aria-hidden="true"`, `focusable="false"`) produced deterministically by
  `scripts/build_scene_overlays.py` from `assets/people/scenes.json`:
  - **Hero visualization (study-1):** In the top home intro section, the hero image "Architecture in miniature"
    (`assets/brief/architectural-model.webp`, 1800×1092, raster unchanged) spans the page at top with its own aspect
    ratio. Its overlay uses `preserveAspectRatio="xMidYMid slice"` matching the image's `object-fit: cover`. Nathan
    and Carla arrive together in the backyard: during the first half of the sequence (`move_until: 0.5`, 2.2s of 4.4s),
    they walk east into the backyard; at 2.2s they stop, turn toward each other, and chat for the remaining 2.2s
    while holding position (zero position change after stop while chat frames continue). Their strips hold 64 distinct
    frames rendered in Blender from licensed Renderpeople scans (Nathan animated 003 and Carla rigged 001).
  - **Gallery studies 1–9:** Inside each `a.study-image`, a matching `.scene-overlay` uses `preserveAspectRatio="xMidYMid meet"`
    to align precisely with the photo raster. Interior studies feature 32-frame motion strips at 192×256 or 256×384,
    animating seated and standing figures (both Nathan and Carla appear across the studies for a diverse group).
  - **Placement & occlusions:** Each actor is nested as `<g class="scene-actor"><g class="actor-move"><svg class="actor-sprite"><g class="actor-frames"><image class="actor-strip">`,
    scaled by `body_height / visible_body_height` with ground shadow ellipses under foot anchors and stationary
    occluder clips via `visible_path` evenodd clipPaths defined outside the moving group so architectural occluders
    (tables, railings) stay fixed while figures move behind them.
  - **Lightbox integration:** In `#study-viewer`, `.viewer-stage` clones the active study's generated overlay with
    `xMidYMid meet` letterboxing matching `#viewer-image`'s `object-fit: contain`, rewriting all IDs and clipPaths
    with a `viewer-` prefix to prevent collisions. Opening or changing studies replays the scene once as an explicit
    user interaction; closing the viewer cleans up the overlay and stops animations while the gallery thumbnails remain in their finished state.
  - **Runtime & accessibility:** Each overlay plays its single 4.4s sequence once when it actually intersects the
    viewport (IntersectionObserver, threshold 0.15; gated on `.motion-ready`). Hiding the page pauses animations in place
    (`.document-hidden`), resuming without restart. Without JavaScript or under `prefers-reduced-motion: reduce`,
    all figures rest statically on their LAST frame at their END position (chat rest pose), ensuring complete visibility
    without missing content.
- **Restaurant studies cluster.** Gallery studies 7, 8, and 9 (`restaurant-window.png`, `restaurant-booths.png`,
  `restaurant-counter.png`) are arranged into a coherent cluster: studies 7 and 8 sit side by side with a slight
  vertical offset, and study 9 sits wider underneath centered, closer grouped than unrelated gallery works,
  transitioning to a tidy contiguous stack on mobile without caption collisions.
- **See-through arrow affordances.** Image open arrows in the gallery are 44px hit targets on a mostly transparent
  disc (`rgba(248, 245, 238, .35)`, no backdrop blur) with a thin arrow (`font-weight: 300`) and a hairline edge; the
  disc becomes near-opaque on hover and keyboard focus so it stays findable without distracting from the image.
- **Refined vine and flower clusters.** A single finer, thinner jasmine strand passes through the
  letters of the brand name using front and back layering of `assets/brand/jasmine-vines-v1.png`.
  Hanging flower clusters bloom dynamically along the strand without fixed cluster count
  assumptions. Continuous sway animations have been removed to prevent infinite loops once settled.
- **Marketing DOM cleanup.** The "View full floor plan" link, pause-motion control (`.motion-toggle`), and
  the entrance "Step inside" button have been excised completely from the marketing page DOM, stylesheets, and
  scripts, keeping the presentation uncluttered.
- **Standalone full plan for review.** `floor-plan.html` is retained as an unlinked review artifact.
  It renders the complete architectural plan unrotated and uncropped at its natural aspect ratio
  (derived dynamically from the SVG viewBox), providing links to inspect the raw SVG, download it,
  and return to `index.html#main`.
- **Section headings and copy cleanup.** All section numbering and accordion numerals have been
  removed. Headings are rendered as large, plain, unnumbered titles in document order:
  1. `Design philosophy` (`#philosophy`)
  2. `Gallery` (`#projects`)
  3. `About me` (`#about`)
  4. `Working together` (`#process`)
  5. `Services` (`#services`)
  6. `Start a project` (`#inquiry`)
  The poetic subheadings and the three philosophy taglines have been removed.
- **Floor-plan model and space planning.** Architectural planning integrates a single-storey Dallas residence
  with sixteen named spaces (`assets/brand/floor-plan-model.json`): central courtyard, kitchen with a narrower pantry
  and a laundry/utility room entered directly from the kitchen, dining room, living room with coat closet and direct
  entry, a three-bedroom program (primary bedroom with primary bath and dressing, guest bedroom, and a second guest
  bedroom in the former gallery, both guest rooms with closets, sharing a guest bath), and two hallway/sitting
  spaces. The kitchen island seats three stools; the plan workflow maintains the aisle and clearance measurements.
  Dimensional flexibility confirmed by the user resolves prior measurement blockers.
- **Inquiry isolation.** The form is an interactive client-side preview only; no data is transmitted
  or stored locally (cookies, local/session storage, analytics, and external trackers are strictly
  excluded). A direct `mailto:heather@kingchingaya.com` link is provided.

Five process steps and six services remain. Logo and portrait spaces are reserved.
Instrument Sans is a bundled stand-in for the reference face.

## Run locally

```sh
python3 -m http.server 4184 --bind 127.0.0.1
```

Open <http://127.0.0.1:4184/>. The standalone review plan is at <http://127.0.0.1:4184/floor-plan.html>.

**Publication status.** Feedback 2 was verified and opened as a draft pull request:
<https://github.com/sweetcheeks72/heatherkingchingaya-design/pull/1>. **Feedback 1 and Feedback 3
are local only.** They have not been pushed, published or deployed. The original checkout is
preserved.

## Render the people sprites (coordinator step, before the gates)

The shared all-scenes contract (`research-people/all-scenes-contract.txt`) defines `assets/people/scenes.json` (contract version 1, duration 4.4s) across study-1 through study-9:
- **Hero scene (study-1):** Nathan and Carla walk into the backyard during the first half (`move_until: 0.5`, 2.2s of 4.4s), then stop, turn, and chat for the remaining 2.2s. Renders 64 frames per strip at 192×256 with measured foot anchors and body boxes.
- **Interior gallery scenes (studies 2–9):** 32-frame motion strips at 192×256 or 256×384 animating seated and standing figures (diverse figures across Nathan and Carla) in the raster's pixel space.
- **Provenance & safety:** Only rendered PNG sprites and JSON metadata live in `assets/people/scenes/`. Raw 3D models (FBX, textures, `.blend`) remain strictly outside the site in `research-people/` and are never published.

After rendering the strips, the deterministic generator builds or verifies the SVG overlay blocks:
```sh
# Generate and inject scene overlay SVG blocks into index.html
python3 scripts/build_scene_overlays.py --write

# Verify that index.html matches the generated output (byte-identical)
python3 scripts/build_scene_overlays.py --check
```

## Verify

```sh
python3 tests/test_site.py                 # static gate; requires Pillow
# or: python3 -m pytest tests/test_site.py
node --check app.js
node --check tests/browser_probe.mjs
SITE_URL=http://127.0.0.1:4184 node tests/browser_probe.mjs
```

**Status: Verified locally. All 774/774 sandboxed Chrome checks passed across 1440, 1024, 768, 390 and 320 pixel widths. Strict static checks, both deterministic generators, 267 geometry checks, 10 program checks and 96 rendered-asset checks passed. All nine scene compositions and the desktop/mobile opening sequence were visually reviewed.**
Both the static gate (`tests/test_site.py`) and the comprehensive browser gate (`tests/browser_probe.mjs`)
have been fully adapted to the Feedback 1 requirements. The suite verifies:

- **Static structure and semantics:**
  - Plain, large unnumbered headings (`Design philosophy`, `Gallery`, `About me`, `Working together`, `Services`, `Start a project`)
  - Excision of numbering, taglines, and poetic subheadings
  - Green header and nav with WCAG contrast verification (≥ 4.5:1 small text, ≥ 3:1 brand name)
  - Expanded green band and thinner vine geometry
  - Clean excision of `.motion-toggle` and `.floor-plan-link` from marketing DOM, styles, and script
  - Safe inline SVG entrance contract (`<!-- FLOOR_PLAN_START -->` / `<!-- FLOOR_PLAN_END -->`, stage groups `.plan-shell`, `.plan-fixtures`, `.plan-furniture`)
  - Floor-plan model integration (`assets/brand/floor-plan-model.json`): required rooms, geometry and routes
  - Standalone `floor-plan.html` structure and return links
  - Scene people in EVERY scene: generated SVG overlays in the raster's pixel space across the hero and all nine
    gallery studies (`study-1` .. `study-9`), figures placed from measured metadata (`scale = body_height / visible_body_height`),
    finite single 4.4s sequence gated on `.motion-ready` and `.scene-active`, observer trigger and hidden-page pause wiring in `app.js`,
    ground shadow ellipses under foot anchors, stationary occluder clips via `visible_path` evenodd clipPaths outside moving groups,
    and base transforms resting on LAST frame at END position for no-JS and reduced motion
  - Lightbox integration: `#study-viewer .viewer-stage` clones the active study's generated overlay with
    `xMidYMid meet` letterboxing matching `#viewer-image`'s `object-fit: contain`, rewriting all IDs and clipPaths
    with a `viewer-` prefix to prevent collisions, replaying the sequence once on open/change, and removing the clone on close
  - See-through gallery arrow (alpha .30–.40, no blur, 44px)
- **Browser probe execution (headless Chromium with sandbox enabled):**
  - Viewports: 1440×900, 1024×768, 768×1024, 390×844, 320×700
  - Custom `.enter-cursor` on desktop fine pointers; absence of replacement cursor on touch/mobile
  - Entrance via mouse click, keyboard navigation (`ArrowDown`, `Tab` + `Enter`), mouse wheel, and touch swipe
  - Staged reveal animation timings (0s, 0.55s, 1.65s, complete ≤ 4.5s) without infinite sway loops
  - Scene people overlays at every viewport (figure height in source pixels, raster alignment, observer trigger,
    strip dimensions, diverse cast with both Nathan and Carla across scenes)
  - Hero walk and chat sequence pass (1440×900): static until the stage intersects (precondition), first-half walk into the
    backyard (move and frames change), midpoint arrival at 2.2s, second-half stationary chat with ZERO position change while
    frames continue to advance, pause and resume-in-place when the page is hidden (`.document-hidden`), finished state within 4.5s;
    captures 3 hero timepoint screenshots (`hero-scene-t0`, `hero-scene-t2200`, `hero-scene-t4400`) and the 9 gallery scene screenshots
  - Standalone `floor-plan.html` verified directly with dynamic aspect ratio derived from SVG viewBox
  - Gallery editorial layout: uncropped image aspect ratios, white space, varied positioning, overlap ≤ 15%, no caption/image or caption/caption collisions
  - Visual artifact prevention: screenshots captured from document top (`(0, 0)`) with document-coordinate clipping to prevent offscreen fixed skip-link artifacts
  - Inquiry isolation, local mailto link, zero network leaks, no cookies/storage, and 44px tap targets

Browser reports and screenshots are output **only** to `verification/latest/`. Prior evidence in
`verification/feedback-2/` and `verification/feedback-3/` remains untouched.

*Model attribution:* Claude Code Opus 5.5 implemented the initial UI redesign and static gate. Fable 5.1 authored the earlier real-person render pipelines, scene overlay generator, runtime/lightbox integration and initial tests. Following Fable's CLI session-limit diagnostic, the user explicitly authorized AGY Gemini 3.8 Flash (High), which authored the all-scenes Blender renderer and placement manifest and finished the browser checks and documentation. Coordinator receipts distinguish completed and interrupted runs.

*Historical (Feedback 3 and Feedback 2, not proof of this revision):* Feedback 3 previously passed
504/504 browser checks (`verification/feedback-3/browser-report.json`); Feedback 2 passed 276/276
checks (`verification/feedback-2/`).

## Inquiry and content status

The form previews information locally only. It never sends or stores an inquiry.
The user-supplied email is available as a direct mail link. Choosing and
verifying a delivery backend remains a separate decision.

Image captions describe supplied drawings, moodboards and visualizations;
they are not asserted project names or construction outcomes. The floor plan is
a dimensioned architectural concept drawn from a feet-based model; no code compliance or
permit-readiness claim is made. Asset provenance and integrity hashes are in
`assets/brief/manifest.json`, `assets/brief/feedback-2-manifest.json` and
`assets/brand/manifest.json`.
