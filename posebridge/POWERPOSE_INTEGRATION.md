# PowerPose-Style Control Integration

**Date:** 2026-02-15
**Status:** Complete - Ready for Testing

## Overview

PoseBridge now uses **DAZ PowerPose-style 4-way directional controls** for bone rotation. Each control point supports four distinct rotation modes based on mouse button (LMB/RMB) and drag direction (horizontal/vertical).

## What Changed

### 1. Control Point Definitions Updated

**File:** `d:\dev\BlenDAZ\daz_shared_utils.py`

Each control point now includes a `controls` dictionary with 4 mappings:

```python
{
    'id': 'head',
    'bone_name': 'head',
    'label': 'Head',
    'group': 'head',
    'controls': {
        'lmb_horiz': 'Z',  # Left mouse + horizontal → Z-axis rotation
        'lmb_vert': 'X',   # Left mouse + vertical → X-axis rotation
        'rmb_horiz': 'Y',  # Right mouse + horizontal → Y-axis rotation
        'rmb_vert': 'X'    # Right mouse + vertical → X-axis rotation
    }
}
```

**Control Points Defined (Single Bone Only):**
- **Head & Neck:** head, neckUpper, neckLower (3 controls)
- **Torso:** chestUpper, chestLower, abdomenUpper, abdomenLower, pelvis (5 controls)
- **Left Arm:** lCollar, lShldrBend, lForearmBend, lHand (4 controls)
- **Right Arm:** rCollar, rShldrBend, rForearmBend, rHand (4 controls)
- **Left Leg:** lThigh, lShin, lFoot (3 controls)
- **Right Leg:** rThigh, rShin, rFoot (3 controls)

**Total: 22 control points** (all single-bone, no groups)

### 2. New Helper Functions Added

**File:** `d:\dev\BlenDAZ\daz_shared_utils.py`

#### `get_rotation_axis_from_control(bone_name, mouse_button, is_horizontal)`
Returns the appropriate rotation axis ('X', 'Y', 'Z', or None) based on:
- Which bone is being controlled
- Which mouse button is pressed ('LEFT' or 'RIGHT')
- Whether drag is primarily horizontal or vertical

#### `apply_rotation_from_delta_directional(bone, initial_rotation, mouse_button, delta_x, delta_y, sensitivity)`
Applies rotation using PowerPose-style directional mapping:
1. Determines if drag is primarily horizontal or vertical
2. Gets appropriate rotation axis from control mapping
3. Applies rotation using that axis

### 3. Interaction System Updated

**File:** `d:\dev\BlenDAZ\daz_bone_select.py`

The `update_rotation()` method now uses the new directional control system:

**Before (complex special-case logic):**
```python
# Separate logic for head, torso, and other bones
if is_head:
    # Special head rotation code
elif is_torso:
    # Special torso rotation code
else:
    # Generic rotation code
```

**After (unified directional system):**
```python
# Single unified call for all bones
apply_rotation_from_delta_directional(
    self._rotation_bone,
    self._rotation_initial_quat,
    self._rotation_mouse_button,  # 'LEFT' or 'RIGHT'
    delta_x,
    delta_y,
    sensitivity
)
```

## Control Mapping Reference

### Head
| Input | Axis | Action | Description |
|-------|------|--------|-------------|
| LMB Horizontal | Z | Turn | Turn head left/right (looking around) |
| LMB Vertical | X | Nod | Tilt head up/down (nodding yes) |
| RMB Horizontal | Y | Side Tilt | Tilt ear to shoulder |
| RMB Vertical | X | Fine Tilt | Subtle forward/back adjustment |

### Neck (neckUpper, neckLower)
| Input | Axis | Action | Description |
|-------|------|--------|-------------|
| LMB Horizontal | Z | Rotate | Rotate neck left/right |
| LMB Vertical | X | Bend | Bend neck forward/back |
| RMB Horizontal | Y | Side Bend | Bend neck to side |
| RMB Vertical | - | - | Not used |

### Torso (chestUpper, chestLower, abdomenUpper, abdomenLower, pelvis)
| Input | Axis | Action | Description |
|-------|------|--------|-------------|
| LMB Horizontal | Z | Twist | Twist/rotate torso |
| LMB Vertical | X | Bend | Bend forward/backward |
| RMB Horizontal | Y | Side Lean | Lean left/right |
| RMB Vertical | Y | Twist (Alt) | Alternative twist control |

### Shoulders (lCollar, rCollar)
| Input | Axis | Action | Description |
|-------|------|--------|-------------|
| LMB Horizontal | Z | Shrug/Drop | Shoulder up/down |
| LMB Vertical | X | Forward/Back | Shoulder forward/backward |
| RMB Horizontal | Y | Roll | Shoulder roll |
| RMB Vertical | - | - | Not used |

### Upper Arms (lShldrBend, rShldrBend)
| Input | Axis | Action | Description |
|-------|------|--------|-------------|
| LMB Horizontal | X | Swing | Arm swing forward/back |
| LMB Vertical | Z | Raise/Lower | Raise/lower arm |
| RMB Horizontal | Y | Twist | Arm twist (palm up/down) |
| RMB Vertical | - | - | Not used |

### Forearms (lForearmBend, rForearmBend)
| Input | Axis | Action | Description |
|-------|------|--------|-------------|
| LMB Horizontal | - | - | Limited movement |
| LMB Vertical | X | Bend Elbow | Main elbow bend |
| RMB Horizontal | Y | Twist | Forearm twist |
| RMB Vertical | - | - | Not used |

### Hands (lHand, rHand)
| Input | Axis | Action | Description |
|-------|------|--------|-------------|
| LMB Horizontal | Z | Side-to-Side | Hand bend left/right |
| LMB Vertical | X | Up/Down | Hand bend up/down |
| RMB Horizontal | Y | Twist | Hand twist |
| RMB Vertical | - | - | Not used |

### Thighs (lThigh, rThigh)
| Input | Axis | Action | Description |
|-------|------|--------|-------------|
| LMB Horizontal | X | Swing | Leg swing forward/back |
| LMB Vertical | Z | Raise/Lower | Raise/lower leg |
| RMB Horizontal | Y | Twist | Thigh twist inward/outward |
| RMB Vertical | Y | Side Move | Move leg away/toward body |

### Shins (lShin, rShin)
| Input | Axis | Action | Description |
|-------|------|--------|-------------|
| LMB Horizontal | - | - | Limited movement |
| LMB Vertical | X | Bend Knee | Main knee bend |
| RMB Horizontal | Y | Twist | Shin twist |
| RMB Vertical | - | - | Not used |

### Feet (lFoot, rFoot)
| Input | Axis | Action | Description |
|-------|------|--------|-------------|
| LMB Horizontal | Z | Side Tilt | Foot tilt inward/outward |
| LMB Vertical | X | Point/Flex | Foot point/flex |
| RMB Horizontal | Y | Twist | Foot twist |
| RMB Vertical | - | - | Not used |

## How It Works

### Mouse Interaction Flow

1. **User hovers** over control point → Control point highlights yellow
2. **User clicks** (LMB or RMB) → Button state tracked in `_rotation_mouse_button`
3. **User drags** → System calculates delta_x (horizontal) and delta_y (vertical)
4. **System determines** primary drag direction:
   - If `abs(delta_x) > abs(delta_y)` → Horizontal drag
   - Otherwise → Vertical drag
5. **System looks up** rotation axis from control mapping table
6. **System applies** rotation around that axis
7. **User releases** → Rotation keyframed (if auto-keyframe enabled)

### Example: Rotating Head

**Scenario 1: Turn head left/right**
- User left-clicks head control point
- User drags horizontally (left/right)
- System detects: `mouse_button='LEFT'`, `is_horizontal=True`
- Looks up: `controls['lmb_horiz']` → `'Z'`
- Applies: Z-axis rotation (head turns)

**Scenario 2: Nod head up/down**
- User left-clicks head control point
- User drags vertically (up/down)
- System detects: `mouse_button='LEFT'`, `is_horizontal=False`
- Looks up: `controls['lmb_vert']` → `'X'`
- Applies: X-axis rotation (head nods)

**Scenario 3: Tilt head side-to-side**
- User right-clicks head control point
- User drags horizontally
- System detects: `mouse_button='RIGHT'`, `is_horizontal=True`
- Looks up: `controls['rmb_horiz']` → `'Y'`
- Applies: Y-axis rotation (head tilts ear to shoulder)

## Files Modified

### Updated Files
1. **`d:\dev\BlenDAZ\daz_shared_utils.py`**
   - Updated `get_genesis8_control_points()` with 4-way control mappings
   - Added `get_rotation_axis_from_control()` function
   - Added `apply_rotation_from_delta_directional()` function

2. **`d:\dev\BlenDAZ\daz_bone_select.py`**
   - Updated `update_rotation()` to use new directional system
   - Simplified from ~70 lines of special-case logic to ~15 lines

### New Files
1. **`d:\dev\BlenDAZ\posebridge\Posebridge_Control_Node_Map.md`**
   - Comprehensive control mapping reference document
   - Implementation guidelines
   - Bone name mapping reference

2. **`d:\dev\BlenDAZ\posebridge\POWERPOSE_INTEGRATION.md`** (this file)
   - Integration summary
   - Usage guide
   - Testing instructions

## Bone Groups Excluded

As requested, **multi-bone group controls have been excluded** from this update. The control point definitions now only include single-bone controls (`bone_name` field only, no `bone_names` arrays).

**Excluded (from previous implementation):**
- `neck_group` (head + neckUpper + neckLower) - diamond shape
- `lShldr` / `rShldr` multi-bone (ShldrBend + ShldrTwist)
- `lForeArm` / `rForeArm` multi-bone (ForearmBend + ForearmTwist)

**Current implementation:** Each bone has its own individual control point.

## Testing Instructions

### Prerequisites
1. Fresh Blender restart (to clear Python module cache)
2. Genesis 8 character loaded in T-pose
3. PoseBridge outline generated and positioned at Z=-50m

### Test Sequence

#### Test 1: Head Controls (4-way)
1. Start PoseBridge mode
2. Hover over head control point (should highlight yellow)
3. **Left-click + drag horizontally** → Head should turn left/right (Z-axis)
4. **Left-click + drag vertically** → Head should nod up/down (X-axis)
5. **Right-click + drag horizontally** → Head should tilt ear to shoulder (Y-axis)

#### Test 2: Torso Controls
1. Hover over chestUpper control point
2. **Left-click + drag horizontally** → Torso should twist (Z-axis)
3. **Left-click + drag vertically** → Torso should bend forward/back (X-axis)
4. **Right-click + drag horizontally** → Torso should lean side-to-side (Y-axis)

#### Test 3: Arm Controls
1. Test lCollar (shoulder):
   - **LMB horizontal** → Shrug/drop shoulder
   - **LMB vertical** → Shoulder forward/back
   - **RMB horizontal** → Shoulder roll

2. Test lShldrBend (upper arm):
   - **LMB horizontal** → Arm swing forward/back
   - **LMB vertical** → Raise/lower arm
   - **RMB horizontal** → Arm twist

3. Test lForearmBend (forearm):
   - **LMB vertical** → Bend elbow (main control)
   - **RMB horizontal** → Forearm twist

4. Test lHand (hand):
   - **LMB horizontal** → Hand bend side-to-side
   - **LMB vertical** → Hand bend up/down
   - **RMB horizontal** → Hand twist

#### Test 4: Leg Controls
1. Test lThigh:
   - **LMB horizontal** → Leg swing forward/back
   - **LMB vertical** → Raise/lower leg
   - **RMB horizontal** → Thigh twist

2. Test lShin:
   - **LMB vertical** → Bend knee (main control)
   - **RMB horizontal** → Shin twist

3. Test lFoot:
   - **LMB horizontal** → Foot tilt side-to-side
   - **LMB vertical** → Foot point/flex
   - **RMB horizontal** → Foot twist

### Expected Behavior

✅ **Correct:**
- Each control point responds to 2-4 different mouse input combinations
- Horizontal vs vertical drag produces different rotations
- LMB vs RMB produces different rotations
- Rotations feel intuitive and match DAZ PowerPose behavior
- Control points that don't support certain inputs (marked with `-` in tables) do nothing

❌ **Incorrect:**
- All inputs produce the same rotation
- Horizontal and vertical drags are not distinguished
- LMB and RMB produce the same result
- Rotations feel backwards or unintuitive

## Known Limitations

1. **Requires Blender Restart**: Changes to `daz_shared_utils.py` require full Blender restart due to Python module caching
2. **Genesis 8 Only**: Control point definitions are hardcoded for Genesis 8 bone names
3. **No Multi-Bone Groups**: Multi-bone controls excluded from this implementation as requested
4. **Single Panel**: Only body panel implemented (head/hands panels in future phase)

## Next Steps

### Immediate Testing
1. Test all 22 control points with different mouse button/direction combinations
2. Verify rotation axes match expected behavior from control mapping tables
3. Test edge cases (very small movements, mixed horizontal/vertical drags)

### Future Enhancements
1. **Multi-Bone Groups** (when ready):
   - Add back neck_group, shoulder groups, forearm groups
   - Use diamond shapes to distinguish from single-bone controls

2. **Panel Views**:
   - Head detail panel (eyes, jaw, facial controls)
   - Hands panels (finger controls)

3. **Visual Feedback**:
   - Show active rotation axis as visual indicator
   - Display mouse button icons near control points

4. **Customization**:
   - Allow users to remap control axes
   - Save custom control templates

## Troubleshooting

### Issue: Control points don't respond to right-click
**Solution:** Check that `_rotation_mouse_button` is being set correctly in `daz_bone_select.py` (lines ~2114 and ~2161)

### Issue: Horizontal and vertical drags produce same rotation
**Solution:** Verify `apply_rotation_from_delta_directional()` is being called (not old `apply_rotation_from_delta()`)

### Issue: Control mapping not found for a bone
**Solution:**
1. Check bone exists in `get_genesis8_control_points()`
2. Verify `bone_name` field matches actual bone name in armature
3. Ensure Blender was restarted after changes to `daz_shared_utils.py`

### Issue: Rotations feel backwards
**Solution:** Check axis mapping in control point definition - may need to invert axis or swap horizontal/vertical

## Success Criteria

- [x] All 22 control points defined with 4-way mappings
- [x] Helper functions implemented and integrated
- [x] Interaction system updated to use directional controls
- [x] Code simplified (removed special-case logic)
- [x] Documentation complete
- [ ] User testing complete
- [ ] All control combinations verified working

## References

- [Posebridge_Control_Node_Map.md](Posebridge_Control_Node_Map.md) - Detailed control mapping reference
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Phase 1 MVP summary
- [scratchpad.md](scratchpad.md) - Testing notes and current status

---

**Status:** Ready for testing
**Blocking Issues:** None
**Required:** Fresh Blender restart to load new control definitions
