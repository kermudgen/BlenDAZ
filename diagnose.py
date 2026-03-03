"""
Diagnose daz_bone_select registration issues
"""

import bpy

print("\n" + "="*60)
print("DAZ BONE SELECT DIAGNOSTIC")
print("="*60)

# Check if operator exists in bpy.ops
print("\n1. Checking bpy.ops.view3d.daz_bone_select...")
if hasattr(bpy.ops.view3d, 'daz_bone_select'):
    print("   ✓ Found in bpy.ops.view3d")
else:
    print("   ✗ NOT found in bpy.ops.view3d")

# Check if class exists in bpy.types
print("\n2. Checking bpy.types.VIEW3D_OT_daz_bone_select...")
if hasattr(bpy.types, 'VIEW3D_OT_daz_bone_select'):
    print("   ✓ Found in bpy.types")
    cls = bpy.types.VIEW3D_OT_daz_bone_select
    print(f"   - bl_idname: {cls.bl_idname}")
    print(f"   - bl_label: {cls.bl_label}")

    # Check if it has required methods
    print("\n3. Checking required methods...")
    if hasattr(cls, 'invoke'):
        print("   ✓ Has invoke() method")
    else:
        print("   ✗ Missing invoke() method")

    if hasattr(cls, 'modal'):
        print("   ✓ Has modal() method")
    else:
        print("   ✗ Missing modal() method")
else:
    print("   ✗ NOT found in bpy.types")
    print("\n   ERROR: Class not registered!")
    print("   Run daz_bone_select.py first")

# Check current context
print("\n4. Current context...")
print(f"   - Mode: {bpy.context.mode}")
print(f"   - Active object: {bpy.context.active_object}")
if bpy.context.active_object:
    print(f"   - Object type: {bpy.context.active_object.type}")
print(f"   - Area type: {bpy.context.area.type if bpy.context.area else 'None'}")

# Try to get operator reference
print("\n5. Trying to get operator reference...")
try:
    op = bpy.ops.view3d.daz_bone_select
    print(f"   ✓ Got reference: {op}")

    # Try to check if it's callable
    print("\n6. Checking if operator can run...")

    # Get current context
    if bpy.context.area and bpy.context.area.type == 'VIEW_3D':
        print("   ✓ In 3D View context")

        # Try to invoke it
        print("\n7. Attempting to invoke...")
        try:
            result = bpy.ops.view3d.daz_bone_select('INVOKE_DEFAULT')
            print(f"   ✓ SUCCESS! Result: {result}")
        except Exception as e:
            print(f"   ✗ FAILED: {e}")
            print(f"   Error type: {type(e).__name__}")
    else:
        print("   ✗ NOT in 3D View context")
        print("   This script must be run from 3D View area")

except AttributeError as e:
    print(f"   ✗ Cannot get operator: {e}")

print("\n" + "="*60)
print("END DIAGNOSTIC")
print("="*60 + "\n")
