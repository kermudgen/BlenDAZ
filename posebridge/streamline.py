# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joshua D Rother
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Streamline — bulk mute/unmute drivers, modifiers, shape keys and more.

DAZ characters carry hundreds of shape-key drivers (JCMs, flexions, FACS
blendshapes), heavy modifiers (Subsurf, Corrective Smooth, etc.) and physics
that fire every frame.  Streamline disables them in bulk for snappy
interactive posing, then restores them when full fidelity is needed again.

Categories inspired by MustardSimplify (https://github.com/Mustard2/MustardSimplify).
"""

import bpy

import logging
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Modifier classification
# ---------------------------------------------------------------------------

# Modifier types to disable in the viewport (render stays enabled)
_DISABLE_MOD_TYPES = {
    'SUBSURF', 'MULTIRES',
    'CORRECTIVE_SMOOTH', 'SURFACE_DEFORM', 'MESH_DEFORM',
    'SHRINKWRAP', 'LAPLACIANDEFORM',
}

# Never touch these
_KEEP_MOD_TYPES = {'ARMATURE', 'HOOK', 'LINEART'}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iter_character_objects():
    """Yield (armature, [child meshes]) for every registered DAZ character."""
    settings = getattr(bpy.context.scene, 'posebridge_settings', None)
    if not settings:
        return
    for slot in settings.blendaz_characters:
        armature = bpy.data.objects.get(slot.armature_name)
        if not armature:
            continue
        children = [c for c in armature.children if c.type == 'MESH']
        yield armature, children


def _is_smooth_by_angle(mod):
    """Return True if *mod* is a Geometry-Nodes 'Smooth by Angle' modifier."""
    return (mod.type == 'NODES'
            and mod.node_group is not None
            and mod.node_group.name == 'Smooth by Angle')


# ---------------------------------------------------------------------------
# Core apply / restore
# ---------------------------------------------------------------------------

def apply_streamline(enabled,
                     mute_drivers=True,
                     mute_shape_keys=True,
                     disable_modifiers=True,
                     disable_physics=True,
                     disable_normals_auto_smooth=True,
                     blender_simplify=True,
                     mute_armature_meshes=True):
    """Apply or remove streamline settings across all registered characters.

    Args:
        enabled:  True to engage streamline (mute/disable), False to restore.
        mute_drivers:  Mute armature + shape-key drivers.
        mute_shape_keys:  Directly mute shape keys (independent of drivers).
        disable_modifiers:  Hide heavy modifiers in viewport.
        disable_physics:  Disable rigid-body world.
        disable_normals_auto_smooth:  Disable 'Smooth by Angle' GN modifier.
        blender_simplify:  Toggle Blender's built-in render.use_simplify.
        mute_armature_meshes:  Hide selected child meshes and disable their Armature modifier.

    Returns:
        Dict of counts for each category.
    """
    mute = enabled
    counts = {
        'drivers': 0,
        'shape_keys': 0,
        'modifiers': 0,
        'normals': 0,
        'physics': 0,
        'meshes': 0,
    }

    # --- Blender built-in simplify ---
    if blender_simplify:
        bpy.context.scene.render.use_simplify = mute

    # --- Physics (rigid body world) ---
    if disable_physics:
        rbw = bpy.context.scene.rigidbody_world
        if rbw:
            rbw.enabled = not mute
            counts['physics'] += 1

    # --- Per-character objects ---
    processed_mesh_data = set()  # avoid double-processing shared mesh data

    for armature, meshes in _iter_character_objects():

        # Armature drivers (FACS joint-morph rotation drivers on bones)
        if mute_drivers and armature.animation_data:
            for drv in armature.animation_data.drivers:
                drv.mute = mute
                counts['drivers'] += 1

        for mesh_obj in meshes:
            mesh_data = mesh_obj.data

            # --- Shape-key drivers ---
            if mute_drivers and mesh_data.shape_keys:
                sk_anim = mesh_data.shape_keys.animation_data
                if sk_anim and sk_anim.drivers:
                    for drv in sk_anim.drivers:
                        drv.mute = mute
                        counts['drivers'] += 1

            # --- Shape keys (direct mute) ---
            if mute_shape_keys and mesh_data.shape_keys:
                if id(mesh_data) not in processed_mesh_data:
                    processed_mesh_data.add(id(mesh_data))
                    for sk in mesh_data.shape_keys.key_blocks:
                        if sk.name == 'Basis':
                            continue
                        sk.mute = mute
                        counts['shape_keys'] += 1

            # --- Heavy modifiers (viewport only) ---
            if disable_modifiers:
                for mod in mesh_obj.modifiers:
                    if mod.type in _DISABLE_MOD_TYPES:
                        mod.show_viewport = not mute
                        counts['modifiers'] += 1

            # --- Normals auto-smooth (Smooth by Angle GN modifier) ---
            if disable_normals_auto_smooth:
                for mod in mesh_obj.modifiers:
                    if _is_smooth_by_angle(mod):
                        mod.show_viewport = not mute
                        counts['normals'] += 1

        # --- High-poly mesh hiding + Armature modifier muting ---
        if mute_armature_meshes:
            settings = bpy.context.scene.posebridge_settings
            slot = None
            for s in settings.blendaz_characters:
                if s.armature_name == armature.name:
                    slot = s
                    break
            if slot:
                muted_names = set(slot.get_muted_meshes_list())
                for mesh_obj in meshes:
                    if mesh_obj.name in muted_names:
                        mesh_obj.hide_viewport = mute
                        for mod in mesh_obj.modifiers:
                            if mod.type == 'ARMATURE':
                                mod.show_viewport = not mute
                        counts['meshes'] += 1

    state = "ON" if enabled else "OFF"
    parts = [f"{v} {k}" for k, v in counts.items() if v > 0]
    log.info(f"Streamline {state}: {', '.join(parts) if parts else 'nothing affected'}")
    return counts
