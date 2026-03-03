BlenDAZ Quick Test - No BS, Just Test
======================================

SETUP (one time):
1. Load Genesis 8/9 character in Blender
2. Select armature, switch to Pose mode
3. Load daz_bone_select.py (and posebridge if you want)

TESTING (every time):
1. In Blender, go to Scripting workspace
2. Open quick_test.py
3. Click "Run Script" button
   OR
   Copy/paste into Python console

That's it. You'll be in testing mode immediately.

WHAT IT DOES:
- Checks you have an armature selected
- Switches to Pose mode if needed
- Enables posebridge (if available)
- Starts daz_bone_select operator
- Ready to test

NOW TEST:
- Hover over bones (you'll see highlights/control points)
- Click and drag to rotate
- ESC when done

NO CHECKLISTS. NO CEREMONY. JUST TEST.

Troubleshooting:
- "operator not found" → Load daz_bone_select.py first
- "no armature" → Select the Genesis armature
- Nothing happens → Check Blender console for errors
