import json
import sys
import os
from datetime import datetime, timezone
from collections import Counter
from typing import List, Dict, Any, Optional, Tuple

# Add parent skills directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'evo-gh-data-fetcher'))
from scripts.fetch import parse_gh_timestamp


def compute_pr_metrics(prs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute pull request metrics from raw PR data.
    
    Counts PRs by state (OPEN, CLOSED, MERGED) and calculates
    average time-to-merge for merged PRs.
    
    Args:
        prs: List of PR dictionaries with state, createdAt, mergedAt fields
        
    Returns:
        Dictionary with total, merged, closed, open counts and avg_time_to_merge_days
    """
    total = len(prs)
    merged = 0
    closed = 0
    open_count = 0
    merge_times = []
    
    for pr in prs:
        state = pr.get("state", "").upper()
        
        if state == "MERGED":
            merged += 1
            # Calculate time to merge
            created = parse_gh_timestamp(pr.get("createdAt"))
            merged_at = parse_gh_timestamp(pr.get("mergedAt"))
            if created and merged_at:
                delta_days = (merged_at - created).total_seconds() / (24 * 3600)
                merge_times.append(delta_days)
        elif state == "CLOSED":
            closed += 1
        elif state == "OPEN":
            open_count += 1
    
    avg_merge_days = round(sum(merge_times) / len(merge_times), 2) if merge_times else 0.0
    
    return {
        "total": total,
        "merged": merged,
        "closed": closed,
        "open": open_count,
        "avg_time_to_merge_days": avg_merge_days
    }


def identify_top_contributor(prs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Find the author with the most PRs.
    
    Extracts author.login from each PR and counts occurrences.
    
    Args:
        prs: List of PR dictionaries with author field
        
    Returns:
        Dictionary with login and count of the top contributor,
        or empty dict if no authors found
    """
    author_counts = Counter()
    
    for pr in prs:
        author_data = pr.get("author")
        if author_data and isinstance(author_data, dict):
            login = author_data.get("login")
            if login:
                author_counts[login] += 1
    
    if not author_counts:
        return {"login": "unknown", "count": 0}
    
    top_login, top_count = author_counts.most_common(1)[0]
    return {"login": top_login, "count": top_count}


def is_bug_issue(issue: Dict[str, Any]) -> bool:
    """Check if an issue has a bug-related label.
    
    Uses case-insensitive substring matching for 'bug' in label names.
    
    Args:
        issue: Issue dictionary with labels field
        
    Returns:
        True if any label name contains 'bug'
    """
    labels = issue.get("labels", [])
    for label in labels:
        label_name = label.get("name", "").lower()
        if "bug" in label_name:
            return True
    return False


def compute_issue_metrics(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute issue metrics from raw issue data.
    
    Counts total issues, bug-labeled issues, and resolved (closed) bugs.
    
    Args:
        issues: List of issue dictionaries with state and labels fields
        
    Returns:
        Dictionary with total, bugs, and resolved_bugs counts
    """
    total = len(issues)
    bugs = 0
    resolved_bugs = 0
    
    for issue in issues:
        if is_bug_issue(issue):
            bugs += 1
            state = issue.get("state", "").upper()
            if state == "CLOSED":
                resolved_bugs += 1
    
    return {
        "total": total,
        "bugs": bugs,
        "resolved_bugs": resolved_bugs
    }


def generate_report(
    prs: List[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    output_path: str,
    repo: str = "cli/cli",
    period: str = "2024-12-01..2024-12-31"
) -> Dict[str, Any]:
    """Generate a complete metrics report and write to JSON file.
    
    Orchestrates all metric computations and serializes results.
    
    Args:
        prs: List of PR dictionaries
        issues: List of issue dictionaries
        output_path: Path to write report.json
        repo: Repository name for the report
        period: Date period string for the report
        
    Returns:
        The complete report dictionary
    """
    pr_metrics = compute_pr_metrics(prs)
    top_contributor = identify_top_contributor(prs)
    issue_metrics = compute_issue_metrics(issues)
    
    report = {
        "repo": repo,
        "period": period,
        "pull_requests": {
            **pr_metrics,
            "top_contributor": top_contributor
        },
        "issues": issue_metrics
    }
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"Report written to {output_path}")
    return report
