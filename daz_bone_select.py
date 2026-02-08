"""
DAZ Bone Select & Pin - Hover, Click to Select, and Pin Bones
Combines fast hover preview, bone selection, and pin marking system
"""

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector, Euler, Quaternion
from mathutils.bvhtree import BVHTree


bl_info = {
    "name": "DAZ Bone Select & Pin",
    "version": (1, 1, 0),
    "blender": (3, 0, 0),
    "description": "Hover to preview, click to select, pin bones for IK",
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
    face_keywords = ['eye', 'brow', 'lid', 'nose', 'mouth', 'lip', 'cheek',
                     'jaw', 'tongue', 'teeth', 'ear', 'lash', 'pupil']
    if any(keyword in bone_lower for keyword in face_keywords):
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
    Calculate how many bones to traverse to get desired number of non-twist bones.
    Accounts for twist bones in the hierarchy.
    """
    current = start_bone
    non_twist_count = 0
    total_count = 0

    while current and non_twist_count < desired_non_twist_count:
        if not is_twist_bone(current.name):
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

    # Hands - full arm chain including collar bone
    # Forearm + upper arm + collar (twist bones will be locked to prevent noodling)
    if 'hand' in bone_lower:
        # Exclude finger bones
        if not any(finger in bone_lower for finger in ['thumb', 'index', 'mid', 'ring', 'pinky', 'carpal']):
            return 3  # Forearm + upper arm + collar bone

    # Feet - full leg chain (foot + shin + thigh)
    # Twist bones will be automatically skipped by the chain builder
    if 'foot' in bone_lower:
        # Exclude toe bones
        if not any(toe in bone_lower for toe in ['toe', 'metatarsal']):
            return 3  # Foot + shin + thigh

    # Forearms - full arm chain including collar
    if any(part in bone_lower for part in ['forearm', 'lorearm']):
        return 3  # Upper arm + collar bone

    # Shins - medium chain to thigh
    if any(part in bone_lower for part in ['shin', 'calf']):
        return 2

    # Head - medium chain for neck control
    if 'head' in bone_lower:
        return 3  # head -> neck -> chest

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
    # STEP 1: Collect non-twist bones for the chain
    # ==================================================================
    daz_bones = []  # PoseBones
    current = clicked_bone

    # Walk up collecting non-twist bones
    while current and len(daz_bones) < chain_length:
        if not is_twist_bone(current.name):
            daz_bones.append(current)
        current = current.parent

    if len(daz_bones) < 2:
        print(f"  ✗ Not enough bones for IK chain")
        return None, None, None

    # Reverse so we have root-to-tip order
    daz_bones = list(reversed(daz_bones))
    daz_bone_names = [b.name for b in daz_bones]

    print(f"  Chain: {' → '.join(daz_bone_names)}")

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
        else:
            # Root bone - parent to DAZ parent (or None)
            if daz_edit.parent:
                # Find non-twist parent
                anchor = daz_edit.parent
                while anchor and is_twist_bone(anchor.name):
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

        # DEBUG: Log tip bone rotation
        if i == len(daz_bone_names) - 1:
            print(f"  DEBUG TIP BONE: {daz_name}")
            print(f"    DAZ rotation property (raw): {daz_bone.rotation_euler if daz_bone.rotation_mode != 'QUATERNION' else daz_bone.rotation_quaternion}")
            print(f"    DAZ matrix_basis rotation (EVAL): {actual_rotation_quat}")
            print(f"    Copied to .ik: {ik_bone.rotation_quaternion}")
            print(f"    DAZ matrix_basis (EVAL): {daz_bone_eval.matrix_basis}")
            print(f"    .ik matrix_basis: {ik_bone.matrix_basis}")

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

        # PHASE 2: IK Stiffness for natural falloff (DAZ-like pulling behavior)
        # Apply increasing stiffness to bones further from the tip (diminishing influence)
        # Tip (hand/foot) = 0.0 (100% influence), Root (shoulder/hip) = 0.8 (20% influence)
        # This creates natural "ragdoll pulling" where parent bones resist more
        chain_position = i / max(1, len(daz_bone_names) - 1)  # 0.0 at tip, 1.0 at root
        stiffness = chain_position * 0.8  # Linear falloff from 0.0 to 0.8

        ik_bone.ik_stiffness_x = stiffness
        ik_bone.ik_stiffness_y = stiffness
        ik_bone.ik_stiffness_z = stiffness

        if i == 0 or i == len(daz_bone_names) - 1:  # Log first and last bone
            print(f"  IK stiffness: {daz_name} = {stiffness:.2f} (chain pos {chain_position:.2f})")

    # CRITICAL: Lock rotation on the TIP bone (last in chain) to preserve manual rotations
    # This prevents IK from rotating the tip bone (e.g., foot/hand), allowing only
    # middle bones (knee/elbow) to rotate. This preserves user's manual R rotations.
    tip_bone = armature.pose.bones[ik_control_names[-1]]
    tip_bone.lock_ik_x = True
    tip_bone.lock_ik_y = True
    tip_bone.lock_ik_z = True
    print(f"  Locked tip bone rotation: {tip_bone.name}")

    # NOTE: Intentionally NOT copying Limit Rotation constraints to IK limits
    # Reason: IK limits constrain the solver during solving (can prevent solutions)
    #         Limit Rotation constraints clamp AFTER solving (better for IK)
    # The workflow is:
    #   1. IK solves freely on .ik bones (except tip rotation is locked)
    #   2. Copy Rotation copies result to DAZ bones
    #   3. DAZ bones' Limit Rotation constraints clamp the final result
    # This gives the IK solver freedom while still respecting joint limits on final pose

    # Add nudge to middle bone to hint bend direction (prevents backwards bending)
    # Larger nudge (0.3 rad ≈ 17°) than previous 0.1 rad for stronger hint
    # Using quaternion rotation since all .ik bones now use QUATERNION mode
    if len(ik_control_names) >= 2:
        middle_bone = armature.pose.bones[ik_control_names[len(ik_control_names)//2]]
        middle_bone_name = middle_bone.name.lower()

        # For legs: nudge shin forward (X-axis rotation in quaternion)
        if 'shin' in middle_bone_name or 'calf' in middle_bone_name:
            # Create rotation quaternion around X-axis (0.3 radians ≈ 17°)
            from mathutils import Quaternion
            import math
            nudge_quat = Quaternion((1, 0, 0), 0.3)  # X-axis, 0.3 radians
            middle_bone.rotation_quaternion = nudge_quat @ middle_bone.rotation_quaternion
            print(f"  Nudged shin forward 0.3 rad (17°) to prevent backward bend")
        # For arms: small nudge around Y-axis
        elif 'forearm' in middle_bone_name or 'lorearm' in middle_bone_name:
            from mathutils import Quaternion
            nudge_quat = Quaternion((0, 1, 0), 0.05)  # Y-axis, small nudge
            middle_bone.rotation_quaternion = nudge_quat @ middle_bone.rotation_quaternion
            print(f"  Nudged forearm 0.05 rad")

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
        # Skip the last bone (tip) - it keeps its manual rotation
        if i == len(daz_bone_names) - 1:
            print(f"  Skipping Copy Rotation for tip bone: {daz_name}")
            continue

        daz_pose = armature.pose.bones[daz_name]

        # Add Copy Rotation constraint
        copy_rot = daz_pose.constraints.new('COPY_ROTATION')
        copy_rot.name = "IK_CopyRot_Temp"
        copy_rot.target = armature
        copy_rot.subtarget = ik_name  # Copy from IK control bone
        copy_rot.target_space = 'LOCAL'  # Copy in local space!
        copy_rot.owner_space = 'LOCAL'   # Apply in local space!
        copy_rot.influence = 1.0  # Active immediately (IK constraint controls pop prevention)

        # CRITICAL: Move Copy Rotation to TOP of constraint stack (index 0)
        # This ensures it runs BEFORE Limit Rotation, so limits can clamp the result
        # Order: Copy Rotation (copies IK result) → Limit Rotation (clamps to joint limits)
        daz_pose.constraints.move(len(daz_pose.constraints) - 1, 0)

    # Force update
    bpy.context.view_layer.update()

    print(f"  ✓ IK chain ready")

    return target_name, ik_control_names, daz_bone_names


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


def dissolve_ik_chain(armature, target_bone_name, ik_control_names, daz_bone_names, keyframe=True):
    """
    Remove IK chain: optionally keyframe DAZ bones, delete Copy Rotation constraints, delete .ik bones.
    CRITICAL: Keyframe BEFORE removing constraints to capture the constrained pose!

    Args:
        keyframe: If False, skip keyframing (used for canceling/right-click)
    """
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

        # Remove all IK_CopyRot_Temp constraints
        constraints_to_remove = [c for c in daz_bone.constraints if c.name == "IK_CopyRot_Temp"]
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

    def modal(self, context, event):
        """Handle mouse events"""

        if event.type == 'MOUSEMOVE':
            # Debug: Check state
            if self._is_dragging:
                print(f"  [MODAL] MOUSEMOVE while dragging")
            # Check if we should start IK drag
            if not self._is_dragging and self._mouse_down_pos and self._drag_bone_name:
                mouse_pos = (event.mouse_region_x, event.mouse_region_y)
                distance = ((mouse_pos[0] - self._mouse_down_pos[0])**2 +
                           (mouse_pos[1] - self._mouse_down_pos[1])**2)**0.5

                # If moved beyond threshold, start IK drag
                if distance > self._click_threshold:
                    self.start_ik_drag(context, event)

                # Consume event during detection phase to prevent box select
                return {'RUNNING_MODAL'}

            # If dragging, update IK target position
            if self._is_dragging:
                self.update_ik_drag(context, event)
                return {'RUNNING_MODAL'}

            # Otherwise update hover preview
            self.check_hover(context, event)
            return {'PASS_THROUGH'}

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            # CRITICAL: Check if we're actually clicking on mesh, not gizmo
            # Do a fresh raycast to verify we hit mesh
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

            # If we didn't hit any mesh, pass through (might be clicking gizmo)
            if not hit_mesh:
                self._mouse_down_pos = None
                return {'PASS_THROUGH'}

            # Record mouse position on press (to detect drags vs clicks)
            self._mouse_down_pos = (event.mouse_region_x, event.mouse_region_y)

            # If hovering over a bone, prepare for potential drag
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
        self._drag_plane_normal = None
        self._drag_plane_point = None
        self._drag_depth_reference = None  # Fixed depth for raycast consistency
        self._drag_initial_target_pos = None  # Initial target bone position (for delta-based movement)
        self._drag_initial_mouse_pos = None  # Initial mouse position (for delta-based movement)

        # Try to detect base body mesh from active armature
        if context.active_object and context.active_object.type == 'ARMATURE':
            self._base_body_mesh = find_base_body_mesh(context, context.active_object)
            if self._base_body_mesh:
                print(f"  Using base mesh: {self._base_body_mesh.name}")

        # Start modal
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set("DAZ Bone Select Active - Click to select, P to pin, ESC to exit")

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
        print("=== DAZ Bone Select & Pin Stopped ===\n")

    def check_hover(self, context, event):
        """Check what's under mouse using dual raycast (prioritizes body mesh)"""

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
        # Prioritize body if it's close behind clothing (within 0.15 units)
        final_mesh = None
        final_location = None

        if body_mesh and body_location:
            # We hit both clothing and body
            distance_difference = body_distance - closest_distance

            if distance_difference < 0.15:  # Body is close behind clothing
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

        # If bone shouldn't use IK (twist bones, etc.), abort
        if not ik_bone_name:
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

        # NEW: Unpack the 3 return values from create_ik_chain
        target_bone_name, ik_control_names, daz_bone_names = result

        # Store bone names
        self._ik_target_bone_name = target_bone_name
        self._ik_control_bone_names = ik_control_names
        self._ik_daz_bone_names = daz_bone_names

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

        # NOW activate IK constraint after target is positioned
        # IK starts disabled (influence 0.0), so bones stay exactly where they are
        # On first move, we activate IK (0.0 → 1.0) and it starts solving
        ik_tip_bone = self._drag_armature.pose.bones[self._ik_control_bone_names[-1]]
        for constraint in ik_tip_bone.constraints:
            if constraint.name == "IK_Temp" and constraint.influence < 0.5:
                constraint.influence = 1.0
                print(f"  Activated IK constraint (influence 0.0 → 1.0)")
                break

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

        # Dissolve IK chain (remove constraints, delete .ik bones)
        # Pass keyframe=False if canceling to skip baking
        dissolve_ik_chain(
            self._drag_armature,
            self._ik_target_bone_name,
            self._ik_control_bone_names,
            self._ik_daz_bone_names,
            keyframe=(not cancel)
        )

        # Clear drag state
        self._is_dragging = False
        self._drag_bone_name = None
        self._drag_armature = None
        self._ik_target_bone_name = None
        self._ik_control_bone_names = []
        self._ik_daz_bone_names = []
        self._drag_plane_normal = None
        self._drag_plane_point = None
        self._drag_depth_reference = None
        self._drag_initial_target_pos = None
        self._drag_initial_mouse_pos = None
        self._mouse_down_pos = None

        # Update header
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


def register():
    bpy.utils.register_class(VIEW3D_OT_daz_bone_select)

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


def unregister():
    bpy.utils.unregister_class(VIEW3D_OT_daz_bone_select)

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.get('3D View')
        if km:
            for kmi in km.keymap_items:
                if kmi.idname == VIEW3D_OT_daz_bone_select.bl_idname:
                    km.keymap_items.remove(kmi)


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

    if result == (None, None, None):
        print("\n✗ FAILED")
        return

    target_name, ik_names, daz_names = result

    print("\n✓ SUCCESS: IK chain created!")
    print(f"  Target: {target_name}")
    print(f"  IK bones: {ik_names}")
    print(f"  DAZ bones: {daz_names}")

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
