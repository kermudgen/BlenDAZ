"""
Reload daz_bone_select addon properly in Blender
Run this in Blender's Python console
"""

import bpy
import sys
import importlib

# Purge any stale draw handlers from a previous load (prevents ReferenceError spam
# that occurs when the operator is reloaded while handlers are still registered)
try:
    import daz_bone_select
    stale = list(daz_bone_select.VIEW3D_OT_daz_bone_select._active_draw_handlers)
    for h in stale:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
            print(f"✓ Removed stale draw handler: {h}")
        except Exception as e:
            print(f"⚠ Handler already gone: {e}")
    daz_bone_select.VIEW3D_OT_daz_bone_select._active_draw_handlers.clear()
except Exception as e:
    print(f"⚠ Handler purge skipped: {e}")

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
