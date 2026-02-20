# PoseBridge Technical Reference

Hard-won knowledge about PowerPose-style rotation controls, DAZ bone architecture, and the PoseBridge control panel system. This document captures what works, what doesn't, and why.

**Last Updated**: 2026-02-19

---

## Table of Contents

1. [DAZ Studio PowerPose Architecture](#daz-studio-powerpose-architecture)
2. [PoseBridge Rotation System](#posebridge-rotation-system)
3. [DAZ Genesis 8 Bone Architecture](#daz-genesis-8-bone-architecture)
4. [Control Point System](#control-point-system)
5. [Research Findings](#research-findings)
6. [Troubleshooting Guide](#troubleshooting-guide)
7. [Code Reference](#code-reference)

---

## DAZ Studio PowerPose Architecture

> Research conducted 2026-02-19 via web search of DAZ 3D forums, documentation, and community template creators.

### Template Format (DSX)

PowerPose templates are XML-based `.dsx` files (Genesis 8+ uses encrypted `.dse`). Each control point is a `<node_data>` element:

```xml
<node_data>
  <x>220</x>              <!-- 2D panel position -->
  <y>292</y>
  <node_label>Left Thigh</node_label>
  <lmb_horiz_prop>yrot</lmb_horiz_prop>     <!-- LMB horizontal → Y rotation -->
  <lmb_vert_prop>xrot</lmb_vert_prop>       <!-- LMB vertical → X rotation -->
  <rmb_horiz_prop>zrot</rmb_horiz_prop>     <!-- RMB horizontal → Z rotation -->
  <rmb_horiz_sign>neg</rmb_horiz_sign>      <!-- optional inversion -->
  <rmb_vert_prop>xrot</rmb_vert_prop>       <!-- RMB vertical → X rotation -->
</node_data>
```

### Key Insight: Euler Angle Manipulation, Not Quaternion Trackball

PowerPose does **NOT** use quaternion trackball rotation for individual control nodes. Each mouse direction simply **adds/subtracts a delta to a single Euler angle property** (`xrot`, `yrot`, or `zrot`).

```
mouse_delta_pixels × sensitivity → added to bone.xrot / .yrot / .zrot
```

This is direct per-axis Euler angle manipulation. The "trackball" behavior mentioned in DAZ documentation refers only to the full-body manipulation mode, not individual control nodes.

### Control Point Types

| Type | Shape | Behavior |
|------|-------|----------|
| **Node Points** | Round dots | Drive raw transforms via General→Transforms→Rotation |
| **Property Points** | Diamonds | Can operate on any property type (rotation, translation, morphs) |
| **Group Nodes** | Varies | Multiple bones controlled simultaneously for coordinated movements |

### Per-Bone Rotation Orders (Critical for Gimbal Avoidance)

DAZ assigns different Euler angle rotation orders to different bones to minimize gimbal lock in their normal range of motion:

| Bone | Rotation Order | Why This Order |
|------|---------------|----------------|
| lThighBend, pelvis | **YZX** | Y (twist) first, Z (spread) second, X (bend) last. Gimbal lock at Z=90 which rarely happens for leg spread |
| lShldrBend | **XYZ** | Standard order, works for shoulder range |
| lForearmBend | **XZY** | Optimized for elbow hinge motion |

**Consequence**: With **YZX** on ThighBend, DAZ safely uses independent Euler angles because:
1. Y (twist) is handled by ThighTwist, never written to ThighBend
2. Z (spread) rarely approaches 90 degrees
3. X (forward/back bend) is the outermost gimbal and freely ranges

### Template Encryption

- Genesis 1-2: Unencrypted `.dsx` files, readable and editable
- Genesis 3: No official template (community workarounds via bipedDynamics.dsx)
- Genesis 8+: Encrypted `.dse` format, not readable or editable
- Community alternative templates exist (NorthOf45) with explicit node-to-bone mappings

### bipedDynamics.dsx

A fallback mapping file used when no explicit template exists for a figure. Contains regex patterns to match generic template control names to figure-specific bone names. Only affects figures without a dedicated template.

---

## PoseBridge Rotation System

### Architecture Overview

PoseBridge uses **quaternion rotation** internally (not Euler angles like PowerPose), applied per-frame from accumulated mouse delta since drag start.

```
rotation = Quaternion(axis_vector, delta_pixels × sensitivity) @ initial_quaternion
```

Each frame recalculates from scratch (delta from drag start), not incremental. This prevents drift accumulation.

### Single-Bone Rotation Flow

1. User clicks a control point → `start_ik_drag()` captures initial quaternion
2. Mouse move → `update_rotation()` calculates total delta from drag start
3. Per-bone axis mapping selects which axis (X/Y/Z) for horizontal and vertical drag
4. Rotation quaternion built per-axis, applied as `new_rot @ initial_quat`
5. Twist bone routing: Y-axis rotations on bend bones redirected to corresponding twist bone
6. Y-lock: ThighBend swing-twist decomposition strips any Y component
7. Constraint enforcement: `view_layer.update()` evaluates LIMIT_ROTATION constraints
8. Mouse release → `end_rotation()` with optional depsgraph readback for constrained result

**Key code path**: `daz_bone_select.py` → `update_rotation()` (~line 4800-5110)

### Multi-Bone (Group) Rotation Flow

1. User clicks a diamond/group control → `start_ik_drag()` captures initial quaternions for ALL bones in group
2. Group ID stored in `_rotation_group_id` for axis lookup
3. Mouse move → `update_multi_bone_rotation()` calculates delta
4. Per-GROUP axis mapping selects axes (not per-bone)
5. Per-axis quaternions built: `rot_x`, `rot_y`, `rot_z`
6. Twist bone filtering: Y-axis rotation → all bones, X/Z → non-twist bones only
7. Combined rotation applied: `combined_rot @ initial_quat[i]` per bone

**Key code path**: `daz_bone_select.py` → `update_multi_bone_rotation()` (~line 5168-5300)

### 4-Way Control Scheme

Every control point has 4 mouse-direction-to-axis mappings:

```python
'controls': {
    'lmb_horiz': 'Z',   # Left mouse button + horizontal drag
    'lmb_vert': 'X',    # Left mouse button + vertical drag
    'rmb_horiz': 'Y',   # Right mouse button + horizontal drag
    'rmb_vert': None     # Right mouse button + vertical drag (disabled)
}
```

This directly mirrors PowerPose's DSX template format (`lmb_horiz_prop`, `lmb_vert_prop`, etc.).

### Twist Bone Filtering (Multi-Bone Groups)

When a group contains both bend and twist bones, rotations are filtered:

| Rotation Axis | Applied To | Reason |
|--------------|-----------|--------|
| **Y** (twist) | ALL bones in group | Twist is along bone length for all DAZ bones |
| **X** (bend) | Non-twist bones only | Bend bones handle forward/back |
| **Z** (side) | Non-twist bones only | Bend bones handle side-to-side |

```python
is_twist_bone = 'twist' in bone.name.lower()

if rot_y:
    combined_rot = rot_y @ combined_rot  # Always applied

if not is_twist_bone:
    if rot_x:
        combined_rot = rot_x @ combined_rot  # Bend bones only
    if rot_z:
        combined_rot = rot_z @ combined_rot  # Bend bones only
```

### Swing-Twist Decomposition (Y-Lock)

For ThighBend, any Y rotation that leaks in from quaternion composition is stripped each frame:

```python
# q = swing × twist (where twist is around Y)
# Keep only swing component → Y is always 0

swing_quat, twist_quat = decompose_swing_twist(current_quat, 'Y')
bone.rotation_quaternion = swing_quat  # Y-locked result
```

**Mathematical basis**: Project quaternion onto Y axis (keep w,y components, zero x,z), normalize, then `swing = q × twist⁻¹`.

**Location**: `daz_shared_utils.py:decompose_swing_twist()`, called from `update_rotation()` ~line 5087

### Twist Bone Routing

When a single-bone control targets a bend bone, Y-axis rotation is automatically redirected to the corresponding twist bone:

| Control | Y-Axis Target | Routing |
|---------|--------------|---------|
| lThighBend (LMB horiz) | lThighTwist | `horiz_target_bone` swap at ~line 4931 |
| lShldrBend (RMB vert) | lShldrTwist | `vert_target_bone` swap at ~line 4910 |
| lForearmBend (LMB vert) | lForearmTwist | `vert_target_bone` swap at ~line 4921 |

### Right-Side Mirroring

Left-side controls are defined as the "canonical" direction. Right-side bones automatically invert both horizontal and vertical controls:

```python
if bone.name.startswith('r') and 'collar' not in bone_lower:
    horiz_invert = not horiz_invert
    vert_invert = not vert_invert
```

### Constraint Enforcement

When `enforce_constraints` is enabled (default: True), `view_layer.update()` is called after each rotation frame. This evaluates Blender's LIMIT_ROTATION constraints imported by Diffeomorphic, clamping bone rotation to anatomical limits in real-time.

On drag release, `end_rotation()` reads back the constrained result from the evaluated depsgraph and writes it to the bone's `rotation_quaternion`, baking the constrained pose.

---

## DAZ Genesis 8 Bone Architecture

### Dual Bend/Twist Bone System

DAZ separates rotation responsibilities into paired bones. This is the fundamental architectural constraint that all rotation code must respect.

| Bend Bone | Twist Bone | Bend Allowed Axes | Twist Axis |
|-----------|------------|-------------------|------------|
| lThighBend | lThighTwist | X (forward/back), Z (spread) | Y only |
| lShin | (none) | X only (hinge) | - |
| lShldrBend | lShldrTwist | X (swing), Z (raise) | Y only |
| lForearmBend | lForearmTwist | X only (hinge) | Y only |

**Critical Rule**: Bend bones should NEVER accumulate Y rotation. All twist belongs on the corresponding Twist bone.

### Bone Naming Patterns (Diffeomorphic Import)

```
Limbs:
  l/rShldrBend, l/rShldrTwist
  l/rForearmBend, l/rForearmTwist
  l/rThighBend, l/rThighTwist
  l/rShin (no twist bone - hinge joint)
  l/rFoot, l/rToe
  l/rCollar

Spine:
  pelvis, hip
  abdomenLower, abdomenUpper
  chestLower, chestUpper
  neckLower, neckUpper
  head

Hands:
  l/rHand
  l/rCarpal1-4
  l/rThumb1-3, l/rIndex1-3, l/rMid1-3, l/rRing1-3, l/rPinky1-3
```

### Bone Rotation Modes

DAZ bones imported via Diffeomorphic may use either Quaternion or Euler rotation modes. Always check before setting:

```python
if bone.rotation_mode == 'QUATERNION':
    bone.rotation_quaternion = rot
else:
    bone.rotation_euler = rot.to_euler(bone.rotation_mode)
```

---

## Control Point System

### Single-Bone Controls (Circles)

Standard round control points that map to one bone. Each has a 4-way control mapping. Some have twist bone routing for Y-axis redirects.

### Multi-Bone Group Controls (Diamonds)

Diamond-shaped controls that rotate multiple bones simultaneously. Defined with `bone_names` list and `reference_bone` for positioning.

| Group ID | Bones | Purpose |
|----------|-------|---------|
| neck_group | head, neckUpper, neckLower | Head/neck unified movement |
| torso_group | abdomenLower/Upper, chestLower/Upper | Spine articulation |
| shoulders_group | lCollar, rCollar, lShldrBend, rShldrBend | Bilateral shoulder movement |
| lArm_group | lShldrBend/Twist, lForearmBend/Twist | Full left arm |
| rArm_group | rShldrBend/Twist, rForearmBend/Twist | Full right arm |
| lLeg_group | lThighBend/Twist, lShin | Full left leg |
| rLeg_group | rThighBend/Twist, rShin | Full right leg |
| legs_group | Both legs (6 bones) | Bilateral leg movement |

### Current Group Axis Mappings

| Group | LMB Horiz | LMB Vert | RMB Horiz | RMB Vert |
|-------|-----------|----------|-----------|----------|
| neck_group | Y (turn) | X (nod) | Z (tilt, inv) | X |
| torso_group | Y (twist) | X (bend) | Z (lean, inv) | - |
| shoulders_group | Z (shrug) | X (forward) | Y (roll) | - |
| lArm/rArm_group | X (swing) | Z (raise) | Y (twist) | - |
| lLeg/rLeg_group | X (swing) | Z (raise) | Y (twist) | - |
| legs_group | X (swing) | Z (raise) | Y (twist) | - |

**Known Issue**: Leg group RMB horiz is currently Y (twist) but should probably be Z (spread) to match single-bone thigh behavior. See [Troubleshooting](#problem-leg-group-nodes-dont-match-single-bone-thigh-behavior).

### Control Point Positioning

Control points are captured from the T-pose armature bone positions, projected to 2D panel coordinates via the PoseBridge camera. Each definition includes:

- `position`: `'head'`, `'mid'`, or `'tail'` of the bone
- `offset`: 3D offset from bone position (for visual separation)
- `reference_bone`: For groups, which bone determines the control point position

### Source of Truth

Control points are defined in **two places** (must stay in sync):
1. `daz_shared_utils.py` → `get_genesis8_control_points()` — canonical definitions with all metadata
2. `daz_bone_select.py` → per-bone if/elif chains in `update_rotation()` — runtime axis mapping

---

## Research Findings

> Atomic, searchable findings. Format: **Finding → Evidence → Consequence → Solution**.

---

### PowerPose uses direct Euler angle manipulation, not quaternion trackball
**Finding**: Each PowerPose control node maps 4 mouse directions to 4 separate Euler angle properties (xrot, yrot, zrot, or translation). Mouse delta is directly added to the property value.
**Evidence**: DSX template `<node_data>` elements contain `lmb_horiz_prop`, `lmb_vert_prop`, `rmb_horiz_prop`, `rmb_vert_prop` each pointing to a single property like `xrot` or `zrot`. Forum template generator scripts confirm this structure.
**Consequence**: PowerPose avoids gimbal lock not through quaternion math, but through per-bone rotation order selection and never writing certain axes to certain bones.
**Solution**: PoseBridge can safely use quaternions (better overall) but must replicate the "never write Y to ThighBend" pattern. The Y-lock via swing-twist decomposition achieves this.
**Sources**: [PowerPose Templates Generator Script](https://www.daz3d.com/forums/discussion/334821/powerpose-templates-generator-script), [Alternative Templates](https://www.daz3d.com/forums/discussion/602891/alternative-powerpose-templates)

---

### DAZ bones use per-bone Euler rotation orders to avoid gimbal lock
**Finding**: Different bones use different Euler angle rotation orders optimized for their range of motion. ThighBend uses YZX, ShldrBend uses XYZ, ForearmBend uses XZY.
**Evidence**: Forum post by developer attempting DAZ↔Blender rotation conversion discovered that rotation order varies per bone, not globally.
**Consequence**: When converting between PoseBridge quaternions and DAZ Euler angles (for import/export), the correct rotation order per bone is critical. For PoseBridge's internal quaternion math, this is less relevant but explains WHY PowerPose can use Euler angles without gimbal issues.
**Solution**: For ThighBend (YZX): Y is applied first (twist, never used), Z second (spread, rarely near 90), X last (bend, free range). This order makes gimbal lock practically unreachable in normal posing.
**Source**: [Rotation Maths](https://www.daz3d.com/forums/discussion/503081/solved-rotation-maths)

---

### Genesis 8 PowerPose templates are encrypted (.dse)
**Finding**: Starting with Genesis 8, DAZ encrypts PowerPose template files, making it impossible to directly read the official axis mappings for each bone.
**Evidence**: Forum discussion confirms `.dsx` (readable) was replaced by `.dse` (encrypted). Community members created alternative unencrypted templates by following the Genesis 2 template format.
**Consequence**: We cannot directly verify the official DAZ thigh axis mappings. Our mappings are derived from anatomical reasoning, the DSX format documentation, and community template discussions.
**Solution**: Use the template format documentation and working behavior from Genesis 2 templates as reference. Iterate based on feel during testing.
**Source**: [Genesis 8 Templates Encrypted](https://www.daz3d.com/forums/discussion/178856/genesis-8-powerpose-templates-are-encrypted-dse-seriously)

---

### PowerPose ThighBend node never writes Y rotation
**Finding**: In PowerPose, the thigh control node routes Y-axis (twist) rotation to ThighTwist bone, never to ThighBend. This is why PowerPose doesn't have gimbal issues on thigh rotation despite using Euler angles.
**Evidence**: Genesis 3 bug report showed that when bipedDynamics couldn't find lThighBend/lThighTwist (only lThigh), the thigh node could only twist, not bend. This confirms the routing is explicit in the template.
**Consequence**: PoseBridge must replicate this routing. For single-bone thigh controls, Y-axis is redirected to ThighTwist. For group nodes containing ThighBend, the twist bone filtering (Y→all, X/Z→bend only) achieves the same effect.
**Solution**: Current implementation handles this correctly for single-bone rotation. Group nodes need the same Y-lock treatment for ThighBend that single-bone rotation has.
**Source**: [Power Pose Only Twisting](https://www.daz3d.com/forums/discussion/583576/power-pose-is-only-twisting-no-bend)

---

### Quaternion Y-lock via swing-twist decomposition prevents gimbal drift
**Finding**: Even when PoseBridge only applies X and Z quaternion rotations to ThighBend, the quaternion composition `rot_x @ rot_z @ initial_quat` can introduce tiny Y components due to the non-commutative nature of quaternion multiplication.
**Evidence**: Debug output showed small Y rotation values (0.1-2 degrees) accumulating on ThighBend after combined X+Z rotations. At extreme poses this could become significant.
**Consequence**: Simply avoiding Y-axis input is insufficient. Active Y-stripping is required after each rotation frame.
**Solution**: Apply swing-twist decomposition after every rotation update, keeping only the swing component: `swing, twist = decompose_swing_twist(quat, 'Y'); bone.rotation_quaternion = swing`
**See**: daz_shared_utils.py:151-206, daz_bone_select.py:5084-5098

---

### Multi-bone group rotation must filter twist bones from X/Z axes
**Finding**: When rotating a group of bones (e.g., leg group containing ThighBend + ThighTwist + Shin), X and Z rotations should only apply to non-twist bones. Twist bones should only receive Y rotation.
**Evidence**: Applying X rotation to ThighTwist would cause unnatural deformation since ThighTwist is a zero-length rotation helper bone, not a structural bone with meaningful X/Z range.
**Consequence**: All group rotation code must check for twist bones and filter accordingly.
**Solution**: `is_twist_bone = 'twist' in bone.name.lower()` — only apply `rot_y` to twist bones, apply all axes to non-twist bones.
**See**: daz_bone_select.py:5271-5293

---

## Troubleshooting Guide

### Problem: Thigh gimbal lock at extreme X+Z rotation

**Symptoms**: At extreme thigh rotation (e.g., leg raised high AND spread wide), rotation becomes unpredictable or "sticky".

**Cause**: Quaternion multiplication of large X and Z rotations introduces Y component. The Y-lock strips it, but at extreme angles the swing-twist decomposition becomes numerically less stable.

**Solutions**:
1. Y-lock is already applied each frame (daz_bone_select.py:5084-5098)
2. Quaternion continuity fix prevents flips (daz_bone_select.py:5074-5082)
3. For truly extreme poses, consider clamping ThighBend range (LIMIT_ROTATION constraint)

### Problem: Leg group nodes don't match single-bone thigh behavior

**Symptoms**: Single-bone thigh RMB horizontal does spread (Z), but leg group RMB horizontal does twist (Y).

**Cause**: Leg group axis mappings in `update_multi_bone_rotation()` were copied from arm group pattern. Arms use RMB horiz=Y (twist) which makes sense, but legs should use RMB horiz=Z (spread).

**Status**: Known issue, fix planned. Requires:
1. Change leg group RMB horiz from Y to Z in `update_multi_bone_rotation()`
2. Add RMB vert=X (same as LMB vert) for leg groups
3. Add Y-lock (swing-twist decomposition) for ThighBend bones within `update_multi_bone_rotation()`
4. Update `daz_shared_utils.py` control dicts to match

### Problem: Bilateral groups (shoulders, legs) don't mirror correctly

**Symptoms**: Both shoulders shrug the same direction, or both legs spread in the same direction.

**Cause**: `update_multi_bone_rotation()` applies the same rotation to all bones without L/R mirroring. For bilateral groups, right-side bones may need inverted Z-axis rotation.

**Status**: Known issue, needs testing after group node hookup is complete.

### Problem: Module caching prevents code changes from taking effect

**Symptoms**: Edited `daz_shared_utils.py` or `daz_bone_select.py` but behavior doesn't change.

**Cause**: Python's module caching in Blender. `importlib.reload()` doesn't work reliably for operator classes.

**Solutions**:
- `daz_shared_utils.py` changes: **Full Blender restart required**
- `daz_bone_select.py` changes: Use reload script or restart
- Use `exec(open(r"D:\dev\BlenDAZ\reload_daz_bone_select.py").read())` for hot reload

### Problem: Control point missing for a bone

**Symptoms**: Expected control point not visible on panel.

**Cause**: Bone name not found in armature (skipped by `initialize_control_points_for_character()`), or bone naming differs from expected Diffeomorphic import pattern.

**Solution**: Check `armature.pose.bones` for actual bone name. May need to add alternative name pattern to control point definition.

---

## Code Reference

### Key Files

| File | Purpose |
|------|---------|
| `daz_bone_select.py` | Main modal operator - single-bone and multi-bone rotation (~6800 lines) |
| `daz_shared_utils.py` | Control point definitions, swing-twist decomposition, rotation utilities |
| `core.py` | PropertyGroup definitions (PoseBridgeSettings, PoseBridgeControlPoint) |
| `panel_ui.py` | N-panel UI (settings, panel view selector) |
| `outline_generator_lineart.py` | Grease Pencil outline generation and control point capture |

### Key Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `update_rotation()` | daz_bone_select.py:~4800 | Single-bone rotation with 4-way controls |
| `update_multi_bone_rotation()` | daz_bone_select.py:~5168 | Multi-bone group rotation |
| `start_ik_drag()` | daz_bone_select.py:~3100 | Captures initial state at drag start |
| `end_rotation()` | daz_bone_select.py:~5300 | Cleanup, depsgraph readback |
| `decompose_swing_twist()` | daz_shared_utils.py:151 | Swing-twist separation for Y-lock |
| `apply_rotation_from_delta()` | daz_shared_utils.py:209 | Simplified rotation application |
| `get_genesis8_control_points()` | daz_shared_utils.py:246 | Control point definitions (source of truth) |
| `get_rotation_axis_from_control()` | daz_shared_utils.py:735 | Fast per-bone axis lookup |
| `enforce_rotation_limits()` | daz_shared_utils.py:53 | Anatomical limit clamping |
| `initialize_control_points_for_character()` | core.py:221 | Control point initialization from armature |

### Class Variables for Rotation State

```python
# Set at drag start, cleared at drag end
_rotation_bone = None               # Active pose bone (single-bone mode)
_rotation_bones = []                 # List of bones (multi-bone mode)
_rotation_initial_quat = None        # Initial quaternion (single-bone)
_rotation_initial_quats = []         # Initial quaternions (multi-bone)
_rotation_group_id = None            # Control point ID for group axis lookup
_rotation_mouse_button = 'LEFT'      # Which button started the drag
_rotation_initial_mouse = (0, 0)     # Mouse position at drag start
_twist_bone_initial_quats = {}       # Initial quaternions for twist bone routing
```

---

## Change Log

### 2026-02-19
- Created TECHNICAL_REFERENCE.md with PowerPose research findings
- Documented PoseBridge rotation architecture (single-bone and multi-bone flows)
- Documented 4-way control scheme mirroring PowerPose DSX template format
- Documented swing-twist decomposition for ThighBend Y-lock
- Documented twist bone filtering in multi-bone groups
- Documented per-bone Euler rotation orders from DAZ (YZX for thigh, XYZ for shoulder, XZY for forearm)
- Identified leg group axis mapping mismatch vs single-bone thigh controls
