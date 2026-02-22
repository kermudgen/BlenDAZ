"""PoseBlend Viewport Setup - Orthographic camera and viewport configuration"""

import bpy
from mathutils import Vector, Euler
import math


# ============================================================================
# Viewport Configuration
# ============================================================================

def setup_poseblend_viewport(context, armature=None):
    """Configure viewport for PoseBlend grid view

    Creates an orthographic camera setup looking at the grid plane.

    Args:
        context: Blender context
        armature: Optional armature to frame in view

    Returns:
        Camera object
    """
    settings = context.scene.poseblend_settings

    # Create or get PoseBlend camera
    cam_data = get_or_create_camera()
    cam_obj = get_or_create_camera_object(context, cam_data)

    # Position camera for grid view
    position_camera_for_grid(cam_obj, armature)

    # Store camera name in settings
    settings.viewport_camera_name = cam_obj.name

    return cam_obj


def get_or_create_camera():
    """Get or create the PoseBlend camera data"""
    cam_name = "PoseBlend_Camera"

    camera = bpy.data.cameras.get(cam_name)
    if not camera:
        camera = bpy.data.cameras.new(cam_name)

    # Configure for orthographic view
    camera.type = 'ORTHO'
    camera.ortho_scale = 3.0  # Adjust based on grid size
    camera.clip_start = 0.1
    camera.clip_end = 100.0

    return camera


def get_or_create_camera_object(context, camera_data):
    """Get or create camera object"""
    cam_obj_name = "PoseBlend_CameraObj"

    cam_obj = bpy.data.objects.get(cam_obj_name)
    if not cam_obj:
        cam_obj = bpy.data.objects.new(cam_obj_name, camera_data)

        # Link to scene collection
        if cam_obj.name not in context.collection.objects:
            context.collection.objects.link(cam_obj)

    return cam_obj


def position_camera_for_grid(camera_obj, armature=None, layout='SIDE_BY_SIDE'):
    """Position camera to view the grid

    The grid overlay is drawn in screen space, but camera positioning
    determines what the user sees in the viewport alongside the grid.

    Args:
        camera_obj: Camera object to position
        armature: Optional armature to help with positioning
        layout: 'SIDE_BY_SIDE', 'FRONT', or 'OVERVIEW'
    """
    if layout == 'SIDE_BY_SIDE':
        # Character on left/center, grid overlay on right
        # Camera far enough back to see full character
        camera_obj.location = Vector((0, -6, 1.5))
        camera_obj.rotation_euler = Euler((math.radians(85), 0, 0), 'XYZ')
        camera_obj.data.ortho_scale = 4.0  # Wide enough for character + grid

    elif layout == 'FRONT':
        # Pure front view of character, grid overlaid in corner
        camera_obj.location = Vector((0, -4, 1.5))
        camera_obj.rotation_euler = Euler((math.radians(90), 0, 0), 'XYZ')
        camera_obj.data.ortho_scale = 3.0

    elif layout == 'OVERVIEW':
        # Angled view showing character from 3/4 angle
        camera_obj.location = Vector((3, -4, 2))
        camera_obj.rotation_euler = Euler((math.radians(75), 0, math.radians(35)), 'XYZ')
        camera_obj.data.ortho_scale = 4.0

    # Frame armature if provided
    if armature:
        # TODO: Calculate bounds and adjust ortho_scale to fit
        pass


def set_viewport_to_camera(context, camera_obj):
    """Set the active 3D viewport to use the PoseBlend camera

    Args:
        context: Blender context
        camera_obj: Camera object to use
    """
    # Find 3D view area
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    # Set to camera view
                    space.region_3d.view_perspective = 'CAMERA'
                    context.scene.camera = camera_obj

                    # Optionally lock view to camera
                    space.lock_camera = False

                    return True
    return False


def restore_viewport(context):
    """Restore viewport to normal perspective view

    Args:
        context: Blender context
    """
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.region_3d.view_perspective = 'PERSP'
                    return True
    return False


# ============================================================================
# Split View Setup (Optional)
# ============================================================================

def setup_split_view(context):
    """Setup a split view with grid on one side, character on other

    This is an advanced feature for later implementation.
    """
    # TODO: Implement split view configuration
    pass


# ============================================================================
# Cleanup
# ============================================================================

def cleanup_poseblend_viewport(context):
    """Remove PoseBlend camera and restore viewport

    Args:
        context: Blender context
    """
    restore_viewport(context)

    # Optionally remove camera objects
    # (keeping them allows quick re-activation)

    cam_obj = bpy.data.objects.get("PoseBlend_CameraObj")
    if cam_obj:
        # Unlink from collections but don't delete
        # This preserves user's camera position adjustments
        pass


# ============================================================================
# Viewport Overlay Control
# ============================================================================

def configure_viewport_overlays(context, show_bones=True, show_grid=False):
    """Configure viewport overlays for PoseBlend mode

    Args:
        context: Blender context
        show_bones: Whether to show armature bones
        show_grid: Whether to show Blender's default grid
    """
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    # Configure overlays
                    space.overlay.show_floor = show_grid
                    space.overlay.show_axis_x = show_grid
                    space.overlay.show_axis_y = show_grid
                    space.overlay.show_axis_z = False

                    # Keep bones visible
                    space.overlay.show_bones = show_bones

                    return


# ============================================================================
# Registration
# ============================================================================

def register():
    pass


def unregister():
    pass
