"""
Move PoseBridge camera and outline to offset location (out of main workspace)
"""

import bpy

def move_posebridge_setup(outline_name="PB_Outline_LineArt", offset_z=-30.0):
    """
    Move the PoseBridge camera and outline to an offset location

    Args:
        outline_name: Name of the outline GP object (must match outline generator)
        offset_z: Z-axis offset in meters (negative moves down)
    """

    # Find the PoseBridge camera
    camera_name = f"{outline_name}_Camera"
    camera = bpy.data.objects.get(camera_name)

    if not camera:
        print(f"❌ Camera '{camera_name}' not found. Run outline generator first.")
        return None, None

    # Find the PoseBridge outline
    outline = bpy.data.objects.get(outline_name)

    if not outline:
        print(f"❌ Outline '{outline_name}' not found. Run outline generator first.")
        return camera, None

    # Find the light
    light_name = f"{outline_name}_Light"
    light = bpy.data.objects.get(light_name)

    # Move camera
    original_camera_z = camera.location.z
    camera.location.z += offset_z
    print(f"✓ Moved camera from Z={original_camera_z:.2f} to Z={camera.location.z:.2f}")

    # Move outline
    original_outline_z = outline.location.z
    outline.location.z += offset_z
    print(f"✓ Moved outline from Z={original_outline_z:.2f} to Z={outline.location.z:.2f}")

    # Move light if it exists
    if light:
        original_light_z = light.location.z
        light.location.z += offset_z
        print(f"✓ Moved light from Z={original_light_z:.2f} to Z={light.location.z:.2f}")

    return camera, outline


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Moving PoseBridge Setup to Offset Location")
    print("="*60)

    camera, outline = move_posebridge_setup(outline_name="PB_Outline_LineArt", offset_z=-30.0)

    if camera and outline:
        print(f"\n✓ PoseBridge setup moved!")
        print(f"  Camera: {camera.name} at {camera.location}")
        print(f"  Outline: {outline.name} at {outline.location}")

        print("\nNext steps:")
        print("  1. Split viewport vertically (left and right)")
        print("  2. In LEFT viewport: Press Numpad 0 to enter camera view")
        print("  3. You should see the outline in isolation")
        print("  4. RIGHT viewport shows your character at original location")
    else:
        print("\n❌ Failed to move PoseBridge setup")
        print("Make sure to run outline_generator_lineart.py first!")

    print("="*60)
