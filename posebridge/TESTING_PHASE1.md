# PoseBridge Phase 1 Testing Plan

## Status: Ready for Testing

### Current Implementation Status

**Completed:**
- ✅ Project structure created
- ✅ Shared utilities extracted to daz_shared_utils.py
- ✅ PropertyGroup classes defined in core.py
- ✅ Line Art outline generator functional
- ✅ PoseBridgeDrawHandler GPU rendering functional
- ✅ Control point hover detection integrated into daz_bone_select.py
- ✅ Rotation behavior integrated into daz_bone_select.py
- ✅ PoseBridge-specific rotation axis logic (uses get_bend_axis)

**Deferred:**
- ⚠️ Settings UI (decision deferred - see plan document)
  - Settings currently set via Python console
  - Decision pending: N-panel vs HUD overlay vs hybrid

### Code Integration Summary

**Modified `daz_bone_select.py`:**

1. **`start_ik_drag()` method** (line ~2433):
   - Added PoseBridge mode detection
   - When active, uses rotation mode for ALL bones (not just pectorals)
   - Skips IK chain creation entirely in PoseBridge mode

2. **`update_rotation()` method** (line ~3235):
   - Detects PoseBridge mode
   - Uses `get_bend_axis()` to determine rotation axis per bone type
   - Uses shared utility `apply_rotation_from_delta()` for rotation
   - Respects PoseBridge sensitivity setting

3. **`check_hover()` method** (line ~1945):
   - Added PoseBridge mode check
   - Calls `check_posebridge_hover()` for 2D hit detection

4. **`check_posebridge_hover()` method** (new, line ~2096):
   - 2D control point hit detection
   - Updates hover state for dual highlighting
   - Sets `PoseBridgeDrawHandler._hovered_control_point`

### Test Scenario 1: Setup PoseBridge Mode

**Prerequisites:**
- Genesis 8 character loaded in scene
- Character in T-pose or rest pose
- Blender in Pose mode

**Steps:**
1. Open Python console
2. Enable PoseBridge mode:
   ```python
   import bpy
   bpy.context.scene.posebridge_settings.is_active = True
   ```
3. Set active armature:
   ```python
   armature = bpy.context.active_object
   if armature and armature.type == 'ARMATURE':
       bpy.context.scene.posebridge_settings.active_armature_name = armature.name
   ```

**Expected Result:**
- PoseBridge settings active
- Control points not yet visible (need to activate modal operator)

### Test Scenario 2: Generate Outline

**Prerequisites:**
- PoseBridge mode enabled (Test 1 complete)

**Steps:**
1. Run outline generator operator:
   ```python
   bpy.ops.pose.posebridge_generate_lineart()
   ```

**Expected Result:**
- Grease Pencil outline object created: "PB_Outline_LineArt_{armature_name}"
- Outline visible in viewport showing character silhouette
- Outline follows character mesh

### Test Scenario 3: Activate Control Points

**Prerequisites:**
- PoseBridge mode enabled
- Outline generated

**Steps:**
1. Activate modal operator:
   ```python
   bpy.ops.view3d.daz_bone_select('INVOKE_DEFAULT')
   ```
2. Move mouse over viewport

**Expected Result:**
- Control points visible as cyan circles on character outline
- Control points positioned at bone locations (head, shoulders, hands, etc.)
- Hovering over control point turns it yellow
- Hovering also highlights corresponding mesh area

### Test Scenario 4: Test Rotation on Limbs

**Prerequisites:**
- PoseBridge mode active
- Control points visible
- Modal operator running

**Steps:**
1. Hover over shoulder control point (lShldr or rShldr)
2. Left-click and hold
3. Drag mouse horizontally
4. Release mouse

**Expected Result:**
- While dragging: Arm rotates around bend axis (shoulder lifts/lowers)
- On release: Rotation keyframed
- Control point remains at new bone position

**Test on Multiple Bones:**
- lShldr / rShldr (shoulders): Horizontal drag = arm abduction
- lForeArm / rForeArm (elbows): Horizontal drag = elbow bend
- lHand / rHand (wrists): Horizontal drag = wrist bend
- head: Vertical drag = head nod
- lThigh / rThigh (hips): Horizontal drag = leg forward/back
- lShin / rShin (knees): Horizontal drag = knee bend
- lFoot / rFoot (ankles): Horizontal drag = ankle bend

### Test Scenario 5: Verify Dual Highlighting

**Prerequisites:**
- Control points visible
- Modal operator running

**Steps:**
1. Hover over any control point (e.g., lHand)
2. Observe visual feedback

**Expected Result:**
- Control point circle turns yellow (PoseBridgeDrawHandler._hovered_control_point)
- Corresponding mesh area highlights (existing daz_bone_select highlighting)
- Header text updates to show bone name and instructions

### Test Scenario 6: Rotation Cancellation

**Prerequisites:**
- Rotation integration complete
- Modal operator running

**Steps:**
1. Click and drag a control point to rotate bone
2. While dragging, press ESC or right-click

**Expected Result:**
- Rotation cancelled
- Bone returns to original rotation
- No keyframe created

### Test Scenario 7: Multiple Rotations

**Prerequisites:**
- Rotation integration complete

**Steps:**
1. Rotate shoulder bone, release (keyframed)
2. Rotate elbow bone, release (keyframed)
3. Rotate wrist bone, release (keyframed)
4. Press Ctrl+Z (undo)

**Expected Result:**
- All rotations applied and keyframed
- Undo system works correctly
- Each bone remembers its rotation

## Performance Benchmarks

**Target Metrics:**
- Hover detection: <1ms per frame
- Control point rendering: <5ms per frame
- Rotation update: <2ms per mouse move
- Total frame time: <16ms (60fps)

**How to Test:**
1. Enable Blender's performance overlay (Window > Show Performance > System Console)
2. Monitor frame rate during interaction
3. Use Python profiling if performance issues detected

## Known Limitations

1. **UI Settings Access**: Settings currently only accessible via Python console
2. **Single Panel Only**: Only body panel implemented (head/hands panels in Phase 3)
3. **Manual Outline Generation**: User must manually run generator operator
4. **Genesis 8 Only**: Control points hardcoded for Genesis 8 skeleton

## Next Steps

1. **Implement rotation integration** (modify start_ik_drag and update_rotation)
2. **Test rotation on all limb types** (arms, legs, head, torso)
3. **Document any issues or unexpected behavior**
4. **Decide on UI settings location** (N-panel vs HUD overlay)
5. **Complete Phase 1 MVP**

## Troubleshooting

### Control Points Not Visible
- Check PoseBridge mode is enabled: `bpy.context.scene.posebridge_settings.is_active`
- Check active armature is set: `bpy.context.scene.posebridge_settings.active_armature_name`
- Check modal operator is running: `bpy.ops.view3d.daz_bone_select('INVOKE_DEFAULT')`
- Check draw handler registered: Look for GPU drawing in viewport

### Outline Not Generated
- Check Genesis 8 armature is selected
- Check mesh object exists with armature modifier
- Check Line Art modifier settings in generated GP object
- Check GP object visibility in outliner

### Hover Not Working
- Check mouse is over viewport (not header or toolbar)
- Check bones exist in armature with expected names
- Check control point definitions in daz_shared_utils.py
- Enable debug prints in check_posebridge_hover()

### Rotation Not Working
- Check PoseBridge mode is enabled
- Check modal operator is running (bpy.ops.view3d.daz_bone_select)
- Check bone exists in armature
- Check bone rotation mode is QUATERNION (set automatically)
- Enable debug prints in start_ik_drag() and update_rotation()
- Verify sensitivity setting (default: 0.01)
- Test with different bones (some bones may have different bend axes)
