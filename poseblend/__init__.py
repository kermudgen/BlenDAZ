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

"""PoseBlend - DAZ Puppeteer-style pose blending system for Blender

A 2D grid interface for saving, organizing, and blending poses.
Place dots on a grid, drag cursor to blend between poses in real-time.
"""

import bpy

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

import logging
log = logging.getLogger(__name__)


bl_info = {
    "name": "PoseBlend",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
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
    log.info("PoseBlend registered")


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
    log.info("PoseBlend unregistered")


if __name__ == "__main__":
    register()
