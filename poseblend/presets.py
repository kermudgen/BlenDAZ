
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

"""PoseBlend Presets - Bone group definitions and default configurations"""

# ============================================================================
# Genesis 8 Bone Groups
# ============================================================================

GENESIS8_BONE_GROUPS = {
    'HEAD': [
        'head', 'neck', 'neckLower', 'neckUpper',
        'lEye', 'rEye',
        'jaw',
        # Basic facial - expand as needed
        'upperFaceRig', 'lowerFaceRig',
    ],

    'UPPER_BODY': [
        # Spine
        'chest', 'chestUpper', 'chestLower',
        'abdomen', 'abdomenUpper', 'abdomenLower', 'abdomen2',
        # Shoulders
        'lCollar', 'rCollar',
        'lShldr', 'rShldr',
        'lShldrBend', 'rShldrBend',
        'lShldrTwist', 'rShldrTwist',
        # Forearms
        'lForeArm', 'rForeArm',
        'lForearmBend', 'rForearmBend',
        'lForearmTwist', 'rForearmTwist',
        # Hands
        'lHand', 'rHand',
    ],

    'LOWER_BODY': [
        'pelvis', 'hip',
        # Thighs
        'lThigh', 'rThigh',
        'lThighBend', 'rThighBend',
        'lThighTwist', 'rThighTwist',
        # Shins
        'lShin', 'rShin',
        # Feet
        'lFoot', 'rFoot',
        'lToe', 'rToe',
        'lMetatarsals', 'rMetatarsals',
    ],

    'ARMS': [
        # Left arm
        'lCollar', 'lShldr', 'lShldrBend', 'lShldrTwist',
        'lForeArm', 'lForearmBend', 'lForearmTwist',
        'lHand',
        # Right arm
        'rCollar', 'rShldr', 'rShldrBend', 'rShldrTwist',
        'rForeArm', 'rForearmBend', 'rForearmTwist',
        'rHand',
        # Include hands
        'lThumb1', 'lThumb2', 'lThumb3',
        'lIndex1', 'lIndex2', 'lIndex3',
        'lMid1', 'lMid2', 'lMid3',
        'lRing1', 'lRing2', 'lRing3',
        'lPinky1', 'lPinky2', 'lPinky3',
        'rThumb1', 'rThumb2', 'rThumb3',
        'rIndex1', 'rIndex2', 'rIndex3',
        'rMid1', 'rMid2', 'rMid3',
        'rRing1', 'rRing2', 'rRing3',
        'rPinky1', 'rPinky2', 'rPinky3',
    ],

    'ARM_L': [
        'lCollar', 'lShldr', 'lShldrBend', 'lShldrTwist',
        'lForeArm', 'lForearmBend', 'lForearmTwist',
        'lHand',
        'lThumb1', 'lThumb2', 'lThumb3',
        'lIndex1', 'lIndex2', 'lIndex3',
        'lMid1', 'lMid2', 'lMid3',
        'lRing1', 'lRing2', 'lRing3',
        'lPinky1', 'lPinky2', 'lPinky3',
    ],

    'ARM_R': [
        'rCollar', 'rShldr', 'rShldrBend', 'rShldrTwist',
        'rForeArm', 'rForearmBend', 'rForearmTwist',
        'rHand',
        'rThumb1', 'rThumb2', 'rThumb3',
        'rIndex1', 'rIndex2', 'rIndex3',
        'rMid1', 'rMid2', 'rMid3',
        'rRing1', 'rRing2', 'rRing3',
        'rPinky1', 'rPinky2', 'rPinky3',
    ],

    'LEGS': [
        'lThigh', 'rThigh',
        'lThighBend', 'rThighBend',
        'lThighTwist', 'rThighTwist',
        'lShin', 'rShin',
        'lFoot', 'rFoot',
        'lToe', 'rToe',
        'lMetatarsals', 'rMetatarsals',
    ],

    'LEG_L': [
        'lThigh', 'lThighBend', 'lThighTwist',
        'lShin',
        'lFoot', 'lToe', 'lMetatarsals',
    ],

    'LEG_R': [
        'rThigh', 'rThighBend', 'rThighTwist',
        'rShin',
        'rFoot', 'rToe', 'rMetatarsals',
    ],

    'HANDS': [
        'lHand', 'rHand',
        # Left hand fingers
        'lThumb1', 'lThumb2', 'lThumb3',
        'lIndex1', 'lIndex2', 'lIndex3',
        'lMid1', 'lMid2', 'lMid3',
        'lRing1', 'lRing2', 'lRing3',
        'lPinky1', 'lPinky2', 'lPinky3',
        # Right hand fingers
        'rThumb1', 'rThumb2', 'rThumb3',
        'rIndex1', 'rIndex2', 'rIndex3',
        'rMid1', 'rMid2', 'rMid3',
        'rRing1', 'rRing2', 'rRing3',
        'rPinky1', 'rPinky2', 'rPinky3',
        # Carpal bones if present
        'lCarpal1', 'lCarpal2', 'lCarpal3', 'lCarpal4',
        'rCarpal1', 'rCarpal2', 'rCarpal3', 'rCarpal4',
    ],

    'SPINE': [
        'pelvis', 'hip',
        'abdomen', 'abdomenUpper', 'abdomenLower', 'abdomen2',
        'chest', 'chestUpper', 'chestLower',
        'neck', 'neckLower', 'neckUpper',
    ],

    'FACE': [
        # Genesis 8 face rig bones
        # This varies by whether the full face rig is present
        'upperFaceRig', 'lowerFaceRig',
        'jaw',
        'lEye', 'rEye',
        'tongue01', 'tongue02', 'tongue03', 'tongue04',
        # Brow
        'CenterBrow',
        'lBrowInner', 'lBrowMid', 'lBrowOuter',
        'rBrowInner', 'rBrowMid', 'rBrowOuter',
        # Eyelids
        'lEyelidUpper', 'lEyelidLower',
        'rEyelidUpper', 'rEyelidLower',
        # Nose
        'lNostril', 'rNostril',
        # Lips
        'lLipCorner', 'rLipCorner',
        'lLipUpperInner', 'lLipUpperOuter',
        'rLipUpperInner', 'rLipUpperOuter',
        'lLipLowerInner', 'lLipLowerOuter',
        'rLipLowerInner', 'rLipLowerOuter',
        # Cheeks
        'lCheekUpper', 'lCheekLower',
        'rCheekUpper', 'rCheekLower',
    ],
}


def get_bone_group(preset_name):
    """Get list of bones for a preset group name

    Args:
        preset_name: One of 'HEAD', 'UPPER_BODY', 'LOWER_BODY', etc.

    Returns:
        List of bone names, or empty list if preset not found
    """
    return GENESIS8_BONE_GROUPS.get(preset_name, [])


def get_all_body_bones():
    """Get all body bones (union of all groups except FACE)"""
    all_bones = set()
    for group_name, bones in GENESIS8_BONE_GROUPS.items():
        if group_name != 'FACE':
            all_bones.update(bones)
    return list(all_bones)


# ============================================================================
# Dot Color Presets by Mask Type
# ============================================================================

DOT_COLORS = {
    'ALL': (1.0, 1.0, 1.0, 1.0),        # White
    'HEAD': (1.0, 0.9, 0.2, 1.0),        # Yellow
    'UPPER_BODY': (0.2, 0.8, 1.0, 1.0),  # Cyan
    'LOWER_BODY': (0.4, 1.0, 0.4, 1.0),  # Green
    'ARMS': (0.4, 0.6, 1.0, 1.0),        # Blue
    'ARM_L': (0.4, 0.6, 1.0, 1.0),       # Blue
    'ARM_R': (0.4, 0.6, 1.0, 1.0),       # Blue
    'LEGS': (0.6, 1.0, 0.6, 1.0),        # Light green
    'LEG_L': (0.6, 1.0, 0.6, 1.0),       # Light green
    'LEG_R': (0.6, 1.0, 0.6, 1.0),       # Light green
    'HANDS': (0.8, 0.5, 1.0, 1.0),       # Purple
    'SPINE': (1.0, 0.6, 0.2, 1.0),       # Orange
    'FACE': (1.0, 0.7, 0.8, 1.0),        # Pink
    'CUSTOM': (1.0, 0.5, 0.0, 1.0),      # Orange
}


def get_dot_color(mask_mode, mask_preset=None):
    """Get appropriate color for a dot based on its mask

    Args:
        mask_mode: 'ALL', 'PRESET', or 'CUSTOM'
        mask_preset: If mode is PRESET, the preset name

    Returns:
        (r, g, b, a) color tuple
    """
    if mask_mode == 'ALL':
        return DOT_COLORS['ALL']
    elif mask_mode == 'CUSTOM':
        return DOT_COLORS['CUSTOM']
    elif mask_mode == 'PRESET' and mask_preset:
        return DOT_COLORS.get(mask_preset, DOT_COLORS['ALL'])
    return DOT_COLORS['ALL']


# ============================================================================
# Default Grid Templates
# ============================================================================

GRID_TEMPLATES = {
    'body_poses': {
        'name': 'Body Poses',
        'grid_divisions': (8, 8),
        'default_mask_mode': 'ALL',
        'description': 'Full body pose blending',
    },
    'expressions': {
        'name': 'Expressions',
        'grid_divisions': (6, 6),
        'default_mask_mode': 'PRESET',
        'default_mask_preset': 'FACE',
        'description': 'Facial expression blending',
    },
    'hand_poses': {
        'name': 'Hand Poses',
        'grid_divisions': (4, 4),
        'default_mask_mode': 'PRESET',
        'default_mask_preset': 'HANDS',
        'description': 'Hand gesture blending',
    },
    'upper_body': {
        'name': 'Upper Body',
        'grid_divisions': (6, 6),
        'default_mask_mode': 'PRESET',
        'default_mask_preset': 'UPPER_BODY',
        'description': 'Upper body pose blending',
    },
}


def get_grid_template(template_name):
    """Get grid template configuration

    Args:
        template_name: Template key from GRID_TEMPLATES

    Returns:
        Dict with template configuration, or None
    """
    return GRID_TEMPLATES.get(template_name)


# ============================================================================
# Registration (nothing to register for presets)
# ============================================================================

def register():
    pass


def unregister():
    pass
