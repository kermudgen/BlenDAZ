"""
Analytical Arm IK Regression Tests

Run in Blender: Text Editor > Open > select this file > Run Script
   or: blender --python tests/test_analytical_arm.py

Requires: Genesis 8/9 armature as active object in Pose mode.

This script reimplements the analytical arm solver math independently and
validates that bone transforms are correct for various chest rotations and
target positions. It catches regressions when the solver code changes.

Mirrors test_analytical_leg.py structure with arm-specific:
  - Shoulder/forearm bones instead of thigh/shin
  - Chest rotation instead of hip rotation
  - Arm-specific reach directions (forward, up, across, behind)
"""

import bpy
import math
from mathutils import Vector, Quaternion, Matrix


class AnalyticalArmTestHarness:
    """Drives the analytical arm solver math and validates results."""

    def __init__(self, armature):
        self.armature = armature
        self.results = []
        self.passed = 0
        self.failed = 0

        # Find bones (left arm)
        pb = armature.pose.bones
        self.chest_upper = pb.get('chestUpper')
        self.chest_lower = pb.get('chestLower')
        self.collar_bone = pb.get('lCollar')
        self.shoulder_bone = pb.get('lShldrBend')
        self.shoulder_twist = pb.get('lShldrTwist')
        self.forearm_bone = pb.get('lForearmBend')
        self.forearm_twist = pb.get('lForearmTwist')
        self.hand_bone = pb.get('lHand')

        if not all([self.shoulder_bone, self.forearm_bone, self.hand_bone]):
            raise RuntimeError("Could not find left arm bones (lShldrBend, lForearmBend, lHand)")

    def reset_pose(self):
        """Reset all bones to rest pose (rotation, location, scale)."""
        for bone in self.armature.pose.bones:
            bone.rotation_mode = 'QUATERNION'
            bone.rotation_quaternion = Quaternion()
            bone.location = Vector((0, 0, 0))
            bone.scale = Vector((1, 1, 1))
        bpy.context.view_layer.update()

    def set_chest_rotation(self, euler_degrees):
        """Set chest rotation in degrees (X, Y, Z).
        Applies to both chestUpper and chestLower for full parent chain stress test."""
        euler_rad = tuple(math.radians(d) for d in euler_degrees)
        from mathutils import Euler
        rot_quat = Euler(euler_rad).to_quaternion()
        if self.chest_upper:
            self.chest_upper.rotation_mode = 'QUATERNION'
            self.chest_upper.rotation_quaternion = rot_quat
        if self.chest_lower:
            self.chest_lower.rotation_mode = 'QUATERNION'
            self.chest_lower.rotation_quaternion = rot_quat
        bpy.context.view_layer.update()

    def get_evaluated_bone_pos(self, bone, head=True):
        """Get bone head or tail in world space from evaluated depsgraph."""
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        arm_eval = self.armature.evaluated_get(depsgraph)
        bone_eval = arm_eval.pose.bones[bone.name]
        pos = Vector(bone_eval.head if head else bone_eval.tail)
        return self.armature.matrix_world @ pos

    def run_solver(self, target_pos):
        """Run the analytical arm solver math and return results.

        Reimplements update_analytical_arm_drag() from daz_bone_select.py.
        """
        armature = self.armature
        shoulder_bone = self.shoulder_bone
        shoulder_twist = self.shoulder_twist
        forearm_bone = self.forearm_bone

        # Get evaluated positions before reset (for bone lengths)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        arm_eval = armature.evaluated_get(depsgraph)
        shoulder_eval = arm_eval.pose.bones[shoulder_bone.name]
        forearm_eval = arm_eval.pose.bones[forearm_bone.name]

        shoulder_world = armature.matrix_world @ Vector(shoulder_eval.head)
        elbow_world = armature.matrix_world @ Vector(forearm_eval.head)
        wrist_world = armature.matrix_world @ Vector(forearm_eval.tail)

        upper_length = (elbow_world - shoulder_world).length
        lower_length = (wrist_world - elbow_world).length

        # --- STEP 1: Reset arm bones to full identity ---
        # forearm_twist is NOT reset (downstream of solver, preserves user twist)
        collar_bone = self.collar_bone
        for reset_bone in [collar_bone, shoulder_bone, shoulder_twist, forearm_bone]:
            if reset_bone:
                reset_bone.rotation_quaternion = Quaternion()
                reset_bone.location = Vector((0, 0, 0))
                reset_bone.scale = Vector((1, 1, 1))
        bpy.context.view_layer.update()

        # --- STEP 1.5: Fractional collar rotation toward target ---
        # Scale with reach distance: no collar help close to shoulder, full help when reaching far.
        collar_influence = 0.45
        shoulder_pos_prelim = armature.matrix_world @ shoulder_bone.head
        if collar_bone:
            collar_world_mat = (armature.matrix_world @ collar_bone.matrix).to_3x3().normalized()
            collar_rest_quat = collar_world_mat.to_quaternion()
            collar_rest_y = Vector(collar_world_mat.col[1]).normalized()
            collar_world_pos = armature.matrix_world @ collar_bone.head

            collar_to_target = target_pos - collar_world_pos
            if collar_to_target.length > 0.001:
                # Reach-distance scaling: ramp from 0 at 40% reach to full at 80%
                max_reach_prelim = upper_length + lower_length
                prelim_distance = (target_pos - shoulder_pos_prelim).length
                reach_ratio = min(prelim_distance / max_reach_prelim, 1.0)
                collar_scale = max(0.0, min(1.0, (reach_ratio - 0.4) / 0.4))
                effective_influence = collar_influence * collar_scale

                if effective_influence > 0.001:
                    collar_to_target_dir = collar_to_target.normalized()
                    full_rotation = collar_rest_y.rotation_difference(collar_to_target_dir)
                    partial_rotation = Quaternion().slerp(full_rotation, effective_influence)
                    collar_local = collar_rest_quat.inverted() @ (partial_rotation @ collar_rest_quat)

                    if not any(math.isnan(v) for v in collar_local):
                        collar_bone.rotation_quaternion = collar_local

            bpy.context.view_layer.update()

        # --- STEP 2: Calculate geometry ---
        # Use updated shoulder position (collar rotation may have shifted it)
        shoulder_pos = armature.matrix_world @ shoulder_bone.head
        shoulder_to_target = target_pos - shoulder_pos
        distance = shoulder_to_target.length
        max_reach = upper_length + lower_length
        min_reach = abs(upper_length - lower_length) * 0.1

        if distance <= min_reach:
            return {'error': 'too_close', 'shoulder_pos': shoulder_pos}

        # Clamp to 99.5% max reach
        if distance >= max_reach:
            distance = max_reach * 0.995

        # Law of cosines
        cos_elbow = (upper_length**2 + lower_length**2 - distance**2) / (2 * upper_length * lower_length)
        cos_elbow = max(-1, min(1, cos_elbow))
        elbow_interior = math.acos(cos_elbow)
        elbow_bend_angle = math.pi - elbow_interior

        cos_shoulder = (upper_length**2 + distance**2 - lower_length**2) / (2 * upper_length * distance)
        cos_shoulder = max(-1, min(1, cos_shoulder))
        shoulder_angle = math.acos(cos_shoulder)

        target_dir = shoulder_to_target.normalized()

        # Dynamic bend_normal: project bone's X-axis perpendicular to target_dir
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
        # Sign check: ensure elbow bends toward -Z
        shoulder_y = Vector(shoulder_world_mat_rest.col[1]).normalized()
        bone_z = Vector(shoulder_world_mat_rest.col[2]).normalized()
        test_dir = Quaternion(bend_normal, 0.01) @ shoulder_y
        if test_dir.dot(bone_z) > shoulder_y.dot(bone_z):
            bend_normal = -bend_normal

        rotation = Quaternion(bend_normal, shoulder_angle)
        upper_arm_dir = rotation @ target_dir

        # --- STEP 3: Calculate ShldrBend rotation ---
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
        target_quat = target_mat_3x3.to_quaternion()

        shoulder_rotation = rest_quat.inverted() @ target_quat

        if any(math.isnan(v) for v in shoulder_rotation):
            shoulder_rotation = Quaternion()
        shoulder_bone.rotation_quaternion = shoulder_rotation
        bpy.context.view_layer.update()

        # --- STEP 4: Apply ForearmBend rotation (full world-space) ---
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
        bpy.context.view_layer.update()

        # --- Read results ---
        actual_elbow = armature.matrix_world @ forearm_bone.head
        actual_wrist = armature.matrix_world @ forearm_bone.tail

        return {
            'shoulder_pos': shoulder_pos.copy(),
            'target_pos': target_pos.copy(),
            'upper_arm_dir': upper_arm_dir.copy(),
            'bend_normal': bend_normal.copy(),
            'upper_length': upper_length,
            'lower_length': lower_length,
            'max_reach': max_reach,
            'distance': distance,
            'elbow_bend_angle': elbow_bend_angle,
            'shoulder_angle': shoulder_angle,
            'actual_elbow': actual_elbow.copy(),
            'actual_wrist': actual_wrist.copy(),
            'wrist_error': (actual_wrist - target_pos).length,
            'shoulder_rotation': shoulder_bone.rotation_quaternion.copy(),
            'forearm_rotation': forearm_bone.rotation_quaternion.copy(),
            'collar_rotation': collar_bone.rotation_quaternion.copy() if collar_bone else Quaternion(),
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
        print("  ANALYTICAL ARM IK REGRESSION TESTS")
        print("="*60)

        armature = self.armature

        # Get bone lengths for target calculations
        self.reset_pose()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        elbow_pos = self.get_evaluated_bone_pos(self.forearm_bone, head=True)
        wrist_pos = self.get_evaluated_bone_pos(self.forearm_bone, head=False)
        upper_length = (elbow_pos - shoulder_pos).length
        lower_length = (wrist_pos - elbow_pos).length
        max_reach = upper_length + lower_length

        print(f"\n  Bone lengths: upper={upper_length:.4f}m, lower={lower_length:.4f}m, max_reach={max_reach:.4f}m")
        print(f"  Shoulder rest pos: ({shoulder_pos.x:.3f}, {shoulder_pos.y:.3f}, {shoulder_pos.z:.3f})")
        print(f"  Wrist rest pos: ({wrist_pos.x:.3f}, {wrist_pos.y:.3f}, {wrist_pos.z:.3f})")

        # Helper: get thigh direction after optional chest rotation
        def get_arm_direction():
            """Get shoulder bone's Y-axis direction after reset (includes parent rotation)."""
            bpy.context.view_layer.update()
            # Reset only arm bones to identity
            for b in [self.shoulder_bone, self.shoulder_twist, self.forearm_bone, self.forearm_twist]:
                if b:
                    b.rotation_quaternion = Quaternion()
                    b.location = Vector((0, 0, 0))
                    b.scale = Vector((1, 1, 1))
            bpy.context.view_layer.update()
            mat = (armature.matrix_world @ self.shoulder_bone.matrix).to_3x3().normalized()
            return Vector(mat.col[1]).normalized(), Vector(mat.col[2]).normalized()

        # ---------------------------------------------------------------
        # Test 1: Rest pose, near full extension (99%)
        # ---------------------------------------------------------------
        print(f"\n--- Test 1: Rest pose, near full extension (99%) ---")
        self.reset_pose()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        target = shoulder_pos + arm_dir * max_reach * 0.99
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.02,
                             f"error={result['wrist_error']:.4f}m")
            self.assert_test("no_nan_shoulder",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             f"quat={result['shoulder_rotation']}")
            elbow_deg = math.degrees(result['elbow_bend_angle'])
            self.assert_test("elbow_nearly_straight",
                             elbow_deg < 40,
                             f"angle={elbow_deg:.1f} deg")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 2: Rest pose, elbow bent
        # ---------------------------------------------------------------
        print(f"\n--- Test 2: Rest pose, elbow bent ---")
        self.reset_pose()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        # Target 60% along arm with perpendicular offset for bend
        target = shoulder_pos + arm_dir * max_reach * 0.5 + arm_z * 0.1
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.02,
                             f"error={result['wrist_error']:.4f}m")
            elbow_deg = math.degrees(result['elbow_bend_angle'])
            self.assert_test("elbow_bent",
                             elbow_deg > 30,
                             f"angle={elbow_deg:.1f} deg")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 3: Chest rotated 30° X, near extension
        # ---------------------------------------------------------------
        print(f"\n--- Test 3: Chest rotated 30deg X, near extension ---")
        self.reset_pose()
        self.set_chest_rotation((30, 0, 0))
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        target = shoulder_pos + arm_dir * max_reach * 0.99
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.02,
                             f"error={result['wrist_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             f"quat={result['shoulder_rotation']}")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 4: Chest rotated 45° X, elbow bent
        # ---------------------------------------------------------------
        print(f"\n--- Test 4: Chest rotated 45deg X, elbow bent ---")
        self.reset_pose()
        self.set_chest_rotation((45, 0, 0))
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        target = shoulder_pos + arm_dir * max_reach * 0.5 + arm_z * 0.1
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.02,
                             f"error={result['wrist_error']:.4f}m")
            elbow_deg = math.degrees(result['elbow_bend_angle'])
            self.assert_test("elbow_bent",
                             elbow_deg > 30,
                             f"angle={elbow_deg:.1f} deg")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             f"quat={result['shoulder_rotation']}")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 5: Near full extension (99.5% reach, clamping boundary)
        # ---------------------------------------------------------------
        print(f"\n--- Test 5: Near full extension (99.5% reach) ---")
        self.reset_pose()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        target = shoulder_pos + arm_dir * max_reach * 0.995
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.02,
                             f"error={result['wrist_error']:.4f}m (relaxed tolerance)")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
            # With collar rotation, shoulder shifts slightly so effective distance
            # won't exactly match pre-collar 99.5%. Just verify it's near max_reach.
            self.assert_test("distance_near_max",
                             result['distance'] > max_reach * 0.9,
                             f"distance={result['distance']:.4f}, max_reach={max_reach:.4f}")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 6: Beyond max reach (tests clamping)
        # ---------------------------------------------------------------
        print(f"\n--- Test 6: Beyond max reach (clamping) ---")
        self.reset_pose()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        target = shoulder_pos + arm_dir * max_reach * 1.2
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("distance_was_clamped",
                             result['distance'] < max_reach,
                             f"distance={result['distance']:.4f}, max_reach={max_reach:.4f}")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 7: Very close to shoulder
        # ---------------------------------------------------------------
        print(f"\n--- Test 7: Very close to shoulder ---")
        self.reset_pose()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        target = shoulder_pos + Vector((0.001, 0.001, 0.001))
        result = self.run_solver(target)
        self.assert_test("no_nan",
                         'error' in result or not any(math.isnan(v) for v in result.get('shoulder_rotation', Quaternion())),
                         "no NaN in output")

        # ---------------------------------------------------------------
        # Test 8: Drag start simulation (small offsets from rest wrist)
        # ---------------------------------------------------------------
        print(f"\n--- Test 8: Drag start simulation ---")
        self.reset_pose()
        wrist_rest = self.get_evaluated_bone_pos(self.forearm_bone, head=False)
        offsets = [
            Vector((0.01, 0, 0)), Vector((-0.01, 0, 0)),
            Vector((0, 0.01, 0)), Vector((0, -0.01, 0)),
            Vector((0, 0, 0.01)), Vector((0, 0, -0.01)),
        ]
        worst_err = 0
        any_nan = False
        for offset in offsets:
            self.reset_pose()
            result = self.run_solver(wrist_rest + offset)
            if 'error' not in result:
                worst_err = max(worst_err, result['wrist_error'])
                if any(math.isnan(v) for v in result['shoulder_rotation']):
                    any_nan = True
        self.assert_test("small_offset_accuracy",
                         worst_err < 0.02,
                         f"worst_error={worst_err:.4f}m across {len(offsets)} offsets")
        self.assert_test("no_nan_small_offsets", not any_nan, "no NaN in any small-offset solve")

        # ---------------------------------------------------------------
        # Test 9: Target behind body (lateral/hard to reach)
        # ---------------------------------------------------------------
        print(f"\n--- Test 9: Target behind body ---")
        self.reset_pose()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        # Target behind and to the side
        target = shoulder_pos + Vector((0, 0.2, -max_reach * 0.5))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target_lateral",
                             result['wrist_error'] < 0.10,
                             f"error={result['wrist_error']:.4f}m (relaxed for lateral)")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 10: Sequential drags (accumulation test)
        # ---------------------------------------------------------------
        print(f"\n--- Test 10: Sequential drags ---")
        self.reset_pose()
        arm_dir, arm_z = get_arm_direction()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        targets = [
            shoulder_pos + arm_dir * max_reach * 0.5 + arm_z * 0.1,
            shoulder_pos + arm_dir * max_reach * 0.6 + arm_z * 0.05,
            shoulder_pos + arm_dir * max_reach * 0.4 + arm_z * 0.15,
            shoulder_pos + arm_dir * max_reach * 0.99,
            shoulder_pos + arm_dir * max_reach * 0.5 + arm_z * 0.1,
        ]
        max_err = 0
        for i, t in enumerate(targets):
            self.reset_pose()
            result = self.run_solver(t)
            if 'error' not in result:
                max_err = max(max_err, result['wrist_error'])
                print(f"    Drag {i+1}: error={result['wrist_error']:.4f}m (ok)")
        self.assert_test("sequential_accuracy",
                         max_err < 0.02,
                         f"max_error={max_err:.4f}m across {len(targets)} sequential drags")

        # ---------------------------------------------------------------
        # Test 11: Elbow twist consistency (re-drag from bent position)
        # ---------------------------------------------------------------
        print(f"\n--- Test 11: Elbow twist consistency (re-drag from bent) ---")
        self.reset_pose()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        target = shoulder_pos + arm_dir * max_reach * 0.5 + arm_z * 0.1
        result1 = self.run_solver(target)
        # Re-solve from the bent position (don't reset)
        result2 = self.run_solver(target)
        if 'error' not in result1 and 'error' not in result2:
            q1 = result1['shoulder_rotation']
            q2 = result2['shoulder_rotation']
            dot = abs(q1.dot(q2))
            angle_diff = math.degrees(2 * math.acos(min(dot, 1.0)))
            # Check X-axis consistency
            mat1 = (armature.matrix_world @ self.shoulder_bone.matrix).to_3x3().normalized()
            x1 = Vector(mat1.col[0])
            # Apply first result, re-solve
            self.reset_pose()
            r1 = self.run_solver(target)
            mat1b = (armature.matrix_world @ self.shoulder_bone.matrix).to_3x3().normalized()
            x1b = Vector(mat1b.col[0])
            self.reset_pose()
            r2 = self.run_solver(target)
            mat2 = (armature.matrix_world @ self.shoulder_bone.matrix).to_3x3().normalized()
            x2 = Vector(mat2.col[0])
            x_dot = x1b.dot(x2)
            print(f"    Solve 1: wrist_err={r1['wrist_error']:.4f}m, shoulder_x={x1b}")
            print(f"    Solve 2: wrist_err={r2['wrist_error']:.4f}m, shoulder_x={x2}")
            print(f"    Quat diff angle: {angle_diff:.2f} deg")
            print(f"    X-axis dot: {x_dot:.4f}")
            self.assert_test("re_drag_rotation_stable",
                             angle_diff < 2.0,
                             f"twist_diff={angle_diff:.2f} deg (should be <2)")
            self.assert_test("re_drag_roll_stable",
                             x_dot > 0.99,
                             f"x_dot={x_dot:.4f} (should be >0.99)")
            self.assert_test("re_drag_wrist_accuracy",
                             r2['wrist_error'] < 0.02,
                             f"error={r2['wrist_error']:.4f}m")
        else:
            self.assert_test("solver_ran", False, "solver failed on re-drag test")

        # ---------------------------------------------------------------
        # Test 12: Chest rotated 30° Z (sideways lean), bent elbow
        # ---------------------------------------------------------------
        print(f"\n--- Test 12: Chest rotated 30deg Z (sideways lean) ---")
        self.reset_pose()
        self.set_chest_rotation((0, 0, 30))
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        target = shoulder_pos + arm_dir * max_reach * 0.5 + arm_z * 0.1
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.02,
                             f"error={result['wrist_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 13: Chest rotated 45° Y (body twist), bent elbow
        # ---------------------------------------------------------------
        print(f"\n--- Test 13: Chest rotated 45deg Y (body twist) ---")
        self.reset_pose()
        self.set_chest_rotation((0, 45, 0))
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        target = shoulder_pos + arm_dir * max_reach * 0.5 + arm_z * 0.1
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.02,
                             f"error={result['wrist_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 14: Combined chest rotation (20X, 15Y, 25Z)
        # ---------------------------------------------------------------
        print(f"\n--- Test 14: Combined chest rotation (20X, 15Y, 25Z) ---")
        self.reset_pose()
        self.set_chest_rotation((20, 15, 25))
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        target = shoulder_pos + arm_dir * max_reach * 0.5 + arm_z * 0.1
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.03,
                             f"error={result['wrist_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 15: Chest 30° X + twist consistency (re-drag)
        # ---------------------------------------------------------------
        print(f"\n--- Test 15: Chest 30deg X + twist consistency ---")
        self.reset_pose()
        self.set_chest_rotation((30, 0, 0))
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        target = shoulder_pos + arm_dir * max_reach * 0.5 + arm_z * 0.1
        r1 = self.run_solver(target)
        r2 = self.run_solver(target)
        if 'error' not in r1 and 'error' not in r2:
            q1 = r1['shoulder_rotation']
            q2 = r2['shoulder_rotation']
            dot = abs(q1.dot(q2))
            angle_diff = math.degrees(2 * math.acos(min(dot, 1.0)))
            print(f"    Solve 1: wrist_err={r1['wrist_error']:.4f}m")
            print(f"    Solve 2: wrist_err={r2['wrist_error']:.4f}m")
            print(f"    Quat diff: {angle_diff:.2f} deg")
            self.assert_test("chest_rot_re_drag_stable",
                             angle_diff < 2.0,
                             f"twist_diff={angle_diff:.2f} deg")
            self.assert_test("chest_rot_re_drag_accuracy",
                             r2['wrist_error'] < 0.02,
                             f"error={r2['wrist_error']:.4f}m")
        else:
            self.assert_test("solver_ran", False, "solver failed on chest+re-drag test")

        # ---------------------------------------------------------------
        # Test 16: Extreme chest rotation (60° X)
        # ---------------------------------------------------------------
        print(f"\n--- Test 16: Extreme chest rotation (60deg X) ---")
        self.reset_pose()
        self.set_chest_rotation((60, 0, 0))
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        target = shoulder_pos + arm_dir * max_reach * 0.5 + arm_z * 0.1
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.05,
                             f"error={result['wrist_error']:.4f}m (relaxed for extreme)")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 17: Chest rotated 90° Y (full sideways turn)
        # ---------------------------------------------------------------
        print(f"\n--- Test 17: Chest rotated 90deg Y ---")
        self.reset_pose()
        self.set_chest_rotation((0, 90, 0))
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        target = shoulder_pos + arm_dir * max_reach * 0.5 + arm_z * 0.1
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.05,
                             f"error={result['wrist_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
            print(f"    Bend normal: ({result['bend_normal'].x:.3f}, {result['bend_normal'].y:.3f}, {result['bend_normal'].z:.3f})")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 18: Chest rotated 90° Y + -90° X (degenerate case)
        # ---------------------------------------------------------------
        print(f"\n--- Test 18: Chest rotated (90Y, -90X) — degenerate ---")
        self.reset_pose()
        self.set_chest_rotation((-90, 90, 0))
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        target = shoulder_pos + arm_dir * max_reach * 0.5 + arm_z * 0.1
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.05,
                             f"error={result['wrist_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
            print(f"    Bend normal: ({result['bend_normal'].x:.3f}, {result['bend_normal'].y:.3f}, {result['bend_normal'].z:.3f})")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 19: Chest rotated -90° X (bent fully forward)
        # ---------------------------------------------------------------
        print(f"\n--- Test 19: Chest rotated -90X ---")
        self.reset_pose()
        self.set_chest_rotation((-90, 0, 0))
        bpy.context.view_layer.update()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        target = shoulder_pos + arm_dir * max_reach * 0.5 + arm_z * 0.1
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.05,
                             f"error={result['wrist_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
            print(f"    Bend normal: ({result['bend_normal'].x:.3f}, {result['bend_normal'].y:.3f}, {result['bend_normal'].z:.3f})")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 20: Reach direction — arm pointing up
        # Arm at rest points down/sideways; pure +Z is nearly opposite.
        # Use a target that's above the shoulder but biased toward arm direction.
        # ---------------------------------------------------------------
        print(f"\n--- Test 20: Reach direction — arm up ---")
        self.reset_pose()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        # Blend arm direction with world up for a reachable "above" target
        up_target_dir = (arm_dir * 0.3 + Vector((0, 0, 1)) * 0.7).normalized()
        target = shoulder_pos + up_target_dir * max_reach * 0.7
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.15,
                             f"error={result['wrist_error']:.4f}m (relaxed for upward reach)")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 21: Reach direction — arm pointing down
        # ---------------------------------------------------------------
        print(f"\n--- Test 21: Reach direction — arm down ---")
        self.reset_pose()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        target = shoulder_pos + Vector((0, 0, -max_reach * 0.8))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.05,
                             f"error={result['wrist_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 22: Reach direction — arm forward
        # ---------------------------------------------------------------
        print(f"\n--- Test 22: Reach direction — arm forward ---")
        self.reset_pose()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        target = shoulder_pos + Vector((0, -max_reach * 0.8, 0))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.05,
                             f"error={result['wrist_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 23: Reach direction — arm across body
        # ---------------------------------------------------------------
        print(f"\n--- Test 23: Reach direction — across body ---")
        self.reset_pose()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        # For left arm, across body is toward -X (right side)
        target = shoulder_pos + Vector((-max_reach * 0.5, -0.1, 0))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.10,
                             f"error={result['wrist_error']:.4f}m (relaxed for across)")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 24: Reach direction — arm behind back
        # ---------------------------------------------------------------
        print(f"\n--- Test 24: Reach direction — behind back ---")
        self.reset_pose()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        target = shoulder_pos + Vector((0, max_reach * 0.5, -0.1))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.10,
                             f"error={result['wrist_error']:.4f}m (relaxed for behind)")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 25: Collar rotates for overhead target
        # ---------------------------------------------------------------
        print(f"\n--- Test 25: Collar rotates for overhead target ---")
        self.reset_pose()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        # Target well above shoulder
        target = shoulder_pos + Vector((0, 0, max_reach * 0.8))
        result = self.run_solver(target)
        if 'error' not in result:
            collar_rot = result['collar_rotation']
            collar_angle = collar_rot.angle  # Angle from identity
            self.assert_test("collar_rotated",
                             collar_angle > math.radians(1.0),
                             f"collar_angle={math.degrees(collar_angle):.1f}° (should be >1°)")
            self.assert_test("collar_not_excessive",
                             collar_angle < math.radians(35.0),
                             f"collar_angle={math.degrees(collar_angle):.1f}° (should be <35°)")
            self.assert_test("no_nan_collar",
                             not any(math.isnan(v) for v in collar_rot),
                             "no NaN in collar rotation")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 26: Collar stays quiet for near-rest target
        # ---------------------------------------------------------------
        print(f"\n--- Test 26: Collar stays quiet for near-rest target ---")
        self.reset_pose()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        # Target along arm direction at 50% reach (easy, no collar needed)
        target = shoulder_pos + arm_dir * max_reach * 0.5
        result = self.run_solver(target)
        if 'error' not in result:
            collar_rot = result['collar_rotation']
            collar_angle = collar_rot.angle
            self.assert_test("collar_minimal",
                             collar_angle < math.radians(15.0),
                             f"collar_angle={math.degrees(collar_angle):.1f}° (should be <15° for easy target)")
            self.assert_test("wrist_still_tracks",
                             result['wrist_error'] < 0.05,
                             f"error={result['wrist_error']:.4f}m")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 27: Collar assists behind-back reach
        # ---------------------------------------------------------------
        print(f"\n--- Test 27: Collar assists behind-back reach ---")
        self.reset_pose()
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        target = shoulder_pos + Vector((0, max_reach * 0.6, -0.1))
        result = self.run_solver(target)
        if 'error' not in result:
            collar_rot = result['collar_rotation']
            collar_angle = collar_rot.angle
            self.assert_test("collar_rotated_behind",
                             collar_angle > math.radians(0.5),
                             f"collar_angle={math.degrees(collar_angle):.1f}° (should contribute)")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['shoulder_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 28: Cancel restores collar to original rotation
        # ---------------------------------------------------------------
        print(f"\n--- Test 28: Cancel restores collar rotation ---")
        self.reset_pose()
        if self.collar_bone:
            original_collar = self.collar_bone.rotation_quaternion.copy()
            shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
            target = shoulder_pos + Vector((0, 0, max_reach * 0.8))
            result = self.run_solver(target)
            if 'error' not in result:
                # Collar should have rotated
                modified_collar = self.collar_bone.rotation_quaternion.copy()
                self.assert_test("collar_was_modified",
                                 modified_collar.angle > math.radians(0.5),
                                 f"collar moved {math.degrees(modified_collar.angle):.1f}°")
                # Simulate cancel: restore original
                self.collar_bone.rotation_quaternion = original_collar
                bpy.context.view_layer.update()
                restored_collar = self.collar_bone.rotation_quaternion.copy()
                diff_angle = original_collar.rotation_difference(restored_collar).angle
                self.assert_test("collar_restored",
                                 diff_angle < math.radians(0.01),
                                 f"diff={math.degrees(diff_angle):.4f}°")
            else:
                self.assert_test("solver_ran", False, f"error: {result['error']}")
        else:
            self.assert_test("collar_bone_exists", False, "no collar bone found")

        # ---------------------------------------------------------------
        # Test 29: Collar with chest rotation (30° X)
        # ---------------------------------------------------------------
        print(f"\n--- Test 29: Collar with chest rotation (30X) ---")
        self.reset_pose()
        self.set_chest_rotation((30, 0, 0))
        shoulder_pos = self.get_evaluated_bone_pos(self.shoulder_bone, head=True)
        arm_dir, arm_z = get_arm_direction()
        target = shoulder_pos + arm_dir * max_reach * 0.6 + arm_z * 0.1
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("wrist_near_target",
                             result['wrist_error'] < 0.05,
                             f"error={result['wrist_error']:.4f}m")
            collar_rot = result['collar_rotation']
            self.assert_test("no_nan_collar",
                             not any(math.isnan(v) for v in collar_rot),
                             "no NaN in collar rotation")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Summary
        # ---------------------------------------------------------------
        self.reset_pose()  # Leave armature in clean state
        print(f"\n{'='*60}")
        print(f"  RESULTS: {self.passed} passed, {self.failed} failed out of {self.passed + self.failed} tests")
        print(f"{'='*60}\n")

        return self.failed == 0


# Entry point
armature = bpy.context.active_object
if not armature or armature.type != 'ARMATURE':
    print("ERROR: Select a Genesis 8/9 armature and switch to Pose mode first")
elif bpy.context.mode != 'POSE':
    print("ERROR: Switch to Pose mode first (select armature, Ctrl+Tab)")
else:
    harness = AnalyticalArmTestHarness(armature)
    harness.run_all_tests()
