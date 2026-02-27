# BlenDAZ - Session Start

> **For AI Assistants**: Read this file first. It's the only file you need for most sessions.
> Update at the end of every session (3-5 min).

**Updated**: 2026-02-24 (session 6)

---

## Current State

**Character init system complete. N-panel reorganisation designed, pending implementation.** BlenDAZ now has a full onboarding flow for DAZ characters with geografts: `register_only.py` → Snapshot Pre-Merge → merge in Diffeomorphic → Remap Face Groups. Face group highlights survive module reloads via auto-rebuild from reference mesh. N-panel structure agreed (BlenDAZ / Touch / PoseBridge / PoseBlend) but not yet built — four open questions documented in `docs/TODO.md` (Next Session section). `daz_bone_select.py` pin system stable, highlight system working on merged meshes.

---

## Active Sub-Projects

| Sub-project | Status | Session Start |
|-------------|--------|---------------|
| [projects/posebridge/](projects/posebridge/) | 🟢 Demo-ready, visual polish | [SESSION_START.md](projects/posebridge/SESSION_START.md) |
| [projects/poseblend/](projects/poseblend/) | 🔴 Pre-first-test | [SESSION_START.md](projects/poseblend/SESSION_START.md) |

**Read the sub-project SESSION_START.md for the one you're working on.**

---

## What We Did Last Session (2026-02-24, session 6)

**Character init system + face group remap + N-panel reorganisation design:**
- **`register_only.py`** — new lightweight startup script that registers all modules without requiring an armature. Entry point for Tier 2 workflow (snapshot before merge).
- **`init_character.py`** — three operators: `blendaz.snapshot_premerge` (creates mannequin copy, records reference), `blendaz.remap_face_groups` (face center remap post-merge), `blendaz.merge_and_remap` (auto Diffeomorphic merge + remap).
- **`build_from_reference_mesh()`** in `dsf_face_groups.py` — face center matching at 4dp precision; handles geograft merge polygon index shift transparently.
- **Auto-restore on reload** — `invoke()` in modal operator now calls `build_from_reference_mesh` if `get_or_create` returns invalid FGM and `blendaz_init_status == 'ready'`. Module reloads no longer lose the remap.
- **Live hot-push** — `_live_instance` class var on modal operator; `_run_face_group_remap` pushes updated FGM into running modal so Remap button takes effect without restart.
- **`used_face_groups` fix** — only blocks vertex-weight fallback when DSF actually returned polygons (not just when FGM is valid).
- **BlenDAZ Setup sub-panel** in `posebridge/panel_ui.py` — status indicator with icon, context-sensitive buttons, collapsed by default once Ready.
- **N-panel reorganisation design** — agreed structure: BlenDAZ root / Touch / PoseBridge (Body Controls + Face Controls + Settings) / PoseBlend. Diagram + open questions saved in `docs/TODO.md` Next Session section.

---

## Next Up

**N-Panel reorganisation (answer open questions first):**
- Decide: Rotation Limits + IK Settings — move to Touch > Settings or drop?
- Decide: Body Controls + Face Controls — DEFAULT_CLOSED or open?
- Decide: "Open in Viewport" — locks to camera immediately or draw-handler only?
- Decide: Stop BlenDAZ — stops everything or just Touch?
- Then implement — full task list in `docs/TODO.md` "Next Session" section

**Character init — test with pre-merge character:**
- Run `register_only.py` on the pre-merge test character
- Click Snapshot Pre-Merge State
- Merge geografts in Diffeomorphic
- Click Remap Face Groups
- Run `setup_all.py` — confirm sections are clean (not janky)

**PoseBridge (after N-panel done):**
- N-Panel: Categorized morph sliders (Brow, Eyes, Mouth sections)
- BUG: Head bone selection fails from deselected state
- BUG: Mesh highlight shows in PoseBridge viewport instead of 3D viewport
- Pin system debugging session (feet/shin disconnect, arm snapping)

**Pin system:**
- **BUG: Unpin pose preservation** — snaps to rest on unpin. Three approaches failed. Try `bpy.ops.constraint.apply()` or set `pose_bone.matrix` directly.

**PoseBlend:**
- Fix `default_mask_mode` crash bug
- First Blender test after fixes

---

## Don't Forget

- `daz_shared_utils.py` changes → **full Blender restart** (importlib.reload doesn't work)
- `posebridge/core.py` changes (PropertyGroup) → **full Blender restart**
- `daz_bone_select.py` changes → reload script or restart
- PoseBlend: `importlib.reload()` works fine (no global shared state)
- All docs are in `docs/` — SCRATCHPAD.md, TODO.md, INDEX.md, TECHNICAL_REFERENCE.md, templates/
- **New startup scripts**: `register_only.py` (no armature needed — for init workflow), `setup_all.py` (full setup with character)
- **Character init workflow**: `register_only.py` → Snapshot Pre-Merge → merge in Diffeomorphic → Remap Face Groups → `setup_all.py`
- **Face group remap persistence**: stored in `posebbridge_settings.blendaz_reference_mesh_name` (survives module reload). Auto-restored in modal `invoke()` if DSF mismatch + status='ready'.
- **`_live_instance`** on `VIEW3D_OT_daz_bone_select` — set in invoke(), cleared in finish(). Used by `_run_face_group_remap` to hot-push FGM updates into running modal.
- **Analytical IK tests**: `tests/test_analytical_leg.py` (57 tests), `tests/test_analytical_arm.py` (62 tests), `tests/test_hip_pin_ik.py` (30 tests), `tests/test_pin_system.py` (30 tests, 78 assertions) — run in Blender's Text Editor with a Genesis 8/9 armature in Pose mode
- **Arm solver key difference from legs**: dynamic bend_normal (recomputed each frame) vs locked (computed once). Arms need this due to full spherical ROM.
- **Hip pin IK architecture**: native `translate('INVOKE_DEFAULT')` + `depsgraph_update_post` handler. Handler has re-entrancy guard (`_hip_pin_solving`). Cleanup via `_end_hip_pin_ik()` called from LEFTMOUSE RELEASE / RIGHTMOUSE / ESC handlers.
- **Pin constraint muting**: Only `DAZ_Pin_Translation` muted during analytical drags. `DAZ_Pin_Rotation` stays active so pinned bone orientation is maintained by the constraint.
- **R key handler**: Intercepts R for hip + spine chain bones when head is rotation-pinned. Passes through for all other bones. Pin override: R on a rotation-pinned bone mutes constraint, passes through to native rotate, updates pin on confirm.
- **Head rotation solver**: `_solve_pinned_neck()` uses `correction @ bone.rotation_quaternion` (compose, not replace). Partial chains via `_find_pinned_head(armature, rotated_bone_name=X)`.
- **Head translation solver**: Neck IK uses `cross(bone_Y, target_dir)` for bend normal (not fixed forward heuristic).
- **Driven rotation bones**: `_get_driven_rotation_bones()` detects jaw/tongue/eye bones with rotation_euler drivers — must stay Euler mode or FACS joint morphs break.
- **KNOWN BUG**: `unpin_bone()` doesn't preserve visual pose — bone snaps to rest on unpin. Three approaches failed.

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
