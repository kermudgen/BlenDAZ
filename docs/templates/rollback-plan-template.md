# Rollback Plan Template

**Use this before**: Refactoring, dependency upgrades, risky changes

Copy this template to SCRATCHPAD.md and fill in the specifics before starting risky work.

---

## [Change Description] - [Date]

Brief description of what you're changing and why.

---

## Current Safe State

**Branch/Commit**: [current branch] @ [commit hash]

**What's Working**:
- [ ] Feature X works correctly
- [ ] Feature Y works correctly
- [ ] All tests passing
- [ ] No known bugs in this area

**Last Known Good Commit**: [commit hash]

---

## Rollback Commands

### Option 1: Delete Feature Branch (If working on branch)

```bash
# Return to master
git checkout master

# Delete feature branch
git branch -D [branch-name]

# Verify clean state
git status
```

### Option 2: Undo Last Commit (If on master)

```bash
# Undo last commit but keep changes
git reset --soft HEAD~1

# Or undo last commit and discard changes
git reset --hard HEAD~1

# Verify state
git log --oneline -5
```

### Option 3: Return to Specific Commit

```bash
# Return to known good commit
git reset --hard [commit-hash]

# Force push if already pushed (DANGEROUS - coordinate with team)
# git push --force origin [branch-name]

# Verify state
git log --oneline -5
git status
```

### Option 4: Revert Published Changes

```bash
# If already pushed and others may have pulled
# Use revert instead of reset (creates new commit that undoes changes)
git revert [commit-hash]

# Or revert multiple commits
git revert [old-commit]..[recent-commit]
```

---

## Verification After Rollback

After rolling back, verify everything still works:

- [ ] Blender loads addon without errors
- [ ] [Key Feature 1] works
- [ ] [Key Feature 2] works
- [ ] [Key Feature 3] works
- [ ] `git status` shows clean working tree
- [ ] No uncommitted changes

**Test command**:
```bash
# Run your test script if you have one
python test_script.py

# Or manual verification
# 1. Start Blender
# 2. Enable addon
# 3. Test [specific features]
```

---

## If Rollback Fails

### Can't Find Commit

```bash
# Git keeps everything for ~30 days in reflog
git reflog

# Find your lost commit in the reflog output
# Look for the commit message or hash

# Create recovery branch from lost commit
git checkout [commit-hash-from-reflog]
git checkout -b recovery-branch
```

### Uncommitted Changes Blocking Rollback

```bash
# Stash changes temporarily
git stash save "backup before rollback"

# Perform rollback
git reset --hard [commit-hash]

# If you need those changes back later
git stash list
git stash pop  # or git stash apply
```

### Partial Rollback (Keep Some Changes)

```bash
# Reset to old commit but keep changes in working directory
git reset --soft [commit-hash]

# Review what's changed
git status
git diff

# Selectively add back what you want to keep
git add [specific-files]
git commit -m "Kept working changes from rollback"
```

---

## Notes

**Why this matters**: When things break, you're stressed and rushing. Having commands ready means faster recovery.

**Update this template**: Add project-specific verification steps as you learn what's critical to test.

**Don't skip this**: 5 minutes documenting rollback saves hours of panic recovery.

---

## Example (Filled Out)

```markdown
## Upgrade Diffeomorphic DAZ Importer - 2026-02-20

Upgrading Diffeomorphic from 1.6.2 to 1.7.0 to get Genesis 9 support.

---

## Current Safe State

**Branch/Commit**: master @ abc1234

**What's Working**:
- [x] Genesis 8 imports correctly
- [x] Pose transfer works
- [x] IK chains function properly
- [x] All test characters pose correctly

**Last Known Good Commit**: abc1234

---

## Rollback Commands

```bash
# Restore old Diffeomorphic version
cd /path/to/diffeomorphic
git checkout 1.6.2

# Restart Blender
# Verify Genesis 8 still imports

# If that doesn't work, full rollback
cd /path/to/BlenDAZ
git reset --hard abc1234
```

---

## Verification After Rollback

- [x] Genesis 8 Female imports without errors
- [x] Pose transfer to imported character works
- [x] IK drag on arm produces correct rotation
- [x] No Python errors in console
```

---

**From**: [claude-craft/patterns/rollback-plans.md](../../claude-craft/patterns/rollback-plans.md)
