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

"""
BlenDAZ Register Only — N-Panel without character setup
========================================================

Run this when you have a fresh DAZ import and want the BlenDAZ N-panel
available before running full character init.

This is the entry point for the Tier 2 workflow:
  1. Import character via Diffeomorphic (your responsibility)
  2. Run THIS script → N-panel appears with BlenDAZ Setup section
  3. Click [Snapshot Pre-Merge State] before merging geografts
  4. Merge geografts in Diffeomorphic manually
  5. Click [Remap Face Groups] in the panel

Also useful any time you just want to reload modules and refresh the panel
without re-running the full setup (which requires an armature + outline).

Usage:
  1. Open this file in Blender's Text Editor
  2. Click "Run Script" (▶)
  3. Open the N-panel (press N in 3D viewport) → DAZ tab
"""

import bpy
import sys
import importlib

# ============================================================================
# Configuration
# ============================================================================

RELOAD_MODULES = True   # Force-reload modules (picks up code changes)
SKIP_POSEBLEND = False  # Set True to skip PoseBlend registration

# ============================================================================
# Path setup — add parent of BlenDAZ so package imports resolve
# ============================================================================

BLENDAZ_PARENT = r"D:\Dev"

if BLENDAZ_PARENT not in sys.path:
    sys.path.insert(0, BLENDAZ_PARENT)


# ============================================================================
# Helpers
# ============================================================================

def purge_modules(prefix):
    to_remove = [k for k in sys.modules if k.startswith(prefix)]
    for k in to_remove:
        del sys.modules[k]
    return len(to_remove)


def safe_unregister(name, mod):
    try:
        mod.unregister()
        print(f"  Unregistered {name}")
    except Exception as e:
        print(f"  Warning unregistering {name}: {e}")


# ============================================================================
# Main
# ============================================================================

print("\n" + "=" * 70)
print("  BLENDAZ REGISTER ONLY")
print("=" * 70)

# --- Step 1: daz_bone_select ---
print("\n--- Step 1: daz_bone_select ---")

# Stop any live modal instance + remove its draw handlers before unregistering.
# Without this, stale draw callbacks fire against unregistered RNA → ReferenceError spam.
if 'BlenDAZ.daz_bone_select' in sys.modules:
    try:
        from BlenDAZ import daz_bone_select as _dbs_old
        op_cls = getattr(_dbs_old, 'VIEW3D_OT_daz_bone_select', None)
        if op_cls is not None:
            # Remove tooltip draw handler
            live = getattr(op_cls, '_live_instance', None)
            if live is not None:
                h = getattr(live, '_tooltip_draw_handler', None)
                if h:
                    try:
                        bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
                    except Exception:
                        pass
                    live._tooltip_draw_handler = None
                op_cls._live_instance = None
                print("  Stopped live modal instance")
    except Exception as _e:
        print(f"  Warning stopping live instance: {_e}")

if RELOAD_MODULES and 'BlenDAZ.daz_bone_select' in sys.modules:
    try:
        from BlenDAZ import daz_bone_select
        safe_unregister('daz_bone_select', daz_bone_select)
    except Exception:
        pass
    purge_modules('BlenDAZ')
    print("  Purged all BlenDAZ modules for clean reload")
elif hasattr(bpy.ops.view3d, 'daz_bone_select'):
    try:
        from BlenDAZ import daz_bone_select
        safe_unregister('daz_bone_select', daz_bone_select)
    except Exception:
        pass

from BlenDAZ import daz_bone_select
if RELOAD_MODULES:
    importlib.reload(daz_bone_select)
daz_bone_select.register()

if hasattr(bpy.ops.view3d, 'daz_bone_select'):
    print("  OK — daz_bone_select registered")
else:
    print("  ERROR: daz_bone_select operator not found after registration!")

# --- Step 2: PoseBridge ---
print("\n--- Step 2: PoseBridge ---")

if RELOAD_MODULES and 'BlenDAZ.posebridge' in sys.modules:
    try:
        from BlenDAZ import posebridge
        safe_unregister('posebridge', posebridge)
    except Exception:
        pass
    try:
        del bpy.types.Scene.posebridge_settings
    except Exception:
        pass
    purge_modules('BlenDAZ.posebridge')
    print("  Purged cached posebridge modules")
elif hasattr(bpy.context.scene, 'posebridge_settings'):
    try:
        from BlenDAZ import posebridge
        safe_unregister('posebridge', posebridge)
    except Exception:
        pass

from BlenDAZ import posebridge
if RELOAD_MODULES:
    for sub in ['core', 'control_points', 'outline_generator',
                 'outline_generator_lineart',
                 'interaction', 'drawing', 'panel_ui', 'presets', 'init_character']:
        mod_name = f'BlenDAZ.posebridge.{sub}'
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])
    importlib.reload(posebridge)

posebridge.register()

if hasattr(bpy.context.scene, 'posebridge_settings'):
    print("  OK — PoseBridge registered (N-panel available)")
    # Register draw handler so it's ready when a character is set up later
    try:
        from BlenDAZ.posebridge.drawing import PoseBridgeDrawHandler
        if PoseBridgeDrawHandler._draw_handler is not None:
            PoseBridgeDrawHandler.unregister()
        PoseBridgeDrawHandler.register()
        print("  OK — Draw handler registered")
    except Exception as e:
        print(f"  Warning: Draw handler: {e}")
else:
    print("  ERROR: posebridge_settings not found after registration!")

# --- Step 3: PoseBlend (optional) ---
if not SKIP_POSEBLEND:
    print("\n--- Step 3: PoseBlend ---")

    if RELOAD_MODULES and 'BlenDAZ.poseblend' in sys.modules:
        try:
            from BlenDAZ import poseblend
            safe_unregister('poseblend', poseblend)
        except Exception:
            pass
        try:
            del bpy.types.Scene.poseblend_settings
        except Exception:
            pass
        purge_modules('BlenDAZ.poseblend')
        print("  Purged cached poseblend modules")
    elif hasattr(bpy.context.scene, 'poseblend_settings'):
        try:
            from BlenDAZ import poseblend
            safe_unregister('poseblend', poseblend)
        except Exception:
            pass

    try:
        from BlenDAZ import poseblend
        if RELOAD_MODULES:
            for sub in ['core', 'presets', 'poses', 'blending', 'grid',
                         'viewport_setup', 'drawing', 'interaction',
                         'panel_ui', 'import_export']:
                mod_name = f'BlenDAZ.poseblend.{sub}'
                if mod_name in sys.modules:
                    importlib.reload(sys.modules[mod_name])
            importlib.reload(poseblend)
        poseblend.register()
        if hasattr(bpy.context.scene, 'poseblend_settings'):
            print("  OK — PoseBlend registered")
        else:
            print("  ERROR: poseblend_settings not found after registration!")
    except Exception as e:
        print(f"  ERROR registering PoseBlend: {e}")
        import traceback
        traceback.print_exc()
else:
    print("\n--- Step 3: PoseBlend --- SKIPPED")

# ============================================================================
# Summary
# ============================================================================

print("\n" + "=" * 70)
print("  REGISTER COMPLETE")
print("=" * 70)
print("""
N-panel is ready. Open the DAZ tab in the N-panel (press N in 3D viewport).

Next steps (character init):
  1. Expand "BlenDAZ Setup" in the N-panel
  2. Click [Snapshot Pre-Merge State]  ← saves reference before geograft merge
  3. Merge geografts in Diffeomorphic
  4. Click [Remap Face Groups]         ← remaps face highlights to merged mesh

Or use [Auto Merge + Remap] for a one-click flow.

To start posing after init, run setup_all.py.
""")
print("=" * 70 + "\n")
