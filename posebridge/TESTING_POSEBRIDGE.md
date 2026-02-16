# PoseBridge Fixed Control Points - Testing Guide

This guide walks you through testing the PoseBridge Phase 1 MVP with fixed control points.

---

## Prerequisites
- Blender open with Genesis 8 character (mesh + armature)
- Character in **T-pose** (arms out horizontally, legs straight)
- BlenDAZ addon files in `D:\dev\BlenDAZ`

---

## Testing Checklist

### ✅ STEP 1: Clean Slate
- [ ] **Restart Blender** (fresh start)
- [ ] Load your character file
- [ ] **Verify T-pose**: Arms out horizontally, legs straight
- [ ] Select the character mesh

---

### ✅ STEP 2: Register PoseBridge

**Run in Python Console:**

> **⚠️ IMPORTANT**: Do NOT copy the \`\`\`python line - only copy the actual Python code below!

```python
import bpy, sys
blendaz_path = r"D:\dev\BlenDAZ"
if blendaz_path not in sys.path:
    sys.path.insert(0, blendaz_path)
import posebridge
posebridge.register()
print("✓ PoseBridge registered")
```

**Expected output:** `✓ PoseBridge registered`

**Troubleshooting:**
- If you get an error, make sure the path is correct: `D:\dev\BlenDAZ`
- Check that `posebridge` folder exists in that directory

---

### ✅ STEP 3: Generate Outline

**Steps:**
1. **Select your mesh** in the viewport
2. Open **Text Editor** (Editor Type → Text Editor)
3. Open file: `D:\dev\BlenDAZ\posebridge\outline_generator_lineart.py`
4. Click **Run Script** button (▶)

**Expected output in console:**
```
======================================================================
Capturing Fixed Control Point Positions...
======================================================================
✓ Captured 20 fixed control point positions from T-pose
======================================================================
```

**Control Points (20 total):**
- Head: head, neck_group (diamond - controls head + neckUpper + neckLower)
- Arms: lHand, rHand, lForeArm, rForeArm, lShldr, rShldr
- Torso: chestUpper, chestLower, abdomenUpper, abdomenLower, pelvis
- Legs: lFoot, rFoot, lShin, rShin, lThigh, rThigh

**Verify:**
- [ ] Outline visible in viewport (cyan line drawing of character)
- [ ] Console shows "Captured X fixed control point positions"

**Troubleshooting:**
- If you see "No valid mesh found": Make sure mesh is selected
- If outline doesn't appear: Check Outliner for `PB_Outline_LineArt` object visibility

---

### ✅ STEP 4: Move Setup to -50m

This moves the outline and camera away from the character to avoid overlap.

**Run in Python Console:**

> **⚠️ IMPORTANT**: Do NOT copy the \`\`\`python line - only copy the actual Python code below!

```python
import bpy
outline = bpy.data.objects.get("PB_Outline_LineArt")
camera = bpy.data.objects.get("PB_Outline_LineArt_Camera")
light = bpy.data.objects.get("PB_Outline_LineArt_Light")
if outline: outline.location.z = -50.0
if camera: camera.location.z = -50.0
if light: light.location.z = -50.0
print("✓ Moved to -50m")
```

**Expected output:** `✓ Moved to -50m`

**Verify:**
- [ ] Objects moved (check Outliner → properties → Z location = -50)

---

### ✅ STEP 4B: Recapture Control Point Positions

**IMPORTANT**: After moving the outline, we need to recapture the control point positions to match the new Z=-50 location.

**Steps:**
1. Open **Text Editor** (Editor Type → Text Editor)
2. Click **Open** button
3. Navigate to: `D:\dev\BlenDAZ\posebridge\recapture_control_points.py`
4. **IMPORTANT**: Before running, change `ARMATURE_NAME = "Fey"` to match your armature's name
5. Click **Run Script** button (▶)

**Expected output in console:**
```
======================================================================
Recapturing Fixed Control Point Positions...
======================================================================
✓ Captured 20 fixed control point positions from T-pose
======================================================================
✓ Recaptured 20 fixed control point positions
✓ Control points now match outline position at Z=-50m
======================================================================
```

**Verify:**
- [ ] Console shows "Recaptured X fixed control point positions"
- [ ] No errors displayed

---

### ✅ STEP 5: Setup Dual Viewports

**Split viewport:**
1. Hover over **top-right corner** of 3D viewport
2. Cursor changes to crosshair
3. **Left-click and drag left** to split vertically
4. Release when you have two side-by-side viewports

**Configure left viewport (PoseBridge control panel):**
1. **Click in left viewport** to make it active
2. Press **Numpad 0** to enter camera view
3. You should see the outline centered

**Configure right viewport (mesh view):**
1. **Click in right viewport** to make it active
2. Leave in normal 3D view
3. Frame your character if needed (**Numpad .** to frame selected)

**Verify:**
- [ ] Left viewport shows outline in camera view
- [ ] Right viewport shows character mesh
- [ ] Both viewports visible simultaneously

---

### ✅ STEP 6: Start PoseBridge

**Option A: Run Startup Script (RECOMMENDED)**

1. Open **Text Editor** (Editor Type → Text Editor)
2. Click **Open** button
3. Navigate to: `D:\dev\BlenDAZ\posebridge\start_posebridge.py`
4. **IMPORTANT**: Before running, open the file and change `ARMATURE_NAME = "Fey"` to match your armature's name
5. Click **Run Script** button (▶)

**Expected output in console:**
```
======================================================================
Starting PoseBridge...
======================================================================
✓ Added D:\dev\BlenDAZ to Python path
✓ PoseBridge registered
✓ daz_bone_select registered
✓ PoseBridge mode enabled for armature: Fey
✓ Draw handler registered
✓ Modal operator registered
======================================================================
✓ PoseBridge is ready!

IMPORTANT: Click in the LEFT viewport (camera view) first!
Then the modal operator will start automatically...
======================================================================

✓ Modal operator started - control points should be visible!
```

**Option B: Manual Python Console Method**

If you prefer to use Python console, run this single command:
```python
exec(open(r"D:\dev\BlenDAZ\posebridge\start_posebridge.py").read())
```

**Expected:**
- [ ] Script runs without errors
- [ ] Blue/cyan control points appear immediately in BOTH viewports
- [ ] Control points positioned at joints (shoulders, elbows, hips, knees, etc.)
- [ ] Modal operator started automatically (no need to press Ctrl+Shift+D)

**Troubleshooting:**
- If no control points appear: Check System Console (Window → Toggle System Console) for errors
- If "Fey" not found: Edit line 13 of `start_posebridge.py` to change `ARMATURE_NAME = "Fey"` to your armature's name
- If script fails: Make sure you completed Steps 1-5 first (especially Step 3 - generate outline)
- If modal operator doesn't start: The script will show an error - read the console output

---

### ✅ STEP 7: Test Hover Detection

**In left viewport (camera view):**
1. **Move mouse slowly** over a control point (shoulder, elbow, etc.)

**Expected behavior:**
- [ ] Control point turns **yellow** when hovering
- [ ] Header text updates with bone name
- [ ] Control point returns to **cyan** when mouse moves away

**Test multiple control points:**
- [ ] Shoulder (lShldr or rShldr)
- [ ] Forearm (lForeArm or rForeArm)
- [ ] Hip (lThigh or rThigh)
- [ ] Knee (lShin or rShin)
- [ ] Head (single bone) - circle shape
- [ ] Neck group (multi-bone) - diamond shape
- [ ] Torso bones (chestUpper, chestLower, abdomenUpper, abdomenLower, pelvis)

---

### ✅ STEP 8: Test Fixed Control Points (THE KEY TEST!)

**In left viewport, test shoulder rotation:**
1. **Hover** over left shoulder control point → turns yellow
2. **Left-click and hold**
3. **Drag horizontally** (left/right)
4. **Observe both viewports**

**Expected behavior:**
- [ ] **Left viewport**: Control point **STAYS IN SAME POSITION** (doesn't move with bone!)
- [ ] **Right viewport**: Arm rotates smoothly in real-time
- [ ] Dragging is smooth and responsive

5. **Release mouse**

**Expected:**
- [ ] Rotation applied to bone
- [ ] Keyframe created (orange marker in timeline)
- [ ] Undo works (Ctrl+Z)

---

### ✅ STEP 9: Test Multiple Bone Rotations

**Test that ALL control points stay fixed:**

1. **Rotate pelvis** (center of hips)
   - [ ] Pelvis control point **stays fixed**
   - [ ] Hip control points **stay fixed** (don't move with pelvis!)
   - [ ] Mesh updates in right viewport

2. **Rotate upper arm** (shoulder)
   - [ ] Shoulder control point **stays fixed**
   - [ ] Elbow control point **stays fixed**
   - [ ] Arm rotates naturally

3. **Rotate head**
   - [ ] Head control point **stays fixed**
   - [ ] Neck rotates
   - [ ] Mesh updates correctly

**This is the critical test**: Control points should NEVER move, even when bones they control are rotated. They're like buttons on a fixed diagram.

---

### ✅ STEP 9B: Test PowerPose-Style 4-Way Controls

**NEW IN THIS VERSION**: All control points now support DAZ PowerPose-style 4-way directional controls!
- **LMB + Horizontal** (left/right drag with left mouse)
- **LMB + Vertical** (up/down drag with left mouse)
- **RMB + Horizontal** (left/right drag with right mouse)
- **RMB + Vertical** (up/down drag with right mouse)

Each control point has different rotation axes mapped to each input combination.

#### Head Control (4-way)
1. **Left-click drag** on head control point:
   - [ ] Drag **left/right** → head **turns** (Y-axis, looking around)
   - [ ] Drag **up/down** → head **nods** (X-axis, yes gesture)
2. **Right-click drag** on head control point:
   - [ ] Drag **left/right** → head **tilts** ear-to-shoulder (Z-axis)
   - [ ] Drag **up/down** → fine forward/back tilt (none)

#### Neck Group (Diamond Shape) - 4-way Multi-Bone Control
1. **Left-click drag** on neck group diamond:
   - [ ] Drag **left/right** → all neck bones **rotate** (Y-axis)
   - [ ] Drag **up/down** → all neck bones **bend** forward/back (X-axis)
2. **Right-click drag** on neck group diamond:
   - [ ] Drag **left/right** → all neck bones **bend to side** (Z-axis)

#### Neck Controls (neckUpper, neckLower) - 4-way Individual
1. **Left-click drag** on neck control:
   - [ ] Drag **left/right** → neck **rotates** (Y-axis)
   - [ ] Drag **up/down** → neck **bends** forward/back (X-axis)
2. **Right-click drag** on neck control:
   - [ ] Drag **left/right** → neck **bends to side** (Z-axis)

#### Torso Controls (chestUpper/Lower, abdomenUpper/Lower, pelvis) - 4-way
1. **Left-click drag** on torso control:
   - [ ] Drag **left/right** → torso **twists** (Y-axis)
   - [ ] Drag **up/down** → torso **bends** forward/back (X-axis)
2. **Right-click drag** on torso control:
   - [ ] Drag **left/right** → torso **leans** side-to-side (Z-axis)
   - [ ] Drag **up/down** → alternative twist (Y-axis)

#### Arm Controls - 4-way

**Collar (lCollar, rCollar):**
1. **Left-click drag**:
   - [ ] Horizontal → shrug/drop shoulder (Z-axis)
   - [ ] Vertical → shoulder forward/back (X-axis)
2. **Right-click drag**:
   - [ ] Horizontal → shoulder roll (Y-axis)

**Upper Arm (lShldrBend, rShldrBend):**
1. **Left-click drag**:
   - [ ] Horizontal → arm swing forward/back (X-axis)
   - [ ] Vertical → raise/lower arm (Z-axis)
2. **Right-click drag**:
   - [ ] Horizontal → arm twist, palm up/down (Y-axis)

**Forearm (lForearmBend, rForearmBend):**
1. **Left-click drag**:
   - [ ] Vertical → **bend elbow** (X-axis) - main control
2. **Right-click drag**:
   - [ ] Horizontal → forearm twist (Y-axis)

**Hand (lHand, rHand):**
1. **Left-click drag**:
   - [ ] Horizontal → hand bend side-to-side (Z-axis)
   - [ ] Vertical → hand bend up/down (X-axis)
2. **Right-click drag**:
   - [ ] Horizontal → hand twist (Y-axis)

#### Leg Controls - 4-way

**Thigh (lThigh, rThigh):**
1. **Left-click drag**:
   - [ ] Horizontal → leg swing forward/back (X-axis)
   - [ ] Vertical → raise/lower leg (Z-axis)
2. **Right-click drag**:
   - [ ] Horizontal → thigh twist inward/outward (Y-axis)
   - [ ] Vertical → side movement, abduction/adduction (Y-axis)

**Shin (lShin, rShin):**
1. **Left-click drag**:
   - [ ] Vertical → **bend knee** (X-axis) - main control
2. **Right-click drag**:
   - [ ] Horizontal → shin twist (Y-axis)

**Foot (lFoot, rFoot):**
1. **Left-click drag**:
   - [ ] Horizontal → foot tilt side-to-side (Z-axis)
   - [ ] Vertical → foot point/flex (X-axis)
2. **Right-click drag**:
   - [ ] Horizontal → foot twist (Y-axis)

---

### ✅ STEP 10: Test Cancellation

1. **Hover** over a control point
2. **Left-click and drag** to start rotation
3. While dragging, **right-click**

**Expected:**
- [ ] Rotation cancelled
- [ ] Bone returns to position before drag started
- [ ] Control point still fixed in place

---

## Success Criteria

**All of these must be true:**

✅ **Visual**
- Control points visible in camera view
- Control points turn yellow on hover
- Outline visible and matches character pose (in T-pose initially)

✅ **Fixed Positioning**
- Control points **NEVER move** when bones rotate
- Control points stay aligned with T-pose outline
- All control points stay in exactly the same screen positions

✅ **Interaction**
- Hover detection works (yellow highlight)
- Click-drag rotates bones smoothly
- Right-click cancels rotation
- Mouse release creates keyframe

✅ **Dual Viewport**
- Left viewport: Fixed control panel (camera view)
- Right viewport: Live mesh updates
- Both update simultaneously during rotation

---

## Troubleshooting

### No control points visible
- Check that modal operator is running (Ctrl+Shift+D)
- Verify fixed positions captured: Console should show "Captured X fixed control point positions"
- Check System Console for errors (Window → Toggle System Console)

### Control points in wrong location
- Verify outline was moved to -50m (Step 4)
- Check armature is at Z=0 (original position)
- Regenerate outline if needed

### Control points moving with bones
- This means fixed positions weren't captured - regenerate outline (Step 3)
- Make sure you ran Step 6 after regenerating

### Blender freezes at Step 6
- This was caused by aggressive module reloading in older version of testing guide
- Use the updated Step 6 script which avoids `importlib.reload()` calls
- If Blender freezes, restart and use the updated script

### Hover not working
- Make sure modal operator is running
- Click in left viewport first to make it active
- Check that Ctrl+Shift+D was pressed

### Rotation not working
- Check System Console for errors
- Verify PoseBridge mode is active: `bpy.context.scene.posebridge_settings.is_active` should be True
- Make sure armature name matches in Step 6

### Rotation limits not respected (head, hands, elbows)
- **Known Issue**: Diffeomorphic import sometimes doesn't create LIMIT_ROTATION constraints for certain bones:
  - Head
  - Shoulder twist bones
  - Elbow bones
  - Forearm twist bones
- **Workaround**: Manually add LIMIT_ROTATION constraints to these bones in Blender:
  1. Select armature in Pose Mode
  2. Select affected bone
  3. Constraints tab → Add Constraint → Limit Rotation
  4. Set appropriate min/max values for X, Y, Z axes
  5. Enable "For Transform" checkbox
- **Note**: This is a Diffeomorphic import issue, not a PoseBridge bug
- PoseBridge will use these constraints once they're added

---

## Quick Restart

If something goes wrong and you need to start over:

1. **ESC** to exit modal operator
2. Restart Blender
3. Start from Step 1 of this checklist

---

## Report Results

When testing is complete, report:
- ✅ Which steps passed
- ❌ Which steps failed (with error messages if any)
- 📝 Any unexpected behavior
- 💡 Suggestions or feedback

---

**Last Updated:** 2026-02-15
**Phase:** Phase 1 MVP - Fixed Control Points + PowerPose Integration
**Status:** Testing in Progress

**Recent Additions (2026-02-15):**

**PowerPose-Style 4-Way Controls (Latest - Performance Optimized):**
- ✨ **Complete DAZ PowerPose control scheme integration**
- 🚀 **Fully optimized for smooth, responsive control** (rotation logic inlined, zero function call overhead)
- ✅ **Original working axis mappings restored** (Head Y/Z, Torso Y/Z)
- 💎 **Neck group diamond restored** (multi-bone control)
- 23 control points total (22 single-bone + 1 multi-bone neck_group)
- 4-way directional controls: LMB/RMB × Horizontal/Vertical
- Each control point has unique rotation mapping per input combination
- See [POWERPOSE_INTEGRATION.md](POWERPOSE_INTEGRATION.md) for full details
- See [Posebridge_Control_Node_Map.md](Posebridge_Control_Node_Map.md) for complete control reference

**Control Points (23 total):**
- Head & Neck: head, neck_group (diamond), neckUpper, neckLower (4)
- Torso: chestUpper, chestLower, abdomenUpper, abdomenLower, pelvis (5)
- Left Arm: lCollar, lShldrBend, lForearmBend, lHand (4)
- Right Arm: rCollar, rShldrBend, rForearmBend, rHand (4)
- Left Leg: lThigh, lShin, lFoot (3)
- Right Leg: rThigh, rShin, rFoot (3)

**Key Axis Mappings (Corrected):**
- Head LMB Horizontal: Y-axis (turn)
- Head RMB Horizontal: Z-axis (tilt)
- Torso LMB Horizontal: Y-axis (twist)
- Torso RMB Horizontal: Z-axis (side lean)

**Previous Additions:**
- Pelvis positioned at bone tail to avoid overlap with abdomenLower
- Control point `position` property support (head/tail/mid)

**Performance Notes:**
- Rotation logic fully inlined in update_rotation() method
- No function call overhead on mouse movement
- Should feel smooth and responsive with no hitching
