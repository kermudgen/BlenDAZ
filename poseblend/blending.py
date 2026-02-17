"""PoseBlend Blending - Distance-weighted interpolation algorithms"""

import math
from mathutils import Quaternion


# ============================================================================
# Weight Calculation
# ============================================================================

def calculate_blend_weights(cursor_pos, dots, falloff='QUADRATIC', radius=0.0):
    """Calculate blend weights for each dot based on cursor position

    Uses inverse distance weighting (IDW) algorithm.

    Args:
        cursor_pos: (x, y) tuple, normalized grid position (0-1)
        dots: List/Collection of PoseBlendDot
        falloff: 'LINEAR', 'QUADRATIC', 'CUBIC', or 'SMOOTH'
        radius: Max influence radius (0 = infinite)

    Returns:
        List of (dot, weight) tuples, normalized to sum to 1.0
        Empty list if no dots or cursor too far from all dots
    """
    if not dots:
        return []

    EPSILON = 0.001  # Threshold for "direct hit"

    weights = []

    for dot in dots:
        # Calculate Euclidean distance
        dx = cursor_pos[0] - dot.position[0]
        dy = cursor_pos[1] - dot.position[1]
        distance = math.sqrt(dx * dx + dy * dy)

        # Check for direct hit
        if distance < EPSILON:
            return [(dot, 1.0)]  # 100% this pose

        # Check radius cutoff
        if radius > 0 and distance > radius:
            continue

        # Calculate weight based on falloff type
        weight = calculate_weight(distance, falloff, radius)

        if weight > 0:
            weights.append((dot, weight))

    # Normalize weights to sum to 1.0
    if not weights:
        return []

    total = sum(w for _, w in weights)
    if total > 0:
        weights = [(dot, w / total) for dot, w in weights]

    return weights


def calculate_weight(distance, falloff, radius):
    """Calculate individual weight for a given distance

    Args:
        distance: Distance from cursor to dot
        falloff: Falloff type string
        radius: Max radius (0 = infinite)

    Returns:
        Unnormalized weight value
    """
    if distance <= 0:
        return float('inf')

    if falloff == 'LINEAR':
        # 1/d - gentle falloff
        return 1.0 / distance

    elif falloff == 'QUADRATIC':
        # 1/d^2 - natural feeling (default)
        return 1.0 / (distance * distance)

    elif falloff == 'CUBIC':
        # 1/d^3 - sharper falloff, more distinct poses
        return 1.0 / (distance * distance * distance)

    elif falloff == 'SMOOTH':
        # Smoothstep-based falloff
        # Requires radius to be set
        if radius <= 0:
            radius = 1.0  # Default to full grid

        # Normalize distance to 0-1 range
        t = min(distance / radius, 1.0)

        # Smoothstep: 3t^2 - 2t^3
        # Inverse for weight: 1 - smoothstep
        smooth = 3 * t * t - 2 * t * t * t
        return max(0, 1.0 - smooth)

    else:
        # Default to quadratic
        return 1.0 / (distance * distance)


# ============================================================================
# Blend Quaternions
# ============================================================================

def blend_quaternions_weighted(quat_weight_list):
    """Blend multiple quaternions with weights

    Uses iterative SLERP for smooth interpolation.

    Args:
        quat_weight_list: List of (Quaternion, weight) tuples
                         Weights should already be normalized

    Returns:
        Blended Quaternion
    """
    if not quat_weight_list:
        return Quaternion()  # Identity

    if len(quat_weight_list) == 1:
        return quat_weight_list[0][0].copy()

    # Sort by weight (largest first) for numerical stability
    sorted_quats = sorted(quat_weight_list, key=lambda x: x[1], reverse=True)

    # Start with highest weight quaternion
    result = sorted_quats[0][0].copy()
    cumulative_weight = sorted_quats[0][1]

    for quat, weight in sorted_quats[1:]:
        if weight <= 0:
            continue

        # Calculate interpolation factor
        total = cumulative_weight + weight
        if total <= 0:
            continue

        t = weight / total

        # Ensure quaternions are in same hemisphere
        # (dot product should be positive for shortest path)
        if result.dot(quat) < 0:
            quat = Quaternion((-quat.w, -quat.x, -quat.y, -quat.z))

        # Spherical linear interpolation
        result = result.slerp(quat, t)
        cumulative_weight = total

    return result


def blend_pose_rotations(weighted_dots, bone_name):
    """Blend rotations for a specific bone from multiple weighted dots

    Args:
        weighted_dots: List of (dot, weight) tuples
        bone_name: Name of bone to blend

    Returns:
        Blended Quaternion, or None if no data
    """
    quat_weights = []

    for dot, weight in weighted_dots:
        quat_data = dot.get_rotation(bone_name)
        if quat_data:
            quat = Quaternion((quat_data[0], quat_data[1], quat_data[2], quat_data[3]))
            quat_weights.append((quat, weight))

    if not quat_weights:
        return None

    return blend_quaternions_weighted(quat_weights)


# ============================================================================
# Full Pose Blending
# ============================================================================

def calculate_blended_pose(cursor_pos, dots, falloff='QUADRATIC', radius=0.0):
    """Calculate complete blended pose from cursor position

    Args:
        cursor_pos: (x, y) cursor position on grid
        dots: Collection of PoseBlendDot
        falloff: Falloff type
        radius: Max influence radius

    Returns:
        Dict of {bone_name: Quaternion} for all affected bones
    """
    # Get weights for each dot
    weights = calculate_blend_weights(cursor_pos, dots, falloff, radius)

    if not weights:
        return {}

    # Special case: single dot with 100% weight
    if len(weights) == 1 and weights[0][1] >= 0.999:
        dot = weights[0][0]
        rotations = dot.get_rotations_dict()
        return {
            name: Quaternion((q[0], q[1], q[2], q[3]))
            for name, q in rotations.items()
        }

    # Collect all affected bones
    all_bones = set()
    for dot, _ in weights:
        rotations = dot.get_rotations_dict()
        all_bones.update(rotations.keys())

    # Blend each bone
    blended = {}
    for bone_name in all_bones:
        # Filter to dots that affect this bone
        bone_weights = []
        for dot, weight in weights:
            if bone_name in dot.get_rotations_dict():
                bone_weights.append((dot, weight))

        if not bone_weights:
            continue

        # Re-normalize weights for this bone
        total = sum(w for _, w in bone_weights)
        if total > 0:
            bone_weights = [(d, w / total) for d, w in bone_weights]

        # Blend
        blended_quat = blend_pose_rotations(bone_weights, bone_name)
        if blended_quat:
            blended[bone_name] = blended_quat

    return blended


# ============================================================================
# Utility Functions
# ============================================================================

def get_dominant_dot(cursor_pos, dots, threshold=0.7):
    """Find if any single dot dominates the blend

    Useful for UI feedback (highlight strongly-weighted dot).

    Args:
        cursor_pos: Cursor position
        dots: Collection of dots
        threshold: Minimum weight to be considered dominant

    Returns:
        (dot, weight) if dominant, else None
    """
    weights = calculate_blend_weights(cursor_pos, dots)

    if not weights:
        return None

    # Sort by weight descending
    weights.sort(key=lambda x: x[1], reverse=True)

    if weights[0][1] >= threshold:
        return weights[0]

    return None


def get_top_influences(cursor_pos, dots, max_count=3):
    """Get top N influential dots for visualization

    Args:
        cursor_pos: Cursor position
        dots: Collection of dots
        max_count: Maximum dots to return

    Returns:
        List of (dot, weight) tuples, sorted by weight descending
    """
    weights = calculate_blend_weights(cursor_pos, dots)
    weights.sort(key=lambda x: x[1], reverse=True)
    return weights[:max_count]


# ============================================================================
# Registration
# ============================================================================

def register():
    pass


def unregister():
    pass
