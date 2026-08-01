# BlenDAZ Project - Claude Code Instructions

## Design Philosophy

**Make posing fun, easy, and tactile for artists.**

Blender is technically powerful but its interface can overwhelm visually-oriented users. BlenDAZ aims to reduce cognitive load, keep viewports clean, feel intuitive via click-drag interactions, and bridge the gap for DAZ Studio users expecting visual, direct manipulation in Blender.

## Project Overview

BlenDAZ is a collection of Blender addons for working with DAZ Studio characters (Genesis 8/9) in Blender. It improves the posing workflow for characters imported via the Diffeomorphic DAZ Importer.

**Tech Stack**: Python 3.x, Blender 5.0+ API (bpy), GPU viewport rendering. Requires Diffeomorphic DAZ Importer (v5 recommended).

## Quick File Lookup

**See [INDEX.md](INDEX.md) for complete reference.** Key files:
- Bone selection, IK, modal interaction → [daz_bone_select.py](daz_bone_select.py)
- Shared utilities (rotation, limits, CPs) → [daz_shared_utils.py](daz_shared_utils.py)
- Visual posing editor → [posebridge/](posebridge/)
- Pose blending → [poseblend/](poseblend/)
- Supporting docs → [docs/](docs/)

## Running / Testing

- **Workflow**: `register_only.py` → Scan for Characters → Register → Activate
- **daz_bone_select**: Press `Ctrl+Shift+D` in Pose mode, hover bones, click-drag to rotate
- **Quick test**: Use [quick_test.py](quick_test.py) — handles prerequisites, enables posebridge, starts operator

## Development Conventions

### Artist-First Design
1. **Visual over Abstract** - Show, don't tell
2. **Direct Manipulation** - Click-drag beats buttons
3. **Immediate Feedback** - Changes visible instantly
4. **Minimal Cognitive Load** - Hide complexity until needed
5. **Discoverable** - Explore without fear of breaking things
6. **Undo-Friendly** - Everything reversible

### Code Simplicity Principle
**Don't overcomplicate things.** When choosing between complex automatic logic with edge cases and simple explicit configuration, choose simple. Manual configuration is easier to understand, debug, and maintain than "clever" automatic systems.

### Blender API Patterns
- `bpy.types.SpaceView3D.draw_handler_add()` for custom drawing
- Draw handlers don't receive context — get from `bpy.context`
- Modal operators return `{'RUNNING_MODAL'}`, `{'FINISHED'}`, or `{'CANCELLED'}`
- Diffeomorphic creates LIMIT_ROTATION constraints on most bones; some may lack them

## Issue Status

> Read this before investigating any bug — prevents re-spinning on documented issues.

### 🟡 second_drag_bug — MOSTLY FIXED (2026-02-18)
Second IK drag snap-back/wrong position. Root causes: constraint space mismatch (fixed → POSE space), bend/twist not separated (fixed → `decompose_swing_twist()`), rotation_mode not checked (fixed). Remaining: rotation_mode visual test, collar bone baking. See [docs/TECHNICAL_REFERENCE.md](docs/TECHNICAL_REFERENCE.md) for full details.

### 🟡 ik_refactor_step_3b — OPEN
Replace old `rotation_cache = {}` patterns with baking approach in 3 remaining locations.

### 🟢 pin_maintenance_parity — CORE COMPLETE (2026-07-03)
Pin maintenance now covers rotation (R on hip/pelvis/spine), over-extension (reach leash per DAZ Rule 8 — hip translates back instead of breaking the pin), and pose preservation (originals-reset instead of identity-reset for solver-unowned bones). Tested against production code in `tests/test_pin_maintenance.py` (synthetic G8 rig, headless). Remaining: live feel-test, multi-hand spine drags, Rule 10 full-chain distribution — see TODO.md.

### ✅ Fixed issues (reference only)
- **arm_shrugs** — Analytical arm IK solver, 62 tests
- **knee_bends_backward** — Analytical leg IK solver, 57 tests

---

## Documentation System

Five-file system at project root, plus supporting docs in [docs/](docs/).

1. **CLAUDE.md** (this file) — Philosophy, conventions, issue status
2. **[SESSION_START.md](SESSION_START.md)** — Fast session resumption (read first every session)
3. **[INDEX.md](INDEX.md)** — File reference and quick lookup
4. **[TODO.md](TODO.md)** — Task tracking, roadmap, backlog
5. **[SCRATCHPAD.md](SCRATCHPAD.md)** — Long-form decision records and experiment logs
6. **[docs/TECHNICAL_REFERENCE.md](docs/TECHNICAL_REFERENCE.md)** — IK, DAZ rigs, Blender integration

See [docs/PROJECT_SETUP_GUIDE.md](docs/PROJECT_SETUP_GUIDE.md) for update cadence, archiving rules, and templates.

---

### For AI Assistants

#### Step 1 — Always read first
**[SESSION_START.md](SESSION_START.md)** — current state, last session, what's next. Only file you need for most sessions.

#### Step 2 — Read this file (CLAUDE.md)
Design philosophy, issue status, code conventions.

#### Step 3 — Only if the task requires it
- Finding a file → [INDEX.md](INDEX.md)
- Full task backlog → [TODO.md](TODO.md)
- IK/rig research → [docs/TECHNICAL_REFERENCE.md](docs/TECHNICAL_REFERENCE.md)
- Decision history → [SCRATCHPAD.md](SCRATCHPAD.md)

**Don't front-load.** Read reference docs only when the task requires them.

#### What about auto-memory?
Auto-memory (MEMORY.md) is loaded automatically — you don't need to read it.
It contains user preferences, workflow corrections, and external references.
Project state lives here in the docs, not in memory.

#### When working on this project
1. Check the Issue Status above before investigating any bug
2. Follow Code Simplicity and Artist-First principles
3. Update [SCRATCHPAD.md](SCRATCHPAD.md), [TODO.md](TODO.md), and Issue Status as you work
4. Prefer simple solutions over complex ones

#### End of session
Run `/save` to update SESSION_START.md and project docs.
Save auto-memories only when something genuinely new and cross-session-relevant was learned.

## Current Focus

**Pin maintenance DAZ parity.** The analytical depsgraph-handler approach shipped in production (`daz_bone_select.py`) — the native-IK test-script route was abandoned. As of 2026-07-03 pins hold through hip translation AND rotation, over-extension leashes the hip (DAZ Rule 8), and user pose survives pinned drags. Next: live feel-testing and Rule 10 full-chain rotation distribution. See [SESSION_START.md](SESSION_START.md).

## Questions to Ask Before Making Changes

1. Does this make the tool easier for artists to use?
2. Am I over-engineering? Is there a simpler way?
3. Does this break existing functionality?
4. Does this follow the Code Simplicity and Artist-First principles?
