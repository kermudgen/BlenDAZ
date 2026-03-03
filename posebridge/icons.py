# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joshua D Rother
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""PoseBridge Icons - Custom GPU-drawn shapes for view switching"""

import gpu
from gpu_extras.batch import batch_for_shader
import math


# ============================================================================
# Icon Shape Definitions
# ============================================================================
# All shapes defined in normalized coordinates (0-1 range)
# Drawing functions scale to desired pixel size

# Body icon - simple stick figure silhouette
ICON_BODY = {
    'name': 'body',
    'lines': [
        # Head (circle approximation - 8 points)
        # Will be drawn separately as circle
    ],
    'head_center': (0.5, 0.85),
    'head_radius': 0.12,
    'body_lines': [
        # Spine
        ((0.5, 0.73), (0.5, 0.35)),
        # Shoulders
        ((0.25, 0.65), (0.75, 0.65)),
        # Left arm
        ((0.25, 0.65), (0.15, 0.45)),
        # Right arm
        ((0.75, 0.65), (0.85, 0.45)),
        # Hips
        ((0.35, 0.35), (0.65, 0.35)),
        # Left leg
        ((0.35, 0.35), (0.30, 0.05)),
        # Right leg
        ((0.65, 0.35), (0.70, 0.05)),
    ],
}

# Hand icon - simplified hand silhouette
# TODO: User to define custom vertices
ICON_HAND = {
    'name': 'hand',
    'outline': [
        # Palm base
        (0.2, 0.0),
        (0.8, 0.0),
        # Palm right side
        (0.85, 0.3),
        # Pinky
        (0.85, 0.5), (0.80, 0.55), (0.75, 0.5),
        # Ring
        (0.75, 0.65), (0.68, 0.72), (0.62, 0.65),
        # Middle
        (0.62, 0.78), (0.52, 0.85), (0.45, 0.78),
        # Index
        (0.45, 0.70), (0.38, 0.75), (0.32, 0.68),
        # Thumb
        (0.25, 0.55), (0.12, 0.50), (0.10, 0.35),
        # Palm left side
        (0.15, 0.15),
        # Close
        (0.2, 0.0),
    ],
}

# Head icon - simple head/face silhouette
# TODO: User to define custom vertices
ICON_HEAD = {
    'name': 'head',
    'outline': [
        # Oval head shape (simplified)
        (0.5, 0.0),   # Chin
        (0.25, 0.15),
        (0.15, 0.4),
        (0.2, 0.7),
        (0.35, 0.9),
        (0.5, 0.95),  # Top of head
        (0.65, 0.9),
        (0.8, 0.7),
        (0.85, 0.4),
        (0.75, 0.15),
        (0.5, 0.0),   # Back to chin
    ],
    # Optional: ear bumps, etc.
}


# ============================================================================
# Drawing Functions
# ============================================================================

def draw_icon_outline(icon_data, position, size, color, line_width=2.0):
    """
    Draw an icon outline at the specified position.

    Args:
        icon_data: Dict with 'outline' key containing vertex list
        position: (x, y) center position in pixels
        size: Size in pixels (width and height)
        color: (r, g, b, a) color tuple
        line_width: Line width in pixels
    """
    if 'outline' not in icon_data:
        return

    outline = icon_data['outline']
    half_size = size / 2

    # Transform normalized coords to screen coords
    vertices = []
    for vx, vy in outline:
        x = position[0] + (vx - 0.5) * size
        y = position[1] + (vy - 0.5) * size
        vertices.append((x, y))

    # Draw
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": vertices})

    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(line_width)

    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')


def draw_icon_filled(icon_data, position, size, color):
    """
    Draw a filled icon at the specified position.

    Args:
        icon_data: Dict with 'outline' key containing vertex list
        position: (x, y) center position in pixels
        size: Size in pixels
        color: (r, g, b, a) color tuple
    """
    if 'outline' not in icon_data:
        return

    outline = icon_data['outline']
    half_size = size / 2

    # Transform normalized coords to screen coords
    vertices = [position]  # Center for triangle fan
    for vx, vy in outline:
        x = position[0] + (vx - 0.5) * size
        y = position[1] + (vy - 0.5) * size
        vertices.append((x, y))

    # Draw filled using triangle fan
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices})

    gpu.state.blend_set('ALPHA')

    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    gpu.state.blend_set('NONE')


def draw_body_icon(position, size, color, line_width=2.0):
    """
    Draw the body stick figure icon.

    Args:
        position: (x, y) center position in pixels
        size: Size in pixels
        color: (r, g, b, a) color tuple
        line_width: Line width in pixels
    """
    half_size = size / 2

    # Draw head circle
    head_cx = position[0] + (ICON_BODY['head_center'][0] - 0.5) * size
    head_cy = position[1] + (ICON_BODY['head_center'][1] - 0.5) * size
    head_radius = ICON_BODY['head_radius'] * size

    # Head circle vertices
    segments = 16
    head_verts = []
    for i in range(segments + 1):
        angle = 2.0 * math.pi * i / segments
        x = head_cx + head_radius * math.cos(angle)
        y = head_cy + head_radius * math.sin(angle)
        head_verts.append((x, y))

    # Body line vertices
    body_verts = []
    for (x1, y1), (x2, y2) in ICON_BODY['body_lines']:
        px1 = position[0] + (x1 - 0.5) * size
        py1 = position[1] + (y1 - 0.5) * size
        px2 = position[0] + (x2 - 0.5) * size
        py2 = position[1] + (y2 - 0.5) * size
        body_verts.extend([(px1, py1), (px2, py2)])

    # Draw
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(line_width)

    shader.bind()
    shader.uniform_float("color", color)

    # Draw head
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": head_verts})
    batch.draw(shader)

    # Draw body lines
    batch = batch_for_shader(shader, 'LINES', {"pos": body_verts})
    batch.draw(shader)

    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')


# ============================================================================
# View Switcher Icons
# ============================================================================

class ViewSwitcherIcons:
    """Manages view switching icons in viewport corner"""

    # Icon positions (will be calculated relative to viewport)
    ICON_SIZE = 40  # pixels
    ICON_SPACING = 10  # pixels between icons
    MARGIN = 20  # pixels from viewport edge

    @classmethod
    def get_icon_positions(cls, region):
        """
        Calculate icon positions for bottom-left corner of viewport.

        Returns:
            Dict mapping view name to (x, y) center position
        """
        x_start = cls.MARGIN + cls.ICON_SIZE / 2
        y = cls.MARGIN + cls.ICON_SIZE / 2

        return {
            'body': (x_start, y),
            'hands': (x_start + cls.ICON_SIZE + cls.ICON_SPACING, y),
            'face': (x_start + 2 * (cls.ICON_SIZE + cls.ICON_SPACING), y),
        }

    @classmethod
    def draw_all(cls, context, active_panel):
        """
        Draw all view switcher icons.

        Args:
            context: Blender context
            active_panel: Currently active panel ('body', 'hands', 'face')
        """
        region = context.region
        positions = cls.get_icon_positions(region)

        # Colors
        color_active = (0.0, 0.8, 1.0, 1.0)    # Cyan for active
        color_inactive = (0.5, 0.5, 0.5, 0.8)  # Gray for inactive
        color_hover = (1.0, 1.0, 0.0, 1.0)     # Yellow for hover

        # Draw each icon
        for view_name, pos in positions.items():
            is_active = (view_name == active_panel)
            color = color_active if is_active else color_inactive

            if view_name == 'body':
                draw_body_icon(pos, cls.ICON_SIZE, color, line_width=2.5 if is_active else 2.0)
            elif view_name == 'hands':
                draw_icon_outline(ICON_HAND, pos, cls.ICON_SIZE, color, line_width=2.5 if is_active else 2.0)
            elif view_name == 'face':
                draw_icon_outline(ICON_HEAD, pos, cls.ICON_SIZE, color, line_width=2.5 if is_active else 2.0)

    @classmethod
    def hit_test(cls, mouse_x, mouse_y, region):
        """
        Check if mouse is over any icon.

        Returns:
            View name ('body', 'hands', 'face') or None
        """
        positions = cls.get_icon_positions(region)
        hit_radius = cls.ICON_SIZE / 2

        for view_name, (cx, cy) in positions.items():
            dist = ((mouse_x - cx) ** 2 + (mouse_y - cy) ** 2) ** 0.5
            if dist <= hit_radius:
                return view_name

        return None
