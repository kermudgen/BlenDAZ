# BlenDAZ - Session Start

> **For AI Assistants**: Read this file first. It's the only file you need for most sessions.
> Update at the end of every session (3-5 min).

**Updated**: 2026-03-06 (session 14)

---

## Current State

**Active stress testing and feature iteration.** PoseBlend morph category blending implemented (FACS, expressions, visemes, body, custom DazMorphCats). Streamline mesh muting added — user-selectable popup hides high-poly meshes + disables their Armature modifiers during Streamline for dramatically faster posing. Streamline sub-toggles now live-update. Face mode isolates active character in PB viewport via Blender local view (other characters hidden in PB viewport only, main viewport unaffected). All changes committed as `2407846`.

---

## Active Sub-Projects

| Sub-project | Status | Session Start |
|-------------|--------|---------------|
| [posebridge/](posebridge/) | 🟢 Streamline mesh muting, face local view isolation, sub-toggle live updates | [SESSION_START.md](posebridge/SESSION_START.md) |
| [poseblend/](poseblend/) | 🟢 Morph category blending working, tested with Diffeomorphic morphs | [SESSION_START.md](poseblend/SESSION_START.md) |

**Read the sub-project SESSION_START.md for the one you're working on.**

---

## What We Did Last Session (2026-03-05/06, sessions 13-14)

### PoseBlend Morph Categories
- Added morph capture/blend/apply to `poseblend/poses.py` (capture_morphs, apply_morphs, blend_morphs)
- New `MORPH_CATEGORIES` in `poseblend/presets.py` mapping to Diffeomorphic attributes (DazFacs, DazExpressions, etc.)
- Custom morph support via `DazMorphCats` collection
- New Morph Categories sub-panel in `poseblend/panel_ui.py` with per-grid toggles
- Morph values stored as JSON on PoseBlendDot, blended alongside bone poses

### Streamline High-Poly Mesh Muting
- `posebridge/core.py`: `streamline_muted_meshes` JSON StringProperty on CharacterSlot + helpers
- `posebridge/streamline.py`: `mute_armature_meshes` param — hides meshes + disables Armature modifiers
- `posebridge/panel_ui.py`: Popup dialog (`BLENDAZ_OT_select_streamline_meshes`) scans child meshes with vertex counts, auto-checks high-poly, All/None buttons
- `posebridge/core.py`: Split callbacks — `_on_streamline_master_toggled` (master ON/OFF) and `_on_streamline_toggled` (sub-toggles do restore-all then re-apply). Master OFF = unconditional full restore.

### Face Mode Local View Isolation
- `posebridge/panel_ui.py`: `_enter_face_local_view()` / `_exit_face_local_view()` — uses Blender local view via `temp_override` to isolate active character in PB viewport only
- `daz_bone_select.py`: `_refresh_face_local_view()` — re-isolates when switching characters in Face mode
- Main 3D viewport stays unaffected (other characters still visible)

### Bug Fixes
- Fixed `bpy.ops.object.select_all()` context error in face local view (replaced with direct `obj.select_set()`)

---

## Next Up

**Testing (active):**
- [ ] Continue stress testing all features with multiple characters
- [ ] Test Streamline mesh muting with various character configurations
- [ ] Test PoseBlend morph blending with all category types

**Feature TODO:**
1. **Head rotation CP in face mode** — add head rotation control point for PoseBridge
2. **Finger bone selection after posing hand** — drill into child bones (low priority)
3. **PoseBlend stale modal on BlenDAZ restart** — auto-relaunch or reset is_active
4. **Rename PoseBridge/PoseBlend** — Touch / Pose / Mixer naming (big refactor, dedicated session)

**Post-v1:**
- Blender-style bone renaming support (`.L`/`.R` suffixes for Paste X-Flipped Pose etc.)

**Release:**
- [ ] Marketing assets (cover image, screenshots, demo video, product description)
- [ ] Launch channels (Superhive, Gumroad, community posts)

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
- **Streamline sub-toggle pattern**: restore-all (`apply_streamline(False)`) then re-apply with current values. Master OFF = `apply_streamline(False)` with all defaults.
- **Face local view**: Uses `bpy.ops.view3d.localview()` with `temp_override` targeting PB area. Must re-ensure camera mode after entering local view. Selection saved/restored around localview call.
- **Diagnostic logger**: `diag_logger.py` — set `DIAG_ENABLED = True` to capture structured events to `logs/diag_events.jsonl`. Disable when not debugging.

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
