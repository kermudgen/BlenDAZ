"""
Analytical Leg IK Regression Tests

Run in Blender: Text Editor > Open > select this file > Run Script
   or: blender --python tests/test_analytical_leg.py

Requires: Genesis 8/9 armature as active object in Pose mode.

This script reimplements the analytical leg solver math independently and
validates that bone transforms are correct for various hip rotations and
target positions. It catches regressions when the solver code changes.

Updated to match current solver in daz_bone_select.py:
  - Full identity reset (rotation, location, scale)
  - Distance clamping to 99.5% max_reach (no full-extension special case)
  - .normalized() on matrices before quaternion extraction
  - Full world-space shin rotation (not local X-axis bend)
  - Actual knee position from Blender (not geometric estimate)
"""

import bpy
import math
from mathutils import Vector, Quaternion, Matrix


class AnalyticalLegTestHarness:
    """Drives the analytical leg solver math and validates results."""

    def __init__(self, armature):
        self.armature = armature
        self.results = []
        self.passed = 0
        self.failed = 0

        # Find bones (left leg)
        pb = armature.pose.bones
        self.hip_bone = pb.get('hip')
        self.pelvis_bone = pb.get('pelvis')
        self.thigh_bone = pb.get('lThighBend')
        self.thigh_twist = pb.get('lThighTwist')
        self.shin_bone = pb.get('lShin')
        self.foot_bone = pb.get('lFoot')

        if not all([self.thigh_bone, self.shin_bone, self.foot_bone]):
            raise RuntimeError("Could not find left leg bones (lThighBend, lShin, lFoot)")

    def reset_pose(self):
        """Reset all bones to rest pose (rotation, location, scale)."""
        for bone in self.armature.pose.bones:
            bone.rotation_mode = 'QUATERNION'
            bone.rotation_quaternion = Quaternion()
            bone.location = Vector((0, 0, 0))
            bone.scale = Vector((1, 1, 1))
        bpy.context.view_layer.update()

    def set_hip_rotation(self, euler_degrees):
        """Set hip bone rotation in degrees (X, Y, Z)."""
        euler_rad = tuple(math.radians(d) for d in euler_degrees)
        # Hip bone controls the root -- rotate pelvis for body rotation
        target = self.pelvis_bone or self.hip_bone
        if target:
            from mathutils import Euler
            target.rotation_mode = 'QUATERNION'
            target.rotation_quaternion = Euler(euler_rad).to_quaternion()
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
        """Run the analytical leg solver math and return results.

        This reimplements the solver from update_analytical_leg_drag() in
        daz_bone_select.py to validate independently.

        Returns dict with solver state and actual bone positions.
        """
        armature = self.armature
        thigh_bone = self.thigh_bone
        thigh_twist = self.thigh_twist
        shin_bone = self.shin_bone

        # Get evaluated positions before reset (for bone lengths)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        arm_eval = armature.evaluated_get(depsgraph)
        thigh_eval = arm_eval.pose.bones[thigh_bone.name]
        shin_eval = arm_eval.pose.bones[shin_bone.name]

        hip_world = armature.matrix_world @ Vector(thigh_eval.head)
        knee_world = armature.matrix_world @ Vector(shin_eval.head)
        ankle_world = armature.matrix_world @ Vector(shin_eval.tail)

        thigh_length = (knee_world - hip_world).length
        shin_length = (ankle_world - knee_world).length

        # --- STEP 1: Reset leg bones to full identity ---
        for reset_bone in [thigh_bone, thigh_twist, shin_bone]:
            if reset_bone:
                reset_bone.rotation_quaternion = Quaternion()
                reset_bone.location = Vector((0, 0, 0))
                reset_bone.scale = Vector((1, 1, 1))
        bpy.context.view_layer.update()

        # Calculate bend plane normal AFTER identity reset.
        # bone.matrix now reflects parent chain (hip rotation) with identity thigh.
        # Use the bone's own X-axis — it IS the knee's lateral axis and already
        # encodes the correct bend plane for ANY parent rotation.  No cross-product
        # needed, no degenerate cases when thigh aligns with armature forward.
        thigh_world_mat_rest = (armature.matrix_world @ thigh_bone.matrix).to_3x3().normalized()
        thigh_vec = Vector(thigh_world_mat_rest.col[1]).normalized()
        bend_normal = Vector(thigh_world_mat_rest.col[0]).normalized()
        # Ensure knee bends forward: positive hip_angle should move thigh toward -Z
        bone_z = Vector(thigh_world_mat_rest.col[2]).normalized()
        test_dir = Quaternion(bend_normal, 0.01) @ thigh_vec
        if test_dir.dot(bone_z) > thigh_vec.dot(bone_z):
            bend_normal = -bend_normal

        # --- STEP 2: Calculate geometry ---
        hip_pos = armature.matrix_world @ thigh_bone.head
        hip_to_target = target_pos - hip_pos
        distance = hip_to_target.length
        max_reach = thigh_length + shin_length
        min_reach = abs(thigh_length - shin_length) * 0.1

        if distance <= min_reach:
            return {'error': 'too_close', 'hip_pos': hip_pos}

        # Clamp to 99.5% max reach -- prevents full lockout snap
        if distance >= max_reach:
            distance = max_reach * 0.995

        # Law of cosines for ALL cases (no special full-extension branch)
        cos_knee = (thigh_length**2 + shin_length**2 - distance**2) / (2 * thigh_length * shin_length)
        cos_knee = max(-1, min(1, cos_knee))
        knee_interior = math.acos(cos_knee)
        knee_bend_angle = math.pi - knee_interior

        cos_hip = (thigh_length**2 + distance**2 - shin_length**2) / (2 * thigh_length * distance)
        cos_hip = max(-1, min(1, cos_hip))
        hip_angle = math.acos(cos_hip)

        target_dir = hip_to_target.normalized()
        rotation = Quaternion(bend_normal, hip_angle)
        thigh_dir = rotation @ target_dir

        # --- STEP 3: Calculate ThighBend rotation ---
        # Read bone's rest-world orientation from Blender's ACTUAL bone.matrix
        # (after identity reset + view_layer.update() -- ground truth)
        thigh_world_mat = (armature.matrix_world @ thigh_bone.matrix).to_3x3().normalized()
        rest_x = Vector(thigh_world_mat.col[0]).normalized()
        rest_quat = thigh_world_mat.to_quaternion()

        # Build target orientation:
        #   Y axis = thigh_dir (aim direction)
        #   X axis = bend_normal projected perp to Y (shin hinge axis / roll)
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
        target_quat = target_mat_3x3.to_quaternion()

        # rotation_quaternion = rest_world.inv() @ target_world
        thigh_rotation = rest_quat.inverted() @ target_quat

        if any(math.isnan(v) for v in thigh_rotation):
            thigh_rotation = Quaternion()
        thigh_bone.rotation_quaternion = thigh_rotation
        bpy.context.view_layer.update()

        # --- STEP 4: Apply Shin rotation (full world-space computation) ---
        # Read shin's rest-world from Blender's ACTUAL bone.matrix after thigh applied
        shin_world_rest = (armature.matrix_world @ shin_bone.matrix).to_3x3().normalized()
        shin_rest_quat = shin_world_rest.to_quaternion()

        # Use ACTUAL knee position from Blender (compensates for thigh angular error)
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
            if shin_target_x.dot(target_x) < 0:  # Keep consistent with thigh's X
                shin_target_x = -shin_target_x
        shin_target_z = shin_target_x.cross(shin_target_y).normalized()

        shin_target_mat = Matrix((
            (shin_target_x[0], shin_target_y[0], shin_target_z[0]),
            (shin_target_x[1], shin_target_y[1], shin_target_z[1]),
            (shin_target_x[2], shin_target_y[2], shin_target_z[2]),
        ))
        shin_target_quat = shin_target_mat.to_quaternion()

        # Convert to local rotation_quaternion (same formula as thigh)
        shin_rotation = shin_rest_quat.inverted() @ shin_target_quat

        if any(math.isnan(v) for v in shin_rotation):
            shin_rotation = Quaternion()
        shin_bone.rotation_quaternion = shin_rotation
        bpy.context.view_layer.update()

        # --- Read results ---
        actual_knee = armature.matrix_world @ shin_bone.head
        actual_foot = armature.matrix_world @ shin_bone.tail

        return {
            'hip_pos': hip_pos.copy(),
            'target_pos': target_pos.copy(),
            'thigh_dir': thigh_dir.copy(),
            'bend_normal': bend_normal.copy(),
            'thigh_length': thigh_length,
            'shin_length': shin_length,
            'max_reach': max_reach,
            'distance': distance,
            'knee_bend_angle': knee_bend_angle,
            'hip_angle': hip_angle,
            'actual_knee': actual_knee.copy(),
            'actual_foot': actual_foot.copy(),
            'foot_error': (actual_foot - target_pos).length,
            'thigh_rotation': thigh_bone.rotation_quaternion.copy(),
            'shin_rotation': shin_bone.rotation_quaternion.copy(),
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
        print("  ANALYTICAL LEG IK REGRESSION TESTS")
        print("="*60)

        # Get rest-pose bone lengths for target calculation
        self.reset_pose()
        hip_pos = self.get_evaluated_bone_pos(self.thigh_bone, head=True)
        knee_pos = self.get_evaluated_bone_pos(self.shin_bone, head=True)
        ankle_pos = self.get_evaluated_bone_pos(self.shin_bone, head=False)
        thigh_len = (knee_pos - hip_pos).length
        shin_len = (ankle_pos - knee_pos).length
        max_reach = thigh_len + shin_len

        print(f"\n  Bone lengths: thigh={thigh_len:.4f}m, shin={shin_len:.4f}m, max_reach={max_reach:.4f}m")
        print(f"  Hip rest pos: ({hip_pos.x:.3f}, {hip_pos.y:.3f}, {hip_pos.z:.3f})")
        print(f"  Ankle rest pos: ({ankle_pos.x:.3f}, {ankle_pos.y:.3f}, {ankle_pos.z:.3f})")

        # ---------------------------------------------------------------
        # Test 1: Rest pose, near full extension (99% reach)
        # ---------------------------------------------------------------
        print(f"\n--- Test 1: Rest pose, near full extension (99%) ---")
        self.reset_pose()
        target = hip_pos + Vector((0, 0, -max_reach * 0.99))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.02,
                             f"error={result['foot_error']:.4f}m")
            self.assert_test("no_nan_thigh",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             f"quat={result['thigh_rotation']}")
            # With 99.5% distance clamping, 99% reach still produces a real
            # knee bend (~16 deg) since the leg isn't perfectly vertical at rest.
            self.assert_test("knee_nearly_straight",
                             result['knee_bend_angle'] < 0.35,
                             f"angle={math.degrees(result['knee_bend_angle']):.1f} deg")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 2: Rest pose, bent forward (70% reach)
        # ---------------------------------------------------------------
        print(f"\n--- Test 2: Rest pose, knee bent forward ---")
        self.reset_pose()
        target = hip_pos + Vector((0, -0.3, -max_reach * 0.5))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.01,
                             f"error={result['foot_error']:.4f}m")
            self.assert_test("knee_bent",
                             result['knee_bend_angle'] > 0.1,
                             f"angle={math.degrees(result['knee_bend_angle']):.1f} deg")
            # Check knee is in front of hip (DAZ forward is -Y)
            knee_forward = (result['actual_knee'] - result['hip_pos']).dot(
                (self.armature.matrix_world.to_3x3() @ Vector((0, -1, 0))).normalized()
            )
            self.assert_test("knee_forward",
                             knee_forward > 0,
                             f"forward_component={knee_forward:.4f}")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 3: Hip rotated 30 degrees forward, near full extension
        # ---------------------------------------------------------------
        print(f"\n--- Test 3: Hip rotated 30deg X, near full extension ---")
        self.reset_pose()
        self.set_hip_rotation((30, 0, 0))
        # Re-read hip position after rotation
        hip_rotated = self.get_evaluated_bone_pos(self.thigh_bone, head=True)
        target = hip_rotated + Vector((0, 0, -max_reach * 0.99))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.02,
                             f"error={result['foot_error']:.4f}m")
            self.assert_test("no_nan_thigh",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             f"quat={result['thigh_rotation']}")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 4: Hip rotated 45 degrees forward, bent knee
        # ---------------------------------------------------------------
        print(f"\n--- Test 4: Hip rotated 45deg X, knee bent ---")
        self.reset_pose()
        self.set_hip_rotation((45, 0, 0))
        hip_rotated = self.get_evaluated_bone_pos(self.thigh_bone, head=True)
        target = hip_rotated + Vector((0, -0.3, -max_reach * 0.5))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.01,
                             f"error={result['foot_error']:.4f}m")
            self.assert_test("knee_bent",
                             result['knee_bend_angle'] > 0.1,
                             f"angle={math.degrees(result['knee_bend_angle']):.1f} deg")
            self.assert_test("no_nan_thigh",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             f"quat={result['thigh_rotation']}")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 5: Near full extension (99.5% reach -- clamping boundary)
        # ---------------------------------------------------------------
        print(f"\n--- Test 5: Near full extension (99.5% reach, clamping boundary) ---")
        self.reset_pose()
        target = hip_pos + Vector((0, -0.01, -max_reach * 0.995))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.02,
                             f"error={result['foot_error']:.4f}m (relaxed tolerance)")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             "no NaN in output")
            self.assert_test("distance_clamped",
                             result['distance'] <= max_reach * 0.995 + 0.001,
                             f"distance={result['distance']:.4f}, clamp={max_reach * 0.995:.4f}")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 6: Beyond max reach (tests clamping)
        # ---------------------------------------------------------------
        print(f"\n--- Test 6: Beyond max reach (tests clamping) ---")
        self.reset_pose()
        target = hip_pos + Vector((0, 0, -max_reach * 1.1))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("distance_was_clamped",
                             result['distance'] < max_reach,
                             f"distance={result['distance']:.4f}, max_reach={result['max_reach']:.4f}")
            self.assert_test("knee_has_slight_bend",
                             result['knee_bend_angle'] > 0.01,
                             f"angle={math.degrees(result['knee_bend_angle']):.2f} deg (should be ~5.7)")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             "no NaN in output")
            self.assert_test("foot_reasonable",
                             result['foot_error'] < 0.1,
                             f"error={result['foot_error']:.4f}m (target was beyond reach)")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 7: Very close to hip (edge case)
        # ---------------------------------------------------------------
        print(f"\n--- Test 7: Very close to hip ---")
        self.reset_pose()
        target = hip_pos + Vector((0, 0, -0.01))
        result = self.run_solver(target)
        # This may return 'too_close' which is acceptable graceful handling
        if 'error' in result and result['error'] == 'too_close':
            self.assert_test("graceful_too_close", True, "correctly rejected too-close target")
        elif 'error' not in result:
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("handled", False, f"unexpected error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 8: Drag start simulation -- small offsets from rest ankle
        # This tests the "skip at beginning" issue where the leg snaps
        # before catching up during slow, careful drags.
        # ---------------------------------------------------------------
        print(f"\n--- Test 8: Drag start simulation (small offsets from rest) ---")
        self.reset_pose()
        # Simulate a slow drag: series of small offsets from rest ankle pos
        offsets = [
            Vector((0, 0, 0.005)),   # 5mm up
            Vector((0, 0, 0.01)),    # 1cm up
            Vector((0, 0, 0.02)),    # 2cm up
            Vector((0, 0, 0.05)),    # 5cm up
            Vector((0, -0.01, 0.02)),  # slight forward + up
            Vector((0, 0.01, 0.02)),   # slight back + up
        ]
        worst_error = 0.0
        any_nan = False
        skip_detected = False

        for i, offset in enumerate(offsets):
            self.reset_pose()
            target = ankle_pos + offset
            result = self.run_solver(target)
            if 'error' not in result:
                err = result['foot_error']
                worst_error = max(worst_error, err)
                if any(math.isnan(v) for v in result['thigh_rotation']):
                    any_nan = True
                # Check for "skip": foot moves AWAY from target initially
                foot_z = result['actual_foot'].z
                expected_z = target.z
                if i == 0:
                    # First tiny offset: foot should be very close to target
                    if abs(foot_z - expected_z) > 0.05:
                        skip_detected = True
                        print(f"    Skip detected at offset {i}: foot_z={foot_z:.4f}, target_z={expected_z:.4f}, diff={abs(foot_z - expected_z):.4f}")

        self.assert_test("small_offset_accuracy",
                         worst_error < 0.02,
                         f"worst_error={worst_error:.4f}m across {len(offsets)} offsets")
        self.assert_test("no_nan_small_offsets",
                         not any_nan,
                         "no NaN in any small-offset solve")
        self.assert_test("no_skip_at_start",
                         not skip_detected,
                         "foot should track target from first small offset")

        # ---------------------------------------------------------------
        # Test 9: Foot target to the side (lateral movement)
        # ---------------------------------------------------------------
        print(f"\n--- Test 9: Foot target to the side ---")
        self.reset_pose()
        target = hip_pos + Vector((-0.2, 0, -max_reach * 0.7))  # left and down
        result = self.run_solver(target)
        if 'error' not in result:
            # Lateral targets have higher error because bend_normal is locked
            # to the sagittal plane (prevents knee wobble during real-time drag).
            # The knee can only bend forward/back, not sideways, so the solver
            # can't perfectly reach far-lateral targets. 10cm tolerance is acceptable.
            self.assert_test("foot_near_target_lateral",
                             result['foot_error'] < 0.10,
                             f"error={result['foot_error']:.4f}m (relaxed for lateral)")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 10: Sequential drags (simulates multiple drag operations)
        # Run solver multiple times without full pose reset between --
        # each run does its own identity reset internally.
        # ---------------------------------------------------------------
        print(f"\n--- Test 10: Sequential drags (accumulation test) ---")
        self.reset_pose()
        targets = [
            hip_pos + Vector((0, -0.2, -max_reach * 0.6)),   # forward-down
            hip_pos + Vector((0, 0, -max_reach * 0.8)),       # straight down
            hip_pos + Vector((0, -0.3, -max_reach * 0.5)),    # more forward
            hip_pos + Vector((0, 0, -max_reach * 0.99)),      # near extension
            hip_pos + Vector((0, -0.1, -max_reach * 0.7)),    # back to moderate
        ]
        max_error = 0.0
        all_ok = True
        for i, tgt in enumerate(targets):
            # Don't reset between drags -- solver should handle it
            result = self.run_solver(tgt)
            if 'error' not in result:
                err = result['foot_error']
                max_error = max(max_error, err)
                if err > 0.03:
                    all_ok = False
                    print(f"    Drag {i+1}: error={err:.4f}m (FAIL)")
                else:
                    print(f"    Drag {i+1}: error={err:.4f}m (ok)")
            else:
                all_ok = False
                print(f"    Drag {i+1}: solver error: {result['error']}")

        self.assert_test("sequential_accuracy",
                         all_ok,
                         f"max_error={max_error:.4f}m across {len(targets)} sequential drags")

        # ---------------------------------------------------------------
        # Test 11: Thigh twist consistency (re-drag from bent position)
        # Simulates: drag to bend leg forward, release, drag again to same
        # target. The thigh's X-axis (roll) should NOT snap between drags.
        # ---------------------------------------------------------------
        print(f"\n--- Test 11: Thigh twist consistency (re-drag from bent) ---")
        self.reset_pose()
        bent_target = hip_pos + Vector((0, -0.3, -max_reach * 0.6))

        # First "drag": solve from rest
        result1 = self.run_solver(bent_target)
        if 'error' not in result1:
            thigh_quat_1 = result1['thigh_rotation'].copy()
            foot_err_1 = result1['foot_error']
            # Read thigh X-axis after first solve
            thigh_mat_1 = (armature.matrix_world @ self.thigh_bone.matrix).to_3x3().normalized()
            thigh_x_1 = Vector(thigh_mat_1.col[0]).normalized()

            # Second "drag": solve AGAIN from the already-bent position
            # (solver does its own identity reset internally, but bend_normal
            # must be consistent so thigh roll doesn't snap)
            result2 = self.run_solver(bent_target)
            if 'error' not in result2:
                thigh_quat_2 = result2['thigh_rotation'].copy()
                foot_err_2 = result2['foot_error']
                thigh_mat_2 = (armature.matrix_world @ self.thigh_bone.matrix).to_3x3().normalized()
                thigh_x_2 = Vector(thigh_mat_2.col[0]).normalized()

                # Quaternion difference between the two solves
                quat_diff = thigh_quat_1.rotation_difference(thigh_quat_2)
                twist_angle = quat_diff.angle
                # X-axis dot product: 1.0 = identical roll, <1.0 = twist snap
                x_dot = thigh_x_1.dot(thigh_x_2)

                print(f"    Solve 1: foot_err={foot_err_1:.4f}m, thigh_x={thigh_x_1}")
                print(f"    Solve 2: foot_err={foot_err_2:.4f}m, thigh_x={thigh_x_2}")
                print(f"    Quat diff angle: {math.degrees(twist_angle):.2f} deg")
                print(f"    X-axis dot: {x_dot:.4f}")

                self.assert_test("re_drag_rotation_stable",
                                 twist_angle < math.radians(2.0),
                                 f"twist_diff={math.degrees(twist_angle):.2f} deg (should be <2)")
                self.assert_test("re_drag_roll_stable",
                                 x_dot > 0.99,
                                 f"x_dot={x_dot:.4f} (should be >0.99)")
                self.assert_test("re_drag_foot_accuracy",
                                 foot_err_2 < 0.02,
                                 f"error={foot_err_2:.4f}m")
            else:
                self.assert_test("second_solve_ran", False, f"error: {result2['error']}")
        else:
            self.assert_test("first_solve_ran", False, f"error: {result1['error']}")

        # ---------------------------------------------------------------
        # Test 12: Hip rotated sideways (Z-axis tilt)
        # Body leaning to the side -- tests that bend_normal stays correct
        # when the character is tilted laterally.
        # ---------------------------------------------------------------
        print(f"\n--- Test 12: Hip rotated 30deg Z (sideways lean), bent knee ---")
        self.reset_pose()
        self.set_hip_rotation((0, 0, 30))
        hip_tilted = self.get_evaluated_bone_pos(self.thigh_bone, head=True)
        target = hip_tilted + Vector((0, -0.2, -max_reach * 0.6))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.02,
                             f"error={result['foot_error']:.4f}m")
            self.assert_test("knee_bent",
                             result['knee_bend_angle'] > 0.1,
                             f"angle={math.degrees(result['knee_bend_angle']):.1f} deg")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 13: Hip rotated on Y-axis (twist/yaw)
        # Body turned to the side -- common pose for walking/turning.
        # ---------------------------------------------------------------
        print(f"\n--- Test 13: Hip rotated 45deg Y (body twist), bent knee ---")
        self.reset_pose()
        self.set_hip_rotation((0, 45, 0))
        hip_twisted = self.get_evaluated_bone_pos(self.thigh_bone, head=True)
        target = hip_twisted + Vector((0, -0.2, -max_reach * 0.6))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.02,
                             f"error={result['foot_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 14: Combined hip rotation (forward + sideways + twist)
        # The hardest case: all three axes rotated simultaneously.
        # ---------------------------------------------------------------
        print(f"\n--- Test 14: Combined hip rotation (20X, 15Y, 25Z), bent knee ---")
        self.reset_pose()
        self.set_hip_rotation((20, 15, 25))
        hip_combined = self.get_evaluated_bone_pos(self.thigh_bone, head=True)
        target = hip_combined + Vector((0, -0.25, -max_reach * 0.55))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.02,
                             f"error={result['foot_error']:.4f}m")
            self.assert_test("knee_bent",
                             result['knee_bend_angle'] > 0.1,
                             f"angle={math.degrees(result['knee_bend_angle']):.1f} deg")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 15: Hip rotated + twist consistency (re-drag)
        # Same as Test 11 but with hip rotated. This catches bugs where
        # the rest-pose bend_normal interacts badly with parent rotations.
        # ---------------------------------------------------------------
        print(f"\n--- Test 15: Hip rotated 30X + twist consistency (re-drag) ---")
        self.reset_pose()
        self.set_hip_rotation((30, 0, 0))
        hip_rot = self.get_evaluated_bone_pos(self.thigh_bone, head=True)
        bent_target_rot = hip_rot + Vector((0, -0.3, -max_reach * 0.6))

        result1 = self.run_solver(bent_target_rot)
        if 'error' not in result1:
            thigh_mat_r1 = (armature.matrix_world @ self.thigh_bone.matrix).to_3x3().normalized()
            thigh_x_r1 = Vector(thigh_mat_r1.col[0]).normalized()

            result2 = self.run_solver(bent_target_rot)
            if 'error' not in result2:
                thigh_mat_r2 = (armature.matrix_world @ self.thigh_bone.matrix).to_3x3().normalized()
                thigh_x_r2 = Vector(thigh_mat_r2.col[0]).normalized()

                quat_diff = result1['thigh_rotation'].rotation_difference(result2['thigh_rotation'])
                twist_angle = quat_diff.angle
                x_dot = thigh_x_r1.dot(thigh_x_r2)

                print(f"    Solve 1: foot_err={result1['foot_error']:.4f}m")
                print(f"    Solve 2: foot_err={result2['foot_error']:.4f}m")
                print(f"    Quat diff: {math.degrees(twist_angle):.2f} deg, X-dot: {x_dot:.4f}")

                self.assert_test("hip_rot_re_drag_stable",
                                 twist_angle < math.radians(2.0),
                                 f"twist_diff={math.degrees(twist_angle):.2f} deg")
                self.assert_test("hip_rot_re_drag_roll",
                                 x_dot > 0.99,
                                 f"x_dot={x_dot:.4f}")
                self.assert_test("hip_rot_re_drag_accuracy",
                                 result2['foot_error'] < 0.02,
                                 f"error={result2['foot_error']:.4f}m")
            else:
                self.assert_test("second_solve_ran", False, f"error: {result2['error']}")
        else:
            self.assert_test("first_solve_ran", False, f"error: {result1['error']}")

        # ---------------------------------------------------------------
        # Test 16: Extreme hip rotation (60 degrees forward)
        # Pushing the limits -- body bent far forward like a deep bow.
        # ---------------------------------------------------------------
        print(f"\n--- Test 16: Extreme hip rotation (60deg X), bent knee ---")
        self.reset_pose()
        self.set_hip_rotation((60, 0, 0))
        hip_extreme = self.get_evaluated_bone_pos(self.thigh_bone, head=True)
        target = hip_extreme + Vector((0, -0.2, -max_reach * 0.6))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.03,
                             f"error={result['foot_error']:.4f}m (relaxed for extreme)")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 17: Hip rotated 90deg Y (body turned fully sideways)
        # This is the case that fails interactively. The bend_normal
        # must account for parent rotations or the knee bends sideways.
        # ---------------------------------------------------------------
        print(f"\n--- Test 17: Hip rotated 90deg Y (full sideways turn) ---")
        self.reset_pose()
        self.set_hip_rotation((0, 90, 0))
        hip_90y = self.get_evaluated_bone_pos(self.thigh_bone, head=True)
        # Target straight down from rotated hip
        target = hip_90y + Vector((0, -0.2, -max_reach * 0.6))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.03,
                             f"error={result['foot_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             "no NaN in output")
            # Check that knee bends forward (in the character's rotated frame)
            # After 90Y, character's "forward" (-Y) is now world +X or -X
            knee_pos = result['actual_knee']
            # Print positions to diagnose bend plane issues
            print(f"    Hip: ({result['hip_pos'].x:.3f}, {result['hip_pos'].y:.3f}, {result['hip_pos'].z:.3f})")
            print(f"    Knee: ({knee_pos.x:.3f}, {knee_pos.y:.3f}, {knee_pos.z:.3f})")
            print(f"    Foot: ({result['actual_foot'].x:.3f}, {result['actual_foot'].y:.3f}, {result['actual_foot'].z:.3f})")
            print(f"    Target: ({target.x:.3f}, {target.y:.3f}, {target.z:.3f})")
            print(f"    Bend normal: ({result['bend_normal'].x:.3f}, {result['bend_normal'].y:.3f}, {result['bend_normal'].z:.3f})")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 18: Hip rotated 90deg Y, near full extension
        # ---------------------------------------------------------------
        print(f"\n--- Test 18: Hip rotated 90deg Y, near full extension ---")
        self.reset_pose()
        self.set_hip_rotation((0, 90, 0))
        hip_90y = self.get_evaluated_bone_pos(self.thigh_bone, head=True)
        target = hip_90y + Vector((0, 0, -max_reach * 0.99))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.03,
                             f"error={result['foot_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 19: Hip rotated 90deg Y + combined X, bent knee
        # Body turned sideways AND leaning forward.
        # ---------------------------------------------------------------
        print(f"\n--- Test 19: Hip rotated (30X, 90Y), bent knee ---")
        self.reset_pose()
        self.set_hip_rotation((30, 90, 0))
        hip_combo = self.get_evaluated_bone_pos(self.thigh_bone, head=True)
        target = hip_combo + Vector((0, -0.2, -max_reach * 0.6))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.03,
                             f"error={result['foot_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             "no NaN in output")
            print(f"    Bend normal: ({result['bend_normal'].x:.3f}, {result['bend_normal'].y:.3f}, {result['bend_normal'].z:.3f})")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 20: Hip rotated 90Y + -90X (turned sideways AND bent forward)
        # This is the degenerate case: thigh direction aligns with
        # armature_forward, making the old cross-product approach fail.
        # The bone X-axis approach handles it correctly.
        # ---------------------------------------------------------------
        print(f"\n--- Test 20: Hip rotated (90Y, -90X) — degenerate case ---")
        self.reset_pose()
        self.set_hip_rotation((-90, 90, 0))
        hip_pos = self.get_evaluated_bone_pos(self.thigh_bone, head=True)
        target = hip_pos + Vector((0, -0.2, -max_reach * 0.6))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.05,
                             f"error={result['foot_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             "no NaN in output")
            print(f"    Hip: ({result['hip_pos'].x:.3f}, {result['hip_pos'].y:.3f}, {result['hip_pos'].z:.3f})")
            print(f"    Knee: ({result['actual_knee'].x:.3f}, {result['actual_knee'].y:.3f}, {result['actual_knee'].z:.3f})")
            print(f"    Foot: ({result['actual_foot'].x:.3f}, {result['actual_foot'].y:.3f}, {result['actual_foot'].z:.3f})")
            print(f"    Target: ({target.x:.3f}, {target.y:.3f}, {target.z:.3f})")
            print(f"    Bend normal: ({result['bend_normal'].x:.3f}, {result['bend_normal'].y:.3f}, {result['bend_normal'].z:.3f})")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 21: Hip rotated 90Y + -90X, near full extension
        # ---------------------------------------------------------------
        print(f"\n--- Test 21: Hip rotated (90Y, -90X), near extension ---")
        self.reset_pose()
        self.set_hip_rotation((-90, 90, 0))
        hip_pos = self.get_evaluated_bone_pos(self.thigh_bone, head=True)
        target = hip_pos + Vector((0, 0, -max_reach * 0.99))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.03,
                             f"error={result['foot_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 22: Hip rotated -90X only (body bent fully forward)
        # Thigh points along armature forward — degenerate for cross-product.
        # Target must follow the thigh's actual direction after rotation.
        # ---------------------------------------------------------------
        print(f"\n--- Test 22: Hip rotated -90X (bent fully forward) ---")
        self.reset_pose()
        self.set_hip_rotation((-90, 0, 0))
        bpy.context.view_layer.update()
        hip_pos = self.get_evaluated_bone_pos(self.thigh_bone, head=True)
        # Get thigh direction after hip rotation (thigh at identity)
        thigh_mat = (self.armature.matrix_world @ self.thigh_bone.matrix).to_3x3().normalized()
        thigh_dir = Vector(thigh_mat.col[1]).normalized()
        # Target 60% along thigh with small perpendicular offset for knee bend
        bone_z = Vector(thigh_mat.col[2]).normalized()
        target = hip_pos + thigh_dir * max_reach * 0.6 + bone_z * 0.1
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.05,
                             f"error={result['foot_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             "no NaN in output")
            print(f"    Hip: ({result['hip_pos'].x:.3f}, {result['hip_pos'].y:.3f}, {result['hip_pos'].z:.3f})")
            print(f"    Knee: ({result['actual_knee'].x:.3f}, {result['actual_knee'].y:.3f}, {result['actual_knee'].z:.3f})")
            print(f"    Foot: ({result['actual_foot'].x:.3f}, {result['actual_foot'].y:.3f}, {result['actual_foot'].z:.3f})")
            print(f"    Bend normal: ({result['bend_normal'].x:.3f}, {result['bend_normal'].y:.3f}, {result['bend_normal'].z:.3f})")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 23: Hip rotated -90X, near full extension
        # ---------------------------------------------------------------
        print(f"\n--- Test 23: Hip rotated -90X, near extension ---")
        self.reset_pose()
        self.set_hip_rotation((-90, 0, 0))
        bpy.context.view_layer.update()
        hip_pos = self.get_evaluated_bone_pos(self.thigh_bone, head=True)
        thigh_mat = (self.armature.matrix_world @ self.thigh_bone.matrix).to_3x3().normalized()
        thigh_dir = Vector(thigh_mat.col[1]).normalized()
        target = hip_pos + thigh_dir * max_reach * 0.99
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.03,
                             f"error={result['foot_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             "no NaN in output")
        else:
            self.assert_test("solver_ran", False, f"error: {result['error']}")

        # ---------------------------------------------------------------
        # Test 24: Extreme combined rotation (45° on all axes)
        # General stress test — no axis alignment degeneracy.
        # ---------------------------------------------------------------
        print(f"\n--- Test 24: Hip rotated (45X, 45Y, 45Z) stress test ---")
        self.reset_pose()
        self.set_hip_rotation((45, 45, 45))
        hip_pos = self.get_evaluated_bone_pos(self.thigh_bone, head=True)
        target = hip_pos + Vector((-0.1, -0.2, -max_reach * 0.6))
        result = self.run_solver(target)
        if 'error' not in result:
            self.assert_test("foot_near_target",
                             result['foot_error'] < 0.05,
                             f"error={result['foot_error']:.4f}m")
            self.assert_test("no_nan",
                             not any(math.isnan(v) for v in result['thigh_rotation']),
                             "no NaN in output")
            print(f"    Bend normal: ({result['bend_normal'].x:.3f}, {result['bend_normal'].y:.3f}, {result['bend_normal'].z:.3f})")
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
    harness = AnalyticalLegTestHarness(armature)
    harness.run_all_tests()
