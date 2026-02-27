# PoseBridge - Session Start

> **For AI Assistants**: Read this file first. It's the only file you need for most sessions.
> Update this file at the end of every session (3-5 min) so the next session starts fast.

**Updated**: 2026-02-24 (session 6)

---

## Current State

**Phase**: Face Panel complete, N-Panel controls functional, visual polish in progress
**Status**: Body, Hands, and Face panels all functional. N-Panel has Body Controls (Reset Pose) and Face Controls (Reset Face + expression/viseme sliders). DAZ-style selection brackets and mesh hover highlights implemented with adjustable opacity. First demo video recorded.

PoseBridge now supports three interaction modes:
- **Body/Hands**: Click-drag bone rotation (quaternion) with 4-way LMB/RMB controls
- **Face**: Click-drag morph values (FACS custom properties on armature) with same 4-way pattern
- **N-Panel sliders**: Expression presets (smile, frown, etc.) and viseme presets (AA, EE, etc.) as 0-1 intensity sliders that scale preset FACS values

Visual overlays:
- **Mesh hover highlight**: Amber overlay on mesh region weighted to hovered bone (opacity adjustable)
- **Selection brackets**: Bone-aligned OBB corner brackets — gold/amber on hover, light gray on select
- **Highlight Opacity slider**: Controls all highlight/bracket alpha from the Settings N-panel

---

## What We Did Last Session (2026-02-24, session 6)

### Bug Fixes
- **Fixed left hand individual finger LMB vert direction** — Drag down was extending fingers instead of curling them closed. Root cause: `vert_invert` defaulted to `False` for fingers; right-hand fingers were accidentally correct because the right-side mirror flipped them, but left-hand fingers got no mirror. Fix: set `vert_invert = is_left_finger` (True for `l*` bones, False for `r*` bones — mirror then handles right side correctly).

**Files modified**:
- `daz_bone_select.py` — Finger branch in `update_rotation()`: added `is_left_finger` check, set `vert_invert = is_left_finger` for LMB and RMB vert (line ~7383)

---

## Next Up

1. **N-Panel: Categorized morph sliders** — DAZ-style sections (Brow, Eyes, Mouth, etc.) instead of flat list
2. **BUG: Head bone selection fails from deselected state** — clicking head CP when nothing is selected doesn't work
3. **BUG: Mesh highlight showing on left (PoseBridge) panel** — highlight overlay appears in the wrong viewport
4. **Polish Shoulders Group LMB horiz** — forward/back axis feels off
5. **Pin system debugging session** — feet/shin disconnect, arm snapping

---

## Don't Forget

- **`daz_shared_utils.py` changes → FULL Blender restart** (importlib.reload() doesn't work)
- **`daz_bone_select.py` changes → reload script** or restart: `exec(open(r"D:\dev\BlenDAZ\reload_daz_bone_select.py").read())`
- **`posebridge/core.py` changes → FULL Blender restart** (PoseBridgeSettings PropertyGroup)
- **`posebridge` module changes** → `exec(open(r"D:\dev\BlenDAZ\projects\posebridge\recapture_with_reload.py").read())`
- **Axis convention**: Y = twist (along bone length), X = forward/back bend, Z = side-to-side bend
- **FACS property tiers**: `facs_ctrl_*` (bilateral), `facs_bs_*_div2` (unilateral blendshape), `facs_jnt_*` (joint-driven via rotation_euler drivers)
- **Boolean FACS properties exist** (e.g., `facs_ctrl_EyeLookAuto`) — always check `isinstance(current, bool)` before assigning float
- **Undo stack is class-level** on `VIEW3D_OT_daz_bone_select` — external operators must use `VIEW3D_OT_daz_bone_select._undo_stack` (not instance ref)
- **Quaternion only** — never use Euler mode in PoseBridge (except bones with rotation_euler drivers — jaw, tongue, eye bones)
- **Driven rotation bones** — `_get_driven_rotation_bones()` detects bones with Diffeomorphic rotation_euler drivers. These MUST stay in Euler mode or FACS joint morphs break.
- **Locked drag state** — `_drag_from_posebridge`, `_drag_control_point_id`, `_drag_bone_names` are set at mouse-down and used throughout drag. Don't rely on hover state during drag.
- **Native translate pass-through** — When `_use_native_translate` is True, the gate at top of `modal()` passes ALL events through until confirm/cancel.

---

## Files Most Likely Needed Today

| File | Why |
|------|-----|
| `daz_bone_select.py` | Modal operator, draw callbacks, bracket/highlight logic, reset operators |
| `daz_shared_utils.py` | FACE_EXPRESSION_PRESETS, FACE_MORPH_CONTROLS, control point defs |
| `projects/posebridge/core.py` | PoseBridgeSettings (highlight_opacity, expression/viseme sliders) |
| `projects/posebridge/panel_ui.py` | Panel view switching, Settings panel, visibility toggling |
| `projects/posebridge/extract_face.py` | Face CP positions, camera setup |
| `projects/posebridge/drawing.py` | GPU overlay (circles/diamonds, morph CP colors) |

---

## Active Research Questions

> Things we still don't know. Add when a question comes up; move answered items to TECHNICAL_REFERENCE.md Research Findings.

- [ ] **Genesis 9 rig compatibility** — same bone naming as G8? Different rotation orders?
- [ ] **Categorized morph slider UI** — best way to organize FACS morphs in N-panel (by region vs by function)
- [ ] **Expression preset blending** — do multiple sliders compose correctly or do they fight over the same FACS properties?

---

## Need Deeper Context?

Only read these if the task requires it:

| File | When to read |
|------|-------------|
| [CLAUDE.md](CLAUDE.md) | Architecture, principles, full file map |
| [INDEX.md](INDEX.md) | Finding a specific file |
| [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md) | Technical findings, research, rig architecture (bone nodes, rig detection, rotation math) |
| [SCRATCHPAD.md](SCRATCHPAD.md) | Understanding decisions from recent sessions |
| [../../docs/CLAUDE.md](../../docs/CLAUDE.md) | Parent BlenDAZ project context |

---

## How to Update This File

At the end of each session, update:
1. **Updated** date
2. **Current State** — 2-3 sentences on where things stand
3. **What We Did Last Session** — bullet list of changes + files modified
4. **Next Up** — sync with TODO.md current work
5. **Don't Forget** — add any new gotchas discovered; remove stale ones
6. **Files Most Likely Needed Today** — update based on what's active

Takes 3-5 minutes. Saves 15-20 minutes next session.
