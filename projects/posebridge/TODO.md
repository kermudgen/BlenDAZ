# PoseBridge - TODO

**Last Updated**: 2026-02-20

Track current development tasks, future features, and improvements needed.

---

## Current Work

### Validate All Bone Rotation Mappings
**Description**: Test every control point's 4-way rotation (LMB horiz/vert, RMB horiz/vert) to confirm axes match PowerPose research after the comprehensive audit.

#### Immediate Tasks
- [ ] Test head, neckUpper, neckLower
- [ ] Test chestUpper, chestLower, abdomenUpper, abdomenLower, pelvis
- [ ] Test lCollar/rCollar, lShldrBend/rShldrBend
- [ ] Test lForearmBend/rForearmBend, lHand/rHand
- [ ] Test lThighBend/rThighBend (critical - was broken at runtime before fix)
- [ ] Test lShin/rShin, lFoot/rFoot, lToe/rToe
- [ ] Test all 8 group nodes (neck, torso, lArm, rArm, lLeg, rLeg, shoulders, legs)
- [ ] Verify bilateral mirroring on shoulders_group and legs_group
- [ ] Verify twist bone filtering on arm/leg groups
- [ ] Fix any axis mappings found to be incorrect

---

## Recently Completed (Feb 2026)

- [x] **Dual-viewport interaction** - `_hover_from_posebridge` flag routes 3D mesh drags to IK and control panel drags to PoseBridge rotation
- [x] **PowerPose axis mapping audit** - Fixed 20+ control point definitions to match PowerPose DSX research
- [x] **Bilateral mirroring** - `mirror_axes` support for legs_group and shoulders_group
- [x] **RMB context menu fix** - Multi-layered event suppression prevents Blender context menu during PoseBridge drags
- [x] **Tooltip flash fix** - Removed premature clear that killed tooltip on next MOUSEMOVE
- [x] **Human-readable group tooltips** - Groups show "Left Leg Group" instead of comma-separated bone names; bone names looked up from definitions at runtime
- [x] **TECHNICAL_REFERENCE.md** - PowerPose DSX research data documented
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
- [ ] Verify constraint enforcement on all bone types

### Robustness
- [x] Handle missing bones gracefully (control point skipped if bone not in rig)
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
- [x] Mouse sensitivity slider (adjust rotation speed during posing)
- [ ] Mute pin toggle (on/off) -- only affects rotations made in PoseBridge control panel; pins are still respected when rotating on the 3D mesh or via Blender gizmo until "Enable Pins" is turned off in BlenDAZ main controls
- [ ] Per-bone 3-axis sliders when bone is selected (X/Y/Z rotation like DAZ Studio's posing sliders)

### Interaction Improvements
- [ ] Undo stack for Ctrl+Z during posing (partially implemented)
- [ ] Auto-keyframe on drag release
- [ ] Pose presets (save/load named poses)
- [ ] Symmetry mode (pose left side, mirror to right)
- [x] UI toggle to enable/disable constraint enforcement

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
- [x] core.py `initialize_control_points_for_character()` doesn't handle `bone_names` / `control_type='multi'` properly

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
