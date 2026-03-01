# Project Documentation Setup Guide

This guide explains how to set up the documentation system used in this project. Use this as a template for new projects or when starting fresh conversations with AI assistants.

---

## 📚 Documentation System Overview

This project uses a five-file documentation system designed to help both humans and AI assistants work effectively:

1. **SESSION_START.md** - Fast session resumption — read this first every session
2. **CLAUDE.md** - Project context and development guidelines
3. **INDEX.md** - Complete file reference and quick lookup
4. **SCRATCHPAD.md** - Development journal for active work
5. **TODO.md** - Task tracking, roadmap, and project backlog

### Why This System?

- **SESSION_START.md** lets AI assistants resume work in seconds — current state, last session, what's next. Replaced each session, stays small forever.
- **CLAUDE.md** gives AI assistants (and new team members) project context without overwhelming them
- **INDEX.md** makes it easy to find where specific functionality lives
- **SCRATCHPAD.md** captures decisions, experiments, and learnings as they happen
- **TODO.md** tracks what needs to be done, what's in progress, and what's completed
- Together, they prevent repeating mistakes and preserve institutional knowledge

**Key insight**: Docs serve *reference* (complete, organized). SESSION_START.md serves *resumption* (fast, current). Different jobs, different files. See [patterns/session-start.md](patterns/session-start.md) for the full pattern.

---

## 🚀 Initial Setup Process

### Step 1: Create CLAUDE.md

**Purpose**: High-level project context and development philosophy

**When to create**: At project start or when bringing AI assistance into an existing project

**What to include**:

```markdown
# [Project Name] - Project Context

## Core Philosophy
[Your development principles - keep it simple, user-first, etc.]

## What This App/Project Does
[2-3 sentence description of what the project is]

## Quick File Lookup
**See [INDEX.md](INDEX.md) for complete file reference**

Common lookups:
- [Key functionality] → `filename.py`
- [Another key area] → `other_file.py`

## Project Structure
[Directory tree showing main components]

## Tech Stack
- [Primary framework/language]
- [Key dependencies]
- [Build/deployment tools]

## Development Guidelines

### Code Style
- [Your coding principles]
- [Preferred patterns]

### [Domain-Specific Principles]
[E.g., "Artist-First Design" for creative tools, "Data Privacy" for healthcare, etc.]

## Using SCRATCHPAD.md
[Explain how and when to update the scratchpad]

### Scratchpad Archiving Convention
[Document the ~300-500 line / 50-75KB archiving rule]

## Running the App
[Development commands]
[Build commands]
[Test commands]

## Common Tasks
[List of frequent operations with step-by-step instructions]

## Important Files to Know
[Critical files that devs need to be aware of]

## Security Notes
[Security considerations, what to never commit, etc.]

## Current Focus
[What's actively being worked on - update this as priorities shift]

## Questions to Ask Before Committing Code
1. [Checklist item 1]
2. [Checklist item 2]
3. Did I update SCRATCHPAD.md with what I learned?
4. Did I check INDEX.md to find the right file?
```

**Tips**:
- Keep it concise - aim for 150-200 lines max
- Focus on "why" not "what" (INDEX.md handles the "what")
- Update "Current Focus" section as project evolves
- Include domain-specific guidelines (UX principles, security requirements, etc.)

### Step 2: Create INDEX.md

**Purpose**: Comprehensive reference of every file and where to find things

**When to create**: After project structure is established (can be done incrementally)

**What to include**:

```markdown
# [Project Name] - File Index

Quick reference guide for what's in each file and where to find specific functionality.

---

## [Category 1] (e.g., 🚀 Entry Points)

### [filename.py](filename.py)
**Purpose**: [One-line description]
- [Key responsibility 1]
- [Key responsibility 2]
- [Key responsibility 3]
**Key functions/methods**: [List important ones]
**When to modify**: [Scenarios that would require changes]

[Repeat for each file in category]

---

## [Category 2] (e.g., 🎨 Core Logic)

[Repeat structure]

---

## 🔍 Quick Lookup

### "Where is [functionality X]?"
→ `filename.py` ([brief context])

### "How do I [common task]?"
→ [Brief answer with file references]

---

## 🎯 Common Modification Points

### [Task category]
**Files**: [list of files]
**What to change**: [guidance]

---

## 📚 Related Documentation
- [CLAUDE.md](CLAUDE.md) - Project context and guidelines
- [SCRATCHPAD.md](SCRATCHPAD.md) - Development journal
- [TODO.md](TODO.md) - Task tracking and roadmap
```

**Tips**:
- Use emojis for categories - makes scanning easier
- Group files by function, not by type (group "authentication" files together, not "all Python files")
- Include "Quick Lookup" section with common questions
- Update incrementally as files are added
- Cross-reference between sections

**How to populate**:
1. List all files: `ls -la` or similar
2. For each file, read the first 50 lines to understand purpose
3. Note key functions/classes
4. Document when you'd need to modify it
5. Add cross-references to related files

### Step 3: Create SCRATCHPAD.md

**Purpose**: Living development journal for active work

**When to create**: Day 1 of active development

**What to include**:

```markdown
# [Project Name] - Development Scratchpad

## Purpose
This file tracks ongoing development work, experiments, bugs, and feature progress. It's a living document that captures what we're working on, what we've tried, and what we've learned.

**Note**: When this file reaches ~300-500 lines or ~50-75KB, archive it to `scratchpad_archive/SCRATCHPAD_YYYY-MM.md` and start fresh.

## Archive History
*Archived scratchpads will be listed here when created*

---

## Current Session: [Date]

### Active Work
- [What are we currently working on?]

### Today's Goals
- [ ] Goal 1
- [ ] Goal 2

### Notes & Observations
- [Quick notes from today's work]

---

## Feature Development Log

### [Feature Name] - [Date Started]
**Status**: 🟡 In Progress | 🟢 Complete | 🔴 Blocked | ⏸️ Paused

**Goal**: [What are we trying to achieve?]

**Approach**:
1. Step 1
2. Step 2

**What Works**:
- ✅ Thing that works

**What Doesn't Work**:
- ❌ Problem encountered

**Decisions Made**:
- Decision 1: Reasoning

**Next Steps**:
- [ ] Action item 1

**Related Files**:
- `file1.py` - description

---

## Bug Tracker

### Bug: [Description] - [Date]
**Priority**: High | Medium | Low
**Status**: Open | In Progress | Fixed

[Bug details, reproduction steps, solution]

---

## Technical Observations

### [Component/System Name]
[Notes about how it works, quirks, performance observations]

---

## Ideas & Future Considerations

### [Idea Name]
**Description**: [What's the idea?]
**Why**: [Potential benefits]
**Challenges**: [What makes this difficult?]

---

## Quick Reference

### Useful Commands
```bash
# [Common command with description]
```

### Important Patterns
[Code patterns or regex patterns frequently used]

---

## Archive (Completed Work)

### ✅ [Completed Feature] - [Date Range]
**Summary**: [What was done]
**Lessons Learned**: [Key takeaways]
```

**Tips**:
- Update throughout the day, not just at the end
- Be informal - it's a scratchpad, not formal docs
- Include failed approaches - they're valuable learning
- Use checkboxes for tasks so you can track completion
- Archive when it hits ~300-500 lines or feels overwhelming

### Step 5: Create SESSION_START.md

**Purpose**: Single always-current entry point for fast session resumption

**When to create**: Once you have 3+ docs and sessions frequently start by "catching up"

**What to include**:

```markdown
# [Project Name] - Session Start

> **For AI Assistants**: Read this file first. It's the only file you need for most sessions.
> Update at the end of every session (3-5 min).

**Updated**: YYYY-MM-DD

---

## ⚡ Current State

[2-3 sentences: phase, status, what's happening right now]

---

## What We Did Last Session

- **[Change description]** — what was done and why
- **Files modified**: `file1.py`, `file2.py`

---

## Next Up

1. [Next task from TODO.md]
2. [Another task]

---

## Don't Forget

- [Critical gotcha — e.g., requires full restart]
- [Non-obvious behavior or active workaround]

---

## Files Most Likely Needed Today

| File | Why |
|------|-----|
| `file1.py` | [What's happening here] |

---

## Need Deeper Context?

| File | When to read |
|------|-------------|
| [CLAUDE.md](CLAUDE.md) | Architecture, principles |
| [INDEX.md](INDEX.md) | Finding a file |
| [SCRATCHPAD.md](SCRATCHPAD.md) | Understanding recent decisions |
| [TODO.md](TODO.md) | Full task backlog |
```

**Critical rules**:
- **Replace, don't append** — "What We Did Last Session" is always just the last session. History goes in SCRATCHPAD.md.
- **Keep it small** — if it grows past ~100 lines, it's drifting into reference territory. Prune it.
- **Update every session** — a stale SESSION_START.md is worse than none. Commit to the 3-5 min ritual.

See [patterns/session-start.md](patterns/session-start.md) for the full pattern with real examples and anti-patterns.

---

### Step 4: Create TODO.md

**Purpose**: Structured task tracking, roadmap planning, and project backlog management

**When to create**: Early in the project, once you have a sense of priorities and upcoming work

**What to include**:

```markdown
# [Project Name] - TODO

**Last Updated**: [Date]

Track current development tasks, future features, and improvements needed.

---

## 🚧 Current Work

### [Active Feature/Task Name]

**Description**: [What you're actively working on right now]

#### Immediate Tasks
- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

#### Current Challenge
**Problem**: [Brief description]
**Goal**: [What you're trying to achieve]
**Next Steps**: [What needs to happen]

---

## ✅ Recently Completed ([Date Range])

- [x] **Task name** - Brief description of what was done
- [x] **Another task** - What was accomplished

---

## 📋 Backlog - High Priority

### [Feature Category]
- [ ] Feature or task description
- [ ] Another planned improvement
- [ ] Something that needs attention soon

[Repeat for different categories]

---

## 🔮 Future Features

### [Category Name]
- [ ] Long-term feature idea
- [ ] Nice-to-have enhancement
- [ ] Experimental concept to explore

---

## 🐛 Known Issues

### High Priority
- [ ] Critical bug description
- [ ] Important issue to fix

### Medium Priority
- [ ] Less urgent bug
- [ ] Minor issue

### Low Priority
- [ ] Small annoyance
- [ ] Edge case

---

## 🔧 Technical Debt

### Code Quality
- [ ] Refactoring needed
- [ ] Code cleanup task

### Testing
- [ ] Test coverage gaps
- [ ] Test scenarios to add

### Performance
- [ ] Optimization opportunity
- [ ] Performance improvement

### Documentation
- [ ] Documentation gap
- [ ] Guide to write

---

## 📊 Project Maintenance

### Regular Tasks
- [ ] Recurring maintenance task
- [ ] Periodic review item

### Monitoring
- [ ] Metrics to track
- [ ] Things to watch

---

## 💡 Ideas to Consider

### Experimental
- [ ] Unvalidated idea
- [ ] Concept to research

### Research Needed
- [ ] Question to investigate
- [ ] Area needing exploration

---

## 📝 Notes

**How to use this file:**
1. Check "Current Work" for active development priorities
2. Move items from Backlog to Current Work as you begin them
3. Mark items complete and move to "Recently Completed"
4. Archive old completed items to SCRATCHPAD.md periodically
5. Add new ideas to appropriate sections
6. Review and groom this file weekly

**Priority Levels:**
- **Current Work**: Active development, highest priority
- **Recently Completed**: Just finished (archive after a few days)
- **Backlog**: High priority, planned for next
- **Future Features**: Long-term vision, requires significant work
- **Ideas**: Brainstorming, needs validation/research
```

**Tips**:
- Keep "Current Work" focused (3-5 items max)
- Move completed items promptly to keep it fresh
- Archive old "Recently Completed" items to SCRATCHPAD.md weekly
- Use checkboxes for tracking progress
- Update the "Last Updated" date when making changes
- Group related tasks under clear category headers
- Distinguish between bugs, features, and technical debt

**How TODO.md differs from SCRATCHPAD.md**:
- **TODO.md**: Structured, forward-looking, what needs doing
- **SCRATCHPAD.md**: Chronological, narrative, what was done and learned
- Use TODO.md for planning and tracking
- Use SCRATCHPAD.md for documenting decisions and discoveries

---

## 🔄 Maintenance & Updates

### When to Update Each File

**SESSION_START.md**:
- **Every session end** — replace (don't append) current state, last session, next up
- Keep under ~100 lines — if it's growing, you're adding reference content that belongs elsewhere
- A stale SESSION_START.md is worse than none — commit to the update ritual or don't create it

**CLAUDE.md**:
- When project philosophy changes
- When adding major new components
- When "Current Focus" shifts
- Monthly review recommended

**INDEX.md**:
- When adding new files
- When file purposes change significantly
- When you notice people asking "where is X?"
- After major refactors

**SCRATCHPAD.md**:
- Daily during active development
- After trying something new
- When making important decisions
- When discovering quirks or gotchas
- Archive when it gets too long (~monthly for active projects)

**TODO.md**:
- When starting new tasks (move from Backlog to Current Work)
- When completing tasks (mark done, move to Recently Completed)
- When discovering new bugs or technical debt
- When brainstorming new features or improvements
- Weekly grooming to keep it organized and current

### Archiving SCRATCHPAD.md

When SCRATCHPAD.md reaches ~300-500 lines or ~50-75KB:

```bash
# Create archive directory
mkdir -p scratchpad_archive

# Move current scratchpad to archive with date
mv SCRATCHPAD.md scratchpad_archive/SCRATCHPAD_2026-02.md

# Create fresh scratchpad (use template above)
# Be sure to:
# 1. Add archive reference in "Archive History" section
# 2. Carry forward any unfinished items
# 3. Keep the structure but clear completed sections
```

---

## 🎯 For AI Assistant Conversations

### Starting a Fresh Conversation

When starting a new conversation with an AI assistant about this project:

1. **First message** — point straight to SESSION_START.md:
   ```
   Read SESSION_START.md to orient yourself, then let me know you're ready.
   ```
   That's it. SESSION_START.md links to everything else.

2. **During conversation**:
   - AI reads INDEX.md only when it needs to find a specific file
   - AI reads TODO.md only when reviewing priorities
   - AI updates SCRATCHPAD.md with decisions and learnings as it works
   - AI references CLAUDE.md for architectural guidance

3. **Before ending**:
   - Update SESSION_START.md (3-5 min): current state, what changed, what's next
   - Update SCRATCHPAD.md with session decisions and discoveries
   - Update TODO.md with completed/new tasks

**In Claude Code (CLI)**: CLAUDE.md is auto-read at session start. If your CLAUDE.md has a "For AI Assistants" section pointing to SESSION_START.md as Step 1, the session wires up automatically — no prompt needed.

### AI Assistant Guidelines

Include this in your CLAUDE.md to wire up the reading order:

```markdown
## For AI Assistants

### Step 1 — Always read first
**[SESSION_START.md](SESSION_START.md)** — current state, last session, next up, gotchas.
This is the only file you need for most sessions.

### Step 2 — Read this file (CLAUDE.md)
Architecture, principles, guidelines.

### Step 3 — Only if the task requires it
- Finding a file → [INDEX.md](INDEX.md)
- Full task backlog → [TODO.md](TODO.md)
- Decision history → [SCRATCHPAD.md](SCRATCHPAD.md)

**Don't front-load.** Read SCRATCHPAD.md and INDEX.md only when the task requires them.

### End of session
Update SESSION_START.md. Takes 3-5 minutes. Keeps the next session fast.
```

---

## 📋 Quick Setup Checklist

For a new project:

- [ ] Create `CLAUDE.md` with project context and philosophy
- [ ] Create `INDEX.md` (can start minimal and expand)
- [ ] Create `SCRATCHPAD.md` with today's date
- [ ] Create `TODO.md` with initial tasks and priorities
- [ ] Create `SESSION_START.md` once you have 3+ docs (see Step 5 above)
- [ ] Add "For AI Assistants" 3-step reading order to CLAUDE.md pointing to SESSION_START.md
- [ ] Add cross-references between all files
- [ ] Add `.gitignore` entries for sensitive files (if applicable)
- [ ] Update CLAUDE.md with "Current Focus"
- [ ] Test by asking: "If a new Claude session started right now, what would it read first?"

---

## 🎨 Customization Tips

### Adapt to Your Domain

**For creative/artist tools**:
- Add "Artist-First Principles" section to CLAUDE.md
- Include user workflow examples
- Document common iteration patterns

**For data/analytics**:
- Add data pipeline documentation to INDEX.md
- Include data schema references
- Document privacy/compliance requirements

**For APIs/backends**:
- Add API endpoint reference to INDEX.md
- Document authentication flows
- Include rate limiting and scaling notes

**For libraries/SDKs**:
- Add public API surface to INDEX.md
- Document versioning strategy
- Include breaking change policy

### Team-Specific Conventions

Add to CLAUDE.md:
- Team coding standards
- Review process
- Deployment procedures
- Communication channels
- Meeting notes references

---

## 📦 Template Files

### Minimal Starter Template

If you're just starting and want to get going quickly:

**CLAUDE.md** (50 lines):
- What the project does
- Tech stack
- How to run it
- Link to INDEX.md and TODO.md

**INDEX.md** (initially 20 lines):
- List of main files with one-line descriptions
- Expand as you go

**TODO.md** (initially 30 lines):
- Current Work section with 2-3 initial tasks
- Empty sections for Backlog and Future Features
- Expand as priorities become clear

**SCRATCHPAD.md** (use full template):
- Start tracking from day 1

### Full Template

For established projects, use the full structures shown above.

---

## ✅ Success Indicators

You'll know this system is working when:

- New team members can get oriented in < 30 minutes
- AI assistants can find files without multiple guesses
- Decisions made months ago are documented and retrievable
- You're not repeating the same mistakes
- The documentation stays up to date because it's actually useful

---

## 🔗 Related Resources

- [CLAUDE.md](CLAUDE.md) - This project's implementation
- [INDEX.md](INDEX.md) - This project's file index
- [SCRATCHPAD.md](SCRATCHPAD.md) - This project's development journal
- [TODO.md](TODO.md) - This project's task tracking system

Use this project as a reference implementation!
