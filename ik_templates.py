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
IK Rig Templates for DAZ Genesis 8/9 Characters

Pre-defined optimal IK setups for each bone type, providing consistent
and predictable behavior across all Genesis 8 DAZ rigs.

Extracted from daz_bone_select.py for maintainability.
"""

from mathutils import Vector

import logging
log = logging.getLogger(__name__)



# ============================================================================
# IK RIG TEMPLATES - Pre-defined optimal IK setups for each bone type
# ============================================================================
# Instead of calculating everything dynamically, we use tested templates
# for consistent, predictable behavior across all Genesis 8 DAZ rigs

IK_RIG_TEMPLATES = {
    'hand': {
        'description': 'Arm IK chain for hand dragging (shoulder + forearm + hand)',
        'chain_length': 3,  # shoulder → forearm → hand (exclude collar for stability)
        'stiffness': {
            'shldr': 0.3,       # Some resistance to prevent wild swinging
            'shoulder': 0.3,    # Alias for shldr
            'forearm': 0.0,     # Bends freely (main bend point)
            'lorearm': 0.0,     # Alias for forearm
            'hand': 0.0         # End effector, no resistance
        },
        'pole_target': {
            'enabled': False,  # Disabled - DAZ twist bones don't work with pole targets
            'reference_bone': 'forearm',
            'method': 'perpendicular_to_line',
            'distance_multiplier': 2.0
        },
        'constraints': {},  # No collar in chain, no damped track needed
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
            'enabled': False,  # Disabled - DAZ twist bones don't work with pole targets
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
            'enabled': False,  # Disabled - DAZ twist bones don't work with pole targets
            'reference_bone': 'shin',
            'method': 'perpendicular_to_line',
            'distance_multiplier': 2.0
        },
        'constraints': {},
        'prebend': {
            'bone_pattern': 'shin',
            'axis': (1, 0, 0),       # X-axis (forward bend)
            'angle': 0.8             # 0.8 radians (~46°) - stronger hint for IK solver
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
            'enabled': False,  # Disabled - DAZ twist bones don't work with pole targets
            'reference_bone': 'shin',
            'method': 'perpendicular_to_line',
            'distance_multiplier': 2.0
        },
        'constraints': {},
        'prebend': {
            'bone_pattern': 'shin',
            'axis': (1, 0, 0),
            'angle': 0.8             # 0.8 radians (~46°) - stronger hint for IK solver
        }
    },

    'head': {
        'description': 'Head IK chain with diminishing torso influence',
        'chain_length': 3,  # head → neck → chest (exclude lower spine/abdomen for stability)
        'stiffness': {
            'head': 0.0,        # End effector, no resistance (1)
            'neckupper': 0.3,   # Upper neck - more mobile, bends more (closer to head)
            'necklower': 0.6,   # Lower neck - more stable, bends less (closer to shoulders)
            'neck': 0.5,        # Fallback for any other neck bones
            'chest': 0.75,      # Strong resistance (2) - Fibonacci adjusted
            'abdomen': 0.90,    # Very strong resistance (3) - Fibonacci adjusted
            'pelvis': 0.98,     # Nearly locked (5) - Fibonacci adjusted
            'spine': 0.90       # Alias for abdomen
        },
        'pole_target': {
            'enabled': False
        },
        'constraints': {},
        'prebend': None,
        'target_offset': 0.25  # Position target tail 25cm above head - tracks tail (tip) for smooth behavior
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
    elif 'head' in bone_lower:
        return IK_RIG_TEMPLATES.get('head')

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
        log.warning(f"  ⚠️  Pole reference bone not found: {reference_pattern}")
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
            log.warning(f"  ⚠️  Chain start not found for pole calculation")
            return None

        # Detect if this is a leg or arm chain
        is_leg = any('shin' in b.name.lower() or 'thigh' in b.name.lower() or 'calf' in b.name.lower()
                    for b in daz_bones)

        # Use CONSISTENT WORLD-SPACE offset from TARGET position (not elbow/knee)
        # This prevents twist accumulation across multiple drags
        # Pole is positioned relative to the foot/hand target, matching dynamic update logic
        pole_distance = 0.3  # 30cm offset

        if is_leg:
            # Legs: pole forward (-Y) from foot position
            pole_offset = Vector((0, -pole_distance, 0))
        else:
            # Arms: pole behind and down from hand position
            pole_offset = Vector((0, pole_distance * 0.8, -pole_distance * 0.6))

        # Position relative to TARGET (clicked_bone_world_tail), not elbow/knee
        # This matches the dynamic pole update logic for consistency
        pole_world_head = clicked_bone_world_tail + pole_offset
        pole_world_tail = pole_world_head + pole_offset.normalized() * 0.05  # 5cm for visibility

        log.debug(f"  ✓ Calculated pole position: {pole_world_head} (method: target_relative, dist: {pole_distance:.3f}m)")
        return (pole_world_head, pole_world_tail)

    return None
