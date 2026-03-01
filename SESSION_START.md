# BlenDAZ - Session Start

> **For AI Assistants**: Read this file first. It's the only file you need for most sessions.
> Update at the end of every session (3-5 min).

**Updated**: 2026-02-28 (session 9)

---

## Current State

**Multi-character Phase 4 — multi-viewport modal architecture implemented, ready for testing.** Major refactor: the single modal operator now works seamlessly across ALL open 3D viewports. Viewport resolution infrastructure (`_resolve_event_viewport`, `_find_pb_viewport`, `_find_main_viewport`) consolidates the repeated "find viewport under mouse" pattern. PB viewport camera swaps correctly on character switch. `mode_set` is isolated to the main viewport via `_mode_set_safe()`. Camera leak from N-panel click is prevented. Header text and tag_redraw broadcast to all viewports.

---

## Active Sub-Projects

| Sub-project | Status | Session Start |
|-------------|--------|---------------|
| [projects/posebridge/](projects/posebridge/) | 🟢 Multi-character Phase 4 — multi-viewport testing | [SESSION_START.md](projects/posebridge/SESSION_START.md) |
| [projects/poseblend/](projects/poseblend/) | 🔴 Pre-first-test | [SESSION_START.md](projects/poseblend/SESSION_START.md) |

**Read the sub-project SESSION_START.md for the one you're working on.**

---

## What We Did Last Session (2026-02-28, session 9)

**Multi-viewport modal architecture — seamless interaction across all 3D viewports:**

### New Helpers (daz_bone_select.py)
- **`_resolve_event_viewport(context, event)`** — canonical helper to find the VIEW_3D area/region/rv3d/space under the mouse. Replaces 3 duplicate viewport-scan patterns in `_crossviewport_raycast`, `_get_region_rv3d`, and `check_posebridge_hover`.
- **`_find_pb_viewport(context)`** — finds the PB viewport (CAMERA mode + PB_Camera_* name). Used by character switch and mode_set isolation.
- **`_find_main_viewport(context)`** — finds the non-PB viewport. Used to route mode_set safely.
- **`_mode_set_safe(context, mode)`** — wraps `bpy.ops.object.mode_set()` with a `temp_override` routed through the main viewport, protecting PB viewport camera/perspective state. Replaces ALL 6 direct mode_set call sites.

### Bug Fixes
- **PB viewport goes black on character switch** — step 3b now uses `_find_pb_viewport()` to swap the PB camera to the new character's hands/face camera.
- **mode_set corrupts PB viewport** — all mode_set calls routed through main viewport via `_mode_set_safe()`.
- **Camera leak to main viewport** — `set_panel_view` in `panel_ui.py` now targets the PB viewport specifically (via new `_find_pb_viewport()` helper in panel_ui.py), not `context.space_data`.
- **Header text only in one viewport** — `_set_header()` now broadcasts to ALL VIEW_3D areas. `clear_hover()` tag_redraw also broadcasts.

### Cross-Viewport Interaction
- **LEFTMOUSE handler** — resolves viewport at top of handler, uses resolved area/region/rv3d for UI check, gizmo proximity, raycasts, double-click detection.
- **check_hover() non-PB path** — uses `_resolve_event_viewport()` for UI region check, gizmo check, and raycast. Hover works in any viewport.
- **Click-through mode** — single-click raycast on non-registered objects uses resolved viewport.
- **Double-click tracking** — uses window-relative coords (stable across viewports).

### Files Modified
- `daz_bone_select.py` — 4 new helpers, refactored 3 existing methods, updated all mode_set calls, LEFTMOUSE handler, check_hover, header/redraw broadcasting
- `projects/posebridge/panel_ui.py` — new `_find_pb_viewport()` module helper, `set_panel_view` targets PB viewport, redraws both areas
- `projects/posebridge/drawing.py` — unchanged (camera check still works correctly with the new architecture)

---

## Next Up

**Test multi-viewport architecture:**
1. Register two characters, click BlenDAZ in right pane
2. Click Hands in left N-panel — verify CPs appear in left only, main viewport stays perspective
3. Click other character in right viewport — verify left viewport switches to new character's hands
4. Switch Face/Body — verify seamless transitions
5. Double-click non-registered object — verify no viewport corruption

**Remaining multi-character issues:**
- [ ] BlenDAZ toggle button should stop modal in ALL viewports
- [ ] Collar snapping during arm IK drag (pre-existing analytical solver issue)

**Deferred TODOs:**
- Camera ortho scale tweaks: Body=5, Hands=0.7, Face=0.525
- N-Panel reorganization (agreed structure in TODO.md)
- PoseBlend first Blender test

---

## Don't Forget

- `daz_shared_utils.py` changes → **full Blender restart** (importlib.reload doesn't work)
- `posebridge/core.py` changes (PropertyGroup) → **full Blender restart**
- `daz_bone_select.py` changes → reload script or restart
- **Blender objects don't support arbitrary Python attributes** — use `obj["foo"]` (custom properties) or return values instead of `obj._foo`
- **User's preferred workflow**: `register_only.py` → Scan → Register → Activate (NOT `setup_all.py` as entry point)
- **Commit discipline**: wait until things work before committing — don't commit every small fix
- **Multi-viewport architecture** (single modal, all viewports):
  - `_resolve_event_viewport(context, event)` — find viewport under mouse (canonical helper)
  - `_find_pb_viewport(context)` — find PB viewport (CAMERA mode + PB_Camera_*)
  - `_find_main_viewport(context)` — find non-PB viewport
  - `_mode_set_safe(context, mode)` — route mode_set through main viewport (protects PB camera)
  - `_set_header(context, text)` — broadcasts to ALL VIEW_3D areas
  - **Never use `context.area`/`context.region` directly** for raycasts or UI checks — always resolve via `_resolve_event_viewport()` since modal's context is pinned to invoking viewport
  - **Never call `bpy.ops.object.mode_set()` directly** — use `_mode_set_safe()` to protect PB viewport
- **Per-character caches** (class-level dicts on `VIEW3D_OT_daz_bone_select`, persist across modal restarts):
  - `_base_body_meshes = {}` — `{armature_name: mesh_obj}` resolves through clothing
  - `_face_group_mgrs = {}` — `{armature_name: FaceGroupManager}` DSF zone detection
  - Both populated at invoke for ALL registered characters
- **RAYCAST 2 pattern**: Scene raycast → armature modifier lookup → raycast cached body mesh → priority within 1.0m threshold
- **`_just_selected_armature`** flag — when True, modal passes through ALL events except clicks on registered DAZ characters
- **`_live_instance`** on `VIEW3D_OT_daz_bone_select` — set in invoke(), cleared in finish()
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
