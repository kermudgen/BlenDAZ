"""PoseBridge Body Outline Generator - Creates recognizable body shape outline"""

import bpy
from mathutils import Vector
import math

def create_genesis8_body_outline(armature, outline_name="PB_Outline_Body"):
    """Generate a recognizable body-shaped outline using bones

    Args:
        armature: Genesis 8 armature object
        outline_name: Name for the curve object

    Returns:
        Curve object or None if failed
    """
    if not armature or armature.type != 'ARMATURE':
        print("Error: Need armature object")
        return None

    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    bones = armature.pose.bones
    world_matrix = armature.matrix_world

    try:
        # Get bone positions
        head = world_matrix @ bones['head'].head
        head_top = world_matrix @ bones['head'].tail
        neck = world_matrix @ bones.get('neckLower', bones['chestUpper']).head

        chest = world_matrix @ bones['chestUpper'].head
        l_collar = world_matrix @ bones['lCollar'].head
        r_collar = world_matrix @ bones['rCollar'].head
        l_shoulder = world_matrix @ bones['lShldrBend'].head
        r_shoulder = world_matrix @ bones['rShldrBend'].head

        abdomen = world_matrix @ bones.get('abdomenLower', bones.get('abdomenUpper', bones['pelvis'])).head
        pelvis = world_matrix @ bones['pelvis'].head

        # Arms
        l_elbow = world_matrix @ bones['lForearmBend'].head
        r_elbow = world_matrix @ bones['rForearmBend'].head
        l_wrist = world_matrix @ bones['lHand'].head
        r_wrist = world_matrix @ bones['lHand'].tail
        l_hand_end = l_wrist + (l_wrist - l_elbow).normalized() * 0.15
        r_hand_end = r_wrist + (r_wrist - r_elbow).normalized() * 0.15

        # Legs
        l_hip = world_matrix @ bones['lThighBend'].head
        r_hip = world_matrix @ bones['rThighBend'].head
        l_knee = world_matrix @ bones['lShin'].head
        r_knee = world_matrix @ bones['rShin'].head
        l_ankle = world_matrix @ bones['lFoot'].head
        r_ankle = world_matrix @ bones['rFoot'].head
        l_toe = world_matrix @ bones['lFoot'].tail
        r_toe = world_matrix @ bones['rFoot'].tail

    except KeyError as e:
        print(f"Missing bone: {e}")
        return None

    # Create curve data
    curve_data = bpy.data.curves.new(outline_name, 'CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = 0.01
    curve_data.bevel_resolution = 3

    # HEAD - Draw as circle
    head_radius = (head_top - head).length * 0.6
    draw_circle(curve_data, head, head_radius, 16)

    # TORSO - Draw as filled shape
    shoulder_width = (r_shoulder - l_shoulder).length / 2
    hip_width = (r_hip - l_hip).length / 2

    torso_points = [
        l_shoulder,
        l_shoulder + Vector((0, 0.05, 0)),  # Back of shoulder
        lerp_3d(l_shoulder, l_hip, 0.5) + Vector((-hip_width * 0.8, 0, 0)),  # Mid waist left
        l_hip,
        r_hip,
        lerp_3d(r_shoulder, r_hip, 0.5) + Vector((hip_width * 0.8, 0, 0)),  # Mid waist right
        r_shoulder + Vector((0, 0.05, 0)),  # Back of shoulder
        r_shoulder,
    ]
    draw_closed_shape(curve_data, torso_points)

    # LEFT ARM - Draw as tube
    draw_limb(curve_data, l_shoulder, l_elbow, 0.035, 0.03)
    draw_limb(curve_data, l_elbow, l_wrist, 0.03, 0.025)
    draw_limb(curve_data, l_wrist, l_hand_end, 0.025, 0.02)

    # RIGHT ARM - Draw as tube
    draw_limb(curve_data, r_shoulder, r_elbow, 0.035, 0.03)
    draw_limb(curve_data, r_elbow, r_wrist, 0.03, 0.025)
    draw_limb(curve_data, r_wrist, r_hand_end, 0.025, 0.02)

    # LEFT LEG - Draw as tube
    draw_limb(curve_data, l_hip, l_knee, 0.055, 0.04)
    draw_limb(curve_data, l_knee, l_ankle, 0.04, 0.035)
    draw_limb(curve_data, l_ankle, l_toe, 0.035, 0.03)

    # RIGHT LEG - Draw as tube
    draw_limb(curve_data, r_hip, r_knee, 0.055, 0.04)
    draw_limb(curve_data, r_knee, r_ankle, 0.04, 0.035)
    draw_limb(curve_data, r_ankle, r_toe, 0.035, 0.03)

    # Create object
    curve_obj = bpy.data.objects.new(outline_name, curve_data)
    bpy.context.scene.collection.objects.link(curve_obj)

    # Material
    mat = bpy.data.materials.new(f"{outline_name}_Material")
    mat.diffuse_color = (0, 0.8, 1, 1)

    if bpy.app.version >= (4, 0, 0):
        # Modern Blender - use nodes
        mat.use_nodes = True
        if mat.node_tree:
            nodes = mat.node_tree.nodes
            nodes.clear()
            emission = nodes.new('ShaderNodeEmission')
            emission.inputs['Color'].default_value = (0, 0.8, 1, 1)
            emission.inputs['Strength'].default_value = 1.5
            output = nodes.new('ShaderNodeOutputMaterial')
            mat.node_tree.links.new(emission.outputs['Emission'], output.inputs['Surface'])

    curve_data.materials.append(mat)

    print(f"Created body outline: {outline_name}")
    return curve_obj


def lerp_3d(a, b, t):
    """Linear interpolation between two 3D points"""
    return a + (b - a) * t


def draw_circle(curve_data, center, radius, segments=16):
    """Draw a circle"""
    spline = curve_data.splines.new('POLY')
    spline.points.add(segments - 1)
    spline.use_cyclic_u = True

    for i in range(segments):
        angle = (i / segments) * 2 * math.pi
        x_offset = math.cos(angle) * radius
        z_offset = math.sin(angle) * radius
        pos = center + Vector((x_offset, 0, z_offset))
        spline.points[i].co = (*pos, 1.0)


def draw_closed_shape(curve_data, points):
    """Draw a closed polygon"""
    spline = curve_data.splines.new('POLY')
    spline.points.add(len(points) - 1)
    spline.use_cyclic_u = True

    for i, pos in enumerate(points):
        spline.points[i].co = (*pos, 1.0)


def draw_limb(curve_data, start, end, width_start, width_end):
    """Draw a limb as a rectangular tube"""
    direction = (end - start).normalized()
    length = (end - start).length

    # Find perpendicular vector
    if abs(direction.z) < 0.9:
        up = Vector((0, 0, 1))
    else:
        up = Vector((1, 0, 0))

    perp = direction.cross(up).normalized()

    # Create 4 corners of rectangle
    points = [
        start + perp * width_start,
        end + perp * width_end,
        end - perp * width_end,
        start - perp * width_start,
    ]

    draw_closed_shape(curve_data, points)


# Operator
class POSE_OT_posebridge_generate_body_outline(bpy.types.Operator):
    """Generate body-shaped outline"""
    bl_idname = "pose.posebridge_generate_body_outline"
    bl_label = "Generate Body Outline"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        curve_obj = create_genesis8_body_outline(context.active_object)
        if curve_obj:
            self.report({'INFO'}, f"Generated outline: {curve_obj.name}")
            return {'FINISHED'}
        return {'CANCELLED'}


def register():
    bpy.utils.register_class(POSE_OT_posebridge_generate_body_outline)

def unregister():
    bpy.utils.unregister_class(POSE_OT_posebridge_generate_body_outline)


if __name__ == "__main__":
    register()

    # Auto-run
    armature = bpy.context.active_object
    if armature and armature.type == 'ARMATURE':
        print(f"Generating body outline for: {armature.name}")
        create_genesis8_body_outline(armature)
    else:
        print("Please select the Genesis 8 armature")
