"""
DSF Face Groups - Parse DAZ DSF geometry files for clean mesh zone detection.

Extracts polygon_groups (face groups) from Genesis 8 DSF files and maps them
to bone names for crisp, hard-edged body region detection during raycast hover.
Falls back gracefully to vertex weight method when DSF data is unavailable.
"""

import json
import gzip
import os
from urllib.parse import unquote
from mathutils import Vector
from mathutils.bvhtree import BVHTree


# ============================================================================
# DSF Face Group → Bone Name Mapping
# ============================================================================

# Maps DSF polygon group names to DAZ bone names used in Blender.
# Many names differ: lShoulder → lShldrBend, Hip → pelvis, etc.
DSF_GROUP_TO_BONE = {
    # Head / Neck
    'Head': 'head',
    'NeckUpper': 'neckUpper',
    'Neck': 'neckLower',
    'LowerJaw': 'lowerJaw',
    'UpperJaw': 'upperJaw',
    'Tongue': 'tongue',
    'lEye': 'lEye',
    'rEye': 'rEye',

    # Torso
    'ChestUpper': 'chestUpper',
    'Chest': 'chestLower',
    'AbdomenUpper': 'abdomenUpper',
    'Abdomen': 'abdomenLower',
    'Hip': 'pelvis',
    'lPectoral': 'lPectoral',
    'rPectoral': 'rPectoral',

    # Left Arm
    'lCollar': 'lCollar',
    'lShoulder': 'lShldrBend',
    'lForearm': 'lForearmBend',
    'lHand': 'lHand',

    # Right Arm
    'rCollar': 'rCollar',
    'rShoulder': 'rShldrBend',
    'rForearm': 'rForearmBend',
    'rHand': 'rHand',

    # Left Leg
    'lThigh': 'lThighBend',
    'lShin': 'lShin',
    'lFoot': 'lFoot',
    'lToe': 'lToe',

    # Right Leg
    'rThigh': 'rThighBend',
    'rShin': 'rShin',
    'rFoot': 'rFoot',
    'rToe': 'rToe',

    # Left Hand Fingers
    'lThumb1': 'lThumb1',
    'lThumb2': 'lThumb2',
    'lThumb3': 'lThumb3',
    'lIndex1': 'lIndex1',
    'lIndex2': 'lIndex2',
    'lIndex3': 'lIndex3',
    'lMid1': 'lMid1',
    'lMid2': 'lMid2',
    'lMid3': 'lMid3',
    'lRing1': 'lRing1',
    'lRing2': 'lRing2',
    'lRing3': 'lRing3',
    'lPinky1': 'lPinky1',
    'lPinky2': 'lPinky2',
    'lPinky3': 'lPinky3',

    # Right Hand Fingers
    'rThumb1': 'rThumb1',
    'rThumb2': 'rThumb2',
    'rThumb3': 'rThumb3',
    'rIndex1': 'rIndex1',
    'rIndex2': 'rIndex2',
    'rIndex3': 'rIndex3',
    'rMid1': 'rMid1',
    'rMid2': 'rMid2',
    'rMid3': 'rMid3',
    'rRing1': 'rRing1',
    'rRing2': 'rRing2',
    'rRing3': 'rRing3',
    'rPinky1': 'rPinky1',
    'rPinky2': 'rPinky2',
    'rPinky3': 'rPinky3',
}

# Known DSF relative paths for Genesis 8 variants
# Relative to DAZ content directory root
KNOWN_DSF_PATHS = {
    ('genesis8', 'female'): 'data/DAZ 3D/Genesis 8/Female/Genesis8Female.dsf',
    ('genesis8', 'male'): 'data/DAZ 3D/Genesis 8/Male/Genesis8Male.dsf',
    ('genesis81', 'female'): 'data/DAZ 3D/Genesis 8/Female 8_1/Genesis8_1Female.dsf',
    ('genesis81', 'male'): 'data/DAZ 3D/Genesis 8/Male 8_1/Genesis8_1Male.dsf',
}


# ============================================================================
# DSF File Parser
# ============================================================================

def parse_dsf_face_groups(dsf_path):
    """
    Parse a DSF file and extract polygon face groups.

    Args:
        dsf_path: Absolute path to the .dsf file

    Returns:
        dict with 'group_names', 'polygon_count', 'vertex_count',
        'face_group_per_polygon' (list of group name per polygon index),
        or None if parsing fails.
    """
    if not os.path.isfile(dsf_path):
        return None

    # DSF files can be plain JSON or gzip-compressed
    data = None
    try:
        with open(dsf_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        try:
            with gzip.open(dsf_path, 'rt', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return None
    except Exception:
        return None

    if not data:
        return None

    # Navigate to geometry
    geo_lib = data.get('geometry_library')
    if not geo_lib or len(geo_lib) == 0:
        return None

    geo = geo_lib[0]

    group_names = geo.get('polygon_groups', {}).get('values', [])
    polylist = geo.get('polylist', {}).get('values', [])
    vertex_count = geo.get('vertices', {}).get('count', 0)

    if not group_names or not polylist:
        return None

    # Build per-polygon face group array
    # Each polylist entry: [group_idx, material_idx, vert0, vert1, vert2, (vert3)]
    face_group_per_polygon = []
    for poly in polylist:
        group_idx = poly[0]
        if 0 <= group_idx < len(group_names):
            face_group_per_polygon.append(group_names[group_idx])
        else:
            face_group_per_polygon.append(None)

    return {
        'group_names': group_names,
        'polygon_count': len(polylist),
        'vertex_count': vertex_count,
        'face_group_per_polygon': face_group_per_polygon,
    }


# ============================================================================
# Content Directory Discovery
# ============================================================================

def get_daz_content_dirs():
    """
    Get DAZ content directories from Diffeomorphic settings and known paths.

    Returns:
        List of absolute directory paths (deduplicated, existing only).
    """
    dirs = []

    # Source 1: Diffeomorphic import settings
    settings_path = os.path.expanduser('~/Documents/DAZ Importer/import_daz_settings.json')
    if os.path.isfile(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            content_dirs = settings.get('daz-settings', {}).get('contentDirs', [])
            dirs.extend(content_dirs)
        except Exception:
            pass

    # Source 2: import-daz-paths.json (Diffeomorphic path config)
    for paths_file in [
        'D:/Daz 3D/import-daz-paths.json',
        os.path.expanduser('~/Documents/DAZ Importer/import-daz-paths.json'),
    ]:
        if os.path.isfile(paths_file):
            try:
                with open(paths_file, 'r', encoding='utf-8') as f:
                    paths_data = json.load(f)
                content_dirs = paths_data.get('content', [])
                dirs.extend(content_dirs)
            except Exception:
                pass

    # Deduplicate and filter to existing directories
    seen = set()
    result = []
    for d in dirs:
        d_norm = os.path.normpath(d)
        if d_norm not in seen and os.path.isdir(d_norm):
            seen.add(d_norm)
            result.append(d_norm)

    return result


# ============================================================================
# DSF Path Resolution
# ============================================================================

def resolve_dsf_path(armature, mesh_obj):
    """
    Find the DSF geometry file for this character.

    Strategy:
    1. Check DazUrl custom property on armature or mesh (set by Diffeomorphic)
    2. Infer from genesis version — try both genders, pick the one whose
       polygon count matches the Blender mesh.

    Returns:
        Absolute filesystem path to .dsf file, or None.
    """
    content_dirs = get_daz_content_dirs()

    # Strategy 1: DazUrl custom property
    daz_url = None
    for obj in [armature, mesh_obj]:
        if obj and 'DazUrl' in obj:
            daz_url = str(obj['DazUrl'])
            break

    if daz_url:
        # Strip fragment (e.g., "#Genesis8Female") and URL-decode
        if '#' in daz_url:
            daz_url = daz_url.split('#')[0]
        rel_path = unquote(daz_url).lstrip('/')

        # Search content directories
        for content_dir in content_dirs:
            full_path = os.path.join(content_dir, rel_path)
            if os.path.isfile(full_path):
                return full_path

    # Strategy 2: Infer from genesis version
    # Detect genesis version from bone markers
    is_genesis8 = False
    if armature and armature.type == 'ARMATURE':
        bone_names = {b.name for b in armature.pose.bones}
        g8_markers = {'lPectoral', 'rPectoral', 'lCollar', 'rCollar'}
        if g8_markers.intersection(bone_names):
            is_genesis8 = True

    if is_genesis8:
        # Try both genders — pick the one whose polygon count matches the mesh
        blender_poly_count = len(mesh_obj.data.polygons) if mesh_obj else 0
        gender_order = _detect_gender(armature, mesh_obj)
        genders = [gender_order, 'male' if gender_order == 'female' else 'female']

        candidates = []
        for gender in genders:
            key = ('genesis8', gender)
            if key in KNOWN_DSF_PATHS:
                rel_path = KNOWN_DSF_PATHS[key]
                for content_dir in content_dirs:
                    full_path = os.path.join(content_dir, rel_path)
                    if os.path.isfile(full_path):
                        candidates.append(full_path)
                        break

        # If we have mesh data, prefer the DSF whose polygon count matches
        if blender_poly_count > 0 and len(candidates) > 1:
            for candidate in candidates:
                dsf_data = parse_dsf_face_groups(candidate)
                if dsf_data and dsf_data['polygon_count'] == blender_poly_count:
                    return candidate

        # Otherwise return first found
        if candidates:
            return candidates[0]

    return None


def _detect_gender(armature, mesh_obj):
    """Detect gender from armature/mesh naming conventions."""
    # Check DazRig property
    if armature and 'DazRig' in armature:
        rig_type = str(armature['DazRig']).lower()
        if 'female' in rig_type:
            return 'female'
        if 'male' in rig_type:
            return 'male'

    # Check object names
    for obj in [armature, mesh_obj]:
        if obj:
            name_lower = obj.name.lower()
            if 'female' in name_lower or 'girl' in name_lower or 'woman' in name_lower:
                return 'female'
            if 'male' in name_lower or 'boy' in name_lower or 'man' in name_lower:
                return 'male'

    # Default to female (Genesis 8 Female is more common)
    return 'female'


# ============================================================================
# Face Group Manager
# ============================================================================

class FaceGroupManager:
    """
    Manages face group lookup for a mesh.
    Built once at init, provides O(1) or O(log N) lookups during hover.
    """

    # Cache: mesh data name -> FaceGroupManager instance
    _cache = {}

    def __init__(self, mesh_obj, armature):
        self.valid = False
        self.face_group_map = []  # polygon_index -> bone_name or None
        self._bvh_tree = None

        self._build(mesh_obj, armature)

    def _build(self, mesh_obj, armature):
        """Build the face group mapping."""
        # Step 1: Resolve DSF path
        dsf_path = resolve_dsf_path(armature, mesh_obj)
        if not dsf_path:
            print("  [FaceGroups] DSF file not found - using vertex weight fallback")
            return

        print(f"  [FaceGroups] Parsing: {dsf_path}")

        # Step 2: Parse DSF
        dsf_data = parse_dsf_face_groups(dsf_path)
        if not dsf_data:
            print("  [FaceGroups] Failed to parse DSF file")
            return

        # Step 3: Validate polygon count
        blender_poly_count = len(mesh_obj.data.polygons)
        dsf_poly_count = dsf_data['polygon_count']

        if blender_poly_count != dsf_poly_count:
            print(f"  [FaceGroups] Polygon count mismatch: Blender={blender_poly_count}, DSF={dsf_poly_count}")
            print("  [FaceGroups] Mesh may have geografts merged or edits applied - using vertex weight fallback")
            return

        # Step 4: Build face_group_map
        armature_bones = set(armature.data.bones.keys()) if armature else set()
        mapped_count = 0
        unmapped_groups = set()

        for dsf_group_name in dsf_data['face_group_per_polygon']:
            if dsf_group_name is None:
                self.face_group_map.append(None)
                continue

            bone_name = DSF_GROUP_TO_BONE.get(dsf_group_name)
            if bone_name and bone_name in armature_bones:
                self.face_group_map.append(bone_name)
                mapped_count += 1
            else:
                self.face_group_map.append(None)
                if dsf_group_name not in unmapped_groups:
                    unmapped_groups.add(dsf_group_name)

        # Step 5: Build BVH tree from base mesh for SubSurf handling
        mesh = mesh_obj.data
        vertices = [v.co.copy() for v in mesh.vertices]
        polygons = [tuple(p.vertices) for p in mesh.polygons]
        self._bvh_tree = BVHTree.FromPolygons(vertices, polygons)

        self.valid = True
        print(f"  [FaceGroups] Loaded: {mapped_count}/{dsf_poly_count} polygons mapped to bones")
        if unmapped_groups:
            print(f"  [FaceGroups] Unmapped DSF groups (no matching bone): {sorted(unmapped_groups)}")

    @classmethod
    def get_or_create(cls, mesh_obj, armature):
        """Get cached instance or create new one."""
        # Include polygon count in key so cache invalidates when mesh is modified
        # (e.g., after merging geografts)
        key = (mesh_obj.data.name, len(mesh_obj.data.polygons))
        if key not in cls._cache:
            cls._cache[key] = cls(mesh_obj, armature)
        return cls._cache[key]

    @classmethod
    def build_from_reference_mesh(cls, reference_mesh_obj, live_mesh_obj, armature):
        """Build a FaceGroupManager for live_mesh_obj using reference_mesh_obj as source.

        Used after a geograft merge: the reference mesh (mannequin copy, pre-merge)
        has a polygon order that matches the DSF file. The live mesh has shifted
        indices after merge. Body vertex positions are unchanged by merge, so face
        centers are bit-for-bit identical — we match on those.

        Args:
            reference_mesh_obj: Pre-merge mesh copy (e.g. '{name}_LineArt_Copy')
            live_mesh_obj:      Post-merge body mesh (shifted polygon indices)
            armature:           Armature object (for bone name validation)

        Returns:
            FaceGroupManager instance cached under live_mesh_obj's key,
            or None if reference mesh has no valid face group data.
        """
        # Build (or retrieve cached) FaceGroupManager on the reference mesh.
        # Its polygon count should match the DSF file exactly.
        ref_key = (reference_mesh_obj.data.name, len(reference_mesh_obj.data.polygons))
        if ref_key in cls._cache:
            ref_fgm = cls._cache[ref_key]
        else:
            ref_fgm = cls(reference_mesh_obj, armature)
            cls._cache[ref_key] = ref_fgm

        if not ref_fgm.valid:
            print("  [FaceGroups] Reference mesh has no valid face group data — remap aborted")
            return None

        ref_mesh = reference_mesh_obj.data
        live_mesh = live_mesh_obj.data

        # Step 1: Build face_center → bone_name lookup from reference mesh
        ref_center_map = {}
        for poly_idx, bone_name in enumerate(ref_fgm.face_group_map):
            if bone_name is None:
                continue
            poly = ref_mesh.polygons[poly_idx]
            center = Vector()
            for vi in poly.vertices:
                center += ref_mesh.vertices[vi].co
            center /= len(poly.vertices)
            key = (round(center.x, 4), round(center.y, 4), round(center.z, 4))
            ref_center_map[key] = bone_name

        print(f"  [FaceGroups] Reference map built: {len(ref_center_map)} mapped face centers")

        # Step 2: Build new face_group_map for live mesh by matching face centers
        new_map = [None] * len(live_mesh.polygons)
        matched = 0
        for poly_idx, poly in enumerate(live_mesh.polygons):
            center = Vector()
            for vi in poly.vertices:
                center += live_mesh.vertices[vi].co
            center /= len(poly.vertices)
            key = (round(center.x, 4), round(center.y, 4), round(center.z, 4))
            bone_name = ref_center_map.get(key)
            if bone_name:
                new_map[poly_idx] = bone_name
                matched += 1

        total = len(live_mesh.polygons)
        new_polys = total - len(ref_mesh.polygons)
        print(f"  [FaceGroups] Remap complete: {matched}/{total} polygons mapped "
              f"({new_polys} new geograft polygons left unmapped — expected)")

        # Step 3: Construct a FaceGroupManager with the remapped data
        instance = cls.__new__(cls)
        instance.valid = True
        instance.face_group_map = new_map
        # Build BVH from live mesh for SubSurf fallback
        vertices = [v.co.copy() for v in live_mesh.vertices]
        polygons = [tuple(p.vertices) for p in live_mesh.polygons]
        instance._bvh_tree = BVHTree.FromPolygons(vertices, polygons)

        # Cache under live mesh key so rest of system uses it transparently
        live_key = (live_mesh_obj.data.name, len(live_mesh.polygons))
        cls._cache[live_key] = instance
        print(f"  [FaceGroups] Cached remapped FaceGroupManager for '{live_mesh_obj.name}'")
        return instance

    @classmethod
    def invalidate(cls, mesh_obj=None):
        """Clear cache. Call when mesh changes or scene reloads."""
        if mesh_obj:
            # Clear all entries for this mesh (any polygon count)
            keys_to_remove = [k for k in cls._cache if k[0] == mesh_obj.data.name]
            for k in keys_to_remove:
                del cls._cache[k]
        else:
            cls._cache.clear()

    def lookup_bone(self, face_index=None, hit_location_local=None):
        """
        Look up bone name for a hit polygon.

        Args:
            face_index: Polygon index from raycast (may be from evaluated/subdivided mesh)
            hit_location_local: Hit point in mesh local space (for BVH fallback)

        Returns:
            Bone name string, or None if lookup fails (caller should fall through
            to vertex weight method).
        """
        if not self.valid:
            return None

        # Fast path: face_index is within base mesh range (no SubSurf)
        if face_index is not None and 0 <= face_index < len(self.face_group_map):
            bone = self.face_group_map[face_index]
            if bone:
                return bone

        # Slow path: SubSurf active or no face_index - use BVH nearest polygon
        if hit_location_local is not None and self._bvh_tree:
            location, normal, base_idx, distance = self._bvh_tree.find_nearest(hit_location_local)
            if base_idx is not None and 0 <= base_idx < len(self.face_group_map):
                return self.face_group_map[base_idx]

        return None
