# BlenDAZ - Development Scratchpad

## Purpose

This file tracks ongoing development work, experiments, bugs, and feature progress. It's a living document that captures what we're working on, what we've tried, and what we've learned.

**Note**: When this file reaches ~300-500 lines or ~50-75KB, archive it to `scratchpad_archive/SCRATCHPAD_YYYY-MM.md` and start fresh.

## Archive History

*No archived scratchpads yet*

**Note**: [posebridge/scratchpad.md](posebridge/scratchpad.md) contains 46KB of PoseBridge development history and should be archived soon.

---

## Current Session: 2026-02-17

### Active Work
- Hand panel implementation - COMMITTED TO MASTER (d068918)
- Icon system for DAZ PowerPose-style view switching - IN PROGRESS (pending icon designs)
- **IK Chain Architecture Refactoring** - STARTING NOW

---

## IK Chain Refactoring - 2026-02-17

### Context
Got stuck on ad hoc IK chain construction when working with Sonnet. Brought in Opus for fresh analysis. Decision: refactor for maintainability and reliability.

### Branch
`refactor/ik-chain-architecture` (created from master @ d068918)

### Rollback Plan
```bash
# If things go wrong:
git checkout master                           # Return to stable
git branch -D refactor/ik-chain-architecture  # Delete failed branch

# Or rollback specific commits:
git reset --hard HEAD~1                       # Undo last commit
```

### Analysis Summary (Opus 4.5)

**Current Architecture** (working but complex):
1. DAZ Bones (original) → receive Copy Rotation from...
2. .IK Control Bones → receive IK constraint targeting...
3. Target/Pole Bones → what user drags

**Identified Issues**:
1. **Chain collection is ad hoc** - Skip conditions scattered in while loop (twist bones, pectorals, pinned bones)
2. **Stiffness not configurable** - Templates are fixed, no runtime adjustment
3. **Mode switching fragile** - Rotation cache/restore pattern duplicated in 3 places (lines 747, 1503, 2387)
4. **Missing constraints** - Diffeomorphic doesn't always create LIMIT_ROTATION for head, shoulder twist, elbow, forearm twist
5. **File too large** - daz_bone_select.py at 267KB does too much

### Refactoring Plan (Incremental, One Commit Each)

| Order | Task | Risk | Status |
|-------|------|------|--------|
| 1 | Extract `ik_templates.py` | Low | [x] Done (c013065) |
| 2 | Extract `bone_utils.py` | Low | [x] Done (a8e5e56) |
| 3a | Create rotation cache module | Low | [x] Done (fb79677) |
| 3b | Replace existing cache patterns | Medium | [ ] Pending - TEST FIRST |
| 4 | Extract `ik_chain.py` | Medium | [ ] Pending |
| 5 | Make stiffness configurable | Medium | [ ] Pending |
| 6 | Refactor chain building to class | Higher | [ ] Pending |

### Test Checklist (Run After Each Change)
- [x] Script loads without import errors
- [ ] Basic arm IK drag works - **PRE-EXISTING ISSUE: arm shrugs instead of reaching**
- [ ] Leg IK with pre-bend works - **PRE-EXISTING ISSUE: knee bends backward, thigh twists**
- [ ] Soft pin behavior intact - works (tested with pinned hand)
- [ ] No snap-back on release
- [ ] Collar/shoulder movement smooth

**Note**: Arm/leg IK issues existed on master before refactoring. Will address after cleanup.

### Key Code Locations
- `daz_bone_select.py:44-134` - IK_RIG_TEMPLATES
- `daz_bone_select.py:534-1414` - create_ik_chain() main function
- `daz_bone_select.py:631-660` - Bone hierarchy traversal
- `daz_bone_select.py:747` - Rotation cache #1
- `daz_bone_select.py:1503` - Rotation cache #2
- `daz_bone_select.py:2387` - Rotation cache #3
- `daz_shared_utils.py` - Rotation utilities, enforce_rotation_limits()

---

### Decisions Made
- **Outline for body view only** - Hand/face views use standin mesh with matcap, no GP outline
  - Rationale: Generating separate GP Line Art bakes for each camera view adds complexity
  - Standin mesh with matcap should be clear enough at hand/face zoom levels
  - Can always add outlines later if needed

- **Combined hands view** - Both hands in single camera (like DAZ PowerPose)
  - Camera: `PB_Camera_Hands` (not separate left/right cameras)
  - Hands positioned side-by-side, dorsal view (back of hand up), thumbs inward
  - Z offset -53m (below body setup at -50m)

- **Thumb group positioning** - Use mid-point of Thumb1 bone
  - Thumb1 bone head is deep in palm (near wrist), not visible
  - Mid-point gives better visual placement near visible thumb base

### Today's Goals
- [ ] Create consolidated init script (`posebridge/init_posebridge.py`)
- [ ] Modify `outline_generator_lineart.py` for standin mesh
- [x] Add hand cameras - `PB_Camera_Hands` created
- [x] Extract hand geometry - `extract_hands.py` working
- [x] Define hand control points - 42 total (21 per hand)
- [x] Store hand control points in PoseBridge settings
- [x] Integrate view switching into panel_ui.py
- [x] Filter control point drawing by active_panel
- [x] Create icon system (icons.py) for view switcher
- [x] Create icon shape extraction tool (extract_icon_shape.py)
- [ ] Wire icons into main drawing.py (pending user icon designs)
- [ ] Add icon click handling in interaction.py

### Test Results - 2026-02-17

**Hand Extraction Test**: SUCCESS
- Vertex groups found: 20 per hand (lHand, lThumb1-3, lIndex1-3, lMid1-3, lRing1-3, lPinky1-3, lCarpal1-4)
- Vertices extracted: 1623 per hand
- Faces extracted cleanly with no gaps

**Calibrated Hand Transforms** (dorsal view, thumbs inward):
```
PB_Hand_Left:
  location=(-0.040003, -0.68324, z_offset + 0.022)
  rotation=(-180.16°, -34.575°, -88.528°)

PB_Hand_Right:
  location=(0.026067, -0.67678, z_offset - 0.049)
  rotation=(187.13°, 32.286°, 95.809°)
```
*Recalibrated after adding origin-to-geometry fix*

**Hand Control Points Integration**: SUCCESS
- 42 control points generated and stored (21 per hand)
- Control points filtered by `panel_view` property
- View switching works via N-Panel buttons and Python

**Icon System Test**: SUCCESS
- GPU overlay rendering working in standalone test
- Body stick figure, hand outline, head outline all render
- Modal operator handles hover highlighting and click cycling
- Press ESC to exit test mode

---

## Hand Panel Implementation - 2026-02-17

### Files Created/Modified

**New Files:**
- `posebridge/extract_hands.py` - Hand geometry extraction and bone position calculation
- `posebridge/test_hand_integration.py` - Consolidated test script
- `posebridge/icons.py` - Icon shape definitions and GPU drawing functions
- `posebridge/test_icons.py` - Standalone icon preview/test script
- `posebridge/extract_icon_shape.py` - Extract icon shapes from Blender meshes

**Modified Files:**
- `posebridge/core.py` - Added `active_panel` EnumProperty
- `posebridge/drawing.py` - Filter control points by active panel
- `posebridge/panel_ui.py` - View switching UI and operator

### Hand Control Points (42 total)

**Per Hand (21 points):**
```
Individual Joints (Circles) - 15:
  Thumb:  Thumb1, Thumb2, Thumb3
  Index:  Index1, Index2, Index3
  Mid:    Mid1, Mid2, Mid3
  Ring:   Ring1, Ring2, Ring3
  Pinky:  Pinky1, Pinky2, Pinky3

Finger Groups (Diamonds) - 5:
  Thumb_group, Index_group, Mid_group, Ring_group, Pinky_group

Fist Control (Diamond) - 1:
  Hand_fist (curls all 15 finger bones)
```

### Key Code Changes

**core.py - Active Panel Property:**
```python
active_panel: EnumProperty(
    name="Active Panel",
    items=[
        ('body', 'Body', 'Full body panel'),
        ('hands', 'Hands', 'Both hands detail panel'),
        ('face', 'Face', 'Face detail panel'),
    ],
    default='body'
)
```

**drawing.py - Control Point Filtering:**
```python
# Get active panel view
active_panel = settings.active_panel

# Draw each fixed control point that matches the active panel
for cp in fixed_control_points:
    cp_panel = cp.panel_view if cp.panel_view else 'body'
    if cp_panel != active_panel:
        continue  # Skip points not in current view
```

**extract_hands.py - Thumb Group Fix:**
```python
# For thumb group, use mid-point (head is deep in palm)
if finger_name == 'Thumb':
    bone_positions[group_key] = transform_point(bone_mid_world)
else:
    bone_positions[group_key] = transform_point(bone_head_world)
```

---

## Icon System for View Switching - 2026-02-17

### Overview
DAZ PowerPose-style icons in viewport corner for switching between Body/Hands/Face views.

### Architecture

**icons.py:**
- Icon shape definitions in normalized 0-1 coordinates
- `ICON_BODY` - stick figure with head circle and body lines
- `ICON_HAND` - hand outline (LINE_STRIP)
- `ICON_HEAD` - head/face outline (LINE_STRIP)
- Drawing functions: `draw_body_icon()`, `draw_icon_outline()`, `draw_icon_filled()`
- `ViewSwitcherIcons` class for positioning and hit testing

**test_icons.py:**
- Standalone GPU overlay test (works in blank scene)
- Modal operator for hover/click interaction
- Press ESC to stop and remove overlay

**extract_icon_shape.py:**
- Extracts icon shapes from selected mesh
- Normalizes vertices to 0-1 range
- Orders vertices by edge connectivity for LINE_STRIP
- Outputs Python code ready to paste into icons.py

### Icon Shape Workflow
1. Create flat mesh on XY plane (Z=0) in Blender
2. Draw icon outline with vertices/edges
3. Work in Top view (Numpad 7)
4. Keep shape within square area
5. Select mesh and run `extract_icon_shape.py`
6. Copy output from System Console to icons.py

### Pending Work
- User designing custom icon shapes
- Wire `icons.py` into main `drawing.py`
- Add click handling in `interaction.py` to switch views
- Update `TESTING_POSEBRIDGE.md` with icon testing steps

### Testing Documentation Updates

**TESTING_POSEBRIDGE.md** updated with Steps 11-14 for hand panel:
- Step 11: Generate Hand Panel (run test_hand_integration.py)
- Step 12: Switch to Hands View (N-Panel or Python)
- Step 13: Test Hand Control Points (circles, diamonds, fist)
- Step 14: Switch Back to Body View

**Success Criteria** updated with:
- Hand panel visual checks (42 control points, mesh visibility)
- View switching checks (buttons, camera, filtering)
- Fixed positioning checks (points never move with bones)

---

## Previous Session: 2026-02-16

### Active Work
- Setting up four-file documentation system (CLAUDE.md, INDEX.md, SCRATCHPAD.md, TODO.md)
- Establishing project organization for better AI assistant collaboration
- **Planning BlenDAZ N-Panel** - Centralized setup and configuration UI

### Goals Completed
- [x] Update CLAUDE.md with documentation system guidelines
- [x] Create INDEX.md with complete file reference
- [x] Create SCRATCHPAD.md (this file)
- [x] Create TODO.md with current tasks and roadmap
- [x] Plan BlenDAZ N-Panel UI structure (draft in this file)
- [x] Design Hand Panel control points (21 per hand: 15 circles + 5 finger groups + 1 fist)
- [x] Test standin mesh reuse (SUCCESS - GP survives visible mesh)

### Session Summary - 2026-02-16
**Accomplished:**
1. Confirmed standin mesh approach works (reuse `_LineArt_Copy`, don't hide, strip materials)
2. Designed hand panel with full control hierarchy (circles + finger groups + fist group)
3. Documented N-Panel structure, init script consolidation, rollback procedures
4. Clarified group node behavior (each bone rotates around own origin)

**Next Session - Ready to Implement:**
1. **Init script** - Consolidate all setup steps into single script
2. **Standin changes** - Modify outline_generator_lineart.py (keep visible, rename, strip materials)
3. **Hand cameras** - Add `PB_Camera_LeftHand`, `PB_Camera_RightHand` generation
4. **Hand control points** - Define 21-point set in control_points.py

---

## BlenDAZ N-Panel Planning - 2026-02-16

### Overview
Create a unified N-Panel for BlenDAZ setup and configuration. Currently posebridge setup is scattered across scripts - need a proper UI for initialization and options.

### Panel Structure (Draft)

```
┌─────────────────────────────────┐
│ BlenDAZ Setup                   │
├─────────────────────────────────┤
│ Figure: [Genesis8Female    ▼]   │
│ Status: ✓ Initialized           │
│                                 │
│ [Initialize Selected Figure]    │
│ [Reset / Cleanup]               │
├─────────────────────────────────┤
│ ▼ Standin Mesh                  │
│   ☑ Enable Standin              │
│   Display: [Solid ▼] (matcap)   │
│   [Regenerate Standin]          │
├─────────────────────────────────┤
│ ▼ Outline                       │
│   ☑ Enable Outline              │
│   Thickness: [====●====] 4      │
│   Color: [■ Cyan]               │
│   [Regenerate Outline]          │
├─────────────────────────────────┤
│ ▼ Control Points                │
│   Size: [====●====] 8           │
│   Color: [■ Cyan]               │
│   Hover Color: [■ Yellow]       │
├─────────────────────────────────┤
│ ▼ Advanced                      │
│   Z Offset: [-50.0] m           │
│   Camera Distance: [12.0] m     │
│   [Move Setup to Offset]        │
└─────────────────────────────────┘
```

### Key Decisions

**1. Initialization Flow**
- User selects figure (mesh or armature)
- Clicks "Initialize"
- Check: Is armature in rest pose? If not, warn/prompt
- Creates: Standin mesh, GP outline, camera, light, control points
- Moves everything to Z offset (-50m)

**2. Standin Mesh (NEW)**
- Reuse existing `_LineArt_Copy` mesh (confirmed GP survives this)
- Rename to `[FigureName]_Standin`
- Strip all materials (rely on viewport matcap)
- Keep visible (don't hide like we do now)
- Static rest pose captured at init time

**3. Outline Options (NEW)**
- Enable/disable: Toggle GP object visibility
- Thickness: GP Thickness modifier (can adjust live post-bake)
- Color: Modify GP material color (can adjust live)
- Currently cyan, user can customize

**4. What Stays vs. What's Regenerated**
- Standin/Outline: Created once at init, options modify existing objects
- Regenerate buttons: For when user wants to start fresh
- Control points: Captured at init, positions are fixed (Phase 1)

### Implementation Notes

**Settings Storage**
- Add properties to `PoseBridgeSettings` in `posebridge/core.py`:
  - `outline_enabled: BoolProperty`
  - `outline_thickness: FloatProperty`
  - `outline_color: FloatVectorProperty(subtype='COLOR')`
  - `standin_enabled: BoolProperty`
  - `z_offset: FloatProperty`
  - etc.

**Outline Thickness Post-Bake**
- After Line Art modifier is applied, add a GP Thickness modifier
- This modifier CAN be adjusted live without regenerating
- Link modifier value to `outline_thickness` property

**Outline Color Post-Bake**
- GP material color can be changed anytime
- Link material color to `outline_color` property
- Use driver or update callback

**Panel Location**
- 3D Viewport > Sidebar (N-Panel) > "BlenDAZ" tab
- Or could be subtab under existing "PoseBridge" tab

### Open Questions

1. **Single panel vs. tabs?** - One "BlenDAZ" panel, or separate "Setup" and "PoseBridge" tabs?
2. **Multi-character support?** - Dropdown to select which figure to configure?
3. **Presets?** - Save/load outline+standin configurations?
4. **Auto-detect Genesis version?** - Or manual selection?

### Test Results - 2026-02-16

**Standin Mesh Reuse Test**: ✅ SUCCESS
- Unhid `Fey Mesh_LineArt_Copy` using `bpy.data.objects["..."].hide_viewport = False`
- GP outline survived having source mesh visible
- Mesh displays nicely with viewport matcap
- Control points render correctly over mesh
- Outline is subtle but visible over solid mesh

**Conclusion**: Can reuse LineArt_Copy as Standin - no need for second mesh copy

---

## Hands & Face Detail Panels - 2026-02-16

### Reference
DAZ PowerPose style layout with:
- Full body view (small, corner thumbnail)
- Two large hand views (left/right)
- Face detail view
- Switchable between views

### Hand Panel Design

**Camera Setup:**
- Two additional cameras: `PB_Camera_LeftHand`, `PB_Camera_RightHand`
- Orthographic, positioned to view hands on standin mesh
- Same Z offset (-50m) as main body setup
- View angle: back-of-hand (dorsal view) - matches DAZ and natural viewing

**Control Points (per hand, 21 points):**

*Individual Joint Controls (Circles) - 15 per hand:*
```
Thumb:   lThumb1, lThumb2, lThumb3 (3)
Index:   lIndex1, lIndex2, lIndex3 (3)
Mid:     lMid1, lMid2, lMid3 (3)
Ring:    lRing1, lRing2, lRing3 (3)
Pinky:   lPinky1, lPinky2, lPinky3 (3)
```

*Finger Group Controls (Diamonds) - 5 per hand:*
```
lThumb_group:  [lThumb1, lThumb2, lThumb3] - curl whole thumb
lIndex_group:  [lIndex1, lIndex2, lIndex3] - curl whole index finger
lMid_group:    [lMid1, lMid2, lMid3] - curl whole middle finger
lRing_group:   [lRing1, lRing2, lRing3] - curl whole ring finger
lPinky_group:  [lPinky1, lPinky2, lPinky3] - curl whole pinky
```

*Fist Control (Diamond) - 1 per hand:*
```
lHand_fist:    [ALL 15 finger bones] - curl all fingers into fist
```

**Total: 21 per hand × 2 = 42 hand control points**

**Control Hierarchy:**
- Circle = individual joint rotation
- Finger diamond = curl entire finger (all 3 joints rotate around own origins)
- Fist diamond = curl ALL fingers (all 15 bones rotate around own origins)

**Control Point Generation:**
- Procedural, like full-body view
- Capture bone head positions projected to hand camera view
- Group nodes positioned at base of each finger (finger groups) and palm center (fist)

### Face Panel Design

**Camera Setup:**
- `PB_Camera_Face` - positioned in front of face on standin
- Orthographic, framed on head/neck area

**Control Points (TBD):**
- Eyes: lEye, rEye (look direction)
- Eyelids: upper/lower for each eye
- Brow: inner, mid, outer for each side
- Jaw: open/close
- Mouth corners, lips
- Nose?

*Note: Genesis 8/9 facial rig has MANY bones - need to decide which are most useful for posing vs. expression*

### View Switching

**UI Options:**
1. **Buttons in N-Panel**: [Body] [L Hand] [R Hand] [Face]
2. **Dropdown**: View: [Body ▼]
3. **Keyboard shortcuts**: 1=Body, 2=LHand, 3=RHand, 4=Face

**Implementation:**
- Store current view mode in settings
- Switch camera in the posebridge viewport
- Load appropriate control point set for that view
- Draw handler checks current view mode

### Open Questions

1. **Hand camera angle** - Dorsal (back of hand) vs palmar (palm)? Dorsal seems more natural.
2. **Face bones** - Which subset? Full facial rig is overwhelming.
3. **Viewport switching** - Change camera in existing viewport, or show/hide different viewports?
4. **Control point persistence** - Generate all at init, or lazily when switching to that view?

---

## Init Script Consolidation - 2026-02-16

### Goal
Single script that runs all posebridge initialization steps from TESTING_POSEBRIDGE.md

### Current Steps to Consolidate
1. Register PoseBridge (path + import + register)
2. Generate outline (outline_generator_lineart.py)
3. Move setup to Z -50m
4. Recapture control points
5. Start PoseBridge (enable mode + modal)

### New: Standin Mesh Changes
- Don't hide `_LineArt_Copy` mesh
- Rename to `[FigureName]_Standin`
- Strip all materials from standin

### Rollback Info
If standin changes break things, to restore original behavior in `outline_generator_lineart.py`:

**Lines ~633-636 (cleanup section):**
```python
# ORIGINAL - hides mesh:
mesh_copy.hide_viewport = True
mesh_copy.hide_render = True

# NEW - keeps visible, strips materials:
mesh_copy.hide_viewport = False  # Keep visible as standin
mesh_copy.hide_render = True     # Still hide from renders
# Strip materials
mesh_copy.data.materials.clear()
# Rename
mesh_copy.name = f"{mesh_obj.name}_Standin"
```

**To rollback**: Restore `hide_viewport = True` and remove material stripping/rename

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

### Icon System Integration - NEXT UP
**Description**: Wire icons.py into main drawing.py and add click handling
**Status**: Waiting for user to design custom icon shapes
**When Ready**:
1. Import icons.py in drawing.py
2. Call ViewSwitcherIcons.draw_all() in draw handler
3. Add hit testing in interaction.py modal operator
4. Switch active_panel when icon clicked
5. Test full workflow body → hands → face → body

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

**GPU Icon Drawing (LINE_STRIP)**:
```python
shader = gpu.shader.from_builtin('UNIFORM_COLOR')
batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": vertices})
gpu.state.blend_set('ALPHA')
gpu.state.line_width_set(2.0)
shader.bind()
shader.uniform_float("color", (0.0, 0.8, 1.0, 1.0))  # Cyan
batch.draw(shader)
```

**View Switching**:
```python
# In panel_ui.py operator
bpy.context.scene.posebridge_settings.active_panel = 'hands'

# In drawing.py filtering
cp_panel = cp.panel_view if cp.panel_view else 'body'
if cp_panel != settings.active_panel:
    continue
```

---

## Archive (Completed Work)

### ✅ Hand Panel Core Implementation - 2026-02-17
**Summary**: Implemented hand panel with 42 control points (21 per hand), view switching, and control point filtering
**Files Created**: extract_hands.py, test_hand_integration.py, icons.py, test_icons.py, extract_icon_shape.py
**Files Modified**: core.py, drawing.py, panel_ui.py, TESTING_POSEBRIDGE.md
**Key Features**:
- Hand geometry extraction from standin mesh using vertex groups
- Bone position calculation with proper transforms
- Finger group diamonds and fist control diamond
- View switching between body/hands/face panels
- Control point filtering by panel_view property
**Lessons Learned**:
- Thumb1 bone head is deep in palm - use mid-point for thumb group
- Normalized 0-1 coordinates work well for icon shapes
- Edge-connectivity ordering essential for LINE_STRIP drawing

### ✅ Documentation System Setup - 2026-02-16
**Summary**: Established four-file documentation system with CLAUDE.md, INDEX.md, SCRATCHPAD.md, TODO.md
**Lessons Learned**:
- Comprehensive INDEX.md requires understanding entire project structure
- Cross-references between docs improve discoverability
- File size statistics help identify potential maintenance issues
