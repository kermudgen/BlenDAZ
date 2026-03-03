# PoseBlend Design Document

**Version:** 0.1 (Design Phase)
**Date:** 2026-02-15
**Purpose:** DAZ Puppeteer-style pose blending system for Blender

---

## Overview

PoseBlend provides an intuitive 2D grid interface for saving, organizing, and blending poses. Users place "dots" on a grid, each representing a saved pose. Moving a cursor across the grid blends between nearby poses in real-time, with the result previewed live on the character.

### Key Differentiators from DAZ Puppeteer

| Feature | DAZ Puppeteer | PoseBlend |
|---------|---------------|-----------|
| Bone filtering | Limited | Full bone group/region filtering per dot |
| Grid visualization | Basic | Enhanced with visual feedback |
| Export/Import | No | Yes (JSON format) |
| Multiple grids | Yes | Yes, with categories |
| Integration | DAZ only | Blender ecosystem |

---

## Architecture

### Module Structure

```
poseblend/
├── __init__.py              # Module registration, bl_info
├── core.py                  # PropertyGroups (PoseBlendDot, PoseBlendGrid, Settings)
├── poses.py                 # Pose capture, application, bone rotation utilities
├── blending.py              # Distance-weighted interpolation algorithms
├── grid.py                  # Grid coordinate math, snap-to-grid, hit testing
├── interaction.py           # Modal operator for grid interaction
├── drawing.py               # GPU drawing (grid, dots, cursor, labels)
├── panel_ui.py              # N-panel interface and controls
├── viewport_setup.py        # Orthographic camera and viewport configuration
├── import_export.py         # JSON serialization for grids and poses
└── presets.py               # Default bone groups, grid templates
```

---

## Data Model

### PoseBlendDot (PropertyGroup)

Represents a single saved pose at a grid position.

```python
class PoseBlendDot(PropertyGroup):
    # Identity
    id: StringProperty()                    # Unique identifier (UUID)
    name: StringProperty()                  # User-friendly name ("Happy", "Arms Up")

    # Grid position (normalized 0-1)
    position: FloatVectorProperty(size=2)   # (x, y) on grid

    # Pose data
    bone_rotations: StringProperty()        # JSON-encoded {bone_name: [w,x,y,z]}

    # Bone mask - which bones this pose affects
    bone_mask_mode: EnumProperty(
        items=[
            ('ALL', 'Full Body', 'All bones'),
            ('PRESET', 'Preset Region', 'Use predefined bone group'),
            ('CUSTOM', 'Custom', 'Custom bone selection'),
        ]
    )
    bone_mask_preset: EnumProperty(
        items=[
            ('HEAD', 'Head & Face', 'Head, neck, eyes, jaw'),
            ('UPPER_BODY', 'Upper Body', 'Spine, chest, shoulders, arms'),
            ('LOWER_BODY', 'Lower Body', 'Pelvis, legs, feet'),
            ('ARMS', 'Arms', 'Both arms and hands'),
            ('ARM_L', 'Left Arm', 'Left arm and hand'),
            ('ARM_R', 'Right Arm', 'Right arm and hand'),
            ('LEGS', 'Legs', 'Both legs and feet'),
            ('LEG_L', 'Left Leg', 'Left leg and foot'),
            ('LEG_R', 'Right Leg', 'Right leg and foot'),
            ('HANDS', 'Hands', 'Fingers only'),
            ('FACE', 'Face', 'Facial bones/expressions'),
            ('SPINE', 'Spine', 'Spine and torso only'),
        ]
    )
    bone_mask_custom: StringProperty()      # JSON list of bone names

    # Visual properties
    color: FloatVectorProperty(size=4)      # RGBA for dot color
    icon: EnumProperty()                    # Optional icon/shape

    # Metadata
    created_time: StringProperty()          # ISO timestamp
    thumbnail: StringProperty()             # Optional base64 preview image
```

### PoseBlendGrid (PropertyGroup)

A collection of dots forming a blending space.

```python
class PoseBlendGrid(PropertyGroup):
    # Identity
    id: StringProperty()                    # Unique identifier
    name: StringProperty()                  # "Body Poses", "Expressions", etc.

    # Dots collection
    dots: CollectionProperty(type=PoseBlendDot)
    active_dot_index: IntProperty()

    # Grid settings
    grid_size: IntVectorProperty(size=2)    # Grid divisions (e.g., 8x8)
    snap_to_grid: BoolProperty()            # Snap dot placement to grid
    show_grid_lines: BoolProperty()

    # Default bone mask for new dots
    default_mask_mode: EnumProperty()
    default_mask_preset: EnumProperty()

    # Visual settings
    background_color: FloatVectorProperty(size=4)
    grid_line_color: FloatVectorProperty(size=4)

    # Associated armature
    armature_name: StringProperty()
```

### PoseBlendSettings (PropertyGroup)

Scene-level settings.

```python
class PoseBlendSettings(PropertyGroup):
    # Mode
    is_active: BoolProperty()               # PoseBlend mode enabled

    # Grids collection
    grids: CollectionProperty(type=PoseBlendGrid)
    active_grid_index: IntProperty()

    # Interaction settings
    preview_mode: EnumProperty(
        items=[
            ('REALTIME', 'Real-time', 'Preview as you drag'),
            ('ON_RELEASE', 'On Release', 'Apply only when mouse released'),
        ]
    )
    auto_keyframe: BoolProperty()

    # Blending settings
    blend_falloff: EnumProperty(
        items=[
            ('LINEAR', 'Linear', '1/distance'),
            ('QUADRATIC', 'Quadratic', '1/distance^2 (default)'),
            ('CUBIC', 'Cubic', '1/distance^3 (sharper)'),
            ('SMOOTH', 'Smooth', 'Smoothstep interpolation'),
        ]
    )
    blend_radius: FloatProperty()           # Max influence radius (0 = infinite)

    # Viewport
    viewport_camera_name: StringProperty()
    viewport_area_index: IntProperty()
```

---

## Bone Group Presets

### Genesis 8 Bone Groups

```python
BONE_GROUPS = {
    'HEAD': [
        'head', 'neck', 'neckLower', 'neckUpper',
        'lEye', 'rEye', 'jaw',
        # Add facial bones as needed
    ],

    'UPPER_BODY': [
        'chest', 'chestUpper', 'chestLower',
        'abdomen', 'abdomenUpper', 'abdomenLower',
        'lCollar', 'rCollar',
        'lShldr', 'rShldr', 'lShldrBend', 'rShldrBend', 'lShldrTwist', 'rShldrTwist',
        'lForeArm', 'rForeArm', 'lForearmBend', 'rForearmBend', 'lForearmTwist', 'rForearmTwist',
        'lHand', 'rHand',
    ],

    'LOWER_BODY': [
        'pelvis', 'hip',
        'lThigh', 'rThigh', 'lThighBend', 'rThighBend', 'lThighTwist', 'rThighTwist',
        'lShin', 'rShin',
        'lFoot', 'rFoot',
        'lToe', 'rToe', 'lMetatarsals', 'rMetatarsals',
    ],

    'ARM_L': [
        'lCollar', 'lShldr', 'lShldrBend', 'lShldrTwist',
        'lForeArm', 'lForearmBend', 'lForearmTwist',
        'lHand',
        # Left finger bones...
    ],

    'ARM_R': [
        'rCollar', 'rShldr', 'rShldrBend', 'rShldrTwist',
        'rForeArm', 'rForearmBend', 'rForearmTwist',
        'rHand',
        # Right finger bones...
    ],

    'HANDS': [
        # All finger bones for both hands
        'lThumb1', 'lThumb2', 'lThumb3',
        'lIndex1', 'lIndex2', 'lIndex3',
        'lMid1', 'lMid2', 'lMid3',
        'lRing1', 'lRing2', 'lRing3',
        'lPinky1', 'lPinky2', 'lPinky3',
        'rThumb1', 'rThumb2', 'rThumb3',
        # ... etc
    ],

    'SPINE': [
        'pelvis', 'hip',
        'abdomen', 'abdomenUpper', 'abdomenLower',
        'chest', 'chestUpper', 'chestLower',
        'neck', 'neckLower', 'neckUpper',
    ],

    'FACE': [
        # Facial bones - depends on rig
        # For Genesis 8, these would be the face rig bones
    ],
}
```

---

## Blending Algorithm

### Inverse Distance Weighting (IDW)

The core algorithm blends poses based on cursor distance from each dot.

```python
def calculate_blend_weights(cursor_pos, dots, falloff='QUADRATIC', radius=0.0):
    """
    Calculate blend weights for each dot based on cursor position.

    Args:
        cursor_pos: (x, y) normalized grid position
        dots: List of PoseBlendDot
        falloff: 'LINEAR', 'QUADRATIC', 'CUBIC', or 'SMOOTH'
        radius: Max influence radius (0 = infinite)

    Returns:
        List of (dot, weight) tuples, normalized to sum to 1.0
    """
    weights = []

    for dot in dots:
        distance = math.sqrt(
            (cursor_pos[0] - dot.position[0])**2 +
            (cursor_pos[1] - dot.position[1])**2
        )

        # Check if cursor is directly on dot
        if distance < 0.001:
            return [(dot, 1.0)]  # 100% this pose

        # Apply radius cutoff if specified
        if radius > 0 and distance > radius:
            continue

        # Calculate weight based on falloff
        if falloff == 'LINEAR':
            weight = 1.0 / distance
        elif falloff == 'QUADRATIC':
            weight = 1.0 / (distance ** 2)
        elif falloff == 'CUBIC':
            weight = 1.0 / (distance ** 3)
        elif falloff == 'SMOOTH':
            # Smoothstep-based falloff
            t = min(distance / (radius or 1.0), 1.0)
            weight = 1.0 - (3 * t**2 - 2 * t**3)

        weights.append((dot, weight))

    # Normalize weights to sum to 1.0
    total = sum(w for _, w in weights)
    if total > 0:
        weights = [(dot, w / total) for dot, w in weights]

    return weights


def blend_rotations(weights, bone_name):
    """
    Blend quaternion rotations from multiple weighted poses.

    Uses iterative SLERP for multiple quaternions.
    """
    if not weights:
        return None

    if len(weights) == 1:
        dot, _ = weights[0]
        return dot.get_rotation(bone_name)

    # Start with first quaternion
    result = weights[0][0].get_rotation(bone_name)
    cumulative_weight = weights[0][1]

    for dot, weight in weights[1:]:
        rotation = dot.get_rotation(bone_name)
        if rotation is None:
            continue

        # Incremental SLERP
        t = weight / (cumulative_weight + weight)
        result = result.slerp(rotation, t)
        cumulative_weight += weight

    return result


def apply_blended_pose(armature, weights):
    """
    Apply blended pose to armature, respecting bone masks.

    Only affects bones that are in ALL contributing dots' masks,
    or uses union mode where any dot affecting a bone contributes.
    """
    # Collect all bones that need blending
    affected_bones = set()
    for dot, weight in weights:
        affected_bones.update(dot.get_bone_mask())

    # Apply blended rotation to each bone
    for bone_name in affected_bones:
        # Filter weights to only dots that affect this bone
        bone_weights = [
            (dot, w) for dot, w in weights
            if bone_name in dot.get_bone_mask()
        ]

        if not bone_weights:
            continue

        # Re-normalize weights for this bone
        total = sum(w for _, w in bone_weights)
        bone_weights = [(d, w/total) for d, w in bone_weights]

        # Calculate blended rotation
        blended_rotation = blend_rotations(bone_weights, bone_name)

        if blended_rotation:
            pose_bone = armature.pose.bones.get(bone_name)
            if pose_bone:
                pose_bone.rotation_quaternion = blended_rotation
```

---

## Viewport Setup

### Orthographic Camera View

Similar to PoseBridge, PoseBlend uses a dedicated orthographic view.

```python
def setup_poseblend_viewport(context):
    """
    Configure viewport for PoseBlend grid view.

    Creates/reuses an orthographic camera looking at a 2D grid plane.
    """
    # Create or get PoseBlend camera
    cam_name = "PoseBlend_Camera"
    camera = bpy.data.cameras.get(cam_name)
    if not camera:
        camera = bpy.data.cameras.new(cam_name)
        camera.type = 'ORTHO'
        camera.ortho_scale = 2.0  # Adjust to fit grid

    # Create camera object
    cam_obj_name = "PoseBlend_CameraObj"
    cam_obj = bpy.data.objects.get(cam_obj_name)
    if not cam_obj:
        cam_obj = bpy.data.objects.new(cam_obj_name, camera)
        context.collection.objects.link(cam_obj)

    # Position camera looking down at XY plane
    cam_obj.location = (0.5, 0.5, 10)  # Center of grid, above
    cam_obj.rotation_euler = (0, 0, 0)  # Looking down -Z

    # Set viewport to use this camera
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.region_3d.view_perspective = 'CAMERA'
                    # ... additional setup
                    break
            break

    return cam_obj
```

### Grid Plane (Optional Visual Aid)

```python
def create_grid_plane():
    """
    Create a visual grid plane for reference.
    Can be a mesh with grid material or just GPU-drawn.
    """
    # Option 1: Mesh plane with grid shader
    # Option 2: Pure GPU drawing (lighter weight)
    pass
```

---

## Interaction Design

### Mouse Events

| Action | Result |
|--------|--------|
| **Click empty space** | Preview blend at that position |
| **Click on dot** | Snap to that exact pose (100% weight) |
| **Drag anywhere** | Continuous blend preview as cursor moves |
| **Release** | Apply pose (optionally keyframe) |
| **Shift + Click empty** | Create new dot at position from current pose |
| **Shift + Drag dot** | Move dot to new position |
| **Ctrl + Click dot** | Delete dot (with confirmation) |
| **Right-click dot** | Context menu (rename, edit mask, delete, duplicate) |
| **Double-click dot** | Edit dot properties |
| **Scroll wheel** | Zoom grid view |
| **Middle-drag** | Pan grid view |

### Modal Operator States

```python
class POSEBLEND_OT_interact(Operator):
    """Modal operator for grid interaction"""

    # States
    IDLE = 'idle'           # Waiting for input
    PREVIEWING = 'preview'  # Showing blend preview
    DRAGGING_DOT = 'drag'   # Moving a dot
    CREATING_DOT = 'create' # Placing new dot

    def modal(self, context, event):
        if self.state == self.IDLE:
            if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                hit_dot = self.hit_test_dots(event.mouse_region_x, event.mouse_region_y)
                if hit_dot:
                    if event.shift:
                        self.state = self.DRAGGING_DOT
                        self.dragged_dot = hit_dot
                    else:
                        self.apply_pose(hit_dot)
                else:
                    if event.shift:
                        self.state = self.CREATING_DOT
                    else:
                        self.state = self.PREVIEWING
                        self.update_preview(event)

        elif self.state == self.PREVIEWING:
            if event.type == 'MOUSEMOVE':
                self.update_preview(event)
            elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                self.finalize_pose()
                self.state = self.IDLE

        # ... etc
```

---

## Visual Design

### Grid Appearance

```
┌─────────────────────────────────┐
│  ·    ·    ·    ·    ·    ·    │  Grid lines (subtle gray)
│       ●Sad        ●Angry       │  Dots with labels
│  ·    ·    ·    ·    ·    ·    │
│            ╳                    │  Cursor position (crosshair)
│  ·    ·    ·    ·    ·    ·    │
│                 ●Happy          │
│  ·    ·    ·    ·    ·    ·    │
│  ●Neutral                       │  Different colors per mask type
└─────────────────────────────────┘
   [+ Add Dot] [Grid: Expressions ▾] [Settings ⚙]
```

### Dot Visualization

| Mask Type | Color | Shape |
|-----------|-------|-------|
| Full Body | White | Circle |
| Head/Face | Yellow | Circle |
| Upper Body | Cyan | Circle |
| Lower Body | Green | Circle |
| Arms | Blue | Circle |
| Hands | Purple | Circle |
| Custom | Orange | Diamond |

### Visual Feedback

- **Hover over dot**: Dot enlarges, shows tooltip with name and mask info
- **Previewing**: Cursor shows as crosshair, faint lines connect to influencing dots
- **Influence radius**: Optional circle around cursor showing blend zone
- **Active dot**: Highlighted ring/glow when cursor is very close

---

## Import/Export Format

### JSON Schema

```json
{
  "version": "1.0",
  "type": "poseblend_grid",
  "name": "Body Poses",
  "armature_type": "Genesis8",
  "grid_size": [8, 8],
  "created": "2026-02-15T12:00:00Z",
  "dots": [
    {
      "id": "uuid-1234",
      "name": "T-Pose",
      "position": [0.5, 0.5],
      "mask_mode": "ALL",
      "mask_preset": null,
      "mask_custom": null,
      "color": [1.0, 1.0, 1.0, 1.0],
      "rotations": {
        "head": [1.0, 0.0, 0.0, 0.0],
        "neck": [1.0, 0.0, 0.0, 0.0],
        "lShldr": [0.98, 0.0, 0.2, 0.0]
      }
    },
    {
      "id": "uuid-5678",
      "name": "Arms Raised",
      "position": [0.8, 0.2],
      "mask_mode": "PRESET",
      "mask_preset": "ARMS",
      "mask_custom": null,
      "color": [0.0, 0.5, 1.0, 1.0],
      "rotations": {
        "lShldr": [0.7, 0.0, 0.7, 0.0],
        "rShldr": [0.7, 0.0, -0.7, 0.0]
      }
    }
  ]
}
```

### Bone Name Remapping

On import, provide option to remap bone names:

```python
BONE_REMAP_PRESETS = {
    'genesis8_to_rigify': {
        'lShldr': 'shoulder.L',
        'rShldr': 'shoulder.R',
        # ...
    },
    'rigify_to_genesis8': {
        'shoulder.L': 'lShldr',
        # ...
    }
}
```

---

## Implementation Phases

### Phase 1: Core Infrastructure
- [ ] Module structure and registration
- [ ] PropertyGroups (Dot, Grid, Settings)
- [ ] Basic viewport setup (orthographic view)
- [ ] Grid drawing (GPU)
- [ ] Dot drawing (GPU)

### Phase 2: Pose Capture & Storage
- [ ] Capture current pose to dot
- [ ] Store bone rotations (quaternions)
- [ ] Bone mask presets
- [ ] Custom bone mask selection UI

### Phase 3: Blending System
- [ ] IDW weight calculation
- [ ] Quaternion blending (multi-pose SLERP)
- [ ] Bone mask filtering during blend
- [ ] Falloff modes

### Phase 4: Interaction
- [ ] Modal operator
- [ ] Click to preview
- [ ] Drag to blend
- [ ] Dot manipulation (move, delete)
- [ ] Create new dot

### Phase 5: UI Polish
- [ ] N-panel controls
- [ ] Dot labels and tooltips
- [ ] Visual feedback (hover, selection)
- [ ] Grid customization

### Phase 6: Import/Export
- [ ] JSON serialization
- [ ] File dialogs
- [ ] Bone remapping on import

### Phase 7: Advanced Features
- [ ] Multiple grids
- [ ] Thumbnails for dots
- [ ] Undo/redo support
- [ ] Keyframe integration

---

## Open Questions

1. **Bone mask conflicts**: When blending dots with different masks, should we:
   - Only blend bones in ALL masks (intersection)?
   - Blend any bone in ANY mask (union)?
   - Per-bone weighted contribution?

2. **Rest pose handling**: If cursor is far from all dots, should we:
   - Blend toward rest pose?
   - Clamp to nearest dot?
   - Show warning/indicator?

3. **Morph targets**: Should PoseBlend also support DAZ morphs (shape keys), or focus only on bone rotations?

4. **Animation integration**: Should moving the cursor record animation, or only set static poses?

---

## Troubleshooting: Recent Fixes

### Shoulder Control Issue (2026-02-15)

**Problem:** Shoulder control node (lShldrBend) not responding to mouse input. Quaternion staying at identity (w=1, x=0, y=0, z=0) despite rotation function being called.

**Root Causes Identified:**
1. **Delta zeroing bug** - Calling code was passing `(delta_x, 0)` for horizontal rotation and `(0, delta_y)` for vertical rotation
2. **Axis mismatch** - The `apply_rotation_from_delta()` function's axis-to-delta mapping didn't match the caller's expectations:
   - `axis='X'` uses `delta_y` (vertical mouse movement)
   - `axis='Y'` uses `delta_x` (horizontal mouse movement)
   - `axis='Z'` uses `delta_x` (horizontal mouse movement)
3. **Swapped axes** - LMB horizontal/vertical controls were backwards

**Fixes Applied:**

1. **[daz_bone_select.py:4066]** - Changed horizontal rotation call from passing `0` to passing `delta_y`
   ```python
   # Before: 0,  # Only horizontal component
   # After:  delta_y,  # Pass actual delta_y so function can use it based on axis
   ```

2. **[daz_bone_select.py:4098]** - Changed vertical rotation call from passing `0` to passing `delta_x`
   ```python
   # Before: 0,  # Only vertical component
   # After:  delta_x,  # Pass actual delta_x so function can use it based on axis
   ```

3. **[daz_bone_select.py:3973-3974]** - Swapped LMB shoulder axes
   ```python
   # Before: horiz_axis='X', vert_axis='Z'
   # After:  horiz_axis='Z', vert_axis='X'
   ```

4. **[daz_bone_select.py:4094-4115]** - Added special handling for RMB shoulder twist
   - Swaps deltas so vertical drag controls Y axis twist
   - Y axis normally uses horizontal delta, but shoulder twist should respond to vertical drag

**Current Shoulder Configuration:**
- **LMB horizontal drag** → Z axis → raise/lower arm (frontal plane)
- **LMB vertical drag** → X axis → swing forward/back (sagittal plane)
- **RMB vertical drag** → Y axis → twist arm (internal/external rotation) on lShldrTwist bone

**Technical Notes:**
- Python module caching in Blender requires full restart after changes to `.py` files
- `enforce_rotation_limits()` was also investigated but was not the root cause
- Multi-bone twist targeting system (lShldrBend + lShldrTwist) working correctly once deltas fixed

---

## References

- DAZ Studio Puppeteer Panel documentation
- Blender GPU module for custom drawing
- Quaternion interpolation techniques (SLERP, NLERP, Squad)
- PoseBridge implementation patterns

---

## Appendix: Quick Start Workflow

1. **Setup**: Select armature, open PoseBlend panel, click "New Grid"
2. **Add poses**: Pose character, Shift+Click on grid to save dot
3. **Label**: Right-click dot, rename to "Happy", "Sad", etc.
4. **Blend**: Click and drag on grid to blend between saved poses
5. **Refine**: Adjust dot positions for intuitive blending relationships
6. **Save**: Grid auto-saves to .blend, export JSON for sharing
