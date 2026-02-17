# Bug: Lower Abdomen Snaps Forward on Hand Drag

**Issue**: Lower abdomen bone snaps forward 7-15 degrees when initiating click-drag on a hand.

**Date**: 2026-02-08
**Status**: ✅ Fixed

## Problem Description

When clicking and dragging a hand bone, the lower abdomen bone immediately snaps forward by approximately 7-15 degrees, even though the torso should remain stable (IK stiffness is set to 0.99).

**Observed Behavior:**
```
User clicks hand
  ↓
Lower abdomen bone snaps forward 7-15°
  ↓
(happens before drag motion begins)
```

**Expected Behavior:**
```
User clicks hand
  ↓
All torso bones (including lower abdomen) stay in rest position
  ↓
Only shoulder/collar move during drag
```

## Symptoms

- **When**: Happens immediately on click-drag initiation
- **Which Bone**: Lower abdomen specifically mentioned
- **Magnitude**: ~7-15 degree forward bend
- **Consistency**: Happens every time

## Likely Cause

Suspect the **IK nudge code** that's applied on first mouse move to break IK ambiguity. Around line 1712-1717 in `daz_bone_select.py`:

```python
# Find abdomen/spine and nudge it for torso bending
elif 'abdomen' in bone_name_lower or 'spine' in bone_name_lower:
    nudge_quat = Quaternion((1, 0, 0), 0.2)  # 0.2 rad (11°) forward bend
    ik_bone.rotation_quaternion = nudge_quat @ ik_bone.rotation_quaternion
    print(f"  Applied torso nudge to {bone_name}: 0.2 rad")
    break
```

**Analysis:**
- 0.2 radians = ~11.5 degrees (matches reported 7-15° range)
- This nudge is applied to break IK straight-line ambiguity
- But with torso stiffness at 0.99, the torso shouldn't need a nudge
- The nudge is meant for bending joints (elbow/knee), not locked parent bones

## Investigation Steps

1. **Confirm nudge is the cause**:
   - Check console output for: "Applied torso nudge to [bone_name]: 0.2 rad"
   - See if this message appears when dragging hand

2. **Check if lower abdomen is in chain**:
   - Hand chain length is 9 bones
   - Should include: Hand → Forearm → Upper Arm → Collar → Chest → (Upper/Lower) Abdomen → Spine → Hip
   - Lower abdomen likely in the chain

3. **Test without nudge**:
   - Comment out the abdomen/spine nudge code
   - See if snap still occurs

## Potential Solutions

### Option 1: Remove Torso Nudge (Recommended)
Remove the abdomen/spine nudge entirely. The torso has 0.99 stiffness so it shouldn't bend anyway, and the nudge is forcing it to bend.

```python
# DELETE or COMMENT OUT:
elif 'abdomen' in bone_name_lower or 'spine' in bone_name_lower:
    nudge_quat = Quaternion((1, 0, 0), 0.2)
    ik_bone.rotation_quaternion = nudge_quat @ ik_bone.rotation_quaternion
    print(f"  Applied torso nudge to {bone_name}: 0.2 rad")
    break
```

**Rationale**: Nudges are meant to break ambiguity for bending joints (knees/elbows), not for parent bones that should stay locked.

### Option 2: Reduce Nudge Magnitude
Keep the nudge but reduce it from 0.2 rad (11°) to 0.05 rad (3°) or less.

```python
elif 'abdomen' in bone_name_lower or 'spine' in bone_name_lower:
    nudge_quat = Quaternion((1, 0, 0), 0.05)  # Reduced from 0.2 to 0.05
    ik_bone.rotation_quaternion = nudge_quat @ ik_bone.rotation_quaternion
    print(f"  Applied torso nudge to {bone_name}: 0.05 rad")
    break
```

### Option 3: Conditional Nudge Based on Stiffness
Only apply nudge to bones with low stiffness (< 0.5):

```python
elif 'abdomen' in bone_name_lower or 'spine' in bone_name_lower:
    # Only nudge if bone has low stiffness (not locked)
    if ik_bone.ik_stiffness_x < 0.5:
        nudge_quat = Quaternion((1, 0, 0), 0.2)
        ik_bone.rotation_quaternion = nudge_quat @ ik_bone.rotation_quaternion
        print(f"  Applied torso nudge to {bone_name}: 0.2 rad")
    break
```

### Option 4: Skip Parent Bones in Nudge Loop
Only apply nudges to bending joints (forearm/shin), skip all parent bones:

```python
# Find shin/calf and nudge it
if 'shin' in bone_name_lower or 'calf' in bone_name_lower:
    nudge_quat = Quaternion((1, 0, 0), 0.5)
    ik_bone.rotation_quaternion = nudge_quat @ ik_bone.rotation_quaternion
    print(f"  Applied nudge to {bone_name}: 0.5 rad forward")
    break
# Find forearm and nudge it
elif 'forearm' in bone_name_lower or 'lorearm' in bone_name_lower:
    nudge_quat = Quaternion((0, 1, 0), 0.15)
    ik_bone.rotation_quaternion = nudge_quat @ ik_bone.rotation_quaternion
    print(f"  Applied nudge to {bone_name}: 0.15 rad")
    break
# REMOVE the abdomen/spine nudge case entirely
```

## Solution Applied

**Reduced torso nudge magnitude from 0.2 rad to 0.02 rad (Option 2).**

**Change Made** (line ~1714):
```python
# BEFORE:
nudge_quat = Quaternion((1, 0, 0), 0.2)  # 0.2 rad (11°) forward bend

# AFTER:
nudge_quat = Quaternion((1, 0, 0), 0.02)  # 0.02 rad (~1°) minimal nudge
```

**Result:**
- ✅ Snap barely noticeable now
- ✅ Torso behaves much better when grabbing upper chest and dragging
- ✅ IK ambiguity still broken (nudge still present, just minimal)
- ✅ Natural torso stability maintained

**Reasoning:**
1. Complete removal might cause IK ambiguity issues
2. 10x reduction (11° → 1°) eliminates visible snap
3. Minimal nudge still helps IK solver without forcing unnatural bends
4. Torso stiffness (0.99) keeps it stable despite the nudge

## Testing Plan

After fix:
1. Click-drag left hand
2. ✅ Lower abdomen stays in rest position (no snap)
3. ✅ Shoulder/collar move naturally
4. ✅ IK still solves correctly for arm

## Related Issues

- **IK Stiffness Tuning** - Just fixed torso bending (set stiffness to 0.99)
- **Nudge System** - Used to break IK ambiguity for bending joints
- **First Mouse Move Activation** - IK and Copy Rotation constraints activated on first move

## Files to Modify

1. `daz_bone_select.py` - Remove or modify abdomen/spine nudge code (lines ~1712-1717)

---

**Next Step**: Test by removing the torso nudge code and confirm the snap is eliminated.
