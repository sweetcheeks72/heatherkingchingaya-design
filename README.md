# Room in Formation — static site

Desktop/mobile homepage and inquiry site for King Chingaya Design.

Deployed publicly on 2026-07-21 with owner authorization, served by GitHub Pages
from `main` at <https://sweetcheeks72.github.io/heatherkingchingaya-design/>.

## Run locally

From this folder:

```powershell
python -m http.server 4173
```

Open `http://127.0.0.1:4173/`.

## Verify

```powershell
python tests/test_site.py
node --check app.js
```

## Inquiry status

The inquiry form never sends or stores data. It previews the submission locally and
says so on screen. A verified delivery route is still required — see the open decision
in `.claude/CLAUDE.md`.

