import subprocess
import json
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

def parse_gh_timestamp(ts_string: str) -> Optional[datetime]:
    """Parse a GitHub ISO 8601 timestamp safely across Python versions.
    Replaces 'Z' with '+00:00' for pre-3.11 compatibility."""
    if not ts_string:
        return None
    try:
        safe_string = ts_string.replace("Z", "+00:00")
        return datetime.fromisoformat(safe_string)
    except (ValueError, TypeError):
        return None

def run_github_api(url: str) -> dict:
    """Execute a curl command to GitHub REST API and return parsed JSON."""
    cmd = ["curl", "-s", "-H", "Accept: application/vnd.github+json", url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        print(f"API Error for {url}: {e}")
        return {}

def fetch_search_results(query: str, per_page: int = 100, max_pages: int = 10) -> List[Dict[str, Any]]:
    """Fetch all results from GitHub Search API with pagination.
    GitHub Search API returns max 1000 results total."""
    all_items = []
    page = 1
    while page <= max_pages:
        url = f"https://api.github.com/search/issues?q={query}&per_page={per_page}&page={page}"
        data = run_github_api(url)
        if not data or "items" not in data:
            break
        items = data["items"]
        all_items.extend(items)
        total_count = data.get("total_count", 0)
        if len(all_items) >= total_count or len(items) < per_page:
            break
        page += 1
        time.sleep(1)  # Rate limiting
    return all_items

def fetch_prs(repo: str, date_start: str, date_end: str) -> List[Dict[str, Any]]:
    """Fetch all PRs created in the given date range.
    Uses GitHub Search API via curl.
    Returns list of PR dicts with full details."""
    query = f"repo:{repo}+type:pr+created:{date_start}..{date_end}"
    items = fetch_search_results(query)
    
    # Enrich with PR-specific data (merge info)
    enriched = []
    for item in items:
        pr_number = item["number"]
        # Fetch individual PR for merge details
        pr_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
        pr_detail = run_github_api(pr_url)
        if pr_detail:
            enriched.append(pr_detail)
        else:
            enriched.append(item)
        time.sleep(0.5)  # Rate limiting
    return enriched

def fetch_prs_fast(repo: str, date_start: str, date_end: str) -> List[Dict[str, Any]]:
    """Fetch all PRs created in the given date range using search API.
    Then fetch individual PR details for merge timestamps.
    Optimized: fetches PR details only for those that appear merged/closed."""
    query = f"repo:{repo}+type:pr+created:{date_start}..{date_end}"
    search_items = fetch_search_results(query)
    
    pr_numbers = [item["number"] for item in search_items]
    print(f"Found {len(pr_numbers)} PRs via search. Fetching details...")
    
    enriched = []
    for i, num in enumerate(pr_numbers):
        pr_url = f"https://api.github.com/repos/{repo}/pulls/{num}"
        pr_detail = run_github_api(pr_url)
        if pr_detail and "number" in pr_detail:
            enriched.append(pr_detail)
        if (i + 1) % 10 == 0:
            print(f"  Fetched {i+1}/{len(pr_numbers)} PR details")
            time.sleep(1)  # Rate limiting pause every 10 requests
        else:
            time.sleep(0.3)
    return enriched

def fetch_issues(repo: str, date_start: str, date_end: str) -> List[Dict[str, Any]]:
    """Fetch all issues (not PRs) created in the given date range.
    Uses GitHub Search API via curl."""
    query = f"repo:{repo}+type:issue+created:{date_start}..{date_end}"
    items = fetch_search_results(query)
    return items

def fetch_issues_with_labels(repo: str, date_start: str, date_end: str) -> List[Dict[str, Any]]:
    """Fetch all issues created in the given date range.
    Labels are included in search results."""
    query = f"repo:{repo}+type:issue+created:{date_start}..{date_end}"
    items = fetch_search_results(query)
    return items
