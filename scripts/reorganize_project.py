"""
BlenDAZ Project Reorganization Script

Safely reorganizes the project into a clean folder structure:
- docs/ - All documentation
- scripts/ - Automation and tools
- reports/ - Generated outputs
- projects/ - Sub-projects (poseblend, posebridge)

Core addon files stay at root for Blender compatibility.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime


# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).parent

# Files to keep at root (Blender needs these)
CORE_ADDON_FILES = [
    'daz_bone_select.py',
    'genesis8_limits.py',
    'ik_templates.py',
    'panel_ui.py',
    'bone_utils.py',
    'daz_shared_utils.py',
    'rotation_cache.py',
    '__init__.py',
    '__pycache__',
    'Assets',
]

# Reorganization mapping
FILE_MOVES = {
    'docs/': [
        'README.md',
        'CLAUDE.md',
        'TODO.md',
        'INDEX.md',
        'SCRATCHPAD.md',
        'TOOL_COMPARISON.md',
        'TECHNICAL_REFERENCE.md',
        'DAZ_BONE_SELECT_OVERVIEW.md',
        'PROJECT_SETUP_GUIDE.md',
    ],
    'docs/bugs/': [
        'BUG_LOWER_AB_SNAP.md',
        'BUG_PECTORAL_ROTATION_SPACE.md',
        'BUG_TORSO_ROTATION_SNAP.md',
    ],
    'docs/fixes/': [
        'FIX_GIZMO_INTERFERENCE.md',
        'FIX_IK_STIFFNESS_TUNING.md',
        'FIX_PECTORAL_IK.md',
        'FIX_PECTORAL_ROTATION_UNDO.md',
    ],
    'docs/planning/': [
        'IK_BREAKTHROUGH.md',
        'IK_INTEGRATION_PLAN.md',
        'IMPLEMENTATION_COMPLETE.md',
        'PROPOSAL_MODULE_REFACTOR.md',
        'SOFT_PIN_IMPLEMENTATION.md',
        'UI_POLISH_DESIGN_DOCUMENT.md',
        'UI_POLISH_INTEGRATION_GUIDE.md',
        'UI_POLISH_README.md',
        'UI_POLISH_RESEARCH_SUMMARY.md',
    ],
    'docs/guides/': [
        'POWERPOSE_FIX_RIGHTCLICK.md',
        'POWERPOSE_IMPLEMENTATION_SUMMARY.md',
        'POWERPOSE_LAYOUT.txt',
        'POWERPOSE_NEW_UI.txt',
        'POWERPOSE_QUICKSTART.md',
        'POWERPOSE_README.md',
        'POWERPOSE_USER_GUIDE.txt',
    ],
    'scripts/': [
        'monitor_updates.py',
        'audit_docs.py',
        'schedule_monitor.bat',
        'schedule_docs_audit.bat',
        'reload_daz_bone_select.py',
        'test_powerpose.py',
        'validate_powerpose.py',
        'reorganize_project.py',  # This script itself
    ],
    'reports/': [
        'TECH_UPDATES.md',
        'DOCS_AUDIT_REPORT.md',
        'MONITORING_README.md',
        'DOCS_AUDIT_README.md',
        'monitor_state.json',
    ],
    'projects/': [
        'poseblend',
        'posebridge',
    ],
}


# ============================================================================
# REORGANIZATION FUNCTIONS
# ============================================================================

def create_folder_structure():
    """Create all necessary folders"""
    folders = set()
    for dest_folder in FILE_MOVES.keys():
        folders.add(PROJECT_ROOT / dest_folder)

    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
        print(f"  Created: {folder.relative_to(PROJECT_ROOT)}")


def move_file(src, dest):
    """Safely move a file or directory"""
    src_path = PROJECT_ROOT / src
    dest_path = PROJECT_ROOT / dest

    if not src_path.exists():
        return False, "Not found"

    if dest_path.exists():
        return False, "Destination exists"

    try:
        # Create parent directory if needed
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if src_path.is_dir():
            shutil.move(str(src_path), str(dest_path))
        else:
            shutil.move(str(src_path), str(dest_path))

        return True, "OK"
    except Exception as e:
        return False, str(e)


def update_script_paths():
    """Update paths in scripts that reference moved files"""

    # Update audit_docs.py
    audit_script = PROJECT_ROOT / 'scripts' / 'audit_docs.py'
    if audit_script.exists():
        content = audit_script.read_text(encoding='utf-8')

        # Update PROJECT_ROOT to go up one level
        content = content.replace(
            'PROJECT_ROOT = Path(__file__).parent',
            'PROJECT_ROOT = Path(__file__).parent.parent'
        )

        # Update DOCS_TO_AUDIT to use docs/ folder
        content = content.replace(
            "PROJECT_ROOT / doc_name",
            "PROJECT_ROOT / 'docs' / doc_name"
        )

        # Update audit report location
        content = content.replace(
            'AUDIT_REPORT = PROJECT_ROOT / "DOCS_AUDIT_REPORT.md"',
            'AUDIT_REPORT = PROJECT_ROOT / "reports" / "DOCS_AUDIT_REPORT.md"'
        )

        audit_script.write_text(content, encoding='utf-8')
        print("  Updated: scripts/audit_docs.py")

    # Update monitor_updates.py
    monitor_script = PROJECT_ROOT / 'scripts' / 'monitor_updates.py'
    if monitor_script.exists():
        content = monitor_script.read_text(encoding='utf-8')

        # Update paths to reports folder
        content = content.replace(
            'STATE_FILE = Path(__file__).parent / "monitor_state.json"',
            'STATE_FILE = Path(__file__).parent.parent / "reports" / "monitor_state.json"'
        )
        content = content.replace(
            'UPDATES_FILE = Path(__file__).parent / "TECH_UPDATES.md"',
            'UPDATES_FILE = Path(__file__).parent.parent / "reports" / "TECH_UPDATES.md"'
        )

        monitor_script.write_text(content, encoding='utf-8')
        print("  Updated: scripts/monitor_updates.py")

    # Update schedule batch files
    for bat_file in ['schedule_monitor.bat', 'schedule_docs_audit.bat']:
        bat_path = PROJECT_ROOT / 'scripts' / bat_file
        if bat_path.exists():
            content = bat_path.read_text(encoding='utf-8')

            # Update Python script path
            if 'monitor_updates.py' in content:
                content = content.replace(
                    'set PYTHON_SCRIPT=%SCRIPT_DIR%monitor_updates.py',
                    'set PYTHON_SCRIPT=%SCRIPT_DIR%..\\scripts\\monitor_updates.py'
                )
            if 'audit_docs.py' in content:
                content = content.replace(
                    'set PYTHON_SCRIPT=%SCRIPT_DIR%audit_docs.py',
                    'set PYTHON_SCRIPT=%SCRIPT_DIR%..\\scripts\\audit_docs.py'
                )

            bat_path.write_text(content, encoding='utf-8')
            print(f"  Updated: scripts/{bat_file}")


def create_backup():
    """Create a backup of current structure"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = PROJECT_ROOT / f'backup_pre_reorganize_{timestamp}.txt'

    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(f"BlenDAZ Project Structure Backup\n")
        f.write(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"\nFile listing before reorganization:\n")
        f.write("=" * 60 + "\n\n")

        for item in sorted(PROJECT_ROOT.iterdir()):
            if item.name.startswith('backup_'):
                continue
            f.write(f"{item.name}\n")

    print(f"\n  Backup created: {backup_file.name}")
    return backup_file


# ============================================================================
# MAIN REORGANIZATION
# ============================================================================

def main():
    """Run the reorganization"""
    print("=" * 60)
    print("BlenDAZ Project Reorganization")
    print("=" * 60)
    print()

    # Create backup
    print("Creating backup...")
    backup_file = create_backup()
    print()

    # Create folder structure
    print("Creating folder structure...")
    create_folder_structure()
    print()

    # Move files
    print("Moving files...")
    moved_count = 0
    skipped_count = 0
    error_count = 0

    for dest_folder, files in FILE_MOVES.items():
        for file_name in files:
            src = file_name
            dest = dest_folder + file_name

            success, msg = move_file(src, dest)

            if success:
                print(f"  [OK] {src} -> {dest}")
                moved_count += 1
            elif "Not found" in msg:
                # File doesn't exist, skip silently
                skipped_count += 1
            else:
                print(f"  [ERROR] {src}: {msg}")
                error_count += 1

    print()

    # Update script paths
    print("Updating script paths...")
    update_script_paths()
    print()

    # Summary
    print("=" * 60)
    print("Reorganization Complete!")
    print("=" * 60)
    print(f"  Files moved: {moved_count}")
    print(f"  Files skipped: {skipped_count}")
    print(f"  Errors: {error_count}")
    print()
    print(f"  Backup: {backup_file.name}")
    print()
    print("New structure:")
    print("  d:\\dev\\BlenDAZ\\")
    print("    ├── (core addon files)")
    print("    ├── docs/")
    print("    │   ├── bugs/")
    print("    │   ├── fixes/")
    print("    │   ├── planning/")
    print("    │   └── guides/")
    print("    ├── scripts/")
    print("    ├── reports/")
    print("    └── projects/")
    print()

    if error_count > 0:
        print("[WARNING] Some errors occurred. Review above output.")
    else:
        print("[OK] All files reorganized successfully!")
    print()


if __name__ == "__main__":
    main()
