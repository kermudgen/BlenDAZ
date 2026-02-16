"""PoseBridge Simple Outline Generator - Fast skeleton-based outline"""

import bpy
from mathutils import Vector

def create_genesis8_body_outline_simple(armature, outline_name="PB_Outline_Body"):
    """Generate a simple skeleton-based outline (FAST - no mesh processing)

    Args:
        armature: Genesis 8 armature object
        outline_name: Name for the curve object

    Returns:
        Curve object or None if failed
    """
    if not armature or armature.type != 'ARMATURE':
        print("Error: Need armature object")
        return None

    # Ensure we're in object mode
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Get bone positions
    bones = armature.pose.bones
    world_matrix = armature.matrix_world

    # Print bone names for debugging (looking for torso/arm bones)
    arm_bones = [b.name for b in bones if any(x in b.name.lower() for x in ['shldr', 'collar', 'arm', 'hand', 'chest', 'neck'])]
    print(f"Arm/torso bones: {arm_bones}")

    try:
        # Head
        head = world_matrix @ bones['head'].head

        # Neck fallback to chest
        neck = world_matrix @ bones.get('neckLower', bones.get('chest', bones['hip'])).head

        # Torso - Genesis 8 uses different names
        chest_l = world_matrix @ bones.get('lCollar', bones.get('lShldrBend', bones['lForearmBend'])).head
        chest_r = world_matrix @ bones.get('rCollar', bones.get('rShldrBend', bones['rForearmBend'])).head
        pelvis_l = world_matrix @ bones['lThighBend'].head
        pelvis_r = world_matrix @ bones['rThighBend'].head

        # Arms
        l_shldr = world_matrix @ bones.get('lCollar', bones.get('lShldrBend', bones['lForearmBend'])).head
        l_elbow = world_matrix @ bones.get('lForearmBend', bones['lHand']).head
        l_hand = world_matrix @ bones['lHand'].head
        r_shldr = world_matrix @ bones.get('rCollar', bones.get('rShldrBend', bones['rForearmBend'])).head
        r_elbow = world_matrix @ bones.get('rForearmBend', bones['rHand']).head
        r_hand = world_matrix @ bones['rHand'].head

        # Legs
        l_hip = world_matrix @ bones['lThighBend'].head
        l_knee = world_matrix @ bones['lShin'].head
        l_foot = world_matrix @ bones['lFoot'].head
        r_hip = world_matrix @ bones['rThighBend'].head
        r_knee = world_matrix @ bones['rShin'].head
        r_foot = world_matrix @ bones['rFoot'].head

    except (KeyError, AttributeError) as e:
        print(f"Error finding bones: {e}")
        print("Check console for available bone names")
        return None

    # Create curve data
    curve_data = bpy.data.curves.new(outline_name, 'CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = 0.015
    curve_data.bevel_resolution = 4

    # Create body outline (torso loop)
    body_points = [
        chest_l + Vector((-0.15, 0, 0)),  # Left shoulder width
        chest_l,
        neck,
        head + Vector((0, 0, 0.15)),  # Top of head
        neck,
        chest_r,
        chest_r + Vector((0.15, 0, 0)),  # Right shoulder width
        pelvis_r + Vector((0.1, 0, 0)),  # Right hip
        pelvis_r,
        pelvis_l,
        pelvis_l + Vector((-0.1, 0, 0)),  # Left hip
        chest_l + Vector((-0.15, 0, 0)),  # Close loop
    ]

    spline = curve_data.splines.new('POLY')
    spline.points.add(len(body_points) - 1)
    for i, pos in enumerate(body_points):
        spline.points[i].co = (*pos, 1.0)
    spline.use_cyclic_u = True

    # Left arm
    left_arm_points = [l_shldr, l_elbow, l_hand]
    spline = curve_data.splines.new('POLY')
    spline.points.add(len(left_arm_points) - 1)
    for i, pos in enumerate(left_arm_points):
        spline.points[i].co = (*pos, 1.0)

    # Right arm
    right_arm_points = [r_shldr, r_elbow, r_hand]
    spline = curve_data.splines.new('POLY')
    spline.points.add(len(right_arm_points) - 1)
    for i, pos in enumerate(right_arm_points):
        spline.points[i].co = (*pos, 1.0)

    # Left leg
    left_leg_points = [l_hip, l_knee, l_foot]
    spline = curve_data.splines.new('POLY')
    spline.points.add(len(left_leg_points) - 1)
    for i, pos in enumerate(left_leg_points):
        spline.points[i].co = (*pos, 1.0)

    # Right leg
    right_leg_points = [r_hip, r_knee, r_foot]
    spline = curve_data.splines.new('POLY')
    spline.points.add(len(right_leg_points) - 1)
    for i, pos in enumerate(right_leg_points):
        spline.points[i].co = (*pos, 1.0)

    # Create curve object
    curve_obj = bpy.data.objects.new(outline_name, curve_data)
    bpy.context.scene.collection.objects.link(curve_obj)

    # Create material (cyan)
    mat = bpy.data.materials.new(f"{outline_name}_Material")
    mat.use_nodes = True
    mat.diffuse_color = (0, 0.8, 1, 1)

    # Emission shader for visibility
    if mat.node_tree:
        nodes = mat.node_tree.nodes
        nodes.clear()
        emission = nodes.new('ShaderNodeEmission')
        emission.inputs['Color'].default_value = (0, 0.8, 1, 1)
        emission.inputs['Strength'].default_value = 1.5
        output = nodes.new('ShaderNodeOutputMaterial')
        mat.node_tree.links.new(emission.outputs['Emission'], output.inputs['Surface'])

    curve_data.materials.append(mat)

    print(f"Created simple outline: {outline_name}")
    return curve_obj


# ============================================================================
# Operator
# ============================================================================

class POSE_OT_posebridge_generate_outline_simple(bpy.types.Operator):
    """Generate simple skeleton-based outline (FAST)"""
    bl_idname = "pose.posebridge_generate_outline_simple"
    bl_label = "Generate Simple Outline"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj:
            return False
        return obj.type == 'ARMATURE'

    def execute(self, context):
        armature = context.active_object
        curve_obj = create_genesis8_body_outline_simple(armature)

        if curve_obj:
            self.report({'INFO'}, f"Generated simple outline: {curve_obj.name}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Failed to generate outline")
            return {'CANCELLED'}


# ============================================================================
# Registration
# ============================================================================

def register():
    bpy.utils.register_class(POSE_OT_posebridge_generate_outline_simple)

def unregister():
    bpy.utils.unregister_class(POSE_OT_posebridge_generate_outline_simple)


# ============================================================================
# Standalone Script Usage
# ============================================================================

if __name__ == "__main__":
    register()

    # Auto-run
    armature = bpy.context.active_object
    if armature and armature.type == 'ARMATURE':
        print(f"Generating simple outline for: {armature.name}")
        create_genesis8_body_outline_simple(armature)
    else:
        print("Please select the Genesis 8 armature")
