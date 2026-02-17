"""
Reload daz_bone_select addon properly in Blender
Run this in Blender's Python console
"""

import bpy
import sys
import importlib

# First, stop any running modal operator
try:
    bpy.ops.view3d.daz_bone_select('INVOKE_DEFAULT')  # This will error but that's ok
except:
    pass

# Unregister the addon
try:
    import daz_bone_select
    daz_bone_select.unregister()
    print("✓ Unregistered daz_bone_select")
except Exception as e:
    print(f"⚠ Unregister warning: {e}")

# Remove from sys.modules to force full reload
if 'daz_bone_select' in sys.modules:
    del sys.modules['daz_bone_select']
    print("✓ Cleared from sys.modules")

# Re-import and register
import daz_bone_select
daz_bone_select.register()
print("✓ Re-registered daz_bone_select")

print("\n✓ Reload complete! Now restart the modal operator:")
print("   bpy.ops.view3d.daz_bone_select('INVOKE_DEFAULT')")
