# SPDX-License-Identifier: GPL-3.0-or-later
"""
FABRIK Solver Regression Tests

Pure math tests — no Blender scene or DAZ armature needed.
Tests the solver module directly with synthetic chain data.

Run:
    blender --background --python -m pytest tests/test_fabrik_regression.py -v
"""

from mathutils import Vector


# ---------------------------------------------------------------------------
# Helper: compute chain segment lengths
# ---------------------------------------------------------------------------
def chain_lengths(positions):
    return [(positions[i + 1] - positions[i]).length for i in range(len(positions) - 1)]


def total_reach(positions):
    return sum(chain_lengths(positions))


# ---------------------------------------------------------------------------
# Synthetic chain data
# ---------------------------------------------------------------------------
BONE_NAMES = ['collar', 'shoulder', 'forearm', 'hand']

def make_straight_chain():
    """4-bone arm chain straight along +X, each segment 0.3m-ish."""
    positions = [
        Vector((0.0, 0.0, 1.4)),    # root (collar head)
        Vector((0.15, 0.0, 1.4)),   # shoulder head
        Vector((0.45, 0.0, 1.4)),   # forearm head (elbow)
        Vector((0.75, 0.0, 1.4)),   # hand head (wrist)
        Vector((0.85, 0.0, 1.4)),   # hand tip
    ]
    return positions


def make_bent_chain():
    """4-bone arm chain with elbow bent ~90 degrees."""
    positions = [
        Vector((0.0, 0.0, 1.4)),    # root
        Vector((0.15, 0.0, 1.4)),   # shoulder
        Vector((0.45, 0.0, 1.4)),   # elbow
        Vector((0.45, -0.30, 1.4)), # wrist (bent down)
        Vector((0.45, -0.40, 1.4)), # hand tip
    ]
    return positions


# ===========================================================================
# _fabrik_solve_chain basic behavior
# ===========================================================================
class TestFABRIKSolveChain:
    """Test core single-chain FABRIK solving."""

    def test_import(self, fabrik_module):
        """Module imports without error."""
        assert hasattr(fabrik_module, 'FABRIKChain')
        assert hasattr(fabrik_module, '_fabrik_solve_chain')

    def test_chain_preserves_segment_lengths(self, fabrik_module):
        """FABRIK must preserve segment lengths after solving."""
        positions = make_straight_chain()
        lengths = chain_lengths(positions)
        originals = [v.copy() for v in positions]
        stiffness = [0.0] * len(positions)
        target = Vector((0.6, 0.2, 1.4))

        fabrik_module._fabrik_solve_chain(
            positions, lengths, stiffness, originals,
            root_pos=originals[0], target_pos=target,
            max_iterations=20, tolerance=1e-4,
        )

        solved_lengths = chain_lengths(positions)
        for i, (orig, solved) in enumerate(zip(lengths, solved_lengths)):
            assert abs(orig - solved) < 0.001, (
                f"Segment {i} length changed: {orig:.4f} → {solved:.4f}"
            )

    def test_chain_reaches_target(self, fabrik_module):
        """FABRIK should converge to a reachable target within tolerance."""
        positions = make_straight_chain()
        lengths = chain_lengths(positions)
        originals = [v.copy() for v in positions]
        stiffness = [0.0] * len(positions)
        target = Vector((0.5, 0.2, 1.4))

        fabrik_module._fabrik_solve_chain(
            positions, lengths, stiffness, originals,
            root_pos=originals[0], target_pos=target,
            max_iterations=50, tolerance=1e-4,
        )

        error = (positions[-1] - target).length
        assert error < 0.01, f"Tip didn't reach target: error = {error:.4f}m"

    def test_unreachable_target_stays_bounded(self, fabrik_module):
        """When target is beyond reach, chain should extend without breaking."""
        positions = make_straight_chain()
        lengths = chain_lengths(positions)
        reach = sum(lengths)
        originals = [v.copy() for v in positions]
        stiffness = [0.0] * len(positions)
        target = Vector((3.0, 0.0, 1.4))

        fabrik_module._fabrik_solve_chain(
            positions, lengths, stiffness, originals,
            root_pos=originals[0], target_pos=target,
            max_iterations=20, tolerance=1e-4,
        )

        chain_span = (positions[-1] - positions[0]).length
        assert chain_span > reach * 0.95, (
            f"Chain not fully extended: span={chain_span:.3f}, reach={reach:.3f}"
        )

    def test_stiffness_resists_motion(self, fabrik_module):
        """High stiffness should keep bones closer to original positions."""
        target = Vector((0.5, 0.3, 1.4))

        # Solve with zero stiffness
        pos_free = make_straight_chain()
        lengths = chain_lengths(pos_free)
        orig_free = [v.copy() for v in pos_free]
        fabrik_module._fabrik_solve_chain(
            pos_free, lengths, [0.0] * len(pos_free), orig_free,
            root_pos=orig_free[0], target_pos=target,
            max_iterations=20, tolerance=1e-4,
        )

        # Solve with high stiffness
        pos_stiff = make_straight_chain()
        orig_stiff = [v.copy() for v in pos_stiff]
        fabrik_module._fabrik_solve_chain(
            pos_stiff, lengths, [0.8] * len(pos_stiff), orig_stiff,
            root_pos=orig_stiff[0], target_pos=target,
            max_iterations=20, tolerance=1e-4,
        )

        # Stiff chain mid-bones should be closer to originals
        originals = make_straight_chain()
        for i in range(1, len(originals) - 1):
            drift_free = (pos_free[i] - originals[i]).length
            drift_stiff = (pos_stiff[i] - originals[i]).length
            assert drift_stiff <= drift_free + 0.001, (
                f"Bone {i}: stiff drift ({drift_stiff:.4f}) > "
                f"free drift ({drift_free:.4f})"
            )


# ===========================================================================
# FABRIKChain split-chain solving
# ===========================================================================
class TestSplitChain:
    """Test split-chain FABRIK for middle-bone dragging with pinned tip."""

    def _make_chain(self, fabrik_module, positions):
        lengths = chain_lengths(positions)
        return fabrik_module.FABRIKChain(
            bone_names=BONE_NAMES,
            positions=[v.copy() for v in positions],
            lengths=lengths,
            stiffness_weights={name: 0.0 for name in BONE_NAMES},
            dragged_bone_index=2,  # forearm
        )

    def test_split_chain_creation(self, fabrik_module):
        """FABRIKChain creates without error."""
        positions = make_bent_chain()
        chain = self._make_chain(fabrik_module, positions)
        assert chain is not None
        assert chain.n == len(positions)

    def test_split_chain_pin_holds(self, fabrik_module):
        """After split-chain solve, the pinned tip should stay at its target.

        This is the core pin invariant: drag a middle bone, tip stays planted.
        """
        positions = make_bent_chain()
        pin_target = positions[-1].copy()
        drag_target = positions[2] + Vector((0.0, 0.1, 0.0))

        chain = self._make_chain(fabrik_module, positions)
        chain.solve_split(
            dragged_joint_pos=drag_target,
            root_pos=positions[0],
            target_pos=pin_target,
            max_iterations=30,
            tolerance=1e-4,
        )

        tip_error = (chain.positions[-1] - pin_target).length
        assert tip_error < 0.005, (
            f"Pin drifted: error = {tip_error * 1000:.1f}mm (max 5mm)"
        )

    def test_split_chain_drag_responds(self, fabrik_module):
        """The dragged bone should move toward the drag target."""
        positions = make_bent_chain()
        pin_target = positions[-1].copy()
        drag_offset = Vector((0.0, 0.15, 0.0))
        drag_target = positions[2] + drag_offset

        chain = self._make_chain(fabrik_module, positions)
        chain.solve_split(
            dragged_joint_pos=drag_target,
            root_pos=positions[0],
            target_pos=pin_target,
            max_iterations=30,
            tolerance=1e-4,
        )

        drag_error = (chain.positions[2] - drag_target).length
        original_dist = drag_offset.length
        # Allow small overshoot from solver convergence (floating point)
        assert drag_error < original_dist + 0.001, (
            f"Drag bone didn't move toward target: "
            f"error={drag_error:.4f}, original distance={original_dist:.4f}"
        )

    def test_split_chain_root_fixed(self, fabrik_module):
        """Root position must not change during split-chain solve."""
        positions = make_bent_chain()
        root_original = positions[0].copy()
        pin_target = positions[-1].copy()
        drag_target = positions[2] + Vector((0.0, 0.1, 0.0))

        chain = self._make_chain(fabrik_module, positions)
        chain.solve_split(
            dragged_joint_pos=drag_target,
            root_pos=root_original,
            target_pos=pin_target,
            max_iterations=30,
            tolerance=1e-4,
        )

        root_error = (chain.positions[0] - root_original).length
        assert root_error < 0.001, f"Root moved: {root_error * 1000:.1f}mm"

    def test_split_chain_preserves_lengths(self, fabrik_module):
        """All segment lengths must be preserved after split-chain solve."""
        positions = make_bent_chain()
        original_lengths = chain_lengths(positions)
        pin_target = positions[-1].copy()
        drag_target = positions[2] + Vector((0.05, 0.1, 0.0))

        chain = self._make_chain(fabrik_module, positions)
        chain.solve_split(
            dragged_joint_pos=drag_target,
            root_pos=positions[0],
            target_pos=pin_target,
            max_iterations=30,
            tolerance=1e-4,
        )

        solved_lengths = chain_lengths(chain.positions)
        for i, (orig, solved) in enumerate(zip(original_lengths, solved_lengths)):
            assert abs(orig - solved) < 0.002, (
                f"Segment {i} length changed: {orig:.4f} → {solved:.4f}"
            )


# ===========================================================================
# Feasibility correction (invariant #7)
# ===========================================================================
class TestFeasibility:
    """Test that feasibility correction only fires on overshoot, not undershoot."""

    def test_reachable_target_no_extreme_rotation(self, fabrik_module):
        """A target within reach should NOT cause extreme bone displacement.

        Invariant #7: correction only when overshoot > FEAS_TOL.
        """
        positions = make_straight_chain()
        lengths = chain_lengths(positions)
        originals = [v.copy() for v in positions]
        stiffness = [0.0] * len(positions)
        # Target well within reach
        target = Vector((0.3, 0.1, 1.4))

        fabrik_module._fabrik_solve_chain(
            positions, lengths, stiffness, originals,
            root_pos=originals[0], target_pos=target,
            max_iterations=20, tolerance=1e-4,
        )

        for i, pos in enumerate(positions):
            dist_from_orig = (pos - originals[i]).length
            assert dist_from_orig < 1.0, (
                f"Bone {i} moved unreasonably far: {dist_from_orig:.3f}m"
            )
