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

### Notes & Observations
- Group nodes all share the same twist bone filtering logic (Y=twist goes to all, X/Z=bend skips twist bones) which is anatomically correct across all groups
- Bilateral groups (shoulders_group, legs_group) apply same rotation to all bones without L/R mirroring -- may need adjustment after testing
- No mirroring/inversion for rArm_group vs lArm_group yet -- the controls dicts are identical, testing will reveal if inversion is needed

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
- Control points must be defined in BOTH `daz_bone_select.py` AND `daz_shared_utils.py`
