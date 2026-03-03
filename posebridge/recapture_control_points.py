"""Recapture Fixed Control Point Positions - Run after moving outline to -50m"""

import sys
import bpy
from mathutils import Vector

# Add BlenDAZ and projects to path
blendaz_path = r"D:\dev\BlenDAZ"
projects_path = r"D:\dev\BlenDAZ\projects"
if blendaz_path not in sys.path:
    sys.path.insert(0, blendaz_path)
if projects_path not in sys.path:
    sys.path.insert(0, projects_path)

from posebridge.outline_generator_lineart import capture_fixed_control_points

# Auto-detect armature, or set manually to override
ARMATURE_NAME = None
OUTLINE_NAME = "PB_Outline_LineArt"

def find_daz_armature():
    """Find a DAZ Genesis armature in the scene."""
    obj = bpy.context.active_object
    if obj and obj.type == 'ARMATURE':
        bone_names = {b.name for b in obj.data.bones}
        if {'lPectoral', 'rPectoral', 'lCollar', 'rCollar'} & bone_names:
            return obj.name
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            bone_names = {b.name for b in obj.data.bones}
            if {'lPectoral', 'rPectoral', 'lCollar', 'rCollar'} & bone_names:
                return obj.name
    return None

if not ARMATURE_NAME:
    ARMATURE_NAME = find_daz_armature()

print("\n" + "="*70)
print("Recapturing Fixed Control Point Positions...")
print("="*70)

# Get armature
armature = bpy.data.objects.get(ARMATURE_NAME) if ARMATURE_NAME else None
if not armature or armature.type != 'ARMATURE':
    print(f"✗ ERROR: No DAZ armature found!")
    print("  Select an armature or set ARMATURE_NAME manually")
else:
    # Recapture positions (will use current outline Z position)
    count = capture_fixed_control_points(armature, OUTLINE_NAME)

    print("="*70)
    print(f"✓ Recaptured {count} fixed control point positions")
    print("✓ Control points now match outline position at Z=-50m")
    print("="*70 + "\n")
