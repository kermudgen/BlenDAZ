# PoseBlend - Development Scratchpad

## Purpose
This file tracks ongoing development work, experiments, bugs, and feature progress. It's a living document that captures what we're working on, what we've tried, and what we've learned.

**Note**: When this file reaches ~300-500 lines or ~50-75KB, archive to `scratchpad_archive/SCRATCHPAD_YYYY-MM.md` and start fresh.

## Archive History
*(none yet)*

---

## Session: 2026-02-22 — Initial Code Review

### Active Work
- Documentation setup; preparing for first Blender test run

### What Was Done
- Created CLAUDE.md, INDEX.md, SCRATCHPAD.md, TODO.md based on PROJECT_SETUP_GUIDE.md
- Full code review of all 11 source files

### Bugs Found in Code Review

#### Bug 1: CRASH — `default_mask_mode` / `default_mask_preset` on PoseBlendGrid
**Priority**: High (will crash on first dot creation)
**Status**: Open

**Root cause**: `PoseBlendGrid` in `core.py` only defines `bone_mask_mode` and `bone_mask_preset`. Two callers reference the non-existent `default_mask_mode` / `default_mask_preset`:

- `interaction.py:324-325` in `create_dot_at_cursor()`:
  ```python
  mask_mode=grid.default_mask_mode,
  mask_preset=grid.default_mask_preset
  ```
- `import_export.py:43-44` in `export_grid_to_dict()`:
  ```python
  "default_mask_mode": grid.default_mask_mode,
  "default_mask_preset": grid.default_mask_preset,
  ```

**Fix**: Replace both `default_mask_mode` → `bone_mask_mode` and `default_mask_preset` → `bone_mask_preset`. These are the same properties — the naming was inconsistent between design and implementation.

#### Bug 2: VISUAL — Dot labels not rendered
**Priority**: Medium (functional, just missing visual polish)
**Status**: Open

`drawing.py:292` `draw_label()` is a `pass` placeholder:
```python
@staticmethod
def draw_label(position, text, offset):
    # TODO: Implement text drawing with blf module
    pass
```

**Fix**: Implement with `blf`:
```python
import blf
font_id = 0
blf.position(font_id, position[0] + offset + 2, position[1], 0)
blf.size(font_id, 11)
blf.color(font_id, 1.0, 1.0, 1.0, 0.8)
blf.draw(font_id, text)
```
Note: `blf` calls must be made within a valid GPU draw context (inside the draw handler callback — which `draw_label` is called from, so this is fine).

#### Bug 3: MINOR — `POSEBLEND_OT_add_dot` ignores grid bone mask
**Priority**: Low
**Status**: Open

`panel_ui.py` `POSEBLEND_OT_add_dot.execute()` calls `grid.add_dot()` without passing mask_mode/mask_preset, so dots added via the N-panel always get defaults (`mask_mode='ALL'`, `mask_preset='HEAD'`) instead of inheriting the grid's configured mask.

**Fix**: Pass `mask_mode=grid.bone_mask_mode, mask_preset=grid.bone_mask_preset` to `grid.add_dot()` in the operator.

#### Bug 4: MINOR — `POSEBLEND_OT_edit_dot_mask` is a stub
**Priority**: Low
**Status**: Open

`interaction.py:475` — the context menu "Edit Bone Mask" operator just reports "not yet implemented".

### Architecture Notes
- The design is clean and well-separated. Drawing, blending, poses, and grid math are all independent modules.
- `blending.py` and `poses.py` both have `blend_quaternions` implementations — they're slightly different (poses.py doesn't sort by weight). Could unify later but not urgent.
- `interaction.py` uses instance variables (`self._cursor_pos`, `self._state`, etc.) on a modal operator — note these are re-initialized in `invoke()` but class-level type annotations are set as class vars. This is fine for Blender modal operators.
- `grid_screen_position` with `'RIGHT'` as default means the grid overlay appears on the right side of viewport by default — reasonable starting position alongside the character.
- The `is_locked` property on grids prevents dot editing during animation mode — nice design for preventing accidental pose changes.

---

## Quick Reference

### Useful Commands
```python
# Register PoseBlend manually in Blender Python console
import sys
sys.path.insert(0, r"D:\Dev\BlenDAZ\projects")
import poseblend
poseblend.register()

# Unregister
poseblend.unregister()
```

### Important Patterns
- Quaternion storage: `[w, x, y, z]` list in JSON, reconstruct as `Quaternion((q[0], q[1], q[2], q[3]))`
- Grid region dict: `{'x': float, 'y': float, 'width': float, 'height': float}` in pixels
- Normalized grid coords: `(0.0, 0.0)` = bottom-left, `(1.0, 1.0)` = top-right
- IDW weights always normalized to sum 1.0; direct hit (distance < 0.001) returns `[(dot, 1.0)]` immediately
- `bone_mask=None` in `capture_pose()` / `apply_pose()` means all bones (no filtering)
