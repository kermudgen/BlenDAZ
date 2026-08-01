# BlenDAZ - Session Start

> **For AI Assistants**: Read this file first. It's the only file you need for most sessions.
> Update at the end of every session (3-5 min).

**Updated**: 2026-07-07 (soft-pin wrist anchor fix)

---

## Current State

**Pin maintenance is in production** (`daz_bone_select.py`) and now covers rotation, over-extension, and pose preservation. Architecture: pins = hidden empties + COPY_LOCATION/COPY_ROTATION constraints; during hip/torso drags a depsgraph handler re-solves pinned limbs analytically every frame (`_solve_pin_maintenance_frame`). The old native-IK test-script approach was abandoned (solver pops — see vault `Pin Maintenance Solver Journey.md`); the analytical depsgraph-handler approach is what shipped.

New this session (2026-07-03):
- **R-key pin maintenance** — rotating hip/pelvis/spine bones keeps pinned hands/feet/head planted (was translation-only; feet used to visually detach from legs)
- **Reach leash (DAZ Rule 8)** — over-extending a drag translates the hip back instead of silently breaking the pin; radial-only so tangential drag slides along the reach sphere
- **Pose preservation** — per-frame reset now uses pre-drag originals for twist bones, endpoints, and neck-compensation spine bones (identity reset was wiping user-posed foot roll / twists / spine during pinned drags)
- **Production-code tests** — `tests/test_pin_maintenance.py` (6 tests) runs the REAL solver methods headlessly against a synthetic G8 rig fixture in `conftest.py` (no DAZ content needed)
- **Live-rig validated** — via Claude Bridge on a G8M ogre with both hands pinned: hip translate/rotate/leash all converge to ≤2mm endpoint error. Three real-rig bugs found and fixed in the process (arm reach measured to forearmBend.tail instead of the wrist, leash overshoot with multiple pins, residual miss from wrist offset + live LIMIT_ROTATION clamping → per-limb aim feedback). See DRAG_FIX_LOG #005.

New 2026-07-07 (spawned from the 07-03 "found in passing" item):
- **Soft-pin drag wrist anchor fixed** — `start_ik_drag` locked the IK goal at forearmBend.tail (mid-forearm on Diffeo rigs, 225.9mm off the ogre's wrist), and the lock point didn't match the IK effector anyway (hand **tail**, another 184mm). All three points (lock position, .ik.target creation, effector via `use_tail=False` in soft-pin mode) now sit at the pinned child's **head** — the wrist/ankle the pin constraint actually holds. Also fixes pinned-foot leg drags. `fabrik_solver.py` audited clean. New test `tests/test_soft_pin_ik_chain.py`; suite 21 pass / 4 skip. DRAG_FIX_LOG #008. **Feel-test pending** (addon hot-reloaded live; restart Touch first).

---

## What We Did Last Session (2026-07-03)

- Mapped the full pin system (creation → maintenance → bake-back) and gap-analyzed against the 10 DAZ behavioral rules from vault research
- Extracted the hip-pin depsgraph handler body into `_solve_pin_maintenance_frame()`; generalized `_start_hip_pin_drag()` with `transform_op` ('TRANSLATE'/'ROTATE') and `rotated_bone_name`
- Added `_apply_pin_reach_leash()` — world-space deficit correction on the root bone, margin 0.99 (tighter than the solver's 0.995 clamp so they never fight)
- R-key block now routes hip/pelvis/spine rotations with pinned limbs through the pin-maintenance handler (intercepts when the rotated bone can move a pin; maintains ALL pins once active since the leash can translate the hip)
- Added synthetic Genesis-8 armature fixture + `load_production_module()` package-import helper (daz_bone_select uses relative imports) to `tests/conftest.py`
- All tests green headless: 6 new + 11 existing (`blender --background --python tests/run_tests.py`)

---

## Next Up

1. **Feel-test in live Blender** — R on hip/chest with pins, leash behavior at full extension (tests prove positions; feel needs eyes)
2. **Spine-bone G-drag with multiple pinned hands** — soft-pin path still honors only ONE pinned descendant (`find_pinned_descendant` singular); DAZ holds both
3. **Rule 10 full-chain participation** — hip-pin arm solve engages collar+arm only; DAZ engages spine→collar→arm with measured distribution (vault: context profiles)
4. **Collar tuning** — pin-maintenance collar influence (0.45 damped-track) vs DAZ's 20.5% absorption
5. **Unpin preservation check** — delta bake-back exists in `unpin_bone()`; TODO.md still lists the old bug as open — verify and close
6. **PinPool** (from plan, never built) — pre-created empties to avoid per-pin object churn

---

## Don't Forget

- **⚠️ Diff dev↔extension BEFORE any sync** — live bridge sessions edit the installed extension directly; in April 2026 the extension was ~650 lines ahead of dev (pin icons, ik_diag logging, freeze anti-pop) and a careless overwrite lost it (recovered from the Blender 5.0 profile, merged 2026-07-07 — DRAG_FIX_LOG #008)
- **Solver-owned bones need identity reset** — `_solve_pinned_limb` reads the pose matrix as its rest frame, so thigh/shin/collar/shoulder/forearm/neck must be identity before each pass; everything else resets to pre-drag originals (see `_PIN_SOLVER_OWNED_KEYS`)
- **Leash margin (0.99) < solver reach clamp (0.995)** — keep that ordering or they fight at the boundary
- **Check vault before implementing** — `BlenDAZ/IK Stiffness Reference.md`, `Pin Maintenance Solver Journey.md`, `blendaz-research-findings.md`. Don't re-derive values that already exist.
- **Headless tests**: `"D:/SteamLibrary/steamapps/common/Blender/blender.exe" --background --python tests/run_tests.py -- tests/test_pin_maintenance.py -v` (pytest is installed in Blender 5.1's Python)
- **Pin workflow**: hover → click to select → P to pin (Shift+P rotation) → select hip → G to drag / R to rotate
- **Live-Blender bridge**: `scripts/bridge_workflow.py` (port 7777) — needs Blender running with Claude Bridge started
- `daz_shared_utils.py` changes → **full Blender restart**
- **Commit discipline**: wait until things work before committing

---

## Files Most Likely Needed Next Session

| File | Why |
|------|-----|
| `daz_bone_select.py` | All pin code: `_start_hip_pin_drag` / `_solve_pin_maintenance_frame` / `_apply_pin_reach_leash` / R-key block (~line 3060) |
| `tests/test_pin_maintenance.py` | Production-code pin tests (synthetic rig) |
| `tests/conftest.py` | `build_synthetic_g8()`, `load_production_module()` |
| `fabrik_solver.py` | Drag-IK FABRIK (soft-pin arm drags) |

---

## Need Deeper Context?

| File | When to read |
|------|-------------|
| [CLAUDE.md](CLAUDE.md) | Design philosophy, issue status, conventions |
| [INDEX.md](INDEX.md) | Finding a specific file |
| [TODO.md](TODO.md) | Full task backlog |
| [docs/TECHNICAL_REFERENCE.md](docs/TECHNICAL_REFERENCE.md) | IK research, DAZ rig architecture, rotation math |
| [SCRATCHPAD.md](SCRATCHPAD.md) | History of decisions |
| Vault: `BlenDAZ/Pin Maintenance Solver Journey.md` | Why FABRIK/CCD failed, why native IK works |
| Vault: `BlenDAZ/IK Stiffness Reference.md` | Proven stiffness values |
