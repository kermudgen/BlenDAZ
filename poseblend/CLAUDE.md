# PoseBlend - Project Context

## Core Philosophy
- **Artist-first**: Mimics DAZ Puppeteer — place dots on a 2D grid, drag cursor to blend poses in real-time
- **Keep it simple**: Overlay-based (GPU drawing in viewport) — no separate window, no camera switching
- **Quaternion only**: All pose storage and blending uses quaternions (`[w, x, y, z]`); never convert to Euler internally
- **Data over code**: Bone groups, dot colors, grid templates live in `presets.py`; add configurations there, not inline in operators

## What This Project Does
PoseBlend provides a 2D grid viewport overlay for saving, organizing, and blending poses. Users place "dots" on the grid (each storing bone rotations + a bone mask), then click/drag a cursor across the grid to blend nearby poses in real-time using inverse distance weighting (IDW). Result is applied live to the character armature. Multiple grids allow separate spaces for body poses, expressions, hand gestures, etc.

## Quick File Lookup
**See [INDEX.md](INDEX.md) for complete file reference**

Common lookups:
- PropertyGroups (Dot, Grid, Settings) → `core.py`
- IDW weight calculation + falloff modes → `blending.py`
- Pose capture / apply / quaternion SLERP → `poses.py`
- Grid coordinate math, hit testing, snap → `grid.py`
- GPU drawing (background, grid lines, dots, cursor) → `drawing.py`
- Modal operator (click/drag/create/delete) → `interaction.py`
- N-panel UI, activate/deactivate, grid/dot lists → `panel_ui.py`
- Genesis 8 bone groups, dot color table → `presets.py`
- JSON import/export, bone name remapping → `import_export.py`

## Project Structure
```
D:\Dev\BlenDAZ\poseblend\
  __init__.py              # Module registration, bl_info, register()/unregister()
  core.py                  # PropertyGroups: PoseBlendDot, PoseBlendGrid, PoseBlendSettings
  poses.py                 # Pose capture, apply, quaternion blending, keyframing
  blending.py              # IDW weights, falloff modes, get_top_influences()
  grid.py                  # Coordinate conversion, snap-to-grid, hit testing
  interaction.py           # Modal operator: IDLE/PREVIEWING/DRAGGING_DOT/CREATING_DOT
  drawing.py               # GPU overlay: background, grid lines, dots, cursor, influence lines
  panel_ui.py              # N-panel: activate/deactivate, grids, dots, settings, I/O panels
  viewport_setup.py        # Orthographic camera, viewport overlay configuration
  import_export.py         # JSON grid serialization, bone name remapping presets
  presets.py               # Genesis 8 bone groups, dot colors per mask, grid templates
  POSEBLEND_DESIGN.md      # Full design doc: algorithm specs, open questions, phases
```

## Tech Stack
- **Blender** 5.0+ (extension format with `blender_manifest.toml`)
- **Python** (Blender embedded)
- **bpy** — scene, armature, collections, PropertyGroups
- **gpu / gpu_extras** — viewport overlay drawing (POST_PIXEL draw handler)
- **mathutils** — Quaternion, Vector, SLERP
- **blf** — font rendering (needed for dot labels — currently a TODO)
- DAZ Genesis 8 rigs via Diffeomorphic import (v5 recommended)

## Development Guidelines

### Code Style
- Separation of concerns: blending math in `blending.py`, drawing in `drawing.py`, data in `core.py`
- PropertyGroup helper methods (get_rotations_dict, get_rotation, etc.) belong on the class in `core.py`
- Bone groups and color tables belong in `presets.py`, not inline in operators

### Quaternion Convention
- Stored as `[w, x, y, z]` lists (JSON-serializable)
- On retrieval: `Quaternion((q[0], q[1], q[2], q[3]))` — w is first argument
- SLERP: always check `result.dot(quat) < 0` and negate one quat for shortest-path interpolation
- Never use Euler mode in PoseBlend

### Grid Coordinate System
- All grid positions normalized 0–1 (both axes), origin at bottom-left
- Pixel ↔ grid: `grid.pixel_to_grid()` / `grid_to_pixel()`
- Grid region (x, y, width, height in pixels) calculated by `PoseBlendDrawHandler.calculate_grid_region()`
- Both `drawing.py` and `interaction.py` call this same function — keeps hit detection and drawing in sync

### Bone Mask Hierarchy
- Dot `bone_mask_mode='USE_GRID'` → inherits from `grid.bone_mask_mode`
- Dot `bone_mask_mode='ALL'` or `'PRESET'` or `'CUSTOM'` → overrides grid
- `get_bone_mask_for_dot(dot)` in `poses.py` resolves the effective mask

### Module Reload
- No global state shared with other BlenDAZ modules
- Standard `importlib.reload()` should work for development without full Blender restart

## Known Bugs (at initial setup — pre first Blender test)

### CRASH: `default_mask_mode` / `default_mask_preset` missing on PoseBlendGrid
`interaction.py` `create_dot_at_cursor()` calls `grid.default_mask_mode` and `grid.default_mask_preset`.
`import_export.py` reads these in `export_grid_to_dict()`.
`PoseBlendGrid` in `core.py` only has `bone_mask_mode` / `bone_mask_preset`.
**Fix needed**: rename references in callers to `bone_mask_mode` / `bone_mask_preset`.

### VISUAL: Dot labels not rendered
`drawing.py` `draw_label()` is a `pass` placeholder. Dot names are silent.
**Fix needed**: implement with `blf` module (`blf.position`, `blf.size`, `blf.draw`).

## Running the Addon

### First Run
1. Register: exec `__init__.py` `register()` or install via Blender addon manager
2. In N-panel (DAZ category) → click **"Enter PoseBlend"** (with armature selected)
3. Set armature in Armature field
4. Click **"New Grid"** → choose template
5. Click **"Start Blending"** to launch modal operator
6. **Shift+click** empty grid space → capture current pose as new dot
7. **Click/drag** anywhere on grid → real-time blend preview
8. **Shift+drag dot** → move dot position
9. **Right-click dot** → context menu (rename, duplicate, delete)

### After Code Changes
- PoseBlend module changes: standard `importlib.reload()` should work without full restart
- All shipped files use relative imports (`from . import`, `from .. import`)

## Current Focus
- All modules scaffolded; Phase 1 complete, polishing
- **Known bug**: `default_mask_mode` crash in `interaction.py` and `import_export.py` (see Known Bugs)
- **TODO**: `draw_label()` with `blf` so dot names render
- **Release prep**: imports converted to relative, logging added, packaged in ZIP

## For AI Assistants

### Step 1 — Always read first
**[SESSION_START.md](SESSION_START.md)** — current state, last session, what's next, gotchas.
This is the only file you need for most sessions.

### Step 2 — Read this file (CLAUDE.md)
Architecture, conventions, known bugs, running the addon.

### Step 3 — Only if the task requires it
- Finding a file or function → [INDEX.md](INDEX.md)
- Algorithm specs, open design questions → [POSEBLEND_DESIGN.md](POSEBLEND_DESIGN.md)
- Full task backlog → [TODO.md](TODO.md)
- Decision history → [SCRATCHPAD.md](SCRATCHPAD.md)
- Parent project context → [../CLAUDE.md](../CLAUDE.md)

**Don't front-load.** Read POSEBLEND_DESIGN.md and SCRATCHPAD.md only when the task requires them.

### End of Session
Update [SESSION_START.md](SESSION_START.md) — current state, what changed, what's next. Takes 3-5 minutes.
