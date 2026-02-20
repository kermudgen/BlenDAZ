"""PoseBridge Drawing - GPU rendering for overlays"""

import bpy
import gpu
import math
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from bpy_extras import view3d_utils

# ============================================================================
# Draw Handler Class
# ============================================================================

class PoseBridgeDrawHandler:
    """Manages GPU drawing for PoseBridge overlay"""

    _draw_handler = None
    _hovered_control_point = None  # Track hovered control point for highlight

    @classmethod
    def register(cls, _context=None):
        """Register draw handlers"""
        if cls._draw_handler is None:
            cls._draw_handler = bpy.types.SpaceView3D.draw_handler_add(
                cls.draw_posebridge_overlay,
                (),  # Let Blender provide per-viewport context
                'WINDOW',
                'POST_PIXEL'
            )

    @classmethod
    def unregister(cls):
        """Remove draw handlers"""
        if cls._draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(cls._draw_handler, 'WINDOW')
            cls._draw_handler = None
            cls._hovered_control_point = None

    @staticmethod
    def draw_posebridge_overlay():
        """Main draw callback for PoseBridge elements"""
        # Get context from bpy - draw handlers don't receive context parameter
        context = bpy.context

        settings = context.scene.posebridge_settings
        if not settings.is_active:
            return

        # Draw control points if enabled
        if settings.show_control_points:
            PoseBridgeDrawHandler.draw_control_points(context)

    @staticmethod
    def draw_outline(context):
        """Ensure GP outline is visible

        Note: For Phase 1, the Line Art GP object handles outline rendering.
        We just need to ensure it's visible and linked properly.
        """
        settings = context.scene.posebridge_settings

        # Get active armature
        armature = None
        if settings.active_armature_name:
            armature = bpy.data.objects.get(settings.active_armature_name)

        if not armature or armature.type != 'ARMATURE':
            return

        # Find associated GP outline object
        outline_name = f"PB_Outline_LineArt_{armature.name}"
        gp_obj = bpy.data.objects.get(outline_name)

        if gp_obj and gp_obj.type == 'GREASEPENCIL':
            # Ensure outline visibility matches settings
            gp_obj.hide_viewport = not settings.show_outline
            gp_obj.hide_render = not settings.show_outline

    @staticmethod
    def draw_control_points(context):
        """Draw control point widgets using GPU"""
        settings = context.scene.posebridge_settings

        # Get active armature
        armature = None
        if settings.active_armature_name:
            armature = bpy.data.objects.get(settings.active_armature_name)

        if not armature or armature.type != 'ARMATURE':
            return

        # Get viewport region and 3D view
        region = context.region
        rv3d = context.space_data.region_3d

        if not region or not rv3d:
            return

        # Import shared utilities
        import sys
        import os
        addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if addon_dir not in sys.path:
            sys.path.insert(0, addon_dir)

        from daz_shared_utils import get_genesis8_control_points

        # USE FIXED CONTROL POINT POSITIONS (from T-pose)
        fixed_control_points = settings.control_points_fixed

        if not fixed_control_points or len(fixed_control_points) == 0:
            # No fixed positions stored yet - need to generate outline first
            return

        # Get active panel view
        active_panel = settings.active_panel

        # Draw each fixed control point that matches the active panel
        for cp in fixed_control_points:
            # Filter by panel view - body control points have empty panel_view (legacy)
            cp_panel = cp.panel_view if cp.panel_view else 'body'
            if cp_panel != active_panel:
                continue
            bone_name = cp.bone_name

            # Get fixed 3D position (from T-pose, with Z offset already applied)
            fixed_pos_3d = Vector(cp.position_3d_fixed)

            # Project fixed 3D position to 2D viewport coordinates
            pos_2d = view3d_utils.location_3d_to_region_2d(
                region,
                rv3d,
                fixed_pos_3d
            )

            if pos_2d is None:
                continue  # Bone is behind camera

            # Determine color (yellow if hovered, cyan otherwise)
            # For multi-bone controls, check against the control point ID
            check_id = cp.id if cp.control_type == 'multi' else bone_name
            is_hovered = (PoseBridgeDrawHandler._hovered_control_point == check_id)
            color = (1.0, 1.0, 0.0, 1.0) if is_hovered else (0.0, 0.8, 1.0, 1.0)  # Yellow : Cyan

            # Draw control point with appropriate shape
            if cp.control_type == 'multi':
                # Multi-bone control: draw as diamond
                PoseBridgeDrawHandler.draw_control_point_diamond(
                    pos_2d,
                    size=10.0,  # Pixel size (slightly larger than circles)
                    color=color,
                    filled=True
                )
            else:
                # Single bone control: draw as circle
                PoseBridgeDrawHandler.draw_control_point_circle(
                    pos_2d,
                    radius=8.0,  # Pixel radius
                    color=color,
                    filled=True
                )

    @staticmethod
    def draw_control_point_circle(position, radius, color, filled=True):
        """Draw single control point circle

        Args:
            position: Vector((x, y)) in pixel coordinates
            radius: Circle radius in pixels
            color: (r, g, b, a) color tuple
            filled: Whether to fill the circle or just outline
        """
        # Generate circle vertices
        segments = 32
        vertices = []

        for i in range(segments):
            angle = 2.0 * math.pi * i / segments
            x = position[0] + radius * math.cos(angle)
            y = position[1] + radius * math.sin(angle)
            vertices.append((x, y))

        # Create shader and batch
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        if filled:
            # Draw filled circle using triangle fan
            # Create triangle fan indices
            fan_vertices = [position]  # Center point
            fan_vertices.extend(vertices)
            fan_vertices.append(vertices[0])  # Close the fan

            batch = batch_for_shader(shader, 'TRI_FAN', {"pos": fan_vertices})
        else:
            # Draw outline using line loop
            batch = batch_for_shader(shader, 'LINE_LOOP', {"pos": vertices})

        # Enable blending for transparency
        gpu.state.blend_set('ALPHA')

        # Draw
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

        # Reset state
        gpu.state.blend_set('NONE')

    @staticmethod
    def draw_control_point_diamond(position, size, color, filled=True):
        """Draw diamond shape for group control points

        Args:
            position: Vector((x, y)) in pixel coordinates
            size: Diamond size in pixels (half-width/height)
            color: (r, g, b, a) color tuple
            filled: Whether to fill the diamond or just outline
        """
        # Generate diamond vertices (4 points)
        vertices = [
            (position[0], position[1] + size),        # Top
            (position[0] + size, position[1]),        # Right
            (position[0], position[1] - size),        # Bottom
            (position[0] - size, position[1]),        # Left
        ]

        # Create shader and batch
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        if filled:
            # Draw filled diamond using triangle fan
            fan_vertices = [position]  # Center point
            fan_vertices.extend(vertices)
            fan_vertices.append(vertices[0])  # Close the fan

            batch = batch_for_shader(shader, 'TRI_FAN', {"pos": fan_vertices})
        else:
            # Draw outline using line loop
            batch = batch_for_shader(shader, 'LINE_LOOP', {"pos": vertices})

        # Enable blending for transparency
        gpu.state.blend_set('ALPHA')

        # Draw
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

        # Reset state
        gpu.state.blend_set('NONE')

    @staticmethod
    def draw_control_point_sun(position, radius, color):
        """Draw sun-shape for multi-bone control (for Phase 2)

        Args:
            position: Vector((x, y)) in pixel coordinates
            radius: Circle radius in pixels
            color: (r, g, b, a) color tuple
        """
        # Draw filled circle center
        PoseBridgeDrawHandler.draw_control_point_circle(position, radius, color, filled=True)

        # Draw radiating lines
        num_rays = 8
        ray_length = radius * 1.5

        vertices = []
        for i in range(num_rays):
            angle = 2.0 * math.pi * i / num_rays
            # Inner point (at circle edge)
            x1 = position[0] + radius * math.cos(angle)
            y1 = position[1] + radius * math.sin(angle)
            # Outer point
            x2 = position[0] + ray_length * math.cos(angle)
            y2 = position[1] + ray_length * math.sin(angle)

            vertices.extend([(x1, y1), (x2, y2)])

        # Draw lines
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'LINES', {"pos": vertices})

        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(2.0)

        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')

# ============================================================================
# Registration
# ============================================================================

def register():
    """Register drawing system"""
    # Draw handlers will be registered when PoseBridge mode is activated
    pass

def unregister():
    """Unregister drawing system"""
    PoseBridgeDrawHandler.unregister()
