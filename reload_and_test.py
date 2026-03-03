"""
Reload daz_bone_select and start it immediately
Use this when testing - ensures clean reload
"""

import bpy
import sys
import importlib

def reload_and_test():
    print("\n" + "="*50)
    print("Reloading daz_bone_select...")
    print("="*50)

    # First, try to unregister if already loaded
    try:
        # Import the module
        if 'daz_bone_select' in sys.modules:
            import daz_bone_select
            print("Found existing module, unregistering...")
            daz_bone_select.unregister()
            print("Unregistered successfully")
        else:
            print("Module not loaded yet")
    except Exception as e:
        print(f"Note: Unregister had issues (this is normal): {e}")

    # Force reload the script file
    print("\nReloading from disk...")
    script_path = r"d:\dev\BlenDAZ\daz_bone_select.py"

    # Read and exec the file
    with open(script_path, 'r', encoding='utf-8') as f:
        code = f.read()

    # Execute in global namespace
    exec(code, globals())

    print("File loaded successfully")

    # Check prerequisites
    if not bpy.context.active_object or bpy.context.active_object.type != 'ARMATURE':
        print("\nERROR: Select an armature first")
        return False

    if bpy.context.mode != 'POSE':
        bpy.ops.object.mode_set(mode='POSE')

    armature = bpy.context.active_object
    print(f"\nArmature: {armature.name}")

    # Try to start the operator
    print("\nStarting daz_bone_select...")
    print("(Make sure your mouse is over the 3D View)")
    print("\n" + "="*50)
    print("Move your mouse to 3D View and press Ctrl+Shift+D")
    print("="*50 + "\n")

    return True

if __name__ == "__main__":
    reload_and_test()
