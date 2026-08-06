# BlenDAZ Test Suite

## Quick Start

```bash
# Set your Blender path (Steam example):
BLENDER="D:/SteamLibrary/steamapps/common/Blender/blender.exe"

# One-time: install pytest into Blender's Python
$BLENDER --background --python-expr "import subprocess, sys; subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pytest'])"

# Run FABRIK solver tests (fast, no scene needed)
$BLENDER --background --python tests/run_tests.py -- tests/test_fabrik_regression.py -v

# Run golden pose tests (needs a DAZ character in the scene)
$BLENDER path/to/test_scene.blend --background --python tests/run_tests.py -- tests/test_golden_poses.py -v

# Run everything
$BLENDER --background --python tests/run_tests.py
```

The `run_tests.py` script runs pytest **inside** Blender's Python process (where `mathutils` and `bpy` are available). Everything after `--` is passed to pytest.

## Test Types

### Pure Math Tests (`test_fabrik_regression.py`)
- Test FABRIK solver directly with synthetic chain data
- No Blender scene or DAZ armature needed
- Fast — run these after every solver change
- Covers: segment length preservation, convergence, stiffness, split-chain, feasibility

### Golden Pose Tests (`test_golden_poses.py`)
- Integration tests requiring a DAZ Genesis 8/9 character
- Load a .blend, pose bones, run solver, measure deltas
- Uses golden rule tier thresholds (T0=0.5°, T1=5°, T2=15°)
- First run captures golden reference poses; subsequent runs compare against them
- Covers: bake+mute pop, drag release snap, euler clamp accuracy

### Legacy Tests (`test_analytical_arm.py`, `test_analytical_leg.py`, etc.)
- Pre-existing Blender-native test scripts
- Run directly: `blender --python tests/test_analytical_arm.py`
- Require a DAZ armature as active object in Pose mode

## Golden Pose Snapshots

Golden poses are stored in `tests/fixtures/golden_poses/` as JSON:
```json
{
  "format_version": 1,
  "metadata": {"description": "...", "tier_target": "T0"},
  "bone_rotations": {"lShldrBend": [1.0, 0.0, 0.0, 0.0], ...}
}
```

To regenerate: delete the JSON file and run the test — it will save a new golden reference.

## Golden Rule Tiers

| Tier | Max Rotation | Max Position | Meaning |
|------|-------------|-------------|---------|
| T0   | 0.5°        | 1mm         | Perfect — required for drag initiation/release |
| T1   | 5.0°        | 5mm         | Cosmetic — acceptable for v1 features |
| T2   | 15.0°       | 15mm        | Noticeable — requires explicit sign-off |
| T3   | >15°        | >15mm       | Disruptive — never shippable |

## Adding New Tests

1. Pure math tests go in `test_fabrik_regression.py` (or a new `test_*.py`)
2. Integration tests go in `test_golden_poses.py`
3. Use fixtures from `conftest.py` (`tiers`, `fabrik_module`, `reset_pose`, etc.)
4. State which tier the test targets in the docstring
