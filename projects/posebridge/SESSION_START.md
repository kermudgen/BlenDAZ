# PoseBridge - Session Start

> **For AI Assistants**: Read this file first. It's the only file you need for most sessions.
> Update this file at the end of every session (3-5 min) so the next session starts fast.

**Updated**: 2026-02-28 (session 9)

---

## Current State

**Phase**: Multi-character + multi-viewport architecture implemented, ready for testing
**Status**: The modal operator now works seamlessly across ALL open 3D viewports. Viewport resolution infrastructure consolidates cross-viewport patterns. PB viewport camera swaps on character switch. mode_set isolated to main viewport. Camera leak from N-panel prevented. Full multi-character workflow: `register_only.py` → Scan → Register → Activate. Character registry (`CharacterSlot`) stores per-character data.

PoseBridge interaction modes (unchanged):
- **Body/Hands**: Click-drag bone rotation (quaternion) with 4-way LMB/RMB controls
- **Face**: Click-drag morph values (FACS custom properties on armature) with same 4-way pattern
- **N-Panel sliders**: Expression presets + viseme presets as 0-1 intensity sliders

---

## What We Did Last Session (2026-02-28, session 9)

### Multi-Viewport Modal Architecture
One modal, all viewports. The BlenDAZ modal now works seamlessly across all open 3D viewports.

**New helpers in `daz_bone_select.py`:**
- `_resolve_event_viewport(context, event)` — canonical "find viewport under mouse" (replaces 3 duplicates)
- `_find_pb_viewport(context)` — find PB viewport by CAMERA mode + PB_Camera_* name
- `_find_main_viewport(context)` — find non-PB viewport
- `_mode_set_safe(context, mode)` — route mode_set through main viewport (protects PB camera)

**Bug fixes:**
- PB viewport goes black on character switch → step 3b swaps PB camera to new character
- mode_set corrupts PB viewport → all 6 mode_set calls routed through main viewport
- Camera leak to main viewport → `set_panel_view` targets PB viewport only
- Header text only in one viewport → `_set_header()` broadcasts to all VIEW_3D areas

**Cross-viewport interaction:**
- LEFTMOUSE resolves viewport at top, uses it for UI/gizmo/raycast checks
- check_hover non-PB path uses resolved viewport
- Click-through raycast uses resolved viewport
- Double-click uses window-relative coords

### Files Modified
- `daz_bone_select.py` — 4 new helpers, 3 refactored methods, 6 mode_set replacements, LEFTMOUSE handler, check_hover, header broadcasting
- `projects/posebridge/panel_ui.py` — `_find_pb_viewport()` helper, `set_panel_view` targets PB viewport

---

## Next Up

1. **Test multi-viewport architecture** — register two characters, test Hands/Face switching + character switching across viewports
2. **Camera ortho scale tweaks** — Body=5, Hands=0.7, Face=0.525
3. **BlenDAZ toggle button should stop modal in ALL viewports**
4. **Collar snapping during arm IK drag** — pre-existing analytical solver issue
5. **N-Panel: Categorized morph sliders** — DAZ-style sections (Brow, Eyes, Mouth)
6. **BUG: Head bone selection fails from deselected state**

---

## Don't Forget

- **`daz_shared_utils.py` changes → FULL Blender restart** (importlib.reload() doesn't work)
- **`daz_bone_select.py` changes → reload script** or restart: `exec(open(r"D:\dev\BlenDAZ\reload_daz_bone_select.py").read())`
- **`posebridge/core.py` changes → FULL Blender restart** (PoseBridgeSettings PropertyGroup)
- **`posebridge` module changes** → `exec(open(r"D:\dev\BlenDAZ\projects\posebridge\recapture_with_reload.py").read())`
- **User's preferred workflow**: `register_only.py` → Scan → Register → Activate (NOT `setup_all.py`)
- **Commit discipline**: wait until things work before committing
- **Blender objects don't support arbitrary Python attributes** — use `obj["foo"]` or return values
- **`_just_selected_armature`** — when True, modal early-out passes ALL events through except clicks on registered DAZ characters
- **Multi-character naming**: `char_tag` = sanitized armature name, used as suffix for PB objects
- **Z-offset stacking**: first char -50m, each subsequent -5m lower
- **Multi-viewport rules**: Never use `context.area`/`context.region` directly — use `_resolve_event_viewport()`. Never call `mode_set()` directly — use `_mode_set_safe()`. PB viewport identified by CAMERA mode + PB_Camera_* name.
- **Testing guide**: `TESTING_MULTI_CHARACTER.md`
- **Axis convention**: Y = twist (along bone length), X = forward/back bend, Z = side-to-side bend
- **FACS property tiers**: `facs_ctrl_*` (bilateral), `facs_bs_*_div2` (unilateral), `facs_jnt_*` (joint-driven)
- **Locked drag state** — `_drag_from_posebridge`, `_drag_control_point_id`, `_drag_bone_names` set at mouse-down
- **Native translate pass-through** — When `_use_native_translate` is True, gate at top passes ALL events

---

## Files Most Likely Needed Today

| File | Why |
|------|-----|
| `daz_bone_select.py` | Modal operator, click-through logic, _just_selected_armature early-out |
| `projects/posebridge/core.py` | CharacterSlot, PoseBridgeSettings, find_character_mesh |
| `projects/posebridge/panel_ui.py` | Register/scan operators, character list UI, per-char cameras |
| `projects/posebridge/outline_generator_lineart.py` | Outline generation with char_tag naming |
| `register_only.py` | Module registration entry point |
| `D:\Dev\SimplySwitch\simply_switch.py` | Reference for click-to-switch pattern |

---

## Active Research Questions

> Things we still don't know. Add when a question comes up; move answered items to TECHNICAL_REFERENCE.md Research Findings.

- [ ] **Genesis 9 rig compatibility** — same bone naming as G8? Different rotation orders?
- [ ] **Non-registered rig interaction** — does Blender's PASS_THROUGH work reliably for bone posing when a modal is running?
- [ ] **Multi-character switching UX** — N-Panel radio vs mesh click — which feels more natural?

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
