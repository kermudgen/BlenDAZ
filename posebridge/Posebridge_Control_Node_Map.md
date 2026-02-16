# PoseBridge Control Node Map

**Version:** 1.0
**Date:** 2026-02-15
**Purpose:** DAZ PowerPose-style mouse control mapping for PoseBridge viewport

## Control Scheme Overview

### Mouse Button Functions
- **LMB (Left Mouse Button)**: Primary bend/rotation controls
- **RMB (Right Mouse Button)**: Twist/secondary rotation controls

### Mouse Movement Axes
- **Horizontal**: Left/Right mouse movement (X-axis delta)
- **Vertical**: Up/Down mouse movement (Y-axis delta)

### Rotation Axes (Blender/DAZ Convention)
- **X-axis**: Side-to-side bend (left/right tilt)
- **Y-axis**: Twist (rotation around bone length)
- **Z-axis**: Forward/backward bend

---

## Head & Face Controls

### Head
**Bone**: `head`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | Rotate Head Left/Right | Z-axis | Turn head horizontally (looking left/right) |
| LMB Vertical | Tilt Head Up/Down | X-axis | Nod head (looking up/down) |
| RMB Horizontal | Side Tilt | Y-axis | Tilt head to shoulder (ear to shoulder) |
| RMB Vertical | Forward/Back Tilt | X-axis (fine) | Subtle forward/back adjustment |

**Notes**:
- Most common operation is LMB horizontal for "no" gesture
- LMB vertical for "yes" gesture
- RMB for expressive tilts

### Neck
**Bone**: `neck`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | Rotate Neck | Z-axis | Turn neck left/right |
| LMB Vertical | Bend Neck | X-axis | Bend neck forward/backward |
| RMB Horizontal | Side Bend | Y-axis | Bend neck to side |
| RMB Vertical | Twist | Y-axis (subtle) | Subtle neck twist |

### Eyes (Left/Right)
**Bones**: `eye.L`, `eye.R`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | Look Left/Right | Z-axis | Horizontal eye movement |
| LMB Vertical | Look Up/Down | X-axis | Vertical eye movement |
| RMB Horizontal | - | - | (Not typically used) |
| RMB Vertical | - | - | (Not typically used) |

**Notes**:
- Eyes should track together by default
- Option to break symmetry for independent control
- Small mouse movements = large eye rotation (high sensitivity)

### Jaw
**Bone**: `jaw`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Vertical | Open/Close Mouth | X-axis | Jaw open/close |
| LMB Horizontal | Jaw Side-to-Side | Z-axis | Jaw shift left/right |
| RMB Horizontal | Jaw Forward/Back | Y-axis | Jaw protrusion |
| RMB Vertical | - | - | (Not typically used) |

---

## Torso Controls

### Chest
**Bone**: `chest` or `spine.003` (upper spine)

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | Rotate Chest | Z-axis | Twist torso left/right |
| LMB Vertical | Bend Forward/Back | X-axis | Bend chest forward/backward |
| RMB Horizontal | Side Bend | Y-axis | Lean left/right |
| RMB Vertical | Twist | Y-axis | Spine twist |

### Abdomen
**Bone**: `spine.002` (mid spine)

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | Rotate Abdomen | Z-axis | Twist mid-torso |
| LMB Vertical | Bend Forward/Back | X-axis | Bend abdomen forward/backward |
| RMB Horizontal | Side Bend | Y-axis | Lean left/right |
| RMB Vertical | Subtle Twist | Y-axis | Fine twist control |

### Pelvis/Hips
**Bone**: `pelvis` or `spine.001`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | Rotate Hips | Z-axis | Twist hips left/right |
| LMB Vertical | Tilt Forward/Back | X-axis | Pelvic tilt |
| RMB Horizontal | Side Tilt | Y-axis | Hip drop left/right |
| RMB Vertical | - | - | (Optional: fine tilt) |

---

## Arm Controls (Left Side)

### Left Shoulder
**Bone**: `shoulder.L`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | Shrug/Drop | Z-axis | Shoulder up/down |
| LMB Vertical | Forward/Back | X-axis | Shoulder forward/backward |
| RMB Horizontal | Roll | Y-axis | Shoulder roll |
| RMB Vertical | - | - | (Not typically used) |

### Left Upper Arm
**Bone**: `upper_arm.L`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | Swing Forward/Back | X-axis | Arm swing (walking motion) |
| LMB Vertical | Raise/Lower Arm | Z-axis | Arm up/down (Y-axis in some rigs) |
| RMB Horizontal | Arm Twist | Y-axis | Rotate arm (palm up/down) |
| RMB Vertical | Side Movement | Mixed | Move arm away/toward body |

**Notes**:
- Most complex control due to shoulder's range of motion
- May need to combine rotations for natural poses

### Left Forearm
**Bone**: `forearm.L`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | - | - | (Limited movement) |
| LMB Vertical | Bend Elbow | Z-axis/X-axis | Bend elbow (main function) |
| RMB Horizontal | Forearm Twist | Y-axis | Rotate forearm (pronation/supination) |
| RMB Vertical | - | - | (Not typically used) |

**Notes**:
- Elbow is primarily a hinge joint
- Main control is LMB vertical for bend
- RMB horizontal for wrist twist propagation

### Left Hand
**Bone**: `hand.L`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | Side-to-Side | Z-axis | Hand bend left/right (radial/ulnar deviation) |
| LMB Vertical | Up/Down Bend | X-axis | Hand bend up/down (wrist flexion/extension) |
| RMB Horizontal | Hand Twist | Y-axis | Rotate hand |
| RMB Vertical | - | - | (Optional: fine control) |

### Left Fingers (Thumb, Index, Middle, Ring, Pinky)
**Bones**: `thumb.01.L` through `thumb.03.L`, `f_index.01.L` through `f_pinky.03.L`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Vertical | Curl/Uncurl | X-axis | Finger bend (main control) |
| LMB Horizontal | Spread | Z-axis | Finger spread apart/together |
| RMB Horizontal | Twist | Y-axis | Individual finger twist |
| RMB Vertical | - | - | (Not typically used) |

**Notes**:
- Fingers may use hierarchical control (curl all segments together)
- Special handling for thumb (different angle/movement)

---

## Arm Controls (Right Side)

### Right Shoulder
**Bone**: `shoulder.R`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | Shrug/Drop | Z-axis | Shoulder up/down |
| LMB Vertical | Forward/Back | X-axis | Shoulder forward/backward |
| RMB Horizontal | Roll | Y-axis | Shoulder roll |
| RMB Vertical | - | - | (Not typically used) |

### Right Upper Arm
**Bone**: `upper_arm.R`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | Swing Forward/Back | X-axis | Arm swing (walking motion) |
| LMB Vertical | Raise/Lower Arm | Z-axis | Arm up/down |
| RMB Horizontal | Arm Twist | Y-axis | Rotate arm (palm up/down) |
| RMB Vertical | Side Movement | Mixed | Move arm away/toward body |

### Right Forearm
**Bone**: `forearm.R`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | - | - | (Limited movement) |
| LMB Vertical | Bend Elbow | Z-axis/X-axis | Bend elbow (main function) |
| RMB Horizontal | Forearm Twist | Y-axis | Rotate forearm (pronation/supination) |
| RMB Vertical | - | - | (Not typically used) |

### Right Hand
**Bone**: `hand.R`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | Side-to-Side | Z-axis | Hand bend left/right |
| LMB Vertical | Up/Down Bend | X-axis | Hand bend up/down |
| RMB Horizontal | Hand Twist | Y-axis | Rotate hand |
| RMB Vertical | - | - | (Optional: fine control) |

### Right Fingers
**Bones**: `thumb.01.R` through `thumb.03.R`, `f_index.01.R` through `f_pinky.03.R`

*(Same mapping as left fingers)*

---

## Leg Controls (Left Side)

### Left Thigh
**Bone**: `thigh.L`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | Swing Forward/Back | X-axis | Leg swing (walking/kicking) |
| LMB Vertical | Raise/Lower Leg | Z-axis | Leg up/down |
| RMB Horizontal | Thigh Twist | Y-axis | Rotate thigh inward/outward |
| RMB Vertical | Side Movement | Y-axis | Move leg away/toward body (abduction/adduction) |

### Left Shin
**Bone**: `shin.L`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | - | - | (Limited movement) |
| LMB Vertical | Bend Knee | X-axis | Bend knee (main function) |
| RMB Horizontal | Shin Twist | Y-axis | Rotate lower leg |
| RMB Vertical | - | - | (Not typically used) |

**Notes**:
- Knee is primarily a hinge joint (like elbow)
- Main control is LMB vertical for bend

### Left Foot
**Bone**: `foot.L`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | Side-to-Side | Z-axis | Foot tilt inward/outward (inversion/eversion) |
| LMB Vertical | Point/Flex | X-axis | Foot point/flex (plantarflexion/dorsiflexion) |
| RMB Horizontal | Foot Twist | Y-axis | Rotate foot |
| RMB Vertical | - | - | (Optional: fine control) |

### Left Toes
**Bone**: `toe.L`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Vertical | Curl/Extend Toes | X-axis | Toe bend up/down |
| LMB Horizontal | - | - | (Limited movement) |
| RMB Horizontal | - | - | (Not typically used) |
| RMB Vertical | - | - | (Not typically used) |

---

## Leg Controls (Right Side)

### Right Thigh
**Bone**: `thigh.R`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | Swing Forward/Back | X-axis | Leg swing (walking/kicking) |
| LMB Vertical | Raise/Lower Leg | Z-axis | Leg up/down |
| RMB Horizontal | Thigh Twist | Y-axis | Rotate thigh inward/outward |
| RMB Vertical | Side Movement | Y-axis | Move leg away/toward body |

### Right Shin
**Bone**: `shin.R`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | - | - | (Limited movement) |
| LMB Vertical | Bend Knee | X-axis | Bend knee (main function) |
| RMB Horizontal | Shin Twist | Y-axis | Rotate lower leg |
| RMB Vertical | - | - | (Not typically used) |

### Right Foot
**Bone**: `foot.R`

| Input | Action | Rotation Axis | Description |
|-------|--------|---------------|-------------|
| LMB Horizontal | Side-to-Side | Z-axis | Foot tilt inward/outward |
| LMB Vertical | Point/Flex | X-axis | Foot point/flex |
| RMB Horizontal | Foot Twist | Y-axis | Rotate foot |
| RMB Vertical | - | - | (Optional: fine control) |

### Right Toes
**Bone**: `toe.R`

*(Same mapping as left toes)*

---

## Multi-bone Control Nodes

### Overview

PoseBridge supports two types of multi-bone control:

1. **Multi-bone Single Nodes**: Single control points that rotate tightly coupled bone pairs (e.g., Bend/Twist)
2. **Group Nodes**: Single control points that rotate entire hierarchical chains for broad pose control

**Visual Distinction**:
- **Regular Nodes** (single bone): Circle shape ⚫
- **Multi-bone Single Nodes**: Circle shape ⚫ (same as regular, but controls multiple bones)
- **Group Nodes**: Diamond shape ◆

### Multi-bone Single Nodes

These control points rotate coupled bone pairs simultaneously. Used for bones that work together as a unit.

**Shape**: Circle ⚫ (same as regular single-bone nodes)

| Control Node | Bones | Description |
|--------------|-------|-------------|
| **lShldr** | lShldrBend, lShldrTwist | Left shoulder rotation with twist |
| **rShldr** | rShldrBend, rShldrTwist | Right shoulder rotation with twist |
| **lForeArm** | lForearmBend, lForearmTwist | Left forearm with twist (pronation/supination) |
| **rForeArm** | rForearmBend, rForearmTwist | Right forearm with twist |
| **lThigh** | lThighBend, lThighTwist | Left thigh with twist (internal/external rotation) |
| **rThigh** | rThighBend, rThighTwist | Right thigh with twist |

**Behavior**:
- **Click**: Selects both bones, Bend bone becomes active
- **Drag**: Rotates both bones together as one unit
- **Active Bone**: Always the Bend bone (primary control bone)

### Group Nodes

Group nodes provide hierarchical control for posing entire body sections at once.

**Shape**: Diamond ◆ (distinguishes them from regular nodes)

**Anatomical Intelligence**: Group nodes containing both Bend and Twist bones automatically filter rotations by axis:
- **Y-axis (twist) rotations**: Applied to all bones including Twist bones
- **X/Z-axis (bending) rotations**: Only applied to Bend bones; Twist bones are protected from non-twist rotations
- This ensures anatomically correct movement where Twist bones only handle rotation around the bone's length axis

#### Neck Group
| Property | Value |
|----------|-------|
| **Control ID** | `neck_group` |
| **Bones** | head, neckUpper, neckLower |
| **Active Bone** | head (top of chain) |
| **Use Case** | Pose entire neck/head as one unit |

**Rotation Behavior**:
- LMB Horizontal: Y-axis rotation (turn head/neck)
- LMB Vertical: X-axis rotation (nod head/neck) - inverted
- RMB Horizontal: Z-axis rotation (tilt head/neck) - inverted
- RMB Vertical: X-axis rotation (fine forward/back) - inverted

---

#### Left Arm Group
| Property | Value |
|----------|-------|
| **Control ID** | `lArm_group` |
| **Bones** | lShldrBend, lShldrTwist, lForearmBend, lForearmTwist |
| **Active Bone** | lShldrBend (top of chain) |
| **Use Case** | Pose entire left arm from shoulder to elbow |

---

#### Right Arm Group
| Property | Value |
|----------|-------|
| **Control ID** | `rArm_group` |
| **Bones** | rShldrBend, rShldrTwist, rForearmBend, rForearmTwist |
| **Active Bone** | rShldrBend (top of chain) |
| **Use Case** | Pose entire right arm from shoulder to elbow |

---

#### Shoulders Group
| Property | Value |
|----------|-------|
| **Control ID** | `shoulders_group` |
| **Bones** | lCollar, rCollar, lShldrBend, rShldrBend |
| **Active Bone** | lCollar (left side primary) |
| **Use Case** | Pose both shoulders together (shrugging, rolling shoulders) |

---

#### Torso Group
| Property | Value |
|----------|-------|
| **Control ID** | `torso_group` |
| **Bones** | abdomenLower, abdomenUpper, chestLower, chestUpper |
| **Active Bone** | chestUpper (top of chain) |
| **Use Case** | Pose entire torso as one unit (bending, twisting) |

---

#### Left Leg Group
| Property | Value |
|----------|-------|
| **Control ID** | `lLeg_group` |
| **Bones** | lThighBend, lThighTwist, lShin |
| **Active Bone** | lThighBend (top of chain) |
| **Use Case** | Pose entire left leg from hip to knee |

---

#### Right Leg Group
| Property | Value |
|----------|-------|
| **Control ID** | `rLeg_group` |
| **Bones** | rThighBend, rThighTwist, rShin |
| **Active Bone** | rThighBend (top of chain) |
| **Use Case** | Pose entire right leg from hip to knee |

---

#### Legs Group (Both)
| Property | Value |
|----------|-------|
| **Control ID** | `legs_group` |
| **Bones** | All bones from Left Leg Group + Right Leg Group |
| **Active Bone** | lThighBend (left side primary) |
| **Use Case** | Pose both legs together (squatting, jumping poses) |

---

### Group Node Positioning

Group nodes are positioned using an `offset` property relative to a reference bone (typically the first bone in the group or the active bone).

**Offset Format**: `(x, y, z)` tuple in Blender units
- **X-axis**: Left/Right (negative = left from front view)
- **Y-axis**: Front/Back (positive = forward)
- **Z-axis**: Up/Down (positive = up)

**Current Positioning:**

| Group Node | Reference Bone | Offset | Description |
|------------|----------------|--------|-------------|
| **neck_group** | neckUpper | `(-0.075, 0, 0)` | 0.075 units to the left of upper neck |
| **lArm_group** | lShldrTwist | `(0.075, 0, 0)` | 0.075 units toward center from left shoulder twist |
| **rArm_group** | rShldrTwist | `(-0.075, 0, 0)` | 0.075 units toward center from right shoulder twist |
| **shoulders_group** | chestUpper | `(0, 0, 0.075)` | 0.075 units up from upper chest |
| **torso_group** | abdomenUpper | `(-0.1, 0, 0)` | 0.1 units to the left of upper abdomen |
| **lLeg_group** | lThighTwist | `(0.075, 0, 0)` | 0.075 units toward center from left thigh twist |
| **rLeg_group** | rThighTwist | `(-0.075, 0, 0)` | 0.075 units toward center from right thigh twist |
| **legs_group** | pelvis | `(0, 0, -0.275)` | 0.275 units down from pelvis |

**Design Goals:**
- Group nodes should be visually distinct from individual control points
- Avoid overlapping with existing control points
- Place in logical locations relative to the body section they control
- Consider outline viewport visibility and accessibility

**Future Enhancement:**
- Make group node positioning customizable in the UI
- Allow users to adjust offset values per character rig
- Save custom positioning as part of character presets

---

### Group Node Behavior

**Click Behavior**:
1. Selects all bones in the group
2. Sets the specified "Active Bone" (typically top of hierarchy)
3. All bones are selected (like Ctrl+clicking in outliner)
4. Active bone is highlighted differently (Blender's active bone highlight)

**Drag Behavior**:
1. Applies rotation to all bones in group simultaneously
2. Each bone rotates around its own pivot (Individual Origins)
3. Creates coordinated movement across the entire body section
4. **Twist Bone Filtering**: Automatically filters rotations based on bone type:
   - **Y-axis rotations (twist)**: Applied to ALL bones including Twist bones
   - **X/Z-axis rotations (bending)**: Only applied to Bend bones, Twist bones are skipped
   - Ensures anatomically correct behavior (Twist bones only twist, don't bend)

**Rotation Application**:
- Uses the same mouse control scheme as individual bones
- LMB and RMB mappings depend on the body part (see individual bone controls above)
- Sensitivity may be adjusted per group for natural feel

---

### Implementation Notes

**Selection State Management**:
```python
# When clicking a group node
for bone_name in group_bones:
    bone = armature.pose.bones[bone_name]
    bone.bone.select = True

# Set active bone (last in selection = active)
armature.data.bones.active = armature.data.bones[active_bone_name]
```

**Multi-bone Rotation with Axis Filtering**:
```python
# Apply rotation per bone with axis filtering (Individual Origins)
for bone in group_bones:
    initial_quat = bone.rotation_quaternion.copy()

    # Check if this is a twist bone (should only rotate on Y-axis)
    is_twist_bone = 'twist' in bone.name.lower()

    # Build combined rotation based on bone type
    combined_rot = Quaternion()  # Identity

    # Y-axis rotation (twist) - apply to ALL bones
    if rot_y:
        combined_rot = rot_y @ combined_rot

    # X and Z-axis rotations (bending) - only apply to non-twist bones
    if not is_twist_bone:
        if rot_x:
            combined_rot = rot_x @ combined_rot
        if rot_z:
            combined_rot = rot_z @ combined_rot

    bone.rotation_quaternion = combined_rot @ initial_quat
```

**Active Bone Priority**:
- For hierarchical chains (neck, arms, legs): Top/root bone is active
- For Bend/Twist pairs: Bend bone is always active
- For symmetrical groups (shoulders, legs): Left side bone is active by default

---

## Implementation Guidelines

### Mouse Delta Calculation
```python
# Calculate mouse movement deltas
delta_x = current_mouse_x - previous_mouse_x  # Horizontal
delta_y = current_mouse_y - previous_mouse_y  # Vertical (inverted in most UI systems)

# Apply sensitivity multiplier
rotation_amount_x = delta_x * sensitivity * 0.01  # Adjust multiplier as needed
rotation_amount_y = delta_y * sensitivity * 0.01
```

### Rotation Application
```python
# Example: LMB Horizontal on upper arm
if left_mouse_button_pressed:
    if abs(delta_x) > abs(delta_y):  # Primarily horizontal movement
        bone.rotation_euler.x += rotation_amount_x
    else:  # Primarily vertical movement
        bone.rotation_euler.z += rotation_amount_y
elif right_mouse_button_pressed:
    if abs(delta_x) > abs(delta_y):  # Primarily horizontal movement
        bone.rotation_euler.y += rotation_amount_x  # Twist
```

### Visual Feedback
- **Highlight** the active control node when hovered
- **Show rotation gizmo** or axis indicator for active bone
- **Display mouse button icons** showing which button controls which action
- **Color coding**:
  - Blue for selected control
  - Green for hover
  - Red/Yellow for constrained rotations

### Symmetry Options
- **Mirror Mode**: Enable to pose left/right sides simultaneously
- **Break Symmetry**: Allow independent control of left/right limbs
- **Copy Pose**: Copy pose from left to right (or vice versa)

### Control Point Placement
- Place control nodes at **joint locations** (shoulder, elbow, wrist, etc.)
- Use **larger hit areas** for easier selection (especially for fingers)
- Consider **hierarchical selection** (click shoulder to affect entire arm chain)

### Sensitivity Settings
| Body Part | Suggested Sensitivity Multiplier |
|-----------|----------------------------------|
| Eyes | 2.0-3.0 (high sensitivity) |
| Fingers | 1.5-2.0 |
| Head/Neck | 1.0-1.5 |
| Arms/Legs | 0.8-1.2 |
| Torso | 0.5-1.0 (lower sensitivity for stability) |

### Reset Functions
- **Double-click**: Reset individual bone to rest pose
- **Alt + Click**: Reset entire limb chain to rest pose
- **Ctrl + Click**: Reset symmetrical bones (left + right)

### Additional Features to Consider
1. **Constraints**: Implement realistic joint limits (e.g., elbow can't bend backward)
2. **IK/FK Toggle**: Switch between inverse kinematics and forward kinematics
3. **Pose Library**: Save/load common poses
4. **Undo/Redo**: Track rotation history per bone
5. **Multiple Selection**: Control multiple bones simultaneously
6. **Snap to Rotation**: Snap to common angles (0°, 45°, 90°, etc.)

---

## Bone Name Mapping Reference

### Genesis 8/9 (DAZ) to Rigify (Blender)

| DAZ Bone Name | Blender Rigify Name | Notes |
|---------------|---------------------|-------|
| head | head | Direct mapping |
| neck | neck | May have multiple neck bones (neck, neck.001) |
| lShldr / rShldr | shoulder.L / shoulder.R | Shoulder/clavicle |
| lCollar / rCollar | shoulder.L / shoulder.R | Alternative naming |
| lShldrBend / rShldrBend | upper_arm.L / upper_arm.R | Upper arm |
| lForearmBend / rForearmBend | forearm.L / forearm.R | Forearm |
| lHand / rHand | hand.L / hand.R | Hand |
| lThigh / rThigh | thigh.L / thigh.R | Upper leg |
| lShin / rShin | shin.L / shin.R | Lower leg |
| lFoot / rFoot | foot.L / foot.R | Foot |
| lToe / rToe | toe.L / toe.R | Toes |
| abdomen / abdomen2 | spine.001 / spine.002 | Lower/mid spine |
| chest | spine.003 | Upper spine |
| pelvis | pelvis / spine | Hip/pelvis |

**Note**: Your actual bone names may vary depending on your rig setup. Update this mapping table to match your specific implementation.

---

## Version History

### v1.0 (2026-02-15)
- Initial control node mapping
- Complete body coverage (head to toe)
- Mouse control scheme defined
- Implementation guidelines added

---

## Todo / Future Enhancements

- [ ] Add facial expression controls (eyebrows, lips, cheeks)
- [ ] Individual finger bone breakdown (3 segments per finger)
- [ ] Spine segments (detailed vertebrae control)
- [ ] Hand preset poses (fist, open palm, pointing, etc.)
- [ ] Foot preset poses (flexed, pointed, neutral)
- [ ] Custom control templates per character rig type
- [ ] Gamepad/controller support mapping
- [ ] Touch screen gesture support

---

**References**:
- DAZ PowerPose documentation
- Blender Rigify bone naming conventions
- Standard anatomical movement terminology
