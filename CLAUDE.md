# BlenDAZ Project - Claude Code Instructions

## Design Philosophy

**Make posing fun, easy, and tactile for artists.**

Blender is technically powerful but its interface can overwhelm visually-oriented users. BlenDAZ aims to reduce cognitive load, keep viewports clean, feel intuitive via click-drag interactions, and bridge the gap for DAZ Studio users expecting visual, direct manipulation in Blender.

## Project Overview

BlenDAZ is a collection of Blender addons for working with DAZ Studio characters (Genesis 8/9) in Blender. It improves the posing workflow for characters imported via the Diffeomorphic DAZ Importer.

**Tech Stack**: Python 3.x, Blender 4.3+ API (bpy; verified on 5.1.2 — see 2026-08-01 audit), GPU viewport rendering. Requires Diffeomorphic DAZ Importer (v5 recommended).

**Codebase**: ~30K+ lines Python. Main engine is `daz_bone_select.py` (~14K lines) — don't read it blind; use the vault routing below.

## Before You Touch Any Code

**Use the Vault MCP** to read the relevant context notes before modifying code. The vault has architecture docs, invariants, design decisions, and research that won't fit in this file.

### Step 1 — Read the routing table
```
vault: projects/blendaz/_blendaz-map.md
```
The "Task Routing" table tells you which vault notes to read for your specific task.

### Step 2 — Read the invariants for your code area
```
vault: projects/blendaz/blendaz-invariants.md
```
14 "don't break this" contracts. Each has been violated before, causing bugs. The Quick Lookup table at the bottom maps code areas to relevant invariants.

### Step 3 — Read the code you're changing
Only after reading the vault context. This prevents burning context window on 14K lines of code without knowing what matters.

## Key Vault Notes

| Note | What it tells you |
|------|-------------------|
| `blendaz-invariants` | Code contracts — what MUST stay true, failure modes |
| `blendaz-architecture` | Module layout, modal architecture, multi-character, raycast patterns |
| `blendaz-fabrik` | FABRIK solver — split-chain, stiffness, clamping, spine injection |
| `blendaz-golden-rules` | Zero visual disruption on grab and release |
| `blendaz-decisions` | Why things are built this way (prevents relitigating settled questions) |
| `blendaz-bugs` | Known bugs and investigation status |
| `blendaz-research-findings` | DAZ behavioral rules, stiffness data from reverse-engineering |
| `blendaz-audit-2026-08-01` | 28-bug audit closure record, per-item fixes and evidence |

### Vault Access

Read vault notes with the MCP tool:
- `mcp__vault__read_note` with path like `projects/blendaz/blendaz-invariants.md`
- `mcp__vault__search_notes` to find notes by keyword

If the vault MCP is not available, the notes are also readable at `D:\Dev\vault\`.

## Golden Rule

**Zero visual disruption on grab and release.** No pops on initiate, no snaps on release. The pose must be frame-perfect. This applies to all IK/FABRIK/drag code.

The golden rule has **tiers** — see `vault: projects/blendaz/blendaz-golden-rules.md` for the full framework. T0 is always the goal, but T1/T2 can be acceptable for shipping v1 of new features when the alternative is not shipping at all.

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

## Dev Tooling — Bridge Workflow

BlenDAZ has a Claude Bridge integration for **edit → reload → test** without restarting Blender. The bridge addon runs an HTTP server inside Blender on port 7777.

### Prerequisites
- Blender open with a DAZ character
- Claude Bridge addon started (Sidebar > Claude Bridge > Start Server)

### The Edit/Test Loop (use this when working on solver/IK/pin code)
```python
from scripts.bridge_workflow import Workflow
wf = Workflow()

# After editing code:
wf.reload_addon()                        # Hot-reload without restarting Blender
wf.run_all_tests()                       # Run bake_mute_pop, arm_drag, hip_translate, euler_clamp
wf.report()                              # Print tier results (T0/T1/T2/T3)

# Or run with screenshots for visual verification:
wf.run_all_tests(with_screenshots=True)

# Or a single scenario:
wf.run_solver_test("hip_translate")

# Quick solver-only reload (faster, when only tweaking fabrik_solver.py):
wf.reload_solver_only()
```

### Debug Overlay (for FABRIK drag visualization)
```python
wf.enable_overlay()     # Turns on chain drawing in viewport
# Now drag a bone in Blender — you'll see:
#   Blue lines: Sub-chain A (root → drag point)
#   Orange lines: Sub-chain B (drag point → pinned tip)
#   Green cross: Pin target
#   Yellow cross: Drag target
wf.disable_overlay()    # Turns it off
```

The overlay can also be toggled via the flag `_FABRIK_DEBUG_OVERLAY` in `daz_bone_select.py` (line ~105), or by running `scripts/debug_overlay.py` as a script in Blender's Text Editor.

### CLI Usage
```bash
python scripts/bridge_workflow.py --reload                    # Reload + test all
python scripts/bridge_workflow.py --reload --screenshots      # With before/after screenshots
python scripts/bridge_workflow.py --scenario hip_translate     # Single scenario
python scripts/bridge_test_client.py                          # Health check only
```

### Test Scenarios
| Scenario | What it tests | Invariant |
|---|---|---|
| `bake_mute_pop` | Bake+mute cycle causes zero position change | #3 |
| `arm_drag` | Shoulder rotation, measure pinned hand drift | #6, #9 |
| `hip_translate` | Hip 10cm translate, measure pinned hand drift | Pin maintenance |
| `euler_clamp` | Our clamp matches Blender's LIMIT_ROTATION | #8 |

### Automated Tests (pytest-blender, headless)
```bash
BLENDER="D:/SteamLibrary/steamapps/common/Blender/blender.exe"
$BLENDER --background --python tests/run_tests.py -- tests/test_fabrik_regression.py -v
```
See `tests/README.md` for full details. Note: `hide_viewport=True` objects are excluded from background depsgraph eval — unhide to measure. `daz_shared_utils.py` changes need a full Blender restart.

## Commit Discipline

Wait until things work before committing. Don't commit every small fix.

## Agents — When to Use Them

BlenDAZ has two specialized agents in `.claude/agents/` (recreated 2026-08-02). **The trigger is risk, not file count.**

- **Architect** (`architect.md`) — invoke BEFORE writing code when the task touches IK/FABRIK/drag/pin/solver code (even single-file), modal event handling, 3+ files, a new feature, or a solver-approach switch (Approach Pivot Protocol is mandatory). Skip only for simple non-IK changes (UI label, panel button, config tweak).
- **Reviewer** (`reviewer.md`) — invoke BEFORE committing when the change touches IK/FABRIK/drag/pin/solver code (even one line), constraint bake/mute/restore cycles, `view_layer.update()` calls, modal event handling, or 3+ files. Rates golden-rule tier (T0-T3) and checks the 14 vault invariants.

**The key rule**: anything drag/IK/pin-related in `daz_bone_select.py` or `fabrik_solver.py` gets both agents — architect before coding, reviewer before committing. Single-file doesn't mean low-risk in a 13K-line modal. Both agents load context from `D:\Dev\vault\projects\blendaz\` (start at `_blendaz-map.md`).

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
