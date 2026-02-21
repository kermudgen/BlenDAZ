# PoseBridge Technical Reference

Hard-won knowledge about PowerPose-style rotation controls, DAZ bone architecture, and the PoseBridge control panel system. This document captures what works, what doesn't, and why.

**Last Updated**: 2026-02-21

---

## Table of Contents

1. [DAZ Studio PowerPose Architecture](#daz-studio-powerpose-architecture)
2. [PoseBridge Rotation System](#posebridge-rotation-system)
3. [DAZ Genesis 8 Bone Architecture](#daz-genesis-8-bone-architecture)
4. [DSF Face Groups (Mesh Zone Detection)](#dsf-face-groups-mesh-zone-detection)
5. [Control Point System](#control-point-system)
6. [Research Findings](#research-findings)
7. [Troubleshooting Guide](#troubleshooting-guide)
8. [Code Reference](#code-reference)

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

## DSF Face Groups (Mesh Zone Detection)

### Overview

DAZ's DSF geometry files define **polygon_groups** — clean, hard-edged assignments where every polygon belongs to exactly one named body region. This replaces the fuzzy vertex-weight-based bone detection with crisp zone boundaries.

### DSF File Format

Genesis 8 DSF files are plain JSON (some may be gzipped). The geometry lives in `geometry_library[0]`:

```json
{
    "polygon_groups": { "count": 61, "values": ["lPectoral", "rPectoral", "Head", ...] },
    "polygon_material_groups": { "count": 16, "values": ["Torso", "Face", "Arms", "Legs", ...] },
    "polylist": { "count": 16368, "values": [[group_idx, material_idx, v0, v1, v2, v3], ...] },
    "vertices": { "count": 16556, "values": [[x, y, z], ...] }
}
```

Each polylist entry: `[polygon_group_index, material_group_index, vert0, vert1, vert2, (optional vert3)]`

### Genesis 8 Geometry Stats

| Variant | Vertices | Polygons | Face Groups | Same Geometry As |
|---------|----------|----------|-------------|-----------------|
| G8 Female | 16,556 | 16,368 | 61 | G8.1 Female |
| G8.1 Female | 16,556 | 16,368 | 61 | G8 Female |
| G8 Male | 16,384 | 16,196 | 61 | G8.1 Male |
| G8.1 Male | 16,384 | 16,196 | 61 | G8 Male |

### Face Group → Bone Name Mapping

DSF group names differ from DAZ bone names imported by Diffeomorphic:

| DSF Group | Bone Name | DSF Group | Bone Name |
|-----------|-----------|-----------|-----------|
| Head | head | Hip | pelvis |
| NeckUpper | neckUpper | lShoulder | lShldrBend |
| Neck | neckLower | rShoulder | rShldrBend |
| ChestUpper | chestUpper | lForearm | lForearmBend |
| Chest | chestLower | rForearm | rForearmBend |
| AbdomenUpper | abdomenUpper | lThigh | lThighBend |
| Abdomen | abdomenLower | rThigh | rThighBend |

Full mapping (61 groups) in `dsf_face_groups.py:DSF_GROUP_TO_BONE`.

### DSF File Resolution

The system locates DSF files through:
1. **DazUrl property** on armature/mesh (set by Diffeomorphic): e.g., `/data/DAZ%203D/Genesis%208/Female/Genesis8Female.dsf#Genesis8Female`
2. **Genesis version inference** from bone markers (`lPectoral`/`rPectoral` = G8) + gender detection
3. **Content directories** from `~/Documents/DAZ Importer/import_daz_settings.json` and `D:/Daz 3D/import-daz-paths.json`

#### Gender Resolution by Polygon Count

Name-based gender detection is unreliable (e.g., "Finn" doesn't contain "male"). Instead, `resolve_dsf_path()` tries both male and female DSF files and picks the one whose polygon count matches the Blender mesh:

| Gender | DSF Polygon Count | Blender Mesh Match |
|--------|------------------|--------------------|
| G8/8.1 Female | 16,368 | Exact match required |
| G8/8.1 Male | 16,196 | Exact match required |

If only one candidate exists, it's used directly. If both exist, polygon count is the tiebreaker.

### Lookup Architecture

```
INIT (once per armature activation):
  resolve_dsf_path() → parse JSON → validate polygon count matches Blender mesh
  → build face_group_map[polygon_index] = bone_name
  → build BVH tree from base mesh

RUNTIME (every hover):
  Fast path: face_index < base mesh polygon count → face_group_map[face_index]
  Slow path: SubSurf active → BVH find_nearest(hit_location) → base polygon index
  Fallback: face groups unavailable → existing vertex weight method
```

### Caching

`FaceGroupManager` uses a class-level cache keyed by `(mesh_data_name, polygon_count)`. The polygon count in the key prevents stale cache hits when the same mesh is modified (e.g., after merging geografts):

```python
key = (mesh_obj.data.name, len(mesh_obj.data.polygons))
```

Without the polygon count, a clean mesh and a grafted mesh with the same `data.name` would share a cache entry, producing wrong zone mappings.

### Highlight Rendering

The hover highlight overlay in `draw_highlight_callback()` has two rendering paths:

1. **Face group path** (clean zones): Iterates base mesh polygons, checks `face_group_map[poly_idx] in bones_set`, triangulates matching polygons
2. **Vertex weight path** (fallback): Original method aggregating vertex weights per polygon

The face group path produces clean, hard-edged zone boundaries. The vertex weight fallback produces the older jagged boundaries but works on any mesh.

### Edge Cases

| Scenario | Detection | Behavior |
|----------|-----------|----------|
| SubSurf modifier | face_index > base polygon count | BVH find_nearest on base mesh |
| Geograft merged | polygon count mismatch | vertex weight fallback |
| Missing DSF file | file not found | vertex weight fallback |
| User edited mesh | polygon count mismatch | vertex weight fallback |
| Stale cache | polygon count changed | new cache entry created |

### Key File

`dsf_face_groups.py` — DSF parser, path resolution, `DSF_GROUP_TO_BONE` mapping, `FaceGroupManager` class

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
| lLeg/rLeg_group | Y (twist) | X (forward) | Z (spread, inv) | X (forward) |
| legs_group | Y (twist) | X (forward) | Z (spread, inv) | X (forward) |

Leg groups use PowerPose "twist/forward" pattern (Y/X on LMB). Bilateral groups (legs_group, shoulders_group) have `mirror_axes: ['Z']` for automatic L/R inversion.

### Finger Group Axis Mappings

| Group | LMB Horiz | LMB Vert | RMB Horiz | RMB Vert |
|-------|-----------|----------|-----------|----------|
| lIndex_group, rIndex_group | Z (spread) | X (curl) | - | - |
| lMid_group, rMid_group | Z (spread) | X (curl) | - | - |
| lRing_group, rRing_group | Z (spread) | X (curl) | - | - |
| lPinky_group, rPinky_group | Z (spread) | X (curl) | - | - |
| lThumb_group, rThumb_group | Z (spread) | X (curl) | - | - |
| lHand_fist, rHand_fist | Z (spread) | X (curl) | - | - |

**Spread rules** (all finger groups):
- LMB horiz = spread (Z rotation on base joint only — bone name ends in '1')
- Joints 2 and 3 never receive Z rotation (spread only meaningful at metacarpophalangeal joint)
- Ring and Pinky spread in the **opposite** Z direction from Thumb/Index/Mid (fan-spread)
- Per-finger spread weight scales the Z angle to match anatomical range:

```python
FINGER_SPREAD_WEIGHTS = {
    'thumb': 0.5,   # Spreads in a different plane; moderate weight feels natural
    'index': 0.8,   # Spreads toward radial side
    'mid':   0.1,   # Anatomical reference finger — barely moves
    'ring':  0.7,   # Spreads toward ulnar side
    'pinky': 1.0,   # Outermost ulnar finger — full spread
}
```

Weight is applied via quaternion slerp from identity: `Quaternion().slerp(rot_z, weight)`.

**Curl rules** (all finger groups):
- LMB vert = curl (X rotation on all joints of each finger)
- Per-finger curl weight scales the X angle — thumb curls much slower than the other fingers:

```python
FINGER_CURL_WEIGHTS = {
    'thumb': 0.25,  # Observed ~0.25-0.3x rate vs other fingers in DAZ PowerPose; curling faster overshoots under the fist
    'index': 1.0,
    'mid':   1.0,
    'ring':  1.0,
    'pinky': 0.9,   # Slightly softer at the ulnar edge
}
```

Note: Genesis 8 PowerPose templates are encrypted (.dxe), so exact DAZ values are not readable. The thumb weight (0.25) is empirically matched by observing actual PowerPose fist curl behavior.

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

**Status**: FIXED (2026-02-20). Leg groups now use Y/X on LMB (twist/forward) and Z/X on RMB (spread/forward), matching PowerPose pattern. Controls dicts updated in `daz_shared_utils.py`, data-driven routing in `update_multi_bone_rotation()`.

### Problem: Bilateral groups (shoulders, legs) don't mirror correctly

**Status**: FIXED (2026-02-20). Added `mirror_axes: ['Z']` to legs_group and shoulders_group controls dicts. `update_multi_bone_rotation()` detects right-side bones (`name.startswith('r')` + uppercase) and inverts rotation on mirrored axes.

### Problem: Module caching prevents code changes from taking effect

**Symptoms**: Edited `daz_shared_utils.py` or `daz_bone_select.py` but behavior doesn't change.

**Cause**: Python's module caching in Blender. `importlib.reload()` doesn't work reliably for operator classes.

**Solutions**:
- `daz_shared_utils.py` changes: **Full Blender restart required**
- `daz_bone_select.py` changes: Use reload script or restart
- Use `exec(open(r"D:\dev\BlenDAZ\reload_daz_bone_select.py").read())` for hot reload

### Problem: Operator invoke fails from Text Editor ("Must be in 3D View")

**Status**: FIXED (2026-02-21). `start_posebridge.py` runs from Blender's Text Editor, but `invoke()` checks `context.area.type == 'VIEW_3D'`. Fixed by using `bpy.context.temp_override()` to invoke the operator in a 3D View area. Also added armature selection before invoke and fallback armature lookup from `posebridge_settings` in `invoke()`.

### Problem: Face groups not initializing (no [FaceGroups] console output)

**Status**: FIXED (2026-02-21). Two causes:
1. Text Editor context → `invoke()` returned CANCELLED before reaching face group init. Fixed with `temp_override`.
2. Active object not an armature → face group init skipped. Fixed with fallback to `posebridge_settings.active_armature_name`.

### Problem: Null region crash in check_hover()

**Status**: FIXED (2026-02-21). Modal operator receives events from non-3D-View areas where `context.region` is None. Added null guards: `if not region or mouse_x < region.x ...` at both hover check locations.

### Problem: Wrong DSF gender detected for character

**Status**: FIXED (2026-02-21). Name-based gender detection unreliable. `resolve_dsf_path()` now tries both male/female DSF files and picks the one whose polygon count matches the Blender mesh.

### Problem: Stale face group cache after mesh modification

**Status**: FIXED (2026-02-21). Cache key was just `mesh_data_name`. After merging geografts, same name but different mesh. Fixed by including polygon count in cache key: `(mesh_data_name, polygon_count)`.

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
| `dsf_face_groups.py` | DSF parser, face group mapping, FaceGroupManager for clean zone detection |
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
| `FaceGroupManager.get_or_create()` | dsf_face_groups.py | Cached face group manager factory |
| `FaceGroupManager.lookup_bone()` | dsf_face_groups.py | O(1)/O(log N) polygon→bone lookup |
| `parse_dsf_face_groups()` | dsf_face_groups.py | DSF JSON parser for polygon groups |
| `resolve_dsf_path()` | dsf_face_groups.py | Find DSF file from DazUrl or genesis version |
| `get_ik_target_bone()` | bone_utils.py | Remaps bone names for IK (toe→lToe/rToe, metatarsal→foot) |
| `find_daz_armature()` | start_posebridge.py | Auto-detect Genesis armature by DAZ bone markers |

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

### 2026-02-21 (hand panel)
- Added Finger Group Axis Mappings section with spread rules, fan-spread direction, and per-finger weights
- Documented base-joint-only spread (Z rotation only on bone1, never joints 2/3)
- Documented fan-spread: ring/pinky invert Z direction vs thumb/index/mid
- Documented per-finger spread weights (mid=0.1 reference, pinky=1.0 max) with slerp scaling
- Documented LMB-only spread per DAZ method (rmb_horiz=None for finger groups)

### 2026-02-21 (DSF / face groups)
- Added DSF Face Groups section documenting mesh zone detection via DSF polygon_groups
- Added `dsf_face_groups.py` to code reference (parser, face group manager, DSF path resolution)
- Updated group axis mappings table (leg groups now Y/X per PowerPose, bilateral mirroring noted)
- Marked leg group and bilateral mirroring troubleshooting entries as FIXED
- Documented gender resolution by polygon count matching (male vs female DSF)
- Documented face group cache key with polygon count for stale cache prevention
- Documented highlight rendering dual path (face groups vs vertex weights)
- Added troubleshooting entries: Text Editor invoke, null region, wrong gender, stale cache

### 2026-02-20
- Documented dual-viewport interaction (`_hover_from_posebridge` flag)
- Documented PowerPose axis mapping audit (20+ control point fixes)
- Documented bilateral mirroring (`mirror_axes`) for legs_group and shoulders_group
- Documented RMB context menu suppression (multi-layered approach)

### 2026-02-19
- Created TECHNICAL_REFERENCE.md with PowerPose research findings
- Documented PoseBridge rotation architecture (single-bone and multi-bone flows)
- Documented 4-way control scheme mirroring PowerPose DSX template format
- Documented swing-twist decomposition for ThighBend Y-lock
- Documented twist bone filtering in multi-bone groups
- Documented per-bone Euler rotation orders from DAZ (YZX for thigh, XYZ for shoulder, XZY for forearm)
- Identified leg group axis mapping mismatch vs single-bone thigh controls
