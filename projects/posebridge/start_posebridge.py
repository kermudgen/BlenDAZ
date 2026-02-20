"""PoseBridge Startup Script - Run this to start PoseBridge mode

Usage:
1. Open this file in Blender's Text Editor
2. Click the "Run Script" button (▶)
3. Control points should appear and modal operator will start
"""

import sys
import bpy

# ============================================================================
# Configuration
# ============================================================================

# Change this to match your armature's name
ARMATURE_NAME = "Fey"

# ============================================================================
# Setup
# ============================================================================

print("\n" + "="*70)
print("Starting PoseBridge...")
print("="*70)

# Add BlenDAZ and projects to path
blendaz_path = r"D:\dev\BlenDAZ"
projects_path = r"D:\dev\BlenDAZ\projects"
if blendaz_path not in sys.path:
    sys.path.insert(0, blendaz_path)
    print(f"✓ Added {blendaz_path} to Python path")
if projects_path not in sys.path:
    sys.path.insert(0, projects_path)
    print(f"✓ Added {projects_path} to Python path")

# Import modules
import posebridge
import daz_bone_select

# Register PoseBridge
if not hasattr(bpy.context.scene, 'posebridge_settings'):
    posebridge.register()
    print("✓ PoseBridge registered")
else:
    print("✓ PoseBridge already registered")

# Register daz_bone_select (CRITICAL for modal operator!)
# Unregister first if already registered to ensure clean state
if hasattr(bpy.ops.view3d, 'daz_bone_select'):
    print("⚠ daz_bone_select already registered, unregistering for clean state...")
    try:
        daz_bone_select.unregister()
        print("✓ Unregistered old daz_bone_select")
    except Exception as e:
        print(f"⚠ Could not unregister old daz_bone_select: {e}")

# Now register fresh
try:
    daz_bone_select.register()
    print("✓ daz_bone_select registered")
except Exception as e:
    print(f"✗ ERROR registering daz_bone_select: {e}")
    print("="*70)
    raise

# Enable PoseBridge mode
bpy.context.scene.posebridge_settings.is_active = True
bpy.context.scene.posebridge_settings.active_armature_name = ARMATURE_NAME
bpy.context.scene.posebridge_settings.show_control_points = True
print(f"✓ PoseBridge mode enabled for armature: {ARMATURE_NAME}")

# Register draw handler (unregister first if already registered to clean state)
from posebridge.drawing import PoseBridgeDrawHandler
if PoseBridgeDrawHandler._draw_handler is not None:
    print("⚠ Unregistering old draw handler...")
    PoseBridgeDrawHandler.unregister()

PoseBridgeDrawHandler.register()
print("✓ Draw handler registered")

# Verify operator is registered
if hasattr(bpy.ops.view3d, 'daz_bone_select'):
    print("✓ Modal operator registered")
else:
    print("✗ ERROR: Modal operator not found!")
    print("="*70)
    raise RuntimeError("daz_bone_select operator not registered")

print("="*70)
print("✓ PoseBridge is ready!")
print()
print("IMPORTANT: Click in the LEFT viewport (camera view) first!")
print("Then the modal operator will start automatically...")
print("="*70 + "\n")

# Invoke the modal operator automatically
bpy.ops.view3d.daz_bone_select('INVOKE_DEFAULT')
print("✓ Modal operator started - control points should be visible!")
print("  - Move mouse over control points → they turn yellow")
print("  - Click and drag to rotate bones")
print("  - Press ESC to exit")
