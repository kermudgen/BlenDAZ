"""
Quick Test - BlenDAZ Daz Bone Select + PoseBridge
Just run this in Blender and start testing. No checklist BS.

Prerequisites:
- Genesis 8/9 character in scene
- In Pose mode
- Armature selected

Usage: Copy/paste into Blender console or run as script
"""

import bpy

def quick_test():
    print("\n" + "="*50)
    print("BlenDAZ Quick Test")
    print("="*50)

    # Basic checks
    if not bpy.context.active_object or bpy.context.active_object.type != 'ARMATURE':
        print("ERROR: Select an armature first")
        return False

    if bpy.context.mode != 'POSE':
        bpy.ops.object.mode_set(mode='POSE')

    armature = bpy.context.active_object
    print(f"\nArmature: {armature.name}")

    # Enable posebridge if available
    if hasattr(bpy.context.scene, 'posebridge_settings'):
        settings = bpy.context.scene.posebridge_settings
        settings.is_active = True
        settings.active_armature_name = armature.name
        settings.show_control_points = True
        print("PoseBridge: ENABLED")

        # Try to start draw handler (don't fail if already running)
        try:
            from posebridge.drawing import PoseBridgeDrawHandler
            PoseBridgeDrawHandler.register(bpy.context)
            print("Draw Handler: REGISTERED")
        except:
            print("Draw Handler: Already running or not available")
    else:
        print("PoseBridge: Not available")

    # Check if operator is registered
    print("\nChecking daz_bone_select operator...")
    if not hasattr(bpy.ops.view3d, 'daz_bone_select'):
        print("ERROR: daz_bone_select operator not found!")
        print("\nTo fix:")
        print("1. Open daz_bone_select.py in Blender Text Editor")
        print("2. Click 'Run Script' button")
        print("3. Check console for any errors")
        print("4. Run quick_test.py again")
        return False

    print("Operator found: view3d.daz_bone_select")

    # Start the operator - need to override context for 3D view
    print("Starting operator...")

    # Find a 3D view area
    view3d_area = None
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            view3d_area = area
            break

    if not view3d_area:
        print("ERROR: No 3D View found")
        print("Make sure you have a 3D viewport visible")
        return False

    # Override context to use the 3D view
    override = bpy.context.copy()
    override['area'] = view3d_area
    override['region'] = view3d_area.regions[-1]

    try:
        with bpy.context.temp_override(**override):
            bpy.ops.view3d.daz_bone_select('INVOKE_DEFAULT')
        print("\n" + "="*50)
        print("READY TO TEST!")
        print("="*50)
        print("Hover over bones in 3D View, click-drag to rotate")
        print("ESC to exit when done")
        print("="*50 + "\n")
        return True
    except Exception as e:
        print(f"\nERROR starting operator: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    quick_test()
