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

1. **Commit current work** — working tree has uncommitted session work (tests/, scripts/, PoseBlend masking+labels, doc edits). Get to a clean, tagged state.
2. **Dev ↔ installed-extension diff** — the installed extension has previously been ahead of the repo (Apr 2026 incident). Diff and reconcile BEFORE building the release zip. (See memory/SESSION_START "Don't Forget".)
3. **Interactive posing pass** (TODO.md "Remaining follow-ups") — the manual feel-tests never driven: FABRIK drag over panel, hip drag with pins, thigh-twist + ESC, PoseBlend ON_RELEASE/RMB cancel, gizmo dead-zone. Add: **new live-mask + dot labels feel-test** (2026-08-06 work, untested live) and the 2026-07-07 soft-pin wrist-anchor feel-test (still pending).
4. **Strip debug/diagnostic code** (TODO.md v1 polish) — `_FABRIK_DEBUG_OVERLAY` drawing, F-curve recording, ik_diag logging, old stubs. Keep bridge-workflow toggle until the final build.
5. **Clean-machine install test** — build zip via `_make_zip.ps1`, install into a fresh Blender 5.x profile, run the register → scan → activate flow with a stock G8 Diffeo import. Consider trimming dev-only files (`diagnose.py`, `force_register.py`, `register_only.py`) from the ship list or confirming they're user-facing.
6. **Headless suite green** on the release candidate.

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
