# PoseBridge - Development Scratchpad

## Purpose
This file tracks ongoing development work, experiments, bugs, and feature progress. It's a living document that captures what we're working on, what we've tried, and what we've learned.

**Note**: When this file reaches ~300-500 lines or ~50-75KB, archive it to `scratchpad_archive/SCRATCHPAD_YYYY-MM.md` and start fresh.

## Archive History
- `scratchpad_archive/SCRATCHPAD_2026-02-pre-setup.md` - Feb 11–19 2026. Phase 1 MVP, PowerPose integration, shoulder debugging, thigh Y-lock, group nodes.
- `scratchpad_archive/SCRATCHPAD_2026-02.md` - Feb 19–21 2026. Group node axis routing (data-driven), delegate architecture for leg groups, bilateral mirroring, PowerPose audit, DSF face groups, RMB suppression, tooltip fixes, auto-detect armature.

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
- `daz_bone_select.py` changes → reload script or restart
- `importlib.reload()` does not work reliably for operator classes
- **Single-bone** controls: axis mapping in BOTH `daz_bone_select.py` if/elif AND `daz_shared_utils.py` dict (if/elif is authoritative)
- **Group** controls with `group_delegates`: axis mapping ONLY via referenced single-bone node controls (single source of truth)
- **Undo stack**: class-level on `VIEW3D_OT_daz_bone_select` — external operators must use `VIEW3D_OT_daz_bone_select._undo_stack` (not instance)
- **FACS boolean guard**: always check `isinstance(current, bool)` before assigning float values to `facs_*` properties
