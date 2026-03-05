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

"""PoseBridge Panel UI - Blender N-panel interface

Panel hierarchy (all in bl_category='DAZ'):
  BlenDAZ                          (VIEW3D_PT_blendaz_root)
    BlenDAZ Setup                  (VIEW3D_PT_blendaz_setup)
    Touch                          (VIEW3D_PT_touch)
    PoseBridge                     (VIEW3D_PT_posebridge)
      Body Controls                (VIEW3D_PT_posebridge_body)       [DEFAULT_CLOSED]
      Face Controls                (VIEW3D_PT_posebridge_face)       [DEFAULT_CLOSED]
      Settings                     (VIEW3D_PT_posebridge_settings)   [DEFAULT_CLOSED]
"""

import bpy
from bpy.types import Panel, Operator, PropertyGroup

import logging
log = logging.getLogger(__name__)


# DAZ marker bones used to identify DAZ rigs
_DAZ_MARKER_BONES = {'lPectoral', 'rPectoral', 'lCollar', 'rCollar'}


def _find_pb_viewport(context):
    """Find the PoseBridge viewport — the VIEW_3D in CAMERA mode with a PB camera.

    Returns (space, r3d, area) or (None, None, None).
    """
    for area in context.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        for sp in area.spaces:
            if sp.type == 'VIEW_3D':
                rv3d = sp.region_3d
                if rv3d and rv3d.view_perspective == 'CAMERA':
                    cam = sp.camera
                    if cam and cam.name.startswith('PB_Camera_'):
                        return sp, rv3d, area
    return None, None, None


# ============================================================================
# Operators
# ============================================================================

class BLENDAZ_OT_switch_character(Operator):
    """Switch BlenDAZ to a different registered character"""
    bl_idname = "blendaz.switch_character"
    bl_label = "Switch Character"

    armature_name: bpy.props.StringProperty()

    def execute(self, context):
        from .. import daz_bone_select as _dbs
        live = getattr(_dbs.VIEW3D_OT_daz_bone_select, '_live_instance', None)
        if live:
            try:
                if live._switch_active_character(context, self.armature_name):
                    context.area.tag_redraw()
                    return {'FINISHED'}
            except ReferenceError:
                _dbs.VIEW3D_OT_daz_bone_select._live_instance = None
        # Fallback: just update settings (modal not running)
        settings = getattr(context.scene, 'posebridge_settings', None)
        if settings:
            # Save old character's CPs, restore new character's
            from .core import save_control_points, restore_control_points
            old_idx = settings.blendaz_active_index
            if 0 <= old_idx < len(settings.blendaz_characters):
                save_control_points(settings.blendaz_characters[old_idx].char_tag)
            for i, slot in enumerate(settings.blendaz_characters):
                if slot.armature_name == self.armature_name:
                    settings.blendaz_active_index = i
                    settings.active_armature_name = self.armature_name
                    restore_control_points(slot.char_tag)
                    break
            context.area.tag_redraw()
        return {'FINISHED'}


class BLENDAZ_OT_scan_characters(Operator):
    """Scan scene for DAZ armatures and store results for the N-Panel"""
    bl_idname = "blendaz.scan_characters"
    bl_label = "Scan for Characters"

    def execute(self, context):
        found = []
        settings = getattr(context.scene, 'posebridge_settings', None)
        registered = set()
        if settings and hasattr(settings, 'blendaz_characters'):
            registered = {s.armature_name for s in settings.blendaz_characters}

        for obj in context.scene.objects:
            if obj.type == 'ARMATURE':
                bone_names = {b.name for b in obj.data.bones}
                if _DAZ_MARKER_BONES & bone_names:
                    tag = "registered" if obj.name in registered else "unregistered"
                    found.append((obj.name, tag))

        # Store scan results as comma-separated string on scene for panel display
        if settings:
            unreg = [name for name, tag in found if tag == "unregistered"]
            settings.blendaz_scanned_unregistered = ",".join(unreg)

        if found:
            msg = ", ".join(f"{name} ({tag})" for name, tag in found)
            self.report({'INFO'}, f"Found {len(found)} DAZ rig(s): {msg}")
        else:
            self.report({'WARNING'}, "No DAZ armatures found in scene")
            if settings:
                settings.blendaz_scanned_unregistered = ""

        context.area.tag_redraw()
        return {'FINISHED'}


class BLENDAZ_OT_register_character(Operator):
    """Register a DAZ character with BlenDAZ (generates outline, cameras, control points)"""
    bl_idname = "blendaz.register_character"
    bl_label = "Register Character"

    armature_name: bpy.props.StringProperty()

    def execute(self, context):
        import re

        armature_name = self.armature_name
        armature_obj = bpy.data.objects.get(armature_name)
        if not armature_obj or armature_obj.type != 'ARMATURE':
            self.report({'ERROR'}, f"Armature '{armature_name}' not found")
            return {'CANCELLED'}

        settings = getattr(context.scene, 'posebridge_settings', None)
        if not settings:
            self.report({'ERROR'}, "PoseBridge not initialised")
            return {'CANCELLED'}

        # Generate char_tag
        char_tag = re.sub(r'[^A-Za-z0-9_]', '_', armature_name)
        char_tag = re.sub(r'_+', '_', char_tag).strip('_')

        # Object names
        outline_name = f"PB_Outline_{char_tag}"
        camera_name = f"PB_Camera_Body_{char_tag}"
        light_name = f"PB_Light_{char_tag}"

        log.info(f"\n{'='*60}")
        log.info(f"  REGISTERING CHARACTER: {armature_name} (tag: {char_tag})")
        log.info(f"{'='*60}")

        # Find character mesh
        from .core import find_character_mesh, find_standin_mesh
        body_mesh_name = find_character_mesh(armature_name)
        if not body_mesh_name:
            self.report({'ERROR'}, f"No character mesh found for '{armature_name}'")
            return {'CANCELLED'}

        mesh_obj = bpy.data.objects.get(body_mesh_name)
        log.info(f"  Body mesh: {body_mesh_name}")

        # Z-offset for this character
        from .core import next_z_offset
        z_offset = next_z_offset(context)
        log.info(f"  Z-offset: {z_offset}m")

        # --- Save previous character's CPs before anything clears them ---
        # The outline generator internally calls capture_fixed_control_points()
        # which clears the shared collection. Save BEFORE that happens.
        from .core import save_control_points
        if settings.active_armature_name and settings.active_armature_name != armature_name:
            prev_tag = None
            for s in settings.blendaz_characters:
                if s.armature_name == settings.active_armature_name:
                    prev_tag = s.char_tag
                    break
            if prev_tag:
                save_control_points(prev_tag)
                log.info(f"  Saved {prev_tag} CPs to cache before outline generation")

        # --- 1. Generate outline ---
        outline_exists = outline_name in bpy.data.objects
        if not outline_exists and mesh_obj:
            log.info(f"\n--- Generating outline from {body_mesh_name} ---")
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')

            context.view_layer.objects.active = mesh_obj
            mesh_obj.select_set(True)

            try:
                from .outline_generator_lineart import create_genesis8_lineart_outline
                gp_obj = create_genesis8_lineart_outline(mesh_obj, outline_name, char_tag=char_tag)
                if gp_obj:
                    log.info(f"  OK — Outline generated: {outline_name}")
                    outline_exists = True
                else:
                    self.report({'WARNING'}, "Outline generation returned None")
            except Exception as e:
                self.report({'WARNING'}, f"Outline generation failed: {e}")
                import traceback
                traceback.print_exc()

        # Re-check: outline may exist even if the return errored
        if not outline_exists:
            outline_exists = outline_name in bpy.data.objects

        # --- 2. Z-offset positioning ---
        char_h = None  # character height — set from mannequin bbox, used for hand scaling
        if outline_exists:
            mannequin_name = f"{body_mesh_name}_LineArt_Copy"
            camera_z_offset = 0.72  # fallback

            mannequin_obj = bpy.data.objects.get(mannequin_name)
            if mannequin_obj and mannequin_obj.type == 'MESH':
                from mathutils import Vector
                bbox = [mannequin_obj.matrix_world @ Vector(c)
                        for c in mannequin_obj.bound_box]
                char_h = max(c.z for c in bbox) - min(c.z for c in bbox)
                camera_z_offset = char_h * 0.58

            # Move all stage objects to Z-offset
            for obj_name, target_z in [(outline_name, z_offset),
                                        (mannequin_name, z_offset),
                                        (camera_name, z_offset + camera_z_offset),
                                        (light_name, z_offset + camera_z_offset)]:
                obj = bpy.data.objects.get(obj_name)
                if obj:
                    if obj.parent:
                        world_mat = obj.matrix_world.copy()
                        obj.parent = None
                        obj.matrix_world = world_mat
                    obj.location.z = target_z
                    log.debug(f"  Moved '{obj.name}' to Z={target_z:.1f}")

        # --- 3. Capture body control points ---
        if outline_exists:
            # Ensure armature is active and in pose mode for CP capture
            context.view_layer.objects.active = armature_obj
            armature_obj.select_set(True)
            if context.mode != 'POSE':
                bpy.ops.object.mode_set(mode='POSE')

            try:
                from .outline_generator_lineart import capture_fixed_control_points
                count = capture_fixed_control_points(armature_obj, outline_name)
                log.info(f"  OK — Body control points: {count}")
            except Exception as e:
                log.warning(f"  Warning: Body CP capture failed: {e}")

        # --- 4. Extract hands ---
        standin = find_standin_mesh(armature_name)
        if standin and standin in bpy.data.objects:
            try:
                from . import extract_hands
                hand_result = extract_hands.extract_and_setup_hands(
                    standin,
                    z_offset=z_offset - 3.0,  # 3m below body offset
                    armature_name=armature_name,
                    char_name=armature_name,
                    char_tag=char_tag,
                    char_height=char_h,
                )
                if hand_result:
                    count = extract_hands.store_hand_control_points(hand_result)
                    log.info(f"  OK — Hand panel: {count} control points")
            except Exception as e:
                log.warning(f"  Warning: Hand extraction failed: {e}")

        # --- 5. Setup face ---
        try:
            from . import extract_face
            face_result = extract_face.setup_face_panel(
                armature_obj, char_name=armature_name, char_tag=char_tag
            )
            if face_result:
                log.info(f"  OK — Face panel: {face_result['control_points']} control points")
        except Exception as e:
            log.warning(f"  Warning: Face extraction failed: {e}")

        # --- 6. Register CharacterSlot ---
        slot = None
        slot_idx = -1
        for i, s in enumerate(settings.blendaz_characters):
            if s.armature_name == armature_name:
                slot = s
                slot_idx = i
                break

        if slot is None:
            slot = settings.blendaz_characters.add()
            slot_idx = len(settings.blendaz_characters) - 1

        slot.armature_name = armature_name
        slot.char_tag = char_tag
        slot.body_mesh_name = body_mesh_name
        slot.outline_gp_name = outline_name
        slot.camera_body = camera_name
        slot.camera_hands = f"PB_Camera_Hands_{char_tag}"
        slot.camera_face = f"PB_Camera_Face_{char_tag}"
        slot.light_name = light_name
        slot.mannequin_name = f"{body_mesh_name}_LineArt_Copy"
        slot.stage_collection = f"PB_{armature_name}_Stage"
        slot.z_offset = z_offset

        settings.blendaz_active_index = slot_idx
        settings.active_armature_name = armature_name

        # Remove from scanned list
        if settings.blendaz_scanned_unregistered:
            unreg = [n for n in settings.blendaz_scanned_unregistered.split(",")
                     if n and n != armature_name]
            settings.blendaz_scanned_unregistered = ",".join(unreg)

        # --- Restore pose mode on the new armature ---
        context.view_layer.objects.active = armature_obj
        armature_obj.select_set(True)
        if context.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')

        # Cache this character's CPs for later switching
        save_control_points(char_tag)

        log.info(f"\n  Registered character [{slot_idx}]: {armature_name}")
        self.report({'INFO'}, f"Registered: {armature_name}")
        context.area.tag_redraw()
        return {'FINISHED'}


class POSEBRIDGE_OT_set_panel_view(Operator):
    """Switch PoseBridge panel view"""
    bl_idname = "posebridge.set_panel_view"
    bl_label = "Set Panel View"
    bl_options = {'REGISTER', 'UNDO'}

    view: bpy.props.EnumProperty(
        name="View",
        items=[
            ('body', 'Body', 'Full body panel'),
            ('hands', 'Hands', 'Both hands detail panel'),
            ('face', 'Face', 'Face detail panel'),
        ],
        default='body'
    )

    # Fallback camera names (legacy single-character mode)
    CAMERAS_LEGACY = {
        'body':  'PB_Outline_LineArt_Camera',
        'hands': 'PB_Camera_Hands',
        'face':  'PB_Camera_Face',
    }

    # Objects shown in each panel view (substring match)
    BODY_OBJECTS  = {'PB_Outline', '_LineArt_Copy'}
    HANDS_SUBSTR  = {'PB_Hand_Left', 'PB_Hand_Right'}

    # Saved camera state per view: {view_name: (offset, zoom)}
    _saved_state = {}

    def _get_camera_name(self, context, view):
        """Get camera name from active CharacterSlot, or fall back to legacy names."""
        settings = getattr(context.scene, 'posebridge_settings', None)
        if settings and hasattr(settings, 'blendaz_characters'):
            idx = settings.blendaz_active_index
            if 0 <= idx < len(settings.blendaz_characters):
                slot = settings.blendaz_characters[idx]
                cam_map = {'body': slot.camera_body, 'hands': slot.camera_hands, 'face': slot.camera_face}
                name = cam_map.get(view, '')
                if name and name in bpy.data.objects:
                    return name
        # Fallback to legacy
        return self.CAMERAS_LEGACY.get(view)

    def _enter_face_local_view(self, context, settings, pb_space, pb_area):
        """Enter local view in PB viewport to isolate the active character."""
        # Already in local view — skip
        if pb_space.local_view:
            return
        idx = settings.blendaz_active_index
        if idx < 0 or idx >= len(settings.blendaz_characters):
            return
        slot = settings.blendaz_characters[idx]
        armature = bpy.data.objects.get(slot.armature_name)
        if not armature:
            return

        # Collect objects that belong to the active character
        char_objs = {armature}
        for child in armature.children:
            char_objs.add(child)
        # Include the face camera so camera view stays valid
        cam_name = slot.camera_face
        if cam_name:
            cam = bpy.data.objects.get(cam_name)
            if cam:
                char_objs.add(cam)

        # Save current selection, select only character objects
        saved_sel = context.selected_objects[:]
        saved_active = context.view_layer.objects.active
        for obj in context.selected_objects:
            obj.select_set(False)
        for obj in char_objs:
            obj.select_set(True)
        context.view_layer.objects.active = armature

        # Enter local view in the PB viewport
        region = None
        for r in pb_area.regions:
            if r.type == 'WINDOW':
                region = r
                break
        if region:
            with context.temp_override(area=pb_area, region=region):
                bpy.ops.view3d.localview(frame_selected=False)

        # Restore selection
        for obj in context.selected_objects:
            obj.select_set(False)
        for obj in saved_sel:
            try:
                obj.select_set(True)
            except ReferenceError:
                pass
        if saved_active:
            try:
                context.view_layer.objects.active = saved_active
            except ReferenceError:
                pass

    def _exit_face_local_view(self, context, pb_space, pb_area):
        """Exit local view in PB viewport when leaving Face mode."""
        if not pb_space.local_view:
            return
        region = None
        for r in pb_area.regions:
            if r.type == 'WINDOW':
                region = r
                break
        if region:
            with context.temp_override(area=pb_area, region=region):
                bpy.ops.view3d.localview(frame_selected=False)

    def execute(self, context):
        settings = context.scene.posebridge_settings
        previous_panel = settings.active_panel
        settings.active_panel = self.view

        show_body  = (self.view == 'body')
        show_hands = (self.view == 'hands')
        show_face  = (self.view == 'face')

        # Switch camera in the PB viewport (not whichever viewport the N-panel is in).
        pb_space, pb_r3d, pb_area = _find_pb_viewport(context)
        # Fall back to context.space_data for first-time setup (no PB viewport yet)
        space = pb_space if pb_space else context.space_data
        r3d = pb_r3d if pb_r3d else (space.region_3d if space and space.type == 'VIEW_3D' else None)

        # Exit face local view BEFORE switching camera (so body/hands
        # cameras become visible in the viewport again).
        if pb_space and pb_area and previous_panel == 'face' and not show_face:
            self._exit_face_local_view(context, pb_space, pb_area)

        if space and space.type == 'VIEW_3D' and r3d:
            # Save state of the view we're leaving
            self._saved_state[previous_panel] = (
                tuple(r3d.view_camera_offset),
                r3d.view_camera_zoom,
            )

            camera_name = self._get_camera_name(context, self.view)
            camera = bpy.data.objects.get(camera_name) if camera_name else None
            if camera:
                space.camera = camera
                r3d.view_perspective = 'CAMERA'

                # Restore saved state for the view we're entering
                if self.view in self._saved_state:
                    saved_offset, saved_zoom = self._saved_state[self.view]
                    r3d.view_camera_offset = saved_offset
                    r3d.view_camera_zoom = saved_zoom

        # Toggle PB object visibility
        active_char_tag = None
        if hasattr(settings, 'blendaz_characters'):
            idx = settings.blendaz_active_index
            if 0 <= idx < len(settings.blendaz_characters):
                active_char_tag = settings.blendaz_characters[idx].char_tag

        for obj in context.scene.objects:
            name = obj.name
            if any(s in name for s in self.BODY_OBJECTS):
                obj.hide_viewport = not show_body
            elif any(s in name for s in self.HANDS_SUBSTR):
                is_active_hands = (not active_char_tag or active_char_tag in name
                                   or name in ('PB_Hand_Left', 'PB_Hand_Right'))
                obj.hide_viewport = not (show_hands and is_active_hands)

        # Face panel: hide all PB_ objects (standin, outlines, hand meshes)
        if show_face:
            for obj in context.scene.objects:
                if obj.name.startswith('PB_') and obj.type != 'CAMERA':
                    obj.hide_viewport = True

        # Enter face local view AFTER camera is set (so the face camera is
        # included in the local view). Only needed with multiple characters.
        if pb_space and pb_area and show_face:
            if hasattr(settings, 'blendaz_characters') and len(settings.blendaz_characters) > 1:
                self._enter_face_local_view(context, settings, pb_space, pb_area)
                # Re-ensure camera mode — localview may snap out of it
                if space and space.type == 'VIEW_3D' and r3d:
                    camera_name = self._get_camera_name(context, self.view)
                    camera = bpy.data.objects.get(camera_name) if camera_name else None
                    if camera:
                        space.camera = camera
                        r3d.view_perspective = 'CAMERA'

        # Redraw both the invoking area and the PB area (may differ)
        if context.area:
            context.area.tag_redraw()
        if pb_area and pb_area != context.area:
            pb_area.tag_redraw()

        return {'FINISHED'}


class BLENDAZ_OT_start_touch(Operator):
    """Start BlenDAZ Touch — activates DAZ Bone Select in this viewport"""
    bl_idname = "blendaz.start_touch"
    bl_label = "Start Touch"

    def execute(self, context):
        try:
            bpy.ops.view3d.daz_bone_select('INVOKE_DEFAULT')
        except Exception as e:
            self.report({'ERROR'}, f"Failed to start Touch: {e}")
            return {'CANCELLED'}

        # Ensure PoseBridge starts deactivated — user opens it in their chosen viewport
        settings = getattr(context.scene, 'posebridge_settings', None)
        if settings:
            settings.is_active = False

        return {'FINISHED'}


class BLENDAZ_OT_stop_blendaz(Operator):
    """Stop BlenDAZ — ends Touch, PoseBridge, and PoseBlend"""
    bl_idname = "blendaz.stop_blendaz"
    bl_label = "Stop BlenDAZ"

    def execute(self, context):
        from .. import daz_bone_select as _dbs
        # Stop Touch (daz_bone_select modal)
        live = getattr(_dbs.VIEW3D_OT_daz_bone_select, '_live_instance', None)
        if live is not None:
            try:
                live.finish(context)
            except ReferenceError:
                # Stale reference — operator class was re-registered
                _dbs.VIEW3D_OT_daz_bone_select._live_instance = None

        # Stop PoseBridge
        settings = getattr(context.scene, 'posebridge_settings', None)
        if settings:
            # Restore drivers/modifiers if Streamline was engaged
            if settings.streamline_enabled:
                from .streamline import apply_streamline
                apply_streamline(False)
                settings.streamline_enabled = False
            settings.is_active = False

        # Unregister PoseBridge draw handler
        from .drawing import PoseBridgeDrawHandler
        PoseBridgeDrawHandler.unregister()

        # Stop PoseBlend
        pb_settings = getattr(context.scene, 'poseblend_settings', None)
        if pb_settings:
            pb_settings.is_active = False

        context.area.tag_redraw()
        return {'FINISHED'}


class POSEBRIDGE_OT_open_in_viewport(Operator):
    """Open PoseBridge panel locked to this viewport"""
    bl_idname = "posebridge.open_in_viewport"
    bl_label = "Open in Viewport"

    def execute(self, context):
        settings = getattr(context.scene, 'posebridge_settings', None)
        if settings is None:
            self.report({'ERROR'}, "PoseBridge not initialized")
            return {'CANCELLED'}

        # Lock to the current viewport using its pointer
        area_ptr = context.area.as_pointer()
        settings.locked_viewport_ptr = area_ptr

        # Lock camera to this viewport immediately
        space = context.space_data
        if space and space.type == 'VIEW_3D':
            # Try per-character camera first, fall back to legacy
            camera_name = None
            if hasattr(settings, 'blendaz_characters'):
                idx = settings.blendaz_active_index
                if 0 <= idx < len(settings.blendaz_characters):
                    slot = settings.blendaz_characters[idx]
                    cam_map = {'body': slot.camera_body, 'hands': slot.camera_hands, 'face': slot.camera_face}
                    camera_name = cam_map.get(settings.active_panel, '')
                    if camera_name and camera_name not in bpy.data.objects:
                        camera_name = None
            if not camera_name:
                camera_name = POSEBRIDGE_OT_set_panel_view.CAMERAS_LEGACY.get(settings.active_panel)
            camera = bpy.data.objects.get(camera_name) if camera_name else None
            if camera:
                space.camera = camera
                space.region_3d.view_perspective = 'CAMERA'

        settings.is_active = True

        # Register PoseBridge draw handler so control points render
        from .drawing import PoseBridgeDrawHandler
        PoseBridgeDrawHandler.register()

        context.area.tag_redraw()
        return {'FINISHED'}


# ============================================================================
# Panel Classes
# ============================================================================

# ----------------------------------------------------------------------------
# Root: BlenDAZ
# ----------------------------------------------------------------------------

class VIEW3D_PT_blendaz_root(Panel):
    """Root BlenDAZ panel"""
    bl_label = "BlenDAZ"
    bl_idname = "VIEW3D_PT_blendaz_root"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'

    def draw(self, context):
        layout = self.layout
        settings = getattr(context.scene, 'posebridge_settings', None)

        # Touch is active when the daz_bone_select modal is running
        from .. import daz_bone_select as _dbs
        live = getattr(_dbs.VIEW3D_OT_daz_bone_select, '_live_instance', None)
        if live is not None:
            try:
                # Probe the instance to detect stale StructRNA references
                _ = live.bl_idname
                touch_active = True
            except ReferenceError:
                _dbs.VIEW3D_OT_daz_bone_select._live_instance = None
                touch_active = False
        else:
            touch_active = False
        pb_active = settings.is_active if settings else False

        row = layout.row()
        row.scale_y = 1.5
        if touch_active or pb_active:
            row.operator("blendaz.stop_blendaz", text="BlenDAZ", icon='PAUSE', depress=True)
        else:
            row.operator("blendaz.start_touch", text="BlenDAZ", icon='POSE_HLT')

        # --- Registered Characters ---
        has_registered = (settings and hasattr(settings, 'blendaz_characters')
                          and len(settings.blendaz_characters) > 0)

        if has_registered:
            layout.separator()
            layout.label(text="Characters:", icon='COMMUNITY')
            active_idx = settings.blendaz_active_index

            for i, slot in enumerate(settings.blendaz_characters):
                is_active = (i == active_idx)
                row = layout.row(align=True)
                if is_active:
                    row.label(text=slot.armature_name, icon='RADIOBUT_ON')
                else:
                    op = row.operator("blendaz.switch_character",
                                      text=slot.armature_name, icon='RADIOBUT_OFF')
                    op.armature_name = slot.armature_name

        # --- Unregistered Characters (from scan) ---
        unreg_names = []
        if settings and settings.blendaz_scanned_unregistered:
            unreg_names = [n for n in settings.blendaz_scanned_unregistered.split(",") if n]

        if unreg_names:
            layout.separator()
            layout.label(text="Unregistered:", icon='QUESTION')
            for name in unreg_names:
                row = layout.row(align=True)
                row.label(text=name, icon='ARMATURE_DATA')
                op = row.operator("blendaz.register_character",
                                  text="Register", icon='ADD')
                op.armature_name = name

        # --- Scan button (always visible) ---
        layout.separator()
        layout.operator("blendaz.scan_characters", text="Scan for Characters", icon='VIEWZOOM')

        # --- Fallback: no characters at all ---
        if not has_registered and not unreg_names:
            layout.separator()
            layout.label(text="No characters registered", icon='INFO')
            layout.label(text="Click 'Scan' to find DAZ rigs")


# ----------------------------------------------------------------------------
# Child of root: BlenDAZ Setup
# ----------------------------------------------------------------------------

class VIEW3D_PT_blendaz_setup(Panel):
    """BlenDAZ character initialisation setup"""
    bl_label = "BlenDAZ Setup"
    bl_idname = "VIEW3D_PT_blendaz_setup"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'
    bl_parent_id = "VIEW3D_PT_blendaz_root"
    bl_options = {'DEFAULT_CLOSED'}

    def _effective_status(self, context):
        settings = context.scene.posebridge_settings
        status = settings.blendaz_init_status
        if status == 'ready' and settings.blendaz_live_mesh_name:
            live_obj = bpy.data.objects.get(settings.blendaz_live_mesh_name)
            if live_obj and len(live_obj.data.polygons) != settings.blendaz_live_mesh_poly_count:
                return 'needs_remap'
        return status

    def draw_header(self, context):
        status = self._effective_status(context)
        icons = {
            'uninitialised': 'RADIOBUT_OFF',
            'snapshot_done': 'TIME',
            'ready':         'CHECKMARK',
            'needs_remap':   'ERROR',
        }
        self.layout.label(icon=icons.get(status, 'RADIOBUT_OFF'))

    def draw(self, context):
        layout = self.layout
        settings = context.scene.posebridge_settings
        status = self._effective_status(context)

        status_labels = {
            'uninitialised': "Not initialised",
            'snapshot_done': "Snapshot saved — merge geografts, then Remap",
            'ready':         "Ready",
            'needs_remap':   "Mesh changed — remap recommended",
        }
        layout.label(text=status_labels.get(status, status))

        layout.separator()

        if status == 'uninitialised':
            layout.operator("blendaz.snapshot_premerge", text="Snapshot Pre-Merge State",
                            icon='OUTLINER_OB_MESH')
            layout.separator()
            layout.operator("blendaz.merge_and_remap", text="Auto Merge + Remap",
                            icon='AUTOMERGE_ON')

        elif status == 'snapshot_done':
            layout.label(text="Merge geografts in Diffeomorphic,")
            layout.label(text="then click Remap below.")
            layout.separator()
            layout.operator("blendaz.remap_face_groups", text="Remap Face Groups",
                            icon='MOD_DATA_TRANSFER')
            layout.separator()
            layout.operator("blendaz.merge_and_remap", text="Auto Merge + Remap",
                            icon='AUTOMERGE_ON')

        elif status in ('ready', 'needs_remap'):
            layout.operator("blendaz.remap_face_groups", text="Re-Remap Face Groups",
                            icon='MOD_DATA_TRANSFER')
            layout.separator()
            layout.operator("blendaz.snapshot_premerge", text="New Snapshot",
                            icon='OUTLINER_OB_MESH')

        if settings.blendaz_reference_mesh_name:
            layout.separator()
            layout.label(text=f"Ref: {settings.blendaz_reference_mesh_name}", icon='MESH_DATA')


# ----------------------------------------------------------------------------
# Child of root: Touch
# ----------------------------------------------------------------------------

class VIEW3D_PT_touch(Panel):
    """Touch settings — sensitivity, constraints, rotation limits, IK"""
    bl_label = "Touch"
    bl_idname = "VIEW3D_PT_touch"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'
    bl_parent_id = "VIEW3D_PT_blendaz_root"

    def draw(self, context):
        layout = self.layout
        settings = getattr(context.scene, 'posebridge_settings', None)
        blendaz_props = getattr(context.scene, 'blendaz_props', None)

        if settings:
            layout.prop(settings, "sensitivity", text="Rotation Sensitivity", slider=True)
            layout.prop(settings, "morph_sensitivity", text="Morph Sensitivity", slider=True)
            layout.prop(settings, "highlight_opacity", text="Highlight Opacity", slider=True)
            layout.separator()
            layout.prop(settings, "enforce_constraints", text="Enforce Constraints")
            layout.prop(settings, "auto_keyframe", text="Auto Keyframe")

        if blendaz_props:
            layout.separator()

            # Rotation Limits
            box = layout.box()
            box.label(text="Rotation Limits", icon='CON_ROTLIMIT')
            box.prop(blendaz_props, "enable_rotation_limits", text="Enable Limits")
            row = box.row(align=True)
            op = row.operator("blendaz.update_rotation_limits", text="Update", icon='FILE_REFRESH')
            op.force_update = False
            op = row.operator("blendaz.update_rotation_limits", text="Force", icon='RECOVER_LAST')
            op.force_update = True
            box.operator("blendaz.clear_rotation_limits", text="Clear All Limits", icon='X')

            layout.separator()

            # IK Settings
            box = layout.box()
            box.label(text="IK Settings", icon='CON_KINEMATIC')
            box.prop(blendaz_props, "ik_chain_length", text="Chain Length")
            box.prop(blendaz_props, "use_ik_templates", text="Use Templates")
            box.prop(blendaz_props, "enable_prebend", text="Pre-bend")

        # Streamline (performance mode)
        if settings:
            layout.separator()
            box = layout.box()
            row = box.row()
            row.prop(settings, "streamline_enabled", text="Streamline", icon='MOD_SIMPLIFY')
            if settings.streamline_enabled:
                col = box.column(align=True)
                col.prop(settings, "streamline_blender_simplify")
                col.prop(settings, "streamline_drivers")
                col.prop(settings, "streamline_shape_keys")
                col.prop(settings, "streamline_modifiers")
                col.prop(settings, "streamline_physics")
                col.prop(settings, "streamline_normals")
                col.prop(settings, "streamline_meshes")
            # Select Meshes always available (configure before enabling)
            if len(settings.blendaz_characters) > 0:
                row = box.row(align=True)
                row.operator("blendaz.select_streamline_meshes",
                             text="Select Meshes...", icon='MESH_DATA')
                idx = settings.blendaz_active_index
                if 0 <= idx < len(settings.blendaz_characters):
                    muted = settings.blendaz_characters[idx].get_muted_meshes_list()
                    if muted:
                        row.label(text=f"({len(muted)})")


# ----------------------------------------------------------------------------
# Child of root: PoseBridge
# ----------------------------------------------------------------------------

class VIEW3D_PT_posebridge(Panel):
    """PoseBridge panel — viewport, panel view switcher, display options"""
    bl_label = "PoseBridge"
    bl_idname = "VIEW3D_PT_posebridge"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'

    def draw_header(self, context):
        settings = getattr(context.scene, 'posebridge_settings', None)
        if settings and settings.is_active:
            self.layout.label(icon='PLAY')

    def draw(self, context):
        layout = self.layout
        settings = getattr(context.scene, 'posebridge_settings', None)

        # PoseBridge activate button
        row = layout.row()
        row.scale_y = 1.5
        if settings and settings.is_active:
            row.operator("posebridge.open_in_viewport", text="PoseBridge", icon='PAUSE', depress=True)
        else:
            row.operator("posebridge.open_in_viewport", text="PoseBridge", icon='SCREEN_BACK')

        layout.separator()

        if settings:
            # Panel view switcher: Body / Hands / Face
            row = layout.row(align=True)
            op = row.operator("posebridge.set_panel_view", text="Body",
                              depress=(settings.active_panel == 'body'))
            op.view = 'body'
            op = row.operator("posebridge.set_panel_view", text="Hands",
                              depress=(settings.active_panel == 'hands'))
            op.view = 'hands'
            op = row.operator("posebridge.set_panel_view", text="Face",
                              depress=(settings.active_panel == 'face'))
            op.view = 'face'

            # Control point count
            cp_count = len(settings.control_points_fixed)
            if cp_count > 0:
                body_count = sum(1 for cp in settings.control_points_fixed
                                 if not cp.panel_view or cp.panel_view == 'body')
                hand_count = sum(1 for cp in settings.control_points_fixed
                                 if cp.panel_view == 'hands')
                face_count = sum(1 for cp in settings.control_points_fixed
                                 if cp.panel_view == 'face')
                parts = [f"{body_count} body", f"{hand_count} hands"]
                if face_count > 0:
                    parts.append(f"{face_count} face")
                layout.label(text=f"CPs: {', '.join(parts)}")

            layout.separator()

            # Display options
            row = layout.row(align=True)
            row.prop(settings, "show_outline", text="Outline", toggle=True)
            row.prop(settings, "show_control_points", text="CPs", toggle=True)


# ----------------------------------------------------------------------------
# Child of PoseBridge: Body Controls  [DEFAULT_CLOSED]
# ----------------------------------------------------------------------------

class VIEW3D_PT_posebridge_body(Panel):
    """Body Controls — reset pose and pins"""
    bl_label = "Body Controls"
    bl_idname = "VIEW3D_PT_posebridge_body"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'
    bl_parent_id = "VIEW3D_PT_posebridge"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.scale_y = 1.4
        row.operator("pose.body_reset", text="Reset Pose", icon='LOOP_BACK')

        layout.separator()

        layout.operator("blendaz.clear_all_pins", text="Clear All Pins", icon='UNPINNED')


# ----------------------------------------------------------------------------
# Child of PoseBridge: Face Controls  [DEFAULT_CLOSED]
# ----------------------------------------------------------------------------

class VIEW3D_PT_posebridge_face(Panel):
    """Face Controls — expressions and visemes"""
    bl_label = "Face Controls"
    bl_idname = "VIEW3D_PT_posebridge_face"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'
    bl_parent_id = "VIEW3D_PT_posebridge"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        # Delegate to the face panel draw logic that lives in daz_bone_select
        # (imports FACE_EXPRESSION_SLIDERS, FACE_VISEME_SLIDERS, _get_posebridge_armature)
        from .. import daz_bone_select as _dbs

        armature = _dbs._get_posebridge_armature(context)
        if not armature:
            layout.label(text="No armature found", icon='ERROR')
            return

        has_facs = any(k.startswith('facs_') for k in armature.keys() if isinstance(k, str))
        if not has_facs:
            layout.label(text="No FACS morphs loaded", icon='INFO')
            layout.label(text="Import morphs via Diffeomorphic")
            return

        settings = getattr(context.scene, 'posebridge_settings', None)
        if not settings:
            layout.label(text="PoseBridge not initialized", icon='ERROR')
            return

        row = layout.row()
        row.scale_y = 1.4
        row.operator("pose.face_reset", text="Reset Face", icon='LOOP_BACK')

        layout.separator()

        box = layout.box()
        box.label(text="Expressions", icon='MONKEY')
        for prop_id, label in _dbs.FACE_EXPRESSION_SLIDERS:
            box.prop(settings, prop_id, text=label, slider=True)

        layout.separator()

        box = layout.box()
        box.label(text="Visemes", icon='PLAY_SOUND')
        for prop_id, label in _dbs.FACE_VISEME_SLIDERS:
            box.prop(settings, prop_id, text=label, slider=True)


# ----------------------------------------------------------------------------
# Child of PoseBridge: Settings  [DEFAULT_CLOSED]
# ----------------------------------------------------------------------------

class VIEW3D_PT_posebridge_settings(Panel):
    """PoseBridge settings and preferences"""
    bl_label = "Settings"
    bl_idname = "VIEW3D_PT_posebridge_settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'
    bl_parent_id = "VIEW3D_PT_posebridge"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = getattr(context.scene, 'posebridge_settings', None)
        if not settings:
            return

        layout.prop(settings, "show_outline", text="Show Outline")
        layout.prop(settings, "show_control_points", text="Show Control Points")

        layout.separator()

        layout.prop(settings, "sensitivity", text="Rotation Sensitivity", slider=True)
        layout.prop(settings, "morph_sensitivity", text="Morph Sensitivity", slider=True)
        layout.prop(settings, "highlight_opacity", text="Highlight Opacity", slider=True)

        layout.separator()

        layout.prop(settings, "enforce_constraints", text="Enforce Constraints")
        layout.prop(settings, "auto_keyframe", text="Auto Keyframe")


# ============================================================================
# Streamline Mesh Selection
# ============================================================================

class STREAMLINE_MeshItem(PropertyGroup):
    """Single mesh entry for the Streamline mesh selection popup."""
    mesh_name: bpy.props.StringProperty(default="")
    vertex_count: bpy.props.IntProperty(default=0)
    selected: bpy.props.BoolProperty(default=False)


class BLENDAZ_OT_select_streamline_meshes(Operator):
    """Select which child meshes to hide during Streamline"""
    bl_idname = "blendaz.select_streamline_meshes"
    bl_label = "Select Meshes to Mute"
    bl_options = {'REGISTER', 'INTERNAL'}

    mesh_items: bpy.props.CollectionProperty(type=STREAMLINE_MeshItem)

    # Meshes with vertex count >= this are pre-checked on first use
    _AUTO_CHECK_THRESHOLD = 5000

    def invoke(self, context, event):
        self.mesh_items.clear()

        settings = context.scene.posebridge_settings
        idx = settings.blendaz_active_index
        if idx < 0 or idx >= len(settings.blendaz_characters):
            self.report({'WARNING'}, "No active character")
            return {'CANCELLED'}

        slot = settings.blendaz_characters[idx]
        armature = bpy.data.objects.get(slot.armature_name)
        if not armature:
            self.report({'WARNING'}, f"Armature '{slot.armature_name}' not found")
            return {'CANCELLED'}

        body_mesh_name = slot.body_mesh_name
        existing_selection = set(slot.get_muted_meshes_list())
        has_existing = len(existing_selection) > 0

        # Scan child meshes (exclude internal BlenDAZ copies)
        _EXCLUDE_SUFFIXES = ('_Standin', '_LineArt_Copy', '_LineArt')
        children = [
            c for c in armature.children
            if c.type == 'MESH' and not c.name.endswith(_EXCLUDE_SUFFIXES)
        ]

        # Sort: body mesh first, then by vertex count descending
        children.sort(key=lambda c: (c.name != body_mesh_name, -len(c.data.vertices)))

        for child in children:
            item = self.mesh_items.add()
            item.mesh_name = child.name
            item.vertex_count = len(child.data.vertices)

            if has_existing:
                item.selected = child.name in existing_selection
            else:
                # First time: auto-check non-body meshes above threshold
                is_body = (child.name == body_mesh_name)
                item.selected = (not is_body
                                 and item.vertex_count >= self._AUTO_CHECK_THRESHOLD)

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select meshes to hide during Streamline:", icon='MOD_SIMPLIFY')
        layout.separator()

        settings = context.scene.posebridge_settings
        idx = settings.blendaz_active_index
        body_name = ""
        if 0 <= idx < len(settings.blendaz_characters):
            body_name = settings.blendaz_characters[idx].body_mesh_name

        col = layout.column(align=True)
        for item in self.mesh_items:
            row = col.row(align=True)
            row.prop(item, "selected", text="")
            label = item.mesh_name
            if item.mesh_name == body_name:
                label += "  [BODY]"
            row.label(text=f"{label}  ({item.vertex_count:,} verts)")

    def execute(self, context):
        settings = context.scene.posebridge_settings
        idx = settings.blendaz_active_index
        if idx < 0 or idx >= len(settings.blendaz_characters):
            return {'CANCELLED'}

        slot = settings.blendaz_characters[idx]
        selected_names = [item.mesh_name for item in self.mesh_items if item.selected]
        slot.set_muted_meshes_list(selected_names)

        self.report({'INFO'}, f"Streamline: {len(selected_names)} meshes selected for muting")

        # If Streamline is currently engaged, re-apply immediately
        if settings.streamline_enabled:
            from .streamline import apply_streamline
            apply_streamline(
                True,
                mute_drivers=settings.streamline_drivers,
                mute_shape_keys=settings.streamline_shape_keys,
                disable_modifiers=settings.streamline_modifiers,
                disable_physics=settings.streamline_physics,
                disable_normals_auto_smooth=settings.streamline_normals,
                blender_simplify=settings.streamline_blender_simplify,
                mute_armature_meshes=settings.streamline_meshes,
            )

        return {'FINISHED'}


# ============================================================================
# Registration
# ============================================================================

classes = (
    STREAMLINE_MeshItem,
    BLENDAZ_OT_select_streamline_meshes,
    BLENDAZ_OT_switch_character,
    BLENDAZ_OT_scan_characters,
    BLENDAZ_OT_register_character,
    POSEBRIDGE_OT_set_panel_view,
    BLENDAZ_OT_start_touch,
    BLENDAZ_OT_stop_blendaz,
    POSEBRIDGE_OT_open_in_viewport,
    VIEW3D_PT_blendaz_root,
    VIEW3D_PT_blendaz_setup,
    VIEW3D_PT_touch,
    VIEW3D_PT_posebridge,
    VIEW3D_PT_posebridge_body,
    VIEW3D_PT_posebridge_face,
    VIEW3D_PT_posebridge_settings,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
