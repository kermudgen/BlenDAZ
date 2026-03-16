# PoseBridge - Session Start

> **For AI Assistants**: Read this file first. It's the only file you need for most sessions.
> Update this file at the end of every session (3-5 min) so the next session starts fast.

**Updated**: 2026-03-06 (session 14)

---

## Current State

**Phase**: Active stress testing and feature iteration
**Status**: Streamline mesh muting added — user-selectable popup hides high-poly child meshes and disables their Armature modifiers for dramatically faster interactive posing. Sub-toggles now live-update (restore-all then re-apply). Face mode isolates active character in PB viewport via Blender local view. All committed as `2407846`.

PoseBridge interaction modes (unchanged):
- **Body/Hands**: Click-drag bone rotation (quaternion) with 4-way LMB/RMB controls
- **Face**: Click-drag morph values (FACS custom properties on armature) with same 4-way pattern
- **N-Panel sliders**: Expression presets + viseme presets as 0-1 intensity sliders

---

## What We Did Last Session (2026-03-05/06, sessions 13-14)

### Streamline High-Poly Mesh Muting
- `core.py`: `streamline_muted_meshes` JSON StringProperty on CharacterSlot with `get_muted_meshes_list()`/`set_muted_meshes_list()`. New `streamline_meshes` BoolProperty on PoseBridgeSettings.
- `streamline.py`: `mute_armature_meshes` param in `apply_streamline()` — hides mesh objects (`hide_viewport`) + disables Armature modifiers (`mod.show_viewport`). Separate from `_DISABLE_MOD_TYPES` path.
- `panel_ui.py`: `BLENDAZ_OT_select_streamline_meshes` popup — scans child meshes, shows vertex counts, auto-checks ≥5K verts (except body mesh), All/None buttons. Available before Streamline is enabled.

### Streamline Sub-Toggle Live Updates
- `core.py`: Split into `_on_streamline_master_toggled` (master ON/OFF) and `_on_streamline_toggled` (sub-toggles). Sub-toggle callback: `apply_streamline(False)` then `apply_streamline(True, ...)` with current values. Master OFF: unconditional `apply_streamline(False)`.
- All 7 sub-toggle BoolProperties now have `update=_on_streamline_toggled`.

### Face Mode Local View Isolation
- `panel_ui.py`: `_enter_face_local_view()` — selects active character objects + face camera, enters local view in PB viewport via `temp_override`. `_exit_face_local_view()` — exits local view when leaving Face mode. Only activates with 2+ registered characters.
- `daz_bone_select.py`: `_refresh_face_local_view()` in `_switch_active_character()` — exits old local view, re-enters with new character when switching in Face mode.
- Re-ensures camera mode after localview (it can snap out). Selection saved/restored around calls.

### Bug Fixes
- Replaced `bpy.ops.object.select_all()` with direct `obj.select_set()` in face local view (context error from N-panel)

---

## Next Up

**Testing (active):**
- [ ] Continue stress testing all features
- [ ] Test Streamline mesh muting with various configurations
- [ ] Test face local view with 2+ characters

**Features:**
1. **Head rotation CP in face mode** — add head rotation control point
2. **Finger bone selection after posing hand** — drill into child bones (low priority)

**Other:**
- BlenDAZ toggle button should stop modal in ALL viewports
- Collar snapping during arm IK drag (pre-existing)

---

## Don't Forget

- **`daz_shared_utils.py` changes → FULL Blender restart** (importlib.reload() doesn't work)
- **`daz_bone_select.py` changes → reload script** or restart
- **`posebridge/core.py` changes → FULL Blender restart** (PoseBridgeSettings PropertyGroup)
- **User's preferred workflow**: `register_only.py` → Scan → Register → Activate (NOT `setup_all.py`)
- **Commit discipline**: wait until things work before committing
- **Blender objects don't support arbitrary Python attributes** — use `obj["foo"]` or return values
- **`_just_selected_armature`** — when True, modal early-out passes ALL events through except clicks on registered DAZ characters
- **Multi-character naming**: `char_tag` = sanitized armature name, used as suffix for PB objects
- **Z-offset stacking**: first char -50m, each subsequent -5m lower
- **Multi-viewport rules**:
  - Never use `context.area`/`context.region` directly — use `_resolve_event_viewport()`
  - Never call `mode_set()` directly — use `_mode_set_safe()`
  - PB viewport = CAMERA mode + PB_Camera_* name (always check BOTH)
  - `tag_redraw` on resolved `pb_hover_area`, not `context.area`
- **Streamline sub-toggle pattern**: restore-all (`apply_streamline(False)`) then re-apply. Master OFF = unconditional full restore. Don't pass sub-toggle values on master OFF.
- **Streamline mesh muting**: Separate from `_DISABLE_MOD_TYPES` path. Hides `mesh_obj.hide_viewport` + disables `ARMATURE` modifier. JSON list of mesh names on CharacterSlot.
- **Face local view**: `bpy.ops.view3d.localview(frame_selected=False)` with `temp_override(area=pb_area, region=region)`. Must re-ensure camera mode after. Use `obj.select_set()` not `bpy.ops.object.select_all()` (context issues from N-panel).
- **Diagnostic logger**: `DIAG_ENABLED = True` in `diag_logger.py` → logs to `logs/diag_events.jsonl`. Disable when not debugging.
- **Proximity bone override**: After DSF → torso/thigh bone, check IK-target bone proximity (0.15m threshold)
- **Axis convention**: Y = twist (along bone length), X = forward/back bend, Z = side-to-side bend
- **FACS property tiers**: `facs_ctrl_*` (bilateral), `facs_bs_*_div2` (unilateral), `facs_jnt_*` (joint-driven)

---

## Files Most Likely Needed Today

| File | Why |
|------|-----|
| `daz_bone_select.py` | Modal operator, hover detection, proximity override, PB hover, character switching, face local view refresh |
| `posebridge/core.py` | CharacterSlot, PoseBridgeSettings, streamline properties + callbacks |
| `posebridge/panel_ui.py` | Register/scan operators, character list UI, streamline mesh popup, face local view, panel view switching |
| `posebridge/streamline.py` | apply_streamline(), mesh muting logic |
| `posebridge/drawing.py` | CP drawing handler, hover highlight colors |
| `posebridge/extract_face.py` | Face setup, face camera setup |

---

## Active Research Questions

> Things we still don't know. Add when a question comes up; move answered items to TECHNICAL_REFERENCE.md Research Findings.

- [ ] **Genesis 9 rig compatibility** — same bone naming as G8? Different rotation orders?
- [ ] **Non-registered rig interaction** — does Blender's PASS_THROUGH work reliably for bone posing when a modal is running?
- [x] **Multi-character switching UX** — mesh click in 3D viewport triggers switch (implemented)

---

## Need Deeper Context?

Only read these if the task requires it:

| File | When to read |
|------|-------------|
| [CLAUDE.md](CLAUDE.md) | Architecture, principles, full file map |
| [INDEX.md](INDEX.md) | Finding a specific file |
| [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md) | Technical findings, research, rig architecture |
| [SCRATCHPAD.md](SCRATCHPAD.md) | Understanding decisions from recent sessions |

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
