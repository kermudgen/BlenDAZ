"""PoseBlend Core - PropertyGroup definitions and data structures"""

import bpy
from bpy.types import PropertyGroup
from bpy.props import (
    BoolProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
    EnumProperty,
    CollectionProperty,
    FloatVectorProperty,
    IntVectorProperty,
    PointerProperty,
)
import json
import uuid
from datetime import datetime


# ============================================================================
# PropertyGroup Classes
# ============================================================================

class PoseBlendDot(PropertyGroup):
    """A single pose dot on the blending grid"""

    # Identity
    id: StringProperty(
        name="ID",
        description="Unique identifier for this dot",
        default=""
    )

    name: StringProperty(
        name="Name",
        description="User-friendly name for this pose",
        default="Pose"
    )

    # Grid position (normalized 0-1)
    position: FloatVectorProperty(
        name="Position",
        description="Position on the grid (0-1 normalized)",
        size=2,
        default=(0.5, 0.5),
        min=0.0,
        max=1.0
    )

    # Pose data - stored as JSON string
    # Format: {"bone_name": [w, x, y, z], ...}
    bone_rotations: StringProperty(
        name="Bone Rotations",
        description="JSON-encoded bone rotation quaternions",
        default="{}"
    )

    # Bone mask settings
    bone_mask_mode: EnumProperty(
        name="Mask Mode",
        description="Which bones this pose affects",
        items=[
            ('USE_GRID', 'Use Grid Default', 'Inherit bone mask from grid'),
            ('ALL', 'Full Body', 'All bones (override grid)'),
            ('PRESET', 'Preset Region', 'Use predefined bone group (override grid)'),
            ('CUSTOM', 'Custom', 'Custom bone selection'),
        ],
        default='USE_GRID'
    )

    bone_mask_preset: EnumProperty(
        name="Mask Preset",
        description="Predefined bone group",
        items=[
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
        ],
        default='HEAD'
    )

    # Custom bone list - JSON array of bone names
    bone_mask_custom: StringProperty(
        name="Custom Mask",
        description="JSON list of bone names for custom mask",
        default="[]"
    )

    # Visual properties
    color: FloatVectorProperty(
        name="Color",
        description="Dot color",
        subtype='COLOR',
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,
        max=1.0
    )

    # Metadata
    created_time: StringProperty(
        name="Created",
        description="Creation timestamp",
        default=""
    )

    # --- Helper Methods ---

    def generate_id(self):
        """Generate unique ID for this dot"""
        self.id = str(uuid.uuid4())[:8]

    def set_created_time(self):
        """Set creation timestamp to now"""
        self.created_time = datetime.now().isoformat()

    def get_rotations_dict(self):
        """Parse bone_rotations JSON to dict"""
        try:
            return json.loads(self.bone_rotations)
        except json.JSONDecodeError:
            return {}

    def set_rotations_dict(self, rotations):
        """Serialize rotations dict to JSON"""
        self.bone_rotations = json.dumps(rotations)

    def get_rotation(self, bone_name):
        """Get quaternion rotation for specific bone"""
        rotations = self.get_rotations_dict()
        if bone_name in rotations:
            return rotations[bone_name]  # [w, x, y, z]
        return None

    def get_custom_mask_list(self):
        """Parse custom mask JSON to list"""
        try:
            return json.loads(self.bone_mask_custom)
        except json.JSONDecodeError:
            return []

    def set_custom_mask_list(self, bones):
        """Serialize bone list to JSON"""
        self.bone_mask_custom = json.dumps(bones)


class PoseBlendGrid(PropertyGroup):
    """A grid containing multiple pose dots"""

    # Identity
    id: StringProperty(
        name="ID",
        description="Unique identifier for this grid",
        default=""
    )

    name: StringProperty(
        name="Name",
        description="Grid name",
        default="New Grid"
    )

    # Dots collection
    dots: CollectionProperty(
        type=PoseBlendDot,
        name="Dots",
        description="Pose dots on this grid"
    )

    active_dot_index: IntProperty(
        name="Active Dot",
        description="Index of active dot",
        default=-1
    )

    # Lock state - prevents accidental dot modification during animation
    is_locked: BoolProperty(
        name="Locked",
        description="Lock grid to prevent dot modifications (animation mode)",
        default=False
    )

    # Grid settings
    grid_divisions: IntVectorProperty(
        name="Grid Divisions",
        description="Number of grid divisions (columns, rows)",
        size=2,
        default=(8, 8),
        min=2,
        max=32
    )

    snap_to_grid: BoolProperty(
        name="Snap to Grid",
        description="Snap dot placement to grid intersections",
        default=False
    )

    show_grid_lines: BoolProperty(
        name="Show Grid Lines",
        description="Display grid lines",
        default=True
    )

    # Grid-level bone mask (all dots inherit this by default)
    bone_mask_mode: EnumProperty(
        name="Grid Bone Mask",
        description="Which bones this entire grid affects",
        items=[
            ('ALL', 'Full Body', 'All bones'),
            ('PRESET', 'Body Region', 'Specific body region'),
        ],
        default='ALL'
    )

    bone_mask_preset: EnumProperty(
        name="Body Region",
        description="Which body region this grid controls",
        items=[
            ('HEAD', 'Head & Face', 'Head, neck, eyes, jaw - for expressions'),
            ('FACE', 'Face Only', 'Facial bones only - for fine expressions'),
            ('UPPER_BODY', 'Upper Body', 'Spine, chest, shoulders, arms'),
            ('LOWER_BODY', 'Lower Body', 'Pelvis, legs, feet'),
            ('ARMS', 'Arms', 'Both arms and hands'),
            ('ARM_L', 'Left Arm', 'Left arm only'),
            ('ARM_R', 'Right Arm', 'Right arm only'),
            ('HANDS', 'Hands', 'Fingers and hand bones'),
            ('LEGS', 'Legs', 'Both legs and feet'),
            ('SPINE', 'Spine/Torso', 'Core body movement'),
        ],
        default='HEAD'
    )

    # Visual settings
    background_color: FloatVectorProperty(
        name="Background",
        subtype='COLOR',
        size=4,
        default=(0.1, 0.1, 0.1, 0.9),
        min=0.0,
        max=1.0
    )

    grid_line_color: FloatVectorProperty(
        name="Grid Lines",
        subtype='COLOR',
        size=4,
        default=(0.3, 0.3, 0.3, 0.5),
        min=0.0,
        max=1.0
    )

    # Associated armature
    armature_name: StringProperty(
        name="Armature",
        description="Associated armature object name",
        default=""
    )

    # --- Helper Methods ---

    def generate_id(self):
        """Generate unique ID for this grid"""
        self.id = str(uuid.uuid4())[:8]

    def add_dot(self, name, position, rotations_dict, mask_mode='ALL', mask_preset='HEAD'):
        """Add a new dot to the grid"""
        dot = self.dots.add()
        dot.generate_id()
        dot.set_created_time()
        dot.name = name
        dot.position = position
        dot.set_rotations_dict(rotations_dict)
        dot.bone_mask_mode = mask_mode
        if mask_preset is not None:
            dot.bone_mask_preset = mask_preset
        return dot

    def remove_dot(self, index):
        """Remove dot at index"""
        if 0 <= index < len(self.dots):
            self.dots.remove(index)

    def get_active_dot(self):
        """Get currently active dot or None"""
        if 0 <= self.active_dot_index < len(self.dots):
            return self.dots[self.active_dot_index]
        return None


class PoseBlendSettings(PropertyGroup):
    """Scene-level PoseBlend settings"""

    # Mode state
    is_active: BoolProperty(
        name="PoseBlend Active",
        description="PoseBlend mode is active",
        default=False
    )

    # Grids collection
    grids: CollectionProperty(
        type=PoseBlendGrid,
        name="Grids",
        description="Pose blending grids"
    )

    active_grid_index: IntProperty(
        name="Active Grid",
        description="Index of active grid",
        default=-1
    )

    # Interaction settings
    preview_mode: EnumProperty(
        name="Preview Mode",
        description="When to show pose preview",
        items=[
            ('REALTIME', 'Real-time', 'Preview continuously as you drag'),
            ('ON_RELEASE', 'On Release', 'Apply only when mouse released'),
        ],
        default='REALTIME'
    )

    auto_keyframe: BoolProperty(
        name="Auto Keyframe",
        description="Automatically insert keyframes on pose apply",
        default=True
    )

    # Blending settings
    blend_falloff: EnumProperty(
        name="Blend Falloff",
        description="How influence decreases with distance",
        items=[
            ('LINEAR', 'Linear', '1/distance - gentle falloff'),
            ('QUADRATIC', 'Quadratic', '1/distance^2 - natural falloff (default)'),
            ('CUBIC', 'Cubic', '1/distance^3 - sharp falloff'),
            ('SMOOTH', 'Smooth', 'Smoothstep interpolation'),
        ],
        default='QUADRATIC'
    )

    blend_radius: FloatProperty(
        name="Blend Radius",
        description="Maximum influence radius (0 = infinite)",
        default=0.0,
        min=0.0,
        max=1.0
    )

    extrapolation_max: FloatProperty(
        name="Extrapolation",
        description="How far past dots the pose can be pushed (0 = off)",
        default=1.0,
        min=0.0,
        max=2.0,
        subtype='FACTOR'
    )

    # Grid overlay positioning
    grid_screen_position: EnumProperty(
        name="Grid Position",
        description="Where to draw the grid overlay in viewport",
        items=[
            ('BOTTOM_LEFT', 'Bottom Left', 'Grid in bottom left corner'),
            ('LEFT', 'Left Side', 'Grid on left side of viewport'),
            ('RIGHT', 'Right Side', 'Grid on right side of viewport'),
            ('TOP_RIGHT', 'Top Right Corner', 'Grid in top right corner'),
            ('BOTTOM_RIGHT', 'Bottom Right Corner', 'Grid in bottom right corner'),
            ('CENTER', 'Center', 'Grid centered (covers character)'),
        ],
        default='BOTTOM_LEFT'
    )

    grid_screen_size: FloatProperty(
        name="Grid Size",
        description="Grid overlay size (0-1, portion of viewport)",
        default=0.35,
        min=0.1,
        max=0.8
    )

    grid_zoom: FloatProperty(
        name="Zoom",
        description="Zoom level for dot space (lower = zoomed out, more space around dots)",
        default=1.0,
        min=0.2,
        max=4.0,
        subtype='FACTOR'
    )

    grid_pan: FloatVectorProperty(
        name="Pan",
        description="View center in dot space (MMB drag to pan)",
        size=2,
        default=(0.5, 0.5)
    )

    # Cursor position (for drawing)
    cursor_position: FloatVectorProperty(
        name="Cursor",
        size=2,
        default=(0.5, 0.5)
    )

    cursor_active: BoolProperty(
        name="Cursor Active",
        description="Cursor is currently being used for blending",
        default=False
    )

    cursor_over_grid: BoolProperty(
        name="Cursor Over Grid",
        description="Cursor is currently hovering over the grid",
        default=False
    )

    # Viewport
    viewport_camera_name: StringProperty(
        name="Camera",
        default="PoseBlend_Camera"
    )

    # Active armature
    active_armature_name: StringProperty(
        name="Active Armature",
        description="Currently active armature for posing",
        default=""
    )

    # --- Helper Methods ---

    def get_active_grid(self):
        """Get currently active grid or None"""
        if 0 <= self.active_grid_index < len(self.grids):
            return self.grids[self.active_grid_index]
        return None

    def add_grid(self, name="New Grid"):
        """Add a new grid"""
        grid = self.grids.add()
        grid.generate_id()
        grid.name = name
        self.active_grid_index = len(self.grids) - 1
        return grid

    def remove_grid(self, index):
        """Remove grid at index"""
        if 0 <= index < len(self.grids):
            self.grids.remove(index)
            if self.active_grid_index >= len(self.grids):
                self.active_grid_index = len(self.grids) - 1


# ============================================================================
# Registration
# ============================================================================

classes = (
    PoseBlendDot,
    PoseBlendGrid,
    PoseBlendSettings,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.poseblend_settings = PointerProperty(type=PoseBlendSettings)


def unregister():
    del bpy.types.Scene.poseblend_settings

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
