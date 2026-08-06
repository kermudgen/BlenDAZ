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

"""BlenDAZ - Visual posing tools for DAZ characters in Blender"""

import logging

bl_info = {
    "name": "BlenDAZ",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "description": "Visual posing tools for DAZ Genesis 8/9 characters",
    "category": "Rigging",
}

# Logging — silent by default (WARNING+), enable verbose via addon prefs
_log = logging.getLogger("BlenDAZ")
if not _log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    _log.addHandler(_handler)
_log.setLevel(logging.WARNING)

from . import daz_bone_select
from . import panel_ui
from . import posebridge
from . import poseblend


def register():
    daz_bone_select.register()
    panel_ui.register()
    posebridge.register()
    poseblend.register()


def unregister():
    poseblend.unregister()
    posebridge.unregister()
    panel_ui.unregister()
    daz_bone_select.unregister()
