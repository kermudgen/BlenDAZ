# Extract hand geometry from standin mesh for PoseBridge hand panel
# Run in Blender after outline/standin has been generated
#
# Creates two hand meshes positioned side-by-side for the hand view camera

import bpy
import bmesh
from mathutils import Vector, Matrix, Euler
import math

from outline_generator_lineart import get_or_create_pb_collection


# Finger bones for control points (excluding carpals, Hand bone)
FINGER_BONES = [
    'Thumb1', 'Thumb2', 'Thumb3',
    'Index1', 'Index2', 'Index3',
    'Mid1', 'Mid2', 'Mid3',
    'Ring1', 'Ring2', 'Ring3',
    'Pinky1', 'Pinky2', 'Pinky3',
]

def extract_hand_geometry(source_mesh_name, hand_side='left', hands_coll=None, char_tag=None):
    """
    Extract hand geometry from a mesh using vertex groups.

    Args:
        source_mesh_name: Name of the source mesh (e.g., "Fey Mesh_Standin")
        hand_side: 'left' or 'right'

    Returns:
        Tuple of (hand_obj, geometry_center) or (None, None) on failure
        geometry_center is the bounds center before transforms (needed for bone mapping)
    """

    # Get source mesh
    if source_mesh_name not in bpy.data.objects:
        print(f"ERROR: Source mesh '{source_mesh_name}' not found")
        return None, None

    source_obj = bpy.data.objects[source_mesh_name]
    if source_obj.type != 'MESH':
        print(f"ERROR: '{source_mesh_name}' is not a mesh")
        return None, None

    # Define hand bone names based on side
    prefix = 'l' if hand_side == 'left' else 'r'
    hand_bones = [
        f'{prefix}Hand',
        f'{prefix}Thumb1', f'{prefix}Thumb2', f'{prefix}Thumb3',
        f'{prefix}Index1', f'{prefix}Index2', f'{prefix}Index3',
        f'{prefix}Mid1', f'{prefix}Mid2', f'{prefix}Mid3',
        f'{prefix}Ring1', f'{prefix}Ring2', f'{prefix}Ring3',
        f'{prefix}Pinky1', f'{prefix}Pinky2', f'{prefix}Pinky3',
        f'{prefix}Carpal1', f'{prefix}Carpal2', f'{prefix}Carpal3', f'{prefix}Carpal4',
    ]

    # Find vertex group indices
    group_indices = []
    for bone_name in hand_bones:
        if bone_name in source_obj.vertex_groups:
            group_indices.append(source_obj.vertex_groups[bone_name].index)

    if not group_indices:
        print(f"ERROR: No hand vertex groups found for {hand_side} hand")
        return None, None

    print(f"Found {len(group_indices)} vertex groups for {hand_side} hand")

    # Find vertices weighted to any hand bone
    mesh_data = source_obj.data
    hand_vert_indices = set()

    for v in mesh_data.vertices:
        for g in v.groups:
            if g.group in group_indices and g.weight > 0.01:
                hand_vert_indices.add(v.index)
                break

    print(f"Found {len(hand_vert_indices)} vertices for {hand_side} hand")

    if len(hand_vert_indices) == 0:
        print(f"ERROR: No vertices found for {hand_side} hand")
        return None, None

    # Create bmesh and extract hand geometry
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Mark vertices to keep
    verts_to_keep = set(hand_vert_indices)

    # Find faces that have ALL vertices in hand
    faces_to_keep = []
    for face in bm.faces:
        if all(v.index in verts_to_keep for v in face.verts):
            faces_to_keep.append(face)

    print(f"Found {len(faces_to_keep)} faces for {hand_side} hand")

    # Create new bmesh with only hand geometry
    new_bm = bmesh.new()

    # Map old vertex indices to new vertices
    vert_map = {}
    for face in faces_to_keep:
        new_verts = []
        for v in face.verts:
            if v.index not in vert_map:
                new_v = new_bm.verts.new(v.co.copy())
                vert_map[v.index] = new_v
            new_verts.append(vert_map[v.index])

        # Create face
        try:
            new_bm.faces.new(new_verts)
        except ValueError:
            # Face already exists
            pass

    new_bm.verts.ensure_lookup_table()
    new_bm.faces.ensure_lookup_table()

    print(f"Created hand mesh with {len(new_bm.verts)} verts, {len(new_bm.faces)} faces")

    # Create new mesh object (per-character naming for multi-character support)
    if char_tag:
        hand_mesh_name = f"PB_Hand_{hand_side.capitalize()}_{char_tag}"
    else:
        hand_mesh_name = f"PB_Hand_{hand_side.capitalize()}"

    # Remove existing if present
    if hand_mesh_name in bpy.data.objects:
        old_obj = bpy.data.objects[hand_mesh_name]
        bpy.data.objects.remove(old_obj, do_unlink=True)

    # Create mesh data
    new_mesh = bpy.data.meshes.new(hand_mesh_name)
    new_bm.to_mesh(new_mesh)
    new_bm.free()
    bm.free()

    # Create object
    hand_obj = bpy.data.objects.new(hand_mesh_name, new_mesh)
    target = hands_coll if hands_coll else bpy.context.scene.collection
    target.objects.link(hand_obj)

    # Calculate bounds center BEFORE origin_set (needed for bone position mapping)
    # At this point, object is at world origin with no transforms
    min_co = Vector((float('inf'), float('inf'), float('inf')))
    max_co = Vector((float('-inf'), float('-inf'), float('-inf')))
    for v in new_mesh.vertices:
        for i in range(3):
            min_co[i] = min(min_co[i], v.co[i])
            max_co[i] = max(max_co[i], v.co[i])
    geometry_center = (min_co + max_co) / 2
    print(f"  Geometry center: {geometry_center}")

    # Set origin to geometry center (shift vertices, set object location)
    # Done manually to avoid bpy.ops context requirement
    for v in new_mesh.vertices:
        v.co -= geometry_center
    new_mesh.update()
    hand_obj.location = geometry_center.copy()

    # Shade smooth for nicer appearance (no ops needed)
    for poly in new_mesh.polygons:
        poly.use_smooth = True
    new_mesh.update()

    print(f"  Origin set to geometry center, shading smooth")

    return hand_obj, geometry_center


def position_hands_for_view(left_hand_obj, right_hand_obj, z_offset=-53.0):
    """
    Position both hand meshes side-by-side for the hand panel camera.

    Layout: Dorsal view (back of hand up), thumbs pointing inward

    Transforms calibrated manually for Genesis 8 female (Fey) - 2026-02-17

    Args:
        left_hand_obj: Left hand mesh object
        right_hand_obj: Right hand mesh object
        z_offset: Z position for hand view (below body standin)
    """

    if not left_hand_obj or not right_hand_obj:
        print("ERROR: Missing hand objects")
        return False

    # Calibrated transforms (manually positioned for dorsal view, thumbs inward)
    # Recalibrated 2026-02-17 after origin-to-geometry fix

    # Left hand: on left side of view, thumb pointing right
    left_hand_obj.location = Vector((-0.040003, -0.68324, z_offset + 0.022))
    left_hand_obj.rotation_euler = (math.radians(-180.16), math.radians(-34.575), math.radians(-88.528))

    # Right hand: on right side of view, thumb pointing left
    right_hand_obj.location = Vector((0.026067, -0.67678, z_offset - 0.049))
    right_hand_obj.rotation_euler = (math.radians(187.13), math.radians(32.286), math.radians(95.809))

    print(f"Positioned hands at Z≈{z_offset}")
    print(f"  Left hand: {left_hand_obj.location}")
    print(f"  Right hand: {right_hand_obj.location}")

    return True


def create_hand_camera(z_offset=-53.0, camera_distance=2.0, ortho_scale=0.5, hands_coll=None, char_tag=None):
    """
    Create orthographic camera for hand panel view.

    Args:
        z_offset: Z position of hands
        camera_distance: Distance from hands to camera
        ortho_scale: Orthographic scale (smaller = more zoomed in)
        hands_coll: Collection to link camera into (falls back to scene root)
        char_tag: Optional tag for multi-character naming

    Returns:
        The camera object
    """

    camera_name = f"PB_Camera_Hands_{char_tag}" if char_tag else "PB_Camera_Hands"

    # Remove existing
    if camera_name in bpy.data.objects:
        old_cam = bpy.data.objects[camera_name]
        bpy.data.objects.remove(old_cam, do_unlink=True)

    # Create camera
    camera_data = bpy.data.cameras.new(camera_name)
    camera_data.type = 'ORTHO'
    camera_data.ortho_scale = ortho_scale

    camera = bpy.data.objects.new(camera_name, camera_data)
    target = hands_coll if hands_coll else bpy.context.scene.collection
    target.objects.link(camera)

    # Hands are positioned at Y ≈ -0.67, so camera needs to be further back
    hands_y = -0.67
    camera.location = Vector((0, hands_y - camera_distance, z_offset))
    camera.rotation_euler = (math.radians(90), 0, 0)  # Looking down +Y axis

    print(f"Created hand camera at {camera.location}")
    print(f"  Ortho scale: {ortho_scale}")

    return camera


def get_transformed_bone_positions(armature_name, hand_obj, geometry_center, hand_side='left'):
    """
    Get finger bone positions transformed to match the hand mesh's new location/rotation.

    Position types per bone:
    - Thumb1, Thumb2: tail (joint appears at end of segment)
    - Thumb3: mid (fingertip joint)
    - Other finger bones: mid (joints appear mid-segment in dorsal view)
    - Finger1 bones also return head position for group node placement

    Args:
        armature_name: Name of the armature object
        hand_obj: The positioned hand mesh object
        geometry_center: The original geometry center (from extract_hand_geometry)
        hand_side: 'left' or 'right'

    Returns:
        Dict mapping bone names to their transformed world positions (for individual controls)
        Also includes '{finger}_group' entries for finger group diamond positions
    """
    if armature_name not in bpy.data.objects:
        print(f"ERROR: Armature '{armature_name}' not found")
        return {}

    armature = bpy.data.objects[armature_name]
    if armature.type != 'ARMATURE':
        print(f"ERROR: '{armature_name}' is not an armature")
        return {}

    prefix = 'l' if hand_side == 'left' else 'r'
    bone_positions = {}

    # Get the hand object's rotation matrix
    rotation_matrix = hand_obj.rotation_euler.to_matrix().to_4x4()

    def transform_point(local_pos):
        """Transform a local-space position to match hand mesh transforms.

        Both bone positions and geometry_center must be in the same space
        (armature/mesh local) so the subtraction is valid regardless of
        where the armature sits in the scene.
        """
        offset = local_pos - geometry_center
        rotated = rotation_matrix @ offset
        return rotated + hand_obj.location

    for bone_name in FINGER_BONES:
        full_bone_name = f"{prefix}{bone_name}"

        if full_bone_name not in armature.pose.bones:
            print(f"  Warning: Bone '{full_bone_name}' not found")
            continue

        pose_bone = armature.pose.bones[full_bone_name]
        # Use armature-local positions (same space as geometry_center from mesh data)
        bone_head = Vector(pose_bone.head)
        bone_tail = Vector(pose_bone.tail)
        bone_mid = (bone_head + bone_tail) / 2

        # Determine which position to use for this bone's individual control
        if bone_name in ['Thumb1', 'Thumb2']:
            # Thumb first two joints: use tail
            individual_pos = bone_tail
        else:
            # All others (including Thumb3): use mid
            individual_pos = bone_mid

        # Transform and store individual control position
        bone_positions[full_bone_name] = transform_point(individual_pos)

        # For finger1 bones, also store position for group diamond
        if bone_name.endswith('1'):
            finger_name = bone_name[:-1]  # e.g., 'Thumb', 'Index'
            group_key = f"{prefix}{finger_name}_group"
            # Thumb group: use mid-point (head is deep in palm)
            # Other fingers: use head (visible knuckle position)
            if finger_name == 'Thumb':
                bone_positions[group_key] = transform_point(bone_mid)
            else:
                bone_positions[group_key] = transform_point(bone_head)

    # Add Hand bone controls (individual wrist + fist group)
    hand_bone_name = f"{prefix}Hand"
    if hand_bone_name in armature.pose.bones:
        hand_bone = armature.pose.bones[hand_bone_name]
        bone_head = Vector(hand_bone.head)
        bone_tail = Vector(hand_bone.tail)
        bone_mid = (bone_head + bone_tail) / 2
        # Individual wrist control at head of Hand bone
        bone_positions[f"{prefix}Hand"] = transform_point(bone_head)
        # Fist group control at mid-point of Hand bone
        bone_positions[f"{prefix}Hand_fist"] = transform_point(bone_mid)

    print(f"  Transformed {len(bone_positions)} positions for {hand_side} hand")
    return bone_positions


def extract_and_setup_hands(standin_mesh_name, z_offset=-53.0, armature_name=None, char_name=None, char_tag=None):
    """
    Main function: Extract hands from standin and set up for hand panel.

    Args:
        standin_mesh_name: Name of the standin mesh (e.g., "Fey Mesh_Standin")
        z_offset: Z position for hand view
        armature_name: Optional armature name to calculate bone positions for control points
        char_name: Short character name (e.g. 'Fey') for PB_{char}_Hands collection
        char_tag: Optional tag for multi-character naming (camera becomes PB_Camera_Hands_{char_tag})

    Returns:
        Dict with:
            left_hand, right_hand: Hand mesh objects
            camera: Hand view camera
            left_center, right_center: Original geometry centers (for bone mapping)
            left_bone_positions, right_bone_positions: Transformed bone head positions (if armature provided)
    """

    print("\n" + "="*60)
    print("EXTRACTING HANDS FOR POSEBRIDGE HAND PANEL")
    print("="*60)

    # Resolve target collection
    hands_coll = None
    if char_name:
        hands_coll = get_or_create_pb_collection(char_name, 'Hands')
        print(f"  Collection: {hands_coll.name}")

    # Extract left hand
    print("\n--- Extracting LEFT hand ---")
    left_hand, left_center = extract_hand_geometry(standin_mesh_name, 'left', hands_coll=hands_coll, char_tag=char_tag)

    # Extract right hand
    print("\n--- Extracting RIGHT hand ---")
    right_hand, right_center = extract_hand_geometry(standin_mesh_name, 'right', hands_coll=hands_coll, char_tag=char_tag)

    if not left_hand or not right_hand:
        print("\nERROR: Failed to extract one or both hands")
        return None

    # Position hands for camera view
    print("\n--- Positioning hands ---")
    position_hands_for_view(left_hand, right_hand, z_offset=z_offset)

    # Create camera
    print("\n--- Creating hand camera ---")
    camera = create_hand_camera(z_offset=z_offset, hands_coll=hands_coll, char_tag=char_tag)

    # Get bone positions if armature provided
    left_bone_positions = {}
    right_bone_positions = {}
    if armature_name:
        print("\n--- Calculating bone positions ---")
        left_bone_positions = get_transformed_bone_positions(
            armature_name, left_hand, left_center, 'left')
        right_bone_positions = get_transformed_bone_positions(
            armature_name, right_hand, right_center, 'right')

    print("\n" + "="*60)
    print("HAND EXTRACTION COMPLETE")
    print("="*60)
    print(f"\nCreated objects:")
    print(f"  - {left_hand.name}")
    print(f"  - {right_hand.name}")
    print(f"  - {camera.name}")
    if armature_name:
        print(f"\nBone positions calculated: {len(left_bone_positions)} left, {len(right_bone_positions)} right")

    return {
        'left_hand': left_hand,
        'right_hand': right_hand,
        'camera': camera,
        'left_center': left_center,
        'right_center': right_center,
        'left_bone_positions': left_bone_positions,
        'right_bone_positions': right_bone_positions,
    }


def generate_hand_control_points(bone_positions, hand_side='left'):
    """
    Generate control point definitions from calculated bone positions.

    Args:
        bone_positions: Dict from get_transformed_bone_positions()
        hand_side: 'left' or 'right'

    Returns:
        List of control point dictionaries ready for PoseBridge integration
    """
    prefix = 'l' if hand_side == 'left' else 'r'
    side_label = 'Left' if hand_side == 'left' else 'Right'
    control_points = []

    # Wrist / Hand bone control (circle) — at head of Hand bone
    hand_key = f"{prefix}Hand"
    if hand_key in bone_positions:
        pos = bone_positions[hand_key]
        control_points.append({
            'id': hand_key,
            'bone_name': hand_key,
            'label': f'{side_label} Hand',
            'group': f'hand_{hand_side}',
            'panel_view': 'hands',
            'control_type': 'single',
            'position_3d_fixed': (pos.x, pos.y, pos.z),
            'controls': {
                'lmb_horiz': ('Z', False),   # Radial/ulnar deviation
                'lmb_vert':  ('X', False),   # Wrist flex/extend
                'rmb_horiz': ('Z', False),   # Radial/ulnar deviation
                'rmb_vert':  ('Y', False),   # Wrist twist
            }
        })

    # Individual finger joint controls (circles)
    finger_names = ['Thumb', 'Index', 'Mid', 'Ring', 'Pinky']
    for finger in finger_names:
        for joint in [1, 2, 3]:
            bone_name = f"{prefix}{finger}{joint}"
            if bone_name in bone_positions:
                pos = bone_positions[bone_name]
                control_points.append({
                    'id': bone_name,
                    'bone_name': bone_name,
                    'label': f'{side_label} {finger} {joint}',
                    'group': f'hand_{hand_side}',
                    'panel_view': 'hands',
                    'control_type': 'single',
                    'position_3d_fixed': (pos.x, pos.y, pos.z),
                    'controls': {
                        'lmb_horiz': 'Z',  # Spread fingers
                        'lmb_vert': 'X',   # Curl finger
                        'rmb_horiz': None,
                        'rmb_vert': None
                    }
                })

    # Finger group controls (diamonds)
    for finger in finger_names:
        group_key = f"{prefix}{finger}_group"
        if group_key in bone_positions:
            pos = bone_positions[group_key]
            bone_list = [f"{prefix}{finger}{j}" for j in [1, 2, 3]]
            control_points.append({
                'id': group_key,
                'bone_names': bone_list,
                'label': f'{side_label} {finger} Group',
                'group': f'hand_{hand_side}',
                'panel_view': 'hands',
                'control_type': 'multi',
                'shape': 'diamond',
                'reference_bone': f"{prefix}{finger}1",
                'position_3d_fixed': (pos.x, pos.y, pos.z),
                'controls': {
                    'lmb_horiz': 'Z',  # Spread
                    'lmb_vert': 'X',   # Curl all joints
                    'rmb_horiz': None,
                    'rmb_vert': None
                }
            })

    # Fist control (diamond) - curls all fingers
    fist_key = f"{prefix}Hand_fist"
    if fist_key in bone_positions:
        pos = bone_positions[fist_key]
        all_finger_bones = []
        for finger in finger_names:
            all_finger_bones.extend([f"{prefix}{finger}{j}" for j in [1, 2, 3]])
        control_points.append({
            'id': fist_key,
            'bone_names': all_finger_bones,
            'label': f'{side_label} Fist',
            'group': f'hand_{hand_side}',
            'panel_view': 'hands',
            'control_type': 'multi',
            'shape': 'diamond',
            'reference_bone': f"{prefix}Hand",
            'position_3d_fixed': (pos.x, pos.y, pos.z),
            'controls': {
                'lmb_horiz': None,
                'lmb_vert': 'X',   # Curl all into fist
                'rmb_horiz': None,
                'rmb_vert': None
            }
        })

    # Joint-level group controls (squares) — curl all fingers at one joint level
    # Positioned on the pinky side, offset beyond the pinky bone at each joint level
    no_thumb_fingers = ['Index', 'Mid', 'Ring', 'Pinky']
    for joint in [1, 2, 3]:
        pinky_key = f"{prefix}Pinky{joint}"
        index_key = f"{prefix}Index{joint}"
        if pinky_key in bone_positions and index_key in bone_positions:
            pinky_pos = bone_positions[pinky_key]
            index_pos = bone_positions[index_key]
            # Offset direction: from index toward pinky (and beyond)
            spread_dir = pinky_pos - index_pos
            if spread_dir.length > 0.0001:
                spread_dir.normalize()
            # Position: pinky position + offset further outward
            offset_pos = pinky_pos + spread_dir * 0.015
            joint_bones = [f"{prefix}{finger}{joint}" for finger in no_thumb_fingers]
            joint_key = f"{prefix}Joint{joint}_group"
            control_points.append({
                'id': joint_key,
                'bone_names': joint_bones,
                'label': f'{side_label} Joint {joint}',
                'group': f'hand_{hand_side}',
                'panel_view': 'hands',
                'control_type': 'multi',
                'shape': 'square',
                'reference_bone': f"{prefix}Pinky{joint}",
                'position_3d_fixed': (offset_pos.x, offset_pos.y, offset_pos.z),
                'controls': {
                    'lmb_horiz': None,
                    'lmb_vert': 'X',   # Curl all fingers at this joint
                    'rmb_horiz': None,
                    'rmb_vert': None
                }
            })

    return control_points


def store_hand_control_points(result):
    """
    Store hand control points in PoseBridge settings.

    Args:
        result: Dict from extract_and_setup_hands()

    Returns:
        Number of control points stored
    """
    import bpy

    settings = bpy.context.scene.posebridge_settings

    # Generate control points for both hands
    left_cps = generate_hand_control_points(result['left_bone_positions'], 'left')
    right_cps = generate_hand_control_points(result['right_bone_positions'], 'right')

    all_hand_cps = left_cps + right_cps

    # Remove existing hand control points
    to_remove = []
    for i, cp in enumerate(settings.control_points_fixed):
        if cp.panel_view == 'hands':
            to_remove.append(i)
    for i in reversed(to_remove):
        settings.control_points_fixed.remove(i)

    # Add new hand control points
    for cp_def in all_hand_cps:
        cp = settings.control_points_fixed.add()
        cp.id = cp_def['id']
        cp.bone_name = cp_def.get('bone_name', cp_def.get('bone_names', [''])[0])
        cp.label = cp_def['label']
        cp.group = cp_def['group']
        cp.panel_view = cp_def['panel_view']
        cp.control_type = cp_def['control_type']
        cp.shape = cp_def.get('shape', '')
        cp.position_3d_fixed = cp_def['position_3d_fixed']

    print(f"Stored {len(all_hand_cps)} hand control points")
    return len(all_hand_cps)


# Example usage:
if __name__ == "__main__":
    # Replace with your actual mesh and armature names
    standin_name = "Fey Mesh"  # Source mesh with vertex groups
    armature_name = "Fey"      # Armature for bone positions

    # Try alternate names
    if standin_name not in bpy.data.objects:
        standin_name = "Fey Mesh_Standin"
    if standin_name not in bpy.data.objects:
        standin_name = "Fey Mesh_LineArt_Copy"

    if standin_name in bpy.data.objects:
        result = extract_and_setup_hands(
            standin_name,
            z_offset=-53.0,
            armature_name=armature_name if armature_name in bpy.data.objects else None
        )

        # Print bone positions for debugging
        if result and result.get('left_bone_positions'):
            print("\n--- Left hand bone positions ---")
            for bone, pos in result['left_bone_positions'].items():
                print(f"  {bone}: ({pos.x:.4f}, {pos.y:.4f}, {pos.z:.4f})")
    else:
        print("ERROR: Could not find standin mesh. Available meshes:")
        for obj in bpy.data.objects:
            if obj.type == 'MESH':
                print(f"  - {obj.name}")
