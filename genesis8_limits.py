"""
Genesis 8 Rotation Limits Reference

Definitive reference for LIMIT_ROTATION constraints on Genesis 8 characters.
Used to fix missing constraints from Diffeomorphic import.

Based on DAZ Studio's default rotation limits for Genesis 8.
All angles in degrees.
"""

# Format: 'bone_name': {'x': (min, max), 'y': (min, max), 'z': (min, max)}
# None means no limit on that axis

GENESIS8_ROTATION_LIMITS = {
    # ===== HEAD & NECK =====
    'head': {
        'x': (-30, 25),   # Pitch: forward/back tilt
        'y': (-22, 22),   # Yaw: left/right rotation
        'z': (-20, 20),   # Roll: ear to shoulder
    },
    'neckUpper': {
        'x': (-27, 12),
        'y': (-22, 22),
        'z': (-10, 10),
    },
    'neckLower': {
        'x': (-25, 40),
        'y': (-22, 22),
        'z': (-40, 40),
    },

    # ===== SPINE & TORSO =====
    'chest': {
        'x': (-18, 18),
        'y': (-30, 30),
        'z': (-22, 22),
    },
    'chestLower': {
        'x': (-18, 18),
        'y': (-15, 15),
        'z': (-15, 15),
    },
    'chestUpper': {
        'x': (-18, 18),
        'y': (-15, 15),
        'z': (-15, 15),
    },
    'abdomenUpper': {
        'x': (-18, 18),
        'y': (-15, 15),
        'z': (-15, 15),
    },
    'abdomenLower': {
        'x': (-18, 18),
        'y': (-15, 15),
        'z': (-15, 15),
    },
    'abdomen2': {  # Alias
        'x': (-18, 18),
        'y': (-15, 15),
        'z': (-15, 15),
    },

    # ===== PELVIS =====
    'pelvis': {
        'x': (-20, 20),
        'y': (-15, 15),
        'z': (-15, 15),
    },
    'hip': {
        'x': None,
        'y': None,
        'z': None,
    },

    # ===== ARMS - LEFT =====
    'lCollar': {
        'x': (-30, 30),
        'y': (-30, 30),
        'z': (-10, 80),
    },
    'lShldr': {
        'x': (-95, 95),
        'y': (-60, 100),
        'z': (-70, 95),
    },
    'lShldrBend': {  # Shoulder Bend (if present)
        'x': (-40, 40),
        'y': (-30, 30),
        'z': (-30, 30),
    },
    'lShldrTwist': {  # Shoulder Twist
        'x': None,  # Twist bones typically don't have limits
        'y': None,
        'z': None,
    },
    'lForeArm': {
        'x': (-5, 130),
        'y': (-30, 30),
        'z': (-80, 80),
    },
    'lForearmBend': {
        'x': (-5, 130),
        'y': (-15, 15),
        'z': (-40, 40),
    },
    'lForearmTwist': {  # Forearm Twist
        'x': None,
        'y': None,
        'z': None,
    },
    'lHand': {
        'x': (-75, 50),
        'y': (-30, 30),
        'z': (-50, 50),
    },

    # ===== ARMS - RIGHT (mirror of left) =====
    'rCollar': {
        'x': (-30, 30),
        'y': (-30, 30),
        'z': (-80, 10),  # Mirrored Z
    },
    'rShldr': {
        'x': (-95, 95),
        'y': (-100, 60),  # Mirrored Y
        'z': (-95, 70),   # Mirrored Z
    },
    'rShldrBend': {
        'x': (-40, 40),
        'y': (-30, 30),
        'z': (-30, 30),
    },
    'rShldrTwist': {
        'x': None,
        'y': None,
        'z': None,
    },
    'rForeArm': {
        'x': (-5, 130),
        'y': (-30, 30),
        'z': (-80, 80),
    },
    'rForearmBend': {
        'x': (-5, 130),
        'y': (-15, 15),
        'z': (-40, 40),
    },
    'rForearmTwist': {
        'x': None,
        'y': None,
        'z': None,
    },
    'rHand': {
        'x': (-75, 50),
        'y': (-30, 30),
        'z': (-50, 50),
    },

    # ===== LEGS - LEFT =====
    'lThigh': {
        'x': (-120, 45),
        'y': (-40, 70),
        'z': (-40, 40),
    },
    'lThighBend': {
        'x': (-100, 30),
        'y': (-30, 50),
        'z': (-30, 30),
    },
    'lThighTwist': {
        'x': None,
        'y': None,
        'z': None,
    },
    'lShin': {
        'x': (-3, 155),
        'y': (-25, 25),
        'z': (-25, 25),
    },
    'lFoot': {
        'x': (-30, 30),
        'y': (-30, 30),
        'z': (-30, 30),
    },
    'lMetatarsals': {
        'x': (-15, 60),
        'y': (-15, 15),
        'z': (-15, 15),
    },
    'lToe': {
        'x': (-30, 60),
        'y': (-15, 15),
        'z': (-15, 15),
    },

    # ===== LEGS - RIGHT (mirror of left) =====
    'rThigh': {
        'x': (-120, 45),
        'y': (-70, 40),  # Mirrored Y
        'z': (-40, 40),
    },
    'rThighBend': {
        'x': (-100, 30),
        'y': (-50, 30),  # Mirrored Y
        'z': (-30, 30),
    },
    'rThighTwist': {
        'x': None,
        'y': None,
        'z': None,
    },
    'rShin': {
        'x': (-3, 155),
        'y': (-25, 25),
        'z': (-25, 25),
    },
    'rFoot': {
        'x': (-30, 30),
        'y': (-30, 30),
        'z': (-30, 30),
    },
    'rMetatarsals': {
        'x': (-15, 60),
        'y': (-15, 15),
        'z': (-15, 15),
    },
    'rToe': {
        'x': (-30, 60),
        'y': (-15, 15),
        'z': (-15, 15),
    },
}


def apply_rotation_limits(armature, bone_name, force=False):
    """
    Apply Genesis 8 rotation limits to a bone.

    Args:
        armature: Armature object
        bone_name: Name of the bone to apply limits to
        force: If True, replaces existing LIMIT_ROTATION constraints

    Returns:
        True if limits were applied, False otherwise
    """
    import bpy

    if bone_name not in armature.pose.bones:
        return False

    pose_bone = armature.pose.bones[bone_name]

    # Check if bone has limits in our reference
    if bone_name not in GENESIS8_ROTATION_LIMITS:
        return False

    limits = GENESIS8_ROTATION_LIMITS[bone_name]

    # Check if LIMIT_ROTATION already exists
    existing_constraint = None
    for constraint in pose_bone.constraints:
        if constraint.type == 'LIMIT_ROTATION':
            if not force:
                print(f"  {bone_name}: LIMIT_ROTATION already exists")
                return False
            existing_constraint = constraint
            break

    # Remove existing if forcing update
    if existing_constraint and force:
        pose_bone.constraints.remove(existing_constraint)

    # Create new LIMIT_ROTATION constraint
    limit_rot = pose_bone.constraints.new('LIMIT_ROTATION')
    limit_rot.name = "Limit Rotation"
    limit_rot.owner_space = 'LOCAL'

    # Apply X limits
    if limits['x'] is not None:
        limit_rot.use_limit_x = True
        limit_rot.min_x = radians(limits['x'][0])
        limit_rot.max_x = radians(limits['x'][1])

    # Apply Y limits
    if limits['y'] is not None:
        limit_rot.use_limit_y = True
        limit_rot.min_y = radians(limits['y'][0])
        limit_rot.max_y = radians(limits['y'][1])

    # Apply Z limits
    if limits['z'] is not None:
        limit_rot.use_limit_z = True
        limit_rot.min_z = radians(limits['z'][0])
        limit_rot.max_z = radians(limits['z'][1])

    print(f"  ✓ {bone_name}: Applied rotation limits")
    return True


def apply_all_genesis8_limits(armature, force=False):
    """
    Apply rotation limits to all Genesis 8 bones in armature.

    Args:
        armature: Armature object
        force: If True, replaces existing LIMIT_ROTATION constraints

    Returns:
        (applied_count, skipped_count, missing_count)
    """
    applied = 0
    skipped = 0
    missing = 0

    print(f"\n=== Applying Genesis 8 Rotation Limits ===")
    print(f"Armature: {armature.name}")
    print(f"Force update: {force}")

    for bone_name in GENESIS8_ROTATION_LIMITS.keys():
        if bone_name not in armature.pose.bones:
            missing += 1
            continue

        if apply_rotation_limits(armature, bone_name, force=force):
            applied += 1
        else:
            skipped += 1

    print(f"\n=== Summary ===")
    print(f"  Applied: {applied}")
    print(f"  Skipped: {skipped} (already had constraints)")
    print(f"  Missing: {missing} (bones not in armature)")

    return (applied, skipped, missing)


def radians(degrees):
    """Convert degrees to radians"""
    import math
    return math.radians(degrees)
