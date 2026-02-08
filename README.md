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

**Future Polish Items**:
- Pelvis and collar integration
- Body/head grabbing
- Pole target support (Phase 2, if needed)
