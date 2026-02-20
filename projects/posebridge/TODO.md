# PoseBridge - TODO

**Last Updated**: 2026-02-19

Track current development tasks, future features, and improvements needed.

---

## Current Work

### Group Node Hookup
**Description**: Finish connecting all 8 group nodes to their per-group axis mappings so they respond correctly to mouse input.

#### Immediate Tasks
- [x] Store `_rotation_group_id` at drag start
- [x] Replace hardcoded axes in `update_multi_bone_rotation()` with per-group if/elif
- [x] Add inversion flags per group
- [x] Sync neck_group controls dict in daz_shared_utils.py
- [ ] Restart Blender and test all 8 group nodes
- [ ] Verify twist bone filtering works correctly for arm/leg groups
- [ ] Test bilateral groups (shoulders_group, legs_group) for correct behavior
- [ ] Determine if rArm_group / rLeg_group need L/R mirroring inversion

---

## Recently Completed (Feb 2026)

- [x] **Per-group axis routing** - update_multi_bone_rotation() now uses _rotation_group_id to pick axes per group
- [x] **Project documentation setup** - CLAUDE.md, INDEX.md, TODO.md, SCRATCHPAD.md created
- [x] **Toe nodes** - lToe, rToe control points at tail position
- [x] **Hip node** - hip control at mid-bone position
- [x] **Base node** - special node that selects armature in object mode
- [x] **Tooltips** - 1-second hover delay showing control info
- [x] **Thigh Y-lock** - swing-twist decomposition keeps ThighBend Y at 0
- [x] **Shoulder debugging** - fixed delta zeroing, swapped axes, twist targeting
- [x] **PowerPose 4-way controls** - LMB/RMB x horiz/vert per bone
- [x] **Control mapping adjustments** - inversions for head/neck/torso/collar/shoulder
- [x] **Rotation constraint enforcement** - depsgraph readback bakes constraints in real-time
- [x] **Mesh mannequin** - gray material on mesh copy as silhouette backdrop
- [x] **Phase 1 MVP steps 1-9** - outline generation through rotation testing

---

## Backlog - High Priority

### Phase 1 Completion
- [ ] Step 10: Test cancellation (ESC key during rotation)
- [ ] Full end-to-end workflow verification
- [ ] Test all 25+ control points with 4-way controls
- [ ] Verify constraint enforcement on all bone types

### Group Node Refinement
- [ ] Test and tune arm group axis feel
- [ ] Test and tune leg group axis feel
- [ ] Test shoulders_group bilateral behavior (both collars + both shoulders rotating together)
- [ ] Test legs_group bilateral behavior
- [ ] Consider adding inversion for right-side groups if testing reveals need

### Robustness
- [ ] Handle missing bones gracefully (control point skipped if bone not in rig)
- [ ] Handle armature rename mid-session
- [ ] Verify behavior with different Genesis 8 figures (not just Fey)

---

## Future Features

### Phase 2: Hand Panel
- [ ] Hand extraction workflow integration with PoseBridge UI
- [ ] Finger control points with per-joint rotation
- [ ] Fist/curl group controls
- [ ] View switcher: Body <-> Hands using icons.py

### Phase 3: Head/Face Panel
- [ ] Face bone control points
- [ ] Morph target integration (expressions)
- [ ] View switcher: Body <-> Head

### UI Controls (Control Panel Viewport or BlenDAZ N-Panel)
- [ ] Mouse sensitivity slider (adjust rotation speed during posing)
- [ ] Mute pin toggle (on/off) -- only affects rotations made in PoseBridge control panel; pins are still respected when rotating on the 3D mesh or via Blender gizmo until "Enable Pins" is turned off in BlenDAZ main controls
- [ ] Per-bone 3-axis sliders when bone is selected (X/Y/Z rotation like DAZ Studio's posing sliders)

### Interaction Improvements
- [ ] Undo stack for Ctrl+Z during posing (partially implemented)
- [ ] Auto-keyframe on drag release
- [ ] Pose presets (save/load named poses)
- [ ] Symmetry mode (pose left side, mirror to right)
- [ ] UI toggle to enable/disable constraint enforcement

### Visual Improvements
- [ ] Control point size scaling with viewport zoom
- [ ] Color coding by body region (head=blue, arms=green, etc.)
- [ ] Ghost/onion skin for previous pose
- [ ] Visual feedback for rotation limits (dot turns red near limit)

---

## Known Issues

### Medium Priority
- [ ] Minor bugginess at extreme thigh X rotation (gimbal singularity in swing-twist decomposition)
- [ ] Diffeomorphic import sometimes doesn't create LIMIT_ROTATION constraints for head, shoulder twist, elbow, forearm twist
- [ ] Python module caching makes development iteration slow (requires Blender restart for shared_utils changes)

### Low Priority
- [ ] interaction.py and control_points.py are stubs (all logic currently in daz_bone_select.py)
- [ ] presets.py partially superseded by daz_shared_utils.py definitions
- [ ] Debug print statements left in rotation code (useful for development, noisy in production)

---

## Technical Debt

### Code Organization
- [ ] Consolidate control point definitions to single source (currently in both daz_shared_utils.py and daz_bone_select.py axis chains)
- [ ] Consider extracting PoseBridge rotation logic from daz_bone_select.py into interaction.py
- [ ] core.py `initialize_control_points_for_character()` doesn't handle `bone_names` / `control_type='multi'` properly

### Testing
- [ ] No automated tests (all testing is manual in Blender)
- [ ] Document test procedure for each control point type
- [ ] Create test scene file with known-good Genesis 8 setup

---

## Ideas to Consider

### Experimental
- [ ] Drive control point positions from armature-space bone positions (live update as pose changes)
- [ ] Support Rigify rigs in addition to DAZ
- [ ] Touch/tablet input for rotation (pressure sensitivity)

### Research Needed
- [ ] Can we read PowerPose control mappings from .duf files?
- [ ] GPU instancing for control point rendering (performance at scale)
- [ ] Blender 4.x Geometry Nodes for outline generation instead of Line Art modifier

---

## Notes

**How to use this file:**
1. Check "Current Work" for active development priorities
2. Move items from Backlog to Current Work as you begin them
3. Mark items complete and move to "Recently Completed"
4. Archive old completed items to SCRATCHPAD.md periodically
5. Add new ideas to appropriate sections
6. Review and groom this file weekly
