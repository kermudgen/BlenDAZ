# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joshua D Rother
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""PoseBlend Poses - Pose capture and application functions"""

import bpy
import math
from mathutils import Quaternion, Vector
from .presets import get_bone_group, get_all_body_bones



# ============================================================================
# Pose Capture
# ============================================================================

def capture_pose(armature, bone_mask=None):
    """Capture current pose from armature

    Args:
        armature: Armature object
        bone_mask: List of bone names to capture, or None for all

    Returns:
        Dict of {bone_name: [w, x, y, z]} quaternions
    """
    if armature is None or armature.type != 'ARMATURE':
        return {}

    rotations = {}

    for pose_bone in armature.pose.bones:
        # Skip if not in mask
        if bone_mask is not None and pose_bone.name not in bone_mask:
            continue

        # Get rotation as quaternion
        # Handle different rotation modes
        if pose_bone.rotation_mode == 'QUATERNION':
            quat = pose_bone.rotation_quaternion.copy()
        else:
            # Convert from euler
            quat = pose_bone.rotation_euler.to_quaternion()

        rotations[pose_bone.name] = [quat.w, quat.x, quat.y, quat.z]

    return rotations


def capture_pose_for_preset(armature, preset_name):
    """Capture pose for a specific bone group preset

    Args:
        armature: Armature object
        preset_name: Bone group preset name (e.g., 'HEAD', 'ARMS')

    Returns:
        Dict of bone rotations
    """
    bone_mask = get_bone_group(preset_name)
    return capture_pose(armature, bone_mask)


def capture_bone_locations(armature, bone_mask=None):
    """Capture bone locations for bones with non-zero translation (e.g., hip root bone).

    Only stores bones where location is non-zero or the bone is a root bone (no parent),
    to keep the data compact — most bones in a DAZ rig never use location.

    Args:
        armature: Armature object
        bone_mask: List of bone names to capture, or None for all

    Returns:
        Dict of {bone_name: [x, y, z]} locations
    """
    if armature is None or armature.type != 'ARMATURE':
        return {}

    locations = {}

    for pose_bone in armature.pose.bones:
        if bone_mask is not None and pose_bone.name not in bone_mask:
            continue

        # Capture root bones always (hip), and any bone with non-zero location
        is_root = pose_bone.bone.parent is None
        has_location = pose_bone.location.length_squared > 1e-8

        if is_root or has_location:
            loc = pose_bone.location
            locations[pose_bone.name] = [loc.x, loc.y, loc.z]

    return locations


# ============================================================================
# Pose Application
# ============================================================================

def apply_pose(armature, rotations, bone_mask=None, locations=None):
    """Apply pose rotations (and optionally locations) to armature

    Args:
        armature: Armature object
        rotations: Dict of {bone_name: [w, x, y, z]}
        bone_mask: Optional mask to filter which bones to affect
        locations: Optional dict of {bone_name: [x, y, z]}
    """
    if armature is None or armature.type != 'ARMATURE':
        return

    for bone_name, quat_values in rotations.items():
        # Skip if not in mask
        if bone_mask is not None and bone_name not in bone_mask:
            continue

        pose_bone = armature.pose.bones.get(bone_name)
        if pose_bone is None:
            continue

        # Create quaternion
        quat = Quaternion((quat_values[0], quat_values[1], quat_values[2], quat_values[3]))

        # Apply based on rotation mode
        if pose_bone.rotation_mode == 'QUATERNION':
            pose_bone.rotation_quaternion = quat
        else:
            pose_bone.rotation_euler = quat.to_euler(pose_bone.rotation_mode)

    # Apply locations if provided
    if locations:
        for bone_name, loc_values in locations.items():
            if bone_mask is not None and bone_name not in bone_mask:
                continue
            pose_bone = armature.pose.bones.get(bone_name)
            if pose_bone:
                pose_bone.location = Vector(loc_values)


def apply_blended_pose(armature, weighted_poses):
    """Apply a blended pose from multiple weighted sources

    Args:
        armature: Armature object
        weighted_poses: List of (dot, weight) tuples from blending calculation
    """
    if not weighted_poses:
        return

    # Collect all affected bones (from rotations)
    all_bones = set()
    for dot, weight in weighted_poses:
        rotations = dot.get_rotations_dict()
        all_bones.update(rotations.keys())

    # Blend each bone's rotation
    for bone_name in all_bones:
        # Collect rotations for this bone from dots that have it
        bone_rotations = []
        for dot, weight in weighted_poses:
            quat_data = dot.get_rotation(bone_name)
            if quat_data:
                quat = Quaternion((quat_data[0], quat_data[1], quat_data[2], quat_data[3]))
                bone_rotations.append((quat, weight))

        if not bone_rotations:
            continue

        # Blend quaternions
        blended_quat = blend_quaternions(bone_rotations)

        # Apply to bone
        pose_bone = armature.pose.bones.get(bone_name)
        if pose_bone:
            if pose_bone.rotation_mode == 'QUATERNION':
                pose_bone.rotation_quaternion = blended_quat
            else:
                pose_bone.rotation_euler = blended_quat.to_euler(pose_bone.rotation_mode)

    # Blend bone locations (hip root bone, any translated bones)
    all_loc_bones = set()
    for dot, weight in weighted_poses:
        locations = dot.get_locations_dict()
        all_loc_bones.update(locations.keys())

    for bone_name in all_loc_bones:
        # Collect locations from all dots — missing means (0,0,0)
        bone_locs = []
        for dot, weight in weighted_poses:
            loc_data = dot.get_location(bone_name)
            if loc_data:
                bone_locs.append((Vector(loc_data), weight))
            else:
                bone_locs.append((Vector((0, 0, 0)), weight))

        # Weighted average (linear interpolation for locations)
        total_weight = sum(w for _, w in bone_locs)
        if total_weight > 0:
            blended_loc = Vector((0, 0, 0))
            for loc, w in bone_locs:
                blended_loc += loc * (w / total_weight)

            pose_bone = armature.pose.bones.get(bone_name)
            if pose_bone:
                pose_bone.location = blended_loc


def slerp_unclamped(q1, q2, t):
    """Spherical linear interpolation without clamping t to [0, 1].

    Allows extrapolation: t > 1 overshoots past q2, t < 0 goes opposite.
    Blender's Quaternion.slerp() clamps t, so we need our own for extrapolation.

    Args:
        q1: Start quaternion
        q2: End quaternion
        t: Interpolation factor (can be outside 0-1)

    Returns:
        Interpolated/extrapolated Quaternion
    """
    # Use Blender's built-in for normal range
    if 0.0 <= t <= 1.0:
        return q1.slerp(q2, t)

    # Ensure shortest path
    dot = q1.dot(q2)
    if dot < 0:
        q2 = -q2
        dot = -dot

    # Clamp dot for numerical safety
    dot = min(max(dot, -1.0), 1.0)
    theta = math.acos(dot)

    if theta < 0.001:
        # Quaternions nearly identical — lerp
        result = Quaternion((
            q1.w * (1 - t) + q2.w * t,
            q1.x * (1 - t) + q2.x * t,
            q1.y * (1 - t) + q2.y * t,
            q1.z * (1 - t) + q2.z * t,
        ))
        result.normalize()
        return result

    sin_theta = math.sin(theta)
    a = math.sin((1 - t) * theta) / sin_theta
    b = math.sin(t * theta) / sin_theta

    result = Quaternion((
        q1.w * a + q2.w * b,
        q1.x * a + q2.x * b,
        q1.y * a + q2.y * b,
        q1.z * a + q2.z * b,
    ))
    result.normalize()
    return result


def blend_quaternions(weighted_quats):
    """Blend multiple weighted quaternions

    Uses iterative SLERP for smooth blending.
    Supports extrapolation (weights outside 0-1) via slerp_unclamped.

    Args:
        weighted_quats: List of (Quaternion, weight) tuples

    Returns:
        Blended Quaternion
    """
    if not weighted_quats:
        return Quaternion()

    if len(weighted_quats) == 1:
        return weighted_quats[0][0].copy()

    # Normalize weights
    total_weight = sum(w for _, w in weighted_quats)
    if total_weight <= 0:
        return weighted_quats[0][0].copy()

    normalized = [(q, w / total_weight) for q, w in weighted_quats]

    # Iterative SLERP
    result = normalized[0][0].copy()
    cumulative_weight = normalized[0][1]

    for quat, weight in normalized[1:]:
        # Calculate interpolation factor
        t = weight / (cumulative_weight + weight)

        # Ensure quaternions are in same hemisphere for proper interpolation
        if result.dot(quat) < 0:
            quat = -quat

        result = slerp_unclamped(result, quat, t)
        cumulative_weight += weight

    return result


# ============================================================================
# Keyframing
# ============================================================================

def keyframe_pose(armature, bone_mask=None, frame=None):
    """Insert keyframes for current pose (rotations and locations)

    Args:
        armature: Armature object
        bone_mask: Optional list of bones to keyframe
        frame: Frame number, or None for current frame
    """
    if armature is None or armature.type != 'ARMATURE':
        return

    if frame is None:
        frame = bpy.context.scene.frame_current

    for pose_bone in armature.pose.bones:
        if bone_mask is not None and pose_bone.name not in bone_mask:
            continue

        # Keyframe rotation
        if pose_bone.rotation_mode == 'QUATERNION':
            pose_bone.keyframe_insert(data_path='rotation_quaternion', frame=frame)
        else:
            pose_bone.keyframe_insert(data_path='rotation_euler', frame=frame)

        # Keyframe location for root bones or bones with non-zero location
        if pose_bone.bone.parent is None or pose_bone.location.length_squared > 1e-8:
            pose_bone.keyframe_insert(data_path='location', frame=frame)


# ============================================================================
# Bone Mask Utilities
# ============================================================================

def get_bone_mask_for_dot(dot):
    """Get the effective bone mask for a dot

    Args:
        dot: PoseBlendDot PropertyGroup

    Returns:
        List of bone names, or None for all bones
    """
    if dot.bone_mask_mode == 'ALL':
        return None  # All bones
    elif dot.bone_mask_mode == 'PRESET':
        return get_bone_group(dot.bone_mask_preset)
    elif dot.bone_mask_mode == 'CUSTOM':
        return dot.get_custom_mask_list()
    return None


def filter_rotations_by_mask(rotations, bone_mask):
    """Filter rotations dict to only include bones in mask

    Args:
        rotations: Dict of {bone_name: rotation}
        bone_mask: List of bone names, or None for no filtering

    Returns:
        Filtered dict
    """
    if bone_mask is None:
        return rotations

    return {k: v for k, v in rotations.items() if k in bone_mask}


# ============================================================================
# Registration
# ============================================================================

def register():
    pass


def unregister():
    pass
