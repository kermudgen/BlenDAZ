# BlenDAZ - File Index

Quick reference guide for what's in each file and where to find specific functionality.

**Last Updated**: 2026-02-16

---

## 🚀 Core Tools

### [daz_bone_select.py](daz_bone_select.py)
**Purpose**: Modal operator for direct viewport bone selection and rotation

- Click-drag bone rotation in the 3D viewport
- Hover detection with visual feedback
- Respects rotation limits and constraints
- Automatic keyframe insertion support
- **Shortcut**: `Ctrl+Shift+D` to invoke
- **Key classes**: `VIEW3D_OT_daz_bone_select`
- **When to modify**: Adding new rotation modes, changing interaction behavior, adjusting hover detection

### [daz_shared_utils.py](daz_shared_utils.py)
**Purpose**: Shared utility functions used across multiple modules

- `get_bend_axis(bone)` - Determine primary bend axis for a bone
- `get_twist_axis(bone)` - Determine twist axis for a bone
- `apply_rotation_from_delta()` - Apply rotation based on mouse movement
- `enforce_rotation_limits()` - Respect LIMIT_ROTATION constraints
- `get_genesis8_control_points()` - Control point definitions for Genesis 8
- **When to modify**: Adding new bone utility functions, updating control point definitions, modifying rotation logic

---

## 🎨 PoseBridge Module

**Location**: [posebridge/](posebridge/)

Visual posing editor with fixed control points overlaid on a 2D character outline. Phase 1 MVP focuses on basic click-drag rotation with fixed control points.

### Core Files

#### [posebridge/__init__.py](posebridge/__init__.py)
**Purpose**: Module registration and initialization
- Registers all operators, property groups, and UI elements
- Handles module enable/disable
- **When to modify**: Adding new classes to register

#### [posebridge/core.py](posebridge/core.py)
**Purpose**: Property group definitions and core data structures
- `PoseBridgeSettings` - Main settings property group
- `PoseBridgeControlPoint` - Individual control point definition
- Scene properties and state management
- **When to modify**: Adding new settings, control point properties, or state tracking

#### [posebridge/drawing.py](posebridge/drawing.py)
**Purpose**: GPU rendering for control points and visual feedback
- `PoseBridgeDrawHandler` class for GPU draw callback
- Control point circle rendering
- Hover state visualization (yellow highlight)
- **When to modify**: Changing visual appearance, adding new draw elements, adjusting render performance

#### [posebridge/interaction.py](posebridge/interaction.py)
**Purpose**: Modal operator for user interaction
- Mouse hover detection
- Click-drag rotation handling
- Modal operator event processing
- **When to modify**: Adding new interaction modes, gesture detection, multi-touch support

### Control Points & Configuration

#### [posebridge/control_points.py](posebridge/control_points.py)
**Purpose**: Control point definitions and configurations
- Genesis 8/9 control point positions
- Bone mappings for control points
- **When to modify**: Adding control points, adjusting positions, supporting new character types

### Outline Generation

#### [posebridge/outline_generator_lineart.py](posebridge/outline_generator_lineart.py)
**Purpose**: Generate 2D character outline using Blender's Line Art modifier (PRIMARY METHOD)
- Creates Grease Pencil outline from armature mesh
- Uses Line Art modifier for accurate edge detection
- Configurable line thickness and detail
- **When to modify**: Adjusting outline quality, changing Line Art settings, supporting new mesh types

#### [posebridge/outline_generator.py](posebridge/outline_generator.py)
**Purpose**: Original outline generator (deprecated, kept for reference)

#### [posebridge/outline_generator_body.py](posebridge/outline_generator_body.py)
**Purpose**: Body-focused outline generation (experimental)

#### [posebridge/outline_generator_curves.py](posebridge/outline_generator_curves.py)
**Purpose**: Curve-based outline generation (experimental)

#### [posebridge/outline_generator_simple.py](posebridge/outline_generator_simple.py)
**Purpose**: Simplified outline generation (experimental)

### UI & Panels

#### [posebridge/panel_ui.py](posebridge/panel_ui.py)
**Purpose**: UI panels and controls for PoseBridge
- Main PoseBridge panel in 3D viewport sidebar
- Control buttons and settings display
- **When to modify**: Adding new UI controls, changing layout

#### [posebridge/presets.py](posebridge/presets.py)
**Purpose**: Preset system for saving/loading control point configurations
- Save/load control point positions
- Preset management
- **When to modify**: Adding preset categories, changing preset format

### Utility Scripts

#### [posebridge/recapture_control_points.py](posebridge/recapture_control_points.py)
**Purpose**: Recapture control point positions after moving outline
- Updates control point 2D positions
- Must be run after moving outline object to Z=-50m
- **When to run**: After generating outline and moving it to dual viewport position

#### [posebridge/recapture_with_reload.py](posebridge/recapture_with_reload.py)
**Purpose**: Recapture control points with module reload
- Combines recapture with module reloading for development

#### [posebridge/start_posebridge.py](posebridge/start_posebridge.py)
**Purpose**: Startup script for testing PoseBridge
- Registers PoseBridge module
- Sets up initial state
- **When to use**: Testing PoseBridge in development

#### [posebridge/move_posebridge_setup.py](posebridge/move_posebridge_setup.py)
**Purpose**: Setup script for moving outline to dual viewport position

#### [posebridge/QUICKSTART_TEST.py](posebridge/QUICKSTART_TEST.py)
**Purpose**: Quick test script for PoseBridge functionality

### Documentation

#### [posebridge/TESTING_POSEBRIDGE.md](posebridge/TESTING_POSEBRIDGE.md)
**Purpose**: Comprehensive testing checklist for PoseBridge Phase 1
- Setup instructions
- Testing procedures
- Expected behaviors
- **When to read**: Before testing PoseBridge, when troubleshooting issues

#### [posebridge/TESTING_PHASE1.md](posebridge/TESTING_PHASE1.md)
**Purpose**: Phase 1-specific testing documentation

#### [posebridge/IMPLEMENTATION_SUMMARY.md](posebridge/IMPLEMENTATION_SUMMARY.md)
**Purpose**: Summary of PoseBridge implementation decisions and architecture

#### [posebridge/POWERPOSE_INTEGRATION.md](posebridge/POWERPOSE_INTEGRATION.md)
**Purpose**: Documentation on integrating PowerPose features into PoseBridge

#### [posebridge/Posebridge_Control_Node_Map.md](posebridge/Posebridge_Control_Node_Map.md)
**Purpose**: Mapping of control points to bones and their behaviors

#### [posebridge/scratchpad.md](posebridge/scratchpad.md)
**Purpose**: Development notes and experiments for PoseBridge
- 46KB of development history
- **Consider archiving** (approaching 50KB threshold)

---

## 🎭 PoseBlend Module

**Location**: [poseblend/](poseblend/)

Pose blending system for creating and blending between multiple character poses using a grid interface.

### Core Files

#### [poseblend/__init__.py](poseblend/__init__.py)
**Purpose**: Module registration and initialization
- Registers operators, property groups, and panels
- Module enable/disable handling

#### [poseblend/core.py](poseblend/core.py)
**Purpose**: Core data structures and property groups
- Pose storage and management
- Grid state and settings
- Scene properties

#### [poseblend/drawing.py](poseblend/drawing.py)
**Purpose**: GPU rendering for grid and visual elements
- Grid visualization in viewport
- Pose thumbnails
- Visual feedback for pose selection

#### [poseblend/interaction.py](poseblend/interaction.py)
**Purpose**: Modal operator for grid interaction
- Mouse interaction with pose grid
- Pose selection and blending
- Drag-to-blend functionality

### Feature Modules

#### [poseblend/blending.py](poseblend/blending.py)
**Purpose**: Pose blending algorithms and calculations
- Interpolation between poses
- Weight calculation for multi-pose blends
- **When to modify**: Changing blending behavior, adding new interpolation methods

#### [poseblend/grid.py](poseblend/grid.py)
**Purpose**: Grid layout and management
- Grid positioning and sizing
- Cell calculations
- **When to modify**: Changing grid layout, adding grid features

#### [poseblend/poses.py](poseblend/poses.py)
**Purpose**: Pose storage and retrieval
- Save/load pose data
- Pose comparison and validation
- **When to modify**: Changing pose data format, adding pose metadata

#### [poseblend/presets.py](poseblend/presets.py)
**Purpose**: Preset system for pose collections
- Save/load preset collections
- Preset management UI

#### [poseblend/import_export.py](poseblend/import_export.py)
**Purpose**: Import/export functionality for poses
- Export poses to file formats
- Import poses from external sources
- **When to modify**: Adding new file format support, changing export options

### UI & Viewport

#### [poseblend/panel_ui.py](poseblend/panel_ui.py)
**Purpose**: UI panels for PoseBlend
- Main PoseBlend panel
- Grid controls
- Pose management UI

#### [poseblend/viewport_setup.py](poseblend/viewport_setup.py)
**Purpose**: Viewport configuration for PoseBlend
- Camera setup
- Viewport display settings
- **When to modify**: Changing viewport layout, adding view options

### Documentation

#### [poseblend/POSEBLEND_DESIGN.md](poseblend/POSEBLEND_DESIGN.md)
**Purpose**: Design document for PoseBlend system
- Architecture overview
- Design decisions
- Feature roadmap

---

## 📚 Documentation Files

### [CLAUDE.md](CLAUDE.md)
**Purpose**: Project context and development guidelines for AI assistants
- Design philosophy
- Project structure overview
- Development conventions
- Testing procedures
- Documentation system guidelines

### [README.md](README.md)
**Purpose**: Project overview for users and developers
- What BlenDAZ does
- Installation instructions
- Basic usage guide

### [PROJECT_SETUP_GUIDE.md](PROJECT_SETUP_GUIDE.md)
**Purpose**: Template guide for setting up the four-file documentation system
- Documentation system overview
- Setup instructions for CLAUDE.md, INDEX.md, SCRATCHPAD.md, TODO.md
- Best practices and tips

### PowerPose Documentation

#### [POWERPOSE_README.md](POWERPOSE_README.md)
**Purpose**: README for PowerPose feature

#### [POWERPOSE_QUICKSTART.md](POWERPOSE_QUICKSTART.md)
**Purpose**: Quick start guide for PowerPose

#### [POWERPOSE_USER_GUIDE.txt](POWERPOSE_USER_GUIDE.txt)
**Purpose**: Detailed user guide for PowerPose

#### [POWERPOSE_IMPLEMENTATION_SUMMARY.md](POWERPOSE_IMPLEMENTATION_SUMMARY.md)
**Purpose**: Implementation details for PowerPose

#### [POWERPOSE_NEW_UI.txt](POWERPOSE_NEW_UI.txt)
**Purpose**: New UI design for PowerPose

#### [POWERPOSE_LAYOUT.txt](POWERPOSE_LAYOUT.txt)
**Purpose**: Layout specifications for PowerPose

#### [POWERPOSE_FIX_RIGHTCLICK.md](POWERPOSE_FIX_RIGHTCLICK.md)
**Purpose**: Documentation on right-click functionality fix

### Bug Reports & Fixes

#### [BUG_LOWER_AB_SNAP.md](BUG_LOWER_AB_SNAP.md)
**Purpose**: Documentation of lower abdomen snap bug and solution

#### [BUG_PECTORAL_ROTATION_SPACE.md](BUG_PECTORAL_ROTATION_SPACE.md)
**Purpose**: Documentation of pectoral rotation space issue

#### [BUG_TORSO_ROTATION_SNAP.md](BUG_TORSO_ROTATION_SNAP.md)
**Purpose**: Documentation of torso rotation snap bug

#### [FIX_GIZMO_INTERFERENCE.md](FIX_GIZMO_INTERFERENCE.md)
**Purpose**: Solution for gizmo interference issues

#### [FIX_IK_STIFFNESS_TUNING.md](FIX_IK_STIFFNESS_TUNING.md)
**Purpose**: IK stiffness tuning solution

#### [FIX_PECTORAL_IK.md](FIX_PECTORAL_IK.md)
**Purpose**: Pectoral IK fix documentation

#### [FIX_PECTORAL_ROTATION_UNDO.md](FIX_PECTORAL_ROTATION_UNDO.md)
**Purpose**: Pectoral rotation undo fix

### Design & Research Documents

#### [UI_POLISH_DESIGN_DOCUMENT.md](UI_POLISH_DESIGN_DOCUMENT.md)
**Purpose**: UI polish design specifications

#### [UI_POLISH_INTEGRATION_GUIDE.md](UI_POLISH_INTEGRATION_GUIDE.md)
**Purpose**: Guide for integrating UI polish features

#### [UI_POLISH_README.md](UI_POLISH_README.md)
**Purpose**: UI polish feature overview

#### [UI_POLISH_RESEARCH_SUMMARY.md](UI_POLISH_RESEARCH_SUMMARY.md)
**Purpose**: Research summary for UI polish work

#### [IK_BREAKTHROUGH.md](IK_BREAKTHROUGH.md)
**Purpose**: Documentation of IK system breakthrough

#### [IK_INTEGRATION_PLAN.md](IK_INTEGRATION_PLAN.md)
**Purpose**: Plan for integrating IK system

#### [SOFT_PIN_IMPLEMENTATION.md](SOFT_PIN_IMPLEMENTATION.md)
**Purpose**: Soft pin feature implementation details

#### [IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)
**Purpose**: Implementation completion summary

#### [TOOL_COMPARISON.md](TOOL_COMPARISON.md)
**Purpose**: Comparison of different tool approaches

#### [PROPOSAL_MODULE_REFACTOR.md](PROPOSAL_MODULE_REFACTOR.md)
**Purpose**: Proposal for module refactoring

---

## 🧪 Testing & Development

### [test_powerpose.py](test_powerpose.py)
**Purpose**: Test suite for PowerPose functionality
- Unit tests for PowerPose features
- **When to run**: After PowerPose changes

### [validate_powerpose.py](validate_powerpose.py)
**Purpose**: Validation script for PowerPose
- Validates PowerPose installation
- Checks for common issues

### [reload_daz_bone_select.py](reload_daz_bone_select.py)
**Purpose**: Hot reload script for daz_bone_select module during development
- Unregisters old version
- Reloads module
- Registers new version
- **When to use**: During active development to test changes without restarting Blender

---

## 🔍 Quick Lookup

### "Where is the bone selection/rotation logic?"
→ [daz_bone_select.py](daz_bone_select.py) - Modal operator with click-drag rotation

### "Where are rotation limits enforced?"
→ [daz_shared_utils.py](daz_shared_utils.py) - `enforce_rotation_limits()` function

### "Where are control points defined?"
→ [daz_shared_utils.py](daz_shared_utils.py) - `get_genesis8_control_points()` function
→ [posebridge/control_points.py](posebridge/control_points.py) - PoseBridge-specific definitions

### "How do I generate the character outline?"
→ [posebridge/outline_generator_lineart.py](posebridge/outline_generator_lineart.py) - Run this script (primary method)

### "How do I test PoseBridge?"
→ [posebridge/TESTING_POSEBRIDGE.md](posebridge/TESTING_POSEBRIDGE.md) - Complete testing checklist

### "Where is the GPU drawing code?"
→ [posebridge/drawing.py](posebridge/drawing.py) - PoseBridge GPU rendering
→ [poseblend/drawing.py](poseblend/drawing.py) - PoseBlend GPU rendering

### "How do I reload a module during development?"
→ [reload_daz_bone_select.py](reload_daz_bone_select.py) - Example reload script

### "Where are the development notes?"
→ [posebridge/scratchpad.md](posebridge/scratchpad.md) - PoseBridge development journal
→ [SCRATCHPAD.md](SCRATCHPAD.md) - Project-wide development journal (to be created)

---

## 🎯 Common Modification Points

### Adding a New Control Point
**Files**:
- [daz_shared_utils.py](daz_shared_utils.py) or [posebridge/control_points.py](posebridge/control_points.py)
- [posebridge/drawing.py](posebridge/drawing.py) (to render it)

**What to change**:
1. Add control point definition with bone name and 2D position
2. Update GPU draw handler to render new point
3. Recapture positions if working with existing outline

### Modifying Rotation Behavior
**Files**:
- [daz_shared_utils.py](daz_shared_utils.py) - Core rotation logic
- [daz_bone_select.py](daz_bone_select.py) - Click-drag interaction
- [posebridge/interaction.py](posebridge/interaction.py) - PoseBridge interaction

**What to change**:
1. Update `apply_rotation_from_delta()` for rotation calculation
2. Modify `enforce_rotation_limits()` for limit behavior
3. Update modal operator event handling

### Changing Visual Appearance
**Files**:
- [posebridge/drawing.py](posebridge/drawing.py)
- [poseblend/drawing.py](poseblend/drawing.py)

**What to change**:
1. Modify GPU shader code
2. Update color definitions
3. Adjust circle sizes, line widths, etc.

### Adding New Bone Support
**Files**:
- [daz_shared_utils.py](daz_shared_utils.py)
- [posebridge/control_points.py](posebridge/control_points.py)

**What to change**:
1. Add bone name mappings
2. Define bend/twist axes for bone
3. Add control point if needed
4. Test rotation limits

---

## 📚 Related Documentation

- [CLAUDE.md](CLAUDE.md) - Project context and development guidelines
- [SCRATCHPAD.md](SCRATCHPAD.md) - Development journal (to be created)
- [TODO.md](TODO.md) - Task tracking and roadmap (to be created)
- [PROJECT_SETUP_GUIDE.md](PROJECT_SETUP_GUIDE.md) - Documentation system setup guide

---

## 📊 File Statistics

**Total Python Files**: ~30+
**Documentation Files**: ~25+
**Active Modules**: 3 (daz_bone_select, posebridge, poseblend)
**Lines of Code**: ~2000+ (estimated across all modules)

**Largest Files**:
- [posebridge/scratchpad.md](posebridge/scratchpad.md) - 46KB (consider archiving)
- [posebridge/outline_generator_lineart.py](posebridge/outline_generator_lineart.py) - 33KB
- [daz_bone_select.py](daz_bone_select.py) - 267KB (!)

**Note**: daz_bone_select.py at 267KB is unusually large and may benefit from refactoring into smaller modules.
