# Bug: Pectoral Rotation Broken with Rotated Armature

**Issue**: When armature is rotated in object mode (e.g., character lying on side), pectoral bone rotation doesn't follow mouse pointer correctly.

**Date**: 2026-02-12
**Status**: ✅ Fixed (Final Solution)

## Problem Description

When the armature is rotated in object mode and you try to click-drag pectoral bones, the rotation doesn't follow the mouse movement. The bone rotates in unexpected directions.

**Steps to Reproduce:**
1. Select armature in object mode
2. Rotate it (e.g., R Y 90 to make character lie on side)
3. Enter pose mode / activate DAZ Bone Select
4. Click-drag a pectoral bone
5. ❌ Rotation doesn't follow mouse pointer

## Root Cause: Fixed Rotation Axes

**Location**: `update_rotation()` function, lines 3384-3395

The pectoral rotation code uses **fixed local axes** without considering the armature's world rotation:

```python
# Horizontal drag = Z-axis rotation (twist)
# Vertical drag = X-axis rotation (bend forward/back)
angle_z = delta_x * sensitivity   # Horizontal movement = Z rotation
angle_x = delta_y * sensitivity   # Vertical movement = X rotation

# Create rotation quaternions
rot_z = Quaternion(Vector((0, 0, 1)), angle_z)  # ← Fixed Z axis in local space
rot_x = Quaternion(Vector((1, 0, 0)), angle_x)  # ← Fixed X axis in local space

# Combine rotations and apply to bone
combined_rot = rot_z @ rot_x
self._rotation_bone.rotation_quaternion = combined_rot @ self._rotation_initial_quat
```

**Problem:** When the armature is rotated in object mode, local axes (1,0,0) and (0,0,1) no longer align with screen horizontal/vertical movement. The user drags horizontally on screen, but the bone rotates in a diagonal direction.

## Solution: Use View-Space Rotation

Instead of using fixed local axes, we need to calculate rotation relative to the **viewport/camera view**.

### Option 1: View-Aligned Rotation (Recommended)
Calculate rotation axes that align with the camera view, so horizontal mouse movement = horizontal rotation on screen.

```python
# Get view direction and right vector from viewport
region = context.region
rv3d = context.space_data.region_3d

# View matrix gives us camera orientation
view_matrix = rv3d.view_matrix
view_right = view_matrix[0][:3]   # Camera's right vector (screen horizontal)
view_up = view_matrix[1][:3]      # Camera's up vector (screen vertical)

# Create rotations around view-aligned axes
angle_z = delta_x * sensitivity   # Horizontal drag
angle_x = delta_y * sensitivity   # Vertical drag

# Rotate around view axes (in world space)
rot_horiz = Quaternion(view_right, angle_x)
rot_vert = Quaternion(view_up, angle_z)

# Combine and convert to bone local space
combined_rot = rot_horiz @ rot_vert
# ... transform to bone local space and apply
```

### Option 2: Trackball Rotation
Use a trackball-style rotation that naturally follows mouse movement regardless of armature orientation.

### Option 3: Transform Axes by Armature World Matrix
Transform the local axes by the armature's world rotation before creating quaternions.

```python
# Get armature's world rotation
armature = self._drag_armature
world_matrix = armature.matrix_world

# Transform local axes to world space
world_z = world_matrix.to_3x3() @ Vector((0, 0, 1))
world_x = world_matrix.to_3x3() @ Vector((1, 0, 0))

# Create rotations around world-transformed axes
rot_z = Quaternion(world_z, angle_z)
rot_x = Quaternion(world_x, angle_x)

# Combine and convert back to local space
combined_rot_world = rot_z @ rot_x
# ... convert to bone local space
```

## Testing Plan

1. **Normal orientation:**
   - Armature upright (no object rotation)
   - Drag pectoral bone
   - ✓ Should work as before

2. **Rotated 90° on Y:**
   - R Y 90 in object mode (lying on side)
   - Drag pectoral bone
   - ✓ Should follow mouse naturally

3. **Rotated 180° on Z:**
   - R Z 180 in object mode (upside down)
   - Drag pectoral bone
   - ✓ Should follow mouse naturally

4. **Arbitrary rotation:**
   - R X 45 R Z 30 in object mode
   - Drag pectoral bone
   - ✓ Should follow mouse naturally

## Related Code

- `update_rotation()` - Line 3353, handles pectoral bone rotation
- `start_ik_drag()` - Line 2557, detects pectoral bones and starts rotation mode
- `end_rotation()` - Line 3401, finalizes rotation and keyframes

## Files to Modify

1. `daz_bone_select.py` - `update_rotation()` function (lines 3384-3395)

---

## Solution Applied

**Option 1: View-Aligned Rotation** was implemented.

**Changes Made** (lines 3379-3415 in `daz_bone_select.py`):

The rotation code now:
1. **Gets viewport orientation** from `rv3d.view_matrix`
2. **Extracts screen-aligned axes:**
   - `view_right` = camera's right vector (screen horizontal)
   - `view_up` = camera's up vector (screen vertical)
3. **Creates rotations around view axes** (in world space)
4. **Transforms to bone local space** using armature's inverse world matrix

**Key Code:**
```python
# Get view-space axes (screen-aligned)
view_matrix = rv3d.view_matrix
view_right = Vector(view_matrix[0][:3])  # Screen horizontal
view_up = Vector(view_matrix[1][:3])     # Screen vertical

# Rotate around view axes
rot_horiz = Quaternion(view_up, angle_horiz)
rot_vert = Quaternion(view_right, angle_vert)
combined_rot_world = rot_horiz @ rot_vert

# Transform to bone local space
world_to_local = armature.matrix_world.to_3x3().inverted()
combined_rot_local = world_to_local.to_quaternion() @ combined_rot_world @ world_to_local.inverted().to_quaternion()

# Apply
self._rotation_bone.rotation_quaternion = combined_rot_local @ self._rotation_initial_quat
```

**Result:**
- ✅ Pectoral rotation follows mouse naturally
- ✅ Works with armature rotated at any angle
- ✅ Screen horizontal drag = horizontal rotation on screen
- ✅ Screen vertical drag = vertical rotation on screen

**Current Status**: Partial fix applied. Works correctly when armature is in normal orientation or rotated on X/Z axes, but has issues when armature is rotated on Y axis.

**What Works:**
- ✅ Normal armature orientation (upright)
- ✅ Armature rotated on X axis
- ✅ Armature rotated on Z axis

**What Doesn't Work:**
- ❌ Armature rotated on Y axis (turntable rotation)

**Approaches Tried:**
1. View-space rotation with world-to-local conversion (original approach)
2. Transform view axes to local space before rotating
3. Trackball-style rotation
4. Full matrix transformations in world space
5. Using bone parent matrix for conversion

**The Core Problem:**
Converting between screen-space rotations and bone-local rotations while accounting for arbitrary armature orientations is mathematically complex. The Y-axis rotation specifically breaks the coordinate space relationship in a way that's difficult to compensate for.

**Current Implementation:**
Simple approach that works for normal orientation - rotates around screen-aligned axes (view_up, view_right) in world space, then converts to local space using armature's world quaternion.

## Final Solution: Use Blender's Native Trackball Rotate

**Simplest and best approach:** Instead of trying to manually calculate screen-space rotations, just invoke Blender's built-in trackball rotate operator!

**Implementation** (lines 2562-2573 in `daz_bone_select.py`):

```python
# Pectoral bones: Use Blender's trackball rotate
if is_pectoral(self._drag_bone_name):
    print("  → Pectoral bone: Using Blender's trackball rotate")

    # Invoke Blender's trackball rotate operator
    bpy.ops.transform.trackball('INVOKE_DEFAULT')

    # Clear drag state - Blender's operator takes over
    self._drag_bone_name = None
    self._drag_armature = None
    return
```

**Benefits:**
- ✅ Works at ANY armature orientation (normal, rotated on X/Y/Z)
- ✅ No complex quaternion/matrix math needed
- ✅ Uses Blender's proven coordinate space handling
- ✅ Feels exactly like native Blender (because it is!)
- ✅ Simple, maintainable code

**Result:** Pectoral bones now rotate intuitively following the mouse, regardless of how the armature is oriented. Problem solved by leveraging existing Blender functionality!
