# BlenDAZ v1.0 Release Plan

**Created**: 2026-08-06
**Trigger**: Competitors (e.g. BGEN Picker's auto-generated rig picker, announced 2026-08-06) are converging on visual-posing UX for Blender. BlenDAZ still has an edge: direct on-mesh posing, DAZ-parity pin maintenance, reach leash, blend pad, and DAZ-specific morph/JCM handling. Ship while that's true.

## What we have (mechanically ready)

- `blender_manifest.toml` — extension format, v1.0.0, GPL-3.0-or-later, Blender 5.0+
- `_make_zip.ps1` — packaging script (ships `daz_bone_select` core + `poseblend/` + `posebridge/` + `Assets/`)
- Headless test suite (`tests/`, pytest-blender) — 21 pass / 4 skip as of 2026-07-07

## Competitive positioning (for store page + video)

| Them (generic pickers) | BlenDAZ |
|---|---|
| Auto-generated 2D picker buttons | Click-drag **directly on the character mesh** — no picker layer at all |
| Generic rigs | **DAZ Genesis 8/9 native**: Diffeo rigs, JCMs, FACS, morph categories |
| No IK story | Pins that **hold through hip drags** (DAZ ActivePose parity), reach leash, FABRIK drag |
| Pose = one rig state | **PoseBlend** blend pad: capture dots, drag to blend, live body-part mask |

## Release blockers (P0)

1. ✅ **Commit current work** (2026-08-06) — tree clean through `fb1ca89`; backups/diag junk gitignored.
2. ✅ **Dev ↔ installed-extension diff** (2026-08-06) — dev strictly ahead; zero unmerged extension edits (one mtime artifact, content-identical). Installed 5.1 extension is a stale Mar–Jul snapshot; replace via release zip.
3. **Interactive posing pass** (NEEDS USER AT BLENDER) — the manual feel-tests never driven: FABRIK drag over panel, hip drag with pins, thigh-twist + ESC, PoseBlend ON_RELEASE/RMB cancel, gizmo dead-zone. Add: **PoseBlend live-mask + dot labels feel-test** (Jul work, untested live) and the 2026-07-07 soft-pin wrist-anchor feel-test (still pending).
4. ✅ **Disable diagnostic logging** (2026-08-06) — `DIAG_ENABLED = False` (was shipping ON, writing logs/ inside the extension per hover/click). `_FABRIK_DEBUG_OVERLAY` already off by default. Full call-site strip deferred to post-1.0.
5. ✅ **Install test** (2026-08-06) — found + fixed **two DOA bugs**: zip was missing `fabrik_solver.py` (hard import → registration failure on every install), and `__init__.py` registered dev-only `daz_bone_select_test`. Zip now validates (`extension validate`) and installs+enables clean in a sandboxed `BLENDER_USER_RESOURCES` profile. Still to do: full register → scan → activate flow with a real G8 Diffeo character (needs user).
6. ✅ **Headless suite green** (2026-08-06) — 22 passed / 4 skipped on the release candidate.

## Should-fix (P1 — ship-with-known-issues candidates)

- Multi-character setup verification (Z-stacking on real characters)
- Pin icon UI live verification (implemented 2026-04-18, never live-tested)
- Spine G-drag honors only one pinned descendant (DAZ holds both) — document as known limitation if not fixed
- PoseBlend known-bug sweep (`default_mask_mode` crash flagged in poseblend/CLAUDE.md — verify fixed/stale)

## Explicitly deferred (post-1.0)

- DAZ→Blender animation bridge (spike planned)
- PoseBlend reach/IK integration, per-frame cursor keys, override grid, onion skin
- Rule 10 full-chain distribution; remaining pin-maintenance parity items

## Launch assets

- Demo video — see [DEMO_VIDEO_STORYBOARD.md](DEMO_VIDEO_STORYBOARD.md)
- User README / quickstart (install → activate → first pose in 5 minutes)
- Store page copy reusing the positioning table above
- 3–5 GIF clips cut from the demo video for the store page / X thread

## Decisions (made 2026-08-06)

- **Distribution**: Paid, via Gumroad and/or BlenderMarket (GPL permits selling; buyers get the code under GPL-3.0)
- **Scope**: All three modules (daz_bone_select core + PoseBlend + PoseBridge) — current `_make_zip.ps1` bundle
- **Target date**: ASAP after P0 blockers clear; release-prep sweep started 2026-08-06
