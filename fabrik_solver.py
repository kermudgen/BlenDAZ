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
FABRIK (Forward And Backward Reaching Inverse Kinematics) Solver

Custom IK solver for DAZ-like posing with stiffness-weighted rotation distribution.
Used during drag interaction to replace Blender's native IK when pinned bones require
longer chains (e.g., forearm drag with pinned hand needs collar + spine engagement).

KEY DESIGN: Split-chain FABRIK for middle-bone dragging.

When the user drags a middle bone (e.g., forearm) while the tip (hand) is pinned:
- Standard FABRIK can't help because root is fixed and tip is already at its target.
- Solution: split at the dragged bone into two sub-chains:
  - Sub-chain A (root → dragged bone): spine/collar/shoulder adjust to reach new forearm pos
  - Sub-chain B (dragged bone → tip): forearm adjusts to reach pinned wrist
- Each sub-chain runs standard FABRIK independently.

Empirical calibration data from BlenDAZ Exploration project:
- 31 ActivePose capture sessions in DAZ Studio
- 60 professional pose presets analyzed
- Rotation distribution targets from DEEP_ANALYSIS_RESULTS.txt
"""

import logging
from mathutils import Vector, Quaternion

log = logging.getLogger(__name__)


# ============================================================================
# STIFFNESS WEIGHTS
# ============================================================================
# Per-bone resistance to FABRIK repositioning.
# 0.0 = fully compliant (absorbs most rotation)
# 1.0 = completely rigid (frozen in place)
#
# Calibrated from DAZ ActivePose capture data (Forearm Drag 01):
#   lShldrBend: 41.1% → low stiffness (absorbs most)
#   lCollar: 20.5% → moderate stiffness
#   chestLower: 14.2% → high stiffness (resists arm pulls)
#   abdomenUpper: 10.4% → higher stiffness
#   chestUpper: 5.8% → very high stiffness

FABRIK_STIFFNESS = {
    # Stiffness applied in backward pass only (tip→root).
    # 0.0 = fully compliant, 1.0 = frozen.
    #
    # DAZ "Forearm Drag 01" rotation distribution targets:
    #   lShldrBend 41.1%, lCollar 20.5%, chestLower 14.2%,
    #   abdomenUpper 10.4%, abdomenLower 6.3%, chestUpper 5.8%
    #
    # FABRIK only solves the ARM chain (collar → shoulder → forearm).
    # Spine engagement is injected post-solve via SPINE_ENGAGEMENT_RATIOS.
    "hip": 0.92,
    "pelvis": 0.92,
    "abdomenLower": 0.70,
    "abdomenUpper": 0.70,
    "chestLower": 0.60,
    "chestUpper": 0.65,
    "neckLower": 0.90,
    "neckUpper": 0.95,
    "head": 0.99,

    # Arm stiffness — collar absorbs ~20%, shoulder ~41%, forearm remainder
    "lCollar": 0.45,        # DAZ 20.5%
    "lShldrBend": 0.10,     # DAZ 41.1% — most compliant
    "lShldrTwist": 0.70,
    "lForearmBend": 0.10,
    "lForearmTwist": 0.75,
    "lHand": 0.95,

    # Right arm (mirror)
    "rCollar": 0.45,
    "rShldrBend": 0.10,
    "rShldrTwist": 0.70,
    "rForearmBend": 0.10,
    "rForearmTwist": 0.75,
    "rHand": 0.95,

    # Left leg
    "lThighBend": 0.15,
    "lThighTwist": 0.70,
    "lShin": 0.10,
    "lFoot": 0.20,

    # Right leg (mirror)
    "rThighBend": 0.15,
    "rThighTwist": 0.70,
    "rShin": 0.10,
    "rFoot": 0.20,

    # Pectorals (minor movers)
    "lPectoral": 0.85,
    "rPectoral": 0.85,
}

# ============================================================================
# SPINE ENGAGEMENT — Post-FABRIK injection
# ============================================================================
# DAZ engages the spine proportionally to arm displacement during forearm drags.
# FABRIK can't achieve this naturally (backward pass bias concentrates displacement
# at the tip end of the chain), so spine rotation is injected after the arm solve.
#
# Ratios from DAZ "Forearm Drag 01" (DEEP_ANALYSIS_RESULTS.txt):
#   chestLower: 14.2%, abdomenUpper: 10.4%, abdomenLower: 6.3%, chestUpper: 5.8%
#
# Only abdomenLower and abdomenUpper are injected post-solve.
# chestLower and chestUpper are in the FABRIK chain and handled by the solver.
#
# Relative distribution (normalized among injection bones only):
#   abdomenLower: 6.3%, abdomenUpper: 10.4% → ratio 0.38 : 0.62
SPINE_ENGAGEMENT_RATIOS = {
    'abdomenLower': 0.38,   #  6.3 / 16.7
    'abdomenUpper': 0.62,   # 10.4 / 16.7
}

# Spine bones that receive post-solve injection (root → tip order)
SPINE_BONES = ['abdomenLower', 'abdomenUpper']

# Maximum collar rotation in degrees (prevents over-rotation)
COLLAR_MAX_SWING_DEG = 25.0

# Twist bone pairs: bend_bone → twist_bone
# Twist bones don't participate in FABRIK positions but receive
# axial twist extracted from their bend partner post-solve.
TWIST_BONE_PAIRS = {
    "lShldrBend": "lShldrTwist",
    "rShldrBend": "rShldrTwist",
    "lForearmBend": "lForearmTwist",
    "rForearmBend": "rForearmTwist",
    "lThighBend": "lThighTwist",
    "rThighBend": "rThighTwist",
}

# How much twist goes to the twist bone (rest stays on bend bone)
# Based on DAZ's observed distribution
TWIST_DISTRIBUTION = {
    "lShldrBend": 0.5,    # 50% twist → lShldrTwist
    "rShldrBend": 0.5,
    "lForearmBend": 0.7,  # 70% twist → lForearmTwist
    "rForearmBend": 0.7,
    "lThighBend": 0.5,
    "rThighBend": 0.5,
}


# ============================================================================
# ARM CHAIN DEFINITIONS
# ============================================================================
# For forearm drag with pinned hand, the chain goes from spine through arm.
# Twist bones are EXCLUDED from FABRIK positions (handled post-solve).

ARM_CHAIN_BONES = {
    'l': ['chestLower', 'chestUpper', 'lCollar', 'lShldrBend', 'lForearmBend'],
    'r': ['chestLower', 'chestUpper', 'rCollar', 'rShldrBend', 'rForearmBend'],
}

# Extended chain includes abdomen (for larger drags)
ARM_CHAIN_BONES_EXTENDED = {
    'l': ['abdomenLower', 'abdomenUpper', 'chestLower', 'chestUpper', 'lCollar', 'lShldrBend', 'lForearmBend'],
    'r': ['abdomenLower', 'abdomenUpper', 'chestLower', 'chestUpper', 'rCollar', 'rShldrBend', 'rForearmBend'],
}


# ============================================================================
# FABRIK SINGLE-CHAIN SOLVER
# ============================================================================

def _fabrik_solve_chain(positions, lengths, stiffness, original_positions,
                        root_pos, target_pos, max_iterations=10, tolerance=0.001):
    """
    Core FABRIK solver for a single chain segment.

    Solves so positions[0] stays at root_pos and positions[-1] reaches target_pos.

    Stiffness is applied ONLY in the backward pass (tip→root). The forward pass
    is stiffness-free — it only restores segment lengths from the anchored root.

    Why: In standard FABRIK with stiffness in both passes, root-adjacent bones
    become almost immovable. The backward pass displaces them toward the target,
    but the forward pass immediately snaps them back via stiffness lerp. This
    compounds along the chain — each bone's effective stiffness multiplies with
    its ancestors'. Result: spine bones at the chain root never engage.

    With stiffness only in the backward pass, the backward pass establishes
    how much each bone yields (stiff bones resist, compliant bones absorb),
    then the forward pass redistributes segment lengths outward from the root
    without fighting the backward pass's displacement decisions.

    Args:
        positions: List of Vector — mutable, modified in-place
        lengths: List of float — segment lengths
        stiffness: List of float — per-joint stiffness (same length as positions)
        original_positions: List of Vector — starting positions for stiffness blending
        root_pos: Vector — fixed root position
        target_pos: Vector — desired tip position
        max_iterations: int
        tolerance: float (meters)

    Returns:
        int — iteration count at convergence, or -1 if didn't converge
    """
    n = len(positions)

    # Unreachable check
    total_length = sum(lengths)
    dist = (target_pos - root_pos).length
    if dist > total_length:
        direction = (target_pos - root_pos).normalized()
        positions[0] = root_pos.copy()
        for i in range(len(lengths)):
            positions[i + 1] = positions[i] + direction * lengths[i]
        return 0

    for iteration in range(max_iterations):
        tip_error = (positions[-1] - target_pos).length
        if tip_error < tolerance:
            break

        # BACKWARD PASS: tip → root (with stiffness)
        # Stiffness lerp pulls each joint toward its original position,
        # making stiff bones resist displacement from the target pull.
        positions[-1] = target_pos.copy()
        for i in range(n - 2, -1, -1):
            direction = positions[i] - positions[i + 1]
            if direction.length < 1e-8:
                direction = Vector((0, 1e-4, 0))
            direction.normalize()
            solved = positions[i + 1] + direction * lengths[i]
            s = stiffness[i]
            positions[i] = solved.lerp(original_positions[i], s) if s > 0.0 else solved

        # FORWARD PASS: root → tip (stiffness-free)
        # Only enforces segment lengths from the anchored root outward.
        # Does NOT pull bones back toward originals — preserves the
        # displacement pattern established by the backward pass.
        positions[0] = root_pos.copy()
        for i in range(n - 1):
            direction = positions[i + 1] - positions[i]
            if direction.length < 1e-8:
                direction = Vector((0, 1e-4, 0))
            direction.normalize()
            positions[i + 1] = positions[i] + direction * lengths[i]

    else:
        iteration = -1  # didn't converge

    # Final segment length enforcement (already stiffness-free above,
    # but ensure clean lengths after the last iteration's backward pass
    # if the loop exited via convergence before a forward pass).
    positions[0] = root_pos.copy()
    for i in range(n - 1):
        direction = positions[i + 1] - positions[i]
        if direction.length < 1e-8:
            direction = Vector((0, 1e-4, 0))
        direction.normalize()
        positions[i + 1] = positions[i] + direction * lengths[i]

    return iteration


class FABRIKChain:
    """
    Split-chain FABRIK solver for middle-bone dragging.

    When the user drags a bone in the middle of the chain (not the tip),
    the chain is split at the dragged bone into two sub-chains:
    - Sub-chain A: root → dragged bone (adjusts spine/collar/shoulder)
    - Sub-chain B: dragged bone → tip (adjusts forearm to reach pinned wrist)

    Each sub-chain runs standard FABRIK independently.
    """

    def __init__(self, bone_names, positions, lengths, stiffness_weights=None,
                 dragged_bone_index=None):
        """
        Args:
            bone_names: List of bone names root → tip
            positions: List of Vector — world-space joint positions (len = bone_names + 1)
                       [root_head, bone1_head, ..., tip_tail]
            lengths: List of float — segment lengths (len = bone_names)
            stiffness_weights: dict {bone_name: 0.0-1.0}
            dragged_bone_index: Index of dragged bone in bone_names (for split-chain)
        """
        assert len(positions) == len(bone_names) + 1
        assert len(lengths) == len(bone_names)

        self.bone_names = list(bone_names)
        self.positions = [p.copy() for p in positions]
        self.original_positions = [p.copy() for p in positions]
        self.lengths = list(lengths)
        self.n = len(self.positions)
        self.dragged_bone_index = dragged_bone_index

        # Per-joint stiffness array (index 0=root, index n-1=tip)
        self.stiffness = []
        for i, name in enumerate(bone_names):
            s = (stiffness_weights or {}).get(name, 0.0)
            self.stiffness.append(s)
        self.stiffness.append(0.0)  # tip

    def solve_split(self, dragged_joint_pos, root_pos, target_pos,
                    max_iterations=10, tolerance=0.001, debug=False):
        """
        Coupled split-chain solve for middle-bone dragging with a pinned tip.

        The chain is split at the dragged bone into two sub-chains:
        - Sub-chain A: root → dragged bone (spine/collar/shoulder adjust)
        - Sub-chain B: dragged bone → tip (forearm adjusts to reach pinned wrist)

        KEY INSIGHT: Sub-A's stiffness may prevent reaching the exact dragged
        position. If the resolved drag position is not at exactly Sub-B's chain
        length from the pinned wrist, Sub-B can't reach (a rigid rod can only
        span exactly its length). So after Sub-A solves, we project the split
        point onto the sphere of radius sub_b_reach centered at target_pos,
        then re-solve Sub-A to distribute the correction through the chain.

        Args:
            dragged_joint_pos: Vector — desired world position for dragged bone's head
            root_pos: Vector — fixed root (spine)
            target_pos: Vector — fixed tip (pinned wrist)
            max_iterations: int — per sub-chain FABRIK iterations
            tolerance: float (meters)
            debug: bool

        Returns:
            List of solved positions
        """
        d = self.dragged_bone_index
        if d is None or d <= 0 or d >= len(self.bone_names):
            return self._solve_standard(target_pos, root_pos, max_iterations, tolerance, debug)

        len_a = self.lengths[:d]
        stiff_a = self.stiffness[:d + 1]
        orig_a = self.original_positions[:d + 1]

        len_b = self.lengths[d:]
        stiff_b = self.stiffness[d:]
        orig_b = self.original_positions[d:]

        sub_b_reach = sum(len_b)

        if debug:
            print(f"\n  [FABRIK SPLIT] drag_idx={d} ({self.bone_names[d]})")
            print(f"    Sub-A: {d} segments, joints 0..{d}")
            print(f"    Sub-B: {len(len_b)} segments, joints {d}..{self.n - 1}, reach={sub_b_reach:.4f}m")
            print(f"    dragged_pos=({dragged_joint_pos.x:.4f},{dragged_joint_pos.y:.4f},{dragged_joint_pos.z:.4f})")
            print(f"    root_pos=({root_pos.x:.4f},{root_pos.y:.4f},{root_pos.z:.4f})")
            print(f"    target_pos=({target_pos.x:.4f},{target_pos.y:.4f},{target_pos.z:.4f})")

        # --- Phase 1: Solve Sub-A (root → dragged bone) ---
        pos_a = [self.positions[i].copy() for i in range(d + 1)]
        if len(pos_a) >= 2:
            _fabrik_solve_chain(
                pos_a, len_a, stiff_a, orig_a,
                root_pos=root_pos,
                target_pos=dragged_joint_pos,
                max_iterations=max_iterations,
                tolerance=tolerance
            )

        resolved_drag_pos = pos_a[-1].copy()

        # --- Phase 2: Feasibility check + projection ---
        # Only correct when the split point is FARTHER from target than Sub-B
        # can reach (truly unreachable). When the split point is CLOSER than
        # sub_b_reach, the sub-chain can fold to reach the target — no
        # correction needed. (Previously this projected both cases onto the
        # reach sphere, which caused extreme rotations when dragging bones
        # near the chain root, e.g. shoulder with pinned hand.)
        drag_to_target = target_pos - resolved_drag_pos
        dist_to_target = drag_to_target.length

        FEAS_TOL = 0.0005  # 0.5mm

        if dist_to_target < 1e-8:
            drag_to_target = Vector((0, 0, sub_b_reach))
            dist_to_target = sub_b_reach

        # Only correct when target is unreachable (too far), not when chain needs to fold (too close)
        overshoot = dist_to_target - sub_b_reach
        needs_correction = overshoot > FEAS_TOL

        if needs_correction:
            # Project split point onto sphere of radius sub_b_reach from target
            direction = (resolved_drag_pos - target_pos).normalized()
            feasible_pos = target_pos + direction * sub_b_reach

            if debug:
                print(f"    Feasibility: dist={dist_to_target:.4f}m, need={sub_b_reach:.4f}m, "
                      f"overshoot={overshoot:.4f}m → correcting")

            # Re-solve Sub-A targeting the feasible position
            pos_a = [self.original_positions[i].copy() for i in range(d + 1)]
            _fabrik_solve_chain(
                pos_a, len_a, stiff_a, orig_a,
                root_pos=root_pos,
                target_pos=feasible_pos,
                max_iterations=max_iterations,
                tolerance=tolerance
            )

            # Force the split point onto the feasibility sphere if stiffness
            # prevented exact convergence
            resolved_2 = pos_a[-1]
            gap_2 = abs((target_pos - resolved_2).length - sub_b_reach)
            if gap_2 > FEAS_TOL:
                dir_2 = (resolved_2 - target_pos)
                if dir_2.length > 1e-8:
                    dir_2.normalize()
                else:
                    dir_2 = (feasible_pos - target_pos).normalized()
                pos_a[-1] = target_pos + dir_2 * sub_b_reach

                # Redistribute correction through chain (stiffness-free pass)
                n_a = len(pos_a)
                if n_a >= 3:
                    forced_tip = pos_a[-1].copy()
                    pos_a[-1] = forced_tip
                    for j in range(n_a - 2, -1, -1):
                        d_vec = pos_a[j] - pos_a[j + 1]
                        if d_vec.length < 1e-8:
                            d_vec = Vector((0, 1e-4, 0))
                        d_vec.normalize()
                        pos_a[j] = pos_a[j + 1] + d_vec * len_a[j]
                    pos_a[0] = root_pos.copy()
                    for j in range(n_a - 1):
                        d_vec = pos_a[j + 1] - pos_a[j]
                        if d_vec.length < 1e-8:
                            d_vec = Vector((0, 1e-4, 0))
                        d_vec.normalize()
                        pos_a[j + 1] = pos_a[j] + d_vec * len_a[j]

                if debug:
                    seg_len_actual = (pos_a[-1] - pos_a[-2]).length if len(pos_a) >= 2 else 0
                    seg_len_expected = len_a[-1] if len_a else 0
                    print(f"    Force-projected split point, seg_len={seg_len_actual:.4f}m "
                          f"(expected {seg_len_expected:.4f}m, Δ={abs(seg_len_actual - seg_len_expected):.4f}m)")

        # Write Sub-A results
        for i in range(d + 1):
            self.positions[i] = pos_a[i]

        if debug:
            err_a = (self.positions[d] - dragged_joint_pos).length
            print(f"    Sub-A tip_err={err_a:.6f}m (from user's desired drag pos)")

        # --- Phase 3: Solve Sub-B with enforced root ---
        pos_b = [self.positions[d + i].copy() for i in range(self.n - d)]
        sub_b_root = self.positions[d].copy()

        if len(pos_b) >= 2:
            conv_b = _fabrik_solve_chain(
                pos_b, len_b, stiff_b, orig_b,
                root_pos=sub_b_root,
                target_pos=target_pos,
                max_iterations=max_iterations,
                tolerance=tolerance
            )
            if debug:
                err_b = (pos_b[-1] - target_pos).length
                print(f"    Sub-B converged={conv_b}, tip_err={err_b:.6f}m")

        # Write Sub-B results
        for i in range(len(pos_b)):
            self.positions[d + i] = pos_b[i]

        if debug:
            for j in range(self.n):
                name = self.bone_names[j] if j < len(self.bone_names) else "[tip]"
                p = self.positions[j]
                o = self.original_positions[j]
                delta = (p - o).length
                marker = " ← DRAGGED" if j == d else ""
                print(f"    [{j}] {name}: ({p.x:.4f},{p.y:.4f},{p.z:.4f}) moved={delta:.4f}m{marker}")
            wrist_err = (self.positions[-1] - target_pos).length
            print(f"    WRIST ACCURACY: {wrist_err:.6f}m")

        return self.positions

    def _solve_standard(self, target_pos, root_pos, max_iterations, tolerance, debug):
        """Fallback: standard tip-target FABRIK."""
        conv = _fabrik_solve_chain(
            self.positions, self.lengths, self.stiffness, self.original_positions,
            root_pos, target_pos, max_iterations, tolerance
        )
        if debug:
            err = (self.positions[-1] - target_pos).length
            print(f"  [FABRIK STD] converged={conv}, tip_err={err:.6f}m")
        return self.positions


# ============================================================================
# SPINE INJECTION — Post-FABRIK spine engagement
# ============================================================================

import math

def inject_spine_rotation(armature, side, chain_root_bone_name, original_rotations,
                          drag_delta_length, drag_delta=None, debug=False):
    """
    Inject spine rotation proportional to arm displacement after FABRIK solve.

    DAZ engages abdomenLower and abdomenUpper during arm drags proportionally
    to arm displacement. FABRIK only solves the arm chain (chestLower and up),
    so abdomen rotation is injected directly.

    The spine leans in the direction the arm is being pulled:
    - Lateral component (Z-axis): always toward the dragged arm side
    - Forward/back component (X-axis): follows the drag's vertical direction
      (drag up → spine extends back, drag down → spine flexes forward)

    Args:
        armature: Armature object
        side: 'l' or 'r'
        chain_root_bone_name: First bone in FABRIK chain (e.g. 'chestLower')
        original_rotations: dict {bone_name: Quaternion} at drag start
        drag_delta_length: float — magnitude of mouse drag delta (meters)
        drag_delta: Vector — 3D drag delta (world space), or None for lateral-only
        debug: bool

    Returns:
        dict {bone_name: Quaternion} — new rotation for each spine bone,
        or empty dict if no injection needed
    """
    if drag_delta_length < 0.01:
        return {}  # Dead zone — no spine engagement for tiny drags

    # Total spine rotation angle (degrees) scales with drag magnitude.
    # Ramp: 0° at 0.01m, linear up to max at ~0.3m drag
    ramp = min((drag_delta_length - 0.01) / 0.29, 1.0)
    # Max total spine rotation ~8° (split between 2 abdomen bones)
    max_total_spine_deg = 8.0
    total_spine_deg = ramp * max_total_spine_deg

    if total_spine_deg < 0.1:
        return {}

    # Compute directional weights for lateral (Z) and sagittal (X) components.
    # DAZ spine bones: X = forward/back (pitch), Z = side-to-side (lateral lean).
    # The spine should lean in the direction the arm pulls.
    lateral_sign = -1.0 if side == 'l' else 1.0  # Lean toward dragged side

    # Default: pure lateral lean (backward compatibility)
    lateral_weight = 1.0
    sagittal_weight = 0.0

    if drag_delta is not None and drag_delta.length > 0.001:
        # Convert world-space drag direction to spine-relative components.
        # In Blender world space: Z = up, Y = forward, X = right
        # In DAZ bone local space: X = pitch (forward/back), Z = lateral
        dd = drag_delta.normalized()
        # Vertical component: drag up (Z+) → spine extends (negative X rotation)
        # Drag down (Z-) → spine flexes forward (positive X rotation)
        vert = -dd.z  # Negate: up drag → negative pitch (extension)
        # Lateral component: always present, toward the arm side
        lat = abs(dd.x) + 0.3  # Bias toward lateral — always some side lean

        # Normalize weights so they sum to 1
        total_w = abs(vert) + lat
        if total_w > 0.001:
            sagittal_weight = abs(vert) / total_w
            lateral_weight = lat / total_w
            sagittal_sign = 1.0 if vert >= 0 else -1.0
        else:
            sagittal_sign = 0.0

        if debug:
            print(f"    [SPINE INJECT] direction: vert={dd.z:.2f} lat_w={lateral_weight:.2f} "
                  f"sag_w={sagittal_weight:.2f} sag_sign={sagittal_sign:.1f}")
    else:
        sagittal_sign = 0.0

    rotations = {}
    for bone_name in SPINE_BONES:
        ratio = SPINE_ENGAGEMENT_RATIOS.get(bone_name, 0.0)
        if ratio < 0.01:
            continue

        pose_bone = armature.pose.bones.get(bone_name)
        if not pose_bone:
            continue

        orig_rot = original_rotations.get(bone_name)
        if orig_rot is None:
            continue

        # Rotation angle for this bone
        angle_deg = total_spine_deg * ratio
        angle_rad = math.radians(angle_deg)

        # Compose lateral (Z) and sagittal (X) rotations
        lateral_rad = angle_rad * lateral_weight * lateral_sign
        sagittal_rad = angle_rad * sagittal_weight * sagittal_sign

        # Build combined injection quaternion
        quat_z = Quaternion(Vector((0, 0, 1)), lateral_rad)
        quat_x = Quaternion(Vector((1, 0, 0)), sagittal_rad)
        injection_quat = quat_z @ quat_x

        # Compose: new_rot = injection @ original
        new_rot = injection_quat @ orig_rot

        # Hemisphere align
        if new_rot.dot(orig_rot) < 0:
            new_rot.negate()

        rotations[bone_name] = new_rot

        if debug:
            print(f"    [SPINE INJECT] {bone_name}: {angle_deg:.1f}° "
                  f"(ratio={ratio:.2f}, total={total_spine_deg:.1f}°, "
                  f"lat={math.degrees(lateral_rad):.1f}° sag={math.degrees(sagittal_rad):.1f}°)")

    return rotations


def compute_spine_chain_root_shift(armature, spine_rotations, chain_root_bone_name,
                                    original_rotations, original_root_world=None,
                                    debug=False):
    """
    Compute how much the FABRIK chain root shifts due to spine injection,
    and return reconstructed posed matrices for spine bones.

    Spine injection rotates abdomenLower/abdomenUpper. The FABRIK chain root
    (chestLower.head) sits on top of these bones, so its world position moves.
    The caller uses the shift to adjust FABRIK solved positions, and the
    reconstructed matrices to seed FK extraction so it uses the correct
    parent matrices (not stale Blender-cached ones).

    Args:
        armature: Armature object
        spine_rotations: dict {bone_name: Quaternion} from inject_spine_rotation()
        chain_root_bone_name: First FABRIK chain bone (e.g. 'chestLower')
        original_rotations: dict {bone_name: Quaternion} at drag start
        original_root_world: Vector — original chain root world position (from
            FABRIK chain's original_positions[0]). If None, reads from live
            pose_bone.head (may be stale without view_layer.update()).
        debug: bool

    Returns:
        tuple (shift, spine_posed_matrices) where:
            shift: Vector — world-space displacement of chain root
            spine_posed_matrices: dict {bone_name: Matrix 4x4 armature-space}
                for pre-populating extract_rotations_from_positions()'s
                reconstructed_posed dict
    """
    from mathutils import Matrix

    empty = (Vector((0, 0, 0)), {})

    if not spine_rotations:
        return empty

    chain_root_pb = armature.pose.bones.get(chain_root_bone_name)
    if not chain_root_pb:
        return empty

    # Original chain root head in world space
    if original_root_world is not None:
        original_root_head = original_root_world.copy()
    else:
        original_root_head = armature.matrix_world @ chain_root_pb.head

    armature_world = armature.matrix_world

    # Find the lowest modified spine bone
    first_modified = None
    for bone_name in SPINE_BONES:
        if bone_name in spine_rotations:
            first_modified = bone_name
            break

    if first_modified is None:
        return empty

    first_pb = armature.pose.bones.get(first_modified)
    if not first_pb:
        return empty

    # Anchor at the parent of the first modified bone (unmodified)
    if first_pb.parent:
        parent_posed = first_pb.parent.matrix.copy()  # armature-space
    else:
        parent_posed = Matrix.Identity(4)

    spine_posed_matrices = {}

    # Walk through injection spine bones, building FK
    for bone_name in SPINE_BONES:
        pb = armature.pose.bones.get(bone_name)
        if not pb:
            continue
        data_bone = armature.data.bones.get(bone_name)
        if not data_bone:
            continue

        if pb.parent:
            parent_rest = pb.parent.bone.matrix_local
        else:
            parent_rest = Matrix.Identity(4)
        rest_offset = parent_rest.inverted() @ data_bone.matrix_local
        base_frame = parent_posed @ rest_offset

        rot = spine_rotations.get(bone_name) or original_rotations.get(bone_name, Quaternion())
        rot_mat = rot.to_matrix().to_4x4()
        parent_posed = base_frame @ rot_mat

        # Store the posed matrix for this spine bone
        spine_posed_matrices[bone_name] = parent_posed.copy()

    # parent_posed is now abdomenUpper's posed matrix. Reconstruct chestLower's head.
    chain_root_data = armature.data.bones.get(chain_root_bone_name)
    if not chain_root_data:
        return empty

    # chestLower's parent is abdomenUpper
    abdomen_upper_pb = armature.pose.bones.get('abdomenUpper')
    if abdomen_upper_pb:
        parent_rest = abdomen_upper_pb.bone.matrix_local
    else:
        parent_rest = Matrix.Identity(4)
    root_rest_offset = parent_rest.inverted() @ chain_root_data.matrix_local
    root_base = parent_posed @ root_rest_offset

    new_root_head_arm = root_base.translation
    new_root_head_world = armature_world @ new_root_head_arm

    shift = new_root_head_world - original_root_head

    if debug:
        print(f"    [SPINE SHIFT] chain root ({chain_root_bone_name}) shift: "
              f"({shift.x:.4f},{shift.y:.4f},{shift.z:.4f}) len={shift.length:.4f}m")

    return shift, spine_posed_matrices


# ============================================================================
# ROTATION EXTRACTION — FK Reconstruction
# ============================================================================

def _get_parent_posed_matrix(pose_bone, reconstructed_posed, chain_bone_set,
                              original_rotations):
    """
    Get the parent's posed matrix in armature space, handling skipped bones.

    For chain bones: uses reconstructed_posed (our FK propagation).
    For non-chain bones whose ancestors are all outside the chain: reads
    Blender's live pose_bone.matrix (safe — we never modify those bones).
    For non-chain bones that sit BETWEEN chain members (e.g., twist bones
    like lShldrTwist between lShldrBend and lForearmBend): reconstructs
    from the chain ancestor's reconstructed matrix + rest offset + the
    skipped bone's original rotation.

    Args:
        pose_bone: The PoseBone whose parent matrix we need
        reconstructed_posed: dict {bone_name: Matrix} of chain bones we've processed
        chain_bone_set: set of bone names in the FABRIK chain
        original_rotations: dict {bone_name: Quaternion} for reconstructing skipped bones

    Returns:
        Matrix (4x4, armature-space) or None if no parent
    """
    if not pose_bone.parent:
        return None

    parent = pose_bone.parent

    # Fast path: parent already reconstructed (chain bone processed earlier)
    if parent.name in reconstructed_posed:
        return reconstructed_posed[parent.name]

    # Walk up ancestors to find one in reconstructed_posed or confirm
    # we're entirely outside the chain
    skipped = [parent]
    ancestor = parent.parent
    while ancestor:
        if ancestor.name in reconstructed_posed:
            # Found a chain ancestor — must reconstruct skipped bones
            break
        if ancestor.name in chain_bone_set:
            # Chain bone not yet reconstructed — shouldn't happen in root→tip
            break
        skipped.append(ancestor)
        ancestor = ancestor.parent

    if ancestor and ancestor.name in reconstructed_posed:
        # We have a chain ancestor that's been reconstructed.
        # Reconstruct each skipped bone (e.g., twist bones) top-down.
        current_posed = reconstructed_posed[ancestor.name]
        for skipped_bone in reversed(skipped):
            skipped_data = skipped_bone.bone
            par_rest = (skipped_bone.parent.bone.matrix_local
                        if skipped_bone.parent else skipped_data.matrix_local)
            rest_off = par_rest.inverted() @ skipped_data.matrix_local
            orig_rot = original_rotations.get(skipped_bone.name, Quaternion())
            rot_mat = orig_rot.to_matrix().to_4x4()
            current_posed = current_posed @ rest_off @ rot_mat
            reconstructed_posed[skipped_bone.name] = current_posed
        return current_posed

    # All ancestors are outside the chain — safe to read live matrix
    return parent.matrix.copy()


def _compute_local_child_offset(armature, chain_bone, next_chain_bone, original_rotations):
    """
    Compute where next_chain_bone's head ends up in chain_bone's local space,
    accounting for intermediate bones (twist bones) with their original rotations.

    At rest (identity rotations), this equals:
        chain_bone.matrix_local.inv @ next_chain_bone.head_local

    But if twist bones between them have non-identity original_rotations,
    the effective offset changes. We must match what _get_parent_posed_matrix()
    will produce when reconstructing skipped bones.

    Args:
        armature: Armature object
        chain_bone: data bone (Bone) for the current chain bone
        next_chain_bone: data bone (Bone) for the next chain bone
        original_rotations: dict {bone_name: Quaternion}

    Returns:
        Vector — offset from chain_bone's origin to next_chain_bone's head
                 in chain_bone's local coordinate frame
    """
    from mathutils import Matrix

    # Walk the actual Blender hierarchy from chain_bone to next_chain_bone
    # to find all intermediate bones
    pose_bones = armature.pose.bones
    next_pb = pose_bones.get(next_chain_bone.name)
    if not next_pb:
        # Fallback: direct rest-pose computation
        return chain_bone.matrix_local.inverted() @ Vector(next_chain_bone.head_local)

    # Collect intermediate bones from next_chain_bone up to chain_bone
    intermediates = []
    current = next_pb.parent
    while current and current.bone.name != chain_bone.name:
        intermediates.append(current)
        current = current.parent

    if not intermediates:
        # Direct parent-child — no intermediates, rest offset is exact
        return chain_bone.matrix_local.inverted() @ Vector(next_chain_bone.head_local)

    # Build the FK chain from chain_bone through intermediates to next_chain_bone
    # in chain_bone's local space. Start with identity (chain_bone's local origin).
    # Apply: rest_off_intermediate @ orig_rot_intermediate for each intermediate,
    # then rest_off_next to get next_chain_bone's head.
    current_mat = Matrix.Identity(4)  # in chain_bone's local frame

    # Intermediates are collected child→parent, reverse to parent→child order
    for intermediate in reversed(intermediates):
        int_data = intermediate.bone
        # rest_offset from parent to this intermediate
        par_rest = intermediate.parent.bone.matrix_local if intermediate.parent else int_data.matrix_local
        rest_off = par_rest.inverted() @ int_data.matrix_local
        # Original rotation of this intermediate bone
        orig_rot = original_rotations.get(intermediate.name, Quaternion())
        rot_mat = orig_rot.to_matrix().to_4x4()
        current_mat = current_mat @ rest_off @ rot_mat

    # Final rest_offset from last intermediate to next_chain_bone
    last_intermediate = intermediates[0]  # closest parent of next_chain_bone
    rest_off_final = last_intermediate.bone.matrix_local.inverted() @ next_chain_bone.matrix_local

    current_mat = current_mat @ rest_off_final

    # current_mat.translation = next_chain_bone's head in chain_bone's local frame
    return current_mat.translation.copy()


def extract_rotations_from_positions(armature, bone_names, solved_positions,
                                     original_positions, original_rotations,
                                     original_matrices=None, pinned_bone_name=None,
                                     pre_reconstructed=None, debug=True):
    """
    Convert FABRIK-solved world-space positions to bone rotation_quaternion values.

    APPROACH: FK reconstruction with child-head targeting. For each bone (root→tip):
    1. Get parent's posed matrix (reconstructed for chain bones, live for others)
    2. Compute rest_offset = how this bone sits relative to parent at rest
    3. base_frame = parent_posed @ rest_offset (bone's frame with identity rotation)
    4. Compute local_child_head = next chain bone's head in THIS bone's local space
    5. Find rotation that maps local_child_head direction → FABRIK target direction
    6. Preserve original axial twist (FABRIK only solves 2-DOF swing)

    KEY INSIGHT: bone.length (head→tail) != FABRIK segment length (head→head).
    DAZ rig bones have tails that don't coincide with the next bone's head.
    We rotate the actual child-head offset vector (not the Y-axis) so that FK
    propagation through rest_offset places each child at the correct position.

    Non-chain bones (ancestors above root) are never modified during drag,
    so their live pose_bone.matrix is always correct. Chain bones use our
    own reconstructed_posed dict for FK propagation.

    Works without view_layer.update() — propagates its own FK for chain bones.

    Args:
        armature: Armature object
        bone_names: List of bone names in chain order (root → tip)
        solved_positions: List of Vector (len = bone_names + 1) — world space
        original_positions: List of Vector (len = bone_names + 1) — at drag start
        original_rotations: dict {bone_name: Quaternion} — at drag start
        original_matrices: dict {bone_name: Matrix} — (unused, kept for API compat)
        pinned_bone_name: str — name of pinned bone (e.g. 'lHand') for last segment
        pre_reconstructed: dict {bone_name: Matrix 4x4 armature-space} — pre-populated
            posed matrices for bones outside the chain (e.g., spine bones after
            injection). Used so _get_parent_posed_matrix finds correct parent
            matrices instead of stale Blender-cached ones.
        debug: bool

    Returns:
        tuple (rotations, reconstructed_posed) where:
            rotations: dict {bone_name: Quaternion}
            reconstructed_posed: dict {bone_name: Matrix 4x4 armature-space}
    """
    from mathutils import Matrix
    from .daz_shared_utils import decompose_swing_twist

    rotations = {}
    reconstructed_posed = dict(pre_reconstructed) if pre_reconstructed else {}
    chain_bone_set = set(bone_names)

    if debug:
        print(f"\n  [FABRIK ROT] === FK extraction for {len(bone_names)} bones ===")

    armature_world = armature.matrix_world
    armature_world_inv = armature_world.inverted()

    for i, bone_name in enumerate(bone_names):
        orig_rot = original_rotations.get(bone_name, Quaternion())
        pose_bone = armature.pose.bones.get(bone_name)
        data_bone = armature.data.bones.get(bone_name) if pose_bone else None

        if not pose_bone or not data_bone:
            rotations[bone_name] = orig_rot.copy()
            continue

        # --- Compute base frame ---
        # Blender formula:
        #   child.matrix = parent.matrix @ parent.bone.matrix_local.inv @ child.bone.matrix_local @ child.matrix_basis
        # base_frame (before child's own rotation):
        #   = parent.matrix @ parent.bone.matrix_local.inv @ child.bone.matrix_local
        parent_posed = _get_parent_posed_matrix(
            pose_bone, reconstructed_posed, chain_bone_set, original_rotations)
        if parent_posed is None:
            parent_posed = Matrix.Identity(4)

        if pose_bone.parent:
            parent_rest = pose_bone.parent.bone.matrix_local
        else:
            parent_rest = Matrix.Identity(4)
        rest_offset = parent_rest.inverted() @ data_bone.matrix_local

        base_frame = parent_posed @ rest_offset

        # --- Compute rotation to place NEXT chain bone's head at FABRIK target ---
        #
        # KEY INSIGHT: bone.length (head→tail) != FABRIK segment length (head→head).
        # In DAZ rigs, parent tail often doesn't coincide with child head.
        # The old approach aimed the bone's Y-axis (which extends bone.length) at
        # the FABRIK target (at head-to-head distance). This creates cascading
        # FK propagation errors because Blender uses the REAL rest geometry.
        #
        # FIX: Compute where the next chain bone's head sits in THIS bone's
        # local space at rest, then rotate THAT vector toward the FABRIK target.
        # This way, FK propagation through rest_offset places the child correctly.

        # Desired position for the NEXT joint in armature space
        target_next_arm = armature_world_inv @ solved_positions[i + 1]

        # Bone head in armature space from our FK reconstruction
        bone_head_arm = base_frame.translation

        # Desired direction in armature space
        desired_dir_arm = target_next_arm - bone_head_arm
        desired_len = desired_dir_arm.length
        if desired_len < 1e-8:
            rotations[bone_name] = orig_rot.copy()
            reconstructed_posed[bone_name] = base_frame @ orig_rot.to_matrix().to_4x4()
            continue
        desired_dir_arm = desired_dir_arm / desired_len

        # Compute where the next chain bone's head ends up in THIS bone's
        # local space, accounting for intermediate twist bones with their
        # original rotations. This must match what _get_parent_posed_matrix()
        # produces when reconstructing skipped bones.
        if i + 1 < len(bone_names):
            next_bone_name = bone_names[i + 1]
            next_data_bone = armature.data.bones.get(next_bone_name)
        else:
            # Last bone in chain — target is the pinned bone (e.g., lHand)
            # or the bone's own tail if no pinned bone specified
            next_data_bone = None
            if pinned_bone_name:
                next_data_bone = armature.data.bones.get(pinned_bone_name)

        if next_data_bone is not None:
            local_child_head = _compute_local_child_offset(
                armature, data_bone, next_data_bone, original_rotations)
        else:
            # Fallback: bone's tail (no pinned bone or not found)
            local_child_head = Vector((0, data_bone.length, 0))

        # The direction from this bone's local origin to the child's head
        local_child_dir = local_child_head.normalized()
        if local_child_dir.length < 1e-8:
            local_child_dir = Vector((0, 1, 0))

        # Convert desired direction to bone-local space
        # base_frame.to_3x3() maps bone-local → armature space
        base_rot_inv = base_frame.to_3x3().inverted()
        desired_dir_local = (base_rot_inv @ desired_dir_arm).normalized()

        # Preserve original twist (rotation around bone Y-axis)
        # FABRIK only controls bone direction (2 DOF), not axial roll (3rd DOF)
        _, orig_twist = decompose_swing_twist(orig_rot, 'Y')

        # CRITICAL: new_rotation = new_swing @ orig_twist means orig_twist
        # is applied FIRST, then new_swing. So new_swing must map the
        # TWISTED child direction to desired_dir_local, not the original.
        # If local_child_head is off the Y-axis (lcd_off_Y > 0), orig_twist
        # rotates it to a different direction before new_swing acts.
        twisted_child_dir = (orig_twist.to_matrix() @ local_child_head).normalized()
        if twisted_child_dir.length < 1e-8:
            twisted_child_dir = local_child_dir

        # Find swing that maps (orig_twist @ local_child_head) → desired_dir_local
        new_swing = twisted_child_dir.rotation_difference(desired_dir_local)

        # Combine: orig_twist preserves axial roll, new_swing points the bone
        new_rotation = new_swing @ orig_twist

        # Hemisphere align with original to prevent quaternion flipping
        if new_rotation.dot(orig_rot) < 0:
            new_rotation.negate()

        rotations[bone_name] = new_rotation

        # Reconstruct this bone's posed matrix for child FK propagation
        rot_mat = new_rotation.to_matrix().to_4x4()
        reconstructed_posed[bone_name] = base_frame @ rot_mat

        if debug:
            orig_angle = orig_rot.angle * 57.2958 if orig_rot.angle else 0
            new_angle = new_rotation.angle * 57.2958 if new_rotation.angle else 0
            swing_angle = new_swing.angle * 57.2958 if new_swing.angle else 0
            twist_angle = orig_twist.angle * 57.2958 if orig_twist.angle else 0
            # Verify: compute where next chain bone's head ends up via FK
            actual_child_local = new_rotation.to_matrix() @ local_child_head
            actual_child_arm = bone_head_arm + base_frame.to_3x3() @ actual_child_local
            actual_child_world = armature_world @ actual_child_arm
            child_err = (actual_child_world - solved_positions[i + 1]).length
            # FK head vs FABRIK head divergence
            fabrik_head_arm = armature_world_inv @ solved_positions[i]
            head_err = (bone_head_arm - fabrik_head_arm).length
            # Distance comparison: FK child distance vs FABRIK target distance
            lcd_len = local_child_head.length
            print(f"  [FABRIK ROT]   {bone_name}: "
                  f"swing={swing_angle:.1f}° twist={twist_angle:.1f}° rot={new_angle:.1f}° (was {orig_angle:.1f}°) "
                  f"head_err={head_err:.4f}m child_err={child_err:.4f}m "
                  f"lcd_len={lcd_len:.4f}m fabrik_len={desired_len:.4f}m")

    return rotations, reconstructed_posed


# ============================================================================
# CHAIN BUILDER
# ============================================================================

def build_arm_fabrik_chain(armature, side, dragged_bone_name, pinned_bone_name=None,
                           extended=False):
    """
    Build a FABRIK chain for arm drag with pinned hand.

    The FABRIK tip represents the pinned bone (lHand.head). The last segment
    spans from lForearmBend.head through lForearmTwist to lHand.head, so the
    solver naturally keeps the hand planted without twist bone compensation.

    Args:
        armature: Armature object
        side: 'l' or 'r'
        dragged_bone_name: Name of bone being dragged (e.g., 'lForearmBend')
        pinned_bone_name: Name of pinned bone (e.g., 'lHand') — used for last segment
        extended: If True, include abdomen bones for larger drags

    Returns:
        FABRIKChain instance (with dragged_bone_index set), or None
    """
    chain_def = ARM_CHAIN_BONES_EXTENDED[side] if extended else ARM_CHAIN_BONES[side]
    pose_bones = armature.pose.bones

    bone_names = []
    dragged_idx = None
    for name in chain_def:
        if name not in pose_bones:
            log.warning(f"  FABRIK: chain bone '{name}' not found, skipping")
            continue
        if name == dragged_bone_name:
            dragged_idx = len(bone_names)
        bone_names.append(name)

    if len(bone_names) < 2:
        log.warning(f"  FABRIK: too few bones ({len(bone_names)})")
        return None

    if dragged_idx is None:
        # Dragged bone not in chain — use last bone
        log.warning(f"  FABRIK: dragged bone '{dragged_bone_name}' not in chain, using last")
        dragged_idx = len(bone_names) - 1

    # Collect world-space positions (from current pose for FABRIK starting state)
    positions = []
    for name in bone_names:
        pb = pose_bones[name]
        positions.append((armature.matrix_world @ pb.head).copy())

    # Tip position: where the pinned bone's head is.
    # If pinned_bone_name is given (e.g., 'lHand'), use its head position.
    # The FABRIK tip represents lHand.head, so the solver keeps it planted.
    pinned_data = armature.data.bones.get(pinned_bone_name) if pinned_bone_name else None
    if pinned_bone_name and pinned_bone_name in pose_bones:
        pinned_pb = pose_bones[pinned_bone_name]
        positions.append((armature.matrix_world @ pinned_pb.head).copy())
    else:
        # Fallback: tail of last chain bone
        last_pb = pose_bones[bone_names[-1]]
        positions.append((armature.matrix_world @ last_pb.tail).copy())

    # Segment lengths from REST-POSE bone-local child offsets.
    # CRITICAL: These must match the |local_child_head| values used in
    # extract_rotations_from_positions(), because Blender FK always places
    # children at the rest-offset distance regardless of how FABRIK positions
    # the joints. If FABRIK uses different lengths, the solved positions
    # diverge from FK propagation and errors accumulate down the chain.
    orig_rots = {name: pose_bones[name].rotation_quaternion.copy()
                 for name in bone_names if name in pose_bones}
    # Also include twist bone rotations for intermediate offset computation
    for bn in list(orig_rots.keys()):
        tn = TWIST_BONE_PAIRS.get(bn)
        if tn and tn in pose_bones:
            orig_rots[tn] = pose_bones[tn].rotation_quaternion.copy()

    lengths = []
    for i in range(len(bone_names) - 1):
        data_bone = armature.data.bones[bone_names[i]]
        next_data_bone = armature.data.bones[bone_names[i + 1]]
        local_offset = _compute_local_child_offset(
            armature, data_bone, next_data_bone, orig_rots)
        seg = local_offset.length
        lengths.append(max(seg, 0.001))

    # Last segment: FK distance from last chain bone to PINNED bone (lHand).
    # This spans through intermediate bones (lForearmTwist) so the solver
    # naturally accounts for the full FK path, keeping lHand planted.
    last_data = armature.data.bones[bone_names[-1]]
    if pinned_data is not None:
        last_offset = _compute_local_child_offset(
            armature, last_data, pinned_data, orig_rots)
        lengths.append(max(last_offset.length, 0.001))
    else:
        lengths.append(max(last_data.length, 0.001))

    # Stiffness
    stiffness = {name: FABRIK_STIFFNESS.get(name, 0.3) for name in bone_names}

    chain = FABRIKChain(
        bone_names=bone_names,
        positions=positions,
        lengths=lengths,
        stiffness_weights=stiffness,
        dragged_bone_index=dragged_idx
    )

    log.info(f"  FABRIK chain: {' → '.join(bone_names)} (drag={bone_names[dragged_idx]})")
    return chain


def get_pinned_position(armature, pinned_bone_name):
    """
    Get the world-space position that the pinned bone should maintain.

    Args:
        armature: Armature object
        pinned_bone_name: Name of the pinned bone (e.g., 'lHand')

    Returns:
        Vector — world-space target position, or None
    """
    import bpy

    pin_empty_name = f"PIN_translation_{armature.name}_{pinned_bone_name}"
    pin_empty = bpy.data.objects.get(pin_empty_name)
    if pin_empty:
        return pin_empty.matrix_world.translation.copy()

    pose_bone = armature.pose.bones.get(pinned_bone_name)
    if pose_bone:
        return (armature.matrix_world @ pose_bone.head).copy()

    return None
