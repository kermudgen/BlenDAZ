# Extract icon shape from selected mesh
#
# Usage:
# 1. Create a flat mesh on XY plane (Z=0)
# 2. Draw your icon shape as edges (outline)
# 3. Select the mesh
# 4. Run this script
# 5. Copy the output from System Console
#
# Tips:
# - Work in Top view (Numpad 7)
# - Keep shape within a square area (will be normalized to 0-1)
# - Start from bottom-left, trace clockwise or counter-clockwise
# - For LINE_STRIP, vertices should form a connected path

import bpy
import bmesh

def extract_shape_from_mesh(obj):
    """Extract 2D vertex positions from a mesh, normalized to 0-1 range."""

    if obj.type != 'MESH':
        print(f"ERROR: {obj.name} is not a mesh")
        return None

    mesh = obj.data

    # Get world-space vertex positions (XY only)
    vertices = []
    for v in mesh.vertices:
        world_pos = obj.matrix_world @ v.co
        vertices.append((world_pos.x, world_pos.y))

    if not vertices:
        print("ERROR: No vertices found")
        return None

    # Find bounding box
    min_x = min(v[0] for v in vertices)
    max_x = max(v[0] for v in vertices)
    min_y = min(v[1] for v in vertices)
    max_y = max(v[1] for v in vertices)

    width = max_x - min_x
    height = max_y - min_y

    # Use the larger dimension to maintain aspect ratio
    size = max(width, height)
    if size == 0:
        print("ERROR: Shape has zero size")
        return None

    # Center offset (to center the shape in 0-1 space)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    # Normalize vertices to 0-1 range, centered
    normalized = []
    for x, y in vertices:
        nx = 0.5 + (x - center_x) / size
        ny = 0.5 + (y - center_y) / size
        normalized.append((round(nx, 2), round(ny, 2)))

    return normalized


def extract_ordered_outline(obj):
    """
    Extract vertices in edge-connected order (for LINE_STRIP).
    Attempts to find a continuous path through all edges.
    """
    if obj.type != 'MESH':
        print(f"ERROR: {obj.name} is not a mesh")
        return None

    # Create bmesh for edge traversal
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    if len(bm.edges) == 0:
        print("ERROR: No edges found")
        bm.free()
        return None

    # Build adjacency map
    adjacency = {v.index: [] for v in bm.verts}
    for e in bm.edges:
        v1, v2 = e.verts[0].index, e.verts[1].index
        adjacency[v1].append(v2)
        adjacency[v2].append(v1)

    # Find a starting vertex (prefer one with only 1 connection, or any if closed loop)
    start_vert = None
    for v_idx, neighbors in adjacency.items():
        if len(neighbors) == 1:
            start_vert = v_idx
            break
    if start_vert is None:
        start_vert = 0  # Closed loop, start anywhere

    # Walk the edges
    ordered_indices = [start_vert]
    visited = {start_vert}
    current = start_vert

    while True:
        neighbors = adjacency[current]
        next_vert = None
        for n in neighbors:
            if n not in visited:
                next_vert = n
                break

        if next_vert is None:
            # Check if we can close the loop
            for n in neighbors:
                if n == start_vert and len(ordered_indices) > 2:
                    ordered_indices.append(start_vert)  # Close the loop
                    break
            break

        ordered_indices.append(next_vert)
        visited.add(next_vert)
        current = next_vert

    # Get world positions and normalize
    vertices = []
    for v_idx in ordered_indices:
        v = bm.verts[v_idx]
        world_pos = obj.matrix_world @ v.co
        vertices.append((world_pos.x, world_pos.y))

    bm.free()

    # Normalize
    if not vertices:
        return None

    min_x = min(v[0] for v in vertices)
    max_x = max(v[0] for v in vertices)
    min_y = min(v[1] for v in vertices)
    max_y = max(v[1] for v in vertices)

    size = max(max_x - min_x, max_y - min_y)
    if size == 0:
        return None

    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    normalized = []
    for x, y in vertices:
        nx = 0.5 + (x - center_x) / size
        ny = 0.5 + (y - center_y) / size
        normalized.append((round(nx, 2), round(ny, 2)))

    return normalized


def format_for_icons_py(name, vertices):
    """Format vertices as Python code for icons.py"""
    lines = [f"ICON_{name.upper()} = {{"]
    lines.append(f"    'name': '{name.lower()}',")
    lines.append("    'outline': [")

    for i, (x, y) in enumerate(vertices):
        comment = ""
        if i == 0:
            comment = "  # Start"
        elif i == len(vertices) - 1 and vertices[i] == vertices[0]:
            comment = "  # Close loop"
        lines.append(f"        ({x}, {y}),{comment}")

    lines.append("    ],")
    lines.append("}")

    return "\n".join(lines)


# Main execution
if __name__ == "__main__":
    obj = bpy.context.active_object

    if obj is None:
        print("ERROR: No object selected")
    else:
        print("\n" + "="*60)
        print(f"EXTRACTING SHAPE FROM: {obj.name}")
        print("="*60)

        # Try ordered extraction first (for proper LINE_STRIP)
        vertices = extract_ordered_outline(obj)

        if vertices:
            print(f"\nExtracted {len(vertices)} vertices in edge order")
            print("\n--- COPY THIS TO icons.py ---\n")
            print(format_for_icons_py(obj.name, vertices))
            print("\n--- END ---\n")
        else:
            # Fallback to simple extraction
            print("Could not find connected path, using vertex order...")
            vertices = extract_shape_from_mesh(obj)
            if vertices:
                print(f"\nExtracted {len(vertices)} vertices")
                print("\n--- COPY THIS TO icons.py ---\n")
                print(format_for_icons_py(obj.name, vertices))
                print("\n--- END ---\n")
            else:
                print("ERROR: Could not extract vertices")
