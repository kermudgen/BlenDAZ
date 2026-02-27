"""
PoseBridge Face Panel Setup
Creates a live camera aimed at the character's face and generates morph control points.
Unlike the hand panel (which extracts geometry), the face panel uses a live camera
so morph deformations are visible in real-time.
"""

import bpy
import math
from mathutils import Vector

from outline_generator_lineart import get_or_create_pb_collection


def create_face_camera(armature, camera_distance=0.6, ortho_scale=0.22, stage_coll=None):
    """
    Create orthographic camera aimed at the character's face.

    The camera looks at the head bone from the front (-Y direction).
    Uses a tight ortho_scale to frame just the face.

    Args:
        armature: The character's armature object
        camera_distance: Distance from face to camera (along -Y)
        ortho_scale: Orthographic scale (smaller = more zoomed in)

    Returns:
        The camera object, or None on failure
    """
    camera_name = "PB_Camera_Face"

    # Find head bone for positioning
    head_bone = armature.data.bones.get('head')
    if not head_bone:
        print("ERROR: 'head' bone not found in armature")
        return None

    # Head bone center in armature local space (rest pose)
    # Use head_local midpoint between head and tail for center of head
    head_center = (head_bone.head_local + head_bone.tail_local) / 2
    # Transform to world space
    head_world = armature.matrix_world @ head_center

    # Remove existing camera
    if camera_name in bpy.data.objects:
        old_cam = bpy.data.objects[camera_name]
        bpy.data.objects.remove(old_cam, do_unlink=True)

    # Create camera with 9:16 portrait aspect ratio
    camera_data = bpy.data.cameras.new(camera_name)
    camera_data.type = 'ORTHO'
    camera_data.ortho_scale = ortho_scale
    camera_data.sensor_fit = 'VERTICAL'
    camera_data.sensor_width = 20.25   # 9/16 * 36 = 20.25 (36mm is default sensor height)
    camera_data.sensor_height = 36.0

    camera = bpy.data.objects.new(camera_name, camera_data)
    target = stage_coll if stage_coll else bpy.context.scene.collection
    target.objects.link(camera)

    # Set camera to correct world position/rotation FIRST
    # DAZ characters face -Y, so camera is in front at -Y offset, looking along +Y
    camera.location = Vector((
        head_world.x,
        head_world.y - camera_distance,
        head_world.z
    ))
    camera.rotation_euler = (math.radians(90), 0, 0)  # Looking along +Y

    # Now parent to head bone, using matrix_parent_inverse to preserve world transform
    # This way the camera follows the head but starts at the correct position
    from mathutils import Matrix
    camera.parent = armature
    camera.parent_type = 'BONE'
    camera.parent_bone = 'head'

    # Compute the bone's parent matrix (what Blender uses for BONE parenting)
    # parent_mat = armature.matrix_world @ pose_bone.matrix @ tail_offset
    head_pose_bone = armature.pose.bones['head']
    bone_tail_offset = Matrix.Translation((0, head_pose_bone.length, 0))
    parent_mat = armature.matrix_world @ head_pose_bone.matrix @ bone_tail_offset
    camera.matrix_parent_inverse = parent_mat.inverted()

    # Hide camera from viewport so its wireframe doesn't block mesh raycasts/selection
    # It still works as a camera when looked through via space.camera
    camera.hide_viewport = True

    print(f"Created face camera parented to 'head' bone")
    print(f"  World position: {camera.location}")
    print(f"  Head center: {head_world}")
    print(f"  Ortho scale: {ortho_scale}")

    return camera


def get_face_control_positions(armature):
    """
    Calculate 3D world positions for face control points.

    Uses the head bone as the primary reference, with manual offsets
    for each face region. Positions are in world space so they project
    correctly through the face camera.

    Args:
        armature: The character's armature object

    Returns:
        Dict mapping CP id to Vector world position
    """
    head_bone = armature.data.bones.get('head')
    if not head_bone:
        print("ERROR: 'head' bone not found")
        return {}

    # Head center in world space
    head_center = (head_bone.head_local + head_bone.tail_local) / 2
    hc = armature.matrix_world @ head_center

    # Try to get eye and jaw bones for better positioning
    leye_bone = armature.data.bones.get('lEye')
    reye_bone = armature.data.bones.get('rEye')
    jaw_bone = armature.data.bones.get('lowerJaw')

    # Eye positions (fallback to offsets from head center)
    if leye_bone:
        leye_pos = armature.matrix_world @ leye_bone.head_local
    else:
        leye_pos = hc + Vector((0.032, 0, 0.02))

    if reye_bone:
        reye_pos = armature.matrix_world @ reye_bone.head_local
    else:
        reye_pos = hc + Vector((-0.032, 0, 0.02))

    # Jaw position (fallback to offset from head center)
    if jaw_bone:
        jaw_pos = armature.matrix_world @ jaw_bone.tail_local
    else:
        jaw_pos = hc + Vector((0, 0, -0.06))

    # Brow inner bones for combined brow node positioning
    lbrowin_bone = armature.data.bones.get('lBrowInner')
    rbrowin_bone = armature.data.bones.get('rBrowInner')
    if lbrowin_bone:
        lbrowin_pos = armature.matrix_world @ lbrowin_bone.head_local
    else:
        lbrowin_pos = None
    if rbrowin_bone:
        rbrowin_pos = armature.matrix_world @ rbrowin_bone.head_local
    else:
        rbrowin_pos = None

    # Lip bones for mouth upper/lower positioning
    lip_upper_bone = armature.data.bones.get('LipUpperMiddle')
    lip_lower_bone = armature.data.bones.get('LipLowerMiddle')
    if lip_upper_bone:
        lip_upper_pos = armature.matrix_world @ lip_upper_bone.head_local
    else:
        lip_upper_pos = None
    if lip_lower_bone:
        lip_lower_pos = armature.matrix_world @ lip_lower_bone.head_local
    else:
        lip_lower_pos = None

    # Lip corner bones for mouth smile/frown positioning
    llip_corner_bone = armature.data.bones.get('lLipCorner')
    rlip_corner_bone = armature.data.bones.get('rLipCorner')
    if llip_corner_bone:
        llip_corner_pos = armature.matrix_world @ llip_corner_bone.head_local
    else:
        llip_corner_pos = None
    if rlip_corner_bone:
        rlip_corner_pos = armature.matrix_world @ rlip_corner_bone.head_local
    else:
        rlip_corner_pos = None

    # Lip outer bones for mouth upper up / lower down positioning
    llip_upper_outer_bone = armature.data.bones.get('lLipUpperOuter')
    rlip_upper_outer_bone = armature.data.bones.get('rLipUpperOuter')
    llip_lower_outer_bone = armature.data.bones.get('lLipLowerOuter')
    rlip_lower_outer_bone = armature.data.bones.get('rLipLowerOuter')
    if llip_upper_outer_bone:
        llip_upper_outer_pos = armature.matrix_world @ llip_upper_outer_bone.head_local
    else:
        llip_upper_outer_pos = None
    if rlip_upper_outer_bone:
        rlip_upper_outer_pos = armature.matrix_world @ rlip_upper_outer_bone.head_local
    else:
        rlip_upper_outer_pos = None
    if llip_lower_outer_bone:
        llip_lower_outer_pos = armature.matrix_world @ llip_lower_outer_bone.head_local
    else:
        llip_lower_outer_pos = None
    if rlip_lower_outer_bone:
        rlip_lower_outer_pos = armature.matrix_world @ rlip_lower_outer_bone.head_local
    else:
        rlip_lower_outer_pos = None

    # Squint bones for eye squint positioning
    lsquint_bone = armature.data.bones.get('lSquintOuter')
    rsquint_bone = armature.data.bones.get('rSquintOuter')
    if lsquint_bone:
        lsquint_pos = armature.matrix_world @ lsquint_bone.head_local
    else:
        lsquint_pos = None
    if rsquint_bone:
        rsquint_pos = armature.matrix_world @ rsquint_bone.head_local
    else:
        rsquint_pos = None

    # Cheek bones for cheek puff positioning
    lcheek_bone = armature.data.bones.get('lCheekLower')
    rcheek_bone = armature.data.bones.get('rCheekLower')
    if lcheek_bone:
        lcheek_pos = armature.matrix_world @ lcheek_bone.head_local
    else:
        lcheek_pos = None
    if rcheek_bone:
        rcheek_pos = armature.matrix_world @ rcheek_bone.head_local
    else:
        rcheek_pos = None

    # Measure face scale from eye distance for proportional offsets
    eye_dist = (leye_pos - reye_pos).length
    if eye_dist < 0.001:
        eye_dist = 0.064  # fallback

    # Eye center (midpoint between eyes)
    eye_center = (leye_pos + reye_pos) / 2

    # Vertical spacing unit (proportional to face)
    vu = eye_dist * 0.4   # ~0.026
    # Horizontal spacing unit
    hu = eye_dist * 0.5   # ~0.032

    positions = {}

    # ===== BROW REGION =====
    # Combined inner brow node: drag up = inner up, drag down = brow down
    # Positioned at BrowInner bone locations
    brow_y = eye_center.z + vu * 1.5  # fallback
    if lbrowin_pos:
        positions['face_lBrowInner'] = Vector((lbrowin_pos.x, hc.y, lbrowin_pos.z))
    else:
        positions['face_lBrowInner'] = Vector((hc.x + hu * 0.25, hc.y, brow_y))
    if rbrowin_pos:
        positions['face_rBrowInner'] = Vector((rbrowin_pos.x, hc.y, rbrowin_pos.z))
    else:
        positions['face_rBrowInner'] = Vector((hc.x - hu * 0.25, hc.y, brow_y))

    # Brow outer up - at outer edges
    positions['face_lBrowOuterUp'] = Vector((leye_pos.x + hu * 0.7, hc.y, brow_y + vu * 0.2))
    positions['face_rBrowOuterUp'] = Vector((reye_pos.x - hu * 0.7, hc.y, brow_y + vu * 0.2))

    # ===== EYE REGION =====
    # Combined eye node: drag up = wide, drag down = blink
    positions['face_lEye'] = Vector((leye_pos.x, hc.y, leye_pos.z + vu * 0.3))
    positions['face_rEye'] = Vector((reye_pos.x, hc.y, reye_pos.z + vu * 0.3))

    # Squint node - at SquintOuter bone locations
    if lsquint_pos:
        positions['face_lSquint'] = Vector((lsquint_pos.x, hc.y, lsquint_pos.z))
    else:
        positions['face_lSquint'] = Vector((leye_pos.x + hu * 0.5, hc.y, leye_pos.z - vu * 0.2))
    if rsquint_pos:
        positions['face_rSquint'] = Vector((rsquint_pos.x, hc.y, rsquint_pos.z))
    else:
        positions['face_rSquint'] = Vector((reye_pos.x - hu * 0.5, hc.y, reye_pos.z - vu * 0.2))

    # ===== NOSE REGION =====
    nose_z = eye_center.z - vu * 1.2
    positions['face_lNoseSneer'] = Vector((hc.x + hu * 0.35, hc.y, nose_z))
    positions['face_rNoseSneer'] = Vector((hc.x - hu * 0.35, hc.y, nose_z))

    # ===== CHEEK REGION =====
    # Use lCheekLower/rCheekLower bone positions if available
    if lcheek_pos:
        positions['face_lCheekPuff'] = Vector((lcheek_pos.x, hc.y, lcheek_pos.z))
    else:
        cheek_z = eye_center.z - vu * 0.5
        positions['face_lCheekPuff'] = Vector((leye_pos.x + hu * 0.6, hc.y, cheek_z))
    if rcheek_pos:
        positions['face_rCheekPuff'] = Vector((rcheek_pos.x, hc.y, rcheek_pos.z))
    else:
        cheek_z = eye_center.z - vu * 0.5
        positions['face_rCheekPuff'] = Vector((reye_pos.x - hu * 0.6, hc.y, cheek_z))

    # ===== MOUTH REGION =====
    mouth_z = (eye_center.z + jaw_pos.z) / 2 - vu * 0.3

    # Mouth corners - combined smile/frown: drag up = smile, drag down = frown
    if llip_corner_pos:
        positions['face_lMouthCorner'] = Vector((llip_corner_pos.x, hc.y, llip_corner_pos.z))
    else:
        positions['face_lMouthCorner'] = Vector((hc.x + hu * 0.55, hc.y, mouth_z))
    if rlip_corner_pos:
        positions['face_rMouthCorner'] = Vector((rlip_corner_pos.x, hc.y, rlip_corner_pos.z))
    else:
        positions['face_rMouthCorner'] = Vector((hc.x - hu * 0.55, hc.y, mouth_z))

    # Mouth center - use lip bone positions if available
    if lip_upper_pos:
        positions['face_mouthUpper'] = Vector((hc.x, hc.y, lip_upper_pos.z))
    else:
        positions['face_mouthUpper'] = Vector((hc.x, hc.y, mouth_z + vu * 0.1))
    if lip_lower_pos:
        positions['face_mouthLower'] = Vector((hc.x, hc.y, lip_lower_pos.z))
    else:
        positions['face_mouthLower'] = Vector((hc.x, hc.y, mouth_z - vu * 0.1))

    # Mouth upper up / lower down - at LipUpperOuter / LipLowerOuter bone locations
    if llip_upper_outer_pos:
        positions['face_lMouthUpperUp'] = Vector((llip_upper_outer_pos.x, hc.y, llip_upper_outer_pos.z))
    else:
        positions['face_lMouthUpperUp'] = Vector((hc.x + hu * 0.3, hc.y, mouth_z + vu * 0.1))
    if rlip_upper_outer_pos:
        positions['face_rMouthUpperUp'] = Vector((rlip_upper_outer_pos.x, hc.y, rlip_upper_outer_pos.z))
    else:
        positions['face_rMouthUpperUp'] = Vector((hc.x - hu * 0.3, hc.y, mouth_z + vu * 0.1))
    if llip_lower_outer_pos:
        positions['face_lMouthLowerDown'] = Vector((llip_lower_outer_pos.x, hc.y, llip_lower_outer_pos.z))
    else:
        positions['face_lMouthLowerDown'] = Vector((hc.x + hu * 0.3, hc.y, mouth_z - vu * 0.1))
    if rlip_lower_outer_pos:
        positions['face_rMouthLowerDown'] = Vector((rlip_lower_outer_pos.x, hc.y, rlip_lower_outer_pos.z))
    else:
        positions['face_rMouthLowerDown'] = Vector((hc.x - hu * 0.3, hc.y, mouth_z - vu * 0.1))

    # ===== JAW REGION =====
    positions['face_jaw'] = Vector((jaw_pos.x, hc.y, jaw_pos.z - vu * 0.3))

    # ===== TONGUE =====
    positions['face_tongue'] = Vector((hc.x, hc.y, mouth_z - vu * 0.1))

    print(f"Calculated {len(positions)} face control positions")
    for cp_id, pos in sorted(positions.items()):
        print(f"  {cp_id}: ({pos.x:.4f}, {pos.y:.4f}, {pos.z:.4f})")

    return positions


def generate_face_control_points(positions):
    """
    Generate face control point definitions with FACS morph mappings.

    Each CP maps mouse gestures to specific FACS properties:
    - LMB = bilateral (both sides)
    - RMB = asymmetric (just the CP's side)
    - Format: (prop_name, direction, scale)
    - direction: 'positive' = drag-up/right increases, 'negative' = opposite

    Args:
        positions: Dict from get_face_control_positions()

    Returns:
        List of control point definition dicts
    """
    control_points = []

    def add_cp(cp_id, label, controls, group='face'):
        if cp_id not in positions:
            return
        pos = positions[cp_id]
        control_points.append({
            'id': cp_id,
            'bone_name': 'head',  # Reference bone (not driven)
            'label': label,
            'group': group,
            'panel_view': 'face',
            'control_type': 'single',
            'interaction_mode': 'morph',
            'position_3d_fixed': (pos.x, pos.y, pos.z),
            'controls': controls,
        })

    # ===== BROW CONTROLS =====
    # Combined inner brow: drag up = inner up, drag down = brow down
    # Uses split keys (_pos/_neg) for directional vertical control
    add_cp('face_lBrowInner', 'Left Brow Inner', {
        'lmb_vert_pos': ('facs_ctrl_BrowInnerUp', 'positive', 1.0),   # drag up = raise both
        'lmb_vert_neg': ('facs_ctrl_BrowDown', 'positive', 1.0),      # drag down = furrow both
        'lmb_horiz': None,
        'rmb_vert_pos': ('facs_bs_BrowInnerUpLeft_div2', 'positive', 1.0),  # per-side raise
        'rmb_vert_neg': ('facs_BrowDownLeft', 'positive', 1.0),             # per-side furrow
        'rmb_horiz': None,
    })
    add_cp('face_rBrowInner', 'Right Brow Inner', {
        'lmb_vert_pos': ('facs_ctrl_BrowInnerUp', 'positive', 1.0),
        'lmb_vert_neg': ('facs_ctrl_BrowDown', 'positive', 1.0),
        'lmb_horiz': None,
        'rmb_vert_pos': ('facs_bs_BrowInnerUpRight_div2', 'positive', 1.0),
        'rmb_vert_neg': ('facs_BrowDownRight', 'positive', 1.0),
        'rmb_horiz': None,
    })

    add_cp('face_lBrowOuterUp', 'Left Brow Outer Up', {
        'lmb_vert':  ('facs_ctrl_BrowUp', 'positive', 1.0),
        'lmb_horiz': None,
        'rmb_vert':  ('facs_BrowOuterUpLeft', 'positive', 1.0),
        'rmb_horiz': None,
    })
    add_cp('face_rBrowOuterUp', 'Right Brow Outer Up', {
        'lmb_vert':  ('facs_ctrl_BrowUp', 'positive', 1.0),
        'lmb_horiz': None,
        'rmb_vert':  ('facs_BrowOuterUpRight', 'positive', 1.0),
        'rmb_horiz': None,
    })

    # ===== EYE CONTROLS =====
    # Combined node: drag up = wide, drag down = blink
    # Uses split keys (_pos/_neg) for directional vertical control
    add_cp('face_lEye', 'Left Eye', {
        'lmb_vert_pos': ('facs_ctrl_EyeWide', 'positive', 1.0),       # drag up = widen both
        'lmb_vert_neg': ('facs_ctrl_EyesBlink', 'positive', 1.0),     # drag down = blink both
        'lmb_horiz': None,
        'rmb_vert_pos': ('facs_jnt_EyesWideLeft', 'positive', 1.0),   # per-side wide
        'rmb_vert_neg': ('facs_jnt_EyeBlinkLeft', 'positive', 1.0),   # per-side blink
        'rmb_horiz': None,
    })
    add_cp('face_rEye', 'Right Eye', {
        'lmb_vert_pos': ('facs_ctrl_EyeWide', 'positive', 1.0),
        'lmb_vert_neg': ('facs_ctrl_EyesBlink', 'positive', 1.0),
        'lmb_horiz': None,
        'rmb_vert_pos': ('facs_jnt_EyesWideRight', 'positive', 1.0),
        'rmb_vert_neg': ('facs_jnt_EyeBlinkRight', 'positive', 1.0),
        'rmb_horiz': None,
    })

    # Squint - separate node at SquintOuter bone, vertical control
    add_cp('face_lSquint', 'Left Squint', {
        'lmb_vert':  ('facs_ctrl_EyeSquint', 'positive', 1.0),
        'lmb_horiz': None,
        'rmb_vert':  ('facs_bs_EyeSquintLeft_div2', 'positive', 1.0),
        'rmb_horiz': None,
    })
    add_cp('face_rSquint', 'Right Squint', {
        'lmb_vert':  ('facs_ctrl_EyeSquint', 'positive', 1.0),
        'lmb_horiz': None,
        'rmb_vert':  ('facs_bs_EyeSquintRight_div2', 'positive', 1.0),
        'rmb_horiz': None,
    })

    # ===== NOSE CONTROLS =====
    # Actual: facs_ctrl_NoseSneer, facs_bs_NoseSneerLeft/Right_div2
    add_cp('face_lNoseSneer', 'Left Nose Sneer', {
        'lmb_vert':  ('facs_ctrl_NoseSneer', 'positive', 1.0),
        'lmb_horiz': None,
        'rmb_vert':  ('facs_bs_NoseSneerLeft_div2', 'positive', 1.0),
        'rmb_horiz': None,
    })
    add_cp('face_rNoseSneer', 'Right Nose Sneer', {
        'lmb_vert':  ('facs_ctrl_NoseSneer', 'positive', 1.0),
        'lmb_horiz': None,
        'rmb_vert':  ('facs_bs_NoseSneerRight_div2', 'positive', 1.0),
        'rmb_horiz': None,
    })

    # ===== CHEEK CONTROLS =====
    # Actual: facs_ctrl_CheekPuff, facs_bs_CheekPuffLeft/Right_div2
    add_cp('face_lCheekPuff', 'Left Cheek Puff', {
        'lmb_vert':  None,
        'lmb_horiz': ('facs_ctrl_CheekPuff', 'positive', 1.0),
        'rmb_vert':  None,
        'rmb_horiz': ('facs_bs_CheekPuffLeft_div2', 'positive', 1.0),
    })
    add_cp('face_rCheekPuff', 'Right Cheek Puff', {
        'lmb_vert':  None,
        'lmb_horiz': ('facs_ctrl_CheekPuff', 'negative', 1.0),
        'rmb_vert':  None,
        'rmb_horiz': ('facs_bs_CheekPuffRight_div2', 'negative', 1.0),
    })

    # ===== MOUTH CONTROLS =====
    # Combined mouth corner: drag up = smile, drag down = frown
    # Positioned at lip corner bones
    add_cp('face_lMouthCorner', 'Left Mouth Corner', {
        'lmb_vert_pos': ('facs_ctrl_MouthSmile', 'positive', 1.0),        # drag up = smile both
        'lmb_vert_neg': ('facs_ctrl_MouthFrown', 'positive', 1.0),        # drag down = frown both
        'lmb_horiz':    ('facs_ctrl_MouthStretch', 'positive', 1.0),      # horiz = stretch
        'rmb_vert_pos': ('facs_bs_MouthSmileLeft_div2', 'positive', 1.0), # per-side smile
        'rmb_vert_neg': ('facs_bs_MouthFrownLeft_div2', 'positive', 1.0), # per-side frown
        'rmb_horiz':    ('facs_bs_MouthStretchLeft_div2', 'positive', 1.0),
    })
    add_cp('face_rMouthCorner', 'Right Mouth Corner', {
        'lmb_vert_pos': ('facs_ctrl_MouthSmile', 'positive', 1.0),
        'lmb_vert_neg': ('facs_ctrl_MouthFrown', 'positive', 1.0),
        'lmb_horiz':    ('facs_ctrl_MouthStretch', 'negative', 1.0),
        'rmb_vert_pos': ('facs_bs_MouthSmileRight_div2', 'positive', 1.0),
        'rmb_vert_neg': ('facs_bs_MouthFrownRight_div2', 'positive', 1.0),
        'rmb_horiz':    ('facs_bs_MouthStretchRight_div2', 'negative', 1.0),
    })

    # Mouth upper up - at LipUpperOuter bone locations
    add_cp('face_lMouthUpperUp', 'Left Mouth Upper Up', {
        'lmb_vert':  ('facs_ctrl_MouthUpperUp', 'positive', 1.0),
        'lmb_horiz': None,
        'rmb_vert':  ('facs_bs_MouthUpperUpLeft_div2', 'positive', 1.0),
        'rmb_horiz': None,
    })
    add_cp('face_rMouthUpperUp', 'Right Mouth Upper Up', {
        'lmb_vert':  ('facs_ctrl_MouthUpperUp', 'positive', 1.0),
        'lmb_horiz': None,
        'rmb_vert':  ('facs_bs_MouthUpperUpRight_div2', 'positive', 1.0),
        'rmb_horiz': None,
    })

    # Mouth lower down - at LipLowerOuter bone locations
    add_cp('face_lMouthLowerDown', 'Left Mouth Lower Down', {
        'lmb_vert':  ('facs_ctrl_MouthLowerDown', 'negative', 1.0),
        'lmb_horiz': None,
        'rmb_vert':  ('facs_bs_MouthLowerDownLeft_div2', 'negative', 1.0),
        'rmb_horiz': None,
    })
    add_cp('face_rMouthLowerDown', 'Right Mouth Lower Down', {
        'lmb_vert':  ('facs_ctrl_MouthLowerDown', 'negative', 1.0),
        'lmb_horiz': None,
        'rmb_vert':  ('facs_bs_MouthLowerDownRight_div2', 'negative', 1.0),
        'rmb_horiz': None,
    })

    add_cp('face_mouthUpper', 'Mouth Upper', {
        'lmb_vert':  ('facs_bs_MouthPucker_div2', 'positive', 1.0),
        'lmb_horiz': ('facs_bs_MouthFunnel_div2', 'positive', 1.0),
        'rmb_vert':  ('facs_bs_MouthShrugUpper_div2', 'positive', 1.0),
        'rmb_horiz': ('facs_bs_MouthRollUpper_div2', 'positive', 1.0),
    })

    add_cp('face_mouthLower', 'Mouth Lower', {
        'lmb_vert':  ('facs_bs_MouthClose_div2', 'positive', 1.0),
        'lmb_horiz': ('facs_bs_MouthRollLower_div2', 'positive', 1.0),
        'rmb_vert':  ('facs_bs_MouthShrugLower_div2', 'negative', 1.0),
        'rmb_horiz': None,
    })

    # ===== JAW CONTROL =====
    # Actual: facs_jnt_JawOpen, facs_jnt_JawLeft, facs_jnt_JawRight, facs_jnt_JawForward
    add_cp('face_jaw', 'Jaw', {
        'lmb_vert':  ('facs_jnt_JawOpen', 'negative', 1.0),
        'lmb_horiz': ('facs_jnt_JawLeft', 'positive', 1.0),
        'rmb_vert':  ('facs_jnt_JawForward', 'positive', 1.0),
        'rmb_horiz': None,
    })

    # ===== TONGUE CONTROL =====
    # Actual: facs_bs_TongueOut (no _div2 suffix)
    add_cp('face_tongue', 'Tongue', {
        'lmb_vert':  ('facs_bs_TongueOut', 'positive', 1.0),
        'lmb_horiz': None,
        'rmb_vert':  ('facs_jnt_TongueUp', 'positive', 1.0),
        'rmb_horiz': None,
    })

    print(f"Generated {len(control_points)} face control points")
    return control_points


def store_face_control_points(face_cps):
    """
    Store face control points in PoseBridge settings.

    Args:
        face_cps: List of CP definition dicts from generate_face_control_points()

    Returns:
        Number of control points stored
    """
    settings = bpy.context.scene.posebridge_settings

    # Remove existing face control points
    to_remove = []
    for i, cp in enumerate(settings.control_points_fixed):
        if cp.panel_view == 'face':
            to_remove.append(i)
    for i in reversed(to_remove):
        settings.control_points_fixed.remove(i)

    # Add new face control points
    for cp_def in face_cps:
        cp = settings.control_points_fixed.add()
        cp.id = cp_def['id']
        cp.bone_name = cp_def.get('bone_name', '')
        cp.label = cp_def['label']
        cp.group = cp_def['group']
        cp.panel_view = cp_def['panel_view']
        cp.control_type = cp_def['control_type']
        cp.interaction_mode = cp_def.get('interaction_mode', 'rotation')
        cp.shape = cp_def.get('shape', '')
        cp.position_3d_fixed = cp_def['position_3d_fixed']

    print(f"Stored {len(face_cps)} face control points")
    return len(face_cps)


def setup_face_panel(armature=None, char_name=None):
    """
    Main orchestrator: set up the face panel camera and control points.

    Args:
        armature: Armature object (auto-detected if None)
        char_name: Short character name (e.g. 'Fey') for PB_{char}_Stage collection

    Returns:
        Dict with 'camera' and 'control_points' count, or None on failure
    """
    # Auto-detect armature
    if armature is None:
        settings = bpy.context.scene.posebridge_settings
        if settings.active_armature_name:
            armature = bpy.data.objects.get(settings.active_armature_name)
        if not armature:
            obj = bpy.context.active_object
            if obj and obj.type == 'ARMATURE':
                armature = obj
            elif obj and obj.type == 'MESH':
                armature = obj.find_armature()

    if not armature or armature.type != 'ARMATURE':
        print("ERROR: No armature found. Select a DAZ character first.")
        return None

    print(f"\n{'='*60}")
    print(f"Setting up Face Panel for: {armature.name}")
    print(f"{'='*60}")

    # Resolve target collection
    stage_coll = None
    if char_name:
        stage_coll = get_or_create_pb_collection(char_name, 'Stage')
        print(f"  Collection: {stage_coll.name}")

    # Step 1: Create face camera
    camera = create_face_camera(armature, stage_coll=stage_coll)
    if not camera:
        return None

    # Step 2: Calculate control point positions (world space)
    positions = get_face_control_positions(armature)
    if not positions:
        print("ERROR: Could not calculate face control positions")
        return None

    # Step 2b: Convert positions to head-bone-local space
    # This allows the drawing code to transform them using the current head pose,
    # so CPs track with the head when the character moves or is posed.
    head_rest_matrix = armature.matrix_world @ armature.data.bones['head'].matrix_local
    head_rest_inv = head_rest_matrix.inverted()
    for cp_id in positions:
        positions[cp_id] = head_rest_inv @ positions[cp_id]
    print(f"  Converted {len(positions)} positions to head-bone-local space")

    # Step 3: Generate control point definitions
    face_cps = generate_face_control_points(positions)

    # Step 4: Validate FACS properties exist on armature
    all_props = set(k for k in armature.keys() if isinstance(k, str))
    missing = []
    for cp_def in face_cps:
        controls = cp_def.get('controls', {})
        for key, entry in controls.items():
            if entry is not None:
                prop_name = entry[0]
                if prop_name not in all_props:
                    missing.append(prop_name)

    if missing:
        unique_missing = sorted(set(missing))
        print(f"\nWARNING: {len(unique_missing)} FACS properties not found on armature:")
        for prop in unique_missing:
            print(f"  - {prop}")
        print("These controls will have no effect until the properties are loaded.")

    # Step 5: Store control points
    cp_count = store_face_control_points(face_cps)

    print(f"\n{'='*60}")
    print(f"Face panel setup complete!")
    print(f"  Camera: {camera.name}")
    print(f"  Control points: {cp_count}")
    print(f"{'='*60}\n")

    return {
        'camera': camera,
        'control_points': cp_count,
    }


# Allow running as a standalone script in Blender
if __name__ == "__main__":
    setup_face_panel()
