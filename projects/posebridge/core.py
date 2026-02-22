"""PoseBridge Core - PropertyGroup definitions and data structures"""

import bpy
import sys
import os
from bpy.types import PropertyGroup
from bpy.props import (
    BoolProperty,
    FloatProperty,
    StringProperty,
    EnumProperty,
    CollectionProperty,
    FloatVectorProperty,
    PointerProperty,
)

# Ensure addon root is importable
_addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _addon_dir not in sys.path:
    sys.path.insert(0, _addon_dir)

from daz_shared_utils import FACE_EXPRESSION_PRESETS


# ============================================================================
# Expression/Viseme Slider Update Callback
# ============================================================================

def _apply_expression_preset(self, context, preset_name):
    """Update callback: apply a face preset scaled by the slider value."""
    preset_data = FACE_EXPRESSION_PRESETS.get(preset_name)
    if not preset_data:
        return

    # Get armature
    settings = context.scene.posebridge_settings
    armature = None
    if settings.active_armature_name:
        armature = bpy.data.objects.get(settings.active_armature_name)
    if not armature:
        obj = context.active_object
        if obj and obj.type == 'ARMATURE':
            armature = obj
        elif obj and obj.type == 'MESH':
            armature = obj.find_armature()
    if not armature:
        return

    # Get slider value (the property that just changed)
    slider_value = getattr(self, f'expr_{preset_name}', 0.0) if not preset_name.startswith('vis_') else getattr(self, preset_name, 0.0)

    # Apply preset values scaled by slider
    for prop_name, max_value in preset_data.items():
        if prop_name in armature:
            armature[prop_name] = slider_value * max_value

    # Trigger depsgraph update
    armature.update_tag()
    context.view_layer.depsgraph.update()
    context.area.tag_redraw()


def _make_expr_update(preset_name):
    """Factory: create an update callback for a specific preset."""
    def _update(self, context):
        _apply_expression_preset(self, context, preset_name)
    return _update

# ============================================================================
# PropertyGroup Classes
# ============================================================================

class PoseBridgeControlPoint(PropertyGroup):
    """Individual control point data"""

    id: StringProperty(
        name="ID",
        description="Unique identifier for this control point",
        default=""
    )

    bone_name: StringProperty(
        name="Bone Name",
        description="Name of the bone this control point controls",
        default=""
    )

    label: StringProperty(
        name="Label",
        description="Display label for this control point",
        default=""
    )

    group: StringProperty(
        name="Group",
        description="Body region group (head, arms, torso, legs)",
        default=""
    )

    control_type: EnumProperty(
        name="Control Type",
        description="Type of control point",
        items=[
            ('single', 'Single Bone', 'Controls a single bone'),
            ('multi', 'Multi Bone', 'Controls multiple bones as a group'),
        ],
        default='single'
    )

    shape: StringProperty(
        name="Shape",
        description="Visual shape for this control point (circle, diamond, square)",
        default=''
    )

    position_2d: FloatVectorProperty(
        name="2D Position",
        description="Control point position in viewport coordinates (normalized 0-1)",
        size=2,
        default=(0.5, 0.5),
        min=0.0,
        max=1.0
    )

    position_3d_fixed: FloatVectorProperty(
        name="Fixed 3D Position",
        description="Fixed 3D world position from T-pose (for static control points)",
        size=3,
        default=(0.0, 0.0, 0.0)
    )

    is_hovered: BoolProperty(
        name="Is Hovered",
        description="Whether mouse is currently hovering over this control point",
        default=False
    )

    is_selected: BoolProperty(
        name="Is Selected",
        description="Whether this control point is currently selected",
        default=False
    )

    panel_view: StringProperty(
        name="Panel View",
        description="Which panel this control point belongs to",
        default='body'
    )

    interaction_mode: EnumProperty(
        name="Interaction Mode",
        description="How this control point drives changes",
        items=[
            ('rotation', 'Rotation', 'Drive bone rotation (body/hands)'),
            ('morph', 'Morph', 'Drive FACS morph property value (face)'),
        ],
        default='rotation'
    )


class PoseBridgeCharacter(PropertyGroup):
    """Per-armature data"""

    armature_name: StringProperty(
        name="Armature Name",
        description="Name of the armature this data belongs to",
        default=""
    )

    control_points: CollectionProperty(
        type=PoseBridgeControlPoint,
        name="Control Points",
        description="Control points for this character"
    )

    active_panel: EnumProperty(
        name="Active Panel",
        description="Currently active panel view",
        items=[
            ('body', 'Body', 'Full body panel'),
            ('hands', 'Hands', 'Both hands detail panel'),
            ('face', 'Face', 'Face detail panel'),
        ],
        default='body'
    )

    outline_gp_name: StringProperty(
        name="Outline GP Name",
        description="Name of the Grease Pencil object for the outline",
        default=""
    )


class PoseBridgeSettings(PropertyGroup):
    """Scene-level PoseBridge settings"""

    is_active: BoolProperty(
        name="PoseBridge Mode",
        description="Enable/disable PoseBridge mode",
        default=False
    )

    sensitivity: FloatProperty(
        name="Sensitivity",
        description="Rotation sensitivity (radians per pixel)",
        default=0.01,
        min=0.001,
        max=0.05,
        step=0.001,
        precision=3
    )

    show_outline: BoolProperty(
        name="Show Outline",
        description="Show/hide the Grease Pencil outline",
        default=True
    )

    show_control_points: BoolProperty(
        name="Show Control Points",
        description="Show/hide control point widgets",
        default=True
    )

    auto_keyframe: BoolProperty(
        name="Auto Keyframe",
        description="Automatically keyframe rotations on mouse release",
        default=True
    )

    enforce_constraints: BoolProperty(
        name="Enforce Constraints",
        description="Enforce LIMIT_ROTATION constraints during posing (reads back constrained result from depsgraph after each rotation)",
        default=True
    )

    active_armature_name: StringProperty(
        name="Active Armature",
        description="Name of the currently active armature for PoseBridge",
        default=""
    )

    active_panel: EnumProperty(
        name="Active Panel",
        description="Currently active panel view",
        items=[
            ('body', 'Body', 'Full body panel'),
            ('hands', 'Hands', 'Both hands detail panel'),
            ('face', 'Face', 'Face detail panel'),
        ],
        default='body'
    )

    morph_sensitivity: FloatProperty(
        name="Morph Sensitivity",
        description="Morph value change per pixel of mouse movement",
        default=0.005,
        min=0.001,
        max=0.02,
        step=0.001,
        precision=4
    )

    control_points_fixed: CollectionProperty(
        type=PoseBridgeControlPoint,
        name="Fixed Control Points",
        description="Control points with fixed T-pose positions"
    )


# Add expression/viseme slider properties dynamically
# Each is a 0-1 FloatProperty with an update callback that scales the preset
_EXPR_SLIDER_DEFS = [
    ('expr_smile', 'Smile', 'smile'),
    ('expr_frown', 'Frown', 'frown'),
    ('expr_surprise', 'Surprise', 'surprise'),
    ('expr_anger', 'Anger', 'anger'),
    ('expr_disgust', 'Disgust', 'disgust'),
    ('expr_fear', 'Fear', 'fear'),
    ('expr_sadness', 'Sadness', 'sadness'),
    ('expr_wink_l', 'Wink L', 'wink_l'),
    ('expr_wink_r', 'Wink R', 'wink_r'),
    ('vis_AA', 'AA', 'vis_AA'),
    ('vis_EE', 'EE', 'vis_EE'),
    ('vis_IH', 'IH', 'vis_IH'),
    ('vis_OH', 'OH', 'vis_OH'),
    ('vis_OO', 'OO', 'vis_OO'),
    ('vis_FV', 'FV', 'vis_FV'),
    ('vis_TH', 'TH', 'vis_TH'),
    ('vis_MM', 'MM', 'vis_MM'),
    ('vis_CH', 'CH', 'vis_CH'),
]

for _prop_id, _label, _preset_name in _EXPR_SLIDER_DEFS:
    PoseBridgeSettings.__annotations__[_prop_id] = FloatProperty(
        name=_label,
        description=f"Intensity of {_label} expression",
        default=0.0, min=0.0, max=1.0,
        step=1, precision=2,
        update=_make_expr_update(_preset_name),
    )


# ============================================================================
# Helper Functions
# ============================================================================

def get_posebridge_character(armature):
    """Get or create PoseBridgeCharacter data for armature

    Args:
        armature: Armature object

    Returns:
        PoseBridgeCharacter: Character data for this armature
    """
    # For Phase 1, we'll use a simple scene property to store character data
    # In Phase 4 we'll expand this to support multiple characters

    scene = bpy.context.scene
    settings = scene.posebridge_settings

    # For now, just store the armature name
    settings.active_armature_name = armature.name

    # In a future phase, we'll return a proper character object
    # For now, return a placeholder dict
    return {
        'armature_name': armature.name,
        'control_points': [],
        'active_panel': 'body'
    }


def initialize_control_points_for_character(armature, panel_view='body'):
    """Initialize control point positions from bone locations

    Args:
        armature: Armature object
        panel_view: Which panel to initialize ('body', 'head', 'hands_left', 'hands_right')

    Returns:
        List of initialized control points with calculated 2D positions
    """
    # Import shared utilities
    import sys
    import os
    addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if addon_dir not in sys.path:
        sys.path.insert(0, addon_dir)

    from daz_shared_utils import get_genesis8_control_points

    # Get control point definitions
    control_point_defs = get_genesis8_control_points()

    initialized_points = []

    for cp_def in control_point_defs:
        # Determine if this is a multi-bone group or single-bone control
        is_multi = 'bone_names' in cp_def

        if is_multi:
            bone_name = cp_def.get('reference_bone', cp_def['bone_names'][0])
            label = cp_def.get('label', cp_def['id'])  # Human-readable name for tooltips
            control_type = 'multi'
        else:
            bone_name = cp_def.get('bone_name', '')
            label = cp_def.get('label', bone_name)
            control_type = 'single'

        # Skip if required bone doesn't exist in armature
        if bone_name and bone_name not in armature.pose.bones:
            continue

        cp_data = {
            'id': cp_def['id'],
            'bone_name': bone_name,
            'label': label,
            'group': cp_def.get('group', ''),
            'control_type': control_type,
            'panel_view': 'body',
            'position_2d': (0.5, 0.5),  # Placeholder - calculated in drawing phase
            'is_hovered': False,
            'is_selected': False
        }

        initialized_points.append(cp_data)

    return initialized_points

# ============================================================================
# Registration
# ============================================================================

classes = (
    PoseBridgeControlPoint,  # Must be registered first (used in CollectionProperty below)
    PoseBridgeCharacter,
    PoseBridgeSettings,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # Register scene property
    bpy.types.Scene.posebridge_settings = PointerProperty(type=PoseBridgeSettings)

def unregister():
    del bpy.types.Scene.posebridge_settings

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
