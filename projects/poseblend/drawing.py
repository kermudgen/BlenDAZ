"""PoseBlend Drawing - GPU rendering for grid and dots"""

import bpy
import gpu
import math
from gpu_extras.batch import batch_for_shader
from mathutils import Vector


# ============================================================================
# Draw Handler Class
# ============================================================================

class PoseBlendDrawHandler:
    """Manages GPU drawing for PoseBlend overlay"""

    _draw_handler = None
    _hovered_dot_id = None  # Track which dot is being hovered

    @classmethod
    def register_handler(cls):
        """Register draw handler"""
        if cls._draw_handler is None:
            cls._draw_handler = bpy.types.SpaceView3D.draw_handler_add(
                cls.draw_poseblend_overlay,
                (),
                'WINDOW',
                'POST_PIXEL'
            )

    @classmethod
    def unregister_handler(cls):
        """Remove draw handler"""
        if cls._draw_handler is not None:
            bpy.types.SpaceView3D.draw_handler_remove(cls._draw_handler, 'WINDOW')
            cls._draw_handler = None

    @staticmethod
    def draw_poseblend_overlay():
        """Main draw callback"""
        context = bpy.context
        settings = context.scene.poseblend_settings

        if not settings.is_active:
            return

        grid = settings.get_active_grid()
        if not grid:
            return

        # Calculate grid region
        region = context.region
        grid_region = PoseBlendDrawHandler.calculate_grid_region(region, settings)

        zoom = settings.grid_zoom
        pan = tuple(settings.grid_pan)

        # Draw elements
        PoseBlendDrawHandler.draw_background(grid_region, grid.background_color)
        PoseBlendDrawHandler.draw_grid_lines(grid_region, grid, zoom, pan)
        PoseBlendDrawHandler.draw_dots(grid_region, grid, settings, zoom, pan)

        if settings.cursor_over_grid:
            PoseBlendDrawHandler.draw_grid_border(grid_region)

        if settings.cursor_active:
            PoseBlendDrawHandler.draw_cursor(grid_region, settings.cursor_position, zoom, pan)
            PoseBlendDrawHandler.draw_influence_lines(grid_region, grid, settings, zoom, pan)

    @staticmethod
    def calculate_grid_region(region, settings):
        """Calculate grid region within viewport based on position setting

        Args:
            region: Viewport region
            settings: PoseBlendSettings with grid_screen_position and grid_screen_size

        Returns:
            Dict with x, y, width, height in pixels
        """
        margin = 50
        size_ratio = settings.grid_screen_size
        max_size = min(region.width, region.height) * size_ratio

        # Ensure square grid
        grid_size = max_size

        position = settings.grid_screen_position

        if position == 'BOTTOM_LEFT':
            # Bottom left corner (clear of N-panel)
            x = margin
            y = margin

        elif position == 'RIGHT':
            # Right side panel
            x = region.width - grid_size - margin
            y = (region.height - grid_size) / 2

        elif position == 'LEFT':
            # Left side panel
            x = margin
            y = (region.height - grid_size) / 2

        elif position == 'TOP_RIGHT':
            # Top right corner
            x = region.width - grid_size - margin
            y = region.height - grid_size - margin

        elif position == 'BOTTOM_RIGHT':
            # Bottom right corner
            x = region.width - grid_size - margin
            y = margin

        elif position == 'CENTER':
            # Centered (covers character)
            x = (region.width - grid_size) / 2
            y = (region.height - grid_size) / 2

        else:
            # Default to right
            x = region.width - grid_size - margin
            y = (region.height - grid_size) / 2

        return {
            'x': x,
            'y': y,
            'width': grid_size,
            'height': grid_size
        }

    @staticmethod
    def grid_to_pixel(grid_pos, grid_region, zoom=1.0, pan_center=(0.5, 0.5)):
        """Convert dot-space coords to pixel coords, accounting for zoom and pan."""
        view_x = (grid_pos[0] - pan_center[0]) * zoom + 0.5
        view_y = (grid_pos[1] - pan_center[1]) * zoom + 0.5
        return (
            grid_region['x'] + view_x * grid_region['width'],
            grid_region['y'] + view_y * grid_region['height']
        )

    @staticmethod
    def draw_background(grid_region, color):
        """Draw grid background"""
        x, y = grid_region['x'], grid_region['y']
        w, h = grid_region['width'], grid_region['height']

        vertices = [
            (x, y),
            (x + w, y),
            (x + w, y + h),
            (x, y + h)
        ]

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices})

        gpu.state.blend_set('ALPHA')
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        gpu.state.blend_set('NONE')

    @staticmethod
    def draw_grid_border(grid_region):
        """Draw highlight border around grid when cursor is over it"""
        x, y = grid_region['x'], grid_region['y']
        w, h = grid_region['width'], grid_region['height']

        vertices = [
            (x, y),
            (x + w, y),
            (x + w, y + h),
            (x, y + h)
        ]

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'LINE_LOOP', {"pos": vertices})

        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(2.0)
        shader.bind()
        shader.uniform_float("color", (1.0, 0.75, 0.0, 0.6))  # Amber
        batch.draw(shader)
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')

    @staticmethod
    def draw_grid_lines(grid_region, grid, zoom=1.0, pan_center=(0.5, 0.5)):
        """Draw grid lines, scaling with zoom and pan.

        Lines extend across the entire visible area at regular grid
        intervals, not just the 0-1 dot-space range. When zoomed out,
        extra lines fill the space around the dots.
        """
        if not grid.show_grid_lines:
            return

        cols, rows = grid.grid_divisions
        gx, gy = grid_region['x'], grid_region['y']
        gw, gh = grid_region['width'], grid_region['height']

        # Visible range in dot-space
        cx, cy = pan_center
        vis_min_x = cx - 0.5 / zoom if zoom > 0 else 0.0
        vis_max_x = cx + 0.5 / zoom if zoom > 0 else 1.0
        vis_min_y = cy - 0.5 / zoom if zoom > 0 else 0.0
        vis_max_y = cy + 0.5 / zoom if zoom > 0 else 1.0

        vertices = []

        # Vertical lines at cell intervals across full visible range
        cell_w = 1.0 / cols
        first_col = math.floor(vis_min_x / cell_w)
        last_col = math.ceil(vis_max_x / cell_w)
        for i in range(first_col, last_col + 1):
            dot_x = i * cell_w
            px = gx + ((dot_x - cx) * zoom + 0.5) * gw
            vertices.extend([(px, gy), (px, gy + gh)])

        # Horizontal lines at cell intervals across full visible range
        cell_h = 1.0 / rows
        first_row = math.floor(vis_min_y / cell_h)
        last_row = math.ceil(vis_max_y / cell_h)
        for i in range(first_row, last_row + 1):
            dot_y = i * cell_h
            py = gy + ((dot_y - cy) * zoom + 0.5) * gh
            vertices.extend([(gx, py), (gx + gw, py)])

        if not vertices:
            return

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'LINES', {"pos": vertices})

        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(1.0)
        shader.bind()
        shader.uniform_float("color", grid.grid_line_color)
        batch.draw(shader)
        gpu.state.blend_set('NONE')

    @staticmethod
    def draw_dots(grid_region, grid, settings, zoom=1.0, pan_center=(0.5, 0.5)):
        """Draw all dots on the grid"""
        # Check for hover based on cursor position
        hovered_idx = -1
        if settings.cursor_active or True:  # Always check hover for visual feedback
            from .grid import find_dot_at_position
            cursor_pos = tuple(settings.cursor_position)
            _, hovered_idx = find_dot_at_position(cursor_pos, grid.dots, hit_radius=0.05)

        for idx, dot in enumerate(grid.dots):
            pixel_pos = PoseBlendDrawHandler.grid_to_pixel(
                tuple(dot.position), grid_region, zoom, pan_center
            )

            # Skip dots whose center is outside the grid square
            gx, gy = grid_region['x'], grid_region['y']
            gw, gh = grid_region['width'], grid_region['height']
            if pixel_pos[0] < gx or pixel_pos[0] > gx + gw:
                continue
            if pixel_pos[1] < gy or pixel_pos[1] > gy + gh:
                continue

            # Determine state
            is_hovered = (idx == hovered_idx)
            is_selected = (idx == grid.active_dot_index)

            # Choose color based on state
            if is_hovered:
                # Amber highlight on hover
                color = (1.0, 0.75, 0.0, 1.0)
                radius = 14
            elif is_selected:
                color = tuple(dot.color)
                radius = 12
            else:
                color = tuple(dot.color)
                radius = 8

            # Draw dot
            PoseBlendDrawHandler.draw_dot(pixel_pos, radius, color, is_selected, is_hovered)

            # Draw label
            PoseBlendDrawHandler.draw_label(pixel_pos, dot.name, radius)

    @staticmethod
    def draw_dot(position, radius, color, is_selected=False, is_hovered=False):
        """Draw a single dot with optional highlight effects

        Args:
            position: (x, y) pixel coordinates
            radius: Dot radius in pixels
            color: (r, g, b, a) fill color
            is_selected: Draw selection ring
            is_hovered: Draw hover glow effect
        """
        segments = 32
        vertices = []

        # Generate circle vertices
        for i in range(segments):
            angle = 2.0 * math.pi * i / segments
            x = position[0] + radius * math.cos(angle)
            y = position[1] + radius * math.sin(angle)
            vertices.append((x, y))

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')

        # Draw outer glow if hovered (amber halo effect)
        if is_hovered:
            glow_radius = radius + 6
            glow_vertices = []
            for i in range(segments):
                angle = 2.0 * math.pi * i / segments
                x = position[0] + glow_radius * math.cos(angle)
                y = position[1] + glow_radius * math.sin(angle)
                glow_vertices.append((x, y))

            glow_fan = [position] + glow_vertices + [glow_vertices[0]]
            batch_glow = batch_for_shader(shader, 'TRI_FAN', {"pos": glow_fan})
            shader.bind()
            shader.uniform_float("color", (1.0, 0.6, 0.0, 0.3))  # Amber glow, semi-transparent
            batch_glow.draw(shader)

        # Draw filled circle (main dot)
        fan_vertices = [position] + vertices + [vertices[0]]
        batch = batch_for_shader(shader, 'TRI_FAN', {"pos": fan_vertices})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

        # Draw outline ring
        outline_color = (1.0, 1.0, 1.0, 0.8) if is_hovered else (0.2, 0.2, 0.2, 0.6)
        if is_selected:
            outline_color = (1.0, 1.0, 0.0, 1.0)  # Yellow for selected

        batch_outline = batch_for_shader(shader, 'LINE_LOOP', {"pos": vertices})
        gpu.state.line_width_set(2.0 if (is_selected or is_hovered) else 1.0)
        shader.uniform_float("color", outline_color)
        batch_outline.draw(shader)

        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')

    @staticmethod
    def draw_label(position, text, offset):
        """Draw text label near dot

        Note: Blender's GPU module doesn't support text directly.
        For text, we'd need to use blf module.
        This is a placeholder - actual implementation would use blf.
        """
        # TODO: Implement text drawing with blf module
        pass

    @staticmethod
    def draw_cursor(grid_region, cursor_pos, zoom=1.0, pan_center=(0.5, 0.5)):
        """Draw cursor crosshair"""
        pixel_pos = PoseBlendDrawHandler.grid_to_pixel(
            tuple(cursor_pos), grid_region, zoom, pan_center
        )

        size = 15
        vertices = [
            # Horizontal line
            (pixel_pos[0] - size, pixel_pos[1]),
            (pixel_pos[0] + size, pixel_pos[1]),
            # Vertical line
            (pixel_pos[0], pixel_pos[1] - size),
            (pixel_pos[0], pixel_pos[1] + size),
        ]

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'LINES', {"pos": vertices})

        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(2.0)
        shader.bind()
        shader.uniform_float("color", (1.0, 1.0, 1.0, 0.8))
        batch.draw(shader)
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')

    @staticmethod
    def draw_influence_lines(grid_region, grid, settings, zoom=1.0, pan_center=(0.5, 0.5)):
        """Draw lines from cursor to influential dots"""
        from .blending import get_top_influences

        cursor_pos = tuple(settings.cursor_position)
        influences = get_top_influences(cursor_pos, grid.dots, max_count=3)

        if not influences:
            return

        cursor_pixel = PoseBlendDrawHandler.grid_to_pixel(cursor_pos, grid_region, zoom, pan_center)
        vertices = []
        colors = []

        for dot, weight in influences:
            dot_pixel = PoseBlendDrawHandler.grid_to_pixel(
                tuple(dot.position), grid_region, zoom, pan_center
            )
            vertices.extend([cursor_pixel, dot_pixel])

            # Color based on weight (more opaque = more influence)
            alpha = min(1.0, weight * 2)
            colors.extend([
                (1.0, 1.0, 1.0, alpha),
                (1.0, 1.0, 1.0, alpha * 0.5)
            ])

        # Draw influence lines
        # Note: For per-vertex colors, we'd need a different shader
        # For simplicity, drawing with uniform color based on strongest influence
        if vertices:
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            batch = batch_for_shader(shader, 'LINES', {"pos": vertices})

            gpu.state.blend_set('ALPHA')
            gpu.state.line_width_set(1.0)
            shader.bind()
            shader.uniform_float("color", (1.0, 1.0, 1.0, 0.3))
            batch.draw(shader)
            gpu.state.blend_set('NONE')


# ============================================================================
# Registration
# ============================================================================

def register():
    """Register drawing system"""
    # Handler will be registered when PoseBlend is activated
    pass


def unregister():
    """Unregister drawing system"""
    PoseBlendDrawHandler.unregister_handler()
