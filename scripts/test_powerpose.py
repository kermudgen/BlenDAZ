"""
Test script for PowerPose panel - Phase 1 MVP
Run this in Blender's script editor after loading daz_bone_select.py
"""

import bpy

# Ensure the addon is loaded
try:
    import daz_bone_select
    daz_bone_select.unregister()
    daz_bone_select.register()
    print("✓ Reloaded daz_bone_select addon")
except Exception as e:
    print(f"✗ Error reloading addon: {e}")

# Test 1: Check if PowerPose panel class is registered
if hasattr(bpy.types, 'VIEW3D_PT_daz_powerpose_main'):
    print("✓ PowerPose panel class registered")
else:
    print("✗ PowerPose panel class NOT registered")

# Test 2: Check if PowerPose operator is registered
if hasattr(bpy.types, 'POSE_OT_daz_powerpose_control'):
    print("✓ PowerPose operator registered")
else:
    print("✗ PowerPose operator NOT registered")

# Test 3: Check if active object is an armature
if bpy.context.active_object and bpy.context.active_object.type == 'ARMATURE':
    armature = bpy.context.active_object
    print(f"✓ Active armature: {armature.name}")

    # Test 4: Check if control points can be generated
    control_points = daz_bone_select.get_genesis8_control_points()
    print(f"✓ Generated {len(control_points)} control points")

    # Test 5: Check which bones exist in armature
    found_bones = []
    missing_bones = []
    for cp in control_points:
        if cp['bone_name'] in armature.pose.bones:
            found_bones.append(cp['bone_name'])
        else:
            missing_bones.append(cp['bone_name'])

    print(f"✓ Found {len(found_bones)} bones in armature")
    if missing_bones:
        print(f"  Missing bones: {', '.join(missing_bones)}")

else:
    print("✗ No armature selected - select an armature in Pose Mode to test")

print("\n=== MANUAL TESTING ===")
print("1. Open N-panel (press N in 3D viewport)")
print("2. Navigate to 'DAZ' tab")
print("3. You should see 'PowerPose' panel")
print("4. Left-click a control point button and drag to bend")
print("5. Right-click a control point button and drag to twist")
print("6. Release to keyframe, ESC to cancel")
