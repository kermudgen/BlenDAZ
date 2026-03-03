# PoseBridge - Development Scratchpad

## Purpose
This file tracks ongoing development work, experiments, bugs, and feature progress. It's a living document that captures what we're working on, what we've tried, and what we've learned.

**Note**: When this file reaches ~300-500 lines or ~50-75KB, archive it to `scratchpad_archive/SCRATCHPAD_YYYY-MM.md` and start fresh.

## Archive History
- `scratchpad_archive/SCRATCHPAD_2026-02-pre-setup.md` - Feb 11–19 2026. Phase 1 MVP, PowerPose integration, shoulder debugging, thigh Y-lock, group nodes.
- `scratchpad_archive/SCRATCHPAD_2026-02.md` - Feb 19–21 2026. Group node axis routing (data-driven), delegate architecture for leg groups, bilateral mirroring, PowerPose audit, DSF face groups, RMB suppression, tooltip fixes, auto-detect armature.

---

## Session: 2026-02-24

### Active Work
- Visual polish: selection brackets, hover highlights, opacity controls
- Bug fixes: drag race conditions, FACS driver preservation, mannequin cleanup

### What Was Done

#### Morph Drag Race Condition Fix
- `start_morph_drag` updated to use `_drag_control_point_id` (locked at mouse-down) instead of `_hover_control_point_id` (can clear during drag threshold)
- Extended locked drag state pattern to rotation path: added `_drag_bone_names` alongside existing `_drag_from_posebridge` and `_drag_control_point_id`
- `start_ik_drag()` rotation path now reads from `drag_bone_names` and `drag_cp_id` local vars
- **File**: `daz_bone_select.py`

#### FACS Joint Morph Fix (quaternion conversion)
- **Root cause**: `prepare_rig_for_ik()` converted ALL bones to quaternion mode, but Diffeomorphic FACS joint morphs drive `rotation_euler` channels on jaw/tongue/eye bones. Quaternion mode silences those drivers.
- **Fix**: Added `_get_driven_rotation_bones(armature)` — scans `armature.animation_data.drivers` for `rotation_euler` targets, returns set of bone names to skip during conversion.
- Applied same fix to `daz_rig_manager.py` (`_convert_to_quaternion()` classmethod)
- **Files**: `daz_bone_select.py`, `daz_rig_manager.py`

#### Mannequin Shape Key Stripping
- Mannequin mesh copy retained shape keys and drivers from original character → JCMs/flexions applied in control panel
- Added `shape_key_clear()` + non-Armature modifier removal in `outline_generator_lineart.py` (during mesh copy creation)
- Added same cleanup in `setup_all.py` for existing mannequins in temp collection
- **Files**: `outline_generator_lineart.py`, `setup_all.py`

#### Hidden Twist Bone CP Fix
- `capture_fixed_control_points()` wasn't checking `'hidden': True` flag on CP definitions
- Added `if cp_def.get('hidden'): continue` skip
- **File**: `outline_generator_lineart.py`

#### Hip G-Translate Fixes
1. **Hip locked after PoseBridge click**: `_drag_from_posebridge` persisted from control panel click, causing `start_ik_drag` to enter PoseBridge rotation path instead of native translate. Fixed by clearing `_drag_from_posebridge`, `_drag_control_point_id`, `_drag_bone_names` in G key handler.
2. **RMB cancel killed modal**: Native translate events (RMB, ESC, LMB confirm) were being intercepted. Refactored to a single gate at top of `modal()` that passes ALL events through when `_use_native_translate` is True.
- **File**: `daz_bone_select.py`

#### DAZ-Style Selection Brackets
- **Evolution**: World-AABB → bone-aligned OBB, merged box → per-bone, cyan → light gray, bone bounds → mesh vertex bounds
- `_get_bone_vertex_indices()` reuses DSF face group / vertex weight logic to find vertices for a bone
- `_build_bone_bracket_lines()` transforms vertices to bone-local space, computes AABB with 15% padding, builds corner bracket line segments, transforms back to world
- Hip (root bone with no parent) falls back to pelvis mesh region for bounding
- Corner brackets: 3 line segments per corner × 8 corners = 24 segments per bone
- Registered as `POST_VIEW` handler via `_bracket_draw_handler`
- **File**: `daz_bone_select.py`

#### Hover Brackets + Opacity Control
- **Hover**: Gold/amber `(1.0, 0.6, 0.1, 0.6)` matching mesh highlight color. Skipped if bone already selected.
- **Select**: Light gray `(0.75, 0.75, 0.75, 0.8)`
- **Highlight Opacity**: New `highlight_opacity` FloatProperty (0.0–1.0) on PoseBridgeSettings. Multiplied against all alpha values. Slider in Settings N-panel. When 0, drawing callbacks return early.
- **Files**: `daz_bone_select.py`, `projects/posebridge/core.py`, `projects/posebridge/panel_ui.py`

### Notes & Observations
- Bone-aligned OBB requires transforming vertices into bone-local space via `bone_world_mat.inverted_safe()`, computing AABB there, then transforming corners back — much cleaner than trying to rotate an AABB
- `gpu.state.depth_test_set('LESS_EQUAL')` for brackets (respects depth) vs `'ALWAYS'` for mesh highlight (shows through clothing)
- Multiple running modal sessions can produce duplicate overlays (old cyan + new gray brackets) — restart Blender to clear stale sessions
- `core.py` changes (PoseBridgeSettings PropertyGroup) require full Blender restart — same as `daz_shared_utils.py`

---

## Session: 2026-02-22

### Active Work
- N-Panel controls in progress (face/body control panels added, morph sliders next)

### What Was Done

#### Face Panel (completed across multiple sessions, summarized here)
- **Live face camera** (`PB_Camera_Face`) aimed at head bone rest position
- **~26 face control points** — morph interaction mode, LMB bilateral / RMB asymmetric
- **FACS morph drag system** in `daz_bone_select.py`: `start_morph_drag()`, `update_morph()`, `end_morph()`
- **Morph undo**: custom undo stack entries with `type='morph'`
- **Face CP positions** calculated from actual bone rest positions (lEye, rEye, lowerJaw, lip bones, etc.)
- **Visibility toggling**: Face panel hides all `PB_*` objects, shows live character mesh
- **Files**: `daz_bone_select.py`, `daz_shared_utils.py`, `projects/posebridge/extract_face.py`, `projects/posebridge/panel_ui.py`

#### N-Panel Overhaul (2026-02-22)
- **Removed** old PowerPose panel (`POSE_OT_daz_powerpose_control`, `VIEW3D_PT_daz_powerpose_main`)
- **Added Body Controls panel** with Reset Pose (resets all bone rotations/locations/scales)
- **Added Face Controls panel**:
  - Reset Face button (zeroes all `facs_*` properties, resets sliders)
  - Expression sliders: Smile, Frown, Surprise, Anger, Disgust, Fear, Sadness, Wink L/R
  - Viseme sliders: AA, EE, IH, OH, OO, FV, TH, MM, CH
- **Slider architecture**: dynamic FloatProperties on PoseBridgeSettings with update callbacks that scale `FACE_EXPRESSION_PRESETS` values by intensity
- **Boolean guard**: skip `isinstance(current, bool)` in reset loops for `facs_ctrl_EyeLookAuto` etc.
- **Files**: `daz_bone_select.py` (~line 2504), `daz_shared_utils.py`, `projects/posebridge/core.py`, `projects/posebridge/panel_ui.py`

#### Bug Fix: Undo for Reset Pose/Face (2026-02-22)
- **Root cause**: `self._undo_stack = []` in `invoke()` created an instance variable shadowing the class-level list. Reset operators pushed to class list, modal popped from instance list.
- **Fix**: Use `VIEW3D_OT_daz_bone_select._undo_stack.clear()` instead.
- **Also removed** `bpy.ops.ed.undo_push()` from reset operators — unnecessary.
- **File**: `daz_bone_select.py` (~line 2504)

### Notes & Observations
- `daz_shared_utils.py` changes need **full Blender restart** — no importlib workaround
- Face panel FACS properties come in three tiers: `facs_ctrl_*` (bilateral), `facs_bs_*_div2` (unilateral), `facs_jnt_*` (joint-driven)
- Boolean FACS props (e.g., `facs_ctrl_EyeLookAuto`) must be handled with `isinstance(current, bool)` guard before float assignment

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
- `daz_shared_utils.py` changes → **full Blender restart** (Python module caching)
- `posebridge/core.py` changes (PropertyGroup) → **full Blender restart**
- `daz_bone_select.py` changes → reload script or restart
- `importlib.reload()` does not work reliably for operator classes
- **Single-bone** controls: axis mapping in BOTH `daz_bone_select.py` if/elif AND `daz_shared_utils.py` dict (if/elif is authoritative)
- **Group** controls with `group_delegates`: axis mapping ONLY via referenced single-bone node controls (single source of truth)
- **Undo stack**: class-level on `VIEW3D_OT_daz_bone_select` — external operators must use `VIEW3D_OT_daz_bone_select._undo_stack` (not instance)
- **FACS boolean guard**: always check `isinstance(current, bool)` before assigning float values to `facs_*` properties
- **Driven rotation bones**: bones with `rotation_euler` drivers (jaw, tongue, eyes) must stay in Euler mode — skip in quaternion conversion
- **Locked drag state**: `_drag_from_posebridge`, `_drag_control_point_id`, `_drag_bone_names` set at mouse-down, survive hover clearing during drag
- **Native translate gate**: top of `modal()` passes all events when `_use_native_translate=True`
