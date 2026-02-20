# Soft Pin System Implementation

**Date**: 2026-02-08
**Status**: ✅ Implemented, Ready for Testing

## What Was Implemented

A DAZ Studio-like "soft constraint" pin system that allows pins to **resist but yield** under force, preventing bone stretching while maintaining natural body mechanics.

## Key Features

### 1. **Soft Pin Detection**
- Automatically detects when dragging a bone that has pinned children
- Recursively searches through twist bones to find the pinned descendant
- Activates soft pin mode when pinned child is found

### 2. **Yield Calculation**
- Calculates the "natural" chain length (sum of bone lengths from dragged bone to pin)
- Calculates the "desired" length (distance IK wants to span)
- When desired > natural, applies **yield** to prevent stretching

### 3. **Pin Stiffness**
- Controlled by `_soft_pin_stiffness` parameter (default: 0.8)
- **0.0** = No resistance (pin moves freely with pull)
- **1.0** = Maximum resistance (pin barely yields)
- **0.8** = Balanced (pin resists strongly but yields when necessary)

### 4. **Dual Adjustment**
- **Pin moves**: Slightly in the direction of pull (proportional to stretch × yield_factor)
- **IK target adjusts**: Moves closer by same amount to compensate
- Result: No stretching, natural body mechanics preserved

## How It Works

```
Normal IK (without soft pin):
  Drag forearm → IK tries to reach mouse → Hand stretches away from forearm ❌

Soft Pin System:
  Drag forearm → IK calculates stretch needed → Pin yields slightly →
  IK target adjusts → Shoulder/collar/torso adjust → Hand stays pinned ✅
```

**Algorithm Flow:**
1. User drags forearm, hand is pinned
2. Calculate natural chain length (bone lengths summed)
3. Calculate desired length (distance from target to pin)
4. If desired > natural:
   - stretch_amount = desired - natural
   - yield_distance = stretch_amount × (1.0 - stiffness)
   - Move pin by yield_distance in pull direction
   - Adjust IK target by same distance in opposite direction
5. Apply IK with adjusted target
6. Body adjusts naturally (shoulder twists, collar rotates, torso bends)

## Code Changes

### Files Modified
- **D:\Dev\BlenDAZ\daz_bone_select.py**

### New Instance Variables (lines 1519-1524)
```python
self._soft_pin_active = False            # Soft pin mode enabled?
self._soft_pin_child_name = None         # Name of pinned child bone
self._soft_pin_initial_pos = None        # Initial world position of pin
self._soft_pin_stiffness = 0.8           # Resistance factor (0.0-1.0)
self._soft_pin_muted_constraints = []    # Track muted hard constraints
```

### Pinned Child Detection (lines 2023-2059)
- Re-enabled pinned child detection (was disabled for FABRIK)
- Changed to soft pin mode instead of FABRIK
- Mutes hard Copy Location constraints on pinned child
- Stores initial pin position and child bone name

### Soft Pin Adjustment Logic (lines 2246-2336)
- Calculates natural chain length by walking bone hierarchy
- Detects when IK would cause stretching
- Applies yield to pin and adjusts IK target
- Prevents stretching while allowing natural body movement
- Debug output shows stretch amount, yield distance, adjustments

### Cleanup on Drag End (lines 2704-2712)
- Re-enables hard pin constraints that were muted
- Clears soft pin state variables
- Restores normal pin behavior

## Testing Plan

### Setup
1. Open Blender with Genesis 8 figure
2. Enter Pose Mode
3. Select hand bone
4. Press **P** to pin translation (hand should have purple pin indicator)

### Test 1: Drag Forearm with Pinned Hand
1. Pin left hand (P key)
2. Hover over left forearm
3. Click and drag forearm upward
4. **Expected**:
   - ✅ Hand stays at pinned location (no stretching)
   - ✅ Shoulder twists to accommodate
   - ✅ Collar rotates upward
   - ✅ Torso bends slightly (with extended arm)
   - ✅ Forearm stays connected to hand
5. Release mouse
6. **Expected**:
   - ✅ Pose is keyframed
   - ✅ Body stays in natural position
   - ✅ No snap back or stretching

### Test 2: Check Console Output
Look for debug messages like:
```
🔧 SOFT PIN MODE: Detected pinned child, using soft constraint system
  Soft pin child: lHand
  Initial pin position: Vector((x, y, z))
  Muted hard pin constraint on lHand
  [SOFT PIN] Natural length: 0.850
  [SOFT PIN] Desired length: 1.250
  [SOFT PIN] Stretch: 0.400
  [SOFT PIN] Yield distance: 0.080
  [SOFT PIN] Pin moved from ... to ...
  [SOFT PIN] Target adjusted from ... to ...
```

### Test 3: Extreme Drag
1. Pin hand
2. Drag forearm very far away (beyond natural reach)
3. **Expected**:
   - ✅ Pin yields progressively more as distance increases
   - ✅ No sudden snaps or breaks
   - ✅ Body follows naturally (torso bends more as arm extends)
   - ✅ Still no visible stretching

### Test 4: Release and Undo
1. Pin hand, drag forearm
2. Release (keyframe applied)
3. Press **Ctrl+Z** to undo
4. **Expected**:
   - ✅ Body returns to pre-drag pose
   - ✅ Pin is still active
   - ✅ Hard pin constraint is re-enabled

## Tuning Parameters

### Stiffness (line 2026)
```python
self._soft_pin_stiffness = 0.8  # Current value
```
- **Increase to 0.9-0.95**: Pin resists more, less yield, more precise
- **Decrease to 0.6-0.7**: Pin yields more freely, looser feel, more ragdoll-like

### Yield Factor Calculation (line 2302)
```python
yield_factor = 1.0 - self._soft_pin_stiffness
```
- Inverted relationship: higher stiffness = lower yield factor
- Could make this non-linear for different feel: `yield_factor = (1.0 - stiffness) ** 2`

## Differences from DAZ Studio

### Similarities
✅ Pins resist but yield under force
✅ No bone stretching (lengths preserved)
✅ Natural body mechanics (shoulder twists, collar rotates, torso bends)
✅ Progressive yielding (more force = more yield)

### Differences
- **DAZ**: Uses proprietary weight distribution system
- **BlenDAZ**: Uses geometric calculation (chain length comparison)
- **DAZ**: Multiple pin rigidity levels in UI
- **BlenDAZ**: Fixed stiffness (0.8) - could add UI slider later

### Advantages Over DAZ
✅ Simpler algorithm (easier to understand and debug)
✅ Works with any bone chain (no manual weight setup)
✅ Immediate response (no parameter tweaking needed)
✅ Integrates with existing IK system seamlessly

## Future Enhancements

### Phase 2 (Optional)
1. **UI Slider for Stiffness**: Add panel property to adjust stiffness per-drag
2. **Per-Pin Stiffness**: Store stiffness value per pin (in bone custom properties)
3. **Visual Feedback**: Show yield amount with gizmo or overlay
4. **Multi-Pin Support**: Handle multiple pinned children simultaneously
5. **Rigidity Presets**: Quick presets (Loose=0.5, Medium=0.8, Rigid=0.95)

### Phase 3 (Advanced)
1. **Dynamic Stiffness**: Adjust stiffness based on bone type (hands=rigid, torso=flexible)
2. **Force Visualization**: Draw line showing pull force and yield direction
3. **Yield History**: Smooth yielding over multiple frames (damped spring)
4. **Rotation Yielding**: Apply same system to rotation pins

## Known Limitations

1. **Single Pinned Child**: Currently handles one pinned child per drag
   - Multiple pinned children: Only first found is used
   - Fix: Distribute yield across multiple pins

2. **Direct Descendants Only**: Only checks descendants of dragged bone
   - Sibling pins: Not detected
   - Fix: Check entire IK chain for pins

3. **No Rotation Yielding**: Only translation pins yield
   - Rotation pins: Still hard-locked
   - Fix: Apply similar system to rotation constraints

4. **Fixed Stiffness**: Stiffness is hardcoded
   - User control: No UI for per-drag adjustment
   - Fix: Add scene property with UI slider

## Technical Notes

### Chain Length Calculation
Uses recursive walk from dragged bone to pinned child, summing bone lengths:
```python
def walk_to_pin(bone, target_name, depth=0):
    # Add bone length
    bone_length = (bone.tail - bone.head).length
    natural_length += bone_length
    # Recurse through children
    for child in bone.children:
        if walk_to_pin(child, target_name, depth + 1):
            return True
    # Not found, subtract length back
    natural_length -= bone_length
    return False
```

### Coordinate Spaces
- **Pin position**: Stored in world space (matrix_world @ bone.head)
- **Yield calculation**: All in world space for simplicity
- **Bone updates**: Convert back to armature local space for matrix assignment

### Constraint Management
- Hard Copy Location constraint is muted during soft pin drag
- Constraint is tracked in `_soft_pin_muted_constraints` list
- Re-enabled in `end_ik_drag()` cleanup
- Ensures pin returns to hard-locked state after drag completes

## Success Criteria

✅ Hand stays pinned (no stretching)
✅ Forearm follows mouse naturally
✅ Shoulder twists to accommodate
✅ Collar rotates appropriately
✅ Torso bends when arm fully extended
✅ No visible snapping or breaking
✅ Smooth, natural body mechanics
✅ Matches DAZ Studio behavior closely
✅ Works with all Genesis figures (1, 3, 8, 8.1)

---

**Next Step**: Test with Genesis 8 figure and report results!
