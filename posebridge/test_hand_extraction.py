# Test script: Check vertex groups for hand extraction
# Run in Blender with a Genesis 8/9 mesh selected
#
# Purpose: Verify we can extract hand geometry using vertex groups

import bpy

def test_hand_vertex_groups():
    """Check what vertex groups exist for hands on the selected mesh."""

    obj = bpy.context.active_object

    if not obj or obj.type != 'MESH':
        print("ERROR: Please select a mesh object (the character mesh)")
        return

    print(f"\n{'='*60}")
    print(f"Testing hand vertex groups on: {obj.name}")
    print(f"{'='*60}")

    # Get all vertex groups
    all_groups = [vg.name for vg in obj.vertex_groups]
    print(f"\nTotal vertex groups: {len(all_groups)}")

    # Define hand-related bone names (DAZ Genesis naming)
    # Left hand
    left_hand_bones = [
        'lHand',
        'lThumb1', 'lThumb2', 'lThumb3',
        'lIndex1', 'lIndex2', 'lIndex3',
        'lMid1', 'lMid2', 'lMid3',
        'lRing1', 'lRing2', 'lRing3',
        'lPinky1', 'lPinky2', 'lPinky3',
        # Alternative naming (some rigs use these)
        'lCarpal1', 'lCarpal2', 'lCarpal3', 'lCarpal4',
        'lMetacarpal1', 'lMetacarpal2', 'lMetacarpal3', 'lMetacarpal4', 'lMetacarpal5',
    ]

    # Right hand
    right_hand_bones = [
        'rHand',
        'rThumb1', 'rThumb2', 'rThumb3',
        'rIndex1', 'rIndex2', 'rIndex3',
        'rMid1', 'rMid2', 'rMid3',
        'rRing1', 'rRing2', 'rRing3',
        'rPinky1', 'rPinky2', 'rPinky3',
        # Alternative naming
        'rCarpal1', 'rCarpal2', 'rCarpal3', 'rCarpal4',
        'rMetacarpal1', 'rMetacarpal2', 'rMetacarpal3', 'rMetacarpal4', 'rMetacarpal5',
    ]

    # Check which groups exist
    print("\n--- LEFT HAND VERTEX GROUPS ---")
    left_found = []
    left_missing = []
    for bone in left_hand_bones:
        if bone in all_groups:
            left_found.append(bone)
            print(f"  [FOUND] {bone}")
        else:
            left_missing.append(bone)

    print("\n--- RIGHT HAND VERTEX GROUPS ---")
    right_found = []
    right_missing = []
    for bone in right_hand_bones:
        if bone in all_groups:
            right_found.append(bone)
            print(f"  [FOUND] {bone}")
        else:
            right_missing.append(bone)

    # Also check for any other hand-related groups we might have missed
    print("\n--- OTHER HAND-RELATED GROUPS ---")
    other_hand = []
    for group in all_groups:
        group_lower = group.lower()
        if ('hand' in group_lower or 'thumb' in group_lower or
            'index' in group_lower or 'mid' in group_lower or
            'ring' in group_lower or 'pinky' in group_lower or
            'finger' in group_lower or 'carpal' in group_lower or
            'metacarpal' in group_lower):
            if group not in left_found and group not in right_found:
                other_hand.append(group)
                print(f"  [OTHER] {group}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Left hand groups found: {len(left_found)}")
    print(f"Right hand groups found: {len(right_found)}")
    print(f"Other hand-related: {len(other_hand)}")

    # Count vertices in hand groups
    print("\n--- VERTEX COUNTS ---")
    mesh = obj.data

    def count_verts_in_group(group_name):
        """Count vertices with weight > 0 in a vertex group."""
        if group_name not in obj.vertex_groups:
            return 0

        group_index = obj.vertex_groups[group_name].index
        count = 0
        for v in mesh.vertices:
            for g in v.groups:
                if g.group == group_index and g.weight > 0.01:
                    count += 1
                    break
        return count

    # Count for main hand bones
    for bone in ['lHand', 'rHand']:
        if bone in all_groups:
            count = count_verts_in_group(bone)
            print(f"  {bone}: {count} vertices")

    # Count total left hand verts
    left_verts = set()
    for bone in left_found:
        if bone in obj.vertex_groups:
            group_index = obj.vertex_groups[bone].index
            for v in mesh.vertices:
                for g in v.groups:
                    if g.group == group_index and g.weight > 0.01:
                        left_verts.add(v.index)
    print(f"\n  Total LEFT hand vertices (all bones): {len(left_verts)}")

    # Count total right hand verts
    right_verts = set()
    for bone in right_found:
        if bone in obj.vertex_groups:
            group_index = obj.vertex_groups[bone].index
            for v in mesh.vertices:
                for g in v.groups:
                    if g.group == group_index and g.weight > 0.01:
                        right_verts.add(v.index)
    print(f"  Total RIGHT hand vertices (all bones): {len(right_verts)}")

    print(f"\n{'='*60}")
    print("TEST COMPLETE")
    print(f"{'='*60}")

    # Return data for further use
    return {
        'left_found': left_found,
        'right_found': right_found,
        'other_hand': other_hand,
        'left_verts': left_verts,
        'right_verts': right_verts
    }


# Run the test
if __name__ == "__main__":
    test_hand_vertex_groups()
