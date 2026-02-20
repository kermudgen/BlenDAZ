"""DAZ Shared Utilities - Common functions for DAZ Bone Select and PoseBridge

Shared rotation and bone utilities used by multiple BlenDAZ tools.
"""

from mathutils import Vector, Quaternion

# ============================================================================
# Bone Axis Determination
# ============================================================================

def get_bend_axis(bone):
    """
    Determine the primary bending axis for a bone.
    Returns: 'X', 'Y', or 'Z'
    """
    bone_lower = bone.name.lower()

    # Arms typically bend around X axis
    if any(part in bone_lower for part in ['arm', 'shoulder', 'shldr', 'collar', 'elbow']):
        return 'X'

    # Legs typically bend around X axis
    if any(part in bone_lower for part in ['leg', 'thigh', 'shin', 'knee', 'foot']):
        return 'X'

    # Neck/head bend around Y axis (nod)
    if 'neck' in bone_lower or 'head' in bone_lower:
        return 'Y'

    # Fingers bend around X axis
    if any(part in bone_lower for part in ['thumb', 'index', 'mid', 'ring', 'pinky']):
        return 'X'

    # Default to Z axis
    return 'Z'


def get_twist_axis(bone):
    """
    Determine the twisting axis for a bone (rotation around bone length).
    Twist is typically around the bone's local Y axis.
    Returns: 'X', 'Y', or 'Z'
    """
    # Twist is typically around the bone's length axis (Y in Blender)
    return 'Y'


# ============================================================================
# Rotation Application
# ============================================================================

def enforce_rotation_limits(bone):
    """
    Enforce rotation limits on a bone using LIMIT_ROTATION constraints or IK limits.
    If no limits exist, apply sensible anatomical defaults for common bones.
    Converts quaternion to euler, clamps to limits, converts back.

    Args:
        bone: Pose bone with rotation to limit
    """
    import math

    # Check for LIMIT_ROTATION constraints (used by Diffeomorphic DAZ import)
    limit_constraint = None
    for constraint in bone.constraints:
        if constraint.type == 'LIMIT_ROTATION' and not constraint.mute:
            limit_constraint = constraint
            break

    # Check if bone has any IK limits enabled (fallback)
    has_ik_limits = (
        (hasattr(bone, 'use_ik_limit_x') and bone.use_ik_limit_x) or
        (hasattr(bone, 'use_ik_limit_y') and bone.use_ik_limit_y) or
        (hasattr(bone, 'use_ik_limit_z') and bone.use_ik_limit_z)
    )

    # If bone has LIMIT_ROTATION constraint, use those limits
    if limit_constraint:
        # Convert quaternion rotation to euler
        euler = bone.rotation_quaternion.to_euler('XYZ')

        # Apply constraint limits
        if limit_constraint.use_limit_x:
            euler.x = max(limit_constraint.min_x, min(limit_constraint.max_x, euler.x))

        if limit_constraint.use_limit_y:
            euler.y = max(limit_constraint.min_y, min(limit_constraint.max_y, euler.y))

        if limit_constraint.use_limit_z:
            euler.z = max(limit_constraint.min_z, min(limit_constraint.max_z, euler.z))

        # Convert back to quaternion
        bone.rotation_quaternion = euler.to_quaternion()
        return  # Done - constraint limits applied

    # Define default anatomical limits (in radians) for bones without any limits
    bone_lower = bone.name.lower()
    default_limits = None

    if not has_ik_limits:
        # Head: moderate rotation on all axes
        if 'head' in bone_lower:
            default_limits = {
                'x': (-math.radians(40), math.radians(40)),  # Nod up/down
                'y': (-math.radians(70), math.radians(70)),  # Turn left/right
                'z': (-math.radians(45), math.radians(45))   # Tilt left/right
            }
        # Hand/wrist: more rotation on Y (twist), limited on X/Z
        elif 'hand' in bone_lower or 'wrist' in bone_lower:
            default_limits = {
                'x': (-math.radians(70), math.radians(70)),  # Flex/extend
                'y': (-math.radians(20), math.radians(20)),  # Twist
                'z': (-math.radians(30), math.radians(30))   # Side bend
            }
        # Knee: only bends forward (negative X), no backward bend
        elif 'shin' in bone_lower or 'knee' in bone_lower:
            default_limits = {
                'x': (-math.radians(150), math.radians(5)),  # Bend forward only
                'y': (-math.radians(5), math.radians(5)),
                'z': (-math.radians(5), math.radians(5))
            }

    # If no limits at all, return (let bone move freely)
    if not has_ik_limits and not default_limits:
        return

    # Convert quaternion rotation to euler
    euler = bone.rotation_quaternion.to_euler('XYZ')

    # Apply IK limits if they exist
    if has_ik_limits:
        if hasattr(bone, 'use_ik_limit_x') and bone.use_ik_limit_x:
            euler.x = max(bone.ik_min_x, min(bone.ik_max_x, euler.x))

        if hasattr(bone, 'use_ik_limit_y') and bone.use_ik_limit_y:
            euler.y = max(bone.ik_min_y, min(bone.ik_max_y, euler.y))

        if hasattr(bone, 'use_ik_limit_z') and bone.use_ik_limit_z:
            euler.z = max(bone.ik_min_z, min(bone.ik_max_z, euler.z))
    # Otherwise apply default limits
    elif default_limits:
        euler.x = max(default_limits['x'][0], min(default_limits['x'][1], euler.x))
        euler.y = max(default_limits['y'][0], min(default_limits['y'][1], euler.y))
        euler.z = max(default_limits['z'][0], min(default_limits['z'][1], euler.z))

    # Convert back to quaternion
    bone.rotation_quaternion = euler.to_quaternion()


def decompose_swing_twist(quaternion, twist_axis='Y'):
    """
    Decompose a quaternion into swing and twist components.

    This separates a rotation into:
    - Swing: rotation around axes perpendicular to the twist axis (e.g., X and Z if twist_axis='Y')
    - Twist: rotation around the twist axis only

    Used for anatomically correct limb rotation where the "bend" bone should only
    rotate on swing axes, and twist rotation should go to a dedicated twist bone.

    Args:
        quaternion: The quaternion to decompose
        twist_axis: The axis to extract twist around ('X', 'Y', or 'Z')

    Returns:
        tuple: (swing_quaternion, twist_quaternion)

    Mathematical basis:
        q = swing * twist
        twist is the projection of q onto the twist axis
        swing = q * twist.inverted()
    """
    # Extract the twist component by zeroing out the non-twist axis components
    # For twist around Y: keep w and y, zero x and z
    w, x, y, z = quaternion.w, quaternion.x, quaternion.y, quaternion.z

    if twist_axis == 'Y':
        # Project onto Y axis: keep w and y components
        twist = Quaternion((w, 0, y, 0))
    elif twist_axis == 'X':
        # Project onto X axis: keep w and x components
        twist = Quaternion((w, x, 0, 0))
    elif twist_axis == 'Z':
        # Project onto Z axis: keep w and z components
        twist = Quaternion((w, 0, 0, z))
    else:
        # Default to identity (no twist)
        return quaternion.copy(), Quaternion()

    # Normalize the twist quaternion (projection may not be unit length)
    # Handle edge case where twist is zero (no twist component)
    twist_length = (twist.w * twist.w + twist.x * twist.x +
                   twist.y * twist.y + twist.z * twist.z) ** 0.5

    if twist_length < 0.0001:
        # No twist component - return original as swing, identity as twist
        return quaternion.copy(), Quaternion()

    twist = Quaternion((twist.w / twist_length, twist.x / twist_length,
                       twist.y / twist_length, twist.z / twist_length))

    # Swing is the remainder: swing = q * twist.inverted()
    swing = quaternion @ twist.inverted()

    return swing, twist


def apply_rotation_from_delta(bone, initial_rotation, axis, delta, sensitivity=0.01):
    """
    Apply rotation to bone based on mouse delta.

    Args:
        bone: Pose bone to rotate
        initial_rotation: Starting rotation (quaternion)
        axis: Rotation axis ('X', 'Y', or 'Z')
        delta: Mouse movement in pixels (caller decides which: delta_x or delta_y)
        sensitivity: Rotation multiplier (radians per pixel)
    """
    # Calculate angle directly from delta
    angle = delta * sensitivity

    # Create rotation quaternion
    axis_vector = Vector((
        1 if axis == 'X' else 0,
        1 if axis == 'Y' else 0,
        1 if axis == 'Z' else 0
    ))
    rotation_quat = Quaternion(axis_vector, angle)

    # Apply rotation (combine with initial rotation)
    bone.rotation_quaternion = rotation_quat @ initial_rotation


def refresh_3d_viewports(context):
    """Trigger viewport redraws to show rotation changes immediately"""
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


# ============================================================================
# Genesis 8 Control Points
# ============================================================================

def get_genesis8_control_points():
    """
    Get control point definitions for Genesis 8 figure with PowerPose-style control mappings.
    Returns list of control point dictionaries.

    Each control point includes 4-way mouse control mappings:
    - lmb_horiz: Left mouse button + horizontal (left/right) drag
    - lmb_vert: Left mouse button + vertical (up/down) drag
    - rmb_horiz: Right mouse button + horizontal drag
    - rmb_vert: Right mouse button + vertical drag

    Each mapping is either None (disabled) or a tuple: (axis, inverted)
    - axis: 'X', 'Y', or 'Z'
    - inverted: bool, True to negate the mouse delta for this direction

    Mirrors DAZ PowerPose DSX template format (lmb_horiz_prop, rmb_horiz_sign, etc.)

    NOTE: For single-bone controls, inversions are handled by the if/elif chain in
    daz_bone_select.py update_rotation() (which also handles twist routing, armature space,
    right-side mirroring). The inversions here are for documentation only on single-bone controls.
    For group controls, the dict IS the runtime source of truth (data-driven).
    """
    control_points = [
        # ===== HEAD & NECK =====
        {
            'id': 'head',
            'bone_name': 'head',
            'label': 'Head',
            'group': 'head',
            'offset': (0, 0, 0.075),
            'controls': {
                'lmb_horiz': ('Y', False),  # Turn head left/right
                'lmb_vert': ('X', True),    # Nod up/down (inverted)
                'rmb_horiz': ('Z', True),   # Side tilt (inverted)
                'rmb_vert': ('X', True)     # Fine forward/back (inverted)
            }
        },

        # Neck group (multi-bone control) - DATA-DRIVEN at runtime
        {
            'id': 'neck_group',
            'bone_names': ['head', 'neckUpper', 'neckLower'],
            'label': 'Neck Group',
            'group': 'head',
            'shape': 'diamond',
            'reference_bone': 'neckUpper',
            'offset': (-0.075, 0, 0),
            'controls': {
                'lmb_horiz': ('Y', False),   # Turn all
                'lmb_vert': ('X', False),    # Nod all
                'rmb_horiz': ('Z', True),    # Side tilt all (inverted)
                'rmb_vert': ('X', False)     # Fine forward/back
            }
        },

        {
            'id': 'neckUpper',
            'bone_name': 'neckUpper',
            'label': 'Neck Upper',
            'group': 'head',
            'controls': {
                'lmb_horiz': ('Y', False),  # Rotate neck
                'lmb_vert': ('X', True),    # Bend neck forward/back (inverted)
                'rmb_horiz': ('Z', True),   # Side bend (inverted)
                'rmb_vert': ('X', True)     # Fine forward/back (inverted)
            }
        },
        {
            'id': 'neckLower',
            'bone_name': 'neckLower',
            'label': 'Neck Lower',
            'group': 'head',
            'controls': {
                'lmb_horiz': ('Y', False),  # Rotate neck
                'lmb_vert': ('X', True),    # Bend forward/back (inverted)
                'rmb_horiz': ('Z', True),   # Side bend (inverted)
                'rmb_vert': ('X', True)     # Fine forward/back (inverted)
            }
        },

        # ===== TORSO =====
        {
            'id': 'chestUpper',
            'bone_name': 'chestUpper',
            'label': 'Upper Chest',
            'group': 'torso',
            'controls': {
                'lmb_horiz': ('Y', False),  # Twist torso
                'lmb_vert': ('X', False),   # Bend forward/back
                'rmb_horiz': ('Z', True),   # Side lean (inverted)
                'rmb_vert': ('Y', False)    # Twist (alternative)
            }
        },
        {
            'id': 'chestLower',
            'bone_name': 'chestLower',
            'label': 'Lower Chest',
            'group': 'torso',
            'controls': {
                'lmb_horiz': ('Y', False),  # Twist
                'lmb_vert': ('X', False),   # Bend forward/back
                'rmb_horiz': ('Z', True),   # Side lean (inverted)
                'rmb_vert': ('Y', False)    # Twist (alternative)
            }
        },
        {
            'id': 'abdomenUpper',
            'bone_name': 'abdomenUpper',
            'label': 'Upper Abdomen',
            'group': 'torso',
            'controls': {
                'lmb_horiz': ('Y', False),  # Twist abdomen
                'lmb_vert': ('X', False),   # Bend forward/back
                'rmb_horiz': ('Z', True),   # Side lean (inverted)
                'rmb_vert': ('Y', False)    # Fine twist
            }
        },
        {
            'id': 'abdomenLower',
            'bone_name': 'abdomenLower',
            'label': 'Lower Abdomen',
            'group': 'torso',
            'controls': {
                'lmb_horiz': ('Y', False),  # Twist
                'lmb_vert': ('X', False),   # Bend forward/back
                'rmb_horiz': ('Z', True),   # Side lean (inverted)
                'rmb_vert': ('Y', False)    # Fine twist
            }
        },
        {
            'id': 'pelvis',
            'bone_name': 'pelvis',
            'label': 'Pelvis',
            'group': 'torso',
            'position': 'tail',
            'controls': {
                'lmb_horiz': ('Y', False),  # Twist hips
                'lmb_vert': ('X', False),   # Pelvic tilt forward/back
                'rmb_horiz': ('Z', True),   # Side lean (inverted)
                'rmb_vert': ('Y', False)    # Alt twist
            }
        },

        # ===== LEFT ARM =====
        {
            'id': 'lCollar',
            'bone_name': 'lCollar',
            'label': 'Left Collar',
            'group': 'arms',
            'position': 'mid',
            'controls': {
                'lmb_horiz': ('Z', False),  # Shrug/drop shoulder
                'lmb_vert': ('X', False),   # Shoulder forward/back
                'rmb_horiz': None,           # Removed per user testing
                'rmb_vert': ('Y', False)     # Twist/roll
            }
        },
        {
            'id': 'lShldrBend',
            'bone_name': 'lShldrBend',
            'label': 'Left Upper Arm',
            'group': 'arms',
            'position': 'mid',
            'controls': {
                'lmb_horiz': ('X', True),   # Arm swing forward/back (inverted)
                'lmb_vert': ('Z', False),   # Raise/lower arm
                'rmb_horiz': None,           # No horizontal control
                'rmb_vert': ('Y', True)      # Arm twist (inverted, targets lShldrTwist)
            }
        },
        {
            'id': 'lForearmBend',
            'bone_name': 'lForearmBend',
            'label': 'Left Forearm',
            'group': 'arms',
            'controls': {
                'lmb_horiz': ('X', True),    # Bend elbow (inverted)
                'lmb_vert': ('Y', True),     # Twist (inverted, targets lForearmTwist)
                'rmb_horiz': ('Y', False),   # Forearm twist
                'rmb_vert': None
            }
        },
        {
            'id': 'lHand',
            'bone_name': 'lHand',
            'label': 'Left Hand',
            'group': 'arms',
            'controls': {
                'lmb_horiz': ('Y', True),   # Twist (inverted)
                'lmb_vert': ('Z', False),   # Bend up/down
                'rmb_horiz': ('X', True),   # Side-to-side (inverted)
                'rmb_vert': ('Z', False)    # Bend up/down
            }
        },

        # ===== RIGHT ARM =====
        {
            'id': 'rCollar',
            'bone_name': 'rCollar',
            'label': 'Right Collar',
            'group': 'arms',
            'position': 'mid',
            'controls': {
                'lmb_horiz': ('Z', False),  # Shrug/drop shoulder
                'lmb_vert': ('X', False),   # Shoulder forward/back
                'rmb_horiz': None,           # Removed per user testing
                'rmb_vert': ('Y', False)     # Twist/roll
            }
        },
        {
            'id': 'rShldrBend',
            'bone_name': 'rShldrBend',
            'label': 'Right Upper Arm',
            'group': 'arms',
            'position': 'mid',
            'controls': {
                'lmb_horiz': ('X', True),   # Arm swing forward/back (inverted)
                'lmb_vert': ('Z', False),   # Raise/lower arm
                'rmb_horiz': None,           # No horizontal control
                'rmb_vert': ('Y', True)      # Arm twist (inverted, targets rShldrTwist)
            }
        },
        {
            'id': 'rForearmBend',
            'bone_name': 'rForearmBend',
            'label': 'Right Forearm',
            'group': 'arms',
            'controls': {
                'lmb_horiz': ('X', True),    # Bend elbow (inverted)
                'lmb_vert': ('Y', True),     # Twist (inverted, targets rForearmTwist)
                'rmb_horiz': ('Y', False),   # Forearm twist
                'rmb_vert': None
            }
        },
        {
            'id': 'rHand',
            'bone_name': 'rHand',
            'label': 'Right Hand',
            'group': 'arms',
            'controls': {
                'lmb_horiz': ('Y', True),   # Twist (inverted)
                'lmb_vert': ('Z', False),   # Bend up/down
                'rmb_horiz': ('X', True),   # Side-to-side (inverted)
                'rmb_vert': ('Z', False)    # Bend up/down
            }
        },

        # ===== LEFT LEG =====
        {
            'id': 'lThigh',
            'bone_names': ['lThighBend', 'lThighTwist'],
            'label': 'Left Thigh',
            'group': 'legs',
            'position': 'tail',
            'controls': {
                'lmb_horiz': ('Y', True),   # Twist (inverted, targets ThighTwist via filtering)
                'lmb_vert': ('X', True),    # Forward/back swing (inverted)
                'rmb_horiz': ('Z', True),   # Spread (inverted) -- matches PowerPose zrot neg
                'rmb_vert': ('X', True)     # Forward/back (inverted)
            }
        },
        {
            'id': 'lShin',
            'bone_name': 'lShin',
            'label': 'Left Shin',
            'group': 'legs',
            'controls': {
                'lmb_horiz': None,           # Limited
                'lmb_vert': ('X', False),    # Bend knee (main function)
                'rmb_horiz': ('Y', False),   # Shin twist
                'rmb_vert': None
            }
        },
        {
            'id': 'lFoot',
            'bone_name': 'lFoot',
            'label': 'Left Foot',
            'group': 'legs',
            'controls': {
                'lmb_horiz': ('Z', False),  # Foot tilt side-to-side
                'lmb_vert': ('X', False),   # Foot point/flex
                'rmb_horiz': ('Y', False),  # Foot twist
                'rmb_vert': None
            }
        },

        # ===== RIGHT LEG =====
        {
            'id': 'rThigh',
            'bone_names': ['rThighBend', 'rThighTwist'],
            'label': 'Right Thigh',
            'group': 'legs',
            'position': 'tail',
            'controls': {
                'lmb_horiz': ('Y', True),   # Twist (inverted, targets ThighTwist via filtering)
                'lmb_vert': ('X', True),    # Forward/back swing (inverted)
                'rmb_horiz': ('Z', True),   # Spread (inverted)
                'rmb_vert': ('X', True)     # Forward/back (inverted)
            }
        },
        {
            'id': 'rShin',
            'bone_name': 'rShin',
            'label': 'Right Shin',
            'group': 'legs',
            'controls': {
                'lmb_horiz': None,
                'lmb_vert': ('X', False),
                'rmb_horiz': ('Y', False),
                'rmb_vert': None
            }
        },
        {
            'id': 'rFoot',
            'bone_name': 'rFoot',
            'label': 'Right Foot',
            'group': 'legs',
            'controls': {
                'lmb_horiz': ('Z', False),
                'lmb_vert': ('X', False),
                'rmb_horiz': ('Y', False),
                'rmb_vert': None
            }
        },

        # ===== GROUP NODES (Diamond-shaped hierarchical controls) =====
        # Group controls are DATA-DRIVEN at runtime - these dicts are the source of truth.
        # Inversions here are used directly by update_multi_bone_rotation().
        {
            'id': 'lArm_group',
            'bone_names': ['lShldrBend', 'lShldrTwist', 'lForearmBend', 'lForearmTwist'],
            'label': 'Left Arm Group',
            'group': 'arms',
            'shape': 'diamond',
            'reference_bone': 'lShldrTwist',
            'offset': (0.075, 0, 0),
            'controls': {
                'lmb_horiz': ('X', False),  # Swing forward/back
                'lmb_vert': ('Z', False),   # Raise/lower
                'rmb_horiz': ('Y', False),  # Twist
                'rmb_vert': None
            }
        },
        {
            'id': 'rArm_group',
            'bone_names': ['rShldrBend', 'rShldrTwist', 'rForearmBend', 'rForearmTwist'],
            'label': 'Right Arm Group',
            'group': 'arms',
            'shape': 'diamond',
            'reference_bone': 'rShldrTwist',
            'offset': (-0.075, 0, 0),
            'controls': {
                'lmb_horiz': ('X', False),  # Swing forward/back
                'lmb_vert': ('Z', False),   # Raise/lower
                'rmb_horiz': ('Y', False),  # Twist
                'rmb_vert': None
            }
        },
        {
            'id': 'shoulders_group',
            'bone_names': ['lCollar', 'rCollar', 'lShldrBend', 'rShldrBend'],
            'label': 'Shoulders Group',
            'group': 'torso',
            'shape': 'diamond',
            'reference_bone': 'chestUpper',
            'offset': (0, 0, 0.075),
            'controls': {
                'lmb_horiz': ('Z', False),  # Shrug/drop
                'lmb_vert': ('X', False),   # Forward/back
                'rmb_horiz': ('Y', False),  # Roll
                'rmb_vert': None,
                'mirror_axes': ['Z']  # Bilateral: invert Z for right-side bones
            }
        },
        {
            'id': 'torso_group',
            'bone_names': ['abdomenLower', 'abdomenUpper', 'chestLower', 'chestUpper'],
            'label': 'Torso Group',
            'group': 'torso',
            'shape': 'diamond',
            'reference_bone': 'abdomenUpper',
            'offset': (-0.1, 0, 0),
            'controls': {
                'lmb_horiz': ('Y', False),  # Twist
                'lmb_vert': ('X', False),   # Bend forward/back
                'rmb_horiz': ('Z', True),   # Side lean (inverted)
                'rmb_vert': None
            }
        },
        {
            'id': 'lLeg_group',
            'bone_names': ['lThighBend', 'lThighTwist', 'lShin'],
            'label': 'Left Leg Group',
            'group': 'legs',
            'shape': 'diamond',
            'reference_bone': 'lThighTwist',
            'offset': (0.075, 0, 0),
            'controls': {
                'lmb_horiz': ('Y', False),  # Twist (targets twist bones via filtering)
                'lmb_vert': ('X', False),   # Forward/back swing
                'rmb_horiz': ('Z', True),   # Spread (inverted)
                'rmb_vert': ('X', False)    # Forward/back
            }
        },
        {
            'id': 'rLeg_group',
            'bone_names': ['rThighBend', 'rThighTwist', 'rShin'],
            'label': 'Right Leg Group',
            'group': 'legs',
            'shape': 'diamond',
            'reference_bone': 'rThighTwist',
            'offset': (-0.075, 0, 0),
            'controls': {
                'lmb_horiz': ('Y', False),  # Twist (targets twist bones via filtering)
                'lmb_vert': ('X', False),   # Forward/back swing
                'rmb_horiz': ('Z', True),   # Spread (inverted)
                'rmb_vert': ('X', False)    # Forward/back
            }
        },
        {
            'id': 'legs_group',
            'bone_names': ['lThighBend', 'lThighTwist', 'lShin', 'rThighBend', 'rThighTwist', 'rShin'],
            'label': 'Legs Group',
            'group': 'legs',
            'shape': 'diamond',
            'reference_bone': 'pelvis',
            'offset': (0, 0, -0.275),
            'controls': {
                'lmb_horiz': ('Y', False),  # Twist (targets twist bones via filtering)
                'lmb_vert': ('X', False),   # Forward/back swing
                'rmb_horiz': ('Z', True),   # Spread (inverted)
                'rmb_vert': ('X', False),   # Forward/back
                'mirror_axes': ['Z']  # Bilateral: invert Z for right-side bones (spread)
            }
        },

        # ===== TOES =====
        {
            'id': 'lToe',
            'bone_name': 'lToe',
            'label': 'Left Toe',
            'group': 'legs',
            'position': 'tail',
            'controls': {
                'lmb_horiz': ('Z', False),  # Side tilt
                'lmb_vert': ('X', False),   # Curl/extend toes
                'rmb_horiz': ('Y', False),  # Twist
                'rmb_vert': None
            }
        },
        {
            'id': 'rToe',
            'bone_name': 'rToe',
            'label': 'Right Toe',
            'group': 'legs',
            'position': 'tail',
            'controls': {
                'lmb_horiz': ('Z', False),  # Side tilt
                'lmb_vert': ('X', False),   # Curl/extend toes
                'rmb_horiz': ('Y', False),  # Twist
                'rmb_vert': None
            }
        },

        # ===== HIP (Pelvis mid-point) =====
        {
            'id': 'hip',
            'bone_name': 'hip',  # Will try 'hip' first, fallback to 'pelvis'
            'label': 'Hip',
            'group': 'torso',
            'position': 'mid',
            'controls': {
                'lmb_horiz': ('Z', False),  # Rotate hips
                'lmb_vert': ('X', False),   # Tilt forward/back
                'rmb_horiz': ('Y', False),  # Side tilt
                'rmb_vert': None
            }
        },

        # ===== BASE (Special - moves entire armature) =====
        {
            'id': 'base',
            'bone_name': 'lFoot',  # Reference bone for positioning
            'label': 'Base',
            'group': 'base',
            'position': 'head',  # Use head of lFoot
            'special': 'armature_move',  # Special handling flag
            'offset': (0.1, 0, 0),  # 0.1 units in X from lFoot
            'controls': {
                'lmb_horiz': None,
                'lmb_vert': None,
                'rmb_horiz': None,
                'rmb_vert': None
            }
        },
    ]

    return control_points


def get_group_controls(group_id):
    """
    Look up the controls dict for a group node by its ID.
    Called once at drag start and cached for the duration of the drag.

    Args:
        group_id: Control point ID (e.g., 'neck_group', 'lLeg_group')

    Returns:
        dict with lmb_horiz, lmb_vert, rmb_horiz, rmb_vert entries.
        Each entry is None or (axis, inverted) tuple.
        Returns empty dict if group_id not found.
    """
    for cp in get_genesis8_control_points():
        if cp['id'] == group_id:
            return cp.get('controls', {})
    return {}


def get_rotation_axis_from_control(bone_name, mouse_button, is_horizontal):
    """
    Fast lookup for rotation axis based on bone, button, and direction.
    Used for single-bone controls only. Returns just the axis letter (no inversion).
    Single-bone inversions are handled by the if/elif chain in daz_bone_select.py.

    For group controls, use get_group_controls() instead.

    Args:
        bone_name: Name of the bone
        mouse_button: 'LEFT' or 'RIGHT'
        is_horizontal: True if horizontal drag, False if vertical

    Returns:
        'X', 'Y', 'Z', or None if no control defined
    """
    bone_lower = bone_name.lower()

    # HEAD
    if 'head' in bone_lower:
        if mouse_button == 'LEFT':
            return 'Z' if is_horizontal else 'X'  # Turn / Nod
        else:  # RIGHT
            return 'Y' if is_horizontal else 'X'  # Tilt / Fine

    # NECK
    if 'neck' in bone_lower:
        if mouse_button == 'LEFT':
            return 'Z' if is_horizontal else 'X'  # Rotate / Bend
        else:  # RIGHT
            return 'Y' if is_horizontal else None  # Side bend

    # TORSO
    if any(part in bone_lower for part in ['chest', 'abdomen', 'pelvis']):
        if mouse_button == 'LEFT':
            return 'Z' if is_horizontal else 'X'  # Twist / Bend
        else:  # RIGHT
            return 'Y'  # Side lean / twist

    # COLLAR
    if 'collar' in bone_lower:
        if mouse_button == 'LEFT':
            return 'Z' if is_horizontal else 'X'  # Shrug / Forward
        else:  # RIGHT
            return 'Y' if is_horizontal else None  # Roll

    # UPPER ARM (Shoulder)
    if 'shldr' in bone_lower or 'shoulder' in bone_lower:
        if mouse_button == 'LEFT':
            return 'X' if is_horizontal else 'Z'  # Swing / Raise
        else:  # RIGHT
            return 'Y' if is_horizontal else None  # Twist

    # FOREARM (Elbow)
    if 'forearm' in bone_lower or 'lorearm' in bone_lower:
        if mouse_button == 'LEFT':
            return 'X' if not is_horizontal else None  # Bend (vertical only)
        else:  # RIGHT
            return 'Y' if is_horizontal else None  # Twist

    # HAND
    if 'hand' in bone_lower:
        if mouse_button == 'LEFT':
            return 'Z' if is_horizontal else 'X'  # Side / Up-down
        else:  # RIGHT
            return 'Y' if is_horizontal else None  # Twist

    # THIGH
    if 'thigh' in bone_lower:
        if mouse_button == 'LEFT':
            return 'X' if is_horizontal else 'Z'  # Swing / Raise
        else:  # RIGHT
            return 'Y'  # Twist / Side

    # SHIN (Knee)
    if 'shin' in bone_lower or 'knee' in bone_lower:
        if mouse_button == 'LEFT':
            return 'X' if not is_horizontal else None  # Bend (vertical only)
        else:  # RIGHT
            return 'Y' if is_horizontal else None  # Twist

    # FOOT
    if 'foot' in bone_lower:
        if mouse_button == 'LEFT':
            return 'Z' if is_horizontal else 'X'  # Tilt / Point
        else:  # RIGHT
            return 'Y' if is_horizontal else None  # Twist

    # Default: no control
    return None


def apply_rotation_from_delta_directional(bone, initial_rotation, mouse_button, delta_x, delta_y, sensitivity=0.01):
    """
    Apply rotation to bone based on mouse delta with directional control (PowerPose-style).
    Uses fast bone name pattern matching instead of iterating through control points.

    Args:
        bone: Pose bone to rotate
        initial_rotation: Starting rotation (quaternion)
        mouse_button: 'LEFT' or 'RIGHT'
        delta_x: Horizontal mouse movement (pixels)
        delta_y: Vertical mouse movement (pixels)
        sensitivity: Rotation multiplier (radians per pixel)
    """
    # Determine if drag is primarily horizontal or vertical
    abs_dx = abs(delta_x)
    abs_dy = abs(delta_y)

    if abs_dx < 1 and abs_dy < 1:
        return  # No movement

    is_horizontal = abs_dx > abs_dy

    # Fast lookup using bone name patterns
    axis = get_rotation_axis_from_control(bone.name, mouse_button, is_horizontal)

    if axis is None:
        # No control defined for this combination - do nothing
        return

    # Apply rotation using the specified axis
    # Pass the delta that matches the drag direction
    delta = delta_x if is_horizontal else delta_y
    apply_rotation_from_delta(bone, initial_rotation, axis, delta, sensitivity)
