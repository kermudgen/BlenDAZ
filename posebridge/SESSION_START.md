# PoseBridge - Session Start

> **For AI Assistants**: Read this file first. It's the only file you need for most sessions.
> Update this file at the end of every session (3-5 min) so the next session starts fast.

**Updated**: 2026-03-03 (session 12)

---

## Current State

**Phase**: Release preparation — packaging complete, testing next
**Status**: All core features working. Release packaging done: relative imports, logging (replaced 820 prints), LICENSE, blender_manifest.toml, version 1.0.0 unified. ZIP built (`blendaz-v1.0.0.zip`). Next: clean-slate install test.

PoseBridge interaction modes (unchanged):
- **Body/Hands**: Click-drag bone rotation (quaternion) with 4-way LMB/RMB controls
- **Face**: Click-drag morph values (FACS custom properties on armature) with same 4-way pattern
- **N-Panel sliders**: Expression presets + viseme presets as 0-1 intensity sliders

---

## What We Did Last Session (2026-03-03, session 12)

### Import & Path Cleanup
- Moved `projects/posebridge/` → `posebridge/` (direct child of BlenDAZ root)
- All shipped files now use relative imports (`from . import`, `from .. import`)
- Removed all `sys.path` manipulation and hardcoded paths

### Debug Print → Logging
- All `print()` calls replaced with `logging` calls (`log.debug()`, `log.info()`, `log.warning()`)
- Logger per module via `logging.getLogger(__name__)`

### Release Packaging
- `blender_manifest.toml` created (Blender 5.0+ min)
- `LICENSE` (GPL-3.0), version numbers unified to 1.0.0
- ZIP packaged for install testing

---

## Next Up

**Testing (immediate):**
- [ ] Clean-slate install from ZIP
- [ ] Test all PoseBridge modes (body, hands, face)
- [ ] Test multi-character registration/switching
- [ ] Test Streamline on/off

**Features:**
1. **Head rotation CP in face mode** — add head rotation control point
2. **Eye look control CP in face mode** — add eye look control point
3. **Finger bone selection after posing hand** — drill into child bones (low priority)

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
  - PB viewport identified by assigned camera name (not view_perspective)
  - `tag_redraw` on resolved `pb_hover_area`, not `context.area`
- **Diagnostic logger**: `DIAG_ENABLED = True` in `diag_logger.py` → logs to `logs/diag_events.jsonl`. Disable when not debugging.
- **Proximity bone override**: After DSF → torso/thigh bone, check IK-target bone proximity (0.15m threshold)
- **Axis convention**: Y = twist (along bone length), X = forward/back bend, Z = side-to-side bend
- **FACS property tiers**: `facs_ctrl_*` (bilateral), `facs_bs_*_div2` (unilateral), `facs_jnt_*` (joint-driven)
- **Locked drag state** — `_drag_from_posebridge`, `_drag_control_point_id`, `_drag_bone_names` set at mouse-down
- **Native translate pass-through** — When `_use_native_translate` is True, gate at top passes ALL events

---

## Files Most Likely Needed Today

| File | Why |
|------|-----|
| `daz_bone_select.py` | Modal operator, hover detection, proximity override, PB hover, character switching |
| `diag_logger.py` | Diagnostic logging — enable/disable, add new event types |
| `posebridge/core.py` | CharacterSlot, PoseBridgeSettings, find_character_mesh |
| `posebridge/panel_ui.py` | Register/scan operators, character list UI, per-char cameras |
| `posebridge/drawing.py` | CP drawing handler, hover highlight colors |
| `posebridge/outline_generator_lineart.py` | Outline generation, body camera setup |
| `posebridge/extract_hands.py` | Hand extraction, hand camera setup |
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
| [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md) | Technical findings, research, rig architecture (bone nodes, rig detection, rotation math) |
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
