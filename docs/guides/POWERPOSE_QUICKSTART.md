# PowerPose Quick Start Guide

Get started with PowerPose in 60 seconds!

## What is PowerPose?

PowerPose is a **panel-based posing tool** inspired by DAZ Studio. Instead of clicking in the 3D viewport, you click control point buttons in a panel and drag to rotate bones directly.

## Quick Setup

1. **Install** the addon: `daz_bone_select.py`
2. **Open** N-panel: Press **N** in 3D viewport
3. **Find** the **DAZ** tab (click to expand if collapsed)
4. **Select** your armature and enter **Pose Mode**

## Basic Usage

### Click Bend Button = Bend
```
Click "Bend" button next to "Left Forearm" → Drag → Elbow bends
```

### Click Twist Button = Twist
```
Click "Twist" button next to "Left Forearm" → Drag → Forearm twists (pronation/supination)
```

### Cancel = ESC
```
ESC → Reverts to original rotation (before you started dragging)
```

## Control Points (Genesis 8)

**HEAD**
- Head

**ARMS**
- Left/Right Hand
- Left/Right Forearm
- Left/Right Shoulder

**TORSO**
- Chest
- Abdomen
- Pelvis

**LEGS**
- Left/Right Foot
- Left/Right Shin
- Left/Right Thigh

## Mouse Drag Behavior

- **Horizontal drag**: Rotation around one axis
- **Vertical drag**: Rotation around perpendicular axis
- **Combined**: Drag diagonally for complex rotations

**Sensitivity**: 0.01 radians per pixel (~0.57° per pixel)
- Drag slowly for fine control
- Drag quickly for large rotations

## Tips

✅ **Use both tools**: PowerPose (panel) + DAZ Bone Select (viewport hover) are complementary!

✅ **Keyframing**: Rotations are automatically keyframed on mouse release

✅ **Undo**: Standard Blender undo (Ctrl+Z) works

✅ **Real-time**: Viewport updates in real-time as you drag

## Comparison: When to Use Each Tool

### Use PowerPose When:
- ✓ You want precise rotation control
- ✓ You prefer panel-based workflow
- ✓ You want bend/twist separation
- ✓ You're fine-tuning poses

### Use DAZ Bone Select When:
- ✓ You want natural ragdoll posing
- ✓ You prefer hover-select workflow
- ✓ You want IK-based limb posing
- ✓ You're roughing out poses

## Next Steps

Read the full documentation: [POWERPOSE_README.md](POWERPOSE_README.md)

## Common Issues

**Panel doesn't appear?**
→ Press N, check DAZ tab, ensure addon is enabled

**Control points don't work?**
→ Ensure you're in Pose Mode with armature selected

**Rotations too sensitive?**
→ Drag more slowly for fine control (sensitivity adjustment coming in future phase)

---

**Version**: 1.2.0 (Phase 1 MVP)
