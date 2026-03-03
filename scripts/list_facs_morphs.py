"""
Diagnostic script: List all FACS/morph shape keys and Diffeomorphic custom properties.
Run in Blender's Script Editor or Python Console with a DAZ character selected.

Usage: Select the character mesh, then run this script.
"""

import bpy

obj = bpy.context.active_object

if not obj or obj.type != 'MESH':
    print("ERROR: Select a mesh object first")
else:
    print(f"\n{'='*60}")
    print(f"MESH: {obj.name}")
    print(f"{'='*60}")

    # --- Custom Properties ---
    daz_props = {k: v for k, v in obj.items() if isinstance(k, str) and k.startswith('Daz')}
    if daz_props:
        print(f"\n--- Daz Custom Properties on Mesh ({len(daz_props)}) ---")
        for k, v in sorted(daz_props.items()):
            print(f"  {k}: {v}")

    # --- Shape Keys ---
    if obj.data.shape_keys:
        keys = obj.data.shape_keys.key_blocks
        print(f"\n--- Total Shape Keys: {len(keys)} ---")

        # Categorize by prefix
        categories = {}
        for sk in keys:
            name = sk.name
            if name == 'Basis':
                continue
            # Try to extract prefix
            prefix = name.split('_')[0] if '_' in name else 'other'
            if prefix not in categories:
                categories[prefix] = []
            categories[prefix].append((name, sk.value, sk.slider_min, sk.slider_max))

        for cat in sorted(categories.keys()):
            items = categories[cat]
            print(f"\n  [{cat}] ({len(items)} keys)")
            # Show first 10 per category, summarize rest
            for name, val, smin, smax in items[:10]:
                marker = " *" if val != 0.0 else ""
                print(f"    {name}  range=[{smin:.1f}, {smax:.1f}]  value={val:.3f}{marker}")
            if len(items) > 10:
                print(f"    ... and {len(items) - 10} more")
    else:
        print("\n  NO SHAPE KEYS found on this mesh")

    # --- Check Armature ---
    armature = obj.find_armature()
    if armature:
        print(f"\n{'='*60}")
        print(f"ARMATURE: {armature.name}")
        print(f"{'='*60}")

        daz_arm_props = {k: v for k, v in armature.items() if isinstance(k, str) and k.startswith('Daz')}
        if daz_arm_props:
            print(f"\n--- Daz Custom Properties on Armature ({len(daz_arm_props)}) ---")
            for k, v in sorted(daz_arm_props.items()):
                val_str = str(v)[:80]
                print(f"  {k}: {val_str}")

        # Check for morph-related custom properties (drivers)
        morph_props = {k: v for k, v in armature.items()
                       if isinstance(k, str) and any(p in k.lower() for p in
                       ['facs', 'morph', 'ctrl', 'expression', 'ectrl', 'phmm', 'vsm'])}
        if morph_props:
            print(f"\n--- Morph/FACS Custom Properties on Armature ({len(morph_props)}) ---")
            for k, v in sorted(morph_props.items())[:30]:
                print(f"  {k}: {v}")
            if len(morph_props) > 30:
                print(f"  ... and {len(morph_props) - 30} more")

        # Check for drivers on shape keys
        if obj.data.shape_keys and obj.data.shape_keys.animation_data:
            drivers = obj.data.shape_keys.animation_data.drivers
            if drivers:
                print(f"\n--- Shape Key Drivers ({len(drivers)}) ---")
                for i, driver in enumerate(drivers):
                    if i >= 15:
                        print(f"  ... and {len(drivers) - 15} more drivers")
                        break
                    dp = driver.data_path
                    # Extract shape key name from data path
                    if 'key_blocks' in dp:
                        sk_name = dp.split('"')[1] if '"' in dp else dp
                        # Show driver variables
                        vars_info = []
                        for var in driver.driver.variables:
                            for target in var.targets:
                                if target.data_path:
                                    vars_info.append(target.data_path.split('"')[1] if '"' in target.data_path else target.data_path)
                        print(f"  {sk_name} <- {', '.join(vars_info[:3])}")

    print(f"\n{'='*60}")
    print("Done. Shape keys marked with * have non-zero values.")
    print(f"{'='*60}\n")
