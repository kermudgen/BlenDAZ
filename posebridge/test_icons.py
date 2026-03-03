# Test script: Preview PoseBridge icons in any scene
# Run in Blender Text Editor - works in blank scene
#
# Press ESC to stop the test and remove the overlay

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
import math

# ============================================================================
# Icon Definitions (copy from icons.py for standalone testing)
# ============================================================================

ICON_BODY = {
    'name': 'body',
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

# Simple hand outline - customize these vertices!
ICON_HAND = {
    'name': 'hand',
    'outline': [
        # Palm base
        (0.2, 0.05),
        (0.8, 0.05),
        # Palm right edge
        (0.82, 0.35),
        # Pinky
        (0.82, 0.50), (0.78, 0.58), (0.72, 0.50),
        # Ring
        (0.72, 0.68), (0.65, 0.78), (0.58, 0.68),
        # Middle
        (0.58, 0.80), (0.50, 0.92), (0.42, 0.80),
        # Index
        (0.42, 0.72), (0.35, 0.80), (0.28, 0.68),
        # Thumb
        (0.22, 0.55), (0.08, 0.48), (0.10, 0.30),
        # Palm left edge
        (0.18, 0.15),
        # Close back to start
        (0.2, 0.05),
    ],
}

# Simple head outline - customize these vertices!
ICON_HEAD = {
    'name': 'head',
    'outline': [
        # Start at chin
        (0.50, 0.08),
        # Jaw right
        (0.65, 0.15),
        (0.78, 0.30),
        # Ear area right
        (0.82, 0.45),
        (0.80, 0.60),
        # Forehead right
        (0.72, 0.80),
        (0.60, 0.92),
        # Top of head
        (0.50, 0.95),
        # Forehead left
        (0.40, 0.92),
        (0.28, 0.80),
        # Ear area left
        (0.20, 0.60),
        (0.18, 0.45),
        # Jaw left
        (0.22, 0.30),
        (0.35, 0.15),
        # Back to chin
        (0.50, 0.08),
    ],
}


# ============================================================================
# Drawing Functions
# ============================================================================

def draw_icon_outline(icon_data, position, size, color, line_width=2.0):
    """Draw an icon outline."""
    if 'outline' not in icon_data:
        return

    outline = icon_data['outline']

    # Transform normalized coords to screen coords
    vertices = []
    for vx, vy in outline:
        x = position[0] + (vx - 0.5) * size
        y = position[1] + (vy - 0.5) * size
        vertices.append((x, y))

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": vertices})

    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(line_width)

    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)

    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')


def draw_body_icon(position, size, color, line_width=2.0):
    """Draw the body stick figure icon."""
    # Draw head circle
    head_cx = position[0] + (ICON_BODY['head_center'][0] - 0.5) * size
    head_cy = position[1] + (ICON_BODY['head_center'][1] - 0.5) * size
    head_radius = ICON_BODY['head_radius'] * size

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


def draw_background_box(position, size, color):
    """Draw a rounded rectangle background."""
    padding = 8
    x1 = position[0] - size/2 - padding
    y1 = position[1] - size/2 - padding
    x2 = position[0] + size/2 + padding
    y2 = position[1] + size/2 + padding

    vertices = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'TRI_FAN', {"pos": [(position[0], position[1])] + vertices + [vertices[0]]})

    gpu.state.blend_set('ALPHA')
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.blend_set('NONE')


# ============================================================================
# Test Draw Handler
# ============================================================================

_draw_handler = None
_active_icon = 'body'  # Track which icon is "active" for demo

def draw_test_icons():
    """Draw all test icons in bottom-left corner."""
    global _active_icon

    # Icon settings
    icon_size = 50
    spacing = 15
    margin = 30

    # Calculate positions
    positions = {
        'body': (margin + icon_size/2, margin + icon_size/2),
        'hands': (margin + icon_size/2 + icon_size + spacing, margin + icon_size/2),
        'face': (margin + icon_size/2 + 2*(icon_size + spacing), margin + icon_size/2),
    }

    # Colors
    color_active = (0.0, 0.8, 1.0, 1.0)      # Cyan
    color_inactive = (0.6, 0.6, 0.6, 0.9)    # Light gray
    bg_active = (0.2, 0.2, 0.2, 0.8)         # Dark background
    bg_inactive = (0.15, 0.15, 0.15, 0.6)    # Darker background

    # Draw each icon
    for name, pos in positions.items():
        is_active = (name == _active_icon)
        color = color_active if is_active else color_inactive
        bg_color = bg_active if is_active else bg_inactive
        line_width = 3.0 if is_active else 2.0

        # Draw background
        draw_background_box(pos, icon_size, bg_color)

        # Draw icon
        if name == 'body':
            draw_body_icon(pos, icon_size, color, line_width)
        elif name == 'hands':
            draw_icon_outline(ICON_HAND, pos, icon_size, color, line_width)
        elif name == 'face':
            draw_icon_outline(ICON_HEAD, pos, icon_size, color, line_width)

    # Draw label
    # (Note: GPU text rendering is complex, skipping for now)


def register_test_handler():
    """Register the test draw handler."""
    global _draw_handler
    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            draw_test_icons,
            (),
            'WINDOW',
            'POST_PIXEL'
        )
        print("Icon test handler registered - look in bottom-left of 3D viewport")
        print("Press ESC while hovering over viewport to stop")


def unregister_test_handler():
    """Remove the test draw handler."""
    global _draw_handler
    if _draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = None
        print("Icon test handler removed")


# ============================================================================
# Modal Operator for interaction
# ============================================================================

class POSEBRIDGE_OT_test_icons(bpy.types.Operator):
    """Test PoseBridge view switcher icons"""
    bl_idname = "posebridge.test_icons"
    bl_label = "Test PoseBridge Icons"

    def modal(self, context, event):
        global _active_icon

        # Redraw on mouse move
        if event.type == 'MOUSEMOVE':
            context.area.tag_redraw()

            # Simple hit test
            icon_size = 50
            spacing = 15
            margin = 30
            positions = {
                'body': (margin + icon_size/2, margin + icon_size/2),
                'hands': (margin + icon_size/2 + icon_size + spacing, margin + icon_size/2),
                'face': (margin + icon_size/2 + 2*(icon_size + spacing), margin + icon_size/2),
            }

            # Check hover
            for name, (cx, cy) in positions.items():
                dist = ((event.mouse_region_x - cx)**2 + (event.mouse_region_y - cy)**2)**0.5
                if dist < icon_size/2 + 8:
                    _active_icon = name
                    break

        # Click to cycle through icons (for testing)
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            icons = ['body', 'hands', 'face']
            idx = icons.index(_active_icon)
            _active_icon = icons[(idx + 1) % 3]
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        # ESC to exit
        if event.type == 'ESC':
            unregister_test_handler()
            context.area.tag_redraw()
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        register_test_handler()
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


# ============================================================================
# Registration
# ============================================================================

def register():
    bpy.utils.register_class(POSEBRIDGE_OT_test_icons)

def unregister():
    unregister_test_handler()
    bpy.utils.unregister_class(POSEBRIDGE_OT_test_icons)


# Run immediately when script is executed
if __name__ == "__main__":
    # Clean up any existing registration
    try:
        unregister()
    except:
        pass

    register()

    # Start the test
    bpy.ops.posebridge.test_icons('INVOKE_DEFAULT')

    print("\n" + "="*50)
    print("ICON TEST RUNNING")
    print("="*50)
    print("- Icons visible in bottom-left of 3D viewport")
    print("- Hover over icons to highlight")
    print("- Click to cycle active icon")
    print("- Press ESC to stop test")
    print("="*50)
