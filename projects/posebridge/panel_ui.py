"""PoseBridge Panel UI - Blender N-panel interface"""

import bpy
from bpy.types import Panel, Operator

# ============================================================================
# Operators
# ============================================================================

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

    # Camera names for each panel view
    CAMERAS = {
        'body':  'PB_Outline_LineArt_Camera',
        'hands': 'PB_Camera_Hands',
        'face':  'PB_Camera_Face',
    }

    # Objects shown in each panel view
    BODY_OBJECTS  = {'PB_Outline', '_LineArt_Copy'}   # substring match
    HANDS_OBJECTS = {'PB_Hand_Left', 'PB_Hand_Right'} # exact match

    # Saved camera state per view: {view_name: (offset, zoom)}
    _saved_state = {}

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

            camera_name = self.CAMERAS.get(self.view)
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

        for obj in context.scene.objects:
            name = obj.name
            if any(s in name for s in self.BODY_OBJECTS):
                obj.hide_viewport = not show_body
            elif name in self.HANDS_OBJECTS:
                obj.hide_viewport = not show_hands

        context.area.tag_redraw()

        return {'FINISHED'}


# ============================================================================
# Panel Classes
# ============================================================================

class VIEW3D_PT_posebridge_main(Panel):
    """Main PoseBridge panel in N-panel sidebar"""
    bl_label = "PoseBridge Editor"
    bl_idname = "VIEW3D_PT_posebridge_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.posebridge_settings

        # Mode status
        row = layout.row()
        if settings.is_active:
            row.label(text="Mode: ACTIVE", icon='PLAY')
        else:
            row.label(text="Mode: Inactive", icon='PAUSE')

        # Active armature
        if settings.active_armature_name:
            layout.label(text=f"Figure: {settings.active_armature_name}")

        # Control point count
        cp_count = len(settings.control_points_fixed)
        if cp_count > 0:
            body_count = sum(1 for cp in settings.control_points_fixed if not cp.panel_view or cp.panel_view == 'body')
            hand_count = sum(1 for cp in settings.control_points_fixed if cp.panel_view == 'hands')
            layout.label(text=f"Control Points: {body_count} body, {hand_count} hands")


class VIEW3D_PT_posebridge_panel_selector(Panel):
    """Panel view thumbnail selector"""
    bl_label = "Panel Views"
    bl_idname = "VIEW3D_PT_posebridge_panel_selector"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'
    bl_parent_id = "VIEW3D_PT_posebridge_main"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.posebridge_settings

        # View selector buttons
        row = layout.row(align=True)

        # Body button
        op = row.operator("posebridge.set_panel_view", text="Body",
                         depress=(settings.active_panel == 'body'))
        op.view = 'body'

        # Hands button
        op = row.operator("posebridge.set_panel_view", text="Hands",
                         depress=(settings.active_panel == 'hands'))
        op.view = 'hands'

        # Face button (disabled for now)
        sub = row.row(align=True)
        sub.enabled = False
        op = sub.operator("posebridge.set_panel_view", text="Face")
        op.view = 'face'

        # Show current view
        layout.label(text=f"Current: {settings.active_panel.title()}")


class VIEW3D_PT_posebridge_settings(Panel):
    """PoseBridge settings and preferences"""
    bl_label = "Settings"
    bl_idname = "VIEW3D_PT_posebridge_settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'
    bl_parent_id = "VIEW3D_PT_posebridge_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.posebridge_settings

        # Display toggles
        layout.prop(settings, "show_outline", text="Show Outline")
        layout.prop(settings, "show_control_points", text="Show Control Points")

        layout.separator()

        # Sensitivity slider
        layout.prop(settings, "sensitivity", text="Rotation Sensitivity", slider=True)

        layout.separator()

        # Posing options
        layout.prop(settings, "enforce_constraints", text="Enforce Constraints")
        layout.prop(settings, "auto_keyframe", text="Auto Keyframe")


# ============================================================================
# Registration
# ============================================================================

classes = (
    POSEBRIDGE_OT_set_panel_view,
    VIEW3D_PT_posebridge_main,
    VIEW3D_PT_posebridge_panel_selector,
    VIEW3D_PT_posebridge_settings,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
