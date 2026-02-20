"""PoseBridge Outline Generator - Creates GP outlines for Genesis 8 characters"""

import bpy
from mathutils import Vector

# ============================================================================
# Outline Generation
# ============================================================================

def create_genesis8_body_outline(mesh_obj, outline_name="PB_Outline_Body"):
    """Generate a Grease Pencil outline from mesh silhouette (rest pose)

    Args:
        mesh_obj: Genesis 8 mesh object
        outline_name: Name for the GP object

    Returns:
        GPencil object or None if failed
    """
    if not mesh_obj or mesh_obj.type != 'MESH':
        print("Error: Invalid mesh object")
        return None

    # Ensure we're in object mode
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Create Grease Pencil object
    gp_data = bpy.data.grease_pencils.new(outline_name)
    gp_obj = bpy.data.objects.new(outline_name, gp_data)

    # Link to scene
    bpy.context.scene.collection.objects.link(gp_obj)

    # Create layer
    gp_layer = gp_data.layers.new("Outline")

    # Create frame - API differs between versions
    if bpy.app.version >= (4, 3, 0):
        # Blender 4.3+ / 5.0+ - new frame API
        gp_frame = gp_layer.frames.new(frame_number=0)
    else:
        # Blender 3.x-4.2 - legacy frame API
        gp_frame = gp_layer.frames.new(0)

    # Get mesh data
    mesh = mesh_obj.data
    world_matrix = mesh_obj.matrix_world

    # Find silhouette edges (boundary edges with only one adjacent face)
    silhouette_edges = []
    edge_face_count = {}

    # Count faces per edge
    for poly in mesh.polygons:
        for edge_key in poly.edge_keys:
            # Sort vertices to make edge key consistent
            edge_key = tuple(sorted(edge_key))
            edge_face_count[edge_key] = edge_face_count.get(edge_key, 0) + 1

    # Find boundary edges (edges with only 1 face)
    for edge in mesh.edges:
        edge_key = tuple(sorted(edge.vertices))
        if edge_face_count.get(edge_key, 0) == 1:
            silhouette_edges.append(edge)

    # If no boundary edges found, use all edges (closed mesh - we'll project and find outer contour)
    if not silhouette_edges:
        print("No boundary edges found - using edge detection from front view")
        silhouette_edges = detect_silhouette_from_view(mesh, world_matrix)

    # Create GP strokes from silhouette edges
    # Group connected edges into continuous strokes
    stroke_chains = build_stroke_chains(silhouette_edges, mesh.vertices, world_matrix)

    # Blender 5.0+ uses different API for adding strokes
    if bpy.app.version >= (4, 3, 0):
        # New GP v3 system - create drawing and add curves
        drawing = gp_data.new_drawing()
        gp_frame.drawing = drawing

        for chain in stroke_chains:
            if len(chain) < 2:
                continue

            # Resize curves array to add new curve
            num_curves = len(drawing.curves)
            drawing.curves.resize(num_curves + 1)
            curve = drawing.curves[num_curves]

            # Set curve properties
            curve.cyclic = (chain[0] == chain[-1])

            # Resize points and set positions
            curve.points.resize(len(chain))
            for i, vertex_pos in enumerate(chain):
                curve.points[i].position = vertex_pos
                curve.points[i].radius = 0.01  # Line thickness
    else:
        # Legacy GP system (Blender 3.x - 4.2)
        for chain in stroke_chains:
            if len(chain) < 2:
                continue

            stroke = gp_frame.strokes.new()
            stroke.display_mode = '3DSPACE'
            stroke.line_width = 200
            stroke.use_cyclic = chain[0] == chain[-1]

            stroke.points.add(len(chain))
            for i, vertex_pos in enumerate(chain):
                stroke.points[i].co = vertex_pos

    # Set GP object properties
    gp_obj.location = (0, 0, 0)

    # Set color (cyan)
    if bpy.app.version >= (4, 3, 0):
        # Blender 5.0+ - use simple material
        if not gp_data.materials:
            mat = bpy.data.materials.new("GP_Outline_Material")
            mat.use_nodes = True
            # Set viewport color
            mat.diffuse_color = (0, 0.8, 1, 1)  # Cyan
            gp_data.materials.append(mat)
    else:
        # Legacy GP system
        gp_layer.line_change = 4  # Line thickness
        if not gp_data.materials:
            mat = bpy.data.materials.new("GP_Outline_Material")
            bpy.data.materials.create_gpencil_data(mat)
            gp_data.materials.append(mat)
            mat.grease_pencil.color = (0, 0.8, 1, 1)  # Cyan

    print(f"Created outline: {outline_name} with {len(stroke_chains)} strokes")
    return gp_obj


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
    """Generate Grease Pencil outline for PoseBridge"""
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
        gp_obj = create_genesis8_body_outline(mesh_obj)

        if gp_obj:
            self.report({'INFO'}, f"Generated outline: {gp_obj.name}")
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
# Standalone Script Usage (run in Blender Text Editor)
# ============================================================================

if __name__ == "__main__":
    # Register operator
    register()

    # Or run directly:
    # armature = bpy.context.active_object
    # if armature and armature.type == 'ARMATURE':
    #     create_genesis8_body_outline(armature)
