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
- FACS expression presets / sliders -> `daz_shared_utils.py` (`FACE_EXPRESSION_PRESETS`, etc.)
- Single-bone rotation logic -> `daz_bone_select.py` (`update_rotation()`)
- Multi-bone group rotation -> `daz_bone_select.py` (`update_multi_bone_rotation()`)
- Face morph drag -> `daz_bone_select.py` (`start_morph_drag()`, `update_morph()`, `end_morph()`)
- Face CP positions + camera -> `posebridge/extract_face.py`
- Outline generation -> `outline_generator_lineart.py`
- GPU drawing of dots -> `drawing.py`
- Scene settings / expression sliders -> `core.py`
- Panel UI / panel switching -> `posebridge/panel_ui.py`
- Mesh zone detection -> `dsf_face_groups.py` (`FaceGroupManager`)

## Project Structure
```
D:\Dev\BlenDAZ\                     # Addon package (BlenDAZ)
  __init__.py                       # Addon entry point, root logging config
  blender_manifest.toml             # Blender extension manifest (id=blendaz, v1.0.0)
  LICENSE                           # GPL-3.0
  daz_bone_select.py                # Modal operator (~11,400 lines) - hover, rotation, IK, morph drag
  daz_shared_utils.py               # Shared utils - control point defs, FACS presets, rotation math
  bone_utils.py                     # Bone classification helpers
  rotation_cache.py                 # Rotation preservation across mode switches
  genesis8_limits.py                # LIMIT_ROTATION constraint data
  dsf_face_groups.py                # DSF parser for clean mesh zone detection (face groups)
  diag_logger.py                    # Diagnostic event logger
  panel_ui.py                       # BlenDAZ N-panel UI (Body Controls, Face Controls)
  posebridge/                       # This project
    __init__.py                     # Package init, addon registration
    core.py                         # PropertyGroup defs, scene settings, expression slider props
    drawing.py                      # GPU overlay rendering (circles, diamonds)
    icons.py                        # View switcher icon shapes
    interaction.py                  # Modal interaction (skeleton/TODO)
    control_points.py               # Hit detection utilities (stubs)
    presets.py                      # Genesis 8 control point presets
    panel_ui.py                     # PoseBridge N-panel (Body/Face panel switching, visibility)
    outline_generator_lineart.py    # Main outline generator (Line Art modifier)
    outline_generator.py            # GP-based outline (alt)
    outline_generator_body.py       # Skeleton-based outline (alt)
    outline_generator_curves.py     # Curve-based outline (alt)
    outline_generator_simple.py     # Quick skeleton outline (alt)
    extract_hands.py                # Hand geometry extraction
    extract_face.py                 # Face CP positions, face camera setup (PB_Camera_Face)
    extract_icon_shape.py           # Mesh-to-icon utility
    streamline.py                   # Streamline performance mode (bulk mute)
```

## Tech Stack
- **Blender** 5.0+ (extension format with `blender_manifest.toml`)
- **Python** (Blender embedded)
- **bpy** API for scene, armature, GP, GPU drawing
- **DAZ Studio** Genesis 8 rigs via Diffeomorphic import (v5 recommended)

## Development Guidelines

### Code Style
- Inline rotation logic in hot paths (no helper function calls per mouse frame)
- Use if/elif chains for per-bone or per-group axis mappings (matches single-bone pattern)
- Use `logging.getLogger(__name__)` for debug output — root logger "BlenDAZ" at WARNING level by default, set to DEBUG for verbose
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
- Changes to `posebridge/core.py` (PropertyGroup) require **full Blender restart**
- `importlib.reload()` doesn't work reliably for operator classes
- This is a Blender Python limitation, not a bug

### Import Convention
- All shipped files use **relative imports** (`from . import`, `from .. import`)
- Dev entry points (`register_only.py`, `setup_all.py`) use `from BlenDAZ import ...` with `sys.path` setup
- No `sys.path` manipulation in shipped files

## Using SCRATCHPAD.md
Update SCRATCHPAD.md as you work -- log changes made, bugs found, decisions taken. Keep it informal.

### Scratchpad Archiving Convention
When SCRATCHPAD.md reaches ~300-500 lines or ~50-75KB, archive to `scratchpad_archive/SCRATCHPAD_YYYY-MM.md` and start fresh with an archive reference.

## Running the App

### Full Workflow (in Blender)
1. Install `blendaz-v1.0.0.zip` via Edit > Preferences > Get Extensions > Install from Disk
2. Open Blender scene with DAZ Genesis 8 character (imported via Diffeomorphic)
3. In N-Panel (DAZ tab): Scan for Characters → Register → Activate
4. PoseBridge: auto-generates outline, cameras, control points

### Dev Workflow (Text Editor)
1. Run `register_only.py` in Blender Text Editor
2. Scan → Register → Activate from N-Panel

### After Code Changes
- `daz_shared_utils.py` → **full Blender restart**
- `posebridge/core.py` (PropertyGroup) → **full Blender restart**
- `daz_bone_select.py` → reload script or restart

## Important Files to Know
- **daz_bone_select.py** (318K) -- The main modal operator. Most interaction logic lives here. Very large file; search by function name.
- **daz_shared_utils.py** -- Source of truth for control point definitions. Both outline generator and bone select import from here.
- **drawing.py** -- GPU drawing code for circles and diamonds. Static class `PoseBridgeDrawHandler`.

## Current Focus
- **Release preparation** — all features complete, packaging done, testing next
- **All panels complete**: Body, Hands, Face modes with click-drag posing
- **Streamline mode**: 6-category bulk mute for performance
- **Multi-character**: registry, switching, per-character caches

## For AI Assistants

### Step 1 — Always read first
**[SESSION_START.md](SESSION_START.md)** — current state, last session, next up, gotchas, active files.
This is the only file you need for most sessions. Read it before anything else.

### Step 2 — Read this file (CLAUDE.md)
Architecture, principles, axis conventions, and running the app.

### Step 3 — Only if the task requires it
- Finding a file → [INDEX.md](INDEX.md)
- Technical findings, research, rig architecture → [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md)
- Understanding recent decisions → [SCRATCHPAD.md](SCRATCHPAD.md) (recent entries only)
- Parent project context → [../CLAUDE.md](../CLAUDE.md)

### Don't front-load
Do NOT read TECHNICAL_REFERENCE.md (34KB), full SCRATCHPAD.md (26KB), or INDEX.md (13KB)
upfront. They are reference docs — look things up in them as needed.

### End of session
Update [SESSION_START.md](SESSION_START.md) with what changed, what's next, and any new gotchas.
Takes 3-5 minutes. Keeps the next session fast.
