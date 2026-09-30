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
from .presets import get_bone_group



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


def apply_blended_pose(armature, weighted_poses, grid=None, allowed_bones=None):
    """Apply a blended pose from multiple weighted sources.

    Masking is enforced here (it was previously stored on dots but never
    applied). Two independent gates compose:

    - Per-dot mask: each dot only contributes the bones in its own effective
      mask (``get_bone_mask_for_dot``). A "left arm" dot contributes only left
      arm bones, even though it stored a full-body pose at capture time.
    - Grid region mask (``allowed_bones``): the grid's live "active mask" — a
      set of bone names the blend is allowed to write at all. ``None`` means no
      gating (write everything the dots contribute).

    Args:
        armature: Armature object
        weighted_poses: List of (dot, weight) tuples from blending calculation
        grid: Active PoseBlendGrid (needed to resolve USE_GRID dot masks)
        allowed_bones: Set of writable bone names, or None for no region gating
    """
    if not weighted_poses:
        return

    # Precompute each dot's effective mask and parsed pose data once.
    # entries: (weight, mask_set_or_None, rotations_dict, locations_dict)
    entries = []
    for dot, weight in weighted_poses:
        mask = get_bone_mask_for_dot(dot, grid)
        mask_set = set(mask) if mask is not None else None
        entries.append((weight, mask_set, dot.get_rotations_dict(), dot.get_locations_dict()))

    def dot_allows(mask_set, bone_name):
        return mask_set is None or bone_name in mask_set

    def region_allows(bone_name):
        return allowed_bones is None or bone_name in allowed_bones

    # Collect affected rotation bones, respecting per-dot + region masks
    all_bones = set()
    for weight, mask_set, rotations, _locations in entries:
        for b in rotations:
            if dot_allows(mask_set, b) and region_allows(b):
                all_bones.add(b)

    # Blend each bone's rotation
    for bone_name in all_bones:
        bone_rotations = []
        for weight, mask_set, rotations, _locations in entries:
            if not dot_allows(mask_set, bone_name):
                continue
            quat_data = rotations.get(bone_name)
            if quat_data:
                quat = Quaternion((quat_data[0], quat_data[1], quat_data[2], quat_data[3]))
                bone_rotations.append((quat, weight))

        if not bone_rotations:
            continue

        # Blend quaternions (weights renormalized inside)
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
    for weight, mask_set, _rotations, locations in entries:
        for b in locations:
            if dot_allows(mask_set, b) and region_allows(b):
                all_loc_bones.add(b)

    for bone_name in all_loc_bones:
        # Only dots that contribute this bone participate; a masked-out dot
        # must not drag the location toward zero.
        bone_locs = []
        for weight, mask_set, _rotations, locations in entries:
            if not dot_allows(mask_set, bone_name):
                continue
            loc_data = locations.get(bone_name)
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
# Morph Capture / Apply / Blend
# ============================================================================

def capture_morphs(armature, morph_names):
    """Capture current morph values from armature custom properties.

    Args:
        armature: Armature object
        morph_names: List of morph property names to capture

    Returns:
        Dict of {morph_name: float_value}
    """
    morphs = {}
    for name in morph_names:
        val = armature.get(name)
        if isinstance(val, (int, float)):
            morphs[name] = float(val)
    return morphs


def apply_morphs(armature, morph_dict):
    """Apply morph values to armature custom properties.

    Args:
        armature: Armature object
        morph_dict: Dict of {morph_name: float_value}
    """
    for name, value in morph_dict.items():
        if name in armature:
            armature[name] = value
    armature.update_tag()


def blend_morphs(weighted_morph_dicts):
    """Weighted blend of morph values from multiple dots.

    Args:
        weighted_morph_dicts: List of (morph_dict, weight) tuples

    Returns:
        Blended morph_dict {name: float}
    """
    result = {}
    for morph_dict, weight in weighted_morph_dicts:
        for name, value in morph_dict.items():
            result[name] = result.get(name, 0.0) + value * weight
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

def get_bone_mask_for_dot(dot, grid=None):
    """Get the effective bone mask for a dot.

    Args:
        dot: PoseBlendDot PropertyGroup
        grid: Owning PoseBlendGrid — required to resolve 'USE_GRID' mode

    Returns:
        List of bone names, or None for all bones
    """
    mode = dot.bone_mask_mode

    if mode == 'USE_GRID':
        # Inherit the grid's mask. Grid mask is ALL or PRESET.
        if grid is None or grid.bone_mask_mode == 'ALL':
            return None
        return get_bone_group(grid.bone_mask_preset)

    if mode == 'ALL':
        return None  # All bones
    elif mode == 'PRESET':
        return get_bone_group(dot.bone_mask_preset)
    elif mode == 'CUSTOM':
        return dot.get_custom_mask_list()
    return None


def get_grid_region_mask(grid):
    """Resolve a grid's live 'active mask' to a set of writable bone names.

    Args:
        grid: PoseBlendGrid, or None

    Returns:
        Set of bone names the blend is allowed to write, or None for no gating.
        An empty set means every region is disabled (nothing writes).
    """
    if grid is None:
        return None
    regions = grid.get_active_regions()
    if regions is None:
        return None  # All regions active — no gating
    from .presets import bones_for_regions
    return bones_for_regions(regions)


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
