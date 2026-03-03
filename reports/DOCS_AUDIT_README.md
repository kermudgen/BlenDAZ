# BlenDAZ Documentation Audit System

Automated daily checks to keep project documentation lean, organized, and AI-context-efficient.

## What It Does

The documentation audit system analyzes your project docs and provides actionable recommendations:

### Key Features

1. **Size Monitoring**
   - Flags documents exceeding recommended line/size limits
   - Prevents context bloat for AI assistants
   - CLAUDE.md kept especially lean (max 500 lines, 50KB)

2. **Content Analysis**
   - Detects duplicate headers
   - Identifies outdated dated content (>6 months old)
   - Finds verbose language patterns
   - Spots large code blocks that should link to source files

3. **Relocation Suggestions**
   - Suggests moving TODO items to TODO.md
   - Identifies architecture content for ARCHITECTURE.md
   - Finds historical content for CHANGELOG.md
   - Detects issue/bug content for ISSUES.md

4. **Health Scoring**
   - 0-100 score for each document
   - Priority-based recommendations
   - Non-destructive (reports only, never auto-deletes)

## Documents Audited

| Document | Max Lines | Max Size | Priority |
|----------|-----------|----------|----------|
| CLAUDE.md | 500 | 50KB | **High** |
| TODO.md | 300 | 30KB | Medium |
| README.md | 200 | 20KB | Medium |
| MONITORING_README.md | 400 | 40KB | Low |

## Setup

### Quick Start (Windows)
```batch
cd d:\dev\BlenDAZ
schedule_docs_audit.bat
```

This will:
1. Create Windows scheduled task
2. Run daily at 9:00 AM
3. Generate DOCS_AUDIT_REPORT.md with recommendations

### Manual Run
```bash
python audit_docs.py
```

## Understanding the Report

### Health Scores

- **80-100**: [OK] Document is healthy
- **60-79**: [WARNING] Needs attention
- **0-59**: [ERROR] Requires immediate streamlining

### Issue Types

| Issue | Meaning | Action |
|-------|---------|--------|
| `[SIZE]` | Exceeds line/size limits | Break into multiple docs or trim |
| `[DUPLICATE]` | Duplicate headers | Consolidate or rename sections |
| `[DATED]` | Old dated content (>6 months) | Archive or remove |
| `[RELOCATE]` | Content belongs elsewhere | Move to suggested document |
| `[WARNING]` | Specific concern | See recommendation |

## Example Output

```markdown
## Priority: CLAUDE.md Analysis

**Health Score**: 80/100 [OK]

- **Size**: 269 lines (13.9KB)
- **Issues Found**: 2

### Issues

- [RELOCATE] Content matches ARCHITECTURE.md patterns: 1 occurrences
- [RELOCATE] Content matches ISSUES.md patterns: 1 occurrences

## Action Items

- [ ] Review and streamline `TODO.md` (score: 66/100)
```

## Customization

### Adjust Size Limits

Edit `audit_docs.py`:

```python
DOCS_TO_AUDIT = {
    'CLAUDE.md': {
        'max_lines': 500,      # Increase/decrease
        'max_size_kb': 50,     # Increase/decrease
        'priority': 'high',
    },
}
```

### Add New Documents

```python
DOCS_TO_AUDIT = {
    'ARCHITECTURE.md': {
        'max_lines': 600,
        'max_size_kb': 60,
        'priority': 'medium',
    },
}
```

### Customize Relocation Patterns

```python
RELOCATION_PATTERNS = {
    'PERFORMANCE.md': [
        r'performance',
        r'optimization',
        r'bottleneck',
    ],
}
```

## Why This Matters

### AI Context Efficiency

Claude Code reads CLAUDE.md to understand your project. Keeping it concise:
- Faster context loading
- More accurate AI responses
- Better focus on current goals

### Document Organization

Regular audits help:
- Prevent documentation drift
- Maintain clear separation of concerns
- Remove outdated content
- Keep team aligned

## Report Location

After each run, review:
- **DOCS_AUDIT_REPORT.md** - Full audit results

## Integration with TODO Workflow

The audit automatically checks TODO.md for:
- Excessive size (>300 lines)
- Duplicate sections
- Completed items that should be archived

Combine with your regular TODO review process.

## Scheduling

**Default Schedule**:
- **9:00 AM daily** - After morning tech updates at 6:30 AM
- Gives you fresh audit results for the workday

**Change Schedule**:
```batch
# Run at different time
schtasks /change /tn "BlenDAZ_Docs_Audit" /st 18:00

# Run weekly instead
schtasks /delete /tn "BlenDAZ_Docs_Audit" /f
schtasks /create /tn "BlenDAZ_Docs_Audit" /tr "python audit_docs.py" /sc weekly /d MON /st 09:00
```

## Maintenance

### Archive Old Audit Reports

```bash
# Save history
mv DOCS_AUDIT_REPORT.md DOCS_AUDIT_$(date +%Y%m%d).md
```

### Review Action Items Weekly

```bash
# Check for recurring issues
grep "Action Items" DOCS_AUDIT_REPORT.md
```

## Best Practices

1. **Act on High-Priority Issues** - Fix CLAUDE.md issues immediately
2. **Review Weekly** - Check audit report every Monday
3. **Don't Ignore [RELOCATE]** - Move content to appropriate docs
4. **Archive Old Content** - Don't delete, move to ARCHIVE/ folder
5. **Keep CLAUDE.md Lean** - Target <300 lines, <20KB for optimal AI context

## Troubleshooting

### "Document not found"
- Script only audits files that exist
- Add new files to DOCS_TO_AUDIT config

### "All documents healthy but report shows issues"
- Health scores 60+ are passing grades
- Review suggestions are still valuable

### "Too many false positives"
- Adjust relocation patterns
- Increase size limits if needed
- Set priority to 'low' for less critical docs

---

**Last Updated**: 2026-02-19
