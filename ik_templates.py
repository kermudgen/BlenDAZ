"""
IK Rig Templates for DAZ Genesis 8/9 Characters

Pre-defined optimal IK setups for each bone type, providing consistent
and predictable behavior across all Genesis 8 DAZ rigs.

Extracted from daz_bone_select.py for maintainability.
"""

from mathutils import Vector


# ============================================================================
# IK RIG TEMPLATES - Pre-defined optimal IK setups for each bone type
# ============================================================================
# Instead of calculating everything dynamically, we use tested templates
# for consistent, predictable behavior across all Genesis 8 DAZ rigs

IK_RIG_TEMPLATES = {
    'hand': {
        'description': 'Full arm IK chain for hand dragging',
        'chain_length': 4,  # collar → shoulder → forearm → hand
        'stiffness': {
            'collar': 0.75,     # Stable but allows some movement
            'shldr': 0.1,       # Very flexible for natural arm movement
            'shoulder': 0.1,    # Alias for shldr
            'forearm': 0.0,     # Bends freely (main bend point)
            'lorearm': 0.0,     # Alias for forearm
            'hand': 0.0         # End effector, no resistance
        },
        'pole_target': {
            'enabled': True,
            'reference_bone': 'forearm',  # Place pole relative to elbow
            'method': 'perpendicular_to_line',  # Project elbow perpendicular to shoulder-hand
            'distance_multiplier': 2.0   # Extend 2x the elbow offset for stability
        },
        'constraints': {
            'collar': 'damped_track'  # Track shoulder naturally
        },
        'prebend': None  # Arms don't need prebend
    },

    'forearm': {
        'description': 'Forearm IK chain (shorter than hand)',
        'chain_length': 3,  # collar → shoulder → forearm
        'stiffness': {
            'collar': 0.75,
            'shldr': 0.1,
            'shoulder': 0.1,
            'forearm': 0.0,
            'lorearm': 0.0
        },
        'pole_target': {
            'enabled': True,
            'reference_bone': 'forearm',
            'method': 'perpendicular_to_line',
            'distance_multiplier': 2.0
        },
        'constraints': {
            'collar': 'damped_track'
        },
        'prebend': None
    },

    'foot': {
        'description': 'Full leg IK chain for foot dragging',
        'chain_length': 3,  # thigh → shin → foot
        'stiffness': {
            'thigh': 0.2,       # Some resistance for stability
            'shin': 0.0,        # Bends freely (main bend point)
            'calf': 0.0,        # Alias for shin
            'foot': 0.0         # End effector
        },
        'pole_target': {
            'enabled': True,
            'reference_bone': 'shin',  # Place pole relative to knee
            'method': 'perpendicular_to_line',
            'distance_multiplier': 2.0
        },
        'constraints': {},
        'prebend': {
            'bone_pattern': 'shin',  # Apply to shin/calf
            'axis': (1, 0, 0),       # X-axis (forward bend)
            'angle': 0.5             # 0.5 radians (~29°)
        }
    },

    'shin': {
        'description': 'Shin IK chain (shorter than foot)',
        'chain_length': 2,  # thigh → shin
        'stiffness': {
            'thigh': 0.2,
            'shin': 0.0,
            'calf': 0.0
        },
        'pole_target': {
            'enabled': True,
            'reference_bone': 'shin',
            'method': 'perpendicular_to_line',
            'distance_multiplier': 2.0
        },
        'constraints': {},
        'prebend': {
            'bone_pattern': 'shin',
            'axis': (1, 0, 0),
            'angle': 0.5
        }
    }
}


def get_ik_template(bone_name):
    """
    Identify which IK rig template to use based on bone name.

    Args:
        bone_name: Name of the bone being dragged

    Returns:
        Template dict or None if no template found
    """
    bone_lower = bone_name.lower()

    # Match bone patterns to templates
    if 'hand' in bone_lower:
        return IK_RIG_TEMPLATES.get('hand')
    elif 'forearm' in bone_lower or 'lorearm' in bone_lower:
        return IK_RIG_TEMPLATES.get('forearm')
    elif 'foot' in bone_lower:
        return IK_RIG_TEMPLATES.get('foot')
    elif 'shin' in bone_lower or 'calf' in bone_lower:
        return IK_RIG_TEMPLATES.get('shin')

    # Add more bone types as needed
    return None


def calculate_pole_position(template, posed_positions, daz_bones, clicked_bone_world_tail, armature):
    """
    Calculate pole target position based on template settings and current pose.

    Args:
        template: IK rig template dict
        posed_positions: Dict of bone_name → {'head': Vector, 'tail': Vector} in world space
        daz_bones: List of PoseBone objects in the IK chain
        clicked_bone_world_tail: World position of clicked bone's tail (target position)
        armature: Armature object

    Returns:
        (pole_world_head, pole_world_tail) tuple of world space Vectors, or None if disabled
    """
    pole_config = template.get('pole_target')
    if not pole_config or not pole_config.get('enabled'):
        return None

    method = pole_config.get('method')
    reference_pattern = pole_config.get('reference_bone', '').lower()
    distance_mult = pole_config.get('distance_multiplier', 2.0)

    # Find reference bone (e.g., forearm for elbow, shin for knee)
    reference_bone = None
    for bone in daz_bones:
        if reference_pattern in bone.name.lower():
            reference_bone = bone
            break

    if not reference_bone or reference_bone.name not in posed_positions:
        print(f"  ⚠️  Pole reference bone not found: {reference_pattern}")
        return None

    if method == 'perpendicular_to_line':
        # Get current reference bone position (e.g., elbow)
        ref_world = posed_positions[reference_bone.name]['head']

        # Find chain start (shoulder for arms, hip for legs)
        chain_start_world = None
        for bone in daz_bones:
            bone_lower = bone.name.lower()
            if 'shldr' in bone_lower or 'shoulder' in bone_lower or 'thigh' in bone_lower:
                if bone.name in posed_positions:
                    chain_start_world = posed_positions[bone.name]['head']
                    break

        if not chain_start_world:
            print(f"  ⚠️  Chain start not found for pole calculation")
            return None

        # Calculate pole position perpendicular to start-target line
        line_vec = clicked_bone_world_tail - chain_start_world
        ref_vec = ref_world - chain_start_world

        # Project reference onto line
        line_dir = line_vec.normalized()
        projection_length = ref_vec.dot(line_dir)
        projection = chain_start_world + line_dir * projection_length

        # Offset perpendicular to line
        offset = ref_world - projection

        # Extend offset for visibility and stability
        pole_distance = max(offset.length * distance_mult, 0.2)  # Minimum 20cm
        if offset.length > 0.001:
            pole_offset_dir = offset.normalized()
        else:
            # Fallback: use world Z if arm is straight
            pole_offset_dir = Vector((0, 0, 1))

        pole_world_head = ref_world + pole_offset_dir * pole_distance
        pole_world_tail = pole_world_head + pole_offset_dir * 0.05  # 5cm for visibility

        print(f"  ✓ Calculated pole position: {pole_world_head} (method: {method}, offset: {pole_distance:.3f}m)")
        return (pole_world_head, pole_world_tail)

    return None
