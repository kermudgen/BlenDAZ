# SPDX-License-Identifier: GPL-3.0-or-later
"""
Golden Pose Integration Tests

Requires a Blender scene with a DAZ Genesis 8/9 armature.
Tests actual solver integration by posing bones and measuring deltas.

Run:
    blender my_test_scene.blend --background --python -m pytest tests/test_golden_poses.py -v

These tests use the golden rule tier thresholds from conftest.py:
    T0 = 0.5 degrees  (perfect)
    T1 = 5.0 degrees  (cosmetic, acceptable for v1)
    T2 = 15.0 degrees (noticeable, requires sign-off)
    T3 = 15.0+ degrees (disruptive, never shippable)
"""

import math
import os
import pytest


def _bpy_available():
    try:
        import bpy
        return True
    except ImportError:
        return False


# These tests require Blender
pytestmark = pytest.mark.skipif(
    not _bpy_available(),
    reason="Requires Blender (bpy not available)"
)


# ===========================================================================
# Drag initiation pop tests (Golden Rule: zero disruption on grab)
# ===========================================================================
class TestDragInitiationPop:
    """Verify that entering drag mode doesn't visibly change the pose.

    The golden rule says: no pops on initiate. These tests capture bone
    rotations before and after the bake+mute cycle that prepares for drag,
    and assert the delta is within the target tier.
    """

    def test_bake_mute_preserves_rest_pose(self, reset_pose, tiers):
        """Bake+mute on a rest pose should produce zero delta."""
        import bpy
        armature = reset_pose

        # Capture pre-bake rotations
        test_bones = ['lShldrBend', 'lForearmBend', 'lCollar']
        pre_rotations = {}
        for name in test_bones:
            pb = armature.pose.bones.get(name)
            if pb:
                pre_rotations[name] = pb.rotation_quaternion.copy()

        if not pre_rotations:
            pytest.skip("DAZ arm bones not found in armature")

        # Simulate bake+mute: read evaluated rotation, write to quaternion, mute limits
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        arm_eval = armature.evaluated_get(depsgraph)

        for name in pre_rotations:
            pb = armature.pose.bones[name]
            pb_eval = arm_eval.pose.bones[name]
            pb.rotation_quaternion = pb_eval.rotation_quaternion.copy()
            # Mute LIMIT_ROTATION constraints
            for c in pb.constraints:
                if c.type == 'LIMIT_ROTATION':
                    c.mute = True

        bpy.context.view_layer.update()

        # Measure delta
        for name, pre_rot in pre_rotations.items():
            pb = armature.pose.bones[name]
            post_rot = pb.rotation_quaternion
            if pre_rot.dot(post_rot) < 0:
                post_rot = -post_rot
            delta = pre_rot.rotation_difference(post_rot)
            delta_deg = math.degrees(delta.angle)
            assert delta_deg < tiers.T0, (
                f"{name}: bake+mute caused {delta_deg:.2f}° delta (T0 max: {tiers.T0}°)"
            )

        # Restore constraints
        for name in pre_rotations:
            for c in armature.pose.bones[name].constraints:
                if c.type == 'LIMIT_ROTATION':
                    c.mute = False

    def test_bake_mute_preserves_posed_arm(self, reset_pose, tiers):
        """Bake+mute on a posed arm should produce delta within T0."""
        import bpy
        from mathutils import Euler
        armature = reset_pose

        # Set a non-trivial arm pose
        bones_to_pose = {
            'lShldrBend': (30, 0, -20),   # shoulder rotated
            'lForearmBend': (0, 0, -60),   # elbow bent
            'lCollar': (0, 5, -10),        # collar tilted
        }

        for name, euler_deg in bones_to_pose.items():
            pb = armature.pose.bones.get(name)
            if not pb:
                pytest.skip(f"Bone {name} not found")
            pb.rotation_mode = 'QUATERNION'
            euler_rad = tuple(math.radians(d) for d in euler_deg)
            pb.rotation_quaternion = Euler(euler_rad).to_quaternion()

        bpy.context.view_layer.update()

        # Capture pre-bake world positions
        pre_positions = {}
        depsgraph = bpy.context.evaluated_depsgraph_get()
        arm_eval = armature.evaluated_get(depsgraph)
        for name in bones_to_pose:
            pb_eval = arm_eval.pose.bones[name]
            pre_positions[name] = (armature.matrix_world @ pb_eval.head).copy()

        # Bake+mute cycle (mirrors invariant #3)
        for name in bones_to_pose:
            pb = armature.pose.bones[name]
            pb_eval = arm_eval.pose.bones[name]
            pb.rotation_quaternion = pb_eval.rotation_quaternion.copy()
            for c in pb.constraints:
                if c.type == 'LIMIT_ROTATION':
                    c.mute = True

        bpy.context.view_layer.update()

        # Check positions didn't move
        depsgraph = bpy.context.evaluated_depsgraph_get()
        arm_eval = armature.evaluated_get(depsgraph)
        for name, pre_pos in pre_positions.items():
            pb_eval = arm_eval.pose.bones[name]
            post_pos = armature.matrix_world @ pb_eval.head
            dist = (post_pos - pre_pos).length
            assert dist < tiers.T0_POS, (
                f"{name}: bake+mute moved bone {dist * 1000:.1f}mm (T0 max: {tiers.T0_POS * 1000:.0f}mm)"
            )

        # Restore constraints
        for name in bones_to_pose:
            for c in armature.pose.bones[name].constraints:
                if c.type == 'LIMIT_ROTATION':
                    c.mute = False


# ===========================================================================
# Drag release snap tests (Golden Rule: zero disruption on release)
# ===========================================================================
class TestDragReleasePop:
    """Verify that unmuting constraints after FABRIK doesn't cause a snap.

    The key: per-axis euler clamp (invariant #8) should match Blender's
    LIMIT_ROTATION exactly, so unmuting produces zero delta.
    """

    def test_clamped_rotation_matches_constraint(self, reset_pose, tiers):
        """A rotation clamped by our euler clamp should match Blender's constraint."""
        import bpy
        from mathutils import Euler
        armature = reset_pose

        bone_name = 'lShldrBend'
        pb = armature.pose.bones.get(bone_name)
        if not pb:
            pytest.skip(f"Bone {bone_name} not found")

        # Find LIMIT_ROTATION constraint and its limits
        limit_c = None
        for c in pb.constraints:
            if c.type == 'LIMIT_ROTATION':
                limit_c = c
                break

        if not limit_c:
            pytest.skip(f"No LIMIT_ROTATION on {bone_name}")

        # Set a rotation that exceeds limits
        pb.rotation_mode = 'QUATERNION'
        test_euler = Euler((math.radians(80), math.radians(50), math.radians(-80)))
        pb.rotation_quaternion = test_euler.to_quaternion()

        # Manually clamp (mirrors our Step 4b euler clamp)
        euler = pb.rotation_quaternion.to_euler('XYZ')
        if limit_c.use_limit_x:
            euler.x = max(limit_c.min_x, min(limit_c.max_x, euler.x))
        if limit_c.use_limit_y:
            euler.y = max(limit_c.min_y, min(limit_c.max_y, euler.y))
        if limit_c.use_limit_z:
            euler.z = max(limit_c.min_z, min(limit_c.max_z, euler.z))
        clamped_quat = euler.to_quaternion()
        pb.rotation_quaternion = clamped_quat

        # Now let Blender apply the constraint
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        arm_eval = armature.evaluated_get(depsgraph)
        pb_eval = arm_eval.pose.bones[bone_name]

        # Compare our clamp vs Blender's constraint result
        blender_rot = pb_eval.rotation_quaternion.copy()
        if clamped_quat.dot(blender_rot) < 0:
            blender_rot = -blender_rot
        delta = clamped_quat.rotation_difference(blender_rot)
        delta_deg = math.degrees(delta.angle)

        assert delta_deg < tiers.T0, (
            f"Euler clamp doesn't match Blender constraint: "
            f"{delta_deg:.2f}° delta (T0 max: {tiers.T0}°)"
        )


# ===========================================================================
# Golden pose capture and comparison
# ===========================================================================
class TestGoldenPoseSnapshot:
    """Capture and compare solver output against golden reference poses.

    First run: captures golden poses to tests/fixtures/golden_poses/
    Subsequent runs: compares against saved golden poses.
    """

    GOLDEN_FILE = os.path.join(
        os.path.dirname(__file__), 'fixtures', 'golden_poses', 'rest_arm_bake.json'
    )

    def test_rest_arm_bake_golden(self, reset_pose, tiers, pose_helpers):
        """Rest pose arm bake should be stable across code changes."""
        import bpy
        armature = reset_pose

        arm_bones = ['lCollar', 'lShldrBend', 'lShldrTwist',
                      'lForearmBend', 'lForearmTwist', 'lHand']

        # Check bones exist
        available = [n for n in arm_bones if armature.pose.bones.get(n)]
        if len(available) < 3:
            pytest.skip("Not enough DAZ arm bones found")

        # Capture current rotations
        current = {}
        for name in available:
            pb = armature.pose.bones[name]
            q = pb.rotation_quaternion
            current[name] = [q.w, q.x, q.y, q.z]

        if not os.path.exists(self.GOLDEN_FILE):
            # First run — save as golden reference
            os.makedirs(os.path.dirname(self.GOLDEN_FILE), exist_ok=True)
            pose_helpers['save'](self.GOLDEN_FILE, current, {
                'description': 'Rest pose arm bone rotations',
                'tier_target': 'T0',
            })
            pytest.skip("Golden pose saved — run again to test against it")

        # Compare against golden
        golden = pose_helpers['load'](self.GOLDEN_FILE)
        for name, golden_rot in golden['bone_rotations'].items():
            if name not in current:
                continue
            delta = pose_helpers['delta_degrees'](current[name], golden_rot)
            assert delta < tiers.T0, (
                f"{name}: {delta:.2f}° drift from golden pose (T0 max: {tiers.T0}°)"
            )
