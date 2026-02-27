# All-inclusive PoseBridge setup script
# Run in Blender Text Editor BEFORE start_posebridge.py
#
# This script:
# 1. Reloads all PoseBridge modules (picks up code changes)
# 2. Re-registers PropertyGroups (new fields like interaction_mode)
# 3. Extracts hand geometry and stores hand control points
# 4. Creates face camera and stores face control points
# 5. Prints full summary
#
# After this, run start_posebridge.py to launch the modal operator.

import bpy
import sys
import os
import importlib

# ============================================================================
# Configuration - adjust to match your scene
# ============================================================================

STANDIN_NAME = "Fey Mesh_Standin"   # Standin mesh for hand extraction
ARMATURE_NAME = None                # Auto-detected if None
Z_OFFSET = -53.0                    # Hand camera Z offset

# ============================================================================
# Path setup
# ============================================================================

blendaz_path = r"D:\dev\BlenDAZ"
projects_path = r"D:\dev\BlenDAZ\projects"
posebridge_path = r"D:\dev\BlenDAZ\projects\posebridge"

for p in [blendaz_path, projects_path, posebridge_path]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ============================================================================
# Auto-detect DAZ armature
# ============================================================================

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

# ============================================================================
# Module reload + registration
# ============================================================================

print("\n" + "="*70)
print("POSEBRIDGE FULL SETUP")
print("="*70)

if not ARMATURE_NAME:
    print("ERROR: No DAZ armature found! Select an armature or set ARMATURE_NAME.")
    raise RuntimeError("No DAZ armature found")

print(f"Armature: {ARMATURE_NAME}")

# --- Unregister existing PoseBridge if loaded ---
if hasattr(bpy.context.scene, 'posebridge_settings'):
    print("\n--- Unregistering existing PoseBridge ---")
    try:
        import posebridge
        posebridge.unregister()
        print("  Unregistered old PoseBridge")
    except Exception as e:
        print(f"  Warning during unregister: {e}")
        # Force-delete the property if unregister failed
        try:
            del bpy.types.Scene.posebridge_settings
        except:
            pass

# --- Reload all PoseBridge modules ---
print("\n--- Reloading modules ---")

# Reload shared utils first (face morph controls live here)
import daz_shared_utils
importlib.reload(daz_shared_utils)
print("  Reloaded daz_shared_utils")

# Reload posebridge submodules in dependency order
import posebridge.core
import posebridge.drawing
import posebridge.panel_ui
import posebridge.interaction
import posebridge.outline_generator

for mod_name in ['posebridge.core', 'posebridge.control_points',
                 'posebridge.interaction', 'posebridge.drawing',
                 'posebridge.panel_ui', 'posebridge.presets',
                 'posebridge.outline_generator']:
    if mod_name in sys.modules:
        importlib.reload(sys.modules[mod_name])
        print(f"  Reloaded {mod_name}")

# Reload the posebridge package itself
import posebridge
importlib.reload(posebridge)
print("  Reloaded posebridge")

# Reload extract modules
import extract_hands
importlib.reload(extract_hands)
print("  Reloaded extract_hands")

import extract_face
importlib.reload(extract_face)
print("  Reloaded extract_face")

# --- Re-register PoseBridge ---
print("\n--- Registering PoseBridge ---")
posebridge.register()
print("  PoseBridge registered with updated PropertyGroups")

# Set armature
settings = bpy.context.scene.posebridge_settings
settings.active_armature_name = ARMATURE_NAME

# ============================================================================
# Step 1: Hand extraction and control points
# ============================================================================

print("\n" + "-"*70)
print("STEP 1: Hand Panel Setup")
print("-"*70)

# Find standin mesh
standin_name = STANDIN_NAME
alternate_names = ["Fey Mesh", "Fey Mesh_LineArt_Copy"]
for alt in alternate_names:
    if standin_name not in bpy.data.objects and alt in bpy.data.objects:
        standin_name = alt
        break

hand_result = None
hand_cp_count = 0

if standin_name in bpy.data.objects:
    print(f"  Using standin mesh: {standin_name}")

    hand_result = extract_hands.extract_and_setup_hands(
        standin_name,
        z_offset=Z_OFFSET,
        armature_name=ARMATURE_NAME if ARMATURE_NAME in bpy.data.objects else None
    )

    if hand_result:
        hand_cp_count = extract_hands.store_hand_control_points(hand_result)
        print(f"  Hand extraction complete: {hand_cp_count} control points stored")
    else:
        print("  WARNING: Hand extraction failed (hands may already exist)")
else:
    print(f"  WARNING: Standin mesh '{STANDIN_NAME}' not found. Skipping hand setup.")
    print("  Available meshes:")
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            print(f"    - {obj.name}")

# ============================================================================
# Step 2: Face panel setup
# ============================================================================

print("\n" + "-"*70)
print("STEP 2: Face Panel Setup")
print("-"*70)

armature_obj = bpy.data.objects.get(ARMATURE_NAME)
face_result = None

if armature_obj and armature_obj.type == 'ARMATURE':
    face_result = extract_face.setup_face_panel(armature_obj)
    if face_result:
        print(f"  Face setup complete: {face_result['control_points']} control points stored")
    else:
        print("  WARNING: Face panel setup failed")
else:
    print(f"  WARNING: Armature '{ARMATURE_NAME}' not found. Skipping face setup.")

# ============================================================================
# Summary
# ============================================================================

print("\n" + "="*70)
print("POSEBRIDGE SETUP COMPLETE")
print("="*70)

# Count CPs by panel
body_cps = [cp for cp in settings.control_points_fixed if not cp.panel_view or cp.panel_view == 'body']
hand_cps = [cp for cp in settings.control_points_fixed if cp.panel_view == 'hands']
face_cps = [cp for cp in settings.control_points_fixed if cp.panel_view == 'face']

print(f"""
Control Points:
  Body:  {len(body_cps)}
  Hands: {len(hand_cps)} ({len(hand_cps)//2 if hand_cps else 0} per hand)
  Face:  {len(face_cps)}
  Total: {len(body_cps) + len(hand_cps) + len(face_cps)}

Objects created:""")

if hand_result:
    print(f"  - {hand_result['left_hand'].name}")
    print(f"  - {hand_result['right_hand'].name}")
    print(f"  - {hand_result['camera'].name}")
if face_result:
    print(f"  - {face_result['camera'].name}")

print(f"""
Next step:
  Run 'start_posebridge.py' to launch the modal operator.
  Then click in the 3D viewport to start posing!
""")
print("="*70)
