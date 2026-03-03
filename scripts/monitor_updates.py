"""
BlenDAZ Technology Monitor

Scheduled web scraper to track updates from:
- Diffeomorphic DAZ Importer
- Rig on the Fly
- Blender rigging/animation developments
- Related rigging technologies

Run this script periodically (daily/weekly) to stay current.
"""

import requests
import json
from datetime import datetime
from pathlib import Path


# ============================================================================
# CONFIGURATION
# ============================================================================

SOURCES = {
    'diffeomorphic_github': {
        'url': 'https://api.github.com/repos/Diffeomorphic/import-daz/commits',
        'type': 'github_commits',
        'keywords': ['rotation', 'limit', 'constraint', 'ik', 'bone', 'rig'],
    },
    'diffeomorphic_releases': {
        'url': 'https://api.github.com/repos/Diffeomorphic/import-daz/releases',
        'type': 'github_releases',
        'keywords': [],  # Track all releases
    },
    'diffeomorphic_issues': {
        'url': 'https://api.github.com/repos/Diffeomorphic/import-daz/issues?state=all&per_page=10',
        'type': 'github_issues',
        'keywords': ['rotation', 'limit', 'constraint', 'ik', 'pose', 'rig'],
    },
    'diffeomorphic_blog': {
        'url': 'https://diffeomorphic.blogspot.com/feeds/posts/default',  # RSS feed
        'type': 'rss',
        'keywords': ['rotation', 'limit', 'constraint', 'ik', 'bone', 'rig', 'genesis'],
    },
    'blender_dev_blog': {
        'url': 'https://code.blender.org/feed/',  # RSS feed
        'type': 'rss',
        'keywords': ['rigging', 'animation', 'armature', 'constraint', 'ik'],
    },
    # X.com accounts via Nitter RSS bridges
    'x_bproduction3d': {
        'url': 'https://nitter.net/Bproduction3d/rss',
        'type': 'rss',
        'keywords': ['blender', 'daz', 'rigging', 'animation', 'ik', 'constraint', 'genesis', 'diffeomorphic'],
    },
    'x_ryanlykos': {
        'url': 'https://nitter.net/RyanLykos/rss',
        'type': 'rss',
        'keywords': ['blender', 'daz', 'rigging', 'animation', 'ik', 'constraint', 'genesis', 'diffeomorphic'],
    },
    'x_adrianodelfinoc': {
        'url': 'https://nitter.net/adrianodelfinoc/rss',
        'type': 'rss',
        'keywords': ['blender', 'daz', 'rigging', 'animation', 'ik', 'constraint', 'genesis', 'diffeomorphic'],
    },
    'x_frigawestudios': {
        'url': 'https://nitter.net/fRigAweStudios/rss',
        'type': 'rss',
        'keywords': ['blender', 'daz', 'rigging', 'animation', 'ik', 'constraint', 'genesis', 'diffeomorphic'],
    },
    'x_vieleanimations': {
        'url': 'https://nitter.net/vieleanimations/rss',
        'type': 'rss',
        'keywords': ['blender', 'daz', 'rigging', 'animation', 'ik', 'constraint', 'genesis', 'diffeomorphic'],
    },
    'x_superhivemarket': {
        'url': 'https://nitter.net/superhivemarket/rss',
        'type': 'rss',
        'keywords': ['blender', 'daz', 'rigging', 'animation', 'ik', 'constraint', 'genesis', 'diffeomorphic'],
    },
}

# File to store monitoring state
STATE_FILE = Path(__file__).parent.parent / "reports" / "monitor_state.json"
UPDATES_FILE = Path(__file__).parent.parent / "reports" / "TECH_UPDATES.md"


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

def load_state():
    """Load last check timestamps"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_state(state):
    """Save check timestamps"""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


# ============================================================================
# FETCHERS
# ============================================================================

def fetch_github_commits(url, keywords):
    """Fetch recent GitHub commits"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        commits = response.json()

        updates = []
        for commit in commits[:10]:  # Last 10 commits
            message = commit['commit']['message'].lower()

            # Check if any keyword matches
            if any(keyword in message for keyword in keywords) or not keywords:
                updates.append({
                    'title': commit['commit']['message'].split('\n')[0],
                    'description': commit['commit']['message'],
                    'url': commit['html_url'],
                    'date': commit['commit']['author']['date'],
                    'author': commit['commit']['author']['name'],
                })

        return updates
    except Exception as e:
        print(f"Error fetching commits: {e}")
        return []


def fetch_github_releases(url, keywords):
    """Fetch recent GitHub releases"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        releases = response.json()

        updates = []
        for release in releases[:5]:  # Last 5 releases
            updates.append({
                'title': f"Release: {release['tag_name']} - {release['name']}",
                'description': release['body'][:500] if release['body'] else '',
                'url': release['html_url'],
                'date': release['published_at'],
                'author': release['author']['login'],
            })

        return updates
    except Exception as e:
        print(f"Error fetching releases: {e}")
        return []


def fetch_github_issues(url, keywords):
    """Fetch recent GitHub issues"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        issues = response.json()

        updates = []
        for issue in issues:
            title = issue['title'].lower()
            body = (issue['body'] or '').lower()

            # Check if any keyword matches
            if any(keyword in title or keyword in body for keyword in keywords):
                updates.append({
                    'title': f"Issue #{issue['number']}: {issue['title']}",
                    'description': (issue['body'] or '')[:300],
                    'url': issue['html_url'],
                    'date': issue['updated_at'],
                    'author': issue['user']['login'],
                    'state': issue['state'],
                })

        return updates
    except Exception as e:
        print(f"Error fetching issues: {e}")
        return []


def fetch_rss(url, keywords):
    """Fetch RSS feed (requires feedparser)"""
    try:
        import feedparser
        feed = feedparser.parse(url)

        updates = []
        for entry in feed.entries[:10]:
            content = (entry.get('summary', '') + entry.get('title', '')).lower()

            # Check if any keyword matches
            if any(keyword in content for keyword in keywords) or not keywords:
                updates.append({
                    'title': entry.title,
                    'description': entry.get('summary', '')[:500],
                    'url': entry.link,
                    'date': entry.get('published', ''),
                    'author': entry.get('author', 'Unknown'),
                })

        return updates
    except ImportError:
        print("feedparser not installed. Install with: pip install feedparser")
        return []
    except Exception as e:
        print(f"Error fetching RSS: {e}")
        return []


# ============================================================================
# UPDATE CHECKING
# ============================================================================

def check_updates():
    """Check all sources for updates"""
    print("=== BlenDAZ Technology Monitor ===")
    print(f"Checking for updates: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    state = load_state()
    all_updates = {}

    for source_name, config in SOURCES.items():
        print(f"Checking: {source_name}...")

        # Fetch updates based on type
        if config['type'] == 'github_commits':
            updates = fetch_github_commits(config['url'], config['keywords'])
        elif config['type'] == 'github_releases':
            updates = fetch_github_releases(config['url'], config['keywords'])
        elif config['type'] == 'github_issues':
            updates = fetch_github_issues(config['url'], config['keywords'])
        elif config['type'] == 'rss':
            updates = fetch_rss(config['url'], config['keywords'])
        else:
            updates = []

        # Filter out updates we've already seen
        last_check = state.get(source_name, {}).get('last_date', '')
        new_updates = [u for u in updates if u['date'] > last_check]

        if new_updates:
            all_updates[source_name] = new_updates
            # Update state with most recent date
            state[source_name] = {
                'last_check': datetime.now().isoformat(),
                'last_date': max(u['date'] for u in updates)
            }
            print(f"  OK Found {len(new_updates)} new updates")
        else:
            print(f"  - No new updates")

    save_state(state)
    return all_updates


def write_updates_markdown(updates):
    """Write updates to TECH_UPDATES.md"""
    if not updates:
        print("\nNo new updates to write.")
        return

    print(f"\nWriting {sum(len(u) for u in updates.values())} updates to {UPDATES_FILE}...")

    # Read existing content
    existing_content = ""
    if UPDATES_FILE.exists():
        with open(UPDATES_FILE, 'r', encoding='utf-8') as f:
            existing_content = f.read()

    # Prepare new content
    new_content = f"# Technology Updates\n\n"
    new_content += f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    new_content += "---\n\n"

    # Add new updates
    for source_name, source_updates in updates.items():
        new_content += f"## {source_name.replace('_', ' ').title()}\n\n"

        for update in source_updates:
            new_content += f"### {update['title']}\n\n"
            new_content += f"**Date**: {update['date']}\n"
            new_content += f"**Author**: {update['author']}\n"
            if 'state' in update:
                new_content += f"**State**: {update['state']}\n"
            new_content += f"**Link**: [{update['url']}]({update['url']})\n\n"
            if update['description']:
                new_content += f"{update['description']}\n\n"
            new_content += "---\n\n"

    # Append to existing or create new
    if existing_content:
        # Insert new updates after header
        parts = existing_content.split('---\n\n', 1)
        if len(parts) > 1:
            final_content = new_content + parts[1]
        else:
            final_content = new_content + existing_content
    else:
        final_content = new_content

    with open(UPDATES_FILE, 'w', encoding='utf-8') as f:
        f.write(final_content)

    print(f"OK Updates written to {UPDATES_FILE}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run the update checker"""
    updates = check_updates()
    write_updates_markdown(updates)

    print("\n=== Summary ===")
    total = sum(len(u) for u in updates.values())
    print(f"Total new updates: {total}")

    if total > 0:
        print(f"\nReview updates in: {UPDATES_FILE}")


if __name__ == "__main__":
    main()
