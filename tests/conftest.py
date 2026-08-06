# SPDX-License-Identifier: GPL-3.0-or-later
"""
pytest-blender configuration for BlenDAZ test suite.

Usage:
    # Install pytest into Blender's Python:
    blender --background --python-expr "import subprocess, sys; subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pytest'])"

    # Run all tests:
    blender --background --python -m pytest tests/ -v

    # Run just FABRIK solver tests (fast, no scene needed):
    blender --background --python -m pytest tests/test_fabrik_regression.py -v

    # Run golden pose tests (needs fixture .blend):
    blender --background --python -m pytest tests/test_golden_poses.py -v

    # Run with pytest-blender from external Python (if installed):
    pytest tests/ --blender-executable /path/to/blender -v
"""

import sys
import os
import json
import pytest

# Ensure addon root is importable
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

# ---------------------------------------------------------------------------
# Fixtures directory
# ---------------------------------------------------------------------------
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def _ensure_fixtures_dir():
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    golden_dir = os.path.join(FIXTURES_DIR, 'golden_poses')
    os.makedirs(golden_dir, exist_ok=True)
    return FIXTURES_DIR


# ---------------------------------------------------------------------------
# Thresholds matching golden rule tiers
# ---------------------------------------------------------------------------
class GoldenRuleTiers:
    """Numeric thresholds for each golden rule tier (in degrees)."""
    T0 = 0.5    # Perfect: < 0.5 degree
    T1 = 5.0    # Cosmetic: < 5 degrees
    T2 = 15.0   # Noticeable: < 15 degrees
    T3 = 15.0   # Disruptive: >= 15 degrees (always fail)

    # Endpoint position thresholds (in meters)
    T0_POS = 0.001   # 1mm
    T1_POS = 0.005   # 5mm
    T2_POS = 0.015   # 15mm


@pytest.fixture
def tiers():
    """Golden rule tier thresholds."""
    return GoldenRuleTiers


# ---------------------------------------------------------------------------
# FABRIK solver fixtures (pure math, no Blender scene)
# ---------------------------------------------------------------------------
@pytest.fixture
def fabrik_module():
    """Import fabrik_solver module."""
    import fabrik_solver
    return fabrik_solver




# ---------------------------------------------------------------------------
# Golden pose snapshot helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def golden_pose_dir():
    """Directory for golden pose JSON files."""
    d = os.path.join(_ensure_fixtures_dir(), 'golden_poses')
    return d


def save_golden_pose(filepath, bone_rotations, metadata=None):
    """Save a golden pose snapshot to JSON.

    Args:
        filepath: Path to save the JSON file.
        bone_rotations: Dict of {bone_name: [w, x, y, z]} quaternion values.
        metadata: Optional dict with test context (solver version, date, etc.)
    """
    data = {
        'format_version': 1,
        'metadata': metadata or {},
        'bone_rotations': bone_rotations,
    }
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def load_golden_pose(filepath):
    """Load a golden pose snapshot from JSON.

    Returns:
        Dict with 'bone_rotations' and 'metadata'.
    """
    with open(filepath, 'r') as f:
        return json.load(f)


def rotation_delta_degrees(quat_a, quat_b):
    """Compute angular difference between two quaternions in degrees.

    Args:
        quat_a, quat_b: 4-element sequences (w, x, y, z).

    Returns:
        Angle in degrees.
    """
    from mathutils import Quaternion
    import math
    q1 = Quaternion(quat_a)
    q2 = Quaternion(quat_b)
    # Ensure same hemisphere
    if q1.dot(q2) < 0:
        q2 = -q2
    delta = q1.rotation_difference(q2)
    return math.degrees(delta.angle)


# Export helpers for use in test files
@pytest.fixture
def pose_helpers():
    """Bundle of pose helper functions."""
    return {
        'save': save_golden_pose,
        'load': load_golden_pose,
        'delta_degrees': rotation_delta_degrees,
    }


# ---------------------------------------------------------------------------
# Blender scene fixtures (only available when running inside Blender)
# ---------------------------------------------------------------------------
@pytest.fixture
def blender_available():
    """Check if we're running inside Blender with bpy available."""
    try:
        import bpy
        return True
    except ImportError:
        pytest.skip("Requires Blender (bpy not available)")


@pytest.fixture
def armature(blender_available):
    """Get the active armature from the current Blender scene.

    Skips test if no armature is active.
    """
    import bpy
    obj = bpy.context.active_object
    if not obj or obj.type != 'ARMATURE':
        pytest.skip("No active armature — load a DAZ character .blend first")
    return obj


@pytest.fixture
def reset_pose(armature):
    """Reset all bones to rest pose before each test."""
    import bpy
    from mathutils import Quaternion, Vector
    for pb in armature.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = Quaternion()
        pb.location = Vector((0, 0, 0))
        pb.scale = Vector((1, 1, 1))
    bpy.context.view_layer.update()
    return armature


def evaluated_bone_head(armature, bone_name):
    """Get world-space head position of a bone from the evaluated depsgraph."""
    import bpy
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    arm_eval = armature.evaluated_get(depsgraph)
    pb = arm_eval.pose.bones[bone_name]
    return armature.matrix_world @ pb.head


def evaluated_bone_rotation(armature, bone_name):
    """Get the evaluated rotation quaternion of a bone."""
    import bpy
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    arm_eval = armature.evaluated_get(depsgraph)
    pb = arm_eval.pose.bones[bone_name]
    return pb.rotation_quaternion.copy()


@pytest.fixture
def scene_helpers(armature):
    """Bundle of Blender scene helper functions."""
    return {
        'bone_head': lambda name: evaluated_bone_head(armature, name),
        'bone_rotation': lambda name: evaluated_bone_rotation(armature, name),
    }


# ---------------------------------------------------------------------------
# Production module import (daz_bone_select uses relative imports, so it must
# be loaded as a package member — we synthesize a package pointing at the
# addon root instead of importing the real __init__.py, which pulls in
# posebridge/poseblend)
# ---------------------------------------------------------------------------
_TEST_PKG_NAME = 'blendaz_under_test'


def load_production_module(module_name='daz_bone_select'):
    """Import an addon module as part of a synthetic package so its relative
    imports (from . import daz_shared_utils, fabrik_solver, ...) resolve."""
    import types
    import importlib.util

    if _TEST_PKG_NAME not in sys.modules:
        pkg = types.ModuleType(_TEST_PKG_NAME)
        pkg.__path__ = [ADDON_DIR]
        sys.modules[_TEST_PKG_NAME] = pkg

    full_name = f'{_TEST_PKG_NAME}.{module_name}'
    if full_name in sys.modules:
        return sys.modules[full_name]

    spec = importlib.util.spec_from_file_location(
        full_name, os.path.join(ADDON_DIR, f'{module_name}.py'),
        submodule_search_locations=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = _TEST_PKG_NAME
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope='session')
def dbs_module(blender_session):
    """The production daz_bone_select module."""
    return load_production_module('daz_bone_select')


@pytest.fixture(scope='session')
def blender_session():
    """Session-scoped bpy availability check."""
    try:
        import bpy  # noqa: F401
        return True
    except ImportError:
        pytest.skip("Requires Blender (bpy not available)")


# ---------------------------------------------------------------------------
# Synthetic Genesis-8-proportioned armature (no DAZ content needed).
# Bone names, hierarchy, and twist-bone layout match what the pin solvers
# expect; proportions are approximately human. Elbows/knees have a slight
# rest bend so endpoints are inside max reach.
# ---------------------------------------------------------------------------
# (name, parent, head, tail)
_G8_SYNTH_BONES = [
    ('hip',          None,           (0.00, 0.00, 1.00), (0.00, 0.00, 1.10)),
    ('pelvis',       'hip',          (0.00, 0.00, 1.00), (0.00, 0.00, 0.90)),

    ('abdomenLower', 'hip',          (0.00, 0.00, 1.00), (0.00, 0.00, 1.10)),
    ('abdomenUpper', 'abdomenLower', (0.00, 0.00, 1.10), (0.00, 0.00, 1.20)),
    ('chestLower',   'abdomenUpper', (0.00, 0.00, 1.20), (0.00, 0.00, 1.32)),
    ('chestUpper',   'chestLower',   (0.00, 0.00, 1.32), (0.00, 0.00, 1.44)),

    ('neckLower',    'chestUpper',   (0.00, 0.00, 1.44), (0.00, 0.00, 1.50)),
    ('neckUpper',    'neckLower',    (0.00, 0.00, 1.50), (0.00, 0.00, 1.56)),
    ('head',         'neckUpper',    (0.00, 0.00, 1.56), (0.00, 0.00, 1.68)),
]

# Limbs are generated for both sides (x mirrored for 'r')
_G8_SYNTH_LIMB_BONES = [
    ('{s}ThighBend',    'pelvis',           (0.09, 0.00, 0.95), (0.09, 0.00, 0.72)),
    ('{s}ThighTwist',   '{s}ThighBend',     (0.09, 0.00, 0.72), (0.09, 0.00, 0.50)),
    ('{s}Shin',         '{s}ThighTwist',    (0.09, 0.00, 0.50), (0.09, -0.12, 0.12)),
    ('{s}Foot',         '{s}Shin',          (0.09, -0.12, 0.12), (0.09, -0.24, 0.04)),

    # Matches Diffeomorphic G8 layout: the forearm BEND bone ends mid-forearm,
    # the forearm TWIST continues to the wrist, and the hand attaches at the
    # twist's tail. (Solvers that treat forearmBend.tail as the wrist
    # underestimate arm reach — regression covered by test_pin_maintenance.)
    ('{s}Collar',       'chestUpper',       (0.02, 0.00, 1.42), (0.13, 0.00, 1.44)),
    ('{s}ShldrBend',    '{s}Collar',        (0.15, 0.00, 1.43), (0.31, 0.00, 1.43)),
    ('{s}ShldrTwist',   '{s}ShldrBend',     (0.31, 0.00, 1.43), (0.45, 0.00, 1.43)),
    ('{s}ForearmBend',  '{s}ShldrTwist',    (0.45, 0.00, 1.43), (0.535, -0.09, 1.43)),
    ('{s}ForearmTwist', '{s}ForearmBend',   (0.535, -0.09, 1.43), (0.62, -0.18, 1.43)),
    ('{s}Hand',         '{s}ForearmTwist',  (0.62, -0.18, 1.43), (0.70, -0.22, 1.43)),
]


def build_synthetic_g8(name='SyntheticG8'):
    """Create a Genesis-8-like armature in the current scene and return it."""
    import bpy
    from mathutils import Vector

    # Remove a previous instance if present
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)

    arm_data = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, arm_data)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    bone_defs = list(_G8_SYNTH_BONES)
    for side in ('l', 'r'):
        sign = 1.0 if side == 'l' else -1.0
        for tmpl_name, tmpl_parent, head, tail in _G8_SYNTH_LIMB_BONES:
            bone_defs.append((
                tmpl_name.format(s=side),
                tmpl_parent.format(s=side) if tmpl_parent else None,
                (head[0] * sign, head[1], head[2]),
                (tail[0] * sign, tail[1], tail[2]),
            ))

    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = arm_data.edit_bones
    for bone_name, parent_name, head, tail in bone_defs:
        eb = edit_bones.new(bone_name)
        eb.head = Vector(head)
        eb.tail = Vector(tail)
        eb.use_connect = False
        if parent_name:
            eb.parent = edit_bones[parent_name]
    bpy.ops.object.mode_set(mode='POSE')

    for pb in obj.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    bpy.context.view_layer.update()
    return obj


@pytest.fixture
def synthetic_g8(blender_session):
    """Fresh synthetic Genesis-8-like armature, removed after the test."""
    import bpy
    obj = build_synthetic_g8()
    yield obj
    try:
        bpy.ops.object.mode_set(mode='OBJECT')
    except Exception:
        pass
    # Clean up pin empties created during the test
    for o in list(bpy.data.objects):
        if o.name.startswith('PIN_') and obj.name in o.name:
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.objects.remove(obj, do_unlink=True)
