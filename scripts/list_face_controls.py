"""
Diagnostic script: List all face-related FACS and CTRL properties on the armature.
Run in Blender's Script Editor with a DAZ character selected (mesh or armature).

Usage: Select the character mesh or armature, then run this script.
"""

import bpy

obj = bpy.context.active_object

# Find armature
if obj and obj.type == 'ARMATURE':
    armature = obj
elif obj and obj.type == 'MESH':
    armature = obj.find_armature()
else:
    armature = None

if not armature:
    print("ERROR: Select a DAZ character (mesh or armature) first")
else:
    print(f"\n{'='*70}")
    print(f"ARMATURE: {armature.name}")
    print(f"{'='*70}")

    # Collect all custom properties
    all_props = {k: v for k, v in armature.items() if isinstance(k, str) and isinstance(v, (int, float))}

    # --- FACS controls ---
    facs_props = {k: v for k, v in all_props.items() if k.startswith('facs_')}

    # Sub-categorize FACS by face region
    regions = {
        'Brow':   [], 'Eye':    [], 'Cheek':  [], 'Nose':   [],
        'Mouth':  [], 'Jaw':    [], 'Tongue': [], 'Other':  [],
    }

    for name, val in sorted(facs_props.items()):
        name_lower = name.lower()
        if 'brow' in name_lower:
            regions['Brow'].append((name, val))
        elif 'eye' in name_lower or 'squint' in name_lower or 'blink' in name_lower:
            regions['Eye'].append((name, val))
        elif 'cheek' in name_lower:
            regions['Cheek'].append((name, val))
        elif 'nose' in name_lower or 'sneer' in name_lower:
            regions['Nose'].append((name, val))
        elif any(p in name_lower for p in ['mouth', 'lip', 'smile', 'frown', 'pucker', 'funnel', 'press', 'stretch', 'dimple']):
            regions['Mouth'].append((name, val))
        elif 'jaw' in name_lower:
            regions['Jaw'].append((name, val))
        elif 'tongue' in name_lower:
            regions['Tongue'].append((name, val))
        else:
            regions['Other'].append((name, val))

    print(f"\n--- FACS Properties ({len(facs_props)} total) ---")
    for region, props in regions.items():
        if not props:
            continue
        print(f"\n  [{region}] ({len(props)})")
        for name, val in props:
            # Get property range if available
            try:
                id_props = armature.id_properties_ui(name)
                info = id_props.as_dict()
                smin = info.get('min', '?')
                smax = info.get('max', '?')
                range_str = f"  range=[{smin}, {smax}]"
            except:
                range_str = ""
            marker = " *" if val != 0.0 else ""
            print(f"    {name}{range_str}  value={val:.3f}{marker}")

    # --- CTRL face controls ---
    face_ctrl_keywords = ['jaw', 'tongue', 'cheek', 'brow', 'eye', 'lip', 'mouth',
                          'nose', 'neck', 'head', 'dimple', 'iris']
    ctrl_face = {k: v for k, v in all_props.items()
                 if k.startswith('CTRL') and any(p in k.lower() for p in face_ctrl_keywords)}

    if ctrl_face:
        print(f"\n--- CTRL Face Properties ({len(ctrl_face)}) ---")
        for name, val in sorted(ctrl_face.items()):
            try:
                id_props = armature.id_properties_ui(name)
                info = id_props.as_dict()
                smin = info.get('min', '?')
                smax = info.get('max', '?')
                range_str = f"  range=[{smin}, {smax}]"
            except:
                range_str = ""
            marker = " *" if val != 0.0 else ""
            print(f"  {name}{range_str}  value={val:.3f}{marker}")

    # --- Expression presets (eJCM) ---
    ejcm_face = {k: v for k, v in all_props.items()
                 if k.startswith('eJCM') and not any(p in k.lower() for p in ['shin', 'thigh', 'arm', 'leg'])}

    if ejcm_face:
        print(f"\n--- Expression Presets eJCM ({len(ejcm_face)}) ---")
        for name, val in sorted(ejcm_face.items()):
            marker = " *" if val != 0.0 else ""
            print(f"  {name}  value={val:.3f}{marker}")

    print(f"\n{'='*70}")
    print(f"Summary: {len(facs_props)} FACS + {len(ctrl_face)} CTRL face + {len(ejcm_face)} eJCM expressions")
    print(f"{'='*70}\n")
