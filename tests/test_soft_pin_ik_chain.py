# SPDX-License-Identifier: GPL-3.0-or-later
"""
Soft-pin IK chain geometry regression tests — PRODUCTION CODE

Guards the wrist-vs-forearm-tail confusion on Diffeomorphic rigs (the forearm
BEND bone ends mid-forearm; forearmTwist continues to the wrist, and hand.head
sits at the twist's tail — see DRAG_FIX_LOG.md entries 005/006). The soft-pin
drag path must anchor the IK at the pinned bone's HEAD (the wrist/ankle — the
exact point the pin constraint holds):

    create_ik_chain(soft_pin_mode=True):
      - the .ik.target bone is created AT the pinned child's head
      - IK_Temp sits on the pinned child's .ik bone with use_tail=False
        (effector = pinned child's head, matching both target and pin)

Runs headless against the synthetic Genesis-8 armature fixture (no DAZ
content required):

    blender --background --python tests/run_tests.py -- tests/test_soft_pin_ik_chain.py -v

Tier target: endpoint position T0 (1mm) for target placement.
"""

import pytest

bpy = pytest.importorskip('bpy')
from mathutils import Vector  # noqa: E402


TOL_T0 = 0.001  # 1mm — golden rule T0


def _world_head(armature, bone_name):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    arm_eval = armature.evaluated_get(depsgraph)
    return armature.matrix_world @ Vector(arm_eval.pose.bones[bone_name].head)


def _find_ik_temp(armature, bone_name):
    pb = armature.pose.bones.get(bone_name)
    assert pb is not None, f"{bone_name} was not created"
    for c in pb.constraints:
        if c.name == 'IK_Temp':
            return c
    return None


def test_soft_pin_arm_target_at_wrist(synthetic_g8, dbs_module):
    """Forearm drag with pinned hand: the IK target must sit at the WRIST
    (lHand.head), not at lForearmBend.tail (mid-forearm on Diffeomorphic
    rigs) and not at lHand.tail."""
    armature = synthetic_g8
    assert dbs_module.pin_bone_translation(armature, 'lHand')

    wrist = _world_head(armature, 'lHand')
    # The trap this test guards against: on the realistic layout the forearm
    # BEND tail is mid-forearm, well away from the wrist.
    forearm_tail = armature.matrix_world @ armature.pose.bones['lForearmBend'].tail
    assert (forearm_tail - wrist).length > 0.05, \
        "synthetic rig no longer has the mid-forearm bend-tail layout"

    result = dbs_module.create_ik_chain(armature, 'lForearmBend', soft_pin_mode=True)
    target_name = result[0]
    assert target_name, "create_ik_chain failed"

    target_head = armature.matrix_world @ armature.pose.bones[target_name].head
    err = (target_head - wrist).length
    assert err < TOL_T0, f"IK target sits {err*1000:.1f}mm off the wrist pin point"

    ik_con = _find_ik_temp(armature, 'lHand.ik')
    assert ik_con is not None, "IK_Temp constraint missing from pinned child's .ik bone"
    assert ik_con.use_tail is False, \
        "soft-pin effector must be the pinned child's HEAD (use_tail=False)"
    assert ik_con.subtarget == target_name


def test_soft_pin_leg_target_at_ankle(synthetic_g8, dbs_module):
    """Shin drag with pinned foot: same invariant at the ankle (lFoot.head)."""
    armature = synthetic_g8
    assert dbs_module.pin_bone_translation(armature, 'lFoot')

    ankle = _world_head(armature, 'lFoot')
    result = dbs_module.create_ik_chain(armature, 'lShin', soft_pin_mode=True)
    target_name = result[0]
    assert target_name, "create_ik_chain failed"

    target_head = armature.matrix_world @ armature.pose.bones[target_name].head
    err = (target_head - ankle).length
    assert err < TOL_T0, f"IK target sits {err*1000:.1f}mm off the ankle pin point"

    ik_con = _find_ik_temp(armature, 'lFoot.ik')
    assert ik_con is not None, "IK_Temp constraint missing from pinned child's .ik bone"
    assert ik_con.use_tail is False, \
        "soft-pin effector must be the pinned child's HEAD (use_tail=False)"


def test_normal_mode_keeps_tail_effector(synthetic_g8, dbs_module):
    """Non-soft-pin chains keep the original tail effector (unchanged path)."""
    armature = synthetic_g8
    result = dbs_module.create_ik_chain(armature, 'lForearmBend', soft_pin_mode=False)
    target_name = result[0]
    assert target_name, "create_ik_chain failed"

    ik_con = _find_ik_temp(armature, 'lForearmBend.ik')
    assert ik_con is not None, "IK_Temp constraint missing from tip .ik bone"
    assert ik_con.use_tail is True, "normal-mode effector semantics must not change"
