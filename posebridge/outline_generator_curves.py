"""PoseBridge Outline Generator - Creates curve outlines for Genesis 8 characters"""

import bpy
from mathutils import Vector

import logging
log = logging.getLogger(__name__)


# ============================================================================
# Outline Generation Using Curves (Works in all Blender versions)
# ============================================================================

def create_genesis8_body_outline(mesh_obj, outline_name="PB_Outline_Body"):
    """Generate a curve outline from mesh silhouette (rest pose)

    Args:
        mesh_obj: Genesis 8 mesh object
        outline_name: Name for the curve object

    Returns:
        Curve object or None if failed
    """
    if not mesh_obj or mesh_obj.type != 'MESH':
        log.warning("Error: Invalid mesh object")
        return None

    # Ensure we're in object mode
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Get mesh data
    mesh = mesh_obj.data
    world_matrix = mesh_obj.matrix_world

    # For body outline, we want silhouette from front view, not boundary edges
    # (boundary edges would be mouth/eyes/nostrils which we don't want)
    log.info("Detecting silhouette edges from front view...")
    silhouette_edges = detect_silhouette_from_view(mesh, world_matrix)

    # Build stroke chains from silhouette edges
    stroke_chains = build_stroke_chains(silhouette_edges, mesh.vertices, world_matrix)

    if not stroke_chains:
        log.info("No stroke chains generated")
        return None

    # Create curve data
    curve_data = bpy.data.curves.new(outline_name, 'CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = 0.02  # Line thickness (increased for visibility)
    curve_data.bevel_resolution = 4  # Smoothness

    # Create splines from stroke chains
    for chain in stroke_chains:
        if len(chain) < 2:
            continue

        # Create new spline
        spline = curve_data.splines.new('POLY')
        spline.points.add(len(chain) - 1)  # -1 because spline starts with 1 point

        # Set point positions
        for i, vertex_pos in enumerate(chain):
            spline.points[i].co = (*vertex_pos, 1.0)  # 4D coordinate (x, y, z, w)

        # Close spline if it's a loop
        if chain[0] == chain[-1]:
            spline.use_cyclic_u = True

    # Create curve object
    curve_obj = bpy.data.objects.new(outline_name, curve_data)
    bpy.context.scene.collection.objects.link(curve_obj)

    # Create material (cyan)
    mat = bpy.data.materials.new(f"{outline_name}_Material")
    mat.use_nodes = True
    mat.diffuse_color = (0, 0.8, 1, 1)  # Cyan

    # Set emission for visibility
    if mat.node_tree:
        nodes = mat.node_tree.nodes
        nodes.clear()

        # Create emission node
        emission = nodes.new('ShaderNodeEmission')
        emission.inputs['Color'].default_value = (0, 0.8, 1, 1)  # Cyan
        emission.inputs['Strength'].default_value = 1.0

        # Create output node
        output = nodes.new('ShaderNodeOutputMaterial')

        # Link nodes
        mat.node_tree.links.new(emission.outputs['Emission'], output.inputs['Surface'])

    curve_data.materials.append(mat)

    log.info(f"Created outline: {outline_name} with {len(stroke_chains)} splines")
    return curve_obj


def detect_silhouette_from_view(mesh, world_matrix, view_direction=Vector((0, 1, 0))):
    """Detect silhouette edges from a specific view direction

    Args:
        mesh: Mesh data
        world_matrix: Object world matrix
        view_direction: View direction vector (default: front view)

    Returns:
        List of silhouette edges
    """
    silhouette_edges = []

    # For each edge, check if adjacent faces are facing different directions
    for edge in mesh.edges:
        adjacent_faces = []

        # Find faces that use this edge
        for poly in mesh.polygons:
            if set(edge.vertices).issubset(set(poly.vertices)):
                adjacent_faces.append(poly)

        # If edge has exactly 2 adjacent faces
        if len(adjacent_faces) == 2:
            # Get face normals in world space
            normal1 = world_matrix.to_3x3() @ adjacent_faces[0].normal
            normal2 = world_matrix.to_3x3() @ adjacent_faces[1].normal

            # Check if faces are facing opposite directions relative to view
            dot1 = normal1.dot(view_direction)
            dot2 = normal2.dot(view_direction)

            # Silhouette edge if one face is front-facing and one is back-facing
            if (dot1 > 0 and dot2 < 0) or (dot1 < 0 and dot2 > 0):
                silhouette_edges.append(edge)

    return silhouette_edges


def build_stroke_chains(edges, vertices, world_matrix):
    """Build continuous stroke chains from edges

    Args:
        edges: List of edges to connect
        vertices: Mesh vertices
        world_matrix: Object world matrix

    Returns:
        List of vertex position chains (each chain is a list of Vector)
    """
    if not edges:
        return []

    # Build adjacency map
    vert_to_edges = {}
    for edge in edges:
        v1, v2 = edge.vertices
        if v1 not in vert_to_edges:
            vert_to_edges[v1] = []
        if v2 not in vert_to_edges:
            vert_to_edges[v2] = []
        vert_to_edges[v1].append((v2, edge))
        vert_to_edges[v2].append((v1, edge))

    # Build chains by following connected edges
    used_edges = set()
    chains = []

    for edge in edges:
        if edge.key in used_edges:
            continue

        # Start a new chain
        chain = []
        current_vert = edge.vertices[0]
        next_vert = edge.vertices[1]
        used_edges.add(edge.key)

        # Add first vertex
        chain.append(world_matrix @ vertices[current_vert].co)

        # Follow the chain
        while next_vert is not None:
            chain.append(world_matrix @ vertices[next_vert].co)
            current_vert = next_vert
            next_vert = None

            # Find next connected edge
            if current_vert in vert_to_edges:
                for neighbor, neighbor_edge in vert_to_edges[current_vert]:
                    if neighbor_edge.key not in used_edges:
                        used_edges.add(neighbor_edge.key)
                        next_vert = neighbor
                        break

        if len(chain) >= 2:
            chains.append(chain)

    return chains


# ============================================================================
# Operator
# ============================================================================

class POSE_OT_posebridge_generate_outline(bpy.types.Operator):
    """Generate Curve outline for PoseBridge"""
    bl_idname = "pose.posebridge_generate_outline"
    bl_label = "Generate PoseBridge Outline"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj:
            return False

        # Allow either armature or mesh with armature modifier
        if obj.type == 'ARMATURE':
            return True
        elif obj.type == 'MESH':
            # Check for armature modifier
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object:
                    return True

        return False

    def execute(self, context):
        obj = context.active_object
        mesh_obj = None

        # Get mesh from selected object
        if obj.type == 'MESH':
            mesh_obj = obj
        elif obj.type == 'ARMATURE':
            # Find mesh that uses this armature
            for scene_obj in context.scene.objects:
                if scene_obj.type == 'MESH':
                    for mod in scene_obj.modifiers:
                        if mod.type == 'ARMATURE' and mod.object == obj:
                            mesh_obj = scene_obj
                            break
                if mesh_obj:
                    break

        if not mesh_obj:
            self.report({'ERROR'}, "No mesh found for selected object")
            return {'CANCELLED'}

        # Generate outline
        curve_obj = create_genesis8_body_outline(mesh_obj)

        if curve_obj:
            self.report({'INFO'}, f"Generated outline: {curve_obj.name}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Failed to generate outline")
            return {'CANCELLED'}


# ============================================================================
# Registration
# ============================================================================

classes = (
    POSE_OT_posebridge_generate_outline,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


# ============================================================================
# Standalone Script Usage
# ============================================================================

if __name__ == "__main__":
    # Register operator
    register()

    # Auto-run on script execution
    mesh_obj = bpy.context.active_object

    # Handle both mesh and armature selection
    if mesh_obj:
        if mesh_obj.type == 'MESH':
            log.info(f"Generating outline for mesh: {mesh_obj.name}")
            create_genesis8_body_outline(mesh_obj)
        elif mesh_obj.type == 'ARMATURE':
            # Find mesh that uses this armature
            log.info(f"Finding mesh for armature: {mesh_obj.name}")
            for scene_obj in bpy.context.scene.objects:
                if scene_obj.type == 'MESH':
                    for mod in scene_obj.modifiers:
                        if mod.type == 'ARMATURE' and mod.object == mesh_obj:
                            log.info(f"Found mesh: {scene_obj.name}")
                            create_genesis8_body_outline(scene_obj)
                            break
        else:
            log.info(f"Selected object is {mesh_obj.type}, need MESH or ARMATURE")
    else:
        log.info("No object selected - please select Genesis 8 mesh or armature")
