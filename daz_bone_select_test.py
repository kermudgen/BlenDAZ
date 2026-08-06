# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joshua D Rother
#
# FABRIK Pin Maintenance Test Script
#
# Stripped-down modal operator to validate FABRIK as the single solver for
# keeping pinned hands/feet planted when the hip moves or torso rotates.
# No PoseBridge, multi-character, face mode, morphs, or soft pins.
#
# Architecture: Uses Blender's native IK constraint for pin maintenance.
# At drag start, adds temporary INVERSE_KINEMATICS constraints targeting
# pin empties. Blender's own IK solver keeps pinned endpoints planted while
# native bpy.ops.transform handles mouse input. At drag end, IK results
# are baked into bone rotations and temporary constraints removed.
#
# Research basis: BlenDAZ Exploration project (31 ActivePose captures,
# DEEP_ANALYSIS_RESULTS.txt). DAZ rule: hip is translation-only, never rotates.
# Legs are isolated from spine — pelvis is the only bridge.
# Pinned bones counter-rotate to maintain orientation (active, not passive).
#
# Usage: Ctrl+Shift+F in 3D viewport to start.
#   - Hover to highlight bones (orange mesh overlay)
#   - Click to select bone
#   - P to pin/unpin translation
#   - G on hip → drag with mouse, FABRIK keeps pinned limbs planted
#   - R on torso bone → rotate with mouse, FABRIK keeps pinned limbs planted
#   - ESC to exit

import bpy
import gpu
import logging
import math
import os
import time
from gpu_extras.batch import batch_for_shader
from mathutils import Vector, Quaternion, Matrix
import bpy_extras.view3d_utils as v3d

from .fabrik_solver import (
    _compute_local_child_offset,
    FABRIK_STIFFNESS,
    TWIST_BONE_PAIRS,
)
from .daz_bone_select import (
    prepare_rig_for_ik,
    find_base_body_mesh,
    pin_bone_translation,
    unpin_bone,
    is_bone_pinned_translation,
)
from .bone_utils import get_ik_target_bone
from .genesis8_limits import GENESIS8_ROTATION_LIMITS

log = logging.getLogger(__name__)

# ============================================================================
# TEST DIAGNOSTIC LOG
# ============================================================================
_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "fabrik_pin_test.log")
_log_handle = None


def _tlog_start():
    """Open/wipe the test log file."""
    global _log_handle
    os.makedirs(_LOG_DIR, exist_ok=True)
    try:
        if _log_handle:
            _log_handle.close()
        _log_handle = open(_LOG_FILE, 'w', encoding='utf-8')
        _log_handle.write(f"=== FABRIK Pin Test Log — {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
        _log_handle.flush()
    except Exception as e:
        _tlog(f"[PIN TEST] Failed to open log: {e}")
        _log_handle = None


def _tlog(msg):
    """Write a line to the test log."""
    if _log_handle:
        try:
            _log_handle.write(msg + '\n')
            _log_handle.flush()
        except Exception:
            pass


def _tlog_end():
    """Close the test log."""
    global _log_handle
    if _log_handle:
        try:
            _log_handle.close()
        except Exception:
            pass
        _log_handle = None

# Global flag: when True, the production daz_bone_select modal passes all
# events through so the test script has exclusive control.
fabrik_test_active = False


# ============================================================================
# CHAIN DEFINITIONS
# ============================================================================
# Pin maintenance chains: root → tip (excluding the pinned endpoint bone).
# The pinned bone (lFoot, lHand) is the FABRIK target, not a chain member.

LEG_PIN_CHAINS = {
    'l': ['lThighBend', 'lShin'],         # tip target = lFoot
    'r': ['rThighBend', 'rShin'],         # tip target = rFoot
}
ARM_PIN_CHAINS = {
    # Full chain from spine root to arm tip — matches DAZ pin maintenance.
    # When hip moves, ALL bones between hip and pinned hand activate.
    # High IK stiffness (0.95) prevents initiation pop by keeping the solver
    # close to the current pose.
    'l': ['abdomenLower', 'abdomenUpper', 'chestLower', 'chestUpper',
          'lCollar', 'lShldrBend', 'lForearmBend'],   # tip target = lHand
    'r': ['abdomenLower', 'abdomenUpper', 'chestLower', 'chestUpper',
          'rCollar', 'rShldrBend', 'rForearmBend'],    # tip target = rHand
}

# Map pinned bone → (chain dict, side, tip bone name)
PIN_CHAIN_LOOKUP = {
    'lFoot': (LEG_PIN_CHAINS, 'l', 'lFoot'),
    'rFoot': (LEG_PIN_CHAINS, 'r', 'rFoot'),
    'lHand': (ARM_PIN_CHAINS, 'l', 'lHand'),
    'rHand': (ARM_PIN_CHAINS, 'r', 'rHand'),
    'lToe':  (LEG_PIN_CHAINS, 'l', 'lToe'),
    'rToe':  (LEG_PIN_CHAINS, 'r', 'rToe'),
}

# Pin maintenance stiffness overrides.
# For pin maintenance, the tip MUST stay at the pin target. High stiffness
# fights against this — the backward pass lerps bones toward original positions,
# then the forward pass re-anchors from root, pushing the tip off target.
# Use LOW stiffness so FABRIK can freely distribute displacement.
# The visual result is: spine bones bend proportionally to absorb hip movement,
# keeping the pinned hand exactly where it should be.
#
# These are deliberately lower than the DAZ DEEP_ANALYSIS values (0.5-0.65)
# because DAZ's solver has additional mechanisms we don't replicate.
# We can increase later once the pin stays planted.
PIN_STIFFNESS = {
    # From DAZ ActivePose analysis (DEEP_ANALYSIS_RESULTS.txt).
    # DAZ convention: 0=immovable, 1=flexible.
    # Our convention: 0=compliant, 1=frozen.  So: ours = 1 - DAZ.
    #
    # DAZ values → our stiffness:
    #   abdomenLower 0.596 → 0.40    abdomenUpper 0.597 → 0.40
    #   chestLower   0.589 → 0.41    chestUpper   0.483 → 0.52
    #   lCollar      0.539 → 0.46    lShldrBend   0.617 → 0.38
    #   lForearmBend 0.648 → 0.35
    'abdomenLower': 0.40,
    'abdomenUpper': 0.40,
    'chestLower':   0.41,
    'chestUpper':   0.52,
    'lCollar':      0.46,
    'rCollar':      0.46,
    'lShldrBend':   0.38,
    'rShldrBend':   0.38,
    'lForearmBend': 0.35,
    'rForearmBend': 0.35,
    # Legs
    'lThighBend':   0.15,
    'rThighBend':   0.15,
    'lShin':        0.10,
    'rShin':        0.10,
}

# Blender IK stiffness for pin maintenance.
# Sources: FIX_IK_STIFFNESS_TUNING.md, blendaz-research-findings.md,
#          IK Stiffness Reference (vault)
# 0.0 = fully compliant, 0.99 = nearly frozen.
# Pin maintenance needs collar locked (0.99) unlike drag IK (0.40) —
# the chain is already valid and shouldn't be redistributed on initiation.
# Number of MOUSEMOVE events over which stiffness ramps from 0.99 to
# real values. IK influence stays at 1.0 the whole time (hand stays
# planted). Only stiffness changes — bones gradually become responsive.
STIFFNESS_RAMP_STEPS = 8

IK_STIFFNESS = {
    'abdomenLower': 0.99, 'abdomenUpper': 0.99,
    'chestLower': 0.99, 'chestUpper': 0.99,
    'lCollar': 0.80, 'rCollar': 0.80,
    'lShldrBend': 0.10, 'rShldrBend': 0.10,
    'lForearmBend': 0.05, 'rForearmBend': 0.05,
    'lHand': 0.05, 'rHand': 0.05,
    'lThighBend': 0.50, 'rThighBend': 0.50,
    'lShin': 0.30, 'rShin': 0.30,
    'lFoot': 0.05, 'rFoot': 0.05,
}

# Bones that are valid for hip drag (G key)
HIP_BONES = {'hip', 'pelvis'}

# Bones valid for torso rotation (R key)
TORSO_BONES = {
    'abdomenLower', 'abdomenUpper',
    'chestLower', 'chestUpper',
    'neckLower', 'neckUpper',
}


# ============================================================================
# HIGHLIGHT DRAWING
# ============================================================================

_draw_handle = None
_highlight_tri_indices = []
_highlight_mesh_obj = None
_highlight_bone_name = None
_highlight_batch_cache = None
_highlight_pose_sentinel = None
_highlight_color = (1.0, 0.6, 0.0, 0.35)  # Amber, semi-transparent


def _update_highlight(context, armature, bone_name):
    """Cache triangle vertex indices for the given bone (from undeformed mesh)."""
    global _highlight_tri_indices, _highlight_mesh_obj, _highlight_bone_name
    global _highlight_batch_cache, _highlight_pose_sentinel

    mesh_obj = find_base_body_mesh(context, armature)
    if not mesh_obj or not mesh_obj.data:
        _highlight_tri_indices = []
        _highlight_mesh_obj = None
        _highlight_batch_cache = None
        return

    # If same bone+mesh, skip rebuild
    if (bone_name == _highlight_bone_name and mesh_obj == _highlight_mesh_obj
            and _highlight_tri_indices):
        return

    _highlight_bone_name = bone_name
    _highlight_mesh_obj = mesh_obj
    _highlight_batch_cache = None
    _highlight_pose_sentinel = None

    mesh = mesh_obj.data

    # Find vertex group index
    if bone_name not in mesh_obj.vertex_groups:
        _highlight_tri_indices = []
        return
    vg_idx = mesh_obj.vertex_groups[bone_name].index

    # Collect vertices where this bone has the HIGHEST weight
    weighted_verts = set()
    for vert in mesh.vertices:
        if not vert.groups:
            continue
        max_weight = 0.0
        max_group_idx = None
        for group in vert.groups:
            if group.weight > max_weight:
                max_weight = group.weight
                max_group_idx = group.group
        if max_group_idx == vg_idx and max_weight > 0.01:
            weighted_verts.add(vert.index)

    # Collect triangles from polygons that have at least one weighted vertex
    tri_indices = []
    for poly in mesh.polygons:
        if any(v in weighted_verts for v in poly.vertices):
            for i in range(1, len(poly.vertices) - 1):
                tri_indices.append((poly.vertices[0], poly.vertices[i], poly.vertices[i + 1]))

    _highlight_tri_indices = tri_indices


def _draw_highlight_callback():
    """GPU draw callback — reads deformed positions from evaluated depsgraph."""
    global _highlight_batch_cache, _highlight_pose_sentinel

    if not _highlight_tri_indices or not _highlight_mesh_obj:
        return

    # Pose sentinel: only rebuild batch when pose changes
    armature = _highlight_mesh_obj.find_armature()
    pose_sentinel = None
    if armature and _highlight_bone_name and _highlight_bone_name in armature.pose.bones:
        pb = armature.pose.bones[_highlight_bone_name]
        m = armature.matrix_world @ pb.matrix
        pose_sentinel = tuple(round(m[i][j], 4) for i in range(4) for j in range(4))

    if _highlight_batch_cache is None or _highlight_pose_sentinel != pose_sentinel:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        mesh_eval = _highlight_mesh_obj.evaluated_get(depsgraph)
        mesh_data = mesh_eval.data
        world_mat = mesh_eval.matrix_world

        offset_amount = 0.001
        tris = []
        for v0_idx, v1_idx, v2_idx in _highlight_tri_indices:
            v0_co = mesh_data.vertices[v0_idx].co
            v1_co = mesh_data.vertices[v1_idx].co
            v2_co = mesh_data.vertices[v2_idx].co
            v0_n = mesh_data.vertices[v0_idx].normal
            v1_n = mesh_data.vertices[v1_idx].normal
            v2_n = mesh_data.vertices[v2_idx].normal
            tris.extend([
                world_mat @ (v0_co + v0_n * offset_amount),
                world_mat @ (v1_co + v1_n * offset_amount),
                world_mat @ (v2_co + v2_n * offset_amount),
            ])

        if not tris:
            return

        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        _highlight_batch_cache = batch_for_shader(shader, 'TRIS', {"pos": tris})
        _highlight_pose_sentinel = pose_sentinel

    if not _highlight_batch_cache:
        return

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('ALWAYS')
    gpu.state.depth_mask_set(False)
    gpu.state.face_culling_set('BACK')

    shader.bind()
    shader.uniform_float("color", _highlight_color)
    _highlight_batch_cache.draw(shader)

    gpu.state.blend_set('NONE')
    gpu.state.depth_mask_set(True)
    gpu.state.face_culling_set('NONE')
    gpu.state.depth_test_set('LESS_EQUAL')


# ============================================================================
# RAYCAST + BONE LOOKUP
# ============================================================================

def _resolve_event_viewport(context, event):
    """Find the VIEW_3D region under the mouse cursor."""
    mouse_x, mouse_y = event.mouse_x, event.mouse_y
    for area in context.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        for region in area.regions:
            if region.type != 'WINDOW':
                continue
            if (region.x <= mouse_x <= region.x + region.width and
                    region.y <= mouse_y <= region.y + region.height):
                space = area.spaces.active
                r3d = space.region_3d if hasattr(space, 'region_3d') else None
                return area, region, space, r3d
    return None, None, None, None


def _raycast_bone(context, armature, event):
    """
    Raycast from mouse into scene, find which bone the hit point belongs to.
    Returns (bone_name, hit_location) or (None, None).
    """
    area, region, space, r3d = _resolve_event_viewport(context, event)
    if not region or not r3d:
        return None, None

    # Mouse coords relative to region
    mx = event.mouse_x - region.x
    my = event.mouse_y - region.y

    # Cast ray
    origin = v3d.region_2d_to_origin_3d(region, r3d, (mx, my))
    direction = v3d.region_2d_to_vector_3d(region, r3d, (mx, my))

    depsgraph = context.evaluated_depsgraph_get()
    result, location, normal, face_index, obj, matrix = context.scene.ray_cast(
        depsgraph, origin, direction)

    if not result or not obj or obj.type != 'MESH':
        return None, None

    # Check if this mesh is rigged to our armature
    rigged = False
    for mod in obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object == armature:
            rigged = True
            break
    if not rigged:
        return None, None

    # Find bone from vertex weights at hit point
    mesh_obj = find_base_body_mesh(context, armature)
    if not mesh_obj:
        return None, None

    # Raycast against base body mesh specifically for vertex weight lookup
    eval_mesh = mesh_obj.evaluated_get(depsgraph)
    local_origin = eval_mesh.matrix_world.inverted() @ origin
    local_dir = (eval_mesh.matrix_world.inverted().to_3x3() @ direction).normalized()

    success, loc, norm, fi, *_ = eval_mesh.ray_cast(local_origin, local_dir)
    if not success:
        # Use scene raycast result if body raycast fails
        return None, None

    # Get vertex weights from hit face.
    # ray_cast() returns a POLYGON index, not a loop_triangle index.
    mesh_data = eval_mesh.to_mesh()
    if not mesh_data or fi >= len(mesh_data.polygons):
        if mesh_data:
            eval_mesh.to_mesh_clear()
        return None, None
    poly = mesh_data.polygons[fi]
    face_verts = list(poly.vertices)

    # Accumulate bone weights across face vertices
    bone_weights = {}
    for vi in face_verts:
        vert = mesh_data.vertices[vi]
        for g in vert.groups:
            vg = mesh_obj.vertex_groups[g.group]
            bone_name = vg.name
            if bone_name in armature.pose.bones:
                bone_weights[bone_name] = bone_weights.get(bone_name, 0.0) + g.weight

    eval_mesh.to_mesh_clear()

    if not bone_weights:
        return None, None

    # Pick highest weight bone
    best_bone = max(bone_weights, key=bone_weights.get)

    # Map small bones to IK targets (e.g., finger → hand, toe → foot)
    target = get_ik_target_bone(armature, best_bone, silent=True)
    if target is None:
        # Twist/pectoral bone — use parent
        pb = armature.pose.bones.get(best_bone)
        if pb and pb.parent:
            target = pb.parent.name
        else:
            return None, None

    return target, location


# ============================================================================
# CHAIN BUILDER FOR PIN MAINTENANCE
# ============================================================================

def build_pin_maintenance_chain(armature, pinned_bone_name):
    """
    Build FABRIK chain data for maintaining a pinned endpoint.

    The chain runs from the chain root (e.g., lThighBend) to the bone just
    before the pinned bone (e.g., lShin). The pinned bone's head position
    is the FABRIK target.

    Args:
        armature: Armature object
        pinned_bone_name: Name of the pinned bone (e.g., 'lFoot', 'lHand')

    Returns:
        dict with chain data, or None if chain can't be built:
        {
            'bone_names': list of chain bone names,
            'pinned_bone': str,
            'positions': list of Vector (world space, len = bones + 1),
            'lengths': list of float (rest-pose segment lengths),
            'stiffness': list of float,
            'original_positions': list of Vector (copy of positions),
            'original_rotations': dict {bone_name: Quaternion},
            'pin_target': Vector (world space — where pinned bone should stay),
        }
    """
    lookup = PIN_CHAIN_LOOKUP.get(pinned_bone_name)
    if not lookup:
        _tlog(f"[PIN TEST] No chain defined for pinned bone: {pinned_bone_name}")
        return None

    chain_dict, side, tip_name = lookup
    chain_bone_names = chain_dict[side]
    pose_bones = armature.pose.bones

    # Verify all chain bones exist
    for name in chain_bone_names:
        if name not in pose_bones:
            _tlog(f"[PIN TEST] Chain bone '{name}' not found in armature")
            return None

    if pinned_bone_name not in pose_bones:
        _tlog(f"[PIN TEST] Pinned bone '{pinned_bone_name}' not found")
        return None

    world_mat = armature.matrix_world

    # Collect current world positions
    positions = []
    for name in chain_bone_names:
        pb = pose_bones[name]
        positions.append((world_mat @ pb.head).copy())

    # Tip position = pinned bone's head (this is the FABRIK target)
    pinned_pb = pose_bones[pinned_bone_name]
    pin_target = (world_mat @ pinned_pb.head).copy()
    positions.append(pin_target.copy())

    # Collect original rotations (chain bones + their twist partners)
    original_rotations = {}
    for name in chain_bone_names:
        pb = pose_bones[name]
        original_rotations[name] = pb.rotation_quaternion.copy()
        # Include twist bone partner
        twist = TWIST_BONE_PAIRS.get(name)
        if twist and twist in pose_bones:
            original_rotations[twist] = pose_bones[twist].rotation_quaternion.copy()

    # Also include pinned bone rotation
    original_rotations[pinned_bone_name] = pinned_pb.rotation_quaternion.copy()

    # Compute rest-pose segment lengths (must match extract_rotations_from_positions)
    lengths = []
    for i in range(len(chain_bone_names) - 1):
        data_bone = armature.data.bones[chain_bone_names[i]]
        next_data = armature.data.bones[chain_bone_names[i + 1]]
        offset = _compute_local_child_offset(
            armature, data_bone, next_data, original_rotations)
        lengths.append(max(offset.length, 0.001))

    # Last segment: from last chain bone to pinned bone
    last_data = armature.data.bones[chain_bone_names[-1]]
    pinned_data = armature.data.bones[pinned_bone_name]
    last_offset = _compute_local_child_offset(
        armature, last_data, pinned_data, original_rotations)
    lengths.append(max(last_offset.length, 0.001))

    # Stiffness weights — use pin-specific values, fall back to FABRIK_STIFFNESS
    stiffness = []
    for name in chain_bone_names:
        stiffness.append(PIN_STIFFNESS.get(name, FABRIK_STIFFNESS.get(name, 0.5)))
    # Last segment (to pinned bone) — fully compliant
    stiffness.append(0.0)

    # Get pin target from the Pin Empty (authoritative world position)
    pin_empty_name = f"PIN_translation_{armature.name}_{pinned_bone_name}"
    pin_empty = bpy.data.objects.get(pin_empty_name)
    if pin_empty:
        pin_target = pin_empty.matrix_world.to_translation().copy()
    else:
        # Fallback: current bone head position
        pin_target = (world_mat @ pinned_pb.head).copy()

    # Precompute rest-pose local offset from last chain bone to pinned bone.
    # This is the vector from last_bone.head to pinned_bone.head in the
    # last bone's rest-local coordinate system. Computed purely from rest
    # matrices — no twist bone rotation dependency. This is what CCD uses
    # to compute the FK tip position during solving.
    last_rest = armature.data.bones[chain_bone_names[-1]].matrix_local
    pinned_rest = armature.data.bones[pinned_bone_name].matrix_local
    # Pinned bone's head in armature space (rest) = pinned_rest.translation
    # Last bone's head in armature space (rest) = last_rest.translation
    # Offset in last bone's rest-local frame:
    tip_local_offset = last_rest.to_3x3().inverted() @ (
        pinned_rest.translation - last_rest.translation)

    return {
        'bone_names': list(chain_bone_names),
        'pinned_bone': pinned_bone_name,
        'positions': positions,
        'lengths': lengths,
        'stiffness': stiffness,
        'original_positions': [p.copy() for p in positions],
        'original_rotations': original_rotations,
        'pin_target': pin_target,
        'tip_local_offset': tip_local_offset,
    }


# ============================================================================
# EULER CLAMPING (replaces muted LIMIT_ROTATION constraints)
# ============================================================================

def _clamp_rotations_euler(rotations, bone_names, verbose=False):
    """
    Clamp FABRIK-solved rotations to per-axis euler limits from genesis8_limits.
    Prevents elbow hyperextension, spine over-rotation, etc.

    Converts quaternion → euler, clamps each axis, converts back.
    """
    for name in bone_names:
        limits = GENESIS8_ROTATION_LIMITS.get(name)
        if not limits:
            continue
        quat = rotations.get(name)
        if not quat:
            continue

        euler = quat.to_euler('XYZ')
        clamped = False

        for axis_idx, axis_key in enumerate(('x', 'y', 'z')):
            lim = limits.get(axis_key)
            if not lim:
                continue
            min_rad = math.radians(lim[0])
            max_rad = math.radians(lim[1])
            if euler[axis_idx] < min_rad:
                euler[axis_idx] = min_rad
                clamped = True
            elif euler[axis_idx] > max_rad:
                euler[axis_idx] = max_rad
                clamped = True

        if clamped:
            rotations[name] = euler.to_quaternion()
            if verbose:
                _tlog(f"  [CLAMP] {name}: clamped to euler "
                      f"({math.degrees(euler.x):.1f}, {math.degrees(euler.y):.1f}, {math.degrees(euler.z):.1f})")


# ============================================================================
# CCD IK SOLVER FOR PIN MAINTENANCE
# ============================================================================
# CCD (Cyclic Coordinate Descent) works entirely in rotation space.
# No position->rotation conversion needed -- eliminates the lossy step that
# caused 5-25mm FK tip error with the FABRIK+extract_rotations pipeline.
#
# Algorithm: iterate tip->root, rotating each bone so the chain's end-effector
# points at the pin target. Stiffness = rotation damping per bone.
# Euler clamping per-axis enforces joint limits each iteration.

def _ccd_get_bone_base_frame(armature, bone_name, rotations_override):
    """
    Compute the armature-space base frame (parent_posed @ rest_offset) for a bone.

    For chain bones (in rotations_override) and their children, rebuilds FK
    from solved rotations. For bones outside the chain (e.g., hip), uses
    Blender's current pb.matrix which reflects native transform updates
    (critical: hip location changes during translate).

    Returns Matrix (4x4, armature space).
    """
    pb = armature.pose.bones[bone_name]
    db = armature.data.bones[bone_name]

    if pb.parent:
        parent_posed = _ccd_get_bone_posed_matrix(
            armature, pb.parent.name, rotations_override)
        rest_offset = pb.parent.bone.matrix_local.inverted() @ db.matrix_local
        return parent_posed @ rest_offset
    else:
        # Root bone — use rest matrix (location is identity for root)
        return db.matrix_local.copy()


def _ccd_get_bone_posed_matrix(armature, bone_name, rotations_override):
    """
    Compute the armature-space POSED matrix for a bone.

    For chain bones (in rotations_override): posed = base_frame @ rotation.to_4x4()
    For non-chain bones: uses Blender's current pb.matrix directly.
    This is critical because pb.matrix reflects native translate (hip location)
    and any other transform updates, while our FK rebuild only handles rotation.
    """
    if bone_name in rotations_override:
        base = _ccd_get_bone_base_frame(armature, bone_name, rotations_override)
        rot = rotations_override[bone_name]
        return base @ rot.to_matrix().to_4x4()
    else:
        # Non-chain bone — use Blender's actual posed matrix.
        # This correctly includes pb.location (hip translation),
        # pb.rotation_quaternion, and any constraint effects.
        pb = armature.pose.bones.get(bone_name)
        if pb:
            return pb.matrix.copy()
        return armature.data.bones[bone_name].matrix_local.copy()


def _ccd_get_tip_position(armature, chain_bone_names, pinned_bone_name,
                          rotations_override, tip_local_offset):
    """
    Compute the FK tip position (pinned bone's head) in WORLD space,
    using the current rotations_override for chain bones.

    Walks the full FK chain from the last chain bone through any
    intermediate bones (twist bones) to the pinned bone, using
    Blender's current pb.rotation_quaternion for non-chain bones.
    This matches Blender's own FK exactly.
    """
    last_bone_name = chain_bone_names[-1]
    last_posed = _ccd_get_bone_posed_matrix(
        armature, last_bone_name, rotations_override)

    # Walk from last chain bone to pinned bone through intermediates.
    # For each intermediate (e.g., lForearmTwist between lForearmBend and lHand):
    #   posed = parent_posed @ rest_offset @ local_rot
    # This uses the intermediate's CURRENT rotation (not stale original).
    pinned_db = armature.data.bones[pinned_bone_name]
    current_posed = last_posed

    # Build path from last chain bone to pinned bone
    path = []
    bone = pinned_db
    last_db = armature.data.bones[last_bone_name]
    while bone and bone != last_db:
        path.append(bone)
        bone = bone.parent
    path.reverse()  # Now: [intermediate1, intermediate2, ..., pinned_bone]

    for db in path:
        parent_rest = db.parent.matrix_local if db.parent else Matrix.Identity(4)
        rest_offset = parent_rest.inverted() @ db.matrix_local
        # Use current pb.rotation_quaternion for intermediates (not in our chain)
        pb = armature.pose.bones.get(db.name)
        if pb and db.name not in rotations_override:
            local_rot = pb.rotation_quaternion
        elif db.name in rotations_override:
            local_rot = rotations_override[db.name]
        else:
            local_rot = Quaternion()
        current_posed = current_posed @ rest_offset @ local_rot.to_matrix().to_4x4()

    return armature.matrix_world @ current_posed.translation


def _solve_pin_chain_ccd(armature, chain_data):
    """
    CCD IK solver for pin maintenance.

    Iterates tip->root, rotating each bone to aim the chain end-effector
    at the pin target. Works entirely in rotation space -- no lossy
    position->rotation conversion.

    Args:
        armature: Armature object
        chain_data: dict from build_pin_maintenance_chain()

    Returns:
        dict {bone_name: Quaternion} of solved rotations, or None on failure
    """
    bone_names = chain_data['bone_names']
    pinned_bone = chain_data['pinned_bone']
    pin_target = chain_data['pin_target']
    original_rotations = chain_data['original_rotations']
    stiffness_values = chain_data['stiffness']
    tip_local_offset = chain_data['tip_local_offset']

    world_mat = armature.matrix_world
    world_inv = armature.matrix_world.inverted()
    target_arm = world_inv @ pin_target  # Pin target in armature space

    # Start from CURRENT pose bone rotations (previous frame's solution),
    # not from drag-start original_rotations. This is critical: CCD with
    # stiffness damping needs many iterations to converge from scratch, but
    # only small adjustments from the previous frame's result.
    # original_rotations is used only as the stiffness reference (rest pull).
    pose_bones = armature.pose.bones
    rotations = {}
    for name in bone_names:
        pb = pose_bones.get(name)
        if pb:
            rotations[name] = pb.rotation_quaternion.copy()
        else:
            rotations[name] = original_rotations.get(name, Quaternion()).copy()

    # Log setup
    if not hasattr(_solve_pin_chain_ccd, '_log_count'):
        _solve_pin_chain_ccd._log_count = 0
    _solve_pin_chain_ccd._log_count += 1
    verbose = _solve_pin_chain_ccd._log_count <= 5

    # CCD iterations. No damping, no stiffness — should converge fast.
    max_iterations = 50
    tolerance = 0.0005  # 0.5mm

    # --- FK VERIFICATION: compare our reconstruction vs Blender's actual ---
    if verbose:
        _tlog(f"  --- FK verification (before CCD) ---")
        for name in bone_names:
            pb = pose_bones.get(name)
            if not pb:
                continue
            # Our FK reconstruction
            our_posed = _ccd_get_bone_posed_matrix(armature, name, rotations)
            our_head = world_mat @ our_posed.translation
            # Blender's actual
            blender_head = world_mat @ pb.head
            err = (our_head - blender_head).length
            _tlog(f"    {name}: our=({our_head.x:.4f},{our_head.y:.4f},{our_head.z:.4f}) "
                  f"blender=({blender_head.x:.4f},{blender_head.y:.4f},{blender_head.z:.4f}) "
                  f"err={err:.6f}m")
        # Tip comparison
        our_tip = _ccd_get_tip_position(
            armature, bone_names, pinned_bone, rotations, tip_local_offset)
        pinned_pb = pose_bones.get(pinned_bone)
        blender_tip = world_mat @ pinned_pb.head if pinned_pb else Vector()
        tip_err_verify = (our_tip - blender_tip).length
        _tlog(f"    TIP: our=({our_tip.x:.4f},{our_tip.y:.4f},{our_tip.z:.4f}) "
              f"blender=({blender_tip.x:.4f},{blender_tip.y:.4f},{blender_tip.z:.4f}) "
              f"err={tip_err_verify:.6f}m")

    # --- PHASE 1: CCD solve without stiffness (converge freely) ---
    for iteration in range(max_iterations):
        tip_world = _ccd_get_tip_position(
            armature, bone_names, pinned_bone, rotations, tip_local_offset)
        tip_err = (tip_world - pin_target).length

        if tip_err < tolerance:
            if verbose:
                _tlog(f"[CCD] Phase 1 converged at iteration {iteration}, "
                      f"tip_err={tip_err:.6f}m")
            break

        # Sweep tip -> root (last chain bone first, root bone last)
        for bone_idx in range(len(bone_names) - 1, -1, -1):
            bone_name = bone_names[bone_idx]

            # Get this bone's base frame (armature space)
            base_frame = _ccd_get_bone_base_frame(
                armature, bone_name, rotations)
            base_pos_arm = base_frame.translation
            base_rot_3x3 = base_frame.to_3x3()
            base_inv_3x3 = base_rot_3x3.inverted()

            # Current FK tip in armature space
            tip_world = _ccd_get_tip_position(
                armature, bone_names, pinned_bone,
                rotations, tip_local_offset)
            tip_arm = world_inv @ tip_world

            # Vectors from this bone's base position to tip and target
            to_tip = (tip_arm - base_pos_arm).normalized()
            to_target = (target_arm - base_pos_arm).normalized()

            if to_tip.length < 1e-8 or to_target.length < 1e-8:
                continue

            # Rotation in armature space that swings tip toward target.
            # Light damping: each bone applies 1/3 of the full correction.
            # With only 3 arm bones, this prevents overshoot while still
            # converging quickly.
            swing_world = to_tip.rotation_difference(to_target)
            damping = 0.33
            swing_world = Quaternion().slerp(swing_world, damping)

            # Convert to bone-local rotation
            current_rot = rotations[bone_name]
            current_arm = base_rot_3x3 @ current_rot.to_matrix()
            new_arm = swing_world.to_matrix() @ current_arm
            new_local_mat = base_inv_3x3 @ new_arm
            new_local = new_local_mat.to_quaternion()

            # Ensure consistent quaternion hemisphere
            if new_local.dot(current_rot) < 0:
                new_local.negate()

            # Per-axis euler clamping (joint limits)
            limits = GENESIS8_ROTATION_LIMITS.get(bone_name)
            if limits:
                euler = new_local.to_euler('XYZ')
                for axis_idx, axis_key in enumerate(('x', 'y', 'z')):
                    lim = limits.get(axis_key)
                    if not lim:
                        continue
                    min_rad = math.radians(lim[0])
                    max_rad = math.radians(lim[1])
                    if euler[axis_idx] < min_rad:
                        euler[axis_idx] = min_rad
                    elif euler[axis_idx] > max_rad:
                        euler[axis_idx] = max_rad
                new_local = euler.to_quaternion()

            rotations[bone_name] = new_local

    # --- PHASE 2 & 3: DISABLED ---
    # Stiffness blend was causing divergence: it pulls toward the original
    # T-pose rotation, but as the hip translates the "correct" rest shape
    # changes. The fixed pull creates an impossible target, CCD overcorrects,
    # stiffness pulls back, and the cycle diverges exponentially.
    # TODO: Re-add stiffness using relative-to-current-drape approach once
    # basic CCD pin maintenance is stable.

    # Final tip error
    tip_world = _ccd_get_tip_position(
        armature, bone_names, pinned_bone, rotations, tip_local_offset)
    tip_err = (tip_world - pin_target).length

    _tlog(f"[CCD] solve #{_solve_pin_chain_ccd._log_count} {pinned_bone}: "
          f"iters={min(iteration + 1, max_iterations)}, tip_err={tip_err:.6f}m, "
          f"bones={len(bone_names)}")

    if verbose:
        _tlog(f"  target=({pin_target.x:.4f},{pin_target.y:.4f},{pin_target.z:.4f})")
        _tlog(f"  tip=({tip_world.x:.4f},{tip_world.y:.4f},{tip_world.z:.4f})")
        _tlog(f"  chain: {bone_names}")
        _tlog(f"  stiffness: {[f'{s:.2f}' for s in stiffness_values]}")
        for name in bone_names:
            q = rotations[name]
            orig = original_rotations.get(name, Quaternion())
            delta_deg = math.degrees(orig.rotation_difference(q).angle)
            _tlog(f"    {name}: ({q.w:.4f},{q.x:.4f},{q.y:.4f},{q.z:.4f}) "
                  f"delta={delta_deg:.2f}")

    return rotations


def _solve_all_pinned_chains(armature, chain_datas):
    """
    Solve all pin maintenance chains with CCD and apply rotations.

    CCD works in rotation space -- no convergence loop needed since there is
    no lossy position->rotation conversion step.

    When multiple chains share spine bones (e.g., both arms pinned),
    solves iteratively: each chain reads updated rotations after the
    previous chain was applied. Multiple passes converge toward a compromise.

    Returns True if any chain was solved.
    """
    if not chain_datas:
        return False

    # Check if chains share bones (arm chains share spine)
    has_shared = False
    if len(chain_datas) > 1:
        all_bones = [set(cd['bone_names']) for cd in chain_datas]
        for i in range(len(all_bones)):
            for j in range(i + 1, len(all_bones)):
                if all_bones[i] & all_bones[j]:
                    has_shared = True
                    break

    passes = 3 if has_shared else 1
    any_solved = False

    if not hasattr(_solve_all_pinned_chains, '_call_count'):
        _solve_all_pinned_chains._call_count = 0
    _solve_all_pinned_chains._call_count += 1
    show_log = _solve_all_pinned_chains._call_count <= 3

    for _pass in range(passes):
        for chain_data in chain_datas:
            rotations = _solve_pin_chain_ccd(armature, chain_data)
            if not rotations:
                continue

            any_solved = True
            pose_bones = armature.pose.bones

            if show_log:
                _tlog(f"[CCD APPLY] Applying {len(rotations)} rotations "
                      f"for {chain_data['pinned_bone']}:")
            for bone_name, quat in rotations.items():
                pb = pose_bones.get(bone_name)
                if pb:
                    if show_log:
                        old_q = pb.rotation_quaternion.copy()
                        delta = math.degrees(old_q.rotation_difference(quat).angle)
                        _tlog(f"    {bone_name}: delta={delta:.2f}")
                    pb.rotation_quaternion = quat

    return any_solved



# ============================================================================
# CONSTRAINT MUTING
# ============================================================================

def _mute_pin_constraints(armature, chain_datas):
    """
    Mute COPY_LOCATION pin constraints and LIMIT_ROTATION on chain bones
    so FABRIK can freely set rotations.

    Deduplicates constraints when multiple chains share bones (e.g., both arms
    share spine bones). Without dedup, the second chain would record
    original_mute=True (already muted by first chain) and restore would
    leave the constraint muted.

    Returns list of (pose_bone, constraint, original_mute) for restoration.
    """
    muted = []
    seen = set()  # Track constraint IDs to avoid duplicates

    for chain_data in chain_datas:
        pinned_bone = chain_data['pinned_bone']
        pb = armature.pose.bones.get(pinned_bone)
        if pb:
            for c in pb.constraints:
                if c.type == 'COPY_LOCATION' and id(c) not in seen:
                    seen.add(id(c))
                    muted.append((pb, c, c.mute))
                    c.mute = True

        # Mute LIMIT_ROTATION on chain bones
        for bone_name in chain_data['bone_names']:
            pb = armature.pose.bones.get(bone_name)
            if not pb:
                continue
            for c in pb.constraints:
                if c.type == 'LIMIT_ROTATION' and id(c) not in seen:
                    seen.add(id(c))
                    muted.append((pb, c, c.mute))
                    c.mute = True

    return muted


def _unmute_constraints(muted_list):
    """Restore muted constraints to their original state."""
    for pb, constraint, original_mute in muted_list:
        try:
            constraint.mute = original_mute
        except ReferenceError:
            pass


# ============================================================================
# BAKE CURRENT ROTATIONS (pre-solve snapshot)
# ============================================================================

def _bake_visual_rotations(armature, chain_datas):
    """
    Bake constraint-applied rotations into rotation_quaternion for chain bones.
    Call AFTER view_layer.update() so constraints are evaluated.
    """
    for chain_data in chain_datas:
        pose_bones = armature.pose.bones
        for bone_name in chain_data['bone_names']:
            pb = pose_bones.get(bone_name)
            if not pb:
                continue
            # Extract bone-local rotation from the armature-space posed matrix
            parent_mat = pb.parent.matrix if pb.parent else Matrix.Identity(4)
            parent_rest = pb.parent.bone.matrix_local if pb.parent else Matrix.Identity(4)
            rest_offset = parent_rest.inverted() @ pb.bone.matrix_local
            base_frame = parent_mat @ rest_offset
            local_mat = base_frame.inverted() @ pb.matrix
            local_rot = local_mat.to_quaternion()

            pb.rotation_quaternion = local_rot
            # Update original_rotations for FABRIK
            chain_data['original_rotations'][bone_name] = local_rot.copy()

            # Also bake twist partner
            twist = TWIST_BONE_PAIRS.get(bone_name)
            if twist:
                tpb = pose_bones.get(twist)
                if tpb:
                    chain_data['original_rotations'][twist] = tpb.rotation_quaternion.copy()


# ============================================================================
# MODAL OPERATOR
# ============================================================================

class VIEW3D_OT_fabrik_pin_test(bpy.types.Operator):
    """FABRIK Pin Maintenance Test — hover, select, pin, hip drag, torso rotate"""
    bl_idname = "view3d.fabrik_pin_test"
    bl_label = "FABRIK Pin Test"
    bl_options = {'REGISTER'}

    # --- State ---
    # NOTE: No type annotations here — Blender interprets annotations as
    # property definitions on Operator subclasses. Use plain assignment.
    _armature_name = ""         # Store by name, resolve each frame (survives addon reload)
    _hovered_bone = None
    _selected_bone = None

    # Drag/rotate state
    _active_drag = None          # 'translate', 'rotate', or None
    _chain_datas = []            # Active pin chain data dicts
    _muted_constraints = []      # For restore on exit
    _ik_constraints = []         # Temporary IK constraints for pin maintenance
    _pre_drag_rotations = {}     # Snapshot for cancel
    _drag_bone_name = None       # Bone being dragged/rotated

    def _get_armature(self):
        """Resolve armature from stored name. Survives addon reload."""
        if not self._armature_name:
            return None
        return bpy.data.objects.get(self._armature_name)

    def _find_daz_armature(self, context):
        """Find the first DAZ armature in the scene."""
        for obj in context.scene.objects:
            if obj.type != 'ARMATURE':
                continue
            # DAZ rigs have 'hip' bone
            if 'hip' in obj.data.bones:
                return obj
        return None

    def _get_pinned_endpoints(self, armature):
        """Return list of bone names that are currently pinned."""
        pinned = []
        for bone_name in PIN_CHAIN_LOOKUP:
            bone = armature.data.bones.get(bone_name)
            if bone and bone.get("daz_pin_translation", False):
                pinned.append(bone_name)
        return pinned

    def _start_drag(self, context, event, drag_type):
        """
        Start hip translate or torso rotate with analytical pin solving.

        Uses a feedback controller (no Blender IK constraints):
        - Each MOUSEMOVE: move hip, view_layer.update(), read hand FK
          position from depsgraph, correct chain analytically.
        - Phase 1: Spine compensation (proportional CCD on torso bones)
        - Phase 2: Analytical arm solve (mcjAutoLimb style: aim shoulder
          + cosine-rule elbow bend)
        - COPY_LOCATION stays active as visual safety net.
        """
        armature = self._get_armature()
        pinned = self._get_pinned_endpoints(armature)

        if not pinned:
            _tlog("[PIN TEST] No pinned endpoints — normal transform")
            self._active_drag = None
            return False

        sel = self._selected_bone
        _tlog(f"\n{'='*60}")
        _tlog(f"DRAG START: {drag_type} on '{sel}'")
        _tlog(f"  Pinned endpoints: {pinned}")

        # Ensure scene is up to date
        context.view_layer.update()

        muted = []

        # NO IK CONSTRAINTS — feedback controller approach.
        #
        # Blender's IK solver computes from scratch every eval and snaps
        # the chain to its own solution (40°+ deltas on forearm/shoulder).
        # Instead, we own the entire solve:
        #
        # Each MOUSEMOVE:
        #   1. Move hip
        #   2. view_layer.update() — chain moves with hip, hand drifts
        #   3. Read hand world pos from evaluated depsgraph (ground truth)
        #   4. Compute error = hand_actual - pin_target
        #   5. Single CCD pass: rotate arm bones to close the gap
        #   6. (No second update — corrections applied, next frame reads
        #      from Blender's eval which includes our rotations)
        #
        # No internal FK model → no divergence. Each frame reads from
        # Blender's actual evaluation. Small per-frame corrections.
        # COPY_LOCATION stays ACTIVE on the hand — it keeps the hand
        # visually locked to the pin target while we rotate the chain
        # to close the gap underneath. On release, we mute COPY_LOCATION
        # and bake, and the chain should be close enough that there's
        # no visible snap.

        # DON'T mute COPY_LOCATION — it's our safety net during drag.
        # DON'T add IK constraints — we solve manually.
        # Just record which constraints to unmute on cancel.
        for bone_name in pinned:
            pb_pinned = armature.pose.bones.get(bone_name)
            if pb_pinned:
                for c in pb_pinned.constraints:
                    if c.type == 'COPY_LOCATION':
                        muted.append((pb_pinned, c, c.mute))

        # Build correction chain data for each pinned endpoint
        pin_chains = []
        for bone_name in pinned:
            lookup = PIN_CHAIN_LOOKUP.get(bone_name)
            if not lookup:
                continue
            chain_dict, side, tip_name = lookup
            chain_bone_names = chain_dict[side]
            pin_empty_name = f"PIN_translation_{armature.name}_{bone_name}"
            pin_empty = bpy.data.objects.get(pin_empty_name)
            if not pin_empty:
                _tlog(f"  WARNING: Pin empty '{pin_empty_name}' not found")
                continue
            pin_chains.append({
                'pinned_bone': bone_name,
                'chain_bones': chain_bone_names,  # root→tip order
                'pin_target': pin_empty.location.copy(),  # world space
                'pin_empty': pin_empty,
            })
            _tlog(f"  Feedback chain: {chain_bone_names} → {bone_name} "
                  f"target={tuple(round(v,3) for v in pin_empty.location)}")

        if not pin_chains:
            _tlog("[PIN TEST] No pin chains — normal transform")
            self._active_drag = None
            return False

        # Snapshot for cancel
        pre_drag = {}
        all_chain_bones = set()
        for pc in pin_chains:
            for bn in pc['chain_bones']:
                all_chain_bones.add(bn)
            all_chain_bones.add(pc['pinned_bone'])
        for bn in all_chain_bones:
            pb = armature.pose.bones.get(bn)
            if pb:
                pre_drag[bn] = pb.rotation_quaternion.copy()
        drag_pb = armature.pose.bones.get(sel)
        if drag_pb:
            pre_drag['_drag_location'] = drag_pb.location.copy()
            pre_drag['_drag_rotation'] = drag_pb.rotation_quaternion.copy()

        self._muted_constraints = muted
        self._ik_constraints = []  # No IK constraints used
        self._pre_drag_rotations = pre_drag
        self._active_drag = drag_type
        self._drag_bone_name = sel
        self._pin_chains = pin_chains
        self._frame_count = 0
        self._spine_need_smooth = 0.0  # Smoothed spine engagement
        self._last_mouse = None        # For mouse speed tracking
        self._mouse_speed = 0.0        # Pixels per event

        # Store original pin positions BEFORE pre-settle moves them
        self._pin_original_pos = {}
        for pc in pin_chains:
            self._pin_original_pos[pc['pinned_bone']] = pc['pin_empty'].location.copy()

        # We own the drag loop. Native G doesn't write intermediate
        # positions to pose_bone.location during drag (only on confirm),
        # so view_layer.update() can't see the movement. We must move
        # the hip ourselves using region_2d_to_location_3d().
        drag_pb = armature.pose.bones.get(sel)
        if drag_pb:
            self._drag_start_mouse = (event.mouse_x, event.mouse_y)
            self._drag_start_location = drag_pb.location.copy()
            # World position of bone head for depth reference
            self._drag_bone_world_pos = (armature.matrix_world @ drag_pb.head).copy()
        # ── PRE-SETTLE: Move pin empty to FK hand position ──
        # Instead of solving the chain to reach the pin (which diverges),
        # move the pin empty to where the FK chain naturally puts the hand.
        # This means the solver starts with zero error on frame 0.
        # COPY_LOCATION will instantly move the hand to the new pin position,
        # but since we're setting pin = FK position, there's no visual change.
        context.view_layer.update()
        depsgraph = context.evaluated_depsgraph_get()
        armature_eval = armature.evaluated_get(depsgraph)
        for pc in self._pin_chains:
            hp_name = None
            pb_hand = armature.pose.bones.get(pc['pinned_bone'])
            if pb_hand and pb_hand.parent:
                hp_name = pb_hand.parent.name
            if hp_name:
                pb_hp = armature_eval.pose.bones.get(hp_name)
                if pb_hp:
                    fk_pos = armature.matrix_world @ pb_hp.tail
                    old_pin = pc['pin_empty'].location.copy()
                    err = (old_pin - fk_pos).length
                    if err > 0.005:  # > 5mm mismatch
                        pc['pin_empty'].location = fk_pos
                        _tlog(f"  Pre-settle: moved pin {pc['pinned_bone']} "
                              f"from {tuple(round(v,3) for v in old_pin)} "
                              f"to FK pos {tuple(round(v,3) for v in fk_pos)} "
                              f"(was {err*100:.1f}cm off)")
                    else:
                        _tlog(f"  Pre-settle: {pc['pinned_bone']} already at FK pos (err={err*100:.1f}cm)")
        context.view_layer.update()

        # Re-snapshot rotations AFTER settle (so cancel restores settled state)
        for bn in list(pre_drag.keys()):
            if bn.startswith('_'):
                continue
            pb = armature.pose.bones.get(bn)
            if pb:
                pre_drag[bn] = pb.rotation_quaternion.copy()
        self._pre_drag_rotations = pre_drag

        self._frame_count = 0
        _tlog(f"  Manual drag started ({drag_type}) — we own the loop")
        return True

    def _apply_translate(self, context, event, armature, drag_pb, region, r3d):
        """Apply mouse delta as hip bone translation on the screen plane.

        Uses Blender's own region_2d_to_location_3d() for correct
        perspective/ortho projection at the bone's depth.
        """
        mx_local = event.mouse_x - region.x
        my_local = event.mouse_y - region.y
        sx_local = self._drag_start_mouse[0] - region.x
        sy_local = self._drag_start_mouse[1] - region.y

        # Blender's utility: unproject 2D mouse to 3D at a given depth.
        # Using the bone's starting world position as depth reference
        # gives screen-plane movement at the bone's distance from camera.
        depth = self._drag_bone_world_pos
        start_3d = v3d.region_2d_to_location_3d(region, r3d, (sx_local, sy_local), depth)
        curr_3d = v3d.region_2d_to_location_3d(region, r3d, (mx_local, my_local), depth)

        if start_3d is None or curr_3d is None:
            return

        world_delta = curr_3d - start_3d

        # Convert world delta to bone-local space.
        # pose_bone.location is in the bone's rest-space.
        # For a root bone: rest-space = armature_world @ bone.matrix_local
        # For a child bone: rest-space = armature_world @ parent.matrix @ rest_offset
        if drag_pb.parent:
            rest_offset = drag_pb.parent.bone.matrix_local.inverted() @ drag_pb.bone.matrix_local
            parent_world = armature.matrix_world @ drag_pb.parent.matrix @ rest_offset
        else:
            parent_world = armature.matrix_world @ drag_pb.bone.matrix_local
        local_delta = parent_world.inverted().to_3x3() @ world_delta

        drag_pb.location = self._drag_start_location + local_delta

    def _apply_rotate(self, context, event, armature, drag_pb, region, r3d):
        """Apply mouse horizontal delta as bone rotation around view Z axis."""
        sx, sy = self._drag_start_mouse
        mx, my = event.mouse_x, event.mouse_y
        dx = mx - sx

        # Sensitivity: pixels to radians
        angle = dx * 0.005

        # Rotate around the view's forward axis (Z in view space)
        view_mat = r3d.view_matrix
        view_z = Vector((view_mat[2][0], view_mat[2][1], view_mat[2][2])).normalized()

        # Convert view-Z to bone-local axis
        bone_world_mat = armature.matrix_world @ drag_pb.matrix
        bone_inv = bone_world_mat.to_3x3().inverted()
        local_axis = (bone_inv @ view_z).normalized()

        # Build incremental rotation in bone-local space
        rot = Quaternion(local_axis, angle)

        # Apply on top of original rotation
        new_rot = rot @ self._drag_start_rotation
        if new_rot.dot(self._drag_start_rotation) < 0:
            new_rot.negate()
        drag_pb.rotation_quaternion = new_rot

    def _apply_world_rotation(self, armature, armature_eval, bone_name, world_rot):
        """
        Apply a world-space rotation delta to a bone, converting to local space.
        Uses the evaluated depsgraph for accurate parent transforms.
        Returns True if applied.
        """
        pb = armature.pose.bones.get(bone_name)
        pb_eval = armature_eval.pose.bones.get(bone_name)
        if not pb or not pb_eval:
            return False

        # Current world rotation of this bone
        bone_world_mat = armature.matrix_world @ pb_eval.matrix
        bone_world_rot = bone_world_mat.to_quaternion()

        # Apply world-space delta: new_world = world_rot @ old_world
        new_world = world_rot @ bone_world_rot

        # Convert to local: undo parent world rotation, then undo rest offset
        if pb.parent:
            parent_world = armature.matrix_world @ pb_eval.parent.matrix
            parent_inv = parent_world.to_quaternion().inverted()
        else:
            parent_inv = armature.matrix_world.to_quaternion().inverted()

        rest_local = pb.bone.matrix_local.to_quaternion()
        if pb.parent:
            parent_rest = pb.parent.bone.matrix_local.to_quaternion()
            rest_offset = parent_rest.inverted() @ rest_local
        else:
            rest_offset = rest_local

        new_local = rest_offset.inverted() @ parent_inv @ new_world
        new_local.normalize()
        if new_local.dot(pb.rotation_quaternion) < 0:
            new_local.negate()

        pb.rotation_quaternion = new_local
        return True

    def _correct_pin_chains(self, context, armature):
        """
        Analytical arm-only pin correction (mcjAutoLimb style).

        Each frame per pinned limb, 3 iterations of:
          Step 1: SPINE — rotate collar/chest/abdomen toward target (if arm maxed)
          Step 2: AIM — rotate shoulder so limb points at target
          Step 3: BEND — cosine-rule elbow angle to match distance

        Spine engages when the arm alone can't reach. This matches DAZ's
        ActivePose behavior where torso bends to absorb large hip displacements.
        When ALL bones have reached their limits, the pin releases gracefully.
        COPY_LOCATION stays active as visual safety net.
        """
        if not hasattr(self, '_pin_chains') or not self._pin_chains:
            return

        # Mouse speed → adaptive parameters
        # Slow (<5px): gentle corrections, fewer iters
        # Fast (>30px): aggressive corrections, more iters
        speed = getattr(self, '_mouse_speed', 0.0)
        speed_factor = max(0.0, min(1.0, speed / 30.0))  # 0..1

        NUM_ITERS = 3 if speed_factor < 0.5 else 4
        arm_blend = 0.80 + speed_factor * 0.15  # 0.80..0.95

        for pc in self._pin_chains:
            pin_target = pc['pin_empty'].matrix_world.to_translation()
            chain_bones = pc['chain_bones']

            # Classify chain bones
            forearm_name = shldr_name = collar_name = hand_parent_name = None
            spine_names = []  # abdomen/chest bones, root→tip order
            for bn in chain_bones:
                bl = bn.lower()
                if 'forearm' in bl and 'twist' not in bl:
                    forearm_name = bn
                elif 'shldr' in bl and 'twist' not in bl:
                    shldr_name = bn
                elif 'collar' in bl:
                    collar_name = bn
                elif 'abdomen' in bl or 'chest' in bl:
                    spine_names.append(bn)
            pb_hand = armature.pose.bones.get(pc['pinned_bone'])
            if pb_hand and pb_hand.parent:
                hand_parent_name = pb_hand.parent.name

            if not forearm_name or not shldr_name or not hand_parent_name:
                continue

            # Spine correction bones: collar + spine, tip→root order
            # (collar first since it's closest to the arm)
            spine_correct_names = []
            if collar_name:
                spine_correct_names.append(collar_name)
            spine_correct_names.extend(reversed(spine_names))

            error_dist = 0.0
            new_x = 0.0
            spine_need = self._spine_need_smooth

            # ── PHASE 1: Compute spine_need ONCE per frame ──
            # (Outside the iteration loop to prevent 3x smoothing)
            context.view_layer.update()
            depsgraph = context.evaluated_depsgraph_get()
            armature_eval = armature.evaluated_get(depsgraph)

            pb_shldr_eval = armature_eval.pose.bones.get(shldr_name)
            pb_forearm_eval = armature_eval.pose.bones.get(forearm_name)
            pb_hand_parent_eval = armature_eval.pose.bones.get(hand_parent_name)
            pb_forearm = armature.pose.bones.get(forearm_name)
            if not pb_shldr_eval or not pb_forearm_eval or not pb_hand_parent_eval:
                continue

            hand_fk_pos = armature.matrix_world @ pb_hand_parent_eval.tail
            shldr_pivot = armature.matrix_world @ pb_shldr_eval.head
            forearm_head_ws = armature.matrix_world @ pb_forearm_eval.head
            upper_len = (forearm_head_ws - shldr_pivot).length
            forearm_len = (hand_fk_pos - forearm_head_ws).length
            target_dist = (pin_target - shldr_pivot).length
            arm_reach = upper_len + forearm_len

            # What elbow would the arm need WITHOUT spine help?
            if arm_reach > 0.001 and target_dist < arm_reach:
                cos_C = (upper_len**2 + forearm_len**2 - target_dist**2) / (
                    2 * upper_len * forearm_len)
                cos_C = max(-1.0, min(1.0, cos_C))
                raw_elbow_deg = math.degrees(math.pi - math.acos(cos_C))
            else:
                raw_elbow_deg = 0.0

            if target_dist >= arm_reach:
                spine_need_raw = 1.0
            elif raw_elbow_deg < 20.0:
                spine_need_raw = max(0.0, 1.0 - raw_elbow_deg / 20.0)
            else:
                spine_need_raw = 0.0

            # Smooth — once per frame, not per iteration
            if spine_need_raw > self._spine_need_smooth:
                rate = 0.3 + speed_factor * 0.3
            else:
                rate = 0.10 + speed_factor * 0.10
            self._spine_need_smooth += (spine_need_raw - self._spine_need_smooth) * rate
            spine_need = self._spine_need_smooth

            # ── PHASE 2: Apply spine correction ONCE ──
            if spine_correct_names:
                for spine_bn in spine_correct_names:
                    pb_spine = armature.pose.bones.get(spine_bn)
                    pb_spine_eval = armature_eval.pose.bones.get(spine_bn)
                    if not pb_spine or not pb_spine_eval:
                        continue

                    pre_drag_q = self._pre_drag_rotations.get(spine_bn)
                    if not pre_drag_q:
                        continue

                    if spine_need > 0.01:
                        stiff = PIN_STIFFNESS.get(spine_bn, 0.5)
                        gain = (1.0 - stiff) * 0.25
                        if gain < 0.005:
                            continue

                        pivot = armature.matrix_world @ pb_spine_eval.head
                        to_hand = hand_fk_pos - pivot
                        to_target = pin_target - pivot
                        if to_hand.length < 0.001 or to_target.length < 0.001:
                            continue

                        spine_rot = to_hand.rotation_difference(to_target)
                        spine_rot = Quaternion().slerp(spine_rot, gain * spine_need)
                        self._apply_world_rotation(armature, armature_eval,
                                                   spine_bn, spine_rot)
                        hand_fk_pos = pivot + spine_rot @ (hand_fk_pos - pivot)
                    else:
                        # Spring back toward pre-drag — aggressive so spine
                        # keeps up with hip return. Rate scales with how far
                        # spine_need has dropped (lower need = faster return).
                        current_q = pb_spine.rotation_quaternion.copy()
                        pdq = pre_drag_q.copy()
                        if current_q.dot(pdq) < 0:
                            pdq.negate()
                        # spine_need is 0..0.01 here. Use 0.8 base rate.
                        spring_rate = 0.8 + speed_factor * 0.15
                        restored = current_q.slerp(pdq, spring_rate)
                        pb_spine.rotation_quaternion = restored

            # ── PHASE 3: Iterative arm solve (aim + bend) ──
            for iteration in range(NUM_ITERS):
                context.view_layer.update()
                depsgraph = context.evaluated_depsgraph_get()
                armature_eval = armature.evaluated_get(depsgraph)

                pb_shldr_eval = armature_eval.pose.bones.get(shldr_name)
                pb_forearm_eval = armature_eval.pose.bones.get(forearm_name)
                pb_hand_parent_eval = armature_eval.pose.bones.get(hand_parent_name)
                pb_forearm = armature.pose.bones.get(forearm_name)
                if not pb_shldr_eval or not pb_forearm_eval or not pb_hand_parent_eval:
                    break

                hand_fk_pos = armature.matrix_world @ pb_hand_parent_eval.tail
                shldr_pivot = armature.matrix_world @ pb_shldr_eval.head

                error_dist = (pin_target - hand_fk_pos).length
                if error_dist < 0.002:
                    break

                # AIM shoulder toward target
                vec_to_hand = hand_fk_pos - shldr_pivot
                vec_to_target = pin_target - shldr_pivot
                aim_rot = Quaternion()  # identity
                if vec_to_hand.length > 0.0001 and vec_to_target.length > 0.0001:
                    aim_rot = vec_to_hand.rotation_difference(vec_to_target)
                    self._apply_world_rotation(armature, armature_eval,
                                               shldr_name, aim_rot)

                # BEND forearm (cosine rule)
                # Use PREDICTED positions post-aim (aim rotates around shldr head)
                forearm_head_ws = armature.matrix_world @ pb_forearm_eval.head
                forearm_head_aimed = shldr_pivot + aim_rot @ (forearm_head_ws - shldr_pivot)
                hand_fk_aimed = shldr_pivot + aim_rot @ (hand_fk_pos - shldr_pivot)
                upper_len = (forearm_head_aimed - shldr_pivot).length
                forearm_len = (hand_fk_aimed - forearm_head_aimed).length
                target_dist = (pin_target - shldr_pivot).length

                if target_dist >= upper_len + forearm_len:
                    desired_x = 0.0
                elif target_dist <= abs(upper_len - forearm_len):
                    desired_x = math.radians(135)
                else:
                    cos_C = (upper_len**2 + forearm_len**2 - target_dist**2) / (
                        2 * upper_len * forearm_len)
                    cos_C = max(-1.0, min(1.0, cos_C))
                    desired_x = math.pi - math.acos(cos_C)

                limits = GENESIS8_ROTATION_LIMITS.get(forearm_name, {})
                x_lim = limits.get('x', (-5, 130))
                # Clamp to 0 minimum — no hyperextension during pin solve
                x_min = math.radians(max(0, x_lim[0]))
                x_max = math.radians(x_lim[1])
                desired_x = max(x_min, min(x_max, desired_x))

                current_euler = pb_forearm.rotation_quaternion.to_euler('XYZ')
                original_x = current_euler.x
                new_x = original_x + (desired_x - original_x) * arm_blend
                current_euler.x = new_x
                new_q = current_euler.to_quaternion()
                if new_q.dot(pb_forearm.rotation_quaternion) < 0:
                    new_q.negate()
                pb_forearm.rotation_quaternion = new_q

            # ── PHASE 4: Graceful pin release ──
            # After all corrections, if the FK hand is still far from
            # the pin target, move the pin empty to the FK hand position.
            # This keeps the figure intact — the chain drives the hand,
            # not the constraint stretching the mesh. When the user
            # drags back, the pin empty returns to its original position.
            context.view_layer.update()
            depsgraph = context.evaluated_depsgraph_get()
            armature_eval = armature.evaluated_get(depsgraph)
            pb_hp_final = armature_eval.pose.bones.get(hand_parent_name)
            if pb_hp_final:
                hand_fk_final = armature.matrix_world @ pb_hp_final.tail
                error_dist = (pin_target - hand_fk_final).length
                pin_empty = pc['pin_empty']

                original_pin = self._pin_original_pos.get(pc['pinned_bone'], pin_target.copy())

                if error_dist > 0.02:  # > 2cm — chain can't reach
                    # Move pin empty toward FK hand position
                    # Blend smoothly to avoid pop
                    current_pin = pin_empty.location.copy()
                    pin_empty.location = current_pin.lerp(hand_fk_final, 0.5)
                else:
                    # Chain is reaching — move pin back toward original
                    current_pin = pin_empty.location.copy()
                    pin_empty.location = current_pin.lerp(original_pin, 0.3)

            # Log final state
            if self._frame_count % 10 == 0:
                _tlog(f"  Frame {self._frame_count}: err={error_dist*100:.1f}cm "
                      f"elbow={math.degrees(new_x):.1f}deg "
                      f"spine={spine_need:.2f} spd={speed:.0f}px "
                      f"iters={iteration+1}")

    def _end_drag(self, context, cancelled=False):
        """Clean up after drag/rotate ends."""
        armature = self._get_armature()

        if cancelled and self._pre_drag_rotations:
            # Restore original rotations
            for bn, quat in self._pre_drag_rotations.items():
                if bn == '_drag_location':
                    pb = armature.pose.bones.get(self._drag_bone_name)
                    if pb:
                        pb.location = quat  # It's actually a Vector
                    continue
                if bn == '_drag_rotation':
                    pb = armature.pose.bones.get(self._drag_bone_name)
                    if pb:
                        pb.rotation_quaternion = quat
                    continue
                if bn.startswith('_'):
                    continue
                pb = armature.pose.bones.get(bn)
                if pb:
                    pb.rotation_quaternion = quat

        if not cancelled and armature and hasattr(self, '_pin_chains'):
            # Log final chain error before releasing COPY_LOCATION
            context.view_layer.update()
            depsgraph = context.evaluated_depsgraph_get()
            armature_eval = armature.evaluated_get(depsgraph)
            _tlog(f"\n  --- End drag: final chain errors ---")
            for pc in self._pin_chains:
                pin_target = pc['pin_empty'].matrix_world.to_translation()
                pb_eval = armature_eval.pose.bones.get(pc['pinned_bone'])
                if pb_eval:
                    fk_pos = armature.matrix_world @ pb_eval.head
                    err = (pin_target - fk_pos).length
                    _tlog(f"    {pc['pinned_bone']}: FK error={err*100:.2f}cm")

        # Restore pin empties to original positions if they were moved
        # during graceful release
        if hasattr(self, '_pin_original_pos') and self._pin_original_pos:
            for bone_name, orig_pos in self._pin_original_pos.items():
                pin_empty_name = f"PIN_translation_{armature.name}_{bone_name}"
                pin_empty = bpy.data.objects.get(pin_empty_name)
                if pin_empty:
                    pin_empty.location = orig_pos
                    _tlog(f"  Restored pin empty '{pin_empty_name}' to original pos")
            self._pin_original_pos = {}

        # COPY_LOCATION stays active — the pin is still holding.

        # Update scene
        context.view_layer.update()

        self._active_drag = None
        self._pin_chains = []
        self._pre_drag_rotations = {}
        self._drag_bone_name = None
        _tlog("[PIN TEST] Drag ended" + (" (cancelled)" if cancelled else ""))

    # --- Modal ---

    def invoke(self, context, event):
        armature = self._find_daz_armature(context)
        if not armature:
            self.report({'WARNING'}, "No DAZ armature found (needs 'hip' bone)")
            return {'CANCELLED'}

        self._armature_name = armature.name
        self._hovered_bone = None
        self._selected_bone = None
        self._active_drag = None
        self._chain_datas = []
        self._muted_constraints = []
        self._ik_constraints = []
        self._pre_drag_rotations = {}
        self._drag_bone_name = None

        # Prepare rig (convert to quaternions)
        prepare_rig_for_ik(armature)

        # Ensure POSE mode
        if context.view_layer.objects.active != armature:
            context.view_layer.objects.active = armature
        if armature.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')

        # No draw handler — production BlenDAZ already provides mesh highlights.

        # Start diagnostic log
        _tlog_start()

        # Tell production modal to pass through all events while we're active
        global fabrik_test_active
        fabrik_test_active = True

        context.window_manager.modal_handler_add(self)
        self._set_header(context, "FABRIK Pin Test | Hover + Click to select | P = pin | G = hip drag | R = rotate | ESC = exit")
        _tlog(f"[PIN TEST] Started (production modal suspended) armature='{armature.name}'")
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        try:
            return self._modal_inner(context, event)
        except ReferenceError:
            # Armature/object was removed (e.g., undo, file reload, addon reload).
            # Cancel cleanly — don't spam errors forever.
            _tlog("[PIN TEST] Armature reference lost — cancelling")
            global fabrik_test_active
            fabrik_test_active = False
            _tlog_end()
            return {'CANCELLED'}
        except Exception as e:
            import traceback
            _tlog(f"[PIN TEST] Modal error: {e}\n{traceback.format_exc()}")
            return {'PASS_THROUGH'}

    def _modal_inner(self, context, event):
        armature = self._get_armature()
        try:
            valid = armature and armature.name
        except ReferenceError:
            valid = False
        if not valid:
            _tlog(f"[PIN TEST] Armature invalid (name='{self._armature_name}') — cancelling")
            self._cleanup(context)
            return {'CANCELLED'}

        # --- Active drag: we own the loop ---
        # Native G doesn't write intermediate positions to pose_bone.location
        # during drag (only on confirm), so view_layer.update() can't see
        # the movement. We move the hip ourselves and run corrections.
        if self._active_drag and self._active_drag not in ('ending_confirm', 'ending_cancel'):

            if event.type in ('MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'):
                # Track mouse speed (pixels per event)
                mx, my = event.mouse_x, event.mouse_y
                if self._last_mouse:
                    dx = mx - self._last_mouse[0]
                    dy = my - self._last_mouse[1]
                    raw_speed = math.sqrt(dx*dx + dy*dy)
                    # Smooth the speed to avoid single-frame spikes
                    self._mouse_speed += (raw_speed - self._mouse_speed) * 0.3
                self._last_mouse = (mx, my)

                area, region, space, r3d = _resolve_event_viewport(context, event)
                if region and r3d:
                    drag_pb = armature.pose.bones.get(self._drag_bone_name)
                    if drag_pb:
                        if self._active_drag == 'translate':
                            self._apply_translate(context, event, armature,
                                                  drag_pb, region, r3d)
                        elif self._active_drag == 'rotate':
                            self._apply_rotate(context, event, armature,
                                               drag_pb, region, r3d)

                        # Flush depsgraph
                        context.view_layer.update()

                        # Correct arm chain — more iterations when moving fast
                        self._frame_count += 1
                        self._correct_pin_chains(context, armature)

                return {'RUNNING_MODAL'}

            # Confirm drag
            if event.value == 'PRESS' and event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'}:
                _tlog(f"[PIN TEST] Drag confirm ({event.type})")
                self._end_drag(context, cancelled=False)
                return {'RUNNING_MODAL'}

            # Cancel drag
            if event.value == 'PRESS' and event.type in {'RIGHTMOUSE', 'ESC'}:
                _tlog(f"[PIN TEST] Drag cancel ({event.type})")
                self._end_drag(context, cancelled=True)
                return {'RUNNING_MODAL'}

            # Consume other events during drag
            return {'RUNNING_MODAL'}

        # --- ESC: exit operator ---
        if event.type == 'ESC' and event.value == 'PRESS':
            self._cleanup(context)
            return {'CANCELLED'}

        # --- Mouse move: hover ---
        if event.type in ('MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'):
            bone_name, hit_loc = _raycast_bone(context, armature, event)
            if bone_name != self._hovered_bone:
                self._hovered_bone = bone_name
            return {'PASS_THROUGH'}

        # --- LMB: select bone ---
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if self._hovered_bone:
                self._selected_bone = self._hovered_bone
                # Set active pose bone
                pb = armature.pose.bones.get(self._selected_bone)
                if pb:
                    armature.data.bones.active = pb.bone
                _tlog(f"[PIN TEST] Selected: {self._selected_bone}")
                self._update_header(context)
                return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'}

        # --- P: pin/unpin ---
        if event.type == 'P' and event.value == 'PRESS':
            # Sync from Blender's active bone if test modal has no selection
            if not self._selected_bone and context.active_bone:
                self._selected_bone = context.active_bone.name
                _tlog(f"[PIN TEST] Synced selection from active bone: {self._selected_bone}")
            if self._selected_bone:
                bone = armature.data.bones.get(self._selected_bone)
                if bone and is_bone_pinned_translation(bone):
                    unpin_bone(armature, self._selected_bone)
                    _tlog(f"[PIN TEST] Unpinned: {self._selected_bone}")
                else:
                    pin_bone_translation(armature, self._selected_bone)
                    _tlog(f"[PIN TEST] Pinned: {self._selected_bone}")
                context.view_layer.update()
                self._update_header(context)
            return {'RUNNING_MODAL'}

        # --- G: hip drag ---
        if event.type == 'G' and event.value == 'PRESS':
            # Check test modal's selection first, then Blender's active bone
            sel = self._selected_bone
            if not sel and context.active_bone:
                sel = context.active_bone.name
                self._selected_bone = sel
            _tlog(f"[PIN TEST] G pressed, sel='{sel}'")
            if sel and sel.lower() in HIP_BONES:
                pb = armature.pose.bones.get(sel)
                if pb:
                    armature.data.bones.active = pb.bone
                if not self._start_drag(context, event, 'translate'):
                    # No pins — pass through to default Blender translate
                    bpy.ops.transform.translate('INVOKE_DEFAULT')
                return {'RUNNING_MODAL'}
            _tlog(f"[PIN TEST] G ignored — '{sel}' not in HIP_BONES")
            return {'PASS_THROUGH'}

        # --- R: torso rotate ---
        if event.type == 'R' and event.value == 'PRESS':
            sel = self._selected_bone
            if not sel and context.active_bone:
                sel = context.active_bone.name
                self._selected_bone = sel
            _tlog(f"[PIN TEST] R pressed, sel='{sel}'")
            if sel and sel in TORSO_BONES:
                pb = armature.pose.bones.get(sel)
                if pb:
                    armature.data.bones.active = pb.bone
                if not self._start_drag(context, event, 'rotate'):
                    # No pins — pass through to default Blender rotate
                    bpy.ops.transform.rotate('INVOKE_DEFAULT')
                return {'RUNNING_MODAL'}
            _tlog(f"[PIN TEST] R ignored — '{sel}' not in TORSO_BONES")
            return {'PASS_THROUGH'}

        return {'PASS_THROUGH'}

    def _update_header(self, context):
        """Update header with current state info."""
        parts = ["FABRIK Pin Test"]
        if self._selected_bone:
            bone = self._get_armature().data.bones.get(self._selected_bone)
            pinned = is_bone_pinned_translation(bone) if bone else False
            parts.append(f"Sel: {self._selected_bone}")
            if pinned:
                parts.append("[PINNED]")

        # Show all pinned bones
        pinned_list = self._get_pinned_endpoints(self._get_armature())
        if pinned_list:
            parts.append(f"Pins: {', '.join(pinned_list)}")

        parts.append("P=pin | G=hip | R=rotate | ESC=exit")
        self._set_header(context, " | ".join(parts))

    def _set_header(self, context, text):
        """Set header text on all VIEW_3D areas."""
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.header_text_set(text)

    def _cleanup(self, context):
        """Full cleanup on exit."""
        # End any active drag
        if self._active_drag:
            self._end_drag(context, cancelled=True)

        # Re-enable production modal
        global fabrik_test_active
        fabrik_test_active = False

        # Close diagnostic log
        _tlog_end()

        # Clear header
        self._set_header(context, None)

        # Redraw
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        _tlog("[PIN TEST] Exited (production modal resumed)")


# ============================================================================
# REGISTRATION
# ============================================================================

_keymaps = []


def register():
    bpy.utils.register_class(VIEW3D_OT_fabrik_pin_test)

    # Hotkey: Ctrl+Shift+F in 3D View
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(
            VIEW3D_OT_fabrik_pin_test.bl_idname,
            type='F', value='PRESS',
            ctrl=True, shift=True,
        )
        _keymaps.append((km, kmi))


def unregister():
    for km, kmi in _keymaps:
        km.keymap_items.remove(kmi)
    _keymaps.clear()

    bpy.utils.unregister_class(VIEW3D_OT_fabrik_pin_test)
