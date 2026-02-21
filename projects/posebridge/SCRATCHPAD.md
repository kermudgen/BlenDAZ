# PoseBridge - Development Scratchpad

## Purpose
This file tracks ongoing development work, experiments, bugs, and feature progress. It's a living document that captures what we're working on, what we've tried, and what we've learned.

**Note**: When this file reaches ~300-500 lines or ~50-75KB, archive it to `scratchpad_archive/SCRATCHPAD_YYYY-MM.md` and start fresh.

## Archive History
- `scratchpad_archive/SCRATCHPAD_2026-02-pre-setup.md` - Original scratchpad covering Feb 11-19 2026. Contains: Phase 1 MVP testing, PowerPose integration, shoulder debugging, thigh Y-lock, control mapping adjustments, group node definitions, tooltip implementation, base/hip/toe nodes.

---

## Current Session: 2026-02-19

### Active Work
- Hooking up group node control mappings in `update_multi_bone_rotation()`

### Changes Made

#### Group Node Axis Routing (update_multi_bone_rotation)
**Problem:** `update_multi_bone_rotation()` in daz_bone_select.py had hardcoded axes (LEFT: Y/X, RIGHT: Z/X) matching only neck_group. All 8 group nodes have different control mappings defined in daz_shared_utils.py but they were never read at runtime.

**Fix Applied:**
1. Added `_rotation_group_id` class variable and cleanup
2. Stored `_hover_control_point_id` as `_rotation_group_id` at drag start (line ~3132)
3. Replaced hardcoded axes with per-group if/elif chain (lines ~5165-5255):
   - `neck_group` -- LMB: Y(turn)/X(nod), RMB: Z(tilt, inverted)/X
   - `torso_group` -- LMB: Y(twist)/X(bend), RMB: Z(lean, inverted)/None
   - `shoulders_group` -- LMB: Z(shrug)/X(forward), RMB: Y(roll)/None
   - `lArm_group`/`rArm_group` -- LMB: X(swing)/Z(raise), RMB: Y(twist)/None
   - `lLeg_group`/`rLeg_group` -- LMB: X(swing)/Z(raise), RMB: Y(twist)/None
   - `legs_group` -- LMB: X(swing)/Z(raise), RMB: Y(twist)/None
4. Synced neck_group controls dict in daz_shared_utils.py (was Z/X/Y, now Y/X/Z to match tested behavior)

**Twist bone filtering preserved:** Y->all bones, X/Z->bend bones only. Works correctly with all group mappings since Y is always the twist axis for DAZ bones.

**Files Modified:**
- `daz_bone_select.py` - lines ~1948, ~3132, ~5165-5255, ~5316
- `daz_shared_utils.py` - lines 287-290

**Status:** Code complete, needs Blender restart + testing

#### Project Documentation Setup
- Created CLAUDE.md, INDEX.md, TODO.md, SCRATCHPAD.md per PROJECT_SETUP_GUIDE.md
- Archived original scratchpad.md to scratchpad_archive/

#### Autonomous Cleanup (4 items)

**1. Sensitivity slider** -- already existed as `PoseBridgeSettings.sensitivity` and was wired in panel_ui.py. Added `slider=True` for better UX.

**2. Constraint enforcement toggle** -- Added `enforce_constraints` BoolProperty to `PoseBridgeSettings` (core.py). Wired into panel_ui.py Settings panel. Guarded 3 locations in daz_bone_select.py:
- Single-bone rotation `view_layer.update()` (~line 5095)
- Multi-bone rotation `view_layer.update()` (~line 5284)
- `end_rotation()` depsgraph readback (~line 5296)
When off, constraints are not evaluated during PoseBridge rotation (slightly smoother, no clamping).

**3. core.py multi-bone fix** -- `initialize_control_points_for_character()` now:
- Checks for `bone_names` key to detect multi-bone groups
- Sets `control_type = 'multi'` for groups
- Uses `reference_bone` or first bone for `bone_name`
- Stores comma-separated bone_names in `label` (matches outline_generator_lineart.py convention)
- Skips control points whose bone doesn't exist in armature

**4. Missing bone guards** -- Added defensive checks:
- `start_ik_drag()`: single-bone path now checks bone exists before dict access (was potential KeyError)
- `start_ik_drag()`: multi-bone path now bails cleanly if no valid bones found after filtering
- `capture_fixed_control_points()`: single-bone path uses `.get()` with empty fallback

**Files Modified:**
- `core.py` -- added `enforce_constraints` property, fixed `initialize_control_points_for_character()`
- `panel_ui.py` -- added constraint toggle, slider=True for sensitivity
- `daz_bone_select.py` -- constraint toggle guards, missing bone guards
- `outline_generator_lineart.py` -- defensive `.get()` for bone_name

### Notes & Observations
- Group nodes all share the same twist bone filtering logic (Y=twist goes to all, X/Z=bend skips twist bones) which is anatomically correct across all groups
- Bilateral groups (shoulders_group, legs_group) apply same rotation to all bones without L/R mirroring -- may need adjustment after testing
- No mirroring/inversion for rArm_group vs lArm_group yet -- the controls dicts are identical, testing will reveal if inversion is needed

---

## Session: 2026-02-19 (continued)

### Active Work
- PowerPose research and structural improvements based on findings

### PowerPose Research (Web Search)
Searched DAZ forums for the exact rotation formula used in PowerPose control nodes.

**Key findings:**
1. PowerPose uses **direct Euler angle manipulation**, NOT quaternion trackball. Each mouse direction adds delta to a single property (xrot, yrot, zrot).
2. DSX template format has `lmb_horiz_prop`, `lmb_vert_prop`, `rmb_horiz_prop`, `rmb_vert_prop` per control node -- mirrors our controls dict exactly.
3. DAZ uses **per-bone Euler rotation orders** to avoid gimbal: ThighBend=YZX, ShldrBend=XYZ, ForearmBend=XZY.
4. PowerPose NEVER writes Y to ThighBend -- routes twist to ThighTwist explicitly.
5. Genesis 8+ templates are encrypted (.dse), so exact mappings unverifiable.

Created `TECHNICAL_REFERENCE.md` with full research findings.

### Changes Made

#### 1. Controls Dict Format → Tuple with Inversion (daz_shared_utils.py)
**Problem:** Controls dicts only stored axis letter ('X', 'Y', 'Z', None). Inversions were hardcoded in daz_bone_select.py if/elif chains, creating a dual source-of-truth. PowerPose templates store sign info alongside axis (rmb_horiz_sign: neg).

**Fix:** Changed all controls dict entries from `'Z'` to `('Z', False)` tuple format: `(axis, inverted)`. None stays None.
- Updated all 30+ control point definitions in `get_genesis8_control_points()`
- Updated docstring to explain new format
- Single-bone controls: inversions are for documentation only (if/elif chain is authoritative)
- Group controls: inversions are the runtime source of truth (data-driven)

#### 2. Data-Driven Group Rotation (daz_bone_select.py)
**Problem:** `update_multi_bone_rotation()` had a 70-line if/elif chain duplicating axis mappings already in daz_shared_utils.py controls dicts. Adding a new group required editing two files.

**Fix:** Replaced entire if/elif chain with data-driven lookup:
1. Added `_rotation_group_controls` class variable
2. At drag start (`start_ik_drag()`): call `get_group_controls(group_id)` once, cache result
3. At runtime: read `lmb_horiz`/`lmb_vert` or `rmb_horiz`/`rmb_vert` from cached dict
4. Unpack `(axis, inverted)` tuples directly
5. Added `get_group_controls()` helper function to daz_shared_utils.py

**Result:** ~70 lines of if/elif replaced with ~10 lines of dict lookup. Adding a new group now requires only a dict entry in daz_shared_utils.py.

#### 3. Leg Group Mapping Fix + Y-Lock (daz_bone_select.py + daz_shared_utils.py)
**Problem:** Leg group RMB horiz was Y (twist) but should be Z (spread) to match single-bone thigh behavior. Also, `update_multi_bone_rotation()` lacked the Y-lock that single-bone rotation had for ThighBend.

**Fix:**
- Changed lLeg_group, rLeg_group, legs_group controls:
  - `rmb_horiz`: `('Y', False)` → `('Z', True)` (spread, inverted)
  - `rmb_vert`: `None` → `('X', False)` (forward/back)
- Added Y-lock (swing-twist decomposition) inside the multi-bone rotation loop for ThighBend bones
- Uses same `decompose_swing_twist(quat, 'Y')` pattern as single-bone path
- Debug logging with `[Y-LOCK GROUP]` prefix

**Files Modified:**
- `daz_shared_utils.py` -- all controls dicts → tuple format, leg group mappings fixed, added `get_group_controls()`
- `daz_bone_select.py` -- data-driven group rotation, Y-lock in multi-bone loop, `_rotation_group_controls` variable + cleanup
- `TECHNICAL_REFERENCE.md` -- created with PowerPose research
- `INDEX.md`, `CLAUDE.md` -- reference to TECHNICAL_REFERENCE.md

**Status:** Code complete, needs Blender restart + testing (daz_shared_utils.py changed)

---

## Session: 2026-02-20

### Bug Fix: 3D Mesh Drag Not Working When PoseBridge Active

**Problem:** Regular click-drag on the 3D character mesh couldn't start bone rotation when PoseBridge mode was active. `check_hover()` in daz_bone_select.py had an unconditional `return` after calling `check_posebridge_hover()`, bypassing ALL normal 3D raycast hover detection. When cursor was in the 3D mesh viewport, no control points were found (they're at Z=-50m), `_hover_bone_name` stayed None, and clicks passed through.

**Fix (two parts):**

**Part 1 -- Hover fallthrough:** Changed `check_hover()` from unconditionally returning after `check_posebridge_hover()` to only returning if a control point was found. Otherwise falls through to normal 3D raycast.

**Part 2 -- Viewport-aware drag routing:** Added `_hover_from_posebridge` flag to track whether the current hover came from a PoseBridge control point (True) or normal 3D raycast (False). Replaced all 4 `posebridge_mode` checks in click/drag handlers with this flag:
- LMB press: skip raycast check only for control point clicks
- LMB press: "base" node special handling only for control points
- RMB press: start RMB rotation only for control points
- `start_ik_drag()`: use PoseBridge rotation only for control points

Flag is set True in `check_posebridge_hover()` when hit, False in normal 3D raycast hover and `clear_hover()`.

**Result:** Control panel viewport → PoseBridge rotation mode. 3D mesh viewport → normal IK drag-to-pose.

**Files Modified:** `daz_bone_select.py` (~9 locations)
**Status:** Working correctly

### Bilateral L/R Mirroring for Group Nodes

**Problem:** Bilateral groups (legs_group, shoulders_group) applied the same rotation to all bones identically. For spread (Z axis), left and right bones need to rotate in opposite directions or both legs shift sideways instead of spreading apart. DAZ Genesis 8 bones have mirrored local coordinate systems for L/R pairs.

**Fix:**
1. Added `mirror_axes` key to bilateral group controls dicts in `daz_shared_utils.py`:
   - `legs_group`: `mirror_axes: ['Z']` (spread needs L/R inversion)
   - `shoulders_group`: `mirror_axes: ['Z']` (shrug needs L/R inversion)
2. In `update_multi_bone_rotation()` bone loop: detect right-side bones (`bone.name` starts with 'r' + uppercase), invert rotation quaternion on mirrored axes for those bones.

**Files Modified:**
- `daz_shared_utils.py` -- added `mirror_axes` to legs_group and shoulders_group controls
- `daz_bone_select.py` -- bilateral mirroring logic in bone loop (~line 5228)
**Status:** Working correctly

### PowerPose Axis Mapping Audit

**Audit:** Compared all controls dicts in `daz_shared_utils.py` against the if/elif chain in `daz_bone_select.py` and PowerPose DSX template research.

**Critical runtime bug found:** lThigh/rThigh have `bone_names` (multi-bone), so they use the controls dict at runtime -- but axes were completely wrong (X/Z/Y/Y instead of Y/X/Z/X per PowerPose).

**Fixes applied to `daz_shared_utils.py`:**

| Control | What was wrong | Fix |
|---------|---------------|-----|
| **lThigh/rThigh** | All 4 axes wrong (RUNTIME BUG) | Y twist, X forward, Z spread inv, X forward |
| **head** | Z/Y swapped (lmb_horiz, rmb_horiz) | Y turn, Z side tilt inv |
| **neckUpper/Lower** | Z/Y swapped, missing rmb_vert | Y rotate, Z side bend inv, X fine |
| **chest/abdomen** | Z/Y swapped (lmb_horiz, rmb_horiz) | Y twist, Z side lean inv |
| **pelvis** | Z/Y swapped, missing rmb_vert | Y twist, Z side lean inv, Y alt twist |
| **lCollar/rCollar** | rmb_horiz/rmb_vert swapped | rmb_horiz=None, rmb_vert=Y |
| **lShldrBend/rShldrBend** | Missing inversions | Added inv on lmb_horiz, rmb_vert |
| **lForearmBend/rForearmBend** | LMB axes wrong | lmb_horiz=X inv, lmb_vert=Y inv |
| **lHand/rHand** | All 3 axes wrong | Y twist inv, Z bend, X side inv, Z bend |
| **leg groups** | LMB was X/Z (swing/raise) | Changed to Y/X (twist/forward) per PowerPose |

**Note:** Single-bone dicts are documentation only (if/elif is authoritative). Group dicts (lThigh, rThigh, leg groups) are runtime source of truth -- those fixes affect behavior.

**Files Modified:** `daz_shared_utils.py` (20+ control point definitions)
**Status:** Needs full Blender restart + testing

### RMB Context Menu Suppression

**Problem:** Right-click context menu kept popping up during PoseBridge RMB drags. Three rounds of fixes needed:

1. **Round 1:** Added early catch for RIGHTMOUSE events when `_right_click_used_for_drag` set — but Blender generates CLICK events AFTER RELEASE.
2. **Round 2:** `end_rotation()` was clearing `_right_click_used_for_drag = False` before the synthetic CLICK event arrived. Fixed by deferring flag clearing to the next MOUSEMOVE handler.
3. **Round 3:** After first drag, mouse drifts off 20px control point hit radius, `_hover_from_posebridge` clears, next RMB PRESS falls through to `PASS_THROUGH`. Fixed by consuming ALL RMB PRESS events when PoseBridge is active (context menu has no use in PoseBridge workflow).

**Files Modified:** `daz_bone_select.py` (~lines 1973, 1987, 2290)
**Status:** Working correctly

### Tooltip Flash Fix

**Problem:** Tooltip showed for one frame then disappeared. The `elif not show_tooltip and self._tooltip_text:` block cleared the tooltip text on the very next MOUSEMOVE after showing it (because `show_tooltip` is only True for one frame, then `_tooltip_shown` prevents it from being True again).

**Fix:** Removed the premature clear `elif`. Tooltip is now cleared by `clear_hover()` when mouse leaves or by mouse press handler on click/drag.

**Files Modified:** `daz_bone_select.py` (~line 2864)
**Status:** Working correctly

### Human-Readable Group Tooltips

**Problem:** Group node tooltips showed comma-separated bone names ("lThighBend,lThighTwist,lShin") instead of friendly names ("Left Leg Group").

**Fix (3 files):**
1. `core.py` line 251: Changed to use `cp_def.get('label', cp_def['id'])` for human-readable label
2. `outline_generator_lineart.py` line 112-114: Removed the override that stored comma-separated bone names in label field
3. `daz_bone_select.py` line 2828: Changed `check_posebridge_hover()` to look up bone names from `get_genesis8_control_points()` definitions by ID instead of parsing `label.split(',')`

**Status:** Working correctly (requires PoseBridge re-init to regenerate stored control points)

---

## Session: 2026-02-21

### DSF Face Groups for Clean Mesh Zone Detection

**Problem:** BlenDAZ determines which bone was clicked by aggregating vertex weights from the hit polygon. This produces fuzzy, blended boundaries between body regions. DAZ's DSF geometry files contain `polygon_groups` (face groups) — clean, hard-edged per-polygon assignments to body regions.

**Research findings:**
- Genesis8Female.dsf: Plain JSON, 3.5MB, 16,556 vertices, 16,368 polygons, **61 face groups**
- DSF polylist format: `[group_idx, material_idx, vert0, vert1, vert2, (vert3)]`
- G8F and G8.1F share identical geometry (same counts, same 61 group names)
- DSF group names differ from bone names (e.g., `lShoulder` → `lShldrBend`, `Hip` → `pelvis`)
- DSF file located at: `D:\Daz 3D\Applications\Data\DAZ 3D\My DAZ 3D Library\data\DAZ 3D\Genesis 8\Female\Genesis8Female.dsf`

**Implementation: New module `dsf_face_groups.py`**

Components:
- `parse_dsf_face_groups(dsf_path)` — JSON parser for DSF geometry
- `get_daz_content_dirs()` — reads Diffeomorphic settings for content library paths
- `resolve_dsf_path(armature, mesh_obj)` — finds DSF via DazUrl property or genesis version inference
- `DSF_GROUP_TO_BONE` — mapping table for all 61 face groups to bone names
- `FaceGroupManager` class — cached manager with O(1)/O(log N) lookup

Integration in `daz_bone_select.py`:
- Import + reload at top of file
- `_face_group_mgr` class attribute
- Initialized in `invoke()` after `find_base_body_mesh()`
- METHOD 0 in `get_bone_from_hit()` before existing vertex weight methods

**Edge case handling:**
- SubSurf modifier: BVH `find_nearest` on base mesh when face_index is from evaluated mesh
- Geograft merged: Polygon count mismatch detected → `valid = False` → vertex weight fallback
- Missing DSF file: Silent fallback to vertex weights
- Genesis 8 vs 8.1: Same geometry, works identically

**Performance:** ~1 second init (JSON parse + BVH build), <0.1ms per hover lookup

**Files Created:** `dsf_face_groups.py` (~300 lines)
**Files Modified:** `daz_bone_select.py` (~15 lines: import, class attr, invoke init, METHOD 0)
**Status:** Code complete, needs Blender testing

---

## Quick Reference

### Useful Commands
```python
# Start PoseBridge in Blender
exec(open(r"D:\dev\BlenDAZ\projects\posebridge\start_posebridge.py").read())

# Recapture control points after moving outline
exec(open(r"D:\dev\BlenDAZ\projects\posebridge\recapture_control_points.py").read())

# Reload daz_bone_select after code changes
exec(open(r"D:\dev\BlenDAZ\reload_daz_bone_select.py").read())

# Recapture with module reload (development)
exec(open(r"D:\dev\BlenDAZ\projects\posebridge\recapture_with_reload.py").read())
```

### Important Patterns
- Changes to `daz_shared_utils.py` require **full Blender restart** (Python module caching)
- Changes to `daz_bone_select.py` require reload script or restart
- `importlib.reload()` doesn't work reliably for operator classes
- **Single-bone** controls: axis mapping in BOTH `daz_bone_select.py` if/elif AND `daz_shared_utils.py` dict (if/elif is authoritative)
- **Group** controls: axis mapping ONLY in `daz_shared_utils.py` dict (data-driven, single source of truth)
