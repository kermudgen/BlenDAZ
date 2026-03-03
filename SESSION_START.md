# BlenDAZ - Session Start

> **For AI Assistants**: Read this file first. It's the only file you need for most sessions.
> Update at the end of every session (3-5 min).

**Updated**: 2026-03-03 (session 12)

---

## Current State

**Release preparation — packaging complete, testing next.** Completed all pre-release code cleanup: imports converted to relative, debug prints replaced with logging, LICENSE + blender_manifest.toml created, version numbers unified to 1.0.0. ZIP packaged as `blendaz-v1.0.0.zip` (41 shipped files). Next: clean-slate install test on second machine.

---

## Active Sub-Projects

| Sub-project | Status | Session Start |
|-------------|--------|---------------|
| [posebridge/](posebridge/) | 🟢 Multi-character verified, PB hover + switching working | [SESSION_START.md](posebridge/SESSION_START.md) |
| [poseblend/](poseblend/) | 🔴 Pre-first-test | [SESSION_START.md](poseblend/SESSION_START.md) |

**Read the sub-project SESSION_START.md for the one you're working on.**

---

## What We Did Last Session (2026-03-03, session 12)

### Import & Path Cleanup
- Moved `projects/posebridge/` → `posebridge/` and `projects/poseblend/` → `poseblend/` (direct children of BlenDAZ root)
- Converted all shipped files to relative imports (`from . import`, `from .. import`)
- Removed all `sys.path` manipulation and hardcoded paths from shipped files
- Dev entry points (`register_only.py`, `setup_all.py`) use `BLENDAZ_PARENT = r"D:\Dev"` + `from BlenDAZ import ...`
- Created `__init__.py` addon entry point with root logging config

### Debug Print → Logging
- Replaced 820 `print()` calls across all 40 shipped files with `logging` calls
- Root logger `"BlenDAZ"` in `__init__.py`, child loggers via `logging.getLogger(__name__)`
- WARNING level by default (silent), configurable to DEBUG for verbose output
- Cleaned up 17 files with unused logging imports

### Release Packaging
- Created `LICENSE` (GPL-3.0 full text)
- Created `blender_manifest.toml` (schema 1.0.0, id=blendaz, Blender 5.0+ min)
- Unified all version numbers to `(1, 0, 0)` / `"1.0.0"`
- Built `blendaz-v1.0.0.zip` — 41 files, correct `blendaz/` folder structure

### Files Created
- `__init__.py` — addon entry point
- `blender_manifest.toml` — Blender extension manifest
- `LICENSE` — GPL-3.0 full text
- `blendaz-v1.0.0.zip` — release package

### Files Modified (imports + logging)
- All shipped .py files — see session 12 details in SCRATCHPAD

---

## Next Up

**Testing (immediate):**
- [ ] Clean-slate install test from ZIP on work machine (Blender 5.0+)
- [ ] Test with Genesis 8 F/M, 8.1 F/M
- [ ] Test multi-character registration/switching
- [ ] Test all PoseBridge modes (body, hands, face)
- [ ] Test Streamline on/off
- [ ] Test IK on all limbs
- [ ] Verify clean uninstall

**Release checklist (remaining):**
- [ ] Marketing assets (cover image, screenshots, demo video, product description)
- [ ] Launch channels (Superhive, Gumroad, community posts)
- [ ] License key / activation system (lite vs full split)

**Feature TODO:**
1. **Head rotation CP in face mode** — add head rotation control point for PoseBridge
2. **Eye look control CP in face mode** — add eye look control point for PoseBridge
3. **Finger bone selection after posing hand** — drill into child bones after proximity override (low priority)

**Other:**
- [ ] BlenDAZ toggle button should stop modal in ALL viewports
- [ ] Collar snapping during arm IK drag (pre-existing analytical solver issue)

---

## Don't Forget

- **Package structure**: `blendaz/` top-level folder inside ZIP, matching manifest `id`
- **Imports**: All shipped files use relative imports. Dev scripts use `from BlenDAZ import ...`
- **Logging**: `logging.getLogger(__name__)` in each module. Root logger "BlenDAZ" at WARNING level.
- `daz_shared_utils.py` changes → **full Blender restart** (importlib.reload doesn't work)
- `posebridge/core.py` changes (PropertyGroup) → **full Blender restart**
- `daz_bone_select.py` changes → reload script or restart
- **Blender objects don't support arbitrary Python attributes** — use `obj["foo"]` (custom properties) or return values instead of `obj._foo`
- **User's preferred workflow**: `register_only.py` → Scan → Register → Activate (NOT `setup_all.py` as entry point)
- **Commit discipline**: wait until things work before committing — don't commit every small fix
- **Multi-viewport architecture** (single modal, all viewports):
  - `_resolve_event_viewport(context, event)` — find viewport under mouse (canonical helper)
  - `_find_pb_viewport(context)` — find PB viewport (assigned PB_Camera_* name)
  - `_find_main_viewport(context)` — find non-PB viewport
  - `_mode_set_safe(context, mode)` — route mode_set through main viewport (protects PB camera)
  - `_set_header(context, text)` — broadcasts to ALL VIEW_3D areas
  - **Never use `context.area`/`context.region` directly** for raycasts or UI checks — always resolve via `_resolve_event_viewport()`
  - **Never call `bpy.ops.object.mode_set()` directly** — use `_mode_set_safe()` to protect PB viewport
- **Per-character caches** (class-level dicts on `VIEW3D_OT_daz_bone_select`, persist across modal restarts):
  - `_base_body_meshes = {}` — `{armature_name: mesh_obj}` resolves through clothing
  - `_face_group_mgrs = {}` — `{armature_name: FaceGroupManager}` DSF zone detection
- **RAYCAST 2 pattern**: Scene raycast → armature modifier lookup → raycast cached body mesh → priority within 1.0m threshold
- **Proximity bone override**: After DSF resolution, if result is torso/thigh bone, check if IK-target bone's posed position is within 0.15m of hit location
- **Diagnostic logger**: `diag_logger.py` — set `DIAG_ENABLED = True` to capture structured events to `logs/diag_events.jsonl`. Disable when not debugging.
- **Analytical IK tests**: `tests/test_analytical_leg.py` (57), `tests/test_analytical_arm.py` (62), `tests/test_hip_pin_ik.py` (30), `tests/test_pin_system.py` (30)

---

## Need Deeper Context?

| File | When to read |
|------|-------------|
| [CLAUDE.md](CLAUDE.md) | Design philosophy, issue status, conventions |
| [docs/INDEX.md](docs/INDEX.md) | Finding a specific file |
| [docs/TODO.md](docs/TODO.md) | Full task backlog |
| [docs/TECHNICAL_REFERENCE.md](docs/TECHNICAL_REFERENCE.md) | IK research, DAZ rig architecture, rotation math |
| [docs/SCRATCHPAD.md](docs/SCRATCHPAD.md) | History of decisions |

---

## How to Update This File

At the end of each session, update:
1. **Updated** date
2. **Current State** — 2-3 sentences on where things stand
3. **Active Sub-Projects** — update status emoji if phase changes
4. **What We Did Last Session** — replace with this session's work
5. **Next Up** — sync with active sub-project TODOs
6. **Don't Forget** — add new gotchas, prune stale ones
