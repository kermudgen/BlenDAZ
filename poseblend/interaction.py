"""PoseBlend Interaction - Modal operator for grid interaction"""

import bpy
from bpy.types import Operator
from .grid import pixel_to_grid, find_dot_at_position, snap_to_grid, clamp_to_grid
from .blending import calculate_blend_weights
from .poses import apply_blended_pose, capture_pose, keyframe_pose, get_bone_mask_for_dot
from .presets import get_dot_color


# ============================================================================
# Modal Operator States
# ============================================================================

class InteractionState:
    """Enum-like class for interaction states"""
    IDLE = 'idle'
    PREVIEWING = 'previewing'
    DRAGGING_DOT = 'dragging_dot'
    CREATING_DOT = 'creating_dot'


# ============================================================================
# Modal Operator
# ============================================================================

class POSEBLEND_OT_interact(Operator):
    """Interactive pose blending on the grid"""
    bl_idname = "poseblend.interact"
    bl_label = "PoseBlend Interact"
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    # State tracking
    _state: str = InteractionState.IDLE
    _cursor_pos: tuple = (0.5, 0.5)
    _dragged_dot = None
    _dragged_dot_original_pos = None
    _initial_pose = None  # For undo on cancel

    # Grid region (set during invoke)
    _grid_region = None

    def modal(self, context, event):
        """Handle events during modal operation"""
        settings = context.scene.poseblend_settings

        # Always allow escape to exit
        if event.type == 'ESC':
            return self.cancel(context)

        # Update cursor position on mouse move (always, for hover detection)
        if event.type == 'MOUSEMOVE':
            self.update_cursor(context, event)

            if self._state == InteractionState.PREVIEWING:
                self.update_preview(context)
            elif self._state == InteractionState.DRAGGING_DOT:
                self.update_dot_drag(context)

            # Always redraw for hover feedback
            context.area.tag_redraw()

        # Left mouse button
        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                return self.handle_left_press(context, event)
            elif event.value == 'RELEASE':
                return self.handle_left_release(context, event)

        # Right mouse button (context menu / cancel)
        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            if self._state == InteractionState.IDLE:
                return self.handle_right_click(context, event)
            else:
                # Cancel current action
                return self.cancel_action(context)

        # Delete key (remove dot)
        if event.type == 'X' and event.value == 'PRESS':
            return self.handle_delete(context)

        # Allow view navigation
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        """Start modal interaction"""
        settings = context.scene.poseblend_settings

        if not settings.is_active:
            self.report({'WARNING'}, "PoseBlend is not active")
            return {'CANCELLED'}

        grid = settings.get_active_grid()
        if not grid:
            self.report({'WARNING'}, "No active grid")
            return {'CANCELLED'}

        # Get armature
        armature = bpy.data.objects.get(settings.active_armature_name)
        if not armature:
            self.report({'WARNING'}, "No active armature")
            return {'CANCELLED'}

        # Store initial pose for potential undo
        self._initial_pose = capture_pose(armature)

        # Calculate grid region in viewport
        self._grid_region = self.calculate_grid_region(context)

        # Initialize state
        self._state = InteractionState.IDLE
        self.update_cursor(context, event)

        # Start modal
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()

        return {'RUNNING_MODAL'}

    def calculate_grid_region(self, context):
        """Calculate the grid region within the viewport

        Uses the same calculation as drawing.py for consistency.
        """
        from .drawing import PoseBlendDrawHandler

        region = context.region
        settings = context.scene.poseblend_settings

        return PoseBlendDrawHandler.calculate_grid_region(region, settings)

    def update_cursor(self, context, event):
        """Update cursor position from mouse event"""
        if self._grid_region is None:
            return

        pos = pixel_to_grid(
            event.mouse_region_x,
            event.mouse_region_y,
            self._grid_region
        )

        if pos:
            self._cursor_pos = clamp_to_grid(pos)

            # Update settings for drawing
            settings = context.scene.poseblend_settings
            settings.cursor_position = self._cursor_pos

    def handle_left_press(self, context, event):
        """Handle left mouse press"""
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()

        if not grid:
            return {'RUNNING_MODAL'}

        # Check if clicking on a dot
        dot, idx = find_dot_at_position(self._cursor_pos, grid.dots)

        if dot:
            if event.shift and not grid.is_locked:
                # Shift+click: start dragging dot (only if unlocked)
                self._state = InteractionState.DRAGGING_DOT
                self._dragged_dot = dot
                self._dragged_dot_original_pos = tuple(dot.position)
                grid.active_dot_index = idx
            else:
                # Click on dot: apply that pose directly
                self.apply_dot_pose(context, dot)
        else:
            if event.shift and not grid.is_locked:
                # Shift+click empty: create new dot (only if unlocked)
                self._state = InteractionState.CREATING_DOT
                self.create_dot_at_cursor(context)
            else:
                # Click empty: start previewing blend
                self._state = InteractionState.PREVIEWING
                settings.cursor_active = True
                self.update_preview(context)

        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def handle_left_release(self, context, event):
        """Handle left mouse release"""
        settings = context.scene.poseblend_settings

        if self._state == InteractionState.PREVIEWING:
            # Finalize the blend
            self.finalize_pose(context)
            settings.cursor_active = False
            self._state = InteractionState.IDLE

        elif self._state == InteractionState.DRAGGING_DOT:
            # Finalize dot position
            self._dragged_dot = None
            self._state = InteractionState.IDLE

        elif self._state == InteractionState.CREATING_DOT:
            self._state = InteractionState.IDLE

        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def handle_right_click(self, context, event):
        """Handle right click (context menu for dots)"""
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()

        if not grid:
            return {'RUNNING_MODAL'}

        # Check if clicking on a dot
        dot, idx = find_dot_at_position(self._cursor_pos, grid.dots)

        if dot:
            # Show context menu
            grid.active_dot_index = idx
            bpy.ops.wm.call_menu(name='POSEBLEND_MT_dot_context')

        return {'RUNNING_MODAL'}

    def handle_delete(self, context):
        """Handle delete key (remove selected dot)"""
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()

        if not grid:
            return {'RUNNING_MODAL'}

        # Don't allow deletion when grid is locked
        if grid.is_locked:
            self.report({'WARNING'}, "Grid is locked - unlock to delete dots")
            return {'RUNNING_MODAL'}

        # Check if cursor is over a dot
        dot, idx = find_dot_at_position(self._cursor_pos, grid.dots)

        if dot:
            grid.remove_dot(idx)
            self.report({'INFO'}, f"Deleted dot: {dot.name}")
            context.area.tag_redraw()

        return {'RUNNING_MODAL'}

    def update_preview(self, context):
        """Update pose preview based on cursor position"""
        settings = context.scene.poseblend_settings

        if settings.preview_mode != 'REALTIME':
            return

        grid = settings.get_active_grid()
        armature = bpy.data.objects.get(settings.active_armature_name)

        if not grid or not armature or len(grid.dots) == 0:
            return

        # Calculate blend weights
        weights = calculate_blend_weights(
            self._cursor_pos,
            grid.dots,
            settings.blend_falloff,
            settings.blend_radius
        )

        if weights:
            apply_blended_pose(armature, weights)

    def update_dot_drag(self, context):
        """Update dot position during drag"""
        if not self._dragged_dot:
            return

        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()

        # Update dot position
        new_pos = self._cursor_pos

        # Snap if enabled
        if grid and grid.snap_to_grid:
            new_pos = snap_to_grid(new_pos, tuple(grid.grid_divisions))

        self._dragged_dot.position = new_pos

    def apply_dot_pose(self, context, dot):
        """Apply a single dot's pose directly"""
        settings = context.scene.poseblend_settings
        armature = bpy.data.objects.get(settings.active_armature_name)

        if not armature:
            return

        # Apply with 100% weight
        apply_blended_pose(armature, [(dot, 1.0)])

        # Auto keyframe if enabled
        if settings.auto_keyframe:
            bone_mask = get_bone_mask_for_dot(dot)
            keyframe_pose(armature, bone_mask)

    def create_dot_at_cursor(self, context):
        """Create new dot at current cursor position"""
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        armature = bpy.data.objects.get(settings.active_armature_name)

        if not grid or not armature:
            return

        # Capture current pose
        rotations = capture_pose(armature)

        # Snap position if enabled
        position = self._cursor_pos
        if grid.snap_to_grid:
            position = snap_to_grid(position, tuple(grid.grid_divisions))

        # Create dot with default mask
        name = f"Pose {len(grid.dots) + 1}"
        dot = grid.add_dot(
            name=name,
            position=position,
            rotations_dict=rotations,
            mask_mode=grid.default_mask_mode,
            mask_preset=grid.default_mask_preset
        )

        # Set color based on mask
        dot.color = get_dot_color(dot.bone_mask_mode, dot.bone_mask_preset)

        self.report({'INFO'}, f"Created dot: {name}")

    def finalize_pose(self, context):
        """Finalize the current blend and optionally keyframe"""
        settings = context.scene.poseblend_settings
        armature = bpy.data.objects.get(settings.active_armature_name)

        if not armature:
            return

        # Auto keyframe if enabled
        if settings.auto_keyframe:
            keyframe_pose(armature)

    def cancel_action(self, context):
        """Cancel current action and restore state"""
        if self._state == InteractionState.DRAGGING_DOT:
            # Restore dot position
            if self._dragged_dot and self._dragged_dot_original_pos:
                self._dragged_dot.position = self._dragged_dot_original_pos
            self._dragged_dot = None

        settings = context.scene.poseblend_settings
        settings.cursor_active = False
        self._state = InteractionState.IDLE
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        """Cancel modal and restore initial pose"""
        settings = context.scene.poseblend_settings
        settings.cursor_active = False

        # Restore initial pose if we were previewing
        if self._initial_pose:
            armature = bpy.data.objects.get(settings.active_armature_name)
            if armature:
                from .poses import apply_pose
                apply_pose(armature, self._initial_pose)

        context.area.tag_redraw()
        return {'CANCELLED'}


# ============================================================================
# Context Menu
# ============================================================================

class POSEBLEND_MT_dot_context(bpy.types.Menu):
    """Context menu for dots"""
    bl_label = "Dot Options"
    bl_idname = "POSEBLEND_MT_dot_context"

    def draw(self, context):
        layout = self.layout
        layout.operator("poseblend.rename_dot", icon='GREASEPENCIL')
        layout.operator("poseblend.edit_dot_mask", icon='MOD_MASK')
        layout.separator()
        layout.operator("poseblend.duplicate_dot", icon='DUPLICATE')
        layout.operator("poseblend.delete_dot", icon='X')


# ============================================================================
# Helper Operators
# ============================================================================

class POSEBLEND_OT_rename_dot(Operator):
    """Rename the selected dot"""
    bl_idname = "poseblend.rename_dot"
    bl_label = "Rename Dot"

    new_name: bpy.props.StringProperty(name="Name", default="")

    def invoke(self, context, event):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        if grid:
            dot = grid.get_active_dot()
            if dot:
                self.new_name = dot.name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        if grid:
            dot = grid.get_active_dot()
            if dot:
                dot.name = self.new_name
        return {'FINISHED'}


class POSEBLEND_OT_delete_dot(Operator):
    """Delete the selected dot"""
    bl_idname = "poseblend.delete_dot"
    bl_label = "Delete Dot"

    def execute(self, context):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        if grid and grid.active_dot_index >= 0:
            grid.remove_dot(grid.active_dot_index)
        return {'FINISHED'}


class POSEBLEND_OT_duplicate_dot(Operator):
    """Duplicate the selected dot"""
    bl_idname = "poseblend.duplicate_dot"
    bl_label = "Duplicate Dot"

    def execute(self, context):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        if grid:
            dot = grid.get_active_dot()
            if dot:
                # Create copy with offset position
                new_pos = (
                    min(1.0, dot.position[0] + 0.05),
                    min(1.0, dot.position[1] + 0.05)
                )
                new_dot = grid.add_dot(
                    name=f"{dot.name} (copy)",
                    position=new_pos,
                    rotations_dict=dot.get_rotations_dict(),
                    mask_mode=dot.bone_mask_mode,
                    mask_preset=dot.bone_mask_preset
                )
                new_dot.color = dot.color
        return {'FINISHED'}


class POSEBLEND_OT_edit_dot_mask(Operator):
    """Edit bone mask for selected dot"""
    bl_idname = "poseblend.edit_dot_mask"
    bl_label = "Edit Bone Mask"

    # TODO: Implement mask editing UI
    def execute(self, context):
        self.report({'INFO'}, "Mask editing not yet implemented")
        return {'FINISHED'}


# ============================================================================
# Registration
# ============================================================================

classes = (
    POSEBLEND_OT_interact,
    POSEBLEND_MT_dot_context,
    POSEBLEND_OT_rename_dot,
    POSEBLEND_OT_delete_dot,
    POSEBLEND_OT_duplicate_dot,
    POSEBLEND_OT_edit_dot_mask,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
