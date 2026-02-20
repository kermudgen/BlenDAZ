# Tool Comparison: PowerPose vs. DAZ Bone Select

Both tools are included in BlenDAZ and serve different purposes. Use the right tool for your workflow!

## Quick Decision Guide

**Use PowerPose when:**
- ✓ You want precise rotation control
- ✓ You prefer panel-based workflow
- ✓ You want to rotate specific bones without affecting parents
- ✓ You want bend/twist separation (left-click vs. right-click)
- ✓ You're fine-tuning poses or adjusting specific joints

**Use DAZ Bone Select when:**
- ✓ You want natural ragdoll-style posing
- ✓ You prefer viewport-based workflow
- ✓ You want IK-based limb posing (entire arm/leg moves together)
- ✓ You want to pull hands/feet to pose limbs naturally
- ✓ You're roughing out poses quickly

**Use both!** They're designed to complement each other, not replace each other.

## Feature Comparison Table

| Feature | PowerPose | DAZ Bone Select |
|---------|-----------|-----------------|
| **Interface** | 2D Panel (N-panel sidebar) | 3D Viewport (modal operator) |
| **Activation** | Open N-panel > DAZ tab | Press Ctrl+Shift+D |
| **Bone Selection** | Click button in panel | Hover over mesh in viewport |
| **Posing Method** | Direct rotation (FK) | IK chains (IK) |
| **Rotation Type** | Bend (left-click) or Twist (right-click) | IK solving (natural pull) |
| **Affected Bones** | Single bone only | Chain of bones (limb/spine) |
| **Viewport Interaction** | Watch in viewport while using panel | Direct interaction in viewport |
| **Best For** | Precise rotation control | Natural pulling/posing |
| **Learning Curve** | Very easy (click buttons) | Easy (hover and drag) |
| **Performance** | Very fast (direct rotation) | Fast (IK solving) |
| **Keyframing** | Automatic on release | Automatic on release |
| **Undo Support** | Yes (Ctrl+Z) | Yes (Ctrl+Z) |

## Detailed Feature Breakdown

### Interface & Activation

**PowerPose**:
- Lives in the **N-panel sidebar** under the **DAZ tab**
- Always visible when N-panel is open
- Panel-based workflow (list of control point buttons)
- No hotkey needed (just open panel)

**DAZ Bone Select**:
- Activated with **Ctrl+Shift+D** hotkey
- Modal operator (takes over viewport until you press ESC)
- Hover-based workflow (mouse over mesh to detect bones)
- Shows amber highlight on hovered bone region

### Bone Selection

**PowerPose**:
- **Click a button** with the bone name
- Pre-defined control points (16 bones in Phase 1)
- No hovering needed
- Clear visual list of available bones

**DAZ Bone Select**:
- **Hover over mesh** to detect bone underneath
- Works with any bone (even small/hidden ones)
- Visual feedback (amber mesh highlighting)
- Auto-detects base body mesh vs. clothing

### Posing Method

**PowerPose**:
- **Direct rotation manipulation** (FK-style)
- Left-click: Bend around perpendicular axis
- Right-click: Twist around bone length axis
- Rotates only the clicked bone (no parent influence)
- Precise control over rotation amount

**DAZ Bone Select**:
- **IK chain manipulation** (IK-style)
- Click-drag creates temporary IK chain
- Pulls entire limb naturally (elbow/knee bends automatically)
- Ragdoll-style pulling with stiffness falloff
- Stretching and natural limb behavior

### Typical Workflows

**PowerPose Workflow**:
```
1. Open N-panel (press N)
2. Go to DAZ tab
3. Select armature (Pose Mode)
4. Left-click "Left Forearm" button
5. Drag mouse to bend elbow
6. Release to keyframe
7. Right-click "Left Forearm" button
8. Drag mouse to twist forearm
9. Release to keyframe
```

**DAZ Bone Select Workflow**:
```
1. Press Ctrl+Shift+D to activate
2. Hover over left hand mesh
3. See amber highlight (confirms bone detected)
4. Click-drag hand away from body
5. Entire arm follows (IK chain activated)
6. Release to keyframe pose
7. ESC to exit tool
```

## Use Case Scenarios

### Scenario 1: Adjusting Elbow Angle

**PowerPose Approach**:
1. Left-click "Left Forearm" in panel
2. Drag vertically to adjust elbow bend
3. Release to keyframe
4. **Result**: Precise elbow angle control

**DAZ Bone Select Approach**:
1. Hover over left hand
2. Click-drag hand to new position
3. Elbow automatically bends to reach target
4. **Result**: Natural arm pose with elbow bend

**Best Choice**: PowerPose for precise elbow angle, DAZ Bone Select for natural arm repositioning

### Scenario 2: Twisting Forearm (Pronation/Supination)

**PowerPose Approach**:
1. Right-click "Left Forearm" in panel
2. Drag horizontally to twist forearm
3. Release to keyframe
4. **Result**: Clean forearm twist

**DAZ Bone Select Approach**:
1. Select forearm bone (click in viewport)
2. Press R to rotate manually
3. Rotate with mouse
4. **Result**: Manual rotation (not IK-based)

**Best Choice**: PowerPose (right-click twist is specifically designed for this)

### Scenario 3: Reaching for an Object

**PowerPose Approach**:
1. Left-click "Left Shoulder" and adjust
2. Left-click "Left Forearm" and adjust
3. Left-click "Left Hand" and adjust
4. Multiple separate rotations needed
5. **Result**: Precise control but tedious

**DAZ Bone Select Approach**:
1. Hover over left hand
2. Click-drag hand to object location
3. Entire arm adjusts automatically (shoulder + elbow)
4. **Result**: Quick natural reach pose

**Best Choice**: DAZ Bone Select (IK handles entire arm chain)

### Scenario 4: Fine-Tuning an Existing Pose

**PowerPose Approach**:
1. Click individual bone buttons
2. Make small rotation adjustments
3. Left-click for bend, right-click for twist
4. Immediate visual feedback
5. **Result**: Precise fine-tuning

**DAZ Bone Select Approach**:
1. Activate tool (Ctrl+Shift+D)
2. Hover to find bone
3. Click-drag to adjust
4. May affect parent bones unintentionally
5. **Result**: Good for larger adjustments

**Best Choice**: PowerPose (better for small precise adjustments)

## Performance Comparison

| Aspect | PowerPose | DAZ Bone Select |
|--------|-----------|-----------------|
| **Startup Time** | Instant (panel always open) | Quick (Ctrl+Shift+D) |
| **Bone Detection** | Instant (click button) | Fast (hover detection) |
| **Rotation Update** | Instant (direct rotation) | Fast (IK solving) |
| **Viewport Redraw** | Real-time | Real-time |
| **Keyframe Creation** | Instant (1 bone) | Quick (chain of bones) |
| **Tool Cleanup** | None needed (panel stays) | Quick (ESC to exit) |

**Winner**: Tie - Both are very fast with different strengths

## Learning Curve

**PowerPose**:
- ⭐⭐⭐⭐⭐ Very Easy
- Clear button labels
- Simple left-click/right-click distinction
- No hidden features or complex modes
- Panel-based (familiar to Blender users)

**DAZ Bone Select**:
- ⭐⭐⭐⭐ Easy
- Hover detection may take getting used to
- IK behavior requires understanding
- Modal tool (need to activate/deactivate)
- More powerful but slightly more complex

## Integration with Each Other

**PowerPose and DAZ Bone Select work great together!**

### Typical Combined Workflow:

1. **Rough pose** with DAZ Bone Select:
   - Ctrl+Shift+D to activate
   - Drag limbs to approximate positions
   - Get overall pose "close enough"
   - ESC to exit tool

2. **Fine-tune** with PowerPose:
   - Open N-panel > DAZ tab
   - Adjust individual bone rotations
   - Left-click to adjust bends
   - Right-click to adjust twists

3. **Final touches** with either tool:
   - Use whichever feels more natural for the adjustment
   - Switch back and forth as needed

### No Conflicts

- PowerPose doesn't interfere with IK chains
- DAZ Bone Select doesn't interfere with rotations
- Both use standard Blender keyframing (same undo stack)
- No data loss when switching between tools

## Summary

| When You Want... | Use This Tool |
|------------------|---------------|
| Precise rotation control | PowerPose |
| Natural limb pulling | DAZ Bone Select |
| Bend vs. twist separation | PowerPose |
| Ragdoll-style posing | DAZ Bone Select |
| Panel-based workflow | PowerPose |
| Viewport-based workflow | DAZ Bone Select |
| Single bone rotation | PowerPose |
| Entire limb posing | DAZ Bone Select |
| Fine-tuning poses | PowerPose |
| Rough pose blocking | DAZ Bone Select |
| Quick adjustments | Either (both are fast!) |

## Recommendation

**Start with DAZ Bone Select** to rough out your pose quickly, then **switch to PowerPose** to fine-tune individual bone rotations and add precise twisting movements.

The combination of both tools gives you:
- ✓ Fast initial posing (IK)
- ✓ Precise fine-tuning (rotation)
- ✓ Natural limb behavior (IK)
- ✓ Full rotation control (FK)

**Best of both worlds!** 🎉

---

**Both tools are maintained in**: `daz_bone_select.py`
**Documentation**: See README.md and POWERPOSE_README.md
