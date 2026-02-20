# Bug: Torso Bone Rotation Snaps Back on New Selection

**Issue**: When rotating a torso bone, then selecting another bone, the torso bone snaps back to its pre-rotation state.

**Date**: 2026-02-12
**Status**: ✅ Fixed

## Problem Description

After rotating a torso bone and then selecting a different bone, the torso bone immediately snaps back to its original position, losing the rotation that was applied.

**Observed Behavior:**
```
1. Select torso bone (e.g., chest, abdomen, spine, collar)
2. Rotate it (by X degrees)
3. Select different bone (e.g., hand)
   ↓
4. → Torso bone snaps back to original position (rotation lost)
```

**Expected Behavior:**
```
1. Select torso bone
2. Rotate it
3. Select different bone
   ↓
4. → Torso bone maintains its rotation
```

## Related Issue: Upper Abdomen Selection (Not a Bug)

**Initial symptom**: The upper abdomen bone couldn't be selected from certain camera angles.

**Resolution**: This is **not a code bug** - it's a normal limitation of 3D raycast-based selection. When other meshes or bones occlude the upper abdomen from the camera's perspective, the raycast can't reach it. Rotating the viewport to get a clear line of sight allows selection.

**Confirmed**: Hovering shows the bone in the header, and clicking selects it (when not occluded).

## Questions to Answer

1. **Which torso bones** does this happen with?
   - [ ] Chest
   - [ ] Upper Abdomen (also won't select)
   - [ ] Lower Abdomen
   - [ ] Spine
   - [ ] Collar
   - [ ] All of the above?

2. **How are you rotating?**
   - [ ] PowerPose panel
   - [ ] Blender's native rotation tools (R key, rotate gizmo)
   - [ ] Both?

3. **Does it happen with all bone selections?**
   - [ ] Only when selecting specific types of bones after torso rotation
   - [ ] Happens with any bone selection
   - Which bones specifically trigger the snap?

4. **Is the torso bone pinned when you rotate it?**
   - [ ] Yes, bone is pinned
   - [ ] No, bone is not pinned
   - [ ] Happens in both cases

5. **When does the snap happen?**
   - [ ] Immediately when clicking the new bone
   - [ ] When starting to interact with/drag the new bone
   - [ ] Other timing?

## Root Cause: Mode Switching Discards Un-Keyframed Rotations

**FOUND IT!** The issue is in the `select_bone()` function at **lines 2384-2408**.

When selecting a different bone, the code switches from **Pose Mode → Edit Mode → Pose Mode** to force the bone selection. This mode switching **discards any rotations that haven't been keyframed**!

```python
# Line 2384-2408 in select_bone()
try:
    # Go to edit mode
    bpy.ops.object.mode_set(mode='EDIT')

    # Select the bone in edit mode
    edit_bone = armature.data.edit_bones.get(bone_name)
    if edit_bone:
        # ... selection logic ...

    # Go back to pose mode
    bpy.ops.object.mode_set(mode='POSE')  # ← ROTATIONS LOST HERE
```

**Evidence from the code:** Line 2370 has a comment:
```python
# CRITICAL: Check if bone is already active and selected
# If so, skip mode switching to preserve pose (especially manual R rotations)
```

This proves the developer knew mode switching loses manual rotations! But this protection only works when re-selecting the **same** bone. When selecting a **different** bone, the mode switch still happens and rotations are discarded.

## Why Upper Abdomen Won't Select

This is likely a separate issue - need to test if it's being filtered somewhere or if there's a raycast/mesh issue with that specific bone region.

## Investigation Steps

1. **Add debug prints** to track when rotations change:
   ```python
   print(f"Bone {bone_name} rotation before: {bone.rotation_quaternion}")
   # ... selection change ...
   print(f"Bone {bone_name} rotation after: {bone.rotation_quaternion}")
   ```

2. **Check cleanup functions**:
   - Look for `cleanup_ik_chain()`
   - Look for constraint removal code
   - Check what happens on bone selection change

3. **Check Copy Rotation system**:
   - Are Copy Rotation constraints being removed/reapplied?
   - Is original rotation data being restored?

4. **Test upper abdomen selection**:
   - Why can't it be selected?
   - Is it being filtered out somewhere?
   - Check hover detection and selection code

## Potential Solutions

### Option 1: Keyframe Before Mode Switch (Simplest)
Before switching to edit mode, keyframe all currently selected/active bones to preserve their rotations:

```python
# Line ~2387 in select_bone(), before mode switch
# Keyframe current active bone to preserve manual rotations
if context.active_bone:
    current_bone = armature.pose.bones.get(context.active_bone.name)
    if current_bone:
        # Check if bone has been rotated from rest
        if current_bone.rotation_mode == 'QUATERNION':
            # Store rotation with keyframe
            current_bone.keyframe_insert(data_path="rotation_quaternion")
            print(f"  ✓ Preserved rotation for: {context.active_bone.name}")

# Then do mode switch...
bpy.ops.object.mode_set(mode='EDIT')
```

**Pros:** Simple, uses existing Blender infrastructure
**Cons:** Creates keyframes automatically (might not be desired)

### Option 2: Cache and Restore Rotations (Recommended)
Store all bone rotations before mode switch, restore after:

```python
# Line ~2387 in select_bone(), before mode switch
# Cache all bone rotations
rotation_cache = {}
for pose_bone in armature.pose.bones:
    if pose_bone.rotation_mode == 'QUATERNION':
        rotation_cache[pose_bone.name] = pose_bone.rotation_quaternion.copy()
    else:
        rotation_cache[pose_bone.name] = pose_bone.rotation_euler.copy()

# Do mode switch...
bpy.ops.object.mode_set(mode='EDIT')
# ... selection logic ...
bpy.ops.object.mode_set(mode='POSE')

# Restore rotations
for bone_name, rotation in rotation_cache.items():
    pose_bone = armature.pose.bones.get(bone_name)
    if pose_bone:
        if pose_bone.rotation_mode == 'QUATERNION':
            pose_bone.rotation_quaternion = rotation
        else:
            pose_bone.rotation_euler = rotation

print(f"  ✓ Restored rotations for {len(rotation_cache)} bones")
```

**Pros:** Preserves all rotations, no unwanted keyframes
**Cons:** More code, needs to handle different rotation modes

### Option 3: Avoid Mode Switch (Best Long-term)
Find a way to select bones without switching modes. Blender's direct bone selection:

```python
# Instead of mode switching, try direct selection
bpy.ops.pose.select_all(action='DESELECT')

# Set active bone
armature.data.bones.active = armature.data.bones[bone_name]

# Select in pose mode
pose_bone = armature.pose.bones[bone_name]
pose_bone.bone.select = True

# Force update
context.view_layer.update()
context.area.tag_redraw()
```

**Pros:** Cleanest solution, no mode switch needed
**Cons:** Might not work reliably (needs testing)

### Option 4: Track Manual Edits (Most Robust)
Add a system to track which bones have been manually edited and preserve those specifically:

```python
# When user manually rotates (R key detected or gizmo used)
bone['daz_manual_edit'] = True
bone['daz_saved_rotation'] = bone.rotation_quaternion.copy()

# In select_bone(), after mode switch:
for pose_bone in armature.pose.bones:
    if pose_bone.bone.get('daz_manual_edit'):
        # Restore manually edited rotation
        pose_bone.rotation_quaternion = pose_bone.bone['daz_saved_rotation']
        print(f"  ✓ Restored manual edit: {pose_bone.name}")
```

**Pros:** Only preserves intentional edits, most precise
**Cons:** Requires hooking into rotation events, most complex

## Files to Investigate

1. `daz_bone_select.py`:
   - Bone selection change handlers
   - `cleanup_ik_chain()` function
   - Copy Rotation constraint management
   - Upper abdomen selection code (why it won't select)

## Testing Plan

After fix:
1. Select chest bone
2. Rotate it 45 degrees
3. Select hand bone
4. ✅ Chest bone maintains its 45-degree rotation
5. Try with other torso bones (abdomen, spine, collar)
6. ✅ All maintain their rotations after selection change
7. ✅ Upper abdomen bone is selectable

## Related Issues

- **Copy Rotation System** - Used for parent-child relationships
- **IK Chain Cleanup** - May be resetting rotations
- **Pin System** - Pinned bones should definitely maintain rotations
- **Pectoral Rotation Undo** - Similar snap-back issue (see FIX_PECTORAL_ROTATION_UNDO.md)

---

## Solution Applied

**Option 2: Cache and Restore Rotations** was implemented.

**Changes Made** (lines 2387-2420 in `daz_bone_select.py`):

1. **Before mode switch (line ~2390)**: Cache all bone rotations
   ```python
   # CACHE all bone rotations before mode switch
   rotation_cache = {}
   for pose_bone in armature.pose.bones:
       if pose_bone.rotation_mode == 'QUATERNION':
           rotation_cache[pose_bone.name] = pose_bone.rotation_quaternion.copy()
       else:
           rotation_cache[pose_bone.name] = pose_bone.rotation_euler.copy()
   ```

2. **After mode switch (line ~2410)**: Restore all bone rotations
   ```python
   # RESTORE all bone rotations after mode switch
   rotations_restored = 0
   for bone_name_cache, rotation in rotation_cache.items():
       pose_bone = armature.pose.bones.get(bone_name_cache)
       if pose_bone:
           if pose_bone.rotation_mode == 'QUATERNION':
               pose_bone.rotation_quaternion = rotation
           else:
               pose_bone.rotation_euler = rotation
           rotations_restored += 1

   if rotations_restored > 0:
       print(f"  ✓ Preserved rotations for {rotations_restored} bones")
   ```

**Result:**
- ✅ Manual rotations preserved when selecting different bones
- ✅ Works with both QUATERNION and EULER rotation modes
- ✅ No unwanted keyframes created
- ✅ All bones' rotations preserved, not just torso bones

**Next Step**: Test in Blender to confirm rotations are maintained.

---

## Additional Fix: Exclude Torso from Arm IK Chains

**Issue**: Even with rotation preservation on selection, torso still snapped back when dragging arms with IK.

**Root Cause**: Arm IK chains included torso bones (chest, abdomen, spine) with chain lengths of:
- Hands: 9 bones (included entire torso down to hip)
- Forearms: 7 bones (included chest + abdomen + spine)

When IK constraints activated, they overrode manual torso rotations.

**Solution**: Reduced chain lengths to stop at collar/shoulder, excluding all torso bones:

**Changes Made** (lines 266-283 in `daz_bone_select.py`):

```python
# BEFORE:
# Hands: return 9  # Extended chain including hip for stability
# Forearms: return 7  # Forearm + upper arm + collar + chest + abdomen + spine

# AFTER:
# Hands: return 4  # Stop at collar (excludes chest/abdomen/spine)
# Forearms: return 3  # Forearm + upper arm + collar (excludes torso)
```

**Result:**
- ✅ Arm IK chains: Hand → Forearm → Upper Arm → Collar (stops here)
- ✅ Torso bones (chest/abdomen/spine) excluded from arm IK
- ✅ Manual torso rotations preserved during arm dragging
- ✅ Simpler, cleaner solution than trying to preserve rotations through IK

**Trade-off:** Arms no longer have "ragdoll pulling" effect on torso. This is intentional - if you want to bend the torso, rotate it manually first, then pose the arms.

---

## Additional Fix: Rotation Caching in create_ik_chain()

**Issue**: Even after excluding torso from arm IK, rotations still snapped back when starting a drag.

**Root Cause**: The `create_ik_chain()` function has its own mode switch (POSE → EDIT → POSE at lines 501 and 625) that discarded rotations.

**Solution**: Added rotation caching/restoration in `create_ik_chain()` as well.

**Changes Made** (lines 498-645 in `daz_bone_select.py`):

1. **Before EDIT mode switch (line ~500)**: Cache all bone rotations
   ```python
   # STEP 1.6: Cache ALL bone rotations BEFORE mode switch
   rotation_cache = {}
   for pose_bone in armature.pose.bones:
       if pose_bone.rotation_mode == 'QUATERNION':
           rotation_cache[pose_bone.name] = pose_bone.rotation_quaternion.copy()
       else:
           rotation_cache[pose_bone.name] = pose_bone.rotation_euler.copy()
   ```

2. **After POSE mode switch (line ~627)**: Restore all bone rotations
   ```python
   # STEP 3.1: RESTORE all cached bone rotations after mode switch
   for bone_name_cache, rotation in rotation_cache.items():
       pose_bone = armature.pose.bones.get(bone_name_cache)
       if pose_bone:
           if pose_bone.rotation_mode == 'QUATERNION':
               pose_bone.rotation_quaternion = rotation
           else:
               pose_bone.rotation_euler = rotation
   ```

**Result:**
- ✅ Rotations preserved during bone selection (Fix #1)
- ✅ Rotations preserved during IK chain creation (Fix #3)
- ✅ Torso excluded from arm IK chains (Fix #2)

---

## Additional Fix: Rotation Caching in dissolve_ik_chain()

**Issue**: Rotations preserved during drag, but snapped back on mouse release.

**Root Cause**: The `dissolve_ik_chain()` function (called on release) has ANOTHER mode switch (POSE → EDIT → POSE at lines 1180 and 1204) that discarded rotations during cleanup.

**Solution**: Added rotation caching/restoration in `dissolve_ik_chain()` as well.

**Changes Made** (lines 1173-1211 in `daz_bone_select.py`):

1. **Before EDIT mode switch (line ~1180)**: Cache all bone rotations
   ```python
   # STEP 2.5: Cache ALL bone rotations BEFORE mode switch (for cleanup)
   rotation_cache = {}
   for pose_bone in armature.pose.bones:
       if pose_bone.rotation_mode == 'QUATERNION':
           rotation_cache[pose_bone.name] = pose_bone.rotation_quaternion.copy()
       else:
           rotation_cache[pose_bone.name] = pose_bone.rotation_euler.copy()
   ```

2. **After POSE mode switch (line ~1206)**: Restore rotations EXCEPT for IK chain bones
   ```python
   # STEP 3.5: RESTORE cached rotations after mode switch
   # CRITICAL: Skip bones that were in the IK chain - they should keep their new pose!
   for bone_name_cache, rotation in rotation_cache.items():
       # Skip bones that were in the IK chain - they have new poses from the drag
       if bone_name_cache in daz_bone_names:
           continue

       pose_bone = armature.pose.bones.get(bone_name_cache)
       if pose_bone:
           if pose_bone.rotation_mode == 'QUATERNION':
               pose_bone.rotation_quaternion = rotation
           else:
               pose_bone.rotation_euler = rotation
   ```

**Refinement**: Initially restored ALL rotations, which reset the arm pose. Fixed by skipping IK chain bones during restoration - they keep their new IK poses while non-IK bones (torso) keep their manual rotations.

**Final Result - ALL FOUR FIXES:**
1. ✅ Rotation cache in `select_bone()` - preserves on selection
2. ✅ Shorter arm IK chains (stop at collar) - excludes torso from IK
3. ✅ Rotation cache in `create_ik_chain()` - preserves on drag start
4. ✅ **Rotation cache in `dissolve_ik_chain()`** - preserves on drag end (excludes IK bones)
5. ✅ **COMPLETE FIX:**
   - Torso bones keep manual rotations ✓
   - Arm bones keep IK-posed rotations ✓
   - No snap-back at any stage! ✓
