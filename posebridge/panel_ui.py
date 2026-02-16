"""PoseBridge Panel UI - Blender N-panel interface"""

import bpy
from bpy.types import Panel

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

        # TODO: Implement panel UI
        # Mode toggle, sensitivity slider, etc.
        layout.label(text="PoseBridge controls here")

class VIEW3D_PT_posebridge_panel_selector(Panel):
    """Panel view thumbnail selector"""
    bl_label = "Panel Views"
    bl_idname = "VIEW3D_PT_posebridge_panel_selector"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'
    bl_parent_id = "VIEW3D_PT_posebridge_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        # TODO: Implement panel selector
        pass

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
        # TODO: Implement settings panel
        pass

# ============================================================================
# Registration
# ============================================================================

classes = (
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
