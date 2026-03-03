# Test script: Full hand panel integration
# Run in Blender Text Editor after PoseBridge is registered
#
# This script:
# 1. Extracts hand geometry from standin mesh
# 2. Generates hand control points
# 3. Stores them in PoseBridge settings
# 4. Tests view switching

import bpy
import sys
import os

# Add posebridge to path
addon_dir = r"D:\dev\BlenDAZ\projects\posebridge"
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

import importlib
import extract_hands
importlib.reload(extract_hands)

# Configuration - adjust to match your scene
STANDIN_NAME = "Fey Mesh_Standin"  # Try alternate names below
ARMATURE_NAME = "Fey"
Z_OFFSET = -53.0

def run_integration_test():
    """Run full hand panel integration test."""

    print("\n" + "="*70)
    print("HAND PANEL INTEGRATION TEST")
    print("="*70)

    # Find standin mesh
    standin_name = STANDIN_NAME
    alternate_names = ["Fey Mesh", "Fey Mesh_LineArt_Copy"]
    for alt in alternate_names:
        if standin_name not in bpy.data.objects and alt in bpy.data.objects:
            standin_name = alt
            break

    if standin_name not in bpy.data.objects:
        print("ERROR: Could not find standin mesh. Available meshes:")
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                print(f"  - {obj.name}")
        return False

    print(f"\nUsing standin mesh: {standin_name}")
    print(f"Using armature: {ARMATURE_NAME}")

    # Step 1: Extract hand geometry and calculate bone positions
    print("\n--- Step 1: Extract hands and calculate bone positions ---")
    result = extract_hands.extract_and_setup_hands(
        standin_name,
        z_offset=Z_OFFSET,
        armature_name=ARMATURE_NAME if ARMATURE_NAME in bpy.data.objects else None
    )

    if not result:
        print("ERROR: Hand extraction failed")
        return False

    # Step 2: Store hand control points
    print("\n--- Step 2: Store hand control points ---")
    cp_count = extract_hands.store_hand_control_points(result)

    # Step 3: Verify control points were stored
    print("\n--- Step 3: Verify control points ---")
    settings = bpy.context.scene.posebridge_settings

    body_cps = [cp for cp in settings.control_points_fixed if not cp.panel_view or cp.panel_view == 'body']
    hand_cps = [cp for cp in settings.control_points_fixed if cp.panel_view == 'hands']

    print(f"  Body control points: {len(body_cps)}")
    print(f"  Hand control points: {len(hand_cps)}")

    if len(hand_cps) == 0:
        print("WARNING: No hand control points stored!")
    else:
        print("\n  Hand control points stored:")
        for cp in hand_cps[:10]:  # Show first 10
            print(f"    - {cp.id}: {cp.label} ({cp.control_type})")
        if len(hand_cps) > 10:
            print(f"    ... and {len(hand_cps) - 10} more")

    # Step 4: Test view switching
    print("\n--- Step 4: Test view switching ---")
    print(f"  Current active_panel: {settings.active_panel}")

    # Switch to hands view
    settings.active_panel = 'hands'
    print(f"  Switched to: {settings.active_panel}")

    # Switch back to body
    settings.active_panel = 'body'
    print(f"  Switched back to: {settings.active_panel}")

    # Summary
    print("\n" + "="*70)
    print("INTEGRATION TEST COMPLETE")
    print("="*70)
    print(f"""
Objects created:
  - {result['left_hand'].name}
  - {result['right_hand'].name}
  - {result['camera'].name}

Control points:
  - Body: {len(body_cps)}
  - Hands: {len(hand_cps)} ({len(hand_cps)//2} per hand)

To test view switching:
  1. Open N-Panel > DAZ > PoseBridge Editor > Panel Views
  2. Click 'Hands' button to switch to hand view
  3. Switch viewport camera to PB_Camera_Hands (Numpad 0 with camera selected)
  4. You should see hand control points (circles + diamonds)

Or run in console:
  bpy.context.scene.posebridge_settings.active_panel = 'hands'
""")

    return True


# Run the test
if __name__ == "__main__":
    run_integration_test()
