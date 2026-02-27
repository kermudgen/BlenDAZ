"""PoseBridge - Visual posing editor for Blender

A DAZ Studio-style posing tool using Grease Pencil outlines with interactive control points.
"""

import bpy
import sys
import os

# Add parent directory to path for shared utilities
addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

from . import core
from . import control_points
from . import interaction
from . import drawing
from . import panel_ui
from . import presets
from . import outline_generator
from . import init_character

bl_info = {
    "name": "PoseBridge Editor",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "description": "Visual posing tool with Grease Pencil outlines and control points",
    "category": "Rigging",
}

def register():
    """Register PoseBridge addon"""
    core.register()
    outline_generator.register()
    interaction.register()
    drawing.register()
    init_character.register()
    panel_ui.register()
    print("PoseBridge Editor registered")

def unregister():
    """Unregister PoseBridge addon"""
    panel_ui.unregister()
    init_character.unregister()
    drawing.unregister()
    interaction.unregister()
    outline_generator.unregister()
    core.unregister()
    print("PoseBridge Editor unregistered")

if __name__ == "__main__":
    register()
