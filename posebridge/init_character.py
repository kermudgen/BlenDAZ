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
BlenDAZ Character Init — Setup operators for onboarding a new DAZ character.

Three operators covering the full onboarding workflow:

  DAZ_OT_blendaz_snapshot_premerge
      Tier 2 step A: called BEFORE merging geografts.
      Creates the mannequin copy (outline mesh) from the current pre-merge body
      and records the reference mesh name in scene settings for later remap.

  DAZ_OT_blendaz_merge_and_remap
      Tier 1 / Tier 2 step B: merges geografts via Diffeomorphic, then
      immediately remaps face groups from the saved mannequin reference.
      Also callable standalone after a manual merge (Tier 2 step B).

  DAZ_OT_blendaz_remap_face_groups
      Lightweight remap-only operator. Runs the face center remap without
      touching anything else. For users who merged manually and just need
      to resync the face group map.

Typical workflows
-----------------
Tier 1 one-click:
  [Snapshot Pre-Merge]  →  [Merge & Remap]

Tier 2 manual prep:
  (user adds custom morphs etc.)
  [Snapshot Pre-Merge]  →  (user merges via Diffeomorphic)  →  [Remap Face Groups]

Tier 3 no merge:
  Not needed — standard FaceGroupManager path works when polygon count
  matches the DSF file.
"""

import bpy
import re
from bpy.types import Operator

import logging
log = logging.getLogger(__name__)


# ============================================================================
# Prerequisite validation
# ============================================================================

MIN_BLENDER = (5, 0, 0)
DAZ_MERGE_OPERATOR = "daz.merge_geografts"

# DAZ bone names present in Genesis 8/9 rigs — used to detect DAZ armatures
_DAZ_SENTINEL_BONES = {'lPectoral', 'rPectoral', 'lCollar', 'rCollar', 'pelvis'}


def check_prerequisites(context):
    """Validate that the environment is ready for BlenDAZ init.

    Returns:
        (ok: bool, message: str)
    """
    # Blender version
    if bpy.app.version < MIN_BLENDER:
        v = ".".join(str(x) for x in bpy.app.version[:2])
        return False, f"BlenDAZ requires Blender {'.'.join(str(x) for x in MIN_BLENDER[:2])}+. Current: {v}"

    # Diffeomorphic present
    if not hasattr(bpy.ops, DAZ_MERGE_OPERATOR.split('.')[0]):
        return False, "Diffeomorphic addon not found. Install Diffeomorphic 5.0.0.2736+."

    # Active object must be a DAZ armature
    arm = _find_daz_armature(context)
    if arm is None:
        return False, "No DAZ armature found. Select a Genesis 8/9 armature or make it active."

    # Body mesh must be findable
    mesh = _find_body_mesh(context, arm)
    if mesh is None:
        return False, f"Could not find a body mesh rigged to '{arm.name}'."

    return True, "OK"


def _find_daz_armature(context):
    """Return the DAZ armature: active object if it qualifies, else scan scene."""
    obj = context.active_object
    if obj and obj.type == 'ARMATURE':
        if _DAZ_SENTINEL_BONES & {b.name for b in obj.data.bones}:
            return obj
    for obj in context.scene.objects:
        if obj.type == 'ARMATURE':
            if _DAZ_SENTINEL_BONES & {b.name for b in obj.data.bones}:
                return obj
    return None


def _find_body_mesh(context, armature):
    """Return the body mesh: most vertex-grouped mesh rigged to armature."""
    best = None
    best_count = 0
    for obj in context.scene.objects:
        if obj.type != 'MESH':
            continue
        rigged = False
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object == armature:
                rigged = True
                break
        if not rigged and obj.parent == armature:
            rigged = True
        if rigged:
            n = len(obj.vertex_groups)
            if n > best_count:
                best_count = n
                best = obj
    return best


def _find_geografts(context, armature):
    """Return list of geograft mesh objects.

    Strategy (in order):
    1. Selected meshes that are not the body mesh — user has already selected
       them per Diffeomorphic's merge workflow, so we trust the selection.
    2. Fallback: scene scan for known Diffeomorphic graft markers
       (DazGraftGroup on mesh data, or 'DazGraft' custom property on object).
    """
    body_mesh = _find_body_mesh(context, armature)

    # --- Strategy 1: use current selection ---
    selected_meshes = [
        obj for obj in context.selected_objects
        if obj.type == 'MESH' and obj is not body_mesh
    ]
    if selected_meshes:
        log.info(f"[BlenDAZ Init] Found {len(selected_meshes)} geograft(s) from selection: "
                 f"{[o.name for o in selected_meshes]}")
        return selected_meshes

    # --- Strategy 2: scene scan for Diffeomorphic graft markers ---
    GRAFT_KEYS = ('DazGraftGroup', 'DazGraft', 'daz_graft_group', 'DazMergeGrafts')
    grafts = []
    for obj in context.scene.objects:
        if obj.type != 'MESH' or obj is body_mesh:
            continue
        # Check mesh data custom properties
        has_marker = any(obj.data.get(k) for k in GRAFT_KEYS)
        # Check object custom properties
        has_marker = has_marker or any(obj.get(k) for k in GRAFT_KEYS)
        if not has_marker:
            continue
        # Must be rigged to same armature
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object == armature:
                grafts.append(obj)
                break
        else:
            if obj.parent == armature:
                grafts.append(obj)

    if grafts:
        log.info(f"[BlenDAZ Init] Found {len(grafts)} geograft(s) via scene scan: "
                 f"{[o.name for o in grafts]}")
    else:
        # Debug: print custom props on selected meshes to help diagnose
        for obj in context.selected_objects:
            if obj.type == 'MESH' and obj is not body_mesh:
                obj_keys = list(obj.keys())
                data_keys = list(obj.data.keys())
                log.info(f"[BlenDAZ Init] Selected mesh '{obj.name}' — "
                         f"obj props: {obj_keys}, data props: {data_keys}")

    return grafts


def _get_or_build_override(context):
    """Build a context override pointing at a valid (non-camera) VIEW_3D area."""
    for area in context.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        for sp in area.spaces:
            if sp.type != 'VIEW_3D':
                continue
            rv3d = sp.region_3d
            if rv3d and rv3d.view_perspective == 'CAMERA':
                continue  # Skip locked-camera viewports
            for reg in area.regions:
                if reg.type == 'WINDOW':
                    return {'area': area, 'region': reg, 'space_data': sp,
                            'screen': context.screen, 'window': context.window}
    # Fall back to any VIEW_3D
    for area in context.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        for sp in area.spaces:
            if sp.type != 'VIEW_3D':
                continue
            for reg in area.regions:
                if reg.type == 'WINDOW':
                    return {'area': area, 'region': reg, 'space_data': sp,
                            'screen': context.screen, 'window': context.window}
    return None


# ============================================================================
# Shared remap logic
# ============================================================================

def _run_face_group_remap(context, live_mesh_obj, reference_mesh_name, armature):
    """
    Run the face center remap from reference mesh → live mesh.

    Args:
        live_mesh_obj:        The post-merge body mesh object.
        reference_mesh_name:  Name of the pre-merge mannequin copy object.
        armature:             DAZ armature object.

    Returns:
        (ok: bool, message: str)
    """
    from .. import dsf_face_groups

    reference_mesh_obj = bpy.data.objects.get(reference_mesh_name)
    if reference_mesh_obj is None:
        return False, f"Reference mesh '{reference_mesh_name}' not found in scene. Re-run Snapshot Pre-Merge."

    log.info(f"\n[BlenDAZ Init] Running face group remap")
    log.info(f"  Reference mesh: {reference_mesh_obj.name} ({len(reference_mesh_obj.data.polygons)} polygons)")
    log.info(f"  Live mesh:      {live_mesh_obj.name} ({len(live_mesh_obj.data.polygons)} polygons)")

    fgm = dsf_face_groups.FaceGroupManager.build_from_reference_mesh(
        reference_mesh_obj, live_mesh_obj, armature
    )

    if fgm is None:
        return False, (
            "Face group remap failed — reference mesh has no DSF face group data. "
            "Check that the DSF file path is accessible and the polygon count matches."
        )

    # Push the new FaceGroupManager into the live modal operator instance (if running)
    # and clear its highlight cache so it redraws with the remapped zones.
    try:
        from .. import daz_bone_select
        op_cls = daz_bone_select.VIEW3D_OT_daz_bone_select
        op_cls._bracket_vert_cache.clear()
        if hasattr(op_cls, '_highlight_cache'):
            op_cls._highlight_cache.clear()
        # Update the live instance's _face_group_mgr so it uses the remapped data
        # immediately without requiring a restart of the modal operator.
        live_instance = getattr(op_cls, '_live_instance', None)
        if live_instance is not None:
            live_instance._face_group_mgr = fgm
            live_instance._highlight_cache.clear()
            log.info("  [BlenDAZ Init] Updated live operator instance with remapped FaceGroupManager")
        else:
            log.info("  [BlenDAZ Init] Cleared operator caches (modal not running — will apply on next start)")
    except Exception as e:
        log.warning(f"  [BlenDAZ Init] Could not update operator caches (non-fatal): {e}")

    return True, f"Remap complete — {sum(1 for x in fgm.face_group_map if x)} polygons mapped."


# ============================================================================
# Operator: Snapshot Pre-Merge State
# ============================================================================

class DAZ_OT_blendaz_snapshot_premerge(Operator):
    """Create mannequin copy from current body mesh for use as face group reference
after geograft merge. Run this BEFORE merging geografts."""
    bl_idname = "blendaz.snapshot_premerge"
    bl_label = "Snapshot Pre-Merge State"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ok, msg = check_prerequisites(context)
        if not ok:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        armature = _find_daz_armature(context)
        body_mesh = _find_body_mesh(context, armature)

        settings = getattr(context.scene, 'posebridge_settings', None)
        if settings is None:
            self.report({'ERROR'}, "PoseBridge not registered. Run PoseBridge setup first.")
            return {'CANCELLED'}

        # Check if mannequin already exists
        expected_copy_name = f"{body_mesh.name}_LineArt_Copy"
        existing = bpy.data.objects.get(expected_copy_name)
        if existing:
            log.info(f"[BlenDAZ Init] Mannequin copy already exists: {existing.name}")
            settings.blendaz_reference_mesh_name = existing.name
            settings.blendaz_live_mesh_name = body_mesh.name
            settings.blendaz_init_status = 'snapshot_done'
            self.report({'INFO'}, f"Snapshot already exists: '{existing.name}'. Ready to merge.")
            return {'FINISHED'}

        # Create mannequin copy via outline generator
        try:
            from . import outline_generator_lineart

            # Derive char_tag from armature name for multi-character naming
            _char_tag = re.sub(r'[^A-Za-z0-9_]', '_', armature.name)
            _char_tag = re.sub(r'_+', '_', _char_tag).strip('_')

            ov = _get_or_build_override(context)
            if ov:
                with bpy.context.temp_override(**ov):
                    outline_generator_lineart.create_genesis8_lineart_outline(
                        body_mesh,
                        char_tag=_char_tag
                    )
            else:
                outline_generator_lineart.create_genesis8_lineart_outline(
                    body_mesh,
                    char_tag=_char_tag
                )

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Failed to create mannequin: {e}")
            return {'CANCELLED'}

        # Confirm copy was created
        copy_obj = bpy.data.objects.get(expected_copy_name)
        if copy_obj is None:
            self.report({'ERROR'},
                f"Mannequin copy '{expected_copy_name}' not found after outline generation.")
            return {'CANCELLED'}

        # Move all created stage objects to Z-offset (same logic as registration)
        from .core import next_z_offset
        z_offset = next_z_offset(context)
        outline_name = f"PB_Outline_{_char_tag}"
        camera_name = f"PB_Camera_Body_{_char_tag}"
        light_name = f"{outline_name}_Light"

        # Derive camera Z from mannequin height
        camera_z_offset = 0.72
        if copy_obj.type == 'MESH':
            from mathutils import Vector
            bbox = [copy_obj.matrix_world @ Vector(c) for c in copy_obj.bound_box]
            char_h = max(c.z for c in bbox) - min(c.z for c in bbox)
            if char_h > 0:
                camera_z_offset = char_h * 0.58

        for obj_name, target_z in [(outline_name, z_offset),
                                    (expected_copy_name, z_offset),
                                    (camera_name, z_offset + camera_z_offset),
                                    (light_name, z_offset + camera_z_offset)]:
            obj = bpy.data.objects.get(obj_name)
            if obj:
                if obj.parent:
                    world_mat = obj.matrix_world.copy()
                    obj.parent = None
                    obj.matrix_world = world_mat
                obj.location.z = target_z
                log.info(f"  Moved '{obj.name}' to Z={target_z:.1f}")

        # Record reference mesh name in settings
        settings.blendaz_reference_mesh_name = copy_obj.name
        settings.blendaz_live_mesh_name = body_mesh.name
        settings.blendaz_init_status = 'snapshot_done'

        self.report({'INFO'},
            f"Pre-merge snapshot saved: '{copy_obj.name}'. "
            "Now merge your geografts, then click Remap Face Groups.")
        log.info(f"[BlenDAZ Init] Snapshot complete. Reference mesh: {copy_obj.name}")
        return {'FINISHED'}


# ============================================================================
# Operator: Remap Face Groups (post-merge)
# ============================================================================

class DAZ_OT_blendaz_remap_face_groups(Operator):
    """Remap face group highlight data from the pre-merge mannequin to the
current (merged) body mesh. Run after merging geografts."""
    bl_idname = "blendaz.remap_face_groups"
    bl_label = "Remap Face Groups"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = getattr(context.scene, 'posebridge_settings', None)
        if settings is None:
            self.report({'ERROR'}, "PoseBridge not registered.")
            return {'CANCELLED'}

        armature = _find_daz_armature(context)
        if armature is None:
            self.report({'ERROR'}, "No DAZ armature found.")
            return {'CANCELLED'}

        reference_mesh_name = settings.blendaz_reference_mesh_name
        if not reference_mesh_name:
            self.report({'ERROR'},
                "No pre-merge snapshot found. Run 'Snapshot Pre-Merge State' first.")
            return {'CANCELLED'}

        # Find live mesh — prefer stored name, fall back to auto-detect
        live_mesh_name = settings.blendaz_live_mesh_name
        live_mesh = bpy.data.objects.get(live_mesh_name) if live_mesh_name else None
        if live_mesh is None:
            live_mesh = _find_body_mesh(context, armature)
        if live_mesh is None:
            self.report({'ERROR'}, "Could not find body mesh.")
            return {'CANCELLED'}

        ok, msg = _run_face_group_remap(context, live_mesh, reference_mesh_name, armature)

        if not ok:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        # Update stored polygon count (for stale detection)
        settings.blendaz_live_mesh_poly_count = len(live_mesh.data.polygons)
        settings.blendaz_live_mesh_name = live_mesh.name
        settings.blendaz_init_status = 'ready'

        self.report({'INFO'}, f"BlenDAZ: {msg}")
        return {'FINISHED'}


# ============================================================================
# Operator: Merge Geografts + Remap (Tier 1 / Tier 2 step B)
# ============================================================================

class DAZ_OT_blendaz_merge_and_remap(Operator):
    """Merge selected geografts via Diffeomorphic, then remap face groups.
Requires a pre-merge snapshot to already exist."""
    bl_idname = "blendaz.merge_and_remap"
    bl_label = "Merge Geografts & Remap"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = getattr(context.scene, 'posebridge_settings', None)
        if settings is None:
            self.report({'ERROR'}, "PoseBridge not registered.")
            return {'CANCELLED'}

        if not settings.blendaz_reference_mesh_name:
            self.report({'ERROR'},
                "No pre-merge snapshot found. Run 'Snapshot Pre-Merge State' first.")
            return {'CANCELLED'}

        armature = _find_daz_armature(context)
        if armature is None:
            self.report({'ERROR'}, "No DAZ armature found.")
            return {'CANCELLED'}

        live_mesh_name = settings.blendaz_live_mesh_name
        live_mesh = bpy.data.objects.get(live_mesh_name) if live_mesh_name else None
        if live_mesh is None:
            live_mesh = _find_body_mesh(context, armature)
        if live_mesh is None:
            self.report({'ERROR'}, "Could not find body mesh.")
            return {'CANCELLED'}

        grafts = _find_geografts(context, armature)
        if not grafts:
            self.report({'WARNING'}, "No geografts found — skipping merge, running remap only.")
        else:
            # Select body mesh (active) + all geografts (selected)
            ov = _get_or_build_override(context)
            try:
                def _do_merge():
                    bpy.ops.object.select_all(action='DESELECT')
                    live_mesh.select_set(True)
                    context.view_layer.objects.active = live_mesh
                    for g in grafts:
                        g.select_set(True)
                    log.info(f"[BlenDAZ Init] Merging {len(grafts)} geograft(s) into '{live_mesh.name}'")
                    bpy.ops.daz.merge_geografts()

                if ov:
                    with bpy.context.temp_override(**ov):
                        _do_merge()
                else:
                    _do_merge()

                log.info("[BlenDAZ Init] Geograft merge complete")
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.report({'ERROR'}, f"Geograft merge failed: {e}")
                return {'CANCELLED'}

        # After merge the live mesh object may have been renamed by Diffeomorphic
        # (it appends " Merged" to the name). Re-detect.
        live_mesh_after = bpy.data.objects.get(live_mesh.name)
        if live_mesh_after is None:
            # Diffeomorphic renamed it — find by vertex count heuristic
            live_mesh_after = _find_body_mesh(context, armature)
        if live_mesh_after is None:
            self.report({'ERROR'}, "Could not find body mesh after merge.")
            return {'CANCELLED'}

        # Run face group remap
        ok, msg = _run_face_group_remap(
            context, live_mesh_after, settings.blendaz_reference_mesh_name, armature
        )
        if not ok:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        settings.blendaz_live_mesh_poly_count = len(live_mesh_after.data.polygons)
        settings.blendaz_live_mesh_name = live_mesh_after.name
        settings.blendaz_init_status = 'ready'

        graft_count = len(grafts) if grafts else 0
        self.report({'INFO'},
            f"BlenDAZ: Merged {graft_count} geograft(s). {msg}")
        return {'FINISHED'}


# ============================================================================
# Registration
# ============================================================================

classes = (
    DAZ_OT_blendaz_snapshot_premerge,
    DAZ_OT_blendaz_remap_face_groups,
    DAZ_OT_blendaz_merge_and_remap,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
