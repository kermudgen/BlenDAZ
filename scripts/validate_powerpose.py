"""
PowerPose Validation Script
Run this to validate the PowerPose implementation
"""

import sys
import os

def validate_syntax():
    """Validate Python syntax"""
    print("="*60)
    print("VALIDATION: Python Syntax")
    print("="*60)

    file_path = os.path.join(os.path.dirname(__file__), "daz_bone_select.py")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        compile(code, file_path, 'exec')
        print("[PASS] Syntax valid")
        return True
    except SyntaxError as e:
        print(f"[FAIL] Syntax error: {e}")
        return False


def validate_structure():
    """Validate code structure and required components"""
    print("\n" + "="*60)
    print("VALIDATION: Code Structure")
    print("="*60)

    file_path = os.path.join(os.path.dirname(__file__), "daz_bone_select.py")

    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()

    required_components = [
        ("get_bend_axis", "Rotation system - bend axis function"),
        ("get_twist_axis", "Rotation system - twist axis function"),
        ("apply_rotation_from_delta", "Rotation system - apply rotation function"),
        ("refresh_3d_viewports", "Rotation system - viewport refresh function"),
        ("get_genesis8_control_points", "Control point template function"),
        ("POSE_OT_daz_powerpose_control", "PowerPose modal operator class"),
        ("VIEW3D_PT_daz_powerpose_main", "PowerPose main panel class"),
    ]

    all_found = True
    for component, description in required_components:
        if component in code:
            print(f"[PASS] {description}")
        else:
            print(f"[FAIL] MISSING: {description}")
            all_found = False

    return all_found


def validate_registration():
    """Validate registration code"""
    print("\n" + "="*60)
    print("VALIDATION: Registration")
    print("="*60)

    file_path = os.path.join(os.path.dirname(__file__), "daz_bone_select.py")

    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()

    checks = [
        ("bpy.utils.register_class(POSE_OT_daz_powerpose_control)", "Operator registered"),
        ("bpy.utils.register_class(VIEW3D_PT_daz_powerpose_main)", "Panel registered"),
        ("bpy.utils.unregister_class(VIEW3D_PT_daz_powerpose_main)", "Panel unregistered"),
        ("bpy.utils.unregister_class(POSE_OT_daz_powerpose_control)", "Operator unregistered"),
    ]

    all_found = True
    for check_str, description in checks:
        if check_str in code:
            print(f"[PASS] {description}")
        else:
            print(f"[FAIL] MISSING: {description}")
            all_found = False

    return all_found


def validate_bl_info():
    """Validate bl_info metadata"""
    print("\n" + "="*60)
    print("VALIDATION: Addon Metadata")
    print("="*60)

    file_path = os.path.join(os.path.dirname(__file__), "daz_bone_select.py")

    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()

    checks = [
        ("version", "(1, 2, 0)", "Version 1.2.0"),
        ("name", "PowerPose", "Name includes PowerPose"),
        ("description", "PowerPose", "Description includes PowerPose"),
    ]

    all_found = True
    for key, expected, description in checks:
        if expected in code:
            print(f"[PASS] {description}")
        else:
            print(f"[FAIL] MISSING: {description}")
            all_found = False

    return all_found


def validate_documentation():
    """Validate documentation files"""
    print("\n" + "="*60)
    print("VALIDATION: Documentation")
    print("="*60)

    base_dir = os.path.dirname(__file__)

    doc_files = [
        ("README.md", "Main README updated"),
        ("POWERPOSE_README.md", "PowerPose full documentation"),
        ("POWERPOSE_QUICKSTART.md", "PowerPose quick start guide"),
        ("POWERPOSE_LAYOUT.txt", "PowerPose layout diagram"),
        ("POWERPOSE_IMPLEMENTATION_SUMMARY.md", "Implementation summary"),
        ("TOOL_COMPARISON.md", "Tool comparison guide"),
        ("test_powerpose.py", "Test script"),
    ]

    all_found = True
    for filename, description in doc_files:
        file_path = os.path.join(base_dir, filename)
        if os.path.exists(file_path):
            print(f"[PASS] {description}: {filename}")
        else:
            print(f"[FAIL] MISSING: {description}: {filename}")
            all_found = False

    return all_found


def validate_control_points():
    """Validate control point template"""
    print("\n" + "="*60)
    print("VALIDATION: Control Point Template")
    print("="*60)

    file_path = os.path.join(os.path.dirname(__file__), "daz_bone_select.py")

    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()

    # Check for expected bone names
    expected_bones = [
        'head', 'lHand', 'rHand', 'lForeArm', 'rForeArm',
        'lShldr', 'rShldr', 'chest', 'abdomen', 'pelvis',
        'lFoot', 'rFoot', 'lShin', 'rShin', 'lThigh', 'rThigh'
    ]

    all_found = True
    for bone in expected_bones:
        if f"'{bone}'" in code or f'"{bone}"' in code:
            print(f"[PASS] Control point: {bone}")
        else:
            print(f"[FAIL] MISSING: {bone}")
            all_found = False

    return all_found


def main():
    """Run all validations"""
    print("\n")
    print("+" + "="*58 + "+")
    print("|" + " "*14 + "POWERPOSE VALIDATION" + " "*24 + "|")
    print("+" + "="*58 + "+")
    print()

    results = []

    results.append(("Syntax", validate_syntax()))
    results.append(("Structure", validate_structure()))
    results.append(("Registration", validate_registration()))
    results.append(("Metadata", validate_bl_info()))
    results.append(("Documentation", validate_documentation()))
    results.append(("Control Points", validate_control_points()))

    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)

    all_passed = True
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("="*60)

    if all_passed:
        print("\n[SUCCESS] ALL VALIDATIONS PASSED")
        print("\nPhase 1 implementation is complete and ready for testing!")
        print("\nNext steps:")
        print("1. Install addon in Blender")
        print("2. Open N-panel > DAZ tab")
        print("3. Select armature in Pose Mode")
        print("4. Test control point buttons")
        print("5. Test left-click (bend) and right-click (twist)")
        print("6. Verify real-time viewport updates")
        print("7. Verify keyframing on release")
        print("8. Verify ESC cancel")
        print("9. Verify undo (Ctrl+Z)")
        return 0
    else:
        print("\n[FAIL] SOME VALIDATIONS FAILED")
        print("\nPlease review the errors above and fix before testing.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
