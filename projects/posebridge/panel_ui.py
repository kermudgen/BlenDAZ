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

    def execute(self, context):
        settings = context.scene.posebridge_settings
        settings.active_panel = self.view

        # Switch camera based on view
        if self.view == 'body':
            camera_name = "PB_Camera"
        elif self.view == 'hands':
            camera_name = "PB_Camera_Hands"
        elif self.view == 'face':
            camera_name = "PB_Camera_Face"
        else:
            camera_name = None

        if camera_name and camera_name in bpy.data.objects:
            # Set active camera for all 3D viewports
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.camera = bpy.data.objects[camera_name]
                            # If in camera view, update
                            if space.region_3d.view_perspective == 'CAMERA':
                                space.region_3d.view_camera_offset = (0, 0)

        # Force viewport redraw
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

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

        # Sensitivity
        layout.prop(settings, "sensitivity", text="Rotation Sensitivity")

        # Auto keyframe
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
