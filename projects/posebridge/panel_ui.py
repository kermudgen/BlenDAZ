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
from bpy.types import Panel, Operator

# DAZ marker bones used to identify DAZ rigs
_DAZ_MARKER_BONES = {'lPectoral', 'rPectoral', 'lCollar', 'rCollar'}


# ============================================================================
# Operators
# ============================================================================

class BLENDAZ_OT_switch_character(Operator):
    """Switch BlenDAZ to a different registered character"""
    bl_idname = "blendaz.switch_character"
    bl_label = "Switch Character"

    armature_name: bpy.props.StringProperty()

    def execute(self, context):
        import daz_bone_select as _dbs
        live = getattr(_dbs.VIEW3D_OT_daz_bone_select, '_live_instance', None)
        if live:
            if live._switch_active_character(context, self.armature_name):
                context.area.tag_redraw()
                return {'FINISHED'}
        # Fallback: just update settings (modal not running)
        settings = getattr(context.scene, 'posebridge_settings', None)
        if settings:
            for i, slot in enumerate(settings.blendaz_characters):
                if slot.armature_name == self.armature_name:
                    settings.blendaz_active_index = i
                    settings.active_armature_name = self.armature_name
                    break
            context.area.tag_redraw()
        return {'FINISHED'}


class BLENDAZ_OT_scan_characters(Operator):
    """Scan scene for DAZ armatures"""
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

        if found:
            msg = ", ".join(f"{name} ({tag})" for name, tag in found)
            self.report({'INFO'}, f"Found {len(found)} DAZ rig(s): {msg}")
        else:
            self.report({'WARNING'}, "No DAZ armatures found in scene")

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

    # Objects shown in each panel view
    BODY_OBJECTS  = {'PB_Outline', '_LineArt_Copy'}   # substring match
    HANDS_OBJECTS = {'PB_Hand_Left', 'PB_Hand_Right'} # exact match

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

    def execute(self, context):
        settings = context.scene.posebridge_settings
        previous_panel = settings.active_panel
        settings.active_panel = self.view

        # Switch camera in the viewport where the N-panel was clicked
        space = context.space_data
        if space and space.type == 'VIEW_3D':
            r3d = space.region_3d

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

        # Toggle object visibility
        show_body  = (self.view == 'body')
        show_hands = (self.view == 'hands')
        show_face  = (self.view == 'face')

        for obj in context.scene.objects:
            name = obj.name
            if any(s in name for s in self.BODY_OBJECTS):
                obj.hide_viewport = not show_body
            elif name in self.HANDS_OBJECTS:
                obj.hide_viewport = not show_hands

        # Face panel: hide all PB_ objects (standin, outlines, hand meshes)
        # Character mesh stays visible for live face preview
        if show_face:
            for obj in context.scene.objects:
                if obj.name.startswith('PB_') and obj.type != 'CAMERA':
                    obj.hide_viewport = True

        context.area.tag_redraw()

        return {'FINISHED'}


class BLENDAZ_OT_start_touch(Operator):
    """Start BlenDAZ Touch — activates DAZ Bone Select in this viewport"""
    bl_idname = "blendaz.start_touch"
    bl_label = "Start Touch"

    def execute(self, context):
        try:
            bpy.ops.view3d.daz_bone_select('INVOKE_DEFAULT')
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to start Touch: {e}")
            return {'CANCELLED'}


class BLENDAZ_OT_stop_blendaz(Operator):
    """Stop BlenDAZ — ends Touch, PoseBridge, and PoseBlend"""
    bl_idname = "blendaz.stop_blendaz"
    bl_label = "Stop BlenDAZ"

    def execute(self, context):
        import daz_bone_select as _dbs
        # Stop Touch (daz_bone_select modal)
        live = getattr(_dbs.VIEW3D_OT_daz_bone_select, '_live_instance', None)
        if live is not None:
            live.finish(context)

        # Stop PoseBridge
        settings = getattr(context.scene, 'posebridge_settings', None)
        if settings:
            settings.is_active = False

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
            camera_name = POSEBRIDGE_OT_set_panel_view.CAMERAS.get(settings.active_panel)
            camera = bpy.data.objects.get(camera_name) if camera_name else None
            if camera:
                space.camera = camera
                space.region_3d.view_perspective = 'CAMERA'

        settings.is_active = True
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
        import daz_bone_select as _dbs
        touch_active = getattr(_dbs.VIEW3D_OT_daz_bone_select, '_live_instance', None) is not None
        pb_active = settings.is_active if settings else False

        row = layout.row()
        row.scale_y = 1.5
        if touch_active or pb_active:
            row.operator("blendaz.stop_blendaz", text="BlenDAZ", icon='PAUSE', depress=True)
        else:
            row.operator("blendaz.start_touch", text="BlenDAZ", icon='POSE_HLT')

        # --- Registered Characters ---
        if settings and hasattr(settings, 'blendaz_characters') and len(settings.blendaz_characters) > 0:
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

            layout.separator()
            layout.operator("blendaz.scan_characters", text="Scan for Characters", icon='VIEWZOOM')
        else:
            # No characters registered — show single armature info (legacy)
            armature = context.active_object if (
                context.active_object and context.active_object.type == 'ARMATURE'
            ) else None
            arm_name = (
                settings.active_armature_name if (settings and settings.active_armature_name)
                else (armature.name if armature else "")
            )

            if arm_name:
                layout.label(text=f"Figure: {arm_name}", icon='ARMATURE_DATA')
            else:
                layout.label(text="No armature selected", icon='ERROR')

            layout.separator()
            layout.operator("blendaz.scan_characters", text="Scan for Characters", icon='VIEWZOOM')


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
        import daz_bone_select as _dbs

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
# Registration
# ============================================================================

classes = (
    BLENDAZ_OT_switch_character,
    BLENDAZ_OT_scan_characters,
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
