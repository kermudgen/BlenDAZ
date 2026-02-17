# IK Integration Plan for daz_bone_select.py

**Date:** 2026-02-07
**Status:** Ready to integrate

---

## Summary of Working Solution

We've successfully created a working IK system with these key elements:

1. ✅ **Bone targets** (not empty objects)
2. ✅ **Copy Rotation constraints** (not manual copying)
3. ✅ **Proper bone hierarchy** (.ik bones parented correctly)
4. ✅ **Slight rotation nudge** to break straight-line ambiguity
5. ✅ **Read from matrix** (not rotation_euler) to get constraint results

---

## Functions to Replace in daz_bone_select.py

### 1. `create_ik_chain()` (lines 267-427)

**Current issues:**
- Uses empty object as IK target ❌
- Manually copies rotations every frame ❌
- Doesn't add Copy Rotation constraints ❌

**New implementation:**
- Create `.ik` control bones with proper parent hierarchy
- Create `.ik.target` bone (no parent) as draggable target
- Add IK constraint to last `.ik` bone targeting `.ik.target`
- Add Copy Rotation constraints from DAZ bones to `.ik` bones
- Add slight rotation nudge to break straight-line IK ambiguity
- Return target bone name (not empty object)

### 2. `start_ik_drag()` (lines 1091-1148)

**Changes needed:**
- Store target BONE name instead of empty object
- Remove references to `self._ik_target` (empty)
- Add `self._ik_target_bone_name` (string)
- Everything else stays the same

### 3. `update_ik_drag()` (lines 1149-1200+)

**Current issues:**
- Moves empty object ❌
- Manually copies rotations every frame ❌

**New implementation:**
- Move target BONE location (convert mouse to world space)
- Remove manual `copy_rotation_temp_to_real()` calls
- Constraints handle rotation copying automatically
- Read from evaluated matrix for visual feedback (if needed)

### 4. `copy_rotation_temp_to_real()` (lines 430-442)

**Action:** Keep for backward compatibility but won't be called

### 5. `dissolve_ik_chain()` (lines 444-500+)

**Changes needed:**
- Remove Copy Rotation constraints from DAZ bones
- Don't delete empty object (doesn't exist)
- Delete `.ik` control bones and `.ik.target` bone
- Keep everything else (keyframe insertion, cleanup)

---

## New Helper Functions to Add

### `convert_mouse_to_world_location()`

Convert 2D mouse position to 3D world space location using ray-plane intersection.

```python
def convert_mouse_to_world_location(context, event, plane_point, plane_normal):
    """Convert mouse 2D to 3D world location via ray-plane intersection"""
    region = context.region
    rv3d = context.space_data.region_3d
    mouse_pos = (event.mouse_region_x, event.mouse_region_y)

    view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse_pos)
    ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse_pos)

    # Ray-plane intersection
    denom = plane_normal.dot(view_vector)
    if abs(denom) > 0.0001:
        t = (plane_point - ray_origin).dot(plane_normal) / denom
        if t >= 0:
            return ray_origin + view_vector * t

    return plane_point  # Fallback
```

### `move_ik_target_bone()`

Move the IK target bone to a world space location.

```python
def move_ik_target_bone(armature, target_bone_name, world_location):
    """Move IK target bone to world space location"""
    target_pose = armature.pose.bones[target_bone_name]
    local_location = armature.matrix_world.inverted() @ world_location
    target_pose.location = local_location
    bpy.context.view_layer.update()
```

---

## Implementation Steps

### Step 1: Replace `create_ik_chain()` function

Copy the working implementation from `ik_chain_fixed.py`:
- Use `create_ik_chain_fixed()` as the new `create_ik_chain()`
- Returns: `(target_bone_name, ik_control_names, daz_bone_names)`
- Old return was: `(ik_constraint, empty_object, bone_name, temp_names, real_names)`

### Step 2: Update `start_ik_drag()`

Change lines that reference the return values:
```python
# OLD:
self._ik_constraint, self._ik_target, constrained_bone, temp_bones, real_bones = result

# NEW:
target_name, ik_names, daz_names = result
self._ik_target_bone_name = target_name
self._ik_control_bone_names = ik_names
self._ik_daz_bone_names = daz_names
```

Update plane point calculation:
```python
# OLD:
self._drag_plane_point = self._ik_target.location.copy()

# NEW:
target_bone = self._drag_armature.pose.bones[self._ik_target_bone_name]
self._drag_plane_point = (self._drag_armature.matrix_world @ target_bone.head).copy()
```

### Step 3: Update `update_ik_drag()`

Replace empty object movement with bone movement:
```python
# OLD:
self._ik_target.location = world_location

# NEW:
move_ik_target_bone(self._drag_armature, self._ik_target_bone_name, world_location)
```

Remove manual rotation copying:
```python
# DELETE these lines:
copy_rotation_temp_to_real(
    self._drag_armature,
    self._ik_temp_bone_names,
    self._ik_real_bone_names
)
```

### Step 4: Update `end_ik_drag()`

Update to use new `dissolve_ik_chain()` signature:
```python
# OLD:
dissolve_ik_chain(
    self._drag_armature,
    self._drag_bone_name,
    self._ik_constraint,
    self._ik_target,  # Empty object
    self._ik_temp_bone_names,
    self._ik_real_bone_names
)

# NEW:
dissolve_ik_chain(
    self._drag_armature,
    self._ik_target_bone_name,  # Target bone name
    self._ik_control_bone_names,
    self._ik_daz_bone_names
)
```

### Step 5: Update `dissolve_ik_chain()` function

Remove Copy Rotation constraints:
```python
# Add at start:
for daz_name in daz_bone_names:
    daz_pose = armature.pose.bones[daz_name]
    constraints_to_remove = [c for c in daz_pose.constraints
                             if c.name == "IK_CopyRot_Temp"]
    for c in constraints_to_remove:
        daz_pose.constraints.remove(c)
```

Don't delete empty object:
```python
# DELETE:
if ik_target:
    bpy.data.objects.remove(ik_target, do_unlink=True)
```

Delete `.ik` bones and `.ik.target` bone in EDIT mode (similar to current temp bone deletion).

---

## Testing Checklist

After integration, test:

1. ✅ Click on hand → IK chain created
2. ✅ Drag hand → Arm follows smoothly
3. ✅ Release → Rotations baked, IK cleaned up
4. ✅ Twist bones bypassed correctly
5. ✅ Pin system still works (pinned bones don't move)
6. ✅ Works on Fey figure with full DAZ hierarchy
7. ✅ Multiple limbs can be posed in sequence
8. ✅ No leftover bones or constraints after cleanup

---

## Performance Notes

**Expected performance:**
- IK creation: ~50-100ms (one-time on click)
- Drag updates: ~5-10ms per frame (60fps achievable)
- Cleanup: ~50-100ms (one-time on release)

**Optimizations for future:**
- Cache IK rigs (don't recreate on every drag)
- Use constraint influence toggle (faster than create/destroy)
- Batch mode switches (reduce EDIT↔POSE switches)

---

## Files Modified

1. `daz_bone_select.py` - Main integration
   - `create_ik_chain()` - Complete rewrite
   - `start_ik_drag()` - Update return value handling
   - `update_ik_drag()` - Replace empty movement with bone movement
   - `end_ik_drag()` - Update cleanup call
   - `dissolve_ik_chain()` - Add Copy Rotation cleanup

2. `ik_chain_fixed.py` - Reference implementation (keep for testing)

---

## Next Steps

1. Integrate the working `create_ik_chain_fixed()` into `daz_bone_select.py`
2. Test on simple rig
3. Test on Fey figure
4. Add optimization (constraint influence toggle)
5. Update CLAUDE.md and PROGRESS.md

---

**Ready to proceed with integration!** 🚀
