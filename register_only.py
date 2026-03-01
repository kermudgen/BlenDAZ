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
# Path setup
# ============================================================================

BLENDAZ_ROOT   = r"D:\Dev\BlenDAZ"
PROJECTS_DIR   = r"D:\Dev\BlenDAZ\projects"
POSEBRIDGE_DIR = r"D:\Dev\BlenDAZ\projects\posebridge"

for p in [BLENDAZ_ROOT, PROJECTS_DIR, POSEBRIDGE_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)


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
if 'daz_bone_select' in sys.modules:
    try:
        import daz_bone_select as _dbs_old
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

if RELOAD_MODULES and 'daz_bone_select' in sys.modules:
    try:
        import daz_bone_select
        safe_unregister('daz_bone_select', daz_bone_select)
    except Exception:
        pass
    del sys.modules['daz_bone_select']
    if 'daz_shared_utils' in sys.modules:
        importlib.reload(sys.modules['daz_shared_utils'])
        print("  Reloaded daz_shared_utils")
elif hasattr(bpy.ops.view3d, 'daz_bone_select'):
    try:
        import daz_bone_select
        safe_unregister('daz_bone_select', daz_bone_select)
    except Exception:
        pass

import daz_bone_select
if RELOAD_MODULES:
    importlib.reload(daz_bone_select)
daz_bone_select.register()

if hasattr(bpy.ops.view3d, 'daz_bone_select'):
    print("  OK — daz_bone_select registered")
else:
    print("  ERROR: daz_bone_select operator not found after registration!")

# --- Step 2: PoseBridge ---
print("\n--- Step 2: PoseBridge ---")

if RELOAD_MODULES and 'posebridge' in sys.modules:
    try:
        import posebridge
        safe_unregister('posebridge', posebridge)
    except Exception:
        pass
    try:
        del bpy.types.Scene.posebridge_settings
    except Exception:
        pass
    purge_modules('posebridge')
    print("  Purged cached posebridge modules")
elif hasattr(bpy.context.scene, 'posebridge_settings'):
    try:
        import posebridge
        safe_unregister('posebridge', posebridge)
    except Exception:
        pass

import posebridge
if RELOAD_MODULES:
    for sub in ['core', 'control_points', 'outline_generator',
                 'outline_generator_lineart',
                 'interaction', 'drawing', 'panel_ui', 'presets', 'init_character']:
        mod_name = f'posebridge.{sub}'
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])
    importlib.reload(posebridge)

posebridge.register()

if hasattr(bpy.context.scene, 'posebridge_settings'):
    print("  OK — PoseBridge registered (N-panel available)")
    # Register draw handler so it's ready when a character is set up later
    try:
        from posebridge.drawing import PoseBridgeDrawHandler
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

    if RELOAD_MODULES and 'poseblend' in sys.modules:
        try:
            import poseblend
            safe_unregister('poseblend', poseblend)
        except Exception:
            pass
        try:
            del bpy.types.Scene.poseblend_settings
        except Exception:
            pass
        purge_modules('poseblend')
        print("  Purged cached poseblend modules")
    elif hasattr(bpy.context.scene, 'poseblend_settings'):
        try:
            import poseblend
            safe_unregister('poseblend', poseblend)
        except Exception:
            pass

    try:
        import poseblend
        if RELOAD_MODULES:
            for sub in ['core', 'presets', 'poses', 'blending', 'grid',
                         'viewport_setup', 'drawing', 'interaction',
                         'panel_ui', 'import_export']:
                mod_name = f'poseblend.{sub}'
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
