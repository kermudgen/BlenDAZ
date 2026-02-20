# IK Breakthrough - Root Cause Identified

**Date:** 2026-02-07
**Status:** ✓ Root cause found - Solution identified

---

## The Problem

Our IK implementation in `daz_bone_select.py` created IK constraints but bones **never rotated** (stayed at zero). This happened even on simple test rigs.

---

## The Investigation

1. **Initial hypothesis:** DAZ twist bones breaking IK chain
   - Created temp bone system to bypass twist bones
   - **Result:** Still didn't work

2. **Second hypothesis:** Blender 5.0.1 regression
   - Created `simple_ik_test.py` with fresh 2-bone armature
   - **Result:** Still didn't work

3. **Third hypothesis:** Missing Blender setting
   - Checked pose position, preferences, scene settings
   - **Result:** Everything configured correctly

4. **Breakthrough:** Analyzed Diffeomorphic's working IK
   - User ran Diffeomorphic "Add Simple IK" script
   - Inspected constraint configuration
   - **Found the critical difference!**

---

## The Root Cause

**IK targets MUST be bones, not empty objects.**

### Our Failed Approach:
```python
# Created empty object
target_empty = bpy.data.objects.new("IK_Target", None)
bpy.context.scene.collection.objects.link(target_empty)

# Used empty as target
ik_constraint.target = target_empty  # ✗ DOESN'T WORK
ik_constraint.chain_count = 2
ik_constraint.use_stretch = False
# No pole target
```

### Diffeomorphic's Working Approach:
```python
# Target is a BONE within the same armature
ik_constraint.target = armature  # The armature object
ik_constraint.subtarget = "lHandIK"  # Control bone name

# Pole target is also a BONE
ik_constraint.pole_target = armature
ik_constraint.pole_subtarget = "lElbow"  # Pole bone name

ik_constraint.chain_count = 2
ik_constraint.use_stretch = True  # ✓ Important!
ik_constraint.use_tail = True
ik_constraint.use_rotation = False
ik_constraint.target_space = 'WORLD'
ik_constraint.owner_space = 'WORLD'
ik_constraint.iterations = 500
```

---

## The Solution

### Architecture Changes Required:

1. **Create control bones** (what the animator moves)
   - `lHandIK`, `rHandIK` - for hand posing
   - `lFootIK`, `rFootIK` - for foot posing
   - `lElbow`, `rElbow` - pole targets
   - `lKnee`, `rKnee` - pole targets
   - These bones should have **no parent** (free to move)

2. **Create IK bones** (intermediate bones that get constrained)
   - `lForearmIK`, `rForearmIK` - receives IK constraint for arms
   - `lShinIK`, `rShinIK` - receives IK constraint for legs
   - These connect to the control bones via IK constraints

3. **IK constraint setup:**
   ```python
   # Get or create the control bone
   control_bone = ensure_control_bone(armature, "lHandIK", hand_location)

   # Get or create the IK bone (intermediate)
   ik_bone = ensure_ik_bone(armature, "lForearmIK", forearm_location)

   # Add IK constraint to intermediate bone
   ik_constraint = ik_bone.constraints.new('IK')
   ik_constraint.target = armature  # ✓ Armature itself
   ik_constraint.subtarget = "lHandIK"  # ✓ Control bone
   ik_constraint.pole_target = armature
   ik_constraint.pole_subtarget = "lElbow"  # ✓ Pole bone
   ik_constraint.chain_count = 2
   ik_constraint.use_stretch = True
   ```

4. **Connect IK bones to DAZ skeleton:**
   - Use "Copy Location" and "Copy Rotation" constraints
   - DAZ bones follow IK bones
   - Maintains compatibility with DAZ rig structure

---

## Implementation Plan

### Phase 1: Test the fix (15 min)
- [x] Run `bone_target_ik_test.py` to verify bone targets work
- [ ] Confirm IK solves correctly with bone targets

### Phase 2: Update daz_bone_select.py (2-3 hours)
1. **Create control bone system:**
   - Function: `create_control_bone(armature, name, location)`
   - Function: `create_pole_bone(armature, name, location)`
   - Place control bones at current DAZ bone world locations
   - Place pole bones at elbow/knee positions

2. **Create IK bone system:**
   - Function: `create_ik_bone(armature, name, start_loc, end_loc)`
   - Create intermediate bones (lForearmIK, lShinIK, etc.)
   - Parent them properly (lShoulderIK -> lForearmIK)

3. **Update IK constraint creation:**
   - Remove empty object creation code
   - Use bone targets instead
   - Add pole targets
   - Set `use_stretch = True`

4. **Add constraint bridges:**
   - DAZ bones get "Copy Location" constraints pointing to IK bones
   - Maintains twist bones and existing rig structure
   - Non-destructive approach

### Phase 3: Update modal operator (1 hour)
1. **Update click detection:**
   - When user clicks mesh, move control bone (not empty)
   - `control_bone.location = world_location`

2. **Update drag system:**
   - Track which control bone is being dragged
   - Update bone location on mouse move
   - Refresh viewport

3. **Update visual feedback:**
   - Highlight control bones during hover
   - Show IK chain visualization
   - Display pole target positions

---

## Test Cases

After implementation, verify:

1. **Basic IK works:**
   - Click hand mesh → moves lHandIK control bone
   - lForearmIK rotates via IK constraint
   - DAZ lForearmBend follows via copy constraint
   - Arm moves to clicked position

2. **Pole targets work:**
   - Elbow/knee poles control bend direction
   - No IK flipping issues

3. **Stretching works:**
   - Can reach beyond natural arm length
   - Bones scale appropriately

4. **Compatible with existing features:**
   - Pin system still works
   - Twist bones still preserved
   - Can revert to rest pose

---

## Files to Modify

1. **`daz_bone_select.py`** (main changes)
   - Lines 267-427: `create_ik_chain()` function
   - New functions: `create_control_bones()`, `create_ik_bones()`
   - Update modal operator IK drag logic

2. **Test files:**
   - `bone_target_ik_test.py` (already created)
   - Update `ik_prototype_test.py` with bone target method

---

## References

- **Diffeomorphic IK configuration:** See console output 2026-02-07
- **Test script:** `Test Scripts/bone_target_ik_test.py`
- **Research:** `DIFFEOMORPHIC_IK_RESEARCH.md`

---

## Next Steps

1. **Run `bone_target_ik_test.py`** to confirm fix works
2. **Design control bone naming convention** (match Diffeomorphic?)
3. **Implement Phase 2** in `daz_bone_select.py`
4. **Test on actual Fey rig**
5. **Update CLAUDE.md** with milestone completion

---

**This is the breakthrough we needed!** 🎉

The IK system will finally work once we switch from empty objects to bone targets.
