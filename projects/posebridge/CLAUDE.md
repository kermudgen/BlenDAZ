# PoseBridge - Project Context

## Core Philosophy
- **Artist-first**: Controls should feel intuitive to pose artists familiar with DAZ PowerPose
- **Keep it simple**: Prefer straightforward if/elif over clever abstractions. Direct conditional logic is easier to debug and faster to execute
- **Performance matters**: Rotation code runs on every mouse movement frame -- avoid function call overhead, dict lookups, or allocations in hot paths
- **Test in Blender**: Code changes require Blender restart or reload scripts; always verify in-app

## What This Project Does
PoseBridge is a Blender addon that provides a 2D control panel for posing DAZ Genesis 8 characters. It creates an orthographic viewport at Z=-50m showing a gray mannequin silhouette with clickable control point dots. Each dot maps to one or more DAZ rig bones with PowerPose-style 4-way mouse controls (LMB/RMB x horizontal/vertical drag = rotation axes). Single-bone controls render as circles; multi-bone group controls render as diamonds.

## Quick File Lookup
**See [INDEX.md](INDEX.md) for complete file reference**

Common lookups:
- Control point definitions -> `daz_shared_utils.py` (`get_genesis8_control_points()`)
- Single-bone rotation logic -> `daz_bone_select.py` (`update_rotation()`)
- Multi-bone group rotation -> `daz_bone_select.py` (`update_multi_bone_rotation()`)
- Outline generation -> `outline_generator_lineart.py`
- GPU drawing of dots -> `drawing.py`
- Scene settings/properties -> `core.py`
- Panel UI -> `panel_ui.py`

## Project Structure
```
D:\Dev\BlenDAZ\                     # Parent addon (BlenDAZ)
  daz_bone_select.py                # Modal operator (318K) - hover, rotation, IK
  daz_shared_utils.py               # Shared utils - control point defs, rotation math
  daz_rig_manager.py                # Rig detection and preparation
  bone_utils.py                     # Bone classification helpers
  rotation_cache.py                 # Rotation preservation across mode switches
  genesis8_limits.py                # LIMIT_ROTATION constraint data
  panel_ui.py                       # BlenDAZ N-panel UI
  projects/
    posebridge/                     # This project
      __init__.py                   # Package init, addon registration
      core.py                       # PropertyGroup definitions, scene settings
      drawing.py                    # GPU overlay rendering (circles, diamonds)
      icons.py                      # View switcher icon shapes
      interaction.py                # Modal interaction (skeleton/TODO)
      control_points.py             # Hit detection utilities (stubs)
      presets.py                    # Genesis 8 control point presets
      panel_ui.py                   # PoseBridge N-panel UI
      outline_generator_lineart.py  # Main outline generator (Line Art modifier)
      outline_generator.py          # GP-based outline (alt)
      outline_generator_body.py     # Skeleton-based outline (alt)
      outline_generator_curves.py   # Curve-based outline (alt)
      outline_generator_simple.py   # Quick skeleton outline (alt)
      extract_hands.py              # Hand geometry extraction
      extract_icon_shape.py         # Mesh-to-icon utility
      start_posebridge.py           # Startup script
      recapture_control_points.py   # Position recapture utility
      recapture_with_reload.py      # Dev recapture with reload
      scratchpad_archive/           # Archived scratchpads
```

## Tech Stack
- **Blender** 3.0+ (tested on 4.x)
- **Python** (Blender embedded)
- **bpy** API for scene, armature, GP, GPU drawing
- **DAZ Studio** Genesis 8 rigs via Diffeomorphic import

## Development Guidelines

### Code Style
- Inline rotation logic in hot paths (no helper function calls per mouse frame)
- Use if/elif chains for per-bone or per-group axis mappings (matches single-bone pattern)
- Keep debug print statements (prefixed with `[DEBUG]`, `[Y-LOCK]`, etc.) -- they're essential for in-Blender debugging
- Quaternion rotation mode throughout (never Euler in PoseBridge)

### Axis Convention
- **X axis**: Forward/back bending (sagittal plane)
- **Y axis**: Twist/rotation along bone length
- **Z axis**: Side-to-side bending (frontal plane)
- Twist bones only receive Y-axis rotation; Bend bones receive X/Z
- `apply_rotation_from_delta(bone, initial_rot, axis, delta, sensitivity)` -- caller passes the specific delta (delta_x or delta_y), no hidden axis-to-delta mapping

### Control Point Definitions
- Defined in `daz_shared_utils.py` `get_genesis8_control_points()`
- Must also exist in `daz_bone_select.py` axis mapping chains
- Single-bone: `bone_name` property, rendered as circle
- Multi-bone group: `bone_names` array, rendered as diamond, `shape: 'diamond'`
- Each has `controls` dict: `lmb_horiz`, `lmb_vert`, `rmb_horiz`, `rmb_vert` -> axis letter or None

### Blender Module Caching
- Changes to `daz_shared_utils.py` require **full Blender restart**
- Changes to `daz_bone_select.py` require reload script or restart
- `importlib.reload()` doesn't work reliably for operator classes
- This is a Blender Python limitation, not a bug

## Using SCRATCHPAD.md
Update SCRATCHPAD.md as you work -- log changes made, bugs found, decisions taken. Keep it informal.

### Scratchpad Archiving Convention
When SCRATCHPAD.md reaches ~300-500 lines or ~50-75KB, archive to `scratchpad_archive/SCRATCHPAD_YYYY-MM.md` and start fresh with an archive reference.

## Running the App

### Full Workflow (in Blender)
1. Open Blender scene with DAZ Genesis 8 character
2. Run `outline_generator_lineart.py` in Text Editor -- generates outline + captures control points
3. Move outline setup to Z=-50m (manually or via script)
4. Run `recapture_control_points.py` -- syncs control point positions to new Z
5. Set up dual viewports (one at Z=0 for character, one at Z=-50 for control panel)
6. Run `start_posebridge.py` -- activates modal operator with control point overlay

### After Code Changes
```python
# For daz_bone_select.py changes:
exec(open(r"D:\dev\BlenDAZ\reload_daz_bone_select.py").read())

# For daz_shared_utils.py changes:
# Must restart Blender entirely

# For posebridge module changes:
exec(open(r"D:\dev\BlenDAZ\projects\posebridge\recapture_with_reload.py").read())
```

## Important Files to Know
- **daz_bone_select.py** (318K) -- The main modal operator. Most interaction logic lives here. Very large file; search by function name.
- **daz_shared_utils.py** -- Source of truth for control point definitions. Both outline generator and bone select import from here.
- **drawing.py** -- GPU drawing code for circles and diamonds. Static class `PoseBridgeDrawHandler`.

## Current Focus
- Finishing group node hookup (per-group axis routing in `update_multi_bone_rotation`)
- Testing all 8 group nodes with correct axis mappings
- Completing Phase 1 MVP (cancellation testing, end-to-end verification)

## For AI Assistants
When working on this project:
1. Check [INDEX.md](INDEX.md) to find files before searching
2. Check [TODO.md](TODO.md) for current priorities and planned work
3. Follow the principles in this document
4. Update [SCRATCHPAD.md](SCRATCHPAD.md) as you work
5. Update [TODO.md](TODO.md) when completing tasks or discovering new ones
6. Prefer simple solutions over complex ones
7. Ask questions if requirements are unclear
