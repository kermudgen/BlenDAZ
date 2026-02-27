"""
BlenDAZ Full Setup — Register & Start Everything
=================================================

Run in Blender's Text Editor to set up the complete BlenDAZ ecosystem:
  1. daz_bone_select (bone selection, IK, pins, PowerPose)
  2. PoseBridge (visual posing with control points + outlines)
  3. PoseBlend (DAZ Puppeteer-style pose blending)

Prerequisites:
  - Genesis 8/9 character imported via Diffeomorphic
  - Armature selected (or auto-detected)

Usage:
  1. Open this file in Blender's Text Editor
  2. Click "Run Script" (▶)
  3. Hover/click bones in the 3D viewport to start posing

Configuration:
  Set ARMATURE_NAME below to override auto-detection.
  Set SKIP_POSEBRIDGE / SKIP_POSEBLEND to True to skip those modules.
"""

import bpy
import sys
import importlib

# ============================================================================
# Configuration
# ============================================================================

ARMATURE_NAME = None          # Auto-detect if None, or set e.g. "Genesis8Female"
SKIP_POSEBRIDGE = False       # Set True to skip PoseBridge registration
SKIP_POSEBLEND = False        # Set True to skip PoseBlend registration
RELOAD_MODULES = True         # Force-reload modules (picks up code changes)

# PoseBridge extras (only if not skipping)
STANDIN_NAME = None           # Auto-detect standin mesh, or set e.g. "Fey Mesh_Standin"
OUTLINE_Z_OFFSET = -50.0     # Z offset for outline/camera/control points (meters below character)
HAND_Z_OFFSET = -53.0        # Z offset for hand camera
GENERATE_OUTLINE = True       # Generate Line Art outline if it doesn't exist
FORCE_REGENERATE_OUTLINE = False  # Delete existing outline and regenerate from scratch
SETUP_HANDS = True            # Extract hand geometry + control points
SETUP_FACE = True             # Extract face control points

# ============================================================================
# Path setup
# ============================================================================

BLENDAZ_ROOT = r"D:\Dev\BlenDAZ"
PROJECTS_DIR = r"D:\Dev\BlenDAZ\projects"
POSEBRIDGE_DIR = r"D:\Dev\BlenDAZ\projects\posebridge"

for p in [BLENDAZ_ROOT, PROJECTS_DIR, POSEBRIDGE_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ============================================================================
# Helpers
# ============================================================================

def find_daz_armature():
    """Find a DAZ Genesis armature in the scene."""
    daz_markers = {'lPectoral', 'rPectoral', 'lCollar', 'rCollar'}

    # Check active object first
    obj = bpy.context.active_object
    if obj and obj.type == 'ARMATURE':
        bone_names = {b.name for b in obj.data.bones}
        if daz_markers & bone_names:
            return obj.name

    # Search all armatures
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            bone_names = {b.name for b in obj.data.bones}
            if daz_markers & bone_names:
                return obj.name
    return None


def find_standin_mesh(armature_name):
    """Try to find a standin mesh for the armature."""
    # Common naming patterns
    candidates = []
    if armature_name:
        # Look for mesh objects that might be related to the armature
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                name = obj.name
                if '_Standin' in name or '_LineArt_Copy' in name:
                    candidates.append(name)
    # Also try common names
    for name in ["Fey Mesh_Standin", "Fey Mesh_LineArt_Copy", "Fey Mesh"]:
        if name in bpy.data.objects:
            candidates.append(name)

    return candidates[0] if candidates else None


def find_character_mesh(armature_name):
    """Find the main character body mesh for the armature.

    Selection priority:
      1. Mesh named exactly '{armature_name} Mesh' (DAZ convention)
      2. Mesh whose name starts with armature name (e.g. 'Fey Body')
      3. Largest mesh by vertex count (fallback)
    """
    armature = bpy.data.objects.get(armature_name)
    if not armature:
        return None

    # Collect candidate meshes — children of armature, excluding standin/copies
    candidates = []
    skip_suffixes = ('_Standin', '_LineArt_Copy', '_LineArt')

    for child in armature.children:
        if child.type == 'MESH' and not child.name.endswith(skip_suffixes):
            candidates.append(child)

    # Fallback: search meshes with armature modifier pointing to this armature
    if not candidates:
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and not obj.name.endswith(skip_suffixes):
                for mod in obj.modifiers:
                    if mod.type == 'ARMATURE' and mod.object and mod.object.name == armature_name:
                        candidates.append(obj)
                        break

    if not candidates:
        return None

    # Priority 1: Exact DAZ naming convention "{ArmatureName} Mesh"
    exact_name = f"{armature_name} Mesh"
    for obj in candidates:
        if obj.name == exact_name:
            return obj.name

    # Priority 2: Name starts with armature name (e.g. "Fey Body", "Fey Base")
    for obj in candidates:
        if obj.name.startswith(armature_name):
            return obj.name

    # Priority 3: Largest mesh by vertex count (fallback)
    best = max(candidates, key=lambda obj: len(obj.data.vertices))
    return best.name


def purge_modules(prefix):
    """Remove all cached modules starting with prefix."""
    to_remove = [k for k in sys.modules if k.startswith(prefix)]
    for k in to_remove:
        del sys.modules[k]
    return len(to_remove)


def safe_unregister(module_name, module_ref):
    """Unregister a module safely, ignoring errors."""
    try:
        module_ref.unregister()
        print(f"  Unregistered {module_name}")
        return True
    except Exception as e:
        print(f"  Warning unregistering {module_name}: {e}")
        return False


def find_3d_view():
    """Find a 3D viewport area for operator invocation."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                return window, area
    return None, None


# ============================================================================
# Main setup
# ============================================================================

print("\n" + "=" * 70)
print("  BLENDAZ FULL SETUP")
print("=" * 70)

# --- Auto-detect armature ---
armature_name = ARMATURE_NAME or find_daz_armature()
if not armature_name:
    print("\nERROR: No DAZ armature found!")
    print("  Select an armature or set ARMATURE_NAME in the script.")
    print("=" * 70)
    raise RuntimeError("No DAZ armature found")

armature_obj = bpy.data.objects.get(armature_name)
print(f"\nArmature: {armature_name}")

# Generate character tag for multi-character object naming
import re
char_tag = re.sub(r'[^A-Za-z0-9_]', '_', armature_name)
char_tag = re.sub(r'_+', '_', char_tag).strip('_')
print(f"Character tag: {char_tag}")

# --- Ensure pose mode ---
if armature_obj:
    bpy.context.view_layer.objects.active = armature_obj
    armature_obj.select_set(True)
    if bpy.context.mode != 'POSE':
        bpy.ops.object.mode_set(mode='POSE')
        print("Switched to Pose mode")

# ============================================================================
# Step 1: daz_bone_select
# ============================================================================

print(f"\n--- Step 1: daz_bone_select ---")

# Stop any live modal instance + remove its draw handlers before unregistering.
if 'daz_bone_select' in sys.modules:
    try:
        import daz_bone_select as _dbs_old
        op_cls = getattr(_dbs_old, 'VIEW3D_OT_daz_bone_select', None)
        if op_cls is not None:
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
        daz_bone_select.unregister()
    except:
        pass
    del sys.modules['daz_bone_select']
    # Also reload shared utils
    if 'daz_shared_utils' in sys.modules:
        importlib.reload(sys.modules['daz_shared_utils'])
        print("  Reloaded daz_shared_utils")
elif hasattr(bpy.ops.view3d, 'daz_bone_select'):
    try:
        import daz_bone_select
        daz_bone_select.unregister()
    except:
        pass

import daz_bone_select
if RELOAD_MODULES:
    importlib.reload(daz_bone_select)
daz_bone_select.register()

if hasattr(bpy.ops.view3d, 'daz_bone_select'):
    print("  OK — daz_bone_select registered (bone select, IK, pins, PowerPose)")
else:
    print("  ERROR: daz_bone_select operator not found after registration!")
    raise RuntimeError("daz_bone_select registration failed")

# ============================================================================
# Step 2: PoseBridge
# ============================================================================

pb_settings = None

if not SKIP_POSEBRIDGE:
    print(f"\n--- Step 2: PoseBridge ---")

    # Unregister + purge if reloading
    if RELOAD_MODULES and 'posebridge' in sys.modules:
        try:
            import posebridge
            safe_unregister('posebridge', posebridge)
        except:
            pass
        # Force-delete scene property if it lingers
        try:
            del bpy.types.Scene.posebridge_settings
        except:
            pass
        purge_modules('posebridge')
        print("  Purged cached posebridge modules")
    elif hasattr(bpy.context.scene, 'posebridge_settings'):
        try:
            import posebridge
            safe_unregister('posebridge', posebridge)
        except:
            pass

    # Fresh import + register
    import posebridge
    if RELOAD_MODULES:
        # Reload submodules in dependency order
        for sub in ['core', 'control_points', 'outline_generator',
                     'interaction', 'drawing', 'panel_ui', 'presets', 'init_character']:
            mod_name = f'posebridge.{sub}'
            if mod_name in sys.modules:
                importlib.reload(sys.modules[mod_name])
        importlib.reload(posebridge)

    posebridge.register()

    if hasattr(bpy.context.scene, 'posebridge_settings'):
        pb_settings = bpy.context.scene.posebridge_settings
        pb_settings.is_active = True
        pb_settings.active_armature_name = armature_name
        pb_settings.show_control_points = True
        print("  OK — PoseBridge registered and enabled")
    else:
        print("  ERROR: posebridge_settings not found after registration!")

    # Register draw handler
    try:
        from posebridge.drawing import PoseBridgeDrawHandler
        if PoseBridgeDrawHandler._draw_handler is not None:
            PoseBridgeDrawHandler.unregister()
        PoseBridgeDrawHandler.register()
        print("  OK — Draw handler registered")
    except Exception as e:
        print(f"  Warning: Draw handler issue: {e}")

    # --- Generate outline if needed, then capture body control points ---
    if pb_settings and armature_obj:
        outline_name = f"PB_Outline_{char_tag}"
        camera_name = f"PB_Camera_Body_{char_tag}"
        light_name = f"PB_Light_{char_tag}"

        # Reload outline generator module
        if RELOAD_MODULES:
            mod = 'posebridge.outline_generator_lineart'
            if mod in sys.modules:
                importlib.reload(sys.modules[mod])

        from posebridge.outline_generator_lineart import capture_fixed_control_points

        # Force-regenerate: delete existing outline objects so they get recreated
        if FORCE_REGENERATE_OUTLINE:
            for obj_name in [outline_name, camera_name, light_name]:
                obj = bpy.data.objects.get(obj_name)
                if obj:
                    bpy.data.objects.remove(obj, do_unlink=True)
            # Also remove mesh copy from previous generation
            for obj in list(bpy.data.objects):
                if obj.name.endswith('_LineArt_Copy'):
                    bpy.data.objects.remove(obj, do_unlink=True)
            # Remove temp collection
            temp_coll_name = f"{outline_name}_TempCollection"
            if temp_coll_name in bpy.data.collections:
                bpy.data.collections.remove(bpy.data.collections[temp_coll_name])
            print("  Cleared existing outline objects (FORCE_REGENERATE_OUTLINE)")

        # Always show mesh candidates for diagnostics
        armature_ref = bpy.data.objects.get(armature_name)
        if armature_ref:
            skip_suffixes = ('_Standin', '_LineArt_Copy', '_LineArt')
            all_meshes = [
                (c.name, len(c.data.vertices))
                for c in armature_ref.children
                if c.type == 'MESH' and not c.name.endswith(skip_suffixes)
            ]
            all_meshes.sort(key=lambda x: x[1], reverse=True)
            best_mesh = find_character_mesh(armature_name)
            print(f"  Mesh candidates for '{armature_name}' (by vertex count):")
            for name, verts in all_meshes:
                marker = " <-- SELECTED" if name == best_mesh else ""
                print(f"    {name}: {verts:,} verts{marker}")
            if not all_meshes:
                print(f"    (none found — armature has {len(list(armature_ref.children))} children)")

        # Migrate legacy object names to new char_tag convention if needed.
        # Old names: PB_Outline_LineArt, PB_Outline_LineArt_Camera, PB_Outline_LineArt_Light
        _legacy_names = {
            'PB_Outline_LineArt':        outline_name,
            'PB_Outline_LineArt_Camera': camera_name,
            'PB_Outline_LineArt_Light':  light_name,
        }
        for old_name, new_name in _legacy_names.items():
            if old_name != new_name and old_name in bpy.data.objects and new_name not in bpy.data.objects:
                bpy.data.objects[old_name].name = new_name
                print(f"  Migrated '{old_name}' → '{new_name}'")

        # Check if outline already exists
        outline_exists = outline_name in bpy.data.objects

        if outline_exists:
            # Show what mesh the existing outline was built from
            temp_coll_name = f"{outline_name}_TempCollection"
            if temp_coll_name in bpy.data.collections:
                for obj in bpy.data.collections[temp_coll_name].objects:
                    if obj.type == 'MESH':
                        print(f"  Existing outline uses mesh: {obj.name} ({len(obj.data.vertices):,} verts)")
            print(f"  Outline already exists — skipping generation (set FORCE_REGENERATE_OUTLINE = True to rebuild)")

        if not outline_exists and GENERATE_OUTLINE:
            # Need to generate outline — requires mesh object + object mode
            mesh_name = find_character_mesh(armature_name)
            if mesh_name:
                mesh_obj = bpy.data.objects.get(mesh_name)
                print(f"  Generating outline from mesh: {mesh_name}")

                # Must be in object mode with mesh selected for outline generation
                current_mode = bpy.context.mode
                if current_mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')

                # Select the mesh (outline generator needs it selected)
                bpy.context.view_layer.objects.active = mesh_obj
                mesh_obj.select_set(True)

                try:
                    from posebridge.outline_generator_lineart import create_genesis8_lineart_outline
                    gp_obj = create_genesis8_lineart_outline(mesh_obj, outline_name, char_tag=char_tag)
                    if gp_obj:
                        print(f"  OK — Outline generated: {outline_name}")
                        outline_exists = True
                    else:
                        print("  Warning: Outline generation returned None")
                except Exception as e:
                    print(f"  Warning: Outline generation failed: {e}")
                    import traceback
                    traceback.print_exc()

                # Restore pose mode with armature selected
                bpy.context.view_layer.objects.active = armature_obj
                armature_obj.select_set(True)
                bpy.ops.object.mode_set(mode='POSE')
            else:
                print("  Warning: No character mesh found for outline generation")

        # Move outline/camera/light/mesh copy to Z offset using ABSOLUTE positioning
        # (matches TESTING_POSEBRIDGE.md Step 4 — idempotent, safe to run multiple times)
        if outline_exists:
            moved = []
            # Outline GP goes to OUTLINE_Z_OFFSET (character feet level).
            for obj_name in [outline_name]:
                obj = bpy.data.objects.get(obj_name)
                if obj:
                    obj.location.z = OUTLINE_Z_OFFSET
                    moved.append(obj.name)
            # Camera and light: position at OUTLINE_Z_OFFSET + character_height * 0.58
            # so the camera frames the character correctly regardless of height.
            # Derive character_height from the mannequin bounding box (idempotent).
            mannequin_name_for_height = f"{find_character_mesh(armature_name) or ''}_LineArt_Copy".lstrip('_')
            mannequin_for_height = bpy.data.objects.get(mannequin_name_for_height)
            if mannequin_for_height and mannequin_for_height.type == 'MESH':
                from mathutils import Vector as _Vec
                _bbox = [mannequin_for_height.matrix_world @ _Vec(c)
                         for c in mannequin_for_height.bound_box]
                _char_h = max(c.z for c in _bbox) - min(c.z for c in _bbox)
                camera_z_offset = _char_h * 0.58
            else:
                camera_z_offset = 0.72  # Fallback: ~58% of average 1.24m character
            for obj_name in [camera_name, light_name]:
                obj = bpy.data.objects.get(obj_name)
                if obj:
                    obj.location.z = OUTLINE_Z_OFFSET + camera_z_offset
                    moved.append(obj.name)
            # Also move the mannequin mesh copy.
            # It may be in PB_{char}_Stage (new collection flow) or still in the
            # legacy TempCollection — check both so this is safe to run on old and new scenes.
            mannequin_name = f"{find_character_mesh(armature_name) or ''}_LineArt_Copy".lstrip('_')
            # First try the direct name lookup (works regardless of which collection it's in)
            mannequin_obj = bpy.data.objects.get(mannequin_name)
            if mannequin_obj and mannequin_obj.type == 'MESH':
                mannequin_obj.location.z = OUTLINE_Z_OFFSET
                moved.append(mannequin_obj.name)
                # Strip shape keys (JCMs, flexions, FACS) — mannequin is geometry-only
                if mannequin_obj.data.shape_keys:
                    sk_count = len(mannequin_obj.data.shape_keys.key_blocks)
                    mannequin_obj.shape_key_clear()
                    print(f"  Stripped {sk_count} shape keys from {mannequin_obj.name}")
                # Remove non-essential modifiers (keep Armature only)
                for mod in list(mannequin_obj.modifiers):
                    if mod.type != 'ARMATURE':
                        mannequin_obj.modifiers.remove(mod)
            else:
                # Fallback: scan temp collection (legacy scenes before collection management)
                temp_coll_name = f"{outline_name}_TempCollection"
                if temp_coll_name in bpy.data.collections:
                    for obj in bpy.data.collections[temp_coll_name].objects:
                        if obj.type == 'MESH':
                            obj.location.z = OUTLINE_Z_OFFSET
                            moved.append(obj.name)
                            if obj.data.shape_keys:
                                sk_count = len(obj.data.shape_keys.key_blocks)
                                obj.shape_key_clear()
                                print(f"  Stripped {sk_count} shape keys from {obj.name}")
                            for mod in list(obj.modifiers):
                                if mod.type != 'ARMATURE':
                                    obj.modifiers.remove(mod)
            print(f"  OK — Positioned at Z={OUTLINE_Z_OFFSET}m: {', '.join(moved)}")

        # Recapture body control points at new Z position
        # (MUST come before hands/face since capture_fixed_control_points clears all CPs)
        if outline_exists:
            try:
                count = capture_fixed_control_points(armature_obj, outline_name)
                print(f"  OK — Body control points: {count} captured at Z={OUTLINE_Z_OFFSET}m")
            except Exception as e:
                print(f"  Warning: Body control point capture failed: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("  Warning: No outline — body control points not captured")

    # --- Optional: Hand extraction ---
    if SETUP_HANDS and pb_settings:
        standin = STANDIN_NAME or find_standin_mesh(armature_name)
        if standin and standin in bpy.data.objects:
            try:
                import extract_hands
                if RELOAD_MODULES:
                    importlib.reload(extract_hands)
                hand_result = extract_hands.extract_and_setup_hands(
                    standin,
                    z_offset=HAND_Z_OFFSET,
                    armature_name=armature_name if armature_name in bpy.data.objects else None,
                    char_name=armature_name,
                    char_tag=char_tag,
                )
                if hand_result:
                    count = extract_hands.store_hand_control_points(hand_result)
                    print(f"  OK — Hand panel: {count} control points")
                else:
                    print("  Skipped hand extraction (already exists or failed)")
            except Exception as e:
                print(f"  Warning: Hand extraction failed: {e}")
        else:
            print(f"  Skipped hand extraction (no standin mesh found)")

    # --- Optional: Face extraction ---
    if SETUP_FACE and pb_settings and armature_obj:
        try:
            import extract_face
            if RELOAD_MODULES:
                importlib.reload(extract_face)
            face_result = extract_face.setup_face_panel(armature_obj, char_name=armature_name, char_tag=char_tag)
            if face_result:
                print(f"  OK — Face panel: {face_result['control_points']} control points")
            else:
                print("  Skipped face extraction (failed)")
        except Exception as e:
            print(f"  Warning: Face extraction failed: {e}")

else:
    print(f"\n--- Step 2: PoseBridge --- SKIPPED")

# ============================================================================
# Step 3: PoseBlend
# ============================================================================

if not SKIP_POSEBLEND:
    print(f"\n--- Step 3: PoseBlend ---")

    # Unregister + purge if reloading
    if RELOAD_MODULES and 'poseblend' in sys.modules:
        try:
            import poseblend
            safe_unregister('poseblend', poseblend)
        except:
            pass
        try:
            del bpy.types.Scene.poseblend_settings
        except:
            pass
        purge_modules('poseblend')
        print("  Purged cached poseblend modules")
    elif hasattr(bpy.context.scene, 'poseblend_settings'):
        try:
            import poseblend
            safe_unregister('poseblend', poseblend)
        except:
            pass

    # Fresh import + register
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
            bl_settings = bpy.context.scene.poseblend_settings
            bl_settings.is_active = True
            bl_settings.active_armature_name = armature_name
            print("  OK — PoseBlend registered and enabled")
        else:
            print("  ERROR: poseblend_settings not found after registration!")
    except Exception as e:
        print(f"  ERROR registering PoseBlend: {e}")
        import traceback
        traceback.print_exc()

else:
    print(f"\n--- Step 3: PoseBlend --- SKIPPED")

# ============================================================================
# Step 4: Activate & invoke modal operator
# ============================================================================

print(f"\n--- Step 4: Activate ---")

# Make sure armature is active and in pose mode
if armature_obj:
    bpy.context.view_layer.objects.active = armature_obj
    armature_obj.select_set(True)
    if bpy.context.mode != 'POSE':
        bpy.ops.object.mode_set(mode='POSE')

# Invoke the main modal operator in a 3D viewport
window, area = find_3d_view()
if window and area:
    with bpy.context.temp_override(window=window, area=area):
        bpy.ops.view3d.daz_bone_select('INVOKE_DEFAULT')
    print("  OK — Modal operator started")
else:
    print("  WARNING: No 3D viewport found — open one and run:")
    print("    bpy.ops.view3d.daz_bone_select('INVOKE_DEFAULT')")

# ============================================================================
# Summary
# ============================================================================

print("\n" + "=" * 70)
print("  SETUP COMPLETE")
print("=" * 70)

components = []
components.append("daz_bone_select (bone select, IK, pins)")

if not SKIP_POSEBRIDGE:
    if pb_settings:
        body_cps = [cp for cp in pb_settings.control_points_fixed
                     if not cp.panel_view or cp.panel_view == 'body']
        hand_cps = [cp for cp in pb_settings.control_points_fixed
                     if cp.panel_view == 'hands']
        face_cps = [cp for cp in pb_settings.control_points_fixed
                     if cp.panel_view == 'face']
        total_cps = len(body_cps) + len(hand_cps) + len(face_cps)
        components.append(f"PoseBridge ({total_cps} control points: "
                         f"{len(body_cps)} body, {len(hand_cps)} hands, {len(face_cps)} face)")
    else:
        components.append("PoseBridge (registered, no control points)")

if not SKIP_POSEBLEND:
    components.append("PoseBlend (registered)")

print(f"\nArmature: {armature_name}")
print(f"Components:")
for c in components:
    print(f"  - {c}")

print(f"""
Controls:
  - Hover over bones to preview, click to select
  - G to drag (IK), R to rotate
  - Right-click for pin menu (pin/unpin translation/rotation)
  - ESC to exit modal operator

N-Panel (DAZ tab):
  BlenDAZ
    BlenDAZ Setup  — character init / face group remap
    Touch          — sensitivity, rotation limits, IK settings
    PoseBridge     — Open in Viewport, Body/Hands/Face switcher
      Body Controls  — Reset Pose, Clear All Pins
      Face Controls  — Reset Face, Expressions, Visemes
      Settings
  PoseBlend        — grid-based pose blending
""")
print("=" * 70 + "\n")

# ============================================================================
# Step 5: Register character in CharacterSlot registry
# ============================================================================

# Ensure naming vars exist even if PoseBridge was skipped
if 'outline_name' not in dir():
    outline_name = f"PB_Outline_{char_tag}"
if 'camera_name' not in dir():
    camera_name = f"PB_Camera_Body_{char_tag}"
if 'light_name' not in dir():
    light_name = f"PB_Light_{char_tag}"

if pb_settings and hasattr(pb_settings, 'blendaz_characters'):
    # Upsert: find existing slot for this armature, or create new one
    slot = None
    slot_idx = -1
    for i, s in enumerate(pb_settings.blendaz_characters):
        if s.armature_name == armature_name:
            slot = s
            slot_idx = i
            break

    if slot is None:
        slot = pb_settings.blendaz_characters.add()
        slot_idx = len(pb_settings.blendaz_characters) - 1
        # Assign Z offset based on number of existing characters
        if slot_idx == 0:
            slot.z_offset = OUTLINE_Z_OFFSET
        else:
            # Stack below previous characters
            min_z = min(s.z_offset for s in pb_settings.blendaz_characters if s != slot)
            slot.z_offset = min_z - 5.0
        print(f"  Registered NEW character slot [{slot_idx}]: {armature_name}")
    else:
        print(f"  Updated EXISTING character slot [{slot_idx}]: {armature_name}")

    # Fill slot fields
    slot.armature_name = armature_name
    slot.char_tag = char_tag
    slot.body_mesh_name = find_character_mesh(armature_name) or ""
    slot.outline_gp_name = outline_name if not SKIP_POSEBRIDGE else ""
    slot.camera_body = camera_name if not SKIP_POSEBRIDGE else ""
    slot.light_name = light_name if not SKIP_POSEBRIDGE else ""
    slot.mannequin_name = f"{slot.body_mesh_name}_LineArt_Copy" if slot.body_mesh_name else ""

    # Camera names for hands/face (may or may not have been created)
    slot.camera_hands = f"PB_Camera_Hands_{char_tag}"
    slot.camera_face = f"PB_Camera_Face_{char_tag}"

    # Stage collection
    slot.stage_collection = f"PB_{armature_name}_Stage"

    # Copy init status from posebridge_settings (for backward compat)
    slot.init_status = pb_settings.blendaz_init_status
    slot.reference_mesh_name = pb_settings.blendaz_reference_mesh_name

    # Set as active
    pb_settings.blendaz_active_index = slot_idx

    print(f"  Active character: [{slot_idx}] {armature_name} (tag: {char_tag})")
    print(f"  Objects: outline={slot.outline_gp_name}, camera={slot.camera_body}, "
          f"mannequin={slot.mannequin_name}")

