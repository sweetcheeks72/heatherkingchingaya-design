# Website direction — 3 October 2026

## Chair-contact correction — 7 October 2026

Direct user request: people should walk together, turn and sit without passing through chairs; research the physics of environmental interaction. User authorized local work and Astra agents at low reasoning effort.

The opening retains the original scanned people, source image, chair destinations and finite 8.8-second budget. Contact-aware motion replaces the hip-centered pose morph: arrival in front, separately supported turning steps, fixed shoe position/orientation during lowering, backward pelvis travel and forward torso inclination. Per-shoe sole measurements remove the former floating feet. Walking travel is matched to the source stride distance. Physical character scale is preserved independently of the sprite camera fit.

Research: Kovar, Schreiner and Gleicher, Footskate Cleanup for Motion Capture Editing (University of Wisconsin, 2002); Jeon et al., Trunk kinematics and muscle activation patterns during stand-to-sit movement (Gait & Posture, 2021); Blender IK and rigid-body manuals. See private hero-chair-correction/physics-research.json for source links and application.

This is contact-constrained skeletal animation composited over an existing raster scene. Chair placement is visually calibrated; full chair-mesh collision dynamics and biomechanical force balance are not simulated. Other scenes, the floor plan, content and typography remain unchanged. Local review only; no publication.

## Approved natural people across all scenes — 4 October 2026

The user approved the isolated reference-led café pair and asked to apply that pose and motion style throughout, with activity-specific timing and scene-matched color. Direct Codex implementation; no external coding-agent handoff.

All nine scenes retain the original Nathan/Carla scans and original texture colors. Dedicated sofa, bedroom and booth profiles fit the actual seating. Lighting is rendered per scene (key/fill color, exposure, softness and direction), without repainting skin or clothing. Seated hands use thigh contact targets; lower bodies remain planted. Conversation gestures ease in and out, then rest. Standing profiles retain captured asymmetric upper-body motion.

Every actor has an explicit duration and delay within an 8.8-second total budget. People start at different times; every take runs once and holds its final pose. The opening retains the walk to the two existing chairs, turn, sit and settled hold. Offscreen scenes, hidden documents, and gallery scenes covered by the viewer pause in place and resume without restarting. Reduced motion and no-JS show the final static poses.

Approval covers local propagation of this direction. Final all-scene visual review precedes any push or publication; publication remains on hold. Scene photographs, floor plan, content, page layout and typography are unchanged.

## People cleanup — 4 October 2026

Direct user request: clean up the people across the images. Codex implemented this pass directly.
All nine scenes retain animated licensed Nathan/Carla scans and their original textures.
Interior strips now use 320×480 frames with 96 distinct authored-motion samples; the sofa has
its own camera angle. Relaxed arms replace repeated folded-arm poses; café/booth figures face
the table, the terrace figure faces outward, and standing feet remain planted and uncrossed.
Softer warm lighting, measured ground-shadow anchors, reduced blurred contact shadows, adjusted
seat placement and a corrected non-overlapping coffee-table occlusion improve scene integration.
The 160-frame opening retains walking to the two existing chairs and sitting, with relaxed hands.
Original scene images, the floor plan, page typography and layout are unchanged by this pass.
These remain rendered overlays; visual acceptance is pending. Publication remains on hold.


## Latest direct revisions — 3 October 2026 (America/Chicago)

This section supersedes conflicting historical specifications below. Local review only;
publication remains on hold. Codex implemented this pass directly at the user's request.

- Continuous kitchen worktop along the pantry wall; pantry entrance relocated to the south.
- Coffee table remains centered on its resized rug, with 18 inches clear of the sectional return
  and 24 inches clear of the north seating run. Coat and laundry doors retract into wall pockets.
- Add a north-facing primary-bath privacy window and a 22-foot dining/living courtyard slider.
- Sitting-area chairs move to the south side. Guest bedroom 1 has its bed/nightstands on the
  south wall, full-width north built-in storage, and no desk. Guest bedroom 2 grows from
  10 to 13 feet wide by reducing laundry width from 10.5 to 7.5 feet; south headboard and west closet.
- Main type uses brighter green #146023 (7.07:1 on cream). Gallery titles use bundled Fraunces
  at weight 300 in black. Footer is light sage #e2e9d9 with two green wordmark shades.
- Backyard figures walk to the two existing chairs, turn and sit. 160 rendered frames over
  8.8 seconds; travel occupies the first 4.4 seconds. Final seat anchors are measured in Blender.
  Interior scenes use the reviewed 96-frame authored-motion candidate over the same finite duration.
  Visual approval is pending; mechanical checks do not imply user approval of poses.
- Reduced-motion and no-JavaScript modes show the final seated/settled frame. Entry plan reveal
  retains its original <=4.5-second limit. Source photos, scanned appearances and licenses are unchanged.


## Feedback 1 — current approved revision (`Feedback 1.pdf`, 3 October 2026)

The user explicitly confirmed that `Feedback 1.pdf` is the latest approved revision,
superseding conflicting choices in Feedback 3 and Feedback 2. Source file: `Feedback 1.pdf`.
The nine-image gallery, footer treatment, approved content, font licences and local-only
inquiry isolation remain applicable.

#### Requirements from Feedback 1 (and latest user revisions)

1. **Plan-only entrance & oval Enter cursor:** The opening screen displays the conceptual Dallas
   residence floor plan. The former "Step inside" button has been completely removed. The floor-plan link
   (`a.enter-plan`) is the sole entrance control for pointer, touch, keyboard, and no-JS fallback. On desktop
   fine-pointer devices, a custom oval `.enter-cursor` (104×52px, noticeably width > height) appears when hovering
   over the plan, hiding the native cursor only while the replacement is active (`pointerleave` restores native
   cursor immediately). Hovering does not trigger site entry; clicking the plan enters `#main`. Real link semantics
   and keyboard navigation (`Tab` + `Enter`, `ArrowDown`), mouse wheel scrolling (`deltaY > 0`), and touch gestures
   retain native interaction and full accessibility without any replacement cursor.
2. **Staged plan reveal:** Under `prefers-reduced-motion: no-preference` and script enhancement,
   the floor-plan elements reveal in three stages: walls and trees at start (0s), fixtures and
   flooring after 0.55s, and furniture after 1.65s. All finite animations complete within 4.5s,
   leaving clean static vectors without continuous loops. Under reduced motion or without
   JavaScript, the full diagram displays statically from the start.
3. **Inline SVG floor plan entry contract:** The entrance plan is staged between
   `<!-- FLOOR_PLAN_START -->` and `<!-- FLOOR_PLAN_END -->` as an inline
   `<svg class="floor-plan" aria-hidden="true" focusable="false">` with derived viewBox (typically
   1600×1200) and stage groups `.plan-shell`, `.plan-fixtures`, and `.plan-furniture`. During
   model and generator integration, a placeholder `<img>` is safely accommodated until the
   generator phase runs.
4. **Editable floor-plan model & Dallas residence program:** The floor-plan design is driven by
   an editable model (`assets/brand/floor-plan-model.json`) and deterministic generator
   (`scripts/build_floor_plan.py`). The model currently defines sixteen named spaces across this program
   (latest user revisions U1–U8 applied by the plan workflow):
   - Central courtyard with architectural tree foliage resembling supplied symbols
   - Kitchen with a narrower pantry, west counter, larger island with three stools, and a laundry / utility
     room entered directly from the kitchen
   - Dining room with a larger table seating eight
   - Living room with larger furniture toward the front wall, coat closet and direct exterior entry
   - Three bedrooms: primary bedroom with primary bath and dressing (after the supplied bathroom/dressing
     reference), guest bedroom, and a second guest bedroom in the former gallery, both guest rooms with closets
   - Guest bath with the tub across the east wall
   - Hallway / sitting area and a second hallway for circulation
5. **Dimensional flexibility & Dallas building code basis:**
   - *Dimensional flexibility:* The user confirmed that the designer may freely choose dimensions
     for the single-storey Dallas concept. This resolves the previous measurement blocker.
   - *Base building code:* 2021 International Residential Code (IRC), verified from public
     municipal copy (R304.1–2 room area ≥ 70 sqft / 7ft horizontal dimension; R305.1 ceiling
     height ≥ 7ft; R310.1–2 emergency escape/rescue opening ≥ 5.7 sqft net clear, ≥ 20in width,
     ≥ 24in height, sill ≤ 44in; R311.2–3 / R311.6 egress door net clear 32in × 78in, 36in landing
     depth, 36in hallway).
   - *Dallas local amendments:* City of Dallas Chapter 57 amendments (city-published 2021 residential amendments,
     effective May 12, 2023: structural load path R301, bathroom ventilation R303.3, fixture
     spacing R307, toilet-wall blocking R307.4, egress door security R311.2.1, security measures
     Chapter 45) and administrative amendments Ordinance 33099 / 25-0688.
   - *Disclaimer:* **No claim of certified code compliance, permit readiness, or structural/MEP
     engineering warranty is made.** This is an architectural schematic concept for design review.
     Citations are recorded in documentation only to avoid marketing UI clutter.
6. **Green header/nav & brand area:** The sage band (`#78926d` / `--sage-band`) has expanded
   vertical padding, and the entire top navigation sits on this green field. The top black wordmark
   is replaced with an explicit elegant `[ LOGO ]` placeholder (`a.wordmark.logo-placeholder[data-placeholder="logo"]`)
   with accessible home link brand label. In section `#brand`, the large live white title “King Chingaya Design”
   sits almost touching the bottom of the band within bounds readable with no unintended clipping at all widths
   (`padding: max(64px, 12vw) 0 max(4px, 0.5vw)`). A finer, thinner jasmine vine strand passes through the letters
   with dynamic flower clusters (no fixed 5-cluster assertions). Continuous sway animations are removed to ensure static rest.
7. **Stronger green body & delicate black gallery titles:** Main page text uses a bolder, stronger green
   (`--ink: #1c4424;` font-weight 500 for body, 600 for headings/nav). Gallery image titles are styled in
   delicate black (`#111111`, font-weight 350, fine letterforms) with thin rules.
8. **Scene people in EVERY scene with 64-frame hero walk/chat and 32-frame interior motion:**
   By the user's explicit direction (3 October 2026), animated realistic, diverse people appear across EVERY scene
   on the website: the hero architectural model and all nine gallery studies. Each scene receives a generated decorative
   inline SVG overlay (`.scene-overlay`, `aria-hidden="true"`, `focusable="false"`) produced deterministically by
   `scripts/build_scene_overlays.py` from `assets/people/scenes.json`:
   - *Hero scene (study-1):* In the top home intro section, the hero image "Architecture in miniature"
     (`assets/brief/architectural-model.webp`, 1800×1092, unchanged) spans the page with its own aspect ratio; the caption
     reads "Architecture in miniature / Architectural model". Its overlay uses `preserveAspectRatio="xMidYMid slice"`.
     Nathan and Carla arrive together in the backyard: during the first half (`move_until: 0.5`, 2.2s of 4.4s), they walk east
     into the backyard; at 2.2s they stop, turn to face each other, and chat for the remaining 2.2s while holding position
     (zero position change after stop while chat frames continue). Their strips hold 64 distinct frames rendered from
     licensed Renderpeople scans (Nathan animated 003 and Carla rigged 001).
   - *Gallery studies 1–9:* Inside each `a.study-image`, a matching `.scene-overlay` uses `preserveAspectRatio="xMidYMid meet"`
     to align with the photo raster. Interior studies feature 32-frame motion strips at 192×256 or 256×384, animating seated
     and standing figures (both Nathan and Carla appear across the studies for a diverse group).
   - *Placement & stationary occluders:* Figures are placed according to measured strip metadata (`scale = body_height / visible_body_height`),
     with ground shadow ellipses under foot anchors and stationary occluder clips via `visible_path` evenodd clipPaths outside
     the moving actor group so tables and railings remain stationary while figures move behind them.
   - *Lightbox integration:* In `#study-viewer`, `.viewer-stage` clones the active study's generated overlay with `xMidYMid meet`
     letterboxing matching `#viewer-image`'s `object-fit: contain`, rewriting all IDs and clipPaths with a `viewer-` prefix to
     prevent collisions. Opening/changing studies replays the scene once as an explicit user interaction; closing cleans up the
     overlay and stops animations.
   - *Runtime & accessibility:* Single 4.4s finite sequence starting on first viewport intersection (IntersectionObserver, threshold 0.15;
     gated on `.motion-ready`). Hiding the page pauses animations in place (`.document-hidden`), resuming without restart. Without
     JavaScript or under `prefers-reduced-motion: reduce`, all figures rest statically on their LAST frame at their END position
     (chat rest pose), ensuring complete visibility.
9. **Restaurant cluster layout:** Studies 7, 8, and 9 (`restaurant-window.png`, `restaurant-booths.png`,
   `restaurant-counter.png`) are clustered coherently: studies 7 and 8 side by side with slight vertical offset,
   and study 9 wider underneath centered, closer grouped than unrelated gallery works, with a tidy contiguous stack on mobile.
10. **See-through arrow affordances:** Image open arrows are 44px hit targets on a mostly transparent disc
    (`rgba(248, 245, 238, .35)`, no backdrop blur) with a thin arrow (`font-weight: 300`), near-opaque on hover/focus.
11. **Marketing DOM cleanup:** The "View full floor plan" link, pause-motion control (`.motion-toggle`), and
    entrance "Step inside" button have been excised completely from the marketing page DOM, styles, and scripts.
12. **Standalone review artifact (`floor-plan.html`):** Retained as an unlinked review artifact.
    It displays the complete architectural plan unrotated and uncropped at its natural aspect ratio
    (derived from the SVG viewBox), providing links to inspect the raw SVG, download it, and return
    to `index.html#main`.
13. **Section headings and copy cleanup:** All section numbering and accordion numerals are removed.
    Headings are rendered as large, plain, unnumbered titles in document order:
    `Design philosophy` (`#philosophy`), `Gallery` (`#projects`), `About me` (`#about`),
    `Working together` (`#process`), `Services` (`#services`), and `Start a project` (`#inquiry`).
    Poetic subheadings and the three philosophy taglines have been removed.

### Implementation and review status

The initial Feedback 1 visual restructuring and static gate (`tests/test_site.py`) were authored
by Claude Code Opus 5.5. After Claude reached its account session limit, Google Antigravity authorized
model Gemini 3.8 Flash (High) implemented the latest user revisions (removal of "Step inside" button, oval
Enter cursor, logo placeholder, stronger green typography, delicate black captions, restaurant cluster,
enlarged translucent arrow affordances, hero architectural model with backyard walker silhouettes), completed
the browser gate adaptations (`tests/browser_probe.mjs`, including fixing `ReferenceError: g is not defined`),
adapted the static gate, and authored factual documentation. That run was interrupted by a network error after
its edits; Claude Fable 5.1 (`claude-fable-5-1`) then reviewed and finished only the incomplete parts: walker
placement clear of the glazed block and of each other, 86/88 px figures with separate limbs and a finite stride,
a crossing that no longer fades the visible figures out, the hidden-page class applied at load, tests that exercise
the observer trigger, pause/resume and reduced/no-JS states, and the factual corrections in this file and the README.
Gemini's completed changes are retained; the floor-plan model, generator and inline SVG are owned by the plan workflow.

The latest direct user request expands animated people across EVERY scene (all nine gallery studies + hero architectural model),
introducing a 64-frame hero walk/stop/chat sequence, 32-frame interior motion strips, deterministic overlay generation, and
replaying lightbox integration. Fable 5.1 authored the overlay generator, runtime styling, lightbox cloning and initial static/browser checks. After Fable's CLI returned a session-limit diagnostic, the user explicitly authorized AGY Gemini 3.8 Flash (High). AGY authored the new Blender scene renderer and placement manifest and completed the browser checks and documentation. Actual model receipts are recorded by the coordinator.

The subsequent pose revision responds to the user’s report of unnatural poses: native mocap finger curl replaces flat hands, head yaw replaces sideways neck tilt, seated forearms rest toward the thighs, the café pair faces inward, and standing poses use slight asymmetry. AGY Gemini 3.8 Flash (High) authored the correction; the coordinator calibrated Nathan’s seated forearm angle after rendering. A free authored idle donor was inspected but is not used in the final assets.

The completed all-scenes expansion passed 774/774 browser checks across five viewport widths, the strict static gate, both deterministic generators, 267 independent geometry checks, 10 program checks and 96 rendered-asset checks. Actual Blender poses and all nine browser scene compositions were visually reviewed. Browser output is in `verification/latest/`.

Draft PR <https://github.com/sweetcheeks72/heatherkingchingaya-design/pull/1> contains the separately
reviewed Feedback 2 snapshot. Feedback 3, Feedback 1 and the latest all-scenes revisions passed local verification; publication remains coordinated separately. The original dirty checkout is preserved unchanged.

---

## Feedback 3 — historical revision (`Feedback 3.pdf`, 3 October 2026)

The user explicitly asked to apply `Feedback 3.pdf` to the current local website.
The two actual PDF pages and both reference images were inspected. Source SHA-256:
`3e5155f607ed12d9bd23d579d817b255855441e22e982fb7427ef5c27c53a74c`.
These requirements superseded conflicting entrance and floor-plan choices in the
historical Feedback 2 record below. The nine-image gallery, footer treatment,
approved content, font licences and local-only inquiry behavior remain applicable.

1. The opening screen shows the floor plan, with a restrained overlaid entrance
   control. The header and company name appear after entering the website.
2. The white company name sits lower in the sage band and has taller live letters.
   A single vine reveals across it, with compact hanging flower groups recomposed
   from the unchanged jasmine artwork. Growth, bloom and sway respect pause and
   reduced-motion preferences; no-JS content remains visible.
3. The living room has a sliding opening across almost all of its common wall with
   the courtyard. Its larger dotted rug reaches the furniture edges; both chairs
   sit on the right and face the west window.
4. The courtyard's lower-left bench is removed; the lower-right feature is a
   fountain, and its central tree has a leafy canopy.
5. The kitchen island and stools are moved east, clear of the courtyard door.
   The diagram uses two stools to keep this route clear.
6. The bedroom dresser sits against the left wall; its adjacent circular element
   is removed.
7. The bathroom/dressing suite follows the supplied reference: upper-left shower,
   central oval tub, upper-right WC, double basins flanked by closets, dressing
   table and seat below, and a lower storage run. It uses the former garden-room
   bay and a corridor from the bedroom. This spatial interpretation is presented
   for review in the complete plan; it is conceptual and not to scale.
8. `floor-plan.html` shows the entire unrotated, uncropped 1600×1040 diagram, with
   return, standalone-image and SVG download links. The link to this page sits
   inside the main website.

### Implementation and review status (Feedback 3)

The visual implementation and verification code were authored by actual Claude Code
Opus 5.5 subagents. Codex coordinated file transfer, rendered inspection, test
execution, factual documentation and artifact packaging. Final verification status
is recorded in README and `verification/feedback-3/browser-report.json`.

The user subsequently required no Haiku use, including auxiliary calls. Further
Claude inference was paused until a session-only managed policy was verified in the
same process before any task prompt: Haiku denied, exact `claude-opus-5-5` allowlist,
no fallback, and family/background/subagent routing pinned to Opus. The final test
synchronization patch was authored by an actual Opus subagent under that policy;
Codex applied its exact returned edit after a CLI file permission pattern did not
match. No global settings or credentials changed. This is client enforcement, not
visibility into provider internals. Historical main/subagent metadata and reported
usage show `claude-opus-5-5`; they cannot establish the model of every unreported
auxiliary request before the policy was added.

Feedback 3 is local and is not authorized for publication in this task. Draft PR
<https://github.com/sweetcheeks72/heatherkingchingaya-design/pull/1> contains the
separately reviewed and authorized Feedback 2 snapshot. The original dirty checkout
has been preserved unchanged.

## Feedback 2 — historical approved feedback (`Feedback 2.pdf`, 3 October 2026)

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
