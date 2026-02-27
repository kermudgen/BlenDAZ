# BlenDAZ Character Init System

**Date**: 2026-02-24
**Status**: Planned — awaiting implementation
**Target**: Blender 5+, Diffeomorphic 5.0.0.2736+

---

## Problem Statement

When a user imports a DAZ Genesis character via Diffeomorphic and merges geografts
(e.g. genitals, nipples, navel, custom body parts), the body mesh polygon indices shift.
The BlenDAZ face group system (`dsf_face_groups.py`) maps `polygon_index → bone_name`
using the original DSF file polygon order. After a merge, that order no longer matches
the live mesh, so the mesh highlight overlay either shows nothing or highlights the wrong
region.

The current fallback (vertex weight painting) still works but is less accurate — weight
painting bleeds across region boundaries and doesn't respect DAZ's original face group
definitions.

---

## Goal

Provide a reliable, one-click character setup flow that:

1. Preserves accurate face group → bone mapping after geograft merge
2. Requires no manual intervention from the user for the standard workflow
3. Doesn't interfere with custom morphs, clothing, or user-applied modifiers
4. Degrades gracefully when the user has done their own prep work

---

## Core Insight: The Mannequin as Reference Mesh

During PoseBridge setup, the body mesh is duplicated to create
`{mesh_name}_LineArt_Copy` — the mannequin used by the LineArt outline modifier.
This copy is made **before** geograft merge, so its polygon order exactly matches
the original DSF file.

This means:
- The mannequin already has a valid `FaceGroupManager` (DSF polygon count matches)
- We can build a `face_center → bone_name` dict from the mannequin
- After merge, we match the live mesh polygons to that dict by face center position
- Body vertex positions are **unchanged** by geograft merge — only indices shift
- Therefore face centers are bit-for-bit identical, making the match exact

No extra storage. No extra mesh objects. The mannequin already exists for other reasons.

---

## User Workflows

### Tier 1 — One-Click Init (recommended)

Target user: standard DAZ import with Diffeomorphic, no custom setup.

```
1. Import character via Diffeomorphic (user's responsibility)
2. User clicks: [Init Character with BlenDAZ]
3. BlenDAZ automatically:
   a. Validates prerequisites
   b. Creates mannequin copy (PoseBridge outline setup) while mesh is still pre-merge
   c. Merges geografts via Diffeomorphic operator
   d. Runs face group remap (mannequin → live merged mesh)
   e. Runs PoseBridge CP setup
   f. Sets scene status: blendaz_init_status = 'ready'
```

### Tier 2 — Manual Prep, Then Register

Target user: wants to add custom geograft morphs before merging, or uses non-standard
import settings.

```
1. Import character via Diffeomorphic
2. Add custom morphs, make any adjustments
3. User tells BlenDAZ: [Snapshot Pre-Merge State]
   → BlenDAZ creates mannequin copy at this point
4. User merges geografts when ready (manually via Diffeomorphic)
5. User clicks: [Remap Face Groups]
   → BlenDAZ runs the face group remap using the saved mannequin
   → Runs PoseBridge CP setup
```

### Tier 3 — No Merge / Already Set Up

Target user: advanced, no geografts, or pre-merged by another tool.

```
- Character already in final state when BlenDAZ setup runs
- Mannequin polygon order matches live mesh (no remap needed)
- Standard FaceGroupManager path works normally
- Init operator detects this case and skips remap step
```

---

## Technical Design

### Face Group Remap Algorithm

```
Input:  reference_mesh  (mannequin, pre-merge polygon order)
        live_mesh       (merged body mesh, shifted polygon indices)
        armature        (for bone name validation)

Step 1: Build FaceGroupManager on reference_mesh
        (DSF polygon count matches → standard build path)

Step 2: Build ref_center_map: {(x, y, z) rounded to 4dp} → bone_name
        For each polygon in reference_mesh:
            Compute face center = average of vertex positions
            If bone_name is not None:
                ref_center_map[round(center, 4dp)] = bone_name

Step 3: Build new_face_group_map for live_mesh
        For each polygon in live_mesh:
            Compute face center
            Look up in ref_center_map
            new_face_group_map[poly_idx] = match or None

        Unmatched polygons = geograft polygons (correct: no highlight wanted)

Step 4: Construct FaceGroupManager with new_face_group_map
        Cache under key: (live_mesh.data.name, len(live_mesh.data.polygons))
        Standard highlight/raycast system uses it transparently from here
```

Position matching is exact (not approximate) because geograft merge does not move
existing body vertices. 4dp rounding handles float representation noise only.

### Changes Required

**`dsf_face_groups.py`**
Add classmethod `FaceGroupManager.build_from_reference_mesh(ref_mesh, live_mesh, armature)`:
- Builds FaceGroupManager on ref_mesh (DSF path)
- Runs remap algorithm above
- Returns a FaceGroupManager instance valid for live_mesh
- Caches under live_mesh key

**New file: `projects/posebridge/init_character.py`**
Contains:
- `DAZ_OT_blendaz_init_character` — Tier 1 one-click operator
- `DAZ_OT_blendaz_snapshot_premerge` — Tier 2 snapshot step
- `DAZ_OT_blendaz_remap_face_groups` — Tier 2/3 remap-only operator
- `blendaz_check_prerequisites()` — validation helper

**`projects/posebridge/panel_ui.py`**
Add collapsible "BlenDAZ Setup" section at top of N-panel:
- Status indicator: Uninitialised / Ready / Needs Remap
- [Init Character] button (Tier 1)
- Expandable advanced section: [Snapshot Pre-Merge] + [Remap Face Groups] (Tier 2)

**`projects/posebridge/core.py`**
Add to `PoseBridgeSettings`:
- `blendaz_init_status`: EnumProperty ('uninitialised', 'ready', 'needs_remap')
- `blendaz_reference_mesh_name`: StringProperty (name of mannequin copy used for remap)
- `blendaz_live_mesh_poly_count`: IntProperty (polygon count at time of remap, for stale detection)

### Status Detection Logic

The panel displays status by checking:

```
if blendaz_init_status == 'ready':
    if live_mesh.polygon_count != blendaz_live_mesh_poly_count:
        display: "Needs Remap" (mesh changed since last init)
    else:
        display: "Ready"
elif blendaz_init_status == 'uninitialised':
    display: "Uninitialised"
```

---

## Prerequisite Validation

Before running init, check:

| Check | How | Failure Message |
|-------|-----|-----------------|
| Blender 5+ | `bpy.app.version >= (5, 0, 0)` | "BlenDAZ requires Blender 5.0 or later" |
| Diffeomorphic present | `'import_daz' in dir(bpy.ops)` | "Diffeomorphic addon not found. Install v5.0.0.2736+" |
| Diffeomorphic version | Parse `bpy.ops.import_daz.bl_info` or custom property | Warning only (not blocking) |
| DAZ armature selected | Active object is ARMATURE with `DazUrl` custom prop | "Please select a DAZ armature" |
| Body mesh found | `find_base_body_mesh()` returns non-None | "Could not find body mesh rigged to armature" |
| Geografts exist | Check for objects with `DazGeoGraft` custom property | Skip merge step if none found |

---

## UI Design

```
N-Panel (right sidebar):

▼ BlenDAZ Setup
  Status: ● Uninitialised

  [Init Character]          ← Tier 1 one-click

  ▶ Advanced
    [Snapshot Pre-Merge State]   ← Tier 2 step A
    [Remap Face Groups]          ← Tier 2 step B / Tier 3
```

Status indicator colors:
- Grey dot: Uninitialised
- Green dot: Ready
- Orange dot: Needs Remap (mesh changed)

The entire Setup section collapses once init is complete so it stays out of the way
during normal use. Users can re-expand it if they need to reinitialise.

---

## Manual / User-Facing Documentation Notes

Key points to cover in the manual:

1. **When to run Init**: After importing from DAZ/Diffeomorphic, before starting to pose.
   Must run before merging geografts if using the one-click flow.

2. **What it does**: Creates an internal copy of your character mesh (for the PoseBridge
   control panel display), merges geografts for animation performance, and remaps the
   body region highlight system so it works correctly on the merged mesh.

3. **Custom morfhs workflow**: If you want to add custom geograft morphs before merging,
   use the Advanced > Snapshot Pre-Merge State button first, then add your morphs, then
   merge, then use Remap Face Groups.

4. **What it doesn't touch**: Your character's pose, shape keys, materials, clothing,
   hair, or any other mesh objects. It only operates on the body mesh and armature.

5. **If something goes wrong**: The face group remap can be re-run at any time via
   Remap Face Groups. This is safe to run multiple times.

6. **Requirements**: Blender 5.0+, Diffeomorphic 5.0.0.2736+, Genesis 8/8.1/9 character.

---

## Open Questions

- [ ] Does Diffeomorphic 5.x expose a stable operator name for geograft merge?
      Need to verify: `bpy.ops.daz.merge_geografts` or similar
- [ ] Does the mannequin copy need the armature modifier applied (rest pose verts)
      or can we use un-applied positions? Currently strips shape keys but keeps armature.
      For face center matching, rest pose (un-deformed) positions are what matters.
- [ ] Genesis 9 compatibility — same DSF face group structure as G8?
      May need extended `DSF_GROUP_TO_BONE` mapping.
- [ ] Multi-character scenes — one init per armature, status stored per-scene?
      `PoseBridgeSettings` is scene-level so would need to store per-armature.

---

## Implementation Order

1. `FaceGroupManager.build_from_reference_mesh()` in `dsf_face_groups.py`
2. `init_character.py` — operators (start with Tier 1, add Tier 2 after)
3. `core.py` — add status properties to `PoseBridgeSettings`
4. `panel_ui.py` — Setup section UI
5. Manual documentation

---

## Related Files

| File | Role |
|------|------|
| `dsf_face_groups.py` | FaceGroupManager — add `build_from_reference_mesh()` |
| `projects/posebridge/init_character.py` | New — setup operators |
| `projects/posebridge/outline_generator_lineart.py` | Mannequin creation (called by init) |
| `projects/posebridge/setup_posebridge.py` | Existing setup — called after remap |
| `projects/posebridge/core.py` | Add init status properties |
| `projects/posebridge/panel_ui.py` | Add Setup section to N-panel |
| `daz_bone_select.py` | `find_base_body_mesh()` — used by prerequisite check |
