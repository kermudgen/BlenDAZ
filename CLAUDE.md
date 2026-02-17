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

**What This Project Does**: BlenDAZ makes it easy and intuitive to pose DAZ Studio characters in Blender using visual, direct-manipulation tools that feel natural to artists.

BlenDAZ is a collection of Blender addons and tools for working with DAZ Studio characters (Genesis 8/9) in Blender. The project focuses on improving the posing and animation workflow for DAZ characters imported via the Diffeomorphic DAZ Importer.

## Tech Stack

Python 3.x, Blender 3.x+ addons, Blender Python API (bpy), GPU viewport rendering. Requires Diffeomorphic DAZ Importer for Genesis 8/9 characters.

## Quick File Lookup

**See [INDEX.md](INDEX.md) for complete file reference and detailed descriptions**

Common lookups:
- Bone selection and rotation → [daz_bone_select.py](daz_bone_select.py)
- Shared utilities (rotation, limits, control points) → [daz_shared_utils.py](daz_shared_utils.py)
- Visual posing editor → [posebridge/](posebridge/)
- Active development notes → [SCRATCHPAD.md](SCRATCHPAD.md)
- Current tasks and roadmap → [TODO.md](TODO.md)

## Project Structure

**See [INDEX.md](INDEX.md) for complete file reference and detailed descriptions**

- **Core tools**: [daz_bone_select.py](daz_bone_select.py), [daz_shared_utils.py](daz_shared_utils.py)
- **Modules**: [posebridge/](posebridge/) (visual posing), [poseblend/](poseblend/) (pose blending)
- **Docs**: CLAUDE.md (this), INDEX.md (file reference), SCRATCHPAD.md (journal), TODO.md (tasks)

## Running the App

- **Installation**: Requires Diffeomorphic DAZ Importer addon. Import Genesis 8/9 character, then install BlenDAZ addons.
- **daz_bone_select**: Press `Ctrl+Shift+D` in Pose mode, hover over bones, click-drag to rotate
- **PoseBridge testing**: See [posebridge/TESTING_POSEBRIDGE.md](posebridge/TESTING_POSEBRIDGE.md) for full checklist

## Development Conventions

### Artist-First Design Principles
When making design decisions, always prioritize the artist's experience:
1. **Visual over Abstract** - Show, don't tell. Use graphics, not text fields.
2. **Direct Manipulation** - Click and drag beats clicking buttons
3. **Immediate Feedback** - Changes should be visible instantly
4. **Minimal Cognitive Load** - Hide complexity until needed
5. **Discoverable** - Users should be able to explore without fear of breaking things
6. **Undo-Friendly** - Everything should be reversible

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

### Rotation Limits
- Diffeomorphic import creates LIMIT_ROTATION constraints on most bones
- Some bones (head, shoulder twist, elbow, forearm twist) may lack constraints
- `enforce_rotation_limits()` checks constraints first, falls back to IK limits or defaults

## Common Development Tasks

**See [INDEX.md](INDEX.md) "Common Modification Points" for detailed instructions**

- **Add control point**: Update control_points.py, drawing.py, recapture positions
- **Modify rotation**: Edit functions in daz_shared_utils.py, test with/without LIMIT_ROTATION constraints
- **Hot reload**: Use reload_daz_bone_select.py pattern to avoid restarting Blender

## Known Issues

- **LIMIT_ROTATION constraints**: Diffeomorphic sometimes doesn't create constraints for head, shoulder twist, elbow, forearm twist bones
  - Workaround: `enforce_rotation_limits()` falls back to IK limits or defaults
- **Module caching**: Blender module caching can cause issues during development
  - Workaround: Restart Blender or use reload scripts
- **Control point recapture**: Must manually recapture after moving outline
  - Run [recapture_control_points.py](posebridge/recapture_control_points.py)

## Documentation System

This project uses a four-file documentation system to help both humans and AI assistants work effectively:

1. **[CLAUDE.md](CLAUDE.md)** (this file) - Project context, philosophy, and development guidelines
2. **[INDEX.md](INDEX.md)** - Complete file reference and quick lookup for all files
3. **[SCRATCHPAD.md](SCRATCHPAD.md)** - Development journal for active work, experiments, and learnings
4. **[TODO.md](TODO.md)** - Task tracking, roadmap, and project backlog

### For AI Assistants

When working on this project:
1. **Check [INDEX.md](INDEX.md) first** to find files before searching or grepping
2. **Check [TODO.md](TODO.md)** for current priorities and planned work
3. **Follow the principles** in this document (especially "Code Simplicity Principle")
4. **Update [SCRATCHPAD.md](SCRATCHPAD.md)** as you work:
   - Document decisions made
   - Note what works and what doesn't
   - Capture bugs encountered and solutions
   - Record technical observations
5. **Update [TODO.md](TODO.md)** when:
   - Completing tasks (mark done, move to Recently Completed)
   - Discovering new bugs or issues
   - Identifying technical debt
   - Having ideas for future improvements
6. **Prefer simple solutions** over complex ones
7. **Ask questions** if requirements are unclear

### SCRATCHPAD.md Archiving

When SCRATCHPAD.md reaches ~300-500 lines or ~50-75KB:
1. Create `scratchpad_archive/` directory if it doesn't exist
2. Move current scratchpad to `scratchpad_archive/SCRATCHPAD_YYYY-MM.md`
3. Create fresh SCRATCHPAD.md with archive reference
4. Carry forward any unfinished items

**Note**: [posebridge/scratchpad.md](posebridge/scratchpad.md) is currently 46KB and should be archived soon.

## Documentation Maintenance

**When to update each file**:

- **[CLAUDE.md](CLAUDE.md)** (this file):
  - When design philosophy or development principles change
  - When "Current Focus" shifts significantly
  - Monthly review recommended

- **[INDEX.md](INDEX.md)**:
  - When adding new files
  - When file purposes change significantly
  - After major refactors
  - When you notice people asking "where is X?"

- **[SCRATCHPAD.md](SCRATCHPAD.md)**:
  - Daily during active development
  - After making important decisions or discoveries
  - When encountering bugs or quirks
  - **Archive when ~300-500 lines or ~50-75KB**

- **[TODO.md](TODO.md)**:
  - When starting new tasks (move from Backlog to Current Work)
  - When completing tasks (mark done, move to Recently Completed)
  - When discovering new bugs or technical debt
  - Weekly grooming recommended

## Current Focus

**Active Development Phase**: PoseBridge Phase 1 MVP

**Current Work**: See [TODO.md](TODO.md) "Current Work" section for up-to-date priorities

**Phase 1 MVP Goals**:
- ✅ Control points visible in viewport
- ✅ Hover detection (yellow highlight)
- 🟡 Click-drag rotation (in testing)
- ✅ Fixed positions (don't follow bones)

**PoseBridge Roadmap**:
- **Phase 1** (Current): Fixed control points with basic rotation
- **Phase 2**: Directional gestures (horizontal/vertical drag for different axes)
- **Phase 3**: Panel views (head, hands detail)
- **Phase 4**: Multi-character support
- **Phase 5**: Polish and optimization

**Other Active Work**:
- Documentation system setup (completed 2026-02-16)
- PoseBlend module refinement

## Questions to Ask Before Making Changes

1. **Does this make the tool easier for artists to use?**
2. **Am I over-engineering? Is there a simpler way?**
3. **Have I checked [INDEX.md](INDEX.md) and [TODO.md](TODO.md)?**
4. **Have I tested with Genesis 8/9 and characters lacking LIMIT_ROTATION constraints?**
5. **Does this break existing functionality?**
6. **Have I updated [SCRATCHPAD.md](SCRATCHPAD.md) with what I learned?**
7. **Does this follow the Code Simplicity and Artist-First principles?**
