# BlenDAZ - TODO

**Last Updated**: 2026-02-28

Track current development tasks, future features, and improvements needed.

---

## 🚧 Current Work

### DAZ Rig Manager 🟢 In Progress

**Description**: Centralized rig detection, preparation, and metadata storage. Foundation for all BlenDAZ operations.

**Module**: `daz_rig_manager.py`

#### Core Features (Implemented)
- [x] `RigManager` singleton class
- [x] `DAZRigInfo` dataclass for rig metadata
- [x] Genesis 8/9 version detection
- [x] Bone hierarchy caching
- [x] Bend/twist pair detection
- [x] Convert all bones to quaternion mode
- [x] Store original rotation modes (for DAZ export)
- [x] Diffeomorphic fingerprint detection

#### Integration Tasks
- [ ] Replace `prepare_rig_for_ik()` in daz_bone_select.py with RigManager
- [ ] Use cached bend_twist_pairs instead of runtime detection
- [ ] Add N-Panel UI showing rig status
- [ ] Error handling for non-DAZ rigs

#### Future: DAZ Export
- [ ] Generate DSF/DUF pose files
- [ ] Restore original rotation modes before export
- [ ] Handle bone name mapping (Blender ↔ DAZ)

---

### Analytical IK Solvers 🟢 Complete

**Description**: Bypass Blender's IK solver for legs and arms using direct law-of-cosines math.

#### Leg Solver (57/57 tests passing)
- [x] 2-bone analytical solve (thigh + shin)
- [x] Bone X-axis bend plane (locked — legs have limited ROM)
- [x] Works across all hip rotations including degenerate 90° cases
- [x] Thigh twist preservation
- [x] Debug overlay (`_DEBUG_DRAW_ANALYTICAL_LEG`)
- [x] Full test suite: `tests/test_analytical_leg.py`

#### Arm Solver (62/62 tests passing)
- [x] 2-bone analytical solve (shoulder + forearm)
- [x] Hand-only trigger (lHand/rHand)
- [x] Collar integration: 45% damped-track with reach-distance scaling
- [x] Dynamic bend plane: Gram-Schmidt projection + sign continuity + dampened blending
- [x] Forearm twist preservation
- [x] Debug overlay (`_DEBUG_DRAW_ANALYTICAL_ARM`)
- [x] Full test suite: `tests/test_analytical_arm.py`

#### Key Architecture Differences (Leg vs Arm)
- **Legs**: Locked bend_normal (computed once on first frame). Sufficient because hip ROM is limited.
- **Arms**: Dynamic bend_normal (recomputed each frame via Gram-Schmidt). Required because shoulder has full spherical ROM. Sign continuity tracking + 25% dampened blending prevents twist snapping during sweeps.

---

### Init Script & Standin Mesh 🟡 Ready to Implement

**Description**: Consolidate posebridge initialization + add standin mesh support

#### Next Session Tasks
- [ ] Create consolidated init script (`posebridge/init_posebridge.py`):
  - [ ] Auto-detect or prompt for armature name
  - [ ] Check for rest pose (warn if not)
  - [ ] Register PoseBridge
  - [ ] Generate outline + standin
  - [ ] Move setup to Z -50m
  - [ ] Capture control points
  - [ ] Start modal operator
- [ ] Modify `outline_generator_lineart.py` for standin:
  - [ ] Don't hide `_LineArt_Copy` mesh (becomes standin)
  - [ ] Rename to `_Standin` instead of `_LineArt_Copy`
  - [ ] Strip materials from standin mesh

#### Test Results
- ✅ Confirmed: GP outline survives when source mesh is visible
- ✅ Confirmed: Can reuse `_LineArt_Copy` as standin (no second copy needed)

---

### Hand Panel Implementation 🟡 Design Complete

**Description**: Hand detail view with 21 control points per hand

#### Design (see [SCRATCHPAD.md](SCRATCHPAD.md))
- 15 circles: individual finger joints (3 per finger × 5 fingers)
- 5 finger group diamonds: curl whole finger
- 1 fist diamond: curl all fingers

#### Tasks
- [ ] Add hand cameras to outline generator (`PB_Camera_LeftHand`, `PB_Camera_RightHand`)
- [ ] Define hand control points in `control_points.py`
- [ ] Add view switching (Body/L Hand/R Hand/Face)
- [ ] Wire up draw handler to check current view mode

---

### BlenDAZ N-Panel UI ⏸️ Paused

**Description**: Centralized setup and configuration panel (punted for now)

#### Tasks (for later)
- [ ] Add settings properties to `posebridge/core.py`
- [ ] Create N-Panel UI in `posebridge/panel_ui.py`
- [ ] Wire up outline options (enable, thickness, color)

---

### PoseBridge Phase 1 MVP

---

### PoseBridge Phase 1 MVP

**Description**: Fixed control points with basic click-drag rotation for visual posing

#### Immediate Tasks
- [ ] Complete hover detection implementation
- [ ] Verify click-drag rotation works correctly with all control points
- [ ] Test with Genesis 8 character
- [ ] Test with Genesis 9 character
- [ ] Validate rotation limits are properly enforced

#### Current Status
**Phase**: Phase 1 MVP (Fixed control points, basic rotation)
**Goal**: Complete basic visual posing with fixed 2D control points
**Next Steps**: Complete testing checklist in [posebridge/TESTING_POSEBRIDGE.md](posebridge/TESTING_POSEBRIDGE.md)

---

## 🚧 Next Session — N-Panel Reorganisation

**Goal**: Restructure all DAZ-tab N-panel sections into a clean, DAZ-like hierarchy before further feature work.

### Agreed Structure (diagram finalised this session)

```
DAZ tab
├── BlenDAZ          ← root: master Start/Stop button + Setup sub-panel (init/remap)
├── Touch            ← click-drag posing settings (no own on/off — runs when BlenDAZ active)
├── PoseBridge       ← visual control panel: Open in Viewport, Body/Hands/Face switcher,
│                       Body Controls (Reset Pose), Face Controls (expressions + visemes),
│                       Settings (sensitivity, outlines, keyframe, constraints)
└── PoseBlend        ← dot grid puppeteer: keep existing structure as-is
```

### Open Questions (sleep on these before deciding)

1. **Rotation Limits + IK Settings** (currently in "DAZ Bone Tools" root panel) — move into Touch > Settings, or drop from UI entirely since users don't touch them day-to-day?
2. **Body Controls + Face Controls** — DEFAULT_CLOSED or open by default under PoseBridge?
3. **"Open in Viewport" for PoseBridge** — needs to be built. Should clicking it lock the viewport to camera view immediately (current behavior when clicking Panel Views), or just register the draw handler and let the user switch manually?
4. **BlenDAZ Start button** — does stopping BlenDAZ also stop PoseBridge/PoseBlend viewports, or just Touch?

### Tasks (in order)

- [ ] Create new `D:\Dev\BlenDAZ\projects\posebridge\panel_ui.py` structure:
  - [ ] `VIEW3D_PT_blendaz_root` — master panel ("BlenDAZ"), Start/Stop Touch button, armature + status line
  - [ ] `VIEW3D_PT_blendaz_setup` — move/keep as sub-panel of blendaz_root (currently parented to posebridge_main)
  - [ ] `VIEW3D_PT_touch` — sensitivity, morph sensitivity, opacity, enforce constraints, auto keyframe
  - [ ] `VIEW3D_PT_posebridge` — Open in Viewport button, Body/Hands/Face switcher, show outline/CPs
  - [ ] `VIEW3D_PT_posebridge_body` — Reset Pose, Clear All Pins (sub of posebridge)
  - [ ] `VIEW3D_PT_posebridge_face` — Reset Face, Expressions box, Visemes box (sub of posebridge)
  - [ ] `VIEW3D_PT_posebridge_settings` — existing settings, collapsed (sub of posebridge)
- [ ] Remove `D:\Dev\BlenDAZ\panel_ui.py` root panel ("DAZ Bone Tools") — contents redistributed above
- [ ] Move `VIEW3D_PT_daz_body_controls` and `VIEW3D_PT_daz_face_controls` out of `daz_bone_select.py` into `posebridge/panel_ui.py`
- [ ] Build `POSEBRIDGE_OT_open_in_viewport` operator — targets current viewport via `context.area.as_pointer()`
- [ ] Update `daz_bone_select.py` register/unregister to stop registering the old root panel
- [ ] Update `setup_all.py` summary printout for new panel names
- [ ] Test: full session start → N-panel looks correct → Touch works → PoseBridge opens in viewport → PoseBlend opens in viewport

---

## ✅ Recently Completed (2026-02-28)

- [x] **Multi-character clothing penetration fix** (2026-02-28) — Hovering non-active characters hit clothing instead of body mesh because RAYCAST 2 (clothing-penetration) only checked `_base_body_mesh` (active character). Fix: added `_base_body_meshes = {}` per-character cache (keyed by armature name), populated at invoke for all registered characters. Updated RAYCAST 2 in `check_hover`, cross-viewport hover, posebridge hover, `draw_highlight_callback`, and `draw_selection_brackets_callback` to resolve through clothing for ANY registered character.
- [x] **Multi-character hand/face panel fix** (2026-02-28) — Hands view showed no standins or CPs, face view showed no CPs. Three bugs: (1) `extract_hands.py` used generic names `PB_Hand_Left`/`PB_Hand_Right` — second character's registration deleted first character's hands. Fix: append `char_tag` to hand mesh names. (2) `panel_ui.py` visibility toggle used exact name match. Fix: substring match with active char_tag filter. (3) `drawing.py` camera check used hardcoded legacy camera names (`PB_Camera_Hands`, `PB_Camera_Face`). Fix: look up camera from active CharacterSlot.

## ✅ Previously Completed (2026-02-24)

- [x] **N-Panel reorganisation design** (2026-02-24) — Full diagram agreed, open questions documented in Next Session above. Structure: BlenDAZ root → Touch → PoseBridge (with Body/Face Controls) → PoseBlend.
- [x] **Character Init System** (2026-02-24) — `register_only.py`, `init_character.py` (3 operators), `build_from_reference_mesh()` in `dsf_face_groups.py`, status properties in `core.py`, BlenDAZ Setup sub-panel in `panel_ui.py`. Auto-restores remapped FGM on module reload. Live hot-push of FGM into running modal via `_live_instance`.
- [x] **Face group highlight fix post-merge** (2026-02-24) — `get_or_create` now falls back to `build_from_reference_mesh` when DSF polygon count mismatches and `blendaz_init_status == 'ready'`. `used_face_groups` only blocks vertex-weight fallback when polygons were actually found.
- [x] **Head Rotation Pin + Spine Compensation** (2026-02-24) - `_solve_pinned_neck()` distributes counter-rotation through 6 spine bones. Partial chains, compose-not-replace, reset-to-originals.
- [x] **Head Translation Pin + Neck IK** (2026-02-24) - 2-bone analytical IK through neckLower/neckUpper. Fixed bend normal with `cross(bone_Y, target_dir)`.
- [x] **R/G Key Pass-Through on Pinned Bones** (2026-02-24) - Override pinned bone constraints, update pin on confirm.
- [x] **Rotation Pins Active During IK Drag** (2026-02-24) - Only mute translation pins during G-drag; rotation pins stay active.
- [x] **Pin System Test Suite** (2026-02-24) - `tests/test_pin_system.py` — 30 tests, 78 assertions, all passing.
- [x] **Analytical Arm IK Solver** (2026-02-23) - 2-bone law-of-cosines solver with collar integration, dynamic bend plane, and 62 regression tests
- [x] **Analytical Leg IK Solver** (2026-02-23) - 2-bone solver with bone X-axis bend plane, 57 regression tests, bulletproof across all hip rotations
- [x] **Bone Selection Fix** (2026-02-23) - No more toggle-off on re-click, always selects reliably
- [x] **Documentation System Setup** (2026-02-16) - Four-file documentation system (CLAUDE.md, INDEX.md, SCRATCHPAD.md, TODO.md)

---

## 📋 Backlog - High Priority

### PoseBridge Development
- [ ] Complete Phase 1 MVP testing and validation
- [ ] Fix any bugs discovered during Phase 1 testing
- [ ] Archive [posebridge/scratchpad.md](posebridge/scratchpad.md) (currently 46KB, approaching 50-75KB threshold)
- [ ] Begin Phase 2 planning (directional gestures)

### Code Quality
- [ ] Refactor [daz_bone_select.py](daz_bone_select.py) - Currently 267KB (unusually large)
  - Split into logical modules
  - Identify core functionality vs. helpers
  - Maintain backwards compatibility
- [ ] Review and implement [PROPOSAL_MODULE_REFACTOR.md](PROPOSAL_MODULE_REFACTOR.md) if relevant

### Testing & Validation
- [ ] Run [test_powerpose.py](test_powerpose.py) to ensure PowerPose functionality
- [ ] Run [validate_powerpose.py](validate_powerpose.py) to check installation
- [ ] Create automated tests for PoseBridge core functionality
- [ ] Create automated tests for PoseBlend core functionality

---

## 🔮 Future Features

### PoseBridge Phases
- [ ] **Phase 2**: Directional gestures (horizontal/vertical drag for different rotation axes)
- [ ] **Phase 3**: Panel views (head detail panel, hand detail panels)
- [ ] **Phase 4**: Multi-character support (select which character to pose)
- [ ] **Phase 5**: Polish and optimization (performance improvements, visual refinements)

### PoseBlend Enhancements
- [ ] Improve pose blending algorithms
- [ ] Add more preset collections
- [ ] Enhance grid visualization
- [ ] Add pose thumbnails/previews
- [ ] Implement pose tagging and search

### Diffeomorphic Integration
- [ ] Better handling of characters without LIMIT_ROTATION constraints
- [ ] Automatic detection of Genesis version (8 vs 9)
- [ ] Support for Genesis 3 and earlier versions
- [ ] Custom rig support beyond Genesis

### UI/UX Improvements
- [ ] Implement UI polish suggestions from [UI_POLISH_DESIGN_DOCUMENT.md](UI_POLISH_DESIGN_DOCUMENT.md)
- [ ] Add keyboard shortcuts reference panel
- [ ] Create interactive tutorial/onboarding
- [ ] Add tooltips to all controls

### Performance
- [ ] Optimize GPU drawing for large control point sets
- [ ] Profile and optimize modal operator performance
- [ ] Reduce memory footprint for outline generation
- [ ] Cache frequently accessed bone data

---

## 🐛 Known Issues

### High Priority
- [ ] **Unpin Pose Preservation**: Bones snap to rest pose when unpinned instead of keeping current visual position/rotation. Three approaches failed (matrix decomposition, matrix_basis computation, world-space delta). Constraint visual transform doesn't write to `rotation_quaternion`. Possible fixes: try `bpy.ops.constraint.apply()`, try setting `pose_bone.matrix` directly, try keyframing before removing constraint.
- [ ] **Diffeomorphic Import Issue**: Some bones don't get LIMIT_ROTATION constraints
  - Affects: head, shoulder twist, elbow, forearm twist bones
  - Workaround: Fallback to IK limits or defaults in `enforce_rotation_limits()`
  - Permanent fix: Investigate Diffeomorphic import settings

### Medium Priority
- [ ] **Module Caching**: Blender module caching can cause issues during development
  - Workaround: Restart Blender or use reload scripts
  - Consider: Better reload mechanism or development mode
- [ ] **Control Point Recapture**: Must manually recapture after moving outline
  - Current: Run [recapture_control_points.py](posebridge/recapture_control_points.py)
  - Desired: Automatic recapture or validation warning

### Low Priority
- [ ] Large file size for [daz_bone_select.py](daz_bone_select.py) (267KB)
- [ ] [posebridge/scratchpad.md](posebridge/scratchpad.md) approaching archive size (46KB)
- [ ] BlenDAZ toggle button should stop modal operator in ALL viewports, not just the current one

---

## 🔧 Technical Debt

### Code Quality
- [ ] Refactor [daz_bone_select.py](daz_bone_select.py) into smaller modules
- [ ] Review and clean up experimental outline generators
  - Keep: [outline_generator_lineart.py](posebridge/outline_generator_lineart.py) (primary method)
  - Archive or remove: outline_generator.py, outline_generator_body.py, outline_generator_curves.py, outline_generator_simple.py
- [ ] Standardize error handling across all modules
- [ ] Add type hints to function signatures
- [ ] Remove unused imports

### Testing
- [ ] Create unit tests for [daz_shared_utils.py](daz_shared_utils.py)
  - Test rotation limit enforcement
  - Test bend/twist axis detection
  - Test control point definitions
- [ ] Create integration tests for PoseBridge workflow
- [ ] Create integration tests for PoseBlend workflow
- [ ] Add test coverage reporting

### Performance
- [ ] Profile GPU draw handlers for performance bottlenecks
- [ ] Benchmark outline generation methods
- [ ] Optimize control point hover detection
- [ ] Cache bone axis calculations

### Documentation
- [ ] Create user installation guide
- [ ] Create video tutorials for key features
- [ ] Document known Diffeomorphic compatibility issues
- [ ] Create troubleshooting guide
- [ ] Add inline code documentation for complex functions
- [ ] Document GPU shader code

---

## 📊 Project Maintenance

### Regular Tasks
- [ ] Review and update SCRATCHPAD.md weekly
- [ ] Groom TODO.md (this file) weekly
- [ ] Archive SCRATCHPAD.md when it reaches 300-500 lines or 50-75KB
- [ ] Update CLAUDE.md "Current Focus" section when priorities shift
- [ ] Update INDEX.md when adding new files or changing file purposes
- [ ] Check for Blender API changes with new Blender releases

### Archiving Schedule
- [ ] **Immediate**: Archive [posebridge/scratchpad.md](posebridge/scratchpad.md) (46KB)
- [ ] Create `scratchpad_archive/` directory structure
- [ ] Establish monthly review process for archived documents

### Monitoring
- [ ] Watch for Diffeomorphic DAZ Importer updates
- [ ] Monitor Blender API deprecation warnings
- [ ] Track user feedback on GitHub/forums
- [ ] Monitor performance metrics in production use

---

## 💡 Ideas to Consider

### Experimental
- [ ] **AI-Assisted Posing**: Use pose detection AI to suggest control point adjustments
- [ ] **Pose Library Expansion**: Community-contributed pose library
- [ ] **Motion Capture Integration**: Import mocap data and convert to poses
- [ ] **Facial Expression System**: Extend control points to facial bones
- [ ] **Physics-Based Posing**: Add physics simulation for natural poses

### Research Needed
- [ ] **WebGL Export**: Can we export posed characters for web viewing?
- [ ] **VR Posing Interface**: Use VR controllers for intuitive posing
- [ ] **Pose Interpolation**: Smooth transitions between keyframe poses
- [ ] **Symmetry Tools**: Mirror poses left-to-right
- [ ] **Pose Presets by Genre**: Action, casual, portrait, etc.

### Community Features
- [ ] **Pose Sharing Platform**: Share and download community poses
- [ ] **Tutorial System**: In-app guided tutorials
- [ ] **Preset Marketplace**: Curated pose and preset collections
- [ ] **Plugin API**: Allow third-party extensions

---

## 📝 Notes

**How to use this file:**
1. Check "Current Work" for active development priorities
2. Move items from Backlog to Current Work as you begin them
3. Mark items complete and move to "Recently Completed"
4. Archive old completed items to SCRATCHPAD.md periodically (every few weeks)
5. Add new ideas to appropriate sections
6. Review and groom this file weekly

**Priority Levels:**
- **Current Work**: Active development, highest priority
- **Recently Completed**: Just finished (archive after a few weeks)
- **Backlog**: High priority, planned for next
- **Future Features**: Long-term vision, requires significant work
- **Ideas**: Brainstorming, needs validation/research

**Task Status Indicators:**
- [ ] Not started
- [x] Completed
- 🟡 In progress (use in descriptions)
- 🟢 Complete (use in descriptions)
- 🔴 Blocked (use in descriptions)
- ⏸️ Paused (use in descriptions)

---

## 🎯 Project Phases

### Phase 1: MVP (Current)
**Focus**: Get PoseBridge working with basic functionality
- Fixed control points
- Click-drag rotation
- Hover detection
- Dual viewport setup

### Phase 2: Gestures
**Focus**: Add directional gesture controls
- Horizontal drag = rotation on one axis
- Vertical drag = rotation on different axis
- Combine with modifier keys

### Phase 3: Detail Panels
**Focus**: Add focused panels for detailed work
- Head/face detail panel
- Hand detail panels (left/right)
- Foot detail panels

### Phase 4: Multi-Character 🟢 In Progress
**Focus**: Support multiple characters in scene
- [x] Character selection (seamless click-drag switch between characters)
- [x] Per-character control points (CP cache save/restore on switch)
- [x] Outlining multiple characters (Z-offset stacking)
- [x] Per-character DSF face group managers (`_face_group_mgrs` cache)
- [x] Per-character base body mesh resolution (`_base_body_meshes` cache)
- [x] Hover highlights on non-active characters
- [x] Selection brackets on non-active characters
- [x] Clothing penetration for all characters (not just active)
- [ ] BlenDAZ toggle button should stop modal in ALL viewports
- [ ] Collar snapping during arm IK drag (pre-existing analytical solver issue)

### Phase 5: Polish
**Focus**: Performance and user experience
- Optimization
- Visual refinements
- User testing feedback
- Documentation completion

---

## 🔗 Related Documentation

- [CLAUDE.md](CLAUDE.md) - Project context and development guidelines
- [INDEX.md](INDEX.md) - Complete file reference
- [SCRATCHPAD.md](SCRATCHPAD.md) - Development journal
- [PROJECT_SETUP_GUIDE.md](PROJECT_SETUP_GUIDE.md) - Documentation system guide

---

## 📅 Version History

**2026-02-16**: Initial TODO.md creation with documentation system setup
- Cataloged current work (PoseBridge Phase 1)
- Identified backlog items from existing documentation
- Noted technical debt (large file sizes, refactoring needs)
- Outlined 5-phase development roadmap
