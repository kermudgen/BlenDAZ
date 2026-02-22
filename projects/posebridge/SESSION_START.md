# PoseBridge - Session Start

> **For AI Assistants**: Read this file first. It's the only file you need for most sessions.
> Update this file at the end of every session (3-5 min) so the next session starts fast.

**Updated**: 2026-02-22

---

## Current State

**Phase**: Face Panel complete, N-Panel controls in progress
**Status**: Body, Hands, and Face panels all functional. N-Panel has Body Controls (Reset Pose) and Face Controls (Reset Face + expression/viseme sliders). Undo for reset just fixed.

PoseBridge now supports three interaction modes:
- **Body/Hands**: Click-drag bone rotation (quaternion) with 4-way LMB/RMB controls
- **Face**: Click-drag morph values (FACS custom properties on armature) with same 4-way pattern
- **N-Panel sliders**: Expression presets (smile, frown, etc.) and viseme presets (AA, EE, etc.) as 0-1 intensity sliders that scale preset FACS values

---

## What We Did Last Session

### Face Panel (completed across multiple sessions)
- **Live face camera** (`PB_Camera_Face`) aimed at head bone rest position
- **~26 face control points** with morph interaction mode — LMB bilateral, RMB asymmetric
- **FACS morph drag system**: `start_morph_drag()`, `update_morph()`, `end_morph()` in daz_bone_select.py
- **Morph undo**: Custom undo stack entries with type `'morph'`
- **Face CP positions** calculated from actual bone rest positions (lEye, rEye, lowerJaw, lip bones, etc.)
- **Visibility toggling**: Face panel hides all PB_ objects, shows live character mesh

### N-Panel Overhaul (this session)
- **Removed** old PowerPose panel (`POSE_OT_daz_powerpose_control`, `VIEW3D_PT_daz_powerpose_main`)
- **Added Body Controls panel** with Reset Pose button (resets all bone rotations/locations/scales)
- **Added Face Controls panel** with:
  - Reset Face button (zeroes all `facs_*` properties, resets sliders)
  - Expression sliders: Smile, Frown, Surprise, Anger, Disgust, Fear, Sadness, Wink L, Wink R
  - Viseme sliders: AA, EE, IH, OH, OO, FV, TH, MM, CH
- **Slider architecture**: Dynamic FloatProperties on PoseBridgeSettings with update callbacks that scale FACE_EXPRESSION_PRESETS values by slider intensity
- **Boolean property guard**: Skip `isinstance(current, bool)` in reset loops (e.g., `facs_ctrl_EyeLookAuto`)

### Bug Fixes (this session)
- **Fixed undo for Reset Pose/Face**: `self._undo_stack = []` in invoke() created an instance variable shadowing the class-level list. Reset operators pushed to class list, modal popped from instance list. Fix: `VIEW3D_OT_daz_bone_select._undo_stack.clear()` instead.
- **Removed `bpy.ops.ed.undo_push()`** from reset operators — was unnecessary and potentially interfering

**Files modified**:
- `daz_bone_select.py` — Removed PowerPose classes, added body_reset/face_reset operators, body/face controls panels, undo stack fix (line ~2504)
- `daz_shared_utils.py` — Added `FACE_EXPRESSION_PRESETS`, `FACE_EXPRESSION_SLIDERS`, `FACE_VISEME_SLIDERS`; fixed squint property name (`EyeSquint` → `EyesSquint`); added mouth upper/lower CPs to `FACE_MORPH_CONTROLS`
- `projects/posebridge/core.py` — Added expression/viseme slider FloatProperties with update callbacks, `_apply_expression_preset()`, `_make_expr_update()` factory
- `projects/posebridge/extract_face.py` — Face camera creation, CP position calculation, added mouth upper up / lower down CPs
- `projects/posebridge/panel_ui.py` — Enabled face button, visibility toggling on panel switch

---

## Next Up

1. **N-Panel: Categorized morph sliders** — DAZ-style sections (Brow, Eyes, Mouth, etc.) instead of flat list
2. **BUG: Head bone selection fails from deselected state** — clicking head CP when nothing is selected doesn't work
3. **BUG: Mesh highlight showing on left (PoseBridge) panel** — highlight overlay appears in the wrong viewport
4. **Polish Shoulders Group LMB horiz** — forward/back axis feels off

---

## Don't Forget

- **`daz_shared_utils.py` changes → FULL Blender restart** (importlib.reload() doesn't work)
- **`daz_bone_select.py` changes → reload script** or restart: `exec(open(r"D:\dev\BlenDAZ\reload_daz_bone_select.py").read())`
- **`posebridge` module changes** → `exec(open(r"D:\dev\BlenDAZ\projects\posebridge\recapture_with_reload.py").read())`
- **Axis convention**: Y = twist (along bone length), X = forward/back bend, Z = side-to-side bend
- **FACS property tiers**: `facs_ctrl_*` (bilateral), `facs_bs_*_div2` (unilateral blendshape), `facs_jnt_*` (joint-driven)
- **Boolean FACS properties exist** (e.g., `facs_ctrl_EyeLookAuto`) — always check `isinstance(current, bool)` before assigning float
- **Undo stack is class-level** on `VIEW3D_OT_daz_bone_select` — external operators must use `VIEW3D_OT_daz_bone_select._undo_stack` (not instance ref)
- **Quaternion only** — never use Euler mode in PoseBridge

---

## Files Most Likely Needed Today

| File | Why |
|------|-----|
| `daz_bone_select.py` | Modal operator, reset operators, face/body control panels (~line 7350+) |
| `daz_shared_utils.py` | FACE_EXPRESSION_PRESETS, FACE_MORPH_CONTROLS, control point defs |
| `projects/posebridge/core.py` | Expression/viseme slider properties, update callbacks |
| `projects/posebridge/panel_ui.py` | Panel view switching, visibility toggling |
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
