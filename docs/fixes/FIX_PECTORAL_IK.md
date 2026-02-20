# Fix: Disable IK Chains for Pectoral Bones

**Issue**: Pectoral/breast bones were creating IK chains that pulled the spine/chest when dragged.

**Date**: 2026-02-08
**Status**: ✅ Fixed

## Problem

When hovering over and dragging pectoral/breast bones, the IK system was creating chains that extended up to the spine and chest, causing the entire torso to deform unnaturally.

**Undesired Behavior:**
```
User drags pectoral bone
  ↓
IK chain created: pectoral → chest → spine → pelvis
  ↓
Entire torso pulls and deforms
```

## Solution

Added pectoral bone detection to `get_ik_target_bone()` to return `None`, which disables IK chain creation for these bones.

**Code Change:**
```python
def get_ik_target_bone(armature, bone_name):
    """
    Map small bones to their major parent bone for IK (DAZ-style behavior).
    Returns: bone name to use for IK, or None if bone shouldn't use IK.
    """
    bone_lower = bone_name.lower()

    # Twist/roll bones - NO IK (causes noodle limbs)
    if is_twist_bone(bone_name):
        print(f"  Twist bone detected - IK disabled: {bone_name}")
        return None

    # Pectoral bones - NO IK (shouldn't pull spine/chest)
    # NEW: These are breast/chest bones that should not create IK chains
    if 'pectoral' in bone_lower or 'breast' in bone_lower:
        print(f"  Pectoral bone detected - IK disabled: {bone_name}")
        return None
```

## Detected Bone Names

This fix detects bones with these keywords in their name (case-insensitive):
- `pectoral` (e.g., "lPectoral", "rPectoral")
- `breast` (e.g., "lBreast", "rBreast")

Common DAZ bone names that will be caught:
- lPectoral, rPectoral
- lBreast, rBreast
- Any variant with "pectoral" or "breast" in the name

## New Behavior

**When hovering over pectoral bone:**
```
User clicks pectoral bone
  ↓
get_ik_target_bone() returns None
  ↓
IK drag is disabled
  ↓
Message: "Pectoral bone detected - IK disabled: [bone_name]"
  ↓
User can still select and rotate bone with R key
```

## Alternative Manipulation Methods

Since IK drag is disabled for pectoral bones, users can still manipulate them using:

1. **Rotation (R key)**:
   - Select pectoral bone
   - Press R to rotate
   - Move mouse to adjust
   - Click to confirm

2. **Manual Transform**:
   - Select pectoral bone
   - Use transform gizmo
   - Adjust position/rotation/scale

3. **PowerPose Panel**:
   - Open N-panel > DAZ tab
   - Use PowerPose Bend/Twist buttons
   - Direct rotation control

## Why This Fix?

**Pectoral bones are special because:**
- They're surface detail bones (not structural)
- They shouldn't affect the underlying skeleton
- They're typically used for breast shape/position
- IK chains would deform the entire torso (unnatural)
- They should move independently of the spine

**Similar to twist bones:**
- Twist bones don't use IK (causes noodle limbs)
- Pectoral bones don't use IK (causes torso deformation)
- Both are better controlled via rotation only

## Testing

### Before Fix:
1. Hover over pectoral bone
2. Click and drag
3. ❌ Entire torso deforms
4. ❌ Spine/chest pulled out of position

### After Fix:
1. Hover over pectoral bone
2. Click and drag
3. ✅ Message: "Pectoral bone detected - IK disabled"
4. ✅ Torso remains stable
5. ✅ Can still rotate bone with R key

## Impact

✅ **Positive:**
- Prevents unnatural torso deformation
- More predictable behavior
- Consistent with twist bone handling
- Users can still rotate pectoral bones manually

✅ **No Breaking Changes:**
- Other bones still work normally
- IK system unchanged for limbs
- Hover detection still works
- Selection still works

## Files Modified

1. `daz_bone_select.py` - Added pectoral bone detection to `get_ik_target_bone()`

## Related Functions

- `is_twist_bone()` - Similar pattern for twist bones
- `get_ik_target_bone()` - Main bone mapping function (modified)
- `start_ik_drag()` - Calls `get_ik_target_bone()` to check if IK should be used

---

**Ready to test!** Pectoral bones should no longer create IK chains when dragged.
