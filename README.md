# BlenDAZ - DAZ Bone Select & IK

Blender addon for DAZ figures with intuitive bone selection and temporary IK rigging.

## Features

- **Hover Preview**: Hover over mesh to preview which bone you'll select
- **Click-Drag IK**: Click and drag bones to pose with temporary IK chains
- **Smart IK Chains**: Automatically creates appropriate chain lengths for different bone types
- **Rotation Limits**: Respects joint limits during IK solving (based on Diffeomorphic/RigOnTheFly best practices)
- **Stable IK**: Uses quaternions to prevent flipping and gimbal lock
- **Tip Bone Isolation**: End effector (foot/hand) rotation is independent from IK chain

## Installation

1. Open Blender
2. Edit → Preferences → Add-ons
3. Click "Install" and select `daz_bone_select.py`
4. Enable "DAZ Bone Select & Pin"

## Usage

- **Ctrl+Shift+D**: Activate the tool
- **Hover**: Preview bone under cursor
- **Click**: Select bone
- **Click-Drag**: Create temporary IK chain and drag
- **R**: Rotate end effector (rotation persists between drags)
- **P**: Pin translation
- **Shift+P**: Pin rotation
- **U**: Unpin
- **ESC**: Exit tool

## Technical Details

### IK Architecture (Diffeomorphic-inspired)
- Bone targets (not empties) for stability
- Copy Rotation constraints for FK baking
- Quaternion rotation mode for stability
- Rotation limits NOT copied to IK limits (IK solves freely, limits clamp result)
- Tip bone excluded from Copy Rotation (preserves manual rotations)

### Key Improvements (Phase 1)
- Force quaternion mode on .ik control bones
- Increased knee nudge from 0.1 to 0.3 radians
- Skip tip bone from Copy Rotation and keyframing
- Read from evaluated depsgraph for proper keyframe handling

## Development

**Current Status**: Phase 1 complete ✅
- Knee bending works correctly (no backward bending)
- Thigh rotation limits enforced during dragging
- Foot rotation preserved between IK drags
- Pelvis and collar integration complete (better anchoring)

**Polish/Tuning TODO**:
- Fine-tune collar IK influence (currently 0.8 - may need adjustment to reduce shoulder shrugging)
- Fine-tune head tracking behavior (Y-axis damped track - may need influence adjustment or different track settings)
- **Overall "Rag-Doll Feel"**: Polish the interface so dragging any part feels natural and intuitive, like manipulating a physical figure. Body parts should respond realistically when pulled/moved.

**UX Improvements TODO**:
- **N-Panel Access**: Add tool button to 3D View sidebar (N-Panel) in addition to hotkey
- **Viewport Persistence**: Handle workspace/layout switches gracefully (either persist or exit cleanly with message)
- **Mode Management**: Require Object Mode to start, auto-switch to Pose Mode during use, return to Object Mode on exit

### Roadmap: IK Chain Pulling Behavior

**Goal**: Implement DAZ Studio-like "ragdoll pulling" where dragging a limb beyond reach pulls the whole body with natural falloff.

**Desired Behavior**:
When dragging a hand far from the body:
1. **Short distance**: Arm IK solves normally (elbow bends)
2. **Medium distance**: Arm stretches to limit, shoulder rotates more
3. **Beyond reach**: Starts pulling collar → spine → chest → pelvis with diminishing influence
4. **Way beyond**: Whole body gets dragged like a ragdoll

**Influence Falloff** (natural like pulling a real person):
```
Hand:      100% influence ─┐
Forearm:    95%            │
Upper Arm:  80%            │ Strong influence
Collar:     60%            │
───────────────────────────┘
Chest:      40%            │
Spine:      20%            │ Weak influence
Pelvis:     10%            ┘
```

**Implementation Phases**:

- **Phase 2 (Current)**: IK Stiffness Implementation
  - Add `ik_stiffness_x/y/z` to parent bones with increasing values
  - Higher stiffness = more resistance = less influence
  - Test falloff feel and tune values
  - Low risk, uses native Blender features

- **Phase 3 (Future Goal)**: Hierarchical IK with Dynamic Chain Extension
  - Detect when target exceeds current chain's max reach
  - Dynamically extend chain to include parent bones (collar → spine → pelvis)
  - Apply diminishing influence to newly added bones
  - Creates true DAZ-like progressive pulling behavior
  - More complex but most realistic

**Other Future Features**:
- Body/head grabbing (spine IK, head IK)
- Pole target support (if needed for stability)
