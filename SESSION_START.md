# BlenDAZ - Session Start

> **For AI Assistants**: Read this file first. It's the only file you need for most sessions.
> Update at the end of every session (3-5 min).

**Updated**: 2026-02-24 (session 3)

---

## ⚡ Current State

**Pin system fully integrated with analytical IK solvers.** Hip pin-driven IK works: drag hip with Blender's native G (supports G+X, G+Y, axis constraints, snapping) while pinned limbs solve analytically via depsgraph handler. Right-click context menu for pin management (pin/unpin translation/rotation, unpin all, toggle pins). Pin constraints muted during analytical drags and restored on release. Test suite: `tests/test_hip_pin_ik.py` (30 tests). Two active sub-projects: **PoseBridge** (Phase 1 testing) and **PoseBlend** (Phase 1 scaffolded).

---

## Active Sub-Projects

| Sub-project | Status | Session Start |
|-------------|--------|---------------|
| [projects/posebridge/](projects/posebridge/) | 🟡 Phase 1 testing | [SESSION_START.md](projects/posebridge/SESSION_START.md) |
| [projects/poseblend/](projects/poseblend/) | 🔴 Pre-first-test | [SESSION_START.md](projects/poseblend/SESSION_START.md) |

**Read the sub-project SESSION_START.md for the one you're working on.**

---

## What We Did Last Session (2026-02-24, session 3)

- **Pin constraint muting for analytical solvers** — Mute pin constraints at drag start, restore on release (cancel-aware: doesn't update pin position on cancel)
- **Right-click context menu** — 6 new operator classes: pin/unpin translation, pin/unpin rotation, unpin selected, unpin all, toggle pins. Dynamic labels based on pin state.
- **Hip pin-driven IK** — When hip has pinned descendants, drag uses Blender's native `translate('INVOKE_DEFAULT')` + depsgraph handler that runs analytical 2-bone solver on each pinned limb. Supports G+X, G+Y, all axis constraints. Cancel restores all bones.
- **Key methods**: `_find_pinned_limbs()`, `_start_hip_pin_drag()`, `_solve_pinned_limb()`, `_end_hip_pin_ik()`, `_remove_hip_pin_handler()`
- **Test suite**: `tests/test_hip_pin_ik.py` — 30 tests covering single/dual/mixed/all-4 pinned limbs, various hip directions, cancel/restore, NaN safety, bilateral symmetry, bone length preservation

---

## Next Up

**Pin system (priority)**:
- Rotation pinning — verify it works correctly with current system
- Torso compensation during hip pin drag (Phase 2 — spine bones should distribute rotation between hip and pinned arm/leg)

**UX enhancements**:
- Drag still operates on last-clicked bone only (Shift+click doesn't affect drag behavior)
- Consider visual feedback for multi-selected bones (count indicator?)

**IK Solver (optional enhancements)**:
- Collar integration Phase 2: adaptive influence based on target angle (more collar for overhead, less for forward)
- Consider similar collar treatment for leg solver (hip bone)

**PoseBridge**:
- Validate all bone rotation mappings in Blender (requires restart first)
- Test all 8 group nodes with correct axis mappings
- Verify bilateral mirroring (shoulders, legs)

**PoseBlend**:
- Fix `default_mask_mode` crash bug (see Known Bugs in CLAUDE.md)
- Implement `draw_label()` with `blf` for dot name rendering
- First Blender test after fixes

---

## Don't Forget

- `daz_shared_utils.py` changes → **full Blender restart** (importlib.reload doesn't work)
- `daz_bone_select.py` changes → reload script or restart
- PoseBlend: `importlib.reload()` works fine (no global shared state)
- All docs are in `docs/` — SCRATCHPAD.md, TODO.md, INDEX.md, TECHNICAL_REFERENCE.md, templates/
- **Analytical IK tests**: `tests/test_analytical_leg.py` (57 tests), `tests/test_analytical_arm.py` (62 tests), `tests/test_hip_pin_ik.py` (30 tests) — run in Blender's Text Editor with a Genesis 8/9 armature in Pose mode
- **Arm solver key difference from legs**: dynamic bend_normal (recomputed each frame) vs locked (computed once). Arms need this due to full spherical ROM.
- **Shift+click multi-select**: works for Blender's R rotation; drag still operates on single bone only
- **Hip pin IK architecture**: native `translate('INVOKE_DEFAULT')` + `depsgraph_update_post` handler. Handler has re-entrancy guard (`_hip_pin_solving`). Cleanup via `_end_hip_pin_ik()` called from LEFTMOUSE RELEASE / RIGHTMOUSE / ESC handlers.
- **Pin constraint muting**: analytical solvers mute `DAZ_Pin_Translation`/`DAZ_Pin_Rotation` at drag start, restore on end. Cancel skips pin position update.

---

## Need Deeper Context?

| File | When to read |
|------|-------------|
| [CLAUDE.md](CLAUDE.md) | Design philosophy, issue status, conventions |
| [docs/INDEX.md](docs/INDEX.md) | Finding a specific file |
| [docs/TODO.md](docs/TODO.md) | Full task backlog |
| [docs/TECHNICAL_REFERENCE.md](docs/TECHNICAL_REFERENCE.md) | IK research, DAZ rig architecture, rotation math |
| [docs/SCRATCHPAD.md](docs/SCRATCHPAD.md) | History of decisions |

---

## How to Update This File

At the end of each session, update:
1. **Updated** date
2. **Current State** — 2-3 sentences on where things stand
3. **Active Sub-Projects** — update status emoji if phase changes
4. **What We Did Last Session** — replace with this session's work
5. **Next Up** — sync with active sub-project TODOs
6. **Don't Forget** — add new gotchas, prune stale ones
