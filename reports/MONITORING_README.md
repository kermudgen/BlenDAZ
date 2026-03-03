# BlenDAZ Technology Monitoring System

Stay cutting-edge by automatically tracking updates from Diffeomorphic, Blender, and rigging technologies.

## What It Monitors

### Primary Sources
1. **Diffeomorphic DAZ Importer**
   - GitHub commits (rotation, limits, IK, rigging)
   - New releases
   - Relevant issues (open & closed)

2. **Blender Development**
   - Developer blog (rigging/animation posts)
   - API changes affecting constraints/armatures

### Keywords Tracked
- `rotation limits`, `IK`, `rig`, `pose`, `constraint`
- `Genesis 8`, `Genesis 9`, `DAZ`
- `interactive`, `modal`, `real-time`
- `bone select`, `armature`

---

## Setup

### Quick Start (Windows)
```batch
cd d:\dev\BlenDAZ
schedule_monitor.bat
```

This will:
1. Install required packages (`requests`, `feedparser`)
2. Create Windows scheduled task
3. Run daily at 9:00 AM

### Manual Setup

**Install dependencies:**
```bash
pip install requests feedparser
```

**Run manually:**
```bash
python monitor_updates.py
```

**Schedule with cron (Linux/Mac):**
```bash
# Edit crontab
crontab -e

# Add line (runs daily at 9 AM):
0 9 * * * cd /path/to/BlenDAZ && python monitor_updates.py
```

---

## Output

### TECH_UPDATES.md
All updates are appended to `TECH_UPDATES.md` with:
- Title and description
- Author and date
- Direct links
- State (for issues)

### Example Entry:
```markdown
## Diffeomorphic GitHub

### Fix: Rotation limit constraints not applied to twist bones

**Date**: 2026-02-18T14:32:00Z
**Author**: johnsmith
**Link**: https://github.com/diffeomorphic/daz_importer/commit/abc123

Fixed bug where twist bones (lShldrTwist, rForearmTwist) were not
getting LIMIT_ROTATION constraints during import...
```

### monitor_state.json
Tracks last check timestamps to avoid duplicate notifications.

---

## Customization

### Add New Sources

Edit `monitor_updates.py`:

```python
SOURCES = {
    # Add new source
    'custom_source': {
        'url': 'https://example.com/api',
        'type': 'github_commits',  # or rss, github_issues, etc.
        'keywords': ['keyword1', 'keyword2'],
    },
}
```

### Change Keywords

```python
'keywords': [
    'your', 'custom', 'keywords',
    'spline ik', 'pose library', 'mocap'
],
```

### Change Schedule

**Windows Task Scheduler:**
```batch
# Change to run at 6 PM
schtasks /change /tn "BlenDAZ_Tech_Monitor" /st 18:00
```

**Cron:**
```bash
# Change to run every 6 hours
0 */6 * * * cd /path/to/BlenDAZ && python monitor_updates.py
```

---

## Supported Source Types

### GitHub API
- `github_commits` - Recent commits
- `github_releases` - Release announcements
- `github_issues` - Open/closed issues

### RSS Feeds
- `rss` - Any RSS/Atom feed

### Coming Soon
- Forums (scraping)
- Discord webhooks
- Slack notifications
- Email digests

---

## Advanced Usage

### Filter by Date Range

```bash
# Check updates from last 7 days
python monitor_updates.py --days 7
```

### Force Refresh (Ignore State)

```bash
# Re-check all updates
python monitor_updates.py --force
```

### Export to Different Format

```python
# In monitor_updates.py, add export functions:
def export_to_json(updates):
    # Export as JSON for external tools
    pass

def export_to_html(updates):
    # Generate HTML report
    pass
```

---

## Integration Ideas

### VS Code Notification
Create `.vscode/tasks.json`:
```json
{
  "tasks": [
    {
      "label": "Check Tech Updates",
      "type": "shell",
      "command": "python monitor_updates.py",
      "problemMatcher": []
    }
  ]
}
```

### GitHub Action (Auto-commit Updates)
Create `.github/workflows/monitor.yml`:
```yaml
name: Technology Monitor
on:
  schedule:
    - cron: '0 9 * * *'  # Daily at 9 AM

jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run monitor
        run: python monitor_updates.py
      - name: Commit updates
        run: |
          git config user.name "Tech Monitor Bot"
          git add TECH_UPDATES.md monitor_state.json
          git commit -m "Update tech monitoring"
          git push
```

---

## Maintenance

### Clean Up Old Updates

Periodically archive `TECH_UPDATES.md`:

```bash
# Archive entries older than 90 days
mv TECH_UPDATES.md TECH_UPDATES_$(date +%Y%m%d).md
```

### Monitor the Monitor

Check if scheduled task is running:

```batch
# Windows
schtasks /query /tn "BlenDAZ_Tech_Monitor"

# Linux/Mac
crontab -l
```

---

## Troubleshooting

### "Python not found"
- Add Python to PATH
- Or specify full path in scheduler

### "Module not found: feedparser"
```bash
pip install feedparser requests
```

### No updates appearing
- Check `monitor_state.json` - delete to force re-check
- Verify internet connection
- Check source URLs are still valid

### Rate limiting (GitHub API)
- GitHub API: 60 requests/hour (unauthenticated)
- Add GitHub token for 5000 requests/hour
- See: https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting

---

## Future Enhancements

- [ ] Discord/Slack webhooks for instant notifications
- [ ] AI summarization of updates (using Claude API)
- [ ] Keyword relevance scoring
- [ ] Email digest reports
- [ ] Web dashboard
- [ ] Integration with TODO.md (auto-create tasks)
- [ ] Detect breaking changes automatically
- [ ] Community contribution tracking

---

## Resources

**Diffeomorphic:**
- GitHub: https://github.com/diffeomorphic/daz_importer
- Documentation: http://diffeomorphic.blogspot.com

**Blender:**
- Developer Blog: https://code.blender.org/
- Animation Module: https://projects.blender.org/blender/blender/src/branch/main/source/blender/animrig

**DAZ:**
- Forums: https://www.daz3d.com/forums/
- SDK Docs: https://docs.daz3d.com/

---

**Last Updated**: 2026-02-19
