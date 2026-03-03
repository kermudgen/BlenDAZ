# PoseBlend - File Index

Quick reference for what's in each file and where to find specific functionality.

---

## Entry Point

### [__init__.py](__init__.py)
**Purpose**: Package initialization and Blender addon registration.
- `register()` — calls `register()` on all submodules in dependency order
- `unregister()` — calls `unregister()` in reverse order
- `bl_info` — addon metadata (v1.0.0, Blender 5.0+, category: Rigging)
**When to modify**: When adding new submodules

---

## Data Model

### [core.py](core.py)
**Purpose**: All Blender PropertyGroup definitions. The data layer for PoseBlend.

**Classes**:
- `PoseBlendDot` — single pose on a grid
  - `id`, `name`, `position` (FloatVector 0-1), `bone_rotations` (JSON string `{bone: [w,x,y,z]}`)
  - `bone_mask_mode`: `USE_GRID` | `ALL` | `PRESET` | `CUSTOM`
  - `bone_mask_preset`, `bone_mask_custom` (JSON list), `color`, `created_time`
  - Helpers: `get_rotations_dict()`, `set_rotations_dict()`, `get_rotation(bone_name)`, `get_custom_mask_list()`
- `PoseBlendGrid` — collection of dots
  - `dots` (CollectionProperty), `active_dot_index`, `is_locked`
  - `grid_divisions` (IntVector 2), `snap_to_grid`, `show_grid_lines`
  - `bone_mask_mode`, `bone_mask_preset` — grid-level default mask (dots with `USE_GRID` inherit this)
  - `background_color`, `grid_line_color`, `armature_name`
  - Helpers: `add_dot()`, `remove_dot()`, `get_active_dot()`
- `PoseBlendSettings` — scene-level settings (`bpy.types.Scene.poseblend_settings`)
  - `is_active`, `grids`, `active_grid_index`
  - `preview_mode`: `REALTIME` | `ON_RELEASE`
  - `auto_keyframe`, `blend_falloff`, `blend_radius`
  - `grid_screen_position`, `grid_screen_size`, `cursor_position`, `cursor_active`
  - `active_armature_name`
  - Helpers: `get_active_grid()`, `add_grid()`, `remove_grid()`

**⚠ Known bug**: `PoseBlendGrid` has `bone_mask_mode` / `bone_mask_preset` but callers in `interaction.py` and `import_export.py` reference `default_mask_mode` / `default_mask_preset` — will crash. Fix callers to use `bone_mask_mode` / `bone_mask_preset`.

**When to modify**: When adding new settings, dot properties, or grid properties

---

## Algorithms

### [blending.py](blending.py)
**Purpose**: Inverse distance weighting (IDW) and quaternion blending math. Pure functions, no bpy dependencies.
- `calculate_blend_weights(cursor_pos, dots, falloff, radius)` — IDW weights normalized to sum 1.0; returns `[(dot, weight)]`; direct-hit shortcut (< 0.001 distance) returns 100% for that dot
- `calculate_weight(distance, falloff, radius)` — per-dot weight; falloff modes: `LINEAR` (1/d), `QUADRATIC` (1/d²), `CUBIC` (1/d³), `SMOOTH` (smoothstep)
- `blend_quaternions_weighted(quat_weight_list)` — iterative SLERP; sorts by weight for stability; negates for shortest-path
- `blend_pose_rotations(weighted_dots, bone_name)` — blend a single bone across all weighted dots
- `calculate_blended_pose(cursor_pos, dots, falloff, radius)` → `{bone_name: Quaternion}`
- `get_dominant_dot(cursor_pos, dots, threshold=0.7)` — returns (dot, weight) if any dot > threshold
- `get_top_influences(cursor_pos, dots, max_count=3)` — top N dots by weight (used for influence lines)
**When to modify**: When adding new falloff modes or changing the blending algorithm

### [poses.py](poses.py)
**Purpose**: Pose capture and application to Blender armatures. Bridges blending math with bpy.
- `capture_pose(armature, bone_mask=None)` → `{bone_name: [w,x,y,z]}` — handles both QUATERNION and Euler rotation modes
- `capture_pose_for_preset(armature, preset_name)` — capture filtered by bone group
- `apply_pose(armature, rotations, bone_mask=None)` — apply rotation dict to armature bones
- `apply_blended_pose(armature, weighted_poses)` — applies blended result from `calculate_blend_weights()` output
- `blend_quaternions(weighted_quats)` → `Quaternion` — iterative SLERP (duplicate of blending.py; this one is used internally)
- `keyframe_pose(armature, bone_mask=None, frame=None)` — insert keyframes for current pose
- `get_bone_mask_for_dot(dot)` — resolves effective bone mask respecting `USE_GRID` (returns None for ALL, list otherwise)
- `filter_rotations_by_mask(rotations, bone_mask)` — filter dict to masked bones
**When to modify**: When changing how poses are captured, applied, or keyframed

### [grid.py](grid.py)
**Purpose**: Grid math — coordinate conversion, snapping, hit testing. No bpy dependencies.
- `pixel_to_grid(pixel_x, pixel_y, grid_region)` → `(x, y)` normalized or `None` if outside
- `grid_to_pixel(grid_x, grid_y, grid_region)` → `(pixel_x, pixel_y)`
- `snap_to_grid(position, divisions)` — snap to nearest grid intersection
- `get_grid_cell(position, divisions)` → `(col, row)` indices
- `hit_test_dot(cursor_pos, dot_pos, hit_radius=0.03)` → bool
- `find_dot_at_position(cursor_pos, dots, hit_radius=0.03)` → `(dot, index)` or `(None, -1)`
- `find_nearest_dot(cursor_pos, dots, max_distance=None)` → `(dot, distance, index)`
- `generate_grid_lines(divisions, include_border=True)` → list of line segment tuples
- `generate_grid_intersections(divisions)` → list of (x, y) points
- `distance_2d(pos1, pos2)` → float
- `clamp_to_grid(position)` → clamped (x, y)
**When to modify**: When changing hit radius defaults or adding new spatial queries

---

## Rendering & Interaction

### [drawing.py](drawing.py)
**Purpose**: GPU overlay rendering. Draws the full PoseBlend UI in the viewport via POST_PIXEL callback.
- `PoseBlendDrawHandler` static class
  - `register_handler()` / `unregister_handler()` — adds/removes `SpaceView3D` draw handler
  - `draw_poseblend_overlay()` — main callback; calls background → grid lines → dots → cursor → influence lines
  - `calculate_grid_region(region, settings)` → `{x, y, width, height}` — used by both drawing and interaction
  - `grid_to_pixel(grid_pos, grid_region)` — converts normalized → pixel for drawing
  - `draw_background(grid_region, color)` — filled rectangle
  - `draw_grid_lines(grid_region, grid)` — vertical + horizontal lines from `grid_divisions`
  - `draw_dots(grid_region, grid, settings)` — all dots; calls `find_dot_at_position` for hover detection
  - `draw_dot(position, radius, color, is_selected, is_hovered)` — circle with glow + outline
  - `draw_label(position, text, offset)` — **placeholder (`pass`) — dot names not rendered yet**
  - `draw_cursor(grid_region, cursor_pos)` — crosshair at cursor position
  - `draw_influence_lines(grid_region, grid, settings)` — lines from cursor to top 3 influencing dots

**⚠ Known issue**: `draw_label()` is empty — dot names are not visible. Needs `blf` implementation.
**When to modify**: When changing dot appearance, adding new visual elements, or implementing labels

### [interaction.py](interaction.py)
**Purpose**: Modal operator for all grid interaction. Drives blending and dot management.
- `InteractionState` — `IDLE`, `PREVIEWING`, `DRAGGING_DOT`, `CREATING_DOT`
- `POSEBLEND_OT_interact` modal operator (`bl_options: REGISTER, UNDO, BLOCKING`)
  - `invoke()` — captures initial pose, calculates grid region, starts modal
  - `modal()` — event router; ESC → cancel, MOUSEMOVE → update cursor/preview/drag, LMB → press/release handlers, RMB → context menu or cancel action, X → delete dot
  - `handle_left_press()` — hit test: if dot + shift → drag, if dot → apply pose, if empty + shift → create dot, if empty → start preview
  - `handle_left_release()` — finalizes blend (optionally keyframes) or dot placement
  - `update_preview()` — calls `calculate_blend_weights()` + `apply_blended_pose()` on MOUSEMOVE (REALTIME mode only)
  - `update_dot_drag()` — moves dot position; snaps if `grid.snap_to_grid`
  - `apply_dot_pose()` — applies single dot at 100% weight
  - `create_dot_at_cursor()` — captures current pose, creates new dot; **⚠ references `grid.default_mask_mode` (crash bug)**
  - `finalize_pose()` — inserts keyframe if `auto_keyframe`
  - `cancel_action()` — restores dot position on RMB during drag
  - `cancel()` (ESC) — restores initial pose captured in `invoke()`
- `POSEBLEND_MT_dot_context` — right-click context menu (rename, edit mask, duplicate, delete)
- Helper operators: `POSEBLEND_OT_rename_dot`, `POSEBLEND_OT_delete_dot`, `POSEBLEND_OT_duplicate_dot`, `POSEBLEND_OT_edit_dot_mask` (stub)
**When to modify**: When changing interaction behavior, adding new gestures, or fixing the crash bug

---

## UI & Configuration

### [panel_ui.py](panel_ui.py)
**Purpose**: All N-panel UI, operators for activation, grid management, and dot management.

**Panels** (bl_category: 'DAZ'):
- `VIEW3D_PT_poseblend_main` — Enter/Exit PoseBlend, armature selector, grid list + lock, bone mask, visual settings, "Start Blending" button
- `VIEW3D_PT_poseblend_dots` — dot list with add/remove/duplicate, active dot properties (name, position, color, mask)
- `VIEW3D_PT_poseblend_settings` — grid overlay position/size, preview mode, auto-keyframe, blend falloff/radius
- `VIEW3D_PT_poseblend_io` — Export/Import buttons

**UI Lists**:
- `POSEBLEND_UL_grids` — shows lock icon, name, mask type abbreviation, dot count
- `POSEBLEND_UL_dots` — shows color swatch, name, mask type

**Operators**:
- `POSEBLEND_OT_activate` — sets `is_active=True`, registers draw handler, sets up viewport, auto-selects armature, creates default grid
- `POSEBLEND_OT_deactivate` — unregisters draw handler, restores viewport
- `POSEBLEND_OT_add_grid` — dialog: template selector (Full Body / Expressions / Upper Body / Lower Body / Hand Gestures / Custom) + optional name
- `POSEBLEND_OT_toggle_lock` — toggles `grid.is_locked` (locked = blend only, no dot editing)
- `POSEBLEND_OT_add_dot` — dialog: name prompt; captures current pose; places at center
**When to modify**: When adding new panels, settings, or operators

### [viewport_setup.py](viewport_setup.py)
**Purpose**: Camera and viewport configuration for PoseBlend mode.
- `setup_poseblend_viewport(context, armature=None)` — creates/reuses `PoseBlend_Camera` + `PoseBlend_CameraObj`; stores name in settings
- `get_or_create_camera()` — ortho camera, scale 3.0
- `get_or_create_camera_object(context, camera_data)` — links to scene collection
- `position_camera_for_grid(camera_obj, armature, layout)` — `SIDE_BY_SIDE` (default), `FRONT`, `OVERVIEW`
- `set_viewport_to_camera(context, camera_obj)` — sets viewport to CAMERA perspective
- `restore_viewport(context)` — returns to PERSP
- `configure_viewport_overlays(context, show_bones, show_grid)` — controls floor/axes/bones visibility
**Note**: The grid overlay is drawn in screen space — viewport camera mainly controls character framing alongside the grid
**When to modify**: When changing initial camera position or adding split-view support

### [import_export.py](import_export.py)
**Purpose**: JSON serialization for grids and dots. File dialogs for I/O.
- `export_grid_to_dict(grid, armature_type)` → dict (version 1.0 format)
- `export_grid_to_json(grid, filepath, armature_type)` → bool
- `import_grid_from_dict(data, settings, bone_remap=None)` → `PoseBlendGrid`
- `import_grid_from_json(filepath, settings, bone_remap=None)` → `PoseBlendGrid`
- `remap_bone_names(rotations, remap_dict)` — rename bones in rotation dict
- `get_remap_preset(preset_name)` — returns preset from `BONE_REMAP_PRESETS`
- `BONE_REMAP_PRESETS` — `'genesis8_to_rigify'` and `'rigify_to_genesis8'` mappings
- `POSEBLEND_OT_export_grid` — file dialog operator (ExportHelper)
- `POSEBLEND_OT_import_grid` — file dialog operator (ImportHelper) with remap_preset choice

**⚠ Known bug**: `export_grid_to_dict()` references `grid.default_mask_mode` / `grid.default_mask_preset` (same crash as interaction.py). Fix to use `grid.bone_mask_mode` / `grid.bone_mask_preset`.
**When to modify**: When changing the export format, adding new fields, or supporting new rig types

### [presets.py](presets.py)
**Purpose**: Static data — bone groups, colors, grid templates. No bpy dependencies.
- `GENESIS8_BONE_GROUPS` — dict of `{preset_name: [bone_names]}` for: `HEAD`, `UPPER_BODY`, `LOWER_BODY`, `ARMS`, `ARM_L`, `ARM_R`, `LEGS`, `LEG_L`, `LEG_R`, `HANDS`, `SPINE`, `FACE`
- `get_bone_group(preset_name)` → list of bone names (empty list if not found)
- `get_all_body_bones()` → union of all groups except FACE
- `DOT_COLORS` — `{mask_type: (r,g,b,a)}` color per mask type
- `get_dot_color(mask_mode, mask_preset=None)` → color tuple
- `GRID_TEMPLATES` — `{key: {name, grid_divisions, default_mask_mode, ...}}`
- `get_grid_template(template_name)` → template dict
**When to modify**: When adding new body regions, adjusting bone lists, or adding dot color themes

---

## Quick Lookup

### "Where is the blending algorithm?"
→ `blending.py` `calculate_blend_weights()` + `blend_quaternions_weighted()`

### "Where does blending get applied to bones?"
→ `poses.py` `apply_blended_pose()` — called by `interaction.py` `update_preview()`

### "Where is the crash bug?"
→ `interaction.py:324` `create_dot_at_cursor()` — `grid.default_mask_mode` → should be `grid.bone_mask_mode`
→ `import_export.py:43` `export_grid_to_dict()` — same issue

### "Where are dot names drawn?"
→ `drawing.py:284` `draw_label()` — currently `pass`, needs `blf` implementation

### "Where is the grid overlay positioned on screen?"
→ `drawing.py` `calculate_grid_region()` — also called by `interaction.py` for consistent hit testing

### "How do I add a new falloff mode?"
→ `blending.py` `calculate_weight()` — add elif branch, then add to `PoseBlendSettings.blend_falloff` EnumProperty in `core.py`

### "How do I add a new bone group preset?"
→ `presets.py` `GENESIS8_BONE_GROUPS` dict — add new key + bone list
→ `core.py` `PoseBlendGrid.bone_mask_preset` EnumProperty items — add matching entry

### "How do I add a new grid template?"
→ `presets.py` `GRID_TEMPLATES`
→ `panel_ui.py` `POSEBLEND_OT_add_grid.template` EnumProperty items + `template_config` dict in `execute()`

### "Where is hover detection during modal?"
→ `interaction.py` `update_cursor()` + `grid.py` `find_dot_at_position()`
→ Drawing also calls `find_dot_at_position()` directly in `draw_dots()` for hover highlight

---

## Common Modification Points

### Fix the `default_mask_mode` crash
**Files**: `interaction.py`, `import_export.py`
**What to change**: Replace `grid.default_mask_mode` → `grid.bone_mask_mode`, `grid.default_mask_preset` → `grid.bone_mask_preset`

### Implement dot labels
**Files**: `drawing.py`
**What to change**: Replace `pass` in `draw_label()` with `blf.position()`, `blf.size()`, `blf.draw()`

### Add a new grid position option
**Files**: `core.py` (`PoseBlendSettings.grid_screen_position` EnumProperty), `drawing.py` (`calculate_grid_region()`)
**What to change**: Add enum item, add elif branch in `calculate_grid_region()`

### Change dot visual appearance
**Files**: `drawing.py`
**What to change**: `draw_dot()` for main dot, `draw_dots()` for hover/select logic, `presets.py` `DOT_COLORS` for colors

### Add a pose-capture filter (e.g. only visible bones)
**Files**: `poses.py` `capture_pose()`
**What to change**: Add optional parameter, filter loop

---

## Documentation
- [CLAUDE.md](CLAUDE.md) - Project context, known bugs, running the addon
- [SCRATCHPAD.md](SCRATCHPAD.md) - Development journal
- [TODO.md](TODO.md) - Task tracking and roadmap
- [POSEBLEND_DESIGN.md](POSEBLEND_DESIGN.md) - Full design spec: algorithm pseudocode, open questions, visual design, import/export schema
