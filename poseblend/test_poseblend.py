"""
PoseBlend Test Script
Run in Blender's Text Editor or Script workspace.

Prerequisites:
- Genesis 8/9 character in scene (Diffeomorphic import)
- Armature selected
- In Object or Pose mode

What this does:
1. Registers PoseBlend addon
2. Runs automated checks (registration, data, pose capture, blending, export/import)
3. Sets up scene for manual testing (activates PoseBlend, creates grid with test dots)
4. Optionally starts the modal operator for interactive blending

Usage: Open in Blender Text Editor, click "Run Script"
"""

import bpy
import sys
import os
import json
import math
import traceback
from mathutils import Quaternion

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECTS_DIR = r"D:\Dev\BlenDAZ\projects"
if PROJECTS_DIR not in sys.path:
    sys.path.insert(0, PROJECTS_DIR)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"
results = []

def log(msg):
    print(f"  {msg}")

def record(name, status, detail=""):
    results.append((name, status, detail))
    symbol = {"PASS": "+", "FAIL": "!", "SKIP": "~"}[status]
    suffix = f" -- {detail}" if detail else ""
    print(f"  [{symbol}] {name}{suffix}")

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def summary():
    section("SUMMARY")
    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    skipped = sum(1 for _, s, _ in results if s == SKIP)
    total = len(results)
    print(f"  {passed}/{total} passed, {failed} failed, {skipped} skipped\n")
    if failed:
        print("  FAILURES:")
        for name, status, detail in results:
            if status == FAIL:
                print(f"    - {name}: {detail}")
        print()

# ---------------------------------------------------------------------------
# Find armature
# ---------------------------------------------------------------------------
def find_armature():
    """Find a usable armature in the scene."""
    # Prefer active selection
    obj = bpy.context.active_object
    if obj and obj.type == 'ARMATURE':
        return obj
    # Otherwise search scene
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            return obj
    return None

# ===========================================================================
# TEST 1 — Registration
# ===========================================================================
def test_registration():
    section("1. REGISTRATION")

    # Unregister if already loaded
    if 'poseblend' in sys.modules:
        try:
            import poseblend
            poseblend.unregister()
            log("Unregistered existing poseblend")
        except Exception:
            pass

        # Purge cached modules so we get a clean import
        to_remove = [k for k in sys.modules if k.startswith('poseblend')]
        for k in to_remove:
            del sys.modules[k]

    # Fresh import and register
    try:
        import poseblend
        poseblend.register()
        record("Module import & register", PASS)
    except Exception as e:
        record("Module import & register", FAIL, str(e))
        traceback.print_exc()
        return False

    # Check scene property
    try:
        settings = bpy.context.scene.poseblend_settings
        record("scene.poseblend_settings exists", PASS)
    except AttributeError:
        record("scene.poseblend_settings exists", FAIL, "Property not found on scene")
        return False

    # Check operators registered
    ops_to_check = [
        ("poseblend.activate", "Activate operator"),
        ("poseblend.deactivate", "Deactivate operator"),
        ("poseblend.interact", "Modal interact operator"),
        ("poseblend.add_grid", "Add grid operator"),
        ("poseblend.add_dot", "Add dot operator"),
        ("poseblend.export_grid", "Export operator"),
        ("poseblend.import_grid", "Import operator"),
    ]
    for op_id, label in ops_to_check:
        parts = op_id.split(".")
        has_op = hasattr(getattr(bpy.ops, parts[0], None), parts[1])
        record(label, PASS if has_op else FAIL, op_id)

    return True

# ===========================================================================
# TEST 2 — Data Layer
# ===========================================================================
def test_data_layer():
    section("2. DATA LAYER")

    settings = bpy.context.scene.poseblend_settings

    # Create grid
    grid = settings.add_grid("Test Grid")
    record("Create grid", PASS if grid else FAIL)
    record("Grid name", PASS if grid.name == "Test Grid" else FAIL, grid.name)

    # Grid defaults
    record("Grid divisions default", PASS if tuple(grid.grid_divisions) == (8, 8) else FAIL,
           str(tuple(grid.grid_divisions)))
    record("Grid bone_mask_mode default", PASS if grid.bone_mask_mode == 'ALL' else FAIL,
           grid.bone_mask_mode)

    # Add dot with fake rotation data
    test_rotations = {
        "head": [1.0, 0.0, 0.0, 0.0],
        "neck": [0.9239, 0.3827, 0.0, 0.0],  # ~45 deg X
    }
    dot = grid.add_dot(
        name="Test Dot A",
        position=(0.25, 0.75),
        rotations_dict=test_rotations,
        mask_mode='ALL',
        mask_preset='HEAD'
    )
    record("Add dot", PASS if dot else FAIL)
    record("Dot name", PASS if dot.name == "Test Dot A" else FAIL, dot.name)
    record("Dot position", PASS if abs(dot.position[0] - 0.25) < 0.001 else FAIL,
           str(tuple(dot.position)))
    record("Dot has ID", PASS if dot.id else FAIL, dot.id)
    record("Dot has created_time", PASS if dot.created_time else FAIL)

    # Round-trip rotation data
    loaded = dot.get_rotations_dict()
    head_q = loaded.get("head")
    record("Rotation round-trip (head)", PASS if head_q == [1.0, 0.0, 0.0, 0.0] else FAIL,
           str(head_q))
    neck_q = loaded.get("neck")
    match = neck_q and all(abs(a - b) < 0.001 for a, b in zip(neck_q, [0.9239, 0.3827, 0.0, 0.0]))
    record("Rotation round-trip (neck)", PASS if match else FAIL, str(neck_q))

    # Cleanup test grid
    settings.remove_grid(settings.active_grid_index)
    return True

# ===========================================================================
# TEST 3 — Pose Capture
# ===========================================================================
def test_pose_capture(armature):
    section("3. POSE CAPTURE")

    from poseblend.poses import capture_pose, apply_pose

    # Capture current pose
    rotations = capture_pose(armature)
    record("capture_pose returns data", PASS if rotations else FAIL,
           f"{len(rotations)} bones")

    # Check quaternion format: every value should be [w, x, y, z] with 4 floats
    format_ok = True
    bad_bone = ""
    for bone_name, quat in rotations.items():
        if not (isinstance(quat, list) and len(quat) == 4):
            format_ok = False
            bad_bone = bone_name
            break
    record("Quaternion format [w,x,y,z]", PASS if format_ok else FAIL, bad_bone)

    # Check that known Genesis 8 bones are present
    g8_check_bones = ['hip', 'pelvis', 'spine', 'abdomenUpper', 'chestUpper',
                      'lShldrBend', 'rShldrBend', 'head']
    found = [b for b in g8_check_bones if b in rotations]
    missing = [b for b in g8_check_bones if b not in rotations]
    record(f"Genesis 8 bones found ({len(found)}/{len(g8_check_bones)})",
           PASS if len(found) >= 4 else FAIL,
           f"missing: {missing}" if missing else "")

    # Apply pose round-trip: apply captured pose back, re-capture, compare
    apply_pose(armature, rotations)
    rotations2 = capture_pose(armature)

    # Compare a few bones
    bones_to_compare = [b for b in ['head', 'hip', 'lShldrBend'] if b in rotations and b in rotations2]
    round_trip_ok = True
    for b in bones_to_compare:
        q1 = rotations[b]
        q2 = rotations2[b]
        if any(abs(a - c) > 0.001 for a, c in zip(q1, q2)):
            round_trip_ok = False
            break
    record("apply_pose -> capture_pose round-trip",
           PASS if round_trip_ok else FAIL,
           f"compared {len(bones_to_compare)} bones")

    return True

# ===========================================================================
# TEST 4 — Blending Math
# ===========================================================================
def test_blending(armature):
    section("4. BLENDING MATH")

    from poseblend.blending import calculate_blend_weights
    from poseblend.poses import capture_pose

    settings = bpy.context.scene.poseblend_settings
    grid = settings.add_grid("Blend Test")

    # Capture pose A (current)
    rotA = capture_pose(armature)
    dot_a = grid.add_dot("Pose A", position=(0.0, 0.5), rotations_dict=rotA)

    # Modify a bone slightly to create pose B
    rotB = dict(rotA)
    if 'head' in rotB:
        rotB['head'] = [0.9659, 0.2588, 0.0, 0.0]  # ~30 deg X
    dot_b = grid.add_dot("Pose B", position=(1.0, 0.5), rotations_dict=rotB)

    # Test: cursor at midpoint should give ~50/50
    weights = calculate_blend_weights((0.5, 0.5), grid.dots, 'QUADRATIC', 0.0)
    record("Blend weights returned", PASS if len(weights) == 2 else FAIL,
           f"{len(weights)} weights")
    if len(weights) == 2:
        w0 = weights[0][1]
        w1 = weights[1][1]
        record("Midpoint ~50/50 split",
               PASS if abs(w0 - 0.5) < 0.01 and abs(w1 - 0.5) < 0.01 else FAIL,
               f"{w0:.3f} / {w1:.3f}")

    # Test: cursor directly on dot A should give 100% A
    weights_on_a = calculate_blend_weights((0.0, 0.5), grid.dots, 'QUADRATIC', 0.0)
    if weights_on_a:
        top = weights_on_a[0]
        is_a = (tuple(top[0].position)[:1] == (0.0,))  # dot A is at x=0
        record("Cursor on dot A = 100%",
               PASS if len(weights_on_a) == 1 and top[1] >= 0.99 else FAIL,
               f"weight={top[1]:.3f}")
    else:
        record("Cursor on dot A = 100%", FAIL, "no weights returned")

    # Test: quaternion blending
    from poseblend.poses import blend_quaternions
    q1 = Quaternion((1.0, 0.0, 0.0, 0.0))  # identity
    q2 = Quaternion((0.9659, 0.2588, 0.0, 0.0))  # ~30 deg X
    blended = blend_quaternions([(q1, 0.5), (q2, 0.5)])
    # Midpoint should be ~15 deg X
    expected_w = math.cos(math.radians(15) / 2)
    record("SLERP midpoint",
           PASS if abs(blended.w - expected_w) < 0.01 else FAIL,
           f"w={blended.w:.4f} expected~{expected_w:.4f}")

    # Cleanup
    settings.remove_grid(settings.active_grid_index)
    return True

# ===========================================================================
# TEST 5 — Export / Import Round-Trip
# ===========================================================================
def test_export_import(armature):
    section("5. EXPORT / IMPORT")

    from poseblend.import_export import export_grid_to_dict, import_grid_from_dict
    from poseblend.poses import capture_pose

    settings = bpy.context.scene.poseblend_settings
    grid = settings.add_grid("Export Test")
    grid.bone_mask_mode = 'PRESET'
    grid.bone_mask_preset = 'UPPER_BODY'
    grid.grid_divisions = (6, 6)

    rotA = capture_pose(armature)
    grid.add_dot("Dot 1", position=(0.2, 0.3), rotations_dict=rotA)
    grid.add_dot("Dot 2", position=(0.7, 0.8), rotations_dict=rotA, mask_mode='PRESET', mask_preset='HEAD')

    # Export to dict
    exported = export_grid_to_dict(grid)
    record("Export to dict", PASS if exported else FAIL)
    record("Export has version", PASS if exported.get("version") == "1.0" else FAIL)
    record("Export dot count", PASS if len(exported.get("dots", [])) == 2 else FAIL,
           str(len(exported.get("dots", []))))

    # Verify JSON serializable
    try:
        json_str = json.dumps(exported)
        record("JSON serializable", PASS, f"{len(json_str)} chars")
    except Exception as e:
        record("JSON serializable", FAIL, str(e))

    # Import back
    settings.remove_grid(settings.active_grid_index)
    imported_grid = import_grid_from_dict(exported, settings)
    record("Import from dict", PASS if imported_grid else FAIL)

    if imported_grid:
        record("Imported name matches",
               PASS if imported_grid.name == "Export Test" else FAIL,
               imported_grid.name)
        record("Imported dot count",
               PASS if len(imported_grid.dots) == 2 else FAIL,
               str(len(imported_grid.dots)))
        record("Imported divisions",
               PASS if tuple(imported_grid.grid_divisions) == (6, 6) else FAIL,
               str(tuple(imported_grid.grid_divisions)))
        record("Imported mask mode",
               PASS if imported_grid.bone_mask_mode == 'PRESET' else FAIL,
               imported_grid.bone_mask_mode)

        # Check dot rotation data survived
        if len(imported_grid.dots) >= 1:
            dot1_rots = imported_grid.dots[0].get_rotations_dict()
            record("Imported dot has rotation data",
                   PASS if len(dot1_rots) > 0 else FAIL,
                   f"{len(dot1_rots)} bones")

    # Cleanup
    settings.remove_grid(settings.active_grid_index)
    return True

# ===========================================================================
# SETUP — Prepare scene for manual testing
# ===========================================================================
def setup_manual_test(armature):
    section("MANUAL TEST SETUP")

    from poseblend.poses import capture_pose

    settings = bpy.context.scene.poseblend_settings

    # Activate PoseBlend
    settings.is_active = True
    settings.active_armature_name = armature.name
    log(f"Armature: {armature.name}")

    # Register draw handler
    from poseblend.drawing import PoseBlendDrawHandler
    PoseBlendDrawHandler.register_handler()
    log("Draw handler registered")

    # Create test grid with a couple of dots
    grid = settings.add_grid("Test Grid")
    log(f"Created grid: {grid.name}")

    # Capture current rest/default pose as dot 1
    rotA = capture_pose(armature)
    grid.add_dot("Rest Pose", position=(0.25, 0.5), rotations_dict=rotA)
    log("Dot 1: 'Rest Pose' at (0.25, 0.5)")

    # Rotate head a bit to create a different pose for dot 2
    head_bone = armature.pose.bones.get('head')
    original_head = None
    if head_bone:
        if head_bone.rotation_mode == 'QUATERNION':
            original_head = head_bone.rotation_quaternion.copy()
            head_bone.rotation_quaternion = Quaternion((0.9659, 0.2588, 0.0, 0.0))
        else:
            original_head = head_bone.rotation_euler.copy()
            q = Quaternion((0.9659, 0.2588, 0.0, 0.0))
            head_bone.rotation_euler = q.to_euler(head_bone.rotation_mode)
        bpy.context.view_layer.update()
        log("Rotated head ~30 deg for second pose")

    rotB = capture_pose(armature)
    grid.add_dot("Head Tilt", position=(0.75, 0.5), rotations_dict=rotB)
    log("Dot 2: 'Head Tilt' at (0.75, 0.5)")

    # Restore head
    if head_bone and original_head is not None:
        if head_bone.rotation_mode == 'QUATERNION':
            head_bone.rotation_quaternion = original_head
        else:
            head_bone.rotation_euler = original_head
        bpy.context.view_layer.update()

    # Force redraw
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()

    log("Scene ready for manual testing")
    return True

# ===========================================================================
# MAIN
# ===========================================================================
def main():
    print("\n" + "=" * 60)
    print("  POSEBLEND TEST SCRIPT")
    print("=" * 60)

    # Find armature
    armature = find_armature()
    if not armature:
        print("\n  ERROR: No armature found in scene.")
        print("  Import a Genesis 8/9 character first.\n")
        return

    # Select it and enter pose mode
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    if bpy.context.mode != 'POSE':
        bpy.ops.object.mode_set(mode='POSE')
    print(f"\n  Armature: {armature.name}")
    print(f"  Bones: {len(armature.pose.bones)}")

    # Run tests
    if not test_registration():
        summary()
        return

    test_data_layer()
    test_pose_capture(armature)
    test_blending(armature)
    test_export_import(armature)

    # Summary
    summary()

    # If no failures, set up for manual testing
    failed = sum(1 for _, s, _ in results if s == FAIL)
    if failed == 0:
        setup_manual_test(armature)
        print("=" * 60)
        print("  READY FOR MANUAL TESTING")
        print("=" * 60)
        print("  Grid overlay should be visible in the 3D viewport.")
        print("  Modal is active — non-blocking (pass-through outside grid).")
        print("  Two test dots placed: 'Rest Pose' and 'Head Tilt'")
        print()
        print("  Toggle: N-panel > DAZ > 'PoseBlend' button")
        print()
        print("  Controls (over grid):")
        print("    Click/drag on grid   = blend preview")
        print("    Shift+click empty    = capture new dot from current pose")
        print("    Shift+drag dot       = move dot")
        print("    Click on dot         = apply that pose 100%")
        print("    X over dot           = delete dot")
        print("    Mousewheel           = zoom grid")
        print("    ESC                  = exit PoseBlend (keeps pose)")
        print()
        print("  Outside grid: normal Blender controls (orbit, select, etc.)")
        print("=" * 60 + "\n")
    else:
        print("\n  Fix failures above before manual testing.\n")


if __name__ == "__main__":
    main()
