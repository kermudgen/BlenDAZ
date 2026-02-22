# PoseBlend - TODO

**Last Updated**: 2026-02-22

Track current development tasks, features, and bugs.

---

## Current Work

### First Blender Test — Fix Crash Bugs
**Description**: The addon has never been run in Blender. Fix known crash bugs before first test.

#### Immediate Tasks
- [ ] Fix `default_mask_mode` crash in `interaction.py:324` (→ `grid.bone_mask_mode`)
- [ ] Fix `default_mask_mode` crash in `import_export.py:43` (→ `grid.bone_mask_mode`)
- [ ] Register addon in Blender and verify no registration errors
- [ ] Activate PoseBlend with a Genesis 8 armature selected
- [ ] Create a test grid and verify dot creation works
- [ ] Verify blend preview applies rotations during drag
- [ ] Verify export/import round-trip (grid → JSON → import → same data)

---

## Bug Backlog

### High Priority
- [ ] **CRASH: `default_mask_mode` / `default_mask_preset`** — `interaction.py:324`, `import_export.py:43` reference properties that don't exist on `PoseBlendGrid`. Fix: rename to `bone_mask_mode` / `bone_mask_preset`. *(See SCRATCHPAD for details)*

### Medium Priority
- [ ] **VISUAL: Dot labels not rendered** — `drawing.py:292` `draw_label()` is `pass`. Implement with `blf` module. *(See SCRATCHPAD for code snippet)*

### Low Priority
- [ ] **N-panel add dot ignores grid mask** — `POSEBLEND_OT_add_dot` doesn't pass grid's `bone_mask_mode` to new dot
- [ ] **Edit Bone Mask stub** — `POSEBLEND_OT_edit_dot_mask` just reports "not yet implemented"

---

## Recently Completed

*(none yet — project just scaffolded)*

---

## Backlog - High Priority

### Phase 1: Core Infrastructure (mostly done, needs testing)
- [ ] Verify PropertyGroup registration and property access in Blender
- [ ] Verify draw handler activates and draws background/grid lines/dots
- [ ] Verify modal operator starts and receives mouse events
- [ ] Verify `calculate_grid_region()` matches between drawing and interaction (hit area = drawn area)

### Phase 2: Pose Capture & Storage (written, needs testing)
- [ ] Test `capture_pose()` on a Genesis 8 armature — verify quaternion capture for all bones
- [ ] Test `apply_pose()` restores pose correctly
- [ ] Verify `USE_GRID` mask inheritance chain works end-to-end

### Phase 3: Blending System (written, needs testing)
- [ ] Test IDW weights with 2 dots — cursor at midpoint should give 50/50
- [ ] Test IDW weights with cursor directly on a dot — should give 100%
- [ ] Test all 4 falloff modes visually
- [ ] Test `blend_radius` cutoff — dots outside radius should receive 0 weight
- [ ] Verify SLERP produces smooth interpolation (no flipping)

### Phase 4: Interaction (written, needs testing)
- [ ] Test Shift+click to create dot from current pose
- [ ] Test click on dot → applies pose directly
- [ ] Test click+drag on empty grid → blend preview
- [ ] Test Shift+drag dot → moves dot position
- [ ] Test Snap to Grid during dot creation and drag
- [ ] Test ESC during modal → restores initial pose
- [ ] Test right-click context menu → rename / duplicate / delete

---

## Future Features

### Phase 5: UI Polish
- [ ] Dot labels via `blf` (unblocks visual identification of dots)
- [ ] Tooltip on hover showing dot name, mask info, position
- [ ] Control point size scaling with viewport zoom
- [ ] Color coding dots by mask type (auto-assign from `presets.get_dot_color()` on create)
- [ ] Influence radius circle around cursor (optional visual setting)

### Phase 6: Import/Export (written, needs testing)
- [ ] Test export → JSON round-trip with bone remapping
- [ ] Test import with `genesis8_to_rigify` remap preset
- [ ] Verify format version field for future migration

### Phase 7: Advanced Features
- [ ] Undo/redo support for pose blends (Blender undo push on finalize)
- [ ] Auto-keyframe on drag release (property exists, needs wiring)
- [ ] Multiple grid tabs / category switching
- [ ] Thumbnails for dots (base64 preview image stored in `PoseBlendDot.thumbnail`)
- [ ] Morph target support (DAZ `facs_*` custom properties alongside bone rotations)
- [ ] Expression presets grid (link to PoseBridge face FACS system)

### Interaction Improvements
- [ ] Double-click dot → rename in place
- [ ] Middle-drag grid → pan
- [ ] Scroll wheel → zoom grid
- [ ] Symmetry mode: pose left side, mirror to right

### Rig Support
- [ ] Verify Genesis 8.1 (same bone names as G8? Different rotation orders?)
- [ ] Rigify rig support via bone remapping presets

---

## Known Issues

### Medium Priority
- [ ] `blend_quaternions` exists in both `blending.py` (`blend_quaternions_weighted`) and `poses.py` (`blend_quaternions`) — slight divergence. Unify to single implementation eventually.
- [ ] `POSEBLEND_OT_add_dot` in panel_ui.py places dots at `(0.5, 0.5)` always — user must manually move them. Better UX: place at last cursor position.

### Low Priority
- [ ] `viewport_setup.py` `position_camera_for_grid()` ignores armature parameter (TODO comment) — camera doesn't auto-frame character
- [ ] `viewport_setup.py` `setup_split_view()` is a `pass` stub
- [ ] `POSEBLEND_OT_edit_dot_mask` doesn't have a UI — custom mask bones can't be set from the UI

---

## Technical Debt

### Code Organization
- [ ] `blend_quaternions` duplicated in `blending.py` and `poses.py` — consolidate
- [ ] `drawing.py` `calculate_grid_region()` is a staticmethod called from outside the class — could be a standalone function in `grid.py`
- [ ] `interaction.py` re-calculates grid region on every mouse move (via `calculate_grid_region` in `update_cursor`) — consider caching and only invalidating on region resize events

### Testing
- [ ] No automated tests — all testing is manual in Blender
- [ ] Create a test grid .json file with known dot positions for regression testing

---

## Ideas to Consider

### Experimental
- [ ] Drive dot positions from animation curves (puppeteer-style keyframe scrubbing)
- [ ] Live blend weight visualization (show percentage labels on dots during drag)
- [ ] Cluster mode: automatically group nearby poses and blend within clusters

### Research Needed
- [ ] How does DAZ Puppeteer handle the "no dots nearby" case — rest pose blend or nearest dot clamp?
- [ ] Can we share dot grids between multiple characters (same rig type)?
- [ ] Performance: how many dots before IDW gets slow? Should we spatial-index at > N dots?

---

## Notes

**How to use this file:**
1. Check "Current Work" for active development priorities
2. Move items from Backlog to Current Work as you begin them
3. Mark items complete and move to "Recently Completed"
4. Archive old completed items to SCRATCHPAD.md periodically
5. Add new ideas to appropriate sections
6. Review and groom this file weekly

**Phase reference** (from POSEBLEND_DESIGN.md):
- Phase 1: Core infrastructure (draw handler, GPU grid)
- Phase 2: Pose capture & storage
- Phase 3: Blending system (IDW + SLERP)
- Phase 4: Interaction (modal operator)
- Phase 5: UI polish
- Phase 6: Import/Export
- Phase 7: Advanced features (undo, thumbnails, morphs)
