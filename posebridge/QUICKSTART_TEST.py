"""
PoseBridge Phase 1 - Quick Start Test Script

This script sets up PoseBridge mode for immediate testing.
Copy and paste into Blender's Python console or run as a script.

Prerequisites:
- Genesis 8 character loaded in scene
- Character mesh visible
- Armature selected
- In Pose mode
"""

import bpy

def setup_posebridge_test():
    """Quick setup for PoseBridge testing"""

    print("\n" + "="*60)
    print("PoseBridge Phase 1 - Quick Start Test")
    print("="*60)

    # Step 1: Check prerequisites
    print("\n[Step 1] Checking prerequisites...")

    if not bpy.context.active_object:
        print("  ✗ No active object selected")
        print("  → Please select the Genesis 8 armature")
        return False

    armature = bpy.context.active_object
    if armature.type != 'ARMATURE':
        print(f"  ✗ Active object is {armature.type}, not ARMATURE")
        print("  → Please select the Genesis 8 armature")
        return False

    print(f"  ✓ Armature selected: {armature.name}")

    if bpy.context.mode != 'POSE':
        print("  ⚠️  Not in Pose mode, switching...")
        bpy.ops.object.mode_set(mode='POSE')
    print("  ✓ In Pose mode")

    # Step 2: Enable PoseBridge mode
    print("\n[Step 2] Enabling PoseBridge mode...")

    if not hasattr(bpy.context.scene, 'posebridge_settings'):
        print("  ✗ PoseBridge not registered!")
        print("  → Please ensure posebridge addon is loaded")
        return False

    settings = bpy.context.scene.posebridge_settings
    settings.is_active = True
    settings.active_armature_name = armature.name
    settings.sensitivity = 0.01  # Default sensitivity
    settings.show_control_points = True
    settings.show_outline = True
    settings.auto_keyframe = True

    print("  ✓ PoseBridge mode enabled")
    print(f"  ✓ Active armature: {settings.active_armature_name}")
    print(f"  ✓ Sensitivity: {settings.sensitivity}")

    # Step 3: Generate Line Art outline
    print("\n[Step 3] Generating Line Art outline...")

    outline_name = f"PB_Outline_LineArt_{armature.name}"
    existing_outline = bpy.data.objects.get(outline_name)

    if existing_outline:
        print(f"  ⚠️  Outline already exists: {outline_name}")
        print("  → Skipping generation (delete existing outline to regenerate)")
    else:
        try:
            bpy.ops.pose.posebridge_generate_lineart()
            print(f"  ✓ Outline generated: {outline_name}")
        except Exception as e:
            print(f"  ✗ Failed to generate outline: {e}")
            print("  → Try manually: bpy.ops.pose.posebridge_generate_lineart()")

    # Step 4: Register draw handler
    print("\n[Step 4] Registering draw handler...")

    try:
        from posebridge.drawing import PoseBridgeDrawHandler
        PoseBridgeDrawHandler.register(bpy.context)
        print("  ✓ Draw handler registered")
    except ImportError as e:
        print(f"  ✗ Failed to import PoseBridgeDrawHandler: {e}")
        print("  → Check posebridge/drawing.py exists")
        return False
    except Exception as e:
        print(f"  ⚠️  Draw handler registration: {e}")
        print("  → Handler may already be registered")

    # Step 5: Start modal operator
    print("\n[Step 5] Starting modal operator...")
    print("  → Run this manually to avoid blocking:")
    print("  bpy.ops.view3d.daz_bone_select('INVOKE_DEFAULT')")

    # Step 6: Ready to test
    print("\n" + "="*60)
    print("PoseBridge Setup Complete!")
    print("="*60)
    print("\nNext Steps:")
    print("1. Run: bpy.ops.view3d.daz_bone_select('INVOKE_DEFAULT')")
    print("2. Move mouse over viewport to see control points")
    print("3. Hover over a control point (turns yellow)")
    print("4. Click and drag to rotate bone")
    print("5. Release to keyframe rotation")
    print("6. Press ESC to cancel rotation")
    print("\nControl Points to Test:")
    print("  - lShldr / rShldr (shoulders)")
    print("  - lForeArm / rForeArm (elbows)")
    print("  - lHand / rHand (wrists)")
    print("  - head")
    print("  - lThigh / rThigh (hips)")
    print("  - lShin / rShin (knees)")
    print("  - lFoot / rFoot (ankles)")
    print("\nTroubleshooting:")
    print("  - No control points? Check modal operator is running")
    print("  - No outline? Manually run: bpy.ops.pose.posebridge_generate_lineart()")
    print("  - Rotation not working? Check debug prints in console")
    print("="*60 + "\n")

    return True


# Run setup
if __name__ == "__main__":
    setup_posebridge_test()


# Quick commands for manual control:
"""
# Enable PoseBridge mode:
bpy.context.scene.posebridge_settings.is_active = True
bpy.context.scene.posebridge_settings.active_armature_name = bpy.context.active_object.name

# Generate outline:
bpy.ops.pose.posebridge_generate_lineart()

# Register draw handler:
from posebridge.drawing import PoseBridgeDrawHandler
PoseBridgeDrawHandler.register(bpy.context)

# Start modal operator:
bpy.ops.view3d.daz_bone_select('INVOKE_DEFAULT')

# Disable PoseBridge mode:
bpy.context.scene.posebridge_settings.is_active = False

# Unregister draw handler:
from posebridge.drawing import PoseBridgeDrawHandler
PoseBridgeDrawHandler.unregister()
"""
