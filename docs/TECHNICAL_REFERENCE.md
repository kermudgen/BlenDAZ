# BlenDAZ Technical Reference

Hard-won knowledge about IK chains, DAZ rigs, and Blender integration. This document captures what works, what doesn't, and why.

**Last Updated**: 2026-02-18

---

## Table of Contents

1. [IK Chain Architecture](#ik-chain-architecture)
2. [DAZ Genesis 8/9 Rig Specifics](#daz-genesis-89-rig-specifics)
3. [Axis Locking Strategy](#axis-locking-strategy)
4. [Research Findings](#research-findings)
5. [Research Summary](#research-summary)
6. [Troubleshooting Guide](#troubleshooting-guide)
7. [Code Reference](#code-reference)

---

## Research Findings

> Atomic, searchable findings about non-obvious Blender/DAZ/Diffeomorphic behaviors. Format: **Finding → Evidence → Consequence → Solution**. These are conceptual and don't go stale with code changes.

---

### Blender: Copy Rotation constraint does not write to rotation_quaternion
**Finding**: `COPY_ROTATION` constraints affect the evaluated bone matrix but never modify `pose_bone.rotation_quaternion`.
**Evidence**: Caching `rotation_quaternion` before constraint removal and restoring after causes snap-back to pre-drag pose. The cached value was always the pre-constraint value.
**Consequence**: Any code that tries to "preserve" a constrained pose by caching `rotation_quaternion` and removing the constraint will silently fail — the bone snaps back.
**Solution**: Before removing a constraint, evaluate the depsgraph, extract local rotation from `bone_eval.matrix`, and write it to `rotation_quaternion`. Only then is it safe to remove the constraint.
**See**: TECHNICAL_REFERENCE.md Troubleshooting → ".IK bones float away on second drag", daz_bone_select.py:1276-1317

---

### Blender 5.0: view_layer.update() does not apply F-curve animation
**Finding**: In Blender 5.0, calling `bpy.context.view_layer.update()` does NOT evaluate keyframed bone values. Bones remain at their last manually-set positions.
**Evidence**: After IK chain dissolve, IK chain bones were captured at rest/wrong positions on the second drag despite `view_layer.update()` being called.
**Consequence**: Any code that relies on `view_layer.update()` to bring bones to their keyframed values will silently fail in Blender 5.0. Bone positions are stale.
**Solution**: Call `bpy.context.scene.frame_set(bpy.context.scene.frame_current)` instead. This forces full scene evaluation including F-curves.
**See**: daz_bone_select.py:1388-1392

---

### Collar bones use Damped Track, not Copy Rotation — baking logic skips them
**Finding**: Collar bones get a `Shoulder_Track_Temp` (Damped Track) constraint to guide collar movement naturally, NOT an `IK_CopyRot_Temp` constraint like limb bones.
**Evidence**: `create_ik_chain()` daz_bone_select.py:1023-1038 adds Damped Track to collar bones. The bake step in `dissolve_ik_chain()` daz_bone_select.py:1289-1293 checks only for `c.name == "IK_CopyRot_Temp" and c.influence > 0`.
**Consequence**: Collar bones are silently skipped during baking. Their Damped Track constraint IS removed (daz_bone_select.py:1315 includes "Shoulder_Track_Temp"), but without baking first. Collar rotation relies entirely on `INSERTKEY_VISUAL` + `frame_set()` to survive the dissolve cycle.
**Risk**: If `frame_set()` is unreliable (Blender 5.0 evaluation timing), collar rotation snaps back — visible as shoulder/collar drift between drags.
**Solution (if needed)**: Add a separate bake pass for bones with `Shoulder_Track_Temp` before that constraint is removed. Use the same evaluated depsgraph decomposition pattern.
**Status**: Suspected contributor to second_drag_bug. Not yet confirmed. Discovered 2026-02-18.

---

### Blender: bone.matrix vs bone.matrix_basis for IK initialization
**Finding**: `pose_bone.matrix_basis` is the bone's own local rotation storage, without parent influence or constraint evaluation. `pose_bone.matrix` is the full evaluated armature-space transform including all parents and constraints.
**Evidence**: The original pose-matching code used `daz_bone_eval.matrix_basis.to_quaternion()` to initialize .ik bones. On a posed character (2nd+ drag), `matrix_basis` diverges from the actual bone position because parent rotations aren't included. The IK solver starts in the wrong configuration and snaps to a different solution. Switching to `ik_bone.matrix = daz_bone_eval.matrix.copy()` (full matrix) fixed this — cited as "most reliable method in Blender" (Grok analysis, commit c9ebe4b 2026-02-17).
**Consequence**: Always use `bone.matrix` (armature-space) when initializing .ik bone positions from DAZ bones. Never use `matrix_basis` for this purpose — it only agrees with `matrix` when the bone is at rest or has no parent offset.
**See**: daz_bone_select.py:686, commit c9ebe4b

---

### Blender: per-bone view_layer.update() required for child matrix propagation
**Finding**: When setting multiple bones' matrices in sequence (parent then child), the child's `matrix` setter computes its local rotation relative to its parent's *current evaluated* matrix. If the parent's matrix was just set but the scene hasn't been re-evaluated, the parent's matrix is stale and the child lands in the wrong world position.
**Evidence**: Strong pose matching in `create_ik_chain()` sets .ik bones root-to-tip. Without updating after each bone, child .ik bones end up at wrong world positions despite having correct-looking matrix values. Fix: call `view_layer.update()` after setting each bone before moving to the next.
**Consequence**: Any code that sets a chain of parent→child bones must update the scene after each bone, not once at the end.
**Unresolved caveat**: `view_layer.update()` is known insufficient for F-curve evaluation in Blender 5.0 (use `frame_set()` for that). It's unclear if it's also insufficient for propagating manually-set bone matrices to child bones. If the second drag is still wrong, this is a candidate — the per-bone update may need to be `frame_set()` too.
**See**: daz_bone_select.py:691-695, commit c9ebe4b

---

### IK activation must happen before Copy Rotation — and before first mouse move
**Finding**: The order and timing of IK and Copy Rotation constraint activation is critical:
1. **IK activates immediately** at chain creation (influence 0→1), with target positioned at the current bone tip. This causes the solver to "lock in" the existing pose as a valid solution before the user drags.
2. **Copy Rotation waits** until first mouse move (influence 0→1). If Copy Rotation activates before IK has solved, it copies from .ik bones that are still at rest/wrong positions, overwriting the DAZ bones with an incorrect pose.
3. **The nudge** (tiny 0.012 push on the middle bone) runs after IK activates. It biases the solver toward the existing bend direction, preventing it from choosing the mirror-image solution on subsequent solves.
**Evidence**: This sequence was discovered through three separate bugfix commits (007bbf5, 8b516fe, c9ebe4b). Earlier attempts that activated Copy Rotation too early, or IK too late, all produced snapping.
**Consequence**: Do not change activation order without understanding this sequence. Activating Copy Rotation at influence > 0 before IK solves will cause snap-to-rest on chain creation.
**See**: daz_bone_select.py:1160-1164 (IK immediate), daz_bone_select.py:3499-3500 (Copy Rotation on first move)

---

### Blender: Constraint space LOCAL vs POSE — critical for Copy Rotation between bones with different rest poses
**Finding**: `LOCAL` space reads/writes `matrix_basis` (rotation relative to rest pose). `POSE` space reads/writes the armature-space matrix directly, ignoring rest poses entirely.
**Evidence**: IK control bones (`.ik`) are created in edit mode at the *currently posed* position. Their rest pose IS the current pose, so `matrix_basis ≈ Identity`. Copy Rotation in LOCAL space copies this Identity to the DAZ bone, meaning "go to YOUR rest pose" (T-pose) — the bone snaps straight. Switching to POSE space fixed the second-drag snap because POSE directly matches armature-space orientation regardless of rest pose differences.
**Consequence**: Never use LOCAL space for Copy Rotation between bones with different rest poses (e.g., `.ik` bones and DAZ bones). LOCAL only works when target and owner have identical rest-pose orientations.
**Gotcha**: In POSE space, `use_x`/`use_y`/`use_z` axis filtering applies to *armature-space* axes, NOT bone-local axes. Disabling Y in POSE space does NOT filter the bone's local twist axis when the arm is posed away from rest. Use swing/twist decomposition instead.
**Space reference**:
- `WORLD`: Absolute world coordinates (includes armature object transform)
- `POSE`: Armature-space matrix (`pose_bone.matrix`), no rest-pose involvement
- `LOCAL`: Delta from rest pose (`matrix_basis`), dangerous across different rest poses
- `LOCAL_OWNER_ORIENT`: LOCAL with correction for rest-pose differences (alternative to POSE)
**See**: daz_bone_select.py Copy Rotation creation in create_ik_chain()

---

### Blender: rotation_quaternion is ignored when bone uses Euler rotation mode
**Finding**: Setting `pose_bone.rotation_quaternion` has NO visible effect if the bone's `rotation_mode` is an Euler mode (e.g., `'XYZ'`). Blender only reads `rotation_euler` in that case, and vice versa.
**Evidence**: Swing/twist decomposition was computing correct values (confirmed via console output showing 47° swing) but the mesh didn't move. DAZ bones imported by Diffeomorphic may use Euler rotation mode.
**Consequence**: Always check `bone.rotation_mode` before setting rotation. Use `rotation_quaternion` for `'QUATERNION'` mode, `rotation_euler` with `rot.to_euler(bone.rotation_mode)` for Euler modes.
**Pattern**:
```python
if bone.rotation_mode == 'QUATERNION':
    bone.rotation_quaternion = rot
else:
    bone.rotation_euler = rot.to_euler(bone.rotation_mode)
```
**See**: daz_bone_select.py swing/twist post-processing in update_ik_drag(), bake step in dissolve_ik_chain()

---

### DAZ bend/twist architecture requires swing/twist decomposition, not Copy Rotation
**Finding**: Copy Rotation constraints (in any space) cannot properly separate bend from twist when copying from `.ik` bones to DAZ bend bones. The IK solver puts combined swing+twist rotation on `.ik` bones, and no constraint space setting maps axis filtering to bone-local axes correctly.
**Evidence**: Tried LOCAL (snap-to-rest bug), POSE (twist leaks through armature axes), POSE with `use_y=False` (filters armature Y, not bone twist axis), LOCAL_OWNER_ORIENT (same snap issue as LOCAL).
**Solution**: Remove Copy Rotation from bend bones entirely. In the drag update loop, manually:
1. Read `.ik` bone's evaluated matrix from depsgraph
2. Compute the local rotation the DAZ bone needs: `matrix_basis = rest_offset.inv @ parent_eval.matrix.inv @ ik_eval.matrix`
3. Decompose with `decompose_swing_twist(rot, 'Y')` from `daz_shared_utils.py`
4. Set bend bone = swing, twist bone = twist
5. `view_layer.update()` between bone pairs so child parent matrices cascade
**See**: daz_bone_select.py update_ik_drag() post-processing, dissolve_ik_chain() bake step

---

### DAZ twist bones are incompatible with IK pole targets
**Finding**: DAZ Genesis 8/9 uses bend/twist bone pairs. The twist bone sits alongside the bend bone and handles rotation on one axis. Pole targets fight this architecture.
**Evidence**: Pole targets caused arm "shrugging" and unpredictable rotation. Disabling poles fixed the behavior.
**Consequence**: Do not add pole targets to arm chains. Leg chains may tolerate poles but have not been confirmed stable.
**Solution**: Set `pole_target.enabled = False` in `ik_templates.py` for arm chains. Use axis locking instead to constrain bend direction.
**See**: daz_bone_select.py:560-563, ik_templates.py

---

## IK Chain Architecture

### Three-Layer Bone System

BlenDAZ uses a three-layer architecture for IK:

```
DAZ Bones (original)     ← Copy Rotation constraint from...
    ↑
.IK Control Bones        ← IK constraint targeting...
    ↑
Target/Pole Bones        ← What user drags
```

**Why three layers?**
- DAZ bones preserve original rig structure
- .IK bones can be freely manipulated by IK solver
- Target bones give user direct control
- Copy Rotation transfers solved poses back to DAZ bones

### What Works

| Approach | Status | Notes |
|----------|--------|-------|
| Pole targets disabled | **YES** | DAZ twist bones don't work with poles |
| Axis locking on bend bones | **YES** | Prevents twist accumulation |
| Pre-bend for legs | **YES** | Seeds IK solver direction |
| Chain length 3 (exclude collar) | **YES** | More stable than including collar |
| Stiffness on parent bones | **YES** | Prevents wild swinging |
| POSE space for Copy Rotation | **YES** | Avoids rest-pose mismatch between .ik and DAZ bones |
| Swing/twist decomposition | **YES** | Proper bend/twist split, replaces Copy Rotation on bend bones |

### What Doesn't Work

| Approach | Status | Why It Fails |
|----------|--------|--------------|
| Pole targets enabled | **NO** | Conflicts with DAZ dual bend/twist system |
| Parenting pole to limb bones | **NO** | Creates circular dependency, breaks IK |
| Including collar in arm IK | **NO** | Causes instability and snapping |
| Dynamic pole updates | **NO** | Accumulates twist across drags |
| Hardcoded pre-bend angles | **NO** | Template values weren't being read |
| LOCAL space Copy Rotation | **NO** | .ik bones have different rest pose → snap to T-pose on 2nd drag |
| POSE space axis filtering (use_y=False) | **NO** | Filters armature Y, not bone-local twist axis |

---

## DAZ Genesis 8/9 Rig Specifics

### Dual Bend/Twist Bone System

DAZ separates rotation responsibilities into paired bones:

| Bend Bone | Twist Bone | Allowed Axes |
|-----------|------------|--------------|
| lThighBend | lThighTwist | Bend: X, Z only |
| lShin | (none) | X only (knee hinge) |
| lShldrBend | lShldrTwist | Bend: X, Z only |
| lForearmBend | lForearmTwist | Bend: X only |

**Critical Rule**: Bend bones should NEVER accumulate Y rotation (twist). Any twist belongs on the corresponding Twist bone.

### Bone Naming Patterns (Diffeomorphic Import)

```
Limbs:
  l/rShldrBend, l/rShldrTwist
  l/rForearmBend, l/rForearmTwist
  l/rThighBend, l/rThighTwist
  l/rShin (no twist bone - hinge joint)
  l/rFoot, l/rToe

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

### Known Diffeomorphic Limitations

1. **Missing LIMIT_ROTATION constraints** on some bones:
   - Head
   - Shoulder twist
   - Elbow
   - Forearm twist

   **Workaround**: `enforce_rotation_limits()` falls back to IK limits or defaults

2. **Module caching** in Blender's text editor:
   - Changes to imported modules don't take effect
   - **Fix**: Use `importlib.reload()` for all imported modules

---

## Axis Locking Strategy

Based on DAZ's channel locking approach (not pole targets).

### Leg Chain Locks

| Bone | Lock X | Lock Y | Lock Z | Reason |
|------|--------|--------|--------|--------|
| Thigh | No | **YES** | No | Prevents twist, allows swing |
| Shin | No | **YES** | **YES** | Knee is hinge joint (X only) |
| Foot | **YES** | **YES** | **YES** | End effector, position only |

### Arm Chain Locks

| Bone | Lock X | Lock Y | Lock Z | Reason |
|------|--------|--------|--------|--------|
| Shoulder | No | No | No | Full freedom for reach |
| Forearm | No | **YES** | **YES** | Elbow is hinge joint |
| Hand | **YES** | **YES** | **YES** | End effector, position only |

### Implementation

```python
# In daz_bone_select.py, during IK bone setup:

# Shin: knee bends forward/back only
if 'shin' in daz_name_lower or 'calf' in daz_name_lower:
    ik_bone.lock_ik_y = True  # Lock twist
    ik_bone.lock_ik_z = True  # Lock side-to-side

# Thigh: prevent twist accumulation
if 'thigh' in daz_name_lower:
    ik_bone.lock_ik_y = True  # Lock twist axis
```

---

## Research Summary

### Diffeomorphic / MHX Rig

**Source**: Diffeomorphic DAZ Importer documentation and code

**Key Finding**:
> "Don't use poles or twist bones will not work" (for Genesis 3/8)

- Uses pole angle of -90 degrees for DAZ/MHX rigs
- Reverse foot rig setup for legs
- Warns explicitly against pole targets with dual bone system

### Rig On The Fly

**Source**: Blender addon for auto-rigging

- Uses **slerp interpolation** for smooth pole positioning
- **90 degree shift feature** for different limb orientations
- **Three-layer bone architecture**: control -> mechanism -> deform
- Mechanism bones communicate between layers without being in IK chain

### DAZ Studio IK

**Source**: DAZ Studio behavior analysis, mcjAutoLimb

- Uses **channel locking** instead of explicit pole vectors
- Dual bend/twist bones have separate rotation responsibilities
- **mcjAutoLimb** uses "limb spin angle" as alternative to pole vectors
- This is essentially manual twist control, not solver-computed

### Key Insight

Professional rigs avoid pole targets with dual bone systems. Instead they use:
1. **Axis locking** (what we implemented)
2. **Pre-bend seeding** (hints to IK solver)
3. **Separate twist control** (manual, not IK-driven)

---

## Troubleshooting Guide

### Problem: Limb twists on second drag

**Symptoms**: First drag works, second drag accumulates twist on bend bones

**Cause (old)**: Twist component in bend bone rotation being copied to .IK bone
**Cause (updated)**: Copy Rotation constraint (in any space) cannot separate bend from twist. The IK solver puts combined rotation on .ik bones. In POSE space, axis filtering maps to armature axes, not bone-local axes, so twist leaks through.

**Solutions**:
1. ~~Lock twist axis on bend bones (`lock_ik_y = True` for thigh/forearm)~~ — helps but insufficient
2. **Use swing/twist decomposition** — remove Copy Rotation from bend bones, manually decompose `.ik` bone rotation into swing (→ bend bone) and twist (→ twist bone) using `decompose_swing_twist()` from `daz_shared_utils.py`
3. Always check `bone.rotation_mode` before setting rotation (Diffeomorphic may use Euler mode)

### Problem: Knee bends backward

**Symptoms**: Leg straightens or bends wrong direction

**Cause**: IK solver doesn't know which way to bend

**Solutions**:
1. Apply pre-bend before activating IK (template `prebend.angle`)
2. Increase pre-bend angle (0.8 radians / ~46 degrees works well)
3. Ensure pre-bend is read from template, not hardcoded

### Problem: Arm shrugs instead of reaching

**Symptoms**: Shoulder lifts up, arm doesn't extend forward

**Cause**: Pole target fighting twist bones, or collar in chain

**Solutions**:
1. Disable pole targets (`pole_target.enabled = False`)
2. Reduce chain length to exclude collar
3. Add stiffness to shoulder (0.3) to resist lifting

### Problem: Template changes don't take effect

**Symptoms**: Editing ik_templates.py has no effect

**Cause**: Blender module caching

**Solution**: Add reload at top of daz_bone_select.py:
```python
import importlib
importlib.reload(ik_templates)
```

### Problem: Snap-back on drag release

**Symptoms**: Pose jumps when releasing mouse

**Cause**: Copy Rotation constraint activation timing

**Solution**: Activate IK first, update view layer, THEN activate Copy Rotation:
```python
ik_constraint.influence = 1.0
context.view_layer.update()  # Let IK solve
# THEN activate Copy Rotation
```

### Problem: .IK bones float away on second drag

**Symptoms**: In DEBUG mode, second IK drag causes .ik bones to appear far from mesh, arm/leg snaps straight

**Cause**: Copy Rotation constraints don't modify `rotation_quaternion` - they only affect the final matrix. When cleaning up old IK chain, caching `rotation_quaternion` captures the PRE-drag rotation, not the constraint-applied rotation. Removing constraints causes snap-back to original pose.

**Solution**: BAKE constraint results into bone rotations BEFORE removing constraints:
```python
# Get final matrix from evaluated bone (includes constraint effects)
bone_eval = armature_eval.pose.bones[pose_bone.name]

# Extract local rotation
if pose_bone.parent:
    local_matrix = parent_eval.matrix.inverted() @ bone_eval.matrix
else:
    local_matrix = bone_eval.matrix

loc, rot, scale = local_matrix.decompose()

# Write constraint result to actual rotation property
pose_bone.rotation_quaternion = rot

# NOW safe to remove constraint - bone stays in place
```

---

## Code Reference

### Key Files

| File | Purpose |
|------|---------|
| `daz_bone_select.py` | Main IK drag operator (267KB) |
| `ik_templates.py` | IK chain configurations |
| `bone_utils.py` | Bone classification utilities |
| `rotation_cache.py` | Mode switch rotation preservation |
| `daz_shared_utils.py` | Rotation utilities, limits |

### Key Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `create_ik_chain()` | daz_bone_select.py:534 | Creates IK chain from template |
| `get_ik_template()` | ik_templates.py | Maps bone to template |
| `calculate_pole_position()` | ik_templates.py | Pole calculation (disabled) |
| `is_twist_bone()` | bone_utils.py | Identifies twist bones to skip |
| `PreserveRotations` | rotation_cache.py | Context manager for mode switch |

### IK Template Structure

```python
IK_RIG_TEMPLATES = {
    'foot': {
        'description': 'Full leg IK chain',
        'chain_length': 3,  # thigh -> shin -> foot
        'stiffness': {
            'thigh': 0.2,
            'shin': 0.0,
            'foot': 0.0
        },
        'pole_target': {
            'enabled': False,  # CRITICAL: Must be False for DAZ
        },
        'prebend': {
            'bone_pattern': 'shin',
            'axis': (1, 0, 0),
            'angle': 0.8  # radians
        }
    }
}
```

---

## Change Log

### 2026-02-17
- Disabled pole targets (Diffeomorphic research finding)
- Added thigh Y-axis lock (prevents twist accumulation)
- Fixed pre-bend to read from template (was hardcoded at 0.25 rad)
- Increased pre-bend angle to 0.8 radians (~46 degrees)
- Documented axis locking strategy
- **Fixed second drag bug**: .ik bones now stay with DAZ bones on sequential drags
  - Root cause: Copy Rotation constraints don't modify `rotation_quaternion`
  - Solution: Bake constraint results into bone rotations before cleanup
- **Arm IK improvements** (Grok analysis):
  - Pole targets now explicitly skipped for ALL arm chains (including soft_pin_mode)
  - Conservative pre-bend skip: uses proper quaternion angle (2*acos(|w|)) with 5° threshold
  - If joint already has >5° rotation, pre-bend is skipped entirely (preserves current pose)
