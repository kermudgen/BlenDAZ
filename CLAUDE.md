# BlenDAZ Project - Claude Code Instructions

## Design Philosophy

**Make posing fun, easy, and tactile for artists.**

Blender is technically powerful but its interface can overwhelm right-brained, visually-oriented users. BlenDAZ aims to:

- **Reduce cognitive load** - Hide complexity, surface only what's needed
- **Keep viewports clean** - Minimal UI clutter, focus on the character
- **Feel intuitive** - Click-drag interactions that "just work"
- **Leverage Blender's power** - Use GPU drawing, modal operators, and real-time feedback
- **Bridge the gap** - DAZ Studio users expect visual, direct manipulation; give them that in Blender

The goal: help artists accomplish their vision without fighting the software.

---

## Project Overview

BlenDAZ is a collection of Blender addons and tools for working with DAZ Studio characters (Genesis 8/9) in Blender. The project focuses on improving the posing and animation workflow for DAZ characters imported via the Diffeomorphic DAZ Importer.

## Directory Structure

```
D:\dev\BlenDAZ\
├── daz_bone_select.py       # Modal operator for direct bone selection/rotation
├── daz_shared_utils.py      # Shared utilities (rotation, limits, control points)
├── posebridge/              # PoseBridge visual posing editor (in development)
│   ├── __init__.py          # Module registration
│   ├── core.py              # PropertyGroup definitions
│   ├── drawing.py           # GPU rendering for control points
│   ├── outline_generator_lineart.py  # Line Art outline generation
│   ├── start_posebridge.py  # Startup script for testing
│   ├── recapture_control_points.py   # Position recapture utility
│   ├── TESTING_POSEBRIDGE.md         # Testing checklist
│   └── scratchpad.md        # Development notes
└── CLAUDE.md                # This file
```

## Key Components

### daz_bone_select.py
- Modal operator (`VIEW3D_OT_daz_bone_select`) for click-drag bone rotation
- Supports hover detection, rotation with limits, keyframing
- Shortcut: Ctrl+Shift+D to invoke

### daz_shared_utils.py
- `get_bend_axis(bone)` - Determine primary bend axis for a bone
- `get_twist_axis(bone)` - Determine twist axis for a bone
- `apply_rotation_from_delta()` - Apply rotation based on mouse movement
- `enforce_rotation_limits()` - Respect LIMIT_ROTATION constraints
- `get_genesis8_control_points()` - Control point definitions for Genesis 8

### posebridge/ (Phase 1 MVP - In Development)
Visual posing editor with fixed control points overlaid on a 2D character outline.

**Architecture:**
- Control points stay fixed at T-pose positions (don't follow bones)
- Dual viewport: outline at Z=-50m, character at Z=0m
- GPU draw handlers for control point rendering
- Modal operator for interaction

**Key Files:**
- `core.py` - PoseBridgeSettings, PoseBridgeControlPoint PropertyGroups
- `drawing.py` - PoseBridgeDrawHandler class for GPU rendering
- `outline_generator_lineart.py` - Generates GP outline using Line Art modifier

## Development Conventions

### Code Simplicity Principle
**Don't overcomplicate things or try to add an overly clever solution to something that can just be set manually and be done with.**

When faced with a choice between:
- Complex automatic logic with edge cases and exceptions
- Simple explicit configuration

Choose the simple explicit approach. Manual configuration is easier to understand, debug, and maintain than "clever" automatic systems.

### Blender API Patterns
- Use `bpy.types.SpaceView3D.draw_handler_add()` for custom drawing
- Draw handlers don't receive context parameter - get from `bpy.context`
- Modal operators return `{'RUNNING_MODAL'}`, `{'FINISHED'}`, or `{'CANCELLED'}`
- Register/unregister pattern for classes and handlers

### Genesis 8 Bone Names
Common bones used in control points:
- Head: `head`
- Arms: `lShldr`, `rShldr`, `lForeArm`, `rForeArm`, `lHand`, `rHand`
- Torso: `chest`, `abdomen`, `pelvis`
- Legs: `lThigh`, `rThigh`, `lShin`, `rShin`, `lFoot`, `rFoot`

### Rotation Limits
- Diffeomorphic import creates LIMIT_ROTATION constraints on most bones
- Some bones (head, shoulder twist, elbow, forearm twist) may lack constraints
- `enforce_rotation_limits()` checks constraints first, falls back to IK limits or defaults

## Testing PoseBridge

Follow the checklist in `posebridge/TESTING_POSEBRIDGE.md`:

1. Register PoseBridge
2. Generate outline (run `outline_generator_lineart.py`)
3. Move outline to Z=-50m
4. Recapture control points (run `recapture_control_points.py`)
5. Setup dual viewports
6. Run `start_posebridge.py`

**Important:** Update `ARMATURE_NAME` in scripts to match your character's armature name.

## Known Issues

- Diffeomorphic import sometimes doesn't create LIMIT_ROTATION constraints for certain bones
- Module caching in Blender can cause issues - restart Blender to clear
- Control point positions must be recaptured after moving outline

## Plan File Location

Implementation plan: `C:\Users\joshr\.claude\plans\cheeky-growing-comet.md`

## Current Phase

**Phase 1 MVP** - Fixed control points with basic rotation
- Control points visible in viewport
- Hover detection (yellow highlight)
- Click-drag rotation
- Fixed positions (don't follow bones)

**Next Phases:**
- Phase 2: Directional gestures (horizontal/vertical drag)
- Phase 3: Panel views (head, hands detail)
- Phase 4: Multi-character support
- Phase 5: Polish and optimization
