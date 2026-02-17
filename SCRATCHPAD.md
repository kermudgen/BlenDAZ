# BlenDAZ - Development Scratchpad

## Purpose

This file tracks ongoing development work, experiments, bugs, and feature progress. It's a living document that captures what we're working on, what we've tried, and what we've learned.

**Note**: When this file reaches ~300-500 lines or ~50-75KB, archive it to `scratchpad_archive/SCRATCHPAD_YYYY-MM.md` and start fresh.

## Archive History

*No archived scratchpads yet*

**Note**: [posebridge/scratchpad.md](posebridge/scratchpad.md) contains 46KB of PoseBridge development history and should be archived soon.

---

## Current Session: 2026-02-16

### Active Work
- Setting up four-file documentation system (CLAUDE.md, INDEX.md, SCRATCHPAD.md, TODO.md)
- Establishing project organization for better AI assistant collaboration

### Today's Goals
- [x] Update CLAUDE.md with documentation system guidelines
- [x] Create INDEX.md with complete file reference
- [x] Create SCRATCHPAD.md (this file)
- [ ] Create TODO.md with current tasks and roadmap

### Notes & Observations
- Found that [daz_bone_select.py](daz_bone_select.py) is 267KB - unusually large and may benefit from refactoring
- [posebridge/scratchpad.md](posebridge/scratchpad.md) at 46KB is approaching archive threshold (50-75KB)
- Project has excellent documentation of bugs, fixes, and design decisions
- Clear separation between PoseBridge (visual posing) and PoseBlend (pose blending) modules

---

## Feature Development Log

### Documentation System Setup - 2026-02-16
**Status**: 🟡 In Progress

**Goal**: Establish four-file documentation system to improve project organization and AI assistant effectiveness

**Approach**:
1. Update CLAUDE.md with references to INDEX.md, SCRATCHPAD.md, TODO.md
2. Create comprehensive INDEX.md cataloging all files
3. Create SCRATCHPAD.md for development journal
4. Create TODO.md for task tracking

**What Works**:
- ✅ CLAUDE.md already had good project context and philosophy
- ✅ PROJECT_SETUP_GUIDE.md provides excellent template
- ✅ INDEX.md created with comprehensive file catalog
- ✅ Clear categorization of files by function

**Decisions Made**:
- Organized INDEX.md by functional areas (Core Tools, PoseBridge, PoseBlend) rather than file type
- Included "Quick Lookup" section for common questions
- Added file size statistics and noted that daz_bone_select.py may need refactoring
- Added cross-references between documentation files

**Next Steps**:
- [ ] Create TODO.md to track current work and backlog
- [ ] Consider archiving posebridge/scratchpad.md
- [ ] Consider refactoring daz_bone_select.py (267KB is very large)

**Related Files**:
- [CLAUDE.md](CLAUDE.md) - Updated with documentation system section
- [INDEX.md](INDEX.md) - New comprehensive file reference
- [PROJECT_SETUP_GUIDE.md](PROJECT_SETUP_GUIDE.md) - Template used for setup

---

## Bug Tracker

*No active bugs being tracked in this session*

---

## Technical Observations

### Project Structure
The BlenDAZ project has a clean separation of concerns:
- **Core utilities** ([daz_shared_utils.py](daz_shared_utils.py)) provide shared functionality
- **PoseBridge** focuses on visual, direct-manipulation posing with fixed control points
- **PoseBlend** focuses on pose blending and grid-based pose selection
- Both modules share similar architectures (core.py, drawing.py, interaction.py, panel_ui.py)

### Documentation Quality
- Extensive bug documentation with detailed explanations (BUG_*.md, FIX_*.md)
- PowerPose feature well-documented across multiple files
- Design decisions captured in DESIGN.md and IMPLEMENTATION.md files
- Good separation between user guides and technical documentation

### Development Workflow
- Reload scripts ([reload_daz_bone_select.py](reload_daz_bone_select.py)) for hot-reloading during development
- Testing checklists ([TESTING_POSEBRIDGE.md](posebridge/TESTING_POSEBRIDGE.md)) for structured testing
- Quickstart scripts for rapid testing

---

## Ideas & Future Considerations

### Module Refactoring
**Description**: Split daz_bone_select.py (267KB) into smaller, more maintainable modules
**Why**: Easier to navigate, test, and maintain; follows single responsibility principle
**Challenges**: Need to identify logical boundaries, ensure no circular dependencies

### Scratchpad Archiving Process
**Description**: Establish regular archiving schedule for scratchpad files
**Why**: Keep scratchpads manageable and focused on current work
**Next Action**: Archive posebridge/scratchpad.md which is at 46KB

### Documentation Templates
**Description**: Create templates for new modules based on posebridge/poseblend structure
**Why**: Maintain consistency across modules, speed up new module creation
**Includes**: Standard files like __init__.py, core.py, drawing.py, interaction.py, panel_ui.py

---

## Quick Reference

### Useful Commands

```bash
# List all Python files
find . -name "*.py" -type f

# List all documentation files
find . -name "*.md" -type f

# Check file sizes
ls -lh *.py

# Create scratchpad archive directory
mkdir -p scratchpad_archive
```

### Important Patterns

**Blender Addon Structure**:
- `__init__.py` - Registration and module initialization
- `core.py` - PropertyGroups and data structures
- `drawing.py` - GPU rendering with draw handlers
- `interaction.py` - Modal operators for user interaction
- `panel_ui.py` - UI panels and controls

**Modal Operator Pattern**:
```python
def modal(self, context, event):
    if event.type == 'MOUSEMOVE':
        # Handle mouse movement
        return {'RUNNING_MODAL'}
    elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
        # Handle click
        return {'FINISHED'}
    elif event.type in {'RIGHTMOUSE', 'ESC'}:
        # Cancel
        return {'CANCELLED'}
    return {'PASS_THROUGH'}
```

**GPU Draw Handler Registration**:
```python
handler = bpy.types.SpaceView3D.draw_handler_add(
    draw_callback,
    (),
    'WINDOW',
    'POST_PIXEL'
)
```

---

## Archive (Completed Work)

### ✅ Documentation System Setup - 2026-02-16
**Summary**: Established four-file documentation system with CLAUDE.md, INDEX.md, SCRATCHPAD.md, TODO.md
**Lessons Learned**:
- Comprehensive INDEX.md requires understanding entire project structure
- Cross-references between docs improve discoverability
- File size statistics help identify potential maintenance issues
