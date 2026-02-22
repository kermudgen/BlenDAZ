"""PoseBlend Import/Export - JSON serialization for grids and poses"""

import bpy
from bpy.types import Operator
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper
import json
from datetime import datetime


# ============================================================================
# Export Format Version
# ============================================================================

POSEBLEND_FORMAT_VERSION = "1.0"


# ============================================================================
# Export Functions
# ============================================================================

def export_grid_to_dict(grid, armature_type="Genesis8"):
    """Convert a PoseBlendGrid to exportable dictionary

    Args:
        grid: PoseBlendGrid PropertyGroup
        armature_type: String identifier for rig type

    Returns:
        Dictionary ready for JSON serialization
    """
    data = {
        "version": POSEBLEND_FORMAT_VERSION,
        "type": "poseblend_grid",
        "name": grid.name,
        "armature_type": armature_type,
        "grid_divisions": list(grid.grid_divisions),
        "created": datetime.now().isoformat(),
        "settings": {
            "snap_to_grid": grid.snap_to_grid,
            "show_grid_lines": grid.show_grid_lines,
            "background_color": list(grid.background_color),
            "grid_line_color": list(grid.grid_line_color),
            "default_mask_mode": grid.bone_mask_mode,
            "default_mask_preset": grid.bone_mask_preset,
        },
        "dots": []
    }

    # Export each dot
    for dot in grid.dots:
        dot_data = {
            "id": dot.id,
            "name": dot.name,
            "position": list(dot.position),
            "mask_mode": dot.bone_mask_mode,
            "mask_preset": dot.bone_mask_preset if dot.bone_mask_mode == 'PRESET' else None,
            "mask_custom": dot.get_custom_mask_list() if dot.bone_mask_mode == 'CUSTOM' else None,
            "color": list(dot.color),
            "created": dot.created_time,
            "rotations": dot.get_rotations_dict()
        }
        data["dots"].append(dot_data)

    return data


def export_grid_to_json(grid, filepath, armature_type="Genesis8"):
    """Export grid to JSON file

    Args:
        grid: PoseBlendGrid to export
        filepath: Output file path
        armature_type: Rig type identifier

    Returns:
        True if successful
    """
    try:
        data = export_grid_to_dict(grid, armature_type)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        return True
    except Exception as e:
        print(f"Export error: {e}")
        return False


# ============================================================================
# Import Functions
# ============================================================================

def import_grid_from_dict(data, settings, bone_remap=None):
    """Import grid from dictionary data

    Args:
        data: Dictionary from JSON
        settings: PoseBlendSettings to add grid to
        bone_remap: Optional dict for remapping bone names

    Returns:
        Created PoseBlendGrid, or None on failure
    """
    # Validate format
    if data.get("type") != "poseblend_grid":
        print("Invalid file type")
        return None

    version = data.get("version", "1.0")
    # TODO: Handle version migration if needed

    # Create new grid
    grid = settings.add_grid(data.get("name", "Imported Grid"))

    # Apply settings
    grid_settings = data.get("settings", {})
    if "grid_divisions" in data:
        grid.grid_divisions = tuple(data["grid_divisions"])
    grid.snap_to_grid = grid_settings.get("snap_to_grid", False)
    grid.show_grid_lines = grid_settings.get("show_grid_lines", True)

    if "background_color" in grid_settings:
        grid.background_color = tuple(grid_settings["background_color"])
    if "grid_line_color" in grid_settings:
        grid.grid_line_color = tuple(grid_settings["grid_line_color"])

    grid.bone_mask_mode = grid_settings.get("default_mask_mode", "ALL")
    grid.bone_mask_preset = grid_settings.get("default_mask_preset", "HEAD")

    # Import dots
    for dot_data in data.get("dots", []):
        # Remap bone names if requested
        rotations = dot_data.get("rotations", {})
        if bone_remap:
            rotations = remap_bone_names(rotations, bone_remap)

        dot = grid.add_dot(
            name=dot_data.get("name", "Pose"),
            position=tuple(dot_data.get("position", (0.5, 0.5))),
            rotations_dict=rotations,
            mask_mode=dot_data.get("mask_mode", "ALL"),
            mask_preset=dot_data.get("mask_preset", "HEAD")
        )

        # Set additional properties
        if "color" in dot_data:
            dot.color = tuple(dot_data["color"])
        if "id" in dot_data:
            dot.id = dot_data["id"]
        if "created" in dot_data:
            dot.created_time = dot_data["created"]

        # Handle custom mask
        if dot_data.get("mask_mode") == 'CUSTOM' and dot_data.get("mask_custom"):
            custom_bones = dot_data["mask_custom"]
            if bone_remap:
                custom_bones = [bone_remap.get(b, b) for b in custom_bones]
            dot.set_custom_mask_list(custom_bones)

    return grid


def import_grid_from_json(filepath, settings, bone_remap=None):
    """Import grid from JSON file

    Args:
        filepath: Input file path
        settings: PoseBlendSettings to add grid to
        bone_remap: Optional bone name remapping dict

    Returns:
        Created PoseBlendGrid, or None on failure
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return import_grid_from_dict(data, settings, bone_remap)
    except Exception as e:
        print(f"Import error: {e}")
        return None


# ============================================================================
# Bone Name Remapping
# ============================================================================

# Common bone remapping presets
BONE_REMAP_PRESETS = {
    'genesis8_to_rigify': {
        'lShldr': 'shoulder.L',
        'rShldr': 'shoulder.R',
        'lShldrBend': 'upper_arm.L',
        'rShldrBend': 'upper_arm.R',
        'lForeArm': 'forearm.L',
        'rForeArm': 'forearm.R',
        'lHand': 'hand.L',
        'rHand': 'hand.R',
        'lThigh': 'thigh.L',
        'rThigh': 'thigh.R',
        'lShin': 'shin.L',
        'rShin': 'shin.R',
        'lFoot': 'foot.L',
        'rFoot': 'foot.R',
        # Add more mappings as needed
    },
    'rigify_to_genesis8': {
        'shoulder.L': 'lShldr',
        'shoulder.R': 'rShldr',
        'upper_arm.L': 'lShldrBend',
        'upper_arm.R': 'rShldrBend',
        'forearm.L': 'lForeArm',
        'forearm.R': 'rForeArm',
        'hand.L': 'lHand',
        'hand.R': 'rHand',
        'thigh.L': 'lThigh',
        'thigh.R': 'rThigh',
        'shin.L': 'lShin',
        'shin.R': 'rShin',
        'foot.L': 'lFoot',
        'foot.R': 'rFoot',
    }
}


def remap_bone_names(rotations, remap_dict):
    """Remap bone names in rotations dictionary

    Args:
        rotations: Dict of {bone_name: rotation_data}
        remap_dict: Dict of {old_name: new_name}

    Returns:
        New dict with remapped names
    """
    remapped = {}
    for bone_name, rotation in rotations.items():
        new_name = remap_dict.get(bone_name, bone_name)
        remapped[new_name] = rotation
    return remapped


def get_remap_preset(preset_name):
    """Get bone remapping preset by name

    Args:
        preset_name: Key from BONE_REMAP_PRESETS

    Returns:
        Remap dict, or empty dict if not found
    """
    return BONE_REMAP_PRESETS.get(preset_name, {})


# ============================================================================
# Operators
# ============================================================================

class POSEBLEND_OT_export_grid(Operator, ExportHelper):
    """Export active grid to JSON file"""
    bl_idname = "poseblend.export_grid"
    bl_label = "Export PoseBlend Grid"

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context):
        settings = context.scene.poseblend_settings
        grid = settings.get_active_grid()

        if not grid:
            self.report({'WARNING'}, "No active grid to export")
            return {'CANCELLED'}

        success = export_grid_to_json(grid, self.filepath)

        if success:
            self.report({'INFO'}, f"Exported: {self.filepath}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Export failed")
            return {'CANCELLED'}


class POSEBLEND_OT_import_grid(Operator, ImportHelper):
    """Import grid from JSON file"""
    bl_idname = "poseblend.import_grid"
    bl_label = "Import PoseBlend Grid"

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    remap_preset: bpy.props.EnumProperty(
        name="Bone Remap",
        description="Remap bone names on import",
        items=[
            ('NONE', 'None', 'No remapping'),
            ('genesis8_to_rigify', 'Genesis8 to Rigify', 'Convert Genesis8 names to Rigify'),
            ('rigify_to_genesis8', 'Rigify to Genesis8', 'Convert Rigify names to Genesis8'),
        ],
        default='NONE'
    )

    def execute(self, context):
        settings = context.scene.poseblend_settings

        # Get remap dict if requested
        bone_remap = None
        if self.remap_preset != 'NONE':
            bone_remap = get_remap_preset(self.remap_preset)

        grid = import_grid_from_json(self.filepath, settings, bone_remap)

        if grid:
            self.report({'INFO'}, f"Imported: {grid.name} ({len(grid.dots)} dots)")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Import failed")
            return {'CANCELLED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "remap_preset")


# ============================================================================
# Registration
# ============================================================================

classes = (
    POSEBLEND_OT_export_grid,
    POSEBLEND_OT_import_grid,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
