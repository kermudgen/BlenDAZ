"""
Force clean registration of daz_bone_select
Run this if Ctrl+Shift+D isn't working
"""

import bpy

# First unregister if it exists
try:
    if hasattr(bpy.types, 'VIEW3D_OT_daz_bone_select'):
        bpy.utils.unregister_class(bpy.types.VIEW3D_OT_daz_bone_select)
        print("Unregistered old VIEW3D_OT_daz_bone_select")
except Exception as e:
    print(f"Unregister note: {e}")

try:
    if hasattr(bpy.types, 'POSE_OT_daz_powerpose_control'):
        bpy.utils.unregister_class(bpy.types.POSE_OT_daz_powerpose_control)
        print("Unregistered old POSE_OT_daz_powerpose_control")
except Exception as e:
    print(f"Unregister note: {e}")

try:
    if hasattr(bpy.types, 'VIEW3D_PT_daz_powerpose_main'):
        bpy.utils.unregister_class(bpy.types.VIEW3D_PT_daz_powerpose_main)
        print("Unregister old VIEW3D_PT_daz_powerpose_main")
except Exception as e:
    print(f"Unregister note: {e}")

try:
    if hasattr(bpy.types, 'POSE_OT_clear_ik_pose'):
        bpy.utils.unregister_class(bpy.types.POSE_OT_clear_ik_pose)
        print("Unregister old POSE_OT_clear_ik_pose")
except Exception as e:
    print(f"Unregister note: {e}")

print("\n" + "="*50)
print("Now run daz_bone_select.py from Text Editor")
print("="*50)
print("1. Open daz_bone_select.py in Text Editor")
print("2. Click 'Run Script'")
print("3. Try Ctrl+Shift+D in 3D View")
print("="*50 + "\n")
