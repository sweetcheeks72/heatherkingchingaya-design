# Local source transfer — 8 October 2026

The repository root contains the exact latest tested website (89 files), including the updated floor plan, nine-scene gallery, and corrected opening walk/turn/sit animation. `website-source-manifest.json` records every source hash; `validation-receipt.json` records the completed local checks. Existing remote-only verification images remain unchanged and are historical; use this receipt for the latest source.

## Editable rendering source

`research-people/build_hero_contact_fix.py` is the current hero renderer. `research-people/build_all_scenes_natural.py` renders the current interior profiles. Their complete local Python import closure is included unchanged. These scripts procedurally construct the Blender scene; no saved `.blend` file existed locally. Floor-plan source and generators are included under `assets/brand` and `scripts`.

The runtime sprites already live in `assets/people/scenes/`; the website runs without Blender or the raw scans. Scene placements, timing, physical character size and stride calibration are in `assets/people/scenes.json` and per-strip JSON metadata. The character motion is constrained skeletal animation over raster architecture: chair alignment is visually calibrated, not a full chair collision/force simulation.

## Required but restricted input assets

**Raw Renderpeople FBX models, textures, archives and previews were not uploaded.** This repository is public. Renderpeople terms sections 2.5, 4.2(b) and 4.3(b) apply to the free assets and prohibit their public redistribution; rendering is permitted under 4.1(a). `restricted-dependencies.json` lists every excluded file, size and checksum. Obtain the three named models directly from the official free-model page under an appropriate licence, and keep them outside version control. Do not upload or commit their raw files here. No alternative licence, purchase, account or visibility change was made.

Place licensed files in `research-people/source/`, `research-people/source-carla/`, and `research-people/source-sophia/` exactly as listed in the dependency manifest. Some archive texture filenames contain a literal backslash; preserve the expected paths used by the renderer. Cloud re-rendering is blocked until those inputs are acquired legitimately; website editing and previewing are fully available now.

Blender 4.5.14 LTS was used locally. With licensed inputs available, run from repository root:

```sh
blender --background --factory-startup --disable-autoexec --python research-people/build_hero_contact_fix.py -- --all --samples 32
blender --background --factory-startup --disable-autoexec --python research-people/build_all_scenes_natural.py -- --all --samples 32
```

The current entry points explicitly write beneath `research-people/hero-contact-fix/` and `research-people/all-scenes-natural/`. Older support modules retain historical defaults pointing to a sibling `site` folder; use the current entry points, not those defaults. Render outputs do not automatically overwrite the website. Reconcile regenerated metadata with the current placement manifest, preserve physical source pixels/metre, update the strips and metadata together, then run `python3 scripts/build_scene_overlays.py --write` and the repository checks.

## Transfer and publication boundary

Destination approved by the user: `sweetcheeks72/heatherkingchingaya-design`, branch `codex/feedback-2-review`, draft PR #1 targeting `main`. The existing unpushed local chain ending at `a541cbbeaaf6312507e901e765235e3f21a47740` remains untouched locally. This transfer uses a clean checkout of remote `d87ebd85fe8c1818bc50e7de4bfcdb755745685f` and adds the final source as a new descendant commit, avoiding stale intermediate files and history. No merge, deployment, repository visibility change or design development is part of this transfer.
