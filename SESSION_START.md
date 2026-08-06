# BlenDAZ - Session Start

> **For AI Assistants**: Read this file first. It's the only file you need for most sessions.
> Update at the end of every session (3-5 min).

**Updated**: 2026-08-01 (workflow audit closed — 28/28 fixed)

---

## Current State

**Pin maintenance is in production** (analytical depsgraph-handler approach; see vault `Pin Maintenance Solver Journey.md`) and a **28-bug audit sweep is closed**: a 41-agent parallel audit (2026-08-01) found 28 confirmed bugs across the whole addon — all new, zero overlap with known bugs — and every one is fixed. Two release blockers (outline data-destruction under Duplicate-Data prefs; dead pre-4.3 compat branches) are gone; **minimum Blender is now honestly 4.3+**, verified on 5.1.2. Pre-release prep for Superhive/Gumroad continues.

---

## What We Did Last Session (2026-08-01)

- **Ran the 41-agent workflow audit** (12 per-file auditors + fresh-context refuting verifiers): 29 findings → 28 confirmed / 1 refuted. Report with per-item fixes + evidence: vault `blendaz-audit-2026-08-01`.
- **Fixed all 28** in five clean commits (`bf31ee3` release blockers · `3bd1d87` posing-state · `7d2cebc` multi-character · `563eaa8` extractors · `9cb1c1c` final nine), with pre-existing WIP checkpointed separately (`c729b63`). Headless 5.1.2 test evidence per cluster — highlights: FABRIK invariant-#9 split-point restored to **0.000000m sphere error**; unpin no longer breaks FACS euler drivers; PoseBlend ON_RELEASE mode works for the first time.
- **⚠️ #4/#5 fixed but UNCOMMITTED** (`panel_ui.py`: stage-light restore + PB-viewport hijack) — caught unfixed during the /save closure review.
- **Files modified**: `daz_bone_select.py`, `fabrik_solver.py`, `setup_all.py`, `posebridge/{core,panel_ui,outline_generator_lineart,extract_hands,extract_face}.py`, `poseblend/interaction.py`

---

## Next Up

1. **Commit #4/#5** (panel_ui.py — the last uncommitted audit fixes)
2. **Interactive posing pass** for the fixes headless tests can't drive: FABRIK drag from over the panel, hip drag w/ pins in a failing context, thigh-twist + ESC, PoseBlend ON_RELEASE + RMB cancel, gizmo dead-zone feel
3. **Multi-character setup run** — verify setup_all Z-stacking on real characters
4. **4.5 LTS manual run** before the store listing claims 4.x support
5. *(carried)* Feel-test R-rotation + leash in live Blender; spine G-drag with multiple pinned hands (`find_pinned_descendant` singular)

---

## Don't Forget

- **⚠️ Diff dev↔extension BEFORE any sync** — live bridge sessions edit the installed extension directly (April 2026 near-loss; DRAG_FIX_LOG #008)
- **`bpy.ops.object.duplicate()` honors user Duplicate-Data prefs** — never use it for internal copies (`obj.copy()` + `data.copy()`)
- **`hide_viewport=True` objects are excluded from background depsgraph eval** — evaluated matrices read identity in headless tests; unhide to measure
- **CollectionProperty item refs invalidate on add()/remove()** — capture values first
- **Solver-owned bones need identity reset** (`_PIN_SOLVER_OWNED_KEYS`); everything else resets to pre-drag originals
- **Leash margin (0.99) < solver reach clamp (0.995)** — keep that ordering
- **Check vault before implementing** — `blendaz-invariants` (14 contracts, read the Quick Lookup), `_blendaz-map` routing table, `blendaz-audit-2026-08-01`
- **Headless tests**: `"D:/SteamLibrary/steamapps/common/Blender/blender.exe" --background --python tests/run_tests.py` (pytest lives in Blender 5.1's Python)
- `daz_shared_utils.py` changes → **full Blender restart**

---

## Files Most Likely Needed Next Session

| File | Why |
|------|-----|
| `posebridge/panel_ui.py` | The two uncommitted fixes (#4 BODY_OBJECTS, #5 viewport second-pass) |
| Vault: `blendaz-audit-2026-08-01` | Audit closure record; manual-verification checklist |
| `daz_bone_select.py` | Interactive pass touches FABRIK/hip-pin/twist/gizmo paths |
| `tests/` + `scripts/bridge_workflow.py` | Headless suite; live-Blender bridge (port 7777) for feel-tests |

---

## Need Deeper Context?

| File | When to read |
|------|-------------|
| [CLAUDE.md](CLAUDE.md) | Design philosophy, vault routing |
| [INDEX.md](INDEX.md) | Finding a specific file |
| [TODO.md](TODO.md) | Full task backlog (audit follow-ups at top) |
| [SCRATCHPAD.md](SCRATCHPAD.md) | 2026-08-01 audit session entry (full fix detail) |
| Vault: `_blendaz-map` | Task routing — read before modifying code |
| Vault: `blendaz-invariants` | The 14 "don't break this" contracts |
