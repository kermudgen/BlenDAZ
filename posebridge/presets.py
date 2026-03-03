
"""PoseBridge Presets - Genesis 8 templates and definitions"""

# ============================================================================
# Genesis 8 Control Point Definitions
# ============================================================================

def get_genesis8_body_control_points():
    """Get control points for Genesis 8 body panel

    Returns:
        List of control point dictionaries with bone names, labels, and groups
    """
    control_points = [
        # Head
        {'id': 'head', 'bone_name': 'head', 'label': 'Head', 'group': 'head', 'type': 'single'},

        # Arms
        {'id': 'lHand', 'bone_name': 'lHand', 'label': 'Left Hand', 'group': 'arms', 'type': 'single'},
        {'id': 'rHand', 'bone_name': 'rHand', 'label': 'Right Hand', 'group': 'arms', 'type': 'single'},
        {'id': 'lForeArm', 'bone_name': 'lForeArm', 'label': 'Left Forearm', 'group': 'arms', 'type': 'single'},
        {'id': 'rForeArm', 'bone_name': 'rForeArm', 'label': 'Right Forearm', 'group': 'arms', 'type': 'single'},
        {'id': 'lShldr', 'bone_name': 'lShldr', 'label': 'Left Shoulder', 'group': 'arms', 'type': 'single'},
        {'id': 'rShldr', 'bone_name': 'rShldr', 'label': 'Right Shoulder', 'group': 'arms', 'type': 'single'},

        # Torso
        {'id': 'chest', 'bone_name': 'chest', 'label': 'Chest', 'group': 'torso', 'type': 'single'},
        {'id': 'abdomen', 'bone_name': 'abdomen', 'label': 'Abdomen', 'group': 'torso', 'type': 'single'},
        {'id': 'pelvis', 'bone_name': 'pelvis', 'label': 'Pelvis', 'group': 'torso', 'type': 'single'},

        # Legs
        {'id': 'lFoot', 'bone_name': 'lFoot', 'label': 'Left Foot', 'group': 'legs', 'type': 'single'},
        {'id': 'rFoot', 'bone_name': 'rFoot', 'label': 'Right Foot', 'group': 'legs', 'type': 'single'},
        {'id': 'lShin', 'bone_name': 'lShin', 'label': 'Left Shin', 'group': 'legs', 'type': 'single'},
        {'id': 'rShin', 'bone_name': 'rShin', 'label': 'Right Shin', 'group': 'legs', 'type': 'single'},
        {'id': 'lThigh', 'bone_name': 'lThigh', 'label': 'Left Thigh', 'group': 'legs', 'type': 'single'},
        {'id': 'rThigh', 'bone_name': 'rThigh', 'label': 'Right Thigh', 'group': 'legs', 'type': 'single'},
    ]

    return control_points

def get_genesis8_head_control_points():
    """Get control points for Genesis 8 head panel"""
    # TODO: Implement for Phase 3
    pass

def get_genesis8_hands_control_points():
    """Get control points for Genesis 8 hands panel"""
    # TODO: Implement for Phase 3
    pass
