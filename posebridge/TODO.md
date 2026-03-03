# PoseBridge - TODO

**Last Updated**: 2026-02-24

Track current development tasks, future features, and improvements needed.

---

## Current Work

### N-Panel: Categorized Morph Sliders
**Description**: Add DAZ-style categorized sections (Brow, Eyes, Mouth, etc.) to the Face Controls N-panel instead of a flat expression/viseme list.

#### Immediate Tasks
- [ ] Design category structure for FACS morphs (Brow, Eye, Nose, Mouth, Jaw, Cheek)
- [ ] Decide UI pattern: collapsible sub-panels vs. labeled sections within Face Controls
- [ ] Map existing FACS property names to categories
- [ ] Implement in `panel_ui.py` Face Controls panel
- [ ] Update `FACE_EXPRESSION_SLIDERS` / `FACE_VISEME_SLIDERS` in `daz_shared_utils.py` if needed

---

## Bug Backlog

### BUG: Head bone selection fails from deselected state
**Priority**: Medium
**Description**: Clicking the head CP when nothing is selected doesn't work. Bone selection path probably assumes an already-selected bone.
**File**: `daz_bone_select.py` — `check_posebridge_hover()` / `start_ik_drag()` head path

### BUG: Mesh highlight shows in left (PoseBridge) viewport
**Priority**: Medium
**Description**: The hover highlight overlay appears in the PoseBridge control panel viewport instead of (or in addition to) the 3D character viewport.
**File**: `daz_bone_select.py` — `draw_highlight_callback()` — viewport targeting

---

## Recently Completed (Feb 2026)

- [x] **Selection brackets** - DAZ-style bone-aligned OBB corner brackets. Mesh vertex bounds with 15% padding. Gold/amber hover, light gray select. Hip falls back to pelvis region.
- [x] **Highlight opacity control** - `highlight_opacity` FloatProperty (0–1) on PoseBridgeSettings. Slider in Settings N-panel. Controls mesh highlight + bracket alpha.
- [x] **Morph drag race condition** - `_drag_control_point_id` + `_drag_bone_names` locked at mouse-down. Survives hover state clearing during drag threshold.
- [x] **FACS joint morph fix** - `_get_driven_rotation_bones()` detects bones with rotation_euler drivers; skips them during quaternion conversion so Diffeomorphic joint morphs work.
- [x] **Mannequin cleanup** - Shape key stripping + non-Armature modifier removal on mannequin mesh copy (no more JCMs/flexions in control panel).
- [x] **Hidden twist bone CPs** - `capture_fixed_control_points()` now checks `'hidden': True` flag.
- [x] **Hip G-translate fix** - Clear locked drag state in G handler; single native translate pass-through gate at top of modal().
- [x] **Face Panel** - Live camera (`PB_Camera_Face`), ~26 morph CPs, FACS drag (bilateral + asymmetric), morph undo stack
- [x] **N-Panel overhaul** - Removed old PowerPose panel; added Body Controls (Reset Pose) + Face Controls (Reset Face + expression/viseme sliders)
- [x] **Undo stack fix** - `self._undo_stack = []` in invoke() was shadowing class list; fixed to use `VIEW3D_OT_daz_bone_select._undo_stack.clear()`
- [x] **Expression/viseme sliders** - Dynamic FloatProperties on PoseBridgeSettings, update callbacks scaling FACS presets by intensity; `FACE_EXPRESSION_PRESETS` in daz_shared_utils.py
- [x] **DSF face groups** - Clean hard-edged zone detection; polygon-count-based gender resolution; stale cache fix; geograft fallback
- [x] **Delegate architecture** - Group nodes use `group_delegates` referencing single-bone node controls; eliminates `bone_overrides` + `mirror_axes` complexity
- [x] **Leg group twist fix** - Current-bone-axis correction for sibling twist bones after ThighBend raises; identity-skip guard for ERC compatibility
- [x] **Auto-detect DAZ armature** - start_posebridge.py / recapture scripts auto-find armature by DAZ bone markers
- [x] **Dual-viewport interaction** - `_hover_from_posebridge` flag routes 3D mesh drags to IK, control panel to PoseBridge
- [x] **PowerPose axis mapping audit** - Fixed 20+ control point definitions; data-driven group controls
- [x] **RMB context menu fix** - Multi-layered suppression prevents context menu during PoseBridge drags
- [x] **TECHNICAL_REFERENCE.md** - PowerPose DSX research data documented
- [x] **Phase 1 MVP** - Outline generation, rotation, tooltips, bilateral mirroring, constraint enforcement

---

## Backlog - High Priority

### Validate All Bone Rotation Mappings
- [ ] Test head, neckUpper, neckLower
- [ ] Test chestUpper, chestLower, abdomenUpper, abdomenLower, pelvis
- [ ] Test lCollar/rCollar, lShldrBend/rShldrBend
- [ ] Test lForearmBend/rForearmBend, lHand/rHand
- [ ] Test lShin/rShin, lFoot/rFoot, lToe/rToe
- [ ] Test all 8 group nodes (neck, torso, lArm, rArm, lLeg, rLeg, shoulders, legs)
- [ ] Fix any axis mappings found to be incorrect

### Phase 1 Completion
- [ ] Test ESC cancellation during rotation
- [ ] Full end-to-end workflow verification
- [ ] Verify constraint enforcement on all bone types

### Robustness
- [x] Handle missing bones gracefully (control point skipped if bone not in rig)
- [ ] Handle armature rename mid-session
- [ ] Verify behavior with different Genesis 8 figures (not just Fey)
- [ ] Test with a male character (different body proportions, bone positions)
- [ ] Test with geografts (e.g., geographic genital grafts — extra mesh regions parented to armature)
- [ ] Test with multiple characters in the scene (armature detection, CP assignment, viewport interaction)
- [ ] Test finger IK (hand panel finger controls)

---

## Future Features

### Polish
- [ ] Shoulders Group LMB horiz — forward/back axis feels off, needs recalibration

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
- [x] Highlight opacity slider (adjusts mesh highlight + bracket alpha)
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

### Pin System Bugs (dedicated debugging session needed)
- [ ] **Feet pull away from shins on pelvis rotate** — pin feet, rotate pelvis → feet separate from shin bones. IK solver not maintaining chain connectivity during spine rotation compensation.
- [ ] **Arms snap on hip move with extreme shoulder pose** — pin hands + feet, pose shoulders to extreme position, then G-move hip → arms snap to a different IK solution. Likely the analytical 2-bone IK solver flipping to the alternate elbow solution when the starting configuration changes significantly.
- [ ] **General pin solver audit needed** — test all pin combinations (head rot + feet trans, head trans + feet trans, all limbs) and verify chain connectivity, rotation accuracy, and cancel/restore behavior.

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
- [ ] Make single-bone rotation data-driven: `update_rotation()` should read the `controls` dict from the hovered CP (like multi-bone already does), falling back to hardcoded bone-type mapping if absent. Currently the `controls` dict on single-bone CPs is dead code.
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
