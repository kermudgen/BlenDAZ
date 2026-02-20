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

## Quick Testing (For AI Assistants)

**When the user wants to test daz_bone_select or posebridge:**

1. **DON'T** create elaborate checklists or enter plan mode
2. **DON'T** ask a bunch of questions about what to test
3. **DO** just use [quick_test.py](../quick_test.py) - it handles everything:
   - Checks prerequisites
   - Enables posebridge
   - Starts daz_bone_select operator
   - Ready to test in seconds

**User can then just hover and click-drag to test. That's it. Keep it simple.**

If there's a specific bug or feature to test, focus on that directly without ceremony.

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

## Issue Status

> **For AI assistants**: Read this section before investigating any bug. It records what is already known, what has already been tried, and what NOT to re-investigate. The goal is to prevent re-spinning on documented issues.

---

### 🟡 second_drag_bug — MOSTLY FIXED (2026-02-18, live testing in progress)
**Symptom**: Second IK drag produces wrong result — snap-back, wrong initial position, or accumulated twist.

**Root causes found (2026-02-18)**:
1. **Constraint space mismatch**: Copy Rotation in LOCAL space reads `matrix_basis` (delta from rest pose). Since `.ik` bones' rest pose IS the current posed position, LOCAL copies Identity → DAZ bone snaps to T-pose. **Fixed: Changed to POSE space.**
2. **Bend/twist not separated**: Copy Rotation (in ANY space) copies combined swing+twist to DAZ bend bones. Axis filtering (`use_y=False`) doesn't work because POSE space axes ≠ bone-local axes. **Fixed: Removed Copy Rotation from bend bones, added manual swing/twist decomposition using `decompose_swing_twist()`.**
3. **rotation_mode not checked**: Setting `rotation_quaternion` on Euler-mode bones does nothing. Diffeomorphic imports may use Euler. **Fixed: Added rotation_mode check.**

**Fixes applied (in code, confirmed partially working)**:
- POSE space for Copy Rotation (non-bend bones) — confirmed fixes snap-to-straight
- Swing/twist decomposition in `update_ik_drag()` post-processing — confirmed running, correct values
- Swing/twist decomposition in `dissolve_ik_chain()` bake step — confirmed baking
- rotation_mode check for all rotation setting — just added, awaiting test
- Bake constraint results via evaluated depsgraph before removing — working
- `frame_set()` before STEP 3.5 cache restore in dissolve (ordering fix) — working

**Remaining gaps (in priority order)**:
1. **Does rotation_mode fix make the arm visually move?** — Awaiting test. Console shows correct swing/twist values but mesh wasn't moving before this fix.
2. **Collar bones not baked** — `Shoulder_Track_Temp` (Damped Track) is skipped by bake check. Collar relies on `INSERTKEY_VISUAL` + `frame_set()`.
3. **`cleanup_temp_ik_chains()` (Alt+X debug cleanup) does NOT use new swing/twist approach** — uses old patterns. Only affects debug mode.

**Key technical findings** (see TECHNICAL_REFERENCE.md for full details):
- LOCAL space: reads `matrix_basis` (delta from rest). Breaks when target/owner have different rest poses.
- POSE space: reads armature-space matrix. Rest-pose agnostic. Correct for orientation matching.
- POSE axis filtering: axes are armature-space, NOT bone-local. Cannot filter bone twist this way.
- `decompose_swing_twist(rot, 'Y')`: proper way to separate bend from twist for DAZ architecture.
- Always check `bone.rotation_mode` before setting rotation (QUATERNION vs Euler).

**History**: This bug has been worked on 4 times (Feb 8, 10, 17, 18). The Feb 18 session identified the constraint space as root cause and implemented swing/twist decomposition. Major breakthrough.

**Last investigated**: 2026-02-18 (live testing with user)

---

### 🟡 arm_shrugs — OPEN (pre-existing, deferred)
**Symptom**: Arm shrugs upward instead of reaching forward when dragging hand.
**Status**: Pre-existing before `refactor/ik-chain-architecture` branch. Will address after refactor cleanup.
**Don't re-investigate**: Pole targets — already confirmed disabled for arms (DAZ twist bone incompatibility). See TECHNICAL_REFERENCE.md:220-225.
**Likely cause**: Stiffness tuning on shoulder/collar or chain length including collar.

---

### 🟡 knee_bends_backward — OPEN (pre-existing, deferred)
**Symptom**: Knee bends backward, thigh twists on leg IK drag.
**Status**: Pre-existing before refactor branch.
**Known partial fix**: Pre-bend angle (0.8 radians) in `ik_templates.py`. Thigh Y-axis locked to prevent twist accumulation — daz_bone_select.py:731-736.
**What to check**: Whether pre-bend is being read from template correctly (was hardcoded at one point — fixed, but verify).

---

### 🟡 ik_refactor_step_3b — OPEN (pending)
**What it is**: Replace old rotation cache/restore patterns with the new baking approach in 3 remaining locations.
**Status**: Identified in refactor plan but marked "TEST FIRST" — SCRATCHPAD.md:65.
**Note**: Line numbers in SCRATCHPAD (747, 1503, 2387) have shifted since refactor. Search for `rotation_cache = {}` to find current locations.

---

### ✅ Low-priority / stable issues
- **LIMIT_ROTATION missing**: Diffeomorphic doesn't always create constraints for head, shoulder twist, elbow, forearm twist. Workaround: `enforce_rotation_limits()` falls back to IK limits. Stable.
- **Module caching**: Blender module caching during development. Workaround: restart Blender or use reload scripts.
- **Control point recapture**: Must run manually after moving PoseBridge outline. Run `posebridge/recapture_control_points.py`.

## Documentation System

This project uses a five-file documentation system to help both humans and AI assistants work effectively:

1. **[CLAUDE.md](CLAUDE.md)** (this file) - Project context, philosophy, and development guidelines
2. **[INDEX.md](INDEX.md)** - Complete file reference and quick lookup for all files
3. **[SCRATCHPAD.md](SCRATCHPAD.md)** - Development journal for active work, experiments, and learnings
4. **[TODO.md](TODO.md)** - Task tracking, roadmap, and project backlog
5. **[TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md)** - Hard-won knowledge about IK, DAZ rigs, and Blender integration

### Development Patterns

**Project-specific templates** (see [templates/](templates/) directory):
- [Rollback plan](templates/rollback-plan-template.md) - Use before risky changes (refactors, upgrades)
- [Bug status entry](templates/bug-status-template.md) - Document complex bugs in STATUS section

**General patterns** (see [claude-craft](../../../claude-craft/)):
- [Incremental Refactoring](../../../claude-craft/workflows/incremental-refactoring.md) - Large file refactoring workflow
- [Documentation-First Debugging](../../../claude-craft/patterns/documentation-first-debugging.md) - Prevent re-investigation
- [Constrained AI Prompting](../../../claude-craft/patterns/constrained-ai-prompting.md) - Predictable AI output
- [Socratic Prompting](../../../claude-craft/patterns/socratic-prompting.md) - Deep reasoning through questions
- [Quick Reference](../../../claude-craft/QUICK_REFERENCE.md) - Pattern decision guide

---

### For AI Assistants

When working on this project:
1. **Check the STATUS section above first** — if the bug is listed, read what's already known before investigating
2. **Check [INDEX.md](INDEX.md)** to find files before searching or grepping
3. **Check [TODO.md](TODO.md)** for current priorities and planned work
4. **Check [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md)** when debugging IK or rig issues — especially the Research Findings section for non-obvious Blender/DAZ behaviors
5. **Follow the principles** in this document (especially "Code Simplicity Principle")
6. **Update [SCRATCHPAD.md](SCRATCHPAD.md)** as you work:
   - Document decisions made
   - Note what works and what doesn't
   - Capture bugs encountered and solutions
   - Record technical observations
7. **Update [TODO.md](TODO.md)** when:
   - Completing tasks (mark done, move to Recently Completed)
   - Discovering new bugs or issues
   - Identifying technical debt
   - Having ideas for future improvements
8. **Update [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md)** when:
   - Discovering why something doesn't work
   - Finding solutions to tricky problems
   - Learning new facts about DAZ rigs or Blender IK
9. **Update the STATUS section in this file** when:
   - A listed issue is confirmed fixed (change 🔴/🟡 to ✅, note what resolved it)
   - A new open issue is discovered (add entry with root cause, what's known, what to check)
   - New investigation narrows down a known issue (update "What to check" / "Don't re-investigate")
10. **Use development patterns** from templates/ and claude-craft when situations arise
11. **Prefer simple solutions** over complex ones
12. **Ask questions** if requirements are unclear

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
