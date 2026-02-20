# Fix: IK Stiffness Tuning for Stable Torso

**Issue**: Torso bending excessively when dragging hand bones.

**Date**: 2026-02-08
**Status**: ✅ Fixed

## Problem

When click-dragging a hand bone, the torso (chest, abdomen, spine) was bending away immediately and excessively. The IK chain includes torso bones for ragdoll effect, but the bending was concentrating at the base of the chain where the spine connects to the hip.

**Undesired Behavior:**
```
User drags hand
  ↓
IK chain: Hand → Forearm → Upper Arm → Collar → Chest → Abdomen → Spine → Hip
  ↓
Torso bends excessively at spine-hip connection
```

## Root Cause

The IK stiffness values on torso bones were too low, allowing them to bend easily. The initial values were:
- Chest: 0.1 (very flexible) - TOO LOW
- Abdomen/Spine: 0.1 (very flexible) - TOO LOW
- Hip: 0.8 (high resistance) - Not high enough

Additionally, the chain didn't include the hip bone, so all bending concentrated at the spine-hip connection point.

## Solution

### 1. Added Hip to Chain

Increased hand IK chain length from 8 to 9 bones to include the hip:

**Before:**
```python
return 8  # Hand → ... → Spine (stops at spine)
```

**After:**
```python
return 9  # Hand → ... → Spine → Hip (includes hip for stability)
```

### 2. Tuned IK Stiffness Values

After testing, found optimal stiffness values that keep torso stable while allowing natural shoulder movement:

**Final Values** (line 493-509):
```python
# Shoulder joints (low stiffness = flexible = bends first)
'shldr' or 'shoulder': 0.1  # Very flexible for natural arm movement
'collar' or 'clavicle': 0.4  # Moderate flexibility for shoulder movement

# Torso bones (high stiffness = resistant = only bends when necessary)
'chest': 0.99  # Essentially locked
'abdomen' or 'spine': 0.99  # Essentially locked
'hip': 0.99  # Essentially locked (rotation also locked)
'pelvis': 0.8  # High resistance
```

## How IK Stiffness Works

**IK Stiffness** (`ik_stiffness_x/y/z`):
- Range: 0.0 to 1.0
- **0.0** = No resistance (rotates freely)
- **1.0** = Maximum resistance (essentially locked)

**IK Solver Behavior:**
The IK solver prefers to rotate bones with **lower stiffness** first:

1. **Shoulder (0.1)** - Rotates FIRST (very flexible)
2. **Collar (0.4)** - Rotates SECOND (moderate)
3. **Pelvis (0.8)** - Rotates THIRD (high resistance)
4. **Torso (0.99)** - Rotates LAST (essentially locked)

This creates a natural cascade where the shoulder absorbs most of the movement.

## Testing Results

### Iteration 1: Increased to 0.8
- Chest: 0.1 → 0.8
- Abdomen/Spine: 0.1 → 0.8
- **Result**: Better, but still bending too much

### Iteration 2: Added Hip to Chain
- Chain length: 8 → 9
- **Result**: Better, anchored base, but still some bending

### Iteration 3: Loosened Shoulder
- Collar: 0.98 → 0.5
- **Result**: Better shoulder movement, but torso still moving

### Iteration 4: Very Low Shoulder Stiffness
- Collar: 0.5 → 0.15
- Shoulder: (added) → 0.15
- **Result**: More shoulder movement, but torso still bending

### Iteration 5: Near-Maximum Torso Stiffness (FINAL)
- Shoulder: 0.15 → 0.1
- Collar: 0.15 → 0.4
- Chest: 0.8 → 0.99
- Abdomen/Spine: 0.8 → 0.99
- Hip: 0.8 → 0.99
- **Result**: ✅ Torso stays stable, shoulder moves naturally

## New Behavior

**When dragging hand:**
```
User click-drags hand
  ↓
IK chain: Hand → Forearm → Upper Arm → Collar → Chest → Abdomen → Spine → Hip (9 bones)
  ↓
Shoulder joints (0.1-0.4 stiffness) bend FIRST
  ↓
Torso bones (0.99 stiffness) stay stable
  ↓
Natural arm movement, stable torso ✓
```

## Benefits

✅ **Stable Torso** - Chest, abdomen, spine stay in place
✅ **Natural Shoulder Movement** - Shoulder and collar move freely
✅ **Ragdoll Effect Maintained** - Long chain still allows ragdoll pulling when needed
✅ **No Initial Snap** - Torso doesn't bend immediately on click

## Stiffness Reference Table

| Bone | Stiffness | Behavior |
|------|-----------|----------|
| Shoulder | 0.1 | Very flexible - rotates first |
| Collar | 0.4 | Moderate - rotates second |
| Pelvis | 0.8 | High resistance - rarely rotates |
| Chest | 0.99 | Essentially locked |
| Abdomen/Spine | 0.99 | Essentially locked |
| Hip | 0.99 | Essentially locked + rotation locked |

## Implementation Details

**Location**: `daz_bone_select.py`, `create_ik_chain()` function, lines 492-509

**Code Section**: IK stiffness assignment based on bone name detection

**Applied To**: `.ik` control bones (not DAZ bones directly)

**Update Frequency**: Set once when IK chain is created, not changed during drag

## Related Fixes

- **Pectoral Rotation** - Pectoral bones use custom rotation mode (no IK)
- **Gizmo Interference** - Gizmo area detection prevents hover changes
- **Undo System** - Ctrl+Z properly undoes IK drags

## Files Modified

1. `daz_bone_select.py` - Updated IK stiffness values and chain length

---

**Ready to use!** Hand drags now keep the torso stable with natural shoulder movement.
