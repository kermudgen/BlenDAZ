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
    2. Infer from genesis version + gender detection using known paths

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

    # Strategy 2: Infer from genesis version and gender
    # Detect genesis version from bone markers
    genesis_key = None
    if armature and armature.type == 'ARMATURE':
        bone_names = {b.name for b in armature.pose.bones}

        # Genesis 8 markers (camelCase bones)
        g8_markers = {'lPectoral', 'rPectoral', 'lCollar', 'rCollar'}
        if g8_markers.intersection(bone_names):
            # Detect 8 vs 8.1 - G8.1 has specific bones not in G8
            # For now, try G8 first (same geometry as G8.1)
            # Detect gender from mesh name or bone structure
            gender = _detect_gender(armature, mesh_obj)
            genesis_key = ('genesis8', gender)

    if genesis_key and genesis_key in KNOWN_DSF_PATHS:
        rel_path = KNOWN_DSF_PATHS[genesis_key]
        for content_dir in content_dirs:
            full_path = os.path.join(content_dir, rel_path)
            if os.path.isfile(full_path):
                return full_path

        # Also try the other gender if first didn't work
        alt_gender = 'male' if genesis_key[1] == 'female' else 'female'
        alt_key = (genesis_key[0], alt_gender)
        if alt_key in KNOWN_DSF_PATHS:
            rel_path = KNOWN_DSF_PATHS[alt_key]
            for content_dir in content_dirs:
                full_path = os.path.join(content_dir, rel_path)
                if os.path.isfile(full_path):
                    return full_path

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
        key = mesh_obj.data.name
        if key not in cls._cache:
            cls._cache[key] = cls(mesh_obj, armature)
        return cls._cache[key]

    @classmethod
    def invalidate(cls, mesh_obj=None):
        """Clear cache. Call when mesh changes or scene reloads."""
        if mesh_obj:
            cls._cache.pop(mesh_obj.data.name, None)
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
