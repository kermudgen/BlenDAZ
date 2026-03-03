"""
BlenDAZ Documentation Audit

Daily automated check to streamline project documentation:
- CLAUDE.md: Keep concise for AI context efficiency
- Identify redundant or outdated content
- Suggest content relocation to appropriate documents
- Generate actionable recommendations

Run this script daily to maintain lean, efficient documentation.
"""

import os
from pathlib import Path
from datetime import datetime
import re


# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
AUDIT_REPORT = PROJECT_ROOT / "reports" / "DOCS_AUDIT_REPORT.md"

# Target documents to audit
DOCS_TO_AUDIT = {
    'CLAUDE.md': {
        'max_lines': 500,  # Flag if exceeds this
        'max_size_kb': 50,  # Flag if exceeds this
        'priority': 'high',  # High priority to keep lean for AI context
    },
    'TODO.md': {
        'max_lines': 300,
        'max_size_kb': 30,
        'priority': 'medium',
    },
    'README.md': {
        'max_lines': 200,
        'max_size_kb': 20,
        'priority': 'medium',
    },
    'MONITORING_README.md': {
        'max_lines': 400,
        'max_size_kb': 40,
        'priority': 'low',
    },
}

# Content patterns that suggest relocation
RELOCATION_PATTERNS = {
    'TODO.md': [
        r'\[ \]',  # Unchecked checkboxes
        r'TODO:',
        r'FIXME:',
        r'@TODO',
    ],
    'ARCHITECTURE.md': [
        r'architecture',
        r'design pattern',
        r'class diagram',
        r'system overview',
    ],
    'CHANGELOG.md': [
        r'version \d+\.\d+',
        r'released on',
        r'changes in',
        r'## \d{4}-\d{2}-\d{2}',  # Date headers
    ],
    'ISSUES.md': [
        r'known issue',
        r'bug:',
        r'problem:',
        r'limitation:',
    ],
}


# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

def analyze_document(doc_path, config):
    """Analyze a single document for streamlining opportunities"""
    if not doc_path.exists():
        return None

    with open(doc_path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')

    file_size_kb = len(content.encode('utf-8')) / 1024
    line_count = len(lines)

    issues = []
    suggestions = []

    # Check size thresholds
    if line_count > config['max_lines']:
        issues.append(f"[SIZE] Line count ({line_count}) exceeds recommended max ({config['max_lines']})")
        suggestions.append("Consider breaking into multiple documents or removing outdated sections")

    if file_size_kb > config['max_size_kb']:
        issues.append(f"[SIZE] File size ({file_size_kb:.1f}KB) exceeds recommended max ({config['max_size_kb']}KB)")
        suggestions.append("Consider moving detailed content to separate files")

    # Check for duplicate headers
    headers = [line for line in lines if line.startswith('#')]
    header_counts = {}
    for header in headers:
        header_counts[header] = header_counts.get(header, 0) + 1

    duplicates = {h: c for h, c in header_counts.items() if c > 1}
    if duplicates:
        issues.append(f"[DUPLICATE] Duplicate headers found: {list(duplicates.keys())}")
        suggestions.append("Consolidate or rename duplicate sections")

    # Check for outdated dates (older than 6 months)
    date_pattern = r'\d{4}-\d{2}-\d{2}'
    dates = re.findall(date_pattern, content)
    if dates:
        # Check if any dates are old
        old_dates = []
        for date_str in dates:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d')
                age_days = (datetime.now() - date).days
                if age_days > 180:  # 6 months
                    old_dates.append((date_str, age_days))
            except:
                pass

        if old_dates:
            issues.append(f"[DATED] Contains old dated content: {len(old_dates)} entries older than 6 months")
            suggestions.append("Review and archive or remove outdated dated content")

    # Check for content that should be relocated
    relocation_suggestions = check_relocation_opportunities(content, doc_path.name)
    if relocation_suggestions:
        issues.extend(relocation_suggestions)

    # Check for verbose patterns
    verbose_patterns = [
        (r'(?i)(very detailed|comprehensive guide|complete list|full documentation)',
         "Contains verbose language - consider condensing"),
        (r'```[\s\S]{500,}```',
         "Contains large code blocks - consider linking to source files instead"),
        (r'(\n\n\n+)',
         "Contains excessive whitespace"),
    ]

    for pattern, suggestion in verbose_patterns:
        if re.search(pattern, content):
            if suggestion not in suggestions:
                suggestions.append(suggestion)

    return {
        'path': doc_path,
        'line_count': line_count,
        'size_kb': file_size_kb,
        'priority': config['priority'],
        'issues': issues,
        'suggestions': suggestions,
        'health_score': calculate_health_score(line_count, file_size_kb, config, len(issues))
    }


def check_relocation_opportunities(content, current_doc):
    """Check if content should be relocated to a different document"""
    suggestions = []

    for target_doc, patterns in RELOCATION_PATTERNS.items():
        if target_doc == current_doc:
            continue

        matches = []
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                matches.append(pattern)

        if matches:
            suggestions.append(
                f"[RELOCATE] Content matches {target_doc} patterns: {len(matches)} occurrences. "
                f"Consider moving to {target_doc}"
            )

    return suggestions


def calculate_health_score(line_count, size_kb, config, issue_count):
    """Calculate document health score (0-100)"""
    # Start at 100
    score = 100

    # Deduct for exceeding size limits
    if line_count > config['max_lines']:
        overage = (line_count - config['max_lines']) / config['max_lines']
        score -= min(30, overage * 30)

    if size_kb > config['max_size_kb']:
        overage = (size_kb - config['max_size_kb']) / config['max_size_kb']
        score -= min(30, overage * 30)

    # Deduct for issues
    score -= min(40, issue_count * 10)

    return max(0, int(score))


def analyze_claude_md_specifics(doc_path):
    """Special analysis for CLAUDE.md - AI context efficiency"""
    if not doc_path.exists():
        return []

    with open(doc_path, 'r', encoding='utf-8') as f:
        content = f.read()

    specific_issues = []

    # Check for redundant "how to use" sections
    how_to_count = len(re.findall(r'(?i)(how to|usage|getting started)', content))
    if how_to_count > 3:
        specific_issues.append(
            f"[WARNING] Multiple 'how to' sections ({how_to_count}) - consolidate into single Usage section"
        )

    # Check for embedded code that should reference files
    large_code_blocks = re.findall(r'```[\s\S]{300,}?```', content)
    if large_code_blocks:
        specific_issues.append(
            f"[WARNING] Contains {len(large_code_blocks)} large code blocks - "
            f"replace with file references (e.g., 'See daz_bone_select.py:123-145')"
        )

    # Check for overly detailed technical explanations
    technical_words = ['algorithm', 'implementation', 'specifically', 'detailed', 'comprehensive']
    technical_density = sum(len(re.findall(rf'\b{word}\b', content, re.IGNORECASE)) for word in technical_words)
    if technical_density > 20:
        specific_issues.append(
            f"[WARNING] High technical density ({technical_density} occurrences) - "
            f"move detailed explanations to separate ARCHITECTURE.md or code comments"
        )

    # Check for historical context that's outdated
    if re.search(r'(?i)(originally|previously|old version|deprecated)', content):
        specific_issues.append(
            "[WARNING] Contains historical context - consider moving to CHANGELOG.md or removing"
        )

    return specific_issues


# ============================================================================
# REPORT GENERATION
# ============================================================================

def generate_audit_report(analyses):
    """Generate markdown audit report"""
    report = f"# Documentation Audit Report\n\n"
    report += f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    report += "---\n\n"

    # Summary
    total_docs = len(analyses)
    unhealthy_docs = [a for a in analyses if a and a['health_score'] < 70]

    report += "## Summary\n\n"
    report += f"- **Documents Audited**: {total_docs}\n"
    report += f"- **Needing Attention**: {len(unhealthy_docs)}\n"
    report += f"- **Overall Health**: {'[OK] Good' if len(unhealthy_docs) == 0 else '[WARNING] Needs Attention'}\n\n"

    # Priority documents
    report += "## Priority: CLAUDE.md Analysis\n\n"
    claude_analysis = next((a for a in analyses if a and a['path'].name == 'CLAUDE.md'), None)

    if claude_analysis:
        report += f"**Health Score**: {claude_analysis['health_score']}/100 "
        report += f"{'[OK]' if claude_analysis['health_score'] >= 80 else '[WARNING]' if claude_analysis['health_score'] >= 60 else '[ERROR]'}\n\n"
        report += f"- **Size**: {claude_analysis['line_count']} lines ({claude_analysis['size_kb']:.1f}KB)\n"
        report += f"- **Issues Found**: {len(claude_analysis['issues'])}\n\n"

        # CLAUDE.md specific issues
        claude_md_path = PROJECT_ROOT / 'CLAUDE.md'
        specific_issues = analyze_claude_md_specifics(claude_md_path)

        if claude_analysis['issues'] or specific_issues:
            report += "### Issues\n\n"
            for issue in claude_analysis['issues'] + specific_issues:
                report += f"- {issue}\n"
            report += "\n"

        if claude_analysis['suggestions']:
            report += "### Recommendations\n\n"
            for suggestion in claude_analysis['suggestions']:
                report += f"- {suggestion}\n"
            report += "\n"
    else:
        report += "*CLAUDE.md not found*\n\n"

    # Other documents
    report += "## All Documents\n\n"

    for analysis in sorted(analyses, key=lambda a: a['health_score'] if a else 100):
        if not analysis or analysis['path'].name == 'CLAUDE.md':
            continue

        report += f"### {analysis['path'].name}\n\n"
        report += f"**Health Score**: {analysis['health_score']}/100 "
        report += f"{'[OK]' if analysis['health_score'] >= 80 else '[WARNING]' if analysis['health_score'] >= 60 else '[ERROR]'}\n\n"
        report += f"- **Size**: {analysis['line_count']} lines ({analysis['size_kb']:.1f}KB)\n"
        report += f"- **Priority**: {analysis['priority'].title()}\n"

        if analysis['issues']:
            report += f"- **Issues**: {len(analysis['issues'])}\n\n"
            for issue in analysis['issues']:
                report += f"  - {issue}\n"
            report += "\n"

        if analysis['suggestions']:
            report += "**Suggestions**:\n"
            for suggestion in analysis['suggestions']:
                report += f"- {suggestion}\n"
            report += "\n"

        report += "---\n\n"

    # Action items
    report += "## Action Items\n\n"

    action_items = []
    for analysis in analyses:
        if not analysis:
            continue
        if analysis['health_score'] < 70:
            action_items.append(f"- [ ] Review and streamline `{analysis['path'].name}` (score: {analysis['health_score']}/100)")

    if action_items:
        report += "\n".join(action_items)
        report += "\n"
    else:
        report += "*No immediate actions required* [OK]\n"

    return report


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run documentation audit"""
    print("=== BlenDAZ Documentation Audit ===")
    print(f"Running audit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    analyses = []

    for doc_name, config in DOCS_TO_AUDIT.items():
        doc_path = PROJECT_ROOT / 'docs' / doc_name
        print(f"Analyzing: {doc_name}...")

        analysis = analyze_document(doc_path, config)
        if analysis:
            analyses.append(analysis)
            score_emoji = '[OK]' if analysis['health_score'] >= 80 else '[WARNING]' if analysis['health_score'] >= 60 else '[ERROR]'
            print(f"  {score_emoji} Health Score: {analysis['health_score']}/100")
            if analysis['issues']:
                print(f"  [WARNING] {len(analysis['issues'])} issues found")
        else:
            print(f"  - Not found, skipping")
        print()

    # Generate report
    report = generate_audit_report(analyses)

    with open(AUDIT_REPORT, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"[OK] Audit complete! Report saved to: {AUDIT_REPORT}")

    # Print summary
    unhealthy_count = sum(1 for a in analyses if a['health_score'] < 70)
    if unhealthy_count > 0:
        print(f"\n[WARNING] {unhealthy_count} document(s) need attention. Review {AUDIT_REPORT} for details.")
    else:
        print("\n[OK] All documents are healthy!")


if __name__ == "__main__":
    main()
