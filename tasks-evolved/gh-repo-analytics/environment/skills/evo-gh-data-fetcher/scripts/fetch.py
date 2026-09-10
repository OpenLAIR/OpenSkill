import subprocess
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# Default fields for PR queries
PR_FIELDS = ["number", "state", "createdAt", "mergedAt", "closedAt", "author", "labels"]

# Default fields for issue queries
ISSUE_FIELDS = ["number", "state", "createdAt", "closedAt", "author", "labels"]


def parse_gh_timestamp(ts_string: Optional[str]) -> Optional[datetime]:
    """Safely parse an ISO 8601 timestamp from gh CLI output.
    
    GitHub returns timestamps like '2024-12-15T10:30:00Z'.
    We replace the Z suffix with +00:00 for broad Python version compatibility,
    though Python 3.11+ handles Z natively.
    
    Args:
        ts_string: ISO 8601 timestamp string, or None/empty
        
    Returns:
        datetime object with UTC timezone, or None if input is empty/invalid
    """
    if not ts_string:
        return None
    try:
        safe_string = ts_string.replace("Z", "+00:00")
        return datetime.fromisoformat(safe_string)
    except (ValueError, AttributeError) as e:
        print(f"Warning: Could not parse timestamp '{ts_string}': {e}")
        return None


def run_gh_command(command_parts: List[str]) -> List[Dict[str, Any]]:
    """Execute a gh CLI command and return parsed JSON output.
    
    Args:
        command_parts: List of command arguments (e.g., ['gh', 'pr', 'list', ...])
        
    Returns:
        List of dictionaries parsed from JSON output, or empty list on error
    """
    try:
        result = subprocess.run(
            command_parts,
            capture_output=True,
            text=True,
            check=True
        )
        if not result.stdout.strip():
            return []
        data = json.loads(result.stdout)
        return data if isinstance(data, list) else [data]
    except subprocess.CalledProcessError as e:
        print(f"Error executing gh CLI: {e}")
        print(f"Command: {' '.join(command_parts)}")
        print(f"STDERR: {e.stderr}")
        return []
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON output: {e}")
        return []


def fetch_prs(
    repo: str,
    date_range: str,
    state: str = "all",
    limit: int = 1000,
    fields: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Fetch pull request data from a GitHub repository.
    
    Uses gh pr list with --search for date filtering and --json for structured output.
    The --search flag routes through GitHub Search API (max 1000 results).
    
    Args:
        repo: Repository in 'owner/name' format (e.g., 'cli/cli')
        date_range: Date range string (e.g., '2024-12-01..2024-12-31')
        state: PR state filter - 'all', 'open', 'closed', 'merged'
        limit: Maximum results to return (capped at 1000 by Search API)
        fields: JSON fields to request (defaults to PR_FIELDS)
        
    Returns:
        List of PR dictionaries with requested fields
    """
    if fields is None:
        fields = PR_FIELDS
    
    # Cap limit at 1000 due to GitHub Search API constraint
    if limit > 1000:
        print("Warning: GitHub Search API caps at 1000 results. Limiting to 1000.")
        limit = 1000
    
    search_query = f"created:{date_range}"
    
    command = [
        "gh", "pr", "list",
        "--repo", repo,
        "--search", search_query,
        "--state", state,
        "--limit", str(limit),
        "--json", ",".join(fields)
    ]
    
    print(f"Fetching PRs from {repo} for {date_range} (state={state}, limit={limit})...")
    data = run_gh_command(command)
    print(f"Retrieved {len(data)} PRs.")
    return data


def fetch_issues(
    repo: str,
    date_range: str,
    state: str = "all",
    limit: int = 1000,
    fields: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Fetch issue data from a GitHub repository.
    
    Uses gh issue list with --search for date filtering and --json for structured output.
    Note: Issues only have 'open' and 'closed' states (no 'merged').
    
    Args:
        repo: Repository in 'owner/name' format (e.g., 'cli/cli')
        date_range: Date range string (e.g., '2024-12-01..2024-12-31')
        state: Issue state filter - 'all', 'open', 'closed'
        limit: Maximum results to return (capped at 1000 by Search API)
        fields: JSON fields to request (defaults to ISSUE_FIELDS)
        
    Returns:
        List of issue dictionaries with requested fields
    """
    if fields is None:
        fields = ISSUE_FIELDS
    
    if limit > 1000:
        print("Warning: GitHub Search API caps at 1000 results. Limiting to 1000.")
        limit = 1000
    
    search_query = f"created:{date_range}"
    
    command = [
        "gh", "issue", "list",
        "--repo", repo,
        "--search", search_query,
        "--state", state,
        "--limit", str(limit),
        "--json", ",".join(fields)
    ]
    
    print(f"Fetching issues from {repo} for {date_range} (state={state}, limit={limit})...")
    data = run_gh_command(command)
    print(f"Retrieved {len(data)} issues.")
    return data
