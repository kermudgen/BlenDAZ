# Bug Status Entry Template

**Use this for**: Complex bugs taking multiple sessions to fix

Add entries to CLAUDE.md "Issue Status" section using this template.

---

## Template

```markdown
### [🔴 OPEN | 🟡 PARTIALLY FIXED | ✅ FIXED] bug_name — STATUS_TEXT

**Symptom**: [What the user experiences - observable behavior]

**Root cause**: [Technical cause if known, or "Unknown - investigating"]

**What works**:
- ✅ [Thing that helps or partial fix]
- ✅ [Another working approach]

**What doesn't work**:
- ❌ [Approach tried that failed]
- ❌ [Why it failed / what we learned]

**Don't re-investigate**:
- [Specific dead ends to avoid]
- [Why they don't work]
- [What evidence ruled them out]

**Next steps**:
1. [What to try next]
2. [What to verify]
3. [What information is still needed]

**Related files**:
- `filename.py:123` - [What's relevant here]
- `other_file.py:456` - [Related logic]

**Last investigated**: YYYY-MM-DD
```

---

## Status Indicators

- 🔴 **OPEN** - Actively broken, no fix yet, high priority
- 🟡 **PARTIALLY FIXED** - Some progress, but not fully resolved
- ✅ **FIXED** - Resolved (keep for reference)
- ⏸️ **DEFERRED** - Known issue, not currently prioritized
- ⚠️ **WORKAROUND** - Not fixed properly, but has acceptable workaround

---

## Tips for Writing Good Status Entries

### Symptom (What user sees)
✅ **Good**: "Second IK drag snaps bone to T-pose instead of posed position"
❌ **Bad**: "IK doesn't work right"

### Root Cause (Technical)
✅ **Good**: "LOCAL constraint space reads matrix_basis (delta from rest pose)"
❌ **Bad**: "Something wrong with constraints"

### What Doesn't Work (Save future effort)
✅ **Good**: "Pole targets - tried adjusting angle from 0 to 1.5 radians, made it worse. Root cause is twist bone incompatibility, not pole angle"
❌ **Bad**: "Pole targets don't help"

### Don't Re-investigate (Most valuable section!)
✅ **Good**: "❌ Constraint influence - already tested 0.5, 0.75, 1.0, no effect. Issue is space mismatch, not influence."
❌ **Bad**: "❌ Tried various things"

**Why this matters**: Prevents wasting hours on dead ends you already explored

---

## Example (Filled Out)

```markdown
### 🟡 second_drag_bug — MOSTLY FIXED (2026-02-18)

**Symptom**: Second IK drag produces wrong result — snap-back, wrong initial position, or accumulated twist.

**Root causes found** (2026-02-18):
1. **Constraint space mismatch**: Copy Rotation in LOCAL space reads `matrix_basis` (delta from rest pose).
   Since `.ik` bones' rest pose IS the current posed position, LOCAL copies Identity → DAZ bone snaps to T-pose.
   **Fixed: Changed to POSE space.**

2. **Bend/twist not separated**: Copy Rotation (in ANY space) copies combined swing+twist to DAZ bend bones.
   Axis filtering (`use_y=False`) doesn't work because POSE space axes ≠ bone-local axes.
   **Fixed: Removed Copy Rotation from bend bones, added manual swing/twist decomposition.**

3. **rotation_mode not checked**: Setting `rotation_quaternion` on Euler-mode bones does nothing.
   **Fixed: Added rotation_mode check.**

**Fixes applied** (in code, confirmed working):
- ✅ POSE space for Copy Rotation (non-bend bones) — fixes snap-to-straight
- ✅ Swing/twist decomposition in `update_ik_drag()` — correct values
- ✅ rotation_mode check for all rotation setting — arm now moves correctly

**What doesn't work**:
- ❌ LOCAL space - confirmed broken for our use case (rest pose mismatch)
- ❌ POSE space axis filtering for twist - axes are armature-space, not bone-local
- ❌ Simple Copy Rotation to bend bones - copies twist, causes accumulation

**Don't re-investigate**:
- ❌ Pole targets — already confirmed disabled (DAZ twist bone incompatibility). See TECHNICAL_REFERENCE.md:220-225
- ❌ Constraint influence values — not relevant, issue is space mismatch
- ❌ IK chain length — correct, issue is constraint configuration

**Related files**:
- `daz_bone_select.py:1234` - create_ik_chain() sets up constraints
- `daz_bone_select.py:2456` - update_ik_drag() swing/twist decomposition
- `daz_shared_utils.py:789` - decompose_swing_twist() utility

**Last investigated**: 2026-02-18
```

---

## When to Update

**After each debugging session**:
- Add what you learned (works/doesn't work)
- Update "Next steps"
- Add to "Don't re-investigate" if you ruled something out
- Change status if progress made (🔴 → 🟡 → ✅)

**When bug is fixed**:
- Change status to ✅ FIXED
- Add "What fixed it" summary
- Keep entry for reference (don't delete)

---

## Why This Works

**Without status tracking**:
- Session 1: Try approach A, doesn't work
- Session 2: Forget about A, try it again, waste time
- Session 3: Try B, partially works
- Session 4: Forget B was partial, start over

**With status tracking**:
- Session 1: Try A, document "doesn't work, here's why"
- Session 2: Read status, skip A, try B
- Session 3: B partial, document what works/doesn't
- Session 4: Read status, build on B's progress → SOLVED

**Real example**: BlenDAZ second_drag_bug took 4 sessions because context was lost between sessions. Status tracking would have solved it in 2-3.

---

**From**: [claude-craft/patterns/documentation-first-debugging.md](../../claude-craft/patterns/documentation-first-debugging.md)
