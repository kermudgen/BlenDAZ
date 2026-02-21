"""
Bone Utility Functions for DAZ Genesis 8/9 Characters

Helper functions for bone classification, IK target mapping, and chain length
calculation. Used by the IK system to determine how to handle different bone types.

Extracted from daz_bone_select.py for maintainability.
"""


def is_twist_bone(bone_name):
    """
    Check if bone is a twist/roll bone that shouldn't use IK.

    Twist bones cause "noodle limbs" if included in IK chains because they
    rotate around the limb axis rather than bending.

    Args:
        bone_name: Name of the bone to check

    Returns:
        True if this is a twist/roll bone
    """
    bone_lower = bone_name.lower()
    return 'twist' in bone_lower or 'roll' in bone_lower


def is_pectoral(bone_name):
    """
    Check if bone is a pectoral bone that shouldn't be in IK chains.

    Pectoral/breast bones are surface detail bones that shouldn't pull
    the spine or chest when arms move.

    Args:
        bone_name: Name of the bone to check

    Returns:
        True if this is a pectoral/breast bone
    """
    bone_lower = bone_name.lower()
    return 'pectoral' in bone_lower or 'breast' in bone_lower


def get_ik_target_bone(armature, bone_name, silent=False):
    """
    Map small bones to their major parent bone for IK (DAZ-style behavior).

    This function handles:
    - Twist/roll bones → returns None (no IK)
    - Pectoral bones → returns None (no IK)
    - Carpal/metacarpal → maps to hand
    - Metatarsal → maps to foot
    - Face bones → maps to head
    - Toe bones → maps to foot
    - Major bones → returns bone itself

    Args:
        armature: The armature object containing the bones
        bone_name: Name of the clicked/hovered bone
        silent: If True, suppress print messages (for hover detection)

    Returns:
        Bone name to use for IK, or None if bone shouldn't use IK
    """
    bone_lower = bone_name.lower()

    # Twist/roll bones - NO IK (causes noodle limbs)
    if is_twist_bone(bone_name):
        if not silent:
            print(f"  Twist bone detected - IK disabled: {bone_name}")
        return None

    # Pectoral bones - NO IK (shouldn't pull spine/chest)
    # These are breast/chest bones that should not create IK chains
    if is_pectoral(bone_name):
        if not silent:
            print(f"  Pectoral bone detected - IK disabled: {bone_name}")
        return None

    # Carpal/metacarpal bones → map to hand
    if 'carpal' in bone_lower or 'metacarpal' in bone_lower:
        if 'l' in bone_lower[:2] or 'left' in bone_lower:
            target = 'lHand'
        elif 'r' in bone_lower[:2] or 'right' in bone_lower:
            target = 'rHand'
        else:
            # Try to find hand in hierarchy
            if bone_name in armature.pose.bones:
                current = armature.pose.bones[bone_name]
                while current.parent:
                    if 'hand' in current.parent.name.lower() and 'carpal' not in current.parent.name.lower():
                        target = current.parent.name
                        break
                    current = current.parent
                else:
                    target = bone_name
            else:
                target = bone_name

        if target != bone_name and not silent:
            print(f"  Mapping {bone_name} → {target} for IK")
        return target

    # Metatarsal bones → map to foot
    if 'metatarsal' in bone_lower:
        if 'l' in bone_lower[:2] or 'left' in bone_lower:
            target = 'lFoot'
        elif 'r' in bone_lower[:2] or 'right' in bone_lower:
            target = 'rFoot'
        else:
            # Try to find foot in hierarchy
            if bone_name in armature.pose.bones:
                current = armature.pose.bones[bone_name]
                while current.parent:
                    if 'foot' in current.parent.name.lower() and 'metatarsal' not in current.parent.name.lower():
                        target = current.parent.name
                        break
                    current = current.parent
                else:
                    target = bone_name
            else:
                target = bone_name

        if target != bone_name and not silent:
            print(f"  Mapping {bone_name} → {target} for IK")
        return target

    # Face bones → map to head
    # Use word boundaries to avoid false positives (e.g., "ear" in "forearm")
    face_keywords = ['eye', 'brow', 'lid', 'nose', 'mouth', 'lip', 'cheek',
                     'jaw', 'tongue', 'teeth', 'lash', 'pupil']
    # Check for 'ear' specifically with word boundaries (lear, rear)
    is_face_bone = any(keyword in bone_lower for keyword in face_keywords)
    is_face_bone = is_face_bone or (bone_lower.startswith('ear') or bone_lower.startswith('lear') or bone_lower.startswith('rear'))

    if is_face_bone:
        # Find head bone in hierarchy
        if bone_name in armature.pose.bones:
            current = armature.pose.bones[bone_name]
            while current.parent:
                parent_lower = current.parent.name.lower()
                if 'head' in parent_lower and not any(kw in parent_lower for kw in face_keywords):
                    print(f"  Mapping {bone_name} → {current.parent.name} for IK")
                    return current.parent.name
                current = current.parent

        # Fallback - no IK for face bones if can't find head
        print(f"  Face bone - no head found, IK disabled: {bone_name}")
        return None

    # Metatarsal bones → map to foot
    if 'metatarsal' in bone_lower:
        if 'l' in bone_lower[:2] or 'left' in bone_lower:
            target = 'lFoot'
        elif 'r' in bone_lower[:2] or 'right' in bone_lower:
            target = 'rFoot'
        else:
            target = bone_name

        if target != bone_name and not silent:
            print(f"  Mapping {bone_name} → {target} for IK")
        return target

    # Toe bones → map to main toe bone (lToe/rToe)
    if 'toe' in bone_lower:
        if 'l' in bone_lower[:2] or 'left' in bone_lower:
            target = 'lToe'
        elif 'r' in bone_lower[:2] or 'right' in bone_lower:
            target = 'rToe'
        else:
            target = bone_name

        if target != bone_name and not silent:
            print(f"  Mapping {bone_name} → {target} for IK")
        return target

    # Use the bone itself for major bones
    return bone_name


def calculate_chain_length_skipping_twists(start_bone, desired_non_twist_count):
    """
    Calculate how many bones to traverse to get desired number of non-twist, non-pectoral bones.

    This accounts for twist and pectoral bones in the hierarchy that should be
    skipped when building IK chains.

    Args:
        start_bone: The PoseBone to start from
        desired_non_twist_count: How many "real" bones we want in the chain

    Returns:
        Total bone count needed to get desired_non_twist_count usable bones
    """
    current = start_bone
    non_twist_count = 0
    total_count = 0

    while current and non_twist_count < desired_non_twist_count:
        if not is_twist_bone(current.name) and not is_pectoral(current.name):
            non_twist_count += 1
        total_count += 1
        current = current.parent

    return total_count


def get_smart_chain_length(bone_name):
    """
    Determine appropriate IK chain length based on bone type.

    Uses DAZ/Diffeomorphic bone naming patterns to determine optimal
    chain length for different body parts.

    Chain length philosophy:
    - Arms stop at collar to preserve manual torso rotations
    - Legs include pelvis for freedom but exclude hip to prevent spinning
    - Spine bones have medium chains
    - Extremities (fingers, toes) have short chains

    Args:
        bone_name: Name of the bone being dragged

    Returns:
        Recommended chain length (number of bones)
    """
    bone_lower = bone_name.lower()

    # Hands - stop at collar to preserve torso rotations
    # Hand → forearm → upper arm → collar
    # Excludes torso bones so manual torso rotations aren't affected by arm IK
    if 'hand' in bone_lower:
        # Exclude finger bones
        if not any(finger in bone_lower for finger in ['thumb', 'index', 'mid', 'ring', 'pinky', 'carpal']):
            return 4  # Stop at collar (excludes chest/abdomen/spine)

    # Feet - medium chain (foot → shin → thigh → pelvis)
    # Includes pelvis for more freedom, excludes hip to prevent whole-body spinning
    if 'foot' in bone_lower:
        # Exclude toe bones
        if not any(toe in bone_lower for toe in ['toe', 'metatarsal']):
            return 4  # Medium chain: pelvis is root (prevents hip movement, allows leg freedom)

    # Forearms - stop at collar to preserve torso rotations
    if any(part in bone_lower for part in ['forearm', 'lorearm']):
        return 3  # Forearm + upper arm + collar (excludes torso)

    # Shins - medium chain to thigh
    if any(part in bone_lower for part in ['shin', 'calf']):
        return 2

    # Head - full spine chain down to pelvis
    if 'head' in bone_lower:
        return 7  # head -> neck -> chest -> abdomen -> pelvis (includes optional intermediate bones)

    # Fingers - short chain
    if any(finger in bone_lower for finger in ['thumb', 'index', 'mid', 'ring', 'pinky', 'carpal']):
        return 2

    # Toes - short chain
    if any(toe in bone_lower for toe in ['toe', 'metatarsal']):
        return 2

    # Chest - longer chain to reach lower back
    if 'chest' in bone_lower:
        return 4

    # Spine/torso - medium chain
    if any(part in bone_lower for part in ['abdomen', 'spine', 'pelvis']):
        return 3

    # Neck - short chain
    if 'neck' in bone_lower:
        return 2

    # Upper arm/shoulder - short chain (already at top of arm)
    if any(part in bone_lower for part in ['shldr', 'shoulder', 'collar', 'clavicle']):
        return 2

    # Thigh - short chain (already at top of leg)
    if 'thigh' in bone_lower:
        return 2

    # Default - safe short chain for unknown bones
    return 2
