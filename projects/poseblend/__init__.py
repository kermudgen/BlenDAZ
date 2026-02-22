"""PoseBlend - DAZ Puppeteer-style pose blending system for Blender

A 2D grid interface for saving, organizing, and blending poses.
Place dots on a grid, drag cursor to blend between poses in real-time.
"""

import bpy
import sys
import os

# Add parent directory to path for shared utilities
addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

from . import core
from . import poses
from . import blending
from . import grid
from . import interaction
from . import drawing
from . import panel_ui
from . import viewport_setup
from . import import_export
from . import presets

bl_info = {
    "name": "PoseBlend",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "description": "DAZ Puppeteer-style pose blending with 2D grid interface",
    "category": "Rigging",
}


def register():
    """Register PoseBlend addon"""
    core.register()
    presets.register()
    poses.register()
    blending.register()
    grid.register()
    viewport_setup.register()
    drawing.register()
    interaction.register()
    panel_ui.register()
    import_export.register()
    print("PoseBlend registered")


def unregister():
    """Unregister PoseBlend addon"""
    import_export.unregister()
    panel_ui.unregister()
    interaction.unregister()
    drawing.unregister()
    viewport_setup.unregister()
    grid.unregister()
    blending.unregister()
    poses.unregister()
    presets.unregister()
    core.unregister()
    print("PoseBlend unregistered")


if __name__ == "__main__":
    register()
