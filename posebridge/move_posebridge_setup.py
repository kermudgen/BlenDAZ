"""
Move PoseBridge camera and outline to offset location (out of main workspace)
"""

import bpy

import logging
log = logging.getLogger(__name__)


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
        log.warning(f"❌ Camera '{camera_name}' not found. Run outline generator first.")
        return None, None

    # Find the PoseBridge outline
    outline = bpy.data.objects.get(outline_name)

    if not outline:
        log.warning(f"❌ Outline '{outline_name}' not found. Run outline generator first.")
        return camera, None

    # Find the light
    light_name = f"{outline_name}_Light"
    light = bpy.data.objects.get(light_name)

    # Move camera
    original_camera_z = camera.location.z
    camera.location.z += offset_z
    log.debug(f"✓ Moved camera from Z={original_camera_z:.2f} to Z={camera.location.z:.2f}")

    # Move outline
    original_outline_z = outline.location.z
    outline.location.z += offset_z
    log.debug(f"✓ Moved outline from Z={original_outline_z:.2f} to Z={outline.location.z:.2f}")

    # Move light if it exists
    if light:
        original_light_z = light.location.z
        light.location.z += offset_z
        log.debug(f"✓ Moved light from Z={original_light_z:.2f} to Z={light.location.z:.2f}")

    return camera, outline


if __name__ == "__main__":
    log.info("\n" + "="*60)
    log.info("Moving PoseBridge Setup to Offset Location")
    log.info("="*60)

    camera, outline = move_posebridge_setup(outline_name="PB_Outline_LineArt", offset_z=-30.0)

    if camera and outline:
        log.info(f"\n✓ PoseBridge setup moved!")
        log.info(f"  Camera: {camera.name} at {camera.location}")
        log.info(f"  Outline: {outline.name} at {outline.location}")

        log.info("\nNext steps:")
        log.info("  1. Split viewport vertically (left and right)")
        log.info("  2. In LEFT viewport: Press Numpad 0 to enter camera view")
        log.info("  3. You should see the outline in isolation")
        log.info("  4. RIGHT viewport shows your character at original location")
    else:
        log.warning("\n❌ Failed to move PoseBridge setup")
        log.info("Make sure to run outline_generator_lineart.py first!")

    log.info("="*60)
