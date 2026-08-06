# SPDX-License-Identifier: GPL-3.0-or-later
"""
Pin Maintenance Regression Tests — PRODUCTION CODE

Unlike test_pin_system.py / test_hip_pin_ik.py (which reimplement the solver
math), these tests exercise the actual production methods in
daz_bone_select.py via an operator stub:

    _find_pinned_limbs        — limb state discovery from pins
    _solve_pin_maintenance_frame — the per-depsgraph-update solve pass
    _apply_pin_reach_leash    — DAZ rule 8 root leash
    _solve_pinned_limb        — analytical 2-bone limb IK

Runs headless against the synthetic Genesis-8 armature fixture (no DAZ
content required):

    blender --background --python tests/run_tests.py -- tests/test_pin_maintenance.py -v

Tier targets: endpoint position T1 (5mm) after solve; pose preservation T0
(0.5 deg) for bones the solver doesn't own.
"""

import math
import functools
import pytest

# Only meaningful inside Blender
bpy = pytest.importorskip('bpy')
from mathutils import Vector, Quaternion  # noqa: E402


# ---------------------------------------------------------------------------
# Operator stub: instance state lives here; class constants and methods
# resolve through the production operator class and bind to this stub.
# ---------------------------------------------------------------------------
class OpStub:
    def __init__(self, op_cls, armature, root_name='hip'):
        # NOTE: set instance attrs before anything triggers __getattr__
        self.__dict__['_op_cls'] = op_cls
        self._hip_pin_limbs = []
        self._hip_pin_neck_state = None
        self._hip_original_rotations = {}
        self._hip_bone = armature.pose.bones[root_name]
        self._hip_pin_root_bone = armature.pose.bones['hip']
        self._hip_debug_frame = 0
        self._use_hip_pin_ik = True
        self._hip_pin_solving = False
        self._pinned_arm_log_count = 0

    def __getattr__(self, name):
        attr = getattr(self.__dict__['_op_cls'], name)
        if callable(attr) and not isinstance(attr, type):
            return functools.partial(attr, self)
        return attr


def _world_head(armature, bone_name):
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    arm_eval = armature.evaluated_get(depsgraph)
    return armature.matrix_world @ Vector(arm_eval.pose.bones[bone_name].head)


def _move_root_world(armature, root_pb, world_delta):
    """Translate a root pose bone by a world-space delta (same conversion the
    reach leash uses)."""
    conv = (armature.matrix_world.to_3x3() @ root_pb.bone.matrix_local.to_3x3()).inverted()
    root_pb.location += conv @ Vector(world_delta)
    bpy.context.view_layer.update()


def _rotate_bone_world_axis(armature, pb, world_axis, angle_deg):
    """Compose a rotation about a world-space axis onto a pose bone."""
    bpy.context.view_layer.update()
    bone_world = (armature.matrix_world @ pb.matrix).to_3x3().normalized().to_quaternion()
    world_rot = Quaternion(Vector(world_axis).normalized(), math.radians(angle_deg))
    local_delta = bone_world.inverted() @ world_rot @ bone_world
    pb.rotation_quaternion = local_delta @ pb.rotation_quaternion
    bpy.context.view_layer.update()


def _capture_originals(stub, armature):
    """Mimic _start_hip_pin_drag's originals capture."""
    originals = {}
    for name in ('hip', stub._hip_bone.name):
        pb = armature.pose.bones[name]
        originals[name] = {'location': pb.location.copy(),
                           'rotation': pb.rotation_quaternion.copy()}
    for limb in stub._hip_pin_limbs:
        for bone in limb['bones'].values():
            if bone and bone.name not in originals:
                originals[bone.name] = {'location': bone.location.copy(),
                                        'rotation': bone.rotation_quaternion.copy()}
    stub._hip_original_rotations = originals


def _make_stub(dbs_module, armature, pin_bones, anchor='hip'):
    """Pin the given endpoint bones and build a ready-to-solve stub."""
    op_cls = dbs_module.VIEW3D_OT_daz_bone_select
    for bone_name in pin_bones:
        assert dbs_module.pin_bone_translation(armature, bone_name), \
            f"pin_bone_translation failed for {bone_name}"
    stub = OpStub(op_cls, armature, root_name=anchor)
    stub._hip_pin_limbs = op_cls._find_pinned_limbs(stub, armature)
    assert len(stub._hip_pin_limbs) == len(pin_bones), \
        f"expected {len(pin_bones)} limb(s), got {len(stub._hip_pin_limbs)}"
    # Production mutes the pin constraints during the drag — do the same so
    # COPY_LOCATION doesn't mask solver output.
    for limb in stub._hip_pin_limbs:
        endpoint = armature.pose.bones[limb['endpoint_name']]
        for c in endpoint.constraints:
            if c.name == 'DAZ_Pin_Translation':
                c.mute = True
    _capture_originals(stub, armature)
    return stub


def _solve_frames(stub, armature, frames=3):
    for _ in range(frames):
        stub._solve_pin_maintenance_frame(armature)
    bpy.context.view_layer.update()


TOL_ENDPOINT = 0.005   # 5mm — golden rule T1
TOL_ROT_DEG = 0.5      # 0.5 deg — golden rule T0


# ---------------------------------------------------------------------------
# Translation (G) — existing behavior, now under test
# ---------------------------------------------------------------------------
def test_hip_translate_within_reach_feet_pinned(synthetic_g8, dbs_module):
    armature = synthetic_g8
    stub = _make_stub(dbs_module, armature, ['lFoot', 'rFoot'])
    pins = {l['endpoint_name']: l['pin_target_pos'].copy() for l in stub._hip_pin_limbs}

    hip = armature.pose.bones['hip']
    _move_root_world(armature, hip, (0, 0, -0.10))
    _solve_frames(stub, armature)

    for name, pin_pos in pins.items():
        err = (_world_head(armature, name) - pin_pos).length
        assert err < TOL_ENDPOINT, f"{name} drifted {err*1000:.1f}mm off its pin"

    # Within reach: the leash must not have fought the drag
    hip_z = _world_head(armature, 'hip').z
    assert abs(hip_z - 0.90) < 0.005, f"leash moved hip while within reach (z={hip_z:.3f})"


def test_hip_translate_beyond_reach_leash_holds_pins(synthetic_g8, dbs_module):
    """DAZ rule 8: over-extending drags translate the root back instead of
    breaking the pin."""
    armature = synthetic_g8
    stub = _make_stub(dbs_module, armature, ['lFoot', 'rFoot'])
    pins = {l['endpoint_name']: l['pin_target_pos'].copy() for l in stub._hip_pin_limbs}

    hip = armature.pose.bones['hip']
    _move_root_world(armature, hip, (0, 0, +0.30))   # far beyond leg reach
    _solve_frames(stub, armature)

    for name, pin_pos in pins.items():
        err = (_world_head(armature, name) - pin_pos).length
        assert err < TOL_ENDPOINT, f"{name} broke its pin by {err*1000:.1f}mm"

    # The leash must have pulled the hip most of the way back (legs were
    # nearly fully extended at rest)
    hip_z = _world_head(armature, 'hip').z
    assert hip_z < 1.05, f"leash failed to restrain hip (z={hip_z:.3f}, requested 1.30)"


def test_leash_noop_within_reach(synthetic_g8, dbs_module):
    armature = synthetic_g8
    stub = _make_stub(dbs_module, armature, ['lFoot'])
    hip = armature.pose.bones['hip']
    _move_root_world(armature, hip, (0, 0, -0.05))
    loc_before = hip.location.copy()
    op_cls = dbs_module.VIEW3D_OT_daz_bone_select
    assert op_cls._apply_pin_reach_leash(stub, armature, stub._hip_pin_limbs, hip) is False
    assert (hip.location - loc_before).length < 1e-9


# ---------------------------------------------------------------------------
# Rotation (R) — new pin maintenance path
# ---------------------------------------------------------------------------
def test_hip_rotate_feet_stay_pinned(synthetic_g8, dbs_module):
    armature = synthetic_g8
    stub = _make_stub(dbs_module, armature, ['lFoot', 'rFoot'])
    pins = {l['endpoint_name']: l['pin_target_pos'].copy() for l in stub._hip_pin_limbs}

    hip = armature.pose.bones['hip']
    _rotate_bone_world_axis(armature, hip, (0, 0, 1), 25.0)
    set_rotation = hip.rotation_quaternion.copy()
    _solve_frames(stub, armature)

    for name, pin_pos in pins.items():
        err = (_world_head(armature, name) - pin_pos).length
        assert err < TOL_ENDPOINT, f"{name} drifted {err*1000:.1f}mm off its pin during hip rotation"

    # The solver must not touch the user's rotation channel (only location, via leash)
    delta = set_rotation.rotation_difference(hip.rotation_quaternion)
    assert math.degrees(delta.angle) < TOL_ROT_DEG, "solver modified the hip rotation"


def test_chest_rotate_posed_arm_stays_pinned(synthetic_g8, dbs_module):
    """Touch-rotation path regression: arm POSED away from rest when the hand
    is pinned, then a spine bone rotates. The pre-2026-07-03 rotation path
    reset solver-owned bones to their drag-start pose instead of identity,
    corrupting every solve (the solver reads their pose matrix as its rest
    frame) — hands visibly detached from the forearms."""
    armature = synthetic_g8
    op_cls = dbs_module.VIEW3D_OT_daz_bone_select

    # User poses the arm first (bent elbow, rotated shoulder)
    shoulder = armature.pose.bones['lShldrBend']
    forearm = armature.pose.bones['lForearmBend']
    shoulder.rotation_quaternion = Quaternion((0, 0, 1), math.radians(30))
    forearm.rotation_quaternion = Quaternion((1, 0, 0), math.radians(-40))
    bpy.context.view_layer.update()

    # Pin the hand at its POSED position; originals capture the posed arm
    stub = _make_stub(dbs_module, armature, ['lHand'], anchor='chestUpper')
    pin_pos = stub._hip_pin_limbs[0]['pin_target_pos'].copy()

    chest = armature.pose.bones['chestUpper']
    _rotate_bone_world_axis(armature, chest, (1, 0, 0), 15.0)

    # Invoke via the explicit-args path used by _apply_rotation_pin_ik
    for _ in range(4):
        op_cls._solve_pin_maintenance_frame(
            stub, armature,
            limbs=stub._hip_pin_limbs,
            originals=stub._hip_original_rotations,
            neck_state=None,
            root_bone=armature.pose.bones['hip'])
    bpy.context.view_layer.update()

    err = (_world_head(armature, 'lHand') - pin_pos).length
    assert err < TOL_ENDPOINT, \
        f"lHand detached {err*1000:.1f}mm from its pin (posed-arm chest rotation)"


def test_chest_rotate_hand_stays_pinned(synthetic_g8, dbs_module):
    """R on a spine bone with a pinned hand: the arm re-solves each frame."""
    armature = synthetic_g8
    stub = _make_stub(dbs_module, armature, ['lHand'], anchor='chestUpper')
    pin_pos = stub._hip_pin_limbs[0]['pin_target_pos'].copy()

    chest = armature.pose.bones['chestUpper']
    _rotate_bone_world_axis(armature, chest, (0, 1, 0), 20.0)  # lean sideways
    _solve_frames(stub, armature)

    err = (_world_head(armature, 'lHand') - pin_pos).length
    assert err < TOL_ENDPOINT, f"lHand drifted {err*1000:.1f}mm off its pin during chest rotation"

    # Anchor bone must keep the user's rotation
    bpy.context.view_layer.update()
    assert chest.rotation_quaternion.angle > math.radians(5), "solver wiped the chest rotation"


def test_find_pinned_limbs_self_heals_missing_empty(synthetic_g8, dbs_module):
    """A pin whose helper empty was deleted (re-opened .blend, orphan cleanup)
    must be rediscovered: _find_pinned_limbs recreates the empty at the stored
    daz_pin_location and re-points the constraint."""
    armature = synthetic_g8
    op_cls = dbs_module.VIEW3D_OT_daz_bone_select

    assert dbs_module.pin_bone_translation(armature, 'lHand')
    empty_name = f"PIN_translation_{armature.name}_lHand"
    stored = Vector(armature.data.bones['lHand']["daz_pin_location"])

    # Simulate the degraded state: empty deleted, property survives
    bpy.data.objects.remove(bpy.data.objects[empty_name], do_unlink=True)
    assert bpy.data.objects.get(empty_name) is None

    stub = OpStub(op_cls, armature)
    limbs = op_cls._find_pinned_limbs(stub, armature)

    assert len(limbs) == 1, "self-heal failed: pin with missing empty not rediscovered"
    healed = bpy.data.objects.get(empty_name)
    assert healed is not None, "pin empty was not recreated"
    assert (healed.matrix_world.translation - stored).length < 1e-6, \
        "recreated empty is not at the stored pin location"
    con = next((c for c in armature.pose.bones['lHand'].constraints
                if c.name == 'DAZ_Pin_Translation'), None)
    assert con is not None and con.target == healed, "constraint not re-pointed at healed empty"


# ---------------------------------------------------------------------------
# Pose preservation — solver must not clobber bones it doesn't own
# ---------------------------------------------------------------------------
def test_unpinned_bone_pose_preserved_during_drag(synthetic_g8, dbs_module):
    """Foot roll and thigh twist set by the user survive a pinned hip drag
    (reset-to-originals, not reset-to-identity)."""
    armature = synthetic_g8
    foot = armature.pose.bones['lFoot']
    twist = armature.pose.bones['lThighTwist']

    # User poses foot roll + thigh twist BEFORE pinning
    foot.rotation_quaternion = Quaternion((1, 0, 0), math.radians(20))
    twist.rotation_quaternion = Quaternion((0, 1, 0), math.radians(15))
    bpy.context.view_layer.update()
    foot_orig = foot.rotation_quaternion.copy()
    twist_orig = twist.rotation_quaternion.copy()

    stub = _make_stub(dbs_module, armature, ['lFoot'])
    hip = armature.pose.bones['hip']
    _move_root_world(armature, hip, (0, 0, -0.05))
    _solve_frames(stub, armature)

    for pb, orig, label in ((foot, foot_orig, 'foot roll'),
                            (twist, twist_orig, 'thigh twist')):
        delta = orig.rotation_difference(pb.rotation_quaternion)
        assert math.degrees(delta.angle) < TOL_ROT_DEG, \
            f"solver wiped user-set {label} ({math.degrees(delta.angle):.1f} deg change)"
