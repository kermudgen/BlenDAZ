# BlenDAZ Setup Flow — Complete Reference

This document defines every step that `setup_all.py` performs, in order, with
the rationale for each. Use it as the single source of truth when debugging
setup issues or modifying the script.

**Last Updated:** 2026-02-24

---

## Prerequisites

- Blender open with a Genesis 8/9 character (imported via Diffeomorphic)
- Character should be in **T-pose** (arms out, legs straight)
- BlenDAZ code at `D:\Dev\BlenDAZ`

### Diffeomorphic Import Requirements

When importing the character via Diffeomorphic, certain morph categories **must** be
included or features won't work:

| Morph Category | Required For | How to Import |
|---|---|---|
| **FACS morphs** (`facs_*`) | Face panel control points | Diffeomorphic → Import Morphs → select FACS/Facial |
| **Viseme morphs** | Lip-sync / viseme sliders | Diffeomorphic → Import Morphs → select Visemes |
| **Expression morphs** | Expression preset sliders | Diffeomorphic → Import Morphs → select Expressions |

**How to check if morphs are loaded:**
- Select armature → Properties panel → Object Properties → Custom Properties
- Look for properties starting with `facs_` (e.g., `facs_BrowDownLeft`, `facs_ctrl_MouthSmile`)
- If none exist, face control points will drag but have no visible effect

**How to import missing morphs after initial import:**
1. Select the armature
2. Open the **Diffeomorphic** panel (N-panel → Daz Importer tab)
3. Click **Import Morphs** (or **Add Morphs** depending on version)
4. Select the FACS / Facial / Expression morph categories
5. Click OK to import
6. Re-run `setup_all.py` to reconnect face control points

**Standin mesh** (`{Name}_Standin`): Required for hand panel extraction. If your scene
doesn't have a standin mesh, hand control points will be skipped. You can create one
manually by duplicating the body mesh and renaming it with a `_Standin` suffix.

---

## Configuration (setup_all.py top section)

| Variable | Default | Purpose |
|---|---|---|
| `ARMATURE_NAME` | `None` (auto-detect) | Override armature name |
| `SKIP_POSEBRIDGE` | `False` | Skip PoseBridge registration entirely |
| `SKIP_POSEBLEND` | `False` | Skip PoseBlend registration entirely |
| `RELOAD_MODULES` | `True` | Force-reload all modules (picks up code changes) |
| `STANDIN_NAME` | `None` (auto-detect) | Standin mesh for hand extraction |
| `OUTLINE_Z_OFFSET` | `-50.0` | Z position for outline/mannequin/camera/light |
| `HAND_Z_OFFSET` | `-53.0` | Z position for hand camera (below outline) |
| `GENERATE_OUTLINE` | `True` | Generate Line Art outline if it doesn't exist |
| `FORCE_REGENERATE_OUTLINE` | `False` | Delete existing outline and rebuild from scratch |
| `SETUP_HANDS` | `True` | Extract hand geometry + control points |
| `SETUP_FACE` | `True` | Extract face control points |

---

## Step 0: Path Setup & Armature Detection

**What happens:**
1. Add `D:\Dev\BlenDAZ`, `projects/`, `projects/posebridge/` to `sys.path`
2. Auto-detect DAZ armature by looking for bone markers (`lPectoral`, `rPectoral`, `lCollar`, `rCollar`)
   - Checks active object first, then searches all scene armatures
3. Select armature, switch to **Pose mode**

**Can fail if:** No DAZ armature in scene. Fix: set `ARMATURE_NAME` manually.

---

## Step 1: Register daz_bone_select

**What happens:**
1. If `RELOAD_MODULES`: unregister existing, purge from `sys.modules`, reload `daz_shared_utils`
2. `import daz_bone_select` → `importlib.reload()` → `daz_bone_select.register()`
3. Verify `bpy.ops.view3d.daz_bone_select` exists

**Registers:**
- `DAZ_OT_bone_select` — main modal operator (bone hover, click-rotate, IK, pins, PowerPose)
- `DAZ_OT_face_controls` — face morph panel
- `DAZ_OT_clear_ik_pose` — reset pose operator

**Source:** `D:\Dev\BlenDAZ\daz_bone_select.py`

---

## Step 2: Register PoseBridge

### Step 2a: Module Registration

**What happens:**
1. If `RELOAD_MODULES`: unregister, force-delete `bpy.types.Scene.posebridge_settings`, purge all `posebridge.*` from `sys.modules`
2. Reload submodules in dependency order: `core`, `control_points`, `outline_generator`, `interaction`, `drawing`, `panel_ui`, `presets`
3. `posebridge.register()` — creates `posebridge_settings` PropertyGroup on Scene
4. Set `is_active = True`, `active_armature_name`, `show_control_points = True`
5. Register `PoseBridgeDrawHandler` (GPU overlay for control points)

**Source:** `D:\Dev\BlenDAZ\projects\posebridge\__init__.py` and submodules

### Step 2b: Force Regenerate (optional)

**Only runs if `FORCE_REGENERATE_OUTLINE = True`.**

Deletes all existing outline objects so they get recreated fresh:
- `PB_Outline_LineArt` (GP object)
- `PB_Outline_LineArt_Camera`
- `PB_Outline_LineArt_Light`
- Any `*_LineArt_Copy` mesh objects (mannequin)
- `PB_Outline_LineArt_TempCollection`

**When to use:** After changing characters, fixing wrong mesh selection, or if outline is corrupted.

### Step 2c: Diagnostics

**Always runs.** Prints all mesh children of the armature sorted by vertex count, showing which one would be selected and why. Also shows what mesh the existing outline was built from (if any).

### Step 2d: Generate Outline

**Only runs if outline doesn't already exist and `GENERATE_OUTLINE = True`.**

1. **Find body mesh** via `find_character_mesh()`:
   - Priority 1: Mesh named exactly `"{ArmatureName} Mesh"` (DAZ convention)
   - Priority 2: Mesh whose name starts with armature name
   - Priority 3: Largest mesh by vertex count (fallback)
2. **Switch to Object mode** (required for GP creation)
3. **Select the body mesh** (outline generator needs it as active object)
4. **Call `create_genesis8_lineart_outline(mesh_obj, outline_name)`**

   This function does the following internally:
   1. **Copy mesh** → `{MeshName}_LineArt_Copy` (the "mannequin")
   2. **Create temp collection** `PB_Outline_LineArt_TempCollection`, move copy there
   3. **Exclude original collection** from view layer (temporarily, for clean Line Art)
   4. **Create orthographic camera** `PB_Outline_LineArt_Camera` at Y=-12, Z=58% of character height
   5. **Create point light** `PB_Outline_LineArt_Light` at same position, 50W
   6. **Create GP Line Art object** `PB_Outline_LineArt` using `grease_pencil_add(type='LINEART_OBJECT')`
   7. **Configure Line Art modifier**: source=mesh copy, custom camera, silhouette edges only
   8. **Apply Line Art modifier** (bakes strokes — outline becomes static geometry)
   9. **Flatten GP** (Y-scale = 0, makes it a 2D front-view silhouette)
   10. **Convert mesh copy to mannequin**: remove all modifiers, apply gray material, unlock transforms
   11. **Re-enable original collection**
   12. **Capture body control points** at Z=0 (initial capture, will be recaptured after move)

5. **Restore Pose mode** with armature selected

**Objects created:**
| Object | Type | Purpose |
|---|---|---|
| `PB_Outline_LineArt` | Grease Pencil | Cyan silhouette outline (static, flattened) |
| `PB_Outline_LineArt_Camera` | Camera (ortho) | Camera for the control panel viewport |
| `PB_Outline_LineArt_Light` | Point Light | Lighting for mannequin |
| `{Mesh}_LineArt_Copy` | Mesh | Gray mannequin (silhouette background for control points) |
| `PB_Outline_LineArt_TempCollection` | Collection | Contains the mannequin mesh copy |

### Step 2e: Move Everything to Z Offset

**Runs if outline exists (newly created or pre-existing).**

Sets **absolute** Z position on all PoseBridge objects (idempotent, safe to run multiple times):

```
PB_Outline_LineArt.location.z         = -50.0
PB_Outline_LineArt_Camera.location.z  = -50.0
PB_Outline_LineArt_Light.location.z   = -50.0
{Mesh}_LineArt_Copy.location.z        = -50.0   (mannequin in TempCollection)
```

**Why -50m?** Separates the control panel from the live character so they don't overlap visually. The control panel lives 50 meters below the character. Users view it through the PB camera in one viewport while seeing the live mesh in another.

**Why absolute, not relative?** Relative offsets (`+=`) are not idempotent — running the script twice would move to -100m. Absolute positioning always puts things in the right place.

### Step 2f: Recapture Body Control Points

**Runs after the Z move.** Calls `capture_fixed_control_points(armature, outline_name)`.

This function:
1. Reads the outline object's Z position (now -50.0)
2. Calculates `z_offset = outline_z - armature_z` (= -50.0 - 0.0 = -50.0)
3. **Clears ALL existing control points** (`control_points_fixed.clear()`)
4. For each bone defined in `get_genesis8_control_points()`:
   - Gets bone world position from armature (at Z=0)
   - Adds z_offset (-50.0) to get final position at Z=-50
   - Stores as fixed control point
5. Returns count (typically 23 body + 15 extra = 38)

**IMPORTANT:** This clears ALL CPs. Body must be captured FIRST, then hands and face append to the list.

### Step 2g: Hand Extraction (optional)

**Only runs if `SETUP_HANDS = True` and a standin mesh exists.**

1. Find standin mesh (auto-detect `*_Standin` or `*_LineArt_Copy`, or use `STANDIN_NAME`)
2. Call `extract_hands.extract_and_setup_hands(standin, z_offset=-53.0)`
   - Extracts left/right hand geometry from standin using vertex groups
   - Creates `PB_Hand_Left`, `PB_Hand_Right` meshes
   - Creates `PB_Camera_Hands` at Z=-53m
3. Call `extract_hands.store_hand_control_points(hand_result)`
   - **Appends** 42 hand CPs to the existing list (21 per hand)
   - Does NOT clear existing body CPs

**Objects created:**
| Object | Type | Purpose |
|---|---|---|
| `PB_Hand_Left` | Mesh | Left hand mesh (dorsal view) |
| `PB_Hand_Right` | Mesh | Right hand mesh (dorsal view) |
| `PB_Camera_Hands` | Camera | Camera for hand panel view |

### Step 2h: Face Extraction (optional)

**Only runs if `SETUP_FACE = True`.**

1. Call `extract_face.setup_face_panel(armature_obj)`
   - Creates `PB_Camera_Face` parented to head bone
   - Calculates 22 face control point positions from bone/morph locations
   - **Appends** face CPs to the existing list
2. Face controls map to FACS morph properties on the armature

**IMPORTANT:** Face control points will be created and positioned regardless of whether
FACS morphs are loaded. However, **dragging face CPs has no visible effect unless the
`facs_*` custom properties exist on the armature** (imported via Diffeomorphic). The
setup script warns about missing properties:
```
WARNING: 51 FACS properties not found on armature:
  - facs_BrowDownLeft
  ...
These controls will have no effect until the properties are loaded.
```
See **Prerequisites → Diffeomorphic Import Requirements** above for how to import them.

**Objects created:**
| Object | Type | Purpose |
|---|---|---|
| `PB_Camera_Face` | Camera | Camera for face panel view (follows head) |

---

## Step 3: Register PoseBlend

**What happens:**
1. If `RELOAD_MODULES`: unregister, force-delete `bpy.types.Scene.poseblend_settings`, purge all `poseblend.*`
2. Reload submodules: `core`, `presets`, `poses`, `blending`, `grid`, `viewport_setup`, `drawing`, `interaction`, `panel_ui`, `import_export`
3. `poseblend.register()` — creates `poseblend_settings` PropertyGroup
4. Set `is_active = True`, `active_armature_name`

**Source:** `D:\Dev\BlenDAZ\projects\poseblend\__init__.py` and submodules

---

## Step 4: Activate Modal Operator

**What happens:**
1. Select armature, ensure Pose mode
2. Find a 3D viewport via `find_3d_view()` (searches all windows/areas)
3. `bpy.ops.view3d.daz_bone_select('INVOKE_DEFAULT')` with `temp_override`

**This starts:**
- Bone hover detection (highlights bones under cursor)
- Click-drag rotation (PowerPose-style 4-way controls)
- IK dragging (G key)
- Pin system (P/Shift+P/U keys)
- Face group parsing (loads DSF bone-to-face mapping)
- Quaternion mode conversion for all bones

---

## Step 5: Summary

Prints component list with control point counts by panel (body/hands/face) and control instructions.

---

## Object Hierarchy (after full setup)

```
Scene Collection
├── {Armature}                        ← Live character (Z=0)
│   ├── {Body Mesh}
│   ├── {Hair Mesh}
│   ├── {Clothing Meshes}
│   └── {Accessory Meshes}
├── PB_Outline_LineArt                ← GP silhouette (Z=-50)
├── PB_Outline_LineArt_Camera         ← Body panel camera (Z=-50)
├── PB_Outline_LineArt_Light          ← Body panel light (Z=-50)
├── PB_Outline_LineArt_TempCollection
│   └── {Mesh}_LineArt_Copy           ← Gray mannequin (Z=-50)
├── PB_Hand_Left                      ← Hand mesh (Z=-53)
├── PB_Hand_Right                     ← Hand mesh (Z=-53)
├── PB_Camera_Hands                   ← Hand panel camera (Z=-53)
└── PB_Camera_Face                    ← Face panel camera (parented to head bone)
```

---

## Control Points Summary

| Panel | Count | Source | Capture Function |
|---|---|---|---|
| Body | ~38 | `get_genesis8_control_points()` in `daz_shared_utils` | `capture_fixed_control_points()` — **CLEARS ALL CPs first** |
| Hands | 42 (21/hand) | `extract_hands.store_hand_control_points()` | **Appends** to existing |
| Face | 22 | `extract_face.setup_face_panel()` | **Appends** to existing |

**Capture order matters:** Body MUST be first (it clears the list), then hands, then face.

---

## Viewport Layout (for interactive posing)

```
┌─────────────────────────┬─────────────────────────┐
│                         │                         │
│   LEFT VIEWPORT         │   RIGHT VIEWPORT        │
│   (Camera View)         │   (Free 3D View)        │
│                         │                         │
│   PB_Outline_Camera     │   Normal perspective    │
│   Shows: mannequin +    │   Shows: live character │
│   control points at     │   mesh at Z=0           │
│   Z=-50                 │                         │
│                         │                         │
│   Click/drag CPs here   │   See results here      │
│                         │                         │
└─────────────────────────┴─────────────────────────┘
```

---

## Troubleshooting

### Wrong mesh selected for outline
- Check diagnostics output: "Mesh candidates for ..."
- The script prefers `{ArmatureName} Mesh` by name, then falls back to largest vertex count
- Override: set `FORCE_REGENERATE_OUTLINE = True` and verify the correct mesh is selected

### Control points at Z=0 (on top of live character)
- Outline/camera/light/mannequin all need to be at Z=-50
- Check that Step 2e ran (look for "Positioned at Z=-50.0m" in console)
- Check that Step 2f ran AFTER the move (look for "captured at Z=-50.0m")

### No outline visible in camera view
- Switch left viewport to camera view (Numpad 0) using `PB_Outline_LineArt_Camera`
- Check `PB_Outline_LineArt` visibility in Outliner (eye icon)
- Check mannequin mesh visibility in `PB_Outline_LineArt_TempCollection`

### Face control points don't do anything when dragged
- FACS morph properties (`facs_*`) are not loaded on the armature
- These come from Diffeomorphic morph import, NOT from BlenDAZ
- Check: select armature → Properties → Custom Properties → look for `facs_` keys
- Fix: import FACS morphs via Diffeomorphic (see Prerequisites section)
- The setup script will print a warning listing all missing FACS properties

### Hand extraction fails
- Needs a standin mesh with hand vertex groups (`lHand`, `lThumb1`, etc.)
- If no standin exists, hands are skipped silently
- The mannequin `{Mesh}_LineArt_Copy` does NOT have vertex groups (modifiers stripped)

### context.area is None errors
- Happens when switching workspaces while modal operator is running
- All `context.area.header_text_set()` and `context.area.tag_redraw()` calls are guarded
- If you find a new one, add `if context.area:` guard

### Module reload issues
- Set `RELOAD_MODULES = True` (default) to pick up code changes
- If weird state: restart Blender for a clean slate
- `purge_modules('posebridge')` removes all cached submodules from `sys.modules`

---

## Known Bugs

### Unpin Pose Preservation
When unpinning a bone, the visual pose jumps instead of being preserved.
Three approaches failed (constraint bake, delta rotation, matrix decomposition).
See `docs/SCRATCHPAD.md` for details and possible next approaches.
