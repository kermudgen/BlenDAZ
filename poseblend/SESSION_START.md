# PoseBlend - Session Start

> **For AI Assistants**: Read this file first. It's the only file you need for most sessions.
> Update at the end of every session (3-5 min).

**Updated**: 2026-03-06

---

## Current State

**Phase**: Morph blending implemented, active testing
**Status**: All core features working. Morph category support added — PoseBlend dots now capture and blend Diffeomorphic morph values (FACS, expressions, visemes, body, custom DazMorphCats) alongside bone poses. Non-blocking modal, dot-space zoom/pan, extrapolation, RMB context menus, grid management. Tested with Diffeomorphic Genesis 8 characters.

---

## What We Did Last Session (2026-03-05)

### Morph Category Blending
- `presets.py`: `MORPH_CATEGORIES` OrderedDict mapping internal keys to Diffeomorphic RNA attributes (`DazFacs`, `DazExpressions`, etc.). Helper functions: `_get_daz_rna()`, `_get_morph_pg()`, `get_morph_names_for_categories()`, `get_available_morph_categories()`, `get_available_custom_morph_cats()`
- `core.py`: `morph_values` JSON StringProperty on `PoseBlendDot` with `get_morphs_dict()`/`set_morphs_dict()`. Per-grid morph category BoolProperties (`morph_facs`, `morph_expressions`, etc.) + `morph_custom_cats` JSON for DazMorphCats
- `poses.py`: `capture_morphs()`, `apply_morphs()`, `blend_morphs()` — weighted blending of morph property values
- `interaction.py`: Morphs wired into all paths — cursor drag blend, dot snap, dot creation, dot update, dot duplicate
- `panel_ui.py`: New `VIEW3D_PT_poseblend_morphs` sub-panel with standard category checkboxes and custom DazMorphCats toggle operator

---

## Next Up

1. **Bone mask testing** — verify preset masks (HEAD, UPPER_BODY, ARMS, etc.) select correct DAZ bones
2. **Multi-grid workflow** — multiple grids with different body regions, switching between them
3. **Dot labels** — `drawing.py` `draw_label()` is still a `pass` stub. Implement with `blf` module.
4. **Lock mode testing** — verify locked grid prevents dot creation/deletion/movement but allows blending
5. **Auto-keyframe testing** — verify keyframes land on correct frame for correct bones
6. **Import/export verification** — test JSON file save and load round-trip (now includes morph data)
7. **Edit dot mask operator** — `interaction.py` stub, needs real UI

---

## Don't Forget

- **Non-blocking modal** — events outside grid get PASS_THROUGH; mid-interaction (PREVIEWING, DRAGGING_DOT, PANNING) continues regardless of cursor position
- **Zoom transform**: forward `view = (pos - pan_center) * zoom + 0.5`, inverse `pos = (view - 0.5) / zoom + pan_center`
- **Dots live in 0–1 space** — zoom/pan changes what's visible, not where dots are stored
- **Quaternion storage**: `[w, x, y, z]` lists. On retrieval: `Quaternion((q[0], q[1], q[2], q[3]))`
- **Morph storage**: JSON dict `{"morph_prop_name": float_value}` on PoseBlendDot.morph_values
- **Morph blending**: Weighted sum — `result[name] += value * weight` for each dot
- **Diffeomorphic RNA access**: `_get_daz_rna(armature)` checks `armature.daz_importer` first, falls back to armature direct attrs
- **Custom morph cats**: `DazMorphCats` collection on daz RNA, each has `.morphs` sub-collection
- **Bone mask hierarchy**: Dot mask → inherits from Grid mask if `USE_GRID`; overrides if `ALL`/`PRESET`/`CUSTOM`
- **Never use Euler mode** — quaternion only throughout
- **Grid position default is BOTTOM_LEFT** — avoids N-panel overlap
- **Blender slerp clamps t** — use `slerp_unclamped()` from `poses.py` for extrapolation
- **Extrapolation default is 1.0** — allows pushing past stored poses by default
- **Context menus**: RMB on dot → dot menu, RMB on empty → grid menu
- **Viewport isolation**: `_target_area_ptr` in `PoseBlendDrawHandler` — set on activate, cleared on deactivate. Grid only draws in that viewport.
- **PoseBridge coexistence**: Both modules share the DAZ N-panel tab. Non-blocking modal passes events through to PoseBridge outside the grid square.

---

## Files Most Likely Needed Today

| File | Why |
|------|-----|
| `drawing.py` | `draw_label()` stub, dot rendering, grid lines |
| `interaction.py` | Modal operator, context menus, all operators, morph capture/apply paths |
| `core.py` | PropertyGroups, grid_zoom, grid_pan, morph_values on dots |
| `poses.py` | Bone masks, pose capture/apply, slerp_unclamped, morph capture/apply/blend |
| `presets.py` | Bone mask presets, MORPH_CATEGORIES, Diffeomorphic RNA helpers |
| `panel_ui.py` | Grid management UI, morph categories sub-panel |

---

## Need Deeper Context?

| File | When to read |
|------|-------------|
| [CLAUDE.md](CLAUDE.md) | Architecture, conventions, full known bugs list |
| [INDEX.md](INDEX.md) | Finding a specific file or function |
| [POSEBLEND_DESIGN.md](POSEBLEND_DESIGN.md) | Algorithm specs, IDW math, open design questions |
| [../CLAUDE.md](../CLAUDE.md) | Parent BlenDAZ project context and issue status |

---

## How to Update This File

At the end of each session, update:
1. **Updated** date
2. **Current State** — phase, status, what's happening
3. **What We Did Last Session** — replace with this session's work
4. **Next Up** — sync with TODO.md (create one when active dev starts)
5. **Don't Forget** — add new gotchas, prune stale ones
6. **Files Most Likely Needed Today** — update to reflect what's active
