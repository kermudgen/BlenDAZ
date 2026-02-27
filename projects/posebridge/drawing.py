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

        # Find associated GP outline object from active CharacterSlot
        outline_name = None
        if hasattr(settings, 'blendaz_characters'):
            idx = settings.blendaz_active_index
            if 0 <= idx < len(settings.blendaz_characters):
                outline_name = settings.blendaz_characters[idx].outline_gp_name
        # Fallback: try old naming patterns
        if not outline_name:
            import re
            _tag = re.sub(r'[^A-Za-z0-9_]', '_', armature.name).strip('_')
            outline_name = f"PB_Outline_{_tag}"
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

        # Only draw CPs in the viewport that is looking through the correct PoseBridge camera.
        # This prevents the overlay from drawing (and wasting GPU) in the main 3D viewport.
        # Body panel uses a free viewport — no camera filter applies there.
        panel_cameras = {
            'hands': 'PB_Camera_Hands',
            'face':  'PB_Camera_Face',
        }
        expected_camera = panel_cameras.get(active_panel)
        if expected_camera:
            if rv3d.view_perspective != 'CAMERA':
                return
            space = context.space_data
            cam = space.camera if space.camera else context.scene.camera
            if not cam or cam.name != expected_camera:
                return

        # For face CPs, precompute head bone's current world matrix (bone-local → world)
        face_head_matrix = None
        if active_panel == 'face':
            armature = bpy.data.objects.get(settings.active_armature_name)
            if armature and armature.type == 'ARMATURE':
                head_pbone = armature.pose.bones.get('head')
                if head_pbone:
                    face_head_matrix = armature.matrix_world @ head_pbone.matrix

        # Draw each fixed control point that matches the active panel
        for cp in fixed_control_points:
            # Filter by panel view - body control points have empty panel_view (legacy)
            cp_panel = cp.panel_view if cp.panel_view else 'body'
            if cp_panel != active_panel:
                continue
            bone_name = cp.bone_name

            # Get fixed 3D position (from T-pose, with Z offset already applied)
            fixed_pos_3d = Vector(cp.position_3d_fixed)

            # Face CPs are stored in head-bone-local space — transform to current world
            if cp_panel == 'face' and face_head_matrix:
                fixed_pos_3d = face_head_matrix @ fixed_pos_3d

            # Project fixed 3D position to 2D viewport coordinates
            pos_2d = view3d_utils.location_3d_to_region_2d(
                region,
                rv3d,
                fixed_pos_3d
            )

            if pos_2d is None:
                continue  # Bone is behind camera

            # Determine color based on hover and interaction mode
            # For multi-bone and morph controls, check against CP id; single rotation uses bone_name
            if cp.control_type == 'multi' or cp.interaction_mode == 'morph':
                check_id = cp.id
            else:
                check_id = bone_name
            is_hovered = (PoseBridgeDrawHandler._hovered_control_point == check_id)
            if is_hovered:
                color = (1.0, 1.0, 0.0, 1.0)  # Yellow when hovered
            elif cp.interaction_mode == 'morph':
                color = (1.0, 0.5, 0.8, 1.0)  # Pink for morph CPs (face)
            else:
                color = (0.0, 0.8, 1.0, 1.0)  # Cyan for rotation CPs (body/hands)

            # Draw control point with appropriate shape
            if cp.shape == 'square':
                PoseBridgeDrawHandler.draw_control_point_square(
                    pos_2d,
                    size=8.0,
                    color=color,
                    filled=True
                )
            elif cp.control_type == 'multi':
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
    def draw_control_point_square(position, size, color, filled=True):
        """Draw square shape for joint-level group control points

        Args:
            position: Vector((x, y)) in pixel coordinates
            size: Half-width of the square in pixels
            color: (r, g, b, a) color tuple
            filled: Whether to fill the square or just outline
        """
        vertices = [
            (position[0] - size, position[1] + size),  # Top-left
            (position[0] + size, position[1] + size),  # Top-right
            (position[0] + size, position[1] - size),  # Bottom-right
            (position[0] - size, position[1] - size),  # Bottom-left
        ]

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        if filled:
            fan_vertices = [position]  # Center point
            fan_vertices.extend(vertices)
            fan_vertices.append(vertices[0])  # Close the fan
            batch = batch_for_shader(shader, 'TRI_FAN', {"pos": fan_vertices})
        else:
            batch = batch_for_shader(shader, 'LINE_LOOP', {"pos": vertices})

        gpu.state.blend_set('ALPHA')
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
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
