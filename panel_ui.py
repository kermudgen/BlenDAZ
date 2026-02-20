"""
BlenDAZ N-Panel UI

Centralized panel for DAZ bone tools, settings, and quick actions.
Located in the 3D Viewport sidebar (N-panel).
"""

import bpy
from . import genesis8_limits


# ============================================================================
# PROPERTIES
# ============================================================================

class BlenDAZProperties(bpy.types.PropertyGroup):
    """Properties for BlenDAZ addon settings"""

    # Rotation Limits
    enable_rotation_limits: bpy.props.BoolProperty(
        name="Enable Rotation Limits",
        description="Enable LIMIT_ROTATION constraints on all bones",
        default=True
    )

    # IK Settings
    use_ik_templates: bpy.props.BoolProperty(
        name="Use IK Templates",
        description="Use predefined IK templates for consistent behavior",
        default=True
    )

    enable_prebend: bpy.props.BoolProperty(
        name="Pre-bend Enabled",
        description="Enable pre-bend mouse sampling for natural IK direction",
        default=True
    )

    ik_chain_length: bpy.props.EnumProperty(
        name="Chain Length",
        description="IK chain length calculation method",
        items=[
            ('AUTO', "Auto", "Automatic chain length based on bone type"),
            ('SHORT', "Short", "Shorter chains (2-3 bones)"),
            ('MEDIUM', "Medium", "Medium chains (3-4 bones)"),
            ('LONG', "Long", "Longer chains (4-5 bones)"),
        ],
        default='AUTO'
    )


# ============================================================================
# OPERATORS
# ============================================================================

class BLENDAZ_OT_update_rotation_limits(bpy.types.Operator):
    """Apply or update Genesis 8 rotation limits on all bones"""
    bl_idname = "blendaz.update_rotation_limits"
    bl_label = "Update Limits"
    bl_description = "Apply Genesis 8 rotation limits to all bones (fixes Diffeomorphic import issues)"
    bl_options = {'REGISTER', 'UNDO'}

    force_update: bpy.props.BoolProperty(
        name="Force Update",
        description="Replace existing LIMIT_ROTATION constraints",
        default=False
    )

    def execute(self, context):
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE':
            self.report({'WARNING'}, "No armature selected")
            return {'CANCELLED'}

        applied, skipped, missing = genesis8_limits.apply_all_genesis8_limits(
            armature,
            force=self.force_update
        )

        self.report({'INFO'}, f"Applied: {applied}, Skipped: {skipped}, Missing: {missing}")
        return {'FINISHED'}


class BLENDAZ_OT_clear_rotation_limits(bpy.types.Operator):
    """Remove all LIMIT_ROTATION constraints from armature"""
    bl_idname = "blendaz.clear_rotation_limits"
    bl_label = "Clear All Limits"
    bl_description = "Remove all LIMIT_ROTATION constraints from the armature"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE':
            self.report({'WARNING'}, "No armature selected")
            return {'CANCELLED'}

        count = 0
        for pose_bone in armature.pose.bones:
            for constraint in list(pose_bone.constraints):
                if constraint.type == 'LIMIT_ROTATION':
                    pose_bone.constraints.remove(constraint)
                    count += 1

        self.report({'INFO'}, f"Removed {count} rotation limit constraints")
        return {'FINISHED'}


class BLENDAZ_OT_clear_all_pins(bpy.types.Operator):
    """Clear all pin markers from bones"""
    bl_idname = "blendaz.clear_all_pins"
    bl_label = "Clear All Pins"
    bl_description = "Remove all pin markers from bones"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE':
            self.report({'WARNING'}, "No armature selected")
            return {'CANCELLED'}

        # Import pin utilities (assumes they exist in daz_bone_select.py)
        try:
            from . import daz_bone_select
            count = 0
            for bone in armature.data.bones:
                if daz_bone_select.is_bone_pinned_translation(bone) or daz_bone_select.is_bone_pinned_rotation(bone):
                    daz_bone_select.unpin_bone(bone)
                    count += 1

            self.report({'INFO'}, f"Cleared {count} pin markers")
        except (ImportError, AttributeError) as e:
            self.report({'ERROR'}, f"Pin utilities not available: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}


class BLENDAZ_OT_reset_pose(bpy.types.Operator):
    """Reset armature to rest pose"""
    bl_idname = "blendaz.reset_pose"
    bl_label = "Reset Pose"
    bl_description = "Reset all bones to rest pose"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE':
            self.report({'WARNING'}, "No armature selected")
            return {'CANCELLED'}

        # Reset all pose bones
        for pose_bone in armature.pose.bones:
            pose_bone.location = (0, 0, 0)
            pose_bone.rotation_quaternion = (1, 0, 0, 0)
            pose_bone.rotation_euler = (0, 0, 0)
            pose_bone.scale = (1, 1, 1)

        self.report({'INFO'}, "Reset armature to rest pose")
        return {'FINISHED'}


class BLENDAZ_OT_activate_tool(bpy.types.Operator):
    """Activate DAZ Bone Select modal tool"""
    bl_idname = "blendaz.activate_tool"
    bl_label = "Activate Tool"
    bl_description = "Start the DAZ Bone Select modal operator"

    def execute(self, context):
        try:
            bpy.ops.view3d.daz_bone_select('INVOKE_DEFAULT')
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to activate tool: {e}")
            return {'CANCELLED'}


# ============================================================================
# PANEL
# ============================================================================

class VIEW3D_PT_blendaz_main(bpy.types.Panel):
    """Main BlenDAZ panel in 3D Viewport sidebar"""
    bl_label = "DAZ Bone Tools"
    bl_idname = "VIEW3D_PT_blendaz_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'

    def draw(self, context):
        layout = self.layout
        props = context.scene.blendaz_props

        # Show active armature
        if context.active_object and context.active_object.type == 'ARMATURE':
            armature = context.active_object

            # Header - Armature Info
            box = layout.box()
            row = box.row()
            row.label(text=f"Target: {armature.name}", icon='ARMATURE_DATA')

            # Rotation Limits Section
            box = layout.box()
            box.label(text="Rotation Limits", icon='CON_ROTLIMIT')

            row = box.row()
            row.prop(props, "enable_rotation_limits", text="Enable Limits")

            row = box.row(align=True)
            op = row.operator("blendaz.update_rotation_limits", text="Update Limits", icon='FILE_REFRESH')
            op.force_update = False

            row = box.row()
            op = row.operator("blendaz.update_rotation_limits", text="Force Update", icon='RECOVER_LAST')
            op.force_update = True

            row = box.row()
            row.operator("blendaz.clear_rotation_limits", text="Clear All Limits", icon='X')

            # IK Settings Section
            box = layout.box()
            box.label(text="IK Settings", icon='CON_KINEMATIC')

            row = box.row()
            row.prop(props, "ik_chain_length", text="Chain Length")

            row = box.row()
            row.prop(props, "use_ik_templates", text="Use Templates")

            row = box.row()
            row.prop(props, "enable_prebend", text="Pre-bend")

            # Quick Actions Section
            box = layout.box()
            box.label(text="Quick Actions", icon='PLAY')

            row = box.row()
            row.operator("blendaz.clear_all_pins", text="Clear All Pins", icon='UNPINNED')

            row = box.row()
            row.operator("blendaz.reset_pose", text="Reset Pose", icon='LOOP_BACK')

            row = box.row()
            row.operator("blendaz.activate_tool", text="Activate Tool", icon='HAND')

        else:
            # No armature selected
            layout.label(text="No armature selected", icon='ERROR')
            layout.label(text="Select an armature to use tools")


# ============================================================================
# REGISTRATION
# ============================================================================

classes = (
    BlenDAZProperties,
    BLENDAZ_OT_update_rotation_limits,
    BLENDAZ_OT_clear_rotation_limits,
    BLENDAZ_OT_clear_all_pins,
    BLENDAZ_OT_reset_pose,
    BLENDAZ_OT_activate_tool,
    VIEW3D_PT_blendaz_main,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Register properties
    bpy.types.Scene.blendaz_props = bpy.props.PointerProperty(type=BlenDAZProperties)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    # Unregister properties
    del bpy.types.Scene.blendaz_props


if __name__ == "__main__":
    register()
