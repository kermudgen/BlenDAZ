
import logging
log = logging.getLogger(__name__)

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

"""
Rotation Cache Utilities for DAZ Genesis 8/9 Characters

Context manager and utilities for preserving bone rotations during mode switches.
Blender mode switching (POSE → EDIT → POSE) discards un-keyframed rotations,
so we cache them before and restore after.

Extracted from daz_bone_select.py for maintainability.
"""


class PreserveRotations:
    """
    Context manager that preserves bone rotations across mode switches.

    Blender discards un-keyframed rotations when switching between POSE and EDIT modes.
    This context manager caches all bone rotations before entering and restores them
    when exiting, with optional exclusions.

    Usage:
        # Simple case - restore all rotations
        with PreserveRotations(armature):
            bpy.ops.object.mode_set(mode='EDIT')
            # ... do stuff in edit mode ...
            bpy.ops.object.mode_set(mode='POSE')

        # With exclusions - don't restore IK-affected bones
        with PreserveRotations(armature, exclude_on_restore={'lHand', 'lForeArm'}):
            bpy.ops.object.mode_set(mode='EDIT')
            # ... cleanup ...
            bpy.ops.object.mode_set(mode='POSE')

        # Access the cache if needed
        with PreserveRotations(armature) as pr:
            # pr.rotation_cache contains {bone_name: rotation} dict
            ...

    Args:
        armature: The armature object containing the bones
        exclude_on_restore: Optional set of bone names to skip during restoration.
                           Useful when some bones should keep their new poses (e.g., after IK drag)
        verbose: If True, print cache/restore counts (default: True)
    """

    def __init__(self, armature, exclude_on_restore=None, verbose=True):
        self.armature = armature
        self.exclude_on_restore = exclude_on_restore or set()
        self.verbose = verbose
        self.rotation_cache = {}

    def __enter__(self):
        """Cache all bone rotations before potentially destructive operations."""
        for pose_bone in self.armature.pose.bones:
            if pose_bone.rotation_mode == 'QUATERNION':
                self.rotation_cache[pose_bone.name] = pose_bone.rotation_quaternion.copy()
            else:
                self.rotation_cache[pose_bone.name] = pose_bone.rotation_euler.copy()

        if self.verbose:
            log.info(f"  Cached rotations for {len(self.rotation_cache)} bones before mode switch")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore bone rotations after mode switch, respecting exclusions."""
        rotations_restored = 0

        for bone_name, rotation in self.rotation_cache.items():
            # Skip excluded bones (they should keep their new poses)
            if bone_name in self.exclude_on_restore:
                continue

            pose_bone = self.armature.pose.bones.get(bone_name)
            if pose_bone:
                if pose_bone.rotation_mode == 'QUATERNION':
                    pose_bone.rotation_quaternion = rotation
                else:
                    pose_bone.rotation_euler = rotation
                rotations_restored += 1

        if self.verbose and rotations_restored > 0:
            if self.exclude_on_restore:
                log.info(f"  ✓ Restored {rotations_restored} non-excluded bone rotations after mode switch")
            else:
                log.info(f"  ✓ Restored {rotations_restored} bone rotations after mode switch")

        # Don't suppress exceptions
        return False


def cache_rotations(armature):
    """
    Cache all bone rotations from an armature.

    Standalone function for cases where context manager isn't appropriate.

    Args:
        armature: The armature object

    Returns:
        Dict mapping bone_name → rotation (Quaternion or Euler)
    """
    cache = {}
    for pose_bone in armature.pose.bones:
        if pose_bone.rotation_mode == 'QUATERNION':
            cache[pose_bone.name] = pose_bone.rotation_quaternion.copy()
        else:
            cache[pose_bone.name] = pose_bone.rotation_euler.copy()
    return cache


def restore_rotations(armature, cache, exclude=None):
    """
    Restore bone rotations from a cache.

    Standalone function for cases where context manager isn't appropriate.

    Args:
        armature: The armature object
        cache: Dict mapping bone_name → rotation
        exclude: Optional set of bone names to skip

    Returns:
        Number of rotations restored
    """
    exclude = exclude or set()
    restored = 0

    for bone_name, rotation in cache.items():
        if bone_name in exclude:
            continue

        pose_bone = armature.pose.bones.get(bone_name)
        if pose_bone:
            if pose_bone.rotation_mode == 'QUATERNION':
                pose_bone.rotation_quaternion = rotation
            else:
                pose_bone.rotation_euler = rotation
            restored += 1

    return restored
