# PoseBlend - Session Start

> **For AI Assistants**: Read this file first. It's the only file you need for most sessions.
> Update at the end of every session (3-5 min).

**Updated**: 2026-02-22

---

## ⚡ Current State

**Phase**: Phase 1 complete, active feature development
**Status**: All core features working + extrapolation + "Update with Current Pose" context menu. Tested with Diffeomorphic Genesis 8 character ("Fey", 185 bones).

---

## What We Did Last Session

- Fixed crash bugs: `default_mask_mode` → `bone_mask_mode` in `interaction.py`, `import_export.py`
- Fixed `add_dot()` crash with `None` mask_preset
- Added `BOTTOM_LEFT` grid position (default)
- Created `test_poseblend.py` — automated + manual test setup
- First Blender test: all core features working (blending, dot creation, Shift+click, ESC restore)
- Added "Update with Current Pose" to right-click context menu (`interaction.py`)
- Implemented **pose extrapolation**: drag past a dot to amplify its pose
  - `extrapolation_max` setting in core.py (0.0-2.0, default off)
  - Spatial algorithm in `blending.py` `_apply_extrapolation()` — detects cursor past dominant dot
  - Custom `slerp_unclamped()` in `poses.py` — Blender's slerp clamps t to [0,1], ours doesn't
  - UI slider in Settings > Blending > Extrapolation

---

## Next Up

1. **Dot labels** — `drawing.py` `draw_label()` is still a `pass` stub. Implement with `blf` module.
2. **More pose variety testing** — test with 4+ dots, different body regions, preset masks
3. **Phase 2 testing** — Shift+drag dot movement, right-click context menu, delete dot (X key)
4. **Grid lock mode** — verify locked grid prevents dot creation/deletion/movement
5. **Export/import file round-trip** — test actual JSON file save and load (not just dict)

---

## Don't Forget

- **No full restart needed** — `importlib.reload()` works fine
- **Quaternion storage**: `[w, x, y, z]` lists. On retrieval: `Quaternion((q[0], q[1], q[2], q[3]))`
- **Grid positions**: normalized 0–1, origin bottom-left
- **Bone mask hierarchy**: Dot mask → inherits from Grid mask if `USE_GRID`; overrides if `ALL`/`PRESET`/`CUSTOM`
- **Never use Euler mode** — quaternion only throughout
- **Grid position default is BOTTOM_LEFT** — avoids N-panel overlap
- **`add_dot()` guards `None` mask_preset** — import can pass `None` when mask_mode isn't PRESET
- **Blender slerp clamps t** — use `slerp_unclamped()` from `poses.py` for extrapolation
- **Test script**: `test_poseblend.py` — run in Blender Text Editor with armature selected

---

## Files Most Likely Needed Today

| File | Why |
|------|-----|
| `drawing.py` | `draw_label()` — dot name rendering (next priority) |
| `interaction.py` | Modal operator, context menu |
| `blending.py` | IDW weights + extrapolation |
| `poses.py` | `slerp_unclamped()`, pose capture/apply |
| `test_poseblend.py` | Test script |

---

## Need Deeper Context?

| File | When to read |
|------|-------------|
| [CLAUDE.md](CLAUDE.md) | Architecture, conventions, full known bugs list |
| [INDEX.md](INDEX.md) | Finding a specific file or function |
| [POSEBLEND_DESIGN.md](POSEBLEND_DESIGN.md) | Algorithm specs, IDW math, open design questions |
| [../../CLAUDE.md](../../CLAUDE.md) | Parent BlenDAZ project context and issue status |

---

## How to Update This File

At the end of each session, update:
1. **Updated** date
2. **Current State** — phase, status, what's happening
3. **What We Did Last Session** — replace with this session's work
4. **Next Up** — sync with TODO.md (create one when active dev starts)
5. **Don't Forget** — add new gotchas, prune stale ones
6. **Files Most Likely Needed Today** — update to reflect what's active
