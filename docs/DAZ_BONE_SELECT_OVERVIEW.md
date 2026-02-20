# DAZ Bone Select & Pin & PowerPose - Script Overview

**Version**: 1.2.0
**Purpose**: Advanced bone selection, IK dragging, and posing system for Genesis 8 DAZ rigs in Blender

---

## Overview

This Blender addon provides a complete posing workflow for DAZ Genesis 8 character rigs, combining:
- **Hover preview** - See bone names as you move the mouse
- **Click-to-select** - Select bones by clicking on the mesh
- **Pin system** - Mark bones as fixed points for IK solving
- **IK dragging** - Click and drag bones with automatic IK chain creation
- **Template-based rigging** - Pre-defined optimal IK setups for consistent behavior

---

## Key Features

### 1. Intelligent Bone Selection
- **Raycast-based** - Click anywhere on the mesh to select the underlying bone
- **Base mesh detection** - Automatically finds Genesis 8 base mesh among clothing/hair
- **Hover preview** - Bone name shown in viewport header before clicking
- **Twist bone filtering** - Skips non-poseable twist bones in selection

### 2. Pin System
- **Translation pins** (📍) - Lock bone location in world space
- **Rotation pins** (🔒) - Lock bone rotation in world space
- **Visual indicators** - Color-coded spheres show pin status
- **Soft pin mode** - Lever/fulcrum posing (pin parent, drag child)

### 3. IK Dragging System
- **Automatic IK chains** - Creates temporary IK bones on-the-fly
- **Template-based** - Uses pre-defined optimal settings for each bone type
- **Pole targets** - Prevents arm twisting and unnatural IK solutions
- **Pose preservation** - Rotations maintained between multiple drags
- **Copy Rotation constraints** - Ensures DAZ bones follow IK bones smoothly

### 4. Special Bone Handling
- **Pectoral bones** - Uses Blender's native trackball rotate (not IK)
- **Torso stability** - High stiffness prevents torso from bending during arm drags
- **Collar guidance** - Damped Track constraints for natural shoulder movement
- **Leg pre-bend** - Automatic knee direction hint to prevent hyperextension

---

## Architecture

### IK Template System (NEW!)

Instead of calculating everything dynamically, the script uses **pre-defined templates** for consistent, predictable behavior:

```python
IK_RIG_TEMPLATES = {
    'hand': {
        'chain_length': 4,  # collar → shoulder → forearm → hand
        'stiffness': {
            'collar': 0.75,
            'shoulder': 0.1,
            'forearm': 0.0,
            'hand': 0.0
        },
        'pole_target': {
            'enabled': True,
            'method': 'perpendicular_to_line',
            'distance_multiplier': 2.0
        }
    }
}
```

**Templates defined for:**
- `hand` - Full arm IK chain
- `forearm` - Shorter arm chain
- `foot` - Full leg IK chain
- `shin` - Shorter leg chain

**Template lookup**: `get_ik_template(bone_name)` identifies which template to use

**Pole calculation**: `calculate_pole_position()` uses current pose to position pole target naturally

### IK Chain Structure

When you drag a bone, the script creates:

1. **.ik control bones** - Mirror of DAZ bones, receive IK constraint
2. **.ik.target bone** - What you drag (parentless, follows mouse)
3. **Copy Rotation constraints** - DAZ bones copy .ik bone rotations
4. **Pole target bone** (if template specifies) - Stabilizes IK solution
5. **Shoulder target bones** (for arms) - Guides collar with Damped Track

**Chain hierarchy:**
```
DAZ Bones (posed rig)
    ↓ Copy Rotation
.ik Bones (IK control chain)
    ↓ IK Constraint targets →
.ik.target Bone (follows mouse)

Pole Target (prevents twisting)
    ↑ IK Constraint uses
```

### Coordinate Space Handling

**Critical insight:** Blender's Edit mode always shows bones at REST positions, not POSED positions.

**Solution:**
1. **Capture posed positions BEFORE mode switch** (in POSE mode)
   ```python
   posed_positions = {}
   for bone in chain:
       bone_eval = armature_eval.pose.bones[bone.name]
       posed_positions[bone.name] = {
           'head': armature.matrix_world @ Vector(bone_eval.head),
           'tail': armature.matrix_world @ Vector(bone_eval.tail)
       }
   ```

2. **Create .ik bones at posed positions** (in EDIT mode)
   ```python
   ik_edit.head = armature_inv @ posed_positions[bone.name]['head']
   ik_edit.tail = armature_inv @ posed_positions[bone.name]['tail']
   ```

3. **Copy rotations to .ik bones** (back in POSE mode)
   ```python
   ik_bone.rotation_quaternion = daz_bone_eval.matrix_basis.to_quaternion()
   ```

This ensures IK starts from the CURRENT pose, not REST pose.

---

## Main Components

### Modal Operator: `DAZ_OT_bone_select_pin`

**Modes:**
- `IDLE` - Hover detection, waiting for click
- `DRAGGING_IK` - Dragging bone with IK chain
- `ROTATING` - Rotating pectoral bone with trackball

**Key Methods:**
- `modal()` - Event handling loop
- `check_hover()` - Raycast to find bone under mouse
- `select_bone()` - Select clicked bone with mode switching
- `start_ik_drag()` - Create IK chain and begin drag
- `update_ik_drag()` - Update target position during drag
- `end_ik_drag()` - Clean up IK chain and keyframe results

### Core Functions

**`create_ik_chain(armature, bone_name, ...)`**
- Looks up IK template for bone type
- Builds chain walking up parent hierarchy (skipping twist bones)
- Captures posed positions before Edit mode
- Creates .ik bones, target bone, pole target (from template)
- Sets IK stiffness from template
- Adds Copy Rotation constraints
- Returns: `(target_name, ik_names, daz_names, shoulder_targets, prebend_flag)`

**`dissolve_ik_chain(armature, target_name, ...)`**
- Removes IK and Copy Rotation constraints
- Keyframes DAZ bones (preserves pose)
- Deletes temporary .ik bones
- Restores non-IK bone rotations (preserves rest of pose)

**`calculate_pole_position(template, posed_positions, ...)`**
- Uses template's pole configuration
- Method: "perpendicular_to_line"
  - Projects elbow/knee position perpendicular to shoulder-hand / hip-foot line
  - Extends 2x the offset for visibility and stability
- Returns world space pole head/tail positions

---

## Workflow Example

### Hand Drag Sequence

1. **User clicks hand**
   - Raycast finds "lHand" bone
   - `get_ik_template('lHand')` → returns 'hand' template

2. **Create IK chain**
   - Chain length: 4 (from template)
   - Captures posed positions of: lCollar, lShldrBend, lForearmBend, lHand
   - Switches to Edit mode
   - Creates .ik bones at posed positions
   - Creates .ik.target at hand position
   - Calculates pole position (elbow perpendicular to shoulder-hand line)
   - Creates .pole bone at calculated position
   - Switches back to Pose mode

3. **Setup constraints**
   - Adds IK constraint on lHand.ik → targets lHand.ik.target, uses .pole
   - Sets stiffness: collar=0.75, shoulder=0.1, forearm=0.0
   - Adds Copy Rotation: lCollar → lCollar.ik, etc.
   - Adds Damped Track: lCollar → lCollar.shoulder.target
   - Sets all constraint influences to 0.0 (activate on first move)

4. **User drags mouse**
   - `update_ik_drag()` called each mouse move
   - Calculates 3D mouse position using `region_2d_to_location_3d`
   - Moves .ik.target to follow mouse (delta-based)
   - First move: activates IK + Copy Rotation simultaneously
   - IK solver uses pole target to prevent arm twisting

5. **User releases mouse**
   - `end_ik_drag()` called
   - Keyframes DAZ bones (lCollar, lShldrBend, lForearmBend)
   - Skips tip bone keyframe (preserves manual rotations)
   - Dissolves IK chain (removes constraints + temp bones)
   - Rotations preserved via caching through mode switches

6. **Ready for next drag**
   - Pose is maintained (not snapped to rest)
   - Second drag starts from CURRENT pose (not rest)
   - Pole target recalculated for new arm position

---

## Technical Details

### IK Stiffness Values

From templates (or fallback defaults):

| Bone Type | Stiffness | Purpose |
|-----------|-----------|---------|
| Hand/Foot | 0.0 | Bends freely (end effector) |
| Forearm/Shin | 0.0 | Main bend point |
| Shoulder | 0.1 | Very flexible for natural movement |
| Collar | 0.75 | Stable but allows some motion |
| Thigh | 0.2 | Some resistance for stability |
| Chest/Spine | 0.99 | Essentially locked (torso stable) |
| Hip | 0.99 | Locked (prevents character spinning) |

**Lower stiffness = bends first**
**Higher stiffness = only moves when necessary**

### Pole Target Angle

All pole targets use: `pole_angle = -1.5708` (-90° / -π/2)

This is standard for DAZ/MHX rigs and aligns the pole direction correctly.

### Rotation Preservation

**Problem:** Blender's mode switches (POSE → EDIT → POSE) discard un-keyframed rotations.

**Solution:** Cache and restore rotations around EVERY mode switch:

```python
# Before EDIT mode
rotation_cache = {}
for bone in armature.pose.bones:
    rotation_cache[bone.name] = bone.rotation_quaternion.copy()

# ... do mode switch ...

# After POSE mode
for bone_name, rotation in rotation_cache.items():
    armature.pose.bones[bone_name].rotation_quaternion = rotation
```

Applied in:
- `create_ik_chain()` - Line ~716
- `dissolve_ik_chain()` - Line ~1406
- `select_bone()` - Line ~2590
- `cleanup_temp_ik_chains()` - Line ~3947

### Pre-Bend System

**Purpose:** Break IK ambiguity for straight limbs (especially legs)

**How it works:**
1. Collect first 2 mouse samples during drag
2. Calculate mouse direction (screen space)
3. Apply small rotation (0.5 rad / ~29°) to shin/forearm
4. Direction depends on mouse movement (forward/back/sideways)
5. Only applies if limb is nearly straight (prevents overriding existing bend)

**Result:** Gives IK solver a "hint" about which way to bend the knee/elbow

---

## Bug Fixes & Improvements

### Major Issues Resolved

1. **✅ Pectoral Rotation Space** - Fixed rotation at arbitrary armature orientations
   - Solution: Use Blender's native trackball rotate instead of manual quaternion math

2. **✅ Torso Snap on Selection** - Fixed rotation loss when selecting different bones
   - Solution: Cache/restore rotations around mode switches

3. **✅ Lower Abdomen Snap** - Fixed torso bending on hand drag initiation
   - Solution: Reduced torso nudge from 0.2 rad → 0.02 rad

4. **✅ Torso Excluded from Arm IK** - Fixed arm IK pulling torso
   - Solution: Reduced arm chain lengths to stop at collar (excludes chest/abdomen)

5. **✅ IK Chain at REST on Second Drag** - Fixed snap to rest pose on subsequent drags
   - Solution: Capture POSED positions before Edit mode, create .ik bones at posed positions

6. **✅ Arm Twisting / Wonky Behavior** - Fixed unpredictable arm movement on posed drags
   - Solution: Template-based IK with pole targets calculated from current pose

### Architecture Improvements

1. **Template-based IK System** - Replaced dynamic calculations with pre-defined optimal settings
2. **Pose-aware IK Creation** - .ik bones start at current pose, not rest
3. **Rotation Caching Pattern** - Consistent preservation across all mode switches
4. **Coordinate Space Clarity** - Clear separation of world/local/armature space transformations

---

## Debug Mode

Set `DEBUG_PRESERVE_IK_CHAIN = True` at the top of the script to:
- Keep IK chains after drag (don't auto-cleanup)
- Use Alt+X to manually clean up temp bones
- Inspect .ik bone setup in outliner

**Useful for:**
- Verifying .ik bone positions
- Checking constraint setup
- Testing pole target placement

---

## Future Enhancements

### Potential Template Additions
- `shoulder` / `collar` - Upper arm isolation
- `thigh` - Upper leg isolation
- `head` / `neck` - Head/neck IK
- `finger` / `toe` - Digit chains

### Possible Features
- User-customizable templates (JSON file)
- Multiple pole target methods
- Adaptive stiffness based on pose
- IK/FK blend slider
- Pose library integration

---

## Related Documentation

- `BUG_PECTORAL_ROTATION_SPACE.md` - Pectoral rotation fix details
- `BUG_TORSO_ROTATION_SNAP.md` - Torso preservation fix details
- `BUG_LOWER_AB_SNAP.md` - Abdomen nudge fix details
- `FIX_IK_STIFFNESS_TUNING.md` - Stiffness value rationale

---

## Technical Requirements

- **Blender**: 3.0+
- **Rig Type**: Genesis 8 DAZ rigs (standardized bone names)
- **Dependencies**: None (uses built-in Blender modules)

---

**Last Updated**: 2026-02-12
**Architecture**: Template-based IK rigging with pose-aware chain creation
