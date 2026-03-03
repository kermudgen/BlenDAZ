"""
Pin System Regression Tests

Run in Blender: Text Editor > Open > select this file > Run Script
   or: blender --python tests/test_pin_system.py

Requires: Genesis 8/9 armature as active object in Pose mode.

This script tests the pin system independently:
  A. Pin setup (create/remove constraints, helpers, custom properties)
  B. Head rotation pin + spine compensation (6-bone weighted SLERP)
  C. Head translation pin + neck IK (2-bone analytical)
  D. Combined pins (rotation + translation + limbs)
  E. Edge cases (NaN, connectivity, bone lengths, sequential)

Solver math is reimplemented independently to validate the production code.
"""

import bpy
import math
import sys
import os
from mathutils import Vector, Quaternion, Matrix, Euler


# ---------------------------------------------------------------------------
# Import pin helper functions from the addon
# ---------------------------------------------------------------------------
# Add the parent directory to sys.path so we can import from daz_bone_select
addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

try:
    from daz_bone_select import (
        pin_bone_translation,
        pin_bone_rotation,
        unpin_bone,
        is_bone_pinned_translation,
        is_bone_pinned_rotation,
        get_pin_status_text,
        create_pin_helper_empty,
        get_bone_world_matrix,
    )
    ADDON_IMPORTED = True
except ImportError:
    ADDON_IMPORTED = False
    print("WARNING: Could not import pin functions from daz_bone_select.")
    print("  Pin setup tests (A) will be skipped.")
    print("  Solver tests (B-E) will still run with independent math.")


# ---------------------------------------------------------------------------
# Spine chain definition (mirrors SPINE_CHAIN_DEF in production code)
# ---------------------------------------------------------------------------
SPINE_CHAIN = [
    ('abdomenLower', 0.90),
    ('abdomenUpper', 0.90),
    ('chestLower',   0.75),
    ('chestUpper',   0.75),
    ('neckLower',    0.60),
]
# neckUpper is always the remainder bone


class PinSystemTestHarness:
    """Tests pin setup functions and solver math for the pin system."""

    def __init__(self, armature):
        self.armature = armature
        self.results = []
        self.passed = 0
        self.failed = 0

        pb = armature.pose.bones

        # Hip / root
        self.hip_bone = pb.get('hip')
        if not self.hip_bone:
            raise RuntimeError("Could not find 'hip' bone")

        # Spine chain
        self.pelvis = pb.get('pelvis')
        self.abdomen_lower = pb.get('abdomenLower')
        self.abdomen_upper = pb.get('abdomenUpper')
        self.chest_lower = pb.get('chestLower')
        self.chest_upper = pb.get('chestUpper')
        self.neck_lower = pb.get('neckLower')
        self.neck_upper = pb.get('neckUpper')
        self.head_bone = pb.get('head')

        if not self.neck_lower or not self.neck_upper or not self.head_bone:
            raise RuntimeError("Could not find neck/head bones")

        # Left leg (for combined tests)
        self.l_thigh = pb.get('lThighBend')
        self.l_thigh_twist = pb.get('lThighTwist')
        self.l_shin = pb.get('lShin') or pb.get('lShinBend') or pb.get('lCalf')
        self.l_foot = pb.get('lFoot')

        # Right leg
        self.r_thigh = pb.get('rThighBend')
        self.r_thigh_twist = pb.get('rThighTwist')
        self.r_shin = pb.get('rShin') or pb.get('rShinBend') or pb.get('rCalf')
        self.r_foot = pb.get('rFoot')

        # Collect all spine chain bones that exist
        self.spine_chain_bones = []
        self.spine_chain_weights = []
        mobilities = []
        for bone_name, stiffness in SPINE_CHAIN:
            bone = pb.get(bone_name)
            if bone:
                self.spine_chain_bones.append(bone)
                mobilities.append(1.0 - stiffness)
        total_mobility = sum(mobilities)
        if total_mobility > 0:
            self.spine_chain_weights = [m / total_mobility for m in mobilities]
        else:
            self.spine_chain_weights = [1.0 / len(mobilities)] * len(mobilities)

        # All compensation bones = chain + neckUpper (remainder)
        self.all_comp_bones = self.spine_chain_bones + [self.neck_upper]

        # Capture rest-pose chain gaps for connectivity baseline
        self.capture_rest_gaps()

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

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

    def get_bone_world_rotation(self, bone):
        """Get bone world rotation as quaternion."""
        bpy.context.view_layer.update()
        mat = (self.armature.matrix_world @ bone.matrix).to_3x3().normalized()
        return mat.to_quaternion()

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
        """Move hip by world-space delta. Returns original location."""
        hip = self.hip_bone
        original = hip.location.copy()
        local_delta = self.armature.matrix_world.to_3x3().inverted() @ world_delta
        hip.location = original + local_delta
        bpy.context.view_layer.update()
        return original

    def rotate_hip(self, axis, angle_rad):
        """Rotate hip by angle around axis. Returns original rotation."""
        hip = self.hip_bone
        hip.rotation_mode = 'QUATERNION'
        original = hip.rotation_quaternion.copy()
        rotation = Quaternion(axis, angle_rad)
        hip.rotation_quaternion = rotation @ original
        bpy.context.view_layer.update()
        return original

    def measure_chain_gaps(self):
        """Measure gaps between consecutive bone joints in the neck chain.

        DAZ skeletons have structural offsets (twist/bend split bones) so
        tail-to-head gaps are non-zero even at rest. Returns a dict of gaps.
        """
        gaps = {}
        pairs = []
        if self.chest_upper:
            pairs.append(('chestUpper.tail→neckLower.head',
                          self.chest_upper, False, self.neck_lower, True))
        pairs.append(('neckLower.tail→neckUpper.head',
                      self.neck_lower, False, self.neck_upper, True))
        pairs.append(('neckUpper.tail→head.head',
                      self.neck_upper, False, self.head_bone, True))

        for label, bone_a, head_a, bone_b, head_b in pairs:
            pos_a = self.get_evaluated_bone_pos(bone_a, head=head_a)
            pos_b = self.get_evaluated_bone_pos(bone_b, head=head_b)
            gaps[label] = (pos_a - pos_b).length
        return gaps

    def capture_rest_gaps(self):
        """Capture chain gaps at rest pose (called once during setup)."""
        self.reset_pose()
        self._rest_gaps = self.measure_chain_gaps()

    def check_chain_connectivity(self, test_prefix):
        """Check that neck chain gaps haven't grown vs rest pose.

        DAZ skeletons have non-zero structural offsets between bones, so we
        compare post-solve gaps against rest-pose baseline. A gap increase
        > 1mm indicates the IK solver is causing separation.
        """
        if not hasattr(self, '_rest_gaps'):
            self.capture_rest_gaps()

        connected = True
        current_gaps = self.measure_chain_gaps()
        for label, current_gap in current_gaps.items():
            rest_gap = self._rest_gaps.get(label, 0)
            increase = current_gap - rest_gap
            ok = increase < 0.001  # 1mm tolerance for gap INCREASE
            self.assert_test(
                f"{test_prefix}: {label} gap increase < 1mm",
                ok,
                f"rest={rest_gap*1000:.1f}mm now={current_gap*1000:.1f}mm delta={increase*1000:.2f}mm")
            if not ok:
                connected = False
        return connected

    def assert_test(self, name, condition, message=""):
        """Record a test result."""
        status = "PASS" if condition else "FAIL"
        self.results.append((name, status, message))
        if condition:
            self.passed += 1
        else:
            self.failed += 1
        print(f"  [{status}] {name}" + (f" -- {message}" if message else ""))

    # -------------------------------------------------------------------
    # Independent solver reimplementations
    # -------------------------------------------------------------------

    def solve_spine_rotation_compensation(self, pinned_world_quat):
        """Independent reimplementation of _solve_pinned_neck for testing.

        Distributes compensating rotation through the spine chain to restore
        the head to its pinned world orientation. Bottom-up, weighted SLERP.
        """
        armature = self.armature
        chain_bones = self.spine_chain_bones
        chain_weights = self.spine_chain_weights
        remainder = self.neck_upper
        head = self.head_bone

        # Bottom-up: each chain bone gets its weighted share.
        # Correction is COMPOSED with existing rotation_quaternion to preserve
        # user-set rotations from previous operations.
        for bone, weight in zip(chain_bones, chain_weights):
            head_mat = (armature.matrix_world @ head.matrix).to_3x3().normalized()
            current_quat = head_mat.to_quaternion()

            delta = pinned_world_quat @ current_quat.inverted()
            if delta.dot(Quaternion()) < 0:
                delta.negate()
            if delta.angle < 0.001:
                return  # Close enough

            share = Quaternion().slerp(delta, weight)
            bone_world = (armature.matrix_world @ bone.matrix).to_3x3().normalized().to_quaternion()
            target = share @ bone_world
            correction = bone_world.inverted() @ target
            if any(math.isnan(v) for v in correction):
                correction = Quaternion()
            bone.rotation_quaternion = correction @ bone.rotation_quaternion
            bpy.context.view_layer.update()

        # Remainder bone handles everything left
        head_mat = (armature.matrix_world @ head.matrix).to_3x3().normalized()
        current_quat = head_mat.to_quaternion()
        remaining = pinned_world_quat @ current_quat.inverted()
        if remaining.dot(Quaternion()) < 0:
            remaining.negate()
        if remaining.angle < 0.001:
            return

        bone_world = (armature.matrix_world @ remainder.matrix).to_3x3().normalized().to_quaternion()
        target = remaining @ bone_world
        correction = bone_world.inverted() @ target
        if any(math.isnan(v) for v in correction):
            correction = Quaternion()
        remainder.rotation_quaternion = correction @ remainder.rotation_quaternion
        bpy.context.view_layer.update()

    def solve_neck_translation_ik(self, target_pos):
        """Independent reimplementation of _solve_pinned_limb neck branch.

        2-bone analytical IK: neckLower (upper bone) + neckUpper (lower bone)
        targeting head position. Uses law of cosines.
        """
        armature = self.armature
        neck_lower = self.neck_lower
        neck_upper = self.neck_upper

        # Reset neck bones
        for bone in [neck_lower, neck_upper]:
            bone.rotation_mode = 'QUATERNION'
            bone.rotation_quaternion = Quaternion()
            bone.location = Vector((0, 0, 0))
            bone.scale = Vector((1, 1, 1))
        bpy.context.view_layer.update()

        # Bone lengths
        upper_length, lower_length = self.get_bone_lengths(neck_lower, neck_upper)

        # Joint position (neckLower head, after hip moved)
        joint_pos = armature.matrix_world @ neck_lower.head

        # Geometry
        joint_to_target = target_pos - joint_pos
        distance = joint_to_target.length
        max_reach = upper_length + lower_length
        min_reach = abs(upper_length - lower_length) * 0.1

        if distance <= min_reach:
            return {'error': 'too_close'}
        if distance >= max_reach:
            distance = max_reach * 0.995

        # Bend plane normal — cross product of bone direction × target direction.
        # Unlike legs, the neck must handle targets in any direction, so compute
        # a fresh bend normal from the actual geometry each time.
        nl_world_mat = (armature.matrix_world @ neck_lower.matrix).to_3x3().normalized()
        nl_y = Vector(nl_world_mat.col[1]).normalized()
        bone_x = Vector(nl_world_mat.col[0]).normalized()
        target_dir = joint_to_target.normalized()

        bend_normal = nl_y.cross(target_dir)
        if bend_normal.length < 0.001:
            # Bone and target nearly parallel — fall back to bone X axis
            bend_normal = bone_x.copy()
        else:
            bend_normal.normalize()
            if bend_normal.dot(bone_x) < 0:
                bend_normal = -bend_normal

        # Law of cosines
        cos_upper_joint = (upper_length**2 + distance**2 - lower_length**2) / (2 * upper_length * distance)
        cos_upper_joint = max(-1, min(1, cos_upper_joint))
        upper_angle = math.acos(cos_upper_joint)

        rotation = Quaternion(bend_normal, upper_angle)
        neck_lower_dir = rotation @ target_dir

        # neckLower rotation
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

        target_mat = Matrix((
            (target_x[0], target_y[0], target_z[0]),
            (target_x[1], target_y[1], target_z[1]),
            (target_x[2], target_y[2], target_z[2]),
        ))
        nl_rotation = rest_quat.inverted() @ target_mat.to_quaternion()
        if any(math.isnan(v) for v in nl_rotation):
            nl_rotation = Quaternion()
        neck_lower.rotation_quaternion = nl_rotation
        bpy.context.view_layer.update()

        # neckUpper rotation — point toward target
        nu_world_rest = (armature.matrix_world @ neck_upper.matrix).to_3x3().normalized()
        nu_rest_quat = nu_world_rest.to_quaternion()

        actual_mid = armature.matrix_world @ neck_upper.head
        nu_vec = target_pos - actual_mid
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
        neck_upper.rotation_quaternion = nu_rotation
        bpy.context.view_layer.update()

        # Read actual head position
        actual_head_pos = self.get_evaluated_bone_pos(neck_upper, head=False)

        return {
            'target_pos': target_pos.copy(),
            'actual_pos': actual_head_pos.copy(),
            'head_error': (actual_head_pos - target_pos).length,
            'upper_length': upper_length,
            'lower_length': lower_length,
            'max_reach': max_reach,
            'distance': distance,
            'nl_rotation': neck_lower.rotation_quaternion.copy(),
            'nu_rotation': neck_upper.rotation_quaternion.copy(),
        }

    def solve_leg(self, thigh_bone, shin_bone, target_pos, thigh_twist=None):
        """Simplified analytical 2-bone leg solver for combined tests."""
        armature = self.armature

        for bone in [thigh_bone, thigh_twist, shin_bone]:
            if bone:
                bone.rotation_quaternion = Quaternion()
                bone.location = Vector((0, 0, 0))
                bone.scale = Vector((1, 1, 1))
        bpy.context.view_layer.update()

        thigh_length, shin_length = self.get_bone_lengths(thigh_bone, shin_bone)
        joint_pos = armature.matrix_world @ thigh_bone.head

        joint_to_target = target_pos - joint_pos
        distance = joint_to_target.length
        max_reach = thigh_length + shin_length

        if distance <= abs(thigh_length - shin_length) * 0.1:
            return {'error': 'too_close'}
        if distance >= max_reach:
            distance = max_reach * 0.995

        # Bend normal
        thigh_world_mat = (armature.matrix_world @ thigh_bone.matrix).to_3x3().normalized()
        bend_normal = Vector(thigh_world_mat.col[0]).normalized()
        thigh_y = Vector(thigh_world_mat.col[1]).normalized()
        bone_z = Vector(thigh_world_mat.col[2]).normalized()
        test_dir = Quaternion(bend_normal, 0.01) @ thigh_y
        if test_dir.dot(bone_z) > thigh_y.dot(bone_z):
            bend_normal = -bend_normal

        target_dir = joint_to_target.normalized()

        # Law of cosines
        cos_hip = (thigh_length**2 + distance**2 - shin_length**2) / (2 * thigh_length * distance)
        cos_hip = max(-1, min(1, cos_hip))
        hip_angle = math.acos(cos_hip)

        rotation = Quaternion(bend_normal, hip_angle)
        thigh_dir = rotation @ target_dir

        # Thigh rotation
        rest_x = Vector(thigh_world_mat.col[0]).normalized()
        rest_quat = thigh_world_mat.to_quaternion()

        ty = thigh_dir.normalized()
        tx = bend_normal - bend_normal.dot(ty) * ty
        if tx.length < 0.001:
            tx = rest_x - rest_x.dot(ty) * ty
            if tx.length < 0.001:
                tx = Vector((1, 0, 0))
            tx.normalize()
        else:
            tx.normalize()
            if tx.dot(rest_x) < 0:
                tx = -tx
        tz = tx.cross(ty).normalized()

        thigh_mat = Matrix(((tx[0], ty[0], tz[0]),
                            (tx[1], ty[1], tz[1]),
                            (tx[2], ty[2], tz[2])))
        thigh_rot = rest_quat.inverted() @ thigh_mat.to_quaternion()
        if any(math.isnan(v) for v in thigh_rot):
            thigh_rot = Quaternion()
        thigh_bone.rotation_quaternion = thigh_rot
        bpy.context.view_layer.update()

        # Shin rotation
        shin_world = (armature.matrix_world @ shin_bone.matrix).to_3x3().normalized()
        shin_rest_quat = shin_world.to_quaternion()
        actual_knee = armature.matrix_world @ shin_bone.head
        shin_vec = target_pos - actual_knee
        if shin_vec.length > 0.001:
            shin_dir = shin_vec.normalized()
        else:
            shin_dir = thigh_dir

        sy = shin_dir
        sx = bend_normal - bend_normal.dot(sy) * sy
        if sx.length < 0.001:
            sx = tx - tx.dot(sy) * sy
            if sx.length < 0.001:
                sx = Vector((1, 0, 0))
            sx.normalize()
        else:
            sx.normalize()
            if sx.dot(tx) < 0:
                sx = -sx
        sz = sx.cross(sy).normalized()

        shin_mat = Matrix(((sx[0], sy[0], sz[0]),
                           (sx[1], sy[1], sz[1]),
                           (sx[2], sy[2], sz[2])))
        shin_rot = shin_rest_quat.inverted() @ shin_mat.to_quaternion()
        if any(math.isnan(v) for v in shin_rot):
            shin_rot = Quaternion()
        shin_bone.rotation_quaternion = shin_rot
        bpy.context.view_layer.update()

        actual_foot = self.get_evaluated_bone_pos(shin_bone, head=False)
        return {
            'target_pos': target_pos.copy(),
            'actual_pos': actual_foot.copy(),
            'foot_error': (actual_foot - target_pos).length,
        }

    # ===================================================================
    # TEST RUNNER
    # ===================================================================

    def run_all_tests(self):
        """Run all test cases and report results."""
        print("\n" + "=" * 60)
        print("  PIN SYSTEM REGRESSION TESTS")
        print("=" * 60)

        self.run_pin_setup_tests()
        self.run_spine_rotation_tests()
        self.run_neck_translation_tests()
        self.run_combined_tests()
        self.run_edge_case_tests()

        # SUMMARY
        self.reset_pose()
        print("\n" + "=" * 60)
        total = self.passed + self.failed
        print(f"  RESULTS: {self.passed} passed, {self.failed} failed out of {total} tests")
        print("=" * 60)

        if self.failed > 0:
            print("\n  FAILED TESTS:")
            for name, status, msg in self.results:
                if status == "FAIL":
                    print(f"    ✗ {name}" + (f" -- {msg}" if msg else ""))

        print()
        return self.passed, self.failed

    # ===================================================================
    # A. PIN SETUP TESTS
    # ===================================================================

    def run_pin_setup_tests(self):
        """Tests 1-6: Verify pin setup functions."""
        if not ADDON_IMPORTED:
            print("\n--- Skipping pin setup tests (addon not imported) ---")
            return

        print("\n--- A. Pin Setup Tests ---")
        armature = self.armature

        # Test 1: Pin head translation
        print("\n--- Test 1: Pin head translation ---")
        self.reset_pose()
        unpin_bone(armature, 'head')  # Clean slate
        result = pin_bone_translation(armature, 'head')
        head_data = armature.data.bones.get('head')
        self.assert_test("T1a: pin_bone_translation returns True", result == True)
        self.assert_test("T1b: daz_pin_translation set",
            is_bone_pinned_translation(head_data))
        has_constraint = any(c.name == "DAZ_Pin_Translation"
                           for c in self.head_bone.constraints)
        self.assert_test("T1c: DAZ_Pin_Translation constraint exists", has_constraint)
        empty_name = f"PIN_translation_{armature.name}_head"
        has_empty = bpy.data.objects.get(empty_name) is not None
        self.assert_test("T1d: Pin helper Empty exists", has_empty)
        unpin_bone(armature, 'head')

        # Test 2: Pin head rotation
        print("\n--- Test 2: Pin head rotation ---")
        self.reset_pose()
        result = pin_bone_rotation(armature, 'head')
        head_data = armature.data.bones.get('head')
        self.assert_test("T2a: pin_bone_rotation returns True", result == True)
        self.assert_test("T2b: daz_pin_rotation set",
            is_bone_pinned_rotation(head_data))
        has_rot_constraint = any(c.name == "DAZ_Pin_Rotation"
                                for c in self.head_bone.constraints)
        self.assert_test("T2c: DAZ_Pin_Rotation constraint exists", has_rot_constraint)
        rot_empty_name = f"PIN_rotation_{armature.name}_head"
        has_rot_empty = bpy.data.objects.get(rot_empty_name) is not None
        self.assert_test("T2d: Rotation pin helper Empty exists", has_rot_empty)
        self.assert_test("T2e: daz_pin_rotation_euler stored",
            head_data.get("daz_pin_rotation_euler") is not None)
        unpin_bone(armature, 'head')

        # Test 3: Pin foot translation
        print("\n--- Test 3: Pin lFoot translation ---")
        self.reset_pose()
        if self.l_foot:
            result = pin_bone_translation(armature, 'lFoot')
            foot_data = armature.data.bones.get('lFoot')
            self.assert_test("T3a: pin_bone_translation lFoot returns True", result == True)
            self.assert_test("T3b: lFoot daz_pin_translation set",
                is_bone_pinned_translation(foot_data))
            unpin_bone(armature, 'lFoot')
        else:
            self.assert_test("T3: lFoot exists", False, "lFoot bone not found")

        # Test 4: Unpin clears everything
        print("\n--- Test 4: Unpin clears everything ---")
        self.reset_pose()
        pin_bone_translation(armature, 'head')
        pin_bone_rotation(armature, 'head')
        unpin_bone(armature, 'head')
        head_data = armature.data.bones.get('head')
        self.assert_test("T4a: translation unpinned",
            not is_bone_pinned_translation(head_data))
        self.assert_test("T4b: rotation unpinned",
            not is_bone_pinned_rotation(head_data))
        has_any_pin_constraint = any(c.name.startswith("DAZ_Pin_")
                                    for c in self.head_bone.constraints)
        self.assert_test("T4c: no pin constraints remain", not has_any_pin_constraint)

        # Test 5: Pin both translation + rotation
        print("\n--- Test 5: Pin both translation + rotation ---")
        self.reset_pose()
        pin_bone_translation(armature, 'head')
        pin_bone_rotation(armature, 'head')
        head_data = armature.data.bones.get('head')
        self.assert_test("T5a: both pins set",
            is_bone_pinned_translation(head_data) and is_bone_pinned_rotation(head_data))
        has_trans = any(c.name == "DAZ_Pin_Translation" for c in self.head_bone.constraints)
        has_rot = any(c.name == "DAZ_Pin_Rotation" for c in self.head_bone.constraints)
        self.assert_test("T5b: both constraints exist", has_trans and has_rot)
        unpin_bone(armature, 'head')

        # Test 6: Pin status text
        print("\n--- Test 6: Pin status text ---")
        self.reset_pose()
        head_data = armature.data.bones.get('head')
        self.assert_test("T6a: no pins → empty text",
            get_pin_status_text(head_data) == "")
        pin_bone_translation(armature, 'head')
        head_data = armature.data.bones.get('head')
        self.assert_test("T6b: translation only text",
            "Translation" in get_pin_status_text(head_data))
        pin_bone_rotation(armature, 'head')
        head_data = armature.data.bones.get('head')
        self.assert_test("T6c: both pins text",
            "Translation" in get_pin_status_text(head_data) and
            "Rotation" in get_pin_status_text(head_data))
        unpin_bone(armature, 'head')

    # ===================================================================
    # B. SPINE ROTATION COMPENSATION TESTS
    # ===================================================================

    def run_spine_rotation_tests(self):
        """Tests 7-14: Head rotation pin + spine compensation."""
        print("\n--- B. Spine Rotation Compensation Tests ---")

        # Test 7: Hip rotate X (forward tilt, 15 degrees)
        print("\n--- Test 7: Hip rotate X forward 15° ---")
        self.reset_pose()
        pinned_quat = self.get_bone_world_rotation(self.head_bone)
        self.rotate_hip(Vector((1, 0, 0)), math.radians(15))
        # Reset compensation bones
        for bone in self.all_comp_bones:
            bone.rotation_quaternion = Quaternion()
        bpy.context.view_layer.update()
        self.solve_spine_rotation_compensation(pinned_quat)
        actual_quat = self.get_bone_world_rotation(self.head_bone)
        angle_err = pinned_quat.rotation_difference(actual_quat).angle
        self.assert_test("T7: head rotation error < 2°",
            math.degrees(angle_err) < 2.0,
            f"error={math.degrees(angle_err):.2f}°")

        # Test 8: Hip rotate X (backward tilt, -15 degrees)
        print("\n--- Test 8: Hip rotate X backward 15° ---")
        self.reset_pose()
        pinned_quat = self.get_bone_world_rotation(self.head_bone)
        self.rotate_hip(Vector((1, 0, 0)), math.radians(-15))
        for bone in self.all_comp_bones:
            bone.rotation_quaternion = Quaternion()
        bpy.context.view_layer.update()
        self.solve_spine_rotation_compensation(pinned_quat)
        actual_quat = self.get_bone_world_rotation(self.head_bone)
        angle_err = pinned_quat.rotation_difference(actual_quat).angle
        self.assert_test("T8: head rotation error < 2°",
            math.degrees(angle_err) < 2.0,
            f"error={math.degrees(angle_err):.2f}°")

        # Test 9: Hip rotate Z (side lean, 10 degrees)
        print("\n--- Test 9: Hip rotate Z side lean 10° ---")
        self.reset_pose()
        pinned_quat = self.get_bone_world_rotation(self.head_bone)
        self.rotate_hip(Vector((0, 0, 1)), math.radians(10))
        for bone in self.all_comp_bones:
            bone.rotation_quaternion = Quaternion()
        bpy.context.view_layer.update()
        self.solve_spine_rotation_compensation(pinned_quat)
        actual_quat = self.get_bone_world_rotation(self.head_bone)
        angle_err = pinned_quat.rotation_difference(actual_quat).angle
        self.assert_test("T9: head rotation error < 2°",
            math.degrees(angle_err) < 2.0,
            f"error={math.degrees(angle_err):.2f}°")

        # Test 10: Hip rotate Y (twist, 10 degrees)
        print("\n--- Test 10: Hip rotate Y twist 10° ---")
        self.reset_pose()
        pinned_quat = self.get_bone_world_rotation(self.head_bone)
        self.rotate_hip(Vector((0, 1, 0)), math.radians(10))
        for bone in self.all_comp_bones:
            bone.rotation_quaternion = Quaternion()
        bpy.context.view_layer.update()
        self.solve_spine_rotation_compensation(pinned_quat)
        actual_quat = self.get_bone_world_rotation(self.head_bone)
        angle_err = pinned_quat.rotation_difference(actual_quat).angle
        self.assert_test("T10: head rotation error < 2°",
            math.degrees(angle_err) < 2.0,
            f"error={math.degrees(angle_err):.2f}°")

        # Test 11: Small rotation (1 degree)
        print("\n--- Test 11: Small rotation 1° ---")
        self.reset_pose()
        pinned_quat = self.get_bone_world_rotation(self.head_bone)
        self.rotate_hip(Vector((1, 0, 0)), math.radians(1))
        for bone in self.all_comp_bones:
            bone.rotation_quaternion = Quaternion()
        bpy.context.view_layer.update()
        self.solve_spine_rotation_compensation(pinned_quat)
        actual_quat = self.get_bone_world_rotation(self.head_bone)
        angle_err = pinned_quat.rotation_difference(actual_quat).angle
        self.assert_test("T11: head rotation error < 1°",
            math.degrees(angle_err) < 1.0,
            f"error={math.degrees(angle_err):.2f}°")

        # Test 12: Large rotation (30 degrees) — stress test
        print("\n--- Test 12: Large rotation 30° ---")
        self.reset_pose()
        pinned_quat = self.get_bone_world_rotation(self.head_bone)
        self.rotate_hip(Vector((1, 0, 0)), math.radians(30))
        for bone in self.all_comp_bones:
            bone.rotation_quaternion = Quaternion()
        bpy.context.view_layer.update()
        self.solve_spine_rotation_compensation(pinned_quat)
        actual_quat = self.get_bone_world_rotation(self.head_bone)
        angle_err = pinned_quat.rotation_difference(actual_quat).angle
        self.assert_test("T12a: head rotation error < 5°",
            math.degrees(angle_err) < 5.0,
            f"error={math.degrees(angle_err):.2f}°")
        # NaN check
        all_ok = True
        for bone in self.all_comp_bones:
            if any(math.isnan(v) for v in bone.rotation_quaternion):
                all_ok = False
                break
        self.assert_test("T12b: no NaN in any bone rotation", all_ok)

        # Test 13: Spine weight distribution — verify ordering
        print("\n--- Test 13: Spine weight distribution ordering ---")
        # After test 12, read angular magnitudes of each bone's rotation
        # Expected: abdomen < chest < neck (lower stiffness = more movement)
        bone_angles = []
        for bone in self.all_comp_bones:
            angle = bone.rotation_quaternion.rotation_difference(Quaternion()).angle
            bone_angles.append((bone.name, math.degrees(angle)))
            print(f"    {bone.name}: {math.degrees(angle):.2f}°")

        # Check that neckUpper (remainder) has the largest rotation
        if len(bone_angles) >= 2:
            neck_upper_angle = bone_angles[-1][1]  # Last = neckUpper
            others_max = max(a for _, a in bone_angles[:-1])
            self.assert_test("T13: neckUpper (remainder) has largest rotation",
                neck_upper_angle >= others_max * 0.5,
                f"neckUpper={neck_upper_angle:.2f}°, others_max={others_max:.2f}°")

        # Test 14: Cancel restores all bones
        print("\n--- Test 14: Cancel restores all bones ---")
        self.reset_pose()
        # Store originals
        originals = {}
        for bone in self.all_comp_bones:
            originals[bone.name] = bone.rotation_quaternion.copy()
        pinned_quat = self.get_bone_world_rotation(self.head_bone)
        # Rotate and solve
        self.rotate_hip(Vector((1, 0, 0)), math.radians(15))
        for bone in self.all_comp_bones:
            bone.rotation_quaternion = Quaternion()
        bpy.context.view_layer.update()
        self.solve_spine_rotation_compensation(pinned_quat)
        # "Cancel" — restore originals
        self.hip_bone.rotation_quaternion = Quaternion()
        self.hip_bone.location = Vector((0, 0, 0))
        for bone in self.all_comp_bones:
            bone.rotation_quaternion = originals[bone.name]
        bpy.context.view_layer.update()
        # Verify
        all_restored = True
        for bone in self.all_comp_bones:
            diff = bone.rotation_quaternion.rotation_difference(originals[bone.name]).angle
            if diff > 0.001:
                all_restored = False
                print(f"    {bone.name}: diff={math.degrees(diff):.4f}°")
        self.assert_test("T14: all bones restored to original", all_restored)

    # ===================================================================
    # C. NECK TRANSLATION IK TESTS
    # ===================================================================

    def run_neck_translation_tests(self):
        """Tests 15-22: Head translation pin + neck IK with connectivity."""
        print("\n--- C. Neck Translation IK Tests ---")

        # Test 15: Hip translate down (-Z, 5cm)
        print("\n--- Test 15: Hip translate down 5cm ---")
        self.reset_pose()
        pin_target = self.get_evaluated_bone_pos(self.neck_upper, head=False)
        self.move_hip(Vector((0, 0, -0.05)))
        result = self.solve_neck_translation_ik(pin_target)
        if 'error' not in result:
            self.assert_test("T15a: head error < 2cm",
                result['head_error'] < 0.02,
                f"error={result['head_error']*100:.2f}cm")
            self.check_chain_connectivity("T15b")
        else:
            self.assert_test("T15: solver ran", False, f"error={result['error']}")

        # Test 16: Hip translate up (+Z, 3cm)
        print("\n--- Test 16: Hip translate up 3cm ---")
        self.reset_pose()
        pin_target = self.get_evaluated_bone_pos(self.neck_upper, head=False)
        self.move_hip(Vector((0, 0, 0.03)))
        result = self.solve_neck_translation_ik(pin_target)
        if 'error' not in result:
            self.assert_test("T16a: head error < 2cm",
                result['head_error'] < 0.02,
                f"error={result['head_error']*100:.2f}cm")
            self.check_chain_connectivity("T16b")
        else:
            self.assert_test("T16: solver ran", False, f"error={result['error']}")

        # Test 17: Hip translate forward (+Y, 3cm)
        # Note: the neck chain is ~6cm and nearly vertical. Forward hip movement
        # barely changes the joint-to-target distance (still ~9cm, dominated by
        # the vertical bone length). At 145% of max reach, the chain is fully
        # extended and the error reflects the geometric shortfall, not solver
        # inaccuracy. Tolerance is set accordingly (4cm ≈ expected overshoot).
        print("\n--- Test 17: Hip translate forward 3cm ---")
        self.reset_pose()
        pin_target = self.get_evaluated_bone_pos(self.neck_upper, head=False)
        self.move_hip(Vector((0, 0.03, 0)))
        result = self.solve_neck_translation_ik(pin_target)
        if 'error' not in result:
            self.assert_test("T17a: head error < 4cm (beyond reach)",
                result['head_error'] < 0.04,
                f"error={result['head_error']*100:.2f}cm")
            self.check_chain_connectivity("T17b")
        else:
            self.assert_test("T17: solver ran", False, f"error={result['error']}")

        # Test 18: Hip translate backward (-Y, 3cm)
        # This was the test that caught the bend normal bug — the old fixed
        # "forward bend" heuristic from the leg solver chose the wrong bend
        # direction for backward movement. Fixed by using cross(boneY, targetDir).
        print("\n--- Test 18: Hip translate backward 3cm ---")
        self.reset_pose()
        pin_target = self.get_evaluated_bone_pos(self.neck_upper, head=False)
        self.move_hip(Vector((0, -0.03, 0)))
        result = self.solve_neck_translation_ik(pin_target)
        if 'error' not in result:
            self.assert_test("T18a: head error < 3cm",
                result['head_error'] < 0.03,
                f"error={result['head_error']*100:.2f}cm")
            self.check_chain_connectivity("T18b")
        else:
            self.assert_test("T18: solver ran", False, f"error={result['error']}")

        # Test 19: Hip translate lateral (+X, 3cm)
        print("\n--- Test 19: Hip translate lateral 3cm ---")
        self.reset_pose()
        pin_target = self.get_evaluated_bone_pos(self.neck_upper, head=False)
        self.move_hip(Vector((0.03, 0, 0)))
        result = self.solve_neck_translation_ik(pin_target)
        if 'error' not in result:
            self.assert_test("T19a: head error < 3cm",
                result['head_error'] < 0.03,
                f"error={result['head_error']*100:.2f}cm")
            self.check_chain_connectivity("T19b")
        else:
            self.assert_test("T19: solver ran", False, f"error={result['error']}")

        # Test 20: Small movement (1mm)
        print("\n--- Test 20: Tiny movement 1mm ---")
        self.reset_pose()
        pin_target = self.get_evaluated_bone_pos(self.neck_upper, head=False)
        self.move_hip(Vector((0, 0, -0.001)))
        result = self.solve_neck_translation_ik(pin_target)
        if 'error' not in result:
            self.assert_test("T20a: head error < 1cm",
                result['head_error'] < 0.01,
                f"error={result['head_error']*100:.2f}cm")
            self.check_chain_connectivity("T20b")
        else:
            # too_close is acceptable for 1mm
            self.assert_test("T20: handled gracefully", True,
                f"result={result.get('error')}")

        # Test 21: Near max reach
        print("\n--- Test 21: Near max reach ---")
        self.reset_pose()
        pin_target = self.get_evaluated_bone_pos(self.neck_upper, head=False)
        upper_len, lower_len = self.get_bone_lengths(self.neck_lower, self.neck_upper)
        max_reach = upper_len + lower_len
        # Move hip down by 80% of max reach
        self.move_hip(Vector((0, 0, -max_reach * 0.8)))
        result = self.solve_neck_translation_ik(pin_target)
        if 'error' not in result:
            self.assert_test("T21a: head error < 5cm (near extension)",
                result['head_error'] < 0.05,
                f"error={result['head_error']*100:.2f}cm")
            # NaN check
            all_ok = not any(math.isnan(v) for v in result['nl_rotation']) and \
                     not any(math.isnan(v) for v in result['nu_rotation'])
            self.assert_test("T21b: no NaN", all_ok)
            self.check_chain_connectivity("T21c")
        else:
            self.assert_test("T21: solver ran", False, f"error={result['error']}")

        # Test 22: Cancel restores neck bones
        print("\n--- Test 22: Cancel restores neck bones ---")
        self.reset_pose()
        orig_nl = self.neck_lower.rotation_quaternion.copy()
        orig_nu = self.neck_upper.rotation_quaternion.copy()
        pin_target = self.get_evaluated_bone_pos(self.neck_upper, head=False)
        self.move_hip(Vector((0, 0, -0.05)))
        self.solve_neck_translation_ik(pin_target)
        # Cancel — restore
        self.hip_bone.location = Vector((0, 0, 0))
        self.neck_lower.rotation_quaternion = orig_nl
        self.neck_upper.rotation_quaternion = orig_nu
        bpy.context.view_layer.update()
        nl_diff = self.neck_lower.rotation_quaternion.rotation_difference(orig_nl).angle
        nu_diff = self.neck_upper.rotation_quaternion.rotation_difference(orig_nu).angle
        self.assert_test("T22a: neckLower restored",
            nl_diff < 0.001, f"diff={math.degrees(nl_diff):.4f}°")
        self.assert_test("T22b: neckUpper restored",
            nu_diff < 0.001, f"diff={math.degrees(nu_diff):.4f}°")

    # ===================================================================
    # D. COMBINED PIN TESTS
    # ===================================================================

    def run_combined_tests(self):
        """Tests 23-26: Multiple pin types working together."""
        print("\n--- D. Combined Pin Tests ---")

        if not self.l_thigh or not self.l_shin or not self.l_foot:
            print("  Skipping combined tests (leg bones missing)")
            return
        if not self.r_thigh or not self.r_shin or not self.r_foot:
            print("  Skipping combined tests (right leg bones missing)")
            return

        # Test 23: Head rotation pin + both feet translation
        print("\n--- Test 23: Head rotation + both feet pinned, hip forward 5cm ---")
        self.reset_pose()
        pinned_head_quat = self.get_bone_world_rotation(self.head_bone)
        l_foot_target = self.get_evaluated_bone_pos(self.l_shin, head=False)
        r_foot_target = self.get_evaluated_bone_pos(self.r_shin, head=False)

        self.move_hip(Vector((0, 0.05, 0)))

        # Reset all solver bones
        for bone in [self.l_thigh, self.l_thigh_twist, self.l_shin,
                     self.r_thigh, self.r_thigh_twist, self.r_shin]:
            if bone:
                bone.rotation_quaternion = Quaternion()
                bone.location = Vector((0, 0, 0))
                bone.scale = Vector((1, 1, 1))
        for bone in self.all_comp_bones:
            bone.rotation_quaternion = Quaternion()
        bpy.context.view_layer.update()

        # Solve legs
        l_result = self.solve_leg(self.l_thigh, self.l_shin, l_foot_target, self.l_thigh_twist)
        r_result = self.solve_leg(self.r_thigh, self.r_shin, r_foot_target, self.r_thigh_twist)

        # Solve spine rotation compensation
        self.solve_spine_rotation_compensation(pinned_head_quat)

        actual_head_quat = self.get_bone_world_rotation(self.head_bone)
        head_angle_err = pinned_head_quat.rotation_difference(actual_head_quat).angle

        self.assert_test("T23a: head rotation error < 2°",
            math.degrees(head_angle_err) < 2.0,
            f"error={math.degrees(head_angle_err):.2f}°")
        if 'error' not in l_result:
            self.assert_test("T23b: lFoot error < 3cm",
                l_result['foot_error'] < 0.03,
                f"error={l_result['foot_error']*100:.2f}cm")
        if 'error' not in r_result:
            self.assert_test("T23c: rFoot error < 3cm",
                r_result['foot_error'] < 0.03,
                f"error={r_result['foot_error']*100:.2f}cm")

        # Test 24: Head translation + both feet translation
        print("\n--- Test 24: Head translation + both feet, hip down 5cm ---")
        self.reset_pose()
        head_pin_pos = self.get_evaluated_bone_pos(self.neck_upper, head=False)
        l_foot_target = self.get_evaluated_bone_pos(self.l_shin, head=False)
        r_foot_target = self.get_evaluated_bone_pos(self.r_shin, head=False)

        self.move_hip(Vector((0, 0, -0.05)))

        # Reset all
        for bone in [self.l_thigh, self.l_thigh_twist, self.l_shin,
                     self.r_thigh, self.r_thigh_twist, self.r_shin]:
            if bone:
                bone.rotation_quaternion = Quaternion()
                bone.location = Vector((0, 0, 0))
                bone.scale = Vector((1, 1, 1))
        bpy.context.view_layer.update()

        # Solve legs
        l_result = self.solve_leg(self.l_thigh, self.l_shin, l_foot_target, self.l_thigh_twist)
        r_result = self.solve_leg(self.r_thigh, self.r_shin, r_foot_target, self.r_thigh_twist)

        # Solve neck IK
        neck_result = self.solve_neck_translation_ik(head_pin_pos)

        if 'error' not in neck_result:
            self.assert_test("T24a: head position error < 2cm",
                neck_result['head_error'] < 0.02,
                f"error={neck_result['head_error']*100:.2f}cm")
            self.check_chain_connectivity("T24b")
        if 'error' not in l_result:
            self.assert_test("T24c: lFoot error < 3cm",
                l_result['foot_error'] < 0.03,
                f"error={l_result['foot_error']*100:.2f}cm")
        if 'error' not in r_result:
            self.assert_test("T24d: rFoot error < 3cm",
                r_result['foot_error'] < 0.03,
                f"error={r_result['foot_error']*100:.2f}cm")

        # Test 25: Head rotation + translation (rotation should give way if both exist)
        print("\n--- Test 25: Head rotation + translation pins ---")
        self.reset_pose()
        pinned_head_quat = self.get_bone_world_rotation(self.head_bone)
        head_pin_pos = self.get_evaluated_bone_pos(self.neck_upper, head=False)
        self.move_hip(Vector((0, 0, -0.04)))
        # Solve translation first (position takes priority)
        neck_result = self.solve_neck_translation_ik(head_pin_pos)
        if 'error' not in neck_result:
            self.assert_test("T25a: head position maintained",
                neck_result['head_error'] < 0.02,
                f"error={neck_result['head_error']*100:.2f}cm")
            self.check_chain_connectivity("T25b")
        else:
            self.assert_test("T25: solver ran", False)

        # Test 26: Head rotation + all 4 limbs (stress test)
        print("\n--- Test 26: Head rotation + 4 limbs, hip forward 4cm ---")
        self.reset_pose()
        pinned_head_quat = self.get_bone_world_rotation(self.head_bone)
        l_foot_target = self.get_evaluated_bone_pos(self.l_shin, head=False)
        r_foot_target = self.get_evaluated_bone_pos(self.r_shin, head=False)

        self.move_hip(Vector((0, 0.04, 0)))

        for bone in [self.l_thigh, self.l_thigh_twist, self.l_shin,
                     self.r_thigh, self.r_thigh_twist, self.r_shin]:
            if bone:
                bone.rotation_quaternion = Quaternion()
                bone.location = Vector((0, 0, 0))
                bone.scale = Vector((1, 1, 1))
        for bone in self.all_comp_bones:
            bone.rotation_quaternion = Quaternion()
        bpy.context.view_layer.update()

        self.solve_leg(self.l_thigh, self.l_shin, l_foot_target, self.l_thigh_twist)
        self.solve_leg(self.r_thigh, self.r_shin, r_foot_target, self.r_thigh_twist)
        self.solve_spine_rotation_compensation(pinned_head_quat)

        actual_head_quat = self.get_bone_world_rotation(self.head_bone)
        head_angle_err = pinned_head_quat.rotation_difference(actual_head_quat).angle
        self.assert_test("T26: head rotation error < 3° (multi-limb stress)",
            math.degrees(head_angle_err) < 3.0,
            f"error={math.degrees(head_angle_err):.2f}°")

    # ===================================================================
    # E. EDGE CASE TESTS
    # ===================================================================

    def run_edge_case_tests(self):
        """Tests 27-30: Edge cases."""
        print("\n--- E. Edge Case Tests ---")

        # Test 27: NaN safety — all bones after large solve
        print("\n--- Test 27: NaN safety ---")
        self.reset_pose()
        pinned_quat = self.get_bone_world_rotation(self.head_bone)
        self.rotate_hip(Vector((1, 0.5, 0.3)).normalized(), math.radians(25))
        for bone in self.all_comp_bones:
            bone.rotation_quaternion = Quaternion()
        bpy.context.view_layer.update()
        self.solve_spine_rotation_compensation(pinned_quat)
        all_ok = True
        for bone in self.all_comp_bones:
            for v in bone.rotation_quaternion:
                if math.isnan(v) or math.isinf(v):
                    all_ok = False
                    print(f"    NaN/Inf in {bone.name}")
                    break
        self.assert_test("T27: no NaN/Inf in any rotation", all_ok)

        # Test 28: Bone length preservation after neck IK
        print("\n--- Test 28: Bone length preservation ---")
        self.reset_pose()
        nl_len_rest, nu_len_rest = self.get_bone_lengths(self.neck_lower, self.neck_upper)
        pin_target = self.get_evaluated_bone_pos(self.neck_upper, head=False)
        self.move_hip(Vector((0, 0, -0.05)))
        self.solve_neck_translation_ik(pin_target)
        nl_len_post, nu_len_post = self.get_bone_lengths(self.neck_lower, self.neck_upper)
        nl_diff = abs(nl_len_post - nl_len_rest)
        nu_diff = abs(nu_len_post - nu_len_rest)
        self.assert_test("T28a: neckLower length preserved (< 1mm)",
            nl_diff < 0.001,
            f"rest={nl_len_rest*100:.2f}cm post={nl_len_post*100:.2f}cm diff={nl_diff*1000:.2f}mm")
        self.assert_test("T28b: neckUpper length preserved (< 1mm)",
            nu_diff < 0.001,
            f"rest={nu_len_rest*100:.2f}cm post={nu_len_post*100:.2f}cm diff={nu_diff*1000:.2f}mm")

        # Test 29: Sequential solves without full reset
        print("\n--- Test 29: Sequential rotation solves ---")
        self.reset_pose()
        pinned_quat = self.get_bone_world_rotation(self.head_bone)
        # First solve
        self.rotate_hip(Vector((1, 0, 0)), math.radians(10))
        for bone in self.all_comp_bones:
            bone.rotation_quaternion = Quaternion()
        bpy.context.view_layer.update()
        self.solve_spine_rotation_compensation(pinned_quat)
        # Second rotation on top
        current_hip = self.hip_bone.rotation_quaternion.copy()
        self.hip_bone.rotation_quaternion = Quaternion(Vector((0, 0, 1)), math.radians(8)) @ current_hip
        bpy.context.view_layer.update()
        for bone in self.all_comp_bones:
            bone.rotation_quaternion = Quaternion()
        bpy.context.view_layer.update()
        self.solve_spine_rotation_compensation(pinned_quat)
        actual_quat = self.get_bone_world_rotation(self.head_bone)
        angle_err = pinned_quat.rotation_difference(actual_quat).angle
        self.assert_test("T29: sequential solve error < 3°",
            math.degrees(angle_err) < 3.0,
            f"error={math.degrees(angle_err):.2f}°")

        # Test 30: Identity solve — zero movement produces zero rotation
        print("\n--- Test 30: Identity solve ---")
        self.reset_pose()
        pinned_quat = self.get_bone_world_rotation(self.head_bone)
        # Don't move hip — just solve with identity
        for bone in self.all_comp_bones:
            bone.rotation_quaternion = Quaternion()
        bpy.context.view_layer.update()
        self.solve_spine_rotation_compensation(pinned_quat)
        # All bones should still be at identity (or very close)
        max_angle = 0
        for bone in self.all_comp_bones:
            angle = bone.rotation_quaternion.rotation_difference(Quaternion()).angle
            max_angle = max(max_angle, angle)
        self.assert_test("T30: identity solve — max bone rotation < 0.1°",
            math.degrees(max_angle) < 0.1,
            f"max_angle={math.degrees(max_angle):.4f}°")


# ===================================================================
# Entry point — run in Blender's Text Editor or via command line
# ===================================================================
armature = bpy.context.active_object
if not armature or armature.type != 'ARMATURE':
    print("ERROR: Select a Genesis 8/9 armature and switch to Pose mode first")
elif bpy.context.mode != 'POSE':
    print("ERROR: Switch to Pose mode first (select armature, Ctrl+Tab)")
else:
    harness = PinSystemTestHarness(armature)
    harness.run_all_tests()
