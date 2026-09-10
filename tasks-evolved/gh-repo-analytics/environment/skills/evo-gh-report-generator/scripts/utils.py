import json
from datetime import datetime, timezone
from collections import Counter
from typing import List, Dict, Any, Optional

def parse_gh_timestamp(ts_string: str) -> Optional[datetime]:
    """Parse a GitHub ISO 8601 timestamp safely."""
    if not ts_string:
        return None
    try:
        safe_string = ts_string.replace("Z", "+00:00")
        return datetime.fromisoformat(safe_string)
    except (ValueError, TypeError):
        return None

def is_bug_issue(issue_data: dict) -> bool:
    """Check if an issue has any label containing the substring 'bug' (case-insensitive)."""
    labels = issue_data.get("labels", [])
    for label in labels:
        label_name = label.get("name", "").lower()
        if "bug" in label_name:
            return True
    return False

def is_closed_during_period(item: dict, date_start: str, date_end: str) -> bool:
    """Check if an item was closed during the specified date period.
    date_start and date_end are YYYY-MM-DD strings."""
    closed_at_str = item.get("closed_at", "")
    if not closed_at_str:
        return False
    closed_at = parse_gh_timestamp(closed_at_str)
    if not closed_at:
        return False
    start = datetime.fromisoformat(f"{date_start}T00:00:00+00:00")
    end = datetime.fromisoformat(f"{date_end}T23:59:59+00:00")
    return start <= closed_at <= end

def identify_top_contributor(prs: List[Dict[str, Any]]) -> str:
    """Find the person who opened the most PRs.
    Returns the login of the top contributor."""
    author_counts = Counter()
    for pr in prs:
        # REST API uses 'user' field with 'login' key
        user = pr.get("user") or pr.get("author")
        if user and isinstance(user, dict):
            login = user.get("login", "")
            if login:
                author_counts[login] += 1
    if not author_counts:
        return ""
    top = author_counts.most_common(1)[0]
    return top[0]

def compute_pr_metrics(prs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute PR metrics from a list of PR data dicts.
    
    PR data from GitHub REST API has:
    - state: 'open' or 'closed'
    - merged: boolean (true if merged)
    - created_at: ISO 8601 timestamp
    - merged_at: ISO 8601 timestamp or null
    
    'merged' and 'closed' report current state as of today:
    - merged: PRs where merged == True
    - closed: PRs where state == 'closed' and merged == False
    
    Returns dict with: total, merged, closed, avg_merge_days, top_contributor
    """
    total = len(prs)
    merged_count = 0
    closed_count = 0  # closed without merging
    merge_durations = []
    
    for pr in prs:
        is_merged = pr.get("merged", False)
        state = pr.get("state", "").lower()
        
        if is_merged:
            merged_count += 1
            created = parse_gh_timestamp(pr.get("created_at"))
            merged_at = parse_gh_timestamp(pr.get("merged_at"))
            if created and merged_at:
                delta_days = (merged_at - created).total_seconds() / (24 * 3600)
                merge_durations.append(delta_days)
        elif state == "closed":
            closed_count += 1
    
    # Average merge days, rounded to 1 decimal
    if merge_durations:
        avg_merge_days = round(sum(merge_durations) / len(merge_durations), 1)
    else:
        avg_merge_days = 0.0
    
    top_contributor = identify_top_contributor(prs)
    
    return {
        "total": total,
        "merged": merged_count,
        "closed": closed_count,
        "avg_merge_days": avg_merge_days,
        "top_contributor": top_contributor
    }

def compute_issue_metrics(issues: List[Dict[str, Any]], date_start: str = "2024-12-01", date_end: str = "2024-12-31") -> Dict[str, Any]:
    """Compute issue metrics from a list of issue data dicts.
    
    Returns dict with: total, bug, resolved_bugs
    - bug: issues where at least one label contains substring 'bug'
    - resolved_bugs: bug issues that were closed DURING the month
      (closed_at is within date_start..date_end)
    """
    total = len(issues)
    bug_count = 0
    resolved_bugs = 0
    
    for issue in issues:
        if is_bug_issue(issue):
            bug_count += 1
            if is_closed_during_period(issue, date_start, date_end):
                resolved_bugs += 1
    
    return {
        "total": total,
        "bug": bug_count,
        "resolved_bugs": resolved_bugs
    }

def generate_report(pr_metrics: Dict[str, Any], issue_metrics: Dict[str, Any], output_path: str = "/app/report.json") -> Dict[str, Any]:
    """Generate the final report.json file."""
    report = {
        "pr": pr_metrics,
        "issue": issue_metrics
    }
    
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"Report written to {output_path}")
    print(json.dumps(report, indent=2))
    return report
