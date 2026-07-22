# Room in Formation

This is a dependency-free static site, published publicly on 2026-07-21 with owner
authorization. It is served by GitHub Pages from `main` at
<https://sweetcheeks72.github.io/heatherkingchingaya-design/>.

Publication status changed; the constraints below did not. They still apply.

## Constraints

- Preserve live HTML text and accessible semantics.
- Do not add tracking, network requests, external fonts, or external links.
- Motion is permitted as of 2026-07-21 by owner ruling, under conditions the gate enforces:
  every motion rule lives inside `@media (prefers-reduced-motion: no-preference)`; a
  `@media (prefers-reduced-motion: reduce)` block disables animation, transition and smooth
  scrolling; and reveal states are gated on the `motion-ready` class that `app.js` adds, so
  content is never hidden when the script fails. Do not add motion outside that structure.
- Do not invent project narratives, outcomes, credits, contact details, or social URLs.
- Noel imagery may be described only as visual correspondence, moodboard, or spatial visualization; never imply causation or construction.
- The inquiry is a local interaction prototype and must never claim that a message was sent.
- Keep the prototype usable at 320px wide and with a keyboard.

## Open decision — inquiry delivery

The inquiry form has no delivery route, and two independent rules enforce that:

- `tests/test_site.py` asserts the form has no `action`/`method`, and bans `fetch`,
  `XMLHttpRequest`, `sendBeacon`, `localStorage`, `sessionStorage` and WebSocket in `app.js`.
- The constraints above forbid network requests and external links, and forbid
  inventing contact details. No contact address exists anywhere in this repo.

A form service (Formspree, Netlify Forms, etc.) requires relaxing both, and is an
owner decision — not a maintenance change. A `mailto:` link is the only route that
passes the gate unmodified, but it needs a real address and exposes it to scrapers.
Until one is chosen, the on-screen "no message was sent" copy must stay accurate.

## Verification

Run all three before handoff:

- `python tests/test_site.py` — static structure, evidence claims, motion guard, asset hashes.
- `node --check app.js`
- `node tests/browser_probe.mjs` — renders at 1440/390/320 in headless Edge and checks hero
  art direction, horizontal overflow, image loading, 44px action targets and the inquiry path.
  Needs a local server on 4173 (`python -m http.server 4173`).

The browser gate is authoritative for anything layout- or viewport-dependent. Do not
substitute a scripted DOM probe in an automation browser: if the page is not being
composited, CSS transitions stay frozen at their start value and IntersectionObserver
never fires, which reads as broken motion when the motion is fine.

