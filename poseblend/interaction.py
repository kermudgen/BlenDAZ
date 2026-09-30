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

"""PoseBlend Interaction - Modal operator for grid interaction"""

import bpy
from bpy.types import Operator
from .grid import pixel_to_grid, find_dot_at_position, snap_to_grid, clamp_to_grid
from .blending import calculate_blend_weights
from .poses import apply_blended_pose, capture_pose, capture_bone_locations, keyframe_pose, get_bone_mask_for_dot, get_grid_region_mask, capture_morphs, apply_morphs, blend_morphs
from .presets import get_dot_color, get_morph_names_for_categories



# ============================================================================
# Modal Operator States
# ============================================================================

class InteractionState:
    """Enum-like class for interaction states"""
    IDLE = 'idle'
    PREVIEWING = 'previewing'
    DRAGGING_DOT = 'dragging_dot'
    CREATING_DOT = 'creating_dot'
    PANNING = 'panning'


# ============================================================================
# Modal Operator
# ============================================================================

class POSEBLEND_OT_interact(Operator):
    """Interactive pose blending on the grid"""
    bl_idname = "poseblend.interact"
    bl_label = "PoseBlend Interact"
    bl_options = {'REGISTER'}

    # State tracking
    _state: str = InteractionState.IDLE
    _cursor_pos: tuple = (0.5, 0.5)
    _dragged_dot = None
    _dragged_dot_original_pos = None

    # Pan tracking (MMB drag)
    _pan_start_pixel = None      # (px, py) at MMB press
    _pan_start_center = None     # pan_center at MMB press

    # Grid region (set during invoke, recalculated on zoom)
    _grid_region = None

    def is_over_grid(self, context, event):
        """Check if mouse is over the grid region"""
        if self._grid_region is None:
            return False

        mx = event.mouse_region_x
        my = event.mouse_region_y
        gr = self._grid_region

        return (gr['x'] <= mx <= gr['x'] + gr['width'] and
                gr['y'] <= my <= gr['y'] + gr['height'])

    def modal(self, context, event):
        """Handle events during modal operation"""
        settings = context.scene.poseblend_settings

        # If PoseBlend was deactivated externally (e.g., button click), exit
        if not settings.is_active:
            settings.cursor_over_grid = False
            settings.cursor_active = False
            return {'FINISHED'}

        # Recalculate grid region each frame (handles window resizes too)
        self._grid_region = self.calculate_grid_region(context)

        over_grid = self.is_over_grid(context, event)

        # Keep border active during mid-interaction even if cursor leaves grid
        in_interaction = self._state in (
            InteractionState.PREVIEWING,
            InteractionState.DRAGGING_DOT,
            InteractionState.PANNING,
        )
        settings.cursor_over_grid = over_grid or in_interaction

        # ESC anywhere → deactivate PoseBlend entirely, keep pose
        if event.type == 'ESC' and event.value == 'PRESS':
            return self.deactivate_and_exit(context)

        # --- Mid-interaction: always handle regardless of cursor position ---
        if self._state in (InteractionState.PREVIEWING, InteractionState.DRAGGING_DOT):
            if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
                self.update_cursor(context, event)
                if self._state == InteractionState.PREVIEWING:
                    self.update_preview(context)
                elif self._state == InteractionState.DRAGGING_DOT:
                    self.update_dot_drag(context)
                context.area.tag_redraw()
                return {'RUNNING_MODAL'}

            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                return self.handle_left_release(context, event)

            if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
                return self.cancel_action(context)

            return {'RUNNING_MODAL'}

        # --- Panning: MMB drag ---
        if self._state == InteractionState.PANNING:
            if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
                self.update_pan(context, event)
                context.area.tag_redraw()
                return {'RUNNING_MODAL'}

            if event.type == 'MIDDLEMOUSE' and event.value == 'RELEASE':
                self._state = InteractionState.IDLE
                context.area.tag_redraw()
                return {'RUNNING_MODAL'}

            return {'RUNNING_MODAL'}

        # --- IDLE state ---

        # Not over grid → pass everything through to Blender
        if not over_grid:
            if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
                context.area.tag_redraw()
            return {'PASS_THROUGH'}

        # Over grid — handle grid-specific events
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            self.update_cursor(context, event)
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        # Mousewheel over grid → zoom
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return self.handle_zoom(context, event)

        # Left mouse button
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            return self.handle_left_press(context, event)

        # Middle mouse button → start panning
        if event.type == 'MIDDLEMOUSE' and event.value == 'PRESS':
            return self.start_pan(context, event)

        # Right mouse button (context menu)
        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            return self.handle_right_click(context, event)

        # Delete key (remove dot)
        if event.type == 'X' and event.value == 'PRESS':
            return self.handle_delete(context)

        # Consume other events over the grid so Blender doesn't act on them
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

        # Calculate grid region in viewport
        self._grid_region = self.calculate_grid_region(context)

        # Initialize state
        self._state = InteractionState.IDLE
        settings.cursor_over_grid = False

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

        settings = context.scene.poseblend_settings
        pos = pixel_to_grid(
            event.mouse_region_x,
            event.mouse_region_y,
            self._grid_region,
            settings.grid_zoom,
            tuple(settings.grid_pan)
        )

        if pos:
            # Don't clamp — with zoom out, cursor can go past 0-1 for extrapolation
            self._cursor_pos = pos

            # Update settings for drawing
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
                # Snapshot pose + morphs before the preview mutates them —
                # RMB cancel restores from this (previously cancel kept
                # whatever the preview had already applied).
                self._capture_preview_snapshot(context)
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
        """Handle right click (context menu for dots, or grid menu on empty)"""
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()

        if not grid:
            return {'RUNNING_MODAL'}

        # Check if clicking on a dot
        dot, idx = find_dot_at_position(self._cursor_pos, grid.dots)

        if dot:
            grid.active_dot_index = idx
            bpy.ops.wm.call_menu(name='POSEBLEND_MT_dot_context')
        else:
            # Empty space → show grid context menu
            bpy.ops.wm.call_menu(name='POSEBLEND_MT_grid_context')

        return {'RUNNING_MODAL'}

    def start_pan(self, context, event):
        """Start panning the grid view with MMB"""
        self._state = InteractionState.PANNING
        self._pan_start_pixel = (event.mouse_region_x, event.mouse_region_y)
        settings = context.scene.poseblend_settings
        self._pan_start_center = tuple(settings.grid_pan)
        return {'RUNNING_MODAL'}

    def update_pan(self, context, event):
        """Update pan position during MMB drag"""
        if self._pan_start_pixel is None or self._grid_region is None:
            return

        settings = context.scene.poseblend_settings
        zoom = settings.grid_zoom
        gw = self._grid_region['width']
        gh = self._grid_region['height']

        dx = event.mouse_region_x - self._pan_start_pixel[0]
        dy = event.mouse_region_y - self._pan_start_pixel[1]

        # Convert pixel delta to dot-space delta (dragging moves content)
        new_cx = self._pan_start_center[0] - dx / (zoom * gw)
        new_cy = self._pan_start_center[1] - dy / (zoom * gh)

        settings.grid_pan = (new_cx, new_cy)

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
            # Capture before remove_dot(): the CollectionProperty item ref is
            # invalid once the collection reshuffles.
            dot_name = dot.name
            grid.remove_dot(idx)
            self.report({'INFO'}, f"Deleted dot: {dot_name}")
            context.area.tag_redraw()

        return {'RUNNING_MODAL'}

    def _capture_preview_snapshot(self, context):
        """Snapshot pose + morphs before a preview starts mutating them."""
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        armature = bpy.data.objects.get(settings.active_armature_name)
        if not grid or not armature:
            self._preview_snapshot = None
            return
        morph_names = get_morph_names_for_categories(armature, grid)
        self._preview_snapshot = {
            'rotations': capture_pose(armature),
            'locations': capture_bone_locations(armature),
            'morphs': capture_morphs(armature, morph_names) if morph_names else {},
        }

    def _restore_preview_snapshot(self, context):
        """Restore the pre-preview pose + morphs (RMB cancel during preview)."""
        snap = getattr(self, '_preview_snapshot', None)
        settings = context.scene.poseblend_settings
        armature = bpy.data.objects.get(settings.active_armature_name)
        if not snap or not armature:
            return
        for bone_name, quat in snap['rotations'].items():
            pb = armature.pose.bones.get(bone_name)
            if pb:
                pb.rotation_quaternion = quat
        for bone_name, loc in snap['locations'].items():
            pb = armature.pose.bones.get(bone_name)
            if pb:
                pb.location = loc
        if snap['morphs']:
            apply_morphs(armature, snap['morphs'])
        self._preview_snapshot = None
        context.view_layer.update()

    def _apply_blend_at_cursor(self, context):
        """Compute weights at the cursor and apply the blended pose + morphs."""
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        armature = bpy.data.objects.get(settings.active_armature_name)

        if not grid or not armature or len(grid.dots) == 0:
            return False

        weights = calculate_blend_weights(
            self._cursor_pos,
            grid.dots,
            settings.blend_falloff,
            settings.blend_radius,
            settings.extrapolation_max
        )
        if not weights:
            return False

        allowed = get_grid_region_mask(grid)
        apply_blended_pose(armature, weights, grid=grid, allowed_bones=allowed)

        # Blend and apply morphs
        weighted_morphs = []
        for dot, weight in weights:
            md = dot.get_morphs_dict()
            if md:
                weighted_morphs.append((md, weight))
        if weighted_morphs:
            blended = blend_morphs(weighted_morphs)
            apply_morphs(armature, blended)
        return True

    def update_preview(self, context):
        """Update pose preview based on cursor position"""
        settings = context.scene.poseblend_settings

        if settings.preview_mode != 'REALTIME':
            return

        self._apply_blend_at_cursor(context)

    def update_dot_drag(self, context):
        """Update dot position during drag"""
        if not self._dragged_dot:
            return

        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()

        # Update dot position (clamp to 0-1 — dots live in dot space)
        new_pos = clamp_to_grid(self._cursor_pos)

        # Snap if enabled
        if grid and grid.snap_to_grid:
            new_pos = snap_to_grid(new_pos, tuple(grid.grid_divisions))

        self._dragged_dot.position = new_pos

    def apply_dot_pose(self, context, dot):
        """Apply a single dot's pose directly"""
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        armature = bpy.data.objects.get(settings.active_armature_name)

        if not armature:
            return

        # Apply with 100% weight, honoring per-dot and grid region masks
        allowed = get_grid_region_mask(grid)
        apply_blended_pose(armature, [(dot, 1.0)], grid=grid, allowed_bones=allowed)

        # Apply morphs
        md = dot.get_morphs_dict()
        if md:
            apply_morphs(armature, md)

        # Auto keyframe if enabled — key the same bones that were written
        # (per-dot mask ∩ active region mask)
        if settings.auto_keyframe:
            bone_mask = get_bone_mask_for_dot(dot, grid)
            if allowed is not None:
                if bone_mask is None:
                    bone_mask = list(allowed)
                else:
                    bone_mask = [b for b in bone_mask if b in allowed]
            keyframe_pose(armature, bone_mask)

    def create_dot_at_cursor(self, context):
        """Create new dot at current cursor position"""
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        armature = bpy.data.objects.get(settings.active_armature_name)

        if not grid or not armature:
            return

        # Capture current pose (rotations + locations)
        rotations = capture_pose(armature)
        locations = capture_bone_locations(armature)

        # Capture morphs for enabled categories
        morph_names = get_morph_names_for_categories(armature, grid)
        morphs = capture_morphs(armature, morph_names) if morph_names else {}

        # Clamp to 0-1 (dots live in dot space) and snap if enabled
        position = clamp_to_grid(self._cursor_pos)
        if grid.snap_to_grid:
            position = snap_to_grid(position, tuple(grid.grid_divisions))

        # Create dot with default mask
        name = f"Pose {len(grid.dots) + 1}"
        dot = grid.add_dot(
            name=name,
            position=position,
            rotations_dict=rotations,
            locations_dict=locations,
            mask_mode=grid.bone_mask_mode,
            mask_preset=grid.bone_mask_preset
        )

        # Store morph values
        if morphs:
            dot.set_morphs_dict(morphs)

        # Set color based on mask
        dot.color = get_dot_color(dot.bone_mask_mode, dot.bone_mask_preset)

        self.report({'INFO'}, f"Created dot: {name}")

    def finalize_pose(self, context):
        """Finalize the current blend and optionally keyframe"""
        settings = context.scene.poseblend_settings
        armature = bpy.data.objects.get(settings.active_armature_name)

        if not armature:
            return

        # ON_RELEASE mode: the blend was never applied during the preview
        # (update_preview early-returns for non-REALTIME) — apply it now at
        # the release position. Previously this path only keyframed, so the
        # unchanged pose got keyed and the mode did nothing at all.
        if settings.preview_mode != 'REALTIME':
            self._apply_blend_at_cursor(context)

        # Blend is committed — the pre-preview snapshot is no longer needed
        self._preview_snapshot = None

        # Auto keyframe if enabled
        if settings.auto_keyframe:
            keyframe_pose(armature)

    def handle_zoom(self, context, event):
        """Handle mousewheel zoom of dot space within grid.

        Scroll up = zoom in (dots bigger, less space around).
        Scroll down = zoom out (dots smaller, more space for extrapolation).
        """
        settings = context.scene.poseblend_settings

        step = 0.1
        if event.type == 'WHEELUPMOUSE':
            settings.grid_zoom = min(4.0, settings.grid_zoom + step)
        else:
            settings.grid_zoom = max(0.2, settings.grid_zoom - step)

        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def cancel_action(self, context):
        """Cancel current action and restore state"""
        if self._state == InteractionState.DRAGGING_DOT:
            # Restore dot position
            if self._dragged_dot and self._dragged_dot_original_pos:
                self._dragged_dot.position = self._dragged_dot_original_pos
            self._dragged_dot = None
        elif self._state == InteractionState.PREVIEWING:
            # Undo the previewed blend — restore the pre-preview pose/morphs
            # (previously cancel only reset flags and kept the mutated pose)
            self._restore_preview_snapshot(context)

        settings = context.scene.poseblend_settings
        settings.cursor_active = False
        self._state = InteractionState.IDLE
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def deactivate_and_exit(self, context):
        """Deactivate PoseBlend and exit modal — keeps current pose"""
        settings = context.scene.poseblend_settings
        settings.cursor_active = False
        settings.cursor_over_grid = False

        # Deactivate PoseBlend (unregister draw handler, etc.)
        bpy.ops.poseblend.deactivate()

        context.area.tag_redraw()
        return {'FINISHED'}

    def cancel(self, context):
        """Called by Blender if modal is interrupted — keep pose, clean up"""
        settings = context.scene.poseblend_settings
        settings.cursor_active = False
        settings.cursor_over_grid = False
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
        layout.operator("poseblend.update_dot_pose", icon='FILE_REFRESH')
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
                # Capture ALL source-dot data BEFORE add_dot(): dots.add() can
                # reallocate the CollectionProperty array and invalidate
                # existing item references (documented BPY gotcha) — reading
                # `dot` after the add is use-after-free.
                new_pos = (
                    min(1.0, dot.position[0] + 0.05),
                    min(1.0, dot.position[1] + 0.05)
                )
                src_name = dot.name
                src_rotations = dot.get_rotations_dict()
                src_locations = dot.get_locations_dict()
                src_mask_mode = dot.bone_mask_mode
                src_mask_preset = dot.bone_mask_preset
                src_color = tuple(dot.color)
                src_morphs = dot.get_morphs_dict()
                new_dot = grid.add_dot(
                    name=f"{src_name} (copy)",
                    position=new_pos,
                    rotations_dict=src_rotations,
                    locations_dict=src_locations,
                    mask_mode=src_mask_mode,
                    mask_preset=src_mask_preset
                )
                new_dot.color = src_color
                new_dot.set_morphs_dict(src_morphs)
        return {'FINISHED'}


class POSEBLEND_OT_update_dot_pose(Operator):
    """Update selected dot with current armature pose"""
    bl_idname = "poseblend.update_dot_pose"
    bl_label = "Update with Current Pose"

    def execute(self, context):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        armature = bpy.data.objects.get(settings.active_armature_name)

        if not grid or not armature:
            self.report({'WARNING'}, "No active grid or armature")
            return {'CANCELLED'}

        dot = grid.get_active_dot()
        if not dot:
            self.report({'WARNING'}, "No active dot")
            return {'CANCELLED'}

        rotations = capture_pose(armature)
        locations = capture_bone_locations(armature)
        dot.set_rotations_dict(rotations)
        dot.set_locations_dict(locations)

        # Update morphs for enabled categories
        morph_names = get_morph_names_for_categories(armature, grid)
        morphs = capture_morphs(armature, morph_names) if morph_names else {}
        dot.set_morphs_dict(morphs)

        self.report({'INFO'}, f"Updated dot: {dot.name}")
        return {'FINISHED'}


_DOT_MASK_MODE_ITEMS = [
    ('USE_GRID', 'Use Grid Default', 'Inherit bone mask from grid'),
    ('ALL', 'Full Body', 'All bones (override grid)'),
    ('PRESET', 'Preset Region', 'Use predefined bone group (override grid)'),
    ('CUSTOM', 'Custom', 'Custom bone selection'),
]

_DOT_MASK_PRESET_ITEMS = [
    ('HEAD', 'Head & Face', 'Head, neck, eyes, jaw'),
    ('UPPER_BODY', 'Upper Body', 'Spine, chest, shoulders, arms'),
    ('LOWER_BODY', 'Lower Body', 'Pelvis, legs, feet'),
    ('ARMS', 'Arms', 'Both arms and hands'),
    ('ARM_L', 'Left Arm', 'Left arm and hand'),
    ('ARM_R', 'Right Arm', 'Right arm and hand'),
    ('LEGS', 'Legs', 'Both legs and feet'),
    ('LEG_L', 'Left Leg', 'Left leg and foot'),
    ('LEG_R', 'Right Leg', 'Right leg and foot'),
    ('HANDS', 'Hands', 'Fingers only'),
    ('FACE', 'Face', 'Facial bones/expressions'),
    ('SPINE', 'Spine', 'Spine and torso only'),
]


class POSEBLEND_OT_edit_dot_mask(Operator):
    """Edit which bones the selected dot contributes to the blend"""
    bl_idname = "poseblend.edit_dot_mask"
    bl_label = "Edit Bone Mask"
    bl_options = {'REGISTER', 'UNDO'}

    mask_mode: bpy.props.EnumProperty(
        name="Mode", items=_DOT_MASK_MODE_ITEMS, default='USE_GRID'
    )
    mask_preset: bpy.props.EnumProperty(
        name="Preset", items=_DOT_MASK_PRESET_ITEMS, default='HEAD'
    )

    def invoke(self, context, event):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        if grid:
            dot = grid.get_active_dot()
            if dot:
                self.mask_mode = dot.bone_mask_mode
                self.mask_preset = dot.bone_mask_preset
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "mask_mode")
        if self.mask_mode == 'PRESET':
            layout.prop(self, "mask_preset")
        elif self.mask_mode == 'CUSTOM':
            layout.label(text="Custom bone list kept as-is.", icon='INFO')

    def execute(self, context):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        if not grid:
            return {'CANCELLED'}
        dot = grid.get_active_dot()
        if not dot:
            self.report({'WARNING'}, "No active dot")
            return {'CANCELLED'}

        dot.bone_mask_mode = self.mask_mode
        dot.bone_mask_preset = self.mask_preset
        dot.color = get_dot_color(dot.bone_mask_mode, dot.bone_mask_preset)
        context.area.tag_redraw()
        self.report({'INFO'}, f"Updated mask for: {dot.name}")
        return {'FINISHED'}


# ============================================================================
# Live Body-Part Mask (Director-style region gate)
# ============================================================================

class POSEBLEND_OT_mask_region(Operator):
    """Toggle a body-part region. Shift-click to solo just this region"""
    bl_idname = "poseblend.mask_region"
    bl_label = "Toggle Mask Region"
    bl_options = {'INTERNAL'}

    region: bpy.props.StringProperty(name="Region", default="")

    _solo: bool = False

    def invoke(self, context, event):
        self._solo = event.shift
        return self.execute(context)

    def execute(self, context):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        if not grid or not self.region:
            return {'CANCELLED'}

        if self._solo:
            grid.solo_region(self.region)
        else:
            grid.toggle_region(self.region)

        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class POSEBLEND_OT_mask_all(Operator):
    """Enable all body-part regions (no masking)"""
    bl_idname = "poseblend.mask_all"
    bl_label = "Mask: All"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        if not grid:
            return {'CANCELLED'}
        grid.set_active_regions(None)
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class POSEBLEND_OT_mask_none(Operator):
    """Disable all body-part regions (freeze everything)"""
    bl_idname = "poseblend.mask_none"
    bl_label = "Mask: None"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        if not grid:
            return {'CANCELLED'}
        grid.set_active_regions([])
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class POSEBLEND_OT_clear_grid(Operator):
    """Remove all dots from the active grid"""
    bl_idname = "poseblend.clear_grid"
    bl_label = "Clear Grid"

    def execute(self, context):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        if not grid:
            return {'CANCELLED'}

        count = len(grid.dots)
        grid.dots.clear()
        grid.active_dot_index = -1
        self.report({'INFO'}, f"Cleared {count} dots")
        context.area.tag_redraw()
        return {'FINISHED'}


class POSEBLEND_OT_reset_view(Operator):
    """Reset grid zoom and pan to default"""
    bl_idname = "poseblend.reset_view"
    bl_label = "Reset View"

    def execute(self, context):
        settings = context.scene.poseblend_settings
        settings.grid_zoom = 1.0
        settings.grid_pan = (0.5, 0.5)
        context.area.tag_redraw()
        return {'FINISHED'}


class POSEBLEND_OT_rename_grid(Operator):
    """Rename the active grid"""
    bl_idname = "poseblend.rename_grid"
    bl_label = "Rename Grid"

    new_name: bpy.props.StringProperty(name="Name", default="")

    def invoke(self, context, event):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        if grid:
            self.new_name = grid.name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        if grid:
            grid.name = self.new_name
            self.report({'INFO'}, f"Renamed grid to: {self.new_name}")
        return {'FINISHED'}


class POSEBLEND_OT_delete_grid(Operator):
    """Delete the active grid from the collection"""
    bl_idname = "poseblend.delete_grid"
    bl_label = "Delete Grid"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()
        if not grid:
            return {'CANCELLED'}

        name = grid.name
        settings.remove_grid(settings.active_grid_index)
        self.report({'INFO'}, f"Deleted grid: {name}")
        context.area.tag_redraw()
        return {'FINISHED'}


class POSEBLEND_MT_grid_context(bpy.types.Menu):
    """Context menu for empty grid space"""
    bl_label = "Grid Options"
    bl_idname = "POSEBLEND_MT_grid_context"

    def draw(self, context):
        layout = self.layout
        layout.operator("poseblend.add_grid", icon='ADD')
        layout.operator("poseblend.rename_grid", icon='GREASEPENCIL')
        layout.separator()
        layout.operator("poseblend.clear_grid", icon='TRASH')
        layout.operator("poseblend.delete_grid", icon='X')
        layout.separator()
        layout.operator("poseblend.reset_view", icon='HOME')


# ============================================================================
# Registration
# ============================================================================

classes = (
    POSEBLEND_OT_interact,
    POSEBLEND_MT_dot_context,
    POSEBLEND_MT_grid_context,
    POSEBLEND_OT_rename_dot,
    POSEBLEND_OT_delete_dot,
    POSEBLEND_OT_duplicate_dot,
    POSEBLEND_OT_update_dot_pose,
    POSEBLEND_OT_edit_dot_mask,
    POSEBLEND_OT_mask_region,
    POSEBLEND_OT_mask_all,
    POSEBLEND_OT_mask_none,
    POSEBLEND_OT_clear_grid,
    POSEBLEND_OT_reset_view,
    POSEBLEND_OT_rename_grid,
    POSEBLEND_OT_delete_grid,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
