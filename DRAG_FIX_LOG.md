# Drag Fix Log

References use `ik_diag_NNN.json#index` format (e.g. `ik_diag_001.json#3` = entry 3 in file 001).
Legacy per-drag files (`ik_diag_YYYYMMDD_HHMMSS.json`) predate the session-based format.

## Entries

### 001 — Analytical arm release pop
- **Diag**: `ik_diag_20260316_061201.json` (legacy) — lForearmBend analytical arm drag
- **Issue**: lShldrBend Z snaps ~6.5° on frame 49 (release). Constraints clamp unclamped solver output.
- **Fix**: Added constraint bake-back to analytical arm + leg end paths. Extract effective rotation from evaluated depsgraph matrix, write back before keyframing.

### 002 — Analytical arm grab pop on pre-posed limb
- **Diag**: `ik_diag_20260316_061847.json` (legacy) — lForearmBend drag on already-bent arm
- **Issue**: lShldrBend Z jumps 0.100→0.157 on first solver frame. Solver resets to identity but targets posed wrist position — mismatch causes pop.
- **Fix**: Added `_analytical_arm_grab_offset` — captures rest-wrist vs posed-wrist offset on first frame, subtracts from target so zero mouse-delta produces identity solve.

### 008 — Soft-pin drag: IK anchored mid-forearm instead of the wrist (2026-07-07)
- **Diag**: follow-up audit spawned from 005's anatomy finding; live bridge measurement on "Big Beast Ogre" — forearmBend.tail → lHand.head = 225.9mm, hand length (head→tail) = 184mm.
- **Issue 1**: `start_ik_drag`'s soft-pin path set `_soft_pin_initial_pos` to forearmBend.tail believing it was the wrist (same wrist-vs-bend-tail confusion as 005). The pole-target path locks the IK goal there every frame, so a pinned hand's IK goal sat mid-forearm.
- **Issue 2 (found during audit)**: the lock point never matched the effector anyway. `create_ik_chain` extends the chain to the pinned child (IK_Temp on hand.ik, `use_tail=True` → effector = hand **tail**) and creates the .ik.target at hand.tail, while the drag locked the target elsewhere → bone-length pop at drag start (184mm on the ogre; foot-length for pinned-foot leg drags).
- **Fix**: unified everything on the pin point = pinned child's **head** (the wrist/ankle — what the Copy Location pin actually holds): `_soft_pin_initial_pos` = pinned child head (forearm-lookup special case deleted); `create_ik_chain` soft-pin target created at pinned child head; `IK_Temp.use_tail = False` in soft-pin mode. The tip .ik bone has all IK DOF locked, so articulation is unchanged — only the effector point moves.
- **Audit**: `fabrik_solver.py` is clean — `build_arm_fabrik_chain` targets hand.head and derives the last segment via `_compute_local_child_offset` through lForearmTwist. `_find_pinned_limbs` already fixed in 005.
- **Regression test**: `tests/test_soft_pin_ik_chain.py` (production `create_ik_chain`, T0): target-at-wrist, target-at-ankle, normal-mode-unchanged. Full suite 21 passed / 4 skipped.
- **Remaining**: live feel-test of a forearm drag with pinned hand. Addon hot-reloaded in the live session (restart Touch first — reload doesn't swap a running modal).

### 009 — Master pins toggle silently disabling all pin logic (2026-07-07)
- **Diag**: live probe — `daz_pin_translation` prop True but `is_bone_pinned_translation()` False. The April merge brought a master pins toggle (`scene.posebridge_settings.pins_enabled`, posebridge/core.py:442, default True) that gates every pin check. The user's scene had it saved as **False** — so ALL solver-side pin logic (soft-pin, spine maintenance routing, hip-pin) reported "unpinned" while the pin's COPY_LOCATION constraint stayed active. Result: chest drag ran the unpinned path, hand held by constraint, arm walked away — "hand separating from forearm."
- **Fix 1**: `pin_bone_translation` / `pin_bone_rotation` auto-enable the master toggle — pressing P while pins are globally disabled was a trap (constraint active, solvers blind).
- **Fix 2**: scene repaired — `pins_enabled=True`, and lHand's stale 98mm location-channel offset cleared (residue: unpinning during the broken state bake-back preserved the constraint displacement into the channel).
- **Fix 3**: backported three more April-only files missed by the root-level diff: `posebridge/core.py` (pins_enabled + more), `posebridge/extract_face.py`, `posebridge/panel_ui.py`. **Diff subdirectories too.**
- **Verified live**: pinned chest solve — hand lands 1.3mm from pin.

### 008 — Dev↔extension divergence: April work recovered and merged (2026-07-07)
- **Diag**: post-fix chest drags produced NO detail entries in `ik_drag_diag.log` — the detail logger calls didn't exist in the deployed file. Investigation showed the installed 5.1 extension had been built from an **April 16** code state that was ~650 lines ahead of the dev repo: pin ICON viewport UI (clickable, replaced pin spheres), `ik_diag_*` drag detail logging, freeze-visual-pose anti-pop for native IK drag release, `_init_drag_curve_recording`, spine engagement ratios. April sessions edited the extension live via the bridge and never synced back to D:\Dev. This session's file syncs overwrote the extension's `daz_bone_select.py` with the (older-base) dev version — likely a contributor to the "wonky" chest drag (no freeze anti-pop → spine pops on release).
- **Recovery**: untouched copy found in the Blender **5.0** profile (`daz_bone_select.py`, Apr 16, 685KB) — preserved as `daz_bone_select_apr16_extension.py.recovered` + full extension backup in `backup_extension_20260707/`.
- **Merge**: 3-way merge (base=HEAD d63e586, ours=dev+this-session pin work, theirs=Apr16). 3 conflicts (header text), resolved keeping April headers + new defensive teardowns. Result: pin icons + diag logging + freeze anti-pop + all of this session's pin maintenance. 18/18 tests pass. Backported `diag_logger.py`, `daz_bone_select_test.py`, `__init__.py` from the extension into dev.
- **Process rule**: BEFORE syncing dev↔extension in either direction, diff the trees — live sessions may have edited the extension directly.

### 007 — Chest/spine drag with pinned hands: multi-pin maintenance (2026-07-06)
- **Diag**: user report + `ik_drag_diag.log` DRAG #13 — chestUpper drag built IK chain ['abdomenLower','abdomenUpper','chestLower','chestUpper','lHand'] (soft-pin spliced ONE pinned hand in, rHand ignored → right arm detached), and dissolve bake showed chestLower Δ=22° drift on release.
- **Fix**: spine/torso drags (`SPINE_TORSO_DRAG_BONES`) with pinned limbs now bypass the single-descendant soft-pin path entirely: normal unpinned spine IK chain (no hand splice) + per-frame `_solve_pin_maintenance_frame` for ALL pinned limbs via shared helpers `_setup_pin_limb_maintenance` / `_solve_pin_limb_maintenance_frame` / `_end_pin_limb_maintenance` (extracted from and shared with the Touch rotation path). On confirm, one final maintenance pass runs AFTER `dissolve_ik_chain` so pins re-plant before their constraints unmute — the 22° dissolve pop can't strand the hands.
- **Review fixes** (reviewer agent): teardown added to start_ik_drag's two abort returns (chain-creation failure, no viewport) — previously leaked muted pin constraints; defensive teardown on the analytical/FABRIK early returns in end_ik_drag.
- **Scope**: FABRIK split-chain still owns forearm/shoulder drags with that arm's pinned hand; unpinned spine drags unchanged.

### 006 — Touch rotation path: hands detach from forearms on spine rotation (2026-07-03)
- **Diag**: live report + bridge probe — hands ON pins (0.0mm, COPY_LOCATION active) but wrists 175–298mm away after rotating spine bones via Touch click-drag.
- **Issue**: `_apply_rotation_pin_ik` (the Touch click-drag rotation path, separate from the R-key path) reset ALL limb bones to their drag-start rotations before each solve — including solver-owned bones, which must be identity (`_solve_pinned_limb` reads their pose matrix as its rest frame). With arms posed away from rest, every solve was corrupted; on release the pin constraint unmuted and snapped the hand back while the arm stayed wrong. The confirm path then moved the pin empty to the bad position, compounding it. Path also predated the 005 arm-reach fix.
- **Fix**: `_apply_rotation_pin_ik` now delegates to `_solve_pin_maintenance_frame` (parameterized with limbs/originals/root), inheriting the identity-reset rule, originals preservation, reach leash, and aim feedback. Originals now store location+rotation; root leash movement restores on cancel and keyframes on confirm.
- **Regression test**: `test_chest_rotate_posed_arm_stays_pinned` — posed arm + pinned hand + chest rotation.
- **Reminder**: a hot-reload does NOT swap code inside a running modal — restart Touch after reloading.

### 005 — Pin maintenance live-rig fixes: arm reach, leash overshoot, aim feedback (2026-07-03)
- **Diag**: live bridge validation on "Big Beast Ogre" (G8M), both hands pinned. Initial errors 100–285mm; leash ran away (-0.43m when asked +0.40m).
- **Issue 1**: `_find_pinned_limbs` measured the lower arm as forearmBend head→tail. On Diffeomorphic rigs forearmBend ends MID-forearm; forearmTwist continues to the wrist. Arm reach underestimated by the twist length (~230mm on the ogre) → pins unreachable by construction → constant miss + leash chasing an unsatisfiable deficit.
- **Fix 1**: lower segment = forearmBend.head → forearmTwist.tail when the twist exists. Synthetic test rig updated to the realistic layout so tests cover this.
- **Issue 2**: leash summed corrections across violated pins → overshoot when several pins pull the same way.
- **Fix 2**: average across violated pins; per-frame convergence handles the remainder.
- **Issue 3**: residual endpoint miss the 2-bone math can't see — 18mm wrist→hand rest offset, LIMIT_ROTATION clamping (live limits stay active during pin drags, unlike bake+mute drag paths).
- **Fix 3**: `_update_pin_aim_offsets()` — closed-loop aim feedback per limb: measure endpoint miss from the evaluated depsgraph, fold into that limb's `solve_target`, reset solver-owned bones to identity (invariant!), re-solve. Offsets persist in the limb dict; converges across frames.
- **Result**: hip ±drags and 25° hip rotation all ≤2mm endpoint error after convergence (was 82–285mm); leash holds hip to ~0mm rise with hands pinned at full extension. Remaining: 16mm on a pin placed 4cm beyond full anatomical reach (needs Rule 10 spine engagement).
- **Note**: a re-solve within one frame MUST re-reset solver-owned bones to identity first — the solver reads their pose matrix as its rest frame. Violating this caused a 3× error regression during development.

### 004 — Pin maintenance: rotation support, reach leash, pose clobbering (2026-07-03)
- **Diag**: `tests/test_pin_maintenance.py` (production-code tests, synthetic G8 rig — no drag diag needed)
- **Issue 1**: R on hip/pelvis/spine with pinned feet/hands did nothing for pins — feet stayed at COPY_LOCATION targets while legs rotated away (visual detach). Only a pinned head was handled.
- **Fix 1**: Generalized `_start_hip_pin_drag(transform_op='ROTATE')`; R-key block routes through the pin-maintenance depsgraph handler.
- **Issue 2**: Dragging the hip beyond a pinned chain's reach silently broke the pin (solver clamps at 0.995 reach, endpoint follows).
- **Fix 2**: `_apply_pin_reach_leash()` — radial deficit correction translates the hip back (DAZ Rule 8); margin 0.99 so the solver clamp never engages.
- **Issue 3**: The per-frame handler reset ALL limb bones to identity, wiping user-posed foot roll, twists, and (with pinned head) the whole spine pose.
- **Fix 3**: `_solve_pin_maintenance_frame()` resets only solver-owned bones (`_PIN_SOLVER_OWNED_KEYS`) to identity; twists/endpoints/neck-compensation bones reset to pre-drag originals.

### 003 — Normal IK collar pop on hand drag
- **Diag**: `ik_diag_20260316_062638.json`, `ik_diag_20260316_062649.json` (legacy) — lHand + rHand
- **Issue**: All bones jump frame 0→1 (collar ~9°, shoulder ~5-7°, forearm ~10-13°). IK influence snaps 0→1.0 in single frame.
- **Fix**: Added IK influence ramp (0.15→1.0 over ~5 frames, +0.20/frame). Both IK constraint and Copy Rotation constraints ramp together. Snaps to 1.0 on release if ramp incomplete.
