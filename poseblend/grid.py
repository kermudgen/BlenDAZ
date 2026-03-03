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

"""PoseBlend Grid - Grid coordinate math and hit testing"""

import math



# ============================================================================
# Coordinate Conversion
# ============================================================================

def pixel_to_grid(pixel_x, pixel_y, grid_region, zoom=1.0, pan_center=(0.5, 0.5)):
    """Convert pixel coordinates to dot-space grid coordinates

    With zoom=1.0 and default pan, output is 0-1 normalized.
    With zoom<1.0 (zoomed out), output can exceed 0-1.

    Args:
        pixel_x: X pixel position
        pixel_y: Y pixel position
        grid_region: Dict with 'x', 'y', 'width', 'height' of grid area in pixels
        zoom: View zoom level (1.0 = normal, <1.0 = zoomed out, >1.0 = zoomed in)
        pan_center: View center in dot-space (default (0.5, 0.5))

    Returns:
        (x, y) dot-space coordinates, or None if outside grid square
    """
    rel_x = pixel_x - grid_region['x']
    rel_y = pixel_y - grid_region['y']

    norm_x = rel_x / grid_region['width']
    norm_y = rel_y / grid_region['height']

    if 0 <= norm_x <= 1 and 0 <= norm_y <= 1:
        grid_x = (norm_x - 0.5) / zoom + pan_center[0]
        grid_y = (norm_y - 0.5) / zoom + pan_center[1]
        return (grid_x, grid_y)
    return None


def grid_to_pixel(grid_x, grid_y, grid_region):
    """Convert normalized grid coordinates to pixel coordinates

    Args:
        grid_x: Normalized X (0-1)
        grid_y: Normalized Y (0-1)
        grid_region: Dict with 'x', 'y', 'width', 'height'

    Returns:
        (pixel_x, pixel_y)
    """
    pixel_x = grid_region['x'] + grid_x * grid_region['width']
    pixel_y = grid_region['y'] + grid_y * grid_region['height']
    return (pixel_x, pixel_y)


# ============================================================================
# Snap to Grid
# ============================================================================

def snap_to_grid(position, divisions):
    """Snap a position to nearest grid intersection

    Args:
        position: (x, y) normalized position (0-1)
        divisions: (cols, rows) grid divisions

    Returns:
        (x, y) snapped position
    """
    cols, rows = divisions

    # Calculate grid cell size
    cell_width = 1.0 / cols
    cell_height = 1.0 / rows

    # Snap to nearest intersection
    snapped_x = round(position[0] / cell_width) * cell_width
    snapped_y = round(position[1] / cell_height) * cell_height

    # Clamp to bounds
    snapped_x = max(0.0, min(1.0, snapped_x))
    snapped_y = max(0.0, min(1.0, snapped_y))

    return (snapped_x, snapped_y)


def get_grid_cell(position, divisions):
    """Get which grid cell a position is in

    Args:
        position: (x, y) normalized position
        divisions: (cols, rows) grid divisions

    Returns:
        (col, row) indices (0-based)
    """
    cols, rows = divisions

    col = min(int(position[0] * cols), cols - 1)
    row = min(int(position[1] * rows), rows - 1)

    return (col, row)


# ============================================================================
# Hit Testing
# ============================================================================

def hit_test_dot(cursor_pos, dot_pos, hit_radius=0.03):
    """Test if cursor is over a dot

    Args:
        cursor_pos: (x, y) cursor position (normalized 0-1)
        dot_pos: (x, y) dot position (normalized 0-1)
        hit_radius: Hit detection radius in normalized units

    Returns:
        True if cursor is over dot
    """
    dx = cursor_pos[0] - dot_pos[0]
    dy = cursor_pos[1] - dot_pos[1]
    distance = math.sqrt(dx * dx + dy * dy)
    return distance <= hit_radius


def find_dot_at_position(cursor_pos, dots, hit_radius=0.03):
    """Find which dot (if any) is at cursor position

    Args:
        cursor_pos: (x, y) cursor position
        dots: Collection of PoseBlendDot
        hit_radius: Hit detection radius

    Returns:
        (dot, index) if found, else (None, -1)
    """
    for idx, dot in enumerate(dots):
        if hit_test_dot(cursor_pos, tuple(dot.position), hit_radius):
            return (dot, idx)
    return (None, -1)


def find_nearest_dot(cursor_pos, dots, max_distance=None):
    """Find the nearest dot to cursor

    Args:
        cursor_pos: (x, y) cursor position
        dots: Collection of PoseBlendDot
        max_distance: Optional maximum distance threshold

    Returns:
        (dot, distance, index) if found, else (None, inf, -1)
    """
    if not dots:
        return (None, float('inf'), -1)

    nearest_dot = None
    nearest_distance = float('inf')
    nearest_index = -1

    for idx, dot in enumerate(dots):
        dx = cursor_pos[0] - dot.position[0]
        dy = cursor_pos[1] - dot.position[1]
        distance = math.sqrt(dx * dx + dy * dy)

        if distance < nearest_distance:
            if max_distance is None or distance <= max_distance:
                nearest_dot = dot
                nearest_distance = distance
                nearest_index = idx

    return (nearest_dot, nearest_distance, nearest_index)


# ============================================================================
# Grid Line Generation
# ============================================================================

def generate_grid_lines(divisions, include_border=True):
    """Generate vertices for grid lines

    Args:
        divisions: (cols, rows) grid divisions
        include_border: Whether to include border lines

    Returns:
        List of ((x1, y1), (x2, y2)) line segment tuples
    """
    cols, rows = divisions
    lines = []

    # Vertical lines
    start_col = 0 if include_border else 1
    end_col = cols if include_border else cols - 1

    for i in range(start_col, end_col + 1):
        x = i / cols
        lines.append(((x, 0), (x, 1)))

    # Horizontal lines
    start_row = 0 if include_border else 1
    end_row = rows if include_border else rows - 1

    for i in range(start_row, end_row + 1):
        y = i / rows
        lines.append(((0, y), (1, y)))

    return lines


def generate_grid_intersections(divisions):
    """Generate grid intersection points (for snapping visualization)

    Args:
        divisions: (cols, rows) grid divisions

    Returns:
        List of (x, y) intersection points
    """
    cols, rows = divisions
    points = []

    for i in range(cols + 1):
        for j in range(rows + 1):
            x = i / cols
            y = j / rows
            points.append((x, y))

    return points


# ============================================================================
# Distance Utilities
# ============================================================================

def distance_2d(pos1, pos2):
    """Calculate Euclidean distance between two 2D points

    Args:
        pos1: (x, y) first point
        pos2: (x, y) second point

    Returns:
        Distance as float
    """
    dx = pos1[0] - pos2[0]
    dy = pos1[1] - pos2[1]
    return math.sqrt(dx * dx + dy * dy)


def clamp_to_grid(position):
    """Clamp position to valid grid bounds (0-1)

    Args:
        position: (x, y) position

    Returns:
        Clamped (x, y)
    """
    return (
        max(0.0, min(1.0, position[0])),
        max(0.0, min(1.0, position[1]))
    )


# ============================================================================
# Registration
# ============================================================================

def register():
    pass


def unregister():
    pass
