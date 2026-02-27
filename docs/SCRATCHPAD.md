# BlenDAZ - Development Scratchpad

## Purpose

This file tracks ongoing development work, experiments, bugs, and feature progress. It's a living document that captures what we're working on, what we've tried, and what we've learned.

**Note**: When this file reaches ~300-500 lines or ~50-75KB, archive it to `scratchpad_archive/SCRATCHPAD_YYYY-MM.md` and start fresh.

## Archive History

*No archived scratchpads yet*

**Note**: [posebridge/scratchpad.md](posebridge/scratchpad.md) contains 46KB of PoseBridge development history and should be archived soon.

---

## Current Session: 2026-02-24 (session 4)

### Active Work: Pin System — Head Pins, Spine Compensation, UX Polish

#### Features Implemented This Session

1. **Head rotation pin + spine compensation** — `_solve_pinned_neck()` distributes counter-rotation through 6 spine bones when hip or any spine bone rotates. Uses `correction @ bone.rotation_quaternion` to compose with existing rotations (not replace). Partial chains: `_find_pinned_head(armature, rotated_bone_name=X)` only compensates with bones ABOVE the rotated bone.

2. **Head translation pin + neck IK** — 2-bone analytical IK through neckLower/neckUpper via `_solve_pinned_limb()`. Fixed bend normal to use `cross(bone_Y, target_dir)` instead of fixed forward heuristic (leg solver copy was wrong for backward movement).

3. **R/G key pass-through on pinned bones** — R on rotation-pinned bone mutes constraint, passes through to native rotate, updates pin Empty on confirm. G on translation-pinned bone uses existing `_temp_unpinned_bone` system.

4. **Rotation pins active during IK drag** — Only `DAZ_Pin_Translation` muted during G-drag; `DAZ_Pin_Rotation` stays active so foot/hand orientation is maintained.

5. **R key handler improvements** — Only intercepts R for hip + spine chain bones when head is rotation-pinned. Pin override allows R on pinned bones themselves.

6. **Depsgraph handler reset to originals** — When rotating a spine bone, handler resets compensation bones to pre-drag originals (not identity), preserving prior user-set rotations on other spine bones.

#### Bugs Fixed This Session

1. **T18 test failure (backward hip translation)** — Bend normal using fixed "forward bend" heuristic from leg solver chose wrong direction for backward movement. Fixed with `cross(bone_Y, target_dir)`.

2. **R key intercepting all rotations** — Handler checked if head was pinned but not which bone was selected. Fixed to only intercept hip + spine chain bones.

3. **NoneType error in end_ik_drag** — `self._drag_armature` was None. Added null guard.

4. **Spine bones snapping to rest** — Depsgraph handler reset all_bones to identity. Changed to reset to pre-drag originals.

5. **Solver overwriting user rotations** — `bone.rotation_quaternion = local_rot` replaced instead of composing. Fixed with `correction @ bone.rotation_quaternion`.

6. **Both pin types muted during IK drag** — Changed to only mute `DAZ_Pin_Translation`, keeping `DAZ_Pin_Rotation` active.

#### Known Bug: Unpin Pose Preservation

**Status**: OPEN — logged as known bug, moving on

**Problem**: When unpinning a bone (removing rotation or translation pin), the bone snaps back to its rest pose instead of keeping its current visual position/rotation.

**Root Cause**: Copy Rotation / Copy Location constraints provide visual transform but don't write to `rotation_quaternion` / `location`. When the constraint is removed, the bone reverts to its unconstrained local transform.

**Three Approaches Tried, All Failed**:
1. **Matrix decomposition** — Computed `pose_matrix = rest_local.inverted() @ local_matrix`, set `rotation_quaternion`. Didn't produce correct results.
2. **matrix_basis computation** — `target_basis = rest_offset.inverted() @ parent_mat.inverted() @ constrained_matrix`. Same snap behavior.
3. **World-space delta** — Snapshot world rotation with constraint, remove constraint, compute quaternion delta, conjugate to local space, compose. Still snaps.

**Possible Next Approaches**:
- Try Blender's built-in `bpy.ops.constraint.apply()` operator (applies constraint and removes it, might handle the math internally)
- Try `pose_bone.matrix = constrained_matrix` directly (Blender might handle decomposition internally when setting `.matrix`)
- Try keyframing the constrained pose before removing constraint
- Investigate if the constraint needs to be evaluated on the depsgraph before reading the constrained matrix

#### Test Suite

`tests/test_pin_system.py` — 30 tests, 78 assertions:
- Pin setup tests (6 tests)
- Head rotation pin + spine compensation (8 tests)
- Head translation pin + neck IK (8 tests)
- Combined pin tests (4 tests)
- Edge cases (4 tests)

All 78/78 passing after bend normal fix and solver compose fix.

#### Key Technical Insights

- **Rotation composition vs replacement**: `correction @ existing` preserves user-set rotations. `= computed_rot` overwrites everything. Critical for multi-bone spine compensation.
- **Bend normal for neck**: `cross(bone_Y, target_dir)` works for any target direction. The leg solver's fixed "forward bend" heuristic only works for leg geometry.
- **Partial spine chains**: When user rotates a spine bone, only bones ABOVE it should compensate. `_find_pinned_head(rotated_bone_name=X)` builds the right chain.
- **Reset to originals, not identity**: Depsgraph handlers must preserve prior user operations on bones not being actively rotated.

---

## Previous Session: 2026-02-19

### Active Work: Analytical Leg IK + DAZ Rig Manager Architecture

#### Leg IK Straightening Problem

**The Issue**: When dragging a bent leg to straighten it, Blender's IK solver keeps the knee bent because it finds a "local minimum" solution. The solver optimizes for minimum change, so a bent leg stays bent even when the target is reachable with a straight leg.

**Approaches Tried**:
1. Pre-bend seeding (0.8 rad) - helps initially but solver re-bends
2. Reset to straight then solve - IK immediately re-bends
3. IK limit locking (ik_max_x) - solver still finds bent solutions
4. Including pelvis in chain - didn't help
5. **Analytical IK** - current approach, bypasses Blender's solver entirely

**Analytical Leg IK Implementation**:
- Uses law of cosines to calculate exact knee angle based on distance
- Key insight: **Knee is a hinge joint** - only rotates on X axis
- Thigh: uses direction calculation (ball joint, can rotate freely)
- Shin: just sets X rotation to knee bend angle
- No local minima, handles straightening correctly

**Files Modified**:
- `daz_bone_select.py`: Added `solve_two_bone_ik_analytical()`, `calculate_bone_rotation_from_direction()`, `update_analytical_leg_drag()`

**Current Status**: ✅ **~99% WORKING!** Foot tracks mouse accurately (~0.02m error), knee bends/straightens correctly, smooth transitions, no snap/jump at drag start. Minor hitches remain but acceptable.

#### Bugs Fixed This Session

1. **Bone hierarchy mismatch** - Discovered `lShin` parent is `lThighTwist`, not `lThighBend`
   - Fix: Calculate `upper_leg_length` as hip-to-shin.head (includes twist bone)
   - Fix: Track ThighTwist bone for keyframing/restore

2. **Thigh rotation not pointing knee correctly** - Was using thigh.tail direction
   - Fix: Calculate rest direction from `thigh.bone.head_local` to `shin.bone.head_local`
   - This accounts for the twist bone in the chain

3. **Shin bend axis flipping** - Axis was recalculated every frame, causing erratic movement
   - Fix: Lock the shin bend axis at drag START (`_analytical_leg_shin_bend_axis`)
   - Hinge joints have a fixed rotation axis - don't recalculate!

4. **Knee bending backwards** - Hardcoded `(1, 0, 0)` as bend axis
   - Fix: Calculate actual axis from thigh/shin cross product at drag start
   - Ensure axis points so positive rotation bends forward (via knee_axis dot product)

5. **Undo not working** - Modal changes weren't registered with Blender's undo system
   - Fix: Added `bpy.ops.ed.undo_push()` at drag start and end

6. **Blender lockup on pose reset** - NaN values in rotation quaternions
   - Fix: Added safety checks for zero-length vectors and NaN validation

7. **Foot not following mouse** - Depth reference was fixed at initial foot position
   - Fix: Use delta-based mouse projection with initial foot as depth reference

8. **ThighTwist rotation ~160° off** - Was comparing rest shin direction to target
   - Fix: Apply shin bend FIRST, then calculate twist based on actual foot position vs target
   - Simplified to 3-option search: calculated angle, opposite, zero

9. **Knee swinging sideways** - Knee offset direction recalculated each frame
   - Fix: Lock `_analytical_leg_bend_plane_normal` at drag start
   - Rotate thigh around this fixed axis to keep knee in original bend plane

10. **Snap to extended when straightening** - Discontinuity between bent/extended cases
    - Fix: Both cases now use same rotation logic (hip_angle=0 for extended)
    - Smooth transition without sudden direction changes

11. **Performance (Blender crash)** - 16+ scene updates per frame for twist search
    - Fix: Reduced to 3 scene updates (calculated, opposite, zero)

12. **Bend plane sign flipped** - Anatomical bend_plane_normal had wrong sign for left leg
    - Left leg normal should point LEFT (-X), not +X
    - Wrong sign caused 170° twist compensation
    - Fix: Flipped sign convention (left=-X, right=+X)

13. **Shin bend axis sign flip** - Calculating from pose caused (-1,0,0) vs (1,0,0)
    - Fix: Hardcode to `(1, 0, 0)` - it's a hinge joint, always local X

14. **Jump/skip at drag start** - Resetting to identity and recalculating didn't match original pose
    - Fix: 3-pixel dead zone before IK kicks in

15. **Snap to straight near rest** - Zero mouse delta → target at max_reach → knee_bend=0
    - Fix: Same dead zone prevents recalculation until real mouse movement

#### IK Solver Implementation Details

```python
# Bone detection
thigh = lThighBend
twist = lThighTwist
shin = lShin
foot = lFoot

# Lengths (IMPORTANT: upper_leg includes twist!)
upper_leg = distance(thigh.head, shin.head)  # ~0.31m
lower_leg = distance(shin.head, shin.tail)   # ~0.28m

# At drag start, lock these:
_analytical_leg_knee_axis = perpendicular to hip-foot, toward knee
_analytical_leg_shin_bend_axis = (1, 0, 0)  # HARDCODED - hinge joint, always local X
_analytical_leg_bend_plane_normal = thigh × character_forward (anatomical, left=-X, right=+X)
```

#### Final Algorithm (per frame)

1. **Dead zone check** - skip if mouse moved < 3 pixels (prevents jump/snap)
2. **Reset** all leg bones to identity (clean slate)
3. **Calculate geometry** using law of cosines:
   - `knee_bend_angle` from hip-to-target distance
   - `hip_angle` for thigh offset from target direction
4. **ThighBend**: Rotate around locked `bend_plane_normal` by `hip_angle`
5. **Shin**: Apply `knee_bend_angle` on `(1, 0, 0)` local X axis
6. **ThighTwist**: Quick 3-option search for best foot-to-target alignment

#### Key Lessons Learned

- **Hinge joints have fixed axes** - Don't calculate from pose, hardcode (1,0,0)
- **Bend plane sign matters** - Left leg = -X normal, right leg = +X normal
- **Reset to identity each frame** - Prevents rotation accumulation errors
- **Dead zone prevents startup artifacts** - Don't recalculate until real mouse movement
- **Anatomical constraints > pose-based** - Use character orientation, not current pose

#### Performance Metrics

- Error: ~0.016-0.022m (1.6-2.2cm) - excellent for interactive posing
- Twist angles: ~14° (anatomically reasonable)
- Scene updates per frame: 5 (reset + thigh + shin bend + twist search x3)
- Smooth drag, no chug or crashes
- 3-pixel dead zone eliminates startup jump

#### DAZ Rig Manager Architecture

**Vision**: Instead of ad-hoc rig preparation scattered throughout the code, create a proper **BlenDAZ Rig Manager** that:

1. **On import/first use** (fingerprinting):
   - Detect DAZ character (Diffeomorphic fingerprint)
   - Convert ALL bones to quaternion mode (eliminates Euler conversion issues)
   - Store rig metadata (bone hierarchy, original rotation modes, constraints)
   - Cache for fast subsequent access
   - Identify Genesis version (8 vs 9)

2. **During posing**:
   - Use cached rig info
   - All operations work in quaternion space
   - Track pose changes

3. **Export to DAZ** (future):
   - Convert quaternions back to Euler (DAZ format)
   - Generate DSF/DUF pose file
   - Handle bone name mapping

**New Module**: `daz_rig_manager.py`

```python
class DAZRigInfo:
    armature_name: str
    fingerprint: str  # Diffeomorphic's rig ID
    genesis_version: int  # 8 or 9
    original_rotation_modes: dict  # For export back to DAZ
    bone_hierarchy: dict  # Parent/child relationships
    ik_chain_definitions: dict  # Pre-calculated IK chains
    bend_twist_pairs: dict  # lShldrBend → lShldrTwist mappings
    is_prepared: bool
```

**Benefits**:
- Single source of truth for rig info
- Detect issues early (missing bones, wrong rig type)
- Eliminate 25+ quaternion/euler mode checks throughout code
- Foundation for DAZ export functionality
- Better error handling and user feedback

**Implementation Added**:
- `prepare_rig_for_ik()` function in daz_bone_select.py
- Called on operator start and drag start
- Converts all bones to quaternion mode
- Tracks prepared armatures to avoid redundant conversion

#### Key Discoveries

1. **Knee only bends on one axis** - Simplifies leg IK to just setting shin's X rotation
2. **DAZ bones use Euler by default** - Source of quaternion/euler conversion issues
3. **25+ places check rotation_mode** - Clear sign we need centralized rig preparation
4. **Shin parent may not be ThighBend** - Need to verify bone hierarchy for proper IK

---

## Previous Session: 2026-02-18

### Active Work: Second Drag Bug Fix + Bend/Twist Architecture

#### Key Discoveries This Session

1. **LOCAL vs POSE constraint space** — Root cause of second-drag snap-to-straight. `.ik` bones have different rest pose than DAZ bones (their rest IS the current posed position). LOCAL space reads `matrix_basis` (delta from rest), so Identity on .ik = "go to rest" on DAZ = snap to T-pose. POSE space matches armature-space matrices directly, bypassing rest pose entirely. **Fix: Changed Copy Rotation to POSE/POSE space.**

2. **POSE space axis filtering doesn't work for bone-local twist** — `use_y = False` in POSE space filters armature Y axis, not the bone's local twist axis. When arm is posed away from rest, these don't align. Tried filtering Y for forearm (80% fix) and shoulder (made things worse). **Dead end for this approach.**

3. **Swing/twist decomposition is the proper solution** — Removed Copy Rotation from bend bones entirely. Added manual post-processing in `update_ik_drag()`: read `.ik` bone's evaluated matrix, compute local rotation via `rest_offset.inv @ parent.matrix.inv @ ik.matrix`, decompose with `decompose_swing_twist(rot, 'Y')`, set bend bone = swing, twist bone = twist.

4. **rotation_quaternion vs rotation_euler** — Setting `rotation_quaternion` on a bone in Euler mode does NOTHING. DAZ bones from Diffeomorphic may use Euler. Must always check `rotation_mode`. **Suspected cause of "arm not moving" with correct decomposition values.**

5. **frame_set() ordering in dissolve** — Swapped `frame_set()` BEFORE STEP 3.5 cache restore to prevent prior-drag keyframes from overriding restored leg positions.

6. **Keyframe reset warning spam** — Moved action/fcurves check outside per-bone loop (was printing 32 "no fcurves" warnings).

#### Changes Made
- `daz_bone_select.py` create_ik_chain(): Bend bones with twist counterparts skip Copy Rotation, tracked in `swing_twist_pairs`
- `daz_bone_select.py` update_ik_drag(): Added swing/twist post-processing after IK solve
- `daz_bone_select.py` dissolve_ik_chain(): Added swing/twist decomposition at bake time
- Return value of create_ik_chain expanded to 6 values (added swing_twist_pairs)
- All rotation setting now checks rotation_mode (QUATERNION vs Euler)

#### Status
- Second drag snap-to-straight: **FIXED** (POSE space)
- Bend/twist separation: **In testing** (manual decomposition approach)
- Rotation mode check: **Just added** (awaiting test results)

---

## Previous Session: 2026-02-17

### Active Work
- Hand panel implementation - COMMITTED TO MASTER (d068918)
- Icon system for DAZ PowerPose-style view switching - IN PROGRESS (pending icon designs)
- **IK Chain Architecture Refactoring** - STARTING NOW

---

## IK Chain Refactoring - 2026-02-17

### Context
Got stuck on ad hoc IK chain construction when working with Sonnet. Brought in Opus for fresh analysis. Decision: refactor for maintainability and reliability.

### Branch
`refactor/ik-chain-architecture` (created from master @ d068918)

### Rollback Plan
```bash
# If things go wrong:
git checkout master                           # Return to stable
git branch -D refactor/ik-chain-architecture  # Delete failed branch

# Or rollback specific commits:
git reset --hard HEAD~1                       # Undo last commit
```

### Analysis Summary (Opus 4.5)

**Current Architecture** (working but complex):
1. DAZ Bones (original) → receive Copy Rotation from...
2. .IK Control Bones → receive IK constraint targeting...
3. Target/Pole Bones → what user drags

**Identified Issues**:
1. **Chain collection is ad hoc** - Skip conditions scattered in while loop (twist bones, pectorals, pinned bones)
2. **Stiffness not configurable** - Templates are fixed, no runtime adjustment
3. **Mode switching fragile** - Rotation cache/restore pattern duplicated in 3 places (lines 747, 1503, 2387)
4. **Missing constraints** - Diffeomorphic doesn't always create LIMIT_ROTATION for head, shoulder twist, elbow, forearm twist
5. **File too large** - daz_bone_select.py at 267KB does too much

### Refactoring Plan (Incremental, One Commit Each)

| Order | Task | Risk | Status |
|-------|------|------|--------|
| 1 | Extract `ik_templates.py` | Low | [x] Done (c013065) |
| 2 | Extract `bone_utils.py` | Low | [x] Done (a8e5e56) |
| 3a | Create rotation cache module | Low | [x] Done (fb79677) |
| 3b | Replace existing cache patterns | Medium | [ ] Pending - TEST FIRST |
| 4 | Extract `ik_chain.py` | Medium | [ ] Pending |
| 5 | Make stiffness configurable | Medium | [ ] Pending |
| 6 | Refactor chain building to class | Higher | [ ] Pending |

### Test Checklist (Run After Each Change)
- [x] Script loads without import errors
- [ ] Basic arm IK drag works - **PRE-EXISTING ISSUE: arm shrugs instead of reaching**
- [ ] Leg IK with pre-bend works - **PRE-EXISTING ISSUE: knee bends backward, thigh twists**
- [ ] Soft pin behavior intact - works (tested with pinned hand)
- [ ] No snap-back on release
- [ ] Collar/shoulder movement smooth

**Note**: Arm/leg IK issues existed on master before refactoring. Will address after cleanup.

### Key Code Locations
- `daz_bone_select.py:44-134` - IK_RIG_TEMPLATES
- `daz_bone_select.py:534-1414` - create_ik_chain() main function
- `daz_bone_select.py:631-660` - Bone hierarchy traversal
- `daz_bone_select.py:747` - Rotation cache #1
- `daz_bone_select.py:1503` - Rotation cache #2
- `daz_bone_select.py:2387` - Rotation cache #3
- `daz_shared_utils.py` - Rotation utilities, enforce_rotation_limits()

---

### Decisions Made
- **Outline for body view only** - Hand/face views use standin mesh with matcap, no GP outline
  - Rationale: Generating separate GP Line Art bakes for each camera view adds complexity
  - Standin mesh with matcap should be clear enough at hand/face zoom levels
  - Can always add outlines later if needed

- **Combined hands view** - Both hands in single camera (like DAZ PowerPose)
  - Camera: `PB_Camera_Hands` (not separate left/right cameras)
  - Hands positioned side-by-side, dorsal view (back of hand up), thumbs inward
  - Z offset -53m (below body setup at -50m)

- **Thumb group positioning** - Use mid-point of Thumb1 bone
  - Thumb1 bone head is deep in palm (near wrist), not visible
  - Mid-point gives better visual placement near visible thumb base

### Today's Goals
- [ ] Create consolidated init script (`posebridge/init_posebridge.py`)
- [ ] Modify `outline_generator_lineart.py` for standin mesh
- [x] Add hand cameras - `PB_Camera_Hands` created
- [x] Extract hand geometry - `extract_hands.py` working
- [x] Define hand control points - 42 total (21 per hand)
- [x] Store hand control points in PoseBridge settings
- [x] Integrate view switching into panel_ui.py
- [x] Filter control point drawing by active_panel
- [x] Create icon system (icons.py) for view switcher
- [x] Create icon shape extraction tool (extract_icon_shape.py)
- [ ] Wire icons into main drawing.py (pending user icon designs)
- [ ] Add icon click handling in interaction.py

### Test Results - 2026-02-17

**Hand Extraction Test**: SUCCESS
- Vertex groups found: 20 per hand (lHand, lThumb1-3, lIndex1-3, lMid1-3, lRing1-3, lPinky1-3, lCarpal1-4)
- Vertices extracted: 1623 per hand
- Faces extracted cleanly with no gaps

**Calibrated Hand Transforms** (dorsal view, thumbs inward):
```
PB_Hand_Left:
  location=(-0.040003, -0.68324, z_offset + 0.022)
  rotation=(-180.16°, -34.575°, -88.528°)

PB_Hand_Right:
  location=(0.026067, -0.67678, z_offset - 0.049)
  rotation=(187.13°, 32.286°, 95.809°)
```
*Recalibrated after adding origin-to-geometry fix*

**Hand Control Points Integration**: SUCCESS
- 42 control points generated and stored (21 per hand)
- Control points filtered by `panel_view` property
- View switching works via N-Panel buttons and Python

**Icon System Test**: SUCCESS
- GPU overlay rendering working in standalone test
- Body stick figure, hand outline, head outline all render
- Modal operator handles hover highlighting and click cycling
- Press ESC to exit test mode

---

## Hand Panel Implementation - 2026-02-17

### Files Created/Modified

**New Files:**
- `posebridge/extract_hands.py` - Hand geometry extraction and bone position calculation
- `posebridge/test_hand_integration.py` - Consolidated test script
- `posebridge/icons.py` - Icon shape definitions and GPU drawing functions
- `posebridge/test_icons.py` - Standalone icon preview/test script
- `posebridge/extract_icon_shape.py` - Extract icon shapes from Blender meshes

**Modified Files:**
- `posebridge/core.py` - Added `active_panel` EnumProperty
- `posebridge/drawing.py` - Filter control points by active panel
- `posebridge/panel_ui.py` - View switching UI and operator

### Hand Control Points (42 total)

**Per Hand (21 points):**
```
Individual Joints (Circles) - 15:
  Thumb:  Thumb1, Thumb2, Thumb3
  Index:  Index1, Index2, Index3
  Mid:    Mid1, Mid2, Mid3
  Ring:   Ring1, Ring2, Ring3
  Pinky:  Pinky1, Pinky2, Pinky3

Finger Groups (Diamonds) - 5:
  Thumb_group, Index_group, Mid_group, Ring_group, Pinky_group

Fist Control (Diamond) - 1:
  Hand_fist (curls all 15 finger bones)
```

### Key Code Changes

**core.py - Active Panel Property:**
```python
active_panel: EnumProperty(
    name="Active Panel",
    items=[
        ('body', 'Body', 'Full body panel'),
        ('hands', 'Hands', 'Both hands detail panel'),
        ('face', 'Face', 'Face detail panel'),
    ],
    default='body'
)
```

**drawing.py - Control Point Filtering:**
```python
# Get active panel view
active_panel = settings.active_panel

# Draw each fixed control point that matches the active panel
for cp in fixed_control_points:
    cp_panel = cp.panel_view if cp.panel_view else 'body'
    if cp_panel != active_panel:
        continue  # Skip points not in current view
```

**extract_hands.py - Thumb Group Fix:**
```python
# For thumb group, use mid-point (head is deep in palm)
if finger_name == 'Thumb':
    bone_positions[group_key] = transform_point(bone_mid_world)
else:
    bone_positions[group_key] = transform_point(bone_head_world)
```

---

## Icon System for View Switching - 2026-02-17

### Overview
DAZ PowerPose-style icons in viewport corner for switching between Body/Hands/Face views.

### Architecture

**icons.py:**
- Icon shape definitions in normalized 0-1 coordinates
- `ICON_BODY` - stick figure with head circle and body lines
- `ICON_HAND` - hand outline (LINE_STRIP)
- `ICON_HEAD` - head/face outline (LINE_STRIP)
- Drawing functions: `draw_body_icon()`, `draw_icon_outline()`, `draw_icon_filled()`
- `ViewSwitcherIcons` class for positioning and hit testing

**test_icons.py:**
- Standalone GPU overlay test (works in blank scene)
- Modal operator for hover/click interaction
- Press ESC to stop and remove overlay

**extract_icon_shape.py:**
- Extracts icon shapes from selected mesh
- Normalizes vertices to 0-1 range
- Orders vertices by edge connectivity for LINE_STRIP
- Outputs Python code ready to paste into icons.py

### Icon Shape Workflow
1. Create flat mesh on XY plane (Z=0) in Blender
2. Draw icon outline with vertices/edges
3. Work in Top view (Numpad 7)
4. Keep shape within square area
5. Select mesh and run `extract_icon_shape.py`
6. Copy output from System Console to icons.py

### Pending Work
- User designing custom icon shapes
- Wire `icons.py` into main `drawing.py`
- Add click handling in `interaction.py` to switch views
- Update `TESTING_POSEBRIDGE.md` with icon testing steps

### Testing Documentation Updates

**TESTING_POSEBRIDGE.md** updated with Steps 11-14 for hand panel:
- Step 11: Generate Hand Panel (run test_hand_integration.py)
- Step 12: Switch to Hands View (N-Panel or Python)
- Step 13: Test Hand Control Points (circles, diamonds, fist)
- Step 14: Switch Back to Body View

**Success Criteria** updated with:
- Hand panel visual checks (42 control points, mesh visibility)
- View switching checks (buttons, camera, filtering)
- Fixed positioning checks (points never move with bones)

---

## Previous Session: 2026-02-16

### Active Work
- Setting up four-file documentation system (CLAUDE.md, INDEX.md, SCRATCHPAD.md, TODO.md)
- Establishing project organization for better AI assistant collaboration
- **Planning BlenDAZ N-Panel** - Centralized setup and configuration UI

### Goals Completed
- [x] Update CLAUDE.md with documentation system guidelines
- [x] Create INDEX.md with complete file reference
- [x] Create SCRATCHPAD.md (this file)
- [x] Create TODO.md with current tasks and roadmap
- [x] Plan BlenDAZ N-Panel UI structure (draft in this file)
- [x] Design Hand Panel control points (21 per hand: 15 circles + 5 finger groups + 1 fist)
- [x] Test standin mesh reuse (SUCCESS - GP survives visible mesh)

### Session Summary - 2026-02-16
**Accomplished:**
1. Confirmed standin mesh approach works (reuse `_LineArt_Copy`, don't hide, strip materials)
2. Designed hand panel with full control hierarchy (circles + finger groups + fist group)
3. Documented N-Panel structure, init script consolidation, rollback procedures
4. Clarified group node behavior (each bone rotates around own origin)

**Next Session - Ready to Implement:**
1. **Init script** - Consolidate all setup steps into single script
2. **Standin changes** - Modify outline_generator_lineart.py (keep visible, rename, strip materials)
3. **Hand cameras** - Add `PB_Camera_LeftHand`, `PB_Camera_RightHand` generation
4. **Hand control points** - Define 21-point set in control_points.py

---

## BlenDAZ N-Panel Planning - 2026-02-16

### Overview
Create a unified N-Panel for BlenDAZ setup and configuration. Currently posebridge setup is scattered across scripts - need a proper UI for initialization and options.

### Panel Structure (Draft)

```
┌─────────────────────────────────┐
│ BlenDAZ Setup                   │
├─────────────────────────────────┤
│ Figure: [Genesis8Female    ▼]   │
│ Status: ✓ Initialized           │
│                                 │
│ [Initialize Selected Figure]    │
│ [Reset / Cleanup]               │
├─────────────────────────────────┤
│ ▼ Standin Mesh                  │
│   ☑ Enable Standin              │
│   Display: [Solid ▼] (matcap)   │
│   [Regenerate Standin]          │
├─────────────────────────────────┤
│ ▼ Outline                       │
│   ☑ Enable Outline              │
│   Thickness: [====●====] 4      │
│   Color: [■ Cyan]               │
│   [Regenerate Outline]          │
├─────────────────────────────────┤
│ ▼ Control Points                │
│   Size: [====●====] 8           │
│   Color: [■ Cyan]               │
│   Hover Color: [■ Yellow]       │
├─────────────────────────────────┤
│ ▼ Advanced                      │
│   Z Offset: [-50.0] m           │
│   Camera Distance: [12.0] m     │
│   [Move Setup to Offset]        │
└─────────────────────────────────┘
```

### Key Decisions

**1. Initialization Flow**
- User selects figure (mesh or armature)
- Clicks "Initialize"
- Check: Is armature in rest pose? If not, warn/prompt
- Creates: Standin mesh, GP outline, camera, light, control points
- Moves everything to Z offset (-50m)

**2. Standin Mesh (NEW)**
- Reuse existing `_LineArt_Copy` mesh (confirmed GP survives this)
- Rename to `[FigureName]_Standin`
- Strip all materials (rely on viewport matcap)
- Keep visible (don't hide like we do now)
- Static rest pose captured at init time

**3. Outline Options (NEW)**
- Enable/disable: Toggle GP object visibility
- Thickness: GP Thickness modifier (can adjust live post-bake)
- Color: Modify GP material color (can adjust live)
- Currently cyan, user can customize

**4. What Stays vs. What's Regenerated**
- Standin/Outline: Created once at init, options modify existing objects
- Regenerate buttons: For when user wants to start fresh
- Control points: Captured at init, positions are fixed (Phase 1)

### Implementation Notes

**Settings Storage**
- Add properties to `PoseBridgeSettings` in `posebridge/core.py`:
  - `outline_enabled: BoolProperty`
  - `outline_thickness: FloatProperty`
  - `outline_color: FloatVectorProperty(subtype='COLOR')`
  - `standin_enabled: BoolProperty`
  - `z_offset: FloatProperty`
  - etc.

**Outline Thickness Post-Bake**
- After Line Art modifier is applied, add a GP Thickness modifier
- This modifier CAN be adjusted live without regenerating
- Link modifier value to `outline_thickness` property

**Outline Color Post-Bake**
- GP material color can be changed anytime
- Link material color to `outline_color` property
- Use driver or update callback

**Panel Location**
- 3D Viewport > Sidebar (N-Panel) > "BlenDAZ" tab
- Or could be subtab under existing "PoseBridge" tab

### Open Questions

1. **Single panel vs. tabs?** - One "BlenDAZ" panel, or separate "Setup" and "PoseBridge" tabs?
2. **Multi-character support?** - Dropdown to select which figure to configure?
3. **Presets?** - Save/load outline+standin configurations?
4. **Auto-detect Genesis version?** - Or manual selection?

### Test Results - 2026-02-16

**Standin Mesh Reuse Test**: ✅ SUCCESS
- Unhid `Fey Mesh_LineArt_Copy` using `bpy.data.objects["..."].hide_viewport = False`
- GP outline survived having source mesh visible
- Mesh displays nicely with viewport matcap
- Control points render correctly over mesh
- Outline is subtle but visible over solid mesh

**Conclusion**: Can reuse LineArt_Copy as Standin - no need for second mesh copy

---

## Hands & Face Detail Panels - 2026-02-16

### Reference
DAZ PowerPose style layout with:
- Full body view (small, corner thumbnail)
- Two large hand views (left/right)
- Face detail view
- Switchable between views

### Hand Panel Design

**Camera Setup:**
- Two additional cameras: `PB_Camera_LeftHand`, `PB_Camera_RightHand`
- Orthographic, positioned to view hands on standin mesh
- Same Z offset (-50m) as main body setup
- View angle: back-of-hand (dorsal view) - matches DAZ and natural viewing

**Control Points (per hand, 21 points):**

*Individual Joint Controls (Circles) - 15 per hand:*
```
Thumb:   lThumb1, lThumb2, lThumb3 (3)
Index:   lIndex1, lIndex2, lIndex3 (3)
Mid:     lMid1, lMid2, lMid3 (3)
Ring:    lRing1, lRing2, lRing3 (3)
Pinky:   lPinky1, lPinky2, lPinky3 (3)
```

*Finger Group Controls (Diamonds) - 5 per hand:*
```
lThumb_group:  [lThumb1, lThumb2, lThumb3] - curl whole thumb
lIndex_group:  [lIndex1, lIndex2, lIndex3] - curl whole index finger
lMid_group:    [lMid1, lMid2, lMid3] - curl whole middle finger
lRing_group:   [lRing1, lRing2, lRing3] - curl whole ring finger
lPinky_group:  [lPinky1, lPinky2, lPinky3] - curl whole pinky
```

*Fist Control (Diamond) - 1 per hand:*
```
lHand_fist:    [ALL 15 finger bones] - curl all fingers into fist
```

**Total: 21 per hand × 2 = 42 hand control points**

**Control Hierarchy:**
- Circle = individual joint rotation
- Finger diamond = curl entire finger (all 3 joints rotate around own origins)
- Fist diamond = curl ALL fingers (all 15 bones rotate around own origins)

**Control Point Generation:**
- Procedural, like full-body view
- Capture bone head positions projected to hand camera view
- Group nodes positioned at base of each finger (finger groups) and palm center (fist)

### Face Panel Design

**Camera Setup:**
- `PB_Camera_Face` - positioned in front of face on standin
- Orthographic, framed on head/neck area

**Control Points (TBD):**
- Eyes: lEye, rEye (look direction)
- Eyelids: upper/lower for each eye
- Brow: inner, mid, outer for each side
- Jaw: open/close
- Mouth corners, lips
- Nose?

*Note: Genesis 8/9 facial rig has MANY bones - need to decide which are most useful for posing vs. expression*

### View Switching

**UI Options:**
1. **Buttons in N-Panel**: [Body] [L Hand] [R Hand] [Face]
2. **Dropdown**: View: [Body ▼]
3. **Keyboard shortcuts**: 1=Body, 2=LHand, 3=RHand, 4=Face

**Implementation:**
- Store current view mode in settings
- Switch camera in the posebridge viewport
- Load appropriate control point set for that view
- Draw handler checks current view mode

### Open Questions

1. **Hand camera angle** - Dorsal (back of hand) vs palmar (palm)? Dorsal seems more natural.
2. **Face bones** - Which subset? Full facial rig is overwhelming.
3. **Viewport switching** - Change camera in existing viewport, or show/hide different viewports?
4. **Control point persistence** - Generate all at init, or lazily when switching to that view?

---

## Init Script Consolidation - 2026-02-16

### Goal
Single script that runs all posebridge initialization steps from TESTING_POSEBRIDGE.md

### Current Steps to Consolidate
1. Register PoseBridge (path + import + register)
2. Generate outline (outline_generator_lineart.py)
3. Move setup to Z -50m
4. Recapture control points
5. Start PoseBridge (enable mode + modal)

### New: Standin Mesh Changes
- Don't hide `_LineArt_Copy` mesh
- Rename to `[FigureName]_Standin`
- Strip all materials from standin

### Rollback Info
If standin changes break things, to restore original behavior in `outline_generator_lineart.py`:

**Lines ~633-636 (cleanup section):**
```python
# ORIGINAL - hides mesh:
mesh_copy.hide_viewport = True
mesh_copy.hide_render = True

# NEW - keeps visible, strips materials:
mesh_copy.hide_viewport = False  # Keep visible as standin
mesh_copy.hide_render = True     # Still hide from renders
# Strip materials
mesh_copy.data.materials.clear()
# Rename
mesh_copy.name = f"{mesh_obj.name}_Standin"
```

**To rollback**: Restore `hide_viewport = True` and remove material stripping/rename

### Notes & Observations
- Found that [daz_bone_select.py](daz_bone_select.py) is 267KB - unusually large and may benefit from refactoring
- [posebridge/scratchpad.md](posebridge/scratchpad.md) at 46KB is approaching archive threshold (50-75KB)
- Project has excellent documentation of bugs, fixes, and design decisions
- Clear separation between PoseBridge (visual posing) and PoseBlend (pose blending) modules

---

## Feature Development Log

### Documentation System Setup - 2026-02-16
**Status**: 🟡 In Progress

**Goal**: Establish four-file documentation system to improve project organization and AI assistant effectiveness

**Approach**:
1. Update CLAUDE.md with references to INDEX.md, SCRATCHPAD.md, TODO.md
2. Create comprehensive INDEX.md cataloging all files
3. Create SCRATCHPAD.md for development journal
4. Create TODO.md for task tracking

**What Works**:
- ✅ CLAUDE.md already had good project context and philosophy
- ✅ PROJECT_SETUP_GUIDE.md provides excellent template
- ✅ INDEX.md created with comprehensive file catalog
- ✅ Clear categorization of files by function

**Decisions Made**:
- Organized INDEX.md by functional areas (Core Tools, PoseBridge, PoseBlend) rather than file type
- Included "Quick Lookup" section for common questions
- Added file size statistics and noted that daz_bone_select.py may need refactoring
- Added cross-references between documentation files

**Next Steps**:
- [ ] Create TODO.md to track current work and backlog
- [ ] Consider archiving posebridge/scratchpad.md
- [ ] Consider refactoring daz_bone_select.py (267KB is very large)

**Related Files**:
- [CLAUDE.md](CLAUDE.md) - Updated with documentation system section
- [INDEX.md](INDEX.md) - New comprehensive file reference
- [PROJECT_SETUP_GUIDE.md](PROJECT_SETUP_GUIDE.md) - Template used for setup

---

## Bug Tracker

*No active bugs being tracked in this session*

---

## Technical Observations

### Project Structure
The BlenDAZ project has a clean separation of concerns:
- **Core utilities** ([daz_shared_utils.py](daz_shared_utils.py)) provide shared functionality
- **PoseBridge** focuses on visual, direct-manipulation posing with fixed control points
- **PoseBlend** focuses on pose blending and grid-based pose selection
- Both modules share similar architectures (core.py, drawing.py, interaction.py, panel_ui.py)

### Documentation Quality
- Extensive bug documentation with detailed explanations (BUG_*.md, FIX_*.md)
- PowerPose feature well-documented across multiple files
- Design decisions captured in DESIGN.md and IMPLEMENTATION.md files
- Good separation between user guides and technical documentation

### Development Workflow
- Reload scripts ([reload_daz_bone_select.py](reload_daz_bone_select.py)) for hot-reloading during development
- Testing checklists ([TESTING_POSEBRIDGE.md](posebridge/TESTING_POSEBRIDGE.md)) for structured testing
- Quickstart scripts for rapid testing

---

## Ideas & Future Considerations

### Icon System Integration - NEXT UP
**Description**: Wire icons.py into main drawing.py and add click handling
**Status**: Waiting for user to design custom icon shapes
**When Ready**:
1. Import icons.py in drawing.py
2. Call ViewSwitcherIcons.draw_all() in draw handler
3. Add hit testing in interaction.py modal operator
4. Switch active_panel when icon clicked
5. Test full workflow body → hands → face → body

### Module Refactoring
**Description**: Split daz_bone_select.py (267KB) into smaller, more maintainable modules
**Why**: Easier to navigate, test, and maintain; follows single responsibility principle
**Challenges**: Need to identify logical boundaries, ensure no circular dependencies

### Scratchpad Archiving Process
**Description**: Establish regular archiving schedule for scratchpad files
**Why**: Keep scratchpads manageable and focused on current work
**Next Action**: Archive posebridge/scratchpad.md which is at 46KB

### Documentation Templates
**Description**: Create templates for new modules based on posebridge/poseblend structure
**Why**: Maintain consistency across modules, speed up new module creation
**Includes**: Standard files like __init__.py, core.py, drawing.py, interaction.py, panel_ui.py

---

## Quick Reference

### Useful Commands

```bash
# List all Python files
find . -name "*.py" -type f

# List all documentation files
find . -name "*.md" -type f

# Check file sizes
ls -lh *.py

# Create scratchpad archive directory
mkdir -p scratchpad_archive
```

### Important Patterns

**Blender Addon Structure**:
- `__init__.py` - Registration and module initialization
- `core.py` - PropertyGroups and data structures
- `drawing.py` - GPU rendering with draw handlers
- `interaction.py` - Modal operators for user interaction
- `panel_ui.py` - UI panels and controls

**Modal Operator Pattern**:
```python
def modal(self, context, event):
    if event.type == 'MOUSEMOVE':
        # Handle mouse movement
        return {'RUNNING_MODAL'}
    elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
        # Handle click
        return {'FINISHED'}
    elif event.type in {'RIGHTMOUSE', 'ESC'}:
        # Cancel
        return {'CANCELLED'}
    return {'PASS_THROUGH'}
```

**GPU Draw Handler Registration**:
```python
handler = bpy.types.SpaceView3D.draw_handler_add(
    draw_callback,
    (),
    'WINDOW',
    'POST_PIXEL'
)
```

**GPU Icon Drawing (LINE_STRIP)**:
```python
shader = gpu.shader.from_builtin('UNIFORM_COLOR')
batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": vertices})
gpu.state.blend_set('ALPHA')
gpu.state.line_width_set(2.0)
shader.bind()
shader.uniform_float("color", (0.0, 0.8, 1.0, 1.0))  # Cyan
batch.draw(shader)
```

**View Switching**:
```python
# In panel_ui.py operator
bpy.context.scene.posebridge_settings.active_panel = 'hands'

# In drawing.py filtering
cp_panel = cp.panel_view if cp.panel_view else 'body'
if cp_panel != settings.active_panel:
    continue
```

---

## IK Second Drag Bug Fix - 2026-02-17

### Problem
On the second IK drag in DEBUG mode, the .ik bones were floating far away from the actual arm mesh instead of overlaying the DAZ bones. This caused the arm to snap straight and not follow the mouse correctly.

### Root Cause
In `create_ik_chain()` cleanup code (lines 218-256), when cleaning up the old IK chain:
1. We cached `rotation_quaternion` values from DAZ bones
2. We removed Copy Rotation constraints
3. We deleted .ik bones in EDIT mode
4. We restored cached rotations

**The bug**: Copy Rotation constraints REPLACE bone rotation but don't modify `rotation_quaternion`. When we cached rotations at step 1, we were caching the BASE rotation (pre-first-drag), not the constraint-applied rotation. When we removed constraints at step 2, bones snapped back to their original pose. Restoring the same cached values didn't help.

Then when we captured `posed_positions` for the new .ik bones, we captured the snapped-back (wrong) positions.

### Solution
Instead of cache/restore, we now BAKE constraint results into actual bone rotations BEFORE removing constraints:

```python
# Get evaluated bone's final matrix (includes constraint effects)
bone_eval = armature_eval.pose.bones[pose_bone.name]

# Extract local rotation from final matrix
if pose_bone.parent:
    local_matrix = parent_eval.matrix.inverted() @ bone_eval.matrix
else:
    local_matrix = bone_eval.matrix

loc, rot, scale = local_matrix.decompose()

# Set bone's actual rotation to match constraint result
pose_bone.rotation_quaternion = rot
```

After baking, removing the constraint doesn't cause snap-back because the bone's own rotation now matches what the constraint was producing.

### Files Modified
- `daz_bone_select.py`: Lines 218-278 (cleanup code in create_ik_chain)

### Key Insight
Copy Rotation constraints are "live" - they affect the final bone matrix but don't modify `pose_bone.rotation_quaternion`. To preserve constraint results after removing the constraint, you must decompose the final matrix and write the rotation back to the bone's rotation property.

---

## Archive (Completed Work)

### ✅ Hand Panel Core Implementation - 2026-02-17
**Summary**: Implemented hand panel with 42 control points (21 per hand), view switching, and control point filtering
**Files Created**: extract_hands.py, test_hand_integration.py, icons.py, test_icons.py, extract_icon_shape.py
**Files Modified**: core.py, drawing.py, panel_ui.py, TESTING_POSEBRIDGE.md
**Key Features**:
- Hand geometry extraction from standin mesh using vertex groups
- Bone position calculation with proper transforms
- Finger group diamonds and fist control diamond
- View switching between body/hands/face panels
- Control point filtering by panel_view property
**Lessons Learned**:
- Thumb1 bone head is deep in palm - use mid-point for thumb group
- Normalized 0-1 coordinates work well for icon shapes
- Edge-connectivity ordering essential for LINE_STRIP drawing

### ✅ Documentation System Setup - 2026-02-16
**Summary**: Established four-file documentation system with CLAUDE.md, INDEX.md, SCRATCHPAD.md, TODO.md
**Lessons Learned**:
- Comprehensive INDEX.md requires understanding entire project structure
- Cross-references between docs improve discoverability
- File size statistics help identify potential maintenance issues
