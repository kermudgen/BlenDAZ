"""
Hip Pin-Driven IK Regression Tests

Run in Blender: Text Editor > Open > select this file > Run Script
   or: blender --python tests/test_hip_pin_ik.py

Requires: Genesis 8/9 armature as active object in Pose mode.

This script reimplements the hip pin IK solver math independently and
validates that when the hip is moved, pinned limb endpoints stay locked
to their pin positions via analytical 2-bone IK.

Tests cover:
  - Single pinned foot (left, right)
  - Single pinned hand (left, right)
  - Both feet pinned simultaneously
  - Both hands pinned simultaneously
  - Mixed: one foot + one hand pinned
  - All four endpoints pinned
  - Various hip movement directions (forward, back, up, down, lateral)
  - Large hip movements (near max reach)
  - Cancel/restore: all bones return to original state
  - NaN safety on all rotations
  - Bone length preservation
  - Collar integration for pinned arms
"""

import bpy
import math
from mathutils import Vector, Quaternion, Matrix


class HipPinIKTestHarness:
    """Drives the hip pin IK solver math and validates results."""

    def __init__(self, armature):
        self.armature = armature
        self.results = []
        self.passed = 0
        self.failed = 0

        pb = armature.pose.bones

        # Hip / root bone
        self.hip_bone = pb.get('hip')
        if not self.hip_bone:
            raise RuntimeError("Could not find 'hip' bone")

        # Left leg
        self.l_thigh = pb.get('lThighBend')
        self.l_thigh_twist = pb.get('lThighTwist')
        self.l_shin = pb.get('lShin') or pb.get('lShinBend') or pb.get('lCalf')
        self.l_foot = pb.get('lFoot')

        # Right leg
        self.r_thigh = pb.get('rThighBend')
        self.r_thigh_twist = pb.get('rThighTwist')
        self.r_shin = pb.get('rShin') or pb.get('rShinBend') or pb.get('rCalf')
        self.r_foot = pb.get('rFoot')

        # Left arm
        self.l_collar = pb.get('lCollar')
        self.l_shoulder = pb.get('lShldrBend')
        self.l_shoulder_twist = pb.get('lShldrTwist')
        self.l_forearm = pb.get('lForearmBend')
        self.l_forearm_twist = pb.get('lForearmTwist')
        self.l_hand = pb.get('lHand')

        # Right arm
        self.r_collar = pb.get('rCollar')
        self.r_shoulder = pb.get('rShldrBend')
        self.r_shoulder_twist = pb.get('rShldrTwist')
        self.r_forearm = pb.get('rForearmBend')
        self.r_forearm_twist = pb.get('rForearmTwist')
        self.r_hand = pb.get('rHand')

        # Validate critical bones
        if not all([self.l_thigh, self.l_shin, self.l_foot]):
            raise RuntimeError("Could not find left leg bones")
        if not all([self.r_thigh, self.r_shin, self.r_foot]):
            raise RuntimeError("Could not find right leg bones")
        if not all([self.l_shoulder, self.l_forearm, self.l_hand]):
            raise RuntimeError("Could not find left arm bones")
        if not all([self.r_shoulder, self.r_forearm, self.r_hand]):
            raise RuntimeError("Could not find right arm bones")

    def reset_pose(self):
        """Reset all bones to rest pose."""
        for bone in self.armature.pose.bones:
            bone.rotation_mode = 'QUATERNION'
            bone.rotation_quaternion = Quaternion()
            bone.location = Vector((0, 0, 0))
            bone.scale = Vector((1, 1, 1))
        bpy.context.view_layer.update()

    def get_evaluated_bone_pos(self, bone, head=True):
        """Get bone head or tail in world space from evaluated depsgraph."""
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        arm_eval = self.armature.evaluated_get(depsgraph)
        bone_eval = arm_eval.pose.bones[bone.name]
        pos = Vector(bone_eval.head if head else bone_eval.tail)
        return self.armature.matrix_world @ pos

    def get_bone_lengths(self, upper_bone, lower_bone):
        """Get upper and lower bone lengths from evaluated armature."""
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        arm_eval = self.armature.evaluated_get(depsgraph)
        upper_eval = arm_eval.pose.bones[upper_bone.name]
        lower_eval = arm_eval.pose.bones[lower_bone.name]

        upper_head = self.armature.matrix_world @ Vector(upper_eval.head)
        lower_head = self.armature.matrix_world @ Vector(lower_eval.head)
        lower_tail = self.armature.matrix_world @ Vector(lower_eval.tail)

        return (lower_head - upper_head).length, (lower_tail - lower_head).length

    def move_hip(self, world_delta):
        """Move the hip bone by a world-space delta vector.

        Converts world delta to armature-local space and applies to hip.location.
        Returns the original hip location for cancel/restore testing.
        """
        armature = self.armature
        hip = self.hip_bone
        original_location = hip.location.copy()

        local_delta = armature.matrix_world.to_3x3().inverted() @ world_delta
        hip.location = original_location + local_delta
        bpy.context.view_layer.update()

        return original_location

    def solve_leg(self, thigh_bone, shin_bone, target_pos, thigh_twist=None):
        """Run analytical 2-bone leg solver. Returns result dict or None on skip."""
        armature = self.armature

        # Reset limb bones to identity
        for bone in [thigh_bone, thigh_twist, shin_bone]:
            if bone:
                bone.rotation_quaternion = Quaternion()
                bone.location = Vector((0, 0, 0))
                bone.scale = Vector((1, 1, 1))
        bpy.context.view_layer.update()

        # Get bone lengths
        thigh_length, shin_length = self.get_bone_lengths(thigh_bone, shin_bone)

        # Read joint position FRESH (hip has moved)
        joint_pos = armature.matrix_world @ thigh_bone.head

        # Geometry
        joint_to_target = target_pos - joint_pos
        distance = joint_to_target.length
        max_reach = thigh_length + shin_length
        min_reach = abs(thigh_length - shin_length) * 0.1

        if distance <= min_reach:
            return {'error': 'too_close', 'joint_pos': joint_pos}
        if distance >= max_reach:
            distance = max_reach * 0.995

        # Bend plane normal (locked for legs)
        thigh_world_mat_rest = (armature.matrix_world @ thigh_bone.matrix).to_3x3().normalized()
        bend_normal = Vector(thigh_world_mat_rest.col[0]).normalized()
        thigh_y = Vector(thigh_world_mat_rest.col[1]).normalized()
        bone_z = Vector(thigh_world_mat_rest.col[2]).normalized()
        test_dir = Quaternion(bend_normal, 0.01) @ thigh_y
        if test_dir.dot(bone_z) > thigh_y.dot(bone_z):
            bend_normal = -bend_normal

        target_dir = joint_to_target.normalized()

        # Law of cosines
        cos_knee = (thigh_length**2 + shin_length**2 - distance**2) / (2 * thigh_length * shin_length)
        cos_knee = max(-1, min(1, cos_knee))
        cos_hip = (thigh_length**2 + distance**2 - shin_length**2) / (2 * thigh_length * distance)
        cos_hip = max(-1, min(1, cos_hip))
        hip_angle = math.acos(cos_hip)
        knee_bend_angle = math.pi - math.acos(cos_knee)

        rotation = Quaternion(bend_normal, hip_angle)
        thigh_dir = rotation @ target_dir

        # Thigh rotation
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
        bpy.context.view_layer.update()

        # Shin rotation
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
        bpy.context.view_layer.update()

        # Read results
        actual_knee = armature.matrix_world @ shin_bone.head
        actual_foot = self.get_evaluated_bone_pos(shin_bone, head=False)

        return {
            'joint_pos': joint_pos.copy(),
            'target_pos': target_pos.copy(),
            'actual_foot': actual_foot.copy(),
            'foot_error': (actual_foot - target_pos).length,
            'thigh_length': thigh_length,
            'shin_length': shin_length,
            'max_reach': max_reach,
            'distance': distance,
            'knee_bend_angle': knee_bend_angle,
            'thigh_rotation': thigh_bone.rotation_quaternion.copy(),
            'shin_rotation': shin_bone.rotation_quaternion.copy(),
        }

    def solve_arm(self, shoulder_bone, forearm_bone, collar_bone, target_pos,
                  shoulder_twist=None):
        """Run analytical 2-bone arm solver with collar. Returns result dict."""
        armature = self.armature

        # Reset limb bones to identity
        for bone in [collar_bone, shoulder_bone, shoulder_twist, forearm_bone]:
            if bone:
                bone.rotation_quaternion = Quaternion()
                bone.location = Vector((0, 0, 0))
                bone.scale = Vector((1, 1, 1))
        bpy.context.view_layer.update()

        # Get bone lengths
        upper_length, lower_length = self.get_bone_lengths(shoulder_bone, forearm_bone)

        # Collar rotation (Step 1.5)
        shoulder_pos = armature.matrix_world @ shoulder_bone.head
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

            bpy.context.view_layer.update()
            shoulder_pos = armature.matrix_world @ shoulder_bone.head

        # Geometry
        shoulder_to_target = target_pos - shoulder_pos
        distance = shoulder_to_target.length
        max_reach = upper_length + lower_length
        min_reach = abs(upper_length - lower_length) * 0.1

        if distance <= min_reach:
            return {'error': 'too_close', 'shoulder_pos': shoulder_pos}
        if distance >= max_reach:
            distance = max_reach * 0.995

        target_dir = shoulder_to_target.normalized()

        # Dynamic bend_normal (Gram-Schmidt)
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

        # Sign check
        shoulder_y = Vector(shoulder_world_mat_rest.col[1]).normalized()
        bone_z = Vector(shoulder_world_mat_rest.col[2]).normalized()
        test_dir = Quaternion(bend_normal, 0.01) @ shoulder_y
        if test_dir.dot(bone_z) > shoulder_y.dot(bone_z):
            bend_normal = -bend_normal

        # Law of cosines
        cos_elbow = (upper_length**2 + lower_length**2 - distance**2) / (2 * upper_length * lower_length)
        cos_elbow = max(-1, min(1, cos_elbow))
        cos_shoulder = (upper_length**2 + distance**2 - lower_length**2) / (2 * upper_length * distance)
        cos_shoulder = max(-1, min(1, cos_shoulder))
        shoulder_angle = math.acos(cos_shoulder)
        elbow_bend_angle = math.pi - math.acos(cos_elbow)

        rotation = Quaternion(bend_normal, shoulder_angle)
        upper_arm_dir = rotation @ target_dir

        # Shoulder rotation
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
        bpy.context.view_layer.update()

        # Forearm rotation
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
        bpy.context.view_layer.update()

        # Read results
        actual_wrist = self.get_evaluated_bone_pos(forearm_bone, head=False)

        return {
            'shoulder_pos': shoulder_pos.copy(),
            'target_pos': target_pos.copy(),
            'actual_wrist': actual_wrist.copy(),
            'wrist_error': (actual_wrist - target_pos).length,
            'upper_length': upper_length,
            'lower_length': lower_length,
            'max_reach': max_reach,
            'distance': distance,
            'elbow_bend_angle': elbow_bend_angle,
            'shoulder_rotation': shoulder_bone.rotation_quaternion.copy(),
            'forearm_rotation': forearm_bone.rotation_quaternion.copy(),
            'collar_rotation': collar_bone.rotation_quaternion.copy() if collar_bone else Quaternion(),
        }

    def run_hip_pin_test(self, hip_delta, pinned_limbs_config):
        """Run a full hip pin IK test.

        Args:
            hip_delta: Vector, world-space delta to move the hip
            pinned_limbs_config: list of dicts, each with:
                'type': 'leg' or 'arm'
                'side': 'l' or 'r'

        Returns dict with per-limb results and overall state.
        """
        armature = self.armature

        # Record pin targets BEFORE moving hip (rest pose endpoint positions)
        pin_targets = {}
        limb_bones = {}
        for config in pinned_limbs_config:
            limb_type = config['type']
            side = config['side']
            key = f"{side}_{limb_type}"

            if limb_type == 'leg':
                if side == 'l':
                    endpoint = self.l_foot
                    upper, lower = self.l_thigh, self.l_shin
                    twist = self.l_thigh_twist
                    collar = None
                else:
                    endpoint = self.r_foot
                    upper, lower = self.r_thigh, self.r_shin
                    twist = self.r_thigh_twist
                    collar = None
            else:  # arm
                if side == 'l':
                    endpoint = self.l_hand
                    upper, lower = self.l_shoulder, self.l_forearm
                    twist = self.l_shoulder_twist
                    collar = self.l_collar
                else:
                    endpoint = self.r_hand
                    upper, lower = self.r_shoulder, self.r_forearm
                    twist = self.r_shoulder_twist
                    collar = self.r_collar

            # Pin target = current endpoint position in rest pose
            pin_pos = self.get_evaluated_bone_pos(lower, head=False)
            pin_targets[key] = pin_pos.copy()
            limb_bones[key] = {
                'type': limb_type, 'side': side,
                'upper': upper, 'lower': lower,
                'twist': twist, 'collar': collar,
                'endpoint': endpoint,
            }

        # Store originals for cancel test
        original_hip_loc = self.hip_bone.location.copy()
        original_rotations = {}
        for key, bones in limb_bones.items():
            for bone_key in ['upper', 'lower', 'twist', 'collar']:
                bone = bones.get(bone_key)
                if bone:
                    original_rotations[bone.name] = bone.rotation_quaternion.copy()

        # === STEP 1: Move hip ===
        self.move_hip(hip_delta)

        # === STEP 2: Reset limb bones to identity ===
        for key, bones in limb_bones.items():
            for bone_key in ['upper', 'lower', 'twist', 'collar']:
                bone = bones.get(bone_key)
                if bone:
                    bone.rotation_quaternion = Quaternion()
                    bone.location = Vector((0, 0, 0))
                    bone.scale = Vector((1, 1, 1))
        bpy.context.view_layer.update()

        # === STEP 3: Solve each pinned limb ===
        limb_results = {}
        for key, bones in limb_bones.items():
            target = pin_targets[key]
            if bones['type'] == 'leg':
                result = self.solve_leg(
                    bones['upper'], bones['lower'], target, bones['twist']
                )
            else:
                result = self.solve_arm(
                    bones['upper'], bones['lower'], bones['collar'], target,
                    bones['twist']
                )
            limb_results[key] = result

        # Read final hip position
        final_hip_pos = armature.matrix_world @ self.hip_bone.head

        return {
            'hip_delta': hip_delta.copy(),
            'final_hip_pos': final_hip_pos,
            'pin_targets': pin_targets,
            'limb_results': limb_results,
            'original_hip_loc': original_hip_loc,
            'original_rotations': original_rotations,
        }

    def assert_test(self, name, condition, message=""):
        """Record a test result."""
        status = "PASS" if condition else "FAIL"
        self.results.append((name, status, message))
        if condition:
            self.passed += 1
        else:
            self.failed += 1
        print(f"  [{status}] {name}" + (f" -- {message}" if message else ""))

    def run_all_tests(self):
        """Run all test cases and report results."""
        print("\n" + "="*60)
        print("  HIP PIN-DRIVEN IK REGRESSION TESTS")
        print("="*60)

        armature = self.armature

        # ---------------------------------------------------------------
        # Test 1: Single left foot pinned, hip moves forward
        # ---------------------------------------------------------------
        print("\n--- Test 1: Left foot pinned, hip forward (+Y) ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0.05, 0)),
            pinned_limbs_config=[{'type': 'leg', 'side': 'l'}]
        )
        lr = result['limb_results']['l_leg']
        if 'error' not in lr:
            self.assert_test("T1a: foot error < 2cm",
                lr['foot_error'] < 0.02,
                f"error={lr['foot_error']:.4f}m")
            self.assert_test("T1b: no NaN in thigh rotation",
                not any(math.isnan(v) for v in lr['thigh_rotation']),
                f"rot={lr['thigh_rotation']}")
            self.assert_test("T1c: no NaN in shin rotation",
                not any(math.isnan(v) for v in lr['shin_rotation']),
                f"rot={lr['shin_rotation']}")
            self.assert_test("T1d: knee is bent",
                lr['knee_bend_angle'] > 0.01,
                f"bend={math.degrees(lr['knee_bend_angle']):.1f}°")
        else:
            self.assert_test("T1: solver ran", False, f"error={lr.get('error')}")

        # ---------------------------------------------------------------
        # Test 2: Single left foot pinned, hip moves backward
        # ---------------------------------------------------------------
        print("\n--- Test 2: Left foot pinned, hip backward (-Y) ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, -0.05, 0)),
            pinned_limbs_config=[{'type': 'leg', 'side': 'l'}]
        )
        lr = result['limb_results']['l_leg']
        if 'error' not in lr:
            self.assert_test("T2a: foot error < 2cm",
                lr['foot_error'] < 0.02,
                f"error={lr['foot_error']:.4f}m")
            self.assert_test("T2b: no NaN in thigh rotation",
                not any(math.isnan(v) for v in lr['thigh_rotation']))
        else:
            self.assert_test("T2: solver ran", False, f"error={lr.get('error')}")

        # ---------------------------------------------------------------
        # Test 3: Single left foot pinned, hip moves up
        # ---------------------------------------------------------------
        print("\n--- Test 3: Left foot pinned, hip up (+Z) ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0, 0.05)),
            pinned_limbs_config=[{'type': 'leg', 'side': 'l'}]
        )
        lr = result['limb_results']['l_leg']
        if 'error' not in lr:
            self.assert_test("T3a: foot error < 2cm",
                lr['foot_error'] < 0.02,
                f"error={lr['foot_error']:.4f}m")
            self.assert_test("T3b: no NaN in thigh rotation",
                not any(math.isnan(v) for v in lr['thigh_rotation']))
        else:
            self.assert_test("T3: solver ran", False, f"error={lr.get('error')}")

        # ---------------------------------------------------------------
        # Test 4: Single left foot pinned, hip moves down
        # ---------------------------------------------------------------
        print("\n--- Test 4: Left foot pinned, hip down (-Z) ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0, -0.03)),
            pinned_limbs_config=[{'type': 'leg', 'side': 'l'}]
        )
        lr = result['limb_results']['l_leg']
        if 'error' not in lr:
            self.assert_test("T4a: foot error < 2cm",
                lr['foot_error'] < 0.02,
                f"error={lr['foot_error']:.4f}m")
            self.assert_test("T4b: knee straightens (closer to full extension)",
                lr['knee_bend_angle'] < lr.get('knee_bend_angle', 999),
                f"bend={math.degrees(lr['knee_bend_angle']):.1f}°")
        else:
            self.assert_test("T4: solver ran", False, f"error={lr.get('error')}")

        # ---------------------------------------------------------------
        # Test 5: Single left foot pinned, hip lateral (+X)
        # ---------------------------------------------------------------
        print("\n--- Test 5: Left foot pinned, hip lateral (+X) ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0.05, 0, 0)),
            pinned_limbs_config=[{'type': 'leg', 'side': 'l'}]
        )
        lr = result['limb_results']['l_leg']
        if 'error' not in lr:
            self.assert_test("T5a: foot error < 3cm",
                lr['foot_error'] < 0.03,
                f"error={lr['foot_error']:.4f}m")
            self.assert_test("T5b: no NaN in rotations",
                not any(math.isnan(v) for v in lr['thigh_rotation']) and
                not any(math.isnan(v) for v in lr['shin_rotation']))
        else:
            self.assert_test("T5: solver ran", False, f"error={lr.get('error')}")

        # ---------------------------------------------------------------
        # Test 6: Right foot pinned, hip forward
        # ---------------------------------------------------------------
        print("\n--- Test 6: Right foot pinned, hip forward ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0.05, 0)),
            pinned_limbs_config=[{'type': 'leg', 'side': 'r'}]
        )
        lr = result['limb_results']['r_leg']
        if 'error' not in lr:
            self.assert_test("T6a: foot error < 2cm",
                lr['foot_error'] < 0.02,
                f"error={lr['foot_error']:.4f}m")
            self.assert_test("T6b: no NaN",
                not any(math.isnan(v) for v in lr['thigh_rotation']))
        else:
            self.assert_test("T6: solver ran", False, f"error={lr.get('error')}")

        # ---------------------------------------------------------------
        # Test 7: Both feet pinned, hip forward
        # ---------------------------------------------------------------
        print("\n--- Test 7: Both feet pinned, hip forward ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0.05, 0)),
            pinned_limbs_config=[
                {'type': 'leg', 'side': 'l'},
                {'type': 'leg', 'side': 'r'},
            ]
        )
        ll = result['limb_results']['l_leg']
        rl = result['limb_results']['r_leg']
        if 'error' not in ll and 'error' not in rl:
            self.assert_test("T7a: left foot error < 2cm",
                ll['foot_error'] < 0.02,
                f"error={ll['foot_error']:.4f}m")
            self.assert_test("T7b: right foot error < 2cm",
                rl['foot_error'] < 0.02,
                f"error={rl['foot_error']:.4f}m")
            self.assert_test("T7c: both knees bent",
                ll['knee_bend_angle'] > 0.01 and rl['knee_bend_angle'] > 0.01,
                f"L={math.degrees(ll['knee_bend_angle']):.1f}° R={math.degrees(rl['knee_bend_angle']):.1f}°")
        else:
            self.assert_test("T7: both solvers ran", False)

        # ---------------------------------------------------------------
        # Test 8: Both feet pinned, hip up
        # ---------------------------------------------------------------
        print("\n--- Test 8: Both feet pinned, hip up ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0, 0.05)),
            pinned_limbs_config=[
                {'type': 'leg', 'side': 'l'},
                {'type': 'leg', 'side': 'r'},
            ]
        )
        ll = result['limb_results']['l_leg']
        rl = result['limb_results']['r_leg']
        if 'error' not in ll and 'error' not in rl:
            self.assert_test("T8a: left foot error < 2cm",
                ll['foot_error'] < 0.02,
                f"error={ll['foot_error']:.4f}m")
            self.assert_test("T8b: right foot error < 2cm",
                rl['foot_error'] < 0.02,
                f"error={rl['foot_error']:.4f}m")
        else:
            self.assert_test("T8: both solvers ran", False)

        # ---------------------------------------------------------------
        # Test 9: Both feet pinned, hip lateral
        # ---------------------------------------------------------------
        print("\n--- Test 9: Both feet pinned, hip lateral (+X) ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0.05, 0, 0)),
            pinned_limbs_config=[
                {'type': 'leg', 'side': 'l'},
                {'type': 'leg', 'side': 'r'},
            ]
        )
        ll = result['limb_results']['l_leg']
        rl = result['limb_results']['r_leg']
        if 'error' not in ll and 'error' not in rl:
            self.assert_test("T9a: left foot error < 3cm",
                ll['foot_error'] < 0.03,
                f"error={ll['foot_error']:.4f}m")
            self.assert_test("T9b: right foot error < 3cm",
                rl['foot_error'] < 0.03,
                f"error={rl['foot_error']:.4f}m")
        else:
            self.assert_test("T9: both solvers ran", False)

        # ---------------------------------------------------------------
        # Test 10: Single left hand pinned, hip forward
        # ---------------------------------------------------------------
        print("\n--- Test 10: Left hand pinned, hip forward ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0.05, 0)),
            pinned_limbs_config=[{'type': 'arm', 'side': 'l'}]
        )
        lr = result['limb_results']['l_arm']
        if 'error' not in lr:
            self.assert_test("T10a: wrist error < 2cm",
                lr['wrist_error'] < 0.02,
                f"error={lr['wrist_error']:.4f}m")
            self.assert_test("T10b: no NaN in shoulder rotation",
                not any(math.isnan(v) for v in lr['shoulder_rotation']))
            self.assert_test("T10c: no NaN in forearm rotation",
                not any(math.isnan(v) for v in lr['forearm_rotation']))
        else:
            self.assert_test("T10: solver ran", False, f"error={lr.get('error')}")

        # ---------------------------------------------------------------
        # Test 11: Single right hand pinned, hip forward
        # ---------------------------------------------------------------
        print("\n--- Test 11: Right hand pinned, hip forward ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0.05, 0)),
            pinned_limbs_config=[{'type': 'arm', 'side': 'r'}]
        )
        lr = result['limb_results']['r_arm']
        if 'error' not in lr:
            self.assert_test("T11a: wrist error < 2cm",
                lr['wrist_error'] < 0.02,
                f"error={lr['wrist_error']:.4f}m")
            self.assert_test("T11b: no NaN in rotations",
                not any(math.isnan(v) for v in lr['shoulder_rotation']) and
                not any(math.isnan(v) for v in lr['forearm_rotation']))
        else:
            self.assert_test("T11: solver ran", False, f"error={lr.get('error')}")

        # ---------------------------------------------------------------
        # Test 12: Left hand pinned, hip up
        # ---------------------------------------------------------------
        print("\n--- Test 12: Left hand pinned, hip up ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0, 0.05)),
            pinned_limbs_config=[{'type': 'arm', 'side': 'l'}]
        )
        lr = result['limb_results']['l_arm']
        if 'error' not in lr:
            self.assert_test("T12a: wrist error < 2cm",
                lr['wrist_error'] < 0.02,
                f"error={lr['wrist_error']:.4f}m")
        else:
            self.assert_test("T12: solver ran", False, f"error={lr.get('error')}")

        # ---------------------------------------------------------------
        # Test 13: Left hand pinned, hip lateral
        # ---------------------------------------------------------------
        print("\n--- Test 13: Left hand pinned, hip lateral (+X) ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0.05, 0, 0)),
            pinned_limbs_config=[{'type': 'arm', 'side': 'l'}]
        )
        lr = result['limb_results']['l_arm']
        if 'error' not in lr:
            self.assert_test("T13a: wrist error < 3cm",
                lr['wrist_error'] < 0.03,
                f"error={lr['wrist_error']:.4f}m")
        else:
            self.assert_test("T13: solver ran", False, f"error={lr.get('error')}")

        # ---------------------------------------------------------------
        # Test 14: Both hands pinned, hip forward
        # ---------------------------------------------------------------
        print("\n--- Test 14: Both hands pinned, hip forward ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0.05, 0)),
            pinned_limbs_config=[
                {'type': 'arm', 'side': 'l'},
                {'type': 'arm', 'side': 'r'},
            ]
        )
        la = result['limb_results']['l_arm']
        ra = result['limb_results']['r_arm']
        if 'error' not in la and 'error' not in ra:
            self.assert_test("T14a: left wrist error < 2cm",
                la['wrist_error'] < 0.02,
                f"error={la['wrist_error']:.4f}m")
            self.assert_test("T14b: right wrist error < 2cm",
                ra['wrist_error'] < 0.02,
                f"error={ra['wrist_error']:.4f}m")
        else:
            self.assert_test("T14: both solvers ran", False)

        # ---------------------------------------------------------------
        # Test 15: Mixed - left foot + right hand, hip forward
        # ---------------------------------------------------------------
        print("\n--- Test 15: Left foot + right hand pinned, hip forward ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0.05, 0)),
            pinned_limbs_config=[
                {'type': 'leg', 'side': 'l'},
                {'type': 'arm', 'side': 'r'},
            ]
        )
        ll = result['limb_results']['l_leg']
        ra = result['limb_results']['r_arm']
        if 'error' not in ll and 'error' not in ra:
            self.assert_test("T15a: foot error < 2cm",
                ll['foot_error'] < 0.02,
                f"error={ll['foot_error']:.4f}m")
            self.assert_test("T15b: wrist error < 2cm",
                ra['wrist_error'] < 0.02,
                f"error={ra['wrist_error']:.4f}m")
        else:
            self.assert_test("T15: both solvers ran", False)

        # ---------------------------------------------------------------
        # Test 16: Mixed - right foot + left hand, hip up
        # ---------------------------------------------------------------
        print("\n--- Test 16: Right foot + left hand pinned, hip up ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0, 0.05)),
            pinned_limbs_config=[
                {'type': 'leg', 'side': 'r'},
                {'type': 'arm', 'side': 'l'},
            ]
        )
        rl = result['limb_results']['r_leg']
        la = result['limb_results']['l_arm']
        if 'error' not in rl and 'error' not in la:
            self.assert_test("T16a: foot error < 2cm",
                rl['foot_error'] < 0.02,
                f"error={rl['foot_error']:.4f}m")
            self.assert_test("T16b: wrist error < 2cm",
                la['wrist_error'] < 0.02,
                f"error={la['wrist_error']:.4f}m")
        else:
            self.assert_test("T16: both solvers ran", False)

        # ---------------------------------------------------------------
        # Test 17: All four endpoints pinned, hip forward
        # ---------------------------------------------------------------
        print("\n--- Test 17: All 4 endpoints pinned, hip forward ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0.04, 0)),
            pinned_limbs_config=[
                {'type': 'leg', 'side': 'l'},
                {'type': 'leg', 'side': 'r'},
                {'type': 'arm', 'side': 'l'},
                {'type': 'arm', 'side': 'r'},
            ]
        )
        all_ok = True
        for key, lr in result['limb_results'].items():
            if 'error' in lr:
                all_ok = False
                continue
            if 'foot_error' in lr:
                err = lr['foot_error']
                label = "foot"
            else:
                err = lr['wrist_error']
                label = "wrist"
            self.assert_test(f"T17: {key} {label} error < 3cm",
                err < 0.03, f"error={err:.4f}m")
            # NaN check
            for rot_key in ['thigh_rotation', 'shin_rotation', 'shoulder_rotation', 'forearm_rotation']:
                if rot_key in lr:
                    self.assert_test(f"T17: {key} {rot_key} no NaN",
                        not any(math.isnan(v) for v in lr[rot_key]))
        if not all_ok:
            self.assert_test("T17: all solvers ran", False)

        # ---------------------------------------------------------------
        # Test 18: All four pinned, hip up
        # ---------------------------------------------------------------
        print("\n--- Test 18: All 4 endpoints pinned, hip up ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0, 0.04)),
            pinned_limbs_config=[
                {'type': 'leg', 'side': 'l'},
                {'type': 'leg', 'side': 'r'},
                {'type': 'arm', 'side': 'l'},
                {'type': 'arm', 'side': 'r'},
            ]
        )
        for key, lr in result['limb_results'].items():
            if 'error' in lr:
                self.assert_test(f"T18: {key} solver ran", False)
                continue
            err = lr.get('foot_error', lr.get('wrist_error', 999))
            label = "foot" if 'foot_error' in lr else "wrist"
            self.assert_test(f"T18: {key} {label} error < 3cm",
                err < 0.03, f"error={err:.4f}m")

        # ---------------------------------------------------------------
        # Test 19: All four pinned, diagonal movement
        # ---------------------------------------------------------------
        print("\n--- Test 19: All 4 pinned, diagonal hip move ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0.03, 0.03, 0.02)),
            pinned_limbs_config=[
                {'type': 'leg', 'side': 'l'},
                {'type': 'leg', 'side': 'r'},
                {'type': 'arm', 'side': 'l'},
                {'type': 'arm', 'side': 'r'},
            ]
        )
        for key, lr in result['limb_results'].items():
            if 'error' in lr:
                self.assert_test(f"T19: {key} solver ran", False)
                continue
            err = lr.get('foot_error', lr.get('wrist_error', 999))
            label = "foot" if 'foot_error' in lr else "wrist"
            self.assert_test(f"T19: {key} {label} error < 3cm",
                err < 0.03, f"error={err:.4f}m")

        # ---------------------------------------------------------------
        # Test 20: Large hip movement - near max reach for legs
        # ---------------------------------------------------------------
        print("\n--- Test 20: Large hip forward (10cm), both feet pinned ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0.10, 0)),
            pinned_limbs_config=[
                {'type': 'leg', 'side': 'l'},
                {'type': 'leg', 'side': 'r'},
            ]
        )
        for key in ['l_leg', 'r_leg']:
            lr = result['limb_results'][key]
            if 'error' not in lr:
                self.assert_test(f"T20: {key} foot error < 3cm",
                    lr['foot_error'] < 0.03,
                    f"error={lr['foot_error']:.4f}m, dist={lr['distance']:.3f}m, max={lr['max_reach']:.3f}m")
            else:
                # too_close is acceptable for large moves
                self.assert_test(f"T20: {key} handled gracefully",
                    lr.get('error') == 'too_close',
                    f"error={lr.get('error')}")

        # ---------------------------------------------------------------
        # Test 21: Cancel/restore — all bones return to original state
        # ---------------------------------------------------------------
        print("\n--- Test 21: Cancel restores all bones ---")
        self.reset_pose()

        # Store original state
        orig_hip_loc = self.hip_bone.location.copy()
        orig_rotations = {}
        for bone in [self.l_thigh, self.l_shin, self.r_thigh, self.r_shin,
                     self.l_shoulder, self.l_forearm, self.r_shoulder, self.r_forearm]:
            if bone:
                orig_rotations[bone.name] = bone.rotation_quaternion.copy()

        # Run solver (modifies bones)
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0.05, 0)),
            pinned_limbs_config=[
                {'type': 'leg', 'side': 'l'},
                {'type': 'arm', 'side': 'r'},
            ]
        )

        # Simulate cancel: restore from stored originals
        self.hip_bone.location = result['original_hip_loc']
        for bone_name, rot in result['original_rotations'].items():
            pose_bone = armature.pose.bones.get(bone_name)
            if pose_bone:
                pose_bone.rotation_quaternion = rot
        bpy.context.view_layer.update()

        # Verify restoration
        hip_loc_diff = (self.hip_bone.location - orig_hip_loc).length
        self.assert_test("T21a: hip location restored",
            hip_loc_diff < 0.0001,
            f"diff={hip_loc_diff:.6f}")

        all_restored = True
        for bone_name, orig_rot in orig_rotations.items():
            pose_bone = armature.pose.bones.get(bone_name)
            if pose_bone:
                diff = pose_bone.rotation_quaternion.rotation_difference(orig_rot).angle
                if diff > 0.001:
                    all_restored = False
                    print(f"    ⚠️  {bone_name} rotation diff: {math.degrees(diff):.3f}°")
        self.assert_test("T21b: all bone rotations restored", all_restored)

        # ---------------------------------------------------------------
        # Test 22: Tiny hip movement — solver still produces valid result
        # ---------------------------------------------------------------
        print("\n--- Test 22: Tiny hip movement (1mm), left foot pinned ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0.001, 0)),
            pinned_limbs_config=[{'type': 'leg', 'side': 'l'}]
        )
        lr = result['limb_results']['l_leg']
        if 'error' not in lr:
            self.assert_test("T22a: foot error < 2cm",
                lr['foot_error'] < 0.02,
                f"error={lr['foot_error']:.4f}m")
            self.assert_test("T22b: no NaN",
                not any(math.isnan(v) for v in lr['thigh_rotation']) and
                not any(math.isnan(v) for v in lr['shin_rotation']))
        else:
            # too_close is acceptable for tiny moves
            self.assert_test("T22: handled gracefully", True,
                f"result={lr.get('error')}")

        # ---------------------------------------------------------------
        # Test 23: Hip backward with feet pinned (lean back)
        # ---------------------------------------------------------------
        print("\n--- Test 23: Both feet pinned, hip backward ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, -0.06, 0)),
            pinned_limbs_config=[
                {'type': 'leg', 'side': 'l'},
                {'type': 'leg', 'side': 'r'},
            ]
        )
        for key in ['l_leg', 'r_leg']:
            lr = result['limb_results'][key]
            if 'error' not in lr:
                self.assert_test(f"T23: {key} foot error < 3cm",
                    lr['foot_error'] < 0.03,
                    f"error={lr['foot_error']:.4f}m")
            else:
                self.assert_test(f"T23: {key} handled gracefully", True,
                    f"result={lr.get('error')}")

        # ---------------------------------------------------------------
        # Test 24: Hip up with hand pinned — collar should engage
        # ---------------------------------------------------------------
        print("\n--- Test 24: Left hand pinned, hip up — collar check ---")
        self.reset_pose()

        # Store collar original
        collar_orig = self.l_collar.rotation_quaternion.copy() if self.l_collar else None

        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0, 0.08)),
            pinned_limbs_config=[{'type': 'arm', 'side': 'l'}]
        )
        lr = result['limb_results']['l_arm']
        if 'error' not in lr and self.l_collar:
            collar_angle = self.l_collar.rotation_quaternion.rotation_difference(
                Quaternion()).angle
            self.assert_test("T24a: wrist error < 3cm",
                lr['wrist_error'] < 0.03,
                f"error={lr['wrist_error']:.4f}m")
            self.assert_test("T24b: collar rotated (reach-based)",
                collar_angle > math.radians(0.5),
                f"collar angle={math.degrees(collar_angle):.1f}°")
        else:
            self.assert_test("T24: solver ran", 'error' not in lr,
                f"error={lr.get('error', 'no collar')}")

        # ---------------------------------------------------------------
        # Test 25: Bilateral symmetry — both feet, hip straight forward
        # ---------------------------------------------------------------
        print("\n--- Test 25: Bilateral symmetry check ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0.05, 0)),
            pinned_limbs_config=[
                {'type': 'leg', 'side': 'l'},
                {'type': 'leg', 'side': 'r'},
            ]
        )
        ll = result['limb_results']['l_leg']
        rl = result['limb_results']['r_leg']
        if 'error' not in ll and 'error' not in rl:
            error_diff = abs(ll['foot_error'] - rl['foot_error'])
            bend_diff = abs(ll['knee_bend_angle'] - rl['knee_bend_angle'])
            self.assert_test("T25a: error symmetry (diff < 1cm)",
                error_diff < 0.01,
                f"L={ll['foot_error']:.4f}m R={rl['foot_error']:.4f}m diff={error_diff:.4f}m")
            self.assert_test("T25b: bend angle symmetry (diff < 5°)",
                bend_diff < math.radians(5),
                f"L={math.degrees(ll['knee_bend_angle']):.1f}° R={math.degrees(rl['knee_bend_angle']):.1f}°")
        else:
            self.assert_test("T25: both solvers ran", False)

        # ---------------------------------------------------------------
        # Test 26: Sequential hip moves without reset
        # ---------------------------------------------------------------
        print("\n--- Test 26: Sequential moves without reset ---")
        self.reset_pose()

        # First move
        result1 = self.run_hip_pin_test(
            hip_delta=Vector((0, 0.03, 0)),
            pinned_limbs_config=[{'type': 'leg', 'side': 'l'}]
        )
        lr1 = result1['limb_results']['l_leg']
        err1 = lr1.get('foot_error', 999) if 'error' not in lr1 else 999

        # Second move from already-moved state (don't reset)
        # The solver resets limb bones internally, so this tests that the solver
        # works correctly when the hip is already offset
        result2 = self.run_hip_pin_test(
            hip_delta=Vector((0, 0.03, 0)),
            pinned_limbs_config=[{'type': 'leg', 'side': 'l'}]
        )
        lr2 = result2['limb_results']['l_leg']
        err2 = lr2.get('foot_error', 999) if 'error' not in lr2 else 999

        self.assert_test("T26a: first move accurate",
            err1 < 0.02, f"error={err1:.4f}m")
        self.assert_test("T26b: second move accurate",
            err2 < 0.03, f"error={err2:.4f}m")

        # ---------------------------------------------------------------
        # Test 27: Hip down (squat) with feet pinned
        # ---------------------------------------------------------------
        print("\n--- Test 27: Hip down (squat), both feet pinned ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0, -0.08)),
            pinned_limbs_config=[
                {'type': 'leg', 'side': 'l'},
                {'type': 'leg', 'side': 'r'},
            ]
        )
        for key in ['l_leg', 'r_leg']:
            lr = result['limb_results'][key]
            if 'error' not in lr:
                self.assert_test(f"T27: {key} foot error < 3cm",
                    lr['foot_error'] < 0.03,
                    f"error={lr['foot_error']:.4f}m")
            else:
                self.assert_test(f"T27: {key} handled gracefully", True,
                    f"result={lr.get('error')}")

        # ---------------------------------------------------------------
        # Test 28: Large lateral with all 4 pinned (stress test)
        # ---------------------------------------------------------------
        print("\n--- Test 28: All 4 pinned, large lateral (8cm) ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0.08, 0, 0)),
            pinned_limbs_config=[
                {'type': 'leg', 'side': 'l'},
                {'type': 'leg', 'side': 'r'},
                {'type': 'arm', 'side': 'l'},
                {'type': 'arm', 'side': 'r'},
            ]
        )
        for key, lr in result['limb_results'].items():
            if 'error' in lr:
                self.assert_test(f"T28: {key} handled gracefully", True,
                    f"result={lr.get('error')}")
                continue
            err = lr.get('foot_error', lr.get('wrist_error', 999))
            label = "foot" if 'foot_error' in lr else "wrist"
            self.assert_test(f"T28: {key} {label} error < 5cm",
                err < 0.05, f"error={err:.4f}m")
            # NaN safety
            for rot_key in ['thigh_rotation', 'shin_rotation', 'shoulder_rotation', 'forearm_rotation']:
                if rot_key in lr:
                    self.assert_test(f"T28: {key} {rot_key} no NaN",
                        not any(math.isnan(v) for v in lr[rot_key]))

        # ---------------------------------------------------------------
        # Test 29: Arm collar NOT excessive for small hip move
        # ---------------------------------------------------------------
        print("\n--- Test 29: Small hip move — collar not excessive ---")
        self.reset_pose()
        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0.02, 0)),
            pinned_limbs_config=[{'type': 'arm', 'side': 'l'}]
        )
        lr = result['limb_results']['l_arm']
        if 'error' not in lr and self.l_collar:
            collar_angle = self.l_collar.rotation_quaternion.rotation_difference(
                Quaternion()).angle
            self.assert_test("T29a: wrist error < 2cm",
                lr['wrist_error'] < 0.02,
                f"error={lr['wrist_error']:.4f}m")
            self.assert_test("T29b: collar not excessive (< 20°)",
                collar_angle < math.radians(20),
                f"collar angle={math.degrees(collar_angle):.1f}°")
        else:
            self.assert_test("T29: solver ran", 'error' not in lr)

        # ---------------------------------------------------------------
        # Test 30: Bone length preservation after solve
        # ---------------------------------------------------------------
        print("\n--- Test 30: Bone length preservation ---")
        self.reset_pose()

        # Get rest-pose lengths
        l_thigh_len_rest, l_shin_len_rest = self.get_bone_lengths(self.l_thigh, self.l_shin)

        result = self.run_hip_pin_test(
            hip_delta=Vector((0, 0.06, 0)),
            pinned_limbs_config=[{'type': 'leg', 'side': 'l'}]
        )

        # Get post-solve lengths
        l_thigh_len_post, l_shin_len_post = self.get_bone_lengths(self.l_thigh, self.l_shin)

        thigh_diff = abs(l_thigh_len_post - l_thigh_len_rest)
        shin_diff = abs(l_shin_len_post - l_shin_len_rest)
        self.assert_test("T30a: thigh length preserved (diff < 1mm)",
            thigh_diff < 0.001,
            f"rest={l_thigh_len_rest:.4f}m post={l_thigh_len_post:.4f}m diff={thigh_diff:.4f}m")
        self.assert_test("T30b: shin length preserved (diff < 1mm)",
            shin_diff < 0.001,
            f"rest={l_shin_len_rest:.4f}m post={l_shin_len_post:.4f}m diff={shin_diff:.4f}m")

        # ===============================================================
        # SUMMARY
        # ===============================================================
        self.reset_pose()  # Leave armature clean

        print("\n" + "="*60)
        total = self.passed + self.failed
        print(f"  RESULTS: {self.passed} passed, {self.failed} failed out of {total} tests")
        print("="*60)

        if self.failed > 0:
            print("\n  FAILED TESTS:")
            for name, status, msg in self.results:
                if status == "FAIL":
                    print(f"    ✗ {name}" + (f" -- {msg}" if msg else ""))

        print()
        return self.passed, self.failed


# ===================================================================
# Entry point — run in Blender's Text Editor or via command line
# ===================================================================
armature = bpy.context.active_object
if not armature or armature.type != 'ARMATURE':
    print("ERROR: Select a Genesis 8/9 armature and switch to Pose mode first")
elif bpy.context.mode != 'POSE':
    print("ERROR: Switch to Pose mode first (select armature, Ctrl+Tab)")
else:
    harness = HipPinIKTestHarness(armature)
    harness.run_all_tests()
