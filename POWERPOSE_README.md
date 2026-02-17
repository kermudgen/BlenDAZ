# PowerPose for BlenDAZ

**Status**: Phase 1 - Basic Main Panel (MVP) ✅

PowerPose is a DAZ Studio-inspired posing system that provides an intuitive 2D panel interface for posing characters through rotation-based bone manipulation.

## What is PowerPose?

PowerPose provides a **panel-based interface** (in Blender's N-panel) where you can click and drag control points to rotate bones directly. Unlike the existing DAZ Bone Select IK tool, PowerPose uses **direct rotation** rather than IK chains, giving you precise control over individual bone rotations.

### Key Features (Phase 1)

- ✅ **2D Panel Interface** - Control points in N-panel sidebar (DAZ tab)
- ✅ **Dual Mouse Button Control**:
  - **Left-click + drag**: Bend (rotate around perpendicular axis)
  - **Right-click + drag**: Twist (rotate around bone length axis)
- ✅ **Real-Time Viewport Updates** - See changes immediately in 3D viewport
- ✅ **Automatic Keyframing** - Rotations are keyframed on mouse release
- ✅ **ESC to Cancel** - Revert to original rotation if you change your mind
- ✅ **Genesis 8 Control Points** - Pre-configured for Genesis 8 figures
- ✅ **Organized by Body Region** - Head, Arms, Torso, Legs sections

## Installation

1. Copy `daz_bone_select.py` to your Blender scripts folder or install as addon
2. Enable the addon in Blender Preferences > Add-ons
3. Activate DAZ Bone Select with **Ctrl+Shift+D** (optional)
4. Open PowerPose panel in **N-panel > DAZ tab**

## Usage

### Opening PowerPose Panel

1. Open the 3D Viewport
2. Press **N** to open the N-panel sidebar
3. Navigate to the **DAZ** tab
4. You'll see the **PowerPose** panel

### Basic Workflow

1. **Select your armature** and enter **Pose Mode**
2. Open the **PowerPose panel** (N-panel > DAZ tab)
3. **Left-click** a control point button (e.g., "Left Forearm")
4. **Drag** the mouse to rotate the bone
   - Horizontal drag: Rotation around one axis
   - Vertical drag: Rotation around perpendicular axis
5. **Release** mouse button to keyframe the rotation
6. **ESC** to cancel and revert to original rotation

### Dual Button Control

PowerPose provides **two buttons per control point** for different rotation modes:

- **Bend button + drag**: **BEND** - Rotates bone around its perpendicular axis
  - Example: Click "Bend" next to "Left Forearm" → bends elbow
  - Example: Click "Bend" next to "Left Shin" → bends knee

- **Twist button + drag**: **TWIST** - Rotates bone around its length axis
  - Example: Click "Twist" next to "Left Forearm" → twists forearm (pronation/supination)
  - Example: Click "Twist" next to "Left Thigh" → twists thigh

This dual-button approach gives you comprehensive control without needing to switch modes!

### Control Points

Phase 1 includes these control points (Genesis 8 template):

**HEAD**
- Head

**ARMS**
- Left Hand, Right Hand
- Left Forearm, Right Forearm
- Left Shoulder, Right Shoulder

**TORSO**
- Chest
- Abdomen
- Pelvis

**LEGS**
- Left Foot, Right Foot
- Left Shin, Right Shin
- Left Thigh, Right Thigh

## Technical Details

### Rotation System

PowerPose uses **direct quaternion rotation** manipulation:
- Forces all bones to `QUATERNION` rotation mode for stability
- Calculates rotation axis based on bone type (bend vs. twist)
- Applies delta rotation based on mouse movement
- Sensitivity: 0.01 radians per pixel (~0.57 degrees per pixel)

### Axis Determination

**Bend Axis** (perpendicular to bone):
- Arms/Legs: X axis (typical elbow/knee bending)
- Neck/Head: Y axis (nodding motion)
- Fingers: X axis (curling motion)

**Twist Axis** (along bone length):
- All bones: Y axis (Blender's bone length axis)

### Keyframing

- Rotations are automatically keyframed on mouse release
- Uses `keyframe_insert(data_path="rotation_quaternion")`
- Standard Blender undo system works (Ctrl+Z)

## Architecture

PowerPose is **completely independent** from the existing DAZ Bone Select IK tool:
- **DAZ Bone Select** (Ctrl+Shift+D): IK-based viewport posing with hover selection
- **PowerPose** (N-panel): Rotation-based panel posing with control point buttons

Both tools can coexist and be used for different workflows!

### File Structure

All PowerPose code is in `daz_bone_select.py`:
- **Rotation Functions**: `get_bend_axis()`, `get_twist_axis()`, `apply_rotation_from_delta()`
- **Control Point Template**: `get_genesis8_control_points()`
- **Modal Operator**: `POSE_OT_daz_powerpose_control`
- **Panel Class**: `VIEW3D_PT_daz_powerpose_main`

## Roadmap

### Phase 2: Dual Mouse Button Support + Figure Outline (Next)
- ✅ Right-click twist functionality (DONE in Phase 1!)
- ⏳ Visual figure outline in panel (ASCII art or custom drawing)
- ⏳ Better control point layout (spatial arrangement)

### Phase 3: Detail Panels
- ⏳ Head detail panel (neck, jaw, eyes)
- ⏳ Hands detail panel (per-finger control)
- ⏳ Collapsible panel organization

### Phase 4: Group Controls + Special Features
- ⏳ Multi-bone group controls (e.g., "entire arm", "all torso")
- ⏳ Special control points for complex movements
- ⏳ Fine-tune rotation sensitivity
- ⏳ Rotation limits toggle

### Phase 5: Advanced Features (Future)
- ⏳ Template selection (Genesis 1, 3, 8, 8.1, custom)
- ⏳ Coordinate system switching (World/Local)
- ⏳ Symmetry options (mirror L/R poses)
- ⏳ Pose presets integration
- ⏳ Custom GPU drawing for DAZ-like aesthetic

## Comparison: PowerPose vs. DAZ Bone Select

| Feature | PowerPose | DAZ Bone Select |
|---------|-----------|-----------------|
| **Interface** | 2D Panel (N-panel) | 3D Viewport (modal) |
| **Posing Method** | Direct rotation | IK chains |
| **Interaction** | Click-drag buttons | Hover + click-drag mesh |
| **Best For** | Precise rotation control | Natural pulling/ragdoll posing |
| **Workflow** | Panel-based | Viewport-based |

**Use PowerPose when**:
- You want precise rotation control
- You prefer panel-based workflow
- You want to rotate specific bones without affecting parents
- You want dual-button bend/twist control

**Use DAZ Bone Select when**:
- You want natural ragdoll-style posing
- You prefer hover-select workflow
- You want IK-based limb posing
- You want to pull hands/feet to move entire arm/leg chains

## Troubleshooting

### Panel doesn't appear
- Ensure addon is enabled and registered
- Press N to open N-panel sidebar
- Navigate to DAZ tab (it may be collapsed)

### Control points don't work
- Ensure you're in Pose Mode
- Ensure an armature is selected and active
- Check that bone names match (Genesis 8 template may not match custom rigs)

### Rotations feel too sensitive or too slow
- Current sensitivity: 0.01 radians per pixel
- Will be adjustable in future phases
- For now, drag slowly for fine control, quickly for large rotations

### Bone snaps to unexpected rotation
- This may happen if bone has constraints or animation data
- Try clearing constraints or keyframes first
- ESC to cancel the rotation

## Contributing

PowerPose is in active development! Feedback and testing are welcome:
- Report issues or suggestions in BlenDAZ repository
- Test with different Genesis versions (1, 3, 8, 8.1)
- Suggest additional control points or features

## Credits

PowerPose design inspired by DAZ Studio's PowerPose feature, adapted for Blender's architecture and workflow.

**Improvements over DAZ Studio**:
- Dual mouse button functionality (bend vs. twist)
- Complementary with IK tool (not exclusive)
- Standard Blender N-panel integration
- Direct axis-based rotation (more predictable)

---

**Version**: 1.2.0 (Phase 1 MVP)
**Last Updated**: 2026-02-08
