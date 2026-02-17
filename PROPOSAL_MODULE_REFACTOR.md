# Proposal: Refactor Script into Modules

**Date**: 2026-02-12
**Status**: Proposed (awaiting decision)
**Reason**: Reduce context window usage, improve maintainability, clearer organization

---

## Problem Statement

The current `daz_bone_select.py` script is ~4700 lines and growing. This causes:
- High context/token usage when making changes
- Difficult to navigate and find specific functionality
- All code must be loaded even when working on small sections
- Harder to test individual components

---

## Proposed Module Structure

```
blendaz/
├── __init__.py              # Addon registration, imports everything (~100 lines)
├── config.py                # Constants, DEBUG flags, bl_info (~50 lines)
├── templates.py             # IK rig templates + lookup functions (~200 lines)
├── ik_chain.py              # create_ik_chain(), dissolve_ik_chain() (~600 lines)
├── operators.py             # DAZ_OT_bone_select_pin modal operator (~1200 lines)
├── ui.py                    # PowerPose panel, UI classes (~200 lines)
├── utils.py                 # Helper functions (raycast, bone detection) (~400 lines)
└── pin_system.py            # Pin/unpin functions, constraints (~300 lines)
```

### Module Breakdown

**`__init__.py`** - Entry point
```python
import config
import templates
import ik_chain
import operators
import ui
import utils
import pin_system

def register():
    operators.register()
    ui.register()

def unregister():
    operators.unregister()
    ui.unregister()
```

**`config.py`** - Global settings
- `DEBUG_PRESERVE_IK_CHAIN`
- `bl_info` dict
- Global constants

**`templates.py`** - IK rig templates
- `IK_RIG_TEMPLATES` dict (hand, forearm, foot, shin)
- `get_ik_template(bone_name)`
- `calculate_pole_position(...)`

**`ik_chain.py`** - IK chain management
- `create_ik_chain()`
- `dissolve_ik_chain()`
- `get_smart_chain_length()`
- `calculate_chain_length_skipping_twists()`

**`operators.py`** - Main interaction
- `DAZ_OT_bone_select_pin` class
- Modal loop, event handling
- `start_ik_drag()`, `update_ik_drag()`, `end_ik_drag()`
- `update_rotation()`, `end_rotation()`
- Undo system

**`utils.py`** - Utility functions
- `find_base_body_mesh()`
- `raycast_specific_mesh()`
- `is_twist_bone()`, `is_pectoral()`
- `get_bone_world_matrix()`
- Bone detection helpers

**`pin_system.py`** - Pin functionality
- `pin_bone_translation()`, `pin_bone_rotation()`, `unpin_bone()`
- `is_bone_pinned_translation()`, `is_bone_pinned_rotation()`
- `add_translation_pin_constraint()`, `add_rotation_pin_constraint()`
- `has_pinned_children()`
- `create_pin_helper_empty()`, `remove_pin_helper_empty()`

**`ui.py`** - User interface
- PowerPose panel
- Pin button operators
- UI layout

---

## Testing Workflow Options

### Option 1: Simple Imports (No Workflow Change)

**Setup:** All files in `d:\dev\blendaz\` folder

**`__init__.py` structure:**
```python
import templates
import ik_chain
import operators
# ... etc (simple imports, not relative)
```

**Your workflow:**
1. Edit files in `d:\dev\blendaz\`
2. In Blender: Scripting tab → open `__init__.py` → Run Script
3. Test immediately

**Pros:**
- ✅ Zero workflow change
- ✅ Same as current single-file approach
- ✅ No setup required

**Cons:**
- ❌ Must run full addon each time (loads all modules)
- ❌ Can't use relative imports (less "proper")

---

### Option 2: Development Addon Install (Cleanest)

**One-time setup:**
1. Find Blender's addons folder:
   - Windows: `%APPDATA%\Blender Foundation\Blender\4.x\scripts\addons\`
   - Blender menu: Edit → Preferences → File Paths → Scripts
2. Create junction/symlink to your dev folder:
   ```cmd
   mklink /J "C:\Users\YourName\AppData\Roaming\Blender Foundation\Blender\4.x\scripts\addons\blendaz" "d:\dev\blendaz"
   ```
3. In Blender: Edit → Preferences → Add-ons → Enable "DAZ Bone Select & Pin"

**`__init__.py` structure:**
```python
from . import templates
from . import ik_chain
from . import operators
# ... etc (relative imports)
```

**Your workflow:**
1. Edit files in `d:\dev\blendaz\` (your normal dev location)
2. In Blender: `F3` → type "Reload Scripts" → Enter
3. Test immediately

**Pros:**
- ✅ Clean, proper addon workflow
- ✅ Uses relative imports (more maintainable)
- ✅ Addon stays enabled across sessions
- ✅ Just "Reload Scripts" to test changes
- ✅ Edit files in your dev folder, changes reflect immediately

**Cons:**
- ❌ One-time setup (5 minutes, but only needed once)
- ❌ Need to understand addon installation

---

### Option 3: Single File with Clear Sections (No Refactor)

Keep everything in one file but organize with clear section markers:

```python
# ============================================================================
# SECTION 1: IK TEMPLATES (Lines 1-500)
# ============================================================================
IK_RIG_TEMPLATES = {...}
def get_ik_template(...):
    ...

# ============================================================================
# SECTION 2: UTILITY FUNCTIONS (Lines 501-1000)
# ============================================================================
def find_base_body_mesh(...):
    ...

# ============================================================================
# SECTION 3: IK CHAIN CREATION (Lines 1001-1600)
# ============================================================================
def create_ik_chain(...):
    ...

# ... etc
```

**When working on templates, I only read lines 1-500 instead of entire file**

**Pros:**
- ✅ Zero workflow change
- ✅ Still saves context/tokens (partial file reads)
- ✅ Clear organization with section markers
- ✅ No import complexity

**Cons:**
- ❌ Still one large file
- ❌ Can't reuse modules independently
- ❌ Less clean separation of concerns

---

## Recommended Approach

**Phase 1: Start with Option 1 (Simple Imports)**
- No workflow disruption
- Test that multi-file approach works
- Same "just run the script" behavior

**Phase 2: Migrate to Option 2 (Symlink Install)** when comfortable
- Set up symlink (5 minutes, one time)
- Switch to relative imports
- Cleaner long-term workflow

**Alternative: Use Option 3** if you prefer simplicity over modularity
- Keep single file
- Add clear section markers
- I only load relevant sections when working

---

## Benefits of Refactoring

1. **Context/Token Savings**
   - Working on templates? Only load `templates.py` (200 lines vs 4700)
   - Working on IK chains? Only load `ik_chain.py` (600 lines)

2. **Maintainability**
   - Clear separation of concerns
   - Easier to find specific functionality
   - Less scrolling through giant file

3. **Testability**
   - Could test `templates.py` independently
   - Could unit test `calculate_pole_position()`
   - Easier to verify changes don't break unrelated features

4. **Reusability**
   - `templates.py` could be used in other addons
   - `utils.py` could be shared across projects

5. **Git/Version Control**
   - Changes isolated to relevant files
   - Clearer diffs (changed `ik_chain.py`, not "entire script")
   - Easier to review pull requests

---

## Risks / Considerations

1. **Import Complexity**
   - Need to ensure imports work correctly
   - Circular import issues (if any)

2. **Debugging**
   - Error stack traces show multiple files (could be clearer or more confusing)

3. **Distribution**
   - If sharing addon, need to zip entire folder (not just one file)
   - Users install folder, not single .py file

4. **Learning Curve**
   - Need to understand which file has which functionality
   - More files to navigate

---

## Effort Estimate

**Option 1 or 2 (Full Refactor):** 1-2 hours
- Split code into modules
- Set up imports
- Test all functionality still works
- Update documentation

**Option 3 (Section Markers):** 15 minutes
- Add section comments
- Test that nothing broke

---

## Decision Points

Before proceeding, answer:
1. ✅ **Do we want modularity?** (Yes = Option 1/2, No = Option 3)
2. ✅ **Are you comfortable with multi-file addons?** (Yes = Option 2, No = Option 1)
3. ✅ **Should we test the template system first?** (Ensure it works before big refactor)

---

## Next Steps

**If approved:**
1. Decide on Option 1, 2, or 3
2. Create module structure
3. Move code to appropriate modules
4. Test all functionality (drag, pin, rotate, undo)
5. Update `DAZ_BONE_SELECT_OVERVIEW.md` with new structure

**If deferred:**
- Continue with current single-file approach
- Revisit when script grows larger or context becomes an issue

---

**Status**: Awaiting user decision after discussing other ideas
