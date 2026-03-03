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

"""
BlenDAZ Diagnostic Logger — Structured event logging for modal operator debugging.

Developer-only component. Captures raycast data, hover/click events, character switching,
and auto-flags anomalies. Output: JSON lines file at logs/diag_events.jsonl.

Usage:
    1. Set DIAG_ENABLED = True below
    2. Run the addon normally in Blender
    3. Read logs/diag_events.jsonl for structured diagnostic data

Toggle: DIAG_ENABLED (False = zero overhead, single boolean check per event)
"""

import os
import json
import time

import logging
log = logging.getLogger(__name__)


# ============================================================================
# Master switch — zero overhead when False
# ============================================================================
DIAG_ENABLED = True

# Resolve log dir robustly — __file__ may be unreliable in Blender's text editor context
try:
    _module_dir = os.path.dirname(os.path.abspath(__file__))
except (NameError, TypeError):
    _module_dir = os.getcwd()
DIAG_LOG_DIR = os.path.join(_module_dir, "logs")
DIAG_LOG_FILE = "diag_events.jsonl"


# ============================================================================
# Anomaly detection
# ============================================================================

def _detect_anomalies(entry):
    """Check a hover/click entry for suspicious data. Returns list of anomaly strings."""
    anomalies = []

    r1 = entry.get('raycast1')
    r2 = entry.get('raycast2')

    if r1 and r2:
        # Large position divergence between raycast 1 and 2
        if r1.get('hit') and r2.get('hit') and r1.get('location') and r2.get('location'):
            loc1 = r1['location']
            loc2 = r2['location']
            pos_diff = sum((a - b) ** 2 for a, b in zip(loc1, loc2)) ** 0.5
            if pos_diff > 0.3:
                anomalies.append(
                    f"POSITION_DIVERGENCE: raycast1 vs raycast2 = {pos_diff:.3f}m (threshold 0.3m)")

        # Scene missed but body hit
        if not r1.get('hit') and r2.get('hit'):
            anomalies.append("SCENE_MISS_BODY_HIT: scene raycast missed but body mesh raycast hit")

        # Rest-pose BVH (always true for raycast2 currently)
        if r2.get('hit') and not r2.get('is_evaluated'):
            anomalies.append("REST_POSE_BVH: raycast2 used mesh_obj.ray_cast() (rest-pose BVH)")

    # Bone resolution failed despite mesh hit
    bone_res = entry.get('bone_resolution')
    if bone_res is not None:
        has_hit = (r1 and r1.get('hit')) or (r2 and r2.get('hit'))
        if has_hit and not bone_res.get('raw_bone'):
            anomalies.append("BONE_RESOLUTION_FAILED: mesh hit but no bone resolved")

    # Priority logic rejected body mesh
    priority = entry.get('priority')
    if priority and priority.get('winner') == 'closest' and r2 and r2.get('hit'):
        anomalies.append(
            f"BODY_REJECTED: body mesh hit rejected (distance_diff={priority.get('distance_diff', '?')})")

    return anomalies


# ============================================================================
# DiagLogger class — singleton per modal session
# ============================================================================

class DiagLogger:
    _instance = None

    def __init__(self):
        self._file = None
        self._session_id = None
        self._event_seq = 0
        self._anomaly_count = 0
        self._last_hover_key = None  # (bone, mesh, armature) for dedup
        self._last_entry = None      # For amend_last_hover

    @classmethod
    def start_session(cls, **kwargs):
        """Create/open log file. Called from invoke()."""
        # Close any leftover session from a previous modal run
        if cls._instance and cls._instance._file:
            try:
                cls._instance._file.close()
            except Exception:
                pass
        cls._instance = cls()
        inst = cls._instance
        os.makedirs(DIAG_LOG_DIR, exist_ok=True)
        filepath = os.path.join(DIAG_LOG_DIR, DIAG_LOG_FILE)
        inst._file = open(filepath, 'a', encoding='utf-8')
        inst._session_id = f"{time.strftime('%Y%m%d_%H%M%S')}_{id(inst) & 0xFFFF:04x}"
        log.info(f"[DIAG] Session started — logging to {filepath}")
        inst._write_entry({
            'event': 'session_start',
            **kwargs,
        })

    @classmethod
    def end_session(cls):
        """Flush and close. Called from finish/cancel."""
        inst = cls._instance
        if not inst:
            return
        inst._write_entry({'event': 'session_end'})
        if inst._file:
            inst._file.flush()
            inst._file.close()
            inst._file = None
        cls._instance = None

    @classmethod
    def get(cls):
        return cls._instance

    def _write_entry(self, data):
        """Inject common fields, run anomaly detection, write JSON line."""
        if not self._file:
            return
        self._event_seq += 1
        entry = {
            'seq': self._event_seq,
            'ts': round(time.time(), 3),
            'session': self._session_id,
        }
        entry.update(data)

        # Run anomaly detection on hover/click events
        if entry.get('event') in ('hover', 'click'):
            anomalies = _detect_anomalies(entry)
            if anomalies:
                entry['anomalies'] = anomalies
                self._anomaly_count += len(anomalies)

        try:
            self._file.write(json.dumps(entry, default=_json_default) + '\n')
            self._file.flush()
        except Exception as e:
            log.warning(f"[DIAG] Write error: {e}")


# ============================================================================
# JSON serialization helper
# ============================================================================

def _json_default(obj):
    """Handle non-serializable types (Vector, Matrix, etc.)."""
    if hasattr(obj, '__iter__'):
        return list(obj)
    return str(obj)


def _round_vec(v, decimals=4):
    """Round a vector/tuple to N decimal places for compact output."""
    if v is None:
        return None
    return [round(x, decimals) for x in v]


# ============================================================================
# Public API — each guards on DIAG_ENABLED
# ============================================================================

def log_session_start(**kwargs):
    if not DIAG_ENABLED:
        return
    try:
        DiagLogger.start_session(**kwargs)
    except Exception as e:
        log.warning(f"[DIAG] ERROR in log_session_start: {e}")
        import traceback; traceback.print_exc()


def log_session_end():
    if not DIAG_ENABLED:
        return
    DiagLogger.end_session()


def log_hover(mouse=None, mouse_abs=None, viewport=None,
              raycast1_hit=False, raycast1_mesh=None, raycast1_location=None,
              raycast1_distance=None, raycast1_face_index=None,
              raycast2_hit=False, raycast2_mesh=None, raycast2_location=None,
              raycast2_distance=None, raycast2_is_evaluated=False,
              active_character=None, mode=None):
    """Log a hover event with dual-raycast data. Deduplicates repeated same-bone hovers."""
    if not DIAG_ENABLED:
        return
    inst = DiagLogger.get()
    if not inst:
        return

    entry = {
        'event': 'hover',
        'mouse': list(mouse) if mouse else None,
        'mouse_abs': list(mouse_abs) if mouse_abs else None,
        'viewport': viewport,
        'active_character': active_character,
        'mode': mode,
        'raycast1': {
            'hit': raycast1_hit,
            'mesh': raycast1_mesh,
            'location': _round_vec(raycast1_location),
            'distance': round(raycast1_distance, 4) if raycast1_distance is not None else None,
            'face_index': raycast1_face_index,
        },
        'raycast2': {
            'hit': raycast2_hit,
            'mesh': raycast2_mesh,
            'location': _round_vec(raycast2_location),
            'distance': round(raycast2_distance, 4) if raycast2_distance is not None else None,
            'is_evaluated': raycast2_is_evaluated,
        },
    }
    # Store for amend_last_hover
    inst._last_entry = entry
    # Don't write yet — wait for amend_last_hover to add bone resolution


def amend_last_hover(final_mesh=None, priority_winner=None, distance_diff=None,
                     raw_bone=None, mapped_bone=None, resolution_method=None,
                     armature=None):
    """Amend the last hover entry with bone resolution data, then write it."""
    if not DIAG_ENABLED:
        return
    inst = DiagLogger.get()
    if not inst or not inst._last_entry:
        return

    entry = inst._last_entry
    inst._last_entry = None

    entry['priority'] = {
        'winner': priority_winner,
        'distance_diff': round(distance_diff, 4) if distance_diff is not None else None,
    }
    entry['bone_resolution'] = {
        'method': resolution_method,
        'raw_bone': raw_bone,
        'mapped_bone': mapped_bone,
        'armature': armature,
    }

    # Deduplication: skip if same bone/mesh/armature and no anomalies
    hover_key = (raw_bone, final_mesh, armature)
    anomalies = _detect_anomalies(entry)
    if hover_key == inst._last_hover_key and not anomalies:
        return
    inst._last_hover_key = hover_key

    if anomalies:
        entry['anomalies'] = anomalies
        inst._anomaly_count += len(anomalies)

    inst._write_entry(entry)


def flush_pending_hover():
    """Write any pending hover entry that wasn't amended (e.g., no bone hit)."""
    if not DIAG_ENABLED:
        return
    inst = DiagLogger.get()
    if not inst or not inst._last_entry:
        return
    entry = inst._last_entry
    inst._last_entry = None

    # No bone resolution — still log it (miss case is interesting)
    entry['priority'] = {'winner': None, 'distance_diff': None}
    entry['bone_resolution'] = None

    hover_key = (None, None, None)
    anomalies = _detect_anomalies(entry)
    if hover_key == inst._last_hover_key and not anomalies:
        return
    inst._last_hover_key = hover_key

    if anomalies:
        entry['anomalies'] = anomalies
        inst._anomaly_count += len(anomalies)

    inst._write_entry(entry)


def log_click(mouse_abs=None, hover_bone=None, hover_armature=None,
              hover_from_posebridge=False, switch_to_character=None,
              is_double_click=False, active_character=None):
    if not DIAG_ENABLED:
        return
    inst = DiagLogger.get()
    if not inst:
        return
    inst._write_entry({
        'event': 'click',
        'mouse_abs': list(mouse_abs) if mouse_abs else None,
        'hover_bone': hover_bone,
        'hover_armature': hover_armature,
        'hover_from_posebridge': hover_from_posebridge,
        'switch_to_character': switch_to_character,
        'is_double_click': is_double_click,
        'active_character': active_character,
    })


def log_drag_start(bone=None, armature=None, drag_type=None,
                   from_posebridge=False, accumulated_px=None):
    if not DIAG_ENABLED:
        return
    inst = DiagLogger.get()
    if not inst:
        return
    inst._write_entry({
        'event': 'drag_start',
        'bone': bone,
        'armature': armature,
        'drag_type': drag_type,
        'from_posebridge': from_posebridge,
        'accumulated_px': round(accumulated_px, 1) if accumulated_px is not None else None,
    })


def log_drag_end(bone=None, cancel=False):
    if not DIAG_ENABLED:
        return
    inst = DiagLogger.get()
    if not inst:
        return
    inst._write_entry({
        'event': 'drag_end',
        'bone': bone,
        'cancel': cancel,
    })


def log_drag_end_state(bone_name=None, armature=None, bone_head_world=None,
                       bone_tail_world=None, mesh_name=None,
                       mesh_sample_verts=None, depsgraph_method=None):
    """Log bone/mesh world positions after drag-end + view_layer.update().
    Helps diagnose whether the depsgraph actually updated mesh geometry."""
    if not DIAG_ENABLED:
        return
    inst = DiagLogger.get()
    if not inst:
        return
    inst._write_entry({
        'event': 'drag_end_state',
        'bone': bone_name,
        'armature': armature,
        'bone_head_world': _round_vec(bone_head_world),
        'bone_tail_world': _round_vec(bone_tail_world),
        'mesh_name': mesh_name,
        'mesh_sample_verts': [_round_vec(v) for v in mesh_sample_verts] if mesh_sample_verts else None,
        'depsgraph_method': depsgraph_method,
    })


def log_character_switch(from_character=None, to_character=None,
                         body_meshes=None, fgm_keys=None):
    if not DIAG_ENABLED:
        return
    inst = DiagLogger.get()
    if not inst:
        return
    inst._write_entry({
        'event': 'character_switch',
        'from_character': from_character,
        'to_character': to_character,
        'cache_state': {
            'body_meshes': body_meshes or [],
            'fgm_keys': fgm_keys or [],
        },
    })


def log_click_through(hit_object=None, hit_type=None, reason=None):
    if not DIAG_ENABLED:
        return
    inst = DiagLogger.get()
    if not inst:
        return
    inst._write_entry({
        'event': 'click_through',
        'hit_object': hit_object,
        'hit_type': hit_type,
        'reason': reason,
    })


def log_pb_hover_bail(reason=None, active_panel=None, expected_cam=None,
                       viewport_cam=None, view_perspective=None,
                       active_index=None, num_slots=None,
                       has_armature=False, armature_name=None,
                       num_fixed_cps=None):
    """Log when check_posebridge_hover() bails out. Throttled: one per reason change."""
    if not DIAG_ENABLED:
        return
    inst = DiagLogger.get()
    if not inst:
        return
    # Deduplicate: only log when reason changes
    key = ('_pb_bail', reason, expected_cam, viewport_cam)
    if getattr(inst, '_last_pb_bail_key', None) == key:
        return
    inst._last_pb_bail_key = key
    inst._write_entry({
        'event': 'pb_hover_bail',
        'reason': reason,
        'active_panel': active_panel,
        'expected_cam': expected_cam,
        'viewport_cam': viewport_cam,
        'view_perspective': view_perspective,
        'active_index': active_index,
        'num_slots': num_slots,
        'has_armature': has_armature,
        'armature_name': armature_name,
        'num_fixed_cps': num_fixed_cps,
    })


def log_state_dump(trigger=None, **kwargs):
    if not DIAG_ENABLED:
        return
    inst = DiagLogger.get()
    if not inst:
        return
    inst._write_entry({
        'event': 'state_dump',
        'trigger': trigger,
        **kwargs,
    })
