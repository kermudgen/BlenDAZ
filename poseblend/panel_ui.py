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

"""PoseBlend Panel UI - N-panel interface and controls"""

import bpy
from bpy.types import Panel, Operator, UIList



# ============================================================================
# Main Panel
# ============================================================================

class VIEW3D_PT_poseblend_main(Panel):
    """Main PoseBlend panel in N-panel sidebar"""
    bl_label = "PoseBlend"
    bl_idname = "VIEW3D_PT_poseblend_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.poseblend_settings

        # Single toggle button
        row = layout.row(align=True)
        row.scale_y = 1.5

        if settings.is_active:
            row.operator("poseblend.deactivate", text="PoseBlend", icon='PAUSE', depress=True)
        else:
            row.operator("poseblend.activate", text="PoseBlend", icon='POSE_HLT')

        if not settings.is_active:
            return

        layout.separator()

        # Armature selection
        box = layout.box()
        box.label(text="Armature:", icon='ARMATURE_DATA')
        box.prop_search(settings, "active_armature_name", bpy.data, "objects", text="")

        layout.separator()

        # Grid selection
        box = layout.box()
        row = box.row()
        row.label(text="Grids:", icon='MESH_GRID')
        row.operator("poseblend.add_grid", text="", icon='ADD')

        if settings.grids:
            box.template_list(
                "POSEBLEND_UL_grids", "",
                settings, "grids",
                settings, "active_grid_index",
                rows=3
            )

            grid = settings.get_active_grid()
            if grid:
                # Lock toggle - prominent placement
                lock_row = box.row()
                lock_row.scale_y = 1.3
                if grid.is_locked:
                    lock_row.operator("poseblend.toggle_lock", text="Unlock Grid", icon='LOCKED', depress=True)
                else:
                    lock_row.operator("poseblend.toggle_lock", text="Lock Grid", icon='UNLOCKED')

                box.separator()

                # Grid bone mask (what body parts this grid controls)
                col = box.column(align=True)
                col.label(text="Affects:", icon='BONE_DATA')
                col.prop(grid, "bone_mask_mode", text="")
                if grid.bone_mask_mode == 'PRESET':
                    col.prop(grid, "bone_mask_preset", text="")

                box.separator()

                # Grid visual settings
                col = box.column(align=True)
                col.prop(grid, "name", text="Name")
                col.prop(grid, "grid_divisions", text="Divisions")
                row = col.row(align=True)
                row.prop(grid, "snap_to_grid", text="Snap", toggle=True)
                row.prop(grid, "show_grid_lines", text="Lines", toggle=True)


# ============================================================================
# Dots Panel
# ============================================================================

class VIEW3D_PT_poseblend_dots(Panel):
    """Dots management panel"""
    bl_label = "Pose Dots"
    bl_idname = "VIEW3D_PT_poseblend_dots"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'
    bl_parent_id = "VIEW3D_PT_poseblend_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        settings = context.scene.poseblend_settings
        return settings.is_active and settings.get_active_grid() is not None

    def draw(self, context):
        layout = self.layout
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()

        if not grid:
            return

        # Dots list
        row = layout.row()
        row.template_list(
            "POSEBLEND_UL_dots", "",
            grid, "dots",
            grid, "active_dot_index",
            rows=4
        )

        # Dot controls
        col = row.column(align=True)
        col.operator("poseblend.add_dot", text="", icon='ADD')
        col.operator("poseblend.delete_dot", text="", icon='REMOVE')
        col.separator()
        col.operator("poseblend.duplicate_dot", text="", icon='DUPLICATE')

        # Active dot properties
        dot = grid.get_active_dot()
        if dot:
            box = layout.box()
            box.label(text="Dot Properties:", icon='DOT')

            col = box.column(align=True)
            col.prop(dot, "name", text="Name")
            col.prop(dot, "position", text="Position")
            col.prop(dot, "color", text="Color")

            col.separator()
            col.label(text="Bone Mask:")
            col.prop(dot, "bone_mask_mode", text="Mode")

            if dot.bone_mask_mode == 'PRESET':
                col.prop(dot, "bone_mask_preset", text="Preset")


# ============================================================================
# Settings Panel
# ============================================================================

class VIEW3D_PT_poseblend_settings(Panel):
    """PoseBlend settings panel"""
    bl_label = "Settings"
    bl_idname = "VIEW3D_PT_poseblend_settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'
    bl_parent_id = "VIEW3D_PT_poseblend_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.scene.poseblend_settings.is_active

    def draw(self, context):
        layout = self.layout
        settings = context.scene.poseblend_settings

        # Grid overlay positioning
        box = layout.box()
        box.label(text="Grid Overlay:", icon='WINDOW')
        col = box.column(align=True)
        col.prop(settings, "grid_screen_position", text="Position")
        col.prop(settings, "grid_screen_size", text="Size", slider=True)
        col.prop(settings, "grid_zoom", text="Zoom", slider=True)

        layout.separator()

        # Interaction settings
        col = layout.column(align=True)
        col.label(text="Interaction:", icon='HAND')
        col.prop(settings, "preview_mode", text="Preview")
        col.prop(settings, "auto_keyframe", text="Auto Keyframe")

        layout.separator()

        # Blending algorithm
        col = layout.column(align=True)
        col.label(text="Blending:", icon='SMOOTHCURVE')
        col.prop(settings, "blend_falloff", text="Falloff")
        col.prop(settings, "blend_radius", text="Max Radius", slider=True)
        col.prop(settings, "extrapolation_max", text="Extrapolation", slider=True)


# ============================================================================
# Import/Export Panel
# ============================================================================

class VIEW3D_PT_poseblend_io(Panel):
    """Import/Export panel"""
    bl_label = "Import / Export"
    bl_idname = "VIEW3D_PT_poseblend_io"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'
    bl_parent_id = "VIEW3D_PT_poseblend_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.scene.poseblend_settings.is_active

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.operator("poseblend.export_grid", text="Export Grid", icon='EXPORT')
        col.operator("poseblend.import_grid", text="Import Grid", icon='IMPORT')


# ============================================================================
# UI Lists
# ============================================================================

class POSEBLEND_UL_grids(UIList):
    """Grid list UI"""
    bl_idname = "POSEBLEND_UL_grids"

    def draw_item(self, context, layout, data, item, icon, active_data, active_property):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)

            # Lock indicator
            lock_icon = 'LOCKED' if item.is_locked else 'UNLOCKED'
            row.label(text="", icon=lock_icon)

            # Grid name
            row.prop(item, "name", text="", emboss=False)

            # Bone mask indicator (abbreviated)
            if item.bone_mask_mode == 'ALL':
                row.label(text="Body")
            else:
                # Show abbreviated preset name
                preset_short = {
                    'HEAD': 'Head',
                    'FACE': 'Face',
                    'UPPER_BODY': 'Upper',
                    'LOWER_BODY': 'Lower',
                    'ARMS': 'Arms',
                    'HANDS': 'Hands',
                    'LEGS': 'Legs',
                    'SPINE': 'Spine',
                }.get(item.bone_mask_preset, item.bone_mask_preset)
                row.label(text=preset_short)

            # Dot count
            row.label(text=f"({len(item.dots)})")

        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='MESH_GRID')


class POSEBLEND_UL_dots(UIList):
    """Dot list UI"""
    bl_idname = "POSEBLEND_UL_dots"

    def draw_item(self, context, layout, data, item, icon, active_data, active_property):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Color indicator
            row = layout.row(align=True)
            row.prop(item, "color", text="", icon='DOT')
            row.prop(item, "name", text="", emboss=False)

            # Mask indicator
            if item.bone_mask_mode == 'ALL':
                row.label(text="All")
            elif item.bone_mask_mode == 'PRESET':
                row.label(text=item.bone_mask_preset)
            else:
                row.label(text="Custom")

        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='DOT')


# ============================================================================
# Operators
# ============================================================================

class POSEBLEND_OT_activate(Operator):
    """Activate PoseBlend mode"""
    bl_idname = "poseblend.activate"
    bl_label = "Activate PoseBlend"

    def execute(self, context):
        settings = context.scene.poseblend_settings
        settings.is_active = True

        # Register draw handler — only in this viewport
        from .drawing import PoseBlendDrawHandler
        PoseBlendDrawHandler._target_area_ptr = context.area.as_pointer()
        PoseBlendDrawHandler.register_handler()

        # Auto-select armature if one is selected
        if context.active_object and context.active_object.type == 'ARMATURE':
            settings.active_armature_name = context.active_object.name

        # Create default grid if none exists
        if len(settings.grids) == 0:
            settings.add_grid("Body Poses")

        # Start the modal operator in this viewport
        bpy.ops.poseblend.interact('INVOKE_DEFAULT')

        self.report({'INFO'}, "PoseBlend activated")
        context.area.tag_redraw()
        return {'FINISHED'}


class POSEBLEND_OT_deactivate(Operator):
    """Deactivate PoseBlend mode"""
    bl_idname = "poseblend.deactivate"
    bl_label = "Deactivate PoseBlend"

    def execute(self, context):
        settings = context.scene.poseblend_settings
        settings.is_active = False

        # Unregister draw handler and clear target area
        from .drawing import PoseBlendDrawHandler
        PoseBlendDrawHandler._target_area_ptr = None
        PoseBlendDrawHandler.unregister_handler()

        self.report({'INFO'}, "PoseBlend deactivated")
        context.area.tag_redraw()
        return {'FINISHED'}


class POSEBLEND_OT_add_grid(Operator):
    """Add a new pose grid"""
    bl_idname = "poseblend.add_grid"
    bl_label = "Add Grid"

    name: bpy.props.StringProperty(name="Name", default="")

    template: bpy.props.EnumProperty(
        name="Template",
        description="Grid template with preset bone mask",
        items=[
            ('FULL_BODY', 'Full Body Poses', 'All bones - general posing'),
            ('EXPRESSIONS', 'Facial Expressions', 'Head and face bones'),
            ('UPPER_BODY', 'Upper Body', 'Torso, arms, and hands'),
            ('LOWER_BODY', 'Lower Body', 'Hips, legs, and feet'),
            ('HAND_GESTURES', 'Hand Gestures', 'Finger poses'),
            ('CUSTOM', 'Custom', 'Configure manually'),
        ],
        default='FULL_BODY'
    )

    def invoke(self, context, event):
        # Set default name based on template
        self.name = ""
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "template")
        layout.separator()
        layout.prop(self, "name", text="Name (optional)")

    def execute(self, context):
        settings = context.scene.poseblend_settings

        # Determine name and settings from template
        template_config = {
            'FULL_BODY': ('Body Poses', 'ALL', 'HEAD'),
            'EXPRESSIONS': ('Expressions', 'PRESET', 'HEAD'),
            'UPPER_BODY': ('Upper Body', 'PRESET', 'UPPER_BODY'),
            'LOWER_BODY': ('Lower Body', 'PRESET', 'LOWER_BODY'),
            'HAND_GESTURES': ('Hand Gestures', 'PRESET', 'HANDS'),
            'CUSTOM': ('Custom Grid', 'ALL', 'HEAD'),
        }

        default_name, mask_mode, mask_preset = template_config.get(
            self.template, ('New Grid', 'ALL', 'HEAD')
        )

        # Use custom name if provided, otherwise template default
        grid_name = self.name if self.name else default_name

        # Create grid
        grid = settings.add_grid(grid_name)
        grid.bone_mask_mode = mask_mode
        grid.bone_mask_preset = mask_preset

        # Set appropriate grid divisions
        if self.template in ('EXPRESSIONS', 'HAND_GESTURES'):
            grid.grid_divisions = (6, 6)
        else:
            grid.grid_divisions = (8, 8)

        self.report({'INFO'}, f"Created grid: {grid_name}")
        return {'FINISHED'}


class POSEBLEND_OT_toggle_lock(Operator):
    """Toggle grid lock state for animation mode"""
    bl_idname = "poseblend.toggle_lock"
    bl_label = "Toggle Grid Lock"

    def execute(self, context):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()

        if grid:
            grid.is_locked = not grid.is_locked
            state = "locked" if grid.is_locked else "unlocked"
            self.report({'INFO'}, f"Grid {state} - {'blend only' if grid.is_locked else 'can edit dots'}")

        return {'FINISHED'}


class POSEBLEND_OT_add_dot(Operator):
    """Add a new pose dot from current pose"""
    bl_idname = "poseblend.add_dot"
    bl_label = "Add Dot"

    name: bpy.props.StringProperty(name="Name", default="New Pose")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        armature = bpy.data.objects.get(settings.active_armature_name)

        if not grid:
            self.report({'WARNING'}, "No active grid")
            return {'CANCELLED'}

        if not armature:
            self.report({'WARNING'}, "No active armature")
            return {'CANCELLED'}

        # Capture current pose
        from .poses import capture_pose
        rotations = capture_pose(armature)

        # Add dot at center (user can move it)
        grid.add_dot(
            name=self.name,
            position=(0.5, 0.5),
            rotations_dict=rotations
        )

        self.report({'INFO'}, f"Added dot: {self.name}")
        return {'FINISHED'}


# ============================================================================
# Registration
# ============================================================================

classes = (
    VIEW3D_PT_poseblend_main,
    VIEW3D_PT_poseblend_dots,
    VIEW3D_PT_poseblend_settings,
    VIEW3D_PT_poseblend_io,
    POSEBLEND_UL_grids,
    POSEBLEND_UL_dots,
    POSEBLEND_OT_activate,
    POSEBLEND_OT_deactivate,
    POSEBLEND_OT_add_grid,
    POSEBLEND_OT_toggle_lock,
    POSEBLEND_OT_add_dot,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
