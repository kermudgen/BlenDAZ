"""PoseBridge Line Art Outline Generator - Uses Blender's Line Art modifier"""

import bpy
from mathutils import Vector


# ============================================================================
# Collection utilities (shared by outline_generator, extract_hands, extract_face)
# ============================================================================

def _find_layer_collection(layer_coll, name):
    """Recursively find a layer collection by collection name."""
    if layer_coll.collection.name == name:
        return layer_coll
    for child in layer_coll.children:
        found = _find_layer_collection(child, name)
        if found:
            return found
    return None


def get_or_create_pb_collection(char_name, sub=None):
    """Return (and create if needed) a PoseBridge collection for a character.

    Args:
        char_name: Short armature name, e.g. 'Fey'
        sub:       Optional sub-collection suffix, e.g. 'Stage' or 'Hands'.
                   If given, returns PB_{char}_{sub} nested inside PB_{char}.

    Returns:
        The target bpy.types.Collection, ensured to be visible in the view layer.
    """
    scene = bpy.context.scene

    # --- root: PB_{char} ---
    root_name = f"PB_{char_name}"
    if root_name in bpy.data.collections:
        root_coll = bpy.data.collections[root_name]
    else:
        root_coll = bpy.data.collections.new(root_name)
        scene.collection.children.link(root_coll)

    _ensure_collection_visible(root_name)

    if sub is None:
        return root_coll

    # --- child: PB_{char}_{sub} ---
    child_name = f"PB_{char_name}_{sub}"
    if child_name in bpy.data.collections:
        child_coll = bpy.data.collections[child_name]
        # Ensure it's a child of root (not floating)
        if child_name not in [c.name for c in root_coll.children]:
            # Unlink from wherever it is, re-link under root
            for parent in list(child_coll.users_collection if hasattr(child_coll, 'users_collection') else []):
                try:
                    parent.children.unlink(child_coll)
                except Exception:
                    pass
            try:
                root_coll.children.link(child_coll)
            except Exception:
                pass
    else:
        child_coll = bpy.data.collections.new(child_name)
        root_coll.children.link(child_coll)

    _ensure_collection_visible(child_name)
    return child_coll


def _ensure_collection_visible(coll_name):
    """Make sure a collection is not excluded or hidden in the view layer."""
    lc = _find_layer_collection(bpy.context.view_layer.layer_collection, coll_name)
    if lc:
        lc.exclude = False
        lc.hide_viewport = False


def move_object_to_collection(obj, target_coll):
    """Move obj from all current collections into target_coll."""
    for coll in list(obj.users_collection):
        coll.objects.unlink(obj)
    target_coll.objects.link(obj)


def capture_fixed_control_points(armature, outline_name="PB_Outline_LineArt"):
    """Capture fixed 3D positions of control points from T-pose

    Args:
        armature: Armature object in T-pose
        outline_name: Name of the outline GP object

    Returns:
        Number of control points captured
    """
    import sys
    import os

    # Add BlenDAZ and projects to path
    blendaz_path = r"D:\dev\BlenDAZ"
    projects_path = r"D:\dev\BlenDAZ\projects"
    if blendaz_path not in sys.path:
        sys.path.insert(0, blendaz_path)
    if projects_path not in sys.path:
        sys.path.insert(0, projects_path)

    # ENSURE POSEBRIDGE IS REGISTERED
    if not hasattr(bpy.context.scene, 'posebridge_settings'):
        print("⚠ PoseBridge not registered, registering now...")
        import posebridge
        posebridge.register()
        print("✓ PoseBridge registered")

    from daz_shared_utils import get_genesis8_control_points

    # Get control point definitions
    control_points_defs = get_genesis8_control_points()

    # Calculate Z offset (same as drawing code)
    z_offset = 0.0
    outline = bpy.data.objects.get(outline_name)
    if outline:
        armature_z = armature.matrix_world.translation.z
        outline_z = outline.location.z
        z_offset = outline_z - armature_z

    # Clear existing fixed control points
    bpy.context.scene.posebridge_settings.control_points_fixed.clear()

    # Capture positions
    count = 0
    for cp_def in control_points_defs:
        # Skip hidden/virtual entries (e.g. twist bones that are delegates of shoulder/forearm)
        if cp_def.get('hidden'):
            continue

        # Handle both single bone and multi-bone groups
        if 'bone_names' in cp_def:
            # Multi-bone group - use reference_bone if specified, otherwise first bone
            bone_names = cp_def['bone_names']

            # Check for explicit reference_bone for positioning
            if 'reference_bone' in cp_def:
                bone_name = cp_def['reference_bone']
                if bone_name not in armature.pose.bones:
                    continue
            else:
                # Fall back to first bone in list
                if not bone_names or bone_names[0] not in armature.pose.bones:
                    continue
                bone_name = bone_names[0]

            pose_bone = armature.pose.bones[bone_name]
        else:
            # Single bone
            bone_name = cp_def.get('bone_name', '')
            if not bone_name or bone_name not in armature.pose.bones:
                continue
            pose_bone = armature.pose.bones[bone_name]
            bone_names = None  # Not a multi-bone group

        # Get bone 3D position in T-pose (world space)
        # Support 'position' property: 'head' (default), 'tail', or 'mid'
        bone_position = cp_def.get('position', 'head')
        if bone_position == 'tail':
            bone_pos_world = armature.matrix_world @ pose_bone.tail
        elif bone_position == 'mid':
            mid_local = (pose_bone.head + pose_bone.tail) / 2
            bone_pos_world = armature.matrix_world @ mid_local
        else:  # 'head' or default
            bone_pos_world = armature.matrix_world @ pose_bone.head

        # Apply offset if specified (for group controls positioned away from bone)
        offset = cp_def.get('offset', (0, 0, 0))
        position_offset = Vector(offset)

        # Apply Z offset to match outline location and position offset
        fixed_pos_3d = Vector((
            bone_pos_world.x + position_offset.x,
            bone_pos_world.y + position_offset.y,
            bone_pos_world.z + z_offset + position_offset.z
        ))

        # Store in settings
        cp = bpy.context.scene.posebridge_settings.control_points_fixed.add()
        cp.bone_name = bone_name  # Primary bone for single controls
        cp.id = cp_def['id']
        cp.label = cp_def.get('label', bone_name)
        cp.group = cp_def.get('group', '')
        cp.position_3d_fixed = fixed_pos_3d

        # Store additional properties for rendering
        if 'shape' in cp_def:
            cp.control_type = 'multi'  # Mark as multi-bone control
        if bone_names:
            # Keep the human-readable label (set above from cp_def)
            # Bone names are looked up from definitions at runtime by control point ID
            pass

        count += 1

    print(f"✓ Captured {count} fixed control point positions from T-pose")
    return count


def move_posebridge_setup(outline_name="PB_Outline_LineArt", offset_z=-30.0):
    """
    Move the PoseBridge camera and outline to an offset location

    Args:
        outline_name: Name of the outline GP object (must match outline generator)
        offset_z: Z-axis offset in meters (negative moves down)
    """

    # Find the PoseBridge camera
    camera_name = f"{outline_name}_Camera"
    camera = bpy.data.objects.get(camera_name)

    if not camera:
        print(f"❌ Camera '{camera_name}' not found.")
        return None, None

    # Find the PoseBridge outline
    outline = bpy.data.objects.get(outline_name)

    if not outline:
        print(f"❌ Outline '{outline_name}' not found.")
        return camera, None

    # Find the light
    light_name = f"{outline_name}_Light"
    light = bpy.data.objects.get(light_name)

    # Move camera
    original_camera_z = camera.location.z
    camera.location.z += offset_z
    print(f"✓ Moved camera from Z={original_camera_z:.2f} to Z={camera.location.z:.2f}")

    # Move outline
    original_outline_z = outline.location.z
    outline.location.z += offset_z
    print(f"✓ Moved outline from Z={original_outline_z:.2f} to Z={outline.location.z:.2f}")

    # Move light if it exists
    if light:
        original_light_z = light.location.z
        light.location.z += offset_z
        print(f"✓ Moved light from Z={original_light_z:.2f} to Z={light.location.z:.2f}")

    return camera, outline


def create_genesis8_lineart_outline(mesh_obj, outline_name="PB_Outline_LineArt", char_tag=None):
    """Generate a Grease Pencil outline using Line Art modifier

    Args:
        mesh_obj: Genesis 8 mesh object
        outline_name: Name for the GP object (overridden by char_tag if provided)
        char_tag: Optional character tag for multi-character naming.
                  When set, outline_name becomes PB_Outline_{char_tag},
                  camera becomes PB_Camera_Body_{char_tag}, etc.

    Returns:
        Grease Pencil object or None if failed
    """
    # Multi-character naming: derive all names from char_tag
    if char_tag:
        outline_name = f"PB_Outline_{char_tag}"
    if not mesh_obj or mesh_obj.type != 'MESH':
        print("Error: Invalid mesh object")
        return None

    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Set render engine to EEVEE (required for LineArt modifier)
    if bpy.context.scene.render.engine != 'BLENDER_EEVEE':
        print("Setting render engine to EEVEE (required for LineArt)")
        bpy.context.scene.render.engine = 'BLENDER_EEVEE'

    # Enable film transparency for clean background
    bpy.context.scene.render.film_transparent = True

    # Set Grease Pencil antialias quality
    if hasattr(bpy.context.scene.grease_pencil_settings, 'antialias_threshold'):
        bpy.context.scene.grease_pencil_settings.antialias_threshold = 1.0

    print(f"\n{'='*60}")
    print(f"Starting Line Art Outline Generation")
    print(f"{'='*60}")

    # STEP 1: Copy mesh
    print("Step 1: Copying mesh...")
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.duplicate()
    mesh_copy = bpy.context.active_object
    mesh_copy.name = f"{mesh_obj.name}_LineArt_Copy"
    print(f"  Created mesh copy: {mesh_copy.name}")

    # Strip shape keys (JCMs, flexions, FACS blendshapes) — mannequin is geometry-only
    if mesh_copy.data.shape_keys:
        sk_count = len(mesh_copy.data.shape_keys.key_blocks)
        mesh_copy.shape_key_clear()
        print(f"  Stripped {sk_count} shape keys from mannequin")

    # Remove non-essential modifiers (keep only Armature so it follows the pose)
    removed_mods = []
    for mod in list(mesh_copy.modifiers):
        if mod.type != 'ARMATURE':
            removed_mods.append(f"{mod.name} ({mod.type})")
            mesh_copy.modifiers.remove(mod)
    if removed_mods:
        print(f"  Removed {len(removed_mods)} modifiers: {', '.join(removed_mods[:5])}"
              f"{'...' if len(removed_mods) > 5 else ''}")

    # STEP 2: Create temp collection and move copied mesh
    print("Step 2: Moving mesh to temp collection...")
    temp_collection_name = f"{outline_name}_TempCollection"
    if temp_collection_name in bpy.data.collections:
        temp_collection = bpy.data.collections[temp_collection_name]
    else:
        temp_collection = bpy.data.collections.new(temp_collection_name)
        bpy.context.scene.collection.children.link(temp_collection)

    # CRITICAL: Ensure temp collection itself is enabled in viewport
    # Find the layer collection for temp_collection
    def find_layer_collection_for_temp(layer_coll, coll_name):
        """Recursively find layer collection by name"""
        if layer_coll.collection.name == coll_name:
            return layer_coll
        for child in layer_coll.children:
            found = find_layer_collection_for_temp(child, coll_name)
            if found:
                return found
        return None

    temp_layer_coll = find_layer_collection_for_temp(
        bpy.context.view_layer.layer_collection,
        temp_collection_name
    )

    if temp_layer_coll:
        # Ensure collection is NOT excluded and IS visible
        temp_layer_coll.exclude = False
        temp_layer_coll.hide_viewport = False
        print(f"  Ensured temp collection is enabled: exclude={temp_layer_coll.exclude}, hide={temp_layer_coll.hide_viewport}")
    else:
        print(f"  Warning: Could not find layer collection for temp collection")

    # Ensure collection-level viewport visibility
    temp_collection.hide_viewport = False
    temp_collection.hide_render = False

    # Remove mesh from all collections and add to temp collection
    for coll in list(mesh_copy.users_collection):  # Use list() to avoid modification during iteration
        coll.objects.unlink(mesh_copy)
    temp_collection.objects.link(mesh_copy)

    # CRITICAL: Ensure mesh copy is fully visible and enabled
    mesh_copy.hide_viewport = False
    mesh_copy.hide_render = False
    mesh_copy.hide_set(False)
    mesh_copy.hide_select = False

    # Ensure viewport display is enabled
    if hasattr(mesh_copy, 'display_type'):
        # Don't change display type, but ensure it's not 'BOUNDS' or 'WIRE'
        if mesh_copy.display_type in ('BOUNDS', 'WIRE'):
            mesh_copy.display_type = 'TEXTURED'

    # Make absolutely sure it's visible in viewport
    if hasattr(mesh_copy, 'visible_get'):
        print(f"  Mesh copy visible_get(): {mesh_copy.visible_get()}")

    print(f"  Moved to collection: {temp_collection.name}")
    print(f"  Collection visibility: viewport={not temp_collection.hide_viewport}, render={not temp_collection.hide_render}")
    if temp_layer_coll:
        print(f"  Layer collection: exclude={temp_layer_coll.exclude}, hide_viewport={temp_layer_coll.hide_viewport}")
    print(f"  Mesh copy visibility: viewport={not mesh_copy.hide_viewport}, hidden={not mesh_copy.hide_get()}, selectable={not mesh_copy.hide_select}")

    # STEP 3: Exclude original collection from view layer (CRUCIAL!)
    print("Step 3: Excluding original collection from view layer...")
    original_collection = None
    for coll in mesh_obj.users_collection:
        if coll != temp_collection:
            original_collection = coll
            break

    if original_collection:
        # Recursively find the layer collection
        def find_layer_collection(layer_coll, coll_name):
            """Recursively find layer collection by name"""
            if layer_coll.collection.name == coll_name:
                return layer_coll
            for child in layer_coll.children:
                found = find_layer_collection(child, coll_name)
                if found:
                    return found
            return None

        layer_coll = find_layer_collection(
            bpy.context.view_layer.layer_collection,
            original_collection.name
        )

        if layer_coll:
            # Exclude from view layer (the checkbox in outliner)
            layer_coll.exclude = True
            print(f"  ✓ Excluded collection '{original_collection.name}' from view layer")
        else:
            print(f"  ✗ Warning: Could not find layer collection for '{original_collection.name}'")

    # Calculate character height FIRST (needed for camera position)
    # Get bounding box height of mesh copy
    bbox = mesh_copy.bound_box
    bbox_coords = [mesh_copy.matrix_world @ Vector(corner) for corner in bbox]
    min_z = min(coord.z for coord in bbox_coords)
    max_z = max(coord.z for coord in bbox_coords)
    character_height = max_z - min_z
    print(f"  Character height: {character_height:.2f}m")

    # Find armature to get character center position
    armature = None
    for mod in mesh_obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object:
            armature = mod.object
            break

    # Get character center position (use pelvis X/Y, calculated Z)
    if armature and 'pelvis' in armature.pose.bones:
        pelvis_pos = armature.matrix_world @ armature.pose.bones['pelvis'].head
        character_center_x = pelvis_pos.x
        character_center_y = pelvis_pos.y
    else:
        character_center_x = mesh_obj.location.x
        character_center_y = mesh_obj.location.y

    # Calculate optimal camera Z height based on character height
    # Formula: camera_z = character_height × 0.58
    # (derived from Fey: 1.24m tall, camera at 0.72m = 58% of height)
    camera_z = character_height * 0.58

    # STEP 4: Create camera 12 units in front at calculated height, rotated 90° on X
    print("Step 4: Creating camera...")
    camera_name = f"PB_Camera_Body_{char_tag}" if char_tag else f"{outline_name}_Camera"
    if camera_name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[camera_name], do_unlink=True)

    camera_data = bpy.data.cameras.new(camera_name)

    # Set camera to orthographic for flat 2D view (no perspective distortion)
    camera_data.type = 'ORTHO'
    # ortho_scale = visible width in scene units. Derive from character bounding box:
    # use the wider of (character width × 1.4) or (character height × 0.9) so the
    # figure fits with comfortable margin regardless of body proportions.
    min_x = min(coord.x for coord in bbox_coords)
    max_x = max(coord.x for coord in bbox_coords)
    character_width = max_x - min_x
    ortho_scale = max(character_width * 1.4, character_height * 0.9)
    camera_data.ortho_scale = ortho_scale
    print(f"  ortho_scale: {ortho_scale:.3f} (width={character_width:.2f}m, height={character_height:.2f}m)")

    # Determine PB Stage collection for this character
    char_name = armature.name if armature else mesh_obj.name.replace(' Mesh', '').replace('_Mesh', '')
    stage_coll = get_or_create_pb_collection(char_name, 'Stage')

    camera = bpy.data.objects.new(camera_name, camera_data)
    stage_coll.objects.link(camera)

    # Position camera 12 units in front (negative Y), at calculated Z height
    camera.location = Vector((character_center_x, character_center_y - 12, camera_z))
    camera.rotation_euler = (1.5708, 0, 0)  # 90 degrees on X axis
    print(f"  Camera at: {camera.location} (Z = {camera_z:.2f}m = 58% of height)")
    print(f"  Camera type: ORTHOGRAPHIC (ortho_scale = 5.0)")

    # STEP 5: Create light at same location, power 50
    print("Step 5: Creating light...")
    light_name = f"PB_Light_{char_tag}" if char_tag else f"{outline_name}_Light"
    if light_name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[light_name], do_unlink=True)

    light_data = bpy.data.lights.new(light_name, 'POINT')
    light_data.energy = 50  # Power 50 (not 1000!)
    light = bpy.data.objects.new(light_name, light_data)
    stage_coll.objects.link(light)
    light.location = camera.location.copy()
    print(f"  Light power: {light_data.energy}W")

    # STEP 6: Select copied mesh object
    print("Step 6: Selecting copied mesh...")
    bpy.ops.object.select_all(action='DESELECT')
    mesh_copy.select_set(True)
    bpy.context.view_layer.objects.active = mesh_copy

    # STEP 7: Create Grease Pencil using Blender's LINEART_OBJECT operator
    print("Step 7: Creating Grease Pencil Line Art...")
    if bpy.app.version >= (5, 0, 0):
        bpy.ops.object.grease_pencil_add(type='LINEART_OBJECT')
    else:
        # Blender 3.x-4.x uses generic 'LINEART' type
        bpy.ops.object.grease_pencil_add(type='LINEART')

    # Get the newly created GP object (it's now the active object)
    gp_obj = bpy.context.active_object
    if not gp_obj or gp_obj.type != 'GREASEPENCIL':
        print("Error: Failed to create GP Line Art object")
        return None

    # Rename the GP object
    gp_obj.name = outline_name
    gp_data = gp_obj.data
    gp_data.name = outline_name

    # Get the Line Art modifier (automatically created by the operator)
    lineart_mod = None
    if bpy.app.version >= (5, 0, 0):
        for mod in gp_obj.modifiers:
            if mod.type == 'LINEART':
                lineart_mod = mod
                break
    else:
        for mod in gp_obj.grease_pencil_modifiers:
            if mod.type == 'GP_LINEART':
                lineart_mod = mod
                break

    if not lineart_mod:
        print("Error: Line Art modifier not found on GP object")
        return None

    print(f"  Configuring Line Art modifier...")

    # Configure modifier for silhouette/outline - use copied mesh
    lineart_mod.source_type = 'OBJECT'
    lineart_mod.source_object = mesh_copy

    # Set custom camera (required for stroke generation)
    lineart_mod.use_custom_camera = True
    lineart_mod.source_camera = camera

    # Get the auto-created layer and material for debug output
    gp_layer = gp_data.layers[0] if len(gp_data.layers) > 0 else None
    mat = gp_data.materials[0] if len(gp_data.materials) > 0 else None
    mat_index = 0 if mat else -1

    # Customize material color to cyan
    if mat and mat.use_nodes and mat.node_tree:
        nodes = mat.node_tree.nodes
        # Find existing emission or principled node
        for node in nodes:
            if node.type == 'EMISSION':
                node.inputs['Color'].default_value = (0, 0.8, 1, 1)  # Cyan
                node.inputs['Strength'].default_value = 1.5
            elif node.type == 'BSDF_PRINCIPLED':
                node.inputs['Base Color'].default_value = (0, 0.8, 1, 1)  # Cyan

    # Edge Types - ONLY Silhouette (critical for clean outline)
    lineart_mod.use_edge_mark = False
    lineart_mod.use_material = False

    # Silhouette ONLY - all other edge types disabled
    if hasattr(lineart_mod, 'use_contour'):
        lineart_mod.use_contour = True  # Silhouette edges

    if hasattr(lineart_mod, 'use_intersection'):
        lineart_mod.use_intersection = False  # Disabled

    if hasattr(lineart_mod, 'use_loose'):
        lineart_mod.use_loose = False  # Disabled

    lineart_mod.use_crease = False  # Disabled

    # Geometry Processing - Apply discovered optimal settings
    if hasattr(lineart_mod, 'use_invert_collection'):
        lineart_mod.use_invert_collection = False

    if hasattr(lineart_mod, 'use_instancing'):
        lineart_mod.use_instancing = True  # Instanced Objects

    if hasattr(lineart_mod, 'use_clip_plane_boundaries'):
        lineart_mod.use_clip_plane_boundaries = True  # Clipping Boundaries

    if hasattr(lineart_mod, 'use_crease_on_smooth'):
        lineart_mod.use_crease_on_smooth = True  # Crease On Sharp

    if hasattr(lineart_mod, 'use_back_face_culling'):
        lineart_mod.use_back_face_culling = True  # Force Backface Culling

    if hasattr(lineart_mod, 'use_edge_overlap'):
        lineart_mod.use_edge_overlap = True  # Keep Contour

    # Chaining - Intersection With Contour
    if hasattr(lineart_mod, 'use_loose_edge_chain'):
        lineart_mod.use_loose_edge_chain = True

    if hasattr(lineart_mod, 'use_geometry_space_chain'):
        lineart_mod.use_geometry_space_chain = True

    if hasattr(lineart_mod, 'chaining_image_threshold'):
        lineart_mod.chaining_image_threshold = 0.01

    # Calculate Line Radius based on character height
    # Formula derived from user data: Fey (1.24m → 0.004), Finn (1.89m → 0.006)
    # Linear relationship: radius ≈ height * 0.00323
    line_radius = character_height * 0.00323
    print(f"  Calculated Line Radius: {line_radius:.4f}")

    # Thickness and Radius
    if hasattr(lineart_mod, 'thickness'):
        lineart_mod.thickness = 4  # Line thickness in pixels

    if hasattr(lineart_mod, 'stroke_depth_offset'):
        lineart_mod.stroke_depth_offset = line_radius  # Dynamic based on character size

    # Overscan - captures edges beyond frame
    if hasattr(lineart_mod, 'overscan'):
        lineart_mod.overscan = 0.1

    # Silhouette Filtering - CRITICAL! Set to GROUP
    if hasattr(lineart_mod, 'silhouette_filtering'):
        lineart_mod.silhouette_filtering = 'GROUP'

    # Level Start/End - multiple depth levels
    if hasattr(lineart_mod, 'level_start'):
        lineart_mod.level_start = 0
    if hasattr(lineart_mod, 'level_end'):
        lineart_mod.level_end = 6

    # Target layer and material (Blender 5.0 GP v3 handles this differently)
    if bpy.app.version >= (5, 0, 0):
        # Blender 5.0: Line Art with GP v3 automatically uses GP object's layers and materials
        print("Blender 5.0 detected: Line Art will automatically use GP layers and materials")
    else:
        # Blender 3.x-4.x: Need to explicitly set target layer and material
        if hasattr(lineart_mod, 'target_layer'):
            try:
                if hasattr(gp_layer, 'info'):
                    lineart_mod.target_layer = gp_layer.info
                else:
                    lineart_mod.target_layer = gp_layer.name
            except (RuntimeError, TypeError) as e:
                print(f"Note: Could not set target_layer: {e}")

        if hasattr(lineart_mod, 'target_material'):
            try:
                lineart_mod.target_material = gp_data.materials[mat_index]
            except RuntimeError as e:
                print(f"Note: Could not set target_material: {e}")

    # Occlusion
    if hasattr(lineart_mod, 'use_back_face_culling'):
        lineart_mod.use_back_face_culling = True

    # Debug: Print modifier info
    print(f"\n{'='*60}")
    print(f"=== Line Art Modifier Configuration ===")
    print(f"{'='*60}")
    print(f"\n🎬 Scene Settings:")
    print(f"  Render Engine: {bpy.context.scene.render.engine}")
    print(f"  Film Transparent: {bpy.context.scene.render.film_transparent}")
    print(f"\n📝 GP Object & Layers:")
    print(f"  GP Object: {gp_obj.name}")
    print(f"  GP Data: {gp_data.name}")
    print(f"  Layer: {gp_layer.name if gp_layer else 'None (auto-created)'}")
    print(f"  Material: {mat.name if mat else 'None (auto-created)'} (index: {mat_index})")
    print(f"\n⚙️ Line Art Modifier Settings:")
    print(f"  Type: {lineart_mod.type}")
    print(f"  Source Type: {lineart_mod.source_type}")
    print(f"  Source Object: {lineart_mod.source_object.name if lineart_mod.source_object else 'None'}")
    print(f"  Original Mesh: {mesh_obj.name}")
    print(f"  Mesh Copy: {mesh_copy.name}")
    print(f"  Excluded Collection: {original_collection.name if original_collection else 'None'}")
    print(f"  Temp Collection: {temp_collection.name}")
    print(f"  Custom Camera: {camera.name if lineart_mod.use_custom_camera else 'Default'}")
    print(f"  Camera Distance: 12 units")
    print(f"  Light: {light.name} ({light.data.energy}W)")
    if hasattr(lineart_mod, 'target_layer'):
        print(f"  Target Layer: {lineart_mod.target_layer if lineart_mod.target_layer else 'Auto'}")
    if hasattr(lineart_mod, 'target_material'):
        print(f"  Target Material: {lineart_mod.target_material.name if lineart_mod.target_material else 'Auto'}")
    print(f"\n📐 Edge Types:")
    print(f"  Contour/Silhouette: {lineart_mod.use_contour if hasattr(lineart_mod, 'use_contour') else 'N/A'}")
    print(f"  Intersection: {lineart_mod.use_intersection if hasattr(lineart_mod, 'use_intersection') else 'N/A'}")
    print(f"  Loose: {lineart_mod.use_loose if hasattr(lineart_mod, 'use_loose') else 'N/A'}")
    print(f"  Crease: {lineart_mod.use_crease}")
    print(f"\n🔍 Filtering & Quality:")
    print(f"  Silhouette Filtering: {lineart_mod.silhouette_filtering if hasattr(lineart_mod, 'silhouette_filtering') else 'N/A'}")
    print(f"  Overscan: {lineart_mod.overscan if hasattr(lineart_mod, 'overscan') else 'N/A'}")
    print(f"  Level Start: {lineart_mod.level_start if hasattr(lineart_mod, 'level_start') else 'N/A'}")
    print(f"  Level End: {lineart_mod.level_end if hasattr(lineart_mod, 'level_end') else 'N/A'}")
    print(f"\n🎨 Geometry Processing:")
    print(f"  Backface Culling: {lineart_mod.use_back_face_culling if hasattr(lineart_mod, 'use_back_face_culling') else 'N/A'}")
    print(f"  Instancing: {lineart_mod.use_instancing if hasattr(lineart_mod, 'use_instancing') else 'N/A'}")

    # Ensure GP object is visible
    gp_obj.hide_viewport = False
    gp_obj.hide_render = False
    if hasattr(gp_obj, 'show_in_front'):
        gp_obj.show_in_front = True  # Show in front of other objects

    # Force viewport update to generate Line Art strokes
    if bpy.context.view_layer:
        bpy.context.view_layer.update()

    # Debug: Check if GP has any data before applying
    print(f"\n  Debug - Before applying modifier:")
    print(f"    GP object visible: {not gp_obj.hide_viewport}")
    print(f"    Mesh copy visible: {not mesh_copy.hide_viewport}, hidden: {mesh_copy.hide_get()}")
    print(f"    GP data layers: {len(gp_data.layers)}")
    if bpy.app.version >= (5, 0, 0) and hasattr(gp_data, 'drawings'):
        print(f"    GP drawings: {len(gp_data.drawings())}")

    # CRITICAL: Apply Line Art modifier while mesh is still visible
    # (otherwise strokes disappear when mesh is hidden)
    print("\nApplying Line Art modifier (mesh must be visible)...")
    bpy.ops.object.select_all(action='DESELECT')
    gp_obj.select_set(True)
    bpy.context.view_layer.objects.active = gp_obj

    # Apply the modifier
    if bpy.app.version >= (5, 0, 0):
        # Blender 5.0: Use modifier_apply
        try:
            bpy.ops.object.modifier_apply(modifier=lineart_mod.name)
            print(f"  ✓ Applied Line Art modifier")
        except RuntimeError as e:
            print(f"  ✗ Warning: Could not apply modifier: {e}")
    else:
        # Blender 3.x-4.x: Use gpencil_modifier_apply
        try:
            bpy.ops.object.gpencil_modifier_apply(modifier=lineart_mod.name)
            print(f"  ✓ Applied Line Art modifier")
        except RuntimeError as e:
            print(f"  ✗ Warning: Could not apply modifier: {e}")

    # Debug: Check if GP has strokes after applying
    print(f"\n  Debug - After applying modifier:")
    if bpy.app.version >= (5, 0, 0) and hasattr(gp_data, 'drawings'):
        num_drawings = len(gp_data.drawings())
        print(f"    GP drawings: {num_drawings}")
        if num_drawings > 0:
            drawing = gp_data.drawings()[0]
            print(f"    Curves in first drawing: {len(drawing.curves)}")
    print(f"    GP object scale: {gp_obj.scale}")

    # Flatten GP object (scale to 0 on Y-axis for front view)
    print("Flattening GP object (Y-axis scale = 0)...")
    gp_obj.scale[1] = 0.0
    print(f"  ✓ GP scaled to {gp_obj.scale}")

    # Convert mesh copy into a mannequin background for control points
    print("Setting up mesh copy as mannequin...")

    # Unlock all transform channels
    for i in range(3):
        mesh_copy.lock_location[i] = False
        mesh_copy.lock_rotation[i] = False
        mesh_copy.lock_scale[i] = False
    print(f"  ✓ Unlocked all transform channels on {mesh_copy.name}")

    # Strip all modifiers
    for mod in list(mesh_copy.modifiers):
        mesh_copy.modifiers.remove(mod)
    print(f"  ✓ Removed all modifiers from {mesh_copy.name}")

    # Strip all existing materials
    mesh_copy.data.materials.clear()
    print(f"  ✓ Cleared all materials from {mesh_copy.name}")

    # Create and apply a gray mannequin material
    mat_name = "PB_Mannequin_Gray"
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.35, 0.35, 0.35, 1.0)
            bsdf.inputs["Roughness"].default_value = 1.0
            if "Specular IOR Level" in bsdf.inputs:
                bsdf.inputs["Specular IOR Level"].default_value = 0.0
            elif "Specular" in bsdf.inputs:
                bsdf.inputs["Specular"].default_value = 0.0
    mesh_copy.data.materials.append(mat)
    print(f"  ✓ Applied '{mat_name}' material to {mesh_copy.name}")

    # Keep visible in viewport, hide from render
    mesh_copy.hide_viewport = False
    mesh_copy.hide_render = True
    print(f"  ✓ Mannequin visible in viewport: {mesh_copy.name}")

    # Re-enable original collection (un-exclude from view layer)
    if original_collection and layer_coll:
        layer_coll.exclude = False
        print(f"  ✓ Re-enabled collection: {original_collection.name}")

    # Move mannequin and GP outline into PB_{char}_Stage; delete TempCollection
    move_object_to_collection(mesh_copy, stage_coll)
    move_object_to_collection(gp_obj, stage_coll)
    print(f"  ✓ Moved '{mesh_copy.name}' → {stage_coll.name}")
    print(f"  ✓ Moved '{gp_obj.name}' → {stage_coll.name}")
    if temp_collection_name in bpy.data.collections:
        bpy.data.collections.remove(bpy.data.collections[temp_collection_name])
        print(f"  ✓ Deleted temp collection '{temp_collection_name}'")

    print(f"\n{'='*70}")
    print(f"✨ SUCCESS! Line Art Outline Created: {outline_name}")
    print(f"{'='*70}")
    print(f"\n🎯 Workflow Applied:")
    print(f"  1. Copied mesh: {mesh_obj.name} → {mesh_copy.name}")
    print(f"  2. Moved copy to temp collection: {temp_collection_name}")
    print(f"  3. Excluded original collection from view layer")
    print(f"  4. Created camera: 12 units from character, Z = {camera_z:.2f}m (58% of height)")
    print(f"  5. Created light: Same position, 50W power")
    print(f"  6. Selected mesh copy and created GP with LINEART_OBJECT")
    print(f"  7. Applied Line Art modifier (while mesh visible)")
    print(f"  8. Flattened GP object (Y-axis scale = 0)")
    print(f"  9. Converted mesh copy to mannequin and re-enabled original collection")
    print(f"\n✅ Critical Settings:")
    print(f"  ✓ Render Engine: EEVEE")
    print(f"  ✓ Source: {mesh_copy.name} (copy, not original!)")
    print(f"  ✓ Original Collection: {original_collection.name if original_collection else 'N/A'} (temporarily excluded)")
    print(f"  ✓ Character Height: {character_height:.2f}m")
    print(f"  ✓ Line Radius: {line_radius:.4f} (dynamic)")
    print(f"  ✓ Silhouette Filtering: GROUP")
    print(f"  ✓ Edge Types: Silhouette ONLY")
    print(f"  ✓ Camera: Y=-12 units, Z={camera_z:.2f}m (58% height)")
    print(f"  ✓ Light Power: 50W")
    print(f"  ✓ GP Flattened: Y-scale = 0.0")
    print(f"\n📦 Objects Created:")
    print(f"  • GP Object: {gp_obj.name}")
    print(f"  • Mesh Copy: {mesh_copy.name}")
    print(f"  • Temp Collection: {temp_collection_name} (deleted after use)")
    print(f"  • Camera: {camera.name}")
    print(f"  • Light: {light.name}")
    print(f"\n🎨 The outline is now static (modifier applied) and flattened for front view!")
    print(f"  • GP Object: {outline_name}")
    print(f"  • Position control points using bone locations from front camera perspective")
    print(f"  • Original mesh is still active - pose it to test control point placement")

    print(f"\n💡 Next Steps:")
    print(f"  1. Calculate control point positions from bone locations (front camera view)")
    print(f"  2. Use bone head/tail/midpoint positions projected to 2D viewport coords")
    print(f"  3. Place circle controls for single bones, sun controls for multi-bone groups")

    print(f"\n❓ If you don't see the outline:")
    print(f"  1. Check '{outline_name}' visibility in outliner")
    print(f"  2. Ensure viewport shading shows overlays (top right icons)")
    print(f"  3. Verify GP object scale is (1, 0, 1) - flattened on Y")
    print(f"  4. Check that Line Art modifier was applied successfully")
    print(f"{'='*70}\n")

    # CAPTURE FIXED CONTROL POINT POSITIONS from T-pose
    print(f"\n{'='*70}")
    print(f"Capturing Fixed Control Point Positions...")
    print(f"{'='*70}")
    if armature:
        capture_fixed_control_points(armature, outline_name)
    print(f"{'='*70}\n")

    return gp_obj


# ============================================================================
# Operator
# ============================================================================

class POSE_OT_posebridge_generate_lineart_outline(bpy.types.Operator):
    """Generate Line Art outline (automatic, updates with pose)"""
    bl_idname = "pose.posebridge_generate_lineart_outline"
    bl_label = "Generate Line Art Outline"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj:
            return False

        # Allow either armature or mesh
        if obj.type == 'ARMATURE':
            return True
        elif obj.type == 'MESH':
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object:
                    return True
        return False

    def execute(self, context):
        obj = context.active_object
        mesh_obj = None

        # Get mesh from selected object
        if obj.type == 'MESH':
            mesh_obj = obj
        elif obj.type == 'ARMATURE':
            # Find mesh that uses this armature
            for scene_obj in context.scene.objects:
                if scene_obj.type == 'MESH':
                    for mod in scene_obj.modifiers:
                        if mod.type == 'ARMATURE' and mod.object == obj:
                            mesh_obj = scene_obj
                            break
                if mesh_obj:
                    break

        if not mesh_obj:
            self.report({'ERROR'}, "No mesh found for selected object")
            return {'CANCELLED'}

        # Generate outline
        gp_obj = create_genesis8_lineart_outline(mesh_obj)

        if gp_obj:
            self.report({'INFO'}, f"Generated Line Art outline: {gp_obj.name}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Failed to generate outline")
            return {'CANCELLED'}


# ============================================================================
# Registration
# ============================================================================

def register():
    bpy.utils.register_class(POSE_OT_posebridge_generate_lineart_outline)

def unregister():
    bpy.utils.unregister_class(POSE_OT_posebridge_generate_lineart_outline)


# ============================================================================
# Standalone Script Usage
# ============================================================================

if __name__ == "__main__":
    register()

    # Auto-run
    obj = bpy.context.active_object
    if obj:
        mesh_obj = None

        if obj.type == 'MESH':
            mesh_obj = obj
            print(f"Generating Line Art outline for mesh: {obj.name}")
        elif obj.type == 'ARMATURE':
            # Find mesh that uses this armature
            for scene_obj in bpy.context.scene.objects:
                if scene_obj.type == 'MESH':
                    for mod in scene_obj.modifiers:
                        if mod.type == 'ARMATURE' and mod.object == obj:
                            mesh_obj = scene_obj
                            print(f"Generating Line Art outline for mesh: {mesh_obj.name} (from armature {obj.name})")
                            break
                if mesh_obj:
                    break

        if mesh_obj:
            create_genesis8_lineart_outline(mesh_obj)
        else:
            print("No valid mesh found")
    else:
        print("Please select the Genesis 8 mesh or armature")
