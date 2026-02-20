"""
DAZ Rig Manager - Centralized rig detection, preparation, and metadata storage

This module provides a single source of truth for DAZ character rig information,
eliminating scattered quaternion/euler checks and enabling future DAZ export.

Usage:
    from daz_rig_manager import RigManager

    # Initialize rig (call once when first working with armature)
    rig_info = RigManager.prepare_rig(armature)

    # Check if rig is ready
    if RigManager.is_prepared(armature):
        info = RigManager.get_rig_info(armature)
        print(f"Genesis {info.genesis_version} rig with {len(info.bone_hierarchy)} bones")

    # For DAZ export (future)
    RigManager.export_pose_to_daz(armature, "my_pose.duf")
"""

import bpy
from mathutils import Vector, Quaternion
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class DAZRigInfo:
    """Stores all metadata about a DAZ character rig."""

    # Basic identification
    armature_name: str = ""
    armature_id: int = 0  # Python id() for fast lookup
    fingerprint: str = ""  # Diffeomorphic's rig ID if available

    # Genesis version detection
    genesis_version: int = 0  # 8 or 9, 0 if unknown
    is_male: bool = False

    # Bone structure
    bone_count: int = 0
    bone_hierarchy: Dict[str, str] = field(default_factory=dict)  # bone_name → parent_name

    # Rotation mode tracking (for DAZ export)
    original_rotation_modes: Dict[str, str] = field(default_factory=dict)  # bone_name → 'QUATERNION'/'XYZ'/etc

    # IK-related caching
    bend_twist_pairs: Dict[str, str] = field(default_factory=dict)  # lShldrBend → lShldrTwist
    ik_chain_definitions: Dict[str, List[str]] = field(default_factory=dict)  # 'left_arm' → [bone_names]

    # State
    is_prepared: bool = False
    bones_converted_to_quaternion: int = 0


class RigManager:
    """
    Singleton manager for DAZ rig preparation and metadata.

    Handles:
    - Rig detection and fingerprinting
    - Conversion to quaternion mode
    - Caching of rig metadata
    - (Future) Export back to DAZ format
    """

    # Cache of prepared rigs: armature_id → DAZRigInfo
    _rig_cache: Dict[int, DAZRigInfo] = {}

    # Genesis bone patterns for version detection
    GENESIS_8_MARKERS = {'lPectoral', 'rPectoral', 'lCollar', 'rCollar'}
    GENESIS_9_MARKERS = {'l_pectoral', 'r_pectoral', 'l_collar', 'r_collar'}  # G9 uses underscores

    # Bend/Twist bone patterns
    BEND_TWIST_PATTERNS = [
        ('Shldr', 'Shoulder'),  # lShldrBend/lShldrTwist
        ('ForeArm', 'Forearm'),
        ('Thigh',),
        ('Shin',),
    ]

    @classmethod
    def prepare_rig(cls, armature, force: bool = False) -> Optional[DAZRigInfo]:
        """
        Prepare a DAZ rig for IK operations.

        - Detects Genesis version
        - Converts all bones to quaternion mode
        - Caches bone hierarchy and metadata

        Args:
            armature: The armature object
            force: If True, re-prepare even if already done

        Returns:
            DAZRigInfo object, or None if not a valid armature
        """
        if not armature or armature.type != 'ARMATURE':
            return None

        armature_id = id(armature.data)

        # Check cache
        if armature_id in cls._rig_cache and not force:
            return cls._rig_cache[armature_id]

        # Create new rig info
        info = DAZRigInfo()
        info.armature_name = armature.name
        info.armature_id = armature_id

        # Detect Genesis version
        info.genesis_version = cls._detect_genesis_version(armature)

        # Build bone hierarchy
        info.bone_hierarchy = cls._build_bone_hierarchy(armature)
        info.bone_count = len(info.bone_hierarchy)

        # Find bend/twist pairs
        info.bend_twist_pairs = cls._find_bend_twist_pairs(armature)

        # Convert to quaternion mode and track original modes
        info.original_rotation_modes, info.bones_converted_to_quaternion = \
            cls._convert_to_quaternion(armature)

        # Detect fingerprint if Diffeomorphic data available
        info.fingerprint = cls._get_diffeomorphic_fingerprint(armature)

        info.is_prepared = True

        # Cache and return
        cls._rig_cache[armature_id] = info

        print(f"[RIG MANAGER] Prepared rig: {armature.name}")
        print(f"  Genesis version: {info.genesis_version or 'Unknown'}")
        print(f"  Bones: {info.bone_count}")
        print(f"  Converted to quaternion: {info.bones_converted_to_quaternion}")
        print(f"  Bend/twist pairs: {len(info.bend_twist_pairs)}")

        return info

    @classmethod
    def is_prepared(cls, armature) -> bool:
        """Check if armature has been prepared."""
        if not armature:
            return False
        return id(armature.data) in cls._rig_cache

    @classmethod
    def get_rig_info(cls, armature) -> Optional[DAZRigInfo]:
        """Get cached rig info, or None if not prepared."""
        if not armature:
            return None
        return cls._rig_cache.get(id(armature.data))

    @classmethod
    def _detect_genesis_version(cls, armature) -> int:
        """Detect if this is a Genesis 8 or 9 rig."""
        bone_names = {b.name for b in armature.pose.bones}

        # Check for Genesis 9 markers first (more specific)
        if cls.GENESIS_9_MARKERS.intersection(bone_names):
            return 9

        # Check for Genesis 8 markers
        if cls.GENESIS_8_MARKERS.intersection(bone_names):
            return 8

        # Could add more heuristics here
        return 0

    @classmethod
    def _build_bone_hierarchy(cls, armature) -> Dict[str, str]:
        """Build a dictionary of bone_name → parent_name."""
        hierarchy = {}
        for bone in armature.pose.bones:
            parent_name = bone.parent.name if bone.parent else ""
            hierarchy[bone.name] = parent_name
        return hierarchy

    @classmethod
    def _find_bend_twist_pairs(cls, armature) -> Dict[str, str]:
        """Find matching Bend/Twist bone pairs."""
        pairs = {}
        bone_names = {b.name for b in armature.pose.bones}

        for bone in armature.pose.bones:
            name = bone.name
            if 'Bend' in name:
                twist_name = name.replace('Bend', 'Twist')
                if twist_name in bone_names:
                    pairs[name] = twist_name

        return pairs

    @classmethod
    def _convert_to_quaternion(cls, armature) -> Tuple[Dict[str, str], int]:
        """
        Convert all bones to quaternion rotation mode.

        Returns:
            Tuple of (original_modes_dict, count_converted)
        """
        original_modes = {}
        converted_count = 0

        for pose_bone in armature.pose.bones:
            original_mode = pose_bone.rotation_mode
            original_modes[pose_bone.name] = original_mode

            if original_mode != 'QUATERNION':
                # Convert current rotation to quaternion BEFORE changing mode
                if original_mode == 'AXIS_ANGLE':
                    axis = Vector(pose_bone.rotation_axis_angle[1:4])
                    angle = pose_bone.rotation_axis_angle[0]
                    quat = Quaternion(axis, angle)
                else:
                    # Euler to quaternion
                    quat = pose_bone.rotation_euler.to_quaternion()

                # Change mode and set quaternion
                pose_bone.rotation_mode = 'QUATERNION'
                pose_bone.rotation_quaternion = quat
                converted_count += 1

        return original_modes, converted_count

    @classmethod
    def _get_diffeomorphic_fingerprint(cls, armature) -> str:
        """Get Diffeomorphic's rig fingerprint if available."""
        # Diffeomorphic stores metadata in custom properties
        if hasattr(armature, 'DazRig'):
            return str(armature.DazRig)
        if 'DazRig' in armature:
            return str(armature['DazRig'])
        return ""

    @classmethod
    def restore_rotation_modes(cls, armature) -> int:
        """
        Restore bones to their original rotation modes.

        Used when exporting back to DAZ or when user wants to undo preparation.

        Returns:
            Number of bones restored
        """
        info = cls.get_rig_info(armature)
        if not info:
            return 0

        restored_count = 0
        for pose_bone in armature.pose.bones:
            original_mode = info.original_rotation_modes.get(pose_bone.name, 'QUATERNION')

            if pose_bone.rotation_mode != original_mode:
                # Convert current quaternion to target mode
                quat = pose_bone.rotation_quaternion.copy()

                if original_mode == 'AXIS_ANGLE':
                    axis, angle = quat.to_axis_angle()
                    pose_bone.rotation_mode = 'AXIS_ANGLE'
                    pose_bone.rotation_axis_angle = (angle, axis.x, axis.y, axis.z)
                else:
                    # Quaternion to Euler
                    euler = quat.to_euler(original_mode)
                    pose_bone.rotation_mode = original_mode
                    pose_bone.rotation_euler = euler

                restored_count += 1

        return restored_count

    @classmethod
    def get_ik_chain(cls, armature, end_bone_name: str, chain_type: str = 'auto') -> List[str]:
        """
        Get the IK chain for a given end effector bone.

        Args:
            armature: The armature
            end_bone_name: Name of the end effector (e.g., 'lHand', 'lFoot')
            chain_type: 'arm', 'leg', or 'auto' to detect

        Returns:
            List of bone names from root to end
        """
        info = cls.get_rig_info(armature)
        if not info:
            return []

        # Auto-detect chain type from bone name
        if chain_type == 'auto':
            name_lower = end_bone_name.lower()
            if 'hand' in name_lower or 'forearm' in name_lower:
                chain_type = 'arm'
            elif 'foot' in name_lower or 'shin' in name_lower:
                chain_type = 'leg'
            else:
                chain_type = 'unknown'

        # Build chain by walking up the hierarchy
        chain = []
        current_bone = end_bone_name
        max_depth = 10  # Prevent infinite loops

        while current_bone and max_depth > 0:
            chain.insert(0, current_bone)
            current_bone = info.bone_hierarchy.get(current_bone, "")
            max_depth -= 1

            # Stop at certain bones
            if current_bone.lower() in ('pelvis', 'hip', 'spine'):
                break

        return chain

    @classmethod
    def clear_cache(cls):
        """Clear all cached rig info."""
        cls._rig_cache.clear()
        print("[RIG MANAGER] Cache cleared")

    # ========================================================================
    # FUTURE: DAZ Export Functions
    # ========================================================================

    @classmethod
    def export_pose_to_daz(cls, armature, filepath: str) -> bool:
        """
        Export current pose to DAZ-compatible format.

        TODO: Implement DSF/DUF generation

        Args:
            armature: The armature with pose to export
            filepath: Output file path (.duf or .dsf)

        Returns:
            True if successful
        """
        # Placeholder for future implementation
        print(f"[RIG MANAGER] Export to DAZ not yet implemented")
        print(f"  Would export: {armature.name} → {filepath}")
        return False


# Convenience functions for module-level access
def prepare_rig(armature, force=False):
    """Prepare a DAZ rig for IK operations."""
    return RigManager.prepare_rig(armature, force)

def is_rig_prepared(armature):
    """Check if armature has been prepared."""
    return RigManager.is_prepared(armature)

def get_rig_info(armature):
    """Get cached rig info."""
    return RigManager.get_rig_info(armature)
