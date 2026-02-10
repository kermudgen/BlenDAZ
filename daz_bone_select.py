"""
DAZ Bone Select & Pin & PowerPose
Combines fast hover preview, bone selection, pin marking system, and PowerPose panel posing
"""

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector, Euler, Quaternion, Matrix
from mathutils.bvhtree import BVHTree
import gpu
from gpu_extras.batch import batch_for_shader


bl_info = {
    "name": "DAZ Bone Select & Pin & PowerPose",
    "version": (1, 2, 0),
    "blender": (3, 0, 0),
    "description": "Hover to preview, click to select, pin bones for IK, PowerPose panel posing",
    "category": "Rigging",
}


# ============================================================================
# BASE MESH DETECTION - Helper Functions
# ============================================================================

def find_base_body_mesh(context, armature):
    """
    Find the base body mesh - the one with the most vertex groups/bones.
    This is typically the main figure, not clothing or hair.
    """
    if not armature:
        return None

    best_mesh = None
    max_vgroups = 0

    for obj in context.scene.objects:
        if obj.type != 'MESH':
            continue
        if not obj.visible_get():
            continue

        # Check if this mesh is rigged to this armature
        rigged_to_armature = False
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object == armature:
                rigged_to_armature = True
                break

        if not rigged_to_armature:
            if obj.parent == armature:
                rigged_to_armature = True

        if rigged_to_armature:
            vgroup_count = len(obj.vertex_groups)
            if vgroup_count > max_vgroups:
                max_vgroups = vgroup_count
                best_mesh = obj

    if best_mesh:
        print(f"  Base body mesh detected: {best_mesh.name} ({max_vgroups} vertex groups)")

    return best_mesh


def raycast_specific_mesh(mesh_obj, ray_origin, ray_direction, context):
    """
    Raycast against a specific mesh object.
    Returns: (hit_location_world, distance) or (None, None)
    """
    try:
        # Get evaluated mesh with modifiers
        depsgraph = context.evaluated_depsgraph_get()
        obj_eval = mesh_obj.evaluated_get(depsgraph)
        mesh = obj_eval.to_mesh()

        if not mesh:
            return None, None

        # Build BVH tree for this one mesh
        bvh = BVHTree.FromPolygons(
            [v.co for v in mesh.vertices],
            [p.vertices for p in mesh.polygons]
        )

        # Transform ray to object space
        matrix_inv = mesh_obj.matrix_world.inverted()
        origin_local = matrix_inv @ ray_origin
        direction_local = matrix_inv.to_3x3() @ ray_direction

        # Raycast
        location, normal, index, distance = bvh.ray_cast(origin_local, direction_local)

        obj_eval.to_mesh_clear()

        if location:
            # Transform back to world space
            location_world = mesh_obj.matrix_world @ location
            return location_world, distance

        return None, None

    except Exception as e:
        print(f"  Raycast error for {mesh_obj.name}: {e}")
        return None, None


# ============================================================================
# IK SYSTEM - Helper Functions
# ============================================================================

def is_twist_bone(bone_name):
    """Check if bone is a twist/roll bone that shouldn't use IK"""
    bone_lower = bone_name.lower()
    return 'twist' in bone_lower or 'roll' in bone_lower


def is_pectoral(bone_name):
    """Check if bone is a pectoral bone that shouldn't be in IK chains"""
    bone_lower = bone_name.lower()
    return 'pectoral' in bone_lower or 'breast' in bone_lower


def get_ik_target_bone(armature, bone_name):
    """
    Map small bones to their major parent bone for IK (DAZ-style behavior).
    Returns: bone name to use for IK, or None if bone shouldn't use IK.
    """
    bone_lower = bone_name.lower()

    # Twist/roll bones - NO IK (causes noodle limbs)
    if is_twist_bone(bone_name):
        print(f"  Twist bone detected - IK disabled: {bone_name}")
        return None

    # Pectoral bones - NO IK (shouldn't pull spine/chest)
    # These are breast/chest bones that should not create IK chains
    if is_pectoral(bone_name):
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

        if target != bone_name:
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

        if target != bone_name:
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

    # Toe/metatarsal bones → map to foot
    if 'toe' in bone_lower or 'metatarsal' in bone_lower:
        if 'l' in bone_lower[:2] or 'left' in bone_lower:
            target = 'lFoot'
        elif 'r' in bone_lower[:2] or 'right' in bone_lower:
            target = 'rFoot'
        else:
            target = bone_name

        if target != bone_name:
            print(f"  Mapping {bone_name} → {target} for IK")
        return target

    # Use the bone itself for major bones
    return bone_name


def calculate_chain_length_skipping_twists(start_bone, desired_non_twist_count):
    """
    Calculate how many bones to traverse to get desired number of non-twist, non-pectoral bones.
    Accounts for twist and pectoral bones in the hierarchy.
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
    Uses DAZ/Diffeomorphic bone naming patterns.
    """
    bone_lower = bone_name.lower()

    # Hands - full chain for ragdoll pulling
    # Hand → forearm → upper arm → collar → chest → spine → abdomen → hip
    # IK stiffness will create natural falloff (parent bones resist more)
    if 'hand' in bone_lower:
        # Exclude finger bones
        if not any(finger in bone_lower for finger in ['thumb', 'index', 'mid', 'ring', 'pinky', 'carpal']):
            return 9  # Extended chain including hip for stability

    # Feet - full chain for ragdoll pulling
    # Foot → shin → thigh → pelvis → spine → chest
    # IK stiffness will create natural falloff (parent bones resist more)
    if 'foot' in bone_lower:
        # Exclude toe bones
        if not any(toe in bone_lower for toe in ['toe', 'metatarsal']):
            return 7  # Extended chain for ragdoll effect

    # Forearms - full arm chain including collar
    if any(part in bone_lower for part in ['forearm', 'lorearm']):
        return 3  # Forearm + upper arm + collar bone

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

    # Spine/torso - medium chain
    if any(part in bone_lower for part in ['abdomen', 'chest', 'spine', 'pelvis']):
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


def create_ik_chain(armature, bone_name, chain_length=None):
    """
    Create IK chain with BONE targets and Copy Rotation constraints.

    Architecture:
    1. Create .ik control bones (have IK constraints)
    2. Create .ik.target bone (what you drag - no parent)
    3. Add Copy Rotation constraints from DAZ bones to .ik bones

    Returns: (target_bone_name, ik_control_bone_names, daz_bone_names)
    """
    # CRITICAL: Force update to ensure all manual rotations/transforms are applied
    # This captures any R rotations or G moves the user made between IK drags
    bpy.context.view_layer.update()

    if bone_name not in armature.pose.bones:
        print(f"✗ Bone '{bone_name}' not found")
        return None, None, None

    clicked_bone = armature.pose.bones[bone_name]

    # Determine chain length
    if chain_length is None:
        chain_length = get_smart_chain_length(bone_name)

    print(f"Creating IK chain for: {bone_name}")

    # ==================================================================
    # STEP 1: Collect non-twist, non-pectoral bones for the chain
    # ==================================================================
    daz_bones = []  # PoseBones
    current = clicked_bone

    # Walk up collecting bones (exclude twist and pectoral bones)
    while current and len(daz_bones) < chain_length:
        if not is_twist_bone(current.name) and not is_pectoral(current.name):
            daz_bones.append(current)
        current = current.parent

    if len(daz_bones) < 2:
        print(f"  ✗ Not enough bones for IK chain")
        return None, None, None

    # Reverse so we have root-to-tip order
    daz_bones = list(reversed(daz_bones))
    daz_bone_names = [b.name for b in daz_bones]

    print(f"  Chain: {' → '.join(daz_bone_names)}")

    # Detect collar bones in chain for Damped Track setup (prevents collar snapping)
    collar_bones = [name for name in daz_bone_names if 'collar' in name.lower() or 'clavicle' in name.lower()]
    if collar_bones:
        print(f"  Detected collar bones: {', '.join(collar_bones)} - will add Damped Track constraints")

    # ==================================================================
    # STEP 1.5: Capture current world position of clicked bone BEFORE entering EDIT mode
    # ==================================================================
    # CRITICAL: Get the CURRENT posed position, not rest position
    clicked_bone_world_head = armature.matrix_world @ clicked_bone.head
    clicked_bone_world_tail = armature.matrix_world @ clicked_bone.tail

    # ==================================================================
    # STEP 2: Switch to EDIT mode and create all bones
    # ==================================================================
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones

    ik_control_names = []
    prev_ik_edit = None

    # Create IK control bones with proper parent hierarchy
    for i, daz_pose_bone in enumerate(daz_bones):
        daz_edit = edit_bones[daz_pose_bone.name]

        # Create IK control bone
        ik_name = f"{daz_pose_bone.name}.ik"
        ik_edit = edit_bones.new(ik_name)

        # Copy transform from DAZ bone
        ik_edit.head = daz_edit.head.copy()
        ik_edit.tail = daz_edit.tail.copy()
        ik_edit.roll = daz_edit.roll
        ik_edit.use_deform = False  # Don't deform mesh

        # CRITICAL: Set parent to previous IK bone (creates chain)
        if prev_ik_edit:
            ik_edit.parent = prev_ik_edit
            # CRITICAL: Connect bones by adjusting previous bone's tail to this bone's head
            # This fixes disconnected bone issues (e.g., DAZ chest bones)
            prev_ik_edit.tail = ik_edit.head.copy()
            print(f"  Connected {prev_ik_edit.name} → {ik_name}")
        else:
            # Root bone - parent to DAZ parent (or None)
            if daz_edit.parent:
                # Find non-twist, non-pectoral parent
                anchor = daz_edit.parent
                while anchor and (is_twist_bone(anchor.name) or is_pectoral(anchor.name)):
                    anchor = anchor.parent
                ik_edit.parent = anchor
            else:
                ik_edit.parent = None

        ik_control_names.append(ik_name)
        prev_ik_edit = ik_edit

    # Create IK TARGET bone (what animator drags)
    # This has NO parent - free to move
    target_name = f"{bone_name}.ik.target"
    target_edit = edit_bones.new(target_name)

    # CRITICAL: Position at clicked bone's CURRENT world position (not rest position)
    # Convert world positions back to armature local space
    armature_inv = armature.matrix_world.inverted()
    target_edit.head = armature_inv @ clicked_bone_world_head
    target_edit.tail = armature_inv @ clicked_bone_world_tail

    # Copy roll from rest position (roll doesn't change with posing)
    clicked_edit = edit_bones[bone_name]
    target_edit.roll = clicked_edit.roll

    target_edit.parent = None  # CRITICAL: No parent for free movement
    target_edit.use_deform = False

    # Create shoulder target bones for collar guidance (prevents collar snapping)
    shoulder_target_names = []
    if collar_bones:
        for collar_name in collar_bones:
            shoulder_target_name = f"{collar_name}.shoulder.target"
            shoulder_target_edit = edit_bones.new(shoulder_target_name)

            # Position at collar's current world position
            collar_pose = daz_bones[daz_bone_names.index(collar_name)]
            collar_world_head = armature.matrix_world @ collar_pose.head
            collar_world_tail = armature.matrix_world @ collar_pose.tail

            shoulder_target_edit.head = armature_inv @ collar_world_head
            shoulder_target_edit.tail = armature_inv @ collar_world_tail
            shoulder_target_edit.roll = edit_bones[collar_name].roll
            shoulder_target_edit.parent = None  # Free to move
            shoulder_target_edit.use_deform = False

            shoulder_target_names.append(shoulder_target_name)
            print(f"  Created shoulder target: {shoulder_target_name}")

    # ==================================================================
    # STEP 3: Switch to POSE mode and copy initial pose
    # ==================================================================
    bpy.ops.object.mode_set(mode='POSE')

    # CRITICAL: Update after mode switch to ensure pose is current
    # This ensures any manual rotations (R key) are properly loaded
    bpy.context.view_layer.update()

    # CRITICAL: Get evaluated armature to read keyframed values
    # The raw armature.pose.bones don't include keyframe data
    # The evaluated depsgraph includes all keyframes and constraints
    depsgraph = bpy.context.evaluated_depsgraph_get()
    armature_eval = armature.evaluated_get(depsgraph)

    # CRITICAL: Copy the current pose (rotation + location) to prevent initial snap
    # This way, when Copy Rotation activates, nothing changes initially
    for i, (daz_name, ik_name) in enumerate(zip(daz_bone_names, ik_control_names)):
        # Read from EVALUATED bone (includes keyframes)
        daz_bone_eval = armature_eval.pose.bones[daz_name]
        # Write to RAW bone (we're setting it)
        daz_bone = armature.pose.bones[daz_name]
        ik_bone = armature.pose.bones[ik_name]

        # Copy location from evaluated bone
        ik_bone.location = daz_bone_eval.location.copy()

        # CRITICAL: Force QUATERNION mode for IK stability
        # Diffeomorphic recommends quaternions to prevent IK flipping
        # See: Diffeomorphic docs - "Use quaternions for stable IK chains"
        # This is a best practice from established addons (Diffeomorphic, RigOnTheFly)
        ik_bone.rotation_mode = 'QUATERNION'

        # CRITICAL: Read rotation from EVALUATED bone's matrix_basis
        # Evaluated bone includes keyframes and all animation data
        actual_rotation_quat = daz_bone_eval.matrix_basis.to_quaternion()
        ik_bone.rotation_quaternion = actual_rotation_quat.copy()

        # DEBUG: Log ALL bones rotation to diagnose popping
        print(f"  Bone {i}: {daz_name}")
        print(f"    DAZ eval quat: {actual_rotation_quat}")
        print(f"    Copied to .ik: {ik_bone.rotation_quaternion}")
        if i == len(daz_bone_names) - 1:
            print(f"    (TIP BONE - rotation locked, not copied back)")

        # CRITICAL: Copy IK rotation limits from DAZ bone to prevent unrealistic bending
        # This prevents backward-bending knees and excessive ankle rotation
        ik_bone.use_ik_limit_x = daz_bone.use_ik_limit_x
        ik_bone.use_ik_limit_y = daz_bone.use_ik_limit_y
        ik_bone.use_ik_limit_z = daz_bone.use_ik_limit_z

        if daz_bone.use_ik_limit_x:
            ik_bone.ik_min_x = daz_bone.ik_min_x
            ik_bone.ik_max_x = daz_bone.ik_max_x
        if daz_bone.use_ik_limit_y:
            ik_bone.ik_min_y = daz_bone.ik_min_y
            ik_bone.ik_max_y = daz_bone.ik_max_y
        if daz_bone.use_ik_limit_z:
            ik_bone.ik_min_z = daz_bone.ik_min_z
            ik_bone.ik_max_z = daz_bone.ik_max_z

        # Lock IK axes if DAZ bone has them locked
        ik_bone.lock_ik_x = daz_bone.lock_ik_x
        ik_bone.lock_ik_y = daz_bone.lock_ik_y
        ik_bone.lock_ik_z = daz_bone.lock_ik_z

        # PHASE 3: Ragdoll Pulling - IK Stiffness on Parent Bones Only
        # Apply MAXIMUM stiffness to essentially LOCK parent bones
        # They'll only move when IK solver absolutely can't find a solution (limb stretched past limits)
        # Middle joints (forearm, shin) stay at 0.0 to allow free bending
        stiffness = 0.0
        daz_name_lower = daz_name.lower()

        # Lock parent bones with near-maximum stiffness (0.99 ≈ locked)
        if 'collar' in daz_name_lower or 'clavicle' in daz_name_lower:
            stiffness = 0.75  # Collar: balanced stiffness - stable but not locked
        elif 'shldr' in daz_name_lower or 'shoulder' in daz_name_lower:
            stiffness = 0.1  # Shoulder: very flexible for natural arm movement
        elif 'chest' in daz_name_lower:
            stiffness = 0.99  # Chest: essentially locked, only moves when arm stretched far
        elif 'abdomen' in daz_name_lower or 'spine' in daz_name_lower:
            stiffness = 0.99  # Spine: essentially locked, only moves when arm stretched far
        elif 'hip' in daz_name_lower:
            # Hip is the root body controller - lock rotation, allow only translation
            stiffness = 0.99  # Essentially locked
            ik_bone.lock_ik_x = True
            ik_bone.lock_ik_y = True
            ik_bone.lock_ik_z = True
            print(f"  Locked hip IK rotation (translation only, prevents character spinning)")
        elif 'pelvis' in daz_name_lower:
            stiffness = 0.8  # Pelvis: high resistance

        if stiffness > 0:
            ik_bone.ik_stiffness_x = stiffness
            ik_bone.ik_stiffness_y = stiffness
            ik_bone.ik_stiffness_z = stiffness
            print(f"  IK stiffness: {daz_name} = {stiffness:.1f} (ragdoll parent)")

    # CRITICAL: Lock rotation on the TIP bone ONLY if it's an end effector (hand, foot)
    # This preserves user's manual R rotations on hands/feet
    # Mid-limb bones (shoulder, forearm, collar) should NOT be locked as tip
    tip_bone = armature.pose.bones[ik_control_names[-1]]
    tip_bone_daz_name = daz_bone_names[-1]
    tip_lower = tip_bone_daz_name.lower()
    is_end_effector = any(part in tip_lower for part in ['hand', 'foot'])

    if is_end_effector:
        tip_bone.lock_ik_x = True
        tip_bone.lock_ik_y = True
        tip_bone.lock_ik_z = True
        print(f"  Locked tip bone rotation (end effector): {tip_bone.name}")
    else:
        print(f"  Tip bone rotation unlocked (mid-limb can rotate): {tip_bone.name}")

    # NOTE: Intentionally NOT copying Limit Rotation constraints to IK limits
    # Reason: IK limits constrain the solver during solving (can prevent solutions)
    #         Limit Rotation constraints clamp AFTER solving (better for IK)
    # The workflow is:
    #   1. IK solves freely on .ik bones (except tip rotation is locked)
    #   2. Copy Rotation copies result to DAZ bones
    #   3. DAZ bones' Limit Rotation constraints clamp the final result
    # This gives the IK solver freedom while still respecting joint limits on final pose

    # DON'T apply nudge during chain creation - causes first grab issues
    # Instead, nudge will be applied on first mouse move after IK is active
    # This avoids initialization/evaluation timing issues
    print(f"  Nudge will be applied on first mouse move (after IK active)")

    bpy.context.view_layer.update()

    # Add IK constraint to the LAST IK control bone (the one closest to clicked bone)
    ik_tip_name = ik_control_names[-1]
    ik_tip_pose = armature.pose.bones[ik_tip_name]

    ik_constraint = ik_tip_pose.constraints.new('IK')
    ik_constraint.name = "IK_Temp"
    ik_constraint.target = armature  # CRITICAL: Target is ARMATURE
    ik_constraint.subtarget = target_name  # CRITICAL: Subtarget is BONE NAME
    ik_constraint.chain_count = len(ik_control_names)
    ik_constraint.use_tail = True
    ik_constraint.use_stretch = True  # Allow stretching
    ik_constraint.use_rotation = False
    ik_constraint.iterations = 500
    # Explicitly set spaces to WORLD (matching Diffeomorphic)
    ik_constraint.target_space = 'WORLD'
    ik_constraint.owner_space = 'WORLD'
    # CRITICAL: Start IK disabled - activate on first mouse move to prevent initial pop
    ik_constraint.influence = 0.0

    # ==================================================================
    # STEP 4: Add Copy Rotation constraints from DAZ bones to IK bones
    # ==================================================================
    # CRITICAL: Exclude the TIP bone from Copy Rotation
    # We want IK to control middle bones (knee, elbow) but NOT the tip (foot, hand)
    # This preserves the tip's manual rotation (from R key) while IK controls the chain

    for i, (daz_name, ik_name) in enumerate(zip(daz_bone_names, ik_control_names)):
        # Skip Copy Rotation for tip bone ONLY if it's an end effector (hand, foot)
        # Mid-limb bones (shoulder, forearm, collar) should get Copy Rotation even as tip
        if i == len(daz_bone_names) - 1:
            daz_lower = daz_name.lower()
            is_end_effector = any(part in daz_lower for part in ['hand', 'foot'])
            if is_end_effector:
                print(f"  Skipping Copy Rotation for tip bone (end effector): {daz_name}")
                continue
            else:
                print(f"  Adding Copy Rotation for tip bone (mid-limb): {daz_name}")

        daz_pose = armature.pose.bones[daz_name]

        # Add Copy Rotation constraint
        copy_rot = daz_pose.constraints.new('COPY_ROTATION')
        copy_rot.name = "IK_CopyRot_Temp"
        copy_rot.target = armature
        copy_rot.subtarget = ik_name  # Copy from IK control bone
        copy_rot.target_space = 'LOCAL'  # Copy in local space!
        copy_rot.owner_space = 'LOCAL'   # Apply in local space!
        copy_rot.influence = 0.0  # Start disabled - activate WITH IK on first mouse move

        # CRITICAL: Move Copy Rotation to TOP of constraint stack (index 0)
        # This ensures it runs BEFORE Limit Rotation, so limits can clamp the result
        # Order: Copy Rotation (copies IK result) → Limit Rotation (clamps to joint limits)
        daz_pose.constraints.move(len(daz_pose.constraints) - 1, 0)

    # ==================================================================
    # STEP 4.5: Add Damped Track constraints on collar bones (prevents snapping)
    # ==================================================================
    # Collar bones get Damped Track pointing to shoulder targets
    # This guides collar rotation naturally based on arm movement
    for collar_name in collar_bones:
        collar_pose = armature.pose.bones[collar_name]
        shoulder_target_name = f"{collar_name}.shoulder.target"

        # Add Damped Track constraint
        damped_track = collar_pose.constraints.new('DAMPED_TRACK')
        damped_track.name = "Shoulder_Track_Temp"
        damped_track.target = armature
        damped_track.subtarget = shoulder_target_name
        damped_track.track_axis = 'TRACK_Y'  # Collar length axis
        damped_track.influence = 0.0  # Start disabled - activate WITH IK on first mouse move

        print(f"  Added Damped Track on {collar_name} → {shoulder_target_name}")

    # POLISH: Add Damped Track for head bones to make Y axis (top of head) point at target
    # This makes the head orient naturally towards where you're dragging
    tip_daz_bone = armature.pose.bones[daz_bone_names[-1]]
    if 'head' in tip_daz_bone.name.lower():
        track = tip_daz_bone.constraints.new('DAMPED_TRACK')
        track.name = "IK_HeadTrack_Temp"
        track.target = armature
        track.subtarget = target_name  # Point at .ik.target
        track.track_axis = 'TRACK_Y'  # Y axis (top of head) points at target
        track.influence = 1.0
        print(f"  Added head tracking constraint (Y axis → target)")

    # Force update
    bpy.context.view_layer.update()

    print(f"  ✓ IK chain ready")

    return target_name, ik_control_names, daz_bone_names, shoulder_target_names


def copy_rotation_temp_to_real(armature, temp_bone_names, real_bone_names):
    """Copy rotations from temp IK bones to real bones"""
    for temp_name, real_name in zip(temp_bone_names, real_bone_names):
        temp_bone = armature.pose.bones.get(temp_name)
        real_bone = armature.pose.bones.get(real_name)

        if temp_bone and real_bone:
            # Copy rotation from temp to real
            if real_bone.rotation_mode == 'QUATERNION':
                real_bone.rotation_quaternion = temp_bone.rotation_quaternion.copy()
            else:
                real_bone.rotation_euler = temp_bone.rotation_euler.copy()


def dissolve_ik_chain(armature, target_bone_name, ik_control_names, daz_bone_names, shoulder_target_names=None, keyframe=True):
    """
    Remove IK chain: optionally keyframe DAZ bones, delete Copy Rotation constraints, delete .ik bones.
    CRITICAL: Keyframe BEFORE removing constraints to capture the constrained pose!

    Args:
        shoulder_target_names: List of shoulder target bone names (for collar Damped Track)
        keyframe: If False, skip keyframing (used for canceling/right-click)
    """
    if shoulder_target_names is None:
        shoulder_target_names = []
    # STEP 1: Keyframe DAZ bones FIRST (while constraints are still active!)
    # This captures the constrained pose using visual keying
    if keyframe:
        current_frame = bpy.context.scene.frame_current

        # Force one final update to ensure constraints are evaluated
        bpy.context.view_layer.update()

        for i, daz_name in enumerate(daz_bone_names):
            bone = armature.pose.bones.get(daz_name)
            if not bone:
                continue

            # CRITICAL: Skip keyframing the TIP bone (last in chain)
            # The tip bone has no Copy Rotation constraint, so keyframing it locks it at rest pose
            # By NOT keyframing it, manual R rotations stick to the bone property
            if i == len(daz_bone_names) - 1:
                print(f"  Skipping keyframe for tip bone: {daz_name} (preserves manual rotations)")
                continue

            # Insert visual rotation keyframe (captures constraint result)
            if bone.rotation_mode == 'QUATERNION':
                bone.keyframe_insert(
                    data_path="rotation_quaternion",
                    frame=current_frame,
                    options={'INSERTKEY_VISUAL'}
                )
            else:
                bone.keyframe_insert(
                    data_path="rotation_euler",
                    frame=current_frame,
                    options={'INSERTKEY_VISUAL'}
                )

            # TEMP: Disable location keyframing to debug snapping issue
            # For IK chains, world position is determined by parent rotations
            # loc_magnitude = bone.location.length
            # if loc_magnitude > 0.001:
            #     bone.keyframe_insert(
            #         data_path="location",
            #         frame=current_frame,
            #         options={'INSERTKEY_VISUAL'}
            #     )

    # STEP 2: NOW remove Copy Rotation constraints (after keyframing)
    for daz_name in daz_bone_names:
        daz_bone = armature.pose.bones.get(daz_name)
        if not daz_bone:
            continue

        # Remove all temporary IK constraints
        constraints_to_remove = [c for c in daz_bone.constraints if c.name in ("IK_CopyRot_Temp", "IK_HeadTrack_Temp", "Shoulder_Track_Temp")]
        for c in constraints_to_remove:
            daz_bone.constraints.remove(c)

    bpy.context.view_layer.update()

    # STEP 3: Delete .ik control bones and .ik.target bone
    # CRITICAL: Ensure armature is active before mode switch
    if bpy.context.view_layer.objects.active != armature:
        bpy.context.view_layer.objects.active = armature

    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones

    # Delete IK control bones
    for ik_name in ik_control_names:
        if ik_name in edit_bones:
            edit_bones.remove(edit_bones[ik_name])

    # Delete target bone
    if target_bone_name in edit_bones:
        edit_bones.remove(edit_bones[target_bone_name])

    # Delete shoulder target bones
    for shoulder_target_name in shoulder_target_names:
        if shoulder_target_name in edit_bones:
            edit_bones.remove(edit_bones[shoulder_target_name])
            print(f"  Removed shoulder target: {shoulder_target_name}")

    bpy.ops.object.mode_set(mode='POSE')
    bpy.context.view_layer.update()


# ============================================================================
# PIN SYSTEM - Helper Functions
# ============================================================================

def get_bone_world_matrix(armature, bone_name):
    """Get the world matrix of a bone"""
    if bone_name in armature.pose.bones:
        pose_bone = armature.pose.bones[bone_name]
        return armature.matrix_world @ pose_bone.matrix
    return None


def is_bone_pinned_translation(bone):
    """Check if bone has translation pin"""
    return bone.get("daz_pin_translation", False)


def is_bone_pinned_rotation(bone):
    """Check if bone has rotation pin"""
    return bone.get("daz_pin_rotation", False)


def get_pin_status_text(bone):
    """Get human-readable pin status"""
    trans = is_bone_pinned_translation(bone)
    rot = is_bone_pinned_rotation(bone)

    if trans and rot:
        return "PINNED: Translation + Rotation"
    elif trans:
        return "PINNED: Translation"
    elif rot:
        return "PINNED: Rotation"
    else:
        return ""


def pin_bone_translation(armature, bone_name):
    """Mark bone as translation pinned and store world location"""
    bone = armature.data.bones.get(bone_name)
    if not bone:
        return False

    # Get current world location
    world_matrix = get_bone_world_matrix(armature, bone_name)
    if world_matrix:
        world_location = world_matrix.to_translation()

        # Store pin data
        bone["daz_pin_translation"] = True
        bone["daz_pin_location"] = world_location

        print(f"  ✓ Pinned Translation: {bone_name} at {world_location}")
        return True
    return False


def pin_bone_rotation(armature, bone_name):
    """Mark bone as rotation pinned and store world rotation"""
    bone = armature.data.bones.get(bone_name)
    if not bone:
        return False

    # Get current world rotation
    world_matrix = get_bone_world_matrix(armature, bone_name)
    if world_matrix:
        world_rotation = world_matrix.to_euler()

        # Store pin data
        bone["daz_pin_rotation"] = True
        bone["daz_pin_rotation_euler"] = world_rotation

        print(f"  ✓ Pinned Rotation: {bone_name} at {world_rotation}")
        return True
    return False


def unpin_bone(armature, bone_name):
    """Remove all pins from bone"""
    bone = armature.data.bones.get(bone_name)
    if not bone:
        return False

    # Remove pin properties
    had_pins = False
    if "daz_pin_translation" in bone:
        del bone["daz_pin_translation"]
        if "daz_pin_location" in bone:
            del bone["daz_pin_location"]
        had_pins = True

    if "daz_pin_rotation" in bone:
        del bone["daz_pin_rotation"]
        if "daz_pin_rotation_euler" in bone:
            del bone["daz_pin_rotation_euler"]
        had_pins = True

    if had_pins:
        print(f"  ✓ Unpinned: {bone_name}")
        return True
    return False


class VIEW3D_OT_daz_bone_select(bpy.types.Operator):
    """Hover to preview bone, click to select"""
    bl_idname = "view3d.daz_bone_select"
    bl_label = "DAZ Bone Select"
    bl_options = {'REGISTER', 'UNDO'}

    # Store current hover state
    _last_bone = ""
    _hover_mesh = None
    _hover_bone_name = None
    _hover_armature = None
    _base_body_mesh = None  # The main figure mesh (detected automatically)

    # Click detection to ignore gizmo drags
    _mouse_down_pos = None
    _click_threshold = 5  # pixels - if mouse moves more than this, it's a drag not a click

    # IK drag state
    _is_dragging = False
    _drag_bone_name = None
    _drag_armature = None
    _ik_constraint = None
    _ik_target = None
    _ik_constrained_bone_name = None  # Temp bone that has the IK constraint
    _ik_temp_bone_names = None  # List of temp bone names
    _ik_real_bone_names = None  # List of real bone names (corresponding to temp bones)
    _drag_plane_normal = None  # View direction for depth calculation
    _drag_plane_point = None   # 3D point for depth calculation

    # Rotation drag state (for pectoral bones)
    _is_rotating = False
    _rotation_bone = None
    _rotation_initial_quat = None
    _rotation_initial_mouse = None

    # Undo stack for Ctrl+Z
    _undo_stack = []  # List of {frame, bones: [(name, rotation, mode)]} entries

    # GPU draw handler for highlighting
    _draw_handler = None
    _highlight_cache = {}  # Cache of {(mesh_name, bone_name): [triangle_verts]} for performance
    _last_highlighted_bone = None  # Track when to rebuild cache

    def modal(self, context, event):
        """Handle mouse events"""

        if event.type == 'MOUSEMOVE':
            # Debug: Check state
            if self._is_dragging:
                print(f"  [MODAL] MOUSEMOVE while dragging")
            # Check if we should start IK drag or rotation
            if not self._is_dragging and not self._is_rotating and self._mouse_down_pos and self._drag_bone_name:
                mouse_pos = (event.mouse_region_x, event.mouse_region_y)
                distance = ((mouse_pos[0] - self._mouse_down_pos[0])**2 +
                           (mouse_pos[1] - self._mouse_down_pos[1])**2)**0.5

                # If moved beyond threshold, start IK drag
                if distance > self._click_threshold:
                    self.start_ik_drag(context, event)

                # Consume event during detection phase to prevent box select
                return {'RUNNING_MODAL'}

            # If dragging IK, update IK target position
            if self._is_dragging:
                self.update_ik_drag(context, event)
                return {'RUNNING_MODAL'}

            # If rotating (pectoral bones), update rotation
            if self._is_rotating:
                self.update_rotation(context, event)
                return {'RUNNING_MODAL'}

            # Otherwise update hover preview
            self.check_hover(context, event)
            return {'PASS_THROUGH'}

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            # Pass through if clicking on UI regions (header, toolbar, etc.)
            region = context.region
            if region:
                mouse_y = event.mouse_region_y
                mouse_x = event.mouse_region_x

                # If clicking in header area or outside bounds, pass through
                if mouse_y > region.height - 40 or mouse_y < 0 or mouse_x < 0 or mouse_x > region.width:
                    self._mouse_down_pos = None
                    return {'PASS_THROUGH'}

            # Only handle click if we're hovering over a bone (otherwise pass through for gizmos)
            if not self._hover_bone_name or not self._hover_armature:
                self._mouse_down_pos = None
                return {'PASS_THROUGH'}

            # Do a fresh raycast to verify we hit mesh (not clicking through to background)
            region = context.region
            rv3d = context.space_data.region_3d
            coord = (event.mouse_region_x, event.mouse_region_y)
            view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
            ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)

            # Try to hit mesh
            hit_mesh = False
            for obj in context.scene.objects:
                if obj.type == 'MESH':
                    result, location, normal, index = obj.ray_cast(
                        obj.matrix_world.inverted() @ ray_origin,
                        obj.matrix_world.inverted().to_3x3() @ view_vector
                    )
                    if result:
                        hit_mesh = True
                        break

            # If we didn't hit any mesh, pass through (clicking empty space)
            if not hit_mesh:
                self._mouse_down_pos = None
                return {'PASS_THROUGH'}

            # Record mouse position on press (to detect drags vs clicks)
            self._mouse_down_pos = (event.mouse_region_x, event.mouse_region_y)

            # Hovering over a bone - prepare for potential drag
            if self._hover_bone_name and self._hover_armature:
                # Select bone immediately (don't wait for release)
                # This allows click-drag to work in one motion
                self.select_bone(context)

                # Prepare for potential drag
                self._drag_bone_name = self._hover_bone_name
                self._drag_armature = self._hover_armature

                # Consume event to prevent box select
                return {'RUNNING_MODAL'}

            return {'PASS_THROUGH'}

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            # End rotation if active
            if self._is_rotating:
                self.end_rotation(context, cancel=False)
                return {'RUNNING_MODAL'}

            # End IK drag if active (with keyframing)
            if self._is_dragging:
                self.end_ik_drag(context, cancel=False)
                return {'RUNNING_MODAL'}

            # Clear drag preparation state
            if self._drag_bone_name:
                self._drag_bone_name = None
                self._drag_armature = None

            # Clear mouse tracking
            self._mouse_down_pos = None

            return {'PASS_THROUGH'}

        elif event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            # Cancel rotation if active
            if self._is_rotating:
                print("  Right-click: Canceling rotation")
                self.end_rotation(context, cancel=True)
                return {'RUNNING_MODAL'}

            # Cancel IK drag if active (no keyframing, returns to original pose)
            if self._is_dragging:
                print("  Right-click: Canceling IK drag")
                self.end_ik_drag(context, cancel=True)
                return {'RUNNING_MODAL'}

            # Clear drag preparation state
            if self._drag_bone_name:
                self._drag_bone_name = None
                self._drag_armature = None
                self._mouse_down_pos = None

            return {'PASS_THROUGH'}

        elif event.type == 'G' and event.value == 'PRESS':
            # G key: Start IK drag on selected bone (like Blender's grab but with IK)
            if context.mode == 'POSE' and context.active_bone:
                active_bone_name = context.active_bone.name
                armature = context.active_object

                if armature and armature.type == 'ARMATURE':
                    print(f"\n=== G Key: Starting IK Drag on {active_bone_name} ===")

                    # Set up for IK drag
                    self._drag_bone_name = active_bone_name
                    self._drag_armature = armature
                    self._mouse_down_pos = (event.mouse_region_x, event.mouse_region_y)

                    # Start IK drag immediately
                    self.start_ik_drag(context, event)

                    # Consume event to prevent Blender's grab operator
                    return {'RUNNING_MODAL'}

            return {'PASS_THROUGH'}

        elif event.type == 'P' and event.value == 'PRESS':
            # Pin selected bone
            if event.shift:
                # Shift+P: Pin rotation
                self.pin_selected_bone_rotation(context)
            else:
                # P: Pin translation
                self.pin_selected_bone_translation(context)
            return {'RUNNING_MODAL'}

        elif event.type == 'U' and event.value == 'PRESS':
            # U: Unpin selected bone
            self.unpin_selected_bone(context)
            return {'RUNNING_MODAL'}

        elif event.type == 'Z' and event.value == 'PRESS' and event.ctrl:
            # Ctrl+Z: Undo last drag or rotation
            self.undo_last_drag(context)
            # Force viewport refresh
            refresh_3d_viewports(context)
            return {'RUNNING_MODAL'}

        elif event.type == 'ESC' and event.value == 'PRESS':
            # Exit on ESC only
            self.finish(context)
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        """Start the operator"""
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Must be in 3D View")
            return {'CANCELLED'}

        # Initialize state
        self._last_bone = ""
        self._hover_mesh = None
        self._hover_bone_name = None
        self._hover_armature = None
        self._base_body_mesh = None
        self._mouse_down_pos = None

        # Initialize IK drag state
        self._is_dragging = False
        self._drag_bone_name = None
        self._drag_armature = None
        # NEW: Using bone names instead of constraint/empty objects
        self._ik_target_bone_name = None
        self._ik_control_bone_names = []
        self._ik_daz_bone_names = []
        self._shoulder_target_names = []  # Shoulder targets for collar Damped Track
        self._drag_plane_normal = None
        self._drag_plane_point = None
        self._drag_depth_reference = None  # Fixed depth for raycast consistency
        self._drag_initial_target_pos = None  # Initial target bone position (for delta-based movement)
        self._drag_initial_mouse_pos = None  # Initial mouse position (for delta-based movement)

        # Initialize rotation state (for pectoral bones)
        self._is_rotating = False
        self._rotation_bone = None
        self._rotation_initial_quat = None
        self._rotation_initial_mouse = None

        # Initialize undo stack
        self._undo_stack = []

        # Try to detect base body mesh from active armature
        if context.active_object and context.active_object.type == 'ARMATURE':
            self._base_body_mesh = find_base_body_mesh(context, context.active_object)
            if self._base_body_mesh:
                print(f"  Using base mesh: {self._base_body_mesh.name}")

        # Start modal
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set("DAZ Bone Select Active - Click to select, P to pin, ESC to exit")

        # Register draw handler for highlighting
        self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_highlight_callback, (), 'WINDOW', 'POST_VIEW'
        )

        print("\n=== DAZ Bone Select & Pin & IK Started ===")
        print("  Hover over mesh to preview bone")
        print("  Left-click to select bone")
        print("  Click-drag selected bone for IK posing")
        print("  P - Pin Translation")
        print("  Shift+P - Pin Rotation")
        print("  U - Unpin")
        print("  ESC to exit")
        return {'RUNNING_MODAL'}

    def finish(self, context):
        """Cleanup and exit"""
        context.area.header_text_set(None)
        self._last_bone = ""
        self._hover_mesh = None
        self._hover_bone_name = None
        self._hover_armature = None

        # Remove draw handler
        if self._draw_handler:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            self._draw_handler = None

        # Clear highlight cache
        self._highlight_cache.clear()
        self._last_highlighted_bone = None

        print("=== DAZ Bone Select & Pin Stopped ===\n")

    def check_hover(self, context, event):
        """Check what's under mouse using dual raycast (prioritizes body mesh)"""

        # Skip hover check if mouse is over UI regions (header, toolbar, etc.)
        # This prevents interference with UI elements like transform orientation dropdown
        region = context.region
        if region:
            # Check if mouse is in viewport area (not over UI)
            mouse_x = event.mouse_region_x
            mouse_y = event.mouse_region_y

            # If mouse Y is at top (header area) or negative, skip
            if mouse_y > region.height - 40 or mouse_y < 0:
                return

            # If mouse X is at edges (sidebars), skip
            if mouse_x < 0 or mouse_x > region.width:
                return

        # Skip hover check if mouse is near active bone's gizmo
        # This prevents selection changes when manipulating gizmos
        if context.active_bone and context.mode == 'POSE':
            region = context.region
            rv3d = context.space_data.region_3d

            # Get 2D screen position of active bone
            armature = context.active_object
            if armature and armature.type == 'ARMATURE':
                bone_world_pos = armature.matrix_world @ context.active_bone.head
                bone_screen_pos = view3d_utils.location_3d_to_region_2d(
                    region, rv3d, bone_world_pos
                )

                if bone_screen_pos:
                    # Check if mouse is within gizmo radius (approximately 75 pixels)
                    mouse_x = event.mouse_region_x
                    mouse_y = event.mouse_region_y
                    distance = ((mouse_x - bone_screen_pos.x)**2 +
                               (mouse_y - bone_screen_pos.y)**2)**0.5

                    if distance < 75:  # Within gizmo interaction area
                        # Don't update hover - let gizmo handle events
                        return

        # Get viewport and mouse coords
        region = context.region
        rv3d = context.space_data.region_3d
        coord = (event.mouse_region_x, event.mouse_region_y)

        # Get ray from mouse
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)

        # RAYCAST 1: Scene raycast - gets closest mesh (might be clothing/hair)
        result = context.scene.ray_cast(
            context.view_layer.depsgraph,
            ray_origin,
            view_vector
        )

        success, location, normal, index, obj, matrix = result

        closest_mesh = obj
        closest_location = location
        closest_distance = (location - ray_origin).length if success and location else float('inf')

        # RAYCAST 2: Check base body mesh specifically (if available and not already hit)
        body_mesh = None
        body_location = None
        body_distance = float('inf')

        if self._base_body_mesh and closest_mesh != self._base_body_mesh:
            body_location, body_distance = raycast_specific_mesh(
                self._base_body_mesh,
                ray_origin,
                view_vector,
                context
            )
            if body_location:
                body_mesh = self._base_body_mesh
                body_distance = (body_location - ray_origin).length

        # PRIORITY LOGIC: Choose which hit to use
        # Prioritize body if it's behind clothing (increased threshold for poofy dresses)
        final_mesh = None
        final_location = None

        if body_mesh and body_location:
            # We hit both clothing and body
            distance_difference = body_distance - closest_distance

            if distance_difference < 1.0:  # Body is behind clothing (generous threshold for distant clothing)
                final_mesh = body_mesh
                final_location = body_location
                # print(f"  Prioritizing body mesh (distance diff: {distance_difference:.3f})")
            else:
                final_mesh = closest_mesh
                final_location = closest_location
        elif success and closest_mesh:
            # Only hit closest mesh (might be clothing or body)
            final_mesh = closest_mesh
            final_location = closest_location
        elif body_mesh:
            # Only hit body
            final_mesh = body_mesh
            final_location = body_location

        # Get face index from scene raycast (if available)
        face_index = index if success and closest_mesh == final_mesh else None

        # Process the final hit
        if final_mesh and final_mesh.type == 'MESH' and final_location:
            # Find the bone from the hit (pass face index for better accuracy)
            bone_info = self.get_bone_from_hit(final_mesh, final_location, face_index)

            if bone_info:
                mesh_name, bone_name, armature = bone_info

                # Update hover state
                self._hover_mesh = final_mesh
                self._hover_bone_name = bone_name
                self._hover_armature = armature

                # Update header (only if changed to reduce flicker)
                if bone_name != self._last_bone:
                    text = f"Hover: {bone_name} | Mesh: {mesh_name} | Armature: {armature.name} | CLICK to select"
                    context.area.header_text_set(text)
                    self._last_bone = bone_name
                    context.area.tag_redraw()  # Redraw to update highlight
            else:
                # Hit mesh but no bone found
                self.clear_hover(context)
        else:
            # No hit
            self.clear_hover(context)

    def clear_hover(self, context):
        """Clear hover state"""
        if self._last_bone:
            context.area.header_text_set("DAZ Bone Select Active - Click to select | P to pin | U to unpin | ESC to exit")
            self._last_bone = ""
            self._hover_mesh = None
            self._hover_bone_name = None
            self._hover_armature = None
            context.area.tag_redraw()  # Redraw to clear highlight

    def get_bone_from_hit(self, mesh_obj, hit_location, face_index=None):
        """Find the bone at hit location using hit polygon for better accuracy"""

        # Find armature
        armature = None
        for mod in mesh_obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object:
                armature = mod.object
                break

        if not armature:
            if mesh_obj.parent and mesh_obj.parent.type == 'ARMATURE':
                armature = mesh_obj.parent

        if not armature:
            return None

        mesh = mesh_obj.data

        # METHOD 1: Use hit polygon vertices (most accurate)
        if face_index is not None and face_index < len(mesh.polygons):
            polygon = mesh.polygons[face_index]

            # Collect all bone weights from all vertices in this polygon
            bone_weights = {}  # {bone_index: total_weight}

            for vert_idx in polygon.vertices:
                if vert_idx < len(mesh.vertices):
                    vertex = mesh.vertices[vert_idx]

                    for group in vertex.groups:
                        bone_idx = group.group
                        weight = group.weight

                        if bone_idx in bone_weights:
                            bone_weights[bone_idx] += weight
                        else:
                            bone_weights[bone_idx] = weight

            # Find bone with highest total weight for this polygon
            if bone_weights:
                max_group_idx = max(bone_weights, key=bone_weights.get)

                # Get bone name from vertex group
                if max_group_idx < len(mesh_obj.vertex_groups):
                    vgroup = mesh_obj.vertex_groups[max_group_idx]
                    bone_name = vgroup.name

                    # Check bone exists in armature
                    if bone_name in armature.data.bones:
                        # Map hand/foot palm/sole bones to parent hand/foot
                        bone_name_lower = bone_name.lower()
                        if any(term in bone_name_lower for term in ['metacarpal', 'metatarsal', 'carpal', 'tarsal']):
                            # Find parent bone (should be hand or foot)
                            parent_bone = armature.data.bones[bone_name].parent
                            if parent_bone:
                                bone_name = parent_bone.name
                                print(f"  Mapped palm/sole bone to parent: {bone_name}")

                        return (mesh_obj.name, bone_name, armature)

        # METHOD 2: Fallback to nearest vertex (if no face index)
        matrix_inv = mesh_obj.matrix_world.inverted()
        hit_local = matrix_inv @ hit_location

        min_dist = float('inf')
        nearest_vert_idx = None

        for i, vert in enumerate(mesh.vertices):
            dist = (vert.co - hit_local).length
            if dist < min_dist:
                min_dist = dist
                nearest_vert_idx = i

        if nearest_vert_idx is None:
            return None

        # Get vertex groups
        vert = mesh.vertices[nearest_vert_idx]

        if not vert.groups:
            return None

        # Find highest weight group
        max_weight = 0.0
        max_group_idx = None

        for g in vert.groups:
            if g.weight > max_weight:
                max_weight = g.weight
                max_group_idx = g.group

        if max_group_idx is None:
            return None

        # Get bone name from vertex group
        if max_group_idx < len(mesh_obj.vertex_groups):
            vgroup = mesh_obj.vertex_groups[max_group_idx]
            bone_name = vgroup.name

            # Check bone exists in armature
            if bone_name in armature.data.bones:
                # Map hand/foot palm/sole bones to parent hand/foot
                bone_name_lower = bone_name.lower()
                if any(term in bone_name_lower for term in ['metacarpal', 'metatarsal', 'carpal', 'tarsal']):
                    # Find parent bone (should be hand or foot)
                    parent_bone = armature.data.bones[bone_name].parent
                    if parent_bone:
                        bone_name = parent_bone.name
                        print(f"  Mapped palm/sole bone to parent: {bone_name}")

                return (mesh_obj.name, bone_name, armature)

        return None

    def select_bone(self, context):
        """Select the hovered bone in pose mode (with mapping for metatarsals/metacarpals)"""

        if not self._hover_armature or not self._hover_bone_name:
            return

        armature = self._hover_armature
        bone_name = self._hover_bone_name

        # Apply bone mapping (metatarsals → foot, carpals → hand)
        mapped_bone = get_ik_target_bone(armature, bone_name)
        if mapped_bone and mapped_bone != bone_name:
            print(f"\n=== Selecting Bone: {bone_name} (mapped to {mapped_bone}) ===")
            bone_name = mapped_bone
        else:
            print(f"\n=== Selecting Bone: {bone_name} ===")

        # Switch to the armature if needed
        if context.active_object != armature:
            print(f"  Switching active object to: {armature.name}")
            bpy.ops.object.select_all(action='DESELECT')
            armature.select_set(True)
            context.view_layer.objects.active = armature

        # Enter pose mode if not already
        if context.mode != 'POSE':
            print(f"  Switching to Pose Mode")
            bpy.ops.object.mode_set(mode='POSE')

        # Deselect all bones
        bpy.ops.pose.select_all(action='DESELECT')

        # Select the target bone
        if bone_name in armature.pose.bones:
            # Make the armature active
            context.view_layer.objects.active = armature

            # CRITICAL: Check if bone is already active and selected
            # If so, skip mode switching to preserve pose (especially manual R rotations)
            bone_already_active = (context.active_bone and
                                  context.active_bone.name == bone_name)

            if bone_already_active:
                print(f"  ✓ Bone already active: {bone_name} (skipping mode switch to preserve pose)")
            else:
                # Deselect all bones first using operator
                bpy.ops.pose.select_all(action='DESELECT')

                # Set the active bone
                armature.data.bones.active = armature.data.bones[bone_name]

                # Force selection by switching to edit mode and back
                # This is a workaround for bones that don't have direct select attribute
                current_mode = context.mode

                try:
                    # Go to edit mode
                    bpy.ops.object.mode_set(mode='EDIT')

                    # Select the bone in edit mode
                    edit_bone = armature.data.edit_bones.get(bone_name)
                    if edit_bone:
                        # Deselect all
                        for eb in armature.data.edit_bones:
                            eb.select = False
                            eb.select_head = False
                            eb.select_tail = False

                        # Select our bone
                        edit_bone.select = True
                        edit_bone.select_head = True
                        edit_bone.select_tail = True

                        print(f"  ✓ Selected in edit mode: {bone_name}")

                    # Go back to pose mode
                    bpy.ops.object.mode_set(mode='POSE')

                    # Set active again in pose mode
                    armature.data.bones.active = armature.data.bones[bone_name]

                    print(f"  ✓ Selected bone: {bone_name}")

                except Exception as e:
                    print(f"  ✗ Selection error: {e}")
                    # Make sure we end up in pose mode
                    if context.mode != 'POSE':
                        bpy.ops.object.mode_set(mode='POSE')

            # Update view
            context.view_layer.update()
            context.area.tag_redraw()

            self.report({'INFO'}, f"Selected: {bone_name}")

            # Update header to confirm
            text = f"SELECTED: {bone_name} | Hover and click to select another bone"
            context.area.header_text_set(text)
        else:
            print(f"  ✗ Bone not found in armature: {bone_name}")

    def start_ik_drag(self, context, event):
        """Start IK drag on the selected bone"""
        if not self._drag_bone_name or not self._drag_armature:
            return

        print(f"\n=== Starting IK Drag: {self._drag_bone_name} ===")

        # Map to IK-appropriate bone (e.g., carpal → hand, face → head)
        ik_bone_name = get_ik_target_bone(self._drag_armature, self._drag_bone_name)

        # If bone shouldn't use IK, check if it's a pectoral (use rotation mode)
        if not ik_bone_name:
            # Pectoral bones: Start rotation mode instead of IK
            if is_pectoral(self._drag_bone_name):
                print("  → Pectoral bone: Starting rotation mode")
                context.area.header_text_set(f"{self._drag_bone_name} - Drag to rotate | Release to apply")

                # Get the bone
                bone = self._drag_armature.pose.bones[self._drag_bone_name]

                # Force quaternion mode
                bone.rotation_mode = 'QUATERNION'

                # Store initial state
                self._is_rotating = True
                self._rotation_bone = bone
                self._rotation_initial_quat = bone.rotation_quaternion.copy()
                self._rotation_initial_mouse = (event.mouse_x, event.mouse_y)

                # Clear drag bone name (rotation is now active)
                # Keep _drag_armature for undo system
                self._drag_bone_name = None

                print(f"  Initial rotation: {self._rotation_initial_quat}")
                return
            else:
                # Other non-IK bones (twist bones, etc.): abort
                print("  ✗ Bone not suitable for IK drag")
                context.area.header_text_set(f"{self._drag_bone_name} - Not IK-draggable (use gizmo to rotate)")
                self._drag_bone_name = None
                self._drag_armature = None
                return

        # Use the mapped bone for IK
        self._drag_bone_name = ik_bone_name

        # Create IK chain with temp bones (bypasses twist bones for clean IK)
        result = create_ik_chain(
            self._drag_armature,
            self._drag_bone_name
            # chain_length will be auto-detected
        )

        if not result or result[0] is None:
            print("  ✗ Failed to create IK chain")
            return

        # NEW: Unpack the 4 return values from create_ik_chain
        target_bone_name, ik_control_names, daz_bone_names, shoulder_target_names = result

        # Store bone names
        self._ik_target_bone_name = target_bone_name
        self._ik_control_bone_names = ik_control_names
        self._ik_daz_bone_names = daz_bone_names
        self._shoulder_target_names = shoulder_target_names  # For collar Damped Track

        # Store view direction for depth calculation
        region = context.region
        rv3d = context.space_data.region_3d
        self._drag_plane_normal = rv3d.view_rotation @ Vector((0, 0, -1))

        # Get target bone's world location as the FIXED drag depth reference
        target_bone = self._drag_armature.pose.bones[target_bone_name]
        target_world_loc = self._drag_armature.matrix_world @ target_bone.head
        self._drag_plane_point = target_world_loc.copy()

        # CRITICAL: Store fixed depth location for consistent raycasting
        # This prevents feedback loop where depth changes each frame
        self._drag_depth_reference = target_world_loc.copy()

        # CRITICAL: Store initial target position for delta-based movement
        # This prevents bone from snapping to cursor when G is pressed
        self._drag_initial_target_pos = target_world_loc.copy()

        # CRITICAL: Store initial mouse position for delta calculation
        # Must be stored here to persist across mouse moves
        if self._mouse_down_pos:
            self._drag_initial_mouse_pos = self._mouse_down_pos
        else:
            # Fallback: use current event position (shouldn't happen but be safe)
            self._drag_initial_mouse_pos = (event.mouse_region_x, event.mouse_region_y)

        # Reset debug flag for this drag
        self._debug_printed = False

        print(f"  Initial mouse pos stored: {self._drag_initial_mouse_pos}")
        print(f"  Initial target pos stored: {self._drag_initial_target_pos}")

        # Ensure we're in pose mode after creating temp bones
        if context.mode != 'POSE':
            print(f"  WARNING: Not in POSE mode after bone creation! Mode: {context.mode}")
            bpy.ops.object.mode_set(mode='POSE')

        # Enter drag mode
        self._is_dragging = True

        # Update header
        context.area.header_text_set(f"IK DRAGGING: {self._drag_bone_name} | Release to bake pose")

    def update_ik_drag(self, context, event):
        """Update IK target position during drag - uses Blender's built-in 2D-to-3D conversion"""
        print(f"  update_ik_drag called: is_dragging={self._is_dragging}")

        if not self._is_dragging or not self._ik_target_bone_name:
            print(f"  update_ik_drag EARLY RETURN: target={self._ik_target_bone_name}")
            return

        try:
            print(f"  Updating IK drag (mouse: {event.mouse_region_x}, {event.mouse_region_y})")

            # Get target bone
            target_bone = self._drag_armature.pose.bones[self._ik_target_bone_name]
        except Exception as e:
            print(f"  ERROR in update_ik_drag: {e}")
            import traceback
            traceback.print_exc()
            return

        # Use Blender's built-in region_2d_to_location_3d with delta-based movement
        region = context.region
        rv3d = context.space_data.region_3d
        mouse_pos = (event.mouse_region_x, event.mouse_region_y)

        # Get current mouse position in 3D (at fixed depth)
        current_mouse_3d = view3d_utils.region_2d_to_location_3d(
            region,
            rv3d,
            mouse_pos,
            self._drag_depth_reference
        )

        # Get initial mouse position in 3D (when drag started)
        # Use stored initial position, not _mouse_down_pos which may be cleared
        initial_mouse_3d = view3d_utils.region_2d_to_location_3d(
            region,
            rv3d,
            self._drag_initial_mouse_pos,
            self._drag_depth_reference
        )

        # Calculate mouse delta in world space
        mouse_delta = current_mouse_3d - initial_mouse_3d

        # Apply delta to initial target position (prevents snap to cursor)
        new_world_location = self._drag_initial_target_pos + mouse_delta

        # Debug first update only (flag resets each drag)
        if not self._debug_printed:
            self._debug_printed = True
            print(f"  DEBUG: Initial mouse 2D: {self._drag_initial_mouse_pos}")
            print(f"  DEBUG: Current mouse 2D: {mouse_pos}")
            print(f"  DEBUG: Initial target pos: {self._drag_initial_target_pos}")
            print(f"  DEBUG: Initial mouse 3D: {initial_mouse_3d}")
            print(f"  DEBUG: Current mouse 3D: {current_mouse_3d}")
            print(f"  DEBUG: Mouse delta: {mouse_delta}")
            print(f"  DEBUG: New target pos: {new_world_location}")

        # Convert world location to armature local space
        desired_armature_space = self._drag_armature.matrix_world.inverted() @ new_world_location

        # DIRECT APPROACH: Set the bone's matrix to place its head at desired position
        # For a parentless bone, we can construct a translation matrix
        from mathutils import Matrix

        # Create a translation matrix that places the bone's head at desired position
        rest_head = Vector(target_bone.bone.head_local)
        rest_tail = Vector(target_bone.bone.tail_local)
        bone_vector = rest_tail - rest_head

        # Build matrix: translation to move head to desired position
        translation = desired_armature_space - rest_head
        mat = Matrix.Translation(translation)

        # Set the bone's matrix directly
        target_bone.matrix = mat @ target_bone.bone.matrix_local

        # CRITICAL: Update FIRST to ensure target is at new position
        # This prevents IK from solving to the old target position
        context.view_layer.update()

        # Update shoulder target positions (guides collar rotation naturally)
        if self._shoulder_target_names:
            for shoulder_target_name in self._shoulder_target_names:
                # Get the collar name from the shoulder target name
                # Format: "lCollar.shoulder.target" -> "lCollar"
                collar_name = shoulder_target_name.replace('.shoulder.target', '')

                if collar_name not in self._drag_armature.pose.bones:
                    continue

                collar_bone = self._drag_armature.pose.bones[collar_name]
                shoulder_target = self._drag_armature.pose.bones[shoulder_target_name]

                # Calculate natural shoulder target position
                # Strategy: Use collar's natural forward direction (Y axis) as base,
                # then blend toward hand direction to prevent initial inward snap
                collar_world_pos = self._drag_armature.matrix_world @ collar_bone.head
                hand_target_world_pos = self._drag_armature.matrix_world @ target_bone.head

                # Get collar's natural forward direction (Y axis in world space)
                collar_matrix = self._drag_armature.matrix_world @ collar_bone.matrix
                collar_forward = collar_matrix.to_3x3() @ Vector((0, 1, 0))  # Y axis
                collar_forward.normalize()

                # Direction from collar to hand target
                hand_direction = (hand_target_world_pos - collar_world_pos).normalized()

                # Blend between collar's natural direction and hand direction
                # This prevents sudden inward snaps while still guiding toward hand
                # Use 70% collar natural direction, 30% hand direction for smooth behavior
                blend_factor = 0.3
                direction = (collar_forward * (1.0 - blend_factor) + hand_direction * blend_factor).normalized()

                # Position shoulder target at a natural distance along blended direction
                shoulder_distance = (collar_bone.tail - collar_bone.head).length * 3.0
                shoulder_target_world = collar_world_pos + (direction * shoulder_distance)

                # Convert to armature local space
                shoulder_target_local = self._drag_armature.matrix_world.inverted() @ shoulder_target_world

                # Update shoulder target position
                rest_head = Vector(shoulder_target.bone.head_local)
                translation = shoulder_target_local - rest_head
                shoulder_target.matrix = Matrix.Translation(translation) @ shoulder_target.bone.matrix_local

        # NOW activate BOTH IK and Copy Rotation constraints after target is positioned
        # Both start disabled (influence 0.0), so bones stay exactly where they are
        # On first move, we activate BOTH together (0.0 → 1.0)
        ik_tip_bone = self._drag_armature.pose.bones[self._ik_control_bone_names[-1]]
        ik_just_activated = False
        for constraint in ik_tip_bone.constraints:
            # Check if IK constraint needs activation (influence == 0.0 means not activated yet)
            if constraint.name == "IK_Temp" and constraint.influence == 0.0:
                # Check if the root bone of the chain is a collar (dampen shoulder shrugging)
                root_bone_name = self._ik_control_bone_names[0].lower()
                if 'collar' in root_bone_name:
                    constraint.influence = 0.3
                    print(f"  Activated IK constraint with dampened influence (0.0 → 0.3 for collar)")
                else:
                    constraint.influence = 1.0
                    print(f"  Activated IK constraint (influence 0.0 → 1.0)")
                ik_just_activated = True

                # APPLY NUDGE NOW (on first mouse move after IK activation)
                # Find the actual bending joint (shin/forearm) in the chain, not the mathematical middle
                # With extended chains, middle_index might be a parent bone (pelvis/chest)
                from mathutils import Quaternion

                for bone_name in self._ik_control_bone_names:
                    ik_bone = self._drag_armature.pose.bones[bone_name]
                    bone_name_lower = bone_name.lower()

                    # Find shin/calf and nudge it
                    if 'shin' in bone_name_lower or 'calf' in bone_name_lower:
                        nudge_quat = Quaternion((1, 0, 0), 0.5)  # 0.5 rad (29°) for legs
                        ik_bone.rotation_quaternion = nudge_quat @ ik_bone.rotation_quaternion
                        print(f"  Applied nudge to {bone_name}: 0.5 rad forward")
                        break
                    # Find forearm and nudge it
                    elif 'forearm' in bone_name_lower or 'lorearm' in bone_name_lower:
                        nudge_quat = Quaternion((0, 1, 0), 0.02)  # 0.02 rad (~1°) minimal nudge
                        ik_bone.rotation_quaternion = nudge_quat @ ik_bone.rotation_quaternion
                        print(f"  Applied nudge to {bone_name}: 0.02 rad")
                        break
                    # Find abdomen/spine and nudge it for torso bending
                    elif 'abdomen' in bone_name_lower or 'spine' in bone_name_lower:
                        nudge_quat = Quaternion((1, 0, 0), 0.02)  # 0.02 rad (~1°) minimal nudge
                        ik_bone.rotation_quaternion = nudge_quat @ ik_bone.rotation_quaternion
                        print(f"  Applied torso nudge to {bone_name}: 0.02 rad")
                        break
                break

        # Also activate Copy Rotation constraints (but skip collar on ONLY the first frame to prevent snap)
        for daz_name in self._ik_daz_bone_names:
            daz_bone = self._drag_armature.pose.bones[daz_name]

            # Check if this is a collar bone
            bone_lower = daz_name.lower()
            is_collar = 'collar' in bone_lower or 'clavicle' in bone_lower

            for constraint in daz_bone.constraints:
                if constraint.name == "IK_CopyRot_Temp":
                    # Skip collar ONLY on first IK activation frame (check == 0.0 to avoid false positives)
                    if constraint.influence == 0.0:
                        if ik_just_activated and is_collar:
                            # First frame: Skip collar to prevent snap
                            print(f"  Skipping Copy Rotation for {daz_name} on first frame (prevents snap)")
                        else:
                            # Activate normally (including collar on subsequent frames)
                            constraint.influence = 1.0
                            if is_collar:
                                print(f"  Activated Copy Rotation for {daz_name} (subsequent frame)")

        print(f"  Activated Copy Rotation constraints")

        # DON'T activate Damped Track on first frame - let IK solve naturally first
        # This prevents the initial inward snap by giving IK time to position the arm
        # Damped Track will activate on subsequent frames automatically (if needed later)

        # Final update to trigger IK solving with new target position
        context.view_layer.update()

    def end_ik_drag(self, context, cancel=False):
        """End IK drag and optionally bake pose to FK

        Args:
            cancel: If True, skip keyframing (returns to original pose)
        """
        if not self._is_dragging:
            return

        if cancel:
            print(f"\n=== Canceling IK Drag: {self._drag_bone_name} ===")
        else:
            print(f"\n=== Ending IK Drag: {self._drag_bone_name} ===")
            # Store undo state before dissolving (so we can undo this drag)
            self.store_undo_state(context)

        # Dissolve IK chain (remove constraints, delete .ik bones)
        # Pass keyframe=False if canceling to skip baking
        dissolve_ik_chain(
            self._drag_armature,
            self._ik_target_bone_name,
            self._ik_control_bone_names,
            self._ik_daz_bone_names,
            self._shoulder_target_names,
            keyframe=(not cancel)
        )

        # Clear drag state
        self._is_dragging = False
        self._drag_bone_name = None
        self._drag_armature = None
        self._ik_target_bone_name = None
        self._ik_control_bone_names = []
        self._ik_daz_bone_names = []
        self._shoulder_target_names = []
        self._drag_plane_normal = None
        self._drag_plane_point = None
        self._drag_depth_reference = None
        self._drag_initial_target_pos = None
        self._drag_initial_mouse_pos = None
        self._mouse_down_pos = None

        # Update header
        context.area.header_text_set("DAZ Bone Select Active - Click to select | P to pin | U to unpin | ESC to exit")

    def update_rotation(self, context, event):
        """Update bone rotation during drag (for pectoral bones)"""
        if not self._is_rotating or not self._rotation_bone:
            return

        # Calculate mouse delta
        delta_x = event.mouse_x - self._rotation_initial_mouse[0]
        delta_y = event.mouse_y - self._rotation_initial_mouse[1]

        # Apply rotation based on mouse movement (sensitivity: 0.01 radians/pixel)
        sensitivity = 0.01

        # Horizontal drag = Z-axis rotation (twist)
        # Vertical drag = X-axis rotation (bend forward/back)
        angle_z = delta_x * sensitivity   # Horizontal movement = Z rotation
        angle_x = delta_y * sensitivity   # Vertical movement = X rotation (fixed)

        # Create rotation quaternions
        rot_z = Quaternion(Vector((0, 0, 1)), angle_z)
        rot_x = Quaternion(Vector((1, 0, 0)), angle_x)

        # Combine rotations and apply to bone
        combined_rot = rot_z @ rot_x
        self._rotation_bone.rotation_quaternion = combined_rot @ self._rotation_initial_quat

        # Update viewport
        context.area.tag_redraw()
        refresh_3d_viewports(context)

    def end_rotation(self, context, cancel=False):
        """End rotation drag and optionally keyframe"""
        if not self._is_rotating:
            return

        if cancel:
            print(f"\n=== Canceling Rotation: {self._rotation_bone.name} ===")
            # Restore initial rotation
            self._rotation_bone.rotation_quaternion = self._rotation_initial_quat
        else:
            print(f"\n=== Ending Rotation: {self._rotation_bone.name} ===")
            # Store undo state before keyframing
            self.store_rotation_undo_state(context)
            # Keyframe the rotation
            self._rotation_bone.keyframe_insert(data_path="rotation_quaternion")
            print(f"  ✓ Keyframed rotation: {self._rotation_bone.rotation_quaternion}")

        # Clear rotation state
        self._is_rotating = False
        self._rotation_bone = None
        self._rotation_initial_quat = None
        self._rotation_initial_mouse = None
        self._mouse_down_pos = None

        # Update viewport and header
        context.area.tag_redraw()
        refresh_3d_viewports(context)
        context.area.header_text_set("DAZ Bone Select Active - Click to select | P to pin | U to unpin | ESC to exit")

    def pin_selected_bone_translation(self, context):
        """Pin translation of the currently active bone"""
        armature = context.active_object

        if not armature or armature.type != 'ARMATURE':
            self.report({'WARNING'}, "No armature selected")
            return

        if not armature.data.bones.active:
            self.report({'WARNING'}, "No bone selected")
            return

        bone_name = armature.data.bones.active.name
        print(f"\n=== Pin Translation: {bone_name} ===")

        if pin_bone_translation(armature, bone_name):
            self.report({'INFO'}, f"Pinned Translation: {bone_name}")

            # Update header to show pin status
            bone = armature.data.bones[bone_name]
            pin_status = get_pin_status_text(bone)
            text = f"{bone_name} | {pin_status} | Press P/Shift+P to pin, U to unpin"
            context.area.header_text_set(text)
        else:
            self.report({'ERROR'}, f"Failed to pin: {bone_name}")

    def pin_selected_bone_rotation(self, context):
        """Pin rotation of the currently active bone"""
        armature = context.active_object

        if not armature or armature.type != 'ARMATURE':
            self.report({'WARNING'}, "No armature selected")
            return

        if not armature.data.bones.active:
            self.report({'WARNING'}, "No bone selected")
            return

        bone_name = armature.data.bones.active.name
        print(f"\n=== Pin Rotation: {bone_name} ===")

        if pin_bone_rotation(armature, bone_name):
            self.report({'INFO'}, f"Pinned Rotation: {bone_name}")

            # Update header to show pin status
            bone = armature.data.bones[bone_name]
            pin_status = get_pin_status_text(bone)
            text = f"{bone_name} | {pin_status} | Press P/Shift+P to pin, U to unpin"
            context.area.header_text_set(text)
        else:
            self.report({'ERROR'}, f"Failed to pin: {bone_name}")

    def unpin_selected_bone(self, context):
        """Remove all pins from the currently active bone"""
        armature = context.active_object

        if not armature or armature.type != 'ARMATURE':
            self.report({'WARNING'}, "No armature selected")
            return

        if not armature.data.bones.active:
            self.report({'WARNING'}, "No bone selected")
            return

        bone_name = armature.data.bones.active.name
        print(f"\n=== Unpin: {bone_name} ===")

        if unpin_bone(armature, bone_name):
            self.report({'INFO'}, f"Unpinned: {bone_name}")
            text = f"{bone_name} | Press P/Shift+P to pin, U to unpin"
            context.area.header_text_set(text)
        else:
            self.report({'INFO'}, f"{bone_name} was not pinned")

    def store_undo_state(self, context):
        """Store current bone rotations before dissolving IK for undo"""
        if not self._drag_armature or not self._ik_daz_bone_names:
            return

        frame = context.scene.frame_current
        bones_data = []

        # Read from evaluated depsgraph to capture keyframed rotations
        depsgraph = context.evaluated_depsgraph_get()
        armature_eval = self._drag_armature.evaluated_get(depsgraph)

        for bone_name in self._ik_daz_bone_names:
            bone = self._drag_armature.pose.bones.get(bone_name)
            bone_eval = armature_eval.pose.bones.get(bone_name)

            if bone and bone_eval:
                # Store rotation based on mode
                if bone.rotation_mode == 'QUATERNION':
                    rotation = bone_eval.rotation_quaternion.copy()
                else:
                    rotation = bone_eval.rotation_euler.copy()

                bones_data.append((bone_name, rotation, bone.rotation_mode))

        # Store undo entry
        undo_entry = {
            'frame': frame,
            'bones': bones_data,
            'armature': self._drag_armature
        }
        self._undo_stack.append(undo_entry)
        print(f"  Stored undo state: frame {frame}, {len(bones_data)} bones")

    def store_rotation_undo_state(self, context):
        """Store current bone rotation before keyframing (for pectoral bone rotations)"""
        if not self._rotation_bone or not self._drag_armature:
            return

        frame = context.scene.frame_current
        bone = self._rotation_bone
        bone_name = bone.name

        # Store the initial rotation (before the drag)
        bones_data = [(bone_name, self._rotation_initial_quat.copy(), 'QUATERNION')]

        # Store undo entry
        undo_entry = {
            'frame': frame,
            'bones': bones_data,
            'armature': self._drag_armature
        }
        self._undo_stack.append(undo_entry)
        print(f"  Stored rotation undo state: frame {frame}, bone {bone_name}")

    def undo_last_drag(self, context):
        """Undo the last IK drag by restoring previous bone rotations"""
        if not self._undo_stack:
            self.report({'INFO'}, "Nothing to undo")
            return

        # Pop the last undo entry
        undo_entry = self._undo_stack.pop()
        frame = undo_entry['frame']
        bones_data = undo_entry['bones']
        armature = undo_entry['armature']

        print(f"\n=== Undo: Restoring {len(bones_data)} bones at frame {frame} ===")

        # Restore bone rotations
        for bone_name, rotation, rotation_mode in bones_data:
            bone = armature.pose.bones.get(bone_name)
            if bone:
                if rotation_mode == 'QUATERNION':
                    bone.rotation_quaternion = rotation
                    bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
                else:
                    bone.rotation_euler = rotation
                    bone.keyframe_insert(data_path="rotation_euler", frame=frame)

        context.view_layer.update()
        self.report({'INFO'}, f"Undone: Restored {len(bones_data)} bones")
        print(f"  ✓ Undo complete")

    def draw_highlight_callback(self):
        """Draw callback to highlight mesh region weighted to hovered bone (DAZ-style)"""
        # Safety check: verify operator still exists before accessing properties
        try:
            hover_bone = self._hover_bone_name
            hover_arm = self._hover_armature
        except ReferenceError:
            # Operator destroyed, exit silently
            return

        if not hover_bone or not hover_arm:
            return

        armature = hover_arm
        bone_name = hover_bone

        # Use base body mesh for highlighting (ignore clothing)
        mesh_obj = self._base_body_mesh if self._base_body_mesh else self._hover_mesh
        if not mesh_obj:
            return

        # Get bone from armature
        if bone_name not in armature.data.bones:
            return

        # Find vertex group for this bone
        if bone_name not in mesh_obj.vertex_groups:
            return

        # Cache key for this mesh+bone combination
        cache_key = (mesh_obj.name, bone_name)

        # Check cache - only compute weighted verts/polygons once per bone
        if cache_key not in self._highlight_cache or self._last_highlighted_bone != bone_name:
            vgroup = mesh_obj.vertex_groups[bone_name]
            mesh = mesh_obj.data

            # Collect vertices where THIS bone has the HIGHEST weight (DAZ-style clean sections)
            # This prevents bleed into neighboring areas
            weighted_verts = set()
            for vert in mesh.vertices:
                if not vert.groups:
                    continue

                # Find the group with maximum weight for this vertex
                max_weight = 0.0
                max_group_idx = None
                for group in vert.groups:
                    if group.weight > max_weight:
                        max_weight = group.weight
                        max_group_idx = group.group

                # Only include vertex if THIS bone has the max weight
                if max_group_idx == vgroup.index and max_weight > 0.01:  # Small threshold to exclude zero weights
                    weighted_verts.add(vert.index)

            if not weighted_verts:
                self._highlight_cache[cache_key] = []
                self._last_highlighted_bone = bone_name
                return

            # Collect triangle indices (vertex indices, not positions)
            tri_indices = []
            for poly in mesh.polygons:
                # If at least one vertex of the polygon is weighted, include the whole polygon
                if any(v in weighted_verts for v in poly.vertices):
                    # Triangulate polygon (simple fan triangulation from first vertex)
                    for i in range(1, len(poly.vertices) - 1):
                        tri_indices.append((poly.vertices[0], poly.vertices[i], poly.vertices[i + 1]))

            # Cache the triangle indices (not positions)
            self._highlight_cache[cache_key] = tri_indices
            self._last_highlighted_bone = bone_name

        # Get cached triangle indices
        tri_indices = self._highlight_cache[cache_key]
        if not tri_indices:
            return

        # Get DEFORMED mesh from evaluated depsgraph (includes armature deformation)
        import bpy
        depsgraph = bpy.context.evaluated_depsgraph_get()
        mesh_eval = mesh_obj.evaluated_get(depsgraph)
        mesh_data = mesh_eval.data

        # Build triangles using DEFORMED vertex positions
        # CRITICAL: Offset vertices away from surface to prevent z-fighting
        offset_amount = 0.001  # Small offset in world units
        tris = []

        for v0_idx, v1_idx, v2_idx in tri_indices:
            # Get vertex positions and normals
            v0_co = mesh_data.vertices[v0_idx].co
            v1_co = mesh_data.vertices[v1_idx].co
            v2_co = mesh_data.vertices[v2_idx].co

            v0_normal = mesh_data.vertices[v0_idx].normal
            v1_normal = mesh_data.vertices[v1_idx].normal
            v2_normal = mesh_data.vertices[v2_idx].normal

            # Offset along normal to prevent z-fighting (push away from surface)
            v0 = mesh_eval.matrix_world @ (v0_co + v0_normal * offset_amount)
            v1 = mesh_eval.matrix_world @ (v1_co + v1_normal * offset_amount)
            v2 = mesh_eval.matrix_world @ (v2_co + v2_normal * offset_amount)

            tris.extend([v0, v1, v2])

        if not tris:
            return

        # Draw triangles with semi-transparent overlay (DAZ-style clean sections)
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'TRIS', {"pos": tris})

        # Enable blending for transparency
        gpu.state.blend_set('ALPHA')

        # CRITICAL: Depth settings to draw on top of clothing/hair
        gpu.state.depth_test_set('ALWAYS')  # Always draw, ignore depth (show through clothing)
        gpu.state.depth_mask_set(False)  # Don't write to depth buffer (overlay on top cleanly)
        gpu.state.face_culling_set('BACK')  # Only draw front faces (prevents double-draw artifacts)

        # Draw with bright amber highlight (more visible than previous yellow-orange)
        shader.bind()
        shader.uniform_float("color", (1.0, 0.6, 0.1, 0.4))  # Bright amber with moderate transparency

        batch.draw(shader)

        # Reset state
        gpu.state.blend_set('NONE')
        gpu.state.depth_mask_set(True)
        gpu.state.face_culling_set('NONE')
        gpu.state.depth_test_set('LESS_EQUAL')


def register():
    # Register DAZ Bone Select operator
    bpy.utils.register_class(VIEW3D_OT_daz_bone_select)

    # Register PowerPose classes
    bpy.utils.register_class(POSE_OT_daz_powerpose_control)
    bpy.utils.register_class(VIEW3D_PT_daz_powerpose_main)

    # Keyboard shortcut: Ctrl+Shift+D for "DAZ select"
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        km.keymap_items.new(
            VIEW3D_OT_daz_bone_select.bl_idname,
            'D', 'PRESS',
            ctrl=True, shift=True
        )
        print("Registered DAZ Bone Select - Activate with Ctrl+Shift+D")
        print("Registered PowerPose - Open N-panel > DAZ tab")


def unregister():
    # Unregister PowerPose classes
    bpy.utils.unregister_class(VIEW3D_PT_daz_powerpose_main)
    bpy.utils.unregister_class(POSE_OT_daz_powerpose_control)

    # Unregister DAZ Bone Select operator
    bpy.utils.unregister_class(VIEW3D_OT_daz_bone_select)

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.get('3D View')
        if km:
            for kmi in km.keymap_items:
                if kmi.idname == VIEW3D_OT_daz_bone_select.bl_idname:
                    km.keymap_items.remove(kmi)


# ============================================================================
# POWERPOSE SYSTEM - Rotation-Based Panel Posing
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


def apply_rotation_from_delta(bone, initial_rotation, axis, delta_x, delta_y, sensitivity=0.01):
    """
    Apply rotation to bone based on mouse delta.

    Args:
        bone: Pose bone to rotate
        initial_rotation: Starting rotation (quaternion)
        axis: Rotation axis ('X', 'Y', or 'Z')
        delta_x: Horizontal mouse movement (pixels)
        delta_y: Vertical mouse movement (pixels)
        sensitivity: Rotation multiplier (radians per pixel)
    """
    # Determine rotation angle based on mouse delta
    if axis == 'X':
        angle = -delta_y * sensitivity  # Vertical drag
    elif axis == 'Y':
        angle = delta_x * sensitivity   # Horizontal drag
    elif axis == 'Z':
        angle = delta_x * sensitivity   # Horizontal drag
    else:
        angle = 0.0

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


def get_genesis8_control_points():
    """
    Get control point definitions for Genesis 8 figure.
    Returns list of control point dictionaries.
    """
    control_points = [
        # Head
        {'id': 'head', 'bone_name': 'head', 'label': 'Head', 'group': 'head'},

        # Arms
        {'id': 'lHand', 'bone_name': 'lHand', 'label': 'Left Hand', 'group': 'arms'},
        {'id': 'rHand', 'bone_name': 'rHand', 'label': 'Right Hand', 'group': 'arms'},
        {'id': 'lForeArm', 'bone_name': 'lForeArm', 'label': 'Left Forearm', 'group': 'arms'},
        {'id': 'rForeArm', 'bone_name': 'rForeArm', 'label': 'Right Forearm', 'group': 'arms'},
        {'id': 'lShldr', 'bone_name': 'lShldr', 'label': 'Left Shoulder', 'group': 'arms'},
        {'id': 'rShldr', 'bone_name': 'rShldr', 'label': 'Right Shoulder', 'group': 'arms'},

        # Torso
        {'id': 'chest', 'bone_name': 'chest', 'label': 'Chest', 'group': 'torso'},
        {'id': 'abdomen', 'bone_name': 'abdomen', 'label': 'Abdomen', 'group': 'torso'},
        {'id': 'pelvis', 'bone_name': 'pelvis', 'label': 'Pelvis', 'group': 'torso'},

        # Legs
        {'id': 'lFoot', 'bone_name': 'lFoot', 'label': 'Left Foot', 'group': 'legs'},
        {'id': 'rFoot', 'bone_name': 'rFoot', 'label': 'Right Foot', 'group': 'legs'},
        {'id': 'lShin', 'bone_name': 'lShin', 'label': 'Left Shin', 'group': 'legs'},
        {'id': 'rShin', 'bone_name': 'rShin', 'label': 'Right Shin', 'group': 'legs'},
        {'id': 'lThigh', 'bone_name': 'lThigh', 'label': 'Left Thigh', 'group': 'legs'},
        {'id': 'rThigh', 'bone_name': 'rThigh', 'label': 'Right Thigh', 'group': 'legs'},
    ]

    return control_points


class POSE_OT_daz_powerpose_control(bpy.types.Operator):
    """Click and drag to rotate bone"""
    bl_idname = "pose.daz_powerpose_control"
    bl_label = "PowerPose Control"
    bl_options = {'REGISTER', 'UNDO'}

    bone_name: bpy.props.StringProperty()
    control_point_id: bpy.props.StringProperty()
    action: bpy.props.StringProperty(default='bend')  # 'bend' or 'twist'

    def invoke(self, context, event):
        """Start rotation operation"""
        # Action is now set via property when operator is called
        # No need to detect mouse button

        # Get active armature
        self.armature = context.active_object
        if not self.armature or self.armature.type != 'ARMATURE':
            self.report({'WARNING'}, "No armature selected")
            return {'CANCELLED'}

        # Ensure we're in pose mode
        if context.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')

        # Get the bone
        if self.bone_name not in self.armature.pose.bones:
            self.report({'WARNING'}, f"Bone '{self.bone_name}' not found")
            return {'CANCELLED'}

        self.bone = self.armature.pose.bones[self.bone_name]

        # Store initial state
        self.initial_mouse = (event.mouse_x, event.mouse_y)

        # Force quaternion rotation mode for stability
        self.bone.rotation_mode = 'QUATERNION'
        self.initial_rotation = self.bone.rotation_quaternion.copy()

        # Determine rotation axis
        if self.action == 'bend':
            self.rotation_axis = get_bend_axis(self.bone)
        else:  # twist
            self.rotation_axis = get_twist_axis(self.bone)

        print(f"\n=== PowerPose: {self.bone_name} ===")
        print(f"  Action: {self.action}")
        print(f"  Axis: {self.rotation_axis}")

        # Enter modal mode
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        """Handle mouse movement and apply rotation"""
        if event.type == 'MOUSEMOVE':
            # Calculate mouse delta
            delta_x = event.mouse_x - self.initial_mouse[0]
            delta_y = event.mouse_y - self.initial_mouse[1]

            # Apply rotation based on delta
            apply_rotation_from_delta(
                self.bone,
                self.initial_rotation,
                self.rotation_axis,
                delta_x,
                delta_y,
                sensitivity=0.01
            )

            # Update viewport
            context.area.tag_redraw()
            refresh_3d_viewports(context)
            return {'RUNNING_MODAL'}

        elif event.type in {'LEFTMOUSE', 'RIGHTMOUSE'} and event.value == 'RELEASE':
            # Keyframe the rotation
            self.bone.keyframe_insert(data_path="rotation_quaternion")
            print(f"  ✓ Keyframed rotation: {self.bone.rotation_quaternion}")
            return {'FINISHED'}

        elif event.type == 'ESC':
            # Restore initial rotation
            self.bone.rotation_quaternion = self.initial_rotation
            context.area.tag_redraw()
            refresh_3d_viewports(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}


class VIEW3D_PT_daz_powerpose_main(bpy.types.Panel):
    """Main PowerPose panel with full body controls"""
    bl_label = "PowerPose"
    bl_idname = "VIEW3D_PT_daz_powerpose_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DAZ'

    def draw(self, context):
        layout = self.layout

        # Show active armature
        if context.active_object and context.active_object.type == 'ARMATURE':
            armature = context.active_object

            # Header
            box = layout.box()
            box.label(text=f"Target: {armature.name}", icon='ARMATURE_DATA')

            # Instructions
            layout.label(text="Click Bend or Twist, then drag", icon='INFO')

            # Get control points
            control_points = get_genesis8_control_points()

            # Group control points by body region
            groups = {}
            for cp in control_points:
                group = cp['group']
                if group not in groups:
                    groups[group] = []
                groups[group].append(cp)

            # Draw control points by group
            for group_name in ['head', 'arms', 'torso', 'legs']:
                if group_name not in groups:
                    continue

                box = layout.box()
                box.label(text=group_name.upper(), icon='DOT')

                for cp in groups[group_name]:
                    # Check if bone exists
                    if cp['bone_name'] not in armature.pose.bones:
                        continue

                    # Create row with bone label and two buttons
                    row = box.row(align=True)
                    row.label(text=cp['label'])

                    # Bend button
                    op_bend = row.operator(
                        "pose.daz_powerpose_control",
                        text="Bend",
                        icon='LOOP_BACK'
                    )
                    op_bend.bone_name = cp['bone_name']
                    op_bend.control_point_id = cp['id']
                    op_bend.action = 'bend'

                    # Twist button
                    op_twist = row.operator(
                        "pose.daz_powerpose_control",
                        text="Twist",
                        icon='FILE_REFRESH'
                    )
                    op_twist.bone_name = cp['bone_name']
                    op_twist.control_point_id = cp['id']
                    op_twist.action = 'twist'

        else:
            # No armature selected
            layout.label(text="No armature selected", icon='ERROR')
            layout.label(text="Select an armature in Pose Mode")


# ==================================================================
# TEST FUNCTION - Call this to test create_ik_chain()
# ==================================================================
def test_step1_create_ik_chain():
    """Test the new create_ik_chain function on Fey rig"""
    print("\n" + "="*60)
    print("TEST STEP 1: create_ik_chain()")
    print("="*60)

    fey = bpy.data.objects.get("Fey")
    if not fey:
        print("✗ Fey armature not found!")
        return

    print(f"✓ Found armature: {fey.name}")

    # Test on left hand
    test_bone = "lHand"
    print(f"\nCreating IK chain on: {test_bone}")

    result = create_ik_chain(fey, test_bone, chain_length=3)

    if result == (None, None, None, []):
        print("\n✗ FAILED")
        return

    target_name, ik_names, daz_names, shoulder_targets = result

    print("\n✓ SUCCESS: IK chain created!")
    print(f"  Target: {target_name}")
    print(f"  IK bones: {ik_names}")
    print(f"  DAZ bones: {daz_names}")
    print(f"  Shoulder targets: {shoulder_targets}")

    print("\nNow test manually:")
    print(f"  1. Find '{target_name}' in Outliner")
    print(f"  2. Select it and press G to move")
    print(f"  3. Arm should follow smoothly!")


if __name__ == "__main__":
    register()
    print("\n" + "="*60)
    print("DAZ BONE SELECT & PIN & IK - Installed!")
    print("="*60)
    print("Press Ctrl+Shift+D to activate")
    print("  - Hover over mesh to preview bone")
    print("  - Left-click to select bone")
    print("  - Click-drag selected bone for IK posing")
    print("  - P to pin translation")
    print("  - Shift+P to pin rotation")
    print("  - U to unpin")
    print("  - Keep clicking to select multiple bones")
    print("  - ESC to exit")
    print("="*60 + "\n")
