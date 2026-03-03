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

"""PoseBridge - Visual posing editor for Blender

A DAZ Studio-style posing tool using Grease Pencil outlines with interactive control points.
"""

import bpy

from . import core
from . import control_points
from . import interaction
from . import drawing
from . import panel_ui
from . import presets
from . import outline_generator
from . import init_character

import logging
log = logging.getLogger(__name__)


bl_info = {
    "name": "PoseBridge Editor",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
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
    log.info("PoseBridge Editor registered")

def unregister():
    """Unregister PoseBridge addon"""
    panel_ui.unregister()
    init_character.unregister()
    drawing.unregister()
    interaction.unregister()
    outline_generator.unregister()
    core.unregister()
    log.info("PoseBridge Editor unregistered")

if __name__ == "__main__":
    register()
