# BlenDAZ Technical Reference

Hard-won knowledge about IK chains, DAZ rigs, and Blender integration. This document captures what works, what doesn't, and why.

**Last Updated**: 2026-02-17

---

## Table of Contents

1. [IK Chain Architecture](#ik-chain-architecture)
2. [DAZ Genesis 8/9 Rig Specifics](#daz-genesis-89-rig-specifics)
3. [Axis Locking Strategy](#axis-locking-strategy)
4. [Research Summary](#research-summary)
5. [Troubleshooting Guide](#troubleshooting-guide)
6. [Code Reference](#code-reference)

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

### What Doesn't Work

| Approach | Status | Why It Fails |
|----------|--------|--------------|
| Pole targets enabled | **NO** | Conflicts with DAZ dual bend/twist system |
| Parenting pole to limb bones | **NO** | Creates circular dependency, breaks IK |
| Including collar in arm IK | **NO** | Causes instability and snapping |
| Dynamic pole updates | **NO** | Accumulates twist across drags |
| Hardcoded pre-bend angles | **NO** | Template values weren't being read |

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

**Symptoms**: First drag works, second drag accumulates twist

**Cause**: Twist component in bend bone rotation being copied to .IK bone

**Solutions**:
1. Lock twist axis on bend bones (`lock_ik_y = True` for thigh/forearm)
2. Consider decomposing rotation and zeroing twist before copy

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
