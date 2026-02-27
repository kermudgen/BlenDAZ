"""
DAZ Bone Select & Pin & PowerPose
Combines fast hover preview, bone selection, pin marking system, and PowerPose panel posing
"""

# CRITICAL: Add module path BEFORE any local imports
import sys
import os

# Always add the BlenDAZ directory to path (required for imports)
BLENDAZ_DIR = r"D:\dev\BlenDAZ"
if BLENDAZ_DIR not in sys.path:
    sys.path.insert(0, BLENDAZ_DIR)
    print(f"[DAZ] Added to sys.path: {BLENDAZ_DIR}")

# Now safe to import Blender modules and local modules
import bpy
from bpy_extras import view3d_utils
from mathutils import Vector, Euler, Quaternion, Matrix
from mathutils.bvhtree import BVHTree
import gpu
from gpu_extras.batch import batch_for_shader
import blf
import math

# Import shared utilities from daz_shared_utils
import daz_shared_utils
from daz_shared_utils import (
    apply_rotation_from_delta,
    decompose_swing_twist
)

# Import IK templates (extracted for maintainability)
import ik_templates
from ik_templates import (
    get_ik_template,
    calculate_pole_position
)

# Import bone utilities (extracted for maintainability)
import bone_utils
from bone_utils import (
    is_twist_bone,
    is_pectoral,
    get_ik_target_bone,
    calculate_chain_length_skipping_twists,
    get_smart_chain_length
)

# Import DSF face groups for clean zone detection
import dsf_face_groups

# Force reload of imported modules when script is reloaded (Alt+R in Blender)
# Without this, Python caches old versions of imported modules
import importlib
importlib.reload(daz_shared_utils)
importlib.reload(ik_templates)
importlib.reload(bone_utils)
importlib.reload(dsf_face_groups)

# Re-import after reload to get fresh versions
from daz_shared_utils import apply_rotation_from_delta, decompose_swing_twist
from ik_templates import get_ik_template, calculate_pole_position
from bone_utils import is_twist_bone, is_pectoral, get_ik_target_bone, calculate_chain_length_skipping_twists, get_smart_chain_length


bl_info = {
    "name": "DAZ Bone Select & Pin & PowerPose",
    "version": (1, 2, 0),
    "blender": (3, 0, 0),
    "description": "Hover to preview, click to select, pin bones for IK, PowerPose panel posing",
    "category": "Rigging",
}

# DEBUG MODE: Set to True to preserve IK chain for inspection
DEBUG_PRESERVE_IK_CHAIN = False  # Set to True to keep IK chain for inspection

# DEBUG: Visual overlay for analytical leg IK solver
# Set to True to draw hip, target, thigh_dir, bend_normal, knee, foot markers in viewport
_DEBUG_DRAW_ANALYTICAL_LEG = False

# DEBUG: Visual overlay for analytical arm IK solver
_DEBUG_DRAW_ANALYTICAL_ARM = False

# DEBUG VERBOSITY: Controls console output
# 0 = Quiet (errors only)
# 1 = Normal (key events: drag start/end, IK activation, snaps)
# 2 = Verbose (all current output)
DEBUG_VERBOSITY = 1

def debug_print(msg, level=2):
    """Print debug message if verbosity level allows it."""
    if DEBUG_VERBOSITY >= level:
        print(msg)


# ============================================================================
# RIG PREPARATION - Convert DAZ rig to quaternion mode
# ============================================================================
# DAZ rigs use Euler rotations by default, but quaternions are better for IK:
# - No gimbal lock
# - Smoother interpolation
# - Simpler math (no mode checks everywhere)

_prepared_armatures = set()  # Track which armatures have been converted

def _get_driven_rotation_bones(armature):
    """
    Find bones that have drivers on their rotation_euler channels.

    Diffeomorphic FACS joint morphs (facs_jnt_*) create drivers that target
    rotation_euler on jaw, tongue, and eye bones.  Converting these bones to
    quaternion mode causes Blender to stop evaluating those drivers, breaking
    the bone-driven part of morphs while mesh-level shape keys still fire.

    Returns:
        set of bone names that must stay in their original rotation mode.
    """
    driven = set()
    if not armature.animation_data or not armature.animation_data.drivers:
        return driven

    for driver in armature.animation_data.drivers:
        dp = driver.data_path
        # Match patterns like: pose.bones["lowerJaw"].rotation_euler
        if 'pose.bones[' in dp and 'rotation_euler' in dp:
            # Extract bone name from data_path
            try:
                bone_name = dp.split('"')[1]
                driven.add(bone_name)
            except (IndexError, KeyError):
                pass
    return driven


def prepare_rig_for_ik(armature, force=False):
    """
    Convert bones in armature to quaternion rotation mode.

    Skips bones that have Diffeomorphic rotation_euler drivers (FACS joint
    morphs for jaw, tongue, eyes, etc.) — converting those would break the
    driver evaluation chain.

    This should be called once when first interacting with a DAZ rig.
    Preserves current visual rotation when converting from Euler.

    Args:
        armature: The armature object
        force: If True, re-prepare even if already done

    Returns:
        Number of bones converted
    """
    if not armature or armature.type != 'ARMATURE':
        return 0

    # Check if already prepared
    armature_id = id(armature.data)
    if armature_id in _prepared_armatures and not force:
        return 0

    # Find bones with rotation_euler drivers (Diffeomorphic FACS joint morphs)
    # These MUST stay in Euler mode or their drivers stop working
    driven_bones = _get_driven_rotation_bones(armature)

    converted_count = 0
    euler_bones = []
    skipped_bones = []

    for pose_bone in armature.pose.bones:
        if pose_bone.rotation_mode != 'QUATERNION':
            # Skip bones with rotation_euler drivers
            if pose_bone.name in driven_bones:
                skipped_bones.append(pose_bone.name)
                continue

            euler_bones.append(pose_bone.name)

            # Convert current rotation to quaternion BEFORE changing mode
            if pose_bone.rotation_mode == 'AXIS_ANGLE':
                # Axis-angle to quaternion
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

    if converted_count > 0:
        print(f"  [RIG PREP] Converted {converted_count} bones to quaternion mode")
        if DEBUG_VERBOSITY >= 2:
            print(f"    Bones: {', '.join(euler_bones[:10])}{'...' if len(euler_bones) > 10 else ''}")
    if skipped_bones:
        print(f"  [RIG PREP] Kept {len(skipped_bones)} bones in Euler (have rotation drivers): "
              f"{', '.join(skipped_bones[:10])}{'...' if len(skipped_bones) > 10 else ''}")

    _prepared_armatures.add(armature_id)
    return converted_count


def is_rig_prepared(armature):
    """Check if armature has been prepared for IK."""
    if not armature:
        return False
    return id(armature.data) in _prepared_armatures


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
    Raycast against a specific mesh object using the object's native ray_cast method.
    Object.ray_cast uses Blender's internal BVH (built once, cached by Blender) and
    operates in object local space — no Python-side BVH construction needed.
    Returns: (hit_location_world, distance) or (None, None)
    """
    try:
        # Transform ray to object local space
        matrix_inv = mesh_obj.matrix_world.inverted()
        origin_local = matrix_inv @ ray_origin
        direction_local = matrix_inv.to_3x3() @ ray_direction

        # ray_cast uses Blender's internal cached BVH — no rebuild cost
        result, location, normal, index = mesh_obj.ray_cast(origin_local, direction_local)

        if result:
            location_world = mesh_obj.matrix_world @ location
            distance = (location_world - ray_origin).length
            return location_world, distance

        return None, None

    except Exception as e:
        print(f"  Raycast error for {mesh_obj.name}: {e}")
        return None, None


def create_ik_chain(armature, bone_name, chain_length=None, ignore_pin_on_bone=None, soft_pin_mode=False):
    """
    Create IK chain with BONE targets and Copy Rotation constraints.

    Architecture:
    1. Create .ik control bones (have IK constraints)
    2. Create .ik.target bone (what you drag - no parent)
    3. Add Copy Rotation constraints from DAZ bones to .ik bones

    Args:
        ignore_pin_on_bone: Bone name to ignore pin checks on (for temporarily overriding pins)

    Returns: (target_bone_name, ik_control_bone_names, daz_bone_names, shoulder_target_names, leg_prebend_applied, swing_twist_pairs)
    """
    # CRITICAL: Force update to ensure all manual rotations/transforms are applied
    # This captures any R rotations or G moves the user made between IK drags
    bpy.context.view_layer.update()

    if bone_name not in armature.pose.bones:
        print(f"✗ Bone '{bone_name}' not found")
        return None, None, None

    clicked_bone = armature.pose.bones[bone_name]

    # ==================================================================
    # STEP 0: Look up IK rig template for this bone type
    # ==================================================================
    ik_template = get_ik_template(bone_name)
    if ik_template:
        print(f"Creating IK chain for: {bone_name} (using template: {ik_template['description']})")
        # Use template chain length
        if chain_length is None:
            chain_length = ik_template['chain_length']
    else:
        print(f"Creating IK chain for: {bone_name} (no template - using fallback)")
        # Fallback to old logic if no template
        if chain_length is None:
            chain_length = get_smart_chain_length(bone_name)

    # ==================================================================
    # STEP 0.5: Clean up any existing temp IK chain (from previous drag in debug mode)
    # ==================================================================
    # In debug mode (DEBUG_PRESERVE_IK_CHAIN = True), old chains persist between drags
    # We need to dissolve them before creating new ones to prevent conflicts
    if DEBUG_PRESERVE_IK_CHAIN:
        # Look for existing .ik bones and dissolve the chain
        existing_target = None
        for bone in armature.pose.bones:
            if bone.name.endswith('.ik.target') and bone_name.lower() in bone.name.lower():
                # Found a target bone from previous drag - extract base name
                # e.g., "lFoot.ik.target" → base is "lFoot.ik.target"
                existing_target = bone.name
                break

        if existing_target:
            print(f"  [DEBUG] Found existing IK chain, dissolving: {existing_target}")

            # CRITICAL FIX: Bake constraint-applied rotations INTO bone rotation values
            # The Copy Rotation constraint REPLACES bone rotation but doesn't modify rotation_quaternion.
            # If we just remove constraints, bones snap back to their original pose.
            # Solution: Extract final rotation from bone matrix and set it as the new rotation value.
            bpy.context.view_layer.update()
            depsgraph = bpy.context.evaluated_depsgraph_get()
            armature_eval = armature.evaluated_get(depsgraph)

            baked_count = 0
            for pose_bone in armature.pose.bones:
                # Only bake bones that have IK_CopyRot_Temp constraint active
                has_active_copy_rot = any(
                    c.name == "IK_CopyRot_Temp" and c.influence > 0
                    for c in pose_bone.constraints
                )
                if has_active_copy_rot:
                    # Get evaluated bone's final matrix (includes constraint effects)
                    bone_eval = armature_eval.pose.bones[pose_bone.name]

                    # Extract local rotation from the final matrix
                    # bone.matrix is in armature space, we need local rotation
                    if pose_bone.parent:
                        # Local matrix = inverse(parent_matrix) @ bone_matrix
                        parent_eval = armature_eval.pose.bones[pose_bone.parent.name]
                        local_matrix = parent_eval.matrix.inverted() @ bone_eval.matrix
                    else:
                        local_matrix = bone_eval.matrix

                    # Decompose to get rotation
                    loc, rot, scale = local_matrix.decompose()

                    # Set the bone's actual rotation to match the constraint result
                    if pose_bone.rotation_mode == 'QUATERNION':
                        pose_bone.rotation_quaternion = rot
                    else:
                        pose_bone.rotation_euler = rot.to_euler(pose_bone.rotation_mode)
                    baked_count += 1

            if baked_count > 0:
                print(f"  [DEBUG] Baked {baked_count} constraint rotations into bone values")

            # Now safe to remove constraints - bones will stay in place
            for pose_bone in armature.pose.bones:
                constraints_to_remove = [c for c in pose_bone.constraints
                                        if 'IK_Temp' in c.name or 'IK_CopyRot_Temp' in c.name or
                                           'IK_Pin_Temp' in c.name or 'Shoulder_Track_Temp' in c.name]
                for constraint in constraints_to_remove:
                    pose_bone.constraints.remove(constraint)

            # CRITICAL: Cache baked rotations and locations BEFORE mode switch
            # Mode switching (POSE → EDIT → POSE) discards un-keyframed transforms
            # We just baked the constraint results - cache them now to preserve across mode switch
            baked_rotation_cache = {}
            baked_location_cache = {}
            for pose_bone in armature.pose.bones:
                if pose_bone.rotation_mode == 'QUATERNION':
                    baked_rotation_cache[pose_bone.name] = pose_bone.rotation_quaternion.copy()
                else:
                    baked_rotation_cache[pose_bone.name] = pose_bone.rotation_euler.copy()
                if pose_bone.bone.parent is None or pose_bone.location.length_squared > 1e-8:
                    baked_location_cache[pose_bone.name] = pose_bone.location.copy()

            # Switch to edit mode to delete old .ik bones
            bpy.ops.object.mode_set(mode='EDIT')
            edit_bones = armature.data.edit_bones
            bones_to_remove = [b.name for b in edit_bones if '.ik' in b.name or '.shoulder.target' in b.name]
            for bone_name_to_remove in bones_to_remove:
                if bone_name_to_remove in edit_bones:
                    edit_bones.remove(edit_bones[bone_name_to_remove])
            bpy.ops.object.mode_set(mode='POSE')

            # CRITICAL: Restore baked rotations and locations AFTER mode switch
            # This preserves the first drag's pose for the second drag
            for bone_name_cache, rotation in baked_rotation_cache.items():
                pose_bone = armature.pose.bones.get(bone_name_cache)
                if pose_bone:
                    if pose_bone.rotation_mode == 'QUATERNION':
                        pose_bone.rotation_quaternion = rotation
                    else:
                        pose_bone.rotation_euler = rotation
            for bone_name_cache, loc in baked_location_cache.items():
                pose_bone = armature.pose.bones.get(bone_name_cache)
                if pose_bone:
                    pose_bone.location = loc

            bpy.context.view_layer.update()
            print(f"  [DEBUG] Cleaned up {len(bones_to_remove)} old .ik bones, restored {len(baked_rotation_cache)} baked rotations")

    # ==================================================================
    # STEP 1: Collect non-twist, non-pectoral bones for the chain
    # ==================================================================
    daz_bones = []  # PoseBones
    current = clicked_bone

    # Walk up collecting bones (exclude twist and pectoral bones)
    # IMPORTANT: Stop at pinned bones - they act as anchor points for the chain
    while current and len(daz_bones) < chain_length:
        # Check if current bone is pinned (and not the ignored bone)
        data_bone = armature.data.bones.get(current.name)
        is_pinned = (data_bone and
                     current.name != ignore_pin_on_bone and
                     (is_bone_pinned_translation(data_bone) or is_bone_pinned_rotation(data_bone)))

        if is_pinned:
            # Found a pinned bone - include it as the root anchor and stop
            if not is_twist_bone(current.name) and not is_pectoral(current.name):
                daz_bones.append(current)
                print(f"  Found pinned bone {current.name} - stopping chain here (anchor point)")
            break

        if not is_twist_bone(current.name) and not is_pectoral(current.name):
            daz_bones.append(current)

        current = current.parent

    if len(daz_bones) < 2:
        print(f"  ✗ Not enough bones for IK chain")
        return None, None, None

    # Reverse so we have root-to-tip order
    daz_bones = list(reversed(daz_bones))

    # ==================================================================
    # Get evaluated armature for posed positions (needed for pinned child handling below)
    # ==================================================================
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    armature_eval = armature.evaluated_get(depsgraph)

    # ==================================================================
    # EXTENSION: Include pinned children in the chain
    # ==================================================================
    # If the tip bone (clicked bone) has pinned descendants, extend the chain to include them
    # This allows IK to respect pins on child bones (e.g., pinned hand when dragging forearm)
    # Recursively search through twist bones to find pinned children
    # IMPORTANT: Stop at hands/feet - don't extend into fingers/toes

    def find_pinned_descendant(bone, depth=0):
        """Recursively find first pinned descendant, skipping twist/pectoral/finger bones"""
        if depth > 5:  # Safety limit to prevent infinite recursion
            return None

        for child in bone.children:
            child_lower = child.name.lower()

            # Skip fingers and toes (don't extend into digits)
            finger_toe_parts = ['thumb', 'index', 'mid', 'ring', 'pinky', 'carpal', 'metacarpal', 'toe', 'metatarsal']
            if any(part in child_lower for part in finger_toe_parts):
                continue

            # Skip ignored bone
            if child.name == ignore_pin_on_bone:
                continue

            # If twist/pectoral bone, recursively check its children (don't add twist bone to chain)
            if is_twist_bone(child.name) or is_pectoral(child.name):
                result = find_pinned_descendant(child, depth + 1)
                if result:
                    return result
                continue

            # Non-twist bone - check if pinned
            child_data_bone = armature.data.bones.get(child.name)
            if child_data_bone and (is_bone_pinned_translation(child_data_bone) or is_bone_pinned_rotation(child_data_bone)):
                return child

            # Not pinned - recursively check its children
            result = find_pinned_descendant(child, depth + 1)
            if result:
                return result

        return None

    tip_bone = daz_bones[-1]  # This is the clicked bone (at the tip after reversal)
    pinned_child = find_pinned_descendant(tip_bone)

    # Initialize pinned child world position variables
    pinned_child_world_head = None
    pinned_child_world_tail = None

    if pinned_child:
        daz_bones.append(pinned_child)
        # Capture pinned child's CURRENT POSED world position for soft pin mode target
        # PoseBone.head/tail already give posed positions in armature space
        pinned_child_eval = armature_eval.pose.bones[pinned_child.name]
        pinned_child_world_head = armature.matrix_world @ Vector(pinned_child_eval.head)
        pinned_child_world_tail = armature.matrix_world @ Vector(pinned_child_eval.tail)
        print(f"  ✓ Extended chain to include pinned descendant: {pinned_child.name}")

    daz_bone_names = [b.name for b in daz_bones]

    print(f"  Chain: {' → '.join(daz_bone_names)}")

    # Detect collar bones in chain for Damped Track setup (prevents collar snapping)
    collar_bones = [name for name in daz_bone_names if 'collar' in name.lower() or 'clavicle' in name.lower()]
    if collar_bones:
        print(f"  Detected collar bones: {', '.join(collar_bones)} - will add Damped Track constraints")

    # ==================================================================
    # STEP 1.5: Capture current world position of clicked bone BEFORE entering EDIT mode
    # ==================================================================
    # CRITICAL: Force fresh evaluation AFTER cleanup to ensure restored rotations are included
    bpy.context.view_layer.update()
    # Refresh evaluated armature (may have changed since pinned child handling)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    armature_eval = armature.evaluated_get(depsgraph)
    clicked_bone_eval = armature_eval.pose.bones[bone_name]

    # PoseBone.head/tail already give posed positions in armature space - just transform to world
    clicked_bone_world_head = armature.matrix_world @ Vector(clicked_bone_eval.head)
    clicked_bone_world_tail = armature.matrix_world @ Vector(clicked_bone_eval.tail)
    print(f"  DEBUG: Captured {bone_name} EVALUATED world tail: {clicked_bone_world_tail}")

    # ==================================================================
    # STEP 1.6: Cache ALL bone rotations and locations BEFORE mode switch
    # ==================================================================
    # Mode switching (POSE → EDIT → POSE) discards un-keyframed transforms
    # Cache them now so we can restore after returning to POSE mode
    rotation_cache = {}
    location_cache = {}
    for pose_bone in armature.pose.bones:
        if pose_bone.rotation_mode == 'QUATERNION':
            rotation_cache[pose_bone.name] = pose_bone.rotation_quaternion.copy()
        else:
            rotation_cache[pose_bone.name] = pose_bone.rotation_euler.copy()
        # Cache location for root bones and any with non-zero location (e.g., hip)
        if pose_bone.bone.parent is None or pose_bone.location.length_squared > 1e-8:
            location_cache[pose_bone.name] = pose_bone.location.copy()
    print(f"  Cached rotations for {len(rotation_cache)} bones, locations for {len(location_cache)} bones before mode switch")

    # ==================================================================
    # STEP 1.7: Capture POSED world positions for all bones in chain
    # ==================================================================
    # CRITICAL: We need .ik bones to start at POSED positions, not REST positions
    # Edit mode shows bones at REST, so we capture POSED positions here and use them later
    posed_positions = {}
    for daz_pose_bone in daz_bones:
        bone_eval = armature_eval.pose.bones[daz_pose_bone.name]
        posed_positions[daz_pose_bone.name] = {
            'head': armature.matrix_world @ Vector(bone_eval.head),
            'tail': armature.matrix_world @ Vector(bone_eval.tail)
            # Note: roll will be copied from edit bone (doesn't change with pose)
        }
    print(f"  Captured POSED positions for {len(posed_positions)} bones in chain")

    # ==================================================================
    # STEP 2: Switch to EDIT mode and create all bones
    # ==================================================================
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = armature.data.edit_bones

    ik_control_names = []
    prev_ik_edit = None
    armature_inv = armature.matrix_world.inverted()

    # Create IK control bones with proper parent hierarchy
    for i, daz_pose_bone in enumerate(daz_bones):
        daz_edit = edit_bones[daz_pose_bone.name]

        # Create IK control bone
        ik_name = f"{daz_pose_bone.name}.ik"
        ik_edit = edit_bones.new(ik_name)

        # CRITICAL: Set to POSED positions (captured before mode switch)
        # This ensures .ik bones start where DAZ bones actually are, not at REST positions
        posed = posed_positions[daz_pose_bone.name]
        ik_edit.head = armature_inv @ posed['head']
        ik_edit.tail = armature_inv @ posed['tail']
        ik_edit.roll = daz_edit.roll  # Roll from edit bone (doesn't change with pose)
        ik_edit.use_deform = False  # Don't deform mesh

        # CRITICAL: Set parent to previous IK bone (creates chain)
        if prev_ik_edit:
            ik_edit.parent = prev_ik_edit
            # NOTE: DO NOT force-connect bones - preserve DAZ bone offsets
            # Force-connecting creates a straight chain, but DAZ spine bones have offsets.
            # When Copy Rotation activates, DAZ bones snap/arch trying to match the straight chain.
            # prev_ik_edit.tail = ik_edit.head.copy()  # ← DISABLED
            print(f"  Parented {prev_ik_edit.name} → {ik_name} (preserving offset)")
        else:
            # Root .ik bone: NO parent — rest position is already at the correct
            # posed world position (captured at STEP 1.7). Parenting to a DAZ bone
            # would double-transform: the parent's pose would be applied ON TOP of
            # the already-posed rest offset, causing the chain to start at the wrong
            # location when the hip/spine has been moved or rotated.
            ik_edit.parent = None

        ik_control_names.append(ik_name)
        prev_ik_edit = ik_edit

    # Create IK TARGET bone (what animator drags)
    # This has NO parent - free to move
    target_name = f"{bone_name}.ik.target"
    target_edit = edit_bones.new(target_name)

    # CRITICAL: Position at correct bone's CURRENT world position (not rest position)
    # Convert world positions back to armature local space
    armature_inv = armature.matrix_world.inverted()

    # Get target offset from template (larger for head bones to position above mesh)
    offset_distance = ik_template.get('target_offset', 0.1) if ik_template else 0.1

    # In soft pin mode, position target at PINNED CHILD's TIP (tail) to prevent snap
    # Otherwise, position at clicked bone's TIP (tail) to prevent spine arching
    if soft_pin_mode and pinned_child_world_head is not None:
        # CRITICAL: Position target at TAIL of pinned child, not spanning the whole bone
        # This prevents the IK from pulling toward the hand's base instead of its tip
        target_edit.head = armature_inv @ pinned_child_world_tail  # At tip
        target_offset = Vector((0, 0, offset_distance))
        target_edit.tail = armature_inv @ (pinned_child_world_tail + target_offset)
        print(f"  Positioned IK target at pinned child tip for zero-snap initialization")
    else:
        # CRITICAL: Position target at TAIL of clicked bone, not spanning the whole bone
        # This prevents the IK from pulling the spine to meet the bone's head position
        target_local = armature_inv @ clicked_bone_world_tail
        target_edit.head = target_local  # At tip
        print(f"  DEBUG: Target local pos: {target_local}, from world: {clicked_bone_world_tail}")
        # Create a small bone extending upward (for visibility and manipulation)
        target_offset = Vector((0, 0, offset_distance))
        target_edit.tail = armature_inv @ (clicked_bone_world_tail + target_offset)
        print(f"  Target offset: {offset_distance}m ({'template' if ik_template and 'target_offset' in ik_template else 'default'})")

    # Copy roll from rest position (roll doesn't change with posing)
    clicked_edit = edit_bones[bone_name]
    target_edit.roll = clicked_edit.roll

    target_edit.parent = None  # CRITICAL: No parent for free movement
    target_edit.use_deform = False

    # ==================================================================
    # Create POLE TARGET bone using template settings
    # ==================================================================
    pole_target_name = None

    # Detect chain types (for pole target and pre-bend logic)
    is_leg_chain = any(any(part in bone_name.lower() for part in ['shin', 'thigh', 'foot', 'leg'])
                       for bone_name in daz_bone_names)
    is_arm_chain = any(any(part in bone_name.lower() for part in ['shldr', 'shoulder', 'forearm', 'hand'])
                       for bone_name in daz_bone_names)

    # CRITICAL: Skip poles for arm chains entirely - DAZ bend/twist bones don't work with poles
    # Source: Diffeomorphic research + Grok analysis
    if is_arm_chain:
        print(f"  [DAZ COMPAT] Pole target SKIPPED for arm chain (Bend/Twist bone compatibility)")
    # Only allow poles for legs (if template enables them)
    elif not is_arm_chain and ik_template and ik_template.get('pole_target', {}).get('enabled'):
        # Calculate pole position using template method
        pole_positions = calculate_pole_position(
            ik_template,
            posed_positions,
            daz_bones,
            clicked_bone_world_tail,
            armature
        )

        if pole_positions:
            pole_world_head, pole_world_tail = pole_positions
            pole_target_name = target_name + ".pole"
            pole_target_edit = edit_bones.new(pole_target_name)

            # Set pole position (already calculated in world space)
            pole_target_edit.head = armature_inv @ pole_world_head
            pole_target_edit.tail = armature_inv @ pole_world_tail
            pole_target_edit.roll = clicked_edit.roll
            pole_target_edit.parent = None  # No parent - free bone
            pole_target_edit.use_deform = False
            print(f"  ✓ Created pole target: {pole_target_name} (template-based)")
    elif soft_pin_mode and not is_arm_chain:
        # Fallback: soft pin mode (lever/fulcrum) - position at clicked bone
        # But NEVER for arm chains
        pole_target_name = target_name + ".pole"
        pole_target_edit = edit_bones.new(pole_target_name)
        pole_target_edit.head = armature_inv @ clicked_bone_world_head
        pole_target_edit.tail = armature_inv @ clicked_bone_world_tail
        pole_target_edit.roll = clicked_edit.roll
        pole_target_edit.parent = None
        pole_target_edit.use_deform = False
        print(f"  ✓ Created pole target: {pole_target_name} (soft pin mode)")

    # Create shoulder target bones for collar guidance (prevents collar snapping)
    shoulder_target_names = []
    if collar_bones:
        for collar_name in collar_bones:
            shoulder_target_name = f"{collar_name}.shoulder.target"
            shoulder_target_edit = edit_bones.new(shoulder_target_name)

            # Position at SHOULDER bone (next bone in chain), not collar's tail
            # DAZ order: Collar → Shoulder → Twist → Forearm (twist bones come AFTER joints)
            # Shoulder target should point at the shoulder joint, not collar's tail
            collar_idx = daz_bone_names.index(collar_name)

            # Find the next bone in chain after collar (should be shoulder)
            if collar_idx + 1 < len(daz_bones):
                shoulder_bone_name = daz_bones[collar_idx + 1].name
                # Use POSED position from our captured positions ✅
                shoulder_world_head = posed_positions[shoulder_bone_name]['head']

                shoulder_target_edit.head = armature_inv @ shoulder_world_head  # At shoulder joint
                # Create small bone extending outward for visibility
                target_offset = Vector((0.05, 0, 0))  # 5cm outward offset
                shoulder_target_edit.tail = armature_inv @ (shoulder_world_head + target_offset)
            else:
                # Fallback: use collar tail if no next bone (shouldn't happen)
                # Use POSED position from our captured positions ✅
                collar_world_tail = posed_positions[collar_name]['tail']
                shoulder_target_edit.head = armature_inv @ collar_world_tail
                target_offset = Vector((0.05, 0, 0))
                shoulder_target_edit.tail = armature_inv @ (collar_world_tail + target_offset)
            shoulder_target_edit.roll = edit_bones[collar_name].roll
            shoulder_target_edit.parent = None  # Free to move
            shoulder_target_edit.use_deform = False

            shoulder_target_names.append(shoulder_target_name)
            print(f"  Created shoulder target: {shoulder_target_name}")

    # ==================================================================
    # STEP 3: Switch to POSE mode and copy initial pose
    # ==================================================================
    bpy.ops.object.mode_set(mode='POSE')

    # ==================================================================
    # STEP 3.1: RESTORE all cached bone rotations after mode switch
    # ==================================================================
    # Mode switch discarded un-keyframed transforms - restore them now
    rotations_restored = 0
    for bone_name_cache, rotation in rotation_cache.items():
        pose_bone = armature.pose.bones.get(bone_name_cache)
        if pose_bone:
            if pose_bone.rotation_mode == 'QUATERNION':
                pose_bone.rotation_quaternion = rotation
            else:
                pose_bone.rotation_euler = rotation
            rotations_restored += 1
    if rotations_restored > 0:
        print(f"  ✓ Restored {rotations_restored} bone rotations after mode switch")

    # Restore bone locations (hip, any translated bones)
    for bone_name_cache, loc in location_cache.items():
        pose_bone = armature.pose.bones.get(bone_name_cache)
        if pose_bone:
            pose_bone.location = loc

    # CRITICAL: Update after mode switch to ensure pose is current
    # This ensures any manual rotations (R key) are properly loaded
    bpy.context.view_layer.update()

    # CRITICAL: Get evaluated armature to read keyframed values
    # The raw armature.pose.bones don't include keyframe data
    # The evaluated depsgraph includes all keyframes and constraints
    depsgraph = bpy.context.evaluated_depsgraph_get()
    armature_eval = armature.evaluated_get(depsgraph)

    # === CRITICAL: STRONG POSE MATCHING (prevents flip on 2nd+ drags) ===
    # We need each .ik bone to start at the same armature-space position as its
    # corresponding DAZ bone. Setting ik_bone.matrix works, but child .ik bones
    # require their parent .ik bone to already have the correct world matrix —
    # otherwise Blender uses the stale parent matrix and computes the wrong local
    # rotation, putting the child in the wrong world position.
    # FIX: call view_layer.update() after each bone so the next bone's parent is current.
    print("  [INIT] Strong pose matching: forcing .ik bones to exact current DAZ pose")

    for i, (daz_name, ik_name) in enumerate(zip(daz_bone_names, ik_control_names)):
        # Read from EVALUATED bone (includes keyframes)
        daz_bone_eval = armature_eval.pose.bones[daz_name]
        # Write to RAW bone (we're setting it)
        daz_bone = armature.pose.bones[daz_name]
        ik_bone = armature.pose.bones[ik_name]

        # Force QUATERNION mode first so the matrix setter uses quaternion storage
        ik_bone.rotation_mode = 'QUATERNION'

        # Copy armature-space matrix from the evaluated DAZ bone
        ik_bone.matrix = daz_bone_eval.matrix.copy()

        # Extra safety: copy location explicitly (important for pinned/offset bones)
        ik_bone.location = daz_bone_eval.location.copy()

        # CRITICAL: Update after each bone before processing the next one.
        # Child .ik bones compute their local rotation relative to their parent .ik bone.
        # Without this update, the parent's matrix is stale and child ends up at the
        # wrong world position (which LIMIT_ROTATION then clamps, causing snapping).
        bpy.context.view_layer.update()

        print(f"  Bone {i}: {daz_name} → {ik_name} (matrix + location copied, updated)")
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

        # FALLBACK: If DAZ bone has no IK limits but has a LIMIT_ROTATION constraint,
        # read the constraint's min/max values and apply as IK limits on the .ik bone.
        # Diffeomorphic sets LIMIT_ROTATION constraints (not IK limit properties).
        if not (daz_bone.use_ik_limit_x or daz_bone.use_ik_limit_y or daz_bone.use_ik_limit_z):
            for constraint in daz_bone.constraints:
                if constraint.type == 'LIMIT_ROTATION' and not constraint.mute:
                    if constraint.use_limit_x:
                        ik_bone.use_ik_limit_x = True
                        ik_bone.ik_min_x = constraint.min_x
                        ik_bone.ik_max_x = constraint.max_x
                    if constraint.use_limit_y:
                        ik_bone.use_ik_limit_y = True
                        ik_bone.ik_min_y = constraint.min_y
                        ik_bone.ik_max_y = constraint.max_y
                    if constraint.use_limit_z:
                        ik_bone.use_ik_limit_z = True
                        ik_bone.ik_min_z = constraint.min_z
                        ik_bone.ik_max_z = constraint.max_z
                    import math as _math
                    limits_str = []
                    if constraint.use_limit_x:
                        limits_str.append(f"X:[{_math.degrees(constraint.min_x):.0f}°,{_math.degrees(constraint.max_x):.0f}°]")
                    if constraint.use_limit_y:
                        limits_str.append(f"Y:[{_math.degrees(constraint.min_y):.0f}°,{_math.degrees(constraint.max_y):.0f}°]")
                    if constraint.use_limit_z:
                        limits_str.append(f"Z:[{_math.degrees(constraint.min_z):.0f}°,{_math.degrees(constraint.max_z):.0f}°]")
                    print(f"  [LIMIT_ROTATION→IK] {daz_name}: {', '.join(limits_str)}")
                    break  # Only use first LIMIT_ROTATION constraint

        # SPECIAL CASE: Override knee IK limits to allow deeper bends
        # DAZ shin limits often stop at ~90°, but knees should bend to 150°+
        if 'shin' in daz_name.lower() or 'calf' in daz_name.lower():
            if ik_bone.use_ik_limit_x:
                import math as _math
                original_max_deg = _math.degrees(ik_bone.ik_max_x)

                # Expand max to allow deep bends (150° = 2.62 radians)
                ik_bone.ik_max_x = max(ik_bone.ik_max_x, 2.62)

                new_max_deg = _math.degrees(ik_bone.ik_max_x)
                if new_max_deg > original_max_deg:
                    print(f"  [KNEE OVERRIDE] {daz_name}: max X {original_max_deg:.0f}° → {new_max_deg:.0f}°")

        # Lock IK axes if DAZ bone has them locked
        ik_bone.lock_ik_x = daz_bone.lock_ik_x
        ik_bone.lock_ik_y = daz_bone.lock_ik_y
        ik_bone.lock_ik_z = daz_bone.lock_ik_z

        # SPECIAL: Force shin/knee to only bend forward/back (prevent sideways bend/twist)
        # This solves the IK ambiguity problem when leg is straight
        daz_name_lower = daz_name.lower()
        if 'shin' in daz_name_lower or 'calf' in daz_name_lower:
            ik_bone.lock_ik_y = True  # Lock twist
            ik_bone.lock_ik_z = True  # Lock side-to-side bend
            # X axis stays unlocked for forward/back knee bend
            print(f"  Locked shin IK Y/Z axes (knee bends forward/back only): {ik_name}")

        # SPECIAL: Lock thigh twist axis to prevent twist accumulation across drags
        # Thigh can still swing (X = forward/back, Z = side-to-side) but not twist
        if 'thigh' in daz_name_lower:
            ik_bone.lock_ik_y = True  # Lock twist axis
            # X and Z stay unlocked for hip flexion/extension and abduction
            print(f"  Locked thigh IK Y axis (prevents twist): {ik_name}")

        # SPECIAL: Lock forearm/elbow to only bend forward/back (hinge joint)
        # Prevents twist accumulation across drags
        if 'forearm' in daz_name_lower:
            ik_bone.lock_ik_y = True  # Lock twist
            ik_bone.lock_ik_z = True  # Lock side-to-side
            # X axis stays unlocked for elbow flexion/extension
            print(f"  Locked forearm IK Y/Z axes (elbow bends only): {ik_name}")

        # SPECIAL: Lock shoulder twist axis — twist handled by lShldrTwist bone, not IK
        # Without this, the IK solver twists the shoulder freely, producing ~60° of
        # phantom twist that propagates down the chain
        if 'shldr' in daz_name_lower or 'shoulder' in daz_name_lower:
            ik_bone.lock_ik_y = True  # Lock twist axis
            # X (raise/lower) and Z (forward/back) stay unlocked
            print(f"  Locked shoulder IK Y axis (twist handled by twist bone): {ik_name}")

        # PHASE 3: IK Stiffness Assignment
        # Use template values if available, otherwise fall back to hardcoded defaults
        stiffness = 0.0
        daz_name_lower = daz_name.lower()

        # Check if bone is pinned OR has pinned children - if so, lock it completely (stiffness = 1.0)
        # Skip pin check for ignore_pin_on_bone (allows dragging pinned bone directly)
        data_bone = armature.data.bones.get(daz_name)
        is_pinned = (data_bone and
                     daz_name != ignore_pin_on_bone and
                     (is_bone_pinned_translation(data_bone) or is_bone_pinned_rotation(data_bone)))
        has_pinned_child = has_pinned_children(armature, daz_name, ignore_pin_on_bone)

        if is_pinned:
            # Pinned bones use constraints to maintain world transform (not IK stiffness locking)
            # This allows bones to "try to stay" at pinned location/rotation while still
            # being influenced by IK, matching DAZ Studio behavior
            pin_status = get_pin_status_text(data_bone)
            print(f"  ⚓ PINNED: {daz_name} - will add pin constraints, {pin_status}")
            # stiffness remains 0.0 for pinned bones - constraints handle the pinning
        else:
            # Try template stiffness first
            if ik_template:
                template_stiffness = ik_template['stiffness']
                # Check each pattern in template
                for pattern, value in template_stiffness.items():
                    if pattern in daz_name_lower:
                        stiffness = value
                        break

            # Fallback to hardcoded defaults for bones not in template
            if stiffness == 0.0 and not ik_template:
                if 'collar' in daz_name_lower or 'clavicle' in daz_name_lower:
                    stiffness = 0.75
                elif 'shldr' in daz_name_lower or 'shoulder' in daz_name_lower:
                    stiffness = 0.1
                elif 'chest' in daz_name_lower:
                    stiffness = 0.99
                elif 'abdomen' in daz_name_lower or 'spine' in daz_name_lower:
                    stiffness = 0.99
                elif 'hip' in daz_name_lower:
                    stiffness = 0.99
                    ik_bone.lock_ik_x = True
                    ik_bone.lock_ik_y = True
                    ik_bone.lock_ik_z = True
                    print(f"  Locked hip IK rotation (translation only, prevents character spinning)")
                elif 'pelvis' in daz_name_lower:
                    stiffness = 0.99

        if stiffness > 0:
            ik_bone.ik_stiffness_x = stiffness
            ik_bone.ik_stiffness_y = stiffness
            ik_bone.ik_stiffness_z = stiffness
            print(f"  IK stiffness: {daz_name} = {stiffness:.1f} (ragdoll parent)")

    # Update scene to lock in the pose matching
    bpy.context.view_layer.update()
    print("  [INIT] Pose matching complete - IK chain inherits current pose")
    # DIAG: Store .ik bone rotations after pose matching in a global we can read back
    import bpy as _bpy
    _diag = {}
    for ik_name in ik_control_names:
        ik_pb = armature.pose.bones.get(ik_name)
        if ik_pb:
            q = ik_pb.rotation_quaternion
            _diag[f"posematch_{ik_name}"] = (round(q.w,4),round(q.x,4),round(q.y,4),round(q.z,4))
    for daz_name in daz_bone_names:
        daz_pb = armature.pose.bones.get(daz_name)
        if daz_pb:
            e = daz_pb.rotation_euler
            _diag[f"daz_euler_{daz_name}"] = (round(e.x,4),round(e.y,4),round(e.z,4),daz_pb.rotation_mode)
    if not hasattr(_bpy, '_blendaz_diag'):
        _bpy._blendaz_diag = {}
    _bpy._blendaz_diag.update(_diag)

    # CRITICAL: ALWAYS lock rotation on the TIP bone (end of IK chain)
    # This prevents the IK solver from rotating the tip instead of moving it
    # The tip bone should only translate to reach the target, not rotate
    tip_bone = armature.pose.bones[ik_control_names[-1]]
    tip_bone_daz_name = daz_bone_names[-1]
    tip_lower = tip_bone_daz_name.lower()
    is_end_effector = any(part in tip_lower for part in ['hand', 'foot'])

    # Lock rotation for ALL tip bones (not just end effectors)
    tip_bone.lock_ik_x = True
    tip_bone.lock_ik_y = True
    tip_bone.lock_ik_z = True
    if is_end_effector:
        print(f"  Locked tip bone rotation (end effector): {tip_bone.name}")
    else:
        print(f"  Locked tip bone rotation (mid-limb): {tip_bone.name}")

    # NOTE: Intentionally NOT copying Limit Rotation constraints to IK limits
    # Reason: IK limits constrain the solver during solving (can prevent solutions)
    #         Limit Rotation constraints clamp AFTER solving (better for IK)
    # The workflow is:
    #   1. IK solves freely on .ik bones (except tip rotation is locked)
    #   2. Copy Rotation copies result to DAZ bones
    #   3. DAZ bones' Limit Rotation constraints clamp the final result
    # This gives the IK solver freedom while still respecting joint limits on final pose

    # Leg IK: Static pre-bend applied during chain creation (see STEP 3.75)
    # Arm IK: No pre-bend needed (arms work naturally with pole target in soft pin mode)

    bpy.context.view_layer.update()

    # Add IK constraint to the LAST IK control bone (the one closest to clicked bone)
    ik_tip_name = ik_control_names[-1]
    ik_tip_pose = armature.pose.bones[ik_tip_name]

    # DEBUG MODE: Clean up any existing IK_Temp constraints from previous drags
    constraints_to_remove = [c for c in ik_tip_pose.constraints if "IK_Temp" in c.name]
    for constraint in constraints_to_remove:
        constraint_name = constraint.name  # Store name before removing
        ik_tip_pose.constraints.remove(constraint)
        print(f"  Removed old IK constraint: {constraint_name}")

    ik_constraint = ik_tip_pose.constraints.new('IK')
    ik_constraint.name = "IK_Temp"
    ik_constraint.target = armature  # CRITICAL: Target is ARMATURE
    ik_constraint.subtarget = target_name  # CRITICAL: Subtarget is BONE NAME

    # In soft pin mode, use 3-bone IK chain (collar → shoulder → forearm)
    # This matches MHX rig behavior where collar + shoulder rotate with pole target
    if soft_pin_mode:
        # 3-bone chain: collar + shoulder + forearm (like MHX)
        ik_constraint.chain_count = 3
        print(f"  Soft pin mode: IK chain_count = 3 (collar + shoulder + forearm)")
    else:
        ik_constraint.chain_count = len(ik_control_names)
    ik_constraint.use_tail = True

    # Disable stretching when:
    # 1. Dragging a pinned bone directly (prevents hand separation from arm)
    # 2. In soft pin mode with pole target (keeps hand at pinned position)
    # Allow stretching only in normal unpinned IK mode for ragdoll-style behavior
    if ignore_pin_on_bone or soft_pin_mode:
        ik_constraint.use_stretch = False
        reason = "dragging pinned bone" if ignore_pin_on_bone else "soft pin mode"
        print(f"  Disabled IK stretching ({reason})")
    else:
        ik_constraint.use_stretch = True

    ik_constraint.use_rotation = False
    ik_constraint.iterations = 500
    # Explicitly set spaces to WORLD (matching Diffeomorphic)
    ik_constraint.target_space = 'WORLD'
    ik_constraint.owner_space = 'WORLD'
    # CRITICAL: Start IK disabled - activate on first mouse move to prevent initial pop
    ik_constraint.influence = 0.0

    # ==================================================================
    # STEP 3.5: Enable Pole Target (template-based or soft pin mode)
    # ==================================================================
    # Enable pole target if one was created (either from template or soft pin mode)
    if pole_target_name:
        ik_constraint.pole_target = armature
        ik_constraint.pole_subtarget = pole_target_name
        ik_constraint.pole_angle = -1.5708  # -90° (π/2) for DAZ/MHX rigs

        source = "template" if (ik_template and ik_template.get('pole_target', {}).get('enabled')) else "soft pin"
        print(f"  ✓ Enabled pole target: {pole_target_name} (angle: -90°, source: {source})")

    # ==================================================================
    # STEP 3.75: Apply static pre-bend to leg IK chains (before Copy Rotation)
    # ==================================================================
    # For legs, apply a small forward bend to thigh and shin BEFORE Copy Rotation constraints
    # This seeds the IK solver with the correct bend direction (knee forward)
    # ONLY apply if leg is in rest pose (straight) - if already bent, skip pre-bend
    # Since Copy Rotation isn't active yet, this won't affect the DAZ bones (no pop)
    leg_prebend_applied = None  # Track if leg pre-bend was applied (None = not a leg)
    if is_leg_chain:
        from mathutils import Quaternion

        # Check if leg is in rest pose by looking at shin rotation
        shin_bone = None
        for i, (daz_name, ik_name) in enumerate(zip(daz_bone_names, ik_control_names)):
            if 'shin' in daz_name.lower() or 'calf' in daz_name.lower():
                shin_bone = armature.pose.bones[ik_name]
                break

        # If shin is at identity rotation (rest pose), apply pre-bend
        if shin_bone:
            quat = shin_bone.rotation_quaternion
            is_rest_pose = abs(quat.w - 1.0) < 0.01 and abs(quat.x) < 0.01 and abs(quat.y) < 0.01 and abs(quat.z) < 0.01

            if is_rest_pose:
                # Get pre-bend angle from template (default 0.8 radians / ~46°)
                prebend_config = ik_template.get('prebend', {}) if ik_template else {}
                prebend_angle = prebend_config.get('angle', 0.8)
                import math
                prebend_degrees = math.degrees(prebend_angle)
                print(f"  Leg in rest pose - applying pre-bend: {prebend_angle:.2f} rad ({prebend_degrees:.1f}°)")

                for i, (daz_name, ik_name) in enumerate(zip(daz_bone_names, ik_control_names)):
                    daz_name_lower = daz_name.lower()
                    ik_bone = armature.pose.bones[ik_name]

                    # Thigh: forward rotation + translation
                    if 'thigh' in daz_name_lower:
                        # Rotate forward (around X axis, using template angle)
                        nudge_quat = Quaternion((1, 0, 0), prebend_angle)
                        ik_bone.rotation_quaternion = nudge_quat @ ik_bone.rotation_quaternion
                        # Translate forward slightly
                        ik_bone.location.y += 0.02  # Small forward offset
                        print(f"    Nudged {ik_name}: rotation {prebend_degrees:.1f}° forward, translation +0.02 Y")

                    # Shin: forward rotation
                    elif 'shin' in daz_name_lower or 'calf' in daz_name_lower:
                        # Rotate forward (around X axis, using template angle)
                        nudge_quat = Quaternion((1, 0, 0), prebend_angle)
                        ik_bone.rotation_quaternion = nudge_quat @ ik_bone.rotation_quaternion
                        print(f"    Nudged {ik_name}: rotation {prebend_degrees:.1f}° forward")

                bpy.context.view_layer.update()
                print(f"  ✓ Leg pre-bend applied (IK solver will prefer forward knee bend)")
                # Return flag: pre-bend was applied (limb was in rest pose)
                leg_prebend_applied = True
            else:
                print(f"  Leg already bent - skipping pre-bend (using current pose as seed)")
                # Return flag: pre-bend was skipped (limb already bent - use current pose)
                leg_prebend_applied = False

    # ==================================================================
    # STEP 4: Add Copy Rotation constraints from DAZ bones to IK bones
    # ==================================================================
    # CRITICAL: Exclude the TIP bone from Copy Rotation
    # We want IK to control middle bones (knee, elbow) but NOT the tip (foot, hand)
    # This preserves the tip's manual rotation (from R key) while IK controls the chain

    # Track bend/twist pairs for manual swing/twist decomposition during drag.
    # Bend bones with a corresponding Twist bone (e.g., lShldrBend/lShldrTwist) are driven
    # manually instead of by Copy Rotation constraints. This respects the DAZ bend/twist
    # architecture: bend bones get swing rotation only, twist bones get twist only.
    swing_twist_pairs = []

    for i, (daz_name, ik_name) in enumerate(zip(daz_bone_names, ik_control_names)):
        # ALWAYS skip Copy Rotation for the tip bone (end of IK chain)
        # The tip is controlled by IK movement, not rotation copying
        # This prevents rotation artifacts when dragging mid-limb bones (shin/forearm)
        if i == len(daz_bone_names) - 1:
            daz_lower = daz_name.lower()
            is_end_effector = any(part in daz_lower for part in ['hand', 'foot'])
            bone_type = "end effector" if is_end_effector else "mid-limb"
            print(f"  Skipping Copy Rotation for tip bone ({bone_type}): {daz_name}")
            continue

        daz_pose = armature.pose.bones[daz_name]

        # DEBUG MODE: Clean up any existing IK_CopyRot_Temp constraints from previous drags
        constraints_to_remove = [c for c in daz_pose.constraints if "IK_CopyRot_Temp" in c.name]
        for constraint in constraints_to_remove:
            daz_pose.constraints.remove(constraint)

        # Check for corresponding twist bone (DAZ bend/twist architecture)
        # If a twist bone exists, skip Copy Rotation and use manual swing/twist decomposition
        twist_name = daz_name.replace('Bend', 'Twist')
        if twist_name != daz_name and armature.pose.bones.get(twist_name):
            swing_twist_pairs.append((ik_name, daz_name, twist_name))
            print(f"  Swing/twist decomposition: {daz_name} → swing, {twist_name} → twist (no Copy Rotation)")
            continue

        # Add Copy Rotation constraint (only for non-bend bones like spine, shin, etc.)
        copy_rot = daz_pose.constraints.new('COPY_ROTATION')
        copy_rot.name = "IK_CopyRot_Temp"
        copy_rot.target = armature
        copy_rot.subtarget = ik_name  # Copy from IK control bone
        copy_rot.target_space = 'POSE'  # Copy in pose space
        copy_rot.owner_space = 'POSE'   # Apply in pose space

        # Set graduated influence based on bone name for smoother torso control
        daz_name_lower = daz_name.lower()
        if 'abdomenlower' in daz_name_lower or 'abdomen2' in daz_name_lower:
            copy_rot.influence = 0.5  # Lower abdomen - lowest influence
        elif 'abdomenupper' in daz_name_lower or 'abdomen' in daz_name_lower:
            copy_rot.influence = 0.7  # Upper abdomen - medium influence
        elif 'chestlower' in daz_name_lower or 'chest' in daz_name_lower:
            copy_rot.influence = 0.875  # Lower chest - high influence
        elif 'neck' in daz_name_lower:
            copy_rot.influence = 0.7  # Neck bones - start high to reduce snap on activation
        else:
            copy_rot.influence = 0.0  # Other bones - start disabled, activate on first mouse move

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

        # DEBUG MODE: Clean up any existing Shoulder_Track_Temp constraints from previous drags
        constraints_to_remove = [c for c in collar_pose.constraints if "Shoulder_Track_Temp" in c.name]
        for constraint in constraints_to_remove:
            collar_pose.constraints.remove(constraint)

        # Add Damped Track constraint
        damped_track = collar_pose.constraints.new('DAMPED_TRACK')
        damped_track.name = "Shoulder_Track_Temp"
        damped_track.target = armature
        damped_track.subtarget = shoulder_target_name
        damped_track.track_axis = 'TRACK_Y'  # Collar length axis
        damped_track.influence = 0.0  # Start disabled - activate WITH IK on first mouse move

        print(f"  Added Damped Track on {collar_name} → {shoulder_target_name}")

    # ==================================================================
    # STEP 4.7: Pin Constraint Transfer to .ik Bones
    # ==================================================================
    # If the tip bone is pinned (translation pin), add Copy Location to the .ik tip bone
    # This makes the temporary IK chain respect the pin during solving
    # UNLESS the tip bone is being dragged directly (ignore_pin_on_bone) - then skip
    tip_daz_name = daz_bone_names[-1]
    tip_ik_name = ik_control_names[-1]
    tip_data_bone = armature.data.bones.get(tip_daz_name)

    if tip_data_bone and is_bone_pinned_translation(tip_data_bone) and tip_daz_name != ignore_pin_on_bone:
        # SOFT PIN MODE: Skip adding hard pin constraint to .ik bone
        # The soft pin system will manage the position dynamically
        if soft_pin_mode:
            print(f"  ⚙️  SOFT PIN: Skipping hard pin constraint on {tip_ik_name} (soft pin will manage position)")
        else:
            # Get the pin Empty target
            pin_empty_name = f"PIN_translation_{armature.name}_{tip_daz_name}"
            pin_empty = bpy.data.objects.get(pin_empty_name)

            if pin_empty:
                # Add Copy Location to .ik tip bone (same as DAZ bone has)
                tip_ik_pose = armature.pose.bones[tip_ik_name]
                copy_loc = tip_ik_pose.constraints.new('COPY_LOCATION')
                copy_loc.name = "IK_PinLoc_Temp"
                copy_loc.target = pin_empty
                copy_loc.influence = 1.0  # Absolute lock - no movement allowed
                copy_loc.use_offset = False
                copy_loc.target_space = 'WORLD'
                copy_loc.owner_space = 'WORLD'

                # Force constraint evaluation update to ensure Copy Location runs after IK
                bpy.context.view_layer.update()

                print(f"  ✓ Added pin Copy Location to .ik bone: {tip_ik_name} → {pin_empty_name} (influence=1.0)")
                print(f"  → Temporary IK chain will respect pinned location during solving")
            else:
                print(f"  ⚠️  Tip bone {tip_daz_name} is pinned but Empty not found: {pin_empty_name}")

    # ==================================================================
    # STEP 4.75: Add Pin Constraints to ALL Pinned Bones in Chain
    # ==================================================================
    # Handle pinned bones that are NOT the tip (e.g., pinned chest in middle of chain)
    # These need Copy Location constraints on their .ik bones to act as rigid anchors
    for i, (daz_name, ik_name) in enumerate(zip(daz_bone_names, ik_control_names)):
        # Skip tip bone (already handled above)
        if i == len(daz_bone_names) - 1:
            continue

        # Skip bone being dragged directly
        if daz_name == ignore_pin_on_bone:
            continue

        # Skip soft pin mode (handled separately)
        if soft_pin_mode and daz_name == tip_daz_name:
            continue

        # Check if this bone is pinned
        data_bone = armature.data.bones.get(daz_name)
        if data_bone and is_bone_pinned_translation(data_bone):
            # Get the pin Empty target
            pin_empty_name = f"PIN_translation_{armature.name}_{daz_name}"
            pin_empty = bpy.data.objects.get(pin_empty_name)

            if pin_empty:
                # Add strong Copy Location to keep bone at pin position
                # This resists movement but allows minimal yield when IK absolutely needs it
                ik_pose = armature.pose.bones[ik_name]

                # Use Copy Location with high influence to pin position
                # Don't use location locks - they prevent IK from solving properly
                copy_loc = ik_pose.constraints.new('COPY_LOCATION')
                copy_loc.name = "IK_PinLoc_Temp"
                copy_loc.target = pin_empty
                copy_loc.influence = 1.0  # Full lock - acts as rigid anchor point
                copy_loc.use_offset = False
                copy_loc.target_space = 'WORLD'
                copy_loc.owner_space = 'WORLD'

                print(f"  ✓ Locked translation + pin anchor on .ik bone: {ik_name} (rigid anchor)")
            else:
                print(f"  ⚠️  Bone {daz_name} is pinned but Empty not found: {pin_empty_name}")

    # ==================================================================
    # STEP 4.8: Pin Handling (Translation and Rotation Pins)
    # ==================================================================
    # Pins are now persistent constraints on DAZ bones (added when pressing P)
    # When dragging a pinned bone directly (ignore_pin_on_bone), we temporarily
    # disable its pin constraint to allow free movement, then re-enable after drag
    if ignore_pin_on_bone:
        data_bone = armature.data.bones.get(ignore_pin_on_bone)
        pose_bone = armature.pose.bones.get(ignore_pin_on_bone)
        if data_bone and pose_bone:
            # Temporarily disable pin constraint on directly dragged bone
            for c in pose_bone.constraints:
                if c.name in ("DAZ_Pin_Translation", "DAZ_Pin_Rotation"):
                    c.mute = True  # Mute constraint (will unmute after drag)
                    print(f"  Temporarily disabled pin on {ignore_pin_on_bone} (direct drag)")

    # POLISH: Add Damped Track for head bones to make Y axis (top of head) point at target
    # This makes the head orient naturally towards where you're dragging
    # Lower influence = more stable "string pull" feel, less bobble-head wobble
    HEAD_TRACK_INFLUENCE = 0.0  # DISABLED: Pure translation "string pull" - no automatic rotation
    tip_daz_bone = armature.pose.bones[daz_bone_names[-1]]
    if 'head' in tip_daz_bone.name.lower() and HEAD_TRACK_INFLUENCE > 0.0:
        track = tip_daz_bone.constraints.new('DAMPED_TRACK')
        track.name = "IK_HeadTrack_Temp"
        track.target = armature
        track.subtarget = target_name  # Point at .ik.target
        track.head_tail = 1.0  # CRITICAL: Track the TAIL (tip) of target bone, not head (base)
        track.track_axis = 'TRACK_Y'  # Y axis (top of head) points at target
        track.influence = HEAD_TRACK_INFLUENCE
        print(f"  Added head tracking constraint (Y axis → target tail, influence={HEAD_TRACK_INFLUENCE})")

    # Force update
    bpy.context.view_layer.update()

    # Keep IK at influence=0 during creation. The solver will be activated in
    # update_ik_drag when the drag actually starts (either pre-bend path or fast path).
    # Activating here causes the solver to drift .ik bones toward rest pose across
    # viewport redraws between create and first mouse event, which causes snap-to-straight
    # on the second drag (the "second drag bug").
    ik_tip_pose = armature.pose.bones[ik_control_names[-1]]
    for c in ik_tip_pose.constraints:
        if c.name == "IK_Temp":
            c.influence = 0.0
            break
    bpy.context.view_layer.update()
    print(f"  ✓ IK constraint ready (influence=0, activated on first drag update)")
    # DIAG: Store .ik bone rotations AFTER IK solver runs
    import bpy as _bpy2
    _diag2 = {}
    for ik_name in ik_control_names:
        ik_pb = armature.pose.bones.get(ik_name)
        if ik_pb:
            q = ik_pb.rotation_quaternion
            _diag2[f"afterik_{ik_name}"] = (round(q.w,4),round(q.x,4),round(q.y,4),round(q.z,4))
    for daz_name in daz_bone_names:
        daz_pb = armature.pose.bones.get(daz_name)
        if daz_pb:
            e = daz_pb.rotation_euler
            _diag2[f"afterik_daz_{daz_name}"] = (round(e.x,4),round(e.y,4),round(e.z,4))
    if not hasattr(_bpy2, '_blendaz_diag'):
        _bpy2._blendaz_diag = {}
    _bpy2._blendaz_diag.update(_diag2)

    # Fix 3: Tiny directional nudge to lock the solver into the current solution
    # This prevents the solver from choosing the "opposite direction" solution
    # Source: Grok analysis - "final lock-in" for IK solver
    if len(ik_control_names) >= 3:
        middle_ik = armature.pose.bones[ik_control_names[-2]]
        middle_daz_eval = armature_eval.pose.bones[daz_bone_names[-2]]
        nudge_dir = (middle_daz_eval.tail - middle_daz_eval.head).normalized()
        middle_ik.location += nudge_dir * 0.012  # Small nudge in current bend direction
        bpy.context.view_layer.update()
        debug_print(f"  ✓ Applied solver bias nudge to {ik_control_names[-2]}", level=2)

    # Summary: Log tip bone position for snap debugging
    tip_ik = armature.pose.bones[ik_control_names[-1]]
    tip_world = armature.matrix_world @ tip_ik.head
    print(f"  ✓ IK chain ready | tip_pos={tip_world.x:.3f},{tip_world.y:.3f},{tip_world.z:.3f}")

    return target_name, ik_control_names, daz_bone_names, shoulder_target_names, leg_prebend_applied, swing_twist_pairs, is_leg_chain


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


def dissolve_ik_chain(armature, target_bone_name, ik_control_names, daz_bone_names, shoulder_target_names=None, keyframe=True, swing_twist_pairs=None):
    """
    Remove IK chain: optionally keyframe DAZ bones, delete Copy Rotation constraints, delete .ik bones.
    CRITICAL: Keyframe BEFORE removing constraints to capture the constrained pose!

    Args:
        shoulder_target_names: List of shoulder target bone names (for collar Damped Track)
        keyframe: If False, skip keyframing (used for canceling/right-click)
        swing_twist_pairs: List of (ik_name, bend_name, twist_name) tuples for swing/twist decomposition
    """
    if shoulder_target_names is None:
        shoulder_target_names = []
    if swing_twist_pairs is None:
        swing_twist_pairs = []
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

            # Skip keyframing the TIP bone ONLY if it's an end effector (hand, foot)
            # Mid-limb bones (chest, shoulder, forearm) should be keyframed even as tip
            if i == len(daz_bone_names) - 1:
                daz_lower = daz_name.lower()
                is_end_effector = any(part in daz_lower for part in ['hand', 'foot'])
                if is_end_effector:
                    print(f"  Skipping keyframe for tip bone (end effector): {daz_name} (preserves manual rotations)")
                    continue
                else:
                    print(f"  Keyframing tip bone (mid-limb): {daz_name}")

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

    # STEP 2: BAKE constraint results into bone rotations BEFORE removing constraints
    # The Copy Rotation constraint affects the final matrix but NOT rotation_quaternion.
    # If we just remove constraints, bones snap back to their original pose.
    # Fix: Extract rotation from evaluated bone matrix and write to rotation_quaternion.
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    armature_eval = armature.evaluated_get(depsgraph)

    # Build lookup for swing/twist pairs
    swing_twist_bend_names = {bend_name for _, bend_name, _ in swing_twist_pairs}

    for daz_name in daz_bone_names:
        daz_bone = armature.pose.bones.get(daz_name)
        if not daz_bone:
            continue

        # Bend bones with twist counterparts: bake with swing/twist decomposition
        # (These don't have Copy Rotation constraints — they were driven manually during drag)
        if daz_name in swing_twist_bend_names:
            # Find the matching pair
            for ik_name, bend_name, twist_name in swing_twist_pairs:
                if bend_name == daz_name:
                    ik_bone_eval = armature_eval.pose.bones.get(ik_name)
                    if not ik_bone_eval:
                        break

                    # Compute local rotation from .ik bone's evaluated matrix
                    if daz_bone.parent:
                        parent_eval = armature_eval.pose.bones[daz_bone.parent.name]
                        rest_offset = daz_bone.parent.bone.matrix_local.inverted() @ daz_bone.bone.matrix_local
                        matrix_basis = rest_offset.inverted() @ parent_eval.matrix.inverted() @ ik_bone_eval.matrix
                    else:
                        matrix_basis = daz_bone.bone.matrix_local.inverted() @ ik_bone_eval.matrix

                    loc, rot, scale = matrix_basis.decompose()
                    swing, twist = decompose_swing_twist(rot, 'Y')

                    # Bake swing into bend bone
                    if daz_bone.rotation_mode == 'QUATERNION':
                        daz_bone.rotation_quaternion = swing
                    else:
                        daz_bone.rotation_euler = swing.to_euler(daz_bone.rotation_mode)
                    print(f"  [BAKE] {daz_name}: swing baked (twist preserved on {twist_name})")

                    # DON'T bake twist into twist bone — preserve user's manual rotation.
                    # Twist bones are user-controlled only (R key manual rotation).

                    # Update so next bone's parent matrix is current
                    bpy.context.view_layer.update()
                    depsgraph = bpy.context.evaluated_depsgraph_get()
                    armature_eval = armature.evaluated_get(depsgraph)
                    break
            continue

        # Non-bend bones: bake from Copy Rotation constraint as before
        has_active_copy_rot = any(
            c.name == "IK_CopyRot_Temp" and c.influence > 0
            for c in daz_bone.constraints
        )
        if has_active_copy_rot:
            # Get evaluated bone's final matrix (includes constraint effects)
            bone_eval = armature_eval.pose.bones[daz_name]

            # Extract local rotation from final matrix
            if daz_bone.parent:
                parent_eval = armature_eval.pose.bones[daz_bone.parent.name]
                local_matrix = parent_eval.matrix.inverted() @ bone_eval.matrix
            else:
                local_matrix = bone_eval.matrix

            loc, rot, scale = local_matrix.decompose()

            # BAKE: Set bone's rotation to match constraint result
            if daz_bone.rotation_mode == 'QUATERNION':
                daz_bone.rotation_quaternion = rot
            else:
                daz_bone.rotation_euler = rot.to_euler(daz_bone.rotation_mode)
            print(f"  [BAKE] {daz_name}: constraint rotation baked into bone")

        # NOW remove constraints - bone will stay in place because rotation is baked
        constraints_to_remove = [c for c in daz_bone.constraints if c.name in ("IK_CopyRot_Temp", "IK_HeadTrack_Temp", "Shoulder_Track_Temp")]
        for c in constraints_to_remove:
            daz_bone.constraints.remove(c)

    bpy.context.view_layer.update()

    # STEP 2.5: Cache ALL bone rotations and locations BEFORE mode switch (for cleanup)
    # Mode switching discards un-keyframed transforms - cache them now
    # NOTE: Rotations are now BAKED, so this cache contains the posed values
    rotation_cache = {}
    location_cache = {}
    for pose_bone in armature.pose.bones:
        if pose_bone.rotation_mode == 'QUATERNION':
            rotation_cache[pose_bone.name] = pose_bone.rotation_quaternion.copy()
        else:
            rotation_cache[pose_bone.name] = pose_bone.rotation_euler.copy()
        if pose_bone.bone.parent is None or pose_bone.location.length_squared > 1e-8:
            location_cache[pose_bone.name] = pose_bone.location.copy()

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

    # Delete pole target bone (if it exists)
    pole_target_name = target_bone_name + ".pole"
    if pole_target_name in edit_bones:
        edit_bones.remove(edit_bones[pole_target_name])
        print(f"  Removed pole target: {pole_target_name}")

    bpy.ops.object.mode_set(mode='POSE')

    # NOTE: Pin helper Empties are NOT removed here - they are persistent
    # and should only be removed when user explicitly unpins the bone
    # The pin Empties existed before the IK chain was created and should
    # remain after the chain dissolves

    # CRITICAL (Blender 5.0): view_layer.update() alone does NOT apply F-curve animation.
    # frame_set() is required to evaluate keyframes and put IK chain bones in their
    # correct post-drag positions. Run this FIRST, before the cache restore below.
    # WARNING: frame_set() applies ALL F-curves including stale prior-drag keyframes
    # for non-IK bones (e.g., a leg bone moved in a previous drag). STEP 3.5 below
    # overwrites those stale values by restoring from the pre-drag cache.
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)

    # STEP 3.5: RESTORE all cached bone rotations after mode switch + frame_set()
    # Run AFTER frame_set() so this cache restore is the last write, overriding
    # any stale prior-drag keyframe values that frame_set() applied to non-IK bones.
    # CRITICAL: Skip IK chain bones - frame_set() already applied their correct
    # INSERTKEY_VISUAL poses; restoring from cache would snap them back to pre-drag.
    rotations_restored = 0
    for bone_name_cache, rotation in rotation_cache.items():
        # Skip bones that were in the IK chain - their pose is preserved via frame_set()
        if bone_name_cache in daz_bone_names:
            continue

        pose_bone = armature.pose.bones.get(bone_name_cache)
        if pose_bone:
            if pose_bone.rotation_mode == 'QUATERNION':
                pose_bone.rotation_quaternion = rotation
            else:
                pose_bone.rotation_euler = rotation
            rotations_restored += 1
    if rotations_restored > 0:
        print(f"  ✓ Restored {rotations_restored} non-IK bone rotations after cleanup")

    # Restore bone locations (hip, any translated bones)
    for bone_name_cache, loc in location_cache.items():
        if bone_name_cache in daz_bone_names:
            continue
        pose_bone = armature.pose.bones.get(bone_name_cache)
        if pose_bone:
            pose_bone.location = loc


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
    pose_bone = armature.pose.bones.get(bone_name)
    if not bone or not pose_bone:
        return False

    # Get current world location
    world_matrix = get_bone_world_matrix(armature, bone_name)
    if world_matrix:
        world_location = world_matrix.to_translation()

        # Store pin data
        bone["daz_pin_translation"] = True
        bone["daz_pin_location"] = tuple(world_location)  # Store as tuple

        # Create helper empty at pinned location
        from mathutils import Matrix, Vector
        pin_matrix = Matrix.Translation(Vector(world_location))
        empty = create_pin_helper_empty(armature, bone_name, pin_matrix, 'translation')

        # Add persistent Copy Location constraint to the ORIGINAL DAZ bone
        # Remove any existing pin constraint first
        for c in pose_bone.constraints:
            if c.name == "DAZ_Pin_Translation":
                pose_bone.constraints.remove(c)

        constraint = pose_bone.constraints.new('COPY_LOCATION')
        constraint.name = "DAZ_Pin_Translation"
        constraint.target = empty
        constraint.influence = 1.0  # Absolute lock at pinned location
        constraint.use_offset = False
        constraint.target_space = 'WORLD'
        constraint.owner_space = 'WORLD'

        print(f"  ✓ Pinned Translation: {bone_name} at {world_location} (Copy Location constraint)")
        return True
    return False


def pin_bone_rotation(armature, bone_name):
    """Mark bone as rotation pinned, store world rotation, and create Copy Rotation constraint"""
    bone = armature.data.bones.get(bone_name)
    pose_bone = armature.pose.bones.get(bone_name)
    if not bone or not pose_bone:
        return False

    # Get current world matrix
    world_matrix = get_bone_world_matrix(armature, bone_name)
    if world_matrix:
        world_rotation = world_matrix.to_euler()

        # Store pin data
        bone["daz_pin_rotation"] = True
        bone["daz_pin_rotation_euler"] = world_rotation

        # Create helper empty at pinned orientation
        # Empty needs full world matrix (location + rotation) so Copy Rotation works in world space
        from mathutils import Matrix
        rotation_matrix = world_rotation.to_matrix().to_4x4()
        translation_matrix = Matrix.Translation(world_matrix.to_translation())
        pin_matrix = translation_matrix @ rotation_matrix
        empty = create_pin_helper_empty(armature, bone_name, pin_matrix, 'rotation')

        # Add persistent Copy Rotation constraint to the ORIGINAL DAZ bone
        # Remove any existing pin constraint first
        for c in pose_bone.constraints:
            if c.name == "DAZ_Pin_Rotation":
                pose_bone.constraints.remove(c)

        constraint = pose_bone.constraints.new('COPY_ROTATION')
        constraint.name = "DAZ_Pin_Rotation"
        constraint.target = empty
        constraint.influence = 1.0  # Absolute lock at pinned rotation
        constraint.use_offset = False
        constraint.target_space = 'WORLD'
        constraint.owner_space = 'WORLD'
        constraint.mix_mode = 'REPLACE'

        print(f"  ✓ Pinned Rotation: {bone_name} at {world_rotation} (Copy Rotation constraint)")
        return True
    return False


def unpin_bone(armature, bone_name):
    """Remove all pins from bone, preserving current visual pose."""
    bone = armature.data.bones.get(bone_name)
    pose_bone = armature.pose.bones.get(bone_name)
    if not bone:
        return False

    # Remove pin properties
    had_pins = False
    had_translation_pin = False
    had_rotation_pin = False

    if "daz_pin_translation" in bone:
        del bone["daz_pin_translation"]
        if "daz_pin_location" in bone:
            del bone["daz_pin_location"]
        had_pins = True
        had_translation_pin = True

    if "daz_pin_rotation" in bone:
        del bone["daz_pin_rotation"]
        if "daz_pin_rotation_euler" in bone:
            del bone["daz_pin_rotation_euler"]
        had_pins = True
        had_rotation_pin = True

    # Bake the visual pose BEFORE removing constraints, so the bone stays put.
    # Delta-based approach:
    #   1. Snapshot world-space transform WITH constraint active
    #   2. Remove constraint + update
    #   3. Snapshot world-space transform WITHOUT constraint
    #   4. Compute the world-space difference and apply as local correction
    pinned_world_mat = None
    if pose_bone and had_pins:
        bpy.context.view_layer.update()
        pose_bone.rotation_mode = 'QUATERNION'
        # World-space transform while constraint is active (the pose we want to keep)
        pinned_world_mat = (armature.matrix_world @ pose_bone.matrix).copy()

    # Now remove constraints
    if pose_bone:
        if had_translation_pin:
            for c in list(pose_bone.constraints):
                if c.name == "DAZ_Pin_Translation":
                    pose_bone.constraints.remove(c)
                    print(f"  Removed translation pin constraint from {bone_name}")
        if had_rotation_pin:
            for c in list(pose_bone.constraints):
                if c.name == "DAZ_Pin_Rotation":
                    pose_bone.constraints.remove(c)
                    print(f"  Removed rotation pin constraint from {bone_name}")

    # Clean up helper Empties
    if had_translation_pin:
        remove_pin_helper_empty(armature, bone_name, 'translation')
    if had_rotation_pin:
        remove_pin_helper_empty(armature, bone_name, 'rotation')

    # Apply delta correction so bone stays at its pinned world-space pose.
    if pinned_world_mat and pose_bone:
        bpy.context.view_layer.update()
        # World-space transform AFTER constraint removed (bone snapped back)
        current_world_mat = (armature.matrix_world @ pose_bone.matrix)

        if had_rotation_pin:
            # World-space rotation delta: pinned = delta @ current  =>  delta = pinned @ current^-1
            pinned_rot = pinned_world_mat.to_quaternion()
            current_rot = current_world_mat.to_quaternion()
            world_delta = pinned_rot @ current_rot.inverted()

            # Convert world-space delta to bone-local delta:
            # bone_world_axes = armature.matrix_world @ pose_bone.matrix
            # local_delta = bone_world^-1 @ world_delta @ bone_world  (conjugation)
            bone_world_rot = current_world_mat.to_quaternion()
            local_delta = bone_world_rot.inverted() @ world_delta @ bone_world_rot

            # Compose with existing local rotation
            pose_bone.rotation_quaternion = local_delta @ pose_bone.rotation_quaternion

        if had_translation_pin:
            # World-space position delta
            pinned_pos = pinned_world_mat.to_translation()
            current_pos = current_world_mat.to_translation()
            world_offset = pinned_pos - current_pos

            # Convert world offset to bone's local space for the location channel
            # pose_bone.location is in the bone's rest-local coordinate system
            # world_offset needs to go through: armature inverse, then parent bone inverse, then rest inverse
            if pose_bone.parent:
                parent_world = armature.matrix_world @ pose_bone.parent.matrix
                local_offset = (parent_world.to_3x3().inverted() @ world_offset)
            else:
                local_offset = armature.matrix_world.to_3x3().inverted() @ world_offset

            pose_bone.location = pose_bone.location + local_offset

        bpy.context.view_layer.update()
        print(f"  ✓ Baked visual pose to local transform (delta approach)")

    if had_pins:
        print(f"  ✓ Unpinned: {bone_name}")
        return True
    return False


def create_pin_helper_empty(armature, bone_name, world_matrix, pin_type):
    """
    Create or get a helper Empty object for pin constraints.
    This Empty serves as the constraint target to maintain world transforms.

    Args:
        armature: The armature object
        bone_name: Name of the bone being pinned
        world_matrix: World matrix of the pinned bone
        pin_type: 'translation' or 'rotation'

    Returns:
        The Empty object
    """
    empty_name = f"PIN_{pin_type}_{armature.name}_{bone_name}"

    # Check if empty already exists
    if empty_name in bpy.data.objects:
        empty = bpy.data.objects[empty_name]
    else:
        # Create new empty
        empty = bpy.data.objects.new(empty_name, None)
        empty.empty_display_type = 'PLAIN_AXES'
        empty.empty_display_size = 0.01  # Very small, just for debugging
        bpy.context.scene.collection.objects.link(empty)

    # Set empty's world transform to match the pinned bone's current transform
    empty.matrix_world = world_matrix

    # Hide empty in viewport and render
    empty.hide_viewport = True
    empty.hide_render = True

    return empty


def remove_pin_helper_empty(armature, bone_name, pin_type):
    """Remove helper Empty for a pin"""
    empty_name = f"PIN_{pin_type}_{armature.name}_{bone_name}"
    if empty_name in bpy.data.objects:
        empty = bpy.data.objects[empty_name]
        bpy.data.objects.remove(empty, do_unlink=True)


def add_translation_pin_constraint(armature, ik_bone_name, bone_name):
    """
    Add Copy Location constraint to IK bone to maintain world position.
    This makes the bone "try to stay" at the pinned world location.

    Args:
        armature: The armature object
        ik_bone_name: Name of the .ik control bone
        bone_name: Name of the original DAZ bone (for getting pin data)
    """
    pose_bone = armature.pose.bones.get(ik_bone_name)
    data_bone = armature.data.bones.get(bone_name)

    if not pose_bone or not data_bone:
        return

    # Get stored world location
    world_location = data_bone.get("daz_pin_location")
    if not world_location:
        return

    # Create a matrix from the stored pin location
    # Use identity rotation since we only care about position for translation pins
    from mathutils import Matrix, Vector
    world_matrix = Matrix.Translation(Vector(world_location))

    # Create helper empty at pinned location
    empty = create_pin_helper_empty(armature, bone_name, world_matrix, 'translation')

    # Add Copy Location constraint to IK bone
    constraint = pose_bone.constraints.new('COPY_LOCATION')
    constraint.name = "DAZ_Pin_Translation"
    constraint.target = empty
    constraint.influence = 0.99  # Nearly absolute - virtually locked unless extreme IK forces
    constraint.use_offset = False  # Copy absolute world location
    constraint.target_space = 'WORLD'
    constraint.owner_space = 'WORLD'

    print(f"  ⚓ Added translation pin constraint to {ik_bone_name} (influence={constraint.influence})")


def has_pinned_children(armature, bone_name, ignore_pin_on_bone=None):
    """Check if bone has any pinned children (recursively)

    Args:
        armature: The armature object
        bone_name: Name of bone to check
        ignore_pin_on_bone: Bone name to ignore when checking (for temporary pin override)
    """
    pose_bone = armature.pose.bones.get(bone_name)
    if not pose_bone:
        return False

    # Check all children recursively
    for child in pose_bone.children:
        # Skip ignored bone (temporary pin override during direct drag)
        if ignore_pin_on_bone and child.name == ignore_pin_on_bone:
            continue

        data_bone = armature.data.bones.get(child.name)
        if data_bone and (is_bone_pinned_translation(data_bone) or is_bone_pinned_rotation(data_bone)):
            return True
        # Check child's children
        if has_pinned_children(armature, child.name, ignore_pin_on_bone):
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
    _face_group_mgr = None  # DSF face group manager for clean zone detection
    _hover_control_point_id = None  # For multi-bone controls
    _hover_bone_names = None  # List of bone names for multi-bone controls
    _hover_from_posebridge = False  # True when hover came from PoseBridge control point (not 3D raycast)

    # Click detection to ignore gizmo drags
    _mouse_down_pos = None
    _click_threshold = 5  # pixels - if mouse moves more than this, it's a drag not a click
    _accumulated_drag_distance = 0.0  # Track cumulative movement during detection phase
    _accumulated_drag_threshold = 12  # pixels - trigger drag if accumulated movement exceeds this
    _last_detection_mouse_pos = None  # Last mouse position during drag detection

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
    _rotation_parent_frame_quat = None  # Cached parent frame for world-to-local conversion
    _rotation_initial_mouse = None
    _rotation_target_empty = None
    _rotation_constraint = None
    _rotation_mouse_button = None  # 'LEFT' or 'RIGHT' - tracks which button started rotation
    _right_click_used_for_drag = False  # Track if right-click started a drag (to suppress context menu)
    _rotation_bones = []  # List of bones for multi-bone group rotation
    _rotation_initial_quats = []  # List of initial quaternions for multi-bone rotation
    _rotation_group_id = None  # Control point ID for group axis lookup
    _rotation_group_controls = None  # Cached controls dict for data-driven group rotation

    # Drag origin state (locked at mouse-down, not affected by hover changes during drag detection)
    _drag_from_posebridge = False    # True if drag started from a PoseBridge control point
    _drag_control_point_id = None    # CP id at mouse-down (preserved even if hover drifts off CP)
    _drag_bone_names = None          # Multi-bone group names at mouse-down

    # Morph drag state (face panel)
    _is_morphing = False
    _morph_controls = None           # Cached controls dict for the active morph CP
    _morph_initial_values = {}       # {prop_name: float} initial values before drag
    _morph_initial_mouse = None      # (mouse_x, mouse_y) at drag start
    _morph_mouse_button = None       # 'LEFT' or 'RIGHT'
    _morph_cp_id = None              # Control point ID for logging

    # Undo stack for Ctrl+Z
    _undo_stack = []  # List of {frame, bones: [(name, rotation, mode)]} entries

    # GPU draw handlers (instance-level; also tracked class-level for reload cleanup)
    _draw_handler = None  # For highlighting
    _pin_draw_handler = None  # For pin spheres (always visible)
    _tooltip_draw_handler = None  # For tooltip text near mouse cursor
    _bracket_draw_handler = None  # For selection brackets
    _debug_leg_draw_handler = None
    _debug_arm_draw_handler = None
    # Class-level set of all active handlers — lets the reload script remove stale ones
    _active_draw_handlers = set()
    _highlight_cache = {}  # Cache of {(mesh_name, bone_name): [triangle_verts]} for performance
    _last_highlighted_bone = None  # Track when to rebuild cache
    _bracket_vert_cache = {}  # Cache of {(mesh_name, bone_name): set(vert_indices)} — topology never changes
    _live_instance = None  # Reference to the currently running modal instance (for hot-push of FGM updates)

    @staticmethod
    def _set_header(context, text):
        """Set header text safely — guards against None area (e.g. after workspace switch)."""
        if context.area:
            context.area.header_text_set(text)

    def modal(self, context, event):
        """Handle mouse events"""

        # If finish() was called externally (e.g. Stop BlenDAZ button), terminate now
        if getattr(self, '_should_stop', False):
            return {'CANCELLED'}

        # Clear tooltip on any mouse button press
        if event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE'} and event.value == 'PRESS':
            if self._tooltip_text:
                self._tooltip_text = None
                self._tooltip_mouse_pos = None
                if context.area: context.area.tag_redraw()

        # Native translate pass-through (G on hip with no pins)
        # Blender's translate operator runs as a separate modal; we must pass ALL events
        # through so it can handle mouse movement, axis constraints, confirm/cancel.
        # We detect when translate ends (confirm/cancel) and clear the flag.
        if self._use_native_translate:
            if event.value == 'PRESS' and event.type in {'RIGHTMOUSE', 'ESC'}:
                # Translate cancelled
                self._use_native_translate = False
            elif event.value == 'PRESS' and event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'}:
                # Translate confirmed
                self._use_native_translate = False
            return {'PASS_THROUGH'}

        # Consume ALL RMB events during active RMB interaction to prevent context menu
        # Blender generates CLICK events AFTER RELEASE, so we keep the flag set until
        # the next MOUSEMOVE to ensure late CLICK events are also consumed
        if event.type == 'RIGHTMOUSE' and (self._right_click_used_for_drag or
                (self._is_rotating and self._rotation_mouse_button == 'RIGHT')):
            if event.value == 'RELEASE':
                # Handle release: end rotation if active
                if self._is_rotating and self._rotation_mouse_button == 'RIGHT':
                    self.end_rotation(context, cancel=False)
                # DON'T clear _right_click_used_for_drag here -- cleared on next MOUSEMOVE
                # so that post-release CLICK events are still consumed
            return {'RUNNING_MODAL'}

        if event.type == 'MOUSEMOVE':
            # Clear RMB suppression flag after mouse movement (safe: any CLICK already consumed)
            if self._right_click_used_for_drag and not self._is_rotating:
                self._right_click_used_for_drag = False
            # Debug: Check state (verbose - only at level 2)
            if self._is_dragging:
                debug_print(f"  [MODAL] MOUSEMOVE while dragging")
            # Check if we should start IK drag or rotation
            if not self._is_dragging and not self._is_rotating and not self._is_morphing and self._mouse_down_pos and self._drag_bone_name:
                mouse_pos = (event.mouse_x, event.mouse_y)

                # Calculate direct distance from initial mouse-down position
                distance = ((mouse_pos[0] - self._mouse_down_pos[0])**2 +
                           (mouse_pos[1] - self._mouse_down_pos[1])**2)**0.5

                # Accumulate distance traveled (for slow, steady movements)
                if self._last_detection_mouse_pos:
                    movement = ((mouse_pos[0] - self._last_detection_mouse_pos[0])**2 +
                               (mouse_pos[1] - self._last_detection_mouse_pos[1])**2)**0.5
                    self._accumulated_drag_distance += movement
                self._last_detection_mouse_pos = mouse_pos

                # If moved beyond threshold (direct OR accumulated), start IK drag
                if distance > self._click_threshold or self._accumulated_drag_distance > self._accumulated_drag_threshold:
                    if self._accumulated_drag_distance > self._accumulated_drag_threshold and distance <= self._click_threshold:
                        debug_print(f"  [DRAG] Triggered by accumulated distance: {self._accumulated_drag_distance:.1f}px (direct: {distance:.1f}px)", level=1)
                    self.start_ik_drag(context, event)

                # Consume event during detection phase to prevent box select
                return {'RUNNING_MODAL'}

            # If dragging IK, update IK target position
            if self._is_dragging:
                if self._use_analytical_leg_ik:
                    self.update_analytical_leg_drag(context, event)
                elif self._use_analytical_arm_ik:
                    self.update_analytical_arm_drag(context, event)
                elif self._use_fabrik:
                    self.update_fabrik_drag(context, event)
                else:
                    self.update_ik_drag(context, event)
                return {'RUNNING_MODAL'}

            # If morphing (face panel), update morph values
            if self._is_morphing:
                self.update_morph(context, event)
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
            # Skip bounds check for cross-viewport clicks (already verified by _crossviewport_raycast)
            if not getattr(self, '_hover_from_crossviewport', False):
                region = context.region
                if region:
                    mouse_y = event.mouse_region_y
                    mouse_x = event.mouse_region_x

                    # If clicking in header area or outside bounds, pass through
                    if mouse_y > region.height - 40 or mouse_y < 0 or mouse_x < 0 or mouse_x > region.width:
                        self._mouse_down_pos = None
                        self._accumulated_drag_distance = 0.0
                        self._last_detection_mouse_pos = None
                        return {'PASS_THROUGH'}

            # CHARACTER SWITCH: If get_bone_from_hit flagged a switch during hover,
            # perform the switch now on click.
            if self._switch_to_character:
                target = self._switch_to_character
                self._switch_to_character = None
                if self._switch_active_character(context, target):
                    if context.area:
                        context.area.tag_redraw()
                    return {'RUNNING_MODAL'}

            # DOUBLE-CLICK DETECTION: Switch to object mode and select armature (DAZ-style)
            import time
            current_time = time.time()
            current_pos = (event.mouse_region_x, event.mouse_region_y)

            is_double_click = False
            if self._last_click_time > 0:
                time_delta = current_time - self._last_click_time
                if time_delta < 0.3 and self._last_click_pos:  # Within 300ms
                    # Check if clicks are close in position (within 5 pixels)
                    pos_delta = ((current_pos[0] - self._last_click_pos[0])**2 +
                                (current_pos[1] - self._last_click_pos[1])**2)**0.5
                    if pos_delta < 5:
                        is_double_click = True

            # Update click tracking
            self._last_click_time = current_time
            self._last_click_pos = current_pos

            # Handle double-click: select armature in object mode
            if is_double_click and not self._is_dragging:
                print("\n=== Double-click detected: Selecting armature ===")

                # Clean up any active IK chains first
                if hasattr(self, '_ik_target_bone_name') and self._ik_target_bone_name:
                    print("  Cleaning up active IK chain before armature selection...")
                    self.end_ik_drag(context, cancel=True)

                # Find armature — prefer cached hover state, but fall back to a fresh
                # raycast in case _hover_mesh was cleared by the first click's mode switches.
                armature_to_select = None
                mesh_obj = self._hover_mesh

                if not mesh_obj:
                    # Fresh raycast
                    region = context.region
                    rv3d = context.space_data.region_3d if context.space_data else None
                    if region and rv3d:
                        coord = (event.mouse_region_x, event.mouse_region_y)
                        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
                        ray_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
                        ok, _loc, _nor, _idx, hit_obj, _mat = context.scene.ray_cast(
                            context.view_layer.depsgraph, ray_origin, ray_vector
                        )
                        if ok and hit_obj and hit_obj.type == 'MESH':
                            mesh_obj = hit_obj
                            print(f"  (hover was stale — fresh raycast hit: {hit_obj.name})")

                if mesh_obj:
                    for mod in mesh_obj.modifiers:
                        if mod.type == 'ARMATURE' and mod.object:
                            armature_to_select = mod.object
                            break
                    if not armature_to_select and mesh_obj.parent and mesh_obj.parent.type == 'ARMATURE':
                        armature_to_select = mesh_obj.parent

                if armature_to_select:
                    # Switch to object mode
                    if context.mode != 'OBJECT':
                        bpy.ops.object.mode_set(mode='OBJECT')

                    # Deselect all
                    bpy.ops.object.select_all(action='DESELECT')

                    # Select the armature
                    armature_to_select.select_set(True)
                    context.view_layer.objects.active = armature_to_select

                    print(f"  ✓ Selected armature in object mode: {armature_to_select.name}")
                    self._just_selected_armature = True

                    # Consume the event
                    return {'RUNNING_MODAL'}
                else:
                    print("  ⚠️ No armature found for double-click selection")

                # Reset double-click tracking to avoid triple-click issues
                self._last_click_time = 0
                self._last_click_pos = None

            # If we just selected armature (previous double-click), decide what to do:
            # - Hovering over the DAZ character → re-acquire: return to pose mode, then handle click
            # - Hovering over anything else → stay in object mode and pass through so the user
            #   can select non-BlenDAZ objects normally; _just_selected_armature stays True
            #   until the user clicks back on the character
            if self._just_selected_armature and not is_double_click:
                if self._hover_armature:
                    # Clicked back on the DAZ character — re-acquire it
                    print("  Re-acquiring DAZ character — returning to pose mode")
                    if context.mode != 'POSE':
                        # Ensure the active object is visible before mode_set (hidden objects fail poll)
                        active = context.active_object
                        if active and active.hide_viewport:
                            active.hide_viewport = False
                        bpy.ops.object.mode_set(mode='POSE')
                    self._just_selected_armature = False
                    # Continue with normal click handling below...
                else:
                    # Clicked on something else — let Blender handle it normally
                    self._mouse_down_pos = None
                    self._accumulated_drag_distance = 0.0
                    self._last_detection_mouse_pos = None
                    return {'PASS_THROUGH'}

            # Only handle click if we're hovering over a bone or a PoseBridge morph CP
            # (morph CPs have _hover_bone_name=None to suppress mesh highlighting)
            if not self._hover_armature or (not self._hover_bone_name and not self._hover_from_posebridge):
                self._mouse_down_pos = None
                self._accumulated_drag_distance = 0.0
                self._last_detection_mouse_pos = None
                return {'PASS_THROUGH'}

            # POSEBRIDGE MODE: Skip raycast check - 2D control point hit detection is sufficient
            # Also skip for cross-viewport hovers (already raycast-verified)
            if not self._hover_from_posebridge and not getattr(self, '_hover_from_crossviewport', False):
                # Do a fresh raycast to verify we hit mesh (not clicking through to background)
                region = context.region

                # Safety check: ensure we're in a 3D viewport with valid region
                if not region or not context.space_data or context.space_data.type != 'VIEW_3D':
                    return {'PASS_THROUGH'}

                rv3d = context.space_data.region_3d
                if not rv3d:
                    return {'PASS_THROUGH'}

                coord = (event.mouse_region_x, event.mouse_region_y)
                view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
                ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)

                # Try to hit mesh
                hit_mesh = False
                for obj in context.scene.objects:
                    if obj.type == 'MESH':
                        # Skip LineArt copy meshes (hidden, no valid mesh data)
                        if 'LineArt_Copy' in obj.name:
                            continue
                        # Skip hidden objects
                        if obj.hide_viewport or obj.hide_get():
                            continue

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
                    self._accumulated_drag_distance = 0.0
                    self._last_detection_mouse_pos = None
                    return {'PASS_THROUGH'}

            # Record mouse position on press (to detect drags vs clicks)
            # Use absolute coords for cross-viewport compatibility
            self._mouse_down_pos = (event.mouse_x, event.mouse_y)
            self._accumulated_drag_distance = 0.0  # Reset accumulated distance
            self._last_detection_mouse_pos = self._mouse_down_pos  # Start tracking from mouse-down

            # POSEBRIDGE MORPH CP: Check BEFORE bone name check (morph CPs have _hover_bone_name=None)
            if self._hover_from_posebridge and self._hover_armature:
                cp = self._get_hovered_cp(context)
                if cp and cp.interaction_mode == 'morph':
                    # Morph CP: don't select bone, just prepare for drag
                    self._drag_bone_name = self._hover_control_point_id or 'head'
                    self._drag_armature = self._hover_armature
                    self._rotation_mouse_button = 'LEFT'
                    # Lock posebridge state at mouse-down (hover may drift during drag detection)
                    self._drag_from_posebridge = True
                    self._drag_control_point_id = self._hover_control_point_id
                    return {'RUNNING_MODAL'}

            # Hovering over a bone - prepare for potential drag
            if self._hover_bone_name and self._hover_armature:
                # POSEBRIDGE MODE: Check if this is the special "base" node
                if self._hover_from_posebridge and hasattr(self, '_hover_control_point_id'):
                    # Check if this is the base node
                    if self._hover_control_point_id == 'base':
                        # Special handling: Switch to object mode and select armature
                        print(f"  Base node clicked - switching to object mode")

                        # Deselect all
                        bpy.ops.object.select_all(action='DESELECT')

                        # Switch to object mode
                        if context.mode != 'OBJECT':
                            bpy.ops.object.mode_set(mode='OBJECT')

                        # Select the armature
                        self._hover_armature.select_set(True)
                        context.view_layer.objects.active = self._hover_armature

                        print(f"  Armature '{self._hover_armature.name}' selected in object mode")

                        # Clear mouse tracking
                        self._mouse_down_pos = None
                        self._accumulated_drag_distance = 0.0
                        self._last_detection_mouse_pos = None

                        # Consume event
                        return {'RUNNING_MODAL'}

                # Normal bone selection
                # Select bone immediately (don't wait for release)
                # This allows click-drag to work in one motion
                # Shift+click = additive selection (for multi-bone R rotate)
                self.select_bone(context, additive=event.shift)

                # Prepare for potential drag
                self._drag_bone_name = self._hover_bone_name
                self._drag_armature = self._hover_armature
                self._rotation_mouse_button = 'LEFT'  # Track which button will start the rotation
                # Lock posebridge state at mouse-down (hover may drift during drag detection)
                self._drag_from_posebridge = self._hover_from_posebridge
                self._drag_control_point_id = self._hover_control_point_id if self._hover_from_posebridge else None
                self._drag_bone_names = self._hover_bone_names if self._hover_from_posebridge else None

                # Consume event to prevent box select
                return {'RUNNING_MODAL'}

            return {'PASS_THROUGH'}

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            # End pin override (R/G on pinned bone) — confirm
            if self._pin_override_active:
                self._end_pin_override(context, cancel=False)
                return {'RUNNING_MODAL'}

            # End hip pin IK if native translate just confirmed
            if self._use_hip_pin_ik:
                self._end_hip_pin_ik(context, cancel=False)
                return {'RUNNING_MODAL'}

            # End native rotate + neck compensation if active
            if self._use_native_rotate_neck:
                self._end_native_rotate_neck(context, cancel=False)
                return {'RUNNING_MODAL'}

            # End morph if active
            if self._is_morphing:
                self.end_morph(context, cancel=False)
                return {'RUNNING_MODAL'}

            # End rotation if active
            if self._is_rotating:
                self.end_rotation(context, cancel=False)
                return {'RUNNING_MODAL'}

            # End IK drag if active (with keyframing)
            if self._is_dragging:
                self.end_ik_drag(context, cancel=False)
                return {'RUNNING_MODAL'}

            # Clear drag preparation state (click-without-drag: bone was selected on PRESS)
            if self._drag_bone_name:
                self._drag_bone_name = None
                self._drag_armature = None

                # Clear mouse tracking
                self._mouse_down_pos = None
                self._accumulated_drag_distance = 0.0
                self._last_detection_mouse_pos = None

                # Consume the RELEASE so Blender's default pose.select doesn't fire.
                # Without this, PASS_THROUGH lets Blender see "click on empty space"
                # (especially in PoseBridge camera viewports) and deselect the bone
                # we just selected on PRESS.
                return {'RUNNING_MODAL'}

            # Clear mouse tracking
            self._mouse_down_pos = None
            self._accumulated_drag_distance = 0.0
            self._last_detection_mouse_pos = None

            return {'PASS_THROUGH'}

        elif event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            # POSEBRIDGE MODE: Check if hovering over a control point - if so, start RMB rotation/morph
            if self._hover_from_posebridge and self._hover_armature:
                if not self._is_rotating and not self._is_morphing:
                    hover_id = self._hover_control_point_id or self._hover_bone_name
                    if hover_id:
                        print(f"  Right-click on {hover_id}: Starting RMB drag")

                        # Select bone (for rotation CPs)
                        if self._hover_bone_name:
                            self.select_bone(context)

                        # Prepare for drag
                        self._drag_bone_name = self._hover_bone_name or 'head'
                        self._drag_armature = self._hover_armature
                        self._rotation_mouse_button = 'RIGHT'  # Track right-click
                        self._mouse_down_pos = (event.mouse_x, event.mouse_y)  # Absolute coords for cross-viewport
                        self._right_click_used_for_drag = True  # Claim this RMB to suppress context menu
                        # Lock posebridge state at mouse-down (hover may drift during drag detection)
                        self._drag_from_posebridge = True
                        self._drag_control_point_id = self._hover_control_point_id
                        self._drag_bone_names = self._hover_bone_names

                        # Consume event
                        return {'RUNNING_MODAL'}

            # Cancel pin override (R/G on pinned bone)
            if self._pin_override_active:
                print("  Right-click: Canceling pin override")
                self._end_pin_override(context, cancel=True)
                return {'RUNNING_MODAL'}

            # Cancel hip pin IK if native translate was cancelled
            if self._use_hip_pin_ik:
                print("  Right-click: Canceling hip pin IK")
                self._end_hip_pin_ik(context, cancel=True)
                return {'RUNNING_MODAL'}

            # Cancel native rotate + neck compensation
            if self._use_native_rotate_neck:
                print("  Right-click: Canceling native rotate neck")
                self._end_native_rotate_neck(context, cancel=True)
                return {'RUNNING_MODAL'}

            # Cancel morph if active with LMB (RMB cancels LMB morph)
            if self._is_morphing and self._morph_mouse_button == 'LEFT':
                print("  Right-click: Canceling morph")
                self.end_morph(context, cancel=True)
                return {'RUNNING_MODAL'}

            # Cancel rotation if active (non-head bones or ESC alternative)
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
                self._accumulated_drag_distance = 0.0
                self._last_detection_mouse_pos = None

            # Show context menu if a bone is selected (hovered or active)
            armature = context.active_object
            if armature and armature.type == 'ARMATURE' and armature.data.bones.active:
                bpy.ops.wm.call_menu(name='DAZ_MT_bone_context')
                return {'RUNNING_MODAL'}

            return {'PASS_THROUGH'}

        elif event.type == 'RIGHTMOUSE' and event.value == 'RELEASE':
            # End morph if active (for right-click face morphs)
            if self._is_morphing and self._morph_mouse_button == 'RIGHT':
                self.end_morph(context, cancel=False)
                return {'RUNNING_MODAL'}

            # End rotation if active (for right-click head rotations)
            if self._is_rotating and self._rotation_mouse_button == 'RIGHT':
                self.end_rotation(context, cancel=False)
                return {'RUNNING_MODAL'}

            # Suppress context menu if right-click was used for drag
            if self._right_click_used_for_drag:
                print("  Right-click release: Suppressing context menu (was used for drag)")
                self._right_click_used_for_drag = False  # Clear flag
                return {'RUNNING_MODAL'}  # Consume event to prevent menu

            # Clear drag preparation state
            if self._drag_bone_name:
                self._drag_bone_name = None
                self._drag_armature = None
                self._mouse_down_pos = None
                self._accumulated_drag_distance = 0.0
                self._last_detection_mouse_pos = None

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
                    # Use absolute coords so start_ik_drag can correctly compute the
                    # region-local offset against whichever viewport the mouse is in
                    self._mouse_down_pos = (event.mouse_x, event.mouse_y)
                    # G key is always a direct bone operation, not a posebridge CP drag
                    self._drag_from_posebridge = False
                    self._drag_control_point_id = None
                    self._drag_bone_names = None

                    # Start IK drag immediately
                    self.start_ik_drag(context, event)

                    # Consume event to prevent Blender's grab operator
                    return {'RUNNING_MODAL'}

            return {'PASS_THROUGH'}

        elif event.type == 'R' and event.value == 'PRESS' and not event.alt and not event.ctrl and not event.shift:
            # R key: Intercept for neck compensation when rotating the hip OR any
            # spine chain bone. For hip, the full chain compensates. For a spine
            # bone, only bones ABOVE it compensate (the rotated bone itself moves
            # freely). For bones outside the chain, no interception needed — the
            # head's Copy Rotation constraint handles it.
            if context.mode == 'POSE' and context.active_object and context.active_object.type == 'ARMATURE' and context.active_bone:
                armature = context.active_object
                active_bone_name = context.active_bone.name
                active_pose_bone = armature.pose.bones.get(active_bone_name)
                is_hip = active_pose_bone and not active_pose_bone.parent
                spine_chain_names = [name for name, _ in self.SPINE_CHAIN_DEF]
                is_spine_bone = active_bone_name in spine_chain_names

                if is_hip:
                    neck_state = self._find_pinned_head(armature)
                elif is_spine_bone:
                    neck_state = self._find_pinned_head(armature, rotated_bone_name=active_bone_name)
                else:
                    neck_state = None

                # If active bone itself is rotation-pinned, mute constraint and
                # pass through to native rotate (override the pin)
                if not neck_state and active_pose_bone:
                    data_bone = armature.data.bones.get(active_bone_name)
                    if data_bone and is_bone_pinned_rotation(data_bone):
                        print(f"\n=== R Key: Override rotation pin on {active_bone_name} ===")
                        for c in active_pose_bone.constraints:
                            if c.name == "DAZ_Pin_Rotation" and not c.mute:
                                c.mute = True
                                print(f"  Muted {c.name} for override")
                        self._pin_override_active = True
                        self._pin_override_bone = active_bone_name
                        self._pin_override_armature = armature
                        self._pin_override_type = 'rotation'
                        return {'PASS_THROUGH'}

                if neck_state:
                    print(f"\n=== R Key: Native rotate + neck compensation ===")
                    self._drag_armature = armature
                    self._use_native_rotate_neck = True
                    self._native_rotate_neck_state = neck_state

                    # Store original spine/neck rotations for cancel
                    self._native_rotate_neck_originals = {}
                    for bone in neck_state['all_bones']:
                        self._native_rotate_neck_originals[bone.name] = bone.rotation_quaternion.copy()

                    # Mute head's rotation pin constraint
                    self._native_rotate_neck_muted = []
                    head_pose = neck_state['head_bone']
                    for c in head_pose.constraints:
                        if c.name == "DAZ_Pin_Rotation" and not c.mute:
                            c.mute = True
                            self._native_rotate_neck_muted.append((head_pose, c))
                            print(f"  Muted head rotation pin for neck solver")

                    # Install depsgraph handler for neck compensation
                    originals_ref = self._native_rotate_neck_originals
                    def native_rotate_neck_handler(scene, depsgraph):
                        if not self._use_native_rotate_neck or getattr(self, '_native_rotate_solving', False):
                            return
                        self._native_rotate_solving = True
                        try:
                            ns = self._native_rotate_neck_state
                            if not ns:
                                return
                            # Reset compensation bones to their pre-drag state (not identity).
                            # This preserves rotations from previous operations while giving
                            # the solver a clean baseline for this drag's compensation.
                            for bone in ns['all_bones']:
                                orig = originals_ref.get(bone.name)
                                bone.rotation_quaternion = orig.copy() if orig else Quaternion()
                            bpy.context.view_layer.update()
                            # Solve neck
                            self._solve_pinned_neck(bpy.context, armature, ns)
                        except Exception as e:
                            print(f"  [NECK ROT] Handler error: {e}")
                            import traceback
                            traceback.print_exc()
                        finally:
                            self._native_rotate_solving = False

                    self._native_rotate_handler = native_rotate_neck_handler
                    bpy.app.handlers.depsgraph_update_post.append(native_rotate_neck_handler)
                    print(f"  ✓ Installed neck rotation depsgraph handler")

                    # Launch Blender's native rotate
                    try:
                        bpy.ops.transform.rotate('INVOKE_DEFAULT')
                        print(f"  ✓ Invoked native rotate")
                    except Exception as e:
                        print(f"  ✗ Could not invoke rotate: {e}")
                        self._end_native_rotate_neck(context, cancel=True)

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

        elif event.type == 'D' and event.value == 'PRESS' and event.alt:
            # Alt+D: Clear debug overlay + clean up temp IK chains
            self._analytical_leg_debug_draw_data = {}
            self._analytical_leg_debug_trail = []
            if DEBUG_PRESERVE_IK_CHAIN:
                self.cleanup_temp_ik_chains(context)
            refresh_3d_viewports(context)
            self.report({'INFO'}, "Debug overlay cleared")
            return {'RUNNING_MODAL'}

        elif event.type == 'ESC' and event.value == 'PRESS':
            # Cancel pin override
            if self._pin_override_active:
                print("  ESC: Canceling pin override")
                self._end_pin_override(context, cancel=True)
                return {'RUNNING_MODAL'}

            # Cancel hip pin IK if active
            if self._use_hip_pin_ik:
                print("  ESC: Canceling hip pin IK")
                self._end_hip_pin_ik(context, cancel=True)
                return {'RUNNING_MODAL'}

            # Cancel native rotate + neck compensation
            if self._use_native_rotate_neck:
                print("  ESC: Canceling native rotate neck")
                self._end_native_rotate_neck(context, cancel=True)
                return {'RUNNING_MODAL'}

            # Cancel morph if active
            if self._is_morphing:
                self.end_morph(context, cancel=True)
                return {'RUNNING_MODAL'}

            # Exit on ESC only
            self.finish(context)
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        """Start the operator"""
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Must be in 3D View")
            return {'CANCELLED'}

        # Remove any draw handlers left by a previous instance (prevents stuck highlights)
        stale = set(VIEW3D_OT_daz_bone_select._active_draw_handlers)
        for h in stale:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
            except Exception:
                pass
        VIEW3D_OT_daz_bone_select._active_draw_handlers.clear()

        # Initialize state
        self._last_bone = ""
        self._hover_mesh = None
        self._hover_bone_name = None
        self._hover_armature = None
        self._base_body_mesh = None
        self._mouse_down_pos = None
        self._accumulated_drag_distance = 0.0
        self._last_detection_mouse_pos = None

        # Tooltip state (shows after 1 second of hovering)
        self._hover_start_time = None
        self._last_hovered_id = None
        self._tooltip_shown = False
        self._tooltip_text = None  # Text to display in tooltip
        self._tooltip_mouse_pos = None  # Mouse position for tooltip

        # Initialize IK drag state
        self._is_dragging = False
        self._drag_bone_name = None
        self._drag_armature = None
        # NEW: Using bone names instead of constraint/empty objects
        self._ik_target_bone_name = None
        self._ik_control_bone_names = []
        self._ik_daz_bone_names = []
        self._shoulder_target_names = []  # Shoulder targets for collar Damped Track
        self._is_leg_chain = False  # Legs get full range, arms get protection
        self._drag_plane_normal = None
        self._drag_plane_point = None
        self._drag_depth_reference = None  # Fixed depth for raycast consistency
        self._drag_initial_target_pos = None  # Initial target bone position (for delta-based movement)
        self._drag_initial_mouse_pos = None  # Initial mouse position (for delta-based movement)

        # FABRIK solver state (prototype)
        self._use_fabrik = False
        self._fabrik_chain = None
        self._fabrik_pinned_bone = None

        # Analytical leg IK state (bypasses Blender's IK solver completely)
        self._use_analytical_leg_ik = False
        self._analytical_leg_bones = {}  # {'thigh': bone, 'shin': bone, 'foot': bone}
        self._analytical_leg_hip_pos = None  # World position of hip (fixed during drag)
        self._analytical_leg_lengths = {}  # {'thigh': length, 'shin': length}
        self._analytical_leg_original_rotations = {}  # For undo/cancel
        self._analytical_leg_side = None  # 'l' or 'r'
        self._analytical_leg_knee_axis = None  # Knee bend direction from initial pose
        self._analytical_leg_shin_bend_axis = None  # Locked shin rotation axis (prevents flipping)
        self._analytical_leg_bend_plane_normal = None  # Normal to the plane knee bends in (locks knee direction)
        self._analytical_leg_debug_draw_data = {}  # Populated during drag, read by debug draw callback
        self._analytical_leg_debug_trail = []  # Trail of target positions during drag

        # Analytical arm IK state (mirrors leg solver)
        self._use_analytical_arm_ik = False
        self._analytical_arm_bones = {}  # {'shoulder': bone, 'shoulder_twist': bone, 'forearm': bone, 'forearm_twist': bone, 'hand': bone}
        self._analytical_arm_shoulder_pos = None  # World position of shoulder (fixed during drag)
        self._analytical_arm_lengths = {}  # {'upper': length, 'lower': length}
        self._analytical_arm_original_rotations = {}  # For undo/cancel
        self._analytical_arm_side = None  # 'l' or 'r'
        self._analytical_arm_bend_plane_normal = None  # Deferred to first solver frame
        self._analytical_arm_collar_influence = 0.45  # Fractional damped-track rotation for collar bone
        self._analytical_arm_debug_draw_data = {}
        self._analytical_arm_debug_trail = []

        # Native translate pass-through (G on hip with no pins)
        self._use_native_translate = False

        # Hip pin-driven IK state (analytical IK on pinned limbs while dragging hip)
        self._use_hip_pin_ik = False
        self._hip_pin_limbs = []          # List of per-limb state dicts
        self._hip_bone = None             # Hip pose bone reference
        self._hip_original_location = None  # For cancel/undo
        self._hip_original_rotations = {}  # {bone_name: {location, rotation}} for all affected bones
        self._hip_pin_muted_constraints = []  # [(pose_bone, constraint)] to unmute on end
        self._hip_debug_frame = 0
        self._hip_pin_neck_state = None   # Neck solver state dict (when head is rotation-pinned)

        # Soft pin system state (DAZ-like yielding pins)
        self._soft_pin_active = False
        self._soft_pin_child_name = None
        self._soft_pin_initial_pos = None
        self._soft_pin_stiffness = 0.8  # 0.0=no resistance, 1.0=maximum resistance
        self._soft_pin_muted_constraints = []  # Track muted constraints for cleanup

        # Double-click detection for armature selection (DAZ-style)
        self._last_click_time = 0.0
        self._last_click_pos = None
        self._just_selected_armature = False  # Track if we just switched to object mode
        self._switch_to_character = None  # Armature name to switch to (set by get_bone_from_hit)

        # Initialize rotation state (for pectoral bones)
        self._is_rotating = False
        self._rotation_bone = None
        self._rotation_initial_quat = None
        self._rotation_parent_frame_quat = None
        self._rotation_initial_mouse = None
        self._rotation_neck_state = None        # Neck solver state during PoseBridge rotation
        self._rotation_neck_muted = []          # [(pose_bone, constraint)] muted for PoseBridge rotation
        self._rotation_pin_limb_state = None    # Pinned-limb IK state during PoseBridge rotation (None=unchecked, False=not needed, list=active)
        self._rotation_pin_limb_muted = []      # [(pose_bone, constraint)] translation-pin constraints muted during rotation
        self._use_native_rotate_neck = False    # Native R key + neck compensation active
        self._native_rotate_neck_state = None   # Neck solver state for native R
        self._native_rotate_neck_muted = []     # Muted constraints for native R
        self._native_rotate_neck_originals = {} # Original neck rotations for cancel
        self._pin_override_active = False       # R/G on pinned bone — constraint muted, native transform
        self._pin_override_bone = None          # Bone name being overridden
        self._pin_override_armature = None      # Armature reference
        self._pin_override_type = None          # 'rotation' or 'translation'

        # Clear undo stack (use class-level list so external operators can push to it)
        VIEW3D_OT_daz_bone_select._undo_stack.clear()

        # Track temporarily unpinned bones (to restore pins after drag)
        self._temp_unpinned_bone = None
        self._temp_unpinned_data = None  # Store pin data to restore

        # Try to detect base body mesh from armature
        armature = None
        if context.active_object and context.active_object.type == 'ARMATURE':
            armature = context.active_object
        elif hasattr(context.scene, 'posebridge_settings'):
            # Fallback: look up armature from PoseBridge settings
            settings = context.scene.posebridge_settings
            if settings.is_active and settings.active_armature_name:
                arm_obj = bpy.data.objects.get(settings.active_armature_name)
                if arm_obj and arm_obj.type == 'ARMATURE':
                    armature = arm_obj

        if armature:
            # CRITICAL: Convert all bones to quaternion mode for consistent IK behavior
            # This eliminates quaternion/euler conversion issues throughout the code
            prepare_rig_for_ik(armature)

            self._base_body_mesh = find_base_body_mesh(context, armature)
            if self._base_body_mesh:
                print(f"  Using base mesh: {self._base_body_mesh.name}")
                # Initialize DSF face groups for clean zone detection
                self._face_group_mgr = dsf_face_groups.FaceGroupManager.get_or_create(
                    self._base_body_mesh, armature)

                # If DSF lookup failed (e.g. merged mesh polygon count mismatch) but a
                # BlenDAZ remap has been done, rebuild from the saved reference mesh.
                if not self._face_group_mgr.valid:
                    try:
                        pb_settings = context.scene.posebridge_settings
                        if (pb_settings.blendaz_init_status == 'ready' and
                                pb_settings.blendaz_reference_mesh_name):
                            ref_obj = bpy.data.objects.get(pb_settings.blendaz_reference_mesh_name)
                            if ref_obj:
                                print(f"  [FaceGroups] DSF mismatch — rebuilding from reference mesh '{ref_obj.name}'")
                                fgm = dsf_face_groups.FaceGroupManager.build_from_reference_mesh(
                                    ref_obj, self._base_body_mesh, armature)
                                if fgm:
                                    self._face_group_mgr = fgm
                    except Exception as _fgm_e:
                        print(f"  [FaceGroups] Auto-remap failed (non-fatal): {_fgm_e}")

        # Start modal
        context.window_manager.modal_handler_add(self)
        VIEW3D_OT_daz_bone_select._live_instance = self  # Used by init_character remap to push FGM updates
        self._set_header(context,"DAZ Bone Select Active - P to pin | Alt+Shift+R to clear pose | ESC to exit")

        # Register draw handler for highlighting
        self._draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_highlight_callback, (), 'WINDOW', 'POST_VIEW'
        )

        # Register separate persistent draw handler for pin spheres (always visible)
        self._pin_draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_pin_spheres_callback, (), 'WINDOW', 'POST_VIEW'
        )

        # Register tooltip draw handler (shows text near mouse after 1 sec hover)
        # Use a closure so the except block can remove the handler without touching self
        _handler_ref = [None]
        _self_ref = self
        def _tooltip_draw_closure():
            try:
                _self_ref.draw_tooltip_callback()
            except ReferenceError:
                # Operator is dead — remove the orphaned handler
                try:
                    bpy.types.SpaceView3D.draw_handler_remove(_handler_ref[0], 'WINDOW')
                except Exception:
                    pass
        self._tooltip_draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            _tooltip_draw_closure, (), 'WINDOW', 'POST_PIXEL'
        )
        _handler_ref[0] = self._tooltip_draw_handler

        # Register selection bracket draw handler (DAZ-style bounding box around selected bones)
        self._bracket_draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_selection_brackets_callback, (), 'WINDOW', 'POST_VIEW'
        )

        # Track all handlers at class level so the reload script can remove stale ones
        VIEW3D_OT_daz_bone_select._active_draw_handlers.update({
            self._draw_handler,
            self._pin_draw_handler,
            self._tooltip_draw_handler,
            self._bracket_draw_handler,
        })

        # Register debug draw handler for analytical leg IK (only when debug flag is set)
        self._debug_leg_draw_handler = None
        if _DEBUG_DRAW_ANALYTICAL_LEG:
            self._debug_leg_draw_handler = bpy.types.SpaceView3D.draw_handler_add(
                self.draw_analytical_leg_debug_callback, (), 'WINDOW', 'POST_VIEW'
            )

        # Register debug draw handler for analytical arm IK
        self._debug_arm_draw_handler = None
        if _DEBUG_DRAW_ANALYTICAL_ARM:
            self._debug_arm_draw_handler = bpy.types.SpaceView3D.draw_handler_add(
                self.draw_analytical_arm_debug_callback, (), 'WINDOW', 'POST_VIEW'
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
        # Signal the modal to self-terminate on next event
        self._should_stop = True

        self._set_header(context,None)
        self._last_bone = ""
        self._hover_mesh = None
        self._hover_bone_name = None
        self._hover_armature = None

        # Remove draw handlers
        for attr in ('_draw_handler', '_pin_draw_handler', '_tooltip_draw_handler',
                     '_bracket_draw_handler', '_debug_leg_draw_handler', '_debug_arm_draw_handler'):
            h = getattr(self, attr, None)
            if h:
                try:
                    bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
                except Exception:
                    pass
                VIEW3D_OT_daz_bone_select._active_draw_handlers.discard(h)
                setattr(self, attr, None)

        # Clear caches
        self._highlight_cache.clear()
        self._last_highlighted_bone = None
        VIEW3D_OT_daz_bone_select._bracket_vert_cache.clear()
        if VIEW3D_OT_daz_bone_select._live_instance is self:
            VIEW3D_OT_daz_bone_select._live_instance = None

        print("=== DAZ Bone Select & Pin Stopped ===\n")

    def _switch_active_character(self, context, target_armature_name):
        """Switch BlenDAZ to a different registered character.

        Hides old character's mannequin/outline, shows new character's,
        updates posebridge_settings, switches active armature to pose mode,
        and reloads modal state (body mesh, face groups).
        """
        settings = context.scene.posebridge_settings

        # Find old and new slots
        old_idx = settings.blendaz_active_index
        old_slot = settings.blendaz_characters[old_idx] if 0 <= old_idx < len(settings.blendaz_characters) else None
        new_idx = -1
        new_slot = None
        for i, slot in enumerate(settings.blendaz_characters):
            if slot.armature_name == target_armature_name:
                new_idx = i
                new_slot = slot
                break

        if not new_slot:
            print(f"[BlenDAZ] Cannot switch: '{target_armature_name}' not in registry")
            return False

        print(f"\n=== Switching character: {settings.active_armature_name} → {target_armature_name} ===")

        # 1. Cancel any active drag/morph state
        self._is_dragging = False
        self._is_rotating = False
        self._is_morphing = False
        self._drag_bone_name = None
        self._drag_armature = None

        # 2. Hide old character's PoseBridge objects
        if old_slot:
            for obj_name in [old_slot.mannequin_name, old_slot.outline_gp_name]:
                obj = bpy.data.objects.get(obj_name)
                if obj:
                    obj.hide_viewport = True

        # 3. Show new character's PoseBridge objects
        for obj_name in [new_slot.mannequin_name, new_slot.outline_gp_name]:
            obj = bpy.data.objects.get(obj_name)
            if obj:
                obj.hide_viewport = False

        # 4. Update settings
        settings.blendaz_active_index = new_idx
        settings.active_armature_name = target_armature_name

        # 5. Switch active object to new armature, enter pose mode
        new_armature = bpy.data.objects.get(target_armature_name)
        if new_armature:
            # Build context override for mode_set (same approach as select_bone)
            _ov = None
            for _area in context.screen.areas:
                if _area.type == 'VIEW_3D':
                    for _reg in _area.regions:
                        if _reg.type == 'WINDOW':
                            _sp = None
                            for _s in _area.spaces:
                                if _s.type == 'VIEW_3D':
                                    _sp = _s
                                    break
                            _ov = {'area': _area, 'region': _reg, 'space_data': _sp,
                                   'screen': context.screen, 'window': context.window}
                            break
                    if _ov:
                        break

            if context.mode != 'OBJECT':
                if _ov:
                    with bpy.context.temp_override(**_ov):
                        bpy.ops.object.mode_set(mode='OBJECT')
                else:
                    bpy.ops.object.mode_set(mode='OBJECT')

            bpy.ops.object.select_all(action='DESELECT')
            new_armature.select_set(True)
            context.view_layer.objects.active = new_armature

            # Unhide if hidden
            if new_armature.hide_viewport:
                new_armature.hide_viewport = False

            if _ov:
                with bpy.context.temp_override(**_ov):
                    bpy.ops.object.mode_set(mode='POSE')
            else:
                bpy.ops.object.mode_set(mode='POSE')

            # Convert to quaternion if needed
            prepare_rig_for_ik(new_armature)

        # 6. Reload modal state for new character
        self._base_body_mesh = find_base_body_mesh(context, new_armature) if new_armature else None
        self._face_group_mgr = None
        if self._base_body_mesh and new_armature:
            self._face_group_mgr = dsf_face_groups.FaceGroupManager.get_or_create(
                self._base_body_mesh, new_armature)
            # Fallback to reference mesh if DSF lookup fails
            if not self._face_group_mgr.valid:
                if new_slot.reference_mesh_name:
                    ref_obj = bpy.data.objects.get(new_slot.reference_mesh_name)
                    if ref_obj:
                        fgm = dsf_face_groups.FaceGroupManager.build_from_reference_mesh(
                            ref_obj, self._base_body_mesh, new_armature)
                        if fgm:
                            self._face_group_mgr = fgm

        # 7. Clear hover state
        self._hover_mesh = None
        self._hover_bone_name = None
        self._hover_armature = None
        self._highlight_cache.clear()
        self._last_highlighted_bone = None

        # 8. Switch viewport camera to new character's body camera
        space = context.space_data
        if space and space.type == 'VIEW_3D':
            cam = bpy.data.objects.get(new_slot.camera_body)
            if cam:
                space.camera = cam

        print(f"=== Switched to {target_armature_name} ===\n")
        return True

    def check_hover(self, context, event):
        """Check what's under mouse using dual raycast (prioritizes body mesh)"""

        # Clear character switch flag at the start of each hover check.
        # get_bone_from_hit() will re-set it if the mouse is over a registered non-active character.
        self._switch_to_character = None

        # POSEBRIDGE MODE: Use 2D control point hit detection instead of 3D raycast
        # Check this BEFORE bounds checking, since PoseBridge handles multi-viewport detection
        if hasattr(context.scene, 'posebridge_settings') and context.scene.posebridge_settings.is_active:
            self.check_posebridge_hover(context, event)
            if self._hover_from_posebridge:
                return  # Found a PoseBridge control point (or morph CP), done
            # Not on a PoseBridge CP — do cross-viewport mesh raycast.
            # This runs every frame to keep hover updated as the mouse moves.
            # context.region is the modal's invoke area, NOT where the mouse is,
            # so we detect the actual viewport and raycast from there.
            self._crossviewport_raycast(context, event)
            return

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

            # Safety check: ensure we're in a 3D viewport with a valid region
            if not region or not context.space_data or context.space_data.type != 'VIEW_3D':
                return

            rv3d = context.space_data.region_3d
            if not rv3d:
                return

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

        # Safety check: ensure we're in a 3D viewport with a valid region
        if not region or not context.space_data or context.space_data.type != 'VIEW_3D':
            return

        rv3d = context.space_data.region_3d
        if not rv3d:
            return

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

                # Apply IK target bone mapping (metatarsals → foot, carpals → hand)
                # This makes hover show the actual IK target, not the small bone
                mapped_bone = get_ik_target_bone(armature, bone_name, silent=True)
                if mapped_bone:
                    bone_name = mapped_bone
                # If mapping returned None (twist/pectoral), keep original bone
                elif mapped_bone is None:
                    pass  # Keep original bone_name

                # Update hover state
                self._hover_mesh = final_mesh
                self._hover_bone_name = bone_name
                self._hover_armature = armature
                self._hover_from_posebridge = False

                # Update header (only if changed to reduce flicker)
                if bone_name != self._last_bone:
                    # Check pin status for header display
                    data_bone = armature.data.bones.get(bone_name)
                    pin_status = get_pin_status_text(data_bone) if data_bone else ""
                    pin_text = f" | {pin_status}" if pin_status else ""

                    text = f"Hover: {bone_name}{pin_text} | Mesh: {mesh_name} | CLICK to select | P to pin"
                    self._set_header(context,text)
                    self._last_bone = bone_name
                    if context.area: context.area.tag_redraw()  # Redraw to update highlight
            else:
                # Hit mesh but no bone found
                self.clear_hover(context)
        else:
            # No hit
            self.clear_hover(context)

    def _crossviewport_raycast(self, context, event):
        """Raycast in whichever viewport the mouse is actually in.

        Modal operators receive context.region for their invoke area,
        which may differ from the viewport the mouse is currently in.
        This detects the correct viewport and raycasts from there.
        """
        mouse_x = event.mouse_x
        mouse_y = event.mouse_y

        # Find the VIEW_3D region the mouse is in
        target_region = None
        target_rv3d = None
        target_area = None
        for area in context.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for reg in area.regions:
                if reg.type != 'WINDOW':
                    continue
                if (reg.x <= mouse_x < reg.x + reg.width and
                        reg.y <= mouse_y < reg.y + reg.height):
                    target_region = reg
                    target_area = area
                    for sp in area.spaces:
                        if sp.type == 'VIEW_3D':
                            target_rv3d = sp.region_3d
                            break
                    break
            if target_region:
                break

        if not target_region or not target_rv3d:
            self.clear_hover(context)
            return

        # Store for use by drag functions and redraw (context.region is wrong for cross-viewport)
        self._crossviewport_region = target_region
        self._crossviewport_rv3d = target_rv3d
        self._crossviewport_area = target_area

        # Mouse position relative to the target region
        local_x = mouse_x - target_region.x
        local_y = mouse_y - target_region.y

        # Bounds check (header/sidebar)
        if local_y > target_region.height - 40 or local_y < 0:
            return
        if local_x < 0 or local_x > target_region.width:
            return

        coord = (local_x, local_y)

        # Raycast from the target viewport
        view_vector = view3d_utils.region_2d_to_vector_3d(target_region, target_rv3d, coord)
        ray_origin = view3d_utils.region_2d_to_origin_3d(target_region, target_rv3d, coord)

        result = context.scene.ray_cast(
            context.view_layer.depsgraph,
            ray_origin,
            view_vector
        )
        success, location, normal, index, obj, matrix = result

        # Also check base body mesh
        final_mesh = None
        final_location = None

        if self._base_body_mesh and obj != self._base_body_mesh:
            body_loc, body_dist = raycast_specific_mesh(
                self._base_body_mesh, ray_origin, view_vector, context
            )
            if body_loc:
                body_distance = (body_loc - ray_origin).length
                scene_distance = (location - ray_origin).length if success else float('inf')
                if body_distance - scene_distance < 1.0:
                    final_mesh = self._base_body_mesh
                    final_location = body_loc
        if not final_mesh and success and obj and obj.type == 'MESH':
            final_mesh = obj
            final_location = location

        if final_mesh and final_location:
            face_index = index if success and obj == final_mesh else None
            bone_info = self.get_bone_from_hit(final_mesh, final_location, face_index)
            if bone_info:
                mesh_name, bone_name, armature = bone_info
                mapped_bone = get_ik_target_bone(armature, bone_name, silent=True)
                if mapped_bone:
                    bone_name = mapped_bone

                self._hover_mesh = final_mesh
                self._hover_bone_name = bone_name
                self._hover_armature = armature
                self._hover_from_posebridge = False
                self._hover_from_crossviewport = True  # Skip fresh raycast on click (already verified)

                if bone_name != self._last_bone:
                    data_bone = armature.data.bones.get(bone_name)
                    pin_status = get_pin_status_text(data_bone) if data_bone else ""
                    pin_text = f" | {pin_status}" if pin_status else ""
                    text = f"Hover: {bone_name}{pin_text} | Mesh: {mesh_name} | CLICK to select | P to pin"
                    if target_area:
                        target_area.header_text_set(text)
                    self._last_bone = bone_name
                    if target_area:
                        target_area.tag_redraw()
                return

        self.clear_hover(context)

    def _get_region_rv3d(self, context, event):
        """Return (region, rv3d, mouse_local) for the viewport the mouse is in.

        Always finds the correct viewport by matching absolute mouse position
        against all VIEW_3D regions. This handles the cross-viewport case where
        the modal lives in the PoseBridge panel but the user operates in the
        main 3D viewport (e.g. G key drag after selecting via CP).
        mouse_local is (x, y) relative to the returned region.
        """
        mouse_x = event.mouse_x
        mouse_y = event.mouse_y

        # Scan all VIEW_3D areas and find the one the mouse is actually in
        for area in context.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for reg in area.regions:
                if reg.type != 'WINDOW':
                    continue
                if (reg.x <= mouse_x < reg.x + reg.width and
                        reg.y <= mouse_y < reg.y + reg.height):
                    for sp in area.spaces:
                        if sp.type == 'VIEW_3D':
                            rv3d = sp.region_3d
                            if rv3d:
                                local_x = mouse_x - reg.x
                                local_y = mouse_y - reg.y
                                return reg, rv3d, (local_x, local_y)

        # Fall back to context.region (modal's own viewport)
        region = context.region
        if region and context.space_data and context.space_data.type == 'VIEW_3D':
            rv3d = context.space_data.region_3d
            if rv3d:
                return region, rv3d, (event.mouse_region_x, event.mouse_region_y)

        return None, None, (0, 0)

    def check_posebridge_hover(self, context, event):
        """Check for control point hits in PoseBridge mode (2D hit detection)"""

        # Get PoseBridge settings
        settings = getattr(context.scene, 'posebridge_settings', None)
        if not settings:
            return False

        # Get active armature from PoseBridge settings
        armature = None
        if settings.active_armature_name:
            armature = bpy.data.objects.get(settings.active_armature_name)

        if not armature or armature.type != 'ARMATURE':
            self.clear_hover(context)
            return

        # Find which 3D viewport region the mouse is currently in
        region = None
        rv3d = None
        viewport_space = None
        mouse_x = event.mouse_x
        mouse_y = event.mouse_y

        for area in context.screen.areas:
            if area.type != 'VIEW_3D':
                continue

            # Check all regions in this area
            for reg in area.regions:
                if reg.type != 'WINDOW':
                    continue

                # Check if mouse is within this region's bounds
                if (reg.x <= mouse_x < reg.x + reg.width and
                    reg.y <= mouse_y < reg.y + reg.height):
                    # Found the region! Get its space's region_3d
                    region = reg
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            rv3d = space.region_3d
                            viewport_space = space
                            break
                    break

            if region:
                break

        if not region or not rv3d:
            return

        # Only run CP hit-testing in PoseBridge camera viewports.
        # Non-camera viewports (perspective/orbit) are handled by _crossviewport_raycast.
        # Look up camera from active CharacterSlot; fall back to legacy names
        active_panel = settings.active_panel
        expected_cam = None
        if hasattr(settings, 'blendaz_characters'):
            idx = settings.blendaz_active_index
            if 0 <= idx < len(settings.blendaz_characters):
                slot = settings.blendaz_characters[idx]
                expected_cam = {'body': slot.camera_body, 'hands': slot.camera_hands,
                                'face': slot.camera_face}.get(active_panel)
        if not expected_cam or expected_cam not in bpy.data.objects:
            PANEL_CAMERAS_LEGACY = {
                'body':  'PB_Outline_LineArt_Camera',
                'hands': 'PB_Camera_Hands',
                'face':  'PB_Camera_Face',
            }
            expected_cam = PANEL_CAMERAS_LEGACY.get(active_panel)
        if expected_cam:
            if rv3d.view_perspective != 'CAMERA':
                return  # Not in camera view — let _crossviewport_raycast handle it
            viewport_cam = viewport_space.camera if viewport_space.camera else context.scene.camera
            if not viewport_cam or viewport_cam.name != expected_cam:
                return  # Wrong camera — let _crossviewport_raycast handle it

        # Import PoseBridge utilities
        addon_dir = os.path.dirname(os.path.abspath(__file__))
        posebridge_dir = os.path.join(addon_dir, 'posebridge')
        if posebridge_dir not in sys.path:
            sys.path.insert(0, addon_dir)

        # Import shared utilities and PoseBridgeDrawHandler
        from daz_shared_utils import get_genesis8_control_points
        try:
            from posebridge.drawing import PoseBridgeDrawHandler
        except ImportError:
            # PoseBridge not available, fallback to normal mode
            return

        # USE FIXED CONTROL POINT POSITIONS (from T-pose)
        fixed_control_points = settings.control_points_fixed

        if not fixed_control_points or len(fixed_control_points) == 0:
            # No fixed positions stored yet - clear hover and return
            self.clear_hover(context)
            return

        # Mouse position relative to the detected region
        mouse_region_x = event.mouse_x - region.x
        mouse_region_y = event.mouse_y - region.y

        # For face CPs, precompute head bone's current world matrix (bone-local → world)
        face_head_matrix = None
        if active_panel == 'face':
            head_pbone = armature.pose.bones.get('head')
            if head_pbone:
                face_head_matrix = armature.matrix_world @ head_pbone.matrix

        # Find closest control point
        closest_bone = None
        closest_cp_id = None
        closest_cp = None
        closest_distance = 20.0  # Hit threshold in pixels

        from mathutils import Vector

        for cp in fixed_control_points:
            # Only test control points that belong to the active panel
            cp_panel = cp.panel_view if cp.panel_view else 'body'
            if cp_panel != active_panel:
                continue

            bone_name = cp.bone_name

            # Get fixed 3D position (from T-pose, with Z offset already applied)
            fixed_pos_3d = Vector(cp.position_3d_fixed)

            # Face CPs are stored in head-bone-local space — transform to current world
            if cp_panel == 'face' and face_head_matrix:
                fixed_pos_3d = face_head_matrix @ fixed_pos_3d

            # Project fixed 3D position to 2D viewport coordinates
            pos_2d = view3d_utils.location_3d_to_region_2d(
                region,
                rv3d,
                fixed_pos_3d
            )

            if pos_2d is None:
                continue  # Bone is behind camera

            # Calculate distance from mouse
            distance = ((mouse_region_x - pos_2d[0])**2 + (mouse_region_y - pos_2d[1])**2)**0.5

            # Update if this is the closest control point
            if distance < closest_distance:
                closest_distance = distance
                closest_bone = bone_name
                closest_cp_id = cp.id
                closest_cp = cp

        # Update hover state
        if closest_bone and closest_cp:
            # Find mesh associated with armature for highlighting
            mesh_obj = None
            for obj in context.scene.objects:
                if obj.type == 'MESH':
                    for mod in obj.modifiers:
                        if mod.type == 'ARMATURE' and mod.object == armature:
                            mesh_obj = obj
                            break
                    if mesh_obj:
                        break

            # Update hover state (for mesh highlighting)
            # Skip mesh highlight for morph CPs — they all reference 'head'
            # and highlighting the entire head mesh is distracting
            if closest_cp.interaction_mode == 'morph':
                self._hover_mesh = None
                self._hover_bone_name = None
            else:
                self._hover_mesh = mesh_obj
                self._hover_bone_name = closest_bone
            self._hover_armature = armature
            self._hover_from_posebridge = True

            # Store control point info for multi-bone handling and special nodes
            if closest_cp.control_type == 'multi':
                # For multi-bone controls, store the ID and look up bone list from definitions
                self._hover_control_point_id = closest_cp_id
                # Look up bone names from body control point definitions
                cp_defs = get_genesis8_control_points()
                bone_names_list = None
                for cp_def in cp_defs:
                    if cp_def['id'] == closest_cp_id and 'bone_names' in cp_def:
                        bone_names_list = cp_def['bone_names']
                        break
                # Fallback: check hand finger groups / fist controls
                if bone_names_list is None:
                    from daz_shared_utils import get_finger_group_bones
                    bone_names_list = get_finger_group_bones(closest_cp_id)
                self._hover_bone_names = bone_names_list
            else:
                # For single-bone controls, also store ID (for special nodes like "base")
                self._hover_control_point_id = closest_cp_id
                self._hover_bone_names = None

            # Update PoseBridgeDrawHandler (for control point yellow highlight)
            # Use ID for multi-bone controls and morph controls, bone name for single rotation controls
            if closest_cp.control_type == 'multi' or closest_cp.interaction_mode == 'morph':
                PoseBridgeDrawHandler._hovered_control_point = closest_cp_id
            else:
                PoseBridgeDrawHandler._hovered_control_point = closest_bone

            # Tooltip timer: Track hover time for detailed tooltips
            import time
            current_time = time.time()

            # Check if we're hovering over a different control point
            if closest_cp_id != self._last_hovered_id:
                # New control point - reset timer
                self._hover_start_time = current_time
                self._last_hovered_id = closest_cp_id
                self._tooltip_shown = False

            # Check if we've been hovering for more than 1 second
            show_tooltip = False
            if self._hover_start_time and (current_time - self._hover_start_time) >= 1.0:
                if not self._tooltip_shown:
                    show_tooltip = True
                    self._tooltip_shown = True

            # Update header with basic info (always show simple text)
            display_name = closest_cp.id if closest_cp.control_type == 'multi' else closest_bone
            if display_name != self._last_bone:
                text = f"PoseBridge: {display_name} | Click+Drag to rotate | ESC to exit"
                self._set_header(context,text)
                self._last_bone = display_name
                if context.area: context.area.tag_redraw()  # Trigger immediate highlight update

            # Set tooltip text for GPU drawing (appears after 1 second hover)
            # Tooltip persists while hovering same control point.
            # Cleared by: clear_hover() when mouse leaves, or mouse press handler on click/drag.
            if show_tooltip:
                tooltip_text = closest_cp.label
                self._tooltip_text = tooltip_text
                self._tooltip_mouse_pos = (event.mouse_region_x, event.mouse_region_y)
                if context.area: context.area.tag_redraw()
        else:
            # No control point under mouse
            self.clear_hover(context)
            PoseBridgeDrawHandler._hovered_control_point = None

    def clear_hover(self, context):
        """Clear hover state"""
        if self._last_bone:
            self._set_header(context,"DAZ Bone Select Active - P to pin | U to unpin | Alt+Shift+R to clear pose | ESC to exit")
            self._last_bone = ""
            self._hover_mesh = None
            self._hover_bone_name = None
            self._hover_armature = None
            self._hover_from_posebridge = False
            self._hover_from_crossviewport = False

            # Reset tooltip timer and clear tooltip
            self._hover_start_time = None
            self._last_hovered_id = None
            self._tooltip_shown = False
            self._tooltip_text = None
            self._tooltip_mouse_pos = None

            if context.area: context.area.tag_redraw()  # Redraw to clear highlight

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

        # Only interact with BlenDAZ-registered armatures.
        # If the hit armature is registered but not the active one, flag for switching.
        # If it's not registered at all, return None (pass through to Blender).
        settings = getattr(bpy.context.scene, 'posebridge_settings', None)
        if settings and hasattr(settings, 'blendaz_characters') and len(settings.blendaz_characters) > 0:
            # Multi-character registry exists — check against all registered armatures
            registered = False
            for slot in settings.blendaz_characters:
                if slot.armature_name == armature.name:
                    registered = True
                    break
            if not registered:
                return None  # Unregistered rig — pass through
            if armature.name != settings.active_armature_name:
                # Registered but not active — flag for character switch
                self._switch_to_character = armature.name
                return None
        elif settings and settings.active_armature_name:
            # Legacy single-character mode (no registry)
            if armature.name != settings.active_armature_name:
                return None

        mesh = mesh_obj.data

        # METHOD 0: DSF Face Group lookup (clean, hard-edged zone boundaries)
        if self._face_group_mgr and self._face_group_mgr.valid:
            matrix_inv = mesh_obj.matrix_world.inverted()
            hit_local = matrix_inv @ hit_location
            bone_name = self._face_group_mgr.lookup_bone(face_index, hit_local)
            if bone_name and bone_name in armature.data.bones:
                return (mesh_obj.name, bone_name, armature)

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
                        # Return raw bone name - mapping will happen in hover update via get_ik_target_bone
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
            # Fallback: Hit vertex has no weights - search nearby vertices (within 5cm radius)
            # This handles unweighted areas of the mesh
            search_radius = 0.05  # 5cm
            for i, nearby_vert in enumerate(mesh.vertices):
                if nearby_vert.groups and (nearby_vert.co - hit_local).length < search_radius:
                    # Found a weighted vertex nearby - use it instead
                    vert = nearby_vert
                    nearest_vert_idx = i
                    break

            # If still no groups after search, give up
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
                # Return raw bone name - mapping will happen in hover update via get_ik_target_bone
                return (mesh_obj.name, bone_name, armature)

        return None

    def select_bone(self, context, additive=False):
        """Select the hovered bone in pose mode (with mapping for metatarsals/metacarpals).
        If additive=True (Shift+click), adds to current selection instead of replacing."""

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

        # Build a context override pointing at a valid 3D viewport.
        # bpy.ops.object.mode_set / pose.select_all / object.select_all all require
        # a VIEW_3D + WINDOW context to function correctly. When the modal lives in
        # the PoseBridge camera panel, context.region/area are for that panel, which
        # can cause these operators to silently fail or operate on the wrong viewport.
        # Prefer the main (non-camera) perspective viewport; fall back to any VIEW_3D.
        override_area = None
        override_region = None
        override_space = None
        for a in context.screen.areas:
            if a.type != 'VIEW_3D':
                continue
            for sp in a.spaces:
                if sp.type != 'VIEW_3D':
                    continue
                rv3d = sp.region_3d
                # Prefer non-camera perspective viewports (the main 3D viewport)
                is_camera = rv3d and rv3d.view_perspective == 'CAMERA'
                for reg in a.regions:
                    if reg.type == 'WINDOW':
                        if override_area is None or not is_camera:
                            override_area = a
                            override_region = reg
                            override_space = sp
                        if not is_camera:
                            break  # Found a good non-camera viewport, stop looking
            if override_area and override_space and override_space.region_3d and \
                    override_space.region_3d.view_perspective != 'CAMERA':
                break  # Got a non-camera viewport, done

        def _ops_override():
            """Return a context override dict for bpy.ops calls, or None if unavailable."""
            if override_area and override_region:
                return {
                    'area': override_area,
                    'region': override_region,
                    'space_data': override_space,
                    'screen': context.screen,
                    'window': context.window,
                }
            return None

        # Switch to the armature if needed
        if context.active_object != armature:
            print(f"  Switching active object to: {armature.name}")
            ov = _ops_override()
            if ov:
                with bpy.context.temp_override(**ov):
                    bpy.ops.object.select_all(action='DESELECT')
            else:
                bpy.ops.object.select_all(action='DESELECT')
            armature.select_set(True)
            context.view_layer.objects.active = armature

        # Enter pose mode if not already
        if context.mode != 'POSE':
            print(f"  Switching to Pose Mode")
            ov = _ops_override()
            if ov:
                with bpy.context.temp_override(**ov):
                    bpy.ops.object.mode_set(mode='POSE')
            else:
                bpy.ops.object.mode_set(mode='POSE')

        # Select the target bone
        if bone_name in armature.pose.bones:
            # Make the armature active
            context.view_layer.objects.active = armature

            # Always go through full selection path (edit mode roundtrip)
            # The rotation/location cache preserves all pose data through the mode switch
            if not additive:
                ov = _ops_override()
                if ov:
                    with bpy.context.temp_override(**ov):
                        bpy.ops.pose.select_all(action='DESELECT')
                else:
                    bpy.ops.pose.select_all(action='DESELECT')

            # Set the active bone
            armature.data.bones.active = armature.data.bones[bone_name]

            # Select by switching to edit mode and back (robust workaround)
            try:
                # CACHE all bone rotations and locations before mode switch
                rotation_cache = {}
                location_cache = {}
                for pb in armature.pose.bones:
                    if pb.rotation_mode == 'QUATERNION':
                        rotation_cache[pb.name] = pb.rotation_quaternion.copy()
                    else:
                        rotation_cache[pb.name] = pb.rotation_euler.copy()
                    # Cache location for root bones and any with non-zero location
                    if pb.bone.parent is None or pb.location.length_squared > 1e-8:
                        location_cache[pb.name] = pb.location.copy()

                ov = _ops_override()
                if ov:
                    with bpy.context.temp_override(**ov):
                        bpy.ops.object.mode_set(mode='EDIT')
                else:
                    bpy.ops.object.mode_set(mode='EDIT')

                edit_bone = armature.data.edit_bones.get(bone_name)
                if edit_bone:
                    if not additive:
                        for eb in armature.data.edit_bones:
                            eb.select = False
                            eb.select_head = False
                            eb.select_tail = False
                    edit_bone.select = True
                    edit_bone.select_head = True
                    edit_bone.select_tail = True

                ov = _ops_override()
                if ov:
                    with bpy.context.temp_override(**ov):
                        bpy.ops.object.mode_set(mode='POSE')
                else:
                    bpy.ops.object.mode_set(mode='POSE')

                # RESTORE all bone rotations after mode switch
                for bn, rot in rotation_cache.items():
                    pb = armature.pose.bones.get(bn)
                    if pb:
                        if pb.rotation_mode == 'QUATERNION':
                            pb.rotation_quaternion = rot
                        else:
                            pb.rotation_euler = rot

                # RESTORE bone locations (hip, any translated bones)
                for bn, loc in location_cache.items():
                    pb = armature.pose.bones.get(bn)
                    if pb:
                        pb.location = loc

                armature.data.bones.active = armature.data.bones[bone_name]
                print(f"  ✓ {'Added' if additive else 'Selected'} bone: {bone_name}")

            except Exception as e:
                print(f"  ✗ Selection error: {e}")
                ov = _ops_override()
                if context.mode != 'POSE':
                    if ov:
                        with bpy.context.temp_override(**ov):
                            bpy.ops.object.mode_set(mode='POSE')
                    else:
                        bpy.ops.object.mode_set(mode='POSE')

            # Update view — redraw the correct viewport (not modal's invoke area)
            context.view_layer.update()
            xv_area = getattr(self, '_crossviewport_area', None)
            if xv_area and getattr(self, '_hover_from_crossviewport', False):
                xv_area.tag_redraw()
            else:
                if context.area: context.area.tag_redraw()

            self.report({'INFO'}, f"Selected: {bone_name}")

            # Update header to confirm
            text = f"SELECTED: {bone_name} | Hover and click to select another bone"
            self._set_header(context,text)
        else:
            print(f"  ✗ Bone not found in armature: {bone_name}")

    def start_ik_drag(self, context, event):
        """Start IK drag on the selected bone"""
        if not self._drag_bone_name or not self._drag_armature:
            return

        # Ensure rig is in quaternion mode (handles armature switching mid-session)
        prepare_rig_for_ik(self._drag_armature)

        mouse_pos = (event.mouse_x, event.mouse_y)  # Absolute coords for debug
        print(f"\n=== Starting IK Drag: {self._drag_bone_name} | Mouse: {mouse_pos} ===")

        # POSEBRIDGE MODE: Use rotation mode for control point drags (not 3D mesh drags)
        # Use _drag_from_posebridge (locked at mouse-down) instead of _hover_from_posebridge
        # (which may have been cleared if mouse drifted off CP during drag threshold detection)
        if self._drag_from_posebridge:
            # Check if this is a morph control point (face panel)
            # Use stored _drag_control_point_id since hover may have drifted
            cp = None
            cp_id = self._drag_control_point_id or self._hover_control_point_id
            if cp_id:
                settings = context.scene.posebridge_settings
                for c in settings.control_points_fixed:
                    if c.id == cp_id:
                        cp = c
                        break
            if cp and cp.interaction_mode == 'morph':
                print("  → PoseBridge mode: Starting morph mode")
                self.start_morph_drag(context, event)
                return

            print("  → PoseBridge mode: Starting rotation mode")

            # Use locked drag state (set at mouse-down) for multi-bone group and CP id
            drag_bone_names = self._drag_bone_names
            drag_cp_id = self._drag_control_point_id or self._hover_control_point_id

            # Check if this is a multi-bone group control
            if drag_bone_names:
                # Multi-bone group rotation
                print(f"  → Multi-bone group: {drag_bone_names}")
                self._set_header(context,f"PoseBridge: {drag_cp_id} (Group) - Drag to rotate | ESC to cancel")

                # Store initial state for all bones in group
                self._is_rotating = True
                self._rotation_group_id = drag_cp_id  # Store group ID for axis lookup
                self._rotation_bones = []  # List of bones
                self._rotation_initial_quats = []  # List of initial rotations

                # Cache group controls dict for data-driven rotation (looked up once, used per-frame)
                from daz_shared_utils import get_group_controls
                self._rotation_group_controls = get_group_controls(self._rotation_group_id)
                print(f"  → Group controls: {self._rotation_group_controls}")

                for bone_name in drag_bone_names:
                    if bone_name in self._drag_armature.pose.bones:
                        bone = self._drag_armature.pose.bones[bone_name]
                        bone.rotation_mode = 'QUATERNION'
                        self._rotation_bones.append(bone)
                        self._rotation_initial_quats.append(bone.rotation_quaternion.copy())

                # Bail out if no valid bones were found in armature
                if not self._rotation_bones:
                    print(f"  ✗ No valid bones found for group: {drag_bone_names}")
                    self._is_rotating = False
                    self._rotation_group_id = None
                    self._rotation_group_controls = None
                    self._drag_bone_name = None
                    return

                self._rotation_bone = None  # Not used for multi-bone
                self._rotation_initial_mouse = (event.mouse_x, event.mouse_y)

                # Don't set _right_click_used_for_drag yet - wait for actual movement

                # Clear drag bone name
                self._drag_bone_name = None

                print(f"  Initialized {len(self._rotation_bones)} bones for group rotation")
                return
            else:
                # Single bone rotation - verify bone exists in armature
                if self._drag_bone_name not in self._drag_armature.pose.bones:
                    print(f"  ✗ Bone not found in armature: {self._drag_bone_name}")
                    self._drag_bone_name = None
                    return

                self._set_header(context,f"PoseBridge: {self._drag_bone_name} - Drag to rotate | ESC to cancel")

                # Get the bone
                bone = self._drag_armature.pose.bones[self._drag_bone_name]

                # Force quaternion mode
                bone.rotation_mode = 'QUATERNION'

                # Store initial state
                self._is_rotating = True
                self._rotation_bone = bone
                self._rotation_initial_quat = bone.rotation_quaternion.copy()
                self._rotation_initial_mouse = (event.mouse_x, event.mouse_y)

                # Cache the bone's parent-frame orientation for correct world-to-local conversion.
                # parent_frame = bone's world orientation with rotation_quaternion factored out.
                # bone_world = parent_frame @ rotation_quaternion, so
                # rotation_quaternion = parent_frame.inv() @ desired_world
                bone_world_mat = self._drag_armature.matrix_world @ bone.matrix
                basis_rot = bone.matrix_basis.to_quaternion()
                self._rotation_parent_frame_quat = bone_world_mat.to_quaternion() @ basis_rot.inverted()

                # Initialize twist bone storage and check for shoulder/forearm/thigh bend bones
                if not hasattr(self, '_twist_bone_initial_quats'):
                    self._twist_bone_initial_quats = {}

                bone_lower = bone.name.lower()
                if (('shldr' in bone_lower or 'shoulder' in bone_lower or
                     'forearm' in bone_lower or 'lorearm' in bone_lower or
                     'thigh' in bone_lower) and
                    'bend' in bone_lower):
                    twist_bone_name = bone.name.replace('Bend', 'Twist')
                    if twist_bone_name in self._drag_armature.pose.bones:
                        twist_bone = self._drag_armature.pose.bones[twist_bone_name]
                        twist_bone.rotation_mode = 'QUATERNION'
                        self._twist_bone_initial_quats[twist_bone_name] = twist_bone.rotation_quaternion.copy()
                        print(f"  Also initialized twist bone: {twist_bone_name}")

                # Don't set _right_click_used_for_drag yet - wait for actual movement

                # Clear drag bone name (rotation is now active)
                # Keep _drag_armature for undo system
                self._drag_bone_name = None

                print(f"  Initial rotation: {self._rotation_initial_quat}")
                return

        # Check if the bone being dragged is pinned - store for later, but DON'T unpin yet
        # (we need pins active during chain creation so parent bones get locked)
        data_bone = self._drag_armature.data.bones.get(self._drag_bone_name)
        dragging_pinned_bone = data_bone and (is_bone_pinned_translation(data_bone) or is_bone_pinned_rotation(data_bone))
        if dragging_pinned_bone:
            print(f"  ⚠️  Bone is pinned - will temporarily disable pin for this drag")
            # Track which bone to unmute after drag
            self._temp_unpinned_bone = self._drag_bone_name
            # Note: Pin constraint will be muted during IK chain creation

        # Map to IK-appropriate bone (e.g., carpal → hand, face → head)
        ik_bone_name = get_ik_target_bone(self._drag_armature, self._drag_bone_name)

        # If bone shouldn't use IK, check if it's a pectoral (use rotation mode)
        if not ik_bone_name:
            # Pectoral bones: Use Blender's trackball rotate
            if is_pectoral(self._drag_bone_name):
                print("  → Pectoral bone: Using Blender's trackball rotate")

                # The bone is already selected from select_bone()
                # Just invoke Blender's trackball rotate operator
                try:
                    bpy.ops.transform.trackball('INVOKE_DEFAULT')
                    print("  ✓ Invoked trackball rotate")
                except Exception as e:
                    print(f"  ✗ Could not invoke trackball rotate: {e}")

                # Clear drag state - Blender's operator takes over
                self._drag_bone_name = None
                self._drag_armature = None
                return
            else:
                # Other non-IK bones (twist bones, etc.): abort
                print("  ✗ Bone not suitable for IK drag")
                self._set_header(context,f"{self._drag_bone_name} - Not IK-draggable (use gizmo to rotate)")
                self._drag_bone_name = None
                self._drag_armature = None
                return

        # Root bone (hip): no parent for IK chain
        pose_bone = self._drag_armature.pose.bones.get(ik_bone_name)
        if pose_bone and not pose_bone.parent:
            armature = self._drag_armature
            pinned_limbs = self._find_pinned_limbs(armature)
            has_pinned_head = self._find_pinned_head(armature) is not None
            if pinned_limbs or has_pinned_head:
                # Pin-driven hip drag: use native translate + depsgraph handler for IK
                pin_count = len(pinned_limbs) + (1 if has_pinned_head else 0)
                print(f"  → Root bone ({ik_bone_name}): Native translate + pin IK ({pin_count} pin(s))")
                self._start_hip_pin_drag(context, event, pose_bone, pinned_limbs)
                return
            else:
                # No pins: use native translate (original behavior)
                print(f"  → Root bone ({ik_bone_name}): Using Blender's native translate")
                self._use_native_translate = True
                try:
                    bpy.ops.transform.translate('INVOKE_DEFAULT')
                    print("  ✓ Invoked native translate")
                except Exception as e:
                    print(f"  ✗ Could not invoke translate: {e}")
                    self._use_native_translate = False
                self._drag_bone_name = None
                self._drag_armature = None
                return

        # Use the mapped bone for IK
        self._drag_bone_name = ik_bone_name

        # Check for pinned children and enable soft pin system
        # This creates DAZ-like "soft constraint" behavior where pins resist but yield under force
        self._soft_pin_active = False
        self._soft_pin_child_name = None
        self._soft_pin_initial_pos = None
        self._soft_pin_stiffness = 0.8  # 0.0=no resistance, 1.0=maximum resistance (but still yields)

        if has_pinned_children(self._drag_armature, self._drag_bone_name, ignore_pin_on_bone=self._temp_unpinned_bone):
            print("\n  🔧 SOFT PIN MODE: Detected pinned child, using soft constraint system")

            # Walk down to find pinned child (recursively through twist bones)
            def find_pinned_child_recursive(bone, depth=0):
                """Recursively find pinned child, skipping twist bones"""
                if depth > 5:
                    return None
                for child in bone.children:
                    if child.name == self._temp_unpinned_bone:
                        continue
                    # Check if child is twist bone - if so, recurse
                    if is_twist_bone(child.name):
                        result = find_pinned_child_recursive(child, depth + 1)
                        if result:
                            return result
                        continue
                    # Non-twist bone - check if pinned
                    child_data_bone = self._drag_armature.data.bones.get(child.name)
                    if child_data_bone and is_bone_pinned_translation(child_data_bone):
                        return child
                    # Not pinned - recurse
                    result = find_pinned_child_recursive(child, depth + 1)
                    if result:
                        return result
                return None

            dragged_pose_bone = self._drag_armature.pose.bones[self._drag_bone_name]
            pinned_child = find_pinned_child_recursive(dragged_pose_bone)

            if pinned_child:
                self._soft_pin_active = True
                self._soft_pin_child_name = pinned_child.name
                # Store initial world position of pinned bone
                pinned_pose_bone = self._drag_armature.pose.bones[pinned_child.name]
                self._soft_pin_initial_pos = self._drag_armature.matrix_world @ pinned_pose_bone.head
                print(f"  Soft pin child: {pinned_child.name}")
                print(f"  Initial pin position: {self._soft_pin_initial_pos}")

                # IMPORTANT: Mute the hard Copy Location constraint on pinned child
                # We'll manage its position softly instead
                for constraint in pinned_pose_bone.constraints:
                    if constraint.type == 'COPY_LOCATION' and constraint.mute == False:
                        constraint.mute = True
                        print(f"  Muted hard pin constraint on {pinned_child.name}")
                        # Track for re-enabling later
                        if not hasattr(self, '_soft_pin_muted_constraints'):
                            self._soft_pin_muted_constraints = []
                        self._soft_pin_muted_constraints.append((pinned_pose_bone, constraint))
            else:
                print("  ✗ Could not find pinned child, using normal IK")

        # Check if this is a leg bone - use analytical IK instead of Blender's IK solver
        # Analytical IK has no local minima and handles straightening correctly
        bone_lower = self._drag_bone_name.lower()
        is_leg_bone = 'foot' in bone_lower or 'shin' in bone_lower or 'calf' in bone_lower

        if is_leg_bone and not self._soft_pin_active:
            print("  → LEG BONE DETECTED: Using analytical IK (bypasses Blender's solver)")

            # Determine side (left or right)
            if bone_lower.startswith('l'):
                self._analytical_leg_side = 'l'
            elif bone_lower.startswith('r'):
                self._analytical_leg_side = 'r'
            else:
                # Try to find side from bone name
                self._analytical_leg_side = 'l' if 'left' in bone_lower else 'r'

            side = self._analytical_leg_side

            # Find leg bones (thigh, shin, foot)
            # DAZ naming: lThigh, lShin, lFoot (or lThighBend, etc.)
            pose_bones = self._drag_armature.pose.bones

            # Find thigh bone
            thigh_bone = None
            for name_pattern in [f'{side}Thigh', f'{side}ThighBend']:
                if name_pattern in pose_bones:
                    thigh_bone = pose_bones[name_pattern]
                    break

            # Find shin bone
            shin_bone = None
            for name_pattern in [f'{side}Shin', f'{side}ShinBend', f'{side}Calf']:
                if name_pattern in pose_bones:
                    shin_bone = pose_bones[name_pattern]
                    break

            # Find foot bone
            foot_bone = None
            for name_pattern in [f'{side}Foot']:
                if name_pattern in pose_bones:
                    foot_bone = pose_bones[name_pattern]
                    break

            if thigh_bone and shin_bone and foot_bone:
                print(f"  Found leg bones: thigh={thigh_bone.name}, shin={shin_bone.name}, foot={foot_bone.name}")

                # Find twist bone (between thigh and shin)
                thigh_twist = None
                for name_pattern in [f'{side}ThighTwist']:
                    if name_pattern in pose_bones:
                        thigh_twist = pose_bones[name_pattern]
                        break

                # Store bone references (include twist if found)
                self._analytical_leg_bones = {
                    'thigh': thigh_bone,
                    'thigh_twist': thigh_twist,  # May be None
                    'shin': shin_bone,
                    'foot': foot_bone
                }

                if thigh_twist:
                    print(f"  Found twist bone: {thigh_twist.name}")
                    print(f"  Hierarchy: {thigh_bone.name} → {thigh_twist.name} → {shin_bone.name}")

                # CRITICAL: Force depsgraph update before reading bone positions.
                # After hip move/rotate + edit-mode roundtrip, bone matrices may be stale.
                armature = self._drag_armature
                bpy.context.view_layer.update()
                depsgraph = bpy.context.evaluated_depsgraph_get()
                armature_eval = armature.evaluated_get(depsgraph)

                # Read positions from EVALUATED armature (includes hip location/rotation)
                thigh_eval = armature_eval.pose.bones[thigh_bone.name]
                shin_eval = armature_eval.pose.bones[shin_bone.name]
                foot_eval = armature_eval.pose.bones[foot_bone.name]

                # Calculate bone lengths
                # IMPORTANT: thigh_length is hip to knee (includes twist bone!)
                hip_world = armature.matrix_world @ Vector(thigh_eval.head)
                knee_world = armature.matrix_world @ Vector(shin_eval.head)
                ankle_world = armature.matrix_world @ Vector(shin_eval.tail)

                # Upper leg = hip to knee (thigh + twist combined)
                thigh_length = (knee_world - hip_world).length
                # Lower leg = knee to ankle
                shin_length = (ankle_world - knee_world).length

                self._analytical_leg_lengths = {
                    'thigh': thigh_length,
                    'shin': shin_length
                }
                print(f"  Bone lengths: upper_leg={thigh_length:.3f}m, lower_leg={shin_length:.3f}m")

                # Store hip position (fixed during drag) — use evaluated positions
                self._analytical_leg_hip_pos = armature.matrix_world @ Vector(thigh_eval.head)

                # Store original rotations for cancel/undo (include twist if present)
                self._analytical_leg_original_rotations = {
                    'thigh': thigh_bone.rotation_quaternion.copy(),
                    'shin': shin_bone.rotation_quaternion.copy(),
                    'foot': foot_bone.rotation_quaternion.copy()
                }
                if thigh_twist:
                    self._analytical_leg_original_rotations['thigh_twist'] = thigh_twist.rotation_quaternion.copy()

                # Ensure bones use quaternion mode (include twist if present)
                bones_to_convert = [thigh_bone, shin_bone, foot_bone]
                if thigh_twist:
                    bones_to_convert.append(thigh_twist)
                for bone in bones_to_convert:
                    bone.rotation_mode = 'QUATERNION'

                # Log bone transform state at drag start (diagnostic)
                for check_bone in [thigh_bone, shin_bone]:
                    if check_bone:
                        loc = check_bone.location
                        scl = check_bone.scale
                        if loc.length > 0.0001 or abs(scl.x - 1) > 0.001 or abs(scl.y - 1) > 0.001 or abs(scl.z - 1) > 0.001:
                            print(f"  ⚠️  {check_bone.name} has non-default loc=({loc.x:.4f},{loc.y:.4f},{loc.z:.4f}) scale=({scl.x:.4f},{scl.y:.4f},{scl.z:.4f})")

                # Calculate initial knee direction from current pose (evaluated positions)
                # This preserves the knee bend direction throughout the drag
                knee_world = armature.matrix_world @ Vector(shin_eval.head)
                hip_world = armature.matrix_world @ Vector(thigh_eval.head)
                foot_world = armature.matrix_world @ Vector(foot_eval.tail)

                # Knee direction = perpendicular to hip-foot line, toward current knee
                hip_to_foot = (foot_world - hip_world).normalized()
                hip_to_knee = (knee_world - hip_world)
                # Project hip_to_knee onto plane perpendicular to hip_to_foot
                knee_perp = hip_to_knee - (hip_to_knee.dot(hip_to_foot)) * hip_to_foot
                if knee_perp.length > 0.01:
                    self._analytical_leg_knee_axis = knee_perp.normalized()
                    print(f"  Knee axis from pose: {self._analytical_leg_knee_axis}")
                else:
                    # Leg is nearly straight, use forward direction
                    self._analytical_leg_knee_axis = Vector((0, -1, 0))
                    print(f"  Knee axis (default forward): {self._analytical_leg_knee_axis}")

                # Defer bend_normal calculation to the first frame of the solver.
                # After STEP 1 resets leg bones to identity + view_layer.update(),
                # thigh_bone.matrix reflects the parent chain (including hip rotation)
                # with identity thigh rotation. This gives the correct rest direction
                # in world space regardless of parent rotation.
                #
                # We CAN'T compute it here at drag start because:
                # - bone.bone.matrix_local doesn't include parent rotations (wrong at 90Y hip)
                # - bone.matrix includes the thigh's own pose (twist snap on re-drag)
                self._analytical_leg_bend_plane_normal = None  # Computed on first solver frame
                print(f"  Bend plane normal: deferred to first solver frame")

                # Shin bend axis: ALWAYS local X for a hinge joint
                # The knee is a hinge - it bends on one fixed axis in the bone's local space
                # For DAZ shin bones, positive X rotation = forward knee bend
                # No need to calculate from pose (that caused sign flips!)
                self._analytical_leg_shin_bend_axis = Vector((1, 0, 0))
                print(f"  Shin bend axis: (1, 0, 0) (anatomical hinge)")

                # Set up drag state
                self._use_analytical_leg_ik = True
                self._is_dragging = True

                # Store initial ANKLE position for delta-based drag.
                # CRITICAL: Must use shin_eval.tail (ankle), NOT foot_eval.tail (toe tip).
                # The solver targets shin_bone.tail (ankle), so the initial position must
                # match — otherwise the first frame has a ~7cm offset causing a "skip".
                self._drag_initial_target_pos = armature.matrix_world @ Vector(shin_eval.tail)

                # Store view info for 3D projection (cross-viewport safe)
                region, rv3d, mouse_local = self._get_region_rv3d(context, event)
                if not region or not rv3d:
                    print("  ⚠️  No valid viewport - cannot start analytical leg IK")
                    return
                self._drag_initial_mouse_pos = mouse_local
                self._drag_plane_normal = rv3d.view_rotation @ Vector((0, 0, -1))
                self._drag_depth_reference = self._drag_initial_target_pos.copy()

                # Store undo state for analytical leg bones (Ctrl+Z support)
                # NOTE: store_undo_state() uses _ik_daz_bone_names which is empty for
                # analytical leg drags, so we push directly to the undo stack here.
                frame = context.scene.frame_current
                bones_data = []
                for bone_key, bone in self._analytical_leg_bones.items():
                    if bone:
                        bones_data.append((bone.name, bone.rotation_quaternion.copy(), 'QUATERNION'))
                self._undo_stack.append({
                    'frame': frame,
                    'bones': bones_data,
                    'armature': armature
                })
                print(f"  Stored analytical leg undo state: {len(bones_data)} bones")

                # Clear debug trail for new drag
                self._analytical_leg_debug_trail = []

                # Mute translation pin if dragging a pinned bone (we're moving it).
                # Keep rotation pin ACTIVE — it maintains foot orientation during IK.
                if self._temp_unpinned_bone:
                    pose_bone = armature.pose.bones.get(self._temp_unpinned_bone)
                    if pose_bone:
                        for c in pose_bone.constraints:
                            if c.name == "DAZ_Pin_Translation" and not c.mute:
                                c.mute = True
                                print(f"  ✓ Muted pin constraint: {c.name} on {self._temp_unpinned_bone}")

                self._set_header(context,f"ANALYTICAL LEG IK: {self._drag_bone_name} | Release to apply")
                print("  ✓ Analytical leg IK mode activated")
                return  # Skip normal IK chain creation
            else:
                print(f"  ✗ Could not find all leg bones (thigh={thigh_bone}, shin={shin_bone}, foot={foot_bone})")
                print("  → Falling back to normal IK")

        # Check if this is a hand bone - use analytical arm IK
        is_arm_bone = 'hand' in bone_lower

        if is_arm_bone and not self._soft_pin_active:
            print("  → HAND BONE DETECTED: Using analytical arm IK (bypasses Blender's solver)")

            # Determine side (left or right)
            if bone_lower.startswith('l'):
                self._analytical_arm_side = 'l'
            elif bone_lower.startswith('r'):
                self._analytical_arm_side = 'r'
            else:
                self._analytical_arm_side = 'l' if 'left' in bone_lower else 'r'

            side = self._analytical_arm_side

            # Find arm bones (shoulder, forearm, hand)
            pose_bones = self._drag_armature.pose.bones

            # Find shoulder bone (upper arm)
            shoulder_bone = None
            for name_pattern in [f'{side}ShldrBend', f'{side}Shldr', f'{side}Shoulder']:
                if name_pattern in pose_bones:
                    shoulder_bone = pose_bones[name_pattern]
                    break

            # Find forearm bone
            forearm_bone = None
            for name_pattern in [f'{side}ForearmBend', f'{side}ForeArm', f'{side}Forearm']:
                if name_pattern in pose_bones:
                    forearm_bone = pose_bones[name_pattern]
                    break

            # Find hand bone
            hand_bone = None
            for name_pattern in [f'{side}Hand']:
                if name_pattern in pose_bones:
                    hand_bone = pose_bones[name_pattern]
                    break

            if shoulder_bone and forearm_bone and hand_bone:
                print(f"  Found arm bones: shoulder={shoulder_bone.name}, forearm={forearm_bone.name}, hand={hand_bone.name}")

                # Find collar bone (parent of shoulder in DAZ hierarchy)
                collar_bone = pose_bones.get(f'{side}Collar')

                # Find twist bones
                shoulder_twist = None
                for name_pattern in [f'{side}ShldrTwist']:
                    if name_pattern in pose_bones:
                        shoulder_twist = pose_bones[name_pattern]
                        break

                forearm_twist = None
                for name_pattern in [f'{side}ForearmTwist']:
                    if name_pattern in pose_bones:
                        forearm_twist = pose_bones[name_pattern]
                        break

                # Store bone references
                self._analytical_arm_bones = {
                    'collar': collar_bone,  # May be None
                    'shoulder': shoulder_bone,
                    'shoulder_twist': shoulder_twist,  # May be None
                    'forearm': forearm_bone,
                    'forearm_twist': forearm_twist,  # May be None
                    'hand': hand_bone
                }

                if collar_bone:
                    print(f"  Found collar: {collar_bone.name}")
                if shoulder_twist:
                    print(f"  Found shoulder twist: {shoulder_twist.name}")
                if forearm_twist:
                    print(f"  Found forearm twist: {forearm_twist.name}")

                # Force depsgraph update before reading bone positions
                armature = self._drag_armature
                bpy.context.view_layer.update()
                depsgraph = bpy.context.evaluated_depsgraph_get()
                armature_eval = armature.evaluated_get(depsgraph)

                # Read positions from EVALUATED armature
                shoulder_eval = armature_eval.pose.bones[shoulder_bone.name]
                forearm_eval = armature_eval.pose.bones[forearm_bone.name]

                # Calculate bone lengths
                shoulder_world = armature.matrix_world @ Vector(shoulder_eval.head)
                elbow_world = armature.matrix_world @ Vector(forearm_eval.head)
                wrist_world = armature.matrix_world @ Vector(forearm_eval.tail)

                upper_length = (elbow_world - shoulder_world).length
                lower_length = (wrist_world - elbow_world).length

                self._analytical_arm_lengths = {
                    'upper': upper_length,
                    'lower': lower_length
                }
                print(f"  Bone lengths: upper_arm={upper_length:.3f}m, forearm={lower_length:.3f}m")

                # Store shoulder position (fixed during drag)
                self._analytical_arm_shoulder_pos = shoulder_world.copy()

                # Store original rotations for cancel/undo
                self._analytical_arm_original_rotations = {
                    'shoulder': shoulder_bone.rotation_quaternion.copy(),
                    'forearm': forearm_bone.rotation_quaternion.copy(),
                    'hand': hand_bone.rotation_quaternion.copy()
                }
                if shoulder_twist:
                    self._analytical_arm_original_rotations['shoulder_twist'] = shoulder_twist.rotation_quaternion.copy()
                if forearm_twist:
                    self._analytical_arm_original_rotations['forearm_twist'] = forearm_twist.rotation_quaternion.copy()

                # Ensure bones use quaternion mode
                bones_to_convert = [shoulder_bone, forearm_bone, hand_bone]
                if shoulder_twist:
                    bones_to_convert.append(shoulder_twist)
                if forearm_twist:
                    bones_to_convert.append(forearm_twist)
                for bone in bones_to_convert:
                    bone.rotation_mode = 'QUATERNION'

                # Log non-default transforms
                for check_bone in [shoulder_bone, forearm_bone]:
                    if check_bone:
                        loc = check_bone.location
                        scl = check_bone.scale
                        if loc.length > 0.0001 or abs(scl.x - 1) > 0.001 or abs(scl.y - 1) > 0.001 or abs(scl.z - 1) > 0.001:
                            print(f"  ⚠️  {check_bone.name} has non-default loc=({loc.x:.4f},{loc.y:.4f},{loc.z:.4f}) scale=({scl.x:.4f},{scl.y:.4f},{scl.z:.4f})")

                # Defer bend_normal to first solver frame (same pattern as leg)
                self._analytical_arm_bend_plane_normal = None
                print(f"  Bend plane normal: deferred to first solver frame")

                # Set up drag state
                self._use_analytical_arm_ik = True
                self._is_dragging = True

                # Store initial WRIST position for delta-based drag
                # Must use forearm_eval.tail (wrist), analogous to shin_eval.tail (ankle)
                self._drag_initial_target_pos = armature.matrix_world @ Vector(forearm_eval.tail)

                # Store view info for 3D projection
                region, rv3d, mouse_local = self._get_region_rv3d(context, event)
                if not region or not rv3d:
                    print("  ⚠️  No valid viewport - cannot start analytical arm IK")
                    return
                self._drag_initial_mouse_pos = mouse_local
                self._drag_plane_normal = rv3d.view_rotation @ Vector((0, 0, -1))
                self._drag_depth_reference = self._drag_initial_target_pos.copy()

                # Store undo state
                frame = context.scene.frame_current
                bones_data = []
                for bone_key, bone in self._analytical_arm_bones.items():
                    if bone:
                        bones_data.append((bone.name, bone.rotation_quaternion.copy(), 'QUATERNION'))
                self._undo_stack.append({
                    'frame': frame,
                    'bones': bones_data,
                    'armature': armature
                })
                print(f"  Stored analytical arm undo state: {len(bones_data)} bones")

                # Clear debug trail
                self._analytical_arm_debug_trail = []

                # Mute translation pin if dragging a pinned bone (we're moving it).
                # Keep rotation pin ACTIVE — it maintains hand orientation during IK.
                if self._temp_unpinned_bone:
                    pose_bone = armature.pose.bones.get(self._temp_unpinned_bone)
                    if pose_bone:
                        for c in pose_bone.constraints:
                            if c.name == "DAZ_Pin_Translation" and not c.mute:
                                c.mute = True
                                print(f"  ✓ Muted pin constraint: {c.name} on {self._temp_unpinned_bone}")

                self._set_header(context,f"ANALYTICAL ARM IK: {self._drag_bone_name} | Release to apply")
                print("  ✓ Analytical arm IK mode activated")
                return  # Skip normal IK chain creation
            else:
                print(f"  ✗ Could not find all arm bones (shoulder={shoulder_bone}, forearm={forearm_bone}, hand={hand_bone})")
                print("  → Falling back to normal IK")

        # Continue with normal IK path (now with soft pin support)
        # Create IK chain with temp bones (bypasses twist bones for clean IK)
        # Pass the bone to ignore pin checks on if dragging a pinned bone
        # Pin constraints will be temporarily muted for directly dragged bone
        result = create_ik_chain(
            self._drag_armature,
            self._drag_bone_name,
            chain_length=None,  # Auto-detect (same behavior as unpinned)
            ignore_pin_on_bone=self._temp_unpinned_bone,  # Temporarily disable pin on dragged bone
            soft_pin_mode=self._soft_pin_active  # Soft pin mode: skip hard pin on .ik bone
        )

        # Check if IK chain creation succeeded
        if not result or result[0] is None:
            print("  ✗ Failed to create IK chain")
            return

        # Unpack the 7 return values from create_ik_chain
        target_bone_name, ik_control_names, daz_bone_names, shoulder_target_names, leg_prebend_applied, swing_twist_pairs, is_leg_chain = result

        # Store bone names and pre-bend status
        self._ik_target_bone_name = target_bone_name
        self._ik_control_bone_names = ik_control_names
        self._ik_daz_bone_names = daz_bone_names
        self._shoulder_target_names = shoulder_target_names  # For collar Damped Track
        self._leg_prebend_applied = leg_prebend_applied  # Track if leg was in rest pose
        self._swing_twist_pairs = swing_twist_pairs  # Bend/twist bone pairs for manual decomposition
        self._is_leg_chain = is_leg_chain  # Legs get full range, arms get protection

        # Store undo state NOW — before IK solving modifies any rotations
        # This captures the pre-drag bone positions so undo restores correctly
        self.store_undo_state(context)

        # CRITICAL: In soft pin mode, track pinned child for pin location update on release
        # This must happen AFTER create_ik_chain so the pinned child is included in the chain
        if self._soft_pin_active and self._soft_pin_child_name:
            self._temp_unpinned_bone = self._soft_pin_child_name
            print(f"  Tracking {self._soft_pin_child_name} for pin location update on release")

        # Store view direction for depth calculation
        region, rv3d, _ = self._get_region_rv3d(context, event)
        if not region or not rv3d:
            print("  ⚠️  No valid viewport - cannot start IK drag")
            return

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

        # CRITICAL: Store initial mouse position for delta calculation (region-local coords)
        # _mouse_down_pos is in absolute coords, convert to region-local
        if self._mouse_down_pos:
            self._drag_initial_mouse_pos = (
                self._mouse_down_pos[0] - region.x,
                self._mouse_down_pos[1] - region.y
            )
        else:
            # Fallback: use _get_region_rv3d local coords
            _, _, local_mouse = self._get_region_rv3d(context, event)
            self._drag_initial_mouse_pos = local_mouse

        # Reset debug flag for this drag
        self._debug_printed = False

        # Mouse-direction pre-bend: track first mouse moves to determine bend direction
        self._pre_bend_mouse_samples = []  # Store first 2-3 mouse positions
        self._pre_bend_applied = False     # Track if we've applied the pre-bend yet
        self._pre_bend_accumulated_distance = 0.0  # Track cumulative 3D movement for slow drags

        print(f"  Initial mouse pos stored: {self._drag_initial_mouse_pos}")
        print(f"  Initial target pos stored: {self._drag_initial_target_pos}")

        # Ensure we're in pose mode after creating temp bones
        if context.mode != 'POSE':
            print(f"  WARNING: Not in POSE mode after bone creation! Mode: {context.mode}")
            bpy.ops.object.mode_set(mode='POSE')

        # Enter drag mode
        self._is_dragging = True

        # Update header
        self._set_header(context,f"IK DRAGGING: {self._drag_bone_name} | Release to bake pose")

    def update_ik_drag(self, context, event):
        """Update IK target position during drag - uses Blender's built-in 2D-to-3D conversion"""
        debug_print(f"  update_ik_drag called: is_dragging={self._is_dragging}")

        if not self._is_dragging or not self._ik_target_bone_name:
            debug_print(f"  update_ik_drag EARLY RETURN: target={self._ik_target_bone_name}")
            return

        try:
            debug_print(f"  Updating IK drag (mouse: {event.mouse_region_x}, {event.mouse_region_y})")

            # Get target bone
            target_bone = self._drag_armature.pose.bones[self._ik_target_bone_name]
        except Exception as e:
            print(f"  ERROR in update_ik_drag: {e}")
            import traceback
            traceback.print_exc()
            return

        # Use Blender's built-in region_2d_to_location_3d with delta-based movement
        region, rv3d, mouse_pos = self._get_region_rv3d(context, event)
        if not region or not rv3d:
            return

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
        # Even if tip is pinned, target should follow mouse to create tension in IK
        # The Copy Location constraint on the tip will keep it pinned
        new_world_location = self._drag_initial_target_pos + mouse_delta

        # Debug first update only (flag resets each drag)
        if not self._debug_printed:
            self._debug_printed = True
            print(f"  First drag update: mouse {mouse_pos}, delta {mouse_delta.length:.3f}m")

        # POLE TARGET SYSTEM: Use pole target to control elbow direction
        # Hand stays at pin (IK target), elbow bends toward mouse (pole target)
        if self._soft_pin_active and self._soft_pin_child_name:
            print(f"  [POLE] Running pole target adjustment (fulcrum={self._soft_pin_child_name})")
            try:
                # Get the pinned hand position (fulcrum - fixed point)
                hand_pos = self._soft_pin_initial_pos  # Use initial pin position (fixed)
                print(f"  [POLE] Hand (fulcrum) at: {hand_pos}")

                # Get current mouse position in 3D (where elbow should point)
                mouse_3d = current_mouse_3d
                print(f"  [POLE] Mouse (pole target) at: {mouse_3d}")

                # STANDARD IK POLE TARGET APPROACH (matching working test rig):
                # 1. IK target stays FIXED at pinned hand position
                # 2. Pole target positioned EXACTLY at mouse (no offset)
                # 3. Elbow rotates to point toward pole target while hand stays pinned

                # IK target locked at pinned hand position (no movement)
                new_world_location = hand_pos
                print(f"  [POLE] IK target locked at pin: {new_world_location}")

                # Pole target positioned exactly at mouse (standard IK rig behavior)
                self._pole_target_pos = mouse_3d
                print(f"  [POLE] Pole target exactly at mouse: {self._pole_target_pos}")

            except Exception as e:
                print(f"  [POLE ERROR]: {e}")
                import traceback
                traceback.print_exc()

        # Convert world location to armature local space
        desired_armature_space = self._drag_armature.matrix_world.inverted() @ new_world_location

        # DIRECT APPROACH: Set the bone's matrix to place its head at desired position
        # For a parentless bone, we can construct a translation matrix

        # Create a translation matrix that places the bone's head at desired position
        rest_head = Vector(target_bone.bone.head_local)
        rest_tail = Vector(target_bone.bone.tail_local)
        bone_vector = rest_tail - rest_head

        # Build matrix: translation to move head to desired position
        translation = desired_armature_space - rest_head
        mat = Matrix.Translation(translation)

        # CRITICAL: Don't move the target until pre-bend/reinforcement has been applied.
        # If IK is already active (from create_ik_chain) and we jump the target before
        # the pre-bend locks in the bend direction, the solver may flip to a straight-arm
        # solution. This causes the "second drag snap to full extension" bug.
        # On the first few mouse events, pre-bend collects samples and then applies.
        # Once _pre_bend_applied is True, target moves normally on every subsequent event.
        if self._pre_bend_applied:
            # Set the bone's matrix directly
            target_bone.matrix = mat @ target_bone.bone.matrix_local

            # CRITICAL: Update FIRST to ensure target is at new position
            # This prevents IK from solving to the old target position
            context.view_layer.update()

        # POLE TARGET: Update pole target position during drag
        # Soft pin mode: pole follows mouse exactly
        # Normal mode: pole moves to encourage natural elbow bend based on drag direction
        if self._soft_pin_active and self._soft_pin_child_name and hasattr(self, '_pole_target_pos'):
            try:
                pole_target_name = self._ik_target_bone_name + ".pole"
                pole_target_bone = self._drag_armature.pose.bones.get(pole_target_name)

                if pole_target_bone:
                    # Convert pole target position to armature local space
                    pole_armature_space = self._drag_armature.matrix_world.inverted() @ self._pole_target_pos
                    rest_head = Vector(pole_target_bone.bone.head_local)
                    translation = pole_armature_space - rest_head
                    pole_target_bone.matrix = Matrix.Translation(translation) @ pole_target_bone.bone.matrix_local
                    print(f"  [POLE] Updated pole target at: {self._pole_target_pos}")
                else:
                    print(f"  [POLE] Warning: Pole target bone not found: {pole_target_name}")
            except Exception as e:
                print(f"  [POLE] Error updating pole target: {e}")
        # else:
            # Normal drag mode: pole is now PARENTED to forearm/shin .ik bone
            # No dynamic updates needed - the parenting handles rotation automatically
            # The pole swings with the limb, maintaining its local relationship

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

        # MOUSE-DIRECTION PRE-BEND: Collect mouse samples before activating IK
        # This seeds the solver with the intended bend direction
        ik_tip_bone = self._drag_armature.pose.bones[self._ik_control_bone_names[-1]]
        ik_constraint = None
        for constraint in ik_tip_bone.constraints:
            if constraint.name == "IK_Temp":
                ik_constraint = constraint
                break

        if not ik_constraint:
            return

        # FAST PATH: If limb is already bent (second+ drag), activate IK immediately.
        # Pre-bend exists to seed the solver direction for STRAIGHT limbs.
        # Already-bent limbs don't need seeding in the same direction,
        # BUT may need reverse prebend if dragging to straighten.
        if not self._pre_bend_applied:
            import math as _math
            for _bn in self._ik_control_bone_names:
                _bn_lower = _bn.lower()
                if any(p in _bn_lower for p in ['forearm', 'shin', 'calf', 'abdomen', 'spine']):
                    _mid = self._drag_armature.pose.bones.get(_bn)
                    if _mid:
                        _q = _mid.rotation_quaternion
                        _angle = 2 * _math.acos(min(abs(_q.w), 1.0))
                        if _angle > 0.087:  # > 5°
                            print(f"  [PRE-BEND] {_bn} already bent ({_math.degrees(_angle):.1f}°) — activating IK")

                            # Don't mark pre-bend as applied yet - let the normal path handle reverse prebend
                            # Just activate IK and Copy Rotation
                            ik_constraint.influence = 1.0
                            context.view_layer.update()
                            for daz_name in self._ik_daz_bone_names:
                                daz_bone = self._drag_armature.pose.bones[daz_name]
                                for constraint in daz_bone.constraints:
                                    if constraint.name == "IK_CopyRot_Temp":
                                        constraint.influence = 1.0
                            context.view_layer.update()
                            # DON'T set self._pre_bend_applied = True - let normal path check direction
                            break

        # Collect first 2-3 mouse positions to determine direction
        if not self._pre_bend_applied and len(self._pre_bend_mouse_samples) < 10:  # Allow more samples for slow movements
            pb_region, pb_rv3d, pb_mouse = self._get_region_rv3d(context, event)
            if not pb_region or not pb_rv3d:
                return
            current_mouse_3d = view3d_utils.region_2d_to_location_3d(
                pb_region,
                pb_rv3d,
                pb_mouse,
                self._drag_depth_reference
            )

            # Accumulate distance from previous sample
            if len(self._pre_bend_mouse_samples) > 0:
                prev_sample = self._pre_bend_mouse_samples[-1]
                movement = (current_mouse_3d - prev_sample).length
                self._pre_bend_accumulated_distance += movement

            self._pre_bend_mouse_samples.append(current_mouse_3d.copy())
            debug_print(f"  [PRE-BEND] Sample {len(self._pre_bend_mouse_samples)}: accumulated={self._pre_bend_accumulated_distance:.4f}m")

        # After collecting samples, apply pre-bend and activate IK
        if not self._pre_bend_applied and len(self._pre_bend_mouse_samples) >= 2:
            # Calculate mouse movement direction
            mouse_start = self._pre_bend_mouse_samples[0]
            mouse_current = self._pre_bend_mouse_samples[-1]
            mouse_delta = mouse_current - mouse_start

            # CRITICAL: Require minimum movement before activating IK/Copy Rotation
            # This prevents snap when user barely moves the mouse
            # Check BOTH direct distance AND accumulated distance (for slow, steady movements)
            MIN_MOVEMENT_THRESHOLD = 0.003  # 3mm minimum movement (balance between precision and snap prevention)

            # Check both direct distance and accumulated distance
            direct_distance = mouse_delta.length
            accumulated_distance = self._pre_bend_accumulated_distance

            if direct_distance < MIN_MOVEMENT_THRESHOLD and accumulated_distance < MIN_MOVEMENT_THRESHOLD:
                # Not enough movement yet - keep collecting samples
                print(f"  [PRE-BEND] Waiting for movement (direct: {direct_distance:.4f}m, accumulated: {accumulated_distance:.4f}m < {MIN_MOVEMENT_THRESHOLD}m)")
                return  # Exit early, don't activate IK yet

            # Use direct delta for direction (better represents intended direction than accumulated path)
            mouse_direction = mouse_delta.normalized()
            print(f"  [PRE-BEND] Movement threshold reached! Direction: {mouse_direction} (direct: {direct_distance:.4f}m, accumulated: {accumulated_distance:.4f}m)")

            # Find the middle joint to pre-bend (forearm, shin, or spine)
            middle_bone = None
            bend_axis = Vector((0, 1, 0))  # Default axis
            bend_magnitude = 0.03  # 1.7° default

            for i, bone_name in enumerate(self._ik_control_bone_names):
                bone_name_lower = bone_name.lower()

                # Find shin/calf (legs)
                if 'shin' in bone_name_lower or 'calf' in bone_name_lower:
                    middle_bone = self._drag_armature.pose.bones[bone_name]
                    bend_axis = Vector((1, 0, 0))  # X axis for knee
                    bend_magnitude = 0.20  # ~11.5° for legs (stronger nudge to escape bent local minimum)
                    break
                # Find forearm (arms)
                elif 'forearm' in bone_name_lower:
                    middle_bone = self._drag_armature.pose.bones[bone_name]
                    # Elbow flexion is primarily around X axis (pitch)
                    # Use X axis for forward/backward (Y) and up/down (Z) movements
                    # Only use Z axis for pure lateral (X) movements
                    if abs(mouse_direction.x) > abs(mouse_direction.y) and abs(mouse_direction.x) > abs(mouse_direction.z):
                        bend_axis = Vector((0, 0, 1))  # Pure lateral motion - twist
                    else:
                        bend_axis = Vector((1, 0, 0))  # Forward/up/down motion - flex elbow
                    bend_magnitude = 0.15  # ~8.6° for arms (increased for better IK seeding)
                    break
                # Find abdomen/spine (torso)
                elif 'abdomen' in bone_name_lower or 'spine' in bone_name_lower:
                    middle_bone = self._drag_armature.pose.bones[bone_name]
                    bend_axis = Vector((1, 0, 0))
                    bend_magnitude = 0.03  # ~1.7° for torso
                    break

            # SMART PRE-BEND: Arms = protect bent pose, Legs = full range (can straighten)
            # Source: Grok analysis - arms need protection, legs need freedom
            import math
            skip_prebend_for_bent_limb = False

            if middle_bone:
                # Check if joint is already rotated from rest pose
                quat = middle_bone.rotation_quaternion
                quat_angle = 2 * math.acos(min(abs(quat.w), 1.0))

                # ARMS ONLY: Skip prebend if already bent (protects existing pose)
                # LEGS: Never skip - they need full freedom to both bend AND straighten
                is_arm = 'forearm' in middle_bone.name.lower()

                if is_arm and quat_angle > 0.35:  # ~20° threshold for arms
                    skip_prebend_for_bent_limb = True
                    print(f"  [PRE-BEND] ARM SKIP — already bent {math.degrees(quat_angle):.1f}°")
                elif not is_arm:
                    # Leg - always allow full range
                    print(f"  [PRE-BEND] LEG full-range (current bend: {math.degrees(quat_angle):.1f}°)")

            if middle_bone and mouse_delta.length > 0.001 and not skip_prebend_for_bent_limb:
                # Determine direction (positive or negative rotation) based on joint type
                bend_sign = 1.0
                is_leg = 'shin' in middle_bone.name.lower() or 'calf' in middle_bone.name.lower()

                # For LEGS (shin/knee): Use Y direction for bend/straighten
                # In Blender: -Y is FORWARD (toward character's face), +Y is BACKWARD
                # Dragging foot forward (-Y) = knee bends = positive rotation
                if is_leg:
                    # Check current bend angle
                    quat = middle_bone.rotation_quaternion
                    current_bend = 2 * math.acos(min(abs(quat.w), 1.0))
                    is_straightening = mouse_direction.y > 0.2 or mouse_direction.z < -0.5

                    if is_straightening and current_bend > 0.35:  # >20° and trying to straighten
                        # RESET TO STRAIGHT: Give IK solver a clean starting point
                        print(f"  [STRAIGHTEN] Resetting leg chain to near-straight for clean IK solve")

                        # Reset ALL bones in chain toward identity (straight)
                        identity = Quaternion((1, 0, 0, 0))
                        for bone_name in self._ik_control_bone_names[:-1]:  # Exclude tip (foot)
                            bone = self._drag_armature.pose.bones.get(bone_name)
                            if bone:
                                old_angle = 2 * math.acos(min(abs(bone.rotation_quaternion.w), 1.0))
                                # Slerp 90% toward identity (nearly straight, small hint remaining)
                                bone.rotation_quaternion = bone.rotation_quaternion.slerp(identity, 0.90)
                                new_angle = 2 * math.acos(min(abs(bone.rotation_quaternion.w), 1.0))
                                print(f"    {bone_name}: {math.degrees(old_angle):.1f}° → {math.degrees(new_angle):.1f}°")

                        # CRITICAL: Temporarily LOCK shin IK to prevent re-bending
                        # Set max bend angle to near-zero so IK solver CAN'T bend the knee
                        if middle_bone.use_ik_limit_x:
                            self._straighten_original_ik_max_x = middle_bone.ik_max_x
                            middle_bone.ik_max_x = 0.1  # ~6° max - nearly locked straight
                            print(f"  [STRAIGHTEN] Locked shin IK max to {math.degrees(0.1):.1f}° (was {math.degrees(self._straighten_original_ik_max_x):.1f}°)")
                            self._straighten_lock_active = True

                        # Strong straightening prebend
                        bend_sign = -1.0
                        bend_magnitude = 0.8  # ~46° - recommended by docs

                    elif mouse_direction.y < 0:  # Moving forward (away from body, -Y in Blender)
                        bend_sign = 1.0  # Bend knee forward (natural direction)
                    else:  # Moving backward (toward body, +Y in Blender)
                        bend_sign = -1.0  # Knee extends/straightens
                # For ARMS (forearm/elbow): Check Z (up/down) and Y (forward/back) directions
                # In Blender: -Y is FORWARD, +Z is UP
                elif 'forearm' in middle_bone.name.lower():
                    # Primary: Check Y direction for forward reaching (most common case)
                    if abs(mouse_direction.y) > abs(mouse_direction.z):
                        # Forward/backward movement dominates
                        if mouse_direction.y < 0:  # Reaching forward (-Y)
                            bend_sign = 1.0  # Bend elbow (arm curls inward)
                        else:  # Moving backward (+Y)
                            bend_sign = -1.0  # Straighten elbow
                    else:
                        # Up/down movement dominates
                        if mouse_direction.z < 0:  # Moving down
                            bend_sign = -1.0
                        else:  # Moving up
                            bend_sign = 1.0
                # For TORSO: Check Z direction (forward/back lean)
                else:
                    if mouse_direction.z < 0:  # Moving down/back
                        bend_sign = -1.0
                    else:  # Moving up/forward
                        bend_sign = 1.0

                nudge_quat = Quaternion(bend_axis, bend_magnitude * bend_sign)
                middle_bone.rotation_quaternion = nudge_quat @ middle_bone.rotation_quaternion
                print(f"  [PRE-BEND] Applied {bend_magnitude * bend_sign:.3f} rad to {middle_bone.name} on axis {bend_axis}")

            self._pre_bend_applied = True

            # Reset mouse reference so next frame's delta is tiny (one frame of movement).
            # Without this, the next frame would compute the full accumulated delta from
            # drag start, causing a large target jump that flips the IK solver.
            # The target stays at its initial position — no catch-up, no jump.
            _, _, reset_mouse_local = self._get_region_rv3d(context, event)
            self._drag_initial_mouse_pos = reset_mouse_local

            # NOW activate IK constraint
            ik_constraint.influence = 1.0

            # CRITICAL: Update scene to let IK solve BEFORE activating Copy Rotation
            # This ensures .ik bones are in their IK-solved position, not just pre-bent
            # Without this, Copy Rotation copies pre-bent positions before IK has solved
            # NOTE: Target hasn't moved yet — solver stabilizes at current pose
            context.view_layer.update()

            # Log key bone positions at IK activation (helpful for snap debugging)
            mouse_2d = reset_mouse_local
            target_pos = self._drag_armature.pose.bones[self._ik_target_bone_name].head
            print(f"  [IK ACTIVATED] mouse={mouse_2d} target={target_pos.x:.3f},{target_pos.y:.3f},{target_pos.z:.3f}")

            # Activate Copy Rotation constraints IMMEDIATELY
            # The IK has already solved, so we need full influence for bones to follow
            for daz_name in self._ik_daz_bone_names:
                daz_bone = self._drag_armature.pose.bones[daz_name]
                for constraint in daz_bone.constraints:
                    if constraint.name == "IK_CopyRot_Temp":
                        constraint.influence = 1.0
            debug_print(f"  Copy Rotation constraints activated (full influence)")
        else:
            # IK not activated yet - don't activate Copy Rotation (prevents snap on first mouse move)
            if not hasattr(self, '_copy_rot_wait_logged'):
                debug_print(f"  Waiting for IK activation before enabling Copy Rotation...")
                self._copy_rot_wait_logged = True

        # DON'T activate Damped Track on first frame - let IK solve naturally first
        # This prevents the initial inward snap by giving IK time to position the arm
        # Damped Track will activate on subsequent frames automatically (if needed later)

        # Final update to trigger IK solving with new target position
        context.view_layer.update()

        # POST-PROCESS: Swing/twist decomposition for bend bones
        # After IK solves, .ik bones have combined swing+twist rotation.
        # We decompose this and set: bend bone = swing only, twist bone = twist only.
        # This respects the DAZ Bend/Twist bone architecture.
        if self._pre_bend_applied and hasattr(self, '_swing_twist_pairs') and self._swing_twist_pairs:
            import math as _math
            depsgraph = context.evaluated_depsgraph_get()
            armature_eval = self._drag_armature.evaluated_get(depsgraph)

            for ik_name, daz_bend_name, daz_twist_name in self._swing_twist_pairs:
                ik_bone_eval = armature_eval.pose.bones.get(ik_name)
                daz_bend = self._drag_armature.pose.bones.get(daz_bend_name)
                if not ik_bone_eval or not daz_bend:
                    print(f"  [SWING/TWIST] SKIP {daz_bend_name}: ik={ik_bone_eval is not None}, daz={daz_bend is not None}")
                    continue

                # Compute local rotation needed for DAZ bone to match .ik bone's orientation
                if daz_bend.parent:
                    parent_eval = armature_eval.pose.bones[daz_bend.parent.name]
                    rest_offset = daz_bend.parent.bone.matrix_local.inverted() @ daz_bend.bone.matrix_local
                    matrix_basis = rest_offset.inverted() @ parent_eval.matrix.inverted() @ ik_bone_eval.matrix
                else:
                    matrix_basis = daz_bend.bone.matrix_local.inverted() @ ik_bone_eval.matrix

                loc, rot, scale = matrix_basis.decompose()
                swing, twist = decompose_swing_twist(rot, 'Y')

                swing_angle = 2 * _math.acos(min(abs(swing.w), 1.0))
                twist_angle = 2 * _math.acos(min(abs(twist.w), 1.0))
                print(f"  [SWING/TWIST] {daz_bend_name}: swing={_math.degrees(swing_angle):.1f}° twist={_math.degrees(twist_angle):.1f}° → {daz_twist_name} (mode={daz_bend.rotation_mode})")

                # Set bend bone to swing only (no twist)
                if daz_bend.rotation_mode == 'QUATERNION':
                    daz_bend.rotation_quaternion = swing
                else:
                    daz_bend.rotation_euler = swing.to_euler(daz_bend.rotation_mode)

                # DON'T set twist bone — preserve user's manual rotation.
                # The decomposed twist is an IK artifact (from .ik chain skipping twist bones),
                # not intentional rotation. Twist bones are user-controlled only.

                # Update between pairs so next bone's parent matrix is current
                context.view_layer.update()
                depsgraph = context.evaluated_depsgraph_get()
                armature_eval = self._drag_armature.evaluated_get(depsgraph)

    def update_fabrik_drag(self, context, event):
        """Update FABRIK solver during drag (prototype)"""
        print(f"\n[FABRIK] update_fabrik_drag called")

        if not self._is_dragging or not self._use_fabrik:
            print(f"  [FABRIK] EARLY RETURN: is_dragging={self._is_dragging}, use_fabrik={self._use_fabrik}")
            return

        try:
            # Get mouse position in 3D world space (cross-viewport safe)
            region, rv3d, mouse_2d = self._get_region_rv3d(context, event)
            if not region or not rv3d:
                return

            # Use dragged bone's current position as depth reference
            dragged_bone = self._drag_armature.pose.bones[self._drag_bone_name]
            dragged_world_pos = self._drag_armature.matrix_world @ dragged_bone.head

            mouse_3d = view3d_utils.region_2d_to_location_3d(
                region,
                rv3d,
                mouse_2d,
                dragged_world_pos
            )

            print(f"  [FABRIK] Mouse 2D: {mouse_2d}")
            print(f"  [FABRIK] Mouse 3D: {mouse_3d}")

            # Call FABRIK solver
            result = apply_fabrik_to_limb(
                armature=self._drag_armature,
                bone_chain=self._fabrik_chain,
                pinned_bone_name=self._fabrik_pinned_bone,
                dragged_bone_name=self._drag_bone_name,
                mouse_target_pos=mouse_3d
            )

            if not result['success']:
                print(f"  [FABRIK] ✗ FABRIK solve failed")
                return

            # Apply rotations to bones
            rotations = result['rotations']
            for bone_name, rotation_quat in rotations.items():
                pose_bone = self._drag_armature.pose.bones[bone_name]

                # Check bone state BEFORE applying rotation
                print(f"  [FABRIK] Bone: {bone_name}")
                print(f"    Rotation mode: {pose_bone.rotation_mode}")
                print(f"    Constraints: {[c.name for c in pose_bone.constraints]}")
                print(f"    Lock rotation: {pose_bone.lock_rotation}")

                # Store original rotation for undo
                if not hasattr(self, '_fabrik_original_rotations'):
                    self._fabrik_original_rotations = {}
                if bone_name not in self._fabrik_original_rotations:
                    self._fabrik_original_rotations[bone_name] = pose_bone.rotation_quaternion.copy()

                # Get position BEFORE rotation
                pos_before = (self._drag_armature.matrix_world @ pose_bone.matrix).translation

                # Force quaternion mode if not already
                if pose_bone.rotation_mode != 'QUATERNION':
                    print(f"    ⚠️  Switching to QUATERNION mode")
                    pose_bone.rotation_mode = 'QUATERNION'

                # Disable rotation limit constraints temporarily (they block FABRIK)
                for constraint in pose_bone.constraints:
                    if constraint.type == 'LIMIT_ROTATION' and not constraint.mute:
                        constraint.mute = True
                        print(f"    ⚠️  Muted Limit Rotation constraint")

                # Apply FABRIK rotation
                pose_bone.rotation_quaternion = rotation_quat
                print(f"    Applied rotation: {rotation_quat}")

                # Force update and check position AFTER
                context.view_layer.update()
                pos_after = (self._drag_armature.matrix_world @ pose_bone.matrix).translation
                print(f"  [FABRIK]   Position before: {pos_before}")
                print(f"  [FABRIK]   Position after:  {pos_after}")
                print(f"  [FABRIK]   Delta: {(pos_after - pos_before).length:.6f}")

            # Update viewport
            if context.area: context.area.tag_redraw()

            print(f"  [FABRIK] ✓ Rotations applied")

        except Exception as e:
            print(f"  [FABRIK] ERROR: {e}")
            import traceback
            traceback.print_exc()

    def update_analytical_leg_drag(self, context, event):
        """Update analytical two-bone IK for leg during drag.

        Bypasses Blender's IK solver completely - calculates exact rotations
        using law of cosines. No local minima, handles straightening correctly.

        Bone roles (DAZ Genesis 8/9):
        - ThighBend: X/Z rotation at hip to POINT the knee in a direction
        - ThighTwist: Y rotation (roll around thigh) to orient the bend plane
        - Shin: X rotation (hinge joint) for knee bend angle
        """
        if not self._is_dragging or not self._use_analytical_leg_ik:
            return

        try:
            # Get mouse position and convert to 3D (cross-viewport safe)
            region, rv3d, mouse_pos = self._get_region_rv3d(context, event)
            if not region or not rv3d:
                return

            # Calculate mouse delta from initial position
            if self._drag_initial_mouse_pos:
                mouse_delta = (
                    mouse_pos[0] - self._drag_initial_mouse_pos[0],
                    mouse_pos[1] - self._drag_initial_mouse_pos[1]
                )
            else:
                mouse_delta = (0, 0)

            # Dead zone: don't update until mouse has moved enough
            # This prevents the jump at drag start (our recalculated pose won't exactly
            # match the original) and the snap-to-straight near rest pose
            mouse_dist = math.sqrt(mouse_delta[0]**2 + mouse_delta[1]**2)
            if mouse_dist < 3.0:  # 3 pixels dead zone
                return

            # Convert mouse DELTA to 3D target position
            from bpy_extras.view3d_utils import region_2d_to_location_3d, location_3d_to_region_2d

            initial_foot_pos = self._drag_initial_target_pos
            initial_foot_screen = location_3d_to_region_2d(region, rv3d, initial_foot_pos)

            if initial_foot_screen:
                target_screen = (
                    initial_foot_screen[0] + mouse_delta[0],
                    initial_foot_screen[1] + mouse_delta[1]
                )
                target_pos = region_2d_to_location_3d(
                    region, rv3d,
                    target_screen,
                    initial_foot_pos
                )
            else:
                target_pos = initial_foot_pos

            # Get stored values
            hip_pos = self._analytical_leg_hip_pos
            thigh_length = self._analytical_leg_lengths['thigh']
            shin_length = self._analytical_leg_lengths['shin']
            armature = self._drag_armature

            # Get bone references
            thigh_bone = self._analytical_leg_bones['thigh']
            thigh_twist = self._analytical_leg_bones.get('thigh_twist')
            shin_bone = self._analytical_leg_bones['shin']

            # === STEP 1: Reset all leg bones to full identity (rest pose) ===
            # This ensures we calculate rotations from a clean slate each frame.
            # CRITICAL: Reset location and scale too — DAZ imports may have non-zero
            # values that corrupt the rest_world -> rotation_quaternion conversion.
            for reset_bone in [thigh_bone, thigh_twist, shin_bone]:
                if reset_bone:
                    reset_bone.rotation_quaternion = Quaternion()
                    reset_bone.location = Vector((0, 0, 0))
                    reset_bone.scale = Vector((1, 1, 1))
            context.view_layer.update()

            # === STEP 2: Calculate geometry ===
            hip_to_target = target_pos - hip_pos
            distance = hip_to_target.length
            max_reach = thigh_length + shin_length
            min_reach = abs(thigh_length - shin_length) * 0.1

            # Debug counter
            if not hasattr(self, '_debug_frame'):
                self._debug_frame = 0
            self._debug_frame += 1

            # Get the locked bend plane normal (perpendicular to leg bend plane).
            # On the FIRST frame, compute from thigh_bone.matrix (after STEP 1 identity
            # reset). This captures the parent chain (hip rotation) but not the thigh's
            # own rotation — stable across re-drags AND correct with rotated hips.
            bend_normal = self._analytical_leg_bend_plane_normal
            if bend_normal is None:
                # Use the bone's own X-axis as bend_normal.  After STEP 1 resets
                # the thigh to identity, bone.matrix reflects the parent chain
                # (hip rotation) with identity thigh rotation.  The X-axis of
                # this matrix IS the knee's lateral axis — it already encodes
                # the correct bend plane for ANY parent rotation, with no cross-
                # product and no degenerate cases.
                thigh_world_mat_rest = (armature.matrix_world @ thigh_bone.matrix).to_3x3().normalized()
                bend_normal = Vector(thigh_world_mat_rest.col[0]).normalized()

                # Flip so knee bends FORWARD: a positive hip_angle rotation
                # around bend_normal should move the thigh direction (Y-axis)
                # toward the bone's -Z (forward).  Check with a tiny rotation.
                thigh_y = Vector(thigh_world_mat_rest.col[1]).normalized()
                bone_z = Vector(thigh_world_mat_rest.col[2]).normalized()
                test_dir = Quaternion(bend_normal, 0.01) @ thigh_y
                if test_dir.dot(bone_z) > thigh_y.dot(bone_z):
                    # Rotation moved toward +Z (backward) — wrong direction
                    bend_normal = -bend_normal

                self._analytical_leg_bend_plane_normal = bend_normal
                print(f"  Bend plane normal (from bone X-axis): {bend_normal}")

            target_dir = hip_to_target.normalized()

            # Handle edge cases - but ALWAYS use bend plane for smooth transitions
            if distance <= min_reach:
                # Too close - skip this frame
                return
            if distance >= max_reach:
                # Beyond reach — clamp to 99.5% to avoid full lockout snap.
                # This preserves a tiny knee bend (~6°) that looks natural and
                # prevents the "straighten then catch up" skip at drag start.
                distance = max_reach * 0.995

            # Law of cosines for knee and hip angles
            cos_knee = (thigh_length**2 + shin_length**2 - distance**2) / (2 * thigh_length * shin_length)
            cos_knee = max(-1, min(1, cos_knee))
            knee_interior = math.acos(cos_knee)
            knee_bend_angle = math.pi - knee_interior  # Bend = 180° - interior

            cos_hip = (thigh_length**2 + distance**2 - shin_length**2) / (2 * thigh_length * distance)
            cos_hip = max(-1, min(1, cos_hip))
            hip_angle = math.acos(cos_hip)

            # Calculate thigh direction using SAME logic for both extended and bent
            # KEY: Knee must stay in the LOCKED bend plane (captured at drag start)
            # When hip_angle=0 (extended), rotation is identity -> thigh_dir = target_dir
            # This ensures smooth transition without discontinuity
            rotation = Quaternion(bend_normal, hip_angle)
            thigh_dir = rotation @ target_dir

            # === STEP 3: Calculate ThighBend rotation ===
            # Instead of rotation_difference() (which introduces arbitrary roll that
            # varies with hip rotation, causing twist snap), we construct an explicit
            # orientation matrix that controls BOTH aim and roll:
            #   Y axis = thigh_dir (bone direction / aim)
            #   X axis = bend_normal projected perp to Y (shin hinge axis / roll)
            # This keeps the knee plane aligned with bend_normal regardless of hip pose.

            # Read bone's rest-world orientation from Blender's ACTUAL bone.matrix.
            # Our parent+rest formula was 8° off even for rest pose (doesn't account for
            # bone roll, constraints, drivers). Blender's matrix after identity reset +
            # view_layer.update() is the ground truth.
            thigh_world_mat = (armature.matrix_world @ thigh_bone.matrix).to_3x3().normalized()
            rest_x = Vector(thigh_world_mat.col[0]).normalized()
            rest_quat = thigh_world_mat.to_quaternion()

            # Build target orientation
            target_y = thigh_dir.normalized()
            # Project bend_normal perpendicular to target_y for the hinge axis
            target_x = bend_normal - bend_normal.dot(target_y) * target_y
            if target_x.length < 0.001:
                # Degenerate: thigh parallel to bend_normal — use rest X projected
                target_x = rest_x - rest_x.dot(target_y) * target_y
                if target_x.length < 0.001:
                    target_x = Vector((1, 0, 0))  # Ultimate fallback
                target_x.normalize()
            else:
                target_x.normalize()
                # Ensure X doesn't flip vs rest (would reverse knee bend direction)
                if target_x.dot(rest_x) < 0:
                    target_x = -target_x
            target_z = target_x.cross(target_y).normalized()

            # Build target 3x3 matrix (columns = axes)
            target_mat_3x3 = Matrix((
                (target_x[0], target_y[0], target_z[0]),
                (target_x[1], target_y[1], target_z[1]),
                (target_x[2], target_y[2], target_z[2]),
            ))
            target_quat = target_mat_3x3.to_quaternion()

            # Convert target world orientation to bone-local rotation_quaternion.
            # Blender matrix chain: bone_world = rest_world @ rotation_quaternion
            # Therefore: rotation_quaternion = rest_world.inv() @ target_world
            # rest_quat already encodes the full parent chain + rest offset
            # (read from the bone's world matrix at identity rotation above).
            thigh_rotation = rest_quat.inverted() @ target_quat

            # Validate and apply
            if any(math.isnan(v) for v in thigh_rotation):
                thigh_rotation = Quaternion()
            thigh_bone.rotation_quaternion = thigh_rotation
            context.view_layer.update()

            # === STEP 4: Apply Shin rotation (full world-space computation) ===
            # Instead of assuming local X = bend axis (which fails when rest offsets
            # in the thigh_bend → thigh_twist → shin chain misalign the axes),
            # compute the shin's target world orientation and convert to local.

            # Read shin's rest-world orientation from Blender's ACTUAL bone.matrix.
            # After STEP 3 applied thigh rotation + view_layer.update(), the shin bone
            # (at identity rotation) reflects the full parent chain including constraints.
            shin_world_rest = (armature.matrix_world @ shin_bone.matrix).to_3x3().normalized()
            shin_rest_quat = shin_world_rest.to_quaternion()

            # Use ACTUAL knee position from Blender (not geometric estimate).
            # This compensates for any small angular error in the thigh rotation,
            # ensuring the shin always aims from where the knee ACTUALLY is toward the target.
            actual_knee_world = armature.matrix_world @ shin_bone.head
            shin_vec = target_pos - actual_knee_world
            if shin_vec.length > 0.001:
                shin_dir = shin_vec.normalized()
            else:
                shin_dir = thigh_dir  # Fallback: straight extension

            # Build shin target world orientation (same approach as thigh)
            shin_target_y = shin_dir
            shin_target_x = bend_normal - bend_normal.dot(shin_target_y) * shin_target_y
            if shin_target_x.length < 0.001:
                shin_target_x = target_x - target_x.dot(shin_target_y) * shin_target_y
                if shin_target_x.length < 0.001:
                    shin_target_x = Vector((1, 0, 0))
                shin_target_x.normalize()
            else:
                shin_target_x.normalize()
                # Keep consistent direction with thigh's X axis
                if shin_target_x.dot(target_x) < 0:
                    shin_target_x = -shin_target_x
            shin_target_z = shin_target_x.cross(shin_target_y).normalized()

            shin_target_mat = Matrix((
                (shin_target_x[0], shin_target_y[0], shin_target_z[0]),
                (shin_target_x[1], shin_target_y[1], shin_target_z[1]),
                (shin_target_x[2], shin_target_y[2], shin_target_z[2]),
            ))
            shin_target_quat = shin_target_mat.to_quaternion()

            # Convert to local rotation_quaternion
            shin_rotation = shin_rest_quat.inverted() @ shin_target_quat

            if any(math.isnan(v) for v in shin_rotation):
                shin_rotation = Quaternion()
            shin_bone.rotation_quaternion = shin_rotation
            context.view_layer.update()

            # === POPULATE DEBUG DRAW DATA ===
            if _DEBUG_DRAW_ANALYTICAL_LEG:
                actual_knee_dbg = armature.matrix_world @ shin_bone.head
                actual_foot_dbg = armature.matrix_world @ shin_bone.tail
                # Read back the thigh's ACTUAL Y direction after rotation was applied
                actual_thigh_mat = (armature.matrix_world @ thigh_bone.matrix).to_3x3().normalized()
                actual_thigh_y = Vector(actual_thigh_mat.col[1]).normalized()
                # Record trail point (limit to prevent memory bloat)
                if len(self._analytical_leg_debug_trail) < 500:
                    self._analytical_leg_debug_trail.append(target_pos.copy())
                self._analytical_leg_debug_draw_data = {
                    'hip_pos': hip_pos.copy(),
                    'target_pos': target_pos.copy(),
                    'thigh_dir': thigh_dir.copy(),
                    'bend_normal': bend_normal.copy(),
                    'rest_y': Vector(thigh_world_mat.col[1]).normalized(),
                    'actual_thigh_y': actual_thigh_y.copy(),
                    'actual_knee': actual_knee_dbg.copy(),
                    'expected_knee': (hip_pos + thigh_dir * thigh_length).copy(),
                    'actual_foot': actual_foot_dbg.copy(),
                    'foot_error': (actual_foot_dbg - target_pos).length,
                    'trail': list(self._analytical_leg_debug_trail),
                }

            # === DEBUG OUTPUT ===
            if self._debug_frame % 20 == 1:
                actual_foot = armature.matrix_world @ shin_bone.tail
                foot_error = (actual_foot - target_pos).length
                print(f"\n  === ANALYTICAL LEG FRAME {self._debug_frame} ===")
                print(f"  thigh_rot:   {thigh_rotation}")
                print(f"  Target:    ({target_pos.x:.3f}, {target_pos.y:.3f}, {target_pos.z:.3f})")
                print(f"  Foot:      ({actual_foot.x:.3f}, {actual_foot.y:.3f}, {actual_foot.z:.3f})")
                print(f"  Error:     {foot_error:.3f}m")
                print(f"  Knee bend: {math.degrees(knee_bend_angle):.1f}°")
                print(f"  Distance:  {distance:.3f}m (max: {max_reach:.3f}m)")

            if context.area: context.area.tag_redraw()

        except Exception as e:
            print(f"  [ANALYTICAL LEG] ERROR: {e}")
            import traceback
            traceback.print_exc()

    def update_analytical_arm_drag(self, context, event):
        """Update analytical two-bone IK for arm during drag.

        Mirrors the leg solver exactly — law of cosines, locked bend plane,
        bone X-axis for bend normal. The only difference is bone names.

        Bone roles (DAZ Genesis 8/9):
        - ShldrBend: X/Z rotation at shoulder to POINT the elbow direction
        - ShldrTwist: Y rotation (roll around upper arm)
        - ForearmBend: X rotation (hinge joint) for elbow bend angle
        """
        if not self._is_dragging or not self._use_analytical_arm_ik:
            return

        try:
            # Get mouse position and convert to 3D (cross-viewport safe)
            region, rv3d, mouse_pos = self._get_region_rv3d(context, event)
            if not region or not rv3d:
                return

            # Calculate mouse delta from initial position
            if self._drag_initial_mouse_pos:
                mouse_delta = (
                    mouse_pos[0] - self._drag_initial_mouse_pos[0],
                    mouse_pos[1] - self._drag_initial_mouse_pos[1]
                )
            else:
                mouse_delta = (0, 0)

            # Dead zone: don't update until mouse has moved enough
            mouse_dist = math.sqrt(mouse_delta[0]**2 + mouse_delta[1]**2)
            if mouse_dist < 3.0:  # 3 pixels dead zone
                return

            # Convert mouse DELTA to 3D target position
            from bpy_extras.view3d_utils import region_2d_to_location_3d, location_3d_to_region_2d

            initial_wrist_pos = self._drag_initial_target_pos
            initial_wrist_screen = location_3d_to_region_2d(region, rv3d, initial_wrist_pos)

            if initial_wrist_screen:
                target_screen = (
                    initial_wrist_screen[0] + mouse_delta[0],
                    initial_wrist_screen[1] + mouse_delta[1]
                )
                target_pos = region_2d_to_location_3d(
                    region, rv3d,
                    target_screen,
                    initial_wrist_pos
                )
            else:
                target_pos = initial_wrist_pos

            # Get stored values
            shoulder_pos = self._analytical_arm_shoulder_pos
            upper_length = self._analytical_arm_lengths['upper']
            lower_length = self._analytical_arm_lengths['lower']
            armature = self._drag_armature

            # Get bone references
            shoulder_bone = self._analytical_arm_bones['shoulder']
            shoulder_twist = self._analytical_arm_bones.get('shoulder_twist')
            forearm_bone = self._analytical_arm_bones['forearm']
            collar_bone = self._analytical_arm_bones.get('collar')

            # === STEP 1: Reset arm bones to full identity (rest pose) ===
            # NOTE: forearm_twist is NOT reset — it's downstream of the last solver
            # bone (forearm_bone) and doesn't affect wrist position. Preserving it
            # keeps the user's manual twist rotation intact during hand drags.
            for reset_bone in [collar_bone, shoulder_bone, shoulder_twist, forearm_bone]:
                if reset_bone:
                    reset_bone.rotation_quaternion = Quaternion()
                    reset_bone.location = Vector((0, 0, 0))
                    reset_bone.scale = Vector((1, 1, 1))
            context.view_layer.update()

            # === STEP 1.5: Fractional collar rotation toward target ===
            # Scale collar influence with reach distance: no collar help when close
            # to shoulder (prevents instability), full help when reaching far.
            if collar_bone:
                collar_world_mat = (armature.matrix_world @ collar_bone.matrix).to_3x3().normalized()
                collar_rest_quat = collar_world_mat.to_quaternion()
                collar_rest_y = Vector(collar_world_mat.col[1]).normalized()
                collar_world_pos = armature.matrix_world @ collar_bone.head

                collar_to_target = target_pos - collar_world_pos
                if collar_to_target.length > 0.001:
                    # Reach-distance scaling: ramp from 0 at 40% reach to full at 80%
                    max_reach_prelim = upper_length + lower_length
                    prelim_distance = (target_pos - shoulder_pos).length
                    reach_ratio = min(prelim_distance / max_reach_prelim, 1.0)
                    collar_scale = max(0.0, min(1.0, (reach_ratio - 0.4) / 0.4))
                    effective_influence = self._analytical_arm_collar_influence * collar_scale

                    if effective_influence > 0.001:
                        collar_to_target_dir = collar_to_target.normalized()
                        full_rotation = collar_rest_y.rotation_difference(collar_to_target_dir)
                        partial_rotation = Quaternion().slerp(full_rotation, effective_influence)
                        collar_local = collar_rest_quat.inverted() @ (partial_rotation @ collar_rest_quat)

                        if not any(math.isnan(v) for v in collar_local):
                            collar_bone.rotation_quaternion = collar_local

                # Re-read shoulder position after collar rotation
                context.view_layer.update()
                shoulder_pos = armature.matrix_world @ shoulder_bone.head

            # === STEP 2: Calculate geometry ===
            shoulder_to_target = target_pos - shoulder_pos
            distance = shoulder_to_target.length
            max_reach = upper_length + lower_length
            min_reach = abs(upper_length - lower_length) * 0.1

            # Debug counter
            if not hasattr(self, '_arm_debug_frame'):
                self._arm_debug_frame = 0
            self._arm_debug_frame += 1

            target_dir = shoulder_to_target.normalized()

            # Dynamic bend_normal: recompute each frame by projecting the bone's
            # natural X-axis perpendicular to the current target direction.
            # Unlike legs (locked normal, limited ROM), arms need this because the
            # target can be anywhere in a sphere around the shoulder.
            shoulder_world_mat_rest = (armature.matrix_world @ shoulder_bone.matrix).to_3x3().normalized()
            preferred_normal = Vector(shoulder_world_mat_rest.col[0]).normalized()

            # Gram-Schmidt: project preferred_normal perpendicular to target_dir
            projected = preferred_normal - preferred_normal.dot(target_dir) * target_dir
            if projected.length > 0.01:
                bend_normal = projected.normalized()
            else:
                # Target nearly parallel to bone X-axis — use bone Z as fallback
                bone_z_fallback = Vector(shoulder_world_mat_rest.col[2]).normalized()
                projected = bone_z_fallback - bone_z_fallback.dot(target_dir) * target_dir
                if projected.length > 0.01:
                    bend_normal = projected.normalized()
                else:
                    bend_normal = preferred_normal  # Last resort

            # Sign continuity: first frame uses anatomical check, subsequent
            # frames maintain continuity with previous to prevent snap-flips.
            if self._analytical_arm_bend_plane_normal is None:
                # First frame: sign check ensures elbow bends toward -Z
                shoulder_y = Vector(shoulder_world_mat_rest.col[1]).normalized()
                bone_z = Vector(shoulder_world_mat_rest.col[2]).normalized()
                test_dir = Quaternion(bend_normal, 0.01) @ shoulder_y
                if test_dir.dot(bone_z) > shoulder_y.dot(bone_z):
                    bend_normal = -bend_normal
                print(f"  Bend plane normal (dynamic, from bone X-axis): {bend_normal}")
            else:
                # Subsequent frames: sign continuity + dampening.
                # Sign continuity: pick sign closest to previous frame
                if bend_normal.dot(self._analytical_arm_bend_plane_normal) < 0:
                    bend_normal = -bend_normal
                # Dampen: blend between previous and current for smooth transitions.
                # Prevents twist snapping when arm is near-straight and bend_normal
                # is the primary driver of shoulder roll.
                blend_factor = 0.25
                bend_normal = self._analytical_arm_bend_plane_normal.lerp(bend_normal, blend_factor).normalized()

            self._analytical_arm_bend_plane_normal = bend_normal.copy()

            # Handle edge cases
            if distance <= min_reach:
                return
            if distance >= max_reach:
                distance = max_reach * 0.995

            # Law of cosines for elbow and shoulder angles
            cos_elbow = (upper_length**2 + lower_length**2 - distance**2) / (2 * upper_length * lower_length)
            cos_elbow = max(-1, min(1, cos_elbow))
            elbow_interior = math.acos(cos_elbow)
            elbow_bend_angle = math.pi - elbow_interior

            cos_shoulder = (upper_length**2 + distance**2 - lower_length**2) / (2 * upper_length * distance)
            cos_shoulder = max(-1, min(1, cos_shoulder))
            shoulder_angle = math.acos(cos_shoulder)

            # Calculate upper arm direction using locked bend plane
            rotation = Quaternion(bend_normal, shoulder_angle)
            upper_arm_dir = rotation @ target_dir

            # === STEP 3: Calculate ShldrBend rotation ===
            shoulder_world_mat = (armature.matrix_world @ shoulder_bone.matrix).to_3x3().normalized()
            rest_x = Vector(shoulder_world_mat.col[0]).normalized()
            rest_quat = shoulder_world_mat.to_quaternion()

            # Build target orientation
            target_y = upper_arm_dir.normalized()
            target_x = bend_normal - bend_normal.dot(target_y) * target_y
            if target_x.length < 0.001:
                target_x = rest_x - rest_x.dot(target_y) * target_y
                if target_x.length < 0.001:
                    target_x = Vector((1, 0, 0))
                target_x.normalize()
            else:
                target_x.normalize()
                if target_x.dot(rest_x) < 0:
                    target_x = -target_x
            target_z = target_x.cross(target_y).normalized()

            target_mat_3x3 = Matrix((
                (target_x[0], target_y[0], target_z[0]),
                (target_x[1], target_y[1], target_z[1]),
                (target_x[2], target_y[2], target_z[2]),
            ))
            target_quat = target_mat_3x3.to_quaternion()

            shoulder_rotation = rest_quat.inverted() @ target_quat

            if any(math.isnan(v) for v in shoulder_rotation):
                shoulder_rotation = Quaternion()
            shoulder_bone.rotation_quaternion = shoulder_rotation
            context.view_layer.update()

            # === STEP 4: Apply ForearmBend rotation (full world-space) ===
            forearm_world_rest = (armature.matrix_world @ forearm_bone.matrix).to_3x3().normalized()
            forearm_rest_quat = forearm_world_rest.to_quaternion()

            actual_elbow_world = armature.matrix_world @ forearm_bone.head
            forearm_vec = target_pos - actual_elbow_world
            if forearm_vec.length > 0.001:
                forearm_dir = forearm_vec.normalized()
            else:
                forearm_dir = upper_arm_dir

            forearm_target_y = forearm_dir
            forearm_target_x = bend_normal - bend_normal.dot(forearm_target_y) * forearm_target_y
            if forearm_target_x.length < 0.001:
                forearm_target_x = target_x - target_x.dot(forearm_target_y) * forearm_target_y
                if forearm_target_x.length < 0.001:
                    forearm_target_x = Vector((1, 0, 0))
                forearm_target_x.normalize()
            else:
                forearm_target_x.normalize()
                if forearm_target_x.dot(target_x) < 0:
                    forearm_target_x = -forearm_target_x
            forearm_target_z = forearm_target_x.cross(forearm_target_y).normalized()

            forearm_target_mat = Matrix((
                (forearm_target_x[0], forearm_target_y[0], forearm_target_z[0]),
                (forearm_target_x[1], forearm_target_y[1], forearm_target_z[1]),
                (forearm_target_x[2], forearm_target_y[2], forearm_target_z[2]),
            ))
            forearm_target_quat = forearm_target_mat.to_quaternion()

            forearm_rotation = forearm_rest_quat.inverted() @ forearm_target_quat

            if any(math.isnan(v) for v in forearm_rotation):
                forearm_rotation = Quaternion()
            forearm_bone.rotation_quaternion = forearm_rotation
            context.view_layer.update()

            # === POPULATE DEBUG DRAW DATA ===
            if _DEBUG_DRAW_ANALYTICAL_ARM:
                actual_elbow_dbg = armature.matrix_world @ forearm_bone.head
                actual_wrist_dbg = armature.matrix_world @ forearm_bone.tail
                actual_shoulder_mat = (armature.matrix_world @ shoulder_bone.matrix).to_3x3().normalized()
                actual_shoulder_y = Vector(actual_shoulder_mat.col[1]).normalized()
                if len(self._analytical_arm_debug_trail) < 500:
                    self._analytical_arm_debug_trail.append(target_pos.copy())
                collar_debug = {}
                if collar_bone:
                    collar_mat_dbg = (armature.matrix_world @ collar_bone.matrix).to_3x3().normalized()
                    collar_debug = {
                        'collar_pos': (armature.matrix_world @ collar_bone.head).copy(),
                        'collar_y': Vector(collar_mat_dbg.col[1]).normalized(),
                    }
                self._analytical_arm_debug_draw_data = {
                    'shoulder_pos': shoulder_pos.copy(),
                    'target_pos': target_pos.copy(),
                    'upper_arm_dir': upper_arm_dir.copy(),
                    'bend_normal': bend_normal.copy(),
                    'rest_y': Vector(shoulder_world_mat.col[1]).normalized(),
                    'actual_shoulder_y': actual_shoulder_y.copy(),
                    'actual_elbow': actual_elbow_dbg.copy(),
                    'expected_elbow': (shoulder_pos + upper_arm_dir * upper_length).copy(),
                    'actual_wrist': actual_wrist_dbg.copy(),
                    'wrist_error': (actual_wrist_dbg - target_pos).length,
                    'trail': list(self._analytical_arm_debug_trail),
                    **collar_debug,
                }

            # === DEBUG OUTPUT ===
            if self._arm_debug_frame % 20 == 1:
                actual_wrist = armature.matrix_world @ forearm_bone.tail
                wrist_error = (actual_wrist - target_pos).length
                print(f"\n  === ANALYTICAL ARM FRAME {self._arm_debug_frame} ===")
                print(f"  shoulder_rot: {shoulder_rotation}")
                print(f"  Target:    ({target_pos.x:.3f}, {target_pos.y:.3f}, {target_pos.z:.3f})")
                print(f"  Wrist:     ({actual_wrist.x:.3f}, {actual_wrist.y:.3f}, {actual_wrist.z:.3f})")
                print(f"  Error:     {wrist_error:.3f}m")
                print(f"  Elbow bend: {math.degrees(elbow_bend_angle):.1f}°")
                print(f"  Distance:  {distance:.3f}m (max: {max_reach:.3f}m)")

            if context.area: context.area.tag_redraw()

        except Exception as e:
            print(f"  [ANALYTICAL ARM] ERROR: {e}")
            import traceback
            traceback.print_exc()

    # ========================================================================
    # HIP PIN-DRIVEN IK — Analytical solve on pinned limbs while dragging hip
    # ========================================================================

    def _find_pinned_limbs(self, armature):
        """Find all pinned limb endpoints and build per-limb solver state.

        Returns list of limb state dicts, or empty list if no pins found.
        """
        limbs = []
        pose_bones = armature.pose.bones

        # Force depsgraph update for accurate positions
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        armature_eval = armature.evaluated_get(depsgraph)

        # (endpoint, type, side, upper_patterns, twist_patterns, lower_patterns, collar_pattern)
        limb_configs = [
            ('lFoot', 'leg', 'l', ['lThigh', 'lThighBend'], ['lThighTwist'], ['lShin', 'lShinBend', 'lCalf'], None),
            ('rFoot', 'leg', 'r', ['rThigh', 'rThighBend'], ['rThighTwist'], ['rShin', 'rShinBend', 'rCalf'], None),
            ('lHand', 'arm', 'l', ['lShldrBend', 'lShldr', 'lShoulder'], ['lShldrTwist'], ['lForearmBend', 'lForeArm', 'lForearm'], 'lCollar'),
            ('rHand', 'arm', 'r', ['rShldrBend', 'rShldr', 'rShoulder'], ['rShldrTwist'], ['rForearmBend', 'rForeArm', 'rForearm'], 'rCollar'),
            ('head', 'neck', 'c', ['neckLower'], [], ['neckUpper'], None),
        ]

        for endpoint_name, limb_type, side, upper_pats, twist_pats, lower_pats, collar_pat in limb_configs:
            data_bone = armature.data.bones.get(endpoint_name)
            if not data_bone or not is_bone_pinned_translation(data_bone):
                continue

            # Get pin Empty position
            pin_empty_name = f"PIN_translation_{armature.name}_{endpoint_name}"
            pin_empty = bpy.data.objects.get(pin_empty_name)
            if not pin_empty:
                continue
            pin_target_pos = pin_empty.matrix_world.translation.copy()

            # Find bones by pattern
            upper_bone = next((pose_bones[p] for p in upper_pats if p in pose_bones), None)
            twist_bone = next((pose_bones[p] for p in twist_pats if p in pose_bones), None)
            lower_bone = next((pose_bones[p] for p in lower_pats if p in pose_bones), None)
            endpoint_bone = pose_bones.get(endpoint_name)
            collar_bone = pose_bones.get(collar_pat) if collar_pat else None

            if not upper_bone or not lower_bone or not endpoint_bone:
                continue

            # Calculate bone lengths from evaluated armature
            upper_eval = armature_eval.pose.bones[upper_bone.name]
            lower_eval = armature_eval.pose.bones[lower_bone.name]

            upper_head = armature.matrix_world @ Vector(upper_eval.head)
            lower_head = armature.matrix_world @ Vector(lower_eval.head)
            lower_tail = armature.matrix_world @ Vector(lower_eval.tail)

            upper_length = (lower_head - upper_head).length
            lower_length = (lower_tail - lower_head).length

            # Ensure quaternion mode
            for bone in [upper_bone, twist_bone, lower_bone, endpoint_bone, collar_bone]:
                if bone:
                    bone.rotation_mode = 'QUATERNION'

            # Build per-limb state dict
            if limb_type == 'leg':
                bones = {
                    'thigh': upper_bone, 'thigh_twist': twist_bone,
                    'shin': lower_bone, 'foot': endpoint_bone,
                }
                lengths = {'thigh': upper_length, 'shin': lower_length}
            elif limb_type == 'neck':
                bones = {
                    'neck_lower': upper_bone, 'neck_upper': lower_bone,
                    'head': endpoint_bone,
                }
                lengths = {'upper': upper_length, 'lower': lower_length}
            else:
                forearm_twist = pose_bones.get(f'{side}ForearmTwist')
                if forearm_twist:
                    forearm_twist.rotation_mode = 'QUATERNION'
                bones = {
                    'collar': collar_bone, 'shoulder': upper_bone,
                    'shoulder_twist': twist_bone, 'forearm': lower_bone,
                    'forearm_twist': forearm_twist, 'hand': endpoint_bone,
                }
                lengths = {'upper': upper_length, 'lower': lower_length}

            limbs.append({
                'type': limb_type, 'side': side,
                'endpoint_name': endpoint_name,
                'pin_target_pos': pin_target_pos,
                'bones': bones, 'lengths': lengths,
                'bend_plane_normal': None,  # Deferred to first frame
            })
            print(f"  Found pinned {limb_type}: {endpoint_name} → target={pin_target_pos}")

        return limbs

    # Spine chain definition for head rotation pin compensation.
    # Bottom-up order (parent first). neckUpper is always the remainder bone.
    # Stiffness values from ik_templates.py head template.
    SPINE_CHAIN_DEF = [
        ('abdomenLower', 0.90),
        ('abdomenUpper', 0.90),
        ('chestLower',   0.75),
        ('chestUpper',   0.75),
        ('neckLower',    0.60),
    ]

    def _find_pinned_head(self, armature, rotated_bone_name=None):
        """Find rotation-pinned head bone and build spine compensation solver state.

        Returns a dict with solver state if head has a rotation pin, else None.
        Distributes compensating rotation through the spine chain with neckUpper
        handling all remaining correction.

        Args:
            rotated_bone_name: If provided, only include chain bones ABOVE this bone
                (i.e. between the rotated bone and the head). Used when rotating a
                spine bone directly — only bones above it should compensate.
                If None (hip rotation), uses the full chain.
        """
        pose_bones = armature.pose.bones

        head_data = armature.data.bones.get('head')
        if not head_data or not is_bone_pinned_rotation(head_data):
            return None

        head_bone = pose_bones.get('head')
        neck_upper = pose_bones.get('neckUpper')

        if not head_bone or not neck_upper:
            print(f"  [SPINE] Head is rotation-pinned but head/neckUpper bones missing")
            return None

        # Retrieve the stored pinned world rotation
        pinned_euler_raw = head_data.get("daz_pin_rotation_euler")
        if pinned_euler_raw is None:
            print(f"  [SPINE] Head has daz_pin_rotation but no daz_pin_rotation_euler")
            return None

        pinned_world_quat = Euler(pinned_euler_raw).to_quaternion()

        # Build chain from SPINE_CHAIN_DEF, skipping missing bones.
        # If rotated_bone_name is given, only include bones ABOVE it in the chain.
        chain_names = [name for name, _ in self.SPINE_CHAIN_DEF]
        skip_at_or_below = None
        if rotated_bone_name and rotated_bone_name in chain_names:
            skip_at_or_below = chain_names.index(rotated_bone_name)

        chain_bones = []
        chain_mobilities = []
        for i, (bone_name, stiffness) in enumerate(self.SPINE_CHAIN_DEF):
            if skip_at_or_below is not None and i <= skip_at_or_below:
                continue
            bone = pose_bones.get(bone_name)
            if bone:
                bone.rotation_mode = 'QUATERNION'
                chain_bones.append(bone)
                chain_mobilities.append(1.0 - stiffness)

        if not chain_bones:
            print(f"  [SPINE] No spine chain bones found")
            return None

        # Normalize weights so they sum to 1.0
        total_mobility = sum(chain_mobilities)
        chain_weights = [m / total_mobility for m in chain_mobilities] if total_mobility > 0 else [1.0 / len(chain_mobilities)] * len(chain_mobilities)

        # neckUpper is always the remainder bone
        neck_upper.rotation_mode = 'QUATERNION'
        head_bone.rotation_mode = 'QUATERNION'

        # all_bones = chain + remainder (for reset/keyframe loops)
        all_bones = chain_bones + [neck_upper]

        state = {
            'head_bone': head_bone,
            'chain_bones': chain_bones,
            'chain_weights': chain_weights,
            'remainder_bone': neck_upper,
            'pinned_world_quat': pinned_world_quat,
            'all_bones': all_bones,
        }

        bone_names = [b.name for b in chain_bones]
        weight_strs = [f"{b.name}={w:.3f}" for b, w in zip(chain_bones, chain_weights)]
        print(f"  Found rotation-pinned head: chain={bone_names}, "
              f"weights=[{', '.join(weight_strs)}], remainder=neckUpper")
        return state

    def _start_hip_pin_drag(self, context, event, hip_bone, pinned_limbs):
        """Start hip drag: native translate + depsgraph handler for pin IK.

        Uses Blender's own translate operator for hip movement (supports G+X,
        G+Y, G+Shift+Z, snapping, etc.) and installs a depsgraph handler that
        runs the analytical IK solver on pinned limbs after each update.
        """
        armature = self._drag_armature

        print(f"\n=== Starting Hip Pin-Driven IK Drag ===")
        print(f"  Hip bone: {hip_bone.name}, Pinned limbs: {len(pinned_limbs)}")

        # Store state for the depsgraph handler
        self._hip_bone = hip_bone
        self._hip_original_location = hip_bone.location.copy()
        self._hip_pin_limbs = pinned_limbs
        self._hip_debug_frame = 0

        # Check for rotation-pinned head (neck compensation solver)
        # BUT skip if head already has a translation pin (handled as neck limb in pinned_limbs)
        head_has_translation_pin = any(l['type'] == 'neck' for l in pinned_limbs)
        if head_has_translation_pin:
            self._hip_pin_neck_state = None
        else:
            self._hip_pin_neck_state = self._find_pinned_head(armature)

        # Store original rotations for cancel/restore
        self._hip_original_rotations = {}
        self._hip_original_rotations[hip_bone.name] = {
            'location': hip_bone.location.copy(),
            'rotation': hip_bone.rotation_quaternion.copy(),
        }
        for limb in pinned_limbs:
            for bone_key, bone in limb['bones'].items():
                if bone and bone.name not in self._hip_original_rotations:
                    self._hip_original_rotations[bone.name] = {
                        'location': bone.location.copy(),
                        'rotation': bone.rotation_quaternion.copy(),
                    }

        # Store original rotations for spine/neck bones (for cancel/restore)
        if self._hip_pin_neck_state:
            for bone in self._hip_pin_neck_state['all_bones'] + [self._hip_pin_neck_state['head_bone']]:
                if bone.name not in self._hip_original_rotations:
                    self._hip_original_rotations[bone.name] = {
                        'location': bone.location.copy(),
                        'rotation': bone.rotation_quaternion.copy(),
                    }

        # Mute translation pin constraints on pinned endpoints (solver positions them).
        # Keep rotation pins ACTIVE — they maintain foot/hand orientation during IK.
        self._hip_pin_muted_constraints = []
        for limb in pinned_limbs:
            endpoint_pose = armature.pose.bones.get(limb['endpoint_name'])
            if endpoint_pose:
                for c in endpoint_pose.constraints:
                    if c.name == "DAZ_Pin_Translation" and not c.mute:
                        c.mute = True
                        self._hip_pin_muted_constraints.append((endpoint_pose, c))
                        print(f"  Muted pin constraint: {c.name} on {limb['endpoint_name']}")

        # Mute head's rotation pin constraint (neck solver writes rotations directly)
        if self._hip_pin_neck_state:
            head_pose = self._hip_pin_neck_state['head_bone']
            for c in head_pose.constraints:
                if c.name == "DAZ_Pin_Rotation" and not c.mute:
                    c.mute = True
                    self._hip_pin_muted_constraints.append((head_pose, c))
                    print(f"  Muted head rotation pin constraint for neck solver")

        # Install depsgraph handler that solves pinned limbs after each hip update
        self._use_hip_pin_ik = True
        self._hip_pin_solving = False  # Guard against re-entrant calls

        def hip_pin_depsgraph_handler(scene, depsgraph):
            """Called after every depsgraph update while native translate runs."""
            # Guard: skip if we're already solving (our own updates trigger depsgraph)
            if not self._use_hip_pin_ik or self._hip_pin_solving:
                return
            self._hip_pin_solving = True
            try:
                # Reset limb bones to identity
                for limb in self._hip_pin_limbs:
                    for bone_key, bone in limb['bones'].items():
                        if bone:
                            bone.rotation_quaternion = Quaternion()
                            bone.location = Vector((0, 0, 0))
                            bone.scale = Vector((1, 1, 1))

                # Reset spine/neck bones to identity (if head is rotation-pinned)
                neck_state = self._hip_pin_neck_state
                if neck_state:
                    for bone in neck_state['all_bones']:
                        bone.rotation_quaternion = Quaternion()
                        bone.location = Vector((0, 0, 0))
                        bone.scale = Vector((1, 1, 1))

                bpy.context.view_layer.update()

                # Solve pinned limbs (positional IK)
                for limb in self._hip_pin_limbs:
                    self._solve_pinned_limb(bpy.context, armature, limb)

                # Solve neck compensation (rotational — AFTER limbs)
                if neck_state:
                    self._solve_pinned_neck(bpy.context, armature, neck_state)

                self._hip_debug_frame += 1
                if self._hip_debug_frame <= 3 or self._hip_debug_frame % 30 == 0:
                    hip_pos = armature.matrix_world @ hip_bone.head
                    debug_msg = f"  [HIP PIN] Frame {self._hip_debug_frame}: hip=({hip_pos.x:.4f}, {hip_pos.y:.4f}, {hip_pos.z:.4f})"
                    if neck_state:
                        debug_msg += " [NECK COMP]"
                    print(debug_msg)
            except Exception as e:
                print(f"  [HIP PIN] Handler error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self._hip_pin_solving = False

        self._hip_pin_handler = hip_pin_depsgraph_handler
        bpy.app.handlers.depsgraph_update_post.append(hip_pin_depsgraph_handler)
        print("  ✓ Installed depsgraph handler")

        # Launch Blender's native translate — this takes over hip movement
        try:
            bpy.ops.transform.translate('INVOKE_DEFAULT')
            print("  ✓ Invoked native translate")
        except Exception as e:
            print(f"  ✗ Could not invoke translate: {e}")
            self._remove_hip_pin_handler()
            self._use_hip_pin_ik = False

        # Clear drag state — native translate owns the modal now
        # Our modal will detect translate finishing via the handler cleanup
        self._drag_bone_name = None
        self._drag_armature_for_pin = armature  # Keep ref for end handler
        print("  ✓ Hip pin IK mode activated")

    def _remove_hip_pin_handler(self):
        """Remove the depsgraph handler if installed."""
        handler = getattr(self, '_hip_pin_handler', None)
        if handler and handler in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(handler)
            print("  ✓ Removed depsgraph handler")
        self._hip_pin_handler = None

    def _end_hip_pin_ik(self, context, cancel=False):
        """Clean up after native translate finishes (confirm or cancel)."""
        if not self._use_hip_pin_ik:
            return

        self._remove_hip_pin_handler()
        armature = getattr(self, '_drag_armature_for_pin', None) or self._drag_armature
        hip_bone = self._hip_bone

        if cancel:
            print(f"\n=== Canceling Hip Pin IK ===")
            # Native translate already reverted the hip location on cancel.
            # Restore all limb bone rotations from originals.
            if armature:
                for bone_name, original_state in self._hip_original_rotations.items():
                    pose_bone = armature.pose.bones.get(bone_name)
                    if pose_bone:
                        pose_bone.location = original_state['location']
                        pose_bone.rotation_quaternion = original_state['rotation']
                context.view_layer.update()
        else:
            print(f"\n=== Ending Hip Pin IK ===")
            # Native translate already committed the hip location.
            # Keyframe hip location + all limb bone rotations.
            current_frame = context.scene.frame_current

            if hip_bone:
                hip_bone.keyframe_insert(
                    data_path="location",
                    frame=current_frame,
                    options={'INSERTKEY_VISUAL'}
                )
                print(f"  ✓ Keyframed location: {hip_bone.name}")

            for limb in self._hip_pin_limbs:
                for bone_key, bone in limb['bones'].items():
                    if bone:
                        bone.keyframe_insert(
                            data_path="rotation_quaternion",
                            frame=current_frame,
                            options={'INSERTKEY_VISUAL'}
                        )
                        print(f"  ✓ Keyframed rotation: {bone.name}")

            # Keyframe spine/neck bones (if head was rotation-pinned)
            if self._hip_pin_neck_state:
                for bone in self._hip_pin_neck_state['all_bones']:
                    bone.keyframe_insert(
                        data_path="rotation_quaternion",
                        frame=current_frame,
                        options={'INSERTKEY_VISUAL'}
                    )
                    print(f"  ✓ Keyframed neck rotation: {bone.name}")

                # Update head rotation pin to match final head orientation
                head_bone_ns = self._hip_pin_neck_state['head_bone']
                head_data_bone = armature.data.bones.get('head') if armature else None
                if head_bone_ns and head_data_bone and armature:
                    world_mat = armature.matrix_world @ head_bone_ns.matrix
                    if "daz_pin_rotation_euler" in head_data_bone:
                        head_data_bone["daz_pin_rotation_euler"] = world_mat.to_euler()
                    rot_empty_name = f"PIN_rotation_{armature.name}_head"
                    rot_empty = bpy.data.objects.get(rot_empty_name)
                    if rot_empty:
                        rot_empty.matrix_world = world_mat
                        print(f"  ✓ Updated head rotation pin Empty to final orientation")

            # Update pin Empty positions/rotations to match final endpoint state
            if armature:
                for limb in self._hip_pin_limbs:
                    endpoint_name = limb['endpoint_name']
                    endpoint_bone = armature.pose.bones.get(endpoint_name)
                    data_bone = armature.data.bones.get(endpoint_name)
                    if endpoint_bone:
                        new_pos = armature.matrix_world @ endpoint_bone.head
                        # Update translation pin Empty
                        pin_empty_name = f"PIN_translation_{armature.name}_{endpoint_name}"
                        pin_empty = bpy.data.objects.get(pin_empty_name)
                        if pin_empty:
                            pin_empty.location = new_pos
                            print(f"  ✓ Updated pin Empty: {pin_empty_name}")
                        if data_bone and "daz_pin_location" in data_bone:
                            data_bone["daz_pin_location"] = tuple(new_pos)
                        # Update rotation pin Empty
                        rot_empty_name = f"PIN_rotation_{armature.name}_{endpoint_name}"
                        rot_empty = bpy.data.objects.get(rot_empty_name)
                        if rot_empty:
                            world_mat = armature.matrix_world @ endpoint_bone.matrix
                            rot_empty.matrix_world = world_mat
                            print(f"  ✓ Updated rotation pin Empty: {rot_empty_name}")
                        if data_bone and "daz_pin_rotation_euler" in data_bone:
                            world_mat = armature.matrix_world @ endpoint_bone.matrix
                            data_bone["daz_pin_rotation_euler"] = world_mat.to_euler()

        # Unmute pin constraints (always)
        for pose_bone, constraint in self._hip_pin_muted_constraints:
            try:
                constraint.mute = False
                print(f"  ✓ Re-enabled pin constraint: {constraint.name} on {pose_bone.name}")
            except Exception as e:
                print(f"  ⚠️  Error re-enabling pin on {pose_bone.name}: {e}")

        # Clean up state
        self._use_hip_pin_ik = False
        self._hip_pin_limbs = []
        self._hip_bone = None
        self._hip_original_location = None
        self._hip_original_rotations = {}
        self._hip_pin_muted_constraints = []
        self._hip_debug_frame = 0
        self._hip_pin_solving = False
        self._hip_pin_neck_state = None
        self._drag_armature_for_pin = None

        self._set_header(context,"DAZ Bone Select Active - P to pin | U to unpin | Alt+Shift+R to clear pose | ESC to exit")

    def _end_native_rotate_neck(self, context, cancel=False):
        """Clean up after native rotate finishes (confirm or cancel) with neck compensation."""
        if not self._use_native_rotate_neck:
            return

        # Remove depsgraph handler
        handler = getattr(self, '_native_rotate_handler', None)
        if handler and handler in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(handler)
            print("  ✓ Removed neck rotation depsgraph handler")
        self._native_rotate_handler = None

        armature = self._drag_armature
        neck_state = self._native_rotate_neck_state

        if cancel:
            print(f"\n=== Canceling Native Rotate + Neck ===")
            # Native rotate already reverted the bone rotation on cancel.
            # Restore neck bones from originals.
            if armature:
                for bone_name, orig_quat in self._native_rotate_neck_originals.items():
                    pose_bone = armature.pose.bones.get(bone_name)
                    if pose_bone:
                        pose_bone.rotation_quaternion = orig_quat
                context.view_layer.update()
        else:
            print(f"\n=== Ending Native Rotate + Neck ===")
            # Keyframe spine/neck bones
            if neck_state:
                current_frame = context.scene.frame_current
                for bone in neck_state['all_bones']:
                    bone.keyframe_insert(
                        data_path="rotation_quaternion",
                        frame=current_frame,
                        options={'INSERTKEY_VISUAL'}
                    )
                    print(f"  ✓ Keyframed spine/neck rotation: {bone.name}")

                # Update head rotation pin to final orientation
                if armature:
                    head_bone = neck_state['head_bone']
                    head_data_bone = armature.data.bones.get('head')
                    if head_bone and head_data_bone:
                        world_mat = armature.matrix_world @ head_bone.matrix
                        if "daz_pin_rotation_euler" in head_data_bone:
                            head_data_bone["daz_pin_rotation_euler"] = world_mat.to_euler()
                        rot_empty_name = f"PIN_rotation_{armature.name}_head"
                        rot_empty = bpy.data.objects.get(rot_empty_name)
                        if rot_empty:
                            rot_empty.matrix_world = world_mat
                            print(f"  ✓ Updated head rotation pin to final orientation")

        # Unmute head constraint (always)
        for pose_bone, constraint in self._native_rotate_neck_muted:
            try:
                constraint.mute = False
                print(f"  ✓ Re-enabled head rotation pin constraint")
            except Exception as e:
                print(f"  ⚠️  Error re-enabling head constraint: {e}")

        # Clean up state
        self._use_native_rotate_neck = False
        self._native_rotate_neck_state = None
        self._native_rotate_neck_muted = []
        self._native_rotate_neck_originals = {}
        self._native_rotate_solving = False

    def _end_pin_override(self, context, cancel=False):
        """Clean up after R/G on a pinned bone (native transform with muted constraint).

        On confirm: update the pin Empty to the bone's new position/orientation,
        then unmute the constraint so the pin tracks the new pose.
        On cancel: just unmute — native transform already reverted the bone.
        """
        if not self._pin_override_active:
            return

        armature = self._pin_override_armature
        bone_name = self._pin_override_bone
        override_type = self._pin_override_type

        if cancel:
            print(f"\n=== Canceling Pin Override: {bone_name} ({override_type}) ===")
        else:
            print(f"\n=== Ending Pin Override: {bone_name} ({override_type}) ===")

        if armature and bone_name:
            pose_bone = armature.pose.bones.get(bone_name)
            data_bone = armature.data.bones.get(bone_name)

            if not cancel and pose_bone and data_bone:
                # Update pin to new pose
                context.view_layer.update()
                world_mat = armature.matrix_world @ pose_bone.matrix

                if override_type == 'rotation':
                    # Update rotation pin Empty and stored euler
                    if "daz_pin_rotation_euler" in data_bone:
                        data_bone["daz_pin_rotation_euler"] = world_mat.to_euler()
                    rot_empty_name = f"PIN_rotation_{armature.name}_{bone_name}"
                    rot_empty = bpy.data.objects.get(rot_empty_name)
                    if rot_empty:
                        rot_empty.matrix_world = world_mat
                        print(f"  ✓ Updated rotation pin to new orientation")

                elif override_type == 'translation':
                    # Update translation pin Empty position
                    new_pos = armature.matrix_world @ pose_bone.head
                    trans_empty_name = f"PIN_translation_{armature.name}_{bone_name}"
                    trans_empty = bpy.data.objects.get(trans_empty_name)
                    if trans_empty:
                        trans_empty.location = new_pos
                        print(f"  ✓ Updated translation pin to new position")

            # Unmute pin constraints
            if pose_bone:
                constraint_name = f"DAZ_Pin_{'Rotation' if override_type == 'rotation' else 'Translation'}"
                for c in pose_bone.constraints:
                    if c.name == constraint_name and c.mute:
                        c.mute = False
                        print(f"  ✓ Re-enabled {c.name}")

        # Clean up state
        self._pin_override_active = False
        self._pin_override_bone = None
        self._pin_override_armature = None
        self._pin_override_type = None

    def _solve_pinned_limb(self, context, armature, limb):
        """Run analytical 2-bone IK solve for one pinned limb.

        target_pos is the pin position (fixed).
        Joint origin (hip/shoulder) is read fresh from the armature.
        """
        target_pos = limb['pin_target_pos']

        if limb['type'] == 'leg':
            thigh_bone = limb['bones']['thigh']
            shin_bone = limb['bones']['shin']
            thigh_length = limb['lengths']['thigh']
            shin_length = limb['lengths']['shin']

            # Read hip joint position FRESH (it moved this frame)
            joint_pos = armature.matrix_world @ thigh_bone.head

            # Geometry
            joint_to_target = target_pos - joint_pos
            distance = joint_to_target.length
            max_reach = thigh_length + shin_length
            min_reach = abs(thigh_length - shin_length) * 0.1

            if distance <= min_reach:
                return
            if distance >= max_reach:
                distance = max_reach * 0.995

            # Bend plane normal (deferred to first frame, locked for legs)
            bend_normal = limb['bend_plane_normal']
            if bend_normal is None:
                thigh_world_mat_rest = (armature.matrix_world @ thigh_bone.matrix).to_3x3().normalized()
                bend_normal = Vector(thigh_world_mat_rest.col[0]).normalized()
                thigh_y = Vector(thigh_world_mat_rest.col[1]).normalized()
                bone_z = Vector(thigh_world_mat_rest.col[2]).normalized()
                test_dir = Quaternion(bend_normal, 0.01) @ thigh_y
                if test_dir.dot(bone_z) > thigh_y.dot(bone_z):
                    bend_normal = -bend_normal
                limb['bend_plane_normal'] = bend_normal

            target_dir = joint_to_target.normalized()

            # Law of cosines
            cos_knee = (thigh_length**2 + shin_length**2 - distance**2) / (2 * thigh_length * shin_length)
            cos_knee = max(-1, min(1, cos_knee))
            cos_hip = (thigh_length**2 + distance**2 - shin_length**2) / (2 * thigh_length * distance)
            cos_hip = max(-1, min(1, cos_hip))
            hip_angle = math.acos(cos_hip)

            rotation = Quaternion(bend_normal, hip_angle)
            thigh_dir = rotation @ target_dir

            # STEP 3: ThighBend rotation
            thigh_world_mat = (armature.matrix_world @ thigh_bone.matrix).to_3x3().normalized()
            rest_x = Vector(thigh_world_mat.col[0]).normalized()
            rest_quat = thigh_world_mat.to_quaternion()

            target_y = thigh_dir.normalized()
            target_x = bend_normal - bend_normal.dot(target_y) * target_y
            if target_x.length < 0.001:
                target_x = rest_x - rest_x.dot(target_y) * target_y
                if target_x.length < 0.001:
                    target_x = Vector((1, 0, 0))
                target_x.normalize()
            else:
                target_x.normalize()
                if target_x.dot(rest_x) < 0:
                    target_x = -target_x
            target_z = target_x.cross(target_y).normalized()

            target_mat_3x3 = Matrix((
                (target_x[0], target_y[0], target_z[0]),
                (target_x[1], target_y[1], target_z[1]),
                (target_x[2], target_y[2], target_z[2]),
            ))
            thigh_rotation = rest_quat.inverted() @ target_mat_3x3.to_quaternion()

            if any(math.isnan(v) for v in thigh_rotation):
                thigh_rotation = Quaternion()
            thigh_bone.rotation_quaternion = thigh_rotation
            context.view_layer.update()

            # STEP 4: Shin rotation
            shin_world_rest = (armature.matrix_world @ shin_bone.matrix).to_3x3().normalized()
            shin_rest_quat = shin_world_rest.to_quaternion()

            actual_knee_world = armature.matrix_world @ shin_bone.head
            shin_vec = target_pos - actual_knee_world
            if shin_vec.length > 0.001:
                shin_dir = shin_vec.normalized()
            else:
                shin_dir = thigh_dir

            shin_target_y = shin_dir
            shin_target_x = bend_normal - bend_normal.dot(shin_target_y) * shin_target_y
            if shin_target_x.length < 0.001:
                shin_target_x = target_x - target_x.dot(shin_target_y) * shin_target_y
                if shin_target_x.length < 0.001:
                    shin_target_x = Vector((1, 0, 0))
                shin_target_x.normalize()
            else:
                shin_target_x.normalize()
                if shin_target_x.dot(target_x) < 0:
                    shin_target_x = -shin_target_x
            shin_target_z = shin_target_x.cross(shin_target_y).normalized()

            shin_target_mat = Matrix((
                (shin_target_x[0], shin_target_y[0], shin_target_z[0]),
                (shin_target_x[1], shin_target_y[1], shin_target_z[1]),
                (shin_target_x[2], shin_target_y[2], shin_target_z[2]),
            ))
            shin_rotation = shin_rest_quat.inverted() @ shin_target_mat.to_quaternion()

            if any(math.isnan(v) for v in shin_rotation):
                shin_rotation = Quaternion()
            shin_bone.rotation_quaternion = shin_rotation
            context.view_layer.update()

        elif limb['type'] == 'arm':
            shoulder_bone = limb['bones']['shoulder']
            forearm_bone = limb['bones']['forearm']
            collar_bone = limb['bones'].get('collar')
            upper_length = limb['lengths']['upper']
            lower_length = limb['lengths']['lower']

            # Read shoulder position FRESH
            shoulder_pos = armature.matrix_world @ shoulder_bone.head

            # Optional collar rotation (same as arm solver STEP 1.5)
            if collar_bone:
                collar_world_mat = (armature.matrix_world @ collar_bone.matrix).to_3x3().normalized()
                collar_rest_quat = collar_world_mat.to_quaternion()
                collar_rest_y = Vector(collar_world_mat.col[1]).normalized()
                collar_world_pos = armature.matrix_world @ collar_bone.head

                collar_to_target = target_pos - collar_world_pos
                if collar_to_target.length > 0.001:
                    max_reach_prelim = upper_length + lower_length
                    prelim_distance = (target_pos - shoulder_pos).length
                    reach_ratio = min(prelim_distance / max_reach_prelim, 1.0)
                    collar_scale = max(0.0, min(1.0, (reach_ratio - 0.4) / 0.4))
                    effective_influence = 0.45 * collar_scale

                    if effective_influence > 0.001:
                        collar_to_target_dir = collar_to_target.normalized()
                        full_rotation = collar_rest_y.rotation_difference(collar_to_target_dir)
                        partial_rotation = Quaternion().slerp(full_rotation, effective_influence)
                        collar_local = collar_rest_quat.inverted() @ (partial_rotation @ collar_rest_quat)

                        if not any(math.isnan(v) for v in collar_local):
                            collar_bone.rotation_quaternion = collar_local

                context.view_layer.update()
                shoulder_pos = armature.matrix_world @ shoulder_bone.head

            # Geometry
            shoulder_to_target = target_pos - shoulder_pos
            distance = shoulder_to_target.length
            max_reach = upper_length + lower_length
            min_reach = abs(upper_length - lower_length) * 0.1

            if distance <= min_reach:
                return
            if distance >= max_reach:
                distance = max_reach * 0.995

            target_dir = shoulder_to_target.normalized()

            # Dynamic bend_normal (same as arm solver — Gram-Schmidt + sign continuity + dampening)
            shoulder_world_mat_rest = (armature.matrix_world @ shoulder_bone.matrix).to_3x3().normalized()
            preferred_normal = Vector(shoulder_world_mat_rest.col[0]).normalized()

            projected = preferred_normal - preferred_normal.dot(target_dir) * target_dir
            if projected.length > 0.01:
                bend_normal = projected.normalized()
            else:
                bone_z_fallback = Vector(shoulder_world_mat_rest.col[2]).normalized()
                projected = bone_z_fallback - bone_z_fallback.dot(target_dir) * target_dir
                if projected.length > 0.01:
                    bend_normal = projected.normalized()
                else:
                    bend_normal = preferred_normal

            if limb['bend_plane_normal'] is None:
                # First frame: anatomical sign check
                shoulder_y = Vector(shoulder_world_mat_rest.col[1]).normalized()
                bone_z = Vector(shoulder_world_mat_rest.col[2]).normalized()
                test_dir = Quaternion(bend_normal, 0.01) @ shoulder_y
                if test_dir.dot(bone_z) > shoulder_y.dot(bone_z):
                    bend_normal = -bend_normal
            else:
                # Subsequent: sign continuity + dampening
                if bend_normal.dot(limb['bend_plane_normal']) < 0:
                    bend_normal = -bend_normal
                bend_normal = limb['bend_plane_normal'].lerp(bend_normal, 0.25).normalized()

            limb['bend_plane_normal'] = bend_normal.copy()

            # Law of cosines
            cos_elbow = (upper_length**2 + lower_length**2 - distance**2) / (2 * upper_length * lower_length)
            cos_elbow = max(-1, min(1, cos_elbow))
            cos_shoulder = (upper_length**2 + distance**2 - lower_length**2) / (2 * upper_length * distance)
            cos_shoulder = max(-1, min(1, cos_shoulder))
            shoulder_angle = math.acos(cos_shoulder)

            rotation = Quaternion(bend_normal, shoulder_angle)
            upper_arm_dir = rotation @ target_dir

            # STEP 3: ShldrBend rotation
            shoulder_world_mat = (armature.matrix_world @ shoulder_bone.matrix).to_3x3().normalized()
            rest_x = Vector(shoulder_world_mat.col[0]).normalized()
            rest_quat = shoulder_world_mat.to_quaternion()

            target_y = upper_arm_dir.normalized()
            target_x = bend_normal - bend_normal.dot(target_y) * target_y
            if target_x.length < 0.001:
                target_x = rest_x - rest_x.dot(target_y) * target_y
                if target_x.length < 0.001:
                    target_x = Vector((1, 0, 0))
                target_x.normalize()
            else:
                target_x.normalize()
                if target_x.dot(rest_x) < 0:
                    target_x = -target_x
            target_z = target_x.cross(target_y).normalized()

            target_mat_3x3 = Matrix((
                (target_x[0], target_y[0], target_z[0]),
                (target_x[1], target_y[1], target_z[1]),
                (target_x[2], target_y[2], target_z[2]),
            ))
            shoulder_rotation = rest_quat.inverted() @ target_mat_3x3.to_quaternion()

            if any(math.isnan(v) for v in shoulder_rotation):
                shoulder_rotation = Quaternion()
            shoulder_bone.rotation_quaternion = shoulder_rotation
            context.view_layer.update()

            # STEP 4: ForearmBend rotation
            forearm_world_rest = (armature.matrix_world @ forearm_bone.matrix).to_3x3().normalized()
            forearm_rest_quat = forearm_world_rest.to_quaternion()

            actual_elbow_world = armature.matrix_world @ forearm_bone.head
            forearm_vec = target_pos - actual_elbow_world
            if forearm_vec.length > 0.001:
                forearm_dir = forearm_vec.normalized()
            else:
                forearm_dir = upper_arm_dir

            forearm_target_y = forearm_dir
            forearm_target_x = bend_normal - bend_normal.dot(forearm_target_y) * forearm_target_y
            if forearm_target_x.length < 0.001:
                forearm_target_x = target_x - target_x.dot(forearm_target_y) * forearm_target_y
                if forearm_target_x.length < 0.001:
                    forearm_target_x = Vector((1, 0, 0))
                forearm_target_x.normalize()
            else:
                forearm_target_x.normalize()
                if forearm_target_x.dot(target_x) < 0:
                    forearm_target_x = -forearm_target_x
            forearm_target_z = forearm_target_x.cross(forearm_target_y).normalized()

            forearm_target_mat = Matrix((
                (forearm_target_x[0], forearm_target_y[0], forearm_target_z[0]),
                (forearm_target_x[1], forearm_target_y[1], forearm_target_z[1]),
                (forearm_target_x[2], forearm_target_y[2], forearm_target_z[2]),
            ))
            forearm_rotation = forearm_rest_quat.inverted() @ forearm_target_mat.to_quaternion()

            if any(math.isnan(v) for v in forearm_rotation):
                forearm_rotation = Quaternion()
            forearm_bone.rotation_quaternion = forearm_rotation
            context.view_layer.update()

        elif limb['type'] == 'neck':
            neck_lower_bone = limb['bones']['neck_lower']
            neck_upper_bone = limb['bones']['neck_upper']
            upper_length = limb['lengths']['upper']
            lower_length = limb['lengths']['lower']

            # Read neckLower joint position FRESH (spine moved this frame)
            joint_pos = armature.matrix_world @ neck_lower_bone.head

            # Geometry
            joint_to_target = target_pos - joint_pos
            distance = joint_to_target.length
            max_reach = upper_length + lower_length
            min_reach = abs(upper_length - lower_length) * 0.1

            if distance <= min_reach:
                return
            if distance >= max_reach:
                distance = max_reach * 0.995

            # Bend plane normal — derived from bone direction × target direction.
            # Unlike legs (fixed forward bend), the neck must handle targets in
            # any direction relative to the joint, so we compute a fresh bend
            # normal per frame from the cross product of bone Y and target dir.
            # The bone X-axis is used only as a sign reference for consistency.
            nl_world_mat = (armature.matrix_world @ neck_lower_bone.matrix).to_3x3().normalized()
            target_dir = joint_to_target.normalized()
            nl_y = Vector(nl_world_mat.col[1]).normalized()
            bone_x = Vector(nl_world_mat.col[0]).normalized()

            bend_normal = nl_y.cross(target_dir)
            if bend_normal.length < 0.001:
                # Bone and target nearly parallel — fall back to bone X axis
                bend_normal = bone_x.copy()
            else:
                bend_normal.normalize()
                # Keep sign consistent with bone X axis
                if bend_normal.dot(bone_x) < 0:
                    bend_normal = -bend_normal

            # Law of cosines
            cos_upper_joint = (upper_length**2 + distance**2 - lower_length**2) / (2 * upper_length * distance)
            cos_upper_joint = max(-1, min(1, cos_upper_joint))
            upper_angle = math.acos(cos_upper_joint)

            rotation = Quaternion(bend_normal, upper_angle)
            neck_lower_dir = rotation @ target_dir

            # neckLower rotation
            nl_world_mat = (armature.matrix_world @ neck_lower_bone.matrix).to_3x3().normalized()
            rest_x = Vector(nl_world_mat.col[0]).normalized()
            rest_quat = nl_world_mat.to_quaternion()

            target_y = neck_lower_dir.normalized()
            target_x = bend_normal - bend_normal.dot(target_y) * target_y
            if target_x.length < 0.001:
                target_x = rest_x - rest_x.dot(target_y) * target_y
                if target_x.length < 0.001:
                    target_x = Vector((1, 0, 0))
                target_x.normalize()
            else:
                target_x.normalize()
                if target_x.dot(rest_x) < 0:
                    target_x = -target_x
            target_z = target_x.cross(target_y).normalized()

            target_mat_3x3 = Matrix((
                (target_x[0], target_y[0], target_z[0]),
                (target_x[1], target_y[1], target_z[1]),
                (target_x[2], target_y[2], target_z[2]),
            ))
            nl_rotation = rest_quat.inverted() @ target_mat_3x3.to_quaternion()

            if any(math.isnan(v) for v in nl_rotation):
                nl_rotation = Quaternion()
            neck_lower_bone.rotation_quaternion = nl_rotation
            context.view_layer.update()

            # neckUpper rotation — point toward head target
            nu_world_rest = (armature.matrix_world @ neck_upper_bone.matrix).to_3x3().normalized()
            nu_rest_quat = nu_world_rest.to_quaternion()

            actual_mid_world = armature.matrix_world @ neck_upper_bone.head
            nu_vec = target_pos - actual_mid_world
            if nu_vec.length > 0.001:
                nu_dir = nu_vec.normalized()
            else:
                nu_dir = neck_lower_dir

            nu_target_y = nu_dir
            nu_target_x = bend_normal - bend_normal.dot(nu_target_y) * nu_target_y
            if nu_target_x.length < 0.001:
                nu_target_x = target_x - target_x.dot(nu_target_y) * nu_target_y
                if nu_target_x.length < 0.001:
                    nu_target_x = Vector((1, 0, 0))
                nu_target_x.normalize()
            else:
                nu_target_x.normalize()
                if nu_target_x.dot(target_x) < 0:
                    nu_target_x = -nu_target_x
            nu_target_z = nu_target_x.cross(nu_target_y).normalized()

            nu_target_mat = Matrix((
                (nu_target_x[0], nu_target_y[0], nu_target_z[0]),
                (nu_target_x[1], nu_target_y[1], nu_target_z[1]),
                (nu_target_x[2], nu_target_y[2], nu_target_z[2]),
            ))
            nu_rotation = nu_rest_quat.inverted() @ nu_target_mat.to_quaternion()

            if any(math.isnan(v) for v in nu_rotation):
                nu_rotation = Quaternion()
            neck_upper_bone.rotation_quaternion = nu_rotation
            context.view_layer.update()

    def _solve_pinned_neck(self, context, armature, neck_state):
        """Solve spine/neck rotation compensation to maintain head's pinned world rotation.

        Called per-frame in the depsgraph handler, AFTER all compensation bones have
        been reset to identity and view_layer.update() has been called. The head's
        current world rotation reflects only the parent tilt from hip movement.

        Distributes compensating rotation bottom-up through the spine chain
        (abdomenLower → abdomenUpper → chestLower → chestUpper → neckLower),
        with neckUpper handling all remaining correction.
        """
        head_bone = neck_state['head_bone']
        chain_bones = neck_state['chain_bones']
        chain_weights = neck_state['chain_weights']
        remainder_bone = neck_state['remainder_bone']
        pinned_world_quat = neck_state['pinned_world_quat']

        # Bottom-up: each chain bone gets its weighted share of the remaining delta.
        # The correction is COMPOSED with the bone's existing rotation_quaternion
        # (which may contain user-set rotations from previous operations).
        for bone, weight in zip(chain_bones, chain_weights):
            # Read head's current world rotation
            head_world_mat = (armature.matrix_world @ head_bone.matrix).to_3x3().normalized()
            current_quat = head_world_mat.to_quaternion()

            # World-space correction needed
            delta = pinned_world_quat @ current_quat.inverted()
            if delta.dot(Quaternion()) < 0:
                delta.negate()
            if delta.angle < 0.001:
                return  # Close enough — no further correction needed

            # Apply weighted share — compose with existing local rotation
            share = Quaternion().slerp(delta, weight)
            bone_world = (armature.matrix_world @ bone.matrix).to_3x3().normalized().to_quaternion()
            target = share @ bone_world
            # Convert world-space target to local-space correction, then
            # compose with existing rotation to preserve user-set poses
            correction = bone_world.inverted() @ target
            if any(math.isnan(v) for v in correction):
                correction = Quaternion()
            bone.rotation_quaternion = correction @ bone.rotation_quaternion
            context.view_layer.update()

        # Final pass: remainder bone (neckUpper) handles everything left
        head_world_mat = (armature.matrix_world @ head_bone.matrix).to_3x3().normalized()
        current_quat = head_world_mat.to_quaternion()
        remaining = pinned_world_quat @ current_quat.inverted()
        if remaining.dot(Quaternion()) < 0:
            remaining.negate()
        if remaining.angle < 0.001:
            return

        bone_world = (armature.matrix_world @ remainder_bone.matrix).to_3x3().normalized().to_quaternion()
        target = remaining @ bone_world
        correction = bone_world.inverted() @ target
        if any(math.isnan(v) for v in correction):
            correction = Quaternion()
        remainder_bone.rotation_quaternion = correction @ remainder_bone.rotation_quaternion
        context.view_layer.update()

    def end_ik_drag(self, context, cancel=False):
        """End IK drag (or FABRIK drag) and optionally bake pose to FK

        Args:
            cancel: If True, skip keyframing (returns to original pose)
        """
        if not self._is_dragging:
            return

        if not self._drag_armature:
            print("  ⚠ end_ik_drag: armature is None, clearing drag state")
            self._is_dragging = False
            self._drag_bone_name = None
            return

        # NOTE: Hip pin IK mode is handled separately by _end_hip_pin_ik()
        # (triggered from LEFTMOUSE RELEASE / RIGHTMOUSE / ESC handlers)

        # Handle ANALYTICAL LEG IK mode
        if self._use_analytical_leg_ik:
            if cancel:
                print(f"\n=== Canceling Analytical Leg IK Drag ===")
                # Restore original rotations
                for bone_key, original_rot in self._analytical_leg_original_rotations.items():
                    bone = self._analytical_leg_bones.get(bone_key)
                    if bone:
                        bone.rotation_quaternion = original_rot
                context.view_layer.update()
            else:
                print(f"\n=== Ending Analytical Leg IK Drag ===")
                # Keyframe the rotated bones
                current_frame = context.scene.frame_current
                for bone_key, bone in self._analytical_leg_bones.items():
                    if bone:
                        bone.keyframe_insert(
                            data_path="rotation_quaternion",
                            frame=current_frame,
                            options={'INSERTKEY_VISUAL'}
                        )
                        print(f"  ✓ Keyframed: {bone.name}")

                # Undo is handled by the custom _undo_stack (pushed at drag start)

            # Restore pin constraints if we muted them at drag start
            if self._temp_unpinned_bone:
                try:
                    armature = self._drag_armature
                    bone_name = self._temp_unpinned_bone
                    pose_bone = armature.pose.bones.get(bone_name) if armature else None

                    if pose_bone:
                        if not cancel:
                            # Update pin Empty location to new bone position BEFORE re-enabling
                            new_position = armature.matrix_world @ pose_bone.head
                            for c in pose_bone.constraints:
                                if c.name == "DAZ_Pin_Translation" and c.target:
                                    c.target.location = new_position
                                    print(f"  ✓ Updated pin location to new position: {new_position}")

                            # Update stored pin data
                            data_bone = armature.data.bones.get(bone_name)
                            if data_bone and "daz_pin_location" in data_bone:
                                data_bone["daz_pin_location"] = tuple(new_position)

                            # Update rotation pin Empty to new bone orientation
                            if data_bone and "daz_pin_rotation_euler" in data_bone:
                                world_mat = armature.matrix_world @ pose_bone.matrix
                                data_bone["daz_pin_rotation_euler"] = world_mat.to_euler()
                                for c in pose_bone.constraints:
                                    if c.name == "DAZ_Pin_Rotation" and c.target:
                                        c.target.matrix_world = world_mat
                                        print(f"  ✓ Updated rotation pin to new orientation")

                        # Unmute pin constraints (always — whether cancelled or applied)
                        for c in pose_bone.constraints:
                            if c.name in ("DAZ_Pin_Translation", "DAZ_Pin_Rotation") and c.mute:
                                c.mute = False
                                print(f"  ✓ Re-enabled pin constraint: {c.name} on {bone_name}")

                except Exception as e:
                    print(f"  ⚠️  Error re-enabling pin: {e}")

                self._temp_unpinned_bone = None

            # Clean up analytical leg IK state
            self._use_analytical_leg_ik = False
            self._analytical_leg_bones = {}
            self._analytical_leg_hip_pos = None
            self._analytical_leg_lengths = {}
            self._analytical_leg_original_rotations = {}
            self._analytical_leg_side = None
            if hasattr(self, '_analytical_leg_knee_axis'):
                delattr(self, '_analytical_leg_knee_axis')
            if hasattr(self, '_analytical_leg_shin_bend_axis'):
                delattr(self, '_analytical_leg_shin_bend_axis')
            if hasattr(self, '_analytical_leg_bend_plane_normal'):
                delattr(self, '_analytical_leg_bend_plane_normal')
            if hasattr(self, '_analytical_debug_counter'):
                delattr(self, '_analytical_debug_counter')
            if hasattr(self, '_debug_frame'):
                delattr(self, '_debug_frame')
            # Keep debug draw data visible after release for screenshots
            # self._analytical_leg_debug_draw_data = {}

            # Clear drag state
            self._is_dragging = False
            self._drag_bone_name = None

            # Update header
            self._set_header(context,"DAZ Bone Select Active - P to pin | U to unpin | Alt+Shift+R to clear pose | ESC to exit")
            return  # Exit early for analytical leg IK mode

        # Handle ANALYTICAL ARM IK mode
        if self._use_analytical_arm_ik:
            if cancel:
                print(f"\n=== Canceling Analytical Arm IK Drag ===")
                for bone_key, original_rot in self._analytical_arm_original_rotations.items():
                    bone = self._analytical_arm_bones.get(bone_key)
                    if bone:
                        bone.rotation_quaternion = original_rot
                context.view_layer.update()
            else:
                print(f"\n=== Ending Analytical Arm IK Drag ===")
                current_frame = context.scene.frame_current
                for bone_key, bone in self._analytical_arm_bones.items():
                    if bone:
                        bone.keyframe_insert(
                            data_path="rotation_quaternion",
                            frame=current_frame,
                            options={'INSERTKEY_VISUAL'}
                        )
                        print(f"  ✓ Keyframed: {bone.name}")

            # Restore pin constraints if we muted them at drag start
            if self._temp_unpinned_bone:
                try:
                    armature = self._drag_armature
                    bone_name = self._temp_unpinned_bone
                    pose_bone = armature.pose.bones.get(bone_name) if armature else None

                    if pose_bone:
                        if not cancel:
                            # Update pin Empty location to new bone position BEFORE re-enabling
                            new_position = armature.matrix_world @ pose_bone.head
                            for c in pose_bone.constraints:
                                if c.name == "DAZ_Pin_Translation" and c.target:
                                    c.target.location = new_position
                                    print(f"  ✓ Updated pin location to new position: {new_position}")

                            # Update stored pin data
                            data_bone = armature.data.bones.get(bone_name)
                            if data_bone and "daz_pin_location" in data_bone:
                                data_bone["daz_pin_location"] = tuple(new_position)

                            # Update rotation pin Empty to new bone orientation
                            if data_bone and "daz_pin_rotation_euler" in data_bone:
                                world_mat = armature.matrix_world @ pose_bone.matrix
                                data_bone["daz_pin_rotation_euler"] = world_mat.to_euler()
                                for c in pose_bone.constraints:
                                    if c.name == "DAZ_Pin_Rotation" and c.target:
                                        c.target.matrix_world = world_mat
                                        print(f"  ✓ Updated rotation pin to new orientation")

                        # Unmute pin constraints (always — whether cancelled or applied)
                        for c in pose_bone.constraints:
                            if c.name in ("DAZ_Pin_Translation", "DAZ_Pin_Rotation") and c.mute:
                                c.mute = False
                                print(f"  ✓ Re-enabled pin constraint: {c.name} on {bone_name}")

                except Exception as e:
                    print(f"  ⚠️  Error re-enabling pin: {e}")

                self._temp_unpinned_bone = None

            # Clean up analytical arm IK state
            self._use_analytical_arm_ik = False
            self._analytical_arm_bones = {}
            self._analytical_arm_shoulder_pos = None
            self._analytical_arm_lengths = {}
            self._analytical_arm_original_rotations = {}
            self._analytical_arm_side = None
            if hasattr(self, '_analytical_arm_bend_plane_normal'):
                self._analytical_arm_bend_plane_normal = None
            if hasattr(self, '_arm_debug_frame'):
                delattr(self, '_arm_debug_frame')

            # Clear drag state
            self._is_dragging = False
            self._drag_bone_name = None

            self._set_header(context,"DAZ Bone Select Active - P to pin | U to unpin | Alt+Shift+R to clear pose | ESC to exit")
            return  # Exit early for analytical arm IK mode

        # Handle FABRIK mode
        if self._use_fabrik:
            if cancel:
                print(f"\n=== Canceling FABRIK Drag: {self._drag_bone_name} ===")
                # Restore original rotations
                if hasattr(self, '_fabrik_original_rotations'):
                    for bone_name, original_rot in self._fabrik_original_rotations.items():
                        pose_bone = self._drag_armature.pose.bones.get(bone_name)
                        if pose_bone:
                            pose_bone.rotation_quaternion = original_rot
                    context.view_layer.update()
            else:
                print(f"\n=== Ending FABRIK Drag: {self._drag_bone_name} ===")
                # Keyframe the rotated bones
                current_frame = context.scene.frame_current
                for bone_name in self._fabrik_chain:
                    pose_bone = self._drag_armature.pose.bones.get(bone_name)
                    if pose_bone and bone_name != self._fabrik_pinned_bone:
                        # Keyframe rotation (skip pinned bone - it doesn't move)
                        pose_bone.keyframe_insert(
                            data_path="rotation_quaternion",
                            frame=current_frame,
                            options={'INSERTKEY_VISUAL'}
                        )
                        print(f"  ✓ Keyframed: {bone_name}")

            # Re-enable Limit Rotation constraints that were muted
            for bone_name in self._fabrik_chain:
                pose_bone = self._drag_armature.pose.bones.get(bone_name)
                if pose_bone:
                    for constraint in pose_bone.constraints:
                        if constraint.type == 'LIMIT_ROTATION' and constraint.mute:
                            constraint.mute = False
                            print(f"  ✓ Re-enabled Limit Rotation on: {bone_name}")

            # Clean up FABRIK state
            self._use_fabrik = False
            self._fabrik_chain = None
            self._fabrik_pinned_bone = None
            if hasattr(self, '_fabrik_original_rotations'):
                delattr(self, '_fabrik_original_rotations')

            # Re-enable pin constraint if needed (same as normal IK)
            if self._temp_unpinned_bone:
                try:
                    armature = self._drag_armature
                    bone_name = self._temp_unpinned_bone
                    pose_bone = armature.pose.bones.get(bone_name) if armature else None

                    if pose_bone:
                        # CRITICAL: Update pin Empty location to new bone position BEFORE re-enabling
                        new_position = armature.matrix_world @ pose_bone.head

                        for c in pose_bone.constraints:
                            if c.name == "DAZ_Pin_Translation" and c.target:
                                # Update the pin Empty's location to the new position
                                c.target.location = new_position
                                print(f"  ✓ Updated pin location to new position: {new_position}")

                        # Update rotation pin Empty to new bone orientation
                        data_bone = armature.data.bones.get(bone_name)
                        if data_bone and "daz_pin_rotation_euler" in data_bone:
                            world_mat = armature.matrix_world @ pose_bone.matrix
                            data_bone["daz_pin_rotation_euler"] = world_mat.to_euler()
                            for c in pose_bone.constraints:
                                if c.name == "DAZ_Pin_Rotation" and c.target:
                                    c.target.matrix_world = world_mat
                                    print(f"  ✓ Updated rotation pin to new orientation")

                        # Now unmute pin constraints
                        for c in pose_bone.constraints:
                            if c.name in ("DAZ_Pin_Translation", "DAZ_Pin_Rotation") and c.mute:
                                c.mute = False
                                print(f"  ✓ Re-enabled pin constraint on: {bone_name}")

                except Exception as e:
                    print(f"  ⚠️  Error re-enabling pin: {e}")

                # Always clear temp data
                self._temp_unpinned_bone = None
                self._temp_unpinned_data = None

            # Clear drag state
            self._is_dragging = False
            self._drag_bone_name = None
            return  # Exit early for FABRIK mode

        # Normal IK mode continues here
        if cancel:
            print(f"\n=== Canceling IK Drag: {self._drag_bone_name} ===")
        else:
            print(f"\n=== Ending IK Drag: {self._drag_bone_name} ===")

        # Dissolve IK chain (remove constraints, delete .ik bones)
        # Pass keyframe=False if canceling to skip baking
        # Skip dissolve if in debug mode to allow inspection
        if not DEBUG_PRESERVE_IK_CHAIN:
            dissolve_ik_chain(
                self._drag_armature,
                self._ik_target_bone_name,
                self._ik_control_bone_names,
                self._ik_daz_bone_names,
                self._shoulder_target_names,
                keyframe=(not cancel),
                swing_twist_pairs=getattr(self, '_swing_twist_pairs', None)
            )
        else:
            print("  [DEBUG] IK chain preserved for inspection - constraints and .ik bones left intact")

        # Re-enable pin constraint if it was temporarily muted
        if self._temp_unpinned_bone:
            try:
                armature = self._drag_armature
                bone_name = self._temp_unpinned_bone
                pose_bone = armature.pose.bones.get(bone_name) if armature else None

                if pose_bone:
                    # CRITICAL: Update pin Empty location to new bone position BEFORE re-enabling
                    # This allows the pin to follow the drag (Option A behavior)
                    new_position = armature.matrix_world @ pose_bone.head

                    for c in pose_bone.constraints:
                        if c.name == "DAZ_Pin_Translation" and c.target:
                            # Update the pin Empty's location to the new position
                            c.target.location = new_position
                            print(f"  ✓ Updated pin location to new position: {new_position}")

                    # Update rotation pin Empty to new bone orientation
                    data_bone = armature.data.bones.get(bone_name)
                    if data_bone and "daz_pin_rotation_euler" in data_bone:
                        world_mat = armature.matrix_world @ pose_bone.matrix
                        data_bone["daz_pin_rotation_euler"] = world_mat.to_euler()
                        for c in pose_bone.constraints:
                            if c.name == "DAZ_Pin_Rotation" and c.target:
                                c.target.matrix_world = world_mat
                                print(f"  ✓ Updated rotation pin to new orientation")

                    # Now unmute pin constraints
                    for c in pose_bone.constraints:
                        if c.name in ("DAZ_Pin_Translation", "DAZ_Pin_Rotation") and c.mute:
                            c.mute = False
                            print(f"  ✓ Re-enabled pin constraint on: {bone_name}")

            except Exception as e:
                print(f"  ⚠️  Error re-enabling pin: {e}")

            # Always clear temp data
            self._temp_unpinned_bone = None
            self._temp_unpinned_data = None

        # Re-enable soft pin constraints that were muted
        if hasattr(self, '_soft_pin_muted_constraints') and self._soft_pin_muted_constraints:
            for pose_bone, constraint in self._soft_pin_muted_constraints:
                constraint.mute = False
                print(f"  ✓ Re-enabled hard pin constraint on: {pose_bone.name}")
            self._soft_pin_muted_constraints = []

        # Clear soft pin state
        self._soft_pin_active = False
        self._soft_pin_child_name = None
        self._soft_pin_initial_pos = None

        # Restore IK limits if we locked them during straightening
        if getattr(self, '_straighten_lock_active', False):
            try:
                # Find the shin/middle bone and restore its original IK max
                for bone_name in self._ik_control_bone_names:
                    if 'shin' in bone_name.lower() or 'calf' in bone_name.lower():
                        pose_bone = self._drag_armature.pose.bones.get(bone_name)
                        if pose_bone and hasattr(self, '_straighten_original_ik_max_x'):
                            pose_bone.ik_max_x = self._straighten_original_ik_max_x
                            print(f"  ✓ Restored shin IK max to {math.degrees(self._straighten_original_ik_max_x):.1f}°")
                        break
            except Exception as e:
                print(f"  ⚠️  Error restoring IK limits: {e}")
            self._straighten_lock_active = False
            if hasattr(self, '_straighten_original_ik_max_x'):
                delattr(self, '_straighten_original_ik_max_x')

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
        self._accumulated_drag_distance = 0.0
        self._last_detection_mouse_pos = None

        # Update header
        self._set_header(context,"DAZ Bone Select Active - P to pin | U to unpin | Alt+Shift+R to clear pose | ESC to exit")

    def clamp_rotation_to_constraints(self, bone, rotation_quat):
        """
        Clamp a rotation quaternion to respect LIMIT_ROTATION constraints on the bone.
        Returns the clamped quaternion.
        """
        # Check if bone has LIMIT_ROTATION constraints
        limit_constraint = None
        for constraint in bone.constraints:
            if constraint.type == 'LIMIT_ROTATION' and not constraint.mute:
                limit_constraint = constraint
                break

        if not limit_constraint:
            # No rotation limits, return unchanged
            return rotation_quat

        # Convert quaternion to Euler angles using the bone's rotation mode
        # LIMIT_ROTATION works in Euler space
        if bone.rotation_mode == 'QUATERNION':
            euler = rotation_quat.to_euler('XYZ')
        else:
            # Use the bone's rotation mode
            euler = rotation_quat.to_euler(bone.rotation_mode)

        # Clamp each axis if the limit is enabled
        if limit_constraint.use_limit_x:
            if euler.x < limit_constraint.min_x:
                euler.x = limit_constraint.min_x
            elif euler.x > limit_constraint.max_x:
                euler.x = limit_constraint.max_x

        if limit_constraint.use_limit_y:
            if euler.y < limit_constraint.min_y:
                euler.y = limit_constraint.min_y
            elif euler.y > limit_constraint.max_y:
                euler.y = limit_constraint.max_y

        if limit_constraint.use_limit_z:
            if euler.z < limit_constraint.min_z:
                euler.z = limit_constraint.min_z
            elif euler.z > limit_constraint.max_z:
                euler.z = limit_constraint.max_z

        # Convert back to quaternion
        return euler.to_quaternion()

    def _apply_rotation_neck_compensation(self, context):
        """Apply neck compensation during rotation if head has rotation pin.

        Called at the end of each rotation frame. On first call, detects the
        head rotation pin, mutes the constraint, and stores neck originals.
        On every call, resets neck bones and runs the neck solver.
        """
        armature = self._drag_armature
        if not armature:
            return

        # First-call setup
        if self._rotation_neck_state is None:
            neck_state = self._find_pinned_head(armature)
            if neck_state is None:
                # Mark as checked-and-not-needed (use False to distinguish from None)
                self._rotation_neck_state = False
                return
            self._rotation_neck_state = neck_state

            # Store original spine/neck rotations for cancel
            self._rotation_neck_originals = {}
            for bone in neck_state['all_bones']:
                self._rotation_neck_originals[bone.name] = bone.rotation_quaternion.copy()

            # Mute head's rotation pin constraint (solver handles it)
            self._rotation_neck_muted = []
            head_pose = neck_state['head_bone']
            for c in head_pose.constraints:
                if c.name == "DAZ_Pin_Rotation" and not c.mute:
                    c.mute = True
                    self._rotation_neck_muted.append((head_pose, c))
                    print(f"  [NECK ROT] Muted head rotation pin for neck solver")

        if self._rotation_neck_state is False:
            return

        neck_state = self._rotation_neck_state

        # Reset spine/neck bones to identity
        for bone in neck_state['all_bones']:
            bone.rotation_quaternion = Quaternion()

        context.view_layer.update()

        # Run spine/neck solver
        self._solve_pinned_neck(context, armature, neck_state)

    def _apply_rotation_pin_ik(self, context):
        """Apply analytical IK to keep translation-pinned limbs in place during rotation.

        Called at the end of each rotation frame when the rotated bone is a
        root/torso bone that moves the feet/hands. Mirrors the neck compensation
        pattern: mutes COPY_LOCATION constraints, resets limb bones, solves IK.
        Only activates when at least one limb endpoint has a translation pin.
        """
        armature = self._drag_armature
        if not armature:
            return

        # First-call setup — determine if we need limb IK compensation
        if self._rotation_pin_limb_state is None:
            # Only compensate when rotating the hip (root) or torso chain bones,
            # since those are the only bones whose rotation displaces feet/hands.
            bone = self._rotation_bone
            if bone is None:
                # Multi-bone group — check if any bone is a root/torso bone
                is_torso_rotation = False
                if self._rotation_bones:
                    spine_chain_names = [name for name, _ in self.SPINE_CHAIN_DEF]
                    for b in self._rotation_bones:
                        b_lower = b.name.lower()
                        if not b.parent or b.name in spine_chain_names or any(
                            part in b_lower for part in ['chest', 'abdomen', 'pelvis', 'hip']
                        ):
                            is_torso_rotation = True
                            break
            else:
                bone_lower = bone.name.lower()
                spine_chain_names = [name for name, _ in self.SPINE_CHAIN_DEF]
                is_torso_rotation = (
                    not bone.parent or
                    bone.name in spine_chain_names or
                    any(part in bone_lower for part in ['chest', 'abdomen', 'pelvis', 'hip'])
                )

            if not is_torso_rotation:
                self._rotation_pin_limb_state = False
                return

            # Find pinned limbs
            pinned_limbs = self._find_pinned_limbs(armature)
            if not pinned_limbs:
                self._rotation_pin_limb_state = False
                return

            # Store original rotations of all limb bones (for cancel/restore)
            self._rotation_pin_limb_originals = {}
            for limb in pinned_limbs:
                for role, b in limb['bones'].items():
                    if b and b.name not in self._rotation_pin_limb_originals:
                        self._rotation_pin_limb_originals[b.name] = b.rotation_quaternion.copy()

            # Mute translation pin constraints on endpoints so IK solver controls position
            self._rotation_pin_limb_muted = []
            for limb in pinned_limbs:
                ep = armature.pose.bones.get(limb['endpoint_name'])
                if ep:
                    for c in ep.constraints:
                        if c.name == "DAZ_Pin_Translation" and not c.mute:
                            c.mute = True
                            self._rotation_pin_limb_muted.append((ep, c))
                            print(f"  [PIN IK ROT] Muted translation pin on {ep.name}")

            self._rotation_pin_limb_state = pinned_limbs
            print(f"  [PIN IK ROT] Activated for {len(pinned_limbs)} pinned limb(s)")

        if self._rotation_pin_limb_state is False:
            return

        pinned_limbs = self._rotation_pin_limb_state

        # Reset all limb bones to their drag-start rotations (clean IK baseline)
        if hasattr(self, '_rotation_pin_limb_originals'):
            for limb in pinned_limbs:
                for role, b in limb['bones'].items():
                    if b:
                        orig = self._rotation_pin_limb_originals.get(b.name)
                        if orig is not None:
                            b.rotation_quaternion = orig.copy()
                        else:
                            b.rotation_quaternion = Quaternion()

        context.view_layer.update()

        # Solve IK for each pinned limb
        for limb in pinned_limbs:
            self._solve_pinned_limb(context, armature, limb)

    def update_rotation(self, context, event):
        """Update bone rotation during drag (for pectoral bones)"""
        # Check if we're rotating (either single bone or multi-bone group)
        if not self._is_rotating:
            return

        # Handle multi-bone group rotation
        if self._rotation_bones and len(self._rotation_bones) > 0:
            self.update_multi_bone_rotation(context, event)
            return

        # Handle single bone rotation
        if not self._rotation_bone:
            return

        # If using Track To constraint method, move the empty instead
        if self._rotation_target_empty:
            # Get viewport info (cross-viewport safe)
            region, rv3d, mouse_coord = self._get_region_rv3d(context, event)

            if region and rv3d:

                # Get bone head position in world space (rotation pivot point)
                bone_head_world = self._drag_armature.matrix_world @ self._rotation_bone.head

                # Project mouse position onto a plane at the bone's depth
                # This makes the empty follow the mouse smoothly on screen
                target_pos = view3d_utils.region_2d_to_location_3d(
                    region,
                    rv3d,
                    mouse_coord,
                    bone_head_world  # Use bone position as depth reference
                )

                # Move empty to target position
                self._rotation_target_empty.location = target_pos

                # Update viewport
                context.view_layer.update()
                if context.area: context.area.tag_redraw()
            return

        # Calculate mouse delta
        delta_x = event.mouse_x - self._rotation_initial_mouse[0]
        delta_y = event.mouse_y - self._rotation_initial_mouse[1]

        # Track right-click drag for menu suppression (only if actual movement occurred)
        if self._rotation_mouse_button == 'RIGHT' and not self._right_click_used_for_drag:
            # Set flag if we've moved at least 3 pixels in any direction
            if abs(delta_x) > 3 or abs(delta_y) > 3:
                self._right_click_used_for_drag = True

        # POSEBRIDGE MODE: Multi-axis simultaneous rotation for natural posing
        if hasattr(context.scene, 'posebridge_settings') and context.scene.posebridge_settings.is_active:
            # Get PoseBridge sensitivity setting (default 0.01 if not set)
            sensitivity = getattr(context.scene.posebridge_settings, 'sensitivity', 0.01)

            bone_lower = self._rotation_bone.name.lower()
            horiz_axis = None  # Axis for horizontal drag
            vert_axis = None   # Axis for vertical drag
            horiz_invert = False  # Invert horizontal direction
            vert_invert = False   # Invert vertical direction
            horiz_armature_space = False  # Use armature-space for horizontal (default: local)
            vert_armature_space = False   # Use armature-space for vertical (default: local)

            # HEAD
            if 'head' in bone_lower:
                if self._rotation_mouse_button == 'LEFT':
                    horiz_axis = 'Y'  # Turn
                    vert_axis = 'X'   # Nod
                    vert_invert = True  # Invert vertical direction
                else:  # RIGHT
                    horiz_axis = 'Z'  # Side tilt
                    horiz_invert = True  # Invert direction per user testing
                    vert_axis = 'X'   # Fine forward/back
                    vert_invert = True  # Invert vertical direction

            # NECK
            elif 'neck' in bone_lower:
                if self._rotation_mouse_button == 'LEFT':
                    horiz_axis = 'Y'  # Rotate
                    vert_axis = 'X'   # Bend
                    vert_invert = True  # Invert vertical direction
                else:  # RIGHT
                    horiz_axis = 'Z'  # Side bend (tilt)
                    horiz_invert = True  # Invert direction per user testing
                    vert_axis = 'X'  # Fine forward/back (same as head)
                    vert_invert = True  # Invert vertical direction

            # TORSO
            elif any(part in bone_lower for part in ['chest', 'abdomen', 'pelvis']):
                if self._rotation_mouse_button == 'LEFT':
                    horiz_axis = 'Y'  # Twist
                    vert_axis = 'X'   # Bend
                    vert_invert = True
                    if 'pelvis' in bone_lower:
                        vert_invert = False
                else:  # RIGHT
                    horiz_axis = 'Z'  # Side lean
                    horiz_invert = True  # Invert direction per user testing
                    vert_axis = 'Y'   # Alt twist

            # COLLAR
            elif 'collar' in bone_lower:
                if self._rotation_mouse_button == 'LEFT':
                    horiz_axis = 'Z'  # Shrug/drop
                    vert_axis = 'X'   # Forward/back
                else:  # RIGHT
                    horiz_axis = None  # Removed per user testing
                    vert_axis = 'Y'   # Twist (changed from None per user testing)
                    if self._rotation_bone.name.startswith('l'):
                        vert_invert = True

            # UPPER ARM (Shoulder)
            elif 'shldr' in bone_lower or 'shoulder' in bone_lower:
                print(f"[DEBUG] Shoulder detected! Bone: {self._rotation_bone.name}, Button: {self._rotation_mouse_button}")
                if self._rotation_mouse_button == 'LEFT':
                    horiz_axis = 'X'  # Swing forward/back (horizontal drag)
                    vert_axis = 'Z'   # Raise/lower (vertical drag)
                    horiz_invert = True  # Invert horizontal direction
                    print(f"[DEBUG] LMB shoulder: horiz_axis={horiz_axis}, vert_axis={vert_axis}, horiz_invert={horiz_invert}")
                else:  # RIGHT
                    horiz_axis = None  # No horizontal control
                    vert_axis = 'Y'   # Twist (vertical drag)
                    vert_invert = True  # Invert twist direction
                    print(f"[DEBUG] RMB shoulder: horiz_axis={horiz_axis}, vert_axis={vert_axis}")

            # FOREARM (Elbow)
            elif 'forearm' in bone_lower or 'lorearm' in bone_lower:
                if self._rotation_mouse_button == 'LEFT':
                    horiz_axis = 'X'  # Bend elbow
                    vert_axis = 'Y'   # Twist (targets forearmTwist bone)
                    horiz_invert = True  # Invert horizontal bend direction
                    vert_invert = True  # Invert twist direction
                else:  # RIGHT
                    horiz_axis = None
                    vert_axis = None

            # HAND
            elif 'hand' in bone_lower:
                if self._rotation_mouse_button == 'LEFT':
                    horiz_axis = 'Y'  # Twist
                    vert_axis = 'Z'   # Up/down
                    horiz_invert = True  # Invert twist direction
                else:  # RIGHT
                    horiz_axis = 'X'  # Side-to-side
                    horiz_invert = True
                    vert_axis = 'Z'   # Up/down

            # THIGH
            # Uses armature-space for spread/forward-back so movements are consistent
            # regardless of current pose. Twist stays local (along bone length).
            elif 'thigh' in bone_lower:
                if self._rotation_mouse_button == 'LEFT':
                    horiz_axis = 'Y'  # Twist (targets ThighTwist bone)
                    horiz_invert = True  # Invert twist direction
                    horiz_armature_space = False  # Twist is LOCAL (around bone length)
                    vert_axis = 'X'   # Swing forward/back (targets ThighBend bone)
                    vert_invert = True  # Invert forward/back direction
                    vert_armature_space = False  # LOCAL space - simpler behavior
                else:  # RIGHT
                    horiz_axis = 'Z'  # Side-to-side spread (bone-local Z)
                    horiz_invert = True  # Inverted for correct spread direction
                    horiz_armature_space = False  # LOCAL space - simpler, adapts to pose
                    vert_axis = 'X'   # Forward/back
                    vert_invert = True  # Invert direction
                    vert_armature_space = False  # LOCAL space

            # SHIN (Knee)
            elif 'shin' in bone_lower or 'knee' in bone_lower:
                if self._rotation_mouse_button == 'LEFT':
                    horiz_axis = None
                    vert_axis = 'X'   # Bend knee
                    vert_invert = True
                else:  # RIGHT
                    horiz_axis = 'Y'  # Twist
                    vert_axis = None

            # FINGER (Thumb, Index, Mid, Ring, Pinky)
            elif any(part in bone_lower for part in ['thumb', 'index', 'mid', 'ring', 'pinky']):
                is_base_joint = self._rotation_bone.name[-1] == '1'
                is_left_finger = self._rotation_bone.name.startswith('l')
                if self._rotation_mouse_button == 'LEFT':
                    horiz_axis = 'Z' if is_base_joint else None  # Spread only on base joint
                    vert_axis = 'X'   # Curl
                    vert_invert = is_left_finger  # Left: drag down = curl closed; right-side mirror handles rHand
                else:  # RIGHT
                    horiz_axis = 'Y' if is_base_joint else None  # Twist only on base joint
                    if is_base_joint and 'thumb' in bone_lower:
                        horiz_invert = True
                    vert_axis = 'X'   # Curl only
                    vert_invert = is_left_finger  # Left: drag down = curl closed; right-side mirror handles rHand

            # FOOT
            elif 'foot' in bone_lower:
                if self._rotation_mouse_button == 'LEFT':
                    horiz_axis = 'Z'  # Tilt side-to-side
                    vert_axis = 'X'   # Point/flex
                else:  # RIGHT
                    horiz_axis = 'Y'  # Twist
                    vert_axis = None

            # MIRROR FOR RIGHT SIDE: Invert all controls for right-side bones
            # User configures controls for left side, right side mirrors them
            # (collar/shin/thigh excluded — DAZ bone local axes are oriented so both sides use the same inversions)
            if self._rotation_bone.name.startswith('r') and 'collar' not in bone_lower and 'shin' not in bone_lower and 'thigh' not in bone_lower:
                horiz_invert = not horiz_invert
                vert_invert = not vert_invert

            # Check if we need to use an alternate bone for horizontal/vertical rotation
            # (e.g., shoulder/forearm/thigh twist bones)
            horiz_target_bone = self._rotation_bone
            vert_target_bone = self._rotation_bone

            # Initialize twist bone quaternion storage if needed
            if not hasattr(self, '_twist_bone_initial_quats'):
                self._twist_bone_initial_quats = {}

            # Shoulder RMB vertical → shldrTwist bone
            if (vert_axis == 'Y' and
                self._rotation_mouse_button == 'RIGHT' and
                ('shldr' in bone_lower or 'shoulder' in bone_lower) and
                'bend' in bone_lower):
                twist_bone_name = self._rotation_bone.name.replace('Bend', 'Twist')
                if twist_bone_name in self._drag_armature.pose.bones:
                    vert_target_bone = self._drag_armature.pose.bones[twist_bone_name]
                    if twist_bone_name not in self._twist_bone_initial_quats:
                        self._twist_bone_initial_quats[twist_bone_name] = vert_target_bone.rotation_quaternion.copy()

            # Forearm LMB vertical → forearmTwist bone
            elif (vert_axis == 'Y' and
                  self._rotation_mouse_button == 'LEFT' and
                  ('forearm' in bone_lower or 'lorearm' in bone_lower) and
                  'bend' in bone_lower):
                twist_bone_name = self._rotation_bone.name.replace('Bend', 'Twist')
                if twist_bone_name in self._drag_armature.pose.bones:
                    vert_target_bone = self._drag_armature.pose.bones[twist_bone_name]
                    if twist_bone_name not in self._twist_bone_initial_quats:
                        self._twist_bone_initial_quats[twist_bone_name] = vert_target_bone.rotation_quaternion.copy()

            # Thigh LMB horizontal Y axis → thighTwist bone
            elif (horiz_axis == 'Y' and
                  self._rotation_mouse_button == 'LEFT' and
                  'thigh' in bone_lower and
                  'bend' in bone_lower):
                twist_bone_name = self._rotation_bone.name.replace('Bend', 'Twist')
                if twist_bone_name in self._drag_armature.pose.bones:
                    horiz_target_bone = self._drag_armature.pose.bones[twist_bone_name]
                    if twist_bone_name not in self._twist_bone_initial_quats:
                        self._twist_bone_initial_quats[twist_bone_name] = horiz_target_bone.rotation_quaternion.copy()

            # Apply rotations - horizontal and vertical axes simultaneously
            # Use a working copy to compose rotations without modifying the stored initial quat
            current_quat = self._rotation_initial_quat.copy()

            # Debug output for shoulder
            if 'shldr' in bone_lower or 'shoulder' in bone_lower:
                print(f"[DEBUG] About to apply rotation: delta_x={delta_x:.2f}, delta_y={delta_y:.2f}, horiz_axis={horiz_axis}, vert_axis={vert_axis}")

            # Debug output for thigh - track gimbal lock issue
            if 'thigh' in bone_lower:
                print(f"\n[THIGH DEBUG] {self._rotation_bone.name}")
                print(f"  Mouse Button: {self._rotation_mouse_button}")
                print(f"  Delta: x={delta_x:.2f}, y={delta_y:.2f}")
                print(f"  Axes: horiz={horiz_axis}, vert={vert_axis}")
                print(f"  Target Bones: horiz={horiz_target_bone.name}, vert={vert_target_bone.name}")
                print(f"  Inverted: horiz={horiz_invert}, vert={vert_invert}")
                print(f"  Initial Quat: {self._rotation_initial_quat}")
                print(f"  Current Quat: {self._rotation_bone.rotation_quaternion}")

            # Save current quaternions BEFORE applying rotation (for continuity check)
            previous_quat = self._rotation_bone.rotation_quaternion.copy()
            previous_twist_quats = {}
            if horiz_target_bone != self._rotation_bone:
                previous_twist_quats[horiz_target_bone.name] = horiz_target_bone.rotation_quaternion.copy()
            if vert_target_bone != self._rotation_bone and vert_target_bone.name not in previous_twist_quats:
                previous_twist_quats[vert_target_bone.name] = vert_target_bone.rotation_quaternion.copy()

            # Check if both axes target the same bone (need combined rotation)
            same_target = (horiz_target_bone == vert_target_bone)

            if same_target and horiz_target_bone == self._rotation_bone:
                # COMBINED ROTATION: Both axes target the main bone
                # Build combined rotation quaternion and apply once
                combined_rot = Quaternion()  # Identity

                # Get bone's rest quaternion for armature-space transformations (conjugation)
                rest_matrix = self._rotation_bone.bone.matrix_local.to_3x3()
                rest_quat = rest_matrix.to_quaternion()

                # Add horizontal axis rotation
                if horiz_axis is not None and abs(delta_x) > 0:
                    effective_delta_x = -delta_x if horiz_invert else delta_x
                    angle_h = effective_delta_x * sensitivity
                    armature_axis_h = Vector((
                        1 if horiz_axis == 'X' else 0,
                        1 if horiz_axis == 'Y' else 0,
                        1 if horiz_axis == 'Z' else 0
                    ))
                    # For armature-space: use conjugation to transform rotation properly
                    if horiz_armature_space:
                        R_armature_h = Quaternion(armature_axis_h, angle_h)
                        rot_h = rest_quat.inverted() @ R_armature_h @ rest_quat
                    else:
                        rot_h = Quaternion(armature_axis_h, angle_h)
                    combined_rot = rot_h @ combined_rot

                # Add vertical axis rotation
                if vert_axis is not None and abs(delta_y) > 0:
                    effective_delta_y = -delta_y if vert_invert else delta_y
                    angle_v = effective_delta_y * sensitivity
                    armature_axis_v = Vector((
                        1 if vert_axis == 'X' else 0,
                        1 if vert_axis == 'Y' else 0,
                        1 if vert_axis == 'Z' else 0
                    ))
                    # For armature-space: use conjugation to transform rotation properly
                    if vert_armature_space:
                        R_armature_v = Quaternion(armature_axis_v, angle_v)
                        rot_v = rest_quat.inverted() @ R_armature_v @ rest_quat
                    else:
                        rot_v = Quaternion(armature_axis_v, angle_v)
                    combined_rot = rot_v @ combined_rot

                # Apply combined rotation to initial
                if ('thigh' in bone_lower and 'bend' in bone_lower) or 'shldr' in bone_lower or 'shoulder' in bone_lower or 'collar' in bone_lower:
                    # Post-multiply: rotate in bone's LOCAL frame so axes
                    # stay aligned regardless of current pose.
                    self._rotation_bone.rotation_quaternion = self._rotation_initial_quat @ combined_rot
                else:
                    self._rotation_bone.rotation_quaternion = combined_rot @ self._rotation_initial_quat
            else:
                # SEPARATE ROTATIONS: Axes target different bones

                # Apply horizontal axis rotation (responds to horizontal mouse drag)
                if horiz_axis is not None and abs(delta_x) > 0:
                    target_bone = horiz_target_bone
                    if target_bone != self._rotation_bone and target_bone.name in self._twist_bone_initial_quats:
                        # Horizontal targets a different bone (e.g., twist bone) - use its initial rotation
                        horiz_current_quat = self._twist_bone_initial_quats[target_bone.name].copy()
                    else:
                        # Horizontal targets the main bone - ALWAYS use the drag-start initial rotation
                        horiz_current_quat = self._rotation_initial_quat.copy()

                    effective_delta_x = -delta_x if horiz_invert else delta_x
                    apply_rotation_from_delta(
                        target_bone,
                        horiz_current_quat,
                        horiz_axis,
                        effective_delta_x,
                        sensitivity,
                        use_armature_space=horiz_armature_space
                    )

                    # Quaternion continuity fix for horizontal rotation target
                    if target_bone != self._rotation_bone and target_bone.name in previous_twist_quats:
                        new_quat = target_bone.rotation_quaternion.copy()
                        prev_quat = previous_twist_quats[target_bone.name]
                        new_quat.make_compatible(prev_quat)
                        target_bone.rotation_quaternion = new_quat

                # Apply vertical axis rotation (responds to vertical mouse drag)
                if vert_axis is not None and abs(delta_y) > 0:
                    target_bone = vert_target_bone
                    if target_bone != self._rotation_bone and target_bone.name in self._twist_bone_initial_quats:
                        # Vertical targets a different bone (e.g., twist bone) - use its initial rotation
                        vert_current_quat = self._twist_bone_initial_quats[target_bone.name].copy()
                    else:
                        # Vertical targets the main bone - ALWAYS use the drag-start initial rotation
                        vert_current_quat = self._rotation_initial_quat.copy()

                    effective_delta_y = -delta_y if vert_invert else delta_y
                    apply_rotation_from_delta(
                        target_bone,
                        vert_current_quat,
                        vert_axis,
                        effective_delta_y,
                        sensitivity,
                        use_armature_space=vert_armature_space
                    )

                    # Quaternion continuity fix for vertical rotation target
                    if target_bone != self._rotation_bone and target_bone.name in previous_twist_quats:
                        new_quat = target_bone.rotation_quaternion.copy()
                        prev_quat = previous_twist_quats[target_bone.name]
                        new_quat.make_compatible(prev_quat)
                        target_bone.rotation_quaternion = new_quat

            # Quaternion continuity fix: ensure we stay on the same "side" of quaternion sphere
            # This prevents sudden flips when crossing ±180° rotation
            # Use make_compatible() to automatically choose the quaternion representation closest to previous frame
            new_quat = self._rotation_bone.rotation_quaternion.copy()
            original_w = new_quat.w
            new_quat.make_compatible(previous_quat)
            self._rotation_bone.rotation_quaternion = new_quat
            if 'thigh' in bone_lower and abs(new_quat.w - original_w) > 0.01:
                print(f"  [CONTINUITY FIX] Adjusted quaternion to maintain continuity (w: {original_w:.4f} → {new_quat.w:.4f})")

            # Y-LOCK for ThighBend
            # ThighBend should NEVER have Y rotation - only X (forward/back) and Z (spread)
            # Any Y component from gimbal effects is simply removed, not transferred
            if 'thigh' in bone_lower and 'bend' in bone_lower:
                # Decompose current rotation into swing (X/Z) and twist (Y)
                current_quat = self._rotation_bone.rotation_quaternion.copy()
                swing_quat, twist_quat = decompose_swing_twist(current_quat, 'Y')

                # Keep ONLY the swing component (Y-locked)
                self._rotation_bone.rotation_quaternion = swing_quat

                # Debug: show if we removed any Y rotation
                twist_angle = 2.0 * math.acos(min(1.0, abs(twist_quat.w)))
                if twist_angle > 0.01:  # Only log if > 0.5 degrees
                    print(f"  [Y-LOCK] Removed {math.degrees(twist_angle):.1f} deg Y rotation from {self._rotation_bone.name}")

            # Debug output for thigh - show final rotation after application
            if 'thigh' in bone_lower:
                print(f"  Final Quat: {self._rotation_bone.rotation_quaternion}")
                # Convert to euler for easier interpretation
                euler = self._rotation_bone.rotation_quaternion.to_euler('XYZ')
                print(f"  Final Euler (deg): X={math.degrees(euler.x):.1f}, Y={math.degrees(euler.y):.1f}, Z={math.degrees(euler.z):.1f}")

            # Update view layer to evaluate constraints (if enabled)
            if getattr(context.scene.posebridge_settings, 'enforce_constraints', True):
                context.view_layer.update()
        else:
            # Original pectoral bone rotation logic
            # Apply rotation based on mouse movement (sensitivity: 0.01 radians/pixel)
            sensitivity = 0.01

            # Get viewport orientation to make rotation follow mouse regardless of armature rotation
            # Cross-viewport safe: use _get_region_rv3d to find correct viewport
            _, rv3d, _ = self._get_region_rv3d(context, event)

            if rv3d:
                # Simple approach that works for normal armature orientation
                # Get view matrix for screen-space calculations
                view_matrix = rv3d.view_matrix

                # Extract view axes (screen-aligned in world space)
                view_right = Vector(view_matrix[0][:3])  # Screen horizontal axis
                view_up = Vector(view_matrix[1][:3])     # Screen vertical axis

                # Calculate rotation angles
                angle_horizontal = delta_x * sensitivity  # Mouse horizontal movement
                angle_vertical = delta_y * sensitivity    # Mouse vertical movement

                # Create rotations around screen-aligned axes
                rot_h = Quaternion(view_up, angle_horizontal)
                rot_v = Quaternion(view_right, angle_vertical)
                combined_rot_world = rot_h @ rot_v

                # Get armature
                armature = self._drag_armature
                if armature and self._rotation_parent_frame_quat:
                    # Use cached parent frame for correct world-to-local conversion.
                    # parent_frame includes armature world + parent chain + rest offset.
                    # bone_world = parent_frame @ rotation_quaternion
                    parent_frame = self._rotation_parent_frame_quat
                    initial_world_quat = parent_frame @ self._rotation_initial_quat

                    # Apply screen rotation in world space
                    new_world_quat = combined_rot_world @ initial_world_quat

                    # Convert back to bone local space
                    new_local_quat = parent_frame.inverted() @ new_world_quat

                    # Apply to bone
                    self._rotation_bone.rotation_quaternion = new_local_quat
                else:
                    # Fallback if no armature or parent frame
                    self._rotation_bone.rotation_quaternion = combined_rot_world @ self._rotation_initial_quat
            else:
                # Fallback to old method if no 3D view (shouldn't happen)
                angle_z = delta_x * sensitivity
                angle_x = delta_y * sensitivity
                rot_z = Quaternion(Vector((0, 0, 1)), angle_z)
                rot_x = Quaternion(Vector((1, 0, 0)), angle_x)
                combined_rot = rot_z @ rot_x
                self._rotation_bone.rotation_quaternion = combined_rot @ self._rotation_initial_quat

        # Neck compensation for rotation-pinned head
        self._apply_rotation_neck_compensation(context)

        # Limb IK compensation for translation-pinned feet/hands during torso/hip rotation
        self._apply_rotation_pin_ik(context)

        # Update viewport
        if context.area: context.area.tag_redraw()
        refresh_3d_viewports(context)

    def update_multi_bone_rotation(self, context, event):
        """Update multiple bones rotation during drag (Individual Origins behavior)"""
        # Calculate mouse delta
        delta_x = event.mouse_x - self._rotation_initial_mouse[0]
        delta_y = event.mouse_y - self._rotation_initial_mouse[1]

        # POSEBRIDGE MODE: Apply same rotation to all bones
        if hasattr(context.scene, 'posebridge_settings') and context.scene.posebridge_settings.is_active:
            # Get PoseBridge sensitivity setting
            sensitivity = getattr(context.scene.posebridge_settings, 'sensitivity', 0.01)

            # DATA-DRIVEN group axis mapping from controls dict (cached at drag start)
            # Each entry is None or (axis, inverted) — single source of truth in daz_shared_utils.py
            controls = getattr(self, '_rotation_group_controls', None) or {}

            # Check for delegate mode: group_delegates replaces controls for complex groups
            # (e.g. leg groups). Delegates reference single-bone node controls directly,
            # so no bone_overrides or mirror_axes hacks are needed.
            group_delegates = controls.get('group_delegates')

            if group_delegates:
                # ================================================================
                # DELEGATE MODE
                # Each gesture maps to a list of (node_id, gesture_key) tuples.
                # We look up the referenced node's axis/invert, build per-bone
                # rotation quaternions, then apply with twist filtering and Y-lock.
                # ================================================================
                from daz_shared_utils import get_control_point_by_id

                horiz_key = 'lmb_horiz' if self._rotation_mouse_button == 'LEFT' else 'rmb_horiz'
                vert_key  = 'lmb_vert'  if self._rotation_mouse_button == 'LEFT' else 'rmb_vert'

                axis_vecs = {'X': Vector((1, 0, 0)), 'Y': Vector((0, 1, 0)), 'Z': Vector((0, 0, 1))}

                # Build bone_name → (axis, Quaternion) maps for horiz and vert gestures.
                # Separate maps so twist-axis logic can be applied per gesture independently.
                bone_horiz_rots = {}
                bone_vert_rots  = {}

                for gesture_key, delta_raw, bone_map in [
                    (horiz_key,  delta_x,  bone_horiz_rots),
                    (vert_key,   delta_y,  bone_vert_rots),
                ]:
                    for delegate in group_delegates.get(gesture_key, []):
                        node_id      = delegate[0]
                        node_gesture = delegate[1]
                        flip         = delegate[2] if len(delegate) > 2 else False
                        scale        = delegate[3] if len(delegate) > 3 else 1.0

                        node_cp = get_control_point_by_id(node_id)
                        if not node_cp:
                            continue
                        ctrl_entry = node_cp.get('controls', {}).get(node_gesture)
                        if not ctrl_entry:
                            continue

                        axis, invert = ctrl_entry
                        angle = delta_raw * sensitivity * scale * (-1 if invert else 1)
                        if flip:
                            angle = -angle  # Reverse direction (e.g. knee bends opposite to thigh raise)

                        # Get bones owned by the referenced node
                        node_bones = node_cp.get('bone_names', [])
                        if not node_bones:
                            bn = node_cp.get('bone_name')
                            if bn:
                                node_bones = [bn]

                        rot_quat = Quaternion(axis_vecs[axis], angle)
                        for bone_name in node_bones:
                            if bone_name in bone_map:
                                # Compose with existing rotation for this bone
                                prev_axis, prev_rot = bone_map[bone_name]
                                bone_map[bone_name] = (prev_axis, rot_quat @ prev_rot)
                            else:
                                bone_map[bone_name] = (axis, rot_quat)

                # Apply per-bone rotations with twist filtering and Y-lock
                for i, bone in enumerate(self._rotation_bones):
                    initial_quat = self._rotation_initial_quats[i]
                    is_twist_bone = 'twist' in bone.name.lower()
                    combined_rot = Quaternion()

                    for bone_map in (bone_horiz_rots, bone_vert_rots):
                        info = bone_map.get(bone.name)
                        if not info:
                            continue
                        axis, rot_quat = info

                        if is_twist_bone:
                            if axis == 'Y':
                                # Current-bone-axis correction: when a sibling twist bone's
                                # parent is raised, local Y no longer points along the limb.
                                # Rotate (0,1,0) by initial_quat to get the current bone axis.
                                _bone_y = Vector((0, 1, 0))
                                _bone_y.rotate(initial_quat)
                                if _bone_y.length_squared > 0.000001:
                                    _bone_y.normalize()
                                    _twist_angle = 2.0 * math.atan2(rot_quat.y, rot_quat.w)
                                    combined_rot = Quaternion(_bone_y, _twist_angle) @ combined_rot
                                else:
                                    combined_rot = rot_quat @ combined_rot
                            # Non-Y axes on twist bones are silently skipped (ERC drives them)
                        else:
                            combined_rot = rot_quat @ combined_rot

                    # Identity skip: allow ERC to drive twist bones when no Y gesture active
                    _is_identity = (abs(combined_rot.w - 1.0) < 0.0001 and
                                    abs(combined_rot.x) < 0.0001 and
                                    abs(combined_rot.y) < 0.0001 and
                                    abs(combined_rot.z) < 0.0001)
                    if not _is_identity:
                        bone_lower = bone.name.lower()
                        if ('thigh' in bone_lower and 'bend' in bone_lower):
                            # Post-multiply: rotate in bone's LOCAL frame so axes
                            # stay aligned regardless of current pose.
                            bone.rotation_quaternion = initial_quat @ combined_rot
                        else:
                            bone.rotation_quaternion = combined_rot @ initial_quat

                    # Y-LOCK for ThighBend bones
                    bone_lower = bone.name.lower()
                    if 'thigh' in bone_lower and 'bend' in bone_lower:
                        current_quat = bone.rotation_quaternion.copy()
                        swing_quat, twist_quat = decompose_swing_twist(current_quat, 'Y')
                        bone.rotation_quaternion = swing_quat
                        twist_angle = 2.0 * math.acos(min(1.0, abs(twist_quat.w)))
                        if twist_angle > 0.01:
                            print(f"  [Y-LOCK DELEGATE] Removed {math.degrees(twist_angle):.1f} deg Y from {bone.name}")

            else:
                # ================================================================
                # STANDARD MODE: shared axis-driven rotation for all bones
                # ================================================================
                if self._rotation_mouse_button == 'LEFT':
                    horiz_entry = controls.get('lmb_horiz')
                    vert_entry = controls.get('lmb_vert')
                else:
                    horiz_entry = controls.get('rmb_horiz')
                    vert_entry = controls.get('rmb_vert')

                horiz_axis, horiz_invert = horiz_entry if horiz_entry else (None, False)
                vert_axis, vert_invert = vert_entry if vert_entry else (None, False)

                # Build per-axis rotation quaternions from mouse deltas
                rot_x = None
                rot_y = None
                rot_z = None

                axis_vectors = {'X': Vector((1, 0, 0)), 'Y': Vector((0, 1, 0)), 'Z': Vector((0, 0, 1))}

                # Horizontal drag (delta_x)
                if horiz_axis:
                    h_angle = delta_x * sensitivity * (-1 if horiz_invert else 1)
                    h_quat = Quaternion(axis_vectors[horiz_axis], h_angle)
                    if horiz_axis == 'X': rot_x = h_quat
                    elif horiz_axis == 'Y': rot_y = h_quat
                    elif horiz_axis == 'Z': rot_z = h_quat

                # Vertical drag (-delta_y, base inverted for screen coords)
                if vert_axis:
                    v_angle = -delta_y * sensitivity * (-1 if vert_invert else 1)
                    v_quat = Quaternion(axis_vectors[vert_axis], v_angle)
                    if vert_axis == 'X': rot_x = v_quat
                    elif vert_axis == 'Y': rot_y = v_quat
                    elif vert_axis == 'Z': rot_z = v_quat

                # Bilateral mirroring: check which axes need L/R inversion
                mirror_axes = controls.get('mirror_axes', [])

                # Apply rotation to each bone with axis filtering (Individual Origins)
                # Twist bones only receive Y-axis rotations, Bend bones receive all axes
                for i, bone in enumerate(self._rotation_bones):
                    initial_quat = self._rotation_initial_quats[i]

                    # Check if this is a twist bone (should only rotate on Y-axis)
                    is_twist_bone = 'twist' in bone.name.lower()

                    # Finger bones: Z (spread) only applies to the base joint (bone1)
                    bone_lower = bone.name.lower()
                    is_finger_bone = any(p in bone_lower for p in ['thumb', 'index', 'mid', 'ring', 'pinky'])
                    is_base_joint = bone.name[-1] == '1'

                    # Bilateral mirroring: detect right-side bones (rThighBend, rShin, rCollar, etc.)
                    is_right_side = bone.name.startswith('r') and len(bone.name) > 1 and bone.name[1].isupper()
                    mirror_this_bone = is_right_side and len(mirror_axes) > 0

                    # Per-bone rotation quaternions (mirrored if needed)
                    bone_rot_x = rot_x.inverted() if (rot_x and mirror_this_bone and 'X' in mirror_axes) else rot_x
                    bone_rot_y = rot_y.inverted() if (rot_y and mirror_this_bone and 'Y' in mirror_axes) else rot_y
                    bone_rot_z = rot_z.inverted() if (rot_z and mirror_this_bone and 'Z' in mirror_axes) else rot_z

                    # Apply per-bone axis overrides from controls dict
                    # Format: bone_overrides = {'rmb_vert': {'lShin': ('X', True)}, ...}
                    # Override value can be:
                    #   (axis, invert) — re-derives rotation from unmirrored base with the given invert flag
                    #   None           — exclude this bone from this control's axis entirely
                    bone_overrides = controls.get('bone_overrides', {})
                    if bone_overrides:
                        active_horiz_key = 'lmb_horiz' if self._rotation_mouse_button == 'LEFT' else 'rmb_horiz'
                        active_vert_key = 'lmb_vert' if self._rotation_mouse_button == 'LEFT' else 'rmb_vert'
                        for ctrl_key in (active_horiz_key, active_vert_key):
                            ctrl_overrides = bone_overrides.get(ctrl_key, {})
                            if bone.name in ctrl_overrides:
                                bone_override = ctrl_overrides[bone.name]
                                if bone_override is None:
                                    # Exclude: zero out whichever axis this control drives
                                    ctrl_entry = controls.get(ctrl_key)
                                    if ctrl_entry:
                                        excl_axis = ctrl_entry[0]
                                        if excl_axis == 'X': bone_rot_x = None
                                        elif excl_axis == 'Y': bone_rot_y = None
                                        elif excl_axis == 'Z': bone_rot_z = None
                                else:
                                    ov_axis, ov_invert = bone_override
                                    base_rot = {'X': rot_x, 'Y': rot_y, 'Z': rot_z}.get(ov_axis)
                                    if base_rot:
                                        new_rot = base_rot.inverted() if ov_invert else base_rot
                                        if ov_axis == 'X': bone_rot_x = new_rot
                                        elif ov_axis == 'Y': bone_rot_y = new_rot
                                        elif ov_axis == 'Z': bone_rot_z = new_rot

                    # Build combined rotation based on bone type
                    combined_rot = Quaternion()  # Identity quaternion

                    # Y-axis rotation (twist) - apply to ALL bones
                    if bone_rot_y:
                        if is_twist_bone:
                            # Twist bones: rotate around the bone's CURRENT axis rather than the
                            # fixed rest-pose Y. When the parent bend bone is raised, the local Y
                            # axis of a sibling twist bone no longer points along the limb — using
                            # a fixed Y would produce a spread instead of an axial twist.
                            # initial_quat encodes the ERC-adjusted orientation at drag start;
                            # rotating (0,1,0) by it gives the bone's current direction in parent space.
                            _bone_y = Vector((0, 1, 0))
                            _bone_y.rotate(initial_quat)
                            if _bone_y.length_squared > 0.000001:
                                _bone_y.normalize()
                                _twist_angle = 2.0 * math.atan2(bone_rot_y.y, bone_rot_y.w)
                                combined_rot = Quaternion(_bone_y, _twist_angle) @ combined_rot
                            else:
                                combined_rot = bone_rot_y @ combined_rot
                        else:
                            combined_rot = bone_rot_y @ combined_rot

                    # X and Z-axis rotations (bending) - only apply to non-twist bones
                    if not is_twist_bone:
                        if bone_rot_x:
                            if is_finger_bone:
                                # Per-finger curl weight: thumb curls differently / overshoots
                                _curl_weights = {'thumb': 0.25, 'index': 1.0, 'mid': 1.0, 'ring': 1.0, 'pinky': 0.9}
                                curl_weight = next((w for k, w in _curl_weights.items() if k in bone_lower), 1.0)
                                effective_rot_x = Quaternion().slerp(bone_rot_x, curl_weight)
                            else:
                                effective_rot_x = bone_rot_x
                            combined_rot = effective_rot_x @ combined_rot
                        if bone_rot_z:
                            # Finger bones: spread (Z) only on base joint
                            if not is_finger_bone or is_base_joint:
                                # Ring and Pinky spread in opposite direction for natural fan spread
                                is_ulnar_finger = is_finger_bone and any(p in bone_lower for p in ['ring', 'pinky'])
                                effective_rot_z = bone_rot_z.inverted() if is_ulnar_finger else bone_rot_z
                                # Per-finger spread weight: middle barely moves, pinky/index spread most
                                if is_finger_bone:
                                    _spread_weights = {'thumb': 0.5, 'index': 0.8, 'mid': 0.1, 'ring': 0.7, 'pinky': 1.0}
                                    spread_weight = next((w for k, w in _spread_weights.items() if k in bone_lower), 1.0)
                                    effective_rot_z = Quaternion().slerp(effective_rot_z, spread_weight)
                                combined_rot = effective_rot_z @ combined_rot

                    # Skip writing if combined_rot is identity — allows ERC constraints to drive
                    # twist bones freely when no explicit rotation applies (e.g. ThighTwist during
                    # X/Z-only RMB drags; writing identity every frame would override the ERC result).
                    _is_identity = (abs(combined_rot.w - 1.0) < 0.0001 and
                                    abs(combined_rot.x) < 0.0001 and
                                    abs(combined_rot.y) < 0.0001 and
                                    abs(combined_rot.z) < 0.0001)
                    if not _is_identity:
                        bone.rotation_quaternion = combined_rot @ initial_quat

                    # Y-LOCK for ThighBend bones in group rotation
                    # ThighBend should NEVER have Y rotation — only X (forward/back) and Z (spread).
                    # Quaternion composition of X and Z can introduce tiny Y components,
                    # so we actively strip Y after each frame (same pattern as single-bone rotation).
                    bone_lower = bone.name.lower()
                    if 'thigh' in bone_lower and 'bend' in bone_lower:
                        current_quat = bone.rotation_quaternion.copy()
                        swing_quat, twist_quat = decompose_swing_twist(current_quat, 'Y')
                        bone.rotation_quaternion = swing_quat

                        # Debug: show if we removed any Y rotation
                        twist_angle = 2.0 * math.acos(min(1.0, abs(twist_quat.w)))
                        if twist_angle > 0.01:  # Only log if > 0.5 degrees
                            print(f"  [Y-LOCK GROUP] Removed {math.degrees(twist_angle):.1f} deg Y from {bone.name}")

            print(f"  Multi-bone rotation: delta_x={delta_x:.2f}, delta_y={delta_y:.2f}, {len(self._rotation_bones)} bones")

            # Update view layer to evaluate constraints (if enabled)
            if getattr(context.scene.posebridge_settings, 'enforce_constraints', True):
                context.view_layer.update()

        # Neck compensation for rotation-pinned head
        self._apply_rotation_neck_compensation(context)

        # Limb IK compensation for translation-pinned feet/hands during torso/hip rotation
        self._apply_rotation_pin_ik(context)

        # Update viewport
        if context.area: context.area.tag_redraw()
        refresh_3d_viewports(context)

    def end_rotation(self, context, cancel=False):
        """End rotation drag and optionally keyframe"""
        if not self._is_rotating:
            return

        # Bake the constrained rotation before cleanup (respects enforce_constraints setting)
        enforce = getattr(context.scene, 'posebridge_settings', None)
        enforce = getattr(enforce, 'enforce_constraints', True) if enforce else True
        if self._rotation_constraint and self._rotation_bone and not cancel and enforce:
            # Update to ensure constraint is evaluated
            context.view_layer.update()

            # Use evaluated depsgraph to get the constrained result
            depsgraph = context.evaluated_depsgraph_get()
            armature_eval = self._drag_armature.evaluated_get(depsgraph)
            bone_eval = armature_eval.pose.bones[self._rotation_bone.name]

            # Get the constrained rotation from matrix_basis (includes constraint effect)
            constrained_quat = bone_eval.matrix_basis.to_quaternion()

            # Apply to bone (this "bakes" the constrained rotation)
            self._rotation_bone.rotation_quaternion = constrained_quat
            print(f"  Baked constrained rotation: {constrained_quat}")

        # Clean up Track To constraint and empty if they exist
        if self._rotation_constraint and self._rotation_bone:
            print("  Cleaning up Track To constraint")
            self._rotation_bone.constraints.remove(self._rotation_constraint)
            self._rotation_constraint = None

        if self._rotation_target_empty:
            print("  Removing target empty")
            bpy.data.objects.remove(self._rotation_target_empty, do_unlink=True)
            self._rotation_target_empty = None

        # Handle multi-bone or single bone rotation
        if self._rotation_bones and len(self._rotation_bones) > 0:
            # Multi-bone rotation
            if cancel:
                print(f"\n=== Canceling Multi-Bone Rotation: {len(self._rotation_bones)} bones ===")
                # Restore initial rotations for all bones
                for i, bone in enumerate(self._rotation_bones):
                    bone.rotation_quaternion = self._rotation_initial_quats[i]
            else:
                print(f"\n=== Ending Multi-Bone Rotation: {len(self._rotation_bones)} bones ===")
                # Store undo state before keyframing
                self.store_rotation_undo_state(context)
                # Keyframe all bones
                for bone in self._rotation_bones:
                    bone.keyframe_insert(data_path="rotation_quaternion")
                    print(f"  ✓ Keyframed: {bone.name}")
        elif self._rotation_bone:
            # Single bone rotation
            if cancel:
                print(f"\n=== Canceling Rotation: {self._rotation_bone.name} ===")
                # Restore initial rotation
                self._rotation_bone.rotation_quaternion = self._rotation_initial_quat
                # Also restore twist bone if it was used
                if hasattr(self, '_twist_bone_initial_quats'):
                    bone_lower = self._rotation_bone.name.lower()
                    if (('shldr' in bone_lower or 'shoulder' in bone_lower or
                         'forearm' in bone_lower or 'lorearm' in bone_lower) and
                        'bend' in bone_lower):
                        twist_bone_name = self._rotation_bone.name.replace('Bend', 'Twist')
                        if twist_bone_name in self._twist_bone_initial_quats:
                            twist_bone = self._drag_armature.pose.bones[twist_bone_name]
                            twist_bone.rotation_quaternion = self._twist_bone_initial_quats[twist_bone_name]
                            print(f"  ✓ Restored twist bone: {twist_bone_name}")
            else:
                print(f"\n=== Ending Rotation: {self._rotation_bone.name} ===")
                # Store undo state before keyframing
                self.store_rotation_undo_state(context)
                # Keyframe the rotation
                self._rotation_bone.keyframe_insert(data_path="rotation_quaternion")
                print(f"  ✓ Keyframed rotation: {self._rotation_bone.rotation_quaternion}")
                # Also keyframe twist bone if it was used
                if hasattr(self, '_twist_bone_initial_quats'):
                    bone_lower = self._rotation_bone.name.lower()
                    if (('shldr' in bone_lower or 'shoulder' in bone_lower or
                         'forearm' in bone_lower or 'lorearm' in bone_lower) and
                        'bend' in bone_lower):
                        twist_bone_name = self._rotation_bone.name.replace('Bend', 'Twist')
                        if twist_bone_name in self._twist_bone_initial_quats:
                            twist_bone = self._drag_armature.pose.bones[twist_bone_name]
                            twist_bone.keyframe_insert(data_path="rotation_quaternion")
                            print(f"  ✓ Keyframed twist bone: {twist_bone_name}")

        # Clean up neck compensation state (if active)
        if self._rotation_neck_state and self._rotation_neck_state is not False:
            neck_state = self._rotation_neck_state
            if cancel:
                # Restore neck bone originals
                if hasattr(self, '_rotation_neck_originals'):
                    for bone_name, orig_quat in self._rotation_neck_originals.items():
                        bone = self._drag_armature.pose.bones.get(bone_name)
                        if bone:
                            bone.rotation_quaternion = orig_quat
                    print(f"  ✓ Restored neck bones to original rotations")
            else:
                # Keyframe spine/neck bones
                for bone in neck_state['all_bones']:
                    bone.keyframe_insert(data_path="rotation_quaternion")
                    print(f"  ✓ Keyframed spine/neck rotation: {bone.name}")

                # Update head rotation pin to final orientation
                armature = self._drag_armature
                if armature:
                    head_bone = neck_state['head_bone']
                    head_data_bone = armature.data.bones.get('head')
                    if head_bone and head_data_bone:
                        world_mat = armature.matrix_world @ head_bone.matrix
                        if "daz_pin_rotation_euler" in head_data_bone:
                            head_data_bone["daz_pin_rotation_euler"] = world_mat.to_euler()
                        rot_empty_name = f"PIN_rotation_{armature.name}_head"
                        rot_empty = bpy.data.objects.get(rot_empty_name)
                        if rot_empty:
                            rot_empty.matrix_world = world_mat
                            print(f"  ✓ Updated head rotation pin to final orientation")

            # Unmute head constraint (always)
            for pose_bone, constraint in self._rotation_neck_muted:
                try:
                    constraint.mute = False
                    print(f"  ✓ Re-enabled head rotation pin constraint")
                except Exception as e:
                    print(f"  ⚠️  Error re-enabling head constraint: {e}")

        self._rotation_neck_state = None
        self._rotation_neck_muted = []
        if hasattr(self, '_rotation_neck_originals'):
            del self._rotation_neck_originals

        # Clean up translation-pin limb IK state (if active)
        if self._rotation_pin_limb_state and self._rotation_pin_limb_state is not False:
            pinned_limbs = self._rotation_pin_limb_state
            armature = self._drag_armature
            if cancel:
                # Restore all limb bones to their drag-start rotations
                if hasattr(self, '_rotation_pin_limb_originals'):
                    for bone_name, orig_quat in self._rotation_pin_limb_originals.items():
                        bone = armature.pose.bones.get(bone_name) if armature else None
                        if bone:
                            bone.rotation_quaternion = orig_quat
                    print(f"  ✓ Restored pinned limb bones to original rotations")
            else:
                # Keyframe all affected limb bones at their final IK-solved positions
                keyframed = set()
                for limb in pinned_limbs:
                    for role, b in limb['bones'].items():
                        if b and b.name not in keyframed:
                            b.keyframe_insert(data_path="rotation_quaternion")
                            keyframed.add(b.name)
                            print(f"  ✓ Keyframed limb bone: {b.name}")

                # Update translation pin target positions to reflect new world positions
                # (foot may have shifted slightly due to rounding in IK solve)
                if armature:
                    for limb in pinned_limbs:
                        ep_name = limb['endpoint_name']
                        ep_pose = armature.pose.bones.get(ep_name)
                        ep_data = armature.data.bones.get(ep_name)
                        if ep_pose and ep_data:
                            # Recompute world position from depsgraph
                            context.view_layer.update()
                            world_head = armature.matrix_world @ ep_pose.head
                            ep_data["daz_pin_location"] = tuple(world_head)
                            # Update pin Empty to match
                            pin_empty_name = f"PIN_translation_{armature.name}_{ep_name}"
                            pin_empty = bpy.data.objects.get(pin_empty_name)
                            if pin_empty:
                                pin_empty.location = world_head
                            # Update limb's pin_target_pos so it's current for next drag
                            limb['pin_target_pos'] = world_head.copy()
                            print(f"  ✓ Updated translation pin position for {ep_name}")

            # Unmute translation pin constraints (always re-enable)
            for pose_bone, constraint in self._rotation_pin_limb_muted:
                try:
                    constraint.mute = False
                    print(f"  ✓ Re-enabled translation pin constraint on {pose_bone.name}")
                except Exception as e:
                    print(f"  ⚠️  Error re-enabling pin constraint: {e}")

        self._rotation_pin_limb_state = None
        self._rotation_pin_limb_muted = []
        if hasattr(self, '_rotation_pin_limb_originals'):
            del self._rotation_pin_limb_originals

        # Clear rotation state
        self._is_rotating = False
        self._rotation_bone = None
        self._rotation_initial_quat = None
        self._rotation_parent_frame_quat = None
        self._rotation_bones = []
        self._rotation_initial_quats = []
        self._rotation_group_id = None
        self._rotation_group_controls = None
        self._rotation_initial_mouse = None
        self._rotation_mouse_button = None
        # NOTE: Do NOT clear _right_click_used_for_drag here -- it must persist
        # until the next MOUSEMOVE so that post-release CLICK events are consumed
        self._mouse_down_pos = None
        self._accumulated_drag_distance = 0.0
        self._last_detection_mouse_pos = None
        # Clear twist bone state if it exists
        if hasattr(self, '_twist_bone_initial_quats'):
            del self._twist_bone_initial_quats

        # Update viewport and header
        if context.area: context.area.tag_redraw()
        refresh_3d_viewports(context)
        self._set_header(context,"DAZ Bone Select Active - P to pin | U to unpin | Alt+Shift+R to clear pose | ESC to exit")

    # =========================================================================
    # MORPH DRAG (Face Panel)
    # =========================================================================

    def _get_hovered_cp(self, context):
        """Look up the currently hovered control point from settings."""
        if not self._hover_control_point_id:
            return None
        settings = context.scene.posebridge_settings
        for cp in settings.control_points_fixed:
            if cp.id == self._hover_control_point_id:
                return cp
        return None

    def start_morph_drag(self, context, event):
        """Start morph property drag on a face control point."""
        armature = self._drag_armature
        if not armature:
            return

        # Look up the controls dict for this face CP (static dict lookup)
        # Use locked drag state (set at mouse-down) since hover state may have
        # been cleared by MOUSEMOVE events during drag threshold detection
        from daz_shared_utils import get_face_morph_controls
        cp_id = self._drag_control_point_id or self._hover_control_point_id
        controls = get_face_morph_controls(cp_id)
        print(f"  Morph controls lookup: cp_id='{cp_id}' → {controls}")
        if not controls:
            print(f"  No morph controls found for {cp_id}")
            return

        self._is_morphing = True
        self._morph_controls = controls
        self._morph_initial_mouse = (event.mouse_x, event.mouse_y)
        self._morph_mouse_button = self._rotation_mouse_button  # LEFT or RIGHT
        self._morph_cp_id = cp_id

        # Snapshot initial values of all morph properties referenced in controls
        # Include split keys (_pos/_neg) for directional controls
        self._morph_initial_values = {}
        all_keys = [
            'lmb_vert', 'lmb_horiz', 'rmb_vert', 'rmb_horiz',
            'lmb_vert_pos', 'lmb_vert_neg', 'lmb_horiz_pos', 'lmb_horiz_neg',
            'rmb_vert_pos', 'rmb_vert_neg', 'rmb_horiz_pos', 'rmb_horiz_neg',
        ]
        for key in all_keys:
            entry = controls.get(key)
            if entry is not None:
                prop_name = entry[0]
                if prop_name not in self._morph_initial_values:
                    if prop_name in armature:
                        self._morph_initial_values[prop_name] = float(armature[prop_name])
                    else:
                        self._morph_initial_values[prop_name] = 0.0

        # Clear drag bone (morph CPs don't select bones)
        self._drag_bone_name = None

        self._set_header(context,
            f"PoseBridge Face: {self._morph_cp_id} - Drag to adjust | ESC to cancel"
        )
        print(f"\n=== Starting Morph Drag: {self._morph_cp_id} | button={self._morph_mouse_button} ===")
        print(f"  Initial values: {self._morph_initial_values}")

    def update_morph(self, context, event):
        """Update morph property values during face drag."""
        if not self._is_morphing:
            return

        armature = self._drag_armature
        if not armature:
            return

        delta_x = event.mouse_x - self._morph_initial_mouse[0]
        delta_y = event.mouse_y - self._morph_initial_mouse[1]

        settings = context.scene.posebridge_settings
        sensitivity = settings.morph_sensitivity
        controls = self._morph_controls

        # Determine which gesture keys to use based on mouse button
        horiz_key = 'lmb_horiz' if self._morph_mouse_button == 'LEFT' else 'rmb_horiz'
        vert_key = 'lmb_vert' if self._morph_mouse_button == 'LEFT' else 'rmb_vert'

        # Apply horizontal gesture (supports split: _pos/_neg for right/left)
        horiz_pos = controls.get(horiz_key + '_pos')
        horiz_neg = controls.get(horiz_key + '_neg')
        if horiz_pos or horiz_neg:
            self._apply_split_morph(armature, horiz_pos, horiz_neg, delta_x, sensitivity)
        else:
            horiz_entry = controls.get(horiz_key)
            if horiz_entry is not None:
                self._apply_morph_delta(armature, horiz_entry, delta_x, sensitivity)

        # Apply vertical gesture (supports split: _pos/_neg for up/down)
        vert_pos = controls.get(vert_key + '_pos')
        vert_neg = controls.get(vert_key + '_neg')
        if vert_pos or vert_neg:
            self._apply_split_morph(armature, vert_pos, vert_neg, delta_y, sensitivity)
        else:
            vert_entry = controls.get(vert_key)
            if vert_entry is not None:
                self._apply_morph_delta(armature, vert_entry, delta_y, sensitivity)

        # Force driver re-evaluation: tag armature so depsgraph knows properties changed
        armature.update_tag()
        context.view_layer.depsgraph.update()
        if context.area: context.area.tag_redraw()
        refresh_3d_viewports(context)

    def _apply_morph_delta(self, armature, entry, delta_pixels, sensitivity):
        """Apply a morph value change based on mouse delta.

        Args:
            armature: Armature object with custom properties
            entry: (prop_name, direction, scale) tuple
            delta_pixels: Mouse movement in pixels from initial position
            sensitivity: Base sensitivity (value per pixel)
        """
        prop_name, direction, scale = entry[0], entry[1], entry[2]

        # Skip if property doesn't exist on armature
        if prop_name not in armature and prop_name not in self._morph_initial_values:
            return

        # Calculate new value from initial + total delta
        sign = 1.0 if direction == 'positive' else -1.0
        initial = self._morph_initial_values.get(prop_name, 0.0)
        new_value = initial + (delta_pixels * sensitivity * scale * sign)

        # Clamp to valid range
        try:
            info = armature.id_properties_ui(prop_name).as_dict()
            min_val = info.get('min', 0.0)
            max_val = info.get('max', 1.0)
        except Exception:
            min_val, max_val = 0.0, 1.0

        new_value = max(min_val, min(max_val, new_value))
        armature[prop_name] = new_value

    def _apply_split_morph(self, armature, pos_entry, neg_entry, delta_pixels, sensitivity):
        """Apply split morph using virtual axis for smooth transitions.

        Treats pos and neg as one continuous axis: positive delta activates
        pos_entry, negative delta activates neg_entry. Smoothly transitions
        through zero — if neg was at 0.3, dragging positive first decreases
        neg to 0, then starts increasing pos.

        Args:
            armature: Armature object
            pos_entry: (prop_name, direction, scale) for positive direction, or None
            neg_entry: (prop_name, direction, scale) for negative direction, or None
            delta_pixels: Mouse movement from initial position
            sensitivity: Base sensitivity
        """
        pos_prop = pos_entry[0] if pos_entry else None
        neg_prop = neg_entry[0] if neg_entry else None
        pos_scale = pos_entry[2] if pos_entry else 1.0
        neg_scale = neg_entry[2] if neg_entry else 1.0

        # Get initial values at drag start
        pos_initial = self._morph_initial_values.get(pos_prop, 0.0) if pos_prop else 0.0
        neg_initial = self._morph_initial_values.get(neg_prop, 0.0) if neg_prop else 0.0

        # Virtual axis: positive = pos property, negative = neg property
        # If pos was 0 and neg was 0.3, virtual_initial = 0 - 0.3 = -0.3
        virtual_initial = pos_initial - neg_initial
        virtual_current = virtual_initial + delta_pixels * sensitivity

        if virtual_current >= 0:
            # Positive side: pos property active, neg zeroed
            if pos_prop:
                new_val = virtual_current * pos_scale
                try:
                    info = armature.id_properties_ui(pos_prop).as_dict()
                    new_val = max(info.get('min', 0.0), min(info.get('max', 1.0), new_val))
                except Exception:
                    new_val = max(0.0, min(1.0, new_val))
                armature[pos_prop] = new_val
            if neg_prop:
                armature[neg_prop] = 0.0
        else:
            # Negative side: neg property active, pos zeroed
            if neg_prop:
                new_val = -virtual_current * neg_scale
                try:
                    info = armature.id_properties_ui(neg_prop).as_dict()
                    new_val = max(info.get('min', 0.0), min(info.get('max', 1.0), new_val))
                except Exception:
                    new_val = max(0.0, min(1.0, new_val))
                armature[neg_prop] = new_val
            if pos_prop:
                armature[pos_prop] = 0.0

    def end_morph(self, context, cancel=False):
        """End morph drag and optionally keyframe."""
        if not self._is_morphing:
            return

        armature = self._drag_armature

        if cancel:
            # Restore initial values
            print(f"\n=== Canceling Morph Drag: {self._morph_cp_id} ===")
            if armature:
                for prop_name, initial_val in self._morph_initial_values.items():
                    armature[prop_name] = initial_val
        else:
            # Store undo state
            print(f"\n=== Ending Morph Drag: {self._morph_cp_id} ===")
            self.store_morph_undo_state(context)

            # Keyframe all changed morph properties
            if armature:
                settings = context.scene.posebridge_settings
                if settings.auto_keyframe:
                    frame = context.scene.frame_current
                    for prop_name in self._morph_initial_values:
                        if prop_name not in armature:
                            print(f"  Skipping keyframe (property not found): {prop_name}")
                            continue
                        data_path = f'["{prop_name}"]'
                        try:
                            armature.keyframe_insert(data_path=data_path, frame=frame)
                            val = armature.get(prop_name, 0.0)
                            print(f"  Keyframed: {prop_name} = {val:.3f}")
                        except Exception as e:
                            print(f"  Keyframe failed for {prop_name}: {e}")

        # Clear morph state
        self._is_morphing = False
        self._morph_controls = None
        self._morph_initial_values = {}
        self._morph_initial_mouse = None
        self._morph_mouse_button = None
        self._morph_cp_id = None
        self._mouse_down_pos = None
        self._accumulated_drag_distance = 0.0
        self._last_detection_mouse_pos = None

        # Update viewport
        context.view_layer.update()
        if context.area: context.area.tag_redraw()
        refresh_3d_viewports(context)
        self._set_header(context,"DAZ Bone Select Active - P to pin | U to unpin | Alt+Shift+R to clear pose | ESC to exit")

    def store_morph_undo_state(self, context):
        """Store morph property values before keyframing (for Ctrl+Z)."""
        if not self._drag_armature:
            return

        frame = context.scene.frame_current
        morph_data = [
            (prop_name, initial_val)
            for prop_name, initial_val in self._morph_initial_values.items()
        ]

        undo_entry = {
            'frame': frame,
            'type': 'morph',
            'morphs': morph_data,
            'armature': self._drag_armature
        }
        self._undo_stack.append(undo_entry)
        print(f"  Stored morph undo state: frame {frame}, {len(morph_data)} props")

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
            self._set_header(context,text)

            # Force immediate viewport redraw to show pin sphere instantly
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
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
            self._set_header(context,text)

            # Force immediate viewport redraw to show pin sphere instantly
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
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
            self._set_header(context,text)

            # Force immediate viewport redraw to hide pin sphere instantly
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
        else:
            self.report({'INFO'}, f"{bone_name} was not pinned")

    def cleanup_temp_ik_chains(self, context):
        """Clean up all temporary IK chains (for debug mode)"""
        print("\n=== Cleaning Up Temp IK Chains ===")

        armature = context.active_object
        if not armature or armature.type != 'ARMATURE':
            print("  No armature active")
            return

        # STEP 1: Cache all bone rotations and locations BEFORE any changes (preserves DAZ poses)
        rotation_cache = {}
        location_cache = {}
        for pose_bone in armature.pose.bones:
            if pose_bone.rotation_mode == 'QUATERNION':
                rotation_cache[pose_bone.name] = pose_bone.rotation_quaternion.copy()
            else:
                rotation_cache[pose_bone.name] = pose_bone.rotation_euler.copy()
            if pose_bone.bone.parent is None or pose_bone.location.length_squared > 1e-8:
                location_cache[pose_bone.name] = pose_bone.location.copy()

        # STEP 2: Remove all temp constraints FIRST (while still in POSE mode, before deleting bones)
        constraints_removed = 0
        for pose_bone in armature.pose.bones:
            constraints_to_remove = [c for c in pose_bone.constraints
                                    if 'Temp' in c.name or 'IK_' in c.name]
            for c in constraints_to_remove:
                constraint_name = c.name  # Store name before removal
                pose_bone.constraints.remove(c)
                constraints_removed += 1
                print(f"  Removed constraint: {constraint_name} from {pose_bone.name}")

        # STEP 3: Switch to edit mode to delete bones
        if context.mode != 'EDIT_ARMATURE':
            bpy.ops.object.mode_set(mode='EDIT')

        edit_bones = armature.data.edit_bones
        bones_removed = 0

        # Delete all temp bones (.ik, .shoulder.target, .pole)
        temp_bones = [b.name for b in edit_bones
                     if '.ik' in b.name or '.shoulder.target' in b.name or b.name.endswith('.pole')]
        for bone_name in temp_bones:
            if bone_name in edit_bones:
                edit_bones.remove(edit_bones[bone_name])
                bones_removed += 1
                print(f"  Removed: {bone_name}")

        # STEP 5: Switch back to pose mode
        bpy.ops.object.mode_set(mode='POSE')

        # STEP 6: Restore all bone rotations after mode switch (preserves DAZ poses)
        rotations_restored = 0
        for bone_name_cache, rotation in rotation_cache.items():
            pose_bone = armature.pose.bones.get(bone_name_cache)
            if pose_bone:
                if pose_bone.rotation_mode == 'QUATERNION':
                    pose_bone.rotation_quaternion = rotation
                else:
                    pose_bone.rotation_euler = rotation
                rotations_restored += 1

        # Restore bone locations (hip, any translated bones)
        for bone_name_cache, loc in location_cache.items():
            pose_bone = armature.pose.bones.get(bone_name_cache)
            if pose_bone:
                pose_bone.location = loc

        # Force evaluation with restored transforms
        context.view_layer.update()
        print(f"  ✓ Restored rotations for {rotations_restored} bones")

        print(f"  ✓ Cleanup complete: {bones_removed} bones, {constraints_removed} constraints")
        if context.area: context.area.tag_redraw()

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
        """Store current bone rotation before keyframing"""
        if not self._drag_armature:
            return

        frame = context.scene.frame_current

        if self._rotation_bones:
            # Multi-bone group
            bones_data = [
                (bone.name, self._rotation_initial_quats[i].copy(), 'QUATERNION')
                for i, bone in enumerate(self._rotation_bones)
            ]
        elif self._rotation_bone:
            # Single bone
            bones_data = [(self._rotation_bone.name, self._rotation_initial_quat.copy(), 'QUATERNION')]
        else:
            return

        undo_entry = {
            'frame': frame,
            'bones': bones_data,
            'armature': self._drag_armature
        }
        self._undo_stack.append(undo_entry)
        print(f"  Stored rotation undo state: frame {frame}, {len(bones_data)} bones")

    def undo_last_drag(self, context):
        """Undo the last IK drag or morph by restoring previous values"""
        if not self._undo_stack:
            self.report({'INFO'}, "Nothing to undo")
            return

        # Pop the last undo entry
        undo_entry = self._undo_stack.pop()
        frame = undo_entry['frame']
        armature = undo_entry['armature']

        # Check if this is a morph undo entry
        if undo_entry.get('type') == 'morph':
            morph_data = undo_entry['morphs']
            print(f"\n=== Undo Morph: Restoring {len(morph_data)} props at frame {frame} ===")
            for prop_name, value in morph_data:
                armature[prop_name] = value
                armature.keyframe_insert(data_path=f'["{prop_name}"]', frame=frame)
                print(f"  Restored: {prop_name} = {value:.3f}")
            context.view_layer.update()
            self.report({'INFO'}, f"Undone: Restored {len(morph_data)} morph values")
            print(f"  ✓ Morph undo complete")
            return

        # Bone rotation undo (existing logic)
        bones_data = undo_entry['bones']
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

    def draw_tooltip_callback(self):
        """Draw tooltip text near mouse cursor after 1 second hover"""
        tooltip_text = self._tooltip_text
        tooltip_pos = self._tooltip_mouse_pos

        # Only draw if we have text and position
        if not tooltip_text or not tooltip_pos:
            return

        # Set up font
        font_id = 0
        blf.size(font_id, 14)
        blf.color(font_id, 1.0, 1.0, 1.0, 0.95)  # White text with slight transparency

        # Calculate text dimensions for background
        text_width, text_height = blf.dimensions(font_id, tooltip_text)

        # Position tooltip slightly offset from mouse (right and down)
        x = tooltip_pos[0] + 15
        y = tooltip_pos[1] - 20

        # Draw semi-transparent background
        padding = 6
        vertices = (
            (x - padding, y - padding),
            (x + text_width + padding, y - padding),
            (x + text_width + padding, y + text_height + padding),
            (x - padding, y + text_height + padding)
        )

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices})
        shader.bind()
        shader.uniform_float("color", (0.0, 0.0, 0.0, 0.75))  # Dark background
        batch.draw(shader)

        # Draw text on top
        blf.position(font_id, x, y, 0)
        blf.draw(font_id, tooltip_text)

    def _get_bone_vertex_indices(self, mesh_obj, bone_names):
        """Get vertex indices belonging to a set of bones (DSF face groups or vertex weights).
        Returns a set of vertex indices. Results are cached — topology never changes mid-session."""
        cache_key = (mesh_obj.name, tuple(sorted(bone_names)))
        cached = VIEW3D_OT_daz_bone_select._bracket_vert_cache.get(cache_key)
        if cached is not None:
            return cached

        mesh = mesh_obj.data
        vert_indices = set()
        bones_set = set(bone_names)

        # Try DSF face groups first (clean, hard-edged zones)
        if self._face_group_mgr and self._face_group_mgr.valid and mesh_obj == self._base_body_mesh:
            face_map = self._face_group_mgr.face_group_map
            for poly_idx, poly in enumerate(mesh.polygons):
                if poly_idx < len(face_map) and face_map[poly_idx] in bones_set:
                    vert_indices.update(poly.vertices)
            if vert_indices:
                VIEW3D_OT_daz_bone_select._bracket_vert_cache[cache_key] = vert_indices
                return vert_indices

        # Fallback: vertex weight method (highest weight wins)
        for bone_name in bone_names:
            if bone_name not in mesh_obj.vertex_groups:
                continue
            vgroup = mesh_obj.vertex_groups[bone_name]
            for vert in mesh.vertices:
                if not vert.groups:
                    continue
                max_weight = 0.0
                max_group_idx = None
                for group in vert.groups:
                    if group.weight > max_weight:
                        max_weight = group.weight
                        max_group_idx = group.group
                if max_group_idx == vgroup.index and max_weight > 0.01:
                    vert_indices.add(vert.index)

        VIEW3D_OT_daz_bone_select._bracket_vert_cache[cache_key] = vert_indices
        return vert_indices

    def _build_bone_bracket_lines(self, armature, pose_bone, mesh_obj, mesh_data, bone_world_mat, bone_world_mat_inv):
        """Build corner bracket lines for a single bone in bone-aligned space.
        Returns list of Vector pairs (line start, line end) in world space."""
        # Determine bone name for vertex lookup (hip → pelvis)
        bone_name = pose_bone.name
        if not pose_bone.parent and 'pelvis' in armature.pose.bones:
            bone_name = 'pelvis'

        vert_indices = self._get_bone_vertex_indices(mesh_obj, [bone_name])

        if vert_indices:
            # Transform deformed vertices into bone-local space and compute AABB there
            first = True
            for vi in vert_indices:
                world_pos = mesh_obj.matrix_world @ mesh_data.vertices[vi].co
                local_pos = bone_world_mat_inv @ world_pos
                if first:
                    min_x = max_x = local_pos.x
                    min_y = max_y = local_pos.y
                    min_z = max_z = local_pos.z
                    first = False
                else:
                    if local_pos.x < min_x: min_x = local_pos.x
                    if local_pos.x > max_x: max_x = local_pos.x
                    if local_pos.y < min_y: min_y = local_pos.y
                    if local_pos.y > max_y: max_y = local_pos.y
                    if local_pos.z < min_z: min_z = local_pos.z
                    if local_pos.z > max_z: max_z = local_pos.z
        else:
            # Fallback: bone head/tail in local space
            head_local = bone_world_mat_inv @ (armature.matrix_world @ pose_bone.head)
            tail_local = bone_world_mat_inv @ (armature.matrix_world @ pose_bone.tail)
            min_x = min(head_local.x, tail_local.x)
            max_x = max(head_local.x, tail_local.x)
            min_y = min(head_local.y, tail_local.y)
            max_y = max(head_local.y, tail_local.y)
            min_z = min(head_local.z, tail_local.z)
            max_z = max(head_local.z, tail_local.z)

        # 15% padding per axis (min 0.005m)
        pad_x = max((max_x - min_x) * 0.15, 0.005)
        pad_y = max((max_y - min_y) * 0.15, 0.005)
        pad_z = max((max_z - min_z) * 0.15, 0.005)
        min_x -= pad_x; max_x += pad_x
        min_y -= pad_y; max_y += pad_y
        min_z -= pad_z; max_z += pad_z

        # Corner bracket lengths (25% of edge, min 0.008m)
        bx = max((max_x - min_x) * 0.25, 0.008)
        by = max((max_y - min_y) * 0.25, 0.008)
        bz = max((max_z - min_z) * 0.25, 0.008)

        # Build corner bracket lines in bone-local space, then transform to world
        lines = []
        for cx in (min_x, max_x):
            sx = 1.0 if cx == min_x else -1.0
            for cy in (min_y, max_y):
                sy = 1.0 if cy == min_y else -1.0
                for cz in (min_z, max_z):
                    sz = 1.0 if cz == min_z else -1.0
                    c = Vector((cx, cy, cz))
                    lines.append(bone_world_mat @ c)
                    lines.append(bone_world_mat @ Vector((cx + sx * bx, cy, cz)))
                    lines.append(bone_world_mat @ c)
                    lines.append(bone_world_mat @ Vector((cx, cy + sy * by, cz)))
                    lines.append(bone_world_mat @ c)
                    lines.append(bone_world_mat @ Vector((cx, cy, cz + sz * bz)))
        return lines

    def draw_selection_brackets_callback(self):
        """Draw DAZ-style bone-aligned corner brackets: gold on hover, gray on select."""
        try:
            mesh_obj = self._base_body_mesh
            context = bpy.context
            if context.mode != 'POSE':
                return
            armature = context.active_object
            if not armature or armature.type != 'ARMATURE':
                return
        except ReferenceError:
            # Operator was destroyed (e.g. after reload) — self-remove to stop spam
            try:
                bpy.types.SpaceView3D.draw_handler_remove(self._bracket_draw_handler, 'WINDOW')
            except Exception:
                pass
            return
        except AttributeError:
            return
        if not mesh_obj:
            return

        selected = context.selected_pose_bones or []
        selected_names = {pb.name for pb in selected}

        # Determine hover bone (skip if already selected — avoid double bracket)
        hover_bone_name = self._hover_bone_name
        hover_armature = self._hover_armature
        hover_pose_bone = None
        if (hover_bone_name and hover_armature and hover_armature == armature
                and hover_bone_name not in selected_names
                and hover_bone_name in armature.pose.bones):
            hover_pose_bone = armature.pose.bones[hover_bone_name]

        if not selected and not hover_pose_bone:
            return

        # Get deformed mesh (evaluated) once for all bones
        depsgraph = bpy.context.evaluated_depsgraph_get()
        mesh_eval = mesh_obj.evaluated_get(depsgraph)
        mesh_data = mesh_eval.data

        # Get opacity multiplier from settings
        opacity = 1.0
        try:
            settings = bpy.context.scene.posebridge_settings
            opacity = settings.highlight_opacity
        except Exception:
            pass

        if opacity <= 0.0:
            return

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.line_width_set(2.0)
        shader.bind()

        # Draw hover bracket (gold/amber — matches mesh highlight)
        if hover_pose_bone:
            bone_world_mat = armature.matrix_world @ hover_pose_bone.matrix
            bone_world_mat_inv = bone_world_mat.inverted_safe()
            hover_lines = self._build_bone_bracket_lines(
                armature, hover_pose_bone, mesh_obj, mesh_data,
                bone_world_mat, bone_world_mat_inv
            )
            if hover_lines:
                batch = batch_for_shader(shader, 'LINES', {"pos": hover_lines})
                shader.uniform_float("color", (1.0, 0.6, 0.1, 0.6 * opacity))  # Amber
                batch.draw(shader)

        # Draw selection brackets (gray)
        if selected:
            select_lines = []
            for pose_bone in selected:
                bone_world_mat = armature.matrix_world @ pose_bone.matrix
                bone_world_mat_inv = bone_world_mat.inverted_safe()
                select_lines.extend(self._build_bone_bracket_lines(
                    armature, pose_bone, mesh_obj, mesh_data,
                    bone_world_mat, bone_world_mat_inv
                ))
            if select_lines:
                batch = batch_for_shader(shader, 'LINES', {"pos": select_lines})
                shader.uniform_float("color", (0.75, 0.75, 0.75, 0.8 * opacity))  # Light gray
                batch.draw(shader)

        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')

    def draw_highlight_callback(self):
        """Draw callback to highlight mesh region weighted to hovered bone (DAZ-style)"""
        # Safety check: verify operator still exists; self-remove if dead
        try:
            hover_bone = self._hover_bone_name
            hover_arm = self._hover_armature
        except ReferenceError:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(self._draw_handler, 'WINDOW')
            except Exception:
                pass
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

        # Build list of bones to highlight together
        bones_to_highlight = [bone_name]

        bone_lower = bone_name.lower()

        # TOE: If hovering any toe, highlight ALL toes together (not foot/metatarsals)
        if 'toe' in bone_lower:
            # Find parent foot bone to get all sibling toes
            parent = armature.data.bones[bone_name].parent
            if parent:
                for sibling in parent.children:
                    sibling_lower = sibling.name.lower()
                    if 'toe' in sibling_lower:
                        bones_to_highlight.append(sibling.name)
            bones_to_highlight = list(set(bones_to_highlight))  # Remove duplicates

        # FOOT: Include metatarsals only (NOT toes - they have their own zone)
        elif 'foot' in bone_lower:
            for child_bone in armature.data.bones[bone_name].children:
                child_lower = child_bone.name.lower()
                if any(term in child_lower for term in ['metatarsal', 'tarsal']) and 'toe' not in child_lower:
                    bones_to_highlight.append(child_bone.name)

        # HAND: Include metacarpals only (NOT fingers - they stay separate)
        elif 'hand' in bone_lower:
            for child_bone in armature.data.bones[bone_name].children:
                child_lower = child_bone.name.lower()
                # Include metacarpals, carpals (NOT fingers)
                if any(term in child_lower for term in ['metacarpal', 'carpal']) and 'thumb' not in child_lower:
                    bones_to_highlight.append(child_bone.name)

        # Cache key includes all bones we're highlighting
        cache_key = (mesh_obj.name, tuple(sorted(bones_to_highlight)))

        # Check cache - only compute weighted verts/polygons once per bone combination
        if cache_key not in self._highlight_cache:
            mesh = mesh_obj.data

            # Try DSF face groups first (clean, hard-edged zones)
            tri_indices = []
            used_face_groups = False
            if self._face_group_mgr and self._face_group_mgr.valid and mesh_obj == self._base_body_mesh:
                face_map = self._face_group_mgr.face_group_map
                bones_set = set(bones_to_highlight)
                for poly_idx, poly in enumerate(mesh.polygons):
                    if poly_idx < len(face_map) and face_map[poly_idx] in bones_set:
                        for i in range(1, len(poly.vertices) - 1):
                            tri_indices.append((poly.vertices[0], poly.vertices[i], poly.vertices[i + 1]))
                # Only block the vertex weight fallback if we actually got polygons.
                # An empty result means this bone simply has no DSF face group entry —
                # fall through to vertex weights so the hover still shows something.
                used_face_groups = len(tri_indices) > 0

            # Fallback: vertex weight method (fuzzy boundaries)
            if not used_face_groups:
                weighted_verts = set()

                # Collect vertices from ALL bones in the group
                for bone_to_check in bones_to_highlight:
                    if bone_to_check not in mesh_obj.vertex_groups:
                        continue

                    vgroup = mesh_obj.vertex_groups[bone_to_check]

                    # Collect vertices where THIS bone has the HIGHEST weight
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

                        # Include vertex if THIS bone has the max weight
                        if max_group_idx == vgroup.index and max_weight > 0.01:
                            weighted_verts.add(vert.index)

                if not weighted_verts:
                    self._highlight_cache[cache_key] = []
                    return

                # Collect triangle indices (vertex indices, not positions)
                for poly in mesh.polygons:
                    # If at least one vertex of the polygon is weighted, include the whole polygon
                    if any(v in weighted_verts for v in poly.vertices):
                        for i in range(1, len(poly.vertices) - 1):
                            tri_indices.append((poly.vertices[0], poly.vertices[i], poly.vertices[i + 1]))

            # Cache the triangle indices (not positions)
            self._highlight_cache[cache_key] = tri_indices

        # Get cached triangle indices
        tri_indices = self._highlight_cache[cache_key]
        if not tri_indices:
            return

        # Get DEFORMED mesh from evaluated depsgraph (includes armature deformation)
        import bpy
        depsgraph = bpy.context.evaluated_depsgraph_get()

        # Pose hash: sample the hovered bone's head position (world space) as a cheap
        # change sentinel. Rebuilds the GPU batch only when the pose actually changed.
        pose_sentinel = None
        if hover_arm and bone_name in hover_arm.pose.bones:
            pb = hover_arm.pose.bones[bone_name]
            h = hover_arm.matrix_world @ pb.head
            pose_sentinel = (round(h.x, 4), round(h.y, 4), round(h.z, 4))

        batch_cache_key = ('batch', cache_key)
        sentinel_cache_key = ('sentinel', cache_key)
        cached_batch = self._highlight_cache.get(batch_cache_key)
        cached_sentinel = self._highlight_cache.get(sentinel_cache_key)

        if cached_batch is None or cached_sentinel != pose_sentinel:
            mesh_eval = mesh_obj.evaluated_get(depsgraph)
            mesh_data = mesh_eval.data

            offset_amount = 0.001
            tris = []
            for v0_idx, v1_idx, v2_idx in tri_indices:
                v0_co = mesh_data.vertices[v0_idx].co
                v1_co = mesh_data.vertices[v1_idx].co
                v2_co = mesh_data.vertices[v2_idx].co
                v0_normal = mesh_data.vertices[v0_idx].normal
                v1_normal = mesh_data.vertices[v1_idx].normal
                v2_normal = mesh_data.vertices[v2_idx].normal
                v0 = mesh_eval.matrix_world @ (v0_co + v0_normal * offset_amount)
                v1 = mesh_eval.matrix_world @ (v1_co + v1_normal * offset_amount)
                v2 = mesh_eval.matrix_world @ (v2_co + v2_normal * offset_amount)
                tris.extend([v0, v1, v2])

            if not tris:
                return

            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            cached_batch = batch_for_shader(shader, 'TRIS', {"pos": tris})
            self._highlight_cache[batch_cache_key] = cached_batch
            self._highlight_cache[sentinel_cache_key] = pose_sentinel

        batch = cached_batch
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        if not batch:
            return

        # Get opacity multiplier from settings
        opacity = 1.0
        try:
            settings = bpy.context.scene.posebridge_settings
            opacity = settings.highlight_opacity
        except Exception:
            pass

        if opacity <= 0.0:
            return

        # Enable blending for transparency
        gpu.state.blend_set('ALPHA')

        # CRITICAL: Depth settings to draw on top of clothing/hair
        gpu.state.depth_test_set('ALWAYS')  # Always draw, ignore depth (show through clothing)
        gpu.state.depth_mask_set(False)  # Don't write to depth buffer (overlay on top cleanly)
        gpu.state.face_culling_set('BACK')  # Only draw front faces (prevents double-draw artifacts)

        # Draw with bright amber highlight
        shader.bind()
        shader.uniform_float("color", (1.0, 0.6, 0.1, 0.4 * opacity))  # Bright amber with moderate transparency
        batch.draw(shader)

        # Reset state
        gpu.state.blend_set('NONE')
        gpu.state.depth_mask_set(True)
        gpu.state.face_culling_set('NONE')
        gpu.state.depth_test_set('LESS_EQUAL')

    def draw_pin_spheres_callback(self):
        """
        Persistent draw callback for pin spheres.
        This runs independently from hover/highlight and always shows pinned bones.
        """
        try:
            # Find all armatures in the scene
            for obj in bpy.context.scene.objects:
                if obj.type == 'ARMATURE':
                    self.draw_pin_spheres(obj)
        except ReferenceError:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(self._pin_draw_handler, 'WINDOW')
            except Exception:
                pass
        except AttributeError:
            pass

    def draw_pin_spheres(self, armature):
        """Draw purple spheres at pinned bone locations (DAZ-style visual indicator)"""
        if not armature or armature.type != 'ARMATURE':
            return

        import math
        from mathutils import Matrix, Vector

        # Find all pinned bones in the armature
        pinned_bones = []
        for bone in armature.data.bones:
            if is_bone_pinned_translation(bone) or is_bone_pinned_rotation(bone):
                pose_bone = armature.pose.bones.get(bone.name)
                if pose_bone:
                    # Get bone head position in world space
                    world_matrix = armature.matrix_world @ pose_bone.matrix
                    world_pos = world_matrix.to_translation()

                    # Offset sphere outside mesh (along bone's -X axis to avoid body interior)
                    bone_x_axis = world_matrix.to_3x3() @ Vector((-1, 0, 0))  # Bone's -X axis
                    offset_distance = 0.0375  # Move 3.75cm along -X axis (25% closer)
                    world_pos_offset = world_pos + (bone_x_axis.normalized() * offset_distance)

                    pinned_bones.append((bone.name, world_pos_offset))

        if not pinned_bones:
            return

        # Create sphere vertices (icosphere approximation)
        # Using 20 vertices for a simple sphere
        sphere_verts = []
        segments = 8
        rings = 4
        radius = 0.0075  # Sphere size in world units (1/4 of original)

        for ring in range(rings + 1):
            theta = math.pi * ring / rings
            for seg in range(segments):
                phi = 2 * math.pi * seg / segments
                x = radius * math.sin(theta) * math.cos(phi)
                y = radius * math.sin(theta) * math.sin(phi)
                z = radius * math.cos(theta)
                sphere_verts.append((x, y, z))

        # Draw a sphere at each pinned bone location
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')

        for bone_name, world_pos in pinned_bones:
            # Transform sphere vertices to world position
            transformed_verts = []
            for vert in sphere_verts:
                transformed = Vector(vert) + world_pos
                transformed_verts.append(transformed)

            # Create batch for this sphere
            batch = batch_for_shader(shader, 'POINTS', {"pos": transformed_verts})

            # Draw purple sphere
            shader.bind()
            shader.uniform_float("color", (0.7, 0.3, 1.0, 1.0))  # Purple/magenta, fully opaque
            gpu.state.point_size_set(8.0)  # Larger point size for visibility
            batch.draw(shader)

    def draw_analytical_leg_debug_callback(self):
        """Draw debug overlay for analytical leg IK solver state.

        Shows hip, target, thigh direction, bend normal, knee and foot positions
        in the 3D viewport so coordinate space bugs are immediately visible.
        """
        try:
            data = self._analytical_leg_debug_draw_data
            if not data:
                return
        except (ReferenceError, AttributeError):
            return

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('ALWAYS')  # Draw on top of everything
        gpu.state.depth_mask_set(False)

        hip = data.get('hip_pos')
        target = data.get('target_pos')
        thigh_dir = data.get('thigh_dir')
        bend_normal = data.get('bend_normal')
        rest_y = data.get('rest_y')
        actual_thigh_y = data.get('actual_thigh_y')
        actual_knee = data.get('actual_knee')
        expected_knee = data.get('expected_knee')
        actual_foot = data.get('actual_foot')

        vec_length = 0.3  # 30cm vector lines for visibility

        # --- Draw lines ---
        gpu.state.line_width_set(2.0)

        lines = []
        line_colors = []

        if hip and target:
            # Hip to target (yellow)
            lines.extend([hip, target])
            line_colors.append((1.0, 1.0, 0.0, 0.5))

        if hip and thigh_dir:
            # thigh_dir vector from hip (green)
            lines.extend([hip, hip + thigh_dir * vec_length])
            line_colors.append((0.0, 1.0, 0.0, 1.0))

        if hip and bend_normal:
            # bend_normal vector from hip (cyan)
            lines.extend([hip, hip + bend_normal * vec_length])
            line_colors.append((0.0, 1.0, 1.0, 1.0))

        if hip and actual_thigh_y:
            # Actual thigh Y after rotation (magenta) — should overlap green thigh_dir
            lines.extend([hip, hip + actual_thigh_y * vec_length])
            line_colors.append((1.0, 0.0, 1.0, 1.0))

        if hip and rest_y:
            # rest Y axis from hip (gray) — should match thigh_dir after rotation
            lines.extend([hip, hip + rest_y * vec_length])
            line_colors.append((0.5, 0.5, 0.5, 0.5))

        if actual_foot and target:
            # Foot error line (red)
            lines.extend([actual_foot, target])
            line_colors.append((1.0, 0.0, 0.0, 0.7))

        # Draw all lines (each pair of vertices is one line segment)
        for i, color in enumerate(line_colors):
            pair = lines[i*2:i*2+2]
            if len(pair) == 2:
                batch = batch_for_shader(shader, 'LINES', {"pos": pair})
                shader.bind()
                shader.uniform_float("color", color)
                batch.draw(shader)

        # --- Draw points ---
        point_data = []
        if hip:
            point_data.append((hip, (1.0, 1.0, 1.0, 1.0), 12.0))      # White: hip
        if target:
            point_data.append((target, (1.0, 1.0, 0.0, 1.0), 12.0))    # Yellow: target
        if actual_knee:
            point_data.append((actual_knee, (1.0, 0.0, 0.0, 1.0), 10.0))  # Red: actual knee
        if expected_knee:
            point_data.append((expected_knee, (0.0, 1.0, 0.0, 1.0), 10.0))  # Green: expected knee
        if actual_foot:
            point_data.append((actual_foot, (1.0, 0.3, 0.0, 1.0), 10.0))  # Orange: actual foot

        for pos, color, size in point_data:
            batch = batch_for_shader(shader, 'POINTS', {"pos": [pos]})
            shader.bind()
            shader.uniform_float("color", color)
            gpu.state.point_size_set(size)
            batch.draw(shader)

        # --- Draw mouse trail (small white dots showing drag path) ---
        trail = data.get('trail', [])
        if trail:
            gpu.state.point_size_set(4.0)
            batch = batch_for_shader(shader, 'POINTS', {"pos": trail})
            shader.bind()
            shader.uniform_float("color", (1.0, 1.0, 1.0, 0.4))
            batch.draw(shader)

        # Restore GPU state
        gpu.state.line_width_set(1.0)
        gpu.state.point_size_set(1.0)
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.depth_mask_set(True)
        gpu.state.blend_set('NONE')

    def draw_analytical_arm_debug_callback(self):
        """Draw debug overlay for analytical arm IK solver state."""
        try:
            data = self._analytical_arm_debug_draw_data
            if not data:
                return
        except (ReferenceError, AttributeError):
            return

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('ALWAYS')
        gpu.state.depth_mask_set(False)

        shoulder = data.get('shoulder_pos')
        target = data.get('target_pos')
        upper_arm_dir = data.get('upper_arm_dir')
        bend_normal = data.get('bend_normal')
        rest_y = data.get('rest_y')
        actual_shoulder_y = data.get('actual_shoulder_y')
        actual_elbow = data.get('actual_elbow')
        expected_elbow = data.get('expected_elbow')
        actual_wrist = data.get('actual_wrist')

        vec_length = 0.3

        # --- Draw lines ---
        gpu.state.line_width_set(2.0)

        lines = []
        line_colors = []

        if shoulder and target:
            lines.extend([shoulder, target])
            line_colors.append((1.0, 1.0, 0.0, 0.5))  # Yellow: shoulder to target

        if shoulder and upper_arm_dir:
            lines.extend([shoulder, shoulder + upper_arm_dir * vec_length])
            line_colors.append((0.0, 1.0, 0.0, 1.0))  # Green: upper arm direction

        if shoulder and bend_normal:
            lines.extend([shoulder, shoulder + bend_normal * vec_length])
            line_colors.append((0.0, 1.0, 1.0, 1.0))  # Cyan: bend normal

        if shoulder and actual_shoulder_y:
            lines.extend([shoulder, shoulder + actual_shoulder_y * vec_length])
            line_colors.append((1.0, 0.0, 1.0, 1.0))  # Magenta: actual Y after rotation

        if shoulder and rest_y:
            lines.extend([shoulder, shoulder + rest_y * vec_length])
            line_colors.append((0.5, 0.5, 0.5, 0.5))  # Gray: rest Y axis

        if actual_wrist and target:
            lines.extend([actual_wrist, target])
            line_colors.append((1.0, 0.0, 0.0, 0.7))  # Red: wrist error

        # Collar direction line (orange)
        collar_pos = data.get('collar_pos')
        collar_y = data.get('collar_y')
        if collar_pos and collar_y:
            lines.extend([collar_pos, collar_pos + collar_y * vec_length])
            line_colors.append((1.0, 0.5, 0.0, 1.0))  # Orange: collar direction

        for i, color in enumerate(line_colors):
            pair = lines[i*2:i*2+2]
            if len(pair) == 2:
                batch = batch_for_shader(shader, 'LINES', {"pos": pair})
                shader.bind()
                shader.uniform_float("color", color)
                batch.draw(shader)

        # --- Draw points ---
        point_data = []
        if collar_pos:
            point_data.append((collar_pos, (1.0, 0.5, 0.0, 1.0), 8.0))  # Orange: collar
        if shoulder:
            point_data.append((shoulder, (1.0, 1.0, 1.0, 1.0), 12.0))
        if target:
            point_data.append((target, (1.0, 1.0, 0.0, 1.0), 12.0))
        if actual_elbow:
            point_data.append((actual_elbow, (1.0, 0.0, 0.0, 1.0), 10.0))
        if expected_elbow:
            point_data.append((expected_elbow, (0.0, 1.0, 0.0, 1.0), 10.0))
        if actual_wrist:
            point_data.append((actual_wrist, (1.0, 0.3, 0.0, 1.0), 10.0))

        for pos, color, size in point_data:
            batch = batch_for_shader(shader, 'POINTS', {"pos": [pos]})
            shader.bind()
            shader.uniform_float("color", color)
            gpu.state.point_size_set(size)
            batch.draw(shader)

        # --- Draw mouse trail ---
        trail = data.get('trail', [])
        if trail:
            gpu.state.point_size_set(4.0)
            batch = batch_for_shader(shader, 'POINTS', {"pos": trail})
            shader.bind()
            shader.uniform_float("color", (1.0, 1.0, 1.0, 0.4))
            batch.draw(shader)

        # Restore GPU state
        gpu.state.line_width_set(1.0)
        gpu.state.point_size_set(1.0)
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.depth_mask_set(True)
        gpu.state.blend_set('NONE')


class POSE_OT_clear_ik_pose(bpy.types.Operator):
    """Clear IK pose by removing keyframes and resetting rotations to rest pose"""
    bl_idname = "pose.clear_ik_pose"
    bl_label = "Clear IK Pose"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and
                context.active_object and
                context.active_object.type == 'ARMATURE')

    def execute(self, context):
        armature = context.active_object
        selected_bones = context.selected_pose_bones

        if not selected_bones:
            self.report({'WARNING'}, "No bones selected")
            return {'CANCELLED'}

        # Get current frame
        current_frame = context.scene.frame_current

        # Track what we cleared
        cleared_keyframes = 0
        reset_bones = 0

        # Get action and fcurves once (same for all bones)
        action = None
        fcurves = None
        if armature.animation_data and armature.animation_data.action:
            action = armature.animation_data.action
            if hasattr(action, 'fcurves'):
                fcurves = action.fcurves

        # Clear keyframes and reset rotations for each selected bone
        for pose_bone in selected_bones:
            bone_name = pose_bone.name

            # Remove rotation keyframes at current frame
            if fcurves:
                try:
                    for fc in fcurves:
                        if (f'pose.bones["{bone_name}"]' in fc.data_path and
                            'rotation' in fc.data_path):
                            for kf in fc.keyframe_points:
                                if abs(kf.co[0] - current_frame) < 0.001:
                                    fc.keyframe_points.remove(kf, fast=True)
                                    cleared_keyframes += 1
                                    break
                except AttributeError as e:
                    print(f"  ⚠️  Error accessing fcurves for {bone_name}: {e}")

            # Reset rotation to rest pose
            if pose_bone.rotation_mode == 'QUATERNION':
                pose_bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)  # Identity quaternion
            elif pose_bone.rotation_mode == 'AXIS_ANGLE':
                pose_bone.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
            else:  # Euler
                pose_bone.rotation_euler = (0.0, 0.0, 0.0)

            # Also reset location and scale if they're not at rest
            pose_bone.location = (0.0, 0.0, 0.0)
            pose_bone.scale = (1.0, 1.0, 1.0)

            reset_bones += 1

        # Update scene
        context.view_layer.update()

        # Report results
        self.report({'INFO'}, f"Cleared {cleared_keyframes} keyframes, reset {reset_bones} bones to rest pose")
        print(f"\n=== Clear IK Pose ===")
        print(f"  Cleared {cleared_keyframes} rotation keyframes at frame {current_frame}")
        print(f"  Reset {reset_bones} bones to rest pose")

        return {'FINISHED'}


# ============================================================================
# RIGHT-CLICK CONTEXT MENU - Pin management and bone options
# ============================================================================

class DAZ_OT_pin_translation(bpy.types.Operator):
    """Pin or unpin translation of the active bone"""
    bl_idname = "daz.pin_translation"
    bl_label = "Pin Translation"

    def execute(self, context):
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE' or not armature.data.bones.active:
            return {'CANCELLED'}
        bone_name = armature.data.bones.active.name
        data_bone = armature.data.bones[bone_name]

        if is_bone_pinned_translation(data_bone):
            # Unpin — only remove translation, keep rotation if present
            pose_bone = armature.pose.bones.get(bone_name)
            if pose_bone:
                for c in list(pose_bone.constraints):
                    if c.name == "DAZ_Pin_Translation":
                        pose_bone.constraints.remove(c)
            if "daz_pin_translation" in data_bone:
                del data_bone["daz_pin_translation"]
            if "daz_pin_location" in data_bone:
                del data_bone["daz_pin_location"]
            remove_pin_helper_empty(armature, bone_name, 'translation')
            self.report({'INFO'}, f"Unpinned Translation: {bone_name}")
            print(f"  ✓ Unpinned Translation: {bone_name}")
        else:
            pin_bone_translation(armature, bone_name)
            self.report({'INFO'}, f"Pinned Translation: {bone_name}")

        # Redraw viewports to update pin spheres
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


class DAZ_OT_pin_rotation(bpy.types.Operator):
    """Pin or unpin rotation of the active bone"""
    bl_idname = "daz.pin_rotation"
    bl_label = "Pin Rotation"

    def execute(self, context):
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE' or not armature.data.bones.active:
            return {'CANCELLED'}
        bone_name = armature.data.bones.active.name
        data_bone = armature.data.bones[bone_name]

        if is_bone_pinned_rotation(data_bone):
            # Unpin — only remove rotation, keep translation if present
            pose_bone = armature.pose.bones.get(bone_name)
            if pose_bone:
                for c in list(pose_bone.constraints):
                    if c.name == "DAZ_Pin_Rotation":
                        pose_bone.constraints.remove(c)
            if "daz_pin_rotation" in data_bone:
                del data_bone["daz_pin_rotation"]
            if "daz_pin_rotation_euler" in data_bone:
                del data_bone["daz_pin_rotation_euler"]
            remove_pin_helper_empty(armature, bone_name, 'rotation')
            self.report({'INFO'}, f"Unpinned Rotation: {bone_name}")
            print(f"  ✓ Unpinned Rotation: {bone_name}")
        else:
            pin_bone_rotation(armature, bone_name)
            self.report({'INFO'}, f"Pinned Rotation: {bone_name}")

        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


class DAZ_OT_unpin_selected(bpy.types.Operator):
    """Remove all pins from the active bone"""
    bl_idname = "daz.unpin_selected"
    bl_label = "Unpin Selected"

    def execute(self, context):
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE' or not armature.data.bones.active:
            return {'CANCELLED'}
        bone_name = armature.data.bones.active.name
        if unpin_bone(armature, bone_name):
            self.report({'INFO'}, f"Unpinned: {bone_name}")
        else:
            self.report({'INFO'}, f"{bone_name} was not pinned")

        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


class DAZ_OT_unpin_all(bpy.types.Operator):
    """Remove all pins from all bones on the active armature"""
    bl_idname = "daz.unpin_all"
    bl_label = "Unpin All"

    def execute(self, context):
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE':
            return {'CANCELLED'}
        count = 0
        for bone in armature.data.bones:
            if is_bone_pinned_translation(bone) or is_bone_pinned_rotation(bone):
                unpin_bone(armature, bone.name)
                count += 1
        self.report({'INFO'}, f"Unpinned {count} bone(s)")
        print(f"  ✓ Unpinned all: {count} bones")

        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


class DAZ_OT_toggle_pins(bpy.types.Operator):
    """Temporarily enable or disable all pin constraints (mute/unmute)"""
    bl_idname = "daz.toggle_pins"
    bl_label = "Enable Pins"

    def execute(self, context):
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE':
            return {'CANCELLED'}

        # Check current state — if any pin constraint is active, mute all; otherwise unmute all
        any_active = False
        pin_constraints = []
        for pose_bone in armature.pose.bones:
            for c in pose_bone.constraints:
                if c.name in ("DAZ_Pin_Translation", "DAZ_Pin_Rotation"):
                    pin_constraints.append(c)
                    if not c.mute:
                        any_active = True

        if not pin_constraints:
            self.report({'INFO'}, "No pins to toggle")
            return {'FINISHED'}

        # Toggle: if any active → mute all, if all muted → unmute all
        new_mute = any_active
        for c in pin_constraints:
            c.mute = new_mute

        state = "Disabled" if new_mute else "Enabled"
        self.report({'INFO'}, f"Pins {state} ({len(pin_constraints)} constraints)")
        print(f"  ✓ Pins {state}: {len(pin_constraints)} constraints")

        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


class DAZ_MT_bone_context(bpy.types.Menu):
    """Right-click context menu for DAZ bone operations"""
    bl_label = "DAZ Bone Options"
    bl_idname = "DAZ_MT_bone_context"

    def draw(self, context):
        layout = self.layout
        armature = context.active_object

        if not armature or armature.type != 'ARMATURE' or not armature.data.bones.active:
            layout.label(text="No bone selected")
            return

        bone_name = armature.data.bones.active.name
        data_bone = armature.data.bones[bone_name]

        has_trans = is_bone_pinned_translation(data_bone)
        has_rot = is_bone_pinned_rotation(data_bone)

        # Pin/Unpin Translation (toggle label)
        layout.operator("daz.pin_translation",
                        text="Unpin Translation" if has_trans else "Pin Translation",
                        icon='UNPINNED' if has_trans else 'PINNED')

        # Pin/Unpin Rotation (toggle label)
        layout.operator("daz.pin_rotation",
                        text="Unpin Rotation" if has_rot else "Pin Rotation",
                        icon='UNPINNED' if has_rot else 'PINNED')

        layout.separator()

        # Unpin Selected (only if bone has any pin)
        row = layout.row()
        row.enabled = has_trans or has_rot
        row.operator("daz.unpin_selected", icon='X')

        # Unpin All
        layout.operator("daz.unpin_all", icon='CANCEL')

        layout.separator()

        # Enable/Disable Pins (toggle label based on current state)
        any_active = False
        has_pins = False
        for pose_bone in armature.pose.bones:
            for c in pose_bone.constraints:
                if c.name in ("DAZ_Pin_Translation", "DAZ_Pin_Rotation"):
                    has_pins = True
                    if not c.mute:
                        any_active = True
                        break
            if any_active:
                break

        row = layout.row()
        row.enabled = has_pins
        row.operator("daz.toggle_pins",
                     text="Disable Pins" if any_active else "Enable Pins",
                     icon='HIDE_ON' if any_active else 'HIDE_OFF')


def register():
    # Register DAZ Bone Select operator
    bpy.utils.register_class(VIEW3D_OT_daz_bone_select)

    # Register Body/Face operators (panels live in posebridge/panel_ui.py)
    bpy.utils.register_class(POSE_OT_body_reset)
    bpy.utils.register_class(POSE_OT_face_reset)

    # Register Clear IK Pose operator
    bpy.utils.register_class(POSE_OT_clear_ik_pose)

    # Register Pin context menu and operators
    bpy.utils.register_class(DAZ_OT_pin_translation)
    bpy.utils.register_class(DAZ_OT_pin_rotation)
    bpy.utils.register_class(DAZ_OT_unpin_selected)
    bpy.utils.register_class(DAZ_OT_unpin_all)
    bpy.utils.register_class(DAZ_OT_toggle_pins)
    bpy.utils.register_class(DAZ_MT_bone_context)

    # Keyboard shortcut: Ctrl+Shift+D for "DAZ select"
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')

        # DAZ Bone Select: Ctrl+Shift+D
        km.keymap_items.new(
            VIEW3D_OT_daz_bone_select.bl_idname,
            'D', 'PRESS',
            ctrl=True, shift=True
        )

        # Clear IK Pose: Alt+Shift+R (pose mode only)
        km.keymap_items.new(
            POSE_OT_clear_ik_pose.bl_idname,
            'R', 'PRESS',
            alt=True, shift=True
        )

        print("Registered DAZ Bone Select - Activate with Ctrl+Shift+D")
        print("Registered Face Controls - Open N-panel > DAZ tab")
        print("Registered Clear IK Pose - Alt+Shift+R to reset pose with keyframes")


def unregister():
    # Unregister Body/Face operators (panels live in posebridge/panel_ui.py)
    bpy.utils.unregister_class(POSE_OT_face_reset)
    bpy.utils.unregister_class(POSE_OT_body_reset)

    # Unregister Clear IK Pose operator
    bpy.utils.unregister_class(POSE_OT_clear_ik_pose)

    # Unregister Pin context menu and operators
    bpy.utils.unregister_class(DAZ_MT_bone_context)
    bpy.utils.unregister_class(DAZ_OT_toggle_pins)
    bpy.utils.unregister_class(DAZ_OT_unpin_all)
    bpy.utils.unregister_class(DAZ_OT_unpin_selected)
    bpy.utils.unregister_class(DAZ_OT_pin_rotation)
    bpy.utils.unregister_class(DAZ_OT_pin_translation)

    # Unregister DAZ Bone Select operator
    bpy.utils.unregister_class(VIEW3D_OT_daz_bone_select)

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.get('3D View')
        if km:
            for kmi in km.keymap_items:
                if kmi.idname in (VIEW3D_OT_daz_bone_select.bl_idname,
                                 POSE_OT_clear_ik_pose.bl_idname):
                    km.keymap_items.remove(kmi)


# ============================================================================
# ANALYTICAL TWO-BONE IK SOLVER - For legs (bypasses Blender's IK solver)
# ============================================================================
# Uses law of cosines for exact solution - no optimizer, no local minima

def solve_two_bone_ik_analytical(hip_pos, target_pos, thigh_length, shin_length, knee_forward_axis=None):
    """
    Simple two-bone IK solver for leg.

    Key insight: KNEE IS A HINGE - it only bends on one axis (local X).
    So we just need to calculate the knee bend angle, not complex directions.

    Returns:
        (knee_angle, thigh_dir) tuple:
        - knee_angle: How much the shin bends at the knee (radians, positive = forward bend)
        - thigh_dir: Direction the thigh should point (world space Vector)
        Or None if unreachable
    """
    # Default knee direction: forward (-Y)
    if knee_forward_axis is None:
        knee_forward_axis = Vector((0, -1, 0))

    hip_to_target = target_pos - hip_pos
    distance = hip_to_target.length
    max_reach = thigh_length + shin_length
    min_reach = abs(thigh_length - shin_length) * 0.2

    if distance >= max_reach:
        # Fully extended - no knee bend
        direction = hip_to_target.normalized()
        return (0.0, direction)  # knee_angle=0 means straight

    if distance <= min_reach:
        return None

    # Law of cosines for the KNEE angle (angle inside the triangle at knee)
    # This is the interior angle, not the bend amount
    cos_knee_interior = (thigh_length**2 + shin_length**2 - distance**2) / (2 * thigh_length * shin_length)
    cos_knee_interior = max(-1, min(1, cos_knee_interior))
    knee_interior_angle = math.acos(cos_knee_interior)

    # Knee BEND is 180° - interior angle (straight leg = 180° interior = 0° bend)
    knee_bend = math.pi - knee_interior_angle

    # Calculate thigh direction
    # Thigh points toward the knee, which is offset from the hip-to-target line
    # Use law of cosines for hip angle
    cos_hip = (thigh_length**2 + distance**2 - shin_length**2) / (2 * thigh_length * distance)
    cos_hip = max(-1, min(1, cos_hip))
    hip_angle = math.acos(cos_hip)

    # The bend axis should be PERPENDICULAR to both:
    # 1. The hip-to-target direction
    # 2. The knee-forward direction (where we want the knee to go)
    # This ensures the thigh rotates in the plane that contains the knee
    target_dir = hip_to_target.normalized()

    # Project knee_forward_axis onto plane perpendicular to target_dir
    # This gives us the "knee direction" relative to the hip-target line
    knee_component = knee_forward_axis - (knee_forward_axis.dot(target_dir)) * target_dir
    if knee_component.length > 0.001:
        knee_component.normalize()
        # Bend axis is perpendicular to both target_dir and knee direction
        bend_axis = target_dir.cross(knee_component).normalized()
    else:
        # Fallback: use world up
        up = Vector((0, 0, 1))
        bend_axis = target_dir.cross(up)
        if bend_axis.length < 0.001:
            bend_axis = target_dir.cross(Vector((0, 1, 0)))
        bend_axis.normalize()

    # Rotate target_dir by hip_angle around bend_axis to get thigh direction
    # This rotates the thigh TOWARD the knee_forward direction
    rotation = Quaternion(bend_axis, hip_angle)
    thigh_dir = rotation @ target_dir

    print(f"  [HINGE IK] dist={distance:.3f}/{max_reach:.3f}, knee_bend={math.degrees(knee_bend):.1f}°")

    return (knee_bend, thigh_dir)


def calculate_bone_rotation_from_direction(bone, target_direction, armature):
    """
    Calculate the quaternion rotation needed to point a bone in the target direction.

    Uses ABSOLUTE rotation: calculates from REST pose, not current pose.
    This avoids accumulating errors from delta-based approaches.

    Args:
        bone: PoseBone to rotate
        target_direction: World-space direction vector the bone should point
        armature: Armature object (for matrix transforms)

    Returns:
        Quaternion rotation in bone's local space
    """
    # Get bone's REST direction in world space (no pose applied)
    # bone.bone is the EditBone/Bone, matrix_local is rest pose
    rest_matrix_world = armature.matrix_world @ bone.bone.matrix_local
    rest_direction = (rest_matrix_world.to_3x3() @ Vector((0, 1, 0))).normalized()

    # Calculate world-space rotation from REST to TARGET
    world_rotation = rest_direction.rotation_difference(target_direction)

    # Convert to local space (relative to parent's REST pose, not current pose)
    if bone.parent:
        # Parent's rest world rotation
        parent_rest_world = armature.matrix_world @ bone.parent.bone.matrix_local
        parent_rest_rot = parent_rest_world.to_quaternion()
        # Transform to local: inv(parent_rest) * world * parent_rest
        local_rotation = parent_rest_rot.inverted() @ world_rotation @ parent_rest_rot
    else:
        armature_rot = armature.matrix_world.to_quaternion()
        local_rotation = armature_rot.inverted() @ world_rotation @ armature_rot

    return local_rotation


# ============================================================================
# FABRIK IK SOLVER - Analytical Limb IK for Pins
# ============================================================================

def fabrik_solve(bone_positions, bone_lengths, target_pos, root_pos, max_iterations=10, tolerance=0.001):
    """
    FABRIK (Forward And Backward Reaching Inverse Kinematics) solver

    Args:
        bone_positions: List of Vector positions [root, joint1, joint2, ..., tip]
        bone_lengths: List of bone lengths [len0, len1, ..., len_n-1]
        target_pos: Target position for the tip (pinned position)
        root_pos: Fixed root position (collar)
        max_iterations: Maximum iterations
        tolerance: Distance tolerance for convergence

    Returns:
        List of solved bone positions
    """
    positions = [p.copy() for p in bone_positions]
    n = len(positions)

    # Check if target is reachable
    total_length = sum(bone_lengths)
    dist_to_target = (target_pos - root_pos).length

    if dist_to_target > total_length:
        # Target unreachable - stretch toward it
        direction = (target_pos - root_pos).normalized()
        positions[0] = root_pos
        for i in range(len(bone_lengths)):
            positions[i + 1] = positions[i] + direction * bone_lengths[i]
        return positions

    # FABRIK iterations
    for iteration in range(max_iterations):
        # Check convergence
        if (positions[-1] - target_pos).length < tolerance:
            break

        # Forward pass (tip to root)
        positions[-1] = target_pos  # Tip locked at target
        for i in range(n - 2, -1, -1):
            # Direction from child to parent
            direction = (positions[i] - positions[i + 1]).normalized()
            # Place parent at correct distance from child
            positions[i] = positions[i + 1] + direction * bone_lengths[i]

        # Backward pass (root to tip)
        positions[0] = root_pos  # Root locked at origin
        for i in range(n - 1):
            # Direction from parent to child
            direction = (positions[i + 1] - positions[i]).normalized()
            # Place child at correct distance from parent
            positions[i + 1] = positions[i] + direction * bone_lengths[i]

    return positions


def extract_rotation_from_positions(armature, bone_name, current_pos, next_pos, parent_matrix=None):
    """
    Extract quaternion rotation for a bone based on FABRIK positions

    SIMPLIFIED APPROACH:
    1. Compute target direction in world space (from FABRIK)
    2. Get bone's current direction in world space (including parent transforms)
    3. Compute rotation difference in world space
    4. Convert to local space

    Args:
        armature: Armature object
        bone_name: Name of the bone
        current_pos: World position of bone head (from FABRIK)
        next_pos: World position of bone tail/child head (from FABRIK)
        parent_matrix: Parent bone's world matrix (NOT USED - we compute it fresh)

    Returns:
        Quaternion rotation in bone's local space
    """
    pose_bone = armature.pose.bones[bone_name]
    edit_bone = armature.data.bones[bone_name]

    # Target direction in world space (where FABRIK wants the bone to point)
    target_direction_world = (next_pos - current_pos).normalized()

    # Get bone's CURRENT world matrix (not rest!)
    bone_world_matrix = armature.matrix_world @ pose_bone.matrix

    # Get bone's CURRENT Y-axis direction in world space
    # Bones point along +Y in Blender
    bone_current_y_world = bone_world_matrix.to_3x3() @ Vector((0, 1, 0))
    bone_current_y_world.normalize()

    # Compute rotation from CURRENT direction to TARGET direction in world space
    rotation_world = bone_current_y_world.rotation_difference(target_direction_world)

    # Convert world-space rotation to bone's local space
    # We need to account for the parent's world rotation
    if pose_bone.parent:
        parent_world_matrix = armature.matrix_world @ pose_bone.parent.matrix
        parent_world_rot = parent_world_matrix.to_3x3().to_quaternion()
    else:
        parent_world_rot = armature.matrix_world.to_3x3().to_quaternion()

    # Current bone rotation in local space
    bone_current_local = pose_bone.rotation_quaternion.copy()

    # New rotation = current_local * rotation_world (in local space)
    # But rotation_world is in world space, so convert it:
    rotation_local_delta = parent_world_rot.inverted() @ rotation_world @ parent_world_rot

    # Apply delta to current rotation
    rotation_local_new = rotation_local_delta @ bone_current_local

    return rotation_local_new


def apply_fabrik_to_limb(armature, bone_chain, pinned_bone_name, dragged_bone_name, mouse_target_pos):
    """
    Apply FABRIK IK to a limb where tip is pinned and user is dragging a middle bone

    Args:
        armature: Armature object
        bone_chain: List of bone names from root to tip (e.g., ['lCollar', 'lShldrBend', 'lForearmBend', 'lHand'])
        pinned_bone_name: Name of pinned bone (tip of chain)
        dragged_bone_name: Name of bone being dragged
        mouse_target_pos: World position of mouse target

    Returns:
        dict: {'success': bool, 'rotations': {bone_name: quaternion}}
    """
    print(f"\n=== FABRIK Solve: Pinned={pinned_bone_name}, Dragged={dragged_bone_name} ===")

    # Get current bone positions
    bone_positions = []
    bone_lengths = []

    for bone_name in bone_chain:
        pose_bone = armature.pose.bones[bone_name]
        bone_world_matrix = armature.matrix_world @ pose_bone.matrix
        bone_head_world = bone_world_matrix.translation
        bone_positions.append(bone_head_world.copy())

        # Get bone length
        edit_bone = armature.data.bones[bone_name]
        bone_length = edit_bone.length
        bone_lengths.append(bone_length)

    # Add tip position (hand position)
    tip_bone = armature.pose.bones[bone_chain[-1]]
    tip_world_matrix = armature.matrix_world @ tip_bone.matrix
    tip_tail_world = tip_world_matrix @ Vector((0, tip_bone.length, 0))
    bone_positions.append(tip_tail_world.copy())

    print(f"  Chain: {' → '.join(bone_chain)}")
    print(f"  Bone lengths: {[round(l, 3) for l in bone_lengths]}")
    print(f"  Root pos: {bone_positions[0]}")
    print(f"  Tip pos (current): {bone_positions[-1]}")

    # Get pinned target position
    pin_empty_name = f"PIN_translation_{armature.name}_{pinned_bone_name}"
    pin_empty = bpy.data.objects.get(pin_empty_name)

    if not pin_empty:
        print(f"  ✗ Pin Empty not found: {pin_empty_name}")
        return {'success': False}

    target_pos = pin_empty.matrix_world.translation.copy()
    print(f"  Target pos (pinned): {target_pos}")

    # Root position (collar)
    root_pos = bone_positions[0].copy()

    # Run FABRIK solver
    solved_positions = fabrik_solve(
        bone_positions=bone_positions,
        bone_lengths=bone_lengths,
        target_pos=target_pos,
        root_pos=root_pos,
        max_iterations=10,
        tolerance=0.001
    )

    print(f"  Solved tip pos: {solved_positions[-1]}")
    print(f"  Error: {(solved_positions[-1] - target_pos).length:.6f}")

    # Extract rotations from solved positions
    rotations = {}

    for i, bone_name in enumerate(bone_chain):
        current_pos = solved_positions[i]
        next_pos = solved_positions[i + 1]

        # Get parent matrix for local space conversion
        pose_bone = armature.pose.bones[bone_name]
        if pose_bone.parent:
            parent_world_matrix = armature.matrix_world @ pose_bone.parent.matrix
        else:
            parent_world_matrix = armature.matrix_world

        # Extract rotation
        rotation = extract_rotation_from_positions(
            armature=armature,
            bone_name=bone_name,
            current_pos=current_pos,
            next_pos=next_pos,
            parent_matrix=parent_world_matrix
        )

        rotations[bone_name] = rotation
        print(f"  {bone_name}: rotation = {rotation}")

    return {'success': True, 'rotations': rotations}


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


def apply_rotation_from_delta(bone, initial_rotation, axis, delta, sensitivity=0.01, use_armature_space=False):
    """
    Apply rotation to bone based on mouse delta.

    Args:
        bone: Pose bone to rotate
        initial_rotation: Starting rotation (quaternion)
        axis: Rotation axis ('X', 'Y', or 'Z')
        delta: Mouse movement in pixels (caller decides which: delta_x or delta_y)
        sensitivity: Rotation multiplier (radians per pixel)
        use_armature_space: If True, rotate around armature-space axis instead of bone-local axis.
                           This makes rotations consistent regardless of current bone pose.
                           Use for "spread" and "forward/back" movements on limbs.
                           Keep False for "twist" which should always be around the bone's length.
    """
    # Calculate angle directly from delta
    angle = delta * sensitivity

    # Define axis in the appropriate coordinate space
    armature_axis = Vector((
        1 if axis == 'X' else 0,
        1 if axis == 'Y' else 0,
        1 if axis == 'Z' else 0
    ))

    if use_armature_space:
        # Transform armature-space axis to bone-local space
        # bone.bone.matrix_local is the bone's rest pose matrix in armature space
        # Its inverse transforms armature-space vectors to bone-local space
        rest_matrix = bone.bone.matrix_local.to_3x3()
        local_axis = rest_matrix.inverted() @ armature_axis
        local_axis.normalize()
    else:
        # Use bone-local axis directly (current behavior)
        local_axis = armature_axis

    # Create rotation quaternion
    if use_armature_space:
        # For armature-space rotation, we need to properly transform the rotation
        # from armature space to bone-local space using quaternion conjugation:
        # R_local = rest_quat.inverted() @ R_armature @ rest_quat

        # Create rotation in armature space (around the original armature axis)
        R_armature = Quaternion(armature_axis, angle)

        # Get rest orientation as quaternion for conjugation
        rest_matrix = bone.bone.matrix_local.to_3x3()
        rest_quat = rest_matrix.to_quaternion()

        # Transform rotation from armature space to bone-local space via conjugation
        rotation_quat = rest_quat.inverted() @ R_armature @ rest_quat

        # Apply: rotation in armature space, then initial pose
        bone.rotation_quaternion = rotation_quat @ initial_rotation
    else:
        # For local-space, use the axis directly
        rotation_quat = Quaternion(local_axis, angle)
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
        {'id': 'head', 'bone_name': 'head', 'label': 'Head', 'group': 'head', 'offset': (0, 0, 0.075)},

        # Neck group (multi-bone control)
        {'id': 'neck_group', 'bone_names': ['head', 'neckUpper', 'neckLower'], 'label': 'Neck Group', 'group': 'head', 'shape': 'diamond', 'reference_bone': 'neckUpper', 'offset': (-0.075, 0, 0)},

        # Arms - Left (collar to hand)
        {'id': 'lCollar', 'bone_name': 'lCollar', 'label': 'Left Collar', 'group': 'arms'},
        {'id': 'lShldr', 'bone_names': ['lShldrBend', 'lShldrTwist'], 'label': 'Left Shoulder', 'group': 'arms'},
        {'id': 'lForeArm', 'bone_names': ['lForearmBend', 'lForearmTwist'], 'label': 'Left Forearm', 'group': 'arms'},
        {'id': 'lHand', 'bone_name': 'lHand', 'label': 'Left Hand', 'group': 'arms'},

        # Arms - Right (collar to hand)
        {'id': 'rCollar', 'bone_name': 'rCollar', 'label': 'Right Collar', 'group': 'arms'},
        {'id': 'rShldr', 'bone_names': ['rShldrBend', 'rShldrTwist'], 'label': 'Right Shoulder', 'group': 'arms'},
        {'id': 'rForeArm', 'bone_names': ['rForearmBend', 'rForearmTwist'], 'label': 'Right Forearm', 'group': 'arms'},
        {'id': 'rHand', 'bone_name': 'rHand', 'label': 'Right Hand', 'group': 'arms'},

        # Torso (Genesis 8 specific bones - top to bottom)
        {'id': 'chestUpper', 'bone_name': 'chestUpper', 'label': 'Upper Chest', 'group': 'torso'},
        {'id': 'chestLower', 'bone_name': 'chestLower', 'label': 'Lower Chest', 'group': 'torso'},
        {'id': 'abdomenUpper', 'bone_name': 'abdomenUpper', 'label': 'Upper Abdomen', 'group': 'torso'},
        {'id': 'abdomenLower', 'bone_name': 'abdomenLower', 'label': 'Lower Abdomen', 'group': 'torso'},
        {'id': 'pelvis', 'bone_name': 'pelvis', 'label': 'Pelvis', 'group': 'torso', 'position': 'tail'},

        # Legs
        {'id': 'lFoot', 'bone_name': 'lFoot', 'label': 'Left Foot', 'group': 'legs'},
        {'id': 'rFoot', 'bone_name': 'rFoot', 'label': 'Right Foot', 'group': 'legs'},
        {'id': 'lShin', 'bone_name': 'lShin', 'label': 'Left Shin', 'group': 'legs'},
        {'id': 'rShin', 'bone_name': 'rShin', 'label': 'Right Shin', 'group': 'legs'},
        {'id': 'lThigh', 'bone_names': ['lThighBend', 'lThighTwist'], 'label': 'Left Thigh', 'group': 'legs', 'position': 'tail'},
        {'id': 'rThigh', 'bone_names': ['rThighBend', 'rThighTwist'], 'label': 'Right Thigh', 'group': 'legs', 'position': 'tail'},

        # Group Nodes (diamond-shaped hierarchical controls)
        {'id': 'lArm_group', 'bone_names': ['lShldrBend', 'lShldrTwist', 'lForearmBend', 'lForearmTwist'], 'label': 'Left Arm Group', 'group': 'arms', 'shape': 'diamond', 'reference_bone': 'lShldrTwist', 'offset': (0.075, 0, 0)},
        {'id': 'rArm_group', 'bone_names': ['rShldrBend', 'rShldrTwist', 'rForearmBend', 'rForearmTwist'], 'label': 'Right Arm Group', 'group': 'arms', 'shape': 'diamond', 'reference_bone': 'rShldrTwist', 'offset': (-0.075, 0, 0)},
        {'id': 'shoulders_group', 'bone_names': ['lCollar', 'rCollar', 'lShldrBend', 'rShldrBend', 'lShldrTwist', 'rShldrTwist'], 'label': 'Shoulders Group', 'group': 'torso', 'shape': 'diamond', 'reference_bone': 'chestUpper', 'offset': (0, 0, 0.075)},
        {'id': 'torso_group', 'bone_names': ['abdomenLower', 'abdomenUpper', 'chestLower', 'chestUpper'], 'label': 'Torso Group', 'group': 'torso', 'shape': 'diamond', 'reference_bone': 'abdomenUpper', 'offset': (-0.1, 0, 0)},
        {'id': 'lLeg_group', 'bone_names': ['lThighBend', 'lThighTwist', 'lShin'], 'label': 'Left Leg Group', 'group': 'legs', 'shape': 'diamond', 'reference_bone': 'lThighTwist', 'offset': (0.075, 0, 0)},
        {'id': 'rLeg_group', 'bone_names': ['rThighBend', 'rThighTwist', 'rShin'], 'label': 'Right Leg Group', 'group': 'legs', 'shape': 'diamond', 'reference_bone': 'rThighTwist', 'offset': (-0.075, 0, 0)},
        {'id': 'legs_group', 'bone_names': ['lThighBend', 'lThighTwist', 'lShin', 'rThighBend', 'rThighTwist', 'rShin'], 'label': 'Legs Group', 'group': 'legs', 'shape': 'diamond', 'reference_bone': 'pelvis', 'offset': (0, 0, -0.275)},
    ]

    return control_points


# ============================================================================
# Face Controls — N-Panel operators and panel (replaces old PowerPose)
# ============================================================================

from daz_shared_utils import FACE_EXPRESSION_SLIDERS, FACE_VISEME_SLIDERS


def _get_posebridge_armature(context):
    """Get the PoseBridge armature (from settings or active object)."""
    settings = getattr(context.scene, 'posebridge_settings', None)
    if settings and settings.active_armature_name:
        arm = bpy.data.objects.get(settings.active_armature_name)
        if arm and arm.type == 'ARMATURE':
            return arm
    obj = context.active_object
    if obj and obj.type == 'ARMATURE':
        return obj
    if obj and obj.type == 'MESH':
        return obj.find_armature()
    return None


class POSE_OT_body_reset(bpy.types.Operator):
    """Reset all bone rotations/locations to rest pose"""
    bl_idname = "pose.body_reset"
    bl_label = "Reset Pose"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armature = _get_posebridge_armature(context)
        if not armature:
            self.report({'WARNING'}, "No armature found")
            return {'CANCELLED'}

        # Snapshot current state for PoseBridge's internal undo stack
        frame = context.scene.frame_current
        bones_snapshot = []
        for pose_bone in armature.pose.bones:
            if pose_bone.rotation_mode == 'QUATERNION':
                rot = pose_bone.rotation_quaternion.copy()
            else:
                rot = pose_bone.rotation_euler.copy()
            bones_snapshot.append((pose_bone.name, rot, pose_bone.rotation_mode))

        VIEW3D_OT_daz_bone_select._undo_stack.append({
            'type': 'body_reset',
            'frame': frame,
            'bones': bones_snapshot,
            'armature': armature,
        })

        # Reset all bones
        count = 0
        for pose_bone in armature.pose.bones:
            changed = False

            if pose_bone.rotation_mode == 'QUATERNION':
                if pose_bone.rotation_quaternion != Quaternion((1, 0, 0, 0)):
                    pose_bone.rotation_quaternion = Quaternion((1, 0, 0, 0))
                    changed = True
            elif pose_bone.rotation_mode == 'AXIS_ANGLE':
                if tuple(pose_bone.rotation_axis_angle) != (0.0, 0.0, 1.0, 0.0):
                    pose_bone.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
                    changed = True
            else:
                if tuple(pose_bone.rotation_euler) != (0.0, 0.0, 0.0):
                    pose_bone.rotation_euler = (0.0, 0.0, 0.0)
                    changed = True

            if tuple(pose_bone.location) != (0.0, 0.0, 0.0):
                pose_bone.location = (0.0, 0.0, 0.0)
                changed = True

            if tuple(pose_bone.scale) != (1.0, 1.0, 1.0):
                pose_bone.scale = (1.0, 1.0, 1.0)
                changed = True

            if changed:
                count += 1

        # Keyframe if auto-keyframe is on
        settings = getattr(context.scene, 'posebridge_settings', None)
        if settings and settings.auto_keyframe:
            for pose_bone in armature.pose.bones:
                try:
                    pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
                    pose_bone.keyframe_insert(data_path="location", frame=frame)
                except Exception:
                    pass

        context.view_layer.update()
        if context.area: context.area.tag_redraw()
        refresh_3d_viewports(context)
        self.report({'INFO'}, f"Reset {count} bones to rest pose")
        return {'FINISHED'}



class POSE_OT_face_reset(bpy.types.Operator):
    """Reset all FACS morph properties to zero"""
    bl_idname = "pose.face_reset"
    bl_label = "Reset Face"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armature = _get_posebridge_armature(context)
        if not armature:
            self.report({'WARNING'}, "No armature found")
            return {'CANCELLED'}

        # Snapshot current FACS values for undo before resetting
        frame = context.scene.frame_current
        morph_snapshot = []
        for prop_name in list(armature.keys()):
            if isinstance(prop_name, str) and prop_name.startswith('facs_'):
                current = armature.get(prop_name, 0.0)
                if isinstance(current, bool):
                    continue
                if isinstance(current, (int, float)) and current != 0.0:
                    morph_snapshot.append((prop_name, current))

        if morph_snapshot:
            VIEW3D_OT_daz_bone_select._undo_stack.append({
                'type': 'morph',
                'frame': frame,
                'morphs': morph_snapshot,
                'armature': armature,
            })

        # Reset all FACS to 0
        count = 0
        for prop_name in list(armature.keys()):
            if isinstance(prop_name, str) and prop_name.startswith('facs_'):
                current = armature.get(prop_name, 0.0)
                if isinstance(current, bool):
                    continue  # Skip boolean properties (e.g. facs_ctrl_EyeLookAuto)
                if isinstance(current, (int, float)) and current != 0.0:
                    armature[prop_name] = 0.0
                    count += 1

        # Also reset all expression/viseme sliders to 0
        settings = getattr(context.scene, 'posebridge_settings', None)
        for prop_id, _ in FACE_EXPRESSION_SLIDERS:
            if getattr(settings, prop_id, 0.0) != 0.0:
                setattr(settings, prop_id, 0.0)
        for prop_id, _ in FACE_VISEME_SLIDERS:
            if getattr(settings, prop_id, 0.0) != 0.0:
                setattr(settings, prop_id, 0.0)

        # Trigger depsgraph update
        armature.update_tag()
        context.view_layer.depsgraph.update()

        # Keyframe if auto-keyframe is on
        if settings.auto_keyframe:
            frame = context.scene.frame_current
            for prop_name in armature.keys():
                if isinstance(prop_name, str) and prop_name.startswith('facs_'):
                    try:
                        armature.keyframe_insert(data_path=f'["{prop_name}"]', frame=frame)
                    except Exception:
                        pass

        if context.area: context.area.tag_redraw()
        refresh_3d_viewports(context)
        self.report({'INFO'}, f"Reset {count} FACS properties to 0")
        return {'FINISHED'}



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

    if not result or result[0] is None:
        print("\n✗ FAILED")
        return

    target_name, ik_names, daz_names, shoulder_targets, leg_prebend, swing_twist = result

    print("\n✓ SUCCESS: IK chain created!")
    print(f"  Target: {target_name}")
    print(f"  IK bones: {ik_names}")
    print(f"  DAZ bones: {daz_names}")
    print(f"  Shoulder targets: {shoulder_targets}")
    print(f"  Swing/twist pairs: {swing_twist}")

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
