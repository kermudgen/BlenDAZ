"""Recapture Fixed Control Point Positions - WITH MODULE RELOAD"""

import sys
import bpy
from mathutils import Vector

# Add BlenDAZ to path
blendaz_path = r"D:\dev\BlenDAZ"
if blendaz_path not in sys.path:
    sys.path.insert(0, blendaz_path)

# FORCE RELOAD of daz_shared_utils to pick up new control point
if 'daz_shared_utils' in sys.modules:
    import importlib
    import daz_shared_utils
    importlib.reload(daz_shared_utils)
    print("✓ Reloaded daz_shared_utils")

if 'outline_generator_lineart' in sys.modules:
    import importlib
    from posebridge import outline_generator_lineart
    importlib.reload(outline_generator_lineart)
    print("✓ Reloaded outline_generator_lineart")

from posebridge.outline_generator_lineart import capture_fixed_control_points

# Configuration
ARMATURE_NAME = "Fey"
OUTLINE_NAME = "PB_Outline_LineArt"

print("\n" + "="*70)
print("Recapturing Fixed Control Point Positions...")
print("="*70)

# Get armature
armature = bpy.data.objects.get(ARMATURE_NAME)
if not armature or armature.type != 'ARMATURE':
    print(f"✗ ERROR: Armature '{ARMATURE_NAME}' not found!")
    print("  Make sure ARMATURE_NAME matches your armature's name")
else:
    # Recapture positions (will use current outline Z position)
    count = capture_fixed_control_points(armature, OUTLINE_NAME)

    print("="*70)
    print(f"✓ Recaptured {count} fixed control point positions")
    print("✓ Control points now match outline position at Z=-50m")
    print("="*70 + "\n")
