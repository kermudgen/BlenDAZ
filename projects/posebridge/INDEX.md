# PoseBridge - File Index

Quick reference guide for what's in each file and where to find specific functionality.

---

## Entry Points & Utilities

### [start_posebridge.py](start_posebridge.py)
**Purpose**: Startup script to initialize and activate PoseBridge mode in Blender.
- Adds BlenDAZ and projects dirs to sys.path
- Registers posebridge and daz_bone_select modules
- Registers draw handler and invokes modal operator
- **Config**: `ARMATURE_NAME` must match your character
**When to modify**: When changing startup sequence or adding new module registrations

### [recapture_control_points.py](recapture_control_points.py)
**Purpose**: Recapture fixed control point positions after moving outline to Z=-50m.
- Imports `capture_fixed_control_points` from outline_generator_lineart
- **Config**: `ARMATURE_NAME`, `OUTLINE_NAME`
**When to modify**: When changing outline naming or capture workflow

### [recapture_with_reload.py](recapture_with_reload.py)
**Purpose**: Development utility -- recapture with automatic module reloading.
- Force reloads daz_shared_utils and outline_generator_lineart before recapture
**When to modify**: Rarely

### [__init__.py](__init__.py)
**Purpose**: Package initialization and Blender addon registration.
- `register()` / `unregister()` for all submodules
- `bl_info` metadata (v0.1.0, Blender 3.0+, category: Rigging)
**When to modify**: When adding new submodules

---

## Core Data & Settings

### [core.py](core.py)
**Purpose**: Data model layer. Blender PropertyGroup classes for PoseBridge state.
- `PoseBridgeControlPoint` -- id, bone_name, label, group, position_2d, position_3d_fixed, control_type, hover/select state
- `PoseBridgeSettings` -- is_active, sensitivity, show_outline, show_control_points, auto_keyframe, active_armature_name, control_points_fixed
- `PoseBridgeCharacter` -- per-armature data with control_points collection
- `get_posebridge_character()` -- get or create character data for armature
- `initialize_control_points_for_character()` -- init from bone definitions
**When to modify**: When adding new settings or control point properties

### [presets.py](presets.py)
**Purpose**: Genesis 8 control point preset definitions (legacy, 16 body points).
- `get_genesis8_body_control_points()` -- 16 body control point defs
- Stubs for head and hands panels (Phase 3)
**Note**: Main definitions now live in `daz_shared_utils.py`. This file is partially superseded.

### [control_points.py](control_points.py)
**Purpose**: Hit detection and control point management utilities.
- Function stubs only (TODO): `get_control_point_2d_position()`, `find_control_point_at_position()`, `get_control_points_for_view()`
**Status**: Not yet implemented. Hit detection currently lives in daz_bone_select.py `check_posebridge_hover()`.

---

## Rendering & UI

### [drawing.py](drawing.py)
**Purpose**: GPU overlay rendering of control point dots in the viewport.
- `PoseBridgeDrawHandler` static class managing draw callbacks
- `draw_posebridge_overlay()` -- main draw callback
- `draw_control_point_circle()` -- filled/outlined circle (32 segments) for single-bone
- `draw_control_point_diamond()` -- filled/outlined diamond for multi-bone groups
- `draw_control_point_sun()` -- sun shape with radiating lines (Phase 2)
**When to modify**: When changing control point appearance, adding new shapes, or adjusting colors

### [icons.py](icons.py)
**Purpose**: GPU-drawn icon shapes for viewport view switcher (body/hand/head).
- `ICON_BODY`, `ICON_HAND`, `ICON_HEAD` -- vertex data for stick figure icons
- `ViewSwitcherIcons` -- manages bottom-left corner icons with hit testing
- `draw_icon_outline()`, `draw_icon_filled()`, `draw_body_icon()`
**When to modify**: When changing view switcher appearance or adding new views

### [panel_ui.py](panel_ui.py)
**Purpose**: Blender N-panel UI for PoseBridge settings.
- `VIEW3D_PT_posebridge_main` -- main panel (mode status, figure info)
- `VIEW3D_PT_posebridge_panel_selector` -- body/hands/face view buttons
- `VIEW3D_PT_posebridge_settings` -- sensitivity, toggles, keyframe options
- `POSEBRIDGE_OT_set_panel_view` -- operator to switch views
**When to modify**: When adding new settings or UI elements

---

## Outline Generation

### [outline_generator_lineart.py](outline_generator_lineart.py) (PRIMARY)
**Purpose**: Main outline generator using Blender's Line Art modifier. Most feature-complete.
- `create_genesis8_lineart_outline()` -- full pipeline: mesh copy, ortho camera, Line Art GP, mannequin material, control point capture
- `capture_fixed_control_points()` -- stores control point 3D positions from T-pose
- `move_posebridge_setup()` -- offset outline/camera/light together
- Creates `PB_Mannequin_Gray` material on mesh copy (flat gray, no specular)
- Dynamic line radius: height x 0.00323
**When to modify**: When changing outline appearance, control point capture, or mannequin setup

### [outline_generator.py](outline_generator.py)
**Purpose**: Alternative outline using GP from mesh boundary edges.
- `detect_silhouette_from_view()`, `build_stroke_chains()`
**Status**: Functional alternative, not primary

### [outline_generator_body.py](outline_generator_body.py)
**Purpose**: Alternative outline using skeleton bone positions (curves).
- Circle for head, closed shape for torso, rectangular tubes for limbs
**Status**: Functional alternative, not primary

### [outline_generator_curves.py](outline_generator_curves.py)
**Purpose**: Alternative outline using curves from mesh silhouette.
- Emission shader for cyan outline visibility
**Status**: Functional alternative, not primary

### [outline_generator_simple.py](outline_generator_simple.py)
**Purpose**: Fast skeleton-based outline for quick testing.
**Status**: Development utility

---

## Hand Extraction

### [extract_hands.py](extract_hands.py)
**Purpose**: Extract hand geometry from character mesh for hand panel view.
- `extract_hand_geometry()` -- extract via vertex groups
- `position_hands_for_view()` -- side-by-side dorsal view (calibrated for Genesis 8 Fey)
- `create_hand_camera()` -- orthographic camera for hand view
- `generate_hand_control_points()` -- finger joint control points
- `FINGER_BONES` -- 15 finger bone names (Thumb1-3, Index1-3, etc.)
**When to modify**: When adding hand control features or supporting different characters

### [extract_icon_shape.py](extract_icon_shape.py)
**Purpose**: Utility to convert flat mesh shapes into icon vertex data for icons.py.
- `extract_shape_from_mesh()`, `extract_ordered_outline()`, `format_for_icons_py()`
**When to modify**: When creating new icon shapes

---

## Interaction (Skeleton)

### [interaction.py](interaction.py)
**Purpose**: Modal interaction handler (planned replacement for daz_bone_select.py PoseBridge code).
- `VIEW3D_OT_posebridge_interact` -- modal operator with TODO stubs
**Status**: Early skeleton. All interaction currently lives in daz_bone_select.py.

---

## Parent BlenDAZ Files

### [../daz_shared_utils.py](../daz_shared_utils.py)
**Purpose**: Source of truth for control point definitions and rotation math.
- `get_genesis8_control_points()` -- all control point definitions with 4-way mappings
- `apply_rotation_from_delta()` -- simplified: takes bone, axis, delta, sensitivity
- `decompose_swing_twist()` -- swing/twist quaternion decomposition for thigh Y-lock
- `get_bend_axis()`, `get_twist_axis()` -- axis determination by bone name
**When to modify**: When adding/changing control points or rotation math

### [../daz_bone_select.py](../daz_bone_select.py) (~6800 lines)
**Purpose**: Main modal operator for all bone interaction.
- `DazBoneSelect` operator class
- `check_posebridge_hover()` -- 2D hit detection for PoseBridge control points
- `update_rotation()` -- single-bone rotation with per-bone axis mapping
- `update_multi_bone_rotation()` -- multi-bone group rotation with per-group axis mapping
- `start_ik_drag()` -- initiates rotation or IK drag
- `end_rotation()` -- finalizes rotation, optional keyframing
**When to modify**: When changing rotation behavior, adding control points, or fixing interaction bugs

### [../dsf_face_groups.py](../dsf_face_groups.py)
**Purpose**: DSF parser and face group manager for clean mesh zone detection.
- `parse_dsf_face_groups()` -- parse DSF JSON for polygon_groups
- `resolve_dsf_path()` -- find DSF file via DazUrl property or genesis version
- `get_daz_content_dirs()` -- read Diffeomorphic content directory settings
- `DSF_GROUP_TO_BONE` -- mapping table (61 entries: DSF group name → bone name)
- `FaceGroupManager` -- cached per-mesh manager with O(1)/O(log N) polygon→bone lookup
**When to modify**: When supporting new Genesis versions or adding material zone features

### [../daz_rig_manager.py](../daz_rig_manager.py)
**Purpose**: Rig detection, preparation, metadata caching. Converts to quaternion mode.

### [../bone_utils.py](../bone_utils.py)
**Purpose**: Bone classification (twist, pectoral, carpal), IK chain management.

### [../rotation_cache.py](../rotation_cache.py)
**Purpose**: Preserves bone rotations across Blender mode switches.

### [../genesis8_limits.py](../genesis8_limits.py)
**Purpose**: LIMIT_ROTATION constraint data for Genesis 8 bones.

### [../panel_ui.py](../panel_ui.py)
**Purpose**: BlenDAZ N-panel UI for IK settings, rotation limits, quick actions.

---

## Quick Lookup

### "Where are control point definitions?"
-> `daz_shared_utils.py` `get_genesis8_control_points()` (source of truth)
-> `daz_bone_select.py` `update_rotation()` / `update_multi_bone_rotation()` (axis mappings)

### "Where is rotation handled?"
-> Single bone: `daz_bone_select.py` `update_rotation()` (line ~4694)
-> Multi-bone group: `daz_bone_select.py` `update_multi_bone_rotation()` (line ~5154)

### "Where are control points drawn?"
-> `drawing.py` `PoseBridgeDrawHandler.draw_control_points()`

### "Where is hover/click detection?"
-> `daz_bone_select.py` `check_posebridge_hover()` (line ~2720)

### "Where is mesh zone detection (bone from click)?"
-> `daz_bone_select.py` `get_bone_from_hit()` -- METHOD 0: DSF face groups, METHOD 1: vertex weights, METHOD 2: nearest vertex
-> `dsf_face_groups.py` `FaceGroupManager` -- parses DSF, maps polygon→bone

### "How do I add a new control point?"
1. Add definition in `daz_shared_utils.py` `get_genesis8_control_points()`
2. Add axis mapping in `daz_bone_select.py` `update_rotation()` (single) or `update_multi_bone_rotation()` (group)
3. Restart Blender, regenerate outline, recapture positions

### "How do I change a control's axis mapping?"
-> Single bone: `daz_bone_select.py` `update_rotation()` if/elif chain (~line 4762)
-> Group: `daz_bone_select.py` `update_multi_bone_rotation()` if/elif chain (~line 5174)
-> Also update `controls` dict in `daz_shared_utils.py` to keep in sync

---

## Common Modification Points

### Adding a new single-bone control point
**Files**: `daz_shared_utils.py`, `daz_bone_select.py`
**What to change**: Add dict to `get_genesis8_control_points()`, add elif in `update_rotation()`

### Adding a new group node
**Files**: `daz_shared_utils.py`, `daz_bone_select.py`
**What to change**: Add dict with `bone_names`+`shape:'diamond'` to `get_genesis8_control_points()`, add elif in `update_multi_bone_rotation()`

### Changing control point appearance
**Files**: `drawing.py`
**What to change**: `draw_control_point_circle()` or `draw_control_point_diamond()`

### Changing sensitivity or adding settings
**Files**: `core.py`, `panel_ui.py`
**What to change**: Add property to `PoseBridgeSettings`, add UI element to panel

---

## Documentation
- [CLAUDE.md](CLAUDE.md) - Project context and guidelines
- [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md) - PowerPose research, rotation architecture, DAZ bone system, troubleshooting
- [SCRATCHPAD.md](SCRATCHPAD.md) - Development journal
- [TODO.md](TODO.md) - Task tracking and roadmap
- [PROJECT_SETUP_GUIDE.md](PROJECT_SETUP_GUIDE.md) - How this doc system works
- [Posebridge_Control_Node_Map.md](Posebridge_Control_Node_Map.md) - Complete control mapping reference
- [POWERPOSE_INTEGRATION.md](POWERPOSE_INTEGRATION.md) - PowerPose integration guide
- [TESTING_POSEBRIDGE.md](TESTING_POSEBRIDGE.md) - Testing procedures
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Implementation overview
- [TESTING_PHASE1.md](TESTING_PHASE1.md) - Phase 1 test plan

## Test & Debug Scripts
- [start_posebridge.py](start_posebridge.py) - Main startup
- [recapture_control_points.py](recapture_control_points.py) - Position recapture
- [recapture_with_reload.py](recapture_with_reload.py) - Dev recapture with reload
- [QUICKSTART_TEST.py](QUICKSTART_TEST.py) - Quick start test script
- [test_hand_extraction.py](test_hand_extraction.py) - Hand extraction tests
- [test_hand_integration.py](test_hand_integration.py) - Hand integration tests
- [test_icons.py](test_icons.py) - Icon rendering tests
- [move_posebridge_setup.py](move_posebridge_setup.py) - Move outline to Z offset
