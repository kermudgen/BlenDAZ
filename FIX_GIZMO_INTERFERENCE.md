# Fix: Gizmo Interference with DAZ Bone Select Tool

**Issue**: Can't manipulate gizmos when DAZ Bone Select tool is active - gizmo disappears or selects different bone.

**Date**: 2026-02-08
**Status**: ✅ Fixed

## Problem

When the DAZ Bone Select tool is active (modal operator running), trying to use transform gizmos causes issues:

1. **Gizmo disappears** - Hover detection changes selection
2. **Wrong bone selected** - Click on gizmo selects bone under cursor instead
3. **Can't transform** - Tool intercepts mouse events meant for gizmo

**Root Cause:**
- DAZ Bone Select is a modal operator that stays active
- It intercepts MOUSEMOVE events for hover detection
- It intercepts LEFTMOUSE events for bone selection
- This conflicts with gizmo manipulation

## Solution

Added **TAB key toggle** to pause/resume the tool, allowing free gizmo manipulation.

### New Feature: Tool Pause Mode

**Press TAB to pause tool:**
```
Tool active (hover detection on)
  ↓ Press TAB
Tool paused (hover detection off)
  ↓ Use gizmos freely
  ↓ Press TAB again
Tool active (hover detection on)
```

### Code Changes

1. **Added pause state variable:**
```python
# Tool pause state (for gizmo manipulation)
_tool_paused = False
```

2. **Added TAB key handler:**
```python
# TAB key: Pause/resume tool (allows gizmo manipulation)
if event.type == 'TAB' and event.value == 'PRESS':
    self._tool_paused = not self._tool_paused
    if self._tool_paused:
        context.area.header_text_set("DAZ Bone Select PAUSED - Use gizmos freely | TAB to resume | ESC to exit")
        self.clear_hover(context)
    else:
        context.area.header_text_set("DAZ Bone Select Active - Click to select | TAB to pause | ESC to exit")
    return {'RUNNING_MODAL'}
```

3. **Pass through events when paused:**
```python
# If tool is paused, pass through all events (except TAB and ESC)
if self._tool_paused:
    if event.type == 'ESC' and event.value == 'PRESS':
        self.finish(context)
        return {'CANCELLED'}
    return {'PASS_THROUGH'}
```

4. **Updated header messages** to mention TAB key

## Usage

### Workflow with Gizmos

**Before (Broken):**
```
1. Activate tool (Ctrl+Shift+D)
2. Select bone
3. Try to use gizmo
4. ❌ Gizmo disappears or selects wrong bone
5. Must press ESC to exit tool completely
```

**After (Fixed):**
```
1. Activate tool (Ctrl+Shift+D)
2. Select bone
3. Press TAB to pause tool
4. ✅ Use gizmo freely (rotate, move, scale)
5. Press TAB to resume tool (continue selecting bones)
6. Press ESC to exit tool
```

### Example: Rotating Pectoral Bone

**Problem:** Pectoral bones don't support IK dragging (by design)

**Solution:** Use gizmo with paused tool
```
1. Activate tool (Ctrl+Shift+D)
2. Click pectoral bone to select it
3. Press TAB to pause tool
4. Use rotation gizmo to rotate bone
5. Press TAB to resume tool
6. Continue working
```

## Header Messages

**Tool Active:**
```
"DAZ Bone Select Active - Click to select | TAB to pause | ESC to exit"
```

**Tool Paused:**
```
"DAZ Bone Select PAUSED - Use gizmos freely | TAB to resume | ESC to exit"
```

**During Hover:**
```
"Hover: [bone_name] | Mesh: [mesh_name] | Armature: [armature_name] | CLICK to select"
```

## Keyboard Shortcuts Summary

| Key | Action | Description |
|-----|--------|-------------|
| **Ctrl+Shift+D** | Activate tool | Start DAZ Bone Select |
| **TAB** | Pause/Resume | Toggle hover detection on/off |
| **ESC** | Exit tool | Deactivate DAZ Bone Select |
| **P** | Pin Translation | Pin bone translation |
| **Shift+P** | Pin Rotation | Pin bone rotation |
| **U** | Unpin | Remove all pins |
| **Ctrl+Z** | Undo | Undo last IK drag |

## When to Use TAB Pause

**Use TAB pause when you want to:**
- ✓ Manipulate gizmos (rotate, move, scale)
- ✓ Use standard Blender transform tools (G, R, S keys)
- ✓ Adjust properties in side panels
- ✓ Work with bones that don't support IK (pectorals, twist bones)
- ✓ Fine-tune transforms without tool interference

**Don't need to pause for:**
- ✗ Clicking to select different bones (tool handles this)
- ✗ IK dragging bones (tool handles this)
- ✗ Viewing bone pins (tool handles this)

## Alternative: Exit Tool Completely

If you prefer, you can still **press ESC** to exit the tool completely:
```
1. Press Ctrl+Shift+D to activate
2. Select and pose bones
3. Press ESC to exit
4. Use gizmos normally
5. Press Ctrl+Shift+D again to reactivate when needed
```

**TAB pause vs. ESC exit:**
- **TAB pause**: Quick toggle, tool stays loaded, fast workflow
- **ESC exit**: Completely exits tool, cleaner state, need to reactivate

## Benefits

✅ **Flexible Workflow** - Toggle tool on/off as needed
✅ **No Conflicts** - Paused tool doesn't interfere with gizmos
✅ **Quick Toggle** - Single key press (TAB)
✅ **Clear Feedback** - Header shows pause state
✅ **Standard Pattern** - Similar to other modal tools in Blender

## Testing

### Test 1: Pause and Resume
1. Activate tool (Ctrl+Shift+D)
2. Press TAB
3. ✅ Header shows "PAUSED"
4. ✅ Hover highlighting stops
5. Press TAB again
6. ✅ Header shows "Active"
7. ✅ Hover highlighting resumes

### Test 2: Gizmo Manipulation While Paused
1. Activate tool
2. Select bone
3. Press TAB to pause
4. Use rotation gizmo
5. ✅ Bone rotates
6. ✅ No selection changes
7. ✅ Gizmo stays visible

### Test 3: ESC Still Exits
1. Activate tool
2. Press TAB to pause
3. Press ESC
4. ✅ Tool exits completely
5. ✅ Header clears

## Files Modified

1. `daz_bone_select.py` - Added TAB pause toggle functionality

## Related Issues

- **Pectoral IK Issue** - Pectorals don't support IK (fixed separately)
- **Twist Bone Issue** - Twist bones don't support IK (already handled)
- **Gizmo Conflicts** - This fix resolves gizmo interference

---

**Ready to test!** Press TAB to pause the tool and use gizmos freely on any bone, including pectorals.
