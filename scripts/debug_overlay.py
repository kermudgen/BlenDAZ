# SPDX-License-Identifier: GPL-3.0-or-later
"""
FABRIK Debug Overlay — GPU-drawn chain visualization for solver debugging.

Shows solver chain state in the viewport during drag:
- Sub-chain A (root → drag): blue
- Sub-chain B (drag → tip): orange
- Pin target: green cross
- Drag target: yellow cross
- Convergence delta: HUD text

Usage:
    1. Open in Blender Text Editor
    2. Run Script
    3. Start BlenDAZ — overlay activates automatically during FABRIK drags

To use from daz_bone_select.py, call:
    debug_overlay.update_chain(positions_a, positions_b, pin_target, drag_target, delta)
    debug_overlay.clear()

Requires Blender 4.0+ (uses gpu module, NOT bgl).
"""

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

# ---------------------------------------------------------------------------
# State — updated by the solver, drawn by the handler
# ---------------------------------------------------------------------------
_state = {
    'active': False,
    'chain_a': [],       # Sub-chain A positions (root → drag)
    'chain_b': [],       # Sub-chain B positions (drag → tip)
    'pin_target': None,
    'drag_target': None,
    'delta': 0.0,        # Convergence delta in meters
    'iteration': 0,
}

_draw_handler = None

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
COL_CHAIN_A = (0.3, 0.5, 1.0, 0.9)    # blue
COL_CHAIN_B = (1.0, 0.6, 0.2, 0.9)    # orange
COL_PIN = (0.2, 1.0, 0.3, 1.0)        # green
COL_DRAG = (1.0, 1.0, 0.2, 1.0)       # yellow
COL_JOINT_A = (0.5, 0.7, 1.0, 0.8)    # light blue
COL_JOINT_B = (1.0, 0.8, 0.4, 0.8)    # light orange

CROSS_SIZE = 0.015  # meters


# ---------------------------------------------------------------------------
# Drawing functions
# ---------------------------------------------------------------------------
def _make_cross(center, size=CROSS_SIZE):
    """Generate 6 vertices (3 line pairs) for a 3D cross marker."""
    c = Vector(center)
    return [
        c + Vector((size, 0, 0)), c - Vector((size, 0, 0)),
        c + Vector((0, size, 0)), c - Vector((0, size, 0)),
        c + Vector((0, 0, size)), c - Vector((0, 0, size)),
    ]


def _draw_chain(positions, color):
    """Draw a chain as connected line segments."""
    if len(positions) < 2:
        return
    coords = []
    for i in range(len(positions) - 1):
        coords.append(positions[i])
        coords.append(positions[i + 1])

    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'LINES', {"pos": coords})
    shader.bind()
    shader.uniform_float("color", color)
    shader.uniform_float("lineWidth", 3.0)
    # viewportSize is required by POLYLINE shaders
    region = bpy.context.region
    shader.uniform_float("viewportSize", (region.width, region.height))
    batch.draw(shader)


def _draw_cross(position, color, size=CROSS_SIZE):
    """Draw a cross marker at position."""
    if position is None:
        return
    coords = _make_cross(position, size)
    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    batch = batch_for_shader(shader, 'LINES', {"pos": coords})
    shader.bind()
    shader.uniform_float("color", color)
    shader.uniform_float("lineWidth", 2.0)
    region = bpy.context.region
    shader.uniform_float("viewportSize", (region.width, region.height))
    batch.draw(shader)


def _draw_joints(positions, color):
    """Draw small crosses at each joint position."""
    for pos in positions:
        _draw_cross(pos, color, CROSS_SIZE * 0.6)


def _draw_callback():
    """Main draw callback — registered on SpaceView3D."""
    if not _state['active']:
        return

    # Draw through mesh (x-ray)
    gpu.state.depth_test_set('NONE')
    gpu.state.blend_set('ALPHA')

    try:
        # Sub-chains
        _draw_chain(_state['chain_a'], COL_CHAIN_A)
        _draw_chain(_state['chain_b'], COL_CHAIN_B)

        # Joint markers
        _draw_joints(_state['chain_a'], COL_JOINT_A)
        _draw_joints(_state['chain_b'], COL_JOINT_B)

        # Target markers
        _draw_cross(_state['pin_target'], COL_PIN, CROSS_SIZE * 1.5)
        _draw_cross(_state['drag_target'], COL_DRAG, CROSS_SIZE * 1.5)

    finally:
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.blend_set('NONE')


# ---------------------------------------------------------------------------
# Public API — call from daz_bone_select.py
# ---------------------------------------------------------------------------
def update_chain(chain_a=None, chain_b=None, pin_target=None,
                 drag_target=None, delta=0.0, iteration=0):
    """Update the debug overlay with current solver state.

    Args:
        chain_a: List of Vector positions for sub-chain A (root → drag)
        chain_b: List of Vector positions for sub-chain B (drag → tip)
        pin_target: Vector position of the pin target
        drag_target: Vector position of the drag target
        delta: Convergence delta in meters
        iteration: Current solver iteration
    """
    _state['active'] = True
    if chain_a is not None:
        _state['chain_a'] = [Vector(v) for v in chain_a]
    if chain_b is not None:
        _state['chain_b'] = [Vector(v) for v in chain_b]
    _state['pin_target'] = Vector(pin_target) if pin_target else None
    _state['drag_target'] = Vector(drag_target) if drag_target else None
    _state['delta'] = delta
    _state['iteration'] = iteration

    # Force viewport redraw
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


def clear():
    """Clear the debug overlay."""
    _state['active'] = False
    _state['chain_a'] = []
    _state['chain_b'] = []
    _state['pin_target'] = None
    _state['drag_target'] = None
    _state['delta'] = 0.0
    _state['iteration'] = 0

    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


def register():
    """Register the draw handler."""
    global _draw_handler
    if _draw_handler is not None:
        return  # already registered
    _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
        _draw_callback, (), 'WINDOW', 'POST_VIEW'
    )
    print("FABRIK debug overlay: registered")


def unregister():
    """Remove the draw handler."""
    global _draw_handler
    if _draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = None
        print("FABRIK debug overlay: unregistered")


# ---------------------------------------------------------------------------
# Auto-register when run as a script in Blender
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Clean up any existing handler
    unregister()
    register()
    print("\nFABRIK Debug Overlay active.")
    print("Call debug_overlay.update_chain(...) from solver code to visualize.")
    print("Call debug_overlay.clear() to hide.")
    print("Call debug_overlay.unregister() to remove.\n")
